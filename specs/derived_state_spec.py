"""
Basketball Analytics Module Specifications
CHUNK 2: DERIVED STATE MODULES

Bu modüller temel tracking state'den üst seviye durum bilgisi türetir.
Movement classification, ball control gibi anlık durumları analiz eder.

Hierarchy:
    Tracking State → Movement Classification → Ball Control
    
Design Principle:
    - DERIVED: Tracking state'e bağımlı, kendisi state üretmez
    - STATEFUL: Temporal reasoning için buffer tutar
    - INTERPRETABLE: Her çıktı reasoning ile açıklanır
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
# 1. MOVEMENT CLASSIFICATION (BasicMovementClassifier)
# =============================================================================

MOVEMENT_CLASSIFICATION_SPEC = ModuleSpec(
    name="MovementClassification",
    category="derived_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Player object (with velocity data)
        "player": {
            "type": "Player",
            "required_attributes": {
                "positions": "dict[int, tuple] - position history",
                "ID": "int - player identifier"
            },
            "description": "Player with tracking history"
        },
        
        # Velocity analyzer instance
        "velocity_analyzer": {
            "type": "VelocityAnalyzer",
            "description": "For speed/acceleration computation",
            "note": "MUST be initialized with correct court dimensions"
        },
        
        # Current frame data
        "timestamp": {
            "type": "int",
            "description": "Current frame number"
        },
        
        "bbox_height": {
            "type": "float",
            "unit": "pixels",
            "description": "Player bbox height (for jump detection)",
            "source": "PlayerDetection.previous_bb"
        },
        
        # Configuration (passed at init)
        "config": {
            "thresholds": {
                # Speed thresholds
                "walk_speed_min": "float - m/s (default: 0.5)",
                "run_speed_min": "float - m/s (default: 3.0)",
                
                # Jump detection
                "jump_speed_min": "float - m/s (default: 1.0)",
                "jump_bbox_shrink_min": "float - ratio (default: -0.05)",
                
                # Temporal
                "temporal_window_size": "int - frames (default: 15)",
                "min_state_duration_frames": "int (default: 3)",
                
                # Confidence
                "confidence_threshold_min": "float [0,1] (default: 0.5)"
            },
            "enable_logging": "bool - log all decisions",
            "preset": "str - 'default', 'strict', 'permissive'"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Classification result
        "result": {
            "type": "Dict[str, Any]",
            "schema": {
                # Core classification
                "player_id": "int",
                "timestamp": "int",
                "movement_state": "str - 'idle'/'walking'/'running'/'jumping'/'landing'",
                "confidence": "float [0, 1] - classification confidence",
                
                # Pipeline stages
                "raw_state": "str - before temporal smoothing",
                "smoothed_state": "str - after temporal filter",
                "is_valid_transition": "bool - FSM validation passed",
                
                # Debug info
                "features": {
                    "speed": "Optional[float] - m/s",
                    "speed_smoothed": "Optional[float] - m/s",
                    "acceleration": "Optional[float] - m/s²",
                    "bbox_height_change": "Optional[float] - ratio",
                    "bbox_height_stable": "bool",
                    "is_speed_stable": "bool",
                    "data_quality_score": "float [0, 1]"
                },
                
                # Explainability
                "reasoning": "str - human-readable decision chain",
                "data_quality": "float [0, 1] - input data quality"
            }
        },
        
        # Internal state (for statistics)
        "statistics": {
            "total_frames": "int",
            "valid_transitions": "int",
            "invalid_transitions": "int",
            "state_counts": "dict[str, int]",
            "low_confidence_frames": "int",
            "valid_transition_rate": "float",
            "low_confidence_rate": "float"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "player",              # Must have position history
        "velocity_analyzer",   # Must have speed computation
        "timestamp",           # Current frame
        "bbox_height"          # For jump detection
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "dribble_event",   # Dribbling is separate atomic event
        "shot_event",      # Shot detection is separate
        "pass_event",      # Pass detection is game semantics
        "possession"       # Ball control is separate
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",     # player.positions
        "VelocityAnalyzer",    # speed/acceleration
        "NumPy",               # Array operations
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Movement Classification Module (BasicMovementClassifier)
    
    PURPOSE:
        Classifies player movement state from position and bbox data.
        Uses rule-based pipeline with temporal reasoning.
    
    PIPELINE:
        1. Feature Extraction:
           - Speed (from VelocityAnalyzer)
           - Acceleration (from VelocityAnalyzer)
           - Bbox height change (for jump detection)
           - Stability metrics
        
        2. Raw Classification:
           - Jump detection (priority): bbox shrinking + speed threshold
           - Speed-based: idle < 0.5 m/s, walking < 3.0 m/s, running >= 3.0 m/s
        
        3. Temporal Smoothing:
           - Sliding window consensus
           - Hysteresis (prevents flickering)
           - Min duration enforcement
        
        4. State Machine Validation:
           - Physical transition rules (e.g., can't jump from idle)
           - State duration constraints
           - Transition history tracking
        
        5. Confidence Calculation:
           - Feature quality score
           - Stability bonus
           - Transition consistency
    
    STATE MACHINE:
        idle ↔ walking ↔ running → jumping → landing → [idle/walking/running]
        
        Allowed Transitions:
        - idle → walking, running
        - walking → idle, running, jumping
        - running → walking, jumping
        - jumping → landing
        - landing → idle, walking, running
        
        Forbidden:
        - idle → jumping (must walk/run first)
        - jumping → idle (must land first)
    
    ROBUSTNESS:
        - Temporal buffer (reduces noise)
        - FSM constraints (physical validity)
        - Confidence scoring (flags uncertain states)
        - Data quality checks (rejects bad input)
    
    DATA FLOW:
        player.positions + bbox_height → MovementClassifier → movement_state
                                                            ↓
                                                    DribbleDetector
                                                    ShotDetector
    
    INTEGRATION POINTS:
        → DribbleDetector: uses movement_state, movement_confidence
        → ShotDetector: uses movement_state (for jump detection)
        → SequenceParser: uses movement_state for sequence formation
    
    EXPLAINABILITY:
        Every classification includes:
        - Feature values (speed, accel, bbox_change)
        - Pipeline stages (raw → smoothed → validated)
        - FSM transition reason
        - Confidence breakdown
    """
)


