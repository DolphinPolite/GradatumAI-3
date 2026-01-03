"""
Basketball Analytics Module Specifications
CHUNK 4: GAME SEMANTICS MODULES

Bu modüller yüksek seviye oyun semantiğini analiz eder:
- Sequence Parsing (atomic events → meaningful sequences)
- Multi-player interactions (passes, defensive actions)
- Tactical analysis (possession, spacing, pressure)

Game Semantics = Oyun bağlamında anlamlı eylemler (>1 oyuncu olabilir)

Hierarchy:
    Atomic Events → Sequence Parser → Tactical Analysis
    
Design Principle:
    - CONTEXTUAL: Oyun durumunu dikkate alır
    - MULTI-PLAYER: Birden fazla oyuncu arasındaki etkileşimler
    - TACTICAL: Takım stratejisi seviyesinde analiz
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class ModuleSpec:
    name: str
    category: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_fields: List[str]
    forbidden_fields: List[str]
    dependencies: List[str]
    data_flow_direction: str
    state_type: str
    description: str


# =============================================================================
# 1. SEQUENCE PARSER (SequenceParser)
# =============================================================================

SEQUENCE_PARSER_SPEC = ModuleSpec(
    name="SequenceParser",
    category="game_semantics",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Input event (atomic event)
        "event": {
            "type": "InputEvent",
            "schema": {
                "timestamp": "int - frame number",
                "player_id": "str - player identifier",
                "event_type": "str - 'movement'/'dribble'/'shot'",
                "attributes": {
                    # For movement events
                    "movement_type": "Optional[str] - 'idle'/'walk'/'run'/'jump'",
                    "confidence": "float [0, 1]",
                    
                    # For dribble events
                    "bounce_count": "Optional[int]",
                    "avg_interval_frames": "Optional[float]",
                    
                    # For shot events
                    "release_frame": "Optional[int]",
                    "shot_confidence": "Optional[float]"
                }
            },
            "description": "Low-level event from atomic detectors"
        },
        
        # Configuration (passed at init)
        "config": {
            "thresholds": {
                # Temporal rules
                "max_time_gap_frames": "int - max gap between events (default: 30)",
                "min_sequence_duration_frames": "int (default: 10)",
                
                # Sequence formation rules
                "movement_types_for_dribble": "List[str] - ['walk', 'run'] (default)",
                "allow_idle_before_shot": "bool (default: False)",
                
                # Confidence requirements
                "min_movement_confidence": "float [0, 1] (default: 0.5)",
                "min_dribble_confidence": "float [0, 1] (default: 0.5)",
                "min_shot_confidence": "float [0, 1] (default: 0.6)",
                
                # Sequence types
                "sequence_patterns": {
                    "dribble_to_shot": {
                        "required_events": "['movement', 'dribble', 'shot']",
                        "max_gap_between": "int - frames (default: 20)",
                        "min_confidence": "float (default: 0.6)"
                    },
                    "catch_and_shoot": {
                        "required_events": "['movement', 'shot']",
                        "no_dribble_allowed": "bool (default: True)",
                        "max_gap_between": "int - frames (default: 10)",
                        "min_confidence": "float (default: 0.7)"
                    }
                }
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Sequence event (if formed)
        "sequence": {
            "type": "Optional[SequenceEvent]",
            "schema": {
                # Sequence metadata
                "sequence_type": "str - 'dribble_to_shot', 'catch_and_shoot', etc.",
                "player_id": "str",
                "start_frame": "int - first event timestamp",
                "end_frame": "int - last event timestamp",
                "duration_frames": "int",
                
                # Component events
                "events": "List[InputEvent] - atomic events in sequence",
                "event_types": "List[str] - types of component events",
                
                # Quality metrics
                "confidence": "float [0, 1] - sequence confidence",
                "completeness": "float [0, 1] - all required events present",
                "temporal_coherence": "float [0, 1] - timing makes sense",
                
                # Explainability
                "reasoning": "str - why this sequence was formed",
                "context": "Dict[str, Any] - additional context"
            },
            "description": "None if no sequence formed, else SequenceEvent"
        },
        
        # Statistics (for monitoring)
        "statistics": {
            "events_processed": "int",
            "sequences_detected": "int",
            "sequences_by_type": "Dict[str, int]",
            "active_players": "int - players with ongoing sequences",
            "detection_rate": "float"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "event.timestamp",
        "event.player_id",
        "event.event_type",
        "event.attributes"
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "pass_event",      # Pass detection is separate (multi-player)
        "defensive_event", # Defense is separate analysis
        "tactical_state"   # Tactics are higher level
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "MovementClassifier",  # movement events
        "DribbleDetector",     # dribble events
        "ShotDetector",        # shot events
        "NetworkX"             # Graph-based temporal reasoning (optional)
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Sequence Parser Module (SequenceParser)
    
    PURPOSE:
        Transforms low-level atomic events into higher-level sequences.
        Identifies meaningful basketball actions from event chains.
    
    ALGORITHM:
        1. Temporal Graph Construction:
           - Maintain per-player event graph
           - Nodes = events, Edges = temporal connections
           - Edge weight = time gap + compatibility score
        
        2. Sequence Pattern Matching:
           - Define sequence patterns (templates)
           - Example: dribble_to_shot = [movement, dribble+, shot]
           - Match patterns against event chains
        
        3. Validation:
           - Temporal coherence (gaps within limits)
           - Confidence requirements (all events meet threshold)
           - Completeness (all required events present)
        
        4. Confidence Calculation:
           - Component confidence (average of event confidences)
           - Temporal bonus (tight timing = higher confidence)
           - Completeness bonus (all optional events present)
        
        5. Event Emission:
           - Emit SequenceEvent when terminal event occurs (shot)
           - Include all component events
           - Reasoning explains why sequence was formed
    
    SEQUENCE PATTERNS:
        1. dribble_to_shot:
           - Pattern: movement → dribble(1+) → shot
           - Description: Player moves with ball, dribbles, shoots
           - Common in: isolation plays, drives to basket
        
        2. catch_and_shoot:
           - Pattern: movement → shot (NO dribble)
           - Description: Player catches pass and immediately shoots
           - Common in: spot-up shooting, fast breaks
        
        3. pull_up_jumper:
           - Pattern: run → dribble(1-3) → stop → shot
           - Description: Player slows down and shoots
           - Common in: perimeter shooting
        
        4. layup_drive:
           - Pattern: run → dribble(3+) → jump → shot
           - Description: Player drives to basket
           - Common in: layups, dunks
    
    TEMPORAL REASONING:
        - Events must occur within max_time_gap (default: 30 frames)
        - Sequence starts at first relevant event
        - Sequence ends at terminal event (shot)
        - Events between start/end must be compatible
    
    ROBUSTNESS:
        - Per-player state (sequences don't cross players)
        - Timeout mechanism (stale sequences discarded)
        - Flexible patterns (optional events allowed)
        - Confidence scoring (flags uncertain sequences)
    
    DATA FLOW:
        InputEvents → TemporalGraph → PatternMatcher → SequenceValidator
                                                     → SequenceEvent
    
    INTEGRATION POINTS:
        → PlayAnalyzer: uses SequenceEvent for play classification
        → HighlightGenerator: uses SequenceEvent for video compilation
        → TacticalAnalyzer: uses SequenceEvent for strategy insights
    
    EXPLAINABILITY:
        Every SequenceEvent includes:
        - Component events with timestamps
        - Pattern matched (e.g., "dribble_to_shot")
        - Confidence breakdown
        - Reasoning string (e.g., "Player 7 ran with ball (conf=0.85), 
          dribbled 3 times (conf=0.78), shot from jump (conf=0.82)")
    """
)


