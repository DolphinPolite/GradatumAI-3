"""
events.py
Data classes for input events and output sequence events.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class InputEvent:
    """
    Low-level detected event from upstream modules.
    
    Attributes:
        timestamp: Frame index when event occurred
        player_id: Unique identifier for the player
        event_type: Type of event ("movement", "dribble", "shot")
        metadata: Additional event-specific data (confidence, counts, etc.)
    """
    timestamp: int
    player_id: str
    event_type: str  # "movement" | "dribble" | "shot"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event type."""
        valid_types = {"movement", "dribble", "shot"}
        if self.event_type not in valid_types:
            raise ValueError(f"Invalid event_type: {self.event_type}. Must be one of {valid_types}")
    
    @property
    def confidence(self) -> float:
        """Extract confidence from metadata, default to 1.0 if not present."""
        return self.metadata.get("confidence", 1.0)


@dataclass
class SequenceEvent:
    """
    High-level basketball action sequence.
    
    Attributes:
        player_id: Unique identifier for the player
        start_frame: First frame of the sequence
        end_frame: Last frame of the sequence
        sequence_type: Type of sequence (e.g., "dribble_to_shot")
        involved_events: Ordered list of InputEvents that form this sequence
        confidence: Overall confidence score [0, 1]
        reasoning: Human-readable explanation of why this sequence was identified
    """
    player_id: str
    start_frame: int
    end_frame: int
    sequence_type: str
    involved_events: List[InputEvent]
    confidence: float
    reasoning: str
    
    def __post_init__(self):
        """Validate sequence properties."""
        if self.start_frame > self.end_frame:
            raise ValueError(f"start_frame ({self.start_frame}) cannot be after end_frame ({self.end_frame})")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if not self.involved_events:
            raise ValueError("involved_events cannot be empty")
    
    @property
    def duration_frames(self) -> int:
        """Calculate sequence duration in frames."""
        return self.end_frame - self.start_frame
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "sequence_type": self.sequence_type,
            "duration_frames": self.duration_frames,
            "num_events": len(self.involved_events),
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "event_types": [e.event_type for e in self.involved_events]
        }