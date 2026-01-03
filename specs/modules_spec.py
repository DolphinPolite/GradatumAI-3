"""
Basketball Analytics Module Runtime Specifications
Compact format for runtime integration and validation

Burası sadece modüllerin mantığını kavramak için, başka bir işlevi yok.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class RuntimeSpec:
    """Lightweight runtime specification for module integration"""
    name: str
    required_fields: List[str]
    forbidden_fields: List[str]
    input_schema: Dict[str, str]  # field: type
    output_schema: Dict[str, str]  # field: type
    state_type: str  # stateless | stateful_per_frame | stateful_temporal


# =============================================================================
# LAYER 1: TRACKING STATE
# =============================================================================

PLAYER_DETECTION = RuntimeSpec(
    name="PlayerDetection",
    required_fields=[
        "frame",           # np.ndarray (H,W,3) BGR
        "timestamp",       # int
        "M",               # np.ndarray (3,3) homography
        "M1",              # np.ndarray (3,3) homography
        "map_2d",          # np.ndarray (map_H, map_W, 3)
        "players"          # List[Player] pre-initialized
    ],
    forbidden_fields=[
        "ball_position",   # BallTracking produces this
        "speed",           # VelocityAnalyzer produces this
        "movement_state",  # MovementClassifier produces this
        "events"           # Event detectors produce these
    ],
    input_schema={
        "frame": "np.ndarray (H,W,3) uint8 BGR",
        "timestamp": "int",
        "M": "np.ndarray (3,3) float64",
        "M1": "np.ndarray (3,3) float64",
        "map_2d": "np.ndarray (map_H,map_W,3) uint8",
        "players": "List[Player] with {ID, team, color, positions, previous_bb, has_ball}"
    },
    output_schema={
        "annotated_frame": "np.ndarray (H,W,3) uint8",
        "map_2d": "np.ndarray (map_H,map_W,3) uint8",
        "map_2d_text": "np.ndarray (map_H,map_W,3) uint8",
        "players[].positions[timestamp]": "(x, y) in map coords - MUTATED IN-PLACE",
        "players[].previous_bb": "(top, left, bottom, right) - MUTATED IN-PLACE"
    },
    state_type="stateful_temporal"  # Tracks players across frames (7-frame timeout)
)


BALL_TRACKING = RuntimeSpec(
    name="BallTracking",
    required_fields=[
        "frame",           # np.ndarray
        "timestamp",       # int
        "M",               # np.ndarray (3,3)
        "M1",              # np.ndarray (3,3)
        "map_2d",          # np.ndarray
        "map_2d_text",     # np.ndarray
        "players"          # List[Player] with positions[timestamp] already set
    ],
    forbidden_fields=[
        "movement_state",  # MovementClassifier produces this
        "dribble_event",   # DribbleDetector produces this
        "shot_event"       # ShotDetector produces this
    ],
    input_schema={
        "frame": "np.ndarray (H,W,3) uint8",
        "timestamp": "int",
        "M": "np.ndarray (3,3) float64",
        "M1": "np.ndarray (3,3) float64",
        "map_2d": "np.ndarray (map_H,map_W,3) uint8",
        "map_2d_text": "np.ndarray (map_H,map_W,3) uint8",
        "players": "List[Player] with positions[timestamp], previous_bb, team"
    },
    output_schema={
        "annotated_frame": "np.ndarray (H,W,3) uint8",
        "map_2d_or_none": "Optional[np.ndarray] (map_H,map_W,3) uint8",
        "players[].has_ball": "bool - MUTATED IN-PLACE (exactly one True or all False)",
        "ball_position_2d": "Optional[(x, y)] in map coords"
    },
    state_type="stateful_temporal"  # Multi-tracker, motion predictor, bounce detector
)


VELOCITY_ANALYSIS = RuntimeSpec(
    name="VelocityAnalysis",
    required_fields=[
        "player",          # Player object with positions dict
        "timestamp"        # int
    ],
    forbidden_fields=[
        "movement_state",  # MovementClassifier produces this
        "bbox_height",     # PlayerDetection produces this
        "events"           # Event detectors produce these
    ],
    input_schema={
        "player": "Player with positions: dict[int, (x,y)]",
        "timestamp": "int",
        "window": "int (optional, default: 5)"
    },
    output_schema={
        "speed": "Optional[float] m/s",
        "speed_smoothed": "Optional[float] m/s (Savitzky-Golay filtered)",
        "acceleration": "Optional[float] m/s²",
        "distance_traveled": "Optional[float] meters (for time range)",
        "speed_profile": "(List[int], List[float]) timestamps, speeds",
        "player_distance": "Optional[float] meters (between two players)",
        "max_speed": "Optional[float] m/s (for time range)",
        "avg_speed": "Optional[float] m/s (for time range)"
    },
    state_type="stateless"  # Pure function, no internal state
)


DISTANCE_ANALYSIS = RuntimeSpec(
    name="DistanceAnalysis",
    required_fields=[
        "players",         # List[Player]
        "timestamp"        # int
    ],
    forbidden_fields=[
        "movement_state",
        "events",
        "possession"       # BallControlAnalyzer produces this
    ],
    input_schema={
        "players": "List[Player] with positions[timestamp], team, ID",
        "timestamp": "int",
        "include_referees": "bool (optional, default: False)"
    },
    output_schema={
        "pairwise_distances": "List[PlayerPair] with {player1_id, player2_id, distance, same_team}",
        "proximity_info": "ProximityInfo {closest_teammate, closest_opponent, within_3m lists, avg_distances}",
        "distance_matrix": "(np.ndarray NxN, List[int] player_ids)",
        "team_spacing": "Dict {avg_spacing, min/max, std, spread_x/y, centroid}",
        "defensive_pressure": "Dict {closest_defender, distance, within_2m, pressure_score}"
    },
    state_type="stateless"  # Has internal cache but functionally stateless
)


# =============================================================================
# LAYER 2: DERIVED STATE
# =============================================================================

MOVEMENT_CLASSIFICATION = RuntimeSpec(
    name="MovementClassification",
    required_fields=[
        "player",              # Player with positions
        "velocity_analyzer",   # VelocityAnalyzer instance
        "timestamp",           # int
        "bbox_height"          # float (pixels)
    ],
    forbidden_fields=[
        "dribble_event",   # DribbleDetector produces this
        "shot_event",      # ShotDetector produces this
        "pass_event",      # PassDetector produces this
        "possession"       # BallControlAnalyzer produces this
    ],
    input_schema={
        "player": "Player with positions: dict[int, (x,y)]",
        "velocity_analyzer": "VelocityAnalyzer instance",
        "timestamp": "int",
        "bbox_height": "float pixels"
    },
    output_schema={
        "player_id": "int",
        "timestamp": "int",
        "movement_state": "str (idle|walking|running|jumping|landing)",
        "confidence": "float [0,1]",
        "raw_state": "str (before smoothing)",
        "smoothed_state": "str (after temporal filter)",
        "is_valid_transition": "bool (FSM validated)",
        "features": "Dict {speed, acceleration, bbox_height_change, stability_flags}",
        "reasoning": "str (decision chain)",
        "data_quality": "float [0,1]"
    },
    state_type="stateful_temporal"  # Temporal buffer + state machine
)


BALL_CONTROL_ANALYSIS = RuntimeSpec(
    name="BallControlAnalysis",
    required_fields=[
        "timestamp",       # int
        "ball_pos",        # Optional[(x, y)]
        "players"          # List[Player]
    ],
    forbidden_fields=[
        "dribble_event",   # DribbleDetector produces this
        "pass_event",      # PassDetector produces this
        "movement_state"   # MovementClassifier produces this
    ],
    input_schema={
        "timestamp": "int",
        "ball_pos": "Optional[(x, y)] in map coords (from BallTracking)",
        "players": "List[Player] with positions[timestamp], team, ID"
    },
    output_schema={
        "ball_carrier": "Optional[int] player_id",
        "control_stats": "Dict[player_id, {frames_with_ball, total_frames, control_ratio, control_quality}]",
        "aggregate": "Dict {total_control_frames, team_possession, loose_ball_frames}"
    },
    state_type="stateful_temporal"  # Accumulates possession statistics
)


# =============================================================================
# LAYER 3: ATOMIC EVENTS
# =============================================================================

DRIBBLE_DETECTION = RuntimeSpec(
    name="DribbleDetection",
    required_fields=[
        "frame.timestamp",
        "frame.player_id",
        "frame.movement_state",      # From MovementClassifier
        "frame.has_ball",            # From BallTracking
        "frame.ball_position",       # From BallTracking
        "frame.player_position"      # From PlayerDetection
    ],
    forbidden_fields=[
        "shot_event",      # ShotDetector produces this
        "pass_event",      # PassDetector produces this
        "turnover_event"   # Game semantics
    ],
    input_schema={
        "frame": "FramePacket {timestamp, player_id, movement_state, movement_confidence, "
                 "ball_position, has_ball, player_position, speed, bbox_height}"
    },
    output_schema={
        "event": "Optional[DribbleEvent] {player_id, start_frame, end_frame, bounce_count, "
                 "avg_interval_frames, confidence, periodicity_score, vertical_dominance, "
                 "ownership_stability, reasoning}"
    },
    state_type="stateful_temporal"  # Temporal buffer per player, bounce detection state
)


SHOT_DETECTION = RuntimeSpec(
    name="ShotDetection",
    required_fields=[
        "frame.timestamp",
        "frame.player_id",
        "frame.movement_state",      # From MovementClassifier
        "frame.movement_confidence",
        "frame.bbox_height",         # From PlayerDetection
        "frame.ball_position",       # From BallTracking
        "frame.has_ball"             # From BallTracking
    ],
    forbidden_fields=[
        "dribble_event",   # DribbleDetector produces this
        "pass_event",      # PassDetector produces this
        "shot_result"      # Downstream analysis
    ],
    input_schema={
        "frame": "FramePacket {timestamp, player_id, movement_state, movement_confidence, "
                 "bbox_height, bbox_height_change, ball_position, has_ball, speed, acceleration}"
    },
    output_schema={
        "event": "Optional[ShotEvent] {event_type='shot_attempt', player_id, start_frame, "
                 "release_frame, confidence, reasoning, features: {jump_detected, ball_release_detected, "
                 "upward_motion_detected, all_hard_conditions_met}}"
    },
    state_type="stateful_temporal"  # Temporal buffer per player, hard condition gating
)


# =============================================================================
# LAYER 4: GAME SEMANTICS
# =============================================================================

SEQUENCE_PARSER = RuntimeSpec(
    name="SequenceParser",
    required_fields=[
        "event.timestamp",
        "event.player_id",
        "event.event_type",    # 'movement' | 'dribble' | 'shot'
        "event.attributes"
    ],
    forbidden_fields=[
        "pass_event",      # PassDetector produces this (multi-player)
        "defensive_event", # Separate analysis
        "tactical_state"   # Higher level
    ],
    input_schema={
        "event": "InputEvent {timestamp, player_id, event_type, "
                 "attributes: {movement_type, confidence, bounce_count, release_frame}}"
    },
    output_schema={
        "sequence": "Optional[SequenceEvent] {sequence_type, player_id, start_frame, end_frame, "
                    "duration_frames, events: List[InputEvent], confidence, completeness, "
                    "temporal_coherence, reasoning}"
    },
    state_type="stateful_temporal"  # Per-player temporal graph for pattern matching
)


# =============================================================================
# MODULE REGISTRY
# =============================================================================

ALL_MODULES = {
    # Layer 1: Tracking State
    "PlayerDetection": PLAYER_DETECTION,
    "BallTracking": BALL_TRACKING,
    "VelocityAnalysis": VELOCITY_ANALYSIS,
    "DistanceAnalysis": DISTANCE_ANALYSIS,
    
    # Layer 2: Derived State
    "MovementClassification": MOVEMENT_CLASSIFICATION,
    "BallControlAnalysis": BALL_CONTROL_ANALYSIS,
    
    # Layer 3: Atomic Events
    "DribbleDetection": DRIBBLE_DETECTION,
    "ShotDetection": SHOT_DETECTION,
    
    # Layer 4: Game Semantics
    "SequenceParser": SEQUENCE_PARSER
}


# =============================================================================
# EXECUTION ORDER & DEPENDENCIES
# =============================================================================

EXECUTION_ORDER = [
    # Layer 1 (can run in parallel after PlayerDetection)
    "PlayerDetection",      # MUST BE FIRST (produces positions)
    "BallTracking",         # Needs positions from PlayerDetection
    "VelocityAnalysis",     # Needs positions (can run anytime after PlayerDetection)
    "DistanceAnalysis",     # Needs positions (can run anytime after PlayerDetection)
    
    # Layer 2 (needs Layer 1 complete)
    "MovementClassification",  # Needs VelocityAnalysis + bbox from PlayerDetection
    "BallControlAnalysis",     # Needs BallTracking + PlayerDetection
    
    # Layer 3 (needs Layer 2 complete)
    "DribbleDetection",     # Needs MovementClassification + BallTracking
    "ShotDetection",        # Needs MovementClassification + BallTracking
    
    # Layer 4 (needs Layer 3 complete)
    "SequenceParser"        # Needs all atomic events
]


DEPENDENCY_GRAPH = {
    "PlayerDetection": [],
    "BallTracking": ["PlayerDetection"],
    "VelocityAnalysis": ["PlayerDetection"],
    "DistanceAnalysis": ["PlayerDetection"],
    "MovementClassification": ["PlayerDetection", "VelocityAnalysis"],
    "BallControlAnalysis": ["PlayerDetection", "BallTracking"],
    "DribbleDetection": ["MovementClassification", "BallTracking", "PlayerDetection"],
    "ShotDetection": ["MovementClassification", "BallTracking", "PlayerDetection"],
    "SequenceParser": ["MovementClassification", "DribbleDetection", "ShotDetection"]
}


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_input(module_name: str, input_data: Dict[str, Any]) -> tuple[bool, str]:
    """Validate input data against module spec"""
    spec = ALL_MODULES.get(module_name)
    if not spec:
        return False, f"Unknown module: {module_name}"
    
    # Check required fields
    for field in spec.required_fields:
        if field not in input_data:
            return False, f"Missing required field: {field}"
    
    # Check forbidden fields
    for field in spec.forbidden_fields:
        if field in input_data:
            return False, f"Forbidden field present: {field}"
    
    return True, "OK"


def get_module_info(module_name: str) -> str:
    """Get compact module info"""
    spec = ALL_MODULES.get(module_name)
    if not spec:
        return f"Unknown module: {module_name}"
    
    return f"""
