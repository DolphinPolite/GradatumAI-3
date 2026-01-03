"""
Basketball Analytics - Module Registry
Merkezi modül kayıt sistemi - TÜM modüller burada tanımlı
"""

from typing import Dict, Type, Any
from dataclasses import dataclass
import yaml


# =============================================================================
# MODULE BASE CLASS
# =============================================================================

class BaseModule:
    """Tüm modüllerin uyması gereken interface"""
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
    
    def process(self, data: Dict) -> Dict:
        """
        Ana işlem metodu.
        
        Args:
            data: Önceki modüllerden gelen dict
        
        Returns:
            Güncellenmiş data dict
        """
        raise NotImplementedError(f"{self.name} must implement process()")
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        """
        Input validasyonu.
        
        Returns:
            (is_valid, error_message)
        """
        return True, ""
    
    def get_requirements(self) -> list[str]:
        """Bu modülün ihtiyaç duyduğu data key'leri"""
        return []
    
    def get_outputs(self) -> list[str]:
        """Bu modülün üreteceği data key'leri"""
        return []


# =============================================================================
# MODULE IMPLEMENTATIONS
# =============================================================================

class IdRecognitionModule(BaseModule):
    """1. ID & Team Recognition"""
    
    def __init__(self, **kwargs):
        # "TdRecognition" yerine "id_recognition" (Registry'deki key ile aynı olsun)
        super().__init__("id_recognition", **kwargs) 
        self.feet_detector = kwargs.get('feet_detector')
    
    def get_requirements(self) -> list[str]:
        return ['frame', 'timestamp', 'M', 'M1', 'map_2d']
    
    def get_outputs(self) -> list[str]:
        return ['players', 'frame', 'map_2d', 'map_2d_text']
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        required = self.get_requirements()
        missing = [k for k in required if k not in data]
        if missing:
            return False, f"Missing keys: {missing}"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        """Player detection and team recognition"""
        self.execution_count += 1
        
        try:
            frame_out, map_out, map_text = self.feet_detector.get_players_pos(
                data['M'], data['M1'], data['frame'], 
                data['timestamp'], data['map_2d']
            )
            
            # Update data
            data['frame'] = frame_out
            data['map_2d'] = map_out
            data['map_2d_text'] = map_text
            
            # Sync players
            data['players'] = {}
            for player in self.feet_detector.players:
                if data['timestamp'] in player.positions:
                    data['players'][player.ID] = {
                        'id': player.ID,
                        'team': player.team,
                        'position_2d': player.positions[data['timestamp']],
                        'bbox': player.previous_bb,
                        'color': player.color
                    }
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class PlayerPositionTrackingModule(BaseModule):
    """2. Player 2D Position Tracking (part of IDRecognition)"""
    
    def __init__(self, **kwargs):
        super().__init__("player_position_tracking", **kwargs)
    
    def get_requirements(self) -> list[str]:
        return ['players']
    
    def get_outputs(self) -> list[str]:
        return []  # Already in players
    
    def process(self, data: Dict) -> Dict:
        """Positions already tracked by IDRecognition"""
        self.execution_count += 1
        self.success_count += 1
        return data


