"""
Shot Attempt Detector - Main Detection Module

Purpose:
    Main orchestrator that integrates all components:
    - Temporal buffering
    - Feature extraction
    - Confidence calculation
    - Event generation

Design Philosophy:
    - Rule-based core (AI only for refinement)
    - Hard conditions are gatekeepers
    - Explainable decisions
    - Stateful per-player tracking

Public API:
    - process_frame(): Process single frame, return event if detected
    - reset(): Clear all state
    - get_statistics(): Get detection statistics

Author: Shot Detection Module
Date: 2024
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from .thresholds import DetectionThresholds
from .utils import (
    FramePacket,
    ShotEvent,
    validate_frame_packet,
    calculate_confidence_score,
    format_reasoning
)
from .features import FeatureExtractor, ExtractedFeatures
from .temporal_buffer import TemporalBuffer


class ShotAttemptDetector:
    """
    Shot attempt detection system.
    
    This is the main entry point for shot detection. It orchestrates
    all sub-modules and maintains per-player state.
    
    Features:
        - Temporal buffering per player
        - Feature extraction and validation
        - Rule-based detection with optional AI refinement
        - Comprehensive event logging
    
    Architecture:
        Input → TemporalBuffer → FeatureExtractor → Confidence → Event
        
    Usage:
        >>> detector = ShotAttemptDetector()
        >>> 
        >>> # Process frames
        >>> for frame_data in video_stream:
        ...     packet = FramePacket(**frame_data)
        ...     event = detector.process_frame(packet)
        ...     if event:
        ...         print(f"Shot detected: {event}")
    """
    
    def __init__(self,
                 thresholds: Optional[DetectionThresholds] = None,
                 enable_ai_refiner: bool = False,
                 verbose: bool = False):
        """
        Initialize shot attempt detector.
        
        Args:
            thresholds: Detection thresholds (None = default)
            enable_ai_refiner: Enable AI confidence refinement
            verbose: Print debug information
        """
        # Configuration
        self.thresholds = thresholds or DetectionThresholds()
        self.enable_ai_refiner = enable_ai_refiner
        self.verbose = verbose
        
        # Validate configuration
        is_valid, error = self.thresholds.validate()
        if not is_valid:
            raise ValueError(f"Invalid thresholds: {error}")
        
        # Initialize components
        self.temporal_buffer = TemporalBuffer(
            window_size=self.thresholds.temporal_window_size
        )
        self.feature_extractor = FeatureExtractor(self.thresholds)
        
        # Statistics
        self.frame_count = 0
        self.detection_count = 0
        self.detection_history: List[ShotEvent] = []
        
        # Per-player cooldown (prevent duplicate detections)
        self.player_cooldown: Dict[int, int] = {}
        self.cooldown_frames = 10  # Minimum frames between detections
        
        if self.verbose:
            print(f"ShotAttemptDetector initialized")
            print(f"  Thresholds: {self.thresholds.preset_name}")
            print(f"  Window size: {self.thresholds.temporal_window_size} frames")
            print(f"  AI refiner: {'enabled' if self.enable_ai_refiner else 'disabled'}")
    
    # =========================================================================
    # MAIN PROCESSING METHOD
    # =========================================================================
    
    def process_frame(self, frame: FramePacket) -> Optional[ShotEvent]:
        """
        Process single frame and detect shot attempts.
        
        This is the main API method. Call once per frame.
        
        Args:
            frame: FramePacket with player and ball data
        
        Returns:
            ShotEvent if shot detected, None otherwise
        
        Algorithm:
            1. Validate input
            2. Add frame to temporal buffer
            3. Check if ready for detection (enough frames)
            4. Extract features from window
            5. Check hard conditions (gatekeeper)
            6. Calculate confidence
            7. Generate event if confidence above threshold
        
        Example:
            >>> packet = FramePacket(
            ...     timestamp=100,
            ...     player_id=7,
            ...     movement_state="jumping",
            ...     movement_confidence=0.85,
            ...     bbox_height=250.0,
            ...     ball_position=(320, 240),
            ...     has_ball=True
            ... )
            >>> event = detector.process_frame(packet)
            >>> if event:
            ...     print(f"Shot by player {event.player_id}")
        """
        self.frame_count += 1
        
        # Step 1: Validate input
        is_valid, error = validate_frame_packet(frame)
        if not is_valid:
            if self.verbose:
                print(f"[Frame {frame.timestamp}] Validation failed: {error}")
            return None
        
        # Step 2: Add to temporal buffer
        self.temporal_buffer.add_frame(frame.player_id, frame)
        
        # Step 3: Check cooldown (prevent duplicate detections)
        if self._is_in_cooldown(frame.player_id, frame.timestamp):
            return None
        
        # Step 4: Check if ready for detection
        buffer_size = self.temporal_buffer.get_buffer_size(frame.player_id)
        if buffer_size < self.thresholds.temporal_window_min:
            # Not enough frames yet
            return None
        
        # Step 5: Get temporal window
        window = self.temporal_buffer.get_window(
            frame.player_id,
            size=self.thresholds.temporal_window_size
        )
        
        # Step 6: Extract features
        features = self.feature_extractor.extract(window, frame.player_id)
        
        # Step 7: Check hard conditions (GATEKEEPER)
        if not features.all_hard_conditions_met():
            # Hard conditions failed - no shot detected
            return None
        
        # Step 8: Calculate confidence
        confidence = self._calculate_final_confidence(features)
        
        # Step 9: Check confidence threshold
        if confidence < self.thresholds.confidence_min_threshold:
            if self.verbose:
                print(f"[Frame {frame.timestamp}] Low confidence: {confidence:.2f}")
            return None
        
        # Step 10: Generate shot event
        event = self._generate_event(frame.player_id, features, confidence)
        
        # Step 11: Update statistics and cooldown
        self.detection_count += 1
        self.detection_history.append(event)
        self._set_cooldown(frame.player_id, frame.timestamp)
        
        if self.verbose:
            print(f"[Frame {frame.timestamp}] SHOT DETECTED!")
            print(f"  Player: {event.player_id}")
            print(f"  Release: frame {event.release_frame}")
            print(f"  Confidence: {event.confidence:.2f}")
            print(f"  Reasoning: {event.reasoning}")
        
        return event
    
    # =========================================================================
    # CONFIDENCE CALCULATION
    # =========================================================================
    
    def _calculate_final_confidence(self, features: ExtractedFeatures) -> float:
        """
        Calculate final confidence score.
        
        Args:
            features: Extracted features
        
        Returns:
            Final confidence [0, 1]
        
        Note:
            Uses calculate_confidence_score from utils.py (single source of truth).
            Optional AI refinement is applied here.
        """
        # Prepare weight dictionary
        weights = {
            'jump': self.thresholds.weight_jump_confidence,
            'release': self.thresholds.weight_ball_release,
            'velocity': self.thresholds.weight_upward_velocity,
            'temporal': self.thresholds.weight_temporal_consistency,
            'bonus_separation': self.thresholds.bonus_separation_trend,
            'bonus_height': self.thresholds.bonus_release_height,
            'bonus_apex': self.thresholds.bonus_apex_alignment
        }
        
        # Prepare soft scores
        soft_scores = {
            'separation_trend': features.separation_trend_score,
            'release_height': features.release_height_score,
            'apex_alignment': features.apex_alignment_score
        }
        
        # Calculate base confidence (rule-based)
        base_confidence = calculate_confidence_score(
            jump_detected=features.jump_detected,
            jump_confidence=features.jump_confidence,
            ball_release_detected=features.ball_release_detected,
            ball_release_clarity=features.ball_release_clarity,
            upward_motion_detected=features.upward_motion_detected,
            upward_motion_strength=features.upward_motion_strength,
            temporal_consistency=features.temporal_consistency_score,
            weights=weights,
            soft_scores=soft_scores
        )
        
        # Optional AI refinement
        if self.enable_ai_refiner:
            ai_confidence = self._ai_refine_confidence(features)
            # Blend: 80% rule-based, 20% AI
            final_confidence = 0.8 * base_confidence + 0.2 * ai_confidence
        else:
            final_confidence = base_confidence
        
        return final_confidence
    
    def _ai_refine_confidence(self, features: ExtractedFeatures) -> float:
        """
        AI-based confidence refinement (OPTIONAL).
        
        This is where an ML model could be integrated to refine confidence.
        
        Args:
            features: Extracted features
        
        Returns:
            AI-refined confidence [0, 1]
        
        Note:
            AI CANNOT trigger events - only refine confidence!
            The rule-based system is the gatekeeper.
        
        Implementation:
            In production, this would call a lightweight ML model:
            - Input: features.to_dict()
            - Output: confidence adjustment
            - Model: Small neural net or gradient boosting
        
        Current Implementation:
            Placeholder that returns 0.5 (no effect on blend).
        """
        # TODO: Integrate ML model here
        # 
        # Example:
        # feature_vector = self._features_to_vector(features)
        # ai_score = self.ml_model.predict(feature_vector)
        # return ai_score
        
        # Placeholder: no AI refinement
        return 0.5
    
    # =========================================================================
    # EVENT GENERATION
    # =========================================================================
    
    def _generate_event(self,
                       player_id: int,
                       features: ExtractedFeatures,
                       confidence: float) -> ShotEvent:
        """
        Generate shot event from features.
        
        Args:
            player_id: Player ID
            features: Extracted features
            confidence: Final confidence score
        
        Returns:
            ShotEvent
        """
        # Generate reasoning string
        conditions = {
            'jump_detected': features.jump_detected,
            'ball_release_detected': features.ball_release_detected,
            'upward_motion_detected': features.upward_motion_detected
        }
        
        scores = {
            'jump_confidence': features.jump_confidence,
            'upward_motion_strength': features.upward_motion_strength,
            'temporal_consistency': features.temporal_consistency_score,
            'separation_trend': features.separation_trend_score,
            'release_height': features.release_height_score
        }
        
        reasoning = format_reasoning(conditions, scores)
        
        # Create event
        event = ShotEvent(
            event_type="shot_attempt",
            player_id=player_id,
            start_frame=features.window_start,
            release_frame=features.release_frame or -1,
            confidence=confidence,
            reasoning=reasoning,
            features=features.to_dict()
        )
        
        return event
    
    # =========================================================================
    # COOLDOWN MANAGEMENT
    # =========================================================================
    
    def _is_in_cooldown(self, player_id: int, timestamp: int) -> bool:
        """
        Check if player is in cooldown period.
        
        Prevents duplicate detections for same shot.
        """
        if player_id not in self.player_cooldown:
            return False
        
        last_detection = self.player_cooldown[player_id]
        return (timestamp - last_detection) < self.cooldown_frames
    
    def _set_cooldown(self, player_id: int, timestamp: int):
        """Set cooldown for player."""
        self.player_cooldown[player_id] = timestamp
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def reset(self, player_id: Optional[int] = None):
        """
        Reset detector state.
        
        Args:
            player_id: Reset specific player (None = reset all)
        """
        if player_id is None:
            # Reset all
            self.temporal_buffer.clear_all()
            self.player_cooldown.clear()
            self.detection_history.clear()
            self.frame_count = 0
            self.detection_count = 0
        else:
            # Reset specific player
            self.temporal_buffer.clear_player(player_id)
            if player_id in self.player_cooldown:
                del self.player_cooldown[player_id]
        
        if self.verbose:
            print(f"Detector reset (player_id={player_id})")
    
    # =========================================================================
    # STATISTICS AND EXPORT
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detection statistics.
        
        Returns:
            Dictionary with comprehensive statistics
        """
        buffer_stats = self.temporal_buffer.get_statistics()
        
        return {
            'configuration': {
                'preset': self.thresholds.preset_name,
                'window_size': self.thresholds.temporal_window_size,
                'min_confidence': self.thresholds.confidence_min_threshold,
                'ai_refiner_enabled': self.enable_ai_refiner
            },
            'processing': {
                'frames_processed': self.frame_count,
                'shots_detected': self.detection_count,
                'detection_rate': (
                    self.detection_count / self.frame_count
                    if self.frame_count > 0 else 0.0
                )
            },
            'buffer': buffer_stats,
            'recent_detections': [
                {
                    'player_id': e.player_id,
                    'frame': e.release_frame,
                    'confidence': e.confidence
                }
                for e in self.detection_history[-10:]  # Last 10
            ]
        }
    
    def export_detections(self, format: str = 'list') -> Any:
        """
        Export all detected shot attempts.
        
        Args:
            format: Export format ('list', 'dict', 'json')
        
        Returns:
            Exported data in requested format
        """
        if format == 'list':
            return self.detection_history
        
        elif format == 'dict':
            return [event.to_dict() for event in self.detection_history]
        
        elif format == 'json':
            import json
            return json.dumps(
                [event.to_dict() for event in self.detection_history],
                indent=2
            )
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def get_player_detections(self, player_id: int) -> List[ShotEvent]:
        """
        Get all detections for specific player.
        
        Args:
            player_id: Player identifier
        
        Returns:
            List of ShotEvents for that player
        """
        return [
            event for event in self.detection_history
            if event.player_id == player_id
        ]


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Shot Attempt Detector Test ===\n")
    
    # Initialize detector
    detector = ShotAttemptDetector(verbose=True)
    
    print("\nProcessing frame sequence...\n")
    
    # Simulate shot sequence
    for i in range(20):
        # Simulate states
        state = "idle"
        has_ball = True
        bbox_height = 200.0
        bbox_change = 0.0
        ball_y = 200.0
        
        if 5 <= i < 10:
            state = "jumping"
            bbox_height = 185.0
            bbox_change = -15.0
        
        if i >= 8:
            has_ball = False
            ball_y = 200.0 - (i - 8) * 10  # Ball moving up
        
        # Create frame packet
        frame = FramePacket(
            timestamp=100 + i,
            player_id=7,
            movement_state=state,
            movement_confidence=0.85,
            bbox_height=bbox_height,
            bbox_height_change=bbox_change,
            speed=2.5 if state != "idle" else 0.3,
            ball_position=(300.0, ball_y),
            has_ball=has_ball
        )
        
        # Process frame
        event = detector.process_frame(frame)
        
        if event:
            print(f"\n{'='*60}")
            print("SHOT DETECTED!")
            print(f"  Player: {event.player_id}")
            print(f"  Release Frame: {event.release_frame}")
            print(f"  Confidence: {event.confidence:.2f}")
            print(f"  Reasoning: {event.reasoning}")
            print(f"{'='*60}\n")
    
    # Statistics
    print("\n=== Final Statistics ===")
    stats = detector.get_statistics()
    print(f"Frames processed: {stats['processing']['frames_processed']}")
    print(f"Shots detected: {stats['processing']['shots_detected']}")
    print(f"Detection rate: {stats['processing']['detection_rate']:.1%}")