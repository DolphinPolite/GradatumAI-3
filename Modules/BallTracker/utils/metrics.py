"""
Basketball Ball Tracker - Performance Metrics Module

Purpose:
    Tracks and analyzes tracking performance for optimization and debugging.
    Provides metrics useful for ML model evaluation and system tuning.

ML Pipeline Integration:
    - Exports trajectory data for training/validation
    - Calculates tracking quality metrics (precision, recall estimates)
    - Provides frame-level performance data

Usage:
    from utils.metrics import TrackerMetrics
    
    metrics = TrackerMetrics(config)
    metrics.record_detection(bbox, confidence=0.85, method='template')
    metrics.record_tracking(bbox, success=True, tracker='KCF')
    
    summary = metrics.get_summary()
    metrics.export_trajectory('ball_trajectory.json')

Author: Ball Tracking Team
Date: 2025
"""

import numpy as np
from collections import deque, defaultdict
from typing import Optional, List, Tuple, Dict, Any
import json
from pathlib import Path
from datetime import datetime


class TrackerMetrics:
    """
    Collects and analyzes basketball tracking performance metrics.
    
    Features:
        - Track detection/tracking success rates
        - Store ball trajectory for analysis
        - Calculate motion statistics (velocity, acceleration)
        - Export data for ML pipeline
    
    Attributes:
        trajectory (deque): Ring buffer of ball positions with timestamps
        events (list): Log of all tracking events
        frame_metrics (dict): Per-frame performance data
    """
    
    def __init__(self, config: Dict[str, Any], buffer_size: int = 1000):
        """
        Initialize metrics collector.
        
        Args:
            config: Configuration dictionary from tracker_config.yaml
            buffer_size: Maximum trajectory points to store in memory
        """
        self.config = config
        self.buffer_size = buffer_size
        
        # Trajectory storage: (frame_id, timestamp, x, y, w, h, confidence)
        self.trajectory = deque(maxlen=buffer_size)
        
        # Event counters
        self.detection_count = 0
        self.tracking_count = 0
        self.tracking_success_count = 0
        self.tracking_fail_count = 0
        self.bounce_count = 0
        
        # Method breakdown
        self.detection_methods = defaultdict(int)
        self.tracker_types = defaultdict(int)
        
        # Confidence scores
        self.confidence_scores = []
        
        # Timing information
        self.frame_times = []
        
        # Failure analysis
        self.failure_reasons = defaultdict(int)
        
        # State tracking
        self.current_track_length = 0
        self.max_track_length = 0
        self.track_lengths = []
    
    # -------------------------------------------------------------------------
    # Recording Methods
    # -------------------------------------------------------------------------
    
    def record_detection(self, bbox: Tuple[int, int, int, int], 
                        confidence: float, method: str, 
                        frame_id: Optional[int] = None,
                        timestamp: Optional[float] = None):
        """
        Record a ball detection event.
        
        Args:
            bbox: Bounding box (x, y, w, h)
            confidence: Detection confidence (0-1)
            method: Detection method used
            frame_id: Frame number
            timestamp: Frame timestamp (seconds)
        """
        self.detection_count += 1
        self.detection_methods[method] += 1
        self.confidence_scores.append(confidence)
        
        # Add to trajectory
        self.trajectory.append({
            'frame_id': frame_id,
            'timestamp': timestamp,
            'bbox': bbox,
            'center': (bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2),
            'confidence': confidence,
            'source': 'detection',
            'method': method
        })
        
        # Reset track length on new detection
        if self.current_track_length > 0:
            self.track_lengths.append(self.current_track_length)
            self.max_track_length = max(self.max_track_length, self.current_track_length)
            self.current_track_length = 0
    
    def record_tracking(self, bbox: Tuple[int, int, int, int],
                       success: bool, tracker_type: str,
                       frame_id: Optional[int] = None,
                       timestamp: Optional[float] = None):
        """
        Record a tracking update event.
        
        Args:
            bbox: Bounding box (x, y, w, h) or None if failed
            success: Whether tracking succeeded
            tracker_type: Type of tracker used
            frame_id: Frame number
            timestamp: Frame timestamp (seconds)
        """
        self.tracking_count += 1
        self.tracker_types[tracker_type] += 1
        
        if success:
            self.tracking_success_count += 1
            self.current_track_length += 1
            
            # Add to trajectory
            self.trajectory.append({
                'frame_id': frame_id,
                'timestamp': timestamp,
                'bbox': bbox,
                'center': (bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2),
                'confidence': None,  # Tracker doesn't provide confidence
                'source': 'tracking',
                'tracker': tracker_type
            })
        else:
            self.tracking_fail_count += 1
            
            # End current track
            if self.current_track_length > 0:
                self.track_lengths.append(self.current_track_length)
                self.max_track_length = max(self.max_track_length, self.current_track_length)
                self.current_track_length = 0
    
    def record_failure(self, reason: str, context: Optional[Dict] = None):
        """
        Record a tracking failure with reason.
        
        Args:
            reason: Failure reason (e.g., 'occlusion', 'out_of_frame')
            context: Additional context information
        """
        self.failure_reasons[reason] += 1
    
    def record_bounce(self, frame_id: int, position: Tuple[int, int],
                     velocity_change: float):
        """
        Record a basketball bounce event.
        
        Args:
            frame_id: Frame where bounce occurred
            position: Ball position (x, y)
            velocity_change: Change in vertical velocity
        """
        self.bounce_count += 1
    
    def record_frame_time(self, processing_time: float):
        """
        Record frame processing time.
        
        Args:
            processing_time: Time in seconds
        """
        self.frame_times.append(processing_time)
    
    # -------------------------------------------------------------------------
    # Analysis Methods
    # -------------------------------------------------------------------------
    
    def calculate_velocity(self, window_size: int = 3) -> List[Tuple[float, float]]:
        """
        Calculate velocity from trajectory using finite differences.
        
        Args:
            window_size: Number of frames for smoothing
        
        Returns:
            List of (vx, vy) velocities in pixels/frame
        """
        if len(self.trajectory) < 2:
            return []
        
        velocities = []
        traj_list = list(self.trajectory)
        
        for i in range(1, len(traj_list)):
            dt = 1.0  # Assume consecutive frames
            if traj_list[i]['timestamp'] and traj_list[i-1]['timestamp']:
                dt = traj_list[i]['timestamp'] - traj_list[i-1]['timestamp']
                if dt == 0:
                    dt = 1.0
            
            pos_curr = traj_list[i]['center']
            pos_prev = traj_list[i-1]['center']
            
            vx = (pos_curr[0] - pos_prev[0]) / dt
            vy = (pos_curr[1] - pos_prev[1]) / dt
            
            velocities.append((vx, vy))
        
        # Apply moving average smoothing
        if len(velocities) >= window_size:
            smoothed = []
            for i in range(len(velocities)):
                start = max(0, i - window_size//2)
                end = min(len(velocities), i + window_size//2 + 1)
                window = velocities[start:end]
                
                avg_vx = sum(v[0] for v in window) / len(window)
                avg_vy = sum(v[1] for v in window) / len(window)
                smoothed.append((avg_vx, avg_vy))
            
            return smoothed
        
        return velocities
    
    def calculate_acceleration(self, velocities: Optional[List[Tuple[float, float]]] = None
                             ) -> List[Tuple[float, float]]:
        """
        Calculate acceleration from velocities.
        
        Args:
            velocities: List of velocities (if None, calculated from trajectory)
        
        Returns:
            List of (ax, ay) accelerations in pixels/frame²
        """
        if velocities is None:
            velocities = self.calculate_velocity()
        
        if len(velocities) < 2:
            return []
        
        accelerations = []
        for i in range(1, len(velocities)):
            ax = velocities[i][0] - velocities[i-1][0]
            ay = velocities[i][1] - velocities[i-1][1]
            accelerations.append((ax, ay))
        
        return accelerations
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive summary statistics.
        
        Returns:
            Dictionary containing all metrics
        """
        # Finalize current track if ongoing
        if self.current_track_length > 0:
            self.track_lengths.append(self.current_track_length)
        
        # Calculate tracking rate
        total_frames = self.detection_count + self.tracking_count
        tracking_success_rate = (
            self.tracking_success_count / self.tracking_count 
            if self.tracking_count > 0 else 0
        )
        
        # Average confidence
        avg_confidence = (
            sum(self.confidence_scores) / len(self.confidence_scores)
            if self.confidence_scores else 0
        )
        
        # Track length statistics
        avg_track_length = (
            sum(self.track_lengths) / len(self.track_lengths)
            if self.track_lengths else 0
        )
        
        # FPS calculation
        avg_frame_time = (
            sum(self.frame_times) / len(self.frame_times)
            if self.frame_times else 0
        )
        fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        
        summary = {
            'total_frames_processed': total_frames,
            'detection': {
                'count': self.detection_count,
                'avg_confidence': avg_confidence,
                'methods': dict(self.detection_methods)
            },
            'tracking': {
                'count': self.tracking_count,
                'success_count': self.tracking_success_count,
                'fail_count': self.tracking_fail_count,
                'success_rate': tracking_success_rate,
                'tracker_types': dict(self.tracker_types)
            },
            'track_quality': {
                'avg_track_length': avg_track_length,
                'max_track_length': self.max_track_length,
                'total_tracks': len(self.track_lengths)
            },
            'basketball_specific': {
                'bounce_count': self.bounce_count
            },
            'performance': {
                'avg_frame_time_sec': avg_frame_time,
                'fps': fps
            },
            'failures': dict(self.failure_reasons)
        }
        
        return summary
    
    # -------------------------------------------------------------------------
    # Export Methods
    # -------------------------------------------------------------------------
    
    def export_trajectory(self, filepath: Optional[str] = None,
                         format: str = 'json') -> str:
        """
        Export ball trajectory to file.
        
        Args:
            filepath: Output file path (auto-generated if None)
            format: Export format ('json', 'csv', or 'numpy')
        
        Returns:
            Path to exported file
        """
        if not self.trajectory:
            return ""
        
        # Generate filepath if not provided
        if filepath is None:
            log_dir = Path(self.config.get('logging', {}).get('log_directory', 'logs/ball_tracking'))
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            ext = {'json': 'json', 'csv': 'csv', 'numpy': 'npy'}[format]
            filepath = log_dir / f"trajectory_{timestamp}.{ext}"
        
        # Convert trajectory to list
        traj_data = list(self.trajectory)
        
        # Export based on format
        if format == 'json':
            with open(filepath, 'w') as f:
                json.dump(traj_data, f, indent=2)
        
        elif format == 'csv':
            import csv
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame_id', 'timestamp', 'x', 'y', 'w', 'h', 
                               'center_x', 'center_y', 'confidence', 'source'])
                
                for entry in traj_data:
                    bbox = entry['bbox']
                    center = entry['center']
                    writer.writerow([
                        entry['frame_id'], entry['timestamp'],
                        bbox[0], bbox[1], bbox[2], bbox[3],
                        center[0], center[1],
                        entry['confidence'], entry['source']
                    ])
        
        elif format == 'numpy':
            # Convert to numpy array: [frame_id, x, y, w, h, confidence]
            array_data = []
            for entry in traj_data:
                bbox = entry['bbox']
                array_data.append([
                    entry['frame_id'] or 0,
                    bbox[0], bbox[1], bbox[2], bbox[3],
                    entry['confidence'] or 0
                ])
            
            np.save(filepath, np.array(array_data))
        
        return str(filepath)
    
    def get_trajectory_array(self) -> np.ndarray:
        """
        Get trajectory as numpy array for ML processing.
        
        Returns:
            Array of shape (N, 6): [frame_id, x, y, w, h, confidence]
        """
        if not self.trajectory:
            return np.array([])
        
        array_data = []
        for entry in self.trajectory:
            bbox = entry['bbox']
            array_data.append([
                entry['frame_id'] or 0,
                bbox[0], bbox[1], bbox[2], bbox[3],
                entry['confidence'] or 0
            ])
        
        return np.array(array_data)