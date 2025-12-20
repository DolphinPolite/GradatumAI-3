"""
rules.py
Transition rules for identifying basketball action sequences.
"""
from typing import List, Optional
from events import InputEvent, SequenceEvent
from thresholds import SequenceThresholds
from utils import (
    calculate_sequence_confidence,
    get_max_gap,
    format_event_chain,
    frames_to_seconds
)


class SequenceRule:
    """Base class for sequence detection rules."""
    
    def __init__(self, thresholds: SequenceThresholds):
        self.thresholds = thresholds
    
    def matches(self, events: List[InputEvent]) -> bool:
        """
        Check if event chain matches this rule's pattern.
        
        Args:
            events: Ordered list of InputEvents
            
        Returns:
            True if pattern matches
        """
        raise NotImplementedError
    
    def create_sequence(self, events: List[InputEvent]) -> Optional[SequenceEvent]:
        """
        Create a SequenceEvent from matched events.
        
        Args:
            events: Ordered list of InputEvents that match the pattern
            
        Returns:
            SequenceEvent if valid, None otherwise
        """
        raise NotImplementedError


class DribbleToShotRule(SequenceRule):
    """
    Rule: Dribble sequence followed by shot attempt.
    
    Pattern: [dribble]+ → shot
    Conditions:
      - At least min_dribbles_for_sequence dribble events
      - Gap between last dribble and shot ≤ dribble_to_shot_max_gap
      - Total duration within limits
    """
    
    def matches(self, events: List[InputEvent]) -> bool:
        if len(events) < 2:
            return False
        
        # Must end with a shot
        if events[-1].event_type != "shot":
            return False
        
        # Count dribbles before the shot
        dribble_count = sum(1 for e in events[:-1] if e.event_type == "dribble")
        
        if dribble_count < self.thresholds.min_dribbles_for_sequence:
            return False
        
        # Check gap between last dribble and shot
        dribble_events = [e for e in events[:-1] if e.event_type == "dribble"]
        if dribble_events:
            last_dribble = dribble_events[-1]
            shot = events[-1]
            gap = shot.timestamp - last_dribble.timestamp
            
            if gap > self.thresholds.dribble_to_shot_max_gap:
                return False
        
        return True
    
    def create_sequence(self, events: List[InputEvent]) -> Optional[SequenceEvent]:
        if not self.matches(events):
            return None
        
        player_id = events[0].player_id
        start_frame = events[0].timestamp
        end_frame = events[-1].timestamp
        
        # Calculate confidence
        confidence = calculate_sequence_confidence(events, self.thresholds)
        
        if confidence < self.thresholds.min_confidence_threshold:
            return None
        
        # Count dribbles
        dribble_count = sum(1 for e in events[:-1] if e.event_type == "dribble")
        
        # Build reasoning
        duration = frames_to_seconds(end_frame - start_frame)
        last_dribble = [e for e in events[:-1] if e.event_type == "dribble"][-1]
        gap = events[-1].timestamp - last_dribble.timestamp
        gap_sec = frames_to_seconds(gap)
        
        reasoning = (
            f"Detected dribble-to-shot sequence: {dribble_count} dribbles followed by shot. "
            f"Duration: {duration:.2f}s. "
            f"Gap between last dribble and shot: {gap_sec:.2f}s. "
            f"Event chain: {format_event_chain(events)}."
        )
        
        return SequenceEvent(
            player_id=player_id,
            start_frame=start_frame,
            end_frame=end_frame,
            sequence_type="dribble_to_shot",
            involved_events=events,
            confidence=confidence,
            reasoning=reasoning
        )


