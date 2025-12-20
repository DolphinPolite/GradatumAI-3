"""
Shot Attempt Detector - Utility Functions and Data Structures

Purpose:
    - Define all data structures (input/output contracts)
    - Provide validation functions
    - Helper functions for common operations
    - Confidence calculation (SINGLE SOURCE OF TRUTH)

Design Principles:
    - Type-safe dataclasses
    - Explicit validation with error messages
    - Pure functions (no side effects)
    - Single responsibility

Author: Shot Detection Module
Date: 2024
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
import math


# =============================================================================
# INPUT DATA STRUCTURE
# =============================================================================

@dataclass
class FramePacket:
    """
    Input data structure for a single frame.
    
    This is the contract between upstream modules (movement classifier,
    ball tracker) and the shot attempt detector.
    
    Attributes:
        timestamp: Frame index (int)
        player_id: Player identifier
        
        # From Movement Classifier
        movement_state: idle/walking/running/jumping/landing
        movement_confidence: Classifier confidence [0,1]
        bbox_height: Player bounding box height (pixels)
        bbox_height_change: Height change from previous frame (optional)
        speed: Player speed (m/s, optional)
        acceleration: Player acceleration (m/s², optional)
        
        # From Ball Tracker
        ball_position: [x, y] in frame coordinates (None if not visible)
        has_ball: Boolean flag indicating ball possession
    """
    
    # Required fields
    timestamp: int
    player_id: int
    
    # Movement data
    movement_state: str
    movement_confidence: float
    bbox_height: float
    
    # Optional movement data
    bbox_height_change: Optional[float] = None
    speed: Optional[float] = None
    acceleration: Optional[float] = None
    
    # Ball data
    ball_position: Optional[Tuple[float, float]] = None
    has_ball: bool = False
    
    def is_valid(self) -> Tuple[bool, str]:
        """
        Validate frame packet data.
        
        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        if self.timestamp < 0:
            return False, f"Invalid timestamp: {self.timestamp}"
        
        if self.player_id < 0:
            return False, f"Invalid player_id: {self.player_id}"
        
        # Check movement state
        valid_states = {'idle', 'walking', 'running', 'jumping', 'landing'}
        if self.movement_state not in valid_states:
            return False, f"Invalid movement_state: {self.movement_state}"
        
        # Check confidence range
        if not (0.0 <= self.movement_confidence <= 1.0):
            return False, f"movement_confidence out of range: {self.movement_confidence}"
        
        # Check bbox height
        if self.bbox_height <= 0:
            return False, f"Invalid bbox_height: {self.bbox_height}"
        
        # Check optional fields if present
        if self.speed is not None and self.speed < 0:
            return False, f"Invalid speed: {self.speed}"
        
        if self.ball_position is not None:
            if len(self.ball_position) != 2:
                return False, f"ball_position must be (x,y), got {self.ball_position}"
            if any(math.isnan(v) or math.isinf(v) for v in self.ball_position):
                return False, "ball_position contains NaN or Inf"
        
        return True, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/export."""
        return asdict(self)


# =============================================================================
# OUTPUT DATA STRUCTURE
# =============================================================================

@dataclass
class ShotEvent:
    """
    Shot attempt detection result.
    
    This is the output contract of the shot attempt detector.
    
    Attributes:
        event_type: Always "shot_attempt"
        player_id: Player who attempted the shot
        start_frame: Frame where detection window starts
        release_frame: Frame where ball was released
        confidence: Final confidence score [0,1]
        reasoning: Human-readable explanation
        features: Dictionary of extracted features (for debugging)
    """
    
    event_type: str = "shot_attempt"
    player_id: int = -1
    start_frame: int = -1
    release_frame: int = -1
    confidence: float = 0.0
    reasoning: str = ""
    
    features: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return asdict(self)
    
    def __repr__(self) -> str:
        """Pretty string representation."""
        return (
            f"ShotEvent(player={self.player_id}, "
            f"frame={self.release_frame}, "
            f"conf={self.confidence:.2f})"
        )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_frame_packet(packet: FramePacket) -> Tuple[bool, str]:
    """
    Validate input frame packet.
    
    Args:
        packet: FramePacket to validate
    
    Returns:
        (is_valid, error_message)
    
    Example:
        >>> packet = FramePacket(timestamp=100, player_id=7, ...)
        >>> is_valid, msg = validate_frame_packet(packet)
        >>> if not is_valid:
        ...     print(f"Validation failed: {msg}")
    """
    return packet.is_valid()


def validate_window(
    window: List[FramePacket],
    min_size: int = 10
) -> Tuple[bool, str]:
    """
    Validate temporal window of frames.
    
    Checks:
        - Minimum window size
        - All frames valid
        - Consistent player_id
        - Monotonic timestamps
    
    Args:
        window: List of FramePackets
        min_size: Minimum required frames
    
    Returns:
        (is_valid, error_message)
    """
    if len(window) < min_size:
        return False, f"Window too small: {len(window)} < {min_size}"
    
    if len(window) == 0:
        return False, "Empty window"
    
    # Check all frames valid
    for i, frame in enumerate(window):
        is_valid, msg = frame.is_valid()
        if not is_valid:
            return False, f"Frame {i} invalid: {msg}"
    
    # Check consistent player_id
    player_ids = {frame.player_id for frame in window}
    if len(player_ids) > 1:
        return False, f"Multiple player_ids in window: {player_ids}"
    
    # Check monotonic timestamps
    timestamps = [frame.timestamp for frame in window]
    if timestamps != sorted(timestamps):
        return False, "Non-monotonic timestamps"
    
    return True, ""


# =============================================================================
# GEOMETRY HELPERS
# =============================================================================

def calculate_distance(p1: Tuple[float, float], 
                      p2: Tuple[float, float]) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        p1: Point (x, y)
        p2: Point (x, y)
    
    Returns:
        Distance in pixels
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.sqrt(dx*dx + dy*dy)


def calculate_velocity(
    positions: List[Tuple[float, float]],
    timestamps: List[int]
) -> Optional[Tuple[float, float]]:
    """
    Calculate velocity from position history.
    
    Uses simple finite difference: v = Δp / Δt
    
    Args:
        positions: List of (x, y) positions
        timestamps: Corresponding frame indices
    
    Returns:
        (vx, vy) velocity vector or None if insufficient data
    """
    if len(positions) < 2 or len(timestamps) < 2:
        return None
    
    if len(positions) != len(timestamps):
        return None
    
    # Use last two points for instantaneous velocity
    dt = timestamps[-1] - timestamps[-2]
    if dt == 0:
        return None
    
    dx = positions[-1][0] - positions[-2][0]
    dy = positions[-1][1] - positions[-2][1]
    
    vx = dx / dt
    vy = dy / dt
    
    return (vx, vy)


def smooth_velocity(
    velocities: List[Tuple[float, float]],
    window_size: int = 3
) -> Optional[Tuple[float, float]]:
    """
    Smooth velocity using moving average.
    
    Args:
        velocities: List of (vx, vy) tuples
        window_size: Smoothing window size
    
    Returns:
        Smoothed (vx, vy) or None
    """
    if len(velocities) < window_size:
        return None
    
    # Take last window_size velocities
    recent = velocities[-window_size:]
    
    vx_avg = sum(v[0] for v in recent) / len(recent)
    vy_avg = sum(v[1] for v in recent) / len(recent)
    
    return (vx_avg, vy_avg)


def calculate_separation_trend(
    distances: List[float],
    min_frames: int = 3
) -> float:
    """
    Calculate ball-player separation trend.
    
    Returns score [0, 1] indicating how monotonically distance increases.
    1.0 = perfect monotonic increase (shot-like)
    0.0 = non-monotonic or decreasing (pass/rebound-like)
    
    Args:
        distances: List of ball-player distances (pixels)
        min_frames: Minimum frames to analyze
    
    Returns:
        Trend score [0, 1]
    
    Algorithm:
        - Count monotonic increases
        - Normalize by maximum possible increases
    """
    if len(distances) < min_frames:
        return 0.0
    
    # Count increasing pairs
    increases = 0
    total_pairs = len(distances) - 1
    
    for i in range(total_pairs):
        if distances[i+1] > distances[i]:
            increases += 1
    
    # Normalize
    if total_pairs == 0:
        return 0.0
    
    return increases / total_pairs


# =============================================================================
# CONFIDENCE CALCULATION (SINGLE SOURCE OF TRUTH)
# =============================================================================

def calculate_confidence_score(
    jump_detected: bool,
    jump_confidence: float,
    ball_release_detected: bool,
    ball_release_clarity: float,
    upward_motion_detected: bool,
    upward_motion_strength: float,
    temporal_consistency: float,
    weights: Dict[str, float],
    soft_scores: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate final confidence score for shot attempt.
    
    This is the SINGLE SOURCE OF TRUTH for confidence calculation.
    All other modules must use this function.
    
    Args:
        jump_detected: Hard condition - jump detected
        jump_confidence: Jump detection confidence [0,1]
        ball_release_detected: Hard condition - ball released
        ball_release_clarity: Release clarity score [0,1]
        upward_motion_detected: Hard condition - upward motion
        upward_motion_strength: Upward velocity strength [0,1]
        temporal_consistency: Event timing score [0,1]
        weights: Weight dictionary from thresholds
        soft_scores: Optional soft condition scores (bonuses)
    
    Returns:
        Final confidence score [0, 1]
    
    Formula:
        base_confidence = weighted_sum(hard_conditions)
        bonuses = sum(soft_scores)
        final = min(base_confidence + bonuses, 1.0)
    
    Hard Conditions (must all be True):
        - jump_detected
        - ball_release_detected
        - upward_motion_detected
    
    Note:
        If any hard condition is False, this function should not be called
        (detector.py enforces this).
    """
    # Sanity check: hard conditions must be met
    if not (jump_detected and ball_release_detected and upward_motion_detected):
        return 0.0
    
    # Base confidence from weighted hard conditions
    base_confidence = (
        weights['jump'] * jump_confidence +
        weights['release'] * ball_release_clarity +
        weights['velocity'] * upward_motion_strength +
        weights['temporal'] * temporal_consistency
    )
    
    # Add soft condition bonuses
    total_bonus = 0.0
    if soft_scores:
        total_bonus += soft_scores.get('separation_trend', 0.0) * weights.get('bonus_separation', 0.0)
        total_bonus += soft_scores.get('release_height', 0.0) * weights.get('bonus_height', 0.0)
        total_bonus += soft_scores.get('apex_alignment', 0.0) * weights.get('bonus_apex', 0.0)
    
    # Final confidence (capped at 1.0)
    final_confidence = min(base_confidence + total_bonus, 1.0)
    
    return final_confidence


