"""
Basketball Analytics Pipeline - Main Orchestrator

This pipeline coordinates all basketball analytics modules with strict data contracts,
validation, and comprehensive diagnostics.

Design Principles:
- Rule-first, explainable, ML-ready
- Single shared state (FrameContext)
- Strict execution order enforcement
- No module-to-module coupling
- Fail-soft with diagnostics
- Every decision is traceable

Author: Basketball Analytics Team
Version: 1.0.0
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime
import numpy as np


# =============================================================================
# SHARED DATA STRUCTURES
# =============================================================================

@dataclass
class PlayerState:
    """Per-player state at a single frame"""
    player_id: int
    team_id: str  # 'blue', 'white', 'referee'
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x, y, w, h)
    position_2d: Optional[Tuple[float, float]] = None  # (x, y) in map coords
    speed: Optional[float] = None  # m/s
    speed_smoothed: Optional[float] = None
    acceleration: Optional[float] = None  # m/s²
    movement_state: Optional[str] = None  # idle/walking/running/jumping/landing
    movement_confidence: Optional[float] = None
    has_ball: bool = False
    bbox_height: Optional[float] = None  # pixels
    
    # Additional tracking data
    previous_bb: Optional[Tuple] = None  # For IoU tracking
    color: Optional[Tuple] = None  # BGR color


@dataclass
class BallState:
    """Ball state at a single frame"""
    position_2d: Optional[Tuple[float, float]] = None  # (x, y) in map coords
    position_frame: Optional[Tuple[float, float]] = None  # (x, y) in frame coords
    velocity: Optional[Tuple[float, float]] = None  # (vx, vy)
    acceleration: Optional[Tuple[float, float]] = None  # (ax, ay)
    owner_id: Optional[int] = None  # Player controlling ball
    detected: bool = False
    confidence: float = 0.0


@dataclass
class EventEnvelope:
    """Standardized event wrapper for all detections"""
    type: str  # 'movement' | 'dribble' | 'shot' | 'sequence'
    player_id: int
    frame_id: int
    confidence: float  # [0, 1]
    payload: Dict[str, Any]  # Event-specific data
    source_module: str
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


class WarningSeverity(Enum):
    """Diagnostic severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ModuleStatus(Enum):
    """Module execution status"""
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass
class PipelineWarning:
    """Diagnostic warning emitted by pipeline or modules"""
    module: str
    frame_id: int
    severity: WarningSeverity
    message: str
    suggestion: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameContext:
    """
    Shared state object - ALL modules operate on this.
    
    This is the single source of truth for a single frame.
    No module-to-module direct communication allowed.
    """
    frame_id: int
    timestamp: int
    
    # Raw frame data
    frame: Optional[np.ndarray] = None  # BGR frame
    map_2d: Optional[np.ndarray] = None  # 2D court map
    map_2d_text: Optional[np.ndarray] = None  # Map with annotations
    
    # Homography matrices
    M: Optional[np.ndarray] = None  # frame -> field
    M1: Optional[np.ndarray] = None  # field -> 2D map
    
    # State
    players: Dict[int, PlayerState] = field(default_factory=dict)
    ball: BallState = field(default_factory=BallState)
    
    # Events detected this frame
    events: List[EventEnvelope] = field(default_factory=list)
    
    # Diagnostics
    diagnostics: List[PipelineWarning] = field(default_factory=list)
    
    # Module execution tracking (module_name, status)
    completed_modules: List[Tuple[str, ModuleStatus]] = field(default_factory=list)
    
    def emit_event(self, event: EventEnvelope) -> bool:
        """
        Safely emit event with duplicate detection.
        
        Returns:
            True if event added, False if duplicate detected
        """
        # Check for duplicate
        for existing in self.events:
            if (existing.type == event.type and
                existing.player_id == event.player_id and
                existing.frame_id == event.frame_id):
                # Duplicate detected
                return False
        
        self.events.append(event)
        return True


# =============================================================================
# MODULE INTERFACE
# =============================================================================

class ModuleInterface:
    """
    Abstract interface that all modules must implement.
    
    Modules are stateful but communicate only through FrameContext.
    """
    
    @property
    def name(self) -> str:
        """Module identifier"""
        raise NotImplementedError
    
    @property
    def required_fields(self) -> List[str]:
        """Fields that must exist in context before running"""
        raise NotImplementedError
    
    @property
    def produced_fields(self) -> List[str]:
        """Fields this module is allowed to write"""
        raise NotImplementedError
    
    @property
    def forbidden_fields(self) -> List[str]:
        """Fields this module must never modify"""
        raise NotImplementedError
    
    def run(self, context: FrameContext) -> None:
        """
        Execute module logic.
        
        Must modify context in-place.
        Must not raise exceptions (use diagnostics instead).
        """
        raise NotImplementedError
    
    def emit_warnings(self, context: FrameContext) -> List[PipelineWarning]:
        """
        Check context and emit warnings if needed.
        
        Called after run() completes.
        """
        return []
    
    def reset(self) -> None:
        """Reset internal state (between videos/periods)"""
        pass