# =============================================================================
# 2. PASS DETECTION (PassDetector) - NOT IMPLEMENTED YET
# =============================================================================

PASS_DETECTION_SPEC = ModuleSpec(
    name="PassDetection",
    category="game_semantics",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Ball state
        "ball_position": {
            "type": "Optional[Tuple[float, float]]",
            "description": "(x, y) in map coords over time"
        },
        
        # Player states
        "players": {
            "type": "List[Player]",
            "required_attributes": [
                "positions[timestamp]",
                "has_ball",
                "team"
            ]
        },
        
        # Timestamp
        "timestamp": {
            "type": "int",
            "description": "Current frame"
        },
        
        # Ball control history (from BallControlAnalyzer)
        "ball_carrier_history": {
            "type": "Dict[int, int]",
            "description": "{timestamp: player_id}"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        "pass_event": {
            "type": "Optional[PassEvent]",
            "schema": {
                "passer_id": "int",
                "receiver_id": "int",
                "start_frame": "int - ball leaves passer",
                "end_frame": "int - ball reaches receiver",
                "pass_type": "str - 'ground', 'bounce', 'lob', 'chest'",
                "distance": "float - meters",
                "velocity": "float - m/s",
                "success": "bool - completed pass",
                "confidence": "float [0, 1]",
                "reasoning": "str"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "ball_position",
        "players",
        "timestamp"
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "shot_event",  # Different event type
        "turnover"     # Separate detection
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "BallTracking",
        "PlayerDetection",
        "BallControlAnalyzer",
        "DistanceAnalyzer"
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Pass Detection Module (PassDetector) - FUTURE IMPLEMENTATION
    
    PURPOSE:
        Detect passes between players (multi-player interaction).
    
    ALGORITHM:
        1. Ball Carrier Transition:
           - Detect has_ball transition between players
           - Must be same team (otherwise turnover)
        
        2. Trajectory Analysis:
           - Track ball path between transition
           - Classify pass type (ground, bounce, lob)
        
        3. Validation:
           - Ball moved significant distance
           - Receiver was intended target (closest teammate)
           - No intermediate touches
        
        4. Success Determination:
           - Receiver gained possession
           - No turnover within X frames
    
    NOTE: Not currently implemented - requires multi-player tracking
    """
)


# =============================================================================
# 3. TACTICAL ANALYSIS - NOT FULLY IMPLEMENTED
# =============================================================================

TACTICAL_ANALYSIS_SPEC = ModuleSpec(
    name="TacticalAnalysis",
    category="game_semantics",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Player states
        "players": {
            "type": "List[Player]",
            "required_attributes": [
                "positions[timestamp]",
                "team",
                "has_ball"
            ]
        },
        
        # Proximity data (from DistanceAnalyzer)
        "proximity_info": {
            "type": "Dict[int, ProximityInfo]",
            "description": "Per-player proximity metrics"
        },
        
        # Team spacing (from DistanceAnalyzer)
        "team_spacing": {
            "type": "Dict[str, Dict]",
            "description": "Per-team spacing metrics"
        },
        
        # Sequence events (from SequenceParser)
        "recent_sequences": {
            "type": "List[SequenceEvent]",
            "description": "Recent action sequences"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        "tactical_state": {
            "type": "TacticalState",
            "schema": {
                # Possession
                "possession_team": "str - team with ball",
                "possession_duration_frames": "int",
                
                # Formation
                "offensive_formation": "str - '1-4', '2-3', etc.",
                "defensive_formation": "str - 'man', 'zone', 'press'",
                
                # Spacing
                "offensive_spacing_quality": "float [0, 1]",
                "defensive_compactness": "float [0, 1]",
                
                # Pressure
                "ball_pressure": "float [0, 1] - how tightly guarded",
                "help_defense_available": "bool",
                
                # Tempo
                "pace": "float - possessions per minute",
                "transition_state": "str - 'halfcourt', 'fastbreak', 'transition'"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "players",
        "proximity_info"
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",
        "BallControlAnalyzer",
        "DistanceAnalyzer",
        "SequenceParser"
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Tactical Analysis Module - FUTURE IMPLEMENTATION
    
    PURPOSE:
        High-level tactical state analysis.
        Formation recognition, defensive schemes, tempo.
    
    FEATURES:
        1. Formation Recognition:
           - Classify offensive/defensive formations
           - Detect set plays
        
        2. Spacing Analysis:
           - Measure floor spacing quality
           - Identify clustering/spreading
        
        3. Pressure Analysis:
           - Measure defensive pressure on ball
           - Identify double teams
        
        4. Tempo Classification:
           - Fast break vs half court
           - Transition detection
    
    NOTE: Partially implemented via DistanceAnalyzer
    """
)


# =============================================================================
# SUMMARY: GAME SEMANTICS LAYER
# =============================================================================

GAME_SEMANTICS_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════════╗
║                    GAME SEMANTICS LAYER SUMMARY                          ║
╚══════════════════════════════════════════════════════════════════════════╝

MODULES:
    1. SequenceParser      → SequenceEvent (atomic → meaningful actions)
    2. PassDetection       → PassEvent (NOT IMPLEMENTED)
    3. TacticalAnalysis    → TacticalState (PARTIAL via DistanceAnalyzer)

DATA FLOW:
    Atomic Events → SequenceParser → SequenceEvent ──→ Analytics
    Ball Control  → PassDetector   → PassEvent     ──→
    Distance      → TacticalAnalyzer → TacticalState →

KEY CHARACTERISTICS:
    - CONTEXTUAL: Consider game state and situation
    - MULTI-PLAYER: Can involve interactions (passes)
    - TEMPORAL: Long-duration reasoning (sequences)
    - TACTICAL: Team-level strategy analysis

IMPLEMENTATION STATUS:
    ✅ COMPLETE:
        - SequenceParser (dribble_to_shot, catch_and_shoot)
        - DistanceAnalyzer (spacing, pressure, proximity)
    
    🚧 PARTIAL:
        - BallControlAnalyzer (possession tracking)
        - TacticalAnalysis (formation via spacing)
    
    ❌ NOT IMPLEMENTED:
        - PassDetection (multi-player tracking)
        - DefensiveActions (block, steal, charge)
        - SetPlayRecognition (pattern matching)
        - FastBreakDetection (tempo classification)

INTEGRATION RULES:
    1. SequenceParser REQUIRES:
       - InputEvents (from Movement, Dribble, Shot detectors)
       - Temporal ordering (events in chronological order)
    
    2. PassDetector WOULD REQUIRE:
       - ball_carrier_history (from BallControlAnalyzer)
       - player.positions (from PlayerDetection)
       - Distance metrics (from DistanceAnalyzer)
    
    3. TacticalAnalyzer REQUIRES:
       - Proximity info (from DistanceAnalyzer)
       - Team spacing (from DistanceAnalyzer)
       - Sequence history (from SequenceParser)

DESIGN PHILOSOPHY:
    1. Bottom-Up Construction:
       - Start with atomic events (single player, single action)
       - Build sequences (chains of atomic events)
       - Extract tactics (patterns in sequences)
    
    2. Rule-Based Core:
       - Game rules are well-defined
       - Physics constraints apply
       - Explainability is critical
    
    3. Optional ML Enhancement:
       - ML can refine confidence scores
       - ML can classify edge cases
       - But rules remain in control

FUTURE ROADMAP:
    Phase 1 (Current):
    - Basic tracking (position, ball, velocity)
    - Movement classification
    - Atomic events (dribble, shot)
    - Basic sequences
    
    Phase 2 (Next):
    - Pass detection
    - Defensive actions
    - Turnover detection
    - Assist attribution
    
    Phase 3 (Future):
    - Set play recognition
    - Formation classification
    - Tactical recommendations
    - Real-time coaching insights

CRITICAL NOTES:
    - Game semantics build on ALL previous layers
    - Multi-player events require robust tracking (challenging)
    - Tactical analysis requires domain expertise (basketball knowledge)
    - Explainability becomes more important at higher levels
"""

print(GAME_SEMANTICS_SUMMARY)


# =============================================================================
# COMPLETE SYSTEM SUMMARY
# =============================================================================

COMPLETE_SYSTEM_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════════╗
║           BASKETBALL ANALYTICS SYSTEM - COMPLETE ARCHITECTURE            ║
╚══════════════════════════════════════════════════════════════════════════╝

LAYER 1: TRACKING STATE
├─ PlayerDetection      → player.positions[t]
├─ BallTracking         → ball_position, has_ball
├─ VelocityAnalysis     → speed, acceleration
└─ DistanceAnalysis     → proximity, spacing

LAYER 2: DERIVED STATE
├─ MovementClassifier   → movement_state (idle/walk/run/jump)
└─ BallControlAnalyzer  → ball_carrier, possession_stats

LAYER 3: ATOMIC EVENTS
├─ DribbleDetector      → DribbleEvent (bounce sequences)
└─ ShotDetector         → ShotEvent (shot attempts)

LAYER 4: GAME SEMANTICS
├─ SequenceParser       → SequenceEvent (dribble_to_shot, etc.)
├─ PassDetector         → PassEvent (NOT IMPLEMENTED)
└─ TacticalAnalyzer     → TacticalState (PARTIAL)

DATA FLOW (COMPLETE PIPELINE):
    Video Frame
        ↓
    PlayerDetection → player.positions[t]
        ↓
    BallTracking → ball_position, has_ball
        ↓
    VelocityAnalysis → speed, acceleration
        ↓
    DistanceAnalysis → proximity, spacing
        ↓
    MovementClassifier → movement_state
        ↓
    BallControlAnalyzer → ball_carrier
        ↓
    DribbleDetector → DribbleEvent
        ↓
    ShotDetector → ShotEvent
        ↓
    SequenceParser → SequenceEvent
        ↓
    TacticalAnalyzer → TacticalState
        ↓
    [Analytics, Visualization, ML Training]

INTEGRATION CONTRACT:
    1. MUST run layers in order (1 → 2 → 3 → 4)
    2. Lower layers NEVER depend on higher layers
    3. Player.positions is APPEND-ONLY
    4. Player.ID is IMMUTABLE
    5. All events include confidence + reasoning
    6. Timestamps are sequential (no gaps)

CRITICAL DESIGN PRINCIPLES:
    ✓ Single Source of Truth (each module owns one data type)
    ✓ Unidirectional Flow (no circular dependencies)
    ✓ Explainable AI (every decision has reasoning)
    ✓ Rule-Based Core (AI only refines, never decides)
    ✓ Stateful Tracking (temporal reasoning)
    ✓ Confidence Scoring (flag uncertain outputs)
    ✓ Modular Design (plug-and-play components)

MODULE COUNT:
    - Tracking State: 4 modules (COMPLETE)
    - Derived State: 2 modules (COMPLETE)
    - Atomic Events: 2 modules (COMPLETE)
    - Game Semantics: 3 modules (1 COMPLETE, 2 PARTIAL/FUTURE)
    
    Total: 11 modules (8 complete, 1 partial, 2 future)

PERFORMANCE CHARACTERISTICS:
    - Real-time capable: Yes (30 FPS on GPU)
    - Stateful: Yes (maintains temporal buffers)
    - Parallelizable: Partial (per-player parallel, per-frame serial)
    - Memory: O(N*W) where N=players, W=window_size
    - Latency: ~15-30 frames (0.5-1.0 seconds at 30 FPS)
"""

print(COMPLETE_SYSTEM_SUMMARY)