class BallTrackingModule(BaseModule):
    """3. Ball Tracking"""
    
    def __init__(self, **kwargs):
        super().__init__("ball_tracking", **kwargs)
        self.ball_detector = kwargs.get('ball_detector')
    
    def get_requirements(self) -> list[str]:
        return ['frame', 'M', 'M1', 'map_2d', 'map_2d_text', 'timestamp', 'players']
    
    def get_outputs(self) -> list[str]:
        return ['ball', 'players']  # Updates has_ball
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if 'players' not in data or len(data['players']) == 0:
            return False, "No players detected"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            frame_out, ball_map = self.ball_detector.ball_tracker(
                data['M'], data['M1'], data['frame'].copy(),
                data['map_2d'].copy(), data['map_2d_text'], data['timestamp']
            )
            
            data['frame'] = frame_out
            data['ball'] = {
                'detected': ball_map is not None,
                'owner_id': None
            }
            
            # Sync has_ball
            for player in self.ball_detector.players:
                if player.ID in data['players']:
                    data['players'][player.ID]['has_ball'] = player.has_ball
                    if player.has_ball:
                        data['ball']['owner_id'] = player.ID
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class PlayerDistanceModule(BaseModule):
    """4. Player Distance Analysis"""
    
    def __init__(self, **kwargs):
        super().__init__("player_distance", **kwargs)
        self.distance_analyzer = kwargs.get('distance_analyzer')
        self.player_list = kwargs.get('player_list')
    
    def get_requirements(self) -> list[str]:
        return ['players', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['players']  # Adds proximity info
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            for pid, pdata in data['players'].items():
                player_obj = self._find_player(pid)
                if not player_obj:
                    continue
                
                prox = self.distance_analyzer.get_proximity_info(
                    player_obj, self.player_list, data['timestamp']
                )
                
                if prox:
                    pdata['closest_teammate'] = prox.closest_teammate
                    pdata['closest_opponent'] = prox.closest_opponent
                    pdata['teammates_within_3m'] = prox.teammates_within_3m
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data
    
    def _find_player(self, pid):
        for p in self.player_list:
            if p.ID == pid:
                return p
        return None


class SpeedAccelerationModule(BaseModule):
    """5. Speed & Acceleration Analysis"""
    
    def __init__(self, **kwargs):
        super().__init__("speed_acceleration", **kwargs)
        self.velocity_analyzer = kwargs.get('velocity_analyzer')
        self.player_list = kwargs.get('player_list')
    
    def get_requirements(self) -> list[str]:
        return ['players', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['players']  # Adds speed, acceleration
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            for pid, pdata in data['players'].items():
                player_obj = self._find_player(pid)
                if not player_obj:
                    continue
                
                pdata['speed'] = self.velocity_analyzer.calculate_speed(
                    player_obj, data['timestamp']
                )
                pdata['acceleration'] = self.velocity_analyzer.calculate_acceleration(
                    player_obj, data['timestamp']
                )
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data
    
    def _find_player(self, pid):
        for p in self.player_list:
            if p.ID == pid:
                return p
        return None


class MovementClassifierModule(BaseModule):
    """6. Basic Movement Classifier"""
    
    def __init__(self, **kwargs):
        super().__init__("movement_classifier", **kwargs)
    
    def get_requirements(self) -> list[str]:
        return ['players']
    
    def get_outputs(self) -> list[str]:
        return ['players']  # Adds movement_state
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if not any('speed' in p for p in data.get('players', {}).values()):
            return False, "No speed data available"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            for pid, pdata in data['players'].items():
                speed = pdata.get('speed', 0.0)
                
                if speed < 1.0:
                    pdata['movement_state'] = "idle"
                elif speed < 3.0:
                    pdata['movement_state'] = "walking"
                elif speed < 6.0:
                    pdata['movement_state'] = "running"
                else:
                    pdata['movement_state'] = "sprinting"
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class ShotAttemptDetectorModule(BaseModule):
    """7. Shot Attempt Detector"""
    
    def __init__(self, **kwargs):
        super().__init__("shot_attempt_detector", **kwargs)
        self.detector = None
    
    def get_requirements(self) -> list[str]:
        return ['players', 'ball', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['events']
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if not any(p.get('movement_state') == 'jumping' for p in data.get('players', {}).values()):
            return False, "No jumping players"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            if self.detector is None:
                from Modules.ShotAttemp.detector import ShotAttemptDetector
                self.detector = ShotAttemptDetector()
            
            data.setdefault('events', [])
            
            for pid, pdata in data['players'].items():
                if not pdata.get('has_ball') or pdata.get('movement_state') != 'jumping':
                    continue
                
                # Detect shot
                # (simplified - real implementation would create FramePacket)
                data['events'].append({
                    'type': 'shot',
                    'player_id': pid,
                    'frame_id': data['frame_id'],
                    'confidence': 0.85
                })
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class DribbleDetectorModule(BaseModule):
    """8. Dribbling Detector"""
    
    def __init__(self, **kwargs):
        super().__init__("dribble_detector", **kwargs)
        self.detector = None
    
    def get_requirements(self) -> list[str]:
        return ['players', 'ball', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['events']
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if not any(p.get('has_ball') for p in data.get('players', {}).values()):
            return False, "No player has ball"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            if self.detector is None:
                from Modules.DriblingDetector.dribbling_detector import DribblingDetector
                self.detector = DribblingDetector(preset_name="default")
            
            data.setdefault('events', [])
            # Dribble detection logic here
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class SequenceParserModule(BaseModule):
    """9. Sequence Parser"""
    
    def __init__(self, **kwargs):
        super().__init__("sequence_parser", **kwargs)
        self.parser = None
    
    def get_requirements(self) -> list[str]:
        return ['events']
    
    def get_outputs(self) -> list[str]:
        return ['events']  # Adds sequence events
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if not data.get('events'):
            return False, "No events to parse"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            if self.parser is None:
                from Modules.SequenceParser.parser import SequenceParser
                self.parser = SequenceParser()
            
            # Parse sequences
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


class BallControlDurationModule(BaseModule):
    """10. Ball Control Duration"""
    
    def __init__(self, **kwargs):
        super().__init__("ball_control_duration", **kwargs)
        self.analyzer = None
    
    def get_requirements(self) -> list[str]:
        return ['ball', 'players', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['ball_control']
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        try:
            if self.analyzer is None:
                from Modules.BallControl.ball_control_analyzer import BallControlAnalyzer
                self.analyzer = BallControlAnalyzer()
            
            data['ball_control'] = {
                'carrier': data.get('ball', {}).get('owner_id'),
                'duration': 0  # Would track over time
            }
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
        
        return data


# =============================================================================
# MODULE REGISTRY
# =============================================================================

MODULE_REGISTRY: Dict[str, Type[BaseModule]] = {
    "id_recognition": IdRecognitionModule,
    "player_position_tracking": PlayerPositionTrackingModule, # Match2D, pek de bir şeyine gerek yok aslında. Zaten main.py'de çalışıyor.
    "ball_tracking": BallTrackingModule,
    "player_distance": PlayerDistanceModule,
    "speed_acceleration": SpeedAccelerationModule,
    "movement_classifier": MovementClassifierModule,
    "shot_attempt_detector": ShotAttemptDetectorModule,
    "dribble_detector": DribbleDetectorModule,
    "sequence_parser": SequenceParserModule,
    "ball_control_duration": BallControlDurationModule
}


def get_module(name: str, **kwargs) -> BaseModule:
    """
    Registry'den modül al.
    
    Args:
        name: Module key (e.g., 'ball_tracking')
        **kwargs: Module constructor arguments
    
    Returns:
        Initialized module instance
    
    Raises:
        KeyError: If module not in registry
    """
    if name not in MODULE_REGISTRY:
        raise KeyError(f"Module '{name}' not found in registry. "
                      f"Available: {list(MODULE_REGISTRY.keys())}")
    
    return MODULE_REGISTRY[name](**kwargs)


def list_modules() -> list[str]:
    """List all registered modules"""
    return list(MODULE_REGISTRY.keys())


# =============================================================================
# CONFIG SCHEMA
# =============================================================================

DEFAULT_CONFIG = {
    'pipeline': {
        'name': 'Basketball Analytics Pipeline',
        'version': '1.0.0'
    },
    'modules': [
        {'name': 'team_recognition', 'enabled': True},
        {'name': 'player_position_tracking', 'enabled': True},
        {'name': 'ball_tracking', 'enabled': True},
        {'name': 'player_distance', 'enabled': True},
        {'name': 'speed_acceleration', 'enabled': True},
        {'name': 'movement_classifier', 'enabled': True},
        {'name': 'shot_attempt_detector', 'enabled': True},
        {'name': 'dribble_detector', 'enabled': True},
        {'name': 'sequence_parser', 'enabled': True},
        {'name': 'ball_control_duration', 'enabled': True}
    ],
    'logging': {
        'verbose': False,
        'log_level': 'INFO'
    }
}


def load_config(path: str = 'pipeline_config.yaml') -> Dict:
    """Load pipeline configuration"""
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"⚠️  Config not found: {path}, using defaults")
        return DEFAULT_CONFIG


def save_default_config(path: str = 'pipeline_config.yaml'):
    """Save default config to file"""
    with open(path, 'w') as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
    print(f"✅ Default config saved to: {path}")


if __name__ == "__main__":
    print("🏀 Basketball Analytics - Module Registry")
    print("="*60)
    print(f"\nRegistered Modules ({len(MODULE_REGISTRY)}):")
    for i, name in enumerate(list_modules(), 1):
        print(f"  {i}. {name}")
    
    print("\n✅ Registry ready!")