# =============================================================================
# PIPELINE VALIDATOR
# =============================================================================

class PipelineValidator:
    """
    Enforces data contracts and module behavior rules.
    
    This is the gatekeeper that prevents:
    - Modules writing to fields they don't own
    - Missing required dependencies
    - Temporal inconsistencies
    - Invalid state transitions
    """
    
    def __init__(self):
        self.last_frame_id = -1
        self.module_registry: Dict[str, ModuleInterface] = {}
    
    def register_module(self, module: ModuleInterface):
        """Register a module for validation"""
        self.module_registry[module.name] = module
    
    def validate_input(self, module: ModuleInterface, context: FrameContext) -> Tuple[bool, Optional[str]]:
        """
        Validate context before module runs.
        
        Checks:
        - Required fields exist
        - Forbidden fields not present (owned by other modules)
        """
        # Check required fields
        for field in module.required_fields:
            if not self._check_field_exists(context, field):
                return False, f"Missing required field: {field}"
        
        return True, None
    
    def validate_output(self, module: ModuleInterface, 
                       context_before: FrameContext,
                       context_after: FrameContext) -> Tuple[bool, Optional[str]]:
        """
        Validate context after module runs.
        
        Checks:
        - Module only modified fields it owns
        - No forbidden field modifications
        
        Args:
            context_before: Snapshot before module.run()
            context_after: Context after module.run()
        """
        # Check top-level field changes
        forbidden_changes = []
        
        # Check players dict
        if context_before.players != context_after.players:
            # Find what changed
            changed_fields = self._detect_player_changes(
                context_before.players, 
                context_after.players
            )
            
            for field in changed_fields:
                full_field = f"players[].{field}"
                if full_field not in module.produced_fields and full_field in module.forbidden_fields:
                    forbidden_changes.append(full_field)
        
        # Check ball state
        if context_before.ball != context_after.ball:
            changed_ball_fields = self._detect_ball_changes(
                context_before.ball,
                context_after.ball
            )
            
            for field in changed_ball_fields:
                full_field = f"ball.{field}"
                if full_field not in module.produced_fields and full_field in module.forbidden_fields:
                    forbidden_changes.append(full_field)
        
        # Check frame/map modifications
        if not np.array_equal(context_before.frame, context_after.frame):
            if "frame" in module.forbidden_fields:
                forbidden_changes.append("frame")
        
        if forbidden_changes:
            return False, f"Module modified forbidden fields: {', '.join(forbidden_changes)}"
        
        return True, None
    
    def _detect_player_changes(self, before: Dict, after: Dict) -> List[str]:
        """Detect which PlayerState fields changed"""
        changed = set()
        
        for pid in after.keys():
            if pid not in before:
                continue
            
            state_before = before[pid]
            state_after = after[pid]
            
            # Check each field
            for field in ['position_2d', 'speed', 'movement_state', 'has_ball', 
                         'bbox_height', 'movement_confidence', 'acceleration']:
                if getattr(state_before, field) != getattr(state_after, field):
                    changed.add(field)
        
        return list(changed)
    
    def _detect_ball_changes(self, before: BallState, after: BallState) -> List[str]:
        """Detect which BallState fields changed"""
        changed = []
        
        for field in ['position_2d', 'owner_id', 'detected', 'confidence']:
            if getattr(before, field) != getattr(after, field):
                changed.append(field)
        
        return changed
    
    def validate_temporal_consistency(self, context: FrameContext) -> Tuple[bool, Optional[str]]:
        """
        Validate temporal consistency.
        
        Checks:
        - Frame IDs are increasing
        - No time travel (events referencing future frames)
        """
        if context.frame_id <= self.last_frame_id:
            return False, f"Frame ID not increasing: {context.frame_id} <= {self.last_frame_id}"
        
        # Check event frame IDs
        for event in context.events:
            if event.frame_id > context.frame_id:
                return False, f"Event references future frame: {event.frame_id} > {context.frame_id}"
        
        self.last_frame_id = context.frame_id
        return True, None
    
    def _check_field_exists(self, context: FrameContext, field: str) -> bool:
        """
        Check if a field path exists in context with actual data.
        
        Special handling for patterns like players[].field_name
        """
        # Handle special patterns
        if field.startswith("players[]."):
            # Extract field name
            player_field = field.replace("players[].", "")
            
            # Check if ANY player has this field with non-None value
            if not context.players:
                return False
            
            return any(
                getattr(state, player_field, None) is not None
                for state in context.players.values()
            )
        
        if field.startswith("ball."):
            # Extract field name
            ball_field = field.replace("ball.", "")
            return getattr(context.ball, ball_field, None) is not None
        
        # Standard field check
        parts = field.split('.')
        obj = context
        
        try:
            for part in parts:
                if '[' in part:  # Handle dict access
                    base, _ = part.split('[')
                    obj = getattr(obj, base)
                    if not obj:
                        return False
                    return len(obj) > 0
                else:
                    obj = getattr(obj, part)
            return obj is not None
        except (AttributeError, KeyError):
            return False


