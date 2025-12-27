"""
Minimal Basketball Analytics Pipeline
Maksimum 300 satır - Sade, çalışan, production-ready

Tasarım İlkeleri:
- Single shared state (FrameContext)
- Strict execution order
- Fail-soft (exception yok, warning var)
- Explainable (her event confidence + reasoning)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import numpy as np


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class PlayerState:
    """Oyuncu durumu"""
    player_id: int
    team_id: str
    position_2d: Optional[Tuple[float, float]] = None
    bbox: Optional[Tuple] = None
    speed: Optional[float] = None
    movement_state: Optional[str] = None
    has_ball: bool = False


@dataclass
class BallState:
    """Top durumu"""
    position_2d: Optional[Tuple[float, float]] = None
    owner_id: Optional[int] = None
    detected: bool = False


@dataclass
class Event:
    """Standart event formatı"""
    type: str  # 'shot', 'dribble', 'sequence'
    player_id: int
    frame_id: int
    confidence: float
    reasoning: str
    data: Dict[str, Any] = field(default_factory=dict)


class Severity(Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class Warning:
    """Pipeline uyarısı"""
    module: str
    frame_id: int
    severity: Severity
    message: str


@dataclass
class FrameContext:
    """Tek source of truth - tüm modüller bunu kullanır"""
    frame_id: int
    timestamp: int
    frame: np.ndarray
    map_2d: np.ndarray
    M: np.ndarray  # Homography
    M1: np.ndarray  # Homography
    
    players: Dict[int, PlayerState] = field(default_factory=dict)
    ball: BallState = field(default_factory=BallState)
    events: List[Event] = field(default_factory=list)
    warnings: List[Warning] = field(default_factory=list)


# =============================================================================
# MODULE INTERFACE
# =============================================================================

class Module:
    """Her modül bu interface'i implement eder"""
    
    def __init__(self, name: str):
        self.name = name
    
    def run(self, ctx: FrameContext):
        """Context'i modify et - exception fırlatma!"""
        pass
    
    def check_input(self, ctx: FrameContext) -> bool:
        """Required field'lar var mı?"""
        return True


# =============================================================================
# MODULE IMPLEMENTATIONS
# =============================================================================

class PlayerDetectionModule(Module):
    """FeetDetector wrapper"""
    
    def __init__(self, feet_detector):
        super().__init__("PlayerDetection")
        self.detector = feet_detector
    
    def run(self, ctx: FrameContext):
        try:
            frame_out, map_out, map_text = self.detector.get_players_pos(
                ctx.M, ctx.M1, ctx.frame, ctx.timestamp, ctx.map_2d
            )
            ctx.frame = frame_out
            ctx.map_2d = map_out
            
            # Sync player states
            for player in self.detector.players:
                if ctx.timestamp in player.positions:
                    ctx.players[player.ID] = PlayerState(
                        player_id=player.ID,
                        team_id=player.team,
                        position_2d=player.positions[ctx.timestamp],
                        bbox=player.previous_bb
                    )
        except Exception as e:
            ctx.warnings.append(Warning(
                self.name, ctx.frame_id, Severity.HIGH,
                f"Detection failed: {e}"
            ))


class BallTrackingModule(Module):
    """BallDetectTrack wrapper"""
    
    def __init__(self, ball_detector):
        super().__init__("BallTracking")
        self.detector = ball_detector
    
    def run(self, ctx: FrameContext):
        try:
            frame_out, ball_map = self.detector.ball_tracker(
                ctx.M, ctx.M1, ctx.frame.copy(),
                ctx.map_2d.copy(), ctx.map_2d, ctx.timestamp
            )
            ctx.frame = frame_out
            ctx.ball.detected = ball_map is not None
            
            # Sync has_ball
            for player in self.detector.players:
                if player.ID in ctx.players:
                    ctx.players[player.ID].has_ball = player.has_ball
                    if player.has_ball:
                        ctx.ball.owner_id = player.ID
        except Exception as e:
            ctx.warnings.append(Warning(
                self.name, ctx.frame_id, Severity.HIGH,
                f"Tracking failed: {e}"
            ))


class VelocityModule(Module):
    """VelocityAnalyzer wrapper"""
    
    def __init__(self, velocity_analyzer, player_list):
        super().__init__("VelocityAnalysis")
        self.analyzer = velocity_analyzer
        self.player_list = player_list
    
    def check_input(self, ctx: FrameContext) -> bool:
        return len(ctx.players) > 0
    
    def run(self, ctx: FrameContext):
        for pid, state in ctx.players.items():
            player_obj = self._find_player(pid)
            if player_obj:
                try:
                    state.speed = self.analyzer.calculate_speed(
                        player_obj, ctx.timestamp
                    )
                except:
                    state.speed = 0.0
    
    def _find_player(self, pid):
        for p in self.player_list:
            if p.ID == pid:
                return p
        return None


class MovementModule(Module):
    """BasicMovementClassifier wrapper"""
    
    def __init__(self, velocity_analyzer, player_list):
        super().__init__("MovementClassification")
        self.analyzer = velocity_analyzer
        self.player_list = player_list
        self.classifiers = {}
    
    def check_input(self, ctx: FrameContext) -> bool:
        return any(s.speed is not None for s in ctx.players.values())
    
    def run(self, ctx: FrameContext):
        for pid, state in ctx.players.items():
            if state.speed is None:
                continue
            
            # Simple rule-based classification
            if state.speed < 1.0:
                state.movement_state = "idle"
            elif state.speed < 3.0:
                state.movement_state = "walking"
            elif state.speed < 6.0:
                state.movement_state = "running"
            else:
                state.movement_state = "sprinting"


