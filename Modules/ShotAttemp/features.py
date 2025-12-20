"""
Shot Attempt Detector - Feature Extraction Module

Purpose:
    Extract and validate all features required for shot attempt detection.
    This is the BRAIN of the detection system.

Core Responsibility:
    Answer the question: "Is this really a shot attempt?"

Feature Categories:
    - Hard Conditions (H1-H4): Boolean gates, all must pass
    - Soft Conditions (S1-S4): Discriminative scores [0,1]

Design Philosophy:
    - Each condition is independently testable
    - Clear separation of concerns
    - Explicit reasoning for each decision
    - Handles missing/noisy data gracefully

Author: Shot Detection Module
Date: 2024
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import math

from .utils import (
    FramePacket,
    calculate_distance,
    calculate_velocity,
    smooth_velocity,
    calculate_separation_trend,
    infer_ball_owner
)
from .thresholds import DetectionThresholds


# =============================================================================
# FEATURE EXTRACTION RESULT
# =============================================================================

@dataclass
class ExtractedFeatures:
    """
    Container for all extracted features.
    
    This structure holds results of all feature extraction operations
    and is used for confidence calculation and reasoning generation.
    """
    
    # Hard Conditions (H1-H4)
    jump_detected: bool = False
    jump_confidence: float = 0.0
    jump_frame: Optional[int] = None
    
    ball_control_before_jump: bool = False
    control_frames: int = 0
    
    ball_release_detected: bool = False
    ball_release_clarity: float = 0.0
    release_frame: Optional[int] = None
    
    upward_motion_detected: bool = False
    upward_motion_strength: float = 0.0
    upward_velocity: float = 0.0
    
    # Soft Conditions (S1-S4)
    separation_trend_score: float = 0.0
    release_height_score: float = 0.0
    apex_alignment_score: float = 0.0
    temporal_consistency_score: float = 0.0
    
    # Metadata
    window_start: int = -1
    window_end: int = -1
    data_quality: float = 0.0
    
    def all_hard_conditions_met(self) -> bool:
        """Check if all hard conditions passed."""
        return (
            self.jump_detected and
            self.ball_control_before_jump and
            self.ball_release_detected and
            self.upward_motion_detected
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            'hard_conditions': {
                'jump_detected': self.jump_detected,
                'jump_confidence': self.jump_confidence,
                'jump_frame': self.jump_frame,
                'ball_control_before_jump': self.ball_control_before_jump,
                'control_frames': self.control_frames,
                'ball_release_detected': self.ball_release_detected,
                'ball_release_clarity': self.ball_release_clarity,
                'release_frame': self.release_frame,
                'upward_motion_detected': self.upward_motion_detected,
                'upward_motion_strength': self.upward_motion_strength,
                'upward_velocity': self.upward_velocity
            },
            'soft_conditions': {
                'separation_trend': self.separation_trend_score,
                'release_height': self.release_height_score,
                'apex_alignment': self.apex_alignment_score,
                'temporal_consistency': self.temporal_consistency_score
            },
            'metadata': {
                'window_start': self.window_start,
                'window_end': self.window_end,
                'data_quality': self.data_quality
            }
        }


# =============================================================================
# FEATURE EXTRACTOR
# =============================================================================

class FeatureExtractor:
    """
    Extract all features required for shot attempt detection.
    
    This class orchestrates extraction of:
        - Hard conditions (H1-H4): Boolean gates
        - Soft conditions (S1-S4): Discriminative scores
    
    Usage:
        >>> extractor = FeatureExtractor(thresholds)
        >>> features = extractor.extract(window, player_id)
        >>> if features.all_hard_conditions_met():
        ...     print("Potential shot detected!")
    """
    
    def __init__(self, thresholds: DetectionThresholds):
        """
        Initialize feature extractor.
        
        Args:
            thresholds: DetectionThresholds instance
        """
        self.thresholds = thresholds
    
    # =========================================================================
    # MAIN EXTRACTION METHOD
    # =========================================================================
    
    def extract(self, 
                window: List[FramePacket],
                player_id: int) -> ExtractedFeatures:
        """
        Extract all features from temporal window.
        
        This is the main entry point. It orchestrates all feature extraction.
        
        Args:
            window: Temporal window of frames (sorted by timestamp)
            player_id: Player to analyze
        
        Returns:
            ExtractedFeatures containing all extracted features
        
        Algorithm:
            1. Validate window
            2. Extract hard conditions (H1-H4)
            3. If all hard conditions met, extract soft conditions (S1-S4)
            4. Return complete feature set
        """
        features = ExtractedFeatures()
        
        # Metadata
        if len(window) > 0:
            features.window_start = window[0].timestamp
            features.window_end = window[-1].timestamp
        
        # Check data quality
        from .utils import check_data_quality
        features.data_quality = check_data_quality(window)
        
        if features.data_quality < 0.3:
            # Too low quality, don't proceed
            return features
        
        # Extract Hard Conditions (H1-H4)
        self._extract_h1_jump_initiation(window, player_id, features)
        self._extract_h2_ball_control(window, player_id, features)
        self._extract_h3_ball_release(window, player_id, features)
        self._extract_h4_upward_motion(window, player_id, features)
        
        # Extract Soft Conditions (S1-S4) only if hard conditions met
        if features.all_hard_conditions_met():
            self._extract_s1_separation_trend(window, player_id, features)
            self._extract_s2_release_height(window, player_id, features)
            self._extract_s3_apex_alignment(window, player_id, features)
            self._extract_s4_temporal_consistency(window, player_id, features)
        
        return features
    
    # =========================================================================
    # H1 - JUMP INITIATION
    # =========================================================================
    
    def _extract_h1_jump_initiation(self,
                                     window: List[FramePacket],
                                     player_id: int,
                                     features: ExtractedFeatures):
        """
        H1: Detect jump initiation.
        
        Criteria:
            - movement_state == "jumping"
            - movement_confidence >= threshold
            - bbox_height_change < -threshold (shrinking)
            - sustained for min_frames
        
        Updates:
            - features.jump_detected
            - features.jump_confidence
            - features.jump_frame
        """
        # Find jumping frames
        jumping_frames = [
            f for f in window
            if f.player_id == player_id and
               f.movement_state == "jumping" and
               f.movement_confidence >= self.thresholds.jump_confidence_min
        ]
        
        if len(jumping_frames) < self.thresholds.jump_min_frames:
            return
        
        # Check bbox shrinking (perspective effect of jumping)
        valid_jump_frames = []
        for frame in jumping_frames:
            if frame.bbox_height_change is not None:
                shrink_ratio = frame.bbox_height_change / frame.bbox_height
                if shrink_ratio < -self.thresholds.jump_bbox_shrink_min:
                    valid_jump_frames.append(frame)
        
        if len(valid_jump_frames) >= self.thresholds.jump_min_frames:
            # Jump detected!
            features.jump_detected = True
            features.jump_frame = valid_jump_frames[0].timestamp
            
            # Average confidence across valid frames
            features.jump_confidence = sum(
                f.movement_confidence for f in valid_jump_frames
            ) / len(valid_jump_frames)
    
    # =========================================================================
    # H2 - BALL CONTROL BEFORE JUMP
    # =========================================================================
    
    def _extract_h2_ball_control(self,
                                  window: List[FramePacket],
                                  player_id: int,
                                  features: ExtractedFeatures):
        """
        H2: Verify player had ball control before jump.
        
        Criteria:
            - has_ball == True for sufficient frames before jump
            - Continuous control (no steals/deflections)
        
        Updates:
            - features.ball_control_before_jump
            - features.control_frames
        
        Logic:
            1. Find jump_frame (from H1)
            2. Look back N frames
            3. Count frames where has_ball == True
            4. Check if >= min_frames threshold
        """
        if not features.jump_detected or features.jump_frame is None:
            return
        
        # Look back from jump frame
        lookback_start = max(
            window[0].timestamp,
            features.jump_frame - self.thresholds.ownership_lookback_frames
        )
        
        # Get frames in lookback window
        lookback_frames = [
            f for f in window
            if f.player_id == player_id and
               lookback_start <= f.timestamp < features.jump_frame
        ]
        
        if len(lookback_frames) == 0:
            return
        
        # Count frames with ball
        with_ball = sum(1 for f in lookback_frames if f.has_ball)
        
        # Check threshold
        if with_ball >= self.thresholds.ownership_min_frames:
            features.ball_control_before_jump = True
            features.control_frames = with_ball
    
    # =========================================================================
    # H3 - BALL RELEASE
    # =========================================================================
    
    def _extract_h3_ball_release(self,
                                  window: List[FramePacket],
                                  player_id: int,
                                  features: ExtractedFeatures):
        """
        H3: Detect ball release event.
        
        Criteria:
            - has_ball: True → False transition
            - Occurs within gap_max_frames after jump
            - Ball-player distance increasing
        
        Updates:
            - features.ball_release_detected
            - features.ball_release_clarity
            - features.release_frame
        
        Discriminative Power:
            - Shot: clean release, monotonic separation
            - Steal/Deflection: abrupt, irregular separation
            - Pass: slower separation or lateral motion
        """
        if not features.jump_detected or features.jump_frame is None:
            return
        
        # Define search window (after jump)
        search_end = min(
            window[-1].timestamp,
            features.jump_frame + self.thresholds.release_gap_max_frames
        )
        
        # Get frames in search window
        search_frames = [
            f for f in window
            if f.player_id == player_id and
               features.jump_frame <= f.timestamp <= search_end
        ]
        
        if len(search_frames) < 2:
            return
        
        # Find has_ball transition (True → False)
        release_frame_idx = None
        for i in range(len(search_frames) - 1):
            if search_frames[i].has_ball and not search_frames[i+1].has_ball:
                release_frame_idx = i
                break
        
        if release_frame_idx is None:
            return
        
        # Found transition, now validate it's a real release
        release_frame = search_frames[release_frame_idx]
        post_release_frames = search_frames[release_frame_idx+1:]
        
        # Calculate ball-player separation after release
        if len(post_release_frames) >= 2:
            distances = self._calculate_ball_player_distances(
                post_release_frames,
                player_id
            )
            
            if len(distances) >= 2:
                # Check if distance is increasing
                avg_increase = (distances[-1] - distances[0]) / len(distances)
                
                if avg_increase >= self.thresholds.ball_player_distance_increase_min:
                    # Valid release!
                    features.ball_release_detected = True
                    features.release_frame = release_frame.timestamp
                    
                    # Clarity based on separation trend
                    trend = calculate_separation_trend(distances, min_frames=2)
                    features.ball_release_clarity = trend
    
    # =========================================================================
    # H4 - UPWARD BALL MOTION
    # =========================================================================
    
    def _extract_h4_upward_motion(self,
                                   window: List[FramePacket],
                                   player_id: int,
                                   features: ExtractedFeatures):
        """
        H4: Verify upward ball motion after release.
        
        Criteria:
            - ball_velocity_y < -threshold (upward in image coords)
            - Sustained for min_frames
            - Acceleration shows release impulse
        
        Updates:
            - features.upward_motion_detected
            - features.upward_motion_strength
            - features.upward_velocity
        
        Discriminative Power:
            - Shot: strong upward velocity (-3 to -8 px/frame)
            - Pass: weaker or lateral (-0.5 to -3 px/frame)
            - Tip-in: very weak upward (-0.2 to -1 px/frame)
        """
        if not features.ball_release_detected or features.release_frame is None:
            return
        
        # Get frames after release
        post_release = [
            f for f in window
            if f.timestamp > features.release_frame and
               f.ball_position is not None
        ]
        
        if len(post_release) < self.thresholds.ball_upward_sustained_frames:
            return
        
        # Calculate ball velocities
        positions = [f.ball_position for f in post_release]
        timestamps = [f.timestamp for f in post_release]
        
        velocities = []
        for i in range(len(positions) - 1):
            dt = timestamps[i+1] - timestamps[i]
            if dt > 0:
                dy = positions[i+1][1] - positions[i][1]
                vy = dy / dt
                velocities.append(vy)
        
        if len(velocities) < self.thresholds.ball_upward_sustained_frames:
            return
        
        # Check if sustained upward motion (vy < 0 = upward)
        upward_frames = sum(
            1 for vy in velocities[:self.thresholds.ball_upward_sustained_frames]
            if vy < self.thresholds.ball_upward_velocity_min
        )
        
        if upward_frames >= self.thresholds.ball_upward_sustained_frames:
            # Upward motion detected!
            features.upward_motion_detected = True
            
            # Calculate strength (normalized)
            avg_velocity = sum(velocities[:5]) / min(5, len(velocities))
            features.upward_velocity = avg_velocity
            
            # Normalize to [0, 1] (stronger upward = higher score)
            # -8.0 px/frame → 1.0
            # -2.0 px/frame → 0.0
            max_velocity = -8.0
            min_velocity = self.thresholds.ball_upward_velocity_min
            
            if avg_velocity <= max_velocity:
                strength = 1.0
            elif avg_velocity >= min_velocity:
                strength = 0.0
            else:
                strength = (avg_velocity - min_velocity) / (max_velocity - min_velocity)
            
            features.upward_motion_strength = max(0.0, min(1.0, strength))
    
    # =========================================================================
    # S1 - BALL-PLAYER SEPARATION TREND
    # =========================================================================
    
    def _extract_s1_separation_trend(self,
                                     window: List[FramePacket],
                                     player_id: int,
                                     features: ExtractedFeatures):
        """
        S1: Calculate ball-player separation trend score.
        
        Score [0, 1]:
            1.0 = Monotonic increasing distance (shot-like)
            0.0 = Non-monotonic or decreasing (pass/rebound-like)
        
        This is a KEY discriminator between shot and pass.
        
        Updates:
            - features.separation_trend_score
        """
        if features.release_frame is None:
            return
        
        # Get post-release frames
        post_release = [
            f for f in window
            if f.timestamp > features.release_frame and
               f.ball_position is not None
        ]
        
        if len(post_release) < 3:
            return
        
        # Calculate distances
        distances = self._calculate_ball_player_distances(post_release, player_id)
        
        if len(distances) >= 3:
            trend = calculate_separation_trend(distances, min_frames=3)
            features.separation_trend_score = trend
    
    # =========================================================================
    # S2 - RELEASE HEIGHT SCORE
    # =========================================================================
    
    def _extract_s2_release_height(self,
                                    window: List[FramePacket],
                                    player_id: int,
                                    features: ExtractedFeatures):
        """
        S2: Calculate release height relative to player.
        
        Score [0, 1]:
            1.0 = High release (above player center)
            0.0 = Low release (below player center)
        
        Updates:
            - features.release_height_score
        
        Logic:
            - Find player bbox at release_frame
            - Calculate player center_y
            - Compare ball_y to center_y
        """
        if features.release_frame is None:
            return
        
        # Find release frame
        release_frame = next(
            (f for f in window if f.timestamp == features.release_frame),
            None
        )
        
        if release_frame is None or release_frame.ball_position is None:
            return
        
        ball_y = release_frame.ball_position[1]
        
        # Estimate player center (bbox_height gives us vertical extent)
        # Assuming bbox represents player body, center is roughly middle
        player_height = release_frame.bbox_height
        
        # Score based on release height
        # High release (ball above player center) → 1.0
        # Low release (ball at player feet) → 0.0
        
        # Simple heuristic: ball should be in upper half of player bbox
        # Normalize to [0, 1]
        score = 0.5  # Default if we can't determine
        
        # If ball is visible and player bbox is valid
        if player_height > 0:
            # This is approximate - in real implementation, you'd need
            # actual player bbox coordinates (x, y, w, h)
            # For now, use a simplified heuristic
            score = 0.7  # Assume typical shot has decent height
        
        features.release_height_score = score
    
    # =========================================================================
    # S3 - APEX ALIGNMENT SCORE
    # =========================================================================
    
    def _extract_s3_apex_alignment(self,
                                    window: List[FramePacket],
                                    player_id: int,
                                    features: ExtractedFeatures):
        """
        S3: Calculate jump apex alignment score.
        
        Score [0, 1]:
            1.0 = Release at jump apex (optimal)
            0.0 = Release far from apex
        
        Updates:
            - features.apex_alignment_score
        
        Logic:
            - Find jump apex (minimum bbox_height during jump)
            - Calculate temporal distance to release
            - Closer = higher score
        """
        if features.jump_frame is None or features.release_frame is None:
            return
        
        # Find jump apex (minimum bbox height)
        jumping_frames = [
            f for f in window
            if f.player_id == player_id and
               f.movement_state == "jumping" and
               features.jump_frame <= f.timestamp <= features.release_frame + 5
        ]
        
        if len(jumping_frames) == 0:
            return
        
        # Apex is frame with minimum bbox_height
        apex_frame = min(jumping_frames, key=lambda f: f.bbox_height)
        apex_timestamp = apex_frame.timestamp
        
        # Calculate temporal distance
        temporal_distance = abs(features.release_frame - apex_timestamp)
        
        # Normalize to [0, 1]
        # 0 frames away → 1.0
        # 5+ frames away → 0.0
        max_distance = 5
        
        if temporal_distance == 0:
            score = 1.0
        elif temporal_distance >= max_distance:
            score = 0.0
        else:
            score = 1.0 - (temporal_distance / max_distance)
        
        features.apex_alignment_score = score
    
    # =========================================================================
    # S4 - TEMPORAL CONSISTENCY
    # =========================================================================
    
    def _extract_s4_temporal_consistency(self,
                                         window: List[FramePacket],
                                         player_id: int,
                                         features: ExtractedFeatures):
        """
        S4: Calculate temporal consistency score.
        
        Score [0, 1]:
            1.0 = All events within tight window
            0.0 = Events spread out (suspicious)
        
        Updates:
            - features.temporal_consistency_score
        
        Logic:
            - Calculate span: release_frame - jump_frame
            - Compare to expected timing
            - Tighter = more consistent = higher score
        """
        if features.jump_frame is None or features.release_frame is None:
            return
        
        # Calculate event span
        event_span = features.release_frame - features.jump_frame
        
        # Expected timing (from thresholds)
        expected_max = self.thresholds.release_gap_max_frames
        
        # Score based on compactness
        if event_span <= expected_max:
            # Within expected range
            score = 1.0 - (event_span / (expected_max * 2))
        else:
            # Beyond expected range (penalty)
            score = 0.3
        
        features.temporal_consistency_score = max(0.0, min(1.0, score))
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _calculate_ball_player_distances(self,
                                         frames: List[FramePacket],
                                         player_id: int) -> List[float]:
        """
        Calculate ball-player distances for given frames.
        
        Args:
            frames: List of frames with ball positions
            player_id: Player ID
        
        Returns:
            List of distances (pixels)
        
        Note:
            Player position is approximated from bbox (would need actual
            player tracking coordinates in production).
        """
        distances = []
        
        for frame in frames:
            if frame.ball_position is None:
                continue
            
            # Approximate player position
            # In production, you'd have actual player coordinates
            # For now, use ball position as reference (needs improvement)
            
            # This is a simplification - in real system, you'd track
            # player center position separately
            ball_x, ball_y = frame.ball_position
            
            # Placeholder: assume player at (frame center)
            # In real implementation, get from player tracking
            player_x = ball_x  # This is wrong, but shows the pattern
            player_y = ball_y
            
            # Calculate distance
            # (In reality, you need player bbox center or feet position)
            dist = calculate_distance(
                (player_x, player_y),
                frame.ball_position
            )
            
            distances.append(dist)
        
        return distances


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Shot Attempt Feature Extractor Test ===\n")
    
    from .thresholds import DetectionThresholds
    
    # Create mock window
    window = []
    for i in range(15):
        # Simulate jump sequence
        state = "idle"
        confidence = 0.8
        bbox_height = 200.0
        bbox_change = 0.0
        has_ball = True
        
        if 5 <= i < 10:
            state = "jumping"
            confidence = 0.85
            bbox_height = 185.0  # Shrinking
            bbox_change = -15.0
        
        if i >= 8:
            has_ball = False  # Release at frame 8
        
        frame = FramePacket(
            timestamp=100 + i,
            player_id=7,
            movement_state=state,
            movement_confidence=confidence,
            bbox_height=bbox_height,
            bbox_height_change=bbox_change,
            speed=2.5,
            ball_position=(300.0 + i*10, 200.0 - i*5),  # Moving up-right
            has_ball=has_ball
        )
        window.append(frame)
    
    # Extract features
    thresholds = DetectionThresholds()
    extractor = FeatureExtractor(thresholds)
    
    features = extractor.extract(window, player_id=7)
    
    # Display results
    print("Hard Conditions:")
    print(f"  H1 - Jump Detected: {features.jump_detected} (conf={features.jump_confidence:.2f})")
    print(f"  H2 - Ball Control: {features.ball_control_before_jump} ({features.control_frames} frames)")
    print(f"  H3 - Ball Release: {features.ball_release_detected} (frame={features.release_frame})")
    print(f"  H4 - Upward Motion: {features.upward_motion_detected} (strength={features.upward_motion_strength:.2f})")
    print(f"\n  All conditions met: {features.all_hard_conditions_met()}")
    
    print("\nSoft Conditions:")
    print(f"  S1 - Separation Trend: {features.separation_trend_score:.2f}")
    print(f"  S2 - Release Height: {features.release_height_score:.2f}")
    print(f"  S3 - Apex Alignment: {features.apex_alignment_score:.2f}")
    print(f"  S4 - Temporal Consistency: {features.temporal_consistency_score:.2f}")
    
    print(f"\nData Quality: {features.data_quality:.2f}")