Module: {spec.name}
State: {spec.state_type}
Required: {', '.join(spec.required_fields[:3])}{'...' if len(spec.required_fields) > 3 else ''}
Forbidden: {', '.join(spec.forbidden_fields[:3])}{'...' if len(spec.forbidden_fields) > 3 else ''}
Dependencies: {', '.join(DEPENDENCY_GRAPH.get(module_name, []))}
"""


# =============================================================================
# QUICK REFERENCE
# =============================================================================

QUICK_REFERENCE = """
╔══════════════════════════════════════════════════════════════════════════╗
║                   BASKETBALL ANALYTICS - RUNTIME SPECS                   ║
╚══════════════════════════════════════════════════════════════════════════╝

EXECUTION ORDER (must follow):
  1. PlayerDetection      → player.positions[t]
  2. BallTracking         → ball_position, has_ball
  3. VelocityAnalysis     → speed, acceleration
  4. DistanceAnalysis     → proximity, spacing
  5. MovementClassifier   → movement_state
  6. BallControlAnalyzer  → ball_carrier
  7. DribbleDetector      → DribbleEvent
  8. ShotDetector         → ShotEvent
  9. SequenceParser       → SequenceEvent

STATE TYPES:
  • stateless            - No internal state (VelocityAnalysis, DistanceAnalysis)
  • stateful_temporal    - Maintains temporal buffers (all others)

CRITICAL RULES:
  ✓ PlayerDetection MUST run first
  ✓ player.positions is APPEND-ONLY
  ✓ player.ID is IMMUTABLE
  ✓ Each module owns exactly one output type
  ✓ No circular dependencies
  ✓ Forbidden fields enforce data flow

COMMON PATTERNS:
  • Tracking State produces raw data
  • Derived State analyzes tracking data
  • Atomic Events detect single-player actions
  • Game Semantics builds sequences & tactics
"""

if __name__ == "__main__":
    print(QUICK_REFERENCE)
    print("\nModule Details:\n")
    for module_name in EXECUTION_ORDER:
        print(get_module_info(module_name))