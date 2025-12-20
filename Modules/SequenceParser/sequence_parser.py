"""
Sequence Parser
Parses game events into coherent sequences and patterns.
"""

from .config import (
    EVENT_TYPES, MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_GAP,
    MIN_EVENT_CONFIDENCE
)


class GameEvent:
    """Represents a single game event."""
    
    def __init__(self, event_type, timestamp, player_id, confidence=1.0, metadata=None):
        """
        Args:
            event_type: Type of event (from EVENT_TYPES)
            timestamp: Frame number when event occurred
            player_id: ID of player involved
            confidence: Confidence score (0-1)
            metadata: Extra data dict
        """
        self.event_type = event_type
        self.timestamp = timestamp
        self.player_id = player_id
        self.confidence = confidence
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"Event({self.event_type}, ts={self.timestamp}, player={self.player_id})"


class EventSequence:
    """Represents a sequence of connected events."""
    
    def __init__(self, events=None):
        self.events = events or []
        self.team = None
        self.start_ts = None
        self.end_ts = None
        self._update_bounds()
    
    def _update_bounds(self):
        if self.events:
            self.start_ts = min(e.timestamp for e in self.events)
            self.end_ts = max(e.timestamp for e in self.events)
        else:
            self.start_ts = None
            self.end_ts = None
    
    def add_event(self, event):
        """Add event to sequence."""
        self.events.append(event)
        self._update_bounds()
    
    def get_duration(self):
        """Get duration of sequence in frames."""
        if self.start_ts is None or self.end_ts is None:
            return 0
        return self.end_ts - self.start_ts
    
    def __repr__(self):
        return f"Sequence({len(self.events)} events, {self.get_duration()} frames)"


class SequenceParser:
    """Parses raw events into organized sequences."""
    
    def __init__(self):
        self.events = []
        self.sequences = []
    
    def add_event(self, event_type, timestamp, player_id, confidence=1.0, metadata=None):
        """
        Log a game event.
        
        Args:
            event_type: Type of event
            timestamp: Frame number
            player_id: Player ID
            confidence: Confidence score
            metadata: Additional data
        """
        if event_type not in EVENT_TYPES:
            # skip unknown event types
            return False
        
        if confidence < MIN_EVENT_CONFIDENCE:
            return False
        
        event = GameEvent(event_type, timestamp, player_id, confidence, metadata)
        self.events.append(event)
        return True
    
    def parse_sequences(self):
        """
        Parse raw events into sequences.
        Returns list of EventSequence objects.
        """
        if not self.events:
            return []
        
        # sort events by timestamp
        sorted_events = sorted(self.events, key=lambda e: e.timestamp)
        
        sequences = []
        current_seq = EventSequence([sorted_events[0]])
        
        for i in range(1, len(sorted_events)):
            event = sorted_events[i]
            prev_event = sorted_events[i - 1]
            
            time_gap = event.timestamp - prev_event.timestamp
            
            # check if event belongs to current sequence
            if time_gap <= MAX_SEQUENCE_GAP:
                current_seq.add_event(event)
            else:
                # start new sequence
                if len(current_seq.events) >= MIN_SEQUENCE_LENGTH:
                    sequences.append(current_seq)
                current_seq = EventSequence([event])
        
        # add final sequence if valid
        if len(current_seq.events) >= MIN_SEQUENCE_LENGTH:
            sequences.append(current_seq)
        
        self.sequences = sequences
        return sequences
    
    def get_sequence_by_timestamp(self, timestamp):
        """Get the sequence containing a specific timestamp."""
        for seq in self.sequences:
            if seq.start_ts <= timestamp <= seq.end_ts:
                return seq
        return None
    
    def get_sequences_by_player(self, player_id):
        """Get all sequences involving a specific player."""
        result = []
        for seq in self.sequences:
            if any(e.player_id == player_id for e in seq.events):
                result.append(seq)
        return result
    
    def get_event_count_by_type(self):
        """Count events by type."""
        counts = {}
        for event in self.events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts
