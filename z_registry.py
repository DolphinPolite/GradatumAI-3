"""
Basketball Analytics - Module Registry
Merkezi modül kayıt sistemi - TÜM modüller burada tanımlı
"""

from typing import Dict, Type, Any
from dataclasses import dataclass
import yaml
import math
import sys

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
                    # has_ball bilgisini mutlaka data['players'] içine yaz
                    data['players'][player.ID]['has_ball'] = getattr(player, 'has_ball', False)
                    if data['players'][player.ID]['has_ball']:
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
        return ['players', 'distance_matrix']  # Adds proximity info
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        players = data.get('players', {})
        pids = list(players.keys())
        
        # 1. Mesafe Matrisi Oluştur
        dist_matrix = {}
        
        try:
            for i in range(len(pids)):
                id1 = pids[i]
                pos1 = players[id1].get('position_2d')
                
                if id1 not in dist_matrix:
                    dist_matrix[id1] = {}
                
                for j in range(len(pids)):
                    id2 = pids[j]
                    if id1 == id2:
                        dist_matrix[id1][id2] = 0.0
                        continue
                        
                    pos2 = players[id2].get('position_2d')
                    
                    if pos1 and pos2:
                        # Öklid Mesafesi: sqrt((x2-x1)^2 + (y2-y1)^2)
                        dist = math.sqrt((pos2[0]-pos1[0])**2 + (pos2[1]-pos1[1])**2)
                        dist_matrix[id1][id2] = round(dist, 2)
            
            # 2. Veriyi 'data' içine enjekte et
            data['distance_matrix'] = dist_matrix
            
            # 3. Opsiyonel: Her oyuncunun içine 'closest_opponent' bilgisini hala yazalım
            # (Dribble detector gibi modüller buna ihtiyaç duyabilir)
            for pid in pids:
                distances = dist_matrix[pid]
                # Kendisi hariç en küçük mesafeyi bul
                other_distances = {k: v for k, v in distances.items() if k != pid}
                if other_distances:
                    closest_id = min(other_distances, key=other_distances.get)
                    players[pid]['closest_player_id'] = closest_id
                    players[pid]['min_distance'] = other_distances[closest_id]

            self.success_count += 1
            
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({'module': self.name, 'message': str(e)})
            
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
        players_data = data.get('players', {})
        ts = data.get('timestamp')
        
        if not players_data:
            data['speed_debug'] = "OYUNCU BULUNAMADI"
            return data

        try:
            # Sadece tek oyuncu değil, data içindeki TÜM oyuncuları dönüyoruz
            for pid, pdata in players_data.items():
                player_obj = self._find_player(pid)

                pdata['speed'] = 0.0
                pdata['acceleration'] = 0.0
                
                print(f"DEBUG: Player {pid} positions history: {player_obj.positions[-2:]}")

                if player_obj:
                    pos_count = len(getattr(player_obj, 'positions', []))
                    sys.debug_notes.append(f"P{pid}:{pos_count}pos")

                    speed = self.velocity_analyzer.calculate_speed(player_obj, ts)
                    accel = self.velocity_analyzer.calculate_acceleration(player_obj, ts)
                    
                    if speed is not None:
                        pdata['speed'] = round(float(speed), 2)
                    if accel is not None:
                        pdata['acceleration'] = round(float(accel), 2)

                    data['speed_debug'] = " | ".join(sys.debug_notes)

            
            print(f"\n>>> DEBUG HIZ: {data['speed_debug']}", file=sys.stderr)
            sys.stderr.flush()
            
            self.success_count += 1
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name, 
                'message': f"Hız hesaplama hatası: {str(e)}"
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
            for pid, pdata in data.get('players', {}).items():
                speed = pdata.get('speed', 0.0)
    
                if speed > 6.0:
                    state = "sprinting"
                elif speed > 3.0:
                    state = "running"
                elif speed > 0.5:
                    state = "walking"
                else:
                    state = "idle"
                    
                pdata['movement_state'] = state
                
                # 2. History Güncelle (Pattern için)
                if pid not in self.history: self.history[pid] = []
                self.history[pid].append(state)
                if len(self.history[pid]) > 10: self.history[pid].pop(0)
                
                # 3. Pattern Analizi (Örn: Hızlı duruş, ivmelenme)
                pdata['movement_state'] = state
                pdata['history_summary'] = self.history[pid]
            
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