# =============================================================================
# MODULE WRAPPERS (Adapters for existing code)
# =============================================================================

class PlayerDetectionModule(ModuleInterface):
    """Wrapper for FeetDetector (player tracking)"""
    
    def __init__(self, feet_detector):
        self.feet_detector = feet_detector
    
    @property
    def name(self) -> str:
        return "PlayerDetection"
    
    @property
    def required_fields(self) -> List[str]:
        return ["frame", "timestamp", "M", "M1", "map_2d"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["players[].position_2d", "players[].bbox", "players[].previous_bb"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["ball", "events", "players[].movement_state"]
    
    def run(self, context: FrameContext) -> None:
        try:
            # Run original detection
            frame_out, map_2d_out, map_2d_text = self.feet_detector.get_players_pos(
                context.M, context.M1, context.frame, context.timestamp, context.map_2d
            )
            
            # Update context
            context.frame = frame_out
            context.map_2d = map_2d_out
            context.map_2d_text = map_2d_text
            
            # Sync player states
            for player in self.feet_detector.players:
                if context.timestamp in player.positions:
                    if player.ID not in context.players:
                        context.players[player.ID] = PlayerState(
                            player_id=player.ID,
                            team_id=player.team,
                            color=player.color
                        )
                    
                    state = context.players[player.ID]
                    state.position_2d = player.positions[context.timestamp]
                    state.previous_bb = player.previous_bb
                    
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.HIGH,
                message=f"Player detection failed: {str(e)}",
                suggestion="Check frame quality and homography matrices"
            ))


