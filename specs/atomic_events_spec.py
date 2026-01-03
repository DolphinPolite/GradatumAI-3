"""
Basketball Analytics Module Specifications
CHUNK 3: ATOMIC EVENTS MODULES

Bu modüller temel atletik olayları (atomic events) tespit eder:
- Dribbling (ball bouncing while moving)
- Shot Attempts (ball release from jumping player)

Atomic Events = Tek bir oyuncunun tek bir aksiyonu (pass değil, 2 oyuncu var)

Hierarchy:
    Derived State → Dribble Detection → Shot Detection → Sequence Parser
    
Design Principle:
    - ATOMIC: Tek oyuncu, tek aksiyon
    - TEMPORAL: Sequence-based detection
    - EXPLAINABLE: Her event bir reasoning string ile gelir
    - CONFIDENCE-SCORED: 0-1 arası güven skoru
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
# 1. DRIBBLE DETECTION (DribblingDetector)
# =============================================================================

DRIBBLE_DETECTION_SPEC = ModuleSpec(
    name="DribbleDetection",
    category="atomic_events",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Frame packet (complete frame state)
        "frame": {
            "type": "FramePacket",
            "schema": {
                # Core identifiers
                "timestamp": "int - frame number",
                "player_id": "int - player identifier",
                
                # Movement state (from MovementClassifier)
                "movement_state": "str - idle/walking/running/jumping/landing",
                "movement_confidence": "float [0, 1]",
                
                # Ball state (from BallTracking)
                "ball_position": "Optional[Tuple[float, float]] - (x, y) in map coords",
                "has_ball": "bool - from player.has_ball",
                
                # Player state (from PlayerDetection + VelocityAnalyzer)
                "player_position": "Tuple[float, float] - (x, y) in map coords",
                "speed": "Optional[float] - m/s",
                "bbox_height": "float - pixels",
                
                # Optional (for advanced features)
                "ball_height": "Optional[float] - y-coord (lower = higher in frame)",
                "acceleration": "Optional[float] - m/s²"
            },
            "description": "Complete frame state for one player"
        },
        
        # Configuration (passed at init)
        "config": {
            "preset": "str - 'default', 'strict', 'permissive', 'training'",
            "thresholds": {
                # Bounce detection
                "bounce_detection": {
                    "min_bounce_amplitude": "float - pixels",
                    "max_bounce_interval": "int - frames",
                    "min_bounce_interval": "int - frames"
                },
                
                # Dribble sequence
                "min_bounces": "int (default: 2)",
                "min_sequence_duration": "int - frames (default: 10)",
                "max_sequence_duration": "int - frames (default: 90)",
                
                # Motion constraints
                "min_speed": "float - m/s (default: 0.3)",
                "max_speed": "float - m/s (default: 8.0)",
                "max_vertical_motion": "float - ratio (default: 0.3)",
                
                # Possession
                "ownership_stability_threshold": "float [0, 1] (default: 0.6)",
                "max_ball_distance": "float - pixels (default: 100.0)",
                
                # Confidence
                "min_confidence": "float [0, 1] (default: 0.5)"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Dribble event (if detected)
        "event": {
            "type": "Optional[DribbleEvent]",
            "schema": {
                # Event metadata
                "player_id": "int",
                "start_frame": "int - sequence start",
                "end_frame": "int - sequence end",
                "duration_frames": "int - end - start",
                
                # Dribble characteristics
                "bounce_count": "int - number of bounces detected",
                "avg_interval_frames": "float - average bounce spacing",
                "bounce_frames": "List[int] - exact bounce timestamps",
                
                # Quality metrics
                "confidence": "float [0, 1] - detection confidence",
                "periodicity_score": "float [0, 1] - rhythm consistency",
                "vertical_dominance": "float [0, 1] - up/down motion strength",
                "ownership_stability": "float [0, 1] - possession consistency",
                "amplitude_consistency": "float [0, 1] - bounce height similarity",
                "proximity_score": "float [0, 1] - ball-player closeness",
                
                # Explainability
                "reasoning": "str - human-readable explanation",
                "features": "Dict[str, Any] - all extracted features"
            },
            "description": "None if no dribble detected, else DribbleEvent"
        },
        
        # Statistics (for monitoring)
        "statistics": {
            "frames_processed": "int",
            "events_emitted": "int",
            "detection_rate": "float",
            "active_sequences": "List[int] - player IDs with ongoing sequences"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "frame.timestamp",
        "frame.player_id",
        "frame.movement_state",       # From MovementClassifier
        "frame.has_ball",             # From BallTracking
        "frame.ball_position",        # From BallTracking
        "frame.player_position"       # From PlayerDetection
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "shot_event",      # Shot detection is separate
        "pass_event",      # Pass is game semantics (2 players)
        "turnover_event"   # Turnover is game semantics
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "MovementClassifier",  # movement_state
        "BallTracking",        # ball_position, has_ball
        "PlayerDetection",     # player_position
        "VelocityAnalyzer",    # speed (optional)
        "NumPy",               # Signal processing
        "SciPy"                # Peak detection (optional)
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Dribble Detection Module (DribblingDetector)
    
    PURPOSE:
        Detects basketball dribbling sequences from frame data.
        Uses temporal reasoning and physics-based validation.
    
    ALGORITHM:
        1. Temporal Buffering:
           - Maintain per-player frame buffer
           - Window size: configurable (default: 60 frames)
        
        2. Bounce Detection:
           - Track ball y-position (vertical motion)
           - Detect local minima (ball hitting ground)
           - Validate amplitude (realistic bounce height)
           - Check intervals (realistic bounce timing)
        
        3. Sequence Validation:
           - Min bounces: 2+ (single bounce not dribble)
           - Ownership stability: player keeps ball
           - Motion constraints: player moving (not stationary)
           - Proximity: ball stays close to player
        
        4. Feature Extraction:
           - Periodicity: rhythm consistency (FFT-based)
           - Vertical dominance: up/down motion vs lateral
           - Amplitude consistency: similar bounce heights
           - Proximity score: ball-player distance
        
        5. Confidence Calculation:
           - Weighted sum of normalized features
           - Threshold: min_confidence (default: 0.5)
        
        6. Event Emission:
           - Emitted when confidence > threshold
           - Includes all features for interpretability
           - Sequence buffer reset after emission
    
    DRIBBLE CHARACTERISTICS:
        - Periodic: Bounces at regular intervals
        - Vertical: Ball moves up/down more than left/right
        - Continuous: Player maintains possession
        - Mobile: Player is moving (not stationary)
    
    ROBUSTNESS:
        - Temporal buffer (handles noise)
        - Physics constraints (rejects impossible motions)
        - Confidence scoring (flags uncertain detections)
        - Preset system (strict/default/permissive)
    
    DATA FLOW:
        FramePacket → TemporalBuffer → BounceDetector → FeatureExtractor
                                                      → ConfidenceCalculator
                                                      → DribbleEvent
    
    INTEGRATION POINTS:
        → SequenceParser: uses DribbleEvent for sequence formation
        → DribbleAnalyzer: uses DribbleEvent for statistics
        → HighlightGenerator: uses DribbleEvent for video clips
    
    EXPLAINABILITY:
        Every DribbleEvent includes:
        - Bounce count and timing
        - Feature scores (periodicity, vertical dominance, etc.)
        - Reasoning string (e.g., "Detected 3 bounces over 45 frames 
          with consistent rhythm; showing strong vertical motion")
    
    PRESETS:
        - default: Balanced (min_bounces=2, min_confidence=0.5)
        - strict: Conservative (min_bounces=3, min_confidence=0.7)
        - permissive: Liberal (min_bounces=2, min_confidence=0.3)
        - training: Maximum recall (min_bounces=2, min_confidence=0.2)
    """
)


