"""
Basketball Analytics Module Specifications
CHUNK 1: TRACKING STATE MODULES

Bu modüller ham video/sensör verisinden temel tracking bilgilerini çıkarır.
Diğer tüm modüller bu katmana bağımlıdır.

Hierarchy:
    Raw Video → PlayerDetection → BallTracking → VelocityAnalysis
    
Design Principle:
    - SINGLE SOURCE OF TRUTH: Her modül tek bir veri türünden sorumlu
    - NO CIRCULAR DEPENDENCIES: Tek yönlü veri akışı
    - STATEFUL: Frame-by-frame state maintenance
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ModuleSpec:
    """Standard module specification format"""
    name: str
    category: str  # tracking_state / derived_state / atomic_events / game_semantics
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_fields: List[str]
    forbidden_fields: List[str]
    dependencies: List[str]
    data_flow_direction: str  # upstream / downstream / bidirectional
    state_type: str  # stateless / stateful_per_frame / stateful_temporal
    description: str


# =============================================================================
# 1. PLAYER DETECTION & TRACKING (FeetDetector)
# =============================================================================

PLAYER_DETECTION_SPEC = ModuleSpec(
    name="PlayerDetection",
    category="tracking_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Frame data
        "frame": {
            "type": "np.ndarray",
            "shape": "(H, W, 3)",
            "dtype": "uint8",
            "color_space": "BGR",
            "description": "Raw video frame from camera feed"
        },
        
        # Timestamp
        "timestamp": {
            "type": "int",
            "description": "Frame number (sequential, 0-indexed)",
            "constraints": "monotonically increasing"
        },
        
        # Homography matrices (for 2D projection)
        "M": {
            "type": "np.ndarray",
            "shape": "(3, 3)",
            "dtype": "float64",
            "description": "Homography: frame coords → field coords"
        },
        
        "M1": {
            "type": "np.ndarray", 
            "shape": "(3, 3)",
            "dtype": "float64",
            "description": "Homography: field coords → 2D map coords"
        },
        
        # 2D map for visualization
        "map_2d": {
            "type": "np.ndarray",
            "shape": "(map_H, map_W, 3)",
            "dtype": "uint8",
            "description": "Top-down court visualization"
        },
        
        # Pre-initialized player objects
        "players": {
            "type": "List[Player]",
            "description": "List of Player objects (pre-allocated with team info)",
            "player_schema": {
                "ID": "int - unique identifier",
                "team": "str - 'green'/'white'/'referee'",
                "color": "tuple - BGR color for visualization",
                "positions": "dict[int, tuple] - {timestamp: (x, y) in map coords}",
                "previous_bb": "tuple or None - (top, left, bottom, right) bbox",
                "has_ball": "bool - ball possession flag"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA  
    # -------------------------------------------------------------------------
    output_schema={
        # Updated frame with annotations
        "annotated_frame": {
            "type": "np.ndarray",
            "shape": "(H, W, 3)",
            "dtype": "uint8",
            "description": "Frame with player markers drawn"
        },
        
        # Updated 2D map
        "map_2d": {
            "type": "np.ndarray",
            "shape": "(map_H, map_W, 3)", 
            "dtype": "uint8",
            "description": "Map with player positions updated"
        },
        
        # Updated 2D map with IDs
        "map_2d_text": {
            "type": "np.ndarray",
            "shape": "(map_H, map_W, 3)",
            "dtype": "uint8", 
            "description": "Map with player IDs rendered"
        },
        
        # CRITICAL: players list is MUTATED IN-PLACE
        # Each player.positions[timestamp] is updated
        "players": {
            "type": "List[Player]",
            "mutation": "IN-PLACE",
            "updated_fields": [
                "positions[timestamp]",  # NEW: (x, y) in map coords
                "previous_bb",            # UPDATED: latest bbox
                "has_ball"                # RESET: False (ball tracking sets this)
            ],
            "invariants": [
                "ID, team, color are NEVER changed",
                "positions is append-only (old timestamps preserved)",
                "If player missing for 7+ frames → positions cleared, bb reset"
            ]
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "frame",           # Must have video frame
        "timestamp",       # Must have frame index
        "M", "M1",         # Must have homography for projection
        "map_2d",          # Must have visualization target
        "players"          # Must have pre-initialized player objects
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "ball_position",   # Ball tracking is SEPARATE module
        "speed",           # Speed is computed by VelocityAnalyzer
        "movement_state",  # Movement classification is downstream
        "events"           # Event detection is downstream
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "Detectron2",      # Person segmentation model
        "OpenCV",          # Image processing, homography
        "NumPy"            # Array operations
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="upstream",  # Produces data for other modules
    state_type="stateful_temporal",   # Maintains per-player tracking state
    
    description="""
    Player Detection & Tracking Module (FeetDetector)
    
    PURPOSE:
        Detects players in video frames and tracks them across time.
        Projects player positions to 2D court map for downstream analysis.
    
    ALGORITHM:
        1. Detectron2 instance segmentation (person class)
        2. Morphological erosion (noise reduction)
        3. Jersey color classification (HSV thresholding)
        4. Keypoint extraction (head, feet)
        5. Homography projection (frame → field → map)
        6. IoU-based player association (tracking)
        7. Occlusion handling (7-frame timeout)
    
    LIMITATIONS:
        - Color-based team detection (fails on similar jerseys)
        - Static HSV thresholds (brittle to lighting changes)
        - IoU tracking (loses fast-moving players)
        - No re-identification after occlusion
        - Tracks referees but doesn't use them
    
    DATA FLOW:
        Video Frame → Player Detection → Player.positions[t] → ALL DOWNSTREAM
        
    CRITICAL INVARIANTS:
        - Player.ID is IMMUTABLE (never changes)
        - positions[t] is FINAL (never overwritten)
        - Loss of tracking: positions cleared, bb=None, has_ball=False
    
    INTEGRATION POINTS:
        → BallTracking: uses player.positions, player.previous_bb for ball assignment
        → VelocityAnalyzer: uses player.positions for speed calculation
        → MovementClassifier: uses player.positions for trajectory analysis
        → DistanceAnalyzer: uses player.positions for proximity metrics
    """
)


# =============================================================================
# 2. BALL DETECTION & TRACKING (RobustBallTracker)
# =============================================================================

BALL_TRACKING_SPEC = ModuleSpec(
    name="BallTracking",
    category="tracking_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Frame data
        "frame": {
            "type": "np.ndarray",
            "shape": "(H, W, 3)",
            "dtype": "uint8",
            "description": "Current video frame"
        },
        
        # Timestamp
        "timestamp": {
            "type": "int",
            "description": "Frame number"
        },
        
        # Homography matrices
        "M": {
            "type": "np.ndarray",
            "shape": "(3, 3)",
            "description": "Frame → field homography"
        },
        
        "M1": {
            "type": "np.ndarray",
            "shape": "(3, 3)", 
            "description": "Field → 2D map homography"
        },
        
        # Maps for visualization
        "map_2d": {
            "type": "np.ndarray",
            "shape": "(map_H, map_W, 3)",
            "description": "2D court map"
        },
        
        "map_2d_text": {
            "type": "np.ndarray",
            "shape": "(map_H, map_W, 3)",
            "description": "2D court map with player IDs"
        },
        
        # Player data (from PlayerDetection)
        "players": {
            "type": "List[Player]",
            "required_attributes": [
                "positions[timestamp]",  # Current position
                "previous_bb",           # Current bbox
                "team",                  # For ball assignment
                "has_ball"               # To be updated
            ],
            "description": "MUST be called AFTER PlayerDetection"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Updated frame
        "annotated_frame": {
            "type": "np.ndarray",
            "description": "Frame with ball marker (blue rectangle)"
        },
        
        # Updated map (or None if ball not detected)
        "map_2d_or_none": {
            "type": "Optional[np.ndarray]",
            "description": "Map with ball position (red circle), or None"
        },
        
        # CRITICAL: players list is MUTATED IN-PLACE
        "players": {
            "type": "List[Player]",
            "mutation": "IN-PLACE",
            "updated_fields": [
                "has_ball"  # Set to True for closest player (IoU-based)
            ],
            "invariants": [
                "Exactly ONE player has has_ball=True (or none)",
                "Ball assignment based on IoU(ball_bbox, player_bbox)",
                "Only non-referee players can have ball"
            ]
        },
        
        # Internal state (for metrics/debugging)
        "tracking_state": {
            "bbox": "Optional[tuple] - (x, y, w, h) or None",
            "confidence": "float - detection/tracking confidence",
            "tracker_type": "str - 'KCF', 'CSRT', or 'prediction'",
            "ball_position_2d": "Optional[tuple] - (x, y) in map coords"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "frame",
        "timestamp", 
        "M", "M1",
        "map_2d",
        "map_2d_text",
        "players"      # MUST have player positions already
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "movement_state",  # Movement is separate
        "dribble_event",   # Dribbling detection is downstream
        "shot_event"       # Shot detection is downstream
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",  # MUST run after player tracking
        "OpenCV",           # Tracking algorithms (KCF, CSRT)
        "NumPy"             # Array operations
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="upstream",
    state_type="stateful_temporal",
    
    description="""
    Ball Detection & Tracking Module (RobustBallTracker)
    
    PURPOSE:
        Detects and tracks basketball in video frames.
        Assigns ball possession to closest player.
    
    ALGORITHM:
        1. Enhanced Detection:
           - Template matching (orange ball detection)
           - Adaptive thresholding (lighting robustness)
           - Color filtering (HSV range for orange)
        
        2. Multi-Tracker Management:
           - Primary: KCF tracker (fast)
           - Fallback: CSRT tracker (accurate)
           - Re-detection every N frames (drift correction)
        
        3. Motion Prediction:
           - Kalman filter for occlusion handling
           - Bounce detection (basketball physics)
           - Trajectory smoothing
        
        4. Ball Assignment:
           - IoU between ball bbox and player bbox
           - Closest player gets possession
           - Referee excluded from assignment
    
    ROBUSTNESS FEATURES:
        - Multi-tracker fallback (handles occlusion)
        - Motion prediction (handles brief loss)
        - Periodic re-detection (handles drift)
        - Validation layer (rejects invalid detections)
    
    DATA FLOW:
        Frame + Players → Ball Detection → player.has_ball → Dribble/Shot Detection
        
    INTEGRATION POINTS:
        → DribbleDetector: uses ball_position, has_ball for dribble detection
        → ShotDetector: uses ball_position, ball_release for shot detection
        → BallControlAnalyzer: uses ball_position for control statistics
    """
)


# =============================================================================
# 3. VELOCITY ANALYSIS (VelocityAnalyzer)
# =============================================================================

VELOCITY_ANALYSIS_SPEC = ModuleSpec(
    name="VelocityAnalysis",
    category="tracking_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Player object (from PlayerDetection)
        "player": {
            "type": "Player",
            "required_attributes": {
                "positions": "dict[int, tuple] - {timestamp: (x, y) in map coords}",
                "ID": "int - player identifier"
            },
            "description": "Player with position history"
        },
        
        # Timestamp
        "timestamp": {
            "type": "int",
            "description": "Current frame to analyze"
        },
        
        # Analysis window
        "window": {
            "type": "int",
            "default": 5,
            "description": "Number of frames for smoothing/averaging"
        },
        
        # Configuration (passed at init)
        "config": {
            "fps": "int - video frame rate (default: 30)",
            "field_width_meters": "float - court width in meters (default: 28.0)",
            "field_height_meters": "float - court length in meters (default: 15.0)",
            "map_width_pixels": "int - 2D map width",
            "map_height_pixels": "int - 2D map height",
            "pixel_to_meter": "float - computed from above",
            "max_speed_mps": "float - outlier filter (default: 12.0 m/s)",
            "min_frames_for_calc": "int - minimum data (default: 3)"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Instantaneous speed
        "speed": {
            "type": "Optional[float]",
            "unit": "m/s",
            "range": "[0, max_speed_mps]",
            "description": "Current speed (window-averaged)"
        },
        
        # Smoothed speed
        "speed_smoothed": {
            "type": "Optional[float]",
            "unit": "m/s",
            "method": "Savitzky-Golay filter",
            "description": "Noise-robust speed estimate"
        },
        
        # Acceleration
        "acceleration": {
            "type": "Optional[float]",
            "unit": "m/s²",
            "range": "[-5.0, 5.0]",
            "description": "Rate of speed change"
        },
        
        # Distance traveled
        "distance_traveled": {
            "type": "Optional[float]",
            "unit": "meters",
            "description": "Total distance over time range"
        },
        
        # Speed profile
        "speed_profile": {
            "type": "Tuple[List[int], List[float]]",
            "description": "(timestamps, speeds) for time range"
        },
        
        # Inter-player distance
        "player_distance": {
            "type": "Optional[float]",
            "unit": "meters",
            "description": "Distance between two players"
        },
        
        # Aggregate metrics
        "max_speed": {
            "type": "Optional[float]",
            "unit": "m/s",
            "description": "Maximum speed in time range"
        },
        
        "avg_speed": {
            "type": "Optional[float]",
            "unit": "m/s",
            "description": "Average speed in time range"
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "player",      # Must have player with positions
        "timestamp"    # Must specify time point
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "movement_state",  # Movement classification is separate
        "bbox_height",     # Bbox analysis is separate
        "events"           # Event detection is downstream
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",  # Needs player.positions
        "NumPy",            # Array operations
        "SciPy"             # Signal processing (Savitzky-Golay)
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",  # Consumes player positions
    state_type="stateless",             # Pure function (no internal state)
    
    description="""
    Velocity Analysis Module (VelocityAnalyzer)
    
    PURPOSE:
        Computes speed, acceleration, and distance metrics from player positions.
        Provides physics-based motion analysis.
    
    ALGORITHM:
        1. Pixel-to-Meter Conversion:
           - Uses court dimensions and map size
           - Separate x/y scaling (handles non-square pixels)
        
        2. Speed Calculation:
           - displacement = ||pos[t] - pos[t-1]||
           - speed = displacement / time_delta
           - Outlier filtering (max_speed threshold)
        
        3. Speed Smoothing:
           - Savitzky-Golay filter (polynomial smoothing)
           - Reduces noise from tracking jitter
           - Fallback to simple averaging if insufficient data
        
        4. Acceleration:
           - accel = (speed[t] - speed[t-1]) / time_delta
           - Physical bounds: [-5, 5] m/s²
        
        5. Distance Traveled:
           - Sum of frame-to-frame displacements
           - Accounts for curved trajectories
    
    ROBUSTNESS FEATURES:
        - Outlier filtering (rejects impossible speeds)
        - Minimum data requirements (prevents bad estimates)
        - Smoothing (handles tracking noise)
        - Physical constraints (acceleration limits)
    
    DATA FLOW:
        player.positions → VelocityAnalyzer → speed/acceleration → MovementClassifier
        
    INTEGRATION POINTS:
        → MovementClassifier: uses speed_smoothed for state classification
        → DribbleDetector: uses speed for motion validation
        → ShotDetector: uses acceleration for jump detection
        → DistanceAnalyzer: uses player_distance for proximity metrics
    
    CRITICAL NOTES:
        - STATELESS: No internal buffers (unlike other modules)
        - REENTRANT: Can be called concurrently for different players
        - NO MUTATION: Never modifies player object
    """
)


# =============================================================================
# 4. DISTANCE ANALYSIS (DistanceAnalyzer)
# =============================================================================

DISTANCE_ANALYSIS_SPEC = ModuleSpec(
    name="DistanceAnalysis",
    category="tracking_state",
    
    # -------------------------------------------------------------------------
    # INPUT SCHEMA
    # -------------------------------------------------------------------------
    input_schema={
        # Player list
        "players": {
            "type": "List[Player]",
            "required_attributes": [
                "positions[timestamp]",
                "team",
                "ID"
            ],
            "description": "All tracked players"
        },
        
        # Timestamp
        "timestamp": {
            "type": "int",
            "description": "Frame to analyze"
        },
        
        # Configuration
        "config": {
            "pixel_to_meter": "float - conversion ratio",
            "court_width_meters": "float - default: 28.0",
            "court_length_meters": "float - default: 15.0",
            "proximity_threshold": "float - 'close' distance (default: 3.0m)"
        },
        
        # Optional filters
        "include_referees": {
            "type": "bool",
            "default": False,
            "description": "Include referees in analysis"
        }
    },
    
    # -------------------------------------------------------------------------
    # OUTPUT SCHEMA
    # -------------------------------------------------------------------------
    output_schema={
        # Pairwise distances
        "pairwise_distances": {
            "type": "List[PlayerPair]",
            "schema": {
                "player1_id": "int",
                "player2_id": "int",
                "distance": "float (meters)",
                "timestamp": "int",
                "player1_team": "str",
                "player2_team": "str",
                "same_team": "bool"
            }
        },
        
        # Per-player proximity
        "proximity_info": {
            "type": "ProximityInfo",
            "schema": {
                "player_id": "int",
                "timestamp": "int",
                "closest_teammate": "Optional[int]",
                "closest_teammate_distance": "Optional[float]",
                "closest_opponent": "Optional[int]",
                "closest_opponent_distance": "Optional[float]",
                "teammates_within_3m": "List[int]",
                "opponents_within_3m": "List[int]",
                "avg_teammate_distance": "Optional[float]",
                "avg_opponent_distance": "Optional[float]"
            }
        },
        
        # Distance matrix
        "distance_matrix": {
            "type": "Tuple[np.ndarray, List[int]]",
            "description": "(NxN matrix, player_ids) where N = active players"
        },
        
        # Team spacing metrics
        "team_spacing": {
            "type": "Dict[str, float]",
            "schema": {
                "avg_spacing": "float - average teammate distance",
                "min_spacing": "float - closest pair distance",
                "max_spacing": "float - furthest pair distance",
                "std_spacing": "float - spacing variability",
                "spread_x": "float - horizontal spread",
                "spread_y": "float - vertical spread",
                "centroid": "tuple - team center (x, y)"
            }
        },
        
        # Defensive pressure
        "defensive_pressure": {
            "type": "Dict[str, Any]",
            "schema": {
                "closest_defender": "int",
                "closest_defender_distance": "float",
                "defenders_within_2m": "List[int]",
                "pressure_score": "float [0, 1]"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # REQUIRED FIELDS
    # -------------------------------------------------------------------------
    required_fields=[
        "players",
        "timestamp"
    ],
    
    # -------------------------------------------------------------------------
    # FORBIDDEN FIELDS
    # -------------------------------------------------------------------------
    forbidden_fields=[
        "movement_state",
        "events",
        "possession"
    ],
    
    # -------------------------------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------------------------------
    dependencies=[
        "PlayerDetection",  # Needs player.positions
        "NumPy",            # Array operations
        "SciPy"             # cdist for distance matrix
    ],
    
    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    data_flow_direction="downstream",
    state_type="stateless",
    
    description="""
    Distance Analysis Module (DistanceAnalyzer)
    
    PURPOSE:
        Computes spatial relationships between players.
        Provides proximity metrics for tactical analysis.
    
    FEATURES:
        1. Pairwise Distances: All player-to-player distances
        2. Proximity Info: Closest teammates/opponents per player
        3. Distance Matrix: NxN Euclidean distance matrix
        4. Team Spacing: Spread and clustering metrics
        5. Defensive Pressure: How tightly a player is guarded
    
    CACHING:
        - Distance calculations cached by (player1, player2, timestamp)
        - Proximity info cached by (player_id, timestamp)
        - Improves performance for repeated queries
    
    DATA FLOW:
        player.positions → DistanceAnalyzer → proximity metrics → Game Semantics
    """
)


# =============================================================================
# SUMMARY: TRACKING STATE LAYER
# =============================================================================

TRACKING_STATE_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════════╗
║                    TRACKING STATE LAYER SUMMARY                          ║
╚══════════════════════════════════════════════════════════════════════════╝

MODULES:
    1. PlayerDetection   → player.positions[t]
    2. BallTracking      → player.has_ball, ball_position
    3. VelocityAnalysis  → speed, acceleration, distance
    4. DistanceAnalysis  → proximity, spacing, pressure

DATA FLOW:
    Video → PlayerDetection → BallTracking ──→ Downstream Events
                          ↓                 ↓
                   VelocityAnalysis    DistanceAnalysis
                          ↓                 ↓
                   MovementClassifier  Game Semantics

CRITICAL RULES:
    1. PlayerDetection MUST run first (produces positions)
    2. BallTracking MUST run after PlayerDetection (needs positions)
    3. Velocity/Distance are STATELESS (can run anytime after PlayerDetection)
    4. Player.positions is APPEND-ONLY (never overwrite old data)
    5. Player.ID is IMMUTABLE (never changes)

INTEGRATION CONTRACT:
    - All downstream modules DEPEND on player.positions[timestamp]
    - All downstream modules ASSUME positions are in 2D map coordinates
    - All downstream modules ASSUME timestamp is sequential (no gaps)
"""

print(TRACKING_STATE_SUMMARY)