# =============================================================================
# 2. BALL CONTROL ANALYSIS (BallControlAnalyzer)
# =============================================================================

BALL_CONTROL_SPEC = ModuleSpec(
    name="BallControlAnalysis",
    category="derived_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Current frame
        "timestamp": {
            "type": "int",
            "description": "Current frame number"
        },
        
        # Ball position (from BallTracking)
        "ball_pos": {
            "type": "Optional[Tuple[float, float]]",
            "description": "(x, y) in 2D map coords, or None if not detected",
            "source": "BallTracking.ball_position_2d"
        },
        
        # Player list (from PlayerDetection)
        "players": {
            "type": "List[Player]",
            "required_attributes": [
                "positions[timestamp]",
                "team",
                "ID"
            ],
            "description": "All tracked players"
        },
        
        # Configuration (passed at init)
        "config": {
            "BALL_DISTANCE_TH": "float - max distance for control (pixels)",
            "MIN_CONTROL_FRAMES": "int - min frames to count as control",
            "MAX_MISSING_FRAMES": "int - frames before resetting carrier",
            "CONTROL_QUALITY_TH_HIGH": "float - ratio for 'high' quality",
            "CONTROL_QUALITY_TH_MID": "float - ratio for 'mid' quality",
            "CONTROL_QUALITY_TH_LOW": "float - ratio for 'low' quality"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Current ball carrier
        "ball_carrier": {
            "type": "Optional[int]",
            "description": "Player ID with ball, or None"
        },
        
        # Per-player control stats
        "control_stats": {
            "type": "Dict[int, Dict]",
            "schema": {
                "player_id": {
                    "frames_with_ball": "int - total frames with possession",
                    "total_frames": "int - frames player was on court",
                    "last_control_ts": "int - last frame with ball",
                    "player_ref": "Player - reference to player object",
                    "control_ratio": "float - frames_with_ball / total_frames",
                    "control_quality": "str - 'high'/'mid'/'low'/'none'"
                }
            }
        },
        
        # Aggregate stats
        "aggregate": {
            "total_control_frames": "int",
            "team_possession": "Dict[str, int] - frames per team",
            "loose_ball_frames": "int - frames with no clear possession"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "timestamp",
        "ball_pos",  # Can be None
        "players"
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "dribble_event",   # Dribbling is atomic event
        "pass_event",      # Pass detection is game semantics
        "movement_state"   # Movement is separate
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",  # player.positions
        "BallTracking",     # ball_pos
        "NumPy"             # Distance calculation
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Ball Control Analysis Module (BallControlAnalyzer)
    
    PURPOSE:
        Tracks which player controls the ball over time.
        Provides possession statistics per player and team.
    
    ALGORITHM:
        1. Distance-Based Assignment:
           - Find closest player to ball
           - If distance <= threshold → player has control
           - Else → loose ball
        
        2. Temporal Smoothing:
           - Track frames_without_ball counter
           - Reset carrier after MAX_MISSING_FRAMES
           - Prevents flickering on brief occlusions
        
        3. Statistics Accumulation:
           - Per player: frames_with_ball, total_frames
           - Control quality: high/mid/low based on ratio
           - Team possession: aggregate by team
    
    CONTROL QUALITY LEVELS:
        - High: >= 70% of frames with ball
        - Mid: >= 40% of frames with ball
        - Low: >= 10% of frames with ball
        - None: < 10% of frames with ball
    
    USE CASES:
        - Possession time analysis
        - Player efficiency (time with ball vs shots)
        - Team ball movement (control transfers)
        - Ball security (loose ball frequency)
    
    DATA FLOW:
        ball_pos + player.positions → BallControlAnalyzer → possession stats
                                                          ↓
                                                    Game Semantics
    
    INTEGRATION POINTS:
        → DribbleDetector: uses ball_carrier for dribble validation
        → PassDetector: uses control transfer for pass detection
        → PossessionAnalyzer: uses team_possession for tactics
    
    STATE MANAGEMENT:
        - Maintains temporal state (carrier, stats)
        - Frame-by-frame update (stateful)
        - Reset on game breaks (call reset())
    """
)


# =============================================================================
# SUMMARY: DERIVED STATE LAYER
# =============================================================================

DERIVED_STATE_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════════╗
║                     DERIVED STATE LAYER SUMMARY                          ║
╚══════════════════════════════════════════════════════════════════════════╝

MODULES:
    1. MovementClassification → movement_state (idle/walk/run/jump/land)
    2. BallControlAnalysis    → ball_carrier, possession stats

DATA FLOW:
    Tracking State → MovementClassifier → movement_state → Atomic Events
                  → BallControlAnalyzer → possession → Game Semantics

KEY CHARACTERISTICS:
    - DERIVED: Don't produce new sensor data, analyze existing data
    - STATEFUL: Maintain temporal buffers for smoothing
    - INTERPRETABLE: Every output has reasoning string
    - FRAME-BY-FRAME: Update incrementally (online processing)

DESIGN PATTERNS:
    1. Pipeline Architecture:
       Raw → Smoothed → Validated → Final (with confidence)
    
    2. Temporal Reasoning:
       - Sliding windows
       - Hysteresis
       - State machines
    
    3. Explainability:
       - Feature values logged
       - Decision chain tracked
       - Confidence breakdown

INTEGRATION RULES:
    1. MovementClassifier REQUIRES:
       - player.positions (from PlayerDetection)
       - VelocityAnalyzer instance
       - bbox_height (from PlayerDetection)
    
    2. BallControlAnalyzer REQUIRES:
       - ball_pos (from BallTracking)
       - player.positions (from PlayerDetection)
    
    3. Output Usage:
       - movement_state → DribbleDetector, ShotDetector
       - ball_carrier → PassDetector, PossessionAnalyzer

CRITICAL NOTES:
    - Movement state is PER-FRAME (no persistence after frame)
    - Ball control is CUMULATIVE (stats persist across frames)
    - Both modules are STATEFUL (reset between games)
"""

print(DERIVED_STATE_SUMMARY)