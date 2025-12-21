"""
temporal_graph.py
Per-player temporal state management and event chain tracking.
"""
from typing import List, Optional
from collections import deque
from events import InputEvent, SequenceEvent
from thresholds import SequenceThresholds
from rules import RuleEngine


class PlayerTemporalBuffer:
    """
    Maintains temporal event chain for a single player.
    
    Acts as a soft state machine that accumulates events and attempts
    to form sequences when terminal events (e.g., shots) occur.
    """
    
    def __init__(self, player_id: str, thresholds: SequenceThresholds):
        self.player_id = player_id
        self.thresholds = thresholds
        self.rule_engine = RuleEngine(thresholds)
        
        # Event buffer (bounded deque for memory efficiency)
        self.events: deque[InputEvent] = deque(maxlen=thresholds.event_buffer_size)
        
        # Track last event timestamp for staleness detection
        self.last_event_time: Optional[int] = None
    
    def add_event(self, event: InputEvent) -> Optional[SequenceEvent]:
        """
        Add a new event to the buffer and attempt sequence formation.
        
        Args:
            event: New InputEvent to add
            
        Returns:
            SequenceEvent if a terminal event triggers sequence formation, None otherwise
        """
        if event.player_id != self.player_id:
            raise ValueError(f"Event player_id {event.player_id} doesn't match buffer player_id {self.player_id}")
        
        # Clean stale events before adding new one
        self._clean_stale_events(event.timestamp)
        
        # Check for large gap - invalidates current chain
        if self.last_event_time is not None:
            gap = event.timestamp - self.last_event_time
            if gap > self.thresholds.max_gap_frames:
                # Gap too large - clear buffer and start fresh
                self.events.clear()
        
        # Add new event
        self.events.append(event)
        self.last_event_time = event.timestamp
        
        # Check if this is a terminal event (shot)
        if event.event_type == "shot":
            return self._attempt_sequence_formation()
        
        return None
    
    def _clean_stale_events(self, current_time: int):
        """
        Remove events that are too old relative to current time.
        
        Args:
            current_time: Current timestamp (frame index)
        """
        if not self.events:
            return
        
        # Remove events older than stale_event_timeout
        while self.events:
            oldest = self.events[0]
            age = current_time - oldest.timestamp
            
            if age > self.thresholds.stale_event_timeout:
                self.events.popleft()
            else:
                break
    
    def _attempt_sequence_formation(self) -> Optional[SequenceEvent]:
        """
        Attempt to form a sequence from current event buffer.
        
        Called when a terminal event (shot) is added.
        
        Returns:
            SequenceEvent if formation succeeds, None otherwise
        """
        if not self.events:
            return None
        
        # Convert deque to list for rule evaluation
        event_list = list(self.events)
        
        # Filter out events that don't contribute to the sequence
        filtered_events = self._filter_relevant_events(event_list)
        
        if not filtered_events:
            return None
        
        # Validate temporal constraints
        if not self._validate_temporal_constraints(filtered_events):
            return None
        
        # Evaluate against rules
        sequence = self.rule_engine.evaluate(filtered_events)
        
        # Clear buffer after sequence formation (successful or not)
        # This prevents duplicate sequence detection
        self.events.clear()
        self.last_event_time = None
        
        return sequence
    
    def _filter_relevant_events(self, events: List[InputEvent]) -> List[InputEvent]:
        """
        Filter events to keep only those relevant for sequence formation.
        
        Strategy:
          - Keep all dribbles and shots
          - Keep movement events if they're recent enough
          - Remove redundant/noisy movement events
        
        Args:
            events: List of InputEvents
            
        Returns:
            Filtered list of relevant events
        """
        if not events:
            return []
        
        # Always include the terminal shot
        shot_event = events[-1] if events[-1].event_type == "shot" else None
        
        filtered = []
        
        for event in events:
            # Always keep dribbles and shots
            if event.event_type in ["dribble", "shot"]:
                filtered.append(event)
            
            # Keep movement if it's reasonably close to the shot
            elif event.event_type == "movement" and shot_event:
                gap = shot_event.timestamp - event.timestamp
                if gap <= self.thresholds.movement_to_shot_max_gap * 2:  # 2x buffer
                    filtered.append(event)
        
        return filtered
    
    def _validate_temporal_constraints(self, events: List[InputEvent]) -> bool:
        """
        Validate that event chain satisfies temporal constraints.
        
        Args:
            events: List of InputEvents
            
        Returns:
            True if constraints satisfied, False otherwise
        """
        if len(events) < 1:
            return False
        
        if len(events) == 1:
            return True  # Single shot is always valid
        
        # Check minimum duration
        duration = events[-1].timestamp - events[0].timestamp
        if duration < self.thresholds.min_sequence_duration:
            return False
        
        # Check maximum duration
        if duration > self.thresholds.max_sequence_duration:
            return False
        
        return True
    
    def reset(self):
        """Clear all state."""
        self.events.clear()
        self.last_event_time = None
    
    def __repr__(self):
        return f"PlayerTemporalBuffer(player={self.player_id}, events={len(self.events)})"


class TemporalGraph:
    """
    Manages temporal buffers for all players.
    
    Maintains separate state for each player and routes events appropriately.
    """
    
    def __init__(self, thresholds: SequenceThresholds):
        self.thresholds = thresholds
        self.player_buffers: dict[str, PlayerTemporalBuffer] = {}
    
    def add_event(self, event: InputEvent) -> Optional[SequenceEvent]:
        """
        Add event to the appropriate player's buffer.
        
        Args:
            event: InputEvent to process
            
        Returns:
            SequenceEvent if formed, None otherwise
        """
        # Get or create buffer for this player
        if event.player_id not in self.player_buffers:
            self.player_buffers[event.player_id] = PlayerTemporalBuffer(
                event.player_id,
                self.thresholds
            )
        
        buffer = self.player_buffers[event.player_id]
        return buffer.add_event(event)
    
    def get_buffer(self, player_id: str) -> Optional[PlayerTemporalBuffer]:
        """Get buffer for a specific player."""
        return self.player_buffers.get(player_id)
    
    def reset_player(self, player_id: str):
        """Reset state for a specific player."""
        if player_id in self.player_buffers:
            self.player_buffers[player_id].reset()
    
    def reset_all(self):
        """Reset state for all players."""
        for buffer in self.player_buffers.values():
            buffer.reset()
    
    def get_active_players(self) -> List[str]:
        """Get list of player IDs with active buffers."""
        return list(self.player_buffers.keys())
    
    def __repr__(self):
        return f"TemporalGraph(players={len(self.player_buffers)})"