class MovementToShotRule(SequenceRule):
    """
    Rule: Movement followed by shot (e.g., catch-and-shoot).
    
    Pattern: movement → shot
    Conditions:
      - Movement event followed by shot
      - Gap between movement and shot ≤ movement_to_shot_max_gap
      - No dribbles in between (otherwise it's a dribble-to-shot)
    """
    
    def matches(self, events: List[InputEvent]) -> bool:
        if len(events) < 2:
            return False
        
        # Must end with a shot
        if events[-1].event_type != "shot":
            return False
        
        # Must have at least one movement event
        has_movement = any(e.event_type == "movement" for e in events[:-1])
        if not has_movement:
            return False
        
        # Must NOT have dribbles (that would be dribble-to-shot)
        has_dribble = any(e.event_type == "dribble" for e in events)
        if has_dribble:
            return False
        
        # Check gap between last movement and shot
        movement_events = [e for e in events[:-1] if e.event_type == "movement"]
        if movement_events:
            last_movement = movement_events[-1]
            shot = events[-1]
            gap = shot.timestamp - last_movement.timestamp
            
            if gap > self.thresholds.movement_to_shot_max_gap:
                return False
        
        return True
    
    def create_sequence(self, events: List[InputEvent]) -> Optional[SequenceEvent]:
        if not self.matches(events):
            return None
        
        player_id = events[0].player_id
        start_frame = events[0].timestamp
        end_frame = events[-1].timestamp
        
        # Calculate confidence
        confidence = calculate_sequence_confidence(events, self.thresholds)
        
        if confidence < self.thresholds.min_confidence_threshold:
            return None
        
        # Check if it's a "run" to shot based on metadata
        movement_events = [e for e in events[:-1] if e.event_type == "movement"]
        is_run = any(
            e.metadata.get("movement_type") in ["run", "sprint"]
            for e in movement_events
        )
        
        sequence_type = "run_to_shot" if is_run else "movement_to_shot"
        
        # Build reasoning
        duration = frames_to_seconds(end_frame - start_frame)
        last_movement = movement_events[-1]
        gap = events[-1].timestamp - last_movement.timestamp
        gap_sec = frames_to_seconds(gap)
        
        movement_desc = "run" if is_run else "movement"
        reasoning = (
            f"Detected {movement_desc}-to-shot sequence: {len(movement_events)} movement event(s) "
            f"followed by shot. Duration: {duration:.2f}s. "
            f"Gap between last movement and shot: {gap_sec:.2f}s. "
            f"Event chain: {format_event_chain(events)}."
        )
        
        return SequenceEvent(
            player_id=player_id,
            start_frame=start_frame,
            end_frame=end_frame,
            sequence_type=sequence_type,
            involved_events=events,
            confidence=confidence,
            reasoning=reasoning
        )


class StandingShotRule(SequenceRule):
    """
    Rule: Isolated shot with no significant preceding action.
    
    Pattern: shot (with minimal/no preceding events)
    Conditions:
      - Shot event with no or very few preceding events
      - Low-confidence fallback for isolated shots
    """
    
    def matches(self, events: List[InputEvent]) -> bool:
        if not events:
            return False
        
        # Must end with a shot
        if events[-1].event_type != "shot":
            return False
        
        # Should be mostly just the shot (at most 1-2 weak events before)
        if len(events) > 3:
            return False
        
        return True
    
    def create_sequence(self, events: List[InputEvent]) -> Optional[SequenceEvent]:
        if not self.matches(events):
            return None
        
        player_id = events[0].player_id
        start_frame = events[0].timestamp
        end_frame = events[-1].timestamp
        
        # Calculate confidence (typically lower for isolated shots)
        confidence = calculate_sequence_confidence(events, self.thresholds)
        confidence *= 0.8  # Penalty for isolated shot
        
        if confidence < self.thresholds.min_confidence_threshold:
            return None
        
        # Build reasoning
        duration = frames_to_seconds(end_frame - start_frame)
        reasoning = (
            f"Detected standing/isolated shot: minimal preceding action. "
            f"Duration: {duration:.2f}s. "
            f"Event chain: {format_event_chain(events)}. "
            f"Note: Lower confidence due to lack of clear setup."
        )
        
        return SequenceEvent(
            player_id=player_id,
            start_frame=start_frame,
            end_frame=end_frame,
            sequence_type="standing_shot",
            involved_events=events,
            confidence=confidence,
            reasoning=reasoning
        )


class RuleEngine:
    """
    Orchestrates multiple rules with priority ordering.
    
    Rules are evaluated in order of specificity (most specific first).
    """
    
    def __init__(self, thresholds: SequenceThresholds):
        self.thresholds = thresholds
        
        # Rules in priority order (most specific first)
        self.rules = [
            DribbleToShotRule(thresholds),
            MovementToShotRule(thresholds),
            StandingShotRule(thresholds),
        ]
    
    def evaluate(self, events: List[InputEvent]) -> Optional[SequenceEvent]:
        """
        Evaluate events against all rules.
        
        Args:
            events: Ordered list of InputEvents
            
        Returns:
            First matching SequenceEvent, or None if no rules match
        """
        for rule in self.rules:
            sequence = rule.create_sequence(events)
            if sequence is not None:
                return sequence
        
        return None