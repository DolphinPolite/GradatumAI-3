"""
utils.py
Helper functions for sequence parsing.
"""
from typing import List
from events import InputEvent
from thresholds import SequenceThresholds


def calculate_event_confidence(events: List[InputEvent]) -> float:
    """
    Calculate average confidence from a list of events.
    
    Args:
        events: List of InputEvents
        
    Returns:
        Average confidence score [0, 1]
    """
    if not events:
        return 0.0
    
    confidences = [e.confidence for e in events]
    return sum(confidences) / len(confidences)


def calculate_temporal_consistency(
    events: List[InputEvent],
    thresholds: SequenceThresholds
) -> float:
    """
    Calculate temporal consistency score based on gaps between events.
    
    Lower gaps → higher consistency.
    Applies penalties for large gaps and excessive duration.
    
    Args:
        events: Ordered list of InputEvents
        thresholds: Configuration parameters
        
    Returns:
        Temporal consistency score [0, 1]
    """
    if len(events) < 2:
        return 1.0  # Single event has perfect consistency
    
    # Calculate gaps between consecutive events
    gaps = []
    for i in range(len(events) - 1):
        gap = events[i + 1].timestamp - events[i].timestamp
        gaps.append(gap)
    
    # Base score starts at 1.0
    score = 1.0
    
    # Apply gap penalties
    for gap in gaps:
        penalty = gap * thresholds.gap_penalty_rate
        score -= penalty
    
    # Apply duration penalty if sequence is too long
    total_duration = events[-1].timestamp - events[0].timestamp
    if total_duration > thresholds.duration_penalty_threshold:
        excess = total_duration - thresholds.duration_penalty_threshold
        penalty = excess * thresholds.duration_penalty_rate
        score -= penalty
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def calculate_sequence_confidence(
    events: List[InputEvent],
    thresholds: SequenceThresholds
) -> float:
    """
    Calculate overall sequence confidence as weighted combination.
    
    Args:
        events: Ordered list of InputEvents
        thresholds: Configuration parameters
        
    Returns:
        Overall confidence score [0, 1]
    """
    event_conf = calculate_event_confidence(events)
    temporal_conf = calculate_temporal_consistency(events, thresholds)
    
    # Weighted combination
    confidence = (
        thresholds.confidence_event_weight * event_conf +
        thresholds.confidence_temporal_weight * temporal_conf
    )
    
    return confidence


def get_max_gap(events: List[InputEvent]) -> int:
    """
    Get maximum gap between consecutive events.
    
    Args:
        events: Ordered list of InputEvents
        
    Returns:
        Maximum gap in frames, or 0 if less than 2 events
    """
    if len(events) < 2:
        return 0
    
    gaps = [
        events[i + 1].timestamp - events[i].timestamp
        for i in range(len(events) - 1)
    ]
    return max(gaps)


def format_event_chain(events: List[InputEvent]) -> str:
    """
    Format event chain for human-readable reasoning.
    
    Args:
        events: Ordered list of InputEvents
        
    Returns:
        Formatted string like "dribble → dribble → shot"
    """
    if not events:
        return "(empty)"
    
    return " → ".join(e.event_type for e in events)


def frames_to_seconds(frames: int, fps: int = 30) -> float:
    """
    Convert frames to seconds.
    
    Args:
        frames: Number of frames
        fps: Frames per second (default 30)
        
    Returns:
        Time in seconds
    """
    return frames / fps