# =============================================================================
# REASONING GENERATION
# =============================================================================

def format_reasoning(
    conditions: Dict[str, Any],
    scores: Dict[str, float],
    max_length: int = 200
) -> str:
    """
    Generate human-readable reasoning string.
    
    Args:
        conditions: Dictionary of condition results
        scores: Dictionary of scores
        max_length: Maximum string length
    
    Returns:
        Formatted reasoning string
    
    Example:
        >>> conditions = {
        ...     'jump_detected': True,
        ...     'ball_release': True,
        ...     'upward_motion': True
        ... }
        >>> scores = {'jump_conf': 0.85, 'velocity': 0.78}
        >>> reasoning = format_reasoning(conditions, scores)
        >>> print(reasoning)
        "jump(0.85) + release + upward(0.78) | consistent"
    """
    parts = []
    
    # Hard conditions
    if conditions.get('jump_detected'):
        conf = scores.get('jump_confidence', 0.0)
        parts.append(f"jump({conf:.2f})")
    
    if conditions.get('ball_release_detected'):
        parts.append("release")
    
    if conditions.get('upward_motion_detected'):
        strength = scores.get('upward_motion_strength', 0.0)
        parts.append(f"upward({strength:.2f})")
    
    # Temporal consistency
    temporal = scores.get('temporal_consistency', 0.0)
    if temporal > 0.8:
        parts.append("consistent")
    elif temporal > 0.5:
        parts.append("partial-timing")
    
    # Soft bonuses
    if scores.get('separation_trend', 0.0) > 0.7:
        parts.append("sep+")
    
    if scores.get('release_height', 0.0) > 0.7:
        parts.append("high")
    
    reasoning = " + ".join(parts) if parts else "low_quality"
    
    # Truncate if too long
    if len(reasoning) > max_length:
        reasoning = reasoning[:max_length-3] + "..."
    
    return reasoning