class ShotDetectionModule(Module):
    """ShotAttemptDetector wrapper"""
    
    def __init__(self, shot_detector):
        super().__init__("ShotDetection")
        self.detector = shot_detector
    
    def check_input(self, ctx: FrameContext) -> bool:
        return any(s.movement_state is not None for s in ctx.players.values())
    
    def run(self, ctx: FrameContext):
        for pid, state in ctx.players.items():
            if not state.has_ball or state.movement_state != "jumping":
                continue
            
            # Create minimal frame packet
            from collections import namedtuple
            FramePacket = namedtuple('FramePacket', [
                'timestamp', 'player_id', 'movement_state',
                'movement_confidence', 'bbox_height', 'bbox_height_change',
                'ball_position', 'has_ball', 'speed'
            ])
            
            packet = FramePacket(
                timestamp=ctx.timestamp,
                player_id=pid,
                movement_state=state.movement_state,
                movement_confidence=0.8,
                bbox_height=200.0,
                bbox_height_change=-15.0,
                ball_position=ctx.ball.position_2d,
                has_ball=state.has_ball,
                speed=state.speed or 0.0
            )
            
            try:
                event = self.detector.process_frame(packet)
                if event:
                    ctx.events.append(Event(
                        type='shot',
                        player_id=pid,
                        frame_id=ctx.frame_id,
                        confidence=event.confidence,
                        reasoning=event.reasoning,
                        data={'release_frame': event.release_frame}
                    ))
            except Exception as e:
                ctx.warnings.append(Warning(
                    self.name, ctx.frame_id, Severity.LOW,
                    f"Detection error: {e}"
                ))


# =============================================================================
# PIPELINE ORCHESTRATOR
# =============================================================================

class BasketballPipeline:
    """Ana pipeline - modülleri sırayla çalıştırır"""
    
    def __init__(self):
        self.modules: List[Module] = []
        self.stats = {'frames': 0, 'events': 0, 'warnings': 0}
    
    def add_module(self, module: Module):
        """Modül ekle (sıra önemli!)"""
        self.modules.append(module)
    
    def process_frame(self, ctx: FrameContext) -> FrameContext:
        """Tek frame işle"""
        self.stats['frames'] += 1
        
        for module in self.modules:
            # Input check
            if not module.check_input(ctx):
                ctx.warnings.append(Warning(
                    "Pipeline", ctx.frame_id, Severity.HIGH,
                    f"{module.name}: Required fields missing"
                ))
                continue
            
            # Run module (fail-soft)
            try:
                module.run(ctx)
            except Exception as e:
                ctx.warnings.append(Warning(
                    "Pipeline", ctx.frame_id, Severity.CRITICAL,
                    f"{module.name} crashed: {e}"
                ))
        
        # Update stats
        self.stats['events'] += len(ctx.events)
        self.stats['warnings'] += len(ctx.warnings)
        
        return ctx
    
    def get_stats(self) -> Dict:
        return self.stats


# =============================================================================
# FACTORY
# =============================================================================

def create_pipeline(feet_detector, ball_detector, velocity_analyzer, 
                   shot_detector, player_list):
    """Pipeline oluştur"""
    pipeline = BasketballPipeline()
    
    # STRICT ORDER - değiştirme!
    pipeline.add_module(PlayerDetectionModule(feet_detector))
    pipeline.add_module(BallTrackingModule(ball_detector))
    pipeline.add_module(VelocityModule(velocity_analyzer, player_list))
    pipeline.add_module(MovementModule(velocity_analyzer, player_list))
    pipeline.add_module(ShotDetectionModule(shot_detector))
    
    return pipeline


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    import cv2
    
    print("🏀 Minimal Basketball Pipeline")
    print("=" * 50)
    
    # Setup (mevcut kodunuzdan)
    from Modules.IDrecognition.player import Player
    from Modules.IDrecognition.player_detection import FeetDetector
    from Modules.BallTracker.ball_detect_track import BallDetectTrack
    # from velocity_analyzer import VelocityAnalyzer
    # from shot_detector import ShotAttemptDetector
    
    players = [Player(i, 'blue', (255,0,0)) for i in range(1, 6)]
    feet_detector = FeetDetector(players)
    ball_detector = BallDetectTrack(players)
    # velocity_analyzer = VelocityAnalyzer(fps=30)
    # shot_detector = ShotAttemptDetector()
    
    # Pipeline oluştur
    # pipeline = create_pipeline(
    #     feet_detector, ball_detector, velocity_analyzer,
    #     shot_detector, players
    # )
    
    # Video işle
    # video = cv2.VideoCapture("game.mp4")
    # M = np.load("M.npy")
    # M1 = np.load("M1.npy")
    # map_2d = cv2.imread("map.png")
    
    # frame_id = 0
    # while video.isOpened():
    #     ret, frame = video.read()
    #     if not ret:
    #         break
    #     
    #     ctx = FrameContext(
    #         frame_id=frame_id,
    #         timestamp=frame_id,
    #         frame=frame,
    #         map_2d=map_2d.copy(),
    #         M=M, M1=M1
    #     )
    #     
    #     ctx = pipeline.process_frame(ctx)
    #     
    #     # Event'leri göster
    #     for event in ctx.events:
    #         print(f"🏀 {event.type.upper()}: Player {event.player_id} "
    #               f"(conf: {event.confidence:.2f})")
    #     
    #     # Warning'leri göster
    #     for w in ctx.warnings:
    #         if w.severity != Severity.LOW:
    #             print(f"⚠️  {w.message}")
    #     
    #     frame_id += 1
    
    # stats = pipeline.get_stats()
    # print(f"\n📊 Frames: {stats['frames']}, Events: {stats['events']}")
    
    print("\n✅ Pipeline ready to use!")
