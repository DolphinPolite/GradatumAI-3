"""
Basketball Ball Tracker - Main Robust Wrapper

Purpose:
    Main orchestrator that wraps the original BallDetectTrack with all enhancements.
    Provides a drop-in replacement with the same API but improved robustness.

ML Pipeline Integration:
    - Exports structured data for downstream models
    - Provides confidence scores and trajectory data
    - Logs all events for training data analysis

Usage:
    # Instead of:
    # tracker = BallDetectTrack(players)
    
    # Use:
    from wrappers.robust_ball_tracker import RobustBallTracker
    
    tracker = RobustBallTracker(players, config_path='config/tracker_config.yaml')
    frame, map_2d = tracker.ball_tracker(M, M1, frame, map_2d, map_2d_text, timestamp)
    
    # Get statistics
    stats = tracker.get_statistics()
    tracker.export_data('output/')

Author: Ball Tracking Team
Date: 2024
"""

import yaml
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import numpy as np

# Import all wrapper components
from .validation_layer import ValidationLayer
from .detection_enhancer import DetectionEnhancer
from .motion_predictor import MotionPredictor
from .tracker_manager import TrackerManager
from ..utils.logger import BallTrackerLogger
from ..utils.metrics import TrackerMetrics


class RobustBallTracker:
    """
    Robust wrapper around original BallDetectTrack.
    
    Features:
        - Input/output validation
        - Multi-tracker management with fallback
        - Motion prediction during occlusion
        - Enhanced detection with color filtering
        - Comprehensive logging and metrics
        - Basketball bounce detection
    
    Attributes:
        config: Configuration dictionary
        validator: ValidationLayer instance
        tracker_manager: TrackerManager instance
        detector: DetectionEnhancer instance
        predictor: MotionPredictor instance
        logger: BallTrackerLogger instance
        metrics: TrackerMetrics instance
    """
    
    def __init__(self, players: List, config_path: str = 'config/tracker_config.yaml'):
        """
        Initialize robust ball tracker.
        
        Args:
            players: List of player objects (from IDrecognition module)
            config_path: Path to YAML configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        self.players = players
        
        # Initialize components
        self.validator = ValidationLayer(self.config)
        self.tracker_manager = TrackerManager(self.config)
        self.detector = DetectionEnhancer(self.config)
        self.predictor = MotionPredictor(self.config)
        self.logger = BallTrackerLogger(self.config)
        self.metrics = TrackerMetrics(self.config)
        
        # State management
        self.do_detection = True
        self.check_track = self.config.get('tracker', {}).get('max_track_frames', 5)
        self.max_track_frames = self.check_track
        self.ball_padding = self.config.get('tracker', {}).get('ball_padding', 30)
        
        # Performance tracking
        self.frame_count = 0
        self.detection_count = 0
        self.tracking_count = 0
        
        self.logger.logger.info("RobustBallTracker initialized successfully")
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config file
        
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"Warning: Config file not found: {config_path}")
            print("Using default configuration")
            return self._get_default_config()
        except Exception as e:
            print(f"Warning: Error loading config: {e}")
            print("Using default configuration")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file not found."""
        return {
            'tracker': {
                'max_track_frames': 5,
                'ball_padding': 30,
                'iou_ball_padding': 30,
                'tracker_types': ['KCF', 'CSRT']
            },
            'detection': {
                'template_threshold': 0.80,
                'adaptive_threshold': {
                    'enabled': True,
                    'min_threshold': 0.70,
                    'max_threshold': 0.90
                },
                'color_filter': {
                    'enabled': True,
                    'hsv_lower': [5, 100, 100],
                    'hsv_upper': [25, 255, 255],
                    'min_orange_ratio': 0.3
                }
            },
            'validation': {
                'min_bbox_size': 8,
                'max_bbox_size': 120,
                'max_position_jump': 200,
                'max_velocity': 80.0
            },
            'motion_predictor': {
                'enabled': True,
                'buffer_size': 30,
                'max_occlusion_frames': 8
            },
            'tracker_manager': {
                'strategy': 'primary_backup',
                'fallback_timeout': 10,
                'reset_interval': 50
            },
            'logging': {
                'level': 'INFO',
                'log_metrics': True
            }
        }
    
    # -------------------------------------------------------------------------
    # Main Tracking Method
    # -------------------------------------------------------------------------
    
    def ball_tracker(self, M, M1, frame, map_2d, map_2d_text, timestamp):
        """
        Main ball tracking method with enhanced robustness.
        
        This method maintains the same API as original BallDetectTrack.ball_tracker
        but adds validation, multi-tracker fallback, and motion prediction.
        
        Args:
            M: 3x3 homography matrix (frame -> field)
            M1: 3x3 homography matrix (field -> 2D map)
            frame: Input frame (BGR numpy array)
            map_2d: 2D map for visualization
            map_2d_text: 2D map with text annotations
            timestamp: Frame timestamp
        
        Returns:
            (frame, map_2d) tuple if ball found
            (frame, None) if ball not found
        """
        start_time = time.time()
        self.frame_count += 1
        
        # Step 1: Validate inputs
        if not self._validate_inputs(frame, M, M1, map_2d, timestamp):
            self.logger.log_warning("input_validation_failed", 
                                   frame_id=timestamp)
            return frame, None
        
        # Step 2: Detection or Tracking
        bbox = None
        confidence = 0.0
        
        if self.do_detection:
            bbox, confidence = self._perform_detection(frame, timestamp)
            
            if bbox is not None:
                # Initialize tracker with detection
                self.tracker_manager.init(frame, bbox)
                self.predictor.update(bbox, timestamp)
                self.do_detection = False
                self.check_track = self.max_track_frames
                
                # Log detection
                self.logger.log_detection('enhanced_detection', confidence, 
                                         bbox, frame_id=timestamp)
                self.metrics.record_detection(bbox, confidence, 
                                             'enhanced_detection', timestamp)
                self.detection_count += 1
        
        else:
            # Try tracking
            success, bbox = self.tracker_manager.update(frame)
            
            if success:
                # Validate tracking result
                is_valid, error = self.validator.validate_bbox(bbox, frame.shape)
                
                if is_valid:
                    # Check motion consistency
                    if self.predictor.validate_measurement(bbox):
                        self.predictor.update(bbox, timestamp)
                        
                        # Log tracking
                        tracker_type = self.tracker_manager.get_active_tracker()
                        self.logger.log_tracking(tracker_type, bbox, True, 
                                                frame_id=timestamp)
                        self.metrics.record_tracking(bbox, True, tracker_type, 
                                                    timestamp)
                        self.tracking_count += 1
                    else:
                        # Motion validation failed
                        self.logger.log_warning("motion_validation_failed",
                                              bbox=bbox, frame_id=timestamp)
                        bbox = None
                        success = False
                else:
                    # Bbox validation failed
                    self.logger.log_warning("bbox_validation_failed",
                                          message=error, bbox=bbox, 
                                          frame_id=timestamp)
                    bbox = None
                    success = False
            
            if not success:
                # Tracking failed, try prediction
                bbox = self.predictor.predict()
                
                if bbox is not None:
                    self.logger.log_warning("using_prediction", 
                                          bbox=bbox, frame_id=timestamp)
                else:
                    # Prediction also failed, trigger detection
                    self.logger.log_warning("tracking_lost", 
                                          frame_id=timestamp)
                    self.do_detection = True
                    self.check_track = self.max_track_frames
                
                self.metrics.record_tracking(bbox, False, 
                                            self.tracker_manager.get_active_tracker(),
                                            timestamp)
        
        # Step 3: Process ball if found
        if bbox is not None:
            # Sanitize bbox
            bbox = self.validator.sanitize_bbox(bbox, frame.shape)
            
            if bbox is not None:
                # Process ball detection/tracking
                frame, map_2d = self._process_ball(
                    bbox, frame, map_2d, map_2d_text, M, M1, timestamp
                )
                
                # Re-detection check
                self._perform_redetection_check(frame, bbox, timestamp)
            else:
                # Bbox sanitization failed
                self.logger.log_warning("bbox_sanitization_failed", 
                                      frame_id=timestamp)
                return frame, None
        
        # Step 4: Log performance metrics
        frame_time = time.time() - start_time
        self.metrics.record_frame_time(frame_time)
        self.logger.log_metric('frame_processing_time', frame_time, 
                              frame_id=timestamp)
        
        return frame, map_2d if bbox is not None else None
    
    # -------------------------------------------------------------------------
    # Detection
    # -------------------------------------------------------------------------
    
    def _perform_detection(self, frame, timestamp) -> Tuple[Optional[Tuple], float]:
        """
        Perform enhanced ball detection.
        
        Args:
            frame: Input frame
            timestamp: Frame timestamp
        
        Returns:
            (bbox, confidence) tuple
        """
        # Get search region from predictor if available
        search_region = self.predictor.get_search_region()
        
        # Perform detection
        bbox, confidence = self.detector.detect(frame, search_region)
        
        return bbox, confidence
    
    def _perform_redetection_check(self, frame, current_bbox, timestamp):
        """
        Periodically re-detect to verify tracker is still on target.
        
        Args:
            frame: Input frame
            current_bbox: Current tracked bbox
            timestamp: Frame timestamp
        """
        if self.check_track > 0:
            self.check_track -= 1
        
        elif self.check_track == 0:
            # Time to re-detect
            x, y, w, h = current_bbox
            
            # Extract region around current bbox
            y1 = max(0, y - self.ball_padding)
            y2 = min(frame.shape[0], y + h + self.ball_padding)
            x1 = max(0, x - self.ball_padding)
            x2 = min(frame.shape[1], x + w + self.ball_padding)
            
            roi = frame[y1:y2, x1:x2]
            
            # Try detection on ROI
            bbox_roi, confidence = self.detector.detect(roi, None)
            
            if bbox_roi is not None and confidence > 0.5:
                # Re-detection successful
                self.check_track = self.max_track_frames
                self.logger.log_detection('redetection', confidence, 
                                         bbox_roi, frame_id=timestamp)
            else:
                # Re-detection failed, trigger full detection
                self.logger.log_warning("redetection_failed", 
                                      frame_id=timestamp)
                self.do_detection = True
                self.check_track = self.max_track_frames
                self.metrics.record_failure('redetection_failed', 
                                           {'timestamp': timestamp})
    
    # -------------------------------------------------------------------------
    # Ball Processing
    # -------------------------------------------------------------------------
    
    def _process_ball(self, bbox, frame, map_2d, map_2d_text, M, M1, timestamp):
        """
        Process detected/tracked ball: assign to player, draw on maps.
        
        Args:
            bbox: Ball bounding box
            frame: Input frame
            map_2d: 2D map
            map_2d_text: 2D map with text
            M: Homography matrix (frame -> field)
            M1: Homography matrix (field -> 2D map)
            timestamp: Frame timestamp
        
        Returns:
            (annotated_frame, annotated_map)
        """
        from ...IDrecognition.player_detection import FeetDetector
        from operator import itemgetter
        import cv2
        
        x, y, w, h = bbox
        p1 = (int(x), int(y))
        p2 = (int(x + w), int(y + h))
        ball_center = np.array([int(x + w / 2), int(y + h / 2), 1])
        
        # Calculate IoU bbox for player assignment
        iou_padding = self.config.get('tracker', {}).get('iou_ball_padding', 30)
        bbox_iou = (
            ball_center[1] - iou_padding,
            ball_center[0] - iou_padding,
            ball_center[1] + iou_padding,
            ball_center[0] + iou_padding
        )
        
        # Find closest player
        scores = []
        for player in self.players:
            try:
                _ = player.positions[timestamp]
                if player.team != "referee":
                    if hasattr(player, 'previous_bb') and player.previous_bb is not None:
                        iou = FeetDetector.bb_intersection_over_union(
                            bbox_iou, player.previous_bb
                        )
                        scores.append((player, iou))
            except (KeyError, AttributeError):
                pass
        
        # Assign ball to player with highest IoU
        if len(scores) > 0:
            for player in self.players:
                player.has_ball = False
            
            max_score = max(scores, key=itemgetter(1))
            max_score[0].has_ball = True
            
            # Draw on text map
            try:
                player_pos = max_score[0].positions[timestamp]
                cv2.circle(map_2d_text, player_pos, 27, (0, 0, 255), 10)
            except (KeyError, AttributeError):
                pass
        
        # Transform to 2D map
        map_point = self.validator.transform_point_safe(
            (ball_center[0], ball_center[1]), M1 @ M
        )
        
        if map_point is not None:
            # Draw on frame
            cv2.rectangle(frame, p1, p2, (255, 0, 0), 2, 1)
            
            # Draw on map
            cv2.circle(map_2d, map_point, 10, (0, 0, 255), 5)
        
        return frame, map_2d
    
    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    
    def _validate_inputs(self, frame, M, M1, map_2d, timestamp) -> bool:
        """
        Validate all inputs before processing.
        
        Args:
            frame: Input frame
            M: Homography matrix 1
            M1: Homography matrix 2
            map_2d: 2D map
            timestamp: Timestamp
        
        Returns:
            True if all inputs valid
        """
        # Validate frame
        is_valid, error = self.validator.validate_frame(frame)
        if not is_valid:
            self.logger.log_error("frame_validation", message=error, 
                                timestamp=timestamp)
            return False
        
        # Validate homography matrices
        is_valid, error = self.validator.validate_homography(M)
        if not is_valid:
            self.logger.log_error("homography_M_validation", message=error,
                                timestamp=timestamp)
            return False
        
        is_valid, error = self.validator.validate_homography(M1)
        if not is_valid:
            self.logger.log_error("homography_M1_validation", message=error,
                                timestamp=timestamp)
            return False
        
        # Validate players
        is_valid, error = self.validator.validate_players(self.players, timestamp)
        if not is_valid:
            self.logger.log_warning("player_validation", message=error,
                                  timestamp=timestamp)
            # Continue anyway, this is not critical
        
        return True
    
    # -------------------------------------------------------------------------
    # Statistics and Export
    # -------------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive tracking statistics.
        
        Returns:
            Dictionary with all statistics
        """
        metrics_summary = self.metrics.get_summary()
        tracker_stats = self.tracker_manager.get_statistics()
        predictor_state = self.predictor.get_state_dict()
        bounce_events = self.predictor.get_bounce_events()
        
        return {
            'frames_processed': self.frame_count,
            'detection_count': self.detection_count,
            'tracking_count': self.tracking_count,
            'metrics': metrics_summary,
            'tracker_manager': tracker_stats,
            'motion_predictor': predictor_state,
            'bounce_events': len(bounce_events),
            'is_tracking_stable': self.tracker_manager.is_tracking_stable()
        }
    
    def export_data(self, output_dir: str):
        """
        Export all tracking data for ML pipeline.
        
        Args:
            output_dir: Directory to save exports
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export trajectory
        traj_format = self.config.get('logging', {}).get('trajectory_format', 'json')
        traj_file = self.metrics.export_trajectory(
            str(output_path / f'trajectory.{traj_format}'), 
            format=traj_format
        )
        
        # Export metrics
        metrics_file = self.logger.export_metrics(
            str(output_path / 'metrics.json')
        )
        
        # Export statistics
        import json
        stats = self.get_statistics()
        with open(output_path / 'statistics.json', 'w') as f:
            json.dump(stats, f, indent=2)
        
        self.logger.logger.info(f"Data exported to: {output_dir}")
        self.logger.logger.info(f"  - Trajectory: {traj_file}")
        self.logger.logger.info(f"  - Metrics: {metrics_file}")
        self.logger.logger.info(f"  - Statistics: {output_path / 'statistics.json'}")
    
    def reset(self):
        """Reset all tracking state."""
        self.tracker_manager.reset()
        self.predictor.reset()
        self.do_detection = True
        self.check_track = self.max_track_frames
        
        self.logger.logger.info("Tracker reset")