# =============================================================================
# DATA QUALITY CHECKS
# =============================================================================

def check_data_quality(window: List[FramePacket]) -> float:
    """
    Assess data quality of temporal window.
    
    Checks:
        - Missing ball positions
        - Movement confidence
        - Feature completeness
    
    Args:
        window: List of FramePackets
    
    Returns:
        Quality score [0, 1]
        1.0 = perfect data
        0.0 = unusable data
    """
    if len(window) == 0:
        return 0.0
    
    # Count missing ball positions
    ball_visible = sum(1 for f in window if f.ball_position is not None)
    ball_ratio = ball_visible / len(window)
    
    # Average movement confidence
    avg_conf = sum(f.movement_confidence for f in window) / len(window)
    
    # Feature completeness (optional fields present)
    features_present = sum(
        1 for f in window
        if f.bbox_height_change is not None and f.speed is not None
    )
    feature_ratio = features_present / len(window)
    
    # Weighted quality score
    quality = (
        0.5 * ball_ratio +      # Ball visibility most important
        0.3 * avg_conf +         # Movement confidence
        0.2 * feature_ratio      # Optional features
    )
    
    return quality


# =============================================================================
# BALL OWNERSHIP INFERENCE
# =============================================================================

def infer_ball_owner(
    window: List[FramePacket],
    player_id: int
) -> Tuple[bool, int]:
    """
    Infer if player had ball ownership in window.
    
    Uses has_ball flags from ball tracker to determine ownership.
    
    Args:
        window: List of FramePackets
        player_id: Player to check
    
    Returns:
        (had_ownership, num_frames_with_ball)
    
    Algorithm:
        - Count frames where has_ball = True
        - Must have ball for majority of window (>50%)
    """
    if len(window) == 0:
        return False, 0
    
    # Filter frames for this player
    player_frames = [f for f in window if f.player_id == player_id]
    
    if len(player_frames) == 0:
        return False, 0
    
    # Count frames with ball
    with_ball = sum(1 for f in player_frames if f.has_ball)
    
    # Ownership if majority of frames
    had_ownership = with_ball > len(player_frames) * 0.5
    
    return had_ownership, with_ball


