"""
parser.py
Main orchestrator for the Basketball Sequence Parser.

This module transforms low-level detected events (movement, dribble, shot)
into higher-level basketball action sequences using temporal reasoning.
"""
from typing import List, Optional
from events import InputEvent, SequenceEvent
from thresholds import SequenceThresholds, DEFAULT_THRESHOLDS
from temporal_graph import TemporalGraph


class SequenceParser:
    """
    Rule-based, explainable sequence parser for basketball analytics.
    
    Main entry point for transforming low-level events into high-level
    action sequences. Maintains per-player temporal state and applies
    configurable rules to identify patterns like "dribble_to_shot".
    
    Example usage:
        parser = SequenceParser()
        
        # Process events in chronological order
        for event in events:
            sequence = parser.process_event(event)
            if sequence:
                print(f"Detected: {sequence.sequence_type}")
                print(f"Confidence: {sequence.confidence:.2f}")
                print(f"Reasoning: {sequence.reasoning}")
        
        # Or process in batch
        sequences = parser.process_batch(events)
    """
    
    def __init__(self, thresholds: Optional[SequenceThresholds] = None):
        """
        Initialize the sequence parser.
        
        Args:
            thresholds: Configuration parameters. Uses DEFAULT_THRESHOLDS if None.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.thresholds.validate()
        
        self.temporal_graph = TemporalGraph(self.thresholds)
        
        # Statistics
        self.stats = {
            "events_processed": 0,
            "sequences_detected": 0,
            "sequences_by_type": {},
        }
    
    def process_event(self, event: InputEvent) -> Optional[SequenceEvent]:
        """
        Process a single event and attempt sequence formation.
        
        Events should be provided in chronological order (by timestamp).
        Sequences are emitted when terminal events (shots) occur.
        
        Args:
            event: InputEvent to process
            
        Returns:
            SequenceEvent if formed, None otherwise
        """
        self.stats["events_processed"] += 1
        
        # Add event to temporal graph and check for sequence formation
        sequence = self.temporal_graph.add_event(event)
        
        if sequence is not None:
            self._record_sequence(sequence)
        
        return sequence
    
    def process_batch(
        self,
        events: List[InputEvent],
        sort_by_timestamp: bool = True
    ) -> List[SequenceEvent]:
        """
        Process multiple events in batch.
        
        Args:
            events: List of InputEvents to process
            sort_by_timestamp: If True, sort events by timestamp before processing
            
        Returns:
            List of detected SequenceEvents
        """
        sequences = []
        
        # Sort events if requested
        if sort_by_timestamp:
            events = sorted(events, key=lambda e: e.timestamp)
        
        # Process each event
        for event in events:
            sequence = self.process_event(event)
            if sequence is not None:
                sequences.append(sequence)
        
        return sequences
    
    def _record_sequence(self, sequence: SequenceEvent):
        """Update statistics when a sequence is detected."""
        self.stats["sequences_detected"] += 1
        
        seq_type = sequence.sequence_type
        if seq_type not in self.stats["sequences_by_type"]:
            self.stats["sequences_by_type"][seq_type] = 0
        self.stats["sequences_by_type"][seq_type] += 1
    
    def get_statistics(self) -> dict:
        """
        Get parser statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        stats = self.stats.copy()
        
        # Add active player count
        stats["active_players"] = len(self.temporal_graph.get_active_players())
        
        # Calculate detection rate
        if stats["events_processed"] > 0:
            stats["detection_rate"] = (
                stats["sequences_detected"] / stats["events_processed"]
            )
        else:
            stats["detection_rate"] = 0.0
        
        return stats
    
    def reset(self):
        """Reset all state and statistics."""
        self.temporal_graph.reset_all()
        self.stats = {
            "events_processed": 0,
            "sequences_detected": 0,
            "sequences_by_type": {},
        }
    
    def reset_player(self, player_id: str):
        """Reset state for a specific player."""
        self.temporal_graph.reset_player(player_id)
    
    def __repr__(self):
        return (
            f"SequenceParser("
            f"events_processed={self.stats['events_processed']}, "
            f"sequences_detected={self.stats['sequences_detected']})"
        )


# Convenience function for quick processing
def parse_sequences(
    events: List[InputEvent],
    thresholds: Optional[SequenceThresholds] = None
) -> List[SequenceEvent]:
    """
    Convenience function to parse sequences from a list of events.
    
    Args:
        events: List of InputEvents to process
        thresholds: Optional configuration parameters
        
    Returns:
        List of detected SequenceEvents
    """
    parser = SequenceParser(thresholds)
    return parser.process_batch(events)


if __name__ == "__main__":
    # Example usage
    print("Basketball Sequence Parser v1.0")
    print("=" * 50)
    print()
    print("Example: Processing mock basketball events")
    print()
    
    # Create mock events
    mock_events = [
        InputEvent(0, "player1", "movement", {"movement_type": "run", "confidence": 0.9}),
        InputEvent(10, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(25, "player1", "dribble", {"confidence": 0.88}),
        InputEvent(40, "player1", "dribble", {"confidence": 0.82}),
        InputEvent(55, "player1", "shot", {"confidence": 0.95}),
        
        InputEvent(100, "player2", "movement", {"movement_type": "walk", "confidence": 0.7}),
        InputEvent(115, "player2", "shot", {"confidence": 0.85}),
    ]
    
    # Parse sequences
    parser = SequenceParser()
    sequences = parser.process_batch(mock_events)
    
    # Display results
    print(f"Processed {len(mock_events)} events")
    print(f"Detected {len(sequences)} sequences")
    print()
    
    for i, seq in enumerate(sequences, 1):
        print(f"Sequence {i}:")
        print(f"  Type: {seq.sequence_type}")
        print(f"  Player: {seq.player_id}")
        print(f"  Frames: {seq.start_frame} → {seq.end_frame} ({seq.duration_frames} frames)")
        print(f"  Confidence: {seq.confidence:.3f}")
        print(f"  Reasoning: {seq.reasoning}")
        print()
    
    # Show statistics
    print("Parser Statistics:")
    stats = parser.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")