# =============================================================================
# 2. SHOT DETECTION (ShotAttemptDetector)
# =============================================================================

SHOT_DETECTION_SPEC = ModuleSpec(
    name="ShotDetection",
    category="atomic_events",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Frame packet (complete frame state)
        "frame": {
            "type": "FramePacket",
            "schema": {
                # Core identifiers
                "timestamp": "int - frame number",
                "player_id": "int - player identifier",
                
                # Movement state (from MovementClassifier)
                "movement_state": "str - idle/walking/running/jumping/landing",
                "movement_confidence": "float [0, 1]",
                
                # Ball state (from BallTracking)
                "ball_position": "Optional[Tuple[float, float]] - (x, y) in map coords",
                "has_ball": "bool - from player.has_ball",
                
                # Bbox analysis (for jump detection)
                "bbox_height": "float - pixels",
                "bbox_height_change": "Optional[float] - frame-to-frame delta",
                
                # Motion (from VelocityAnalyzer)
                "speed": "Optional[float] - m/s",
                "acceleration": "Optional[float] - m/s²"
            },
            "description": "Complete frame state for one player"
        },
        
        # Configuration (passed at init)
        "config": {
            "thresholds": {
                # Hard conditions (GATEKEEPER)
                "hard_conditions": {
                    "require_jump": "bool (default: True)",
                    "require_ball_release": "bool (default: True)",
                    "require_upward_motion": "bool (default: False)"
                },
                
                # Jump detection
                "jump_detection": {
                    "bbox_shrink_threshold": "float - ratio (default: -0.05)",
                    "min_jump_confidence": "float [0, 1] (default: 0.7)"
                },
                
                # Ball release detection
                "ball_release": {
                    "min_separation_rate": "float - pixels/frame (default: 5.0)",
                    "release_clarity_threshold": "float [0, 1] (default: 0.6)"
                },
                
                # Upward motion
                "upward_motion": {
                    "min_upward_velocity": "float - pixels/frame (default: 3.0)",
                    "strength_threshold": "float [0, 1] (default: 0.5)"
                },
                
                # Temporal
                "temporal_window_size": "int - frames (default: 15)",
                "temporal_window_min": "int - frames (default: 5)",
                
                # Confidence
                "confidence_min_threshold": "float [0, 1] (default: 0.6)",
                
                # Weights (for confidence calculation)
                "weight_jump_confidence": "float (default: 0.3)",
                "weight_ball_release": "float (default: 0.3)",
                "weight_upward_velocity": "float (default: 0.2)",
                "weight_temporal_consistency": "float (default: 0.1)",
                "bonus_separation_trend": "float (default: 0.05)",
                "bonus_release_height": "float (default: 0.03)",
                "bonus_apex_alignment": "float (default: 0.02)"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Shot event (if detected)
        "event": {
            "type": "Optional[ShotEvent]",
            "schema": {
                # Event metadata
                "event_type": "str - 'shot_attempt'",
                "player_id": "int",
                "start_frame": "int - sequence start",
                "release_frame": "int - ball release point",
                "end_frame": "int - sequence end",
                
                # Detection details
                "confidence": "float [0, 1] - detection confidence",
                "reasoning": "str - human-readable explanation",
                
                # Features (for interpretability)
                "features": {
                    # Hard conditions
                    "jump_detected": "bool",
                    "jump_confidence": "float [0, 1]",
                    "ball_release_detected": "bool",
                    "ball_release_clarity": "float [0, 1]",
                    "upward_motion_detected": "bool",
                    "upward_motion_strength": "float [0, 1]",
                    
                    # Soft scores
                    "separation_trend_score": "float [0, 1]",
                    "release_height_score": "float [0, 1]",
                    "apex_alignment_score": "float [0, 1]",
                    "temporal_consistency_score": "float [0, 1]",
                    
                    # Debug info
                    "window_start": "int",
                    "window_end": "int",
                    "all_hard_conditions_met": "bool"
                }
            },
            "description": "None if no shot detected, else ShotEvent"
        },
        
        # Statistics (for monitoring)
        "statistics": {
            "frames_processed": "int",
            "shots_detected": "int",
            "detection_rate": "float",
            "recent_detections": "List[Dict] - last 10 detections"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "frame.timestamp",
        "frame.player_id",
        "frame.movement_state",       # From MovementClassifier
        "frame.movement_confidence",
        "frame.bbox_height",          # From PlayerDetection
        "frame.ball_position",        # From BallTracking
        "frame.has_ball"              # From BallTracking
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "dribble_event",   # Dribble detection is separate
        "pass_event",      # Pass is game semantics
        "shot_result"      # Shot result (make/miss) is downstream
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "MovementClassifier",  # movement_state
        "BallTracking",        # ball_position, has_ball
        "PlayerDetection",     # bbox_height
        "VelocityAnalyzer",    # speed, acceleration (optional)
        "NumPy"                # Array operations
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateful_temporal",
    
    description="""
    Shot Detection Module (ShotAttemptDetector)
    
    PURPOSE:
        Detects basketball shot attempts from frame data.
        Uses rule-based core with optional AI refinement.
    
    ALGORITHM:
        1. Temporal Buffering:
           - Maintain per-player frame buffer
           - Window size: configurable (default: 15 frames)
        
        2. Hard Condition Gatekeeper:
           Three hard conditions (configurable):
           a) Jump Detection: player bbox shrinking + movement_state='jumping'
           b) Ball Release: has_ball → NOT has_ball transition
           c) Upward Motion: ball moving up after release
           
           ALL must be True to proceed (or disabled in config)
        
        3. Feature Extraction:
           - Jump confidence (from movement classifier)
           - Ball release clarity (transition sharpness)
           - Upward motion strength (velocity magnitude)
           - Temporal consistency (feature stability)
           - Separation trend (increasing ball-player distance)
           - Release height (optimal release point)
           - Apex alignment (release near jump peak)
        
        4. Confidence Calculation:
           - Weighted sum of normalized features
           - Bonus for soft features (separation, height, apex)
           - Threshold: min_confidence (default: 0.6)
        
        5. Optional AI Refinement:
           - Rule-based score is primary (80% weight)
           - AI can refine confidence (20% weight)
           - AI CANNOT trigger events (only refine)
        
        6. Event Emission:
           - Emitted when confidence > threshold
           - Includes all features for interpretability
           - Cooldown period (prevents duplicate detections)
    
    SHOT CHARACTERISTICS:
        - Jump: Player leaves ground (bbox shrinks)
        - Release: Ball separates from player
        - Upward: Ball moves toward basket
        - Temporal: Sequence occurs in ~0.5s window
    
    GATEKEEPER DESIGN:
        Hard conditions are REQUIREMENTS:
        - If ANY hard condition fails → NO SHOT
        - Confidence only matters AFTER hard conditions pass
        - This prevents false positives (high priority)
    
    ROBUSTNESS:
        - Hard condition gating (prevents false positives)
        - Temporal buffering (handles noise)
        - Confidence scoring (flags uncertain shots)
        - Cooldown period (prevents duplicates)
        - Optional AI refinement (improves edge cases)
    
    DATA FLOW:
        FramePacket → TemporalBuffer → Hard Condition Check
                                     ↓ (if pass)
                                FeatureExtractor → ConfidenceCalculator
                                                → (optional) AI Refiner
                                                → ShotEvent
    
    INTEGRATION POINTS:
        → SequenceParser: uses ShotEvent for sequence formation
        → ShotAnalyzer: uses ShotEvent + outcome for statistics
        → HighlightGenerator: uses ShotEvent for video clips
    
    EXPLAINABILITY:
        Every ShotEvent includes:
        - Hard condition status (jump, release, upward)
        - Feature scores (confidence, clarity, strength)
        - Reasoning string (e.g., "Jump detected (conf=0.85); 
          Ball released at frame 120 (clarity=0.78); 
          Upward motion detected (strength=0.62)")
    
    AI INTEGRATION PHILOSOPHY:
        - Rule-based system is GATEKEEPER (hard conditions)
        - AI is REFINER (adjusts confidence within [0, 1])
        - AI CANNOT trigger events (prevents black-box decisions)
        - System remains interpretable and debuggable
    """
)


# =============================================================================
# SUMMARY: ATOMIC EVENTS LAYER
# =============================================================================

ATOMIC_EVENTS_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════════╗
║                     ATOMIC EVENTS LAYER SUMMARY                          ║
╚══════════════════════════════════════════════════════════════════════════╝

MODULES:
    1. DribbleDetection → DribbleEvent (bounce sequences)
    2. ShotDetection    → ShotEvent (shot attempts)

DATA FLOW:
    Derived State → DribbleDetector → DribbleEvent ──→ SequenceParser
                  → ShotDetector    → ShotEvent    ──→
                  
KEY CHARACTERISTICS:
    - ATOMIC: Single player, single action
    - TEMPORAL: Sequence-based detection (not single-frame)
    - GATED: Hard conditions prevent false positives
    - CONFIDENT: Every event has confidence score
    - EXPLAINABLE: Every event has reasoning string

DETECTION PHILOSOPHY:
    1. Temporal Buffering:
       - Maintain frame history per player
       - Detect patterns over time (not instantaneous)
    
    2. Hard Condition Gatekeeper:
       - Must meet ALL requirements to proceed
       - Prevents false positives (high precision)
       - Configurable (can disable for high recall)
    
    3. Confidence Scoring:
       - Weighted sum of normalized features
       - Threshold-based emission
       - Optional AI refinement (20% max influence)
    
    4. Explainability:
       - Human-readable reasoning
       - Full feature breakdown
       - Decision chain logged

INTEGRATION RULES:
    1. DribbleDetector REQUIRES:
       - movement_state (from MovementClassifier)
       - ball_position + has_ball (from BallTracking)
       - player_position (from PlayerDetection)
    
    2. ShotDetector REQUIRES:
       - movement_state (from MovementClassifier)
       - ball_position + has_ball (from BallTracking)
       - bbox_height (from PlayerDetection)
    
    3. Both Output:
       - Event objects with confidence + reasoning
       - Used by SequenceParser for high-level sequences

CRITICAL DESIGN DECISIONS:
    1. Why Hard Conditions?
       - Basketball has clear physics rules
       - False positives are worse than false negatives
       - Users trust system more with high precision
    
    2. Why Temporal Buffering?
       - Single-frame detection is too noisy
       - Patterns emerge over sequences
       - Enables validation across time
    
    3. Why Explainable?
       - Users need to trust system
       - Debugging requires visibility
       - ML training needs interpretable labels
    
    4. Why Optional AI?
       - Rules handle 90% of cases well
       - AI can refine edge cases
       - But rules remain in control (gatekeeper)
"""

print(ATOMIC_EVENTS_SUMMARY)