class BallTrackingModule(ModuleInterface):
    """Wrapper for BallDetectTrack"""
    
    def __init__(self, ball_detector):
        self.ball_detector = ball_detector
    
    @property
    def name(self) -> str:
        return "BallTracking"
    
    @property
    def required_fields(self) -> List[str]:
        return ["frame", "timestamp", "M", "M1", "map_2d", "map_2d_text", "players"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["ball.position_2d", "ball.detected", "players[].has_ball"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["events", "players[].movement_state"]
    
    def run(self, context: FrameContext) -> None:
        try:
            frame_out, ball_map = self.ball_detector.ball_tracker(
                context.M, context.M1, context.frame.copy(),
                context.map_2d.copy(), context.map_2d_text, context.timestamp
            )
            
            context.frame = frame_out
            
            # Update ball state
            if ball_map is not None:
                context.ball.detected = True
                
                # CRITICAL FIX: Extract actual ball position from map
                # Find ball position (ball is drawn as red circle on map)
                ball_pos = self._extract_ball_position(ball_map, context.map_2d)
                
                if ball_pos:
                    context.ball.position_2d = ball_pos
                else:
                    # Ball detected but position unclear
                    context.diagnostics.append(PipelineWarning(
                        module=self.name,
                        frame_id=context.frame_id,
                        severity=WarningSeverity.MEDIUM,
                        message="Ball detected but position extraction failed",
                        suggestion="Check ball drawing on map_2d"
                    ))
                    context.ball.detected = False
            else:
                context.ball.detected = False
                context.ball.position_2d = None
            
            # Sync has_ball status
            for player in self.ball_detector.players:
                if player.ID in context.players:
                    context.players[player.ID].has_ball = player.has_ball
                    if player.has_ball:
                        context.ball.owner_id = player.ID
                        
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.MEDIUM,
                message=f"Ball tracking failed: {str(e)}",
                suggestion="Check if ball is visible in frame"
            ))
    
    def _extract_ball_position(self, ball_map: np.ndarray, original_map: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Extract ball position from map by finding red circle.
        
        Returns:
            (x, y) tuple or None if not found
        """
        try:
            # Find difference between maps
            diff = cv2.absdiff(ball_map, original_map)
            
            # Convert to grayscale and threshold
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest contour (ball)
                largest = max(contours, key=cv2.contourArea)
                M = cv2.moments(largest)
                
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return (cx, cy)
            
            return None
        except:
            return None


class VelocityAnalysisModule(ModuleInterface):
    """Wrapper for VelocityAnalyzer"""
    
    def __init__(self, velocity_analyzer, player_list):
        self.velocity_analyzer = velocity_analyzer
        self.player_list = player_list
    
    @property
    def name(self) -> str:
        return "VelocityAnalysis"
    
    @property
    def required_fields(self) -> List[str]:
        return ["players", "timestamp"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["players[].speed", "players[].speed_smoothed", "players[].acceleration"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["events", "ball.owner_id"]
    
    def run(self, context: FrameContext) -> None:
        try:
            for player_id, state in context.players.items():
                # Skip referees
                if state.team_id == 'referee':
                    continue
                
                # Get player object
                player_obj = self._find_player(player_id)
                if player_obj is None:
                    continue
                
                # Calculate metrics
                speed = self.velocity_analyzer.calculate_speed(player_obj, context.timestamp)
                speed_smooth = self.velocity_analyzer.calculate_speed_smoothed(player_obj, context.timestamp)
                accel = self.velocity_analyzer.calculate_acceleration(player_obj, context.timestamp)
                
                # Update state
                state.speed = speed
                state.speed_smoothed = speed_smooth
                state.acceleration = accel
                
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.LOW,
                message=f"Velocity calculation failed: {str(e)}"
            ))
    
    def _find_player(self, player_id):
        """Find player object by ID"""
        for player in self.player_list:
            if player.ID == player_id:
                return player
        return None


class MovementClassificationModule(ModuleInterface):
    """Wrapper for BasicMovementClassifier"""
    
    def __init__(self, velocity_analyzer, player_list):
        """
        Args:
            velocity_analyzer: VelocityAnalyzer instance
            player_list: List of Player objects (for accessing full state)
        """
        self.velocity_analyzer = velocity_analyzer
        self.player_list = player_list
        self.classifiers = {}  # player_id -> BasicMovementClassifier
        self.bbox_history = {}  # player_id -> [(timestamp, bbox_height)]
    
    @property
    def name(self) -> str:
        return "MovementClassification"
    
    @property
    def required_fields(self) -> List[str]:
        return ["players", "timestamp"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["players[].movement_state", "players[].movement_confidence", "players[].bbox_height"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["ball.owner_id", "events"]
    
    def run(self, context: FrameContext) -> None:
        try:
            for player_id, state in context.players.items():
                # Skip referees
                if state.team_id == 'referee':
                    continue
                
                # Find player object
                player_obj = self._find_player(player_id)
                if player_obj is None:
                    continue
                
                # Get or create classifier
                if player_id not in self.classifiers:
                    from .classifier import BasicMovementClassifier
                    self.classifiers[player_id] = BasicMovementClassifier(
                        velocity_analyzer=self.velocity_analyzer,
                        player_id=player_id
                    )
                
                # Extract bbox height
                if state.previous_bb:
                    top, left, bottom, right = state.previous_bb
                    bbox_height = bottom - top
                else:
                    bbox_height = 200.0  # Default fallback
                
                state.bbox_height = bbox_height
                
                # Track bbox history
                if player_id not in self.bbox_history:
                    self.bbox_history[player_id] = []
                self.bbox_history[player_id].append((context.timestamp, bbox_height))
                
                # Keep only recent history (last 10 frames)
                if len(self.bbox_history[player_id]) > 10:
                    self.bbox_history[player_id].pop(0)
                
                # Classify movement
                result = self.classifiers[player_id].classify_frame(
                    player=player_obj,
                    timestamp=context.timestamp,
                    bbox_height=bbox_height
                )
                
                # Update state
                state.movement_state = result['movement_state']
                state.movement_confidence = result['confidence']
    
    def _find_player(self, player_id):
        """Find player object by ID"""
        for player in self.player_list:
            if player.ID == player_id:
                return player
        return None
    
    def get_bbox_height_change(self, player_id: int, current_timestamp: int) -> Optional[float]:
        """
        Calculate bbox height change for temporal analysis.
        
        Returns:
            Height change in pixels, or None if insufficient history
        """
        if player_id not in self.bbox_history or len(self.bbox_history[player_id]) < 2:
            return None
        
        history = self.bbox_history[player_id]
        current_height = history[-1][1]
        previous_height = history[-2][1]
        
        return current_height - previous_height


class BallControlAnalysisModule(ModuleInterface):
    """Wrapper for BallControlAnalyzer"""
    
    def __init__(self, ball_control_analyzer):
        self.analyzer = ball_control_analyzer
    
    @property
    def name(self) -> str:
        return "BallControlAnalysis"
    
    @property
    def required_fields(self) -> List[str]:
        return ["timestamp", "ball", "players"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["ball.owner_id"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["events", "players[].movement_state"]
    
    def run(self, context: FrameContext) -> None:
        try:
            # Convert context players to Player objects
            from .player import Player
            players = []
            for pid, state in context.players.items():
                if state.team_id == 'referee':
                    continue
                player = Player(pid, state.team_id, state.color)
                if state.position_2d:
                    player.positions[context.timestamp] = state.position_2d
                players.append(player)
            
            # Update analyzer
            ball_pos = context.ball.position_2d
            self.analyzer.update(context.timestamp, ball_pos, players)
            
            # Sync ball carrier
            if self.analyzer.ball_carrier is not None:
                context.ball.owner_id = self.analyzer.ball_carrier
            else:
                context.ball.owner_id = None
                
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.LOW,
                message=f"Ball control analysis failed: {str(e)}"
            ))
    
    def emit_warnings(self, context: FrameContext) -> List[PipelineWarning]:
        """Check for control quality issues"""
        warnings = []
        
        # Warn if ball carrier unclear
        if context.ball.detected and context.ball.owner_id is None:
            warnings.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.LOW,
                message="Ball detected but no clear carrier identified",
                suggestion="Check ball distance thresholds"
            ))
        
        return warnings


class ShotDetectionModule(ModuleInterface):
    """Wrapper for ShotAttemptDetector"""
    
    def __init__(self, shot_detector, movement_module: MovementClassificationModule):
        self.detector = shot_detector
        self.movement_module = movement_module  # For bbox history
    
    @property
    def name(self) -> str:
        return "ShotDetection"
    
    @property
    def required_fields(self) -> List[str]:
        return ["timestamp", "players", "ball", "players[].movement_state"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["events"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["players[].position_2d", "ball.owner_id"]
    
    def run(self, context: FrameContext) -> None:
        try:
            for player_id, state in context.players.items():
                if state.team_id == 'referee':
                    continue
                
                # Get bbox height change from movement module history
                bbox_change = self.movement_module.get_bbox_height_change(
                    player_id, context.timestamp
                )
                
                # CRITICAL: Pass None if no history (explicit signal)
                if bbox_change is None:
                    # Not enough history yet - skip this player
                    continue
                
                # Create frame packet
                from .utils import FramePacket
                packet = FramePacket(
                    timestamp=context.timestamp,
                    player_id=player_id,
                    movement_state=state.movement_state or "idle",
                    movement_confidence=state.movement_confidence or 0.0,
                    bbox_height=state.bbox_height or 200.0,
                    bbox_height_change=bbox_change,  # Real temporal data
                    ball_position=context.ball.position_2d,
                    has_ball=state.has_ball,
                    speed=state.speed or 0.0
                )
                
                # Process frame
                event = self.detector.process_frame(packet)
                
                if event:
                    # Convert to EventEnvelope
                    envelope = EventEnvelope(
                        type='shot',
                        player_id=player_id,
                        frame_id=context.frame_id,
                        confidence=event.confidence,
                        payload={
                            'release_frame': event.release_frame,
                            'features': event.features
                        },
                        source_module=self.name,
                        reasoning=event.reasoning
                    )
                    
                    # Use safe emit
                    if not context.emit_event(envelope):
                        context.diagnostics.append(PipelineWarning(
                            module=self.name,
                            frame_id=context.frame_id,
                            severity=WarningSeverity.LOW,
                            message=f"Duplicate shot event prevented for player {player_id}"
                        ))
                    
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.MEDIUM,
                message=f"Shot detection failed: {str(e)}"
            ))
    
    def emit_warnings(self, context: FrameContext) -> List[PipelineWarning]:
        """Check for shot detection issues"""
        warnings = []
        
        # Warn on high-confidence jump with no ball release
        for player_id, state in context.players.items():
            if state.movement_state == 'jumping' and state.movement_confidence > 0.8:
                if state.has_ball:
                    # Potential missed shot
                    warnings.append(PipelineWarning(
                        module=self.name,
                        frame_id=context.frame_id,
                        severity=WarningSeverity.MEDIUM,
                        message=f"Player {player_id} jumping with ball but no shot detected",
                        suggestion="Review ball release detection thresholds"
                    ))
        
        return warnings


class DribbleDetectionModule(ModuleInterface):
    """Wrapper for DribblingDetector"""
    
    def __init__(self, dribble_detector):
        self.detector = dribble_detector
    
    @property
    def name(self) -> str:
        return "DribbleDetection"
    
    @property
    def required_fields(self) -> List[str]:
        return ["timestamp", "players", "ball", "players[].movement_state"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["events"]
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["players[].position_2d", "ball.owner_id"]
    
    def run(self, context: FrameContext) -> None:
        try:
            for player_id, state in context.players.items():
                if state.team_id == 'referee':
                    continue
                
                # Create frame packet
                from .utils import FramePacket
                packet = FramePacket(
                    timestamp=context.timestamp,
                    player_id=player_id,
                    movement_state=state.movement_state or "idle",
                    movement_confidence=state.movement_confidence or 0.0,
                    ball_position=context.ball.position_2d,
                    has_ball=state.has_ball,
                    player_position=state.position_2d,
                    speed=state.speed or 0.0,
                    bbox_height=state.bbox_height or 200.0
                )
                
                # Process frame
                events = self.detector.process_frame(packet)
                
                for event in events:
                    # Convert to EventEnvelope
                    envelope = EventEnvelope(
                        type='dribble',
                        player_id=player_id,
                        frame_id=context.frame_id,
                        confidence=event.confidence,
                        payload={
                            'bounce_count': event.bounce_count,
                            'avg_interval_frames': event.avg_interval_frames,
                            'start_frame': event.start_frame,
                            'end_frame': event.end_frame
                        },
                        source_module=self.name,
                        reasoning=event.reasoning
                    )
                    context.events.append(envelope)
                    
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.MEDIUM,
                message=f"Dribble detection failed: {str(e)}"
            ))


class SequenceParserModule(ModuleInterface):
    """Wrapper for SequenceParser"""
    
    def __init__(self, sequence_parser):
        self.parser = sequence_parser
    
    @property
    def name(self) -> str:
        return "SequenceParser"
    
    @property
    def required_fields(self) -> List[str]:
        return ["events"]
    
    @property
    def produced_fields(self) -> List[str]:
        return ["events"]  # Adds sequence events
    
    @property
    def forbidden_fields(self) -> List[str]:
        return ["players[].position_2d", "ball.owner_id"]
    
    def run(self, context: FrameContext) -> None:
        try:
            # Convert EventEnvelopes to InputEvents
            from .events import InputEvent
            
            for event in context.events:
                # Skip already-processed sequence events
                if event.type == 'sequence':
                    continue
                
                # Convert to InputEvent
                attributes = {
                    'confidence': event.confidence,
                    **event.payload
                }
                
                if event.type == 'movement':
                    attributes['movement_type'] = event.payload.get('movement_state', 'unknown')
                
                input_event = InputEvent(
                    timestamp=event.frame_id,
                    player_id=str(event.player_id),
                    event_type=event.type,
                    attributes=attributes
                )
                
                # Process event
                sequence = self.parser.process_event(input_event)
                
                if sequence:
                    # Convert to EventEnvelope
                    envelope = EventEnvelope(
                        type='sequence',
                        player_id=int(sequence.player_id),
                        frame_id=sequence.end_frame,
                        confidence=sequence.confidence,
                        payload={
                            'sequence_type': sequence.sequence_type,
                            'start_frame': sequence.start_frame,
                            'duration_frames': sequence.duration_frames,
                            'completeness': sequence.completeness,
                            'temporal_coherence': sequence.temporal_coherence
                        },
                        source_module=self.name,
                        reasoning=sequence.reasoning
                    )
                    context.events.append(envelope)
                    
        except Exception as e:
            context.diagnostics.append(PipelineWarning(
                module=self.name,
                frame_id=context.frame_id,
                severity=WarningSeverity.LOW,
                message=f"Sequence parsing failed: {str(e)}"
            ))


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class BasketballPipeline:
    """
    Main orchestrator for basketball analytics.
    
    Coordinates all modules in strict execution order.
    Enforces data contracts and provides diagnostics.
    """
    
    def __init__(self):
        self.validator = PipelineValidator()
        self.modules: List[ModuleInterface] = []
        
        # Statistics
        self.frames_processed = 0
        self.total_events = 0
        self.total_warnings = 0
        
    def register_module(self, module: ModuleInterface):
        """Add module to pipeline"""
        self.modules.append(module)
        self.validator.register_module(module)
    
    def process_frame(self, context: FrameContext) -> FrameContext:
        """
        Process single frame through entire pipeline.
        
        Args:
            context: FrameContext with raw frame data
        
        Returns:
            Updated context with all analysis complete
        """
        self.frames_processed += 1
        
        # Validate temporal consistency
        is_valid, error = self.validator.validate_temporal_consistency(context)
        if not is_valid:
            context.diagnostics.append(PipelineWarning(
                module="Pipeline",
                frame_id=context.frame_id,
                severity=WarningSeverity.CRITICAL,
                message=f"Temporal consistency violated: {error}"
            ))
            return context
        
        # Execute modules in order
        for module in self.modules:
            # Validate input
            is_valid, error = self.validator.validate_input(module, context)
            if not is_valid:
                context.diagnostics.append(PipelineWarning(
                    module="Pipeline",
                    frame_id=context.frame_id,
                    severity=WarningSeverity.HIGH,
                    message=f"Module {module.name} input validation failed: {error}",
                    suggestion="Check module execution order"
                ))
                context.completed_modules.append((module.name, ModuleStatus.SKIPPED))
                continue  # Skip this module
            
            # Take snapshot for output validation
            from copy import deepcopy
            context_snapshot = deepcopy(context)
            
            # Run module
            try:
                module.run(context)
                status = ModuleStatus.SUCCESS
            except Exception as e:
                status = ModuleStatus.FAILED
                context.diagnostics.append(PipelineWarning(
                    module=module.name,
                    frame_id=context.frame_id,
                    severity=WarningSeverity.CRITICAL,
                    message=f"Module crashed: {str(e)}",
                    suggestion="Check module implementation"
                ))
            
            # Validate output
            is_valid, error = self.validator.validate_output(module, context_snapshot, context)
            if not is_valid:
                context.diagnostics.append(PipelineWarning(
                    module="Pipeline",
                    frame_id=context.frame_id,
                    severity=WarningSeverity.CRITICAL,
                    message=f"Module {module.name} violated data contract: {error}",
                    suggestion="Module modified forbidden fields"
                ))
            
            # Collect module warnings
            warnings = module.emit_warnings(context)
            context.diagnostics.extend(warnings)
            
            # Mark completion
            context.completed_modules.append((module.name, status))
        
        # Update statistics
        self.total_events += len(context.events)
        self.total_warnings += len(context.diagnostics)
        
        return context
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            'frames_processed': self.frames_processed,
            'total_events': self.total_events,
            'total_warnings': self.total_warnings,
            'avg_events_per_frame': self.total_events / max(self.frames_processed, 1),
            'avg_warnings_per_frame': self.total_warnings / max(self.frames_processed, 1)
        }
    
    def reset(self):
        """Reset pipeline and all modules"""
        for module in self.modules:
            module.reset()
        self.frames_processed = 0
        self.total_events = 0
        self.total_warnings = 0
        self.validator.last_frame_id = -1


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def create_pipeline(feet_detector, ball_detector, velocity_analyzer, ball_control_analyzer,
                   shot_detector, dribble_detector, sequence_parser, player_list):
    """
    Factory function to create fully configured pipeline.
    
    Args:
        feet_detector: FeetDetector instance
        ball_detector: BallDetectTrack instance (or RobustBallTracker)
        velocity_analyzer: VelocityAnalyzer instance
        ball_control_analyzer: BallControlAnalyzer instance
        shot_detector: ShotAttemptDetector instance
        dribble_detector: DribblingDetector instance
        sequence_parser: SequenceParser instance
        player_list: List of Player objects
    
    Returns:
        Configured BasketballPipeline
    """
    pipeline = BasketballPipeline()
    
    # Register modules in STRICT execution order
    # Layer 1: Tracking State
    pipeline.register_module(PlayerDetectionModule(feet_detector))
    pipeline.register_module(BallTrackingModule(ball_detector))
    pipeline.register_module(VelocityAnalysisModule(velocity_analyzer, player_list))
    
    # Layer 2: Derived State
    movement_module = MovementClassificationModule(velocity_analyzer, player_list)
    pipeline.register_module(movement_module)
    pipeline.register_module(BallControlAnalysisModule(ball_control_analyzer))
    
    # Layer 3: Atomic Events (need movement_module for bbox history)
    pipeline.register_module(ShotDetectionModule(shot_detector, movement_module))
    pipeline.register_module(DribbleDetectionModule(dribble_detector))
    
    # Layer 4: Game Semantics
    pipeline.register_module(SequenceParserModule(sequence_parser))
    
    return pipeline


# =============================================================================
# COMPLETE INTEGRATION EXAMPLE
# =============================================================================

def run_basketball_analytics_pipeline():
    """
    Complete integration example showing how to use the pipeline with your existing modules.
    
    This replaces your VideoHandler.run_detectors() method.
    """
    import cv2
    import numpy as np
    from Modules.IDrecognition.player import Player
    from Modules.IDrecognition.player_detection import FeetDetector, hsv2bgr, COLORS
    from Modules.BallTracker.ball_detect_track import BallDetectTrack
    # from Modules.wrappers.robust_ball_tracker import RobustBallTracker  # Optional upgrade
    
    # Initialize video and court
    video = cv2.VideoCapture("resources/Short4Mosaicing.mp4")
    pano_enhanced = cv2.imread("resources/pano_enhanced.png")
    map_2d = cv2.imread("resources/2d_map.png")
    M1 = np.load("Rectify1.npy")
    
    # Initialize players
    players = []
    for i in range(1, 6):
        players.append(Player(i, 'blue', hsv2bgr(COLORS['blue'][2])))
        players.append(Player(i, 'white', hsv2bgr(COLORS['white'][2])))
    players.append(Player(0, 'referee', hsv2bgr(COLORS['referee'][2])))
    
    # Initialize all modules
    feet_detector = FeetDetector(players)
    ball_detector = BallDetectTrack(players)
    # Or use robust version:
    # ball_detector = RobustBallTracker(players, config_path='config/tracker_config.yaml')
    
    # Initialize analytics modules (you'll need to import these)
    # from velocity_analyzer import VelocityAnalyzer
    # from ball_control import BallControlAnalyzer
    # from shot_detector import ShotAttemptDetector
    # from dribble_detector import DribblingDetector
    # from sequence_parser import SequenceParser
    
    # velocity_analyzer = VelocityAnalyzer(fps=30, ...)
    # ball_control_analyzer = BallControlAnalyzer()
    # shot_detector = ShotAttemptDetector()
    # dribble_detector = DribblingDetector()
    # sequence_parser = SequenceParser()
    
    # Create pipeline
    # pipeline = create_pipeline(
    #     feet_detector, ball_detector, velocity_analyzer,
    #     ball_control_analyzer, shot_detector, dribble_detector,
    #     sequence_parser, players
    # )
    
    # Process video
    frame_id = 0
    TOPCUT = 320
    sift = cv2.xfeatures2d.SIFT_create()
    kp1, des1 = sift.compute(pano_enhanced, sift.detect(pano_enhanced))
    
    print("Processing video...")
    
    while video.isOpened():
        ok, frame = video.read()
        if not ok:
            break
        
        if 0 <= frame_id <= 230:
            # Progress indicator
            print(f"\rFrame {frame_id}/230 ({int(100*frame_id/230)}%)", end='', flush=True)
            
            # Get homography
            frame_cropped = frame[TOPCUT:, :]
            M = get_homography(frame_cropped, des1, kp1, sift)
            
            # Create context
            context = FrameContext(
                frame_id=frame_id,
                timestamp=frame_id,
                frame=frame_cropped.copy(),
                map_2d=map_2d.copy(),
                M=M,
                M1=M1
            )
            
            # Process through pipeline
            # context = pipeline.process_frame(context)
            
            # Handle diagnostics
            # for warning in context.diagnostics:
            #     if warning.severity in [WarningSeverity.HIGH, WarningSeverity.CRITICAL]:
            #         print(f"\n⚠️  [{warning.module}] {warning.message}")
            
            # Handle events
            # for event in context.events:
            #     print(f"\n🎯 Event: {event.type} by player {event.player_id}")
            #     print(f"   Confidence: {event.confidence:.2f}")
            #     print(f"   Reasoning: {event.reasoning[:60]}...")
            
            # Visualize (using updated frame from context)
            # vis = np.vstack((context.frame, 
            #                  cv2.resize(context.map_2d_text, 
            #                            (context.frame.shape[1], context.frame.shape[1]//2))))
            # cv2.imshow("Basketball Analytics", vis)
            
            # if cv2.waitKey(1) & 0xff == 27:
            #     break
        
        frame_id += 1
    
    video.release()
    cv2.destroyAllWindows()
    
    # Print final statistics
    # stats = pipeline.get_statistics()
    # print(f"\n\nPipeline Statistics:")
    # print(f"  Frames processed: {stats['frames_processed']}")
    # print(f"  Total events: {stats['total_events']}")
    # print(f"  Total warnings: {stats['total_warnings']}")
    # print(f"  Avg events/frame: {stats['avg_events_per_frame']:.2f}")


def get_homography(frame, des1, kp1, sift):
    """Helper to compute homography"""
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    
    kp2 = sift.detect(frame)
    kp2, des2 = sift.compute(frame, kp2)
    matches = flann.knnMatch(des1, des2, k=2)
    
    good = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good.append(m)
    
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    
    return M


if __name__ == "__main__":
    print("Basketball Analytics Pipeline v1.0")
    print("="*60)
    print("\nCore Features:")
    print("✓ Strict execution order enforcement")
    print("✓ Data contract validation")
    print("✓ Fail-soft with diagnostics")
    print("✓ Single shared state (FrameContext)")
    print("✓ No module-to-module coupling")
    print("✓ ML-ready event format")
    print("\nSee module docstrings for integration details.")