# =============================================================================
# NUMPY HELPERS
# =============================================================================

def safe_array_operation(
    array: Optional[np.ndarray],
    operation: str,
    default: float = 0.0
) -> float:
    """
    Safely perform array operation with fallback.
    
    Args:
        array: Numpy array or None
        operation: 'mean', 'std', 'max', 'min'
        default: Default value if array is None/empty
    
    Returns:
        Result or default
    """
    if array is None or len(array) == 0:
        return default
    
    try:
        if operation == 'mean':
            return float(np.mean(array))
        elif operation == 'std':
            return float(np.std(array))
        elif operation == 'max':
            return float(np.max(array))
        elif operation == 'min':
            return float(np.min(array))
        else:
            return default
    except Exception:
        return default


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Shot Attempt Detector Utils Test ===\n")
    
    # Test FramePacket
    print("1. FramePacket Validation:")
    packet = FramePacket(
        timestamp=100,
        player_id=7,
        movement_state="jumping",
        movement_confidence=0.85,
        bbox_height=250.0,
        bbox_height_change=-15.0,
        ball_position=(320.0, 240.0),
        has_ball=True
    )
    
    is_valid, msg = packet.is_valid()
    print(f"   Valid: {is_valid}")
    if not is_valid:
        print(f"   Error: {msg}")
    
    # Test confidence calculation
    print("\n2. Confidence Calculation:")
    weights = {
        'jump': 0.30,
        'release': 0.25,
        'velocity': 0.25,
        'temporal': 0.20,
        'bonus_separation': 0.10,
        'bonus_height': 0.05,
        'bonus_apex': 0.05
    }
    
    confidence = calculate_confidence_score(
        jump_detected=True,
        jump_confidence=0.85,
        ball_release_detected=True,
        ball_release_clarity=0.90,
        upward_motion_detected=True,
        upward_motion_strength=0.80,
        temporal_consistency=0.95,
        weights=weights,
        soft_scores={'separation_trend': 0.85, 'release_height': 0.70}
    )
    
    print(f"   Final confidence: {confidence:.3f}")
    
    # Test reasoning generation
    print("\n3. Reasoning Generation:")
    conditions = {
        'jump_detected': True,
        'ball_release_detected': True,
        'upward_motion_detected': True
    }
    scores = {
        'jump_confidence': 0.85,
        'upward_motion_strength': 0.80,
        'temporal_consistency': 0.95,
        'separation_trend': 0.85
    }
    
    reasoning = format_reasoning(conditions, scores)
    print(f"   Reasoning: {reasoning}")
    
    # Test ShotEvent
    print("\n4. ShotEvent Creation:")
    event = ShotEvent(
        player_id=7,
        start_frame=95,
        release_frame=102,
        confidence=confidence,
        reasoning=reasoning,
        features={'jump_height': 0.6, 'release_speed': 5.2}
    )
    print(f"   {event}")
    print(f"   Export: {event.to_dict()}")