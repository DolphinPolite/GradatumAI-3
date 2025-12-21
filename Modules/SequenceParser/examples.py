"""
examples.py
Comprehensive examples demonstrating the Basketball Sequence Parser.
"""

from parser import SequenceParser, parse_sequences
from events import InputEvent
from thresholds import DEFAULT_THRESHOLDS, STRICT_THRESHOLDS, SequenceThresholds


def example_1_basic_usage():
    """Example 1: Basic dribble-to-shot sequence."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Dribble-to-Shot Sequence")
    print("=" * 70)
    
    events = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(15, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(30, "player1", "dribble", {"confidence": 0.88}),
        InputEvent(45, "player1", "shot", {"confidence": 0.95}),
    ]
    
    parser = SequenceParser()
    sequences = parser.process_batch(events)
    
    print(f"\nProcessed {len(events)} events")
    print(f"Detected {len(sequences)} sequence(s)\n")
    
    for seq in sequences:
        print(f"Sequence Type: {seq.sequence_type}")
        print(f"Player: {seq.player_id}")
        print(f"Frames: {seq.start_frame} → {seq.end_frame} ({seq.duration_frames} frames)")
        print(f"Confidence: {seq.confidence:.3f}")
        print(f"Reasoning: {seq.reasoning}\n")


def example_2_movement_to_shot():
    """Example 2: Catch-and-shoot (movement to shot)."""
    print("=" * 70)
    print("EXAMPLE 2: Catch-and-Shoot (Movement-to-Shot)")
    print("=" * 70)
    
    events = [
        InputEvent(100, "player2", "movement", {
            "confidence": 0.8,
            "movement_type": "run"
        }),
        InputEvent(115, "player2", "shot", {"confidence": 0.9}),
    ]
    
    sequences = parse_sequences(events)
    
    print(f"\nProcessed {len(events)} events")
    print(f"Detected {len(sequences)} sequence(s)\n")
    
    for seq in sequences:
        print(f"Sequence Type: {seq.sequence_type}")
        print(f"Confidence: {seq.confidence:.3f}")
        print(f"Reasoning: {seq.reasoning}\n")


def example_3_multiple_players():
    """Example 3: Multiple players with different sequences."""
    print("=" * 70)
    print("EXAMPLE 3: Multiple Players")
    print("=" * 70)
    
    events = [
        # Player 1: Dribble-to-shot
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(20, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(40, "player1", "shot", {"confidence": 0.95}),
        
        # Player 2: Movement-to-shot
        InputEvent(50, "player2", "movement", {"confidence": 0.8}),
        InputEvent(65, "player2", "shot", {"confidence": 0.88}),
        
        # Player 3: Standing shot
        InputEvent(100, "player3", "shot", {"confidence": 0.75}),
        
        # Player 1: Another sequence
        InputEvent(150, "player1", "dribble", {"confidence": 0.82}),
        InputEvent(165, "player1", "dribble", {"confidence": 0.87}),
        InputEvent(180, "player1", "shot", {"confidence": 0.92}),
    ]
    
    parser = SequenceParser()
    sequences = parser.process_batch(events)
    
    print(f"\nProcessed {len(events)} events across multiple players")
    print(f"Detected {len(sequences)} sequence(s)\n")
    
    for i, seq in enumerate(sequences, 1):
        print(f"Sequence {i}:")
        print(f"  Player: {seq.player_id}")
        print(f"  Type: {seq.sequence_type}")
        print(f"  Confidence: {seq.confidence:.3f}")
        print(f"  Event chain: {' → '.join(e.event_type for e in seq.involved_events)}")
        print()
    
    # Show statistics
    stats = parser.get_statistics()
    print("Statistics:")
    print(f"  Events processed: {stats['events_processed']}")
    print(f"  Sequences detected: {stats['sequences_detected']}")
    print(f"  Active players: {stats['active_players']}")
    print(f"  Detection rate: {stats['detection_rate']:.1%}")
    print(f"  By type: {stats['sequences_by_type']}")
    print()


def example_4_gap_handling():
    """Example 4: Handling gaps between events."""
    print("=" * 70)
    print("EXAMPLE 4: Gap Handling")
    print("=" * 70)
    
    print("\n--- Case A: Small gaps (valid sequence) ---")
    events_small_gap = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(20, "player1", "dribble", {"confidence": 0.85}),  # 20 frame gap
        InputEvent(45, "player1", "shot", {"confidence": 0.95}),      # 25 frame gap
    ]
    
    sequences = parse_sequences(events_small_gap)
    print(f"Small gaps: {len(sequences)} sequence(s) detected")
    if sequences:
        print(f"  Confidence: {sequences[0].confidence:.3f}")
    
    print("\n--- Case B: Large gap (invalidates sequence) ---")
    events_large_gap = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(100, "player1", "dribble", {"confidence": 0.85}),  # 100 frame gap - TOO LARGE
        InputEvent(120, "player1", "shot", {"confidence": 0.95}),
    ]
    
    sequences = parse_sequences(events_large_gap)
    print(f"Large gaps: {len(sequences)} sequence(s) detected")
    if sequences:
        print(f"  Note: Only recent events form a sequence")
    print()


def example_5_confidence_filtering():
    """Example 5: Filtering by confidence thresholds."""
    print("=" * 70)
    print("EXAMPLE 5: Confidence Filtering")
    print("=" * 70)
    
    # Low-confidence events
    events = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.4}),
        InputEvent(15, "player1", "dribble", {"confidence": 0.5}),
        InputEvent(30, "player1", "shot", {"confidence": 0.6}),
    ]
    
    print("\n--- Default thresholds (min_confidence=0.5) ---")
    parser_default = SequenceParser(DEFAULT_THRESHOLDS)
    sequences_default = parser_default.process_batch(events)
    print(f"Detected: {len(sequences_default)} sequence(s)")
    if sequences_default:
        print(f"  Confidence: {sequences_default[0].confidence:.3f}")
    
    print("\n--- Strict thresholds (min_confidence=0.7) ---")
    parser_strict = SequenceParser(STRICT_THRESHOLDS)
    sequences_strict = parser_strict.process_batch(events)
    print(f"Detected: {len(sequences_strict)} sequence(s)")
    print(f"  (Rejected due to low confidence)")
    print()


def example_6_custom_configuration():
    """Example 6: Custom threshold configuration."""
    print("=" * 70)
    print("EXAMPLE 6: Custom Configuration")
    print("=" * 70)
    
    # Custom configuration requiring 4+ dribbles
    custom_thresholds = SequenceThresholds(
        min_dribbles_for_sequence=4,  # Require 4+ dribbles
        dribble_to_shot_max_gap=30,   # Tighter timing
        min_confidence_threshold=0.6,  # Moderate confidence
    )
    
    events = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(12, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(24, "player1", "dribble", {"confidence": 0.88}),
        InputEvent(36, "player1", "shot", {"confidence": 0.95}),
    ]
    
    print("\n--- Standard config (2+ dribbles) ---")
    parser_standard = SequenceParser()
    sequences_standard = parser_standard.process_batch(events)
    print(f"Detected: {len(sequences_standard)} sequence(s)")
    
    print("\n--- Custom config (4+ dribbles) ---")
    parser_custom = SequenceParser(custom_thresholds)
    sequences_custom = parser_custom.process_batch(events)
    print(f"Detected: {len(sequences_custom)} sequence(s)")
    print(f"  (Only 3 dribbles - doesn't meet threshold)")
    print()


def example_7_streaming_mode():
    """Example 7: Real-time streaming event processing."""
    print("=" * 70)
    print("EXAMPLE 7: Streaming Mode (Real-time Processing)")
    print("=" * 70)
    
    parser = SequenceParser()
    
    # Simulate streaming events
    print("\nProcessing events in real-time...\n")
    
    stream = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(15, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(30, "player1", "dribble", {"confidence": 0.88}),
        InputEvent(45, "player1", "shot", {"confidence": 0.95}),
        InputEvent(100, "player2", "movement", {"confidence": 0.8}),
        InputEvent(115, "player2", "shot", {"confidence": 0.9}),
    ]
    
    for event in stream:
        print(f"Frame {event.timestamp:3d}: {event.event_type:10s} (player={event.player_id})")
        
        # Process event immediately
        sequence = parser.process_event(event)
        
        if sequence:
            print(f"  ⚡ SEQUENCE DETECTED!")
            print(f"     Type: {sequence.sequence_type}")
            print(f"     Confidence: {sequence.confidence:.3f}")
            print(f"     {sequence.reasoning}")
    
    print()


def example_8_serialization():
    """Example 8: Serializing sequences to dictionaries."""
    print("=" * 70)
    print("EXAMPLE 8: Serialization")
    print("=" * 70)
    
    events = [
        InputEvent(0, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(15, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(30, "player1", "shot", {"confidence": 0.95}),
    ]
    
    sequences = parse_sequences(events)
    
    print("\nSequence as dictionary (JSON-serializable):\n")
    
    for seq in sequences:
        seq_dict = seq.to_dict()
        
        import json
        print(json.dumps(seq_dict, indent=2))
    
    print()


def example_9_robustness():
    """Example 9: Robustness to noisy/missing events."""
    print("=" * 70)
    print("EXAMPLE 9: Robustness to Noise")
    print("=" * 70)
    
    # Noisy sequence with extra movement events
    events = [
        InputEvent(0, "player1", "movement", {"confidence": 0.5}),
        InputEvent(5, "player1", "dribble", {"confidence": 0.9}),
        InputEvent(10, "player1", "movement", {"confidence": 0.4}),  # Noise
        InputEvent(20, "player1", "dribble", {"confidence": 0.85}),
        InputEvent(25, "player1", "movement", {"confidence": 0.3}),  # Noise
        InputEvent(35, "player1", "dribble", {"confidence": 0.88}),
        InputEvent(50, "player1", "shot", {"confidence": 0.95}),
    ]
    
    sequences = parse_sequences(events)
    
    print(f"\nProcessed {len(events)} events (including noise)")
    print(f"Detected {len(sequences)} clean sequence(s)\n")
    
    for seq in sequences:
        print(f"Type: {seq.sequence_type}")
        print(f"Filtered events: {len(seq.involved_events)}/{len(events)}")
        print(f"Event chain: {' → '.join(e.event_type for e in seq.involved_events)}")
        print(f"Note: Parser automatically filtered noisy movement events")
    
    print()


def run_all_examples():
    """Run all examples."""
    examples = [
        example_1_basic_usage,
        example_2_movement_to_shot,
        example_3_multiple_players,
        example_4_gap_handling,
        example_5_confidence_filtering,
        example_6_custom_configuration,
        example_7_streaming_mode,
        example_8_serialization,
        example_9_robustness,
    ]
    
    for i, example in enumerate(examples, 1):
        example()
        if i < len(examples):
            print("\n" * 2)


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "BASKETBALL SEQUENCE PARSER - EXAMPLES" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
    
    run_all_examples()
    
    print("\n")
    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)