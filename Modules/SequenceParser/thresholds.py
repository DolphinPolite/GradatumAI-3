"""
thresholds.py
Configurable timing and confidence parameters for sequence parsing.
"""
from dataclasses import dataclass


@dataclass
class SequenceThresholds:
    """
    Configuration parameters for sequence parsing.
    
    All timing values are in frames (assuming 30 FPS video).
    """
    
    # === Temporal Windows ===
    max_gap_frames: int = 60  # Max frames between events in a sequence (2 seconds @ 30fps)
    min_sequence_duration: int = 15  # Min frames for a valid sequence (0.5 seconds)
    max_sequence_duration: int = 300  # Max frames for a sequence (10 seconds)
    
    # === Dribble-to-Shot Specific ===
    dribble_to_shot_max_gap: int = 45  # Max frames between last dribble and shot (1.5 sec)
    min_dribbles_for_sequence: int = 2  # Minimum dribble events to form a sequence
    
    # === Movement-to-Shot Specific ===
    movement_to_shot_max_gap: int = 30  # Max frames between movement and shot (1 second)
    run_to_shot_min_speed: float = 0.5  # Minimum speed indicator for "run" classification
    
    # === Confidence Calculation ===
    confidence_event_weight: float = 0.6  # Weight for average event confidence
    confidence_temporal_weight: float = 0.4  # Weight for temporal consistency
    min_confidence_threshold: float = 0.5  # Minimum confidence to emit a sequence
    
    # === Temporal Consistency Penalties ===
    gap_penalty_rate: float = 0.01  # Confidence penalty per frame of gap
    duration_penalty_threshold: int = 150  # Start penalizing sequences longer than this (5 sec)
    duration_penalty_rate: float = 0.002  # Penalty per frame over threshold
    
    # === Buffer Management ===
    event_buffer_size: int = 20  # Max events to keep in temporal buffer per player
    stale_event_timeout: int = 180  # Frames after which to clear stale events (6 seconds)
    
    def validate(self):
        """Validate threshold consistency."""
        if self.max_gap_frames < 0:
            raise ValueError("max_gap_frames must be non-negative")
        if self.min_sequence_duration > self.max_sequence_duration:
            raise ValueError("min_sequence_duration cannot exceed max_sequence_duration")
        if self.confidence_event_weight + self.confidence_temporal_weight != 1.0:
            raise ValueError("confidence weights must sum to 1.0")
        if not 0 <= self.min_confidence_threshold <= 1:
            raise ValueError("min_confidence_threshold must be in [0, 1]")


# Default configuration
DEFAULT_THRESHOLDS = SequenceThresholds()
DEFAULT_THRESHOLDS.validate()


# Strict configuration (higher precision, lower recall)
STRICT_THRESHOLDS = SequenceThresholds(
    max_gap_frames=30,
    dribble_to_shot_max_gap=30,
    min_dribbles_for_sequence=3,
    min_confidence_threshold=0.7,
    gap_penalty_rate=0.02
)
STRICT_THRESHOLDS.validate()


# Lenient configuration (higher recall, lower precision)
LENIENT_THRESHOLDS = SequenceThresholds(
    max_gap_frames=90,
    dribble_to_shot_max_gap=60,
    min_dribbles_for_sequence=1,
    min_confidence_threshold=0.3,
    gap_penalty_rate=0.005
)
LENIENT_THRESHOLDS.validate()