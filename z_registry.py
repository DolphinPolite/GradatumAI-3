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
            
            # ÖNCE HERKESIN has_ball'ını False yap
            for pid in data['players']:
                data['players'][pid]['has_ball'] = False
            
            # SONRA gerçek sahipleri işaretle
            for player in self.ball_detector.players:
                if player.ID in data['players']:
                    has_ball_value = getattr(player, 'has_ball', False)
                    data['players'][player.ID]['has_ball'] = has_ball_value
                    
                    if has_ball_value:
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
        self.previous_states = {}
    
    def get_requirements(self) -> list[str]:
        return ['players', 'timestamp']
    
    def get_outputs(self) -> list[str]:
        return ['players']  # Adds speed, acceleration
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        players_data = data.get('players', {})
        current_time = data.get('timestamp')
        
        # Eğer timestamp yoksa işlem yapamayız
        if current_time is None:
            return data

        try:
            for pid, pdata in players_data.items():
                # Varsayılan değerler
                pdata['speed'] = 0.0
                pdata['acceleration'] = 0.0
                
                current_pos = pdata.get('position_2d')
                
                # Geçmiş verisi var mı kontrol et
                if pid in self.previous_states:
                    prev_state = self.previous_states[pid]
                    prev_pos = prev_state['pos']
                    prev_time = prev_state['time']
                    prev_speed = prev_state['speed']
                    
                    time_diff = current_time - prev_time
                    
                    # Zaman farkı 0 veya çok küçükse (ör: aynı kare) hesaplama yapma
                    if time_diff > 0.001 and current_pos and prev_pos:
                        # 1. Hız Hesapla (Distance / Time)
                        # Pixel cinsinden mesafe (gerçek dünya için ölçek katsayısı eklenebilir)
                        dist = math.sqrt((current_pos[0] - prev_pos[0])**2 + (current_pos[1] - prev_pos[1])**2)
                        current_speed = dist / time_diff
                        
                        # 2. İvme Hesapla ((V_son - V_ilk) / Time)
                        acceleration = (current_speed - prev_speed) / time_diff
                        
                        # Veriye yaz (Basit filtreleme: çok uçuk değerleri silebilirsiniz)
                        pdata['speed'] = round(current_speed, 2)
                        pdata['acceleration'] = round(acceleration, 2)
                        
                        # State güncelle (Bir sonraki karede kullanmak için ivme hesabında hıza ihtiyaç var)
                        self.previous_states[pid] = {
                            'pos': current_pos,
                            'time': current_time,
                            'speed': current_speed
                        }
                    else:
                        # Zaman farkı yoksa sadece pozisyonu güncelle
                        self.previous_states[pid]['pos'] = current_pos
                        self.previous_states[pid]['time'] = current_time
                        
                else:
                    # İlk kez görülen oyuncu için kayıt oluştur
                    if current_pos:
                        self.previous_states[pid] = {
                            'pos': current_pos,
                            'time': current_time,
                            'speed': 0.0
                        }

            self.success_count += 1
            
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name, 
                'message': f"Speed calc error: {str(e)}"
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
        self.history = {}
        self.last_states = {}
    
    def get_requirements(self) -> list[str]:
        return ['players']
    
    def get_outputs(self) -> list[str]:
        # Artık 'events' listesine de katkıda bulunuyor
        return ['players', 'events']  # Adds movement_state
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        if not any('speed' in p for p in data.get('players', {}).values()):
            return False, "No speed data available"
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        
        # Events listesini döngüden ÖNCE oluşturuyoruz
        data.setdefault('events', [])
        
        players = data.get('players', {})
        if not players:
            return data

        # DÖNGÜ BAŞLANGICI
        for pid, pdata in players.items():
            try:
                # --- 1. State Belirleme ---
                speed = pdata.get('speed', 0.0)
                accel = pdata.get('acceleration', 0.0)
    
                if abs(accel) > 500.0 and 30.0 < speed < 100.0:
                    state = "jumping"
                elif speed > 150.0:
                    state = "sprinting"
                elif speed > 60.0:
                    state = "running"
                elif speed > 10.0:
                    state = "walking"
                else:
                    state = "idle"
                    
                pdata['movement_state'] = state
                
                # --- 2. Event Üretme (State Change) ---
                prev_state = self.last_states.get(pid)
                
                if prev_state and prev_state != state:
                    event = {
                        'type': 'movement_change',
                        'player_id': pid,
                        'frame_id': data.get('frame_id', 0),
                        'details': {
                            'from': prev_state,
                            'to': state,
                            'speed': speed
                        }
                    }
                    data['events'].append(event)
                
                # --- 3. Geçmişi Kaydetme ---
                self.last_states[pid] = state
                
                if pid not in self.history: self.history[pid] = []
                self.history[pid].append(state)
                if len(self.history[pid]) > 10: self.history[pid].pop(0)
                
                pdata['history_summary'] = self.history[pid]
            except Exception as e:
                self.failure_count += 1
                data.setdefault('warnings', []).append({
                    'module': self.name,
                    'message': str(e)
                })
        
        self.success_count += 1
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
    """8. Dribbling Detector - Fixed Version"""
    
    def __init__(self, **kwargs):
        super().__init__("dribble_detector", **kwargs)
        self.detector = None
        self.last_frame_id = -1
    
    def get_requirements(self) -> list[str]:
        return ['players', 'ball', 'timestamp', 'frame_id']
    
    def get_outputs(self) -> list[str]:
        return ['events']
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        """
        Validation: We need players and ball data.
        Ball doesn't need to have an owner - we detect when ownership exists.
        """
        if 'players' not in data or len(data['players']) == 0:
            return False, "No players detected"
        
        if 'ball' not in data:
            return False, "No ball data"
        
        # Don't require has_ball - we'll check each player
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        """
        Process frame for dribble detection.
        
        Creates FramePacket for each player with ball and feeds to detector.
        Emits dribble_start and dribble_end events.
        """
        self.execution_count += 1
        
        try:
            # Lazy initialization
            if self.detector is None:
                from Modules.DriblingDetector.dribbling_detector import DribblingDetector
                self.detector = DribblingDetector(preset_name="default")
            
            # Ensure events list exists
            data.setdefault('events', [])
            
            frame_id = data.get('frame_id', 0)
            timestamp = data.get('timestamp', 0.0)
            players = data.get('players', {})
            ball_data = data.get('ball', {})
            
            # Process each player who has the ball
            for pid, pdata in players.items():
                has_ball = pdata.get('has_ball', False)
                
                if not has_ball:
                    continue
                
                # Build FramePacket
                packet = self._build_frame_packet(
                    player_id=pid,
                    player_data=pdata,
                    ball_data=ball_data,
                    frame_id=frame_id,
                    timestamp=timestamp
                )
                
                # Process with detector
                dribble_events = self.detector.process_frame(packet)
                
                # Convert DribbleEvent objects to pipeline events
                for dribble_event in dribble_events:
                    self._add_dribble_events(data, dribble_event, pdata)
            
            self.success_count += 1
            
        except Exception as e:
            self.failure_count += 1
            import traceback
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': f"{str(e)} | {traceback.format_exc()}"
            })
        
        return data
    
    def _build_frame_packet(self, player_id: int, player_data: dict, 
                           ball_data: dict, frame_id: int, timestamp: float):
        """
        Build FramePacket from pipeline data.
        
        FramePacket requires:
        - frame_id
        - timestamp
        - player_id
        - player_pos (x, y)
        - ball_pos (x, y)
        - has_ball (bool)
        - distance_matrix (optional)
        """
        from Modules.DriblingDetector.utils import FramePacket
        
        player_pos = player_data.get('position_2d', (0, 0))
        ball_pos = ball_data.get('position', player_pos)  # Default to player pos if no ball pos
        
        # Get closest opponent distance if available
        closest_opponent_dist = player_data.get('min_distance', 999.0)
        
        packet = FramePacket(
            frame_id=frame_id,
            timestamp=timestamp,
            player_id=player_id,
            player_pos=player_pos,
            ball_pos=ball_pos,
            has_ball=True,  # We only create packets for ball carriers
            closest_opponent_distance=closest_opponent_dist
        )
        
        return packet
    
    def _add_dribble_events(self, data: dict, dribble_event, player_data: dict):
        """
        Convert DribbleEvent to pipeline events.
        
        Creates two events:
        1. dribble_start - when dribble sequence begins
        2. dribble_end - when dribble sequence completes
        """
        # Determine dribble type based on player movement
        movement_state = player_data.get('movement_state', 'unknown')
        speed = player_data.get('speed', 0.0)
        
        if speed > 150.0 or movement_state == 'sprinting':
            dribble_type = 'speed_dribble'
        elif speed > 60.0 or movement_state == 'running':
            dribble_type = 'control_dribble'
        else:
            dribble_type = 'stationary_dribble'
        
        # START event
        data['events'].append({
            'type': 'dribble_start',
            'player_id': dribble_event.player_id,
            'frame_id': dribble_event.start_frame,
            'details': {
                'dribble_type': dribble_type,
                'confidence': dribble_event.confidence,
                'reasoning': dribble_event.reasoning
            }
        })
        
        # END event
        duration_frames = dribble_event.end_frame - dribble_event.start_frame
        
        data['events'].append({
            'type': 'dribble_end',
            'player_id': dribble_event.player_id,
            'frame_id': dribble_event.end_frame,
            'details': {
                'duration_frames': duration_frames,
                'bounce_count': dribble_event.bounce_count,
                'avg_interval': dribble_event.avg_interval_frames,
                'confidence': dribble_event.confidence
            }
        })


class SequenceParserModule(BaseModule):
    """9. Sequence Parser"""
    
    def __init__(self, **kwargs):
        super().__init__("sequence_parser", **kwargs)
        self.parser = None
    
    def get_requirements(self) -> list[str]:
        return ['events']
    
    def get_outputs(self) -> list[str]:
        return ['events', 'sequence_output']  # sequence_output artık garanti
    
    def validate_input(self, data: Dict) -> tuple[bool, str]:
        # Events listesi yoksa bile çalışsın (boş sequence üretelim)
        return True, ""
    
    def process(self, data: Dict) -> Dict:
        self.execution_count += 1
        events = data.get('events', [])
        
        try:
            # ✅ sequence_output'u MUTLAKA oluştur (boş bile olsa)
            current_sequence_summary = []
            
            # Eğer hiç olay yoksa boş string dön
            if not events:
                data['sequence_output'] = ""
                self.success_count += 1
                return data

            # Olayları işle
            for event in events:
                etype = event.get('type')
                pid = event.get('player_id')
                
                if etype == 'movement_change':
                    details = event.get('details', {})
                    msg = f"P{pid} {details.get('from')}->{details.get('to')}"
                    current_sequence_summary.append(msg)
                    
                elif etype == 'shot':
                    msg = f"!!! SHOT ATTEMPT by P{pid} !!!"
                    current_sequence_summary.append(msg)
                    
                elif etype == 'dribble':
                    msg = f"P{pid} is dribbling"
                    current_sequence_summary.append(msg)

            # ✅ Her durumda sequence_output oluştur
            data['sequence_output'] = " | ".join(current_sequence_summary) if current_sequence_summary else "No events"
            
            self.success_count += 1
            
        except Exception as e:
            self.failure_count += 1
            data.setdefault('warnings', []).append({
                'module': self.name,
                'message': str(e)
            })
            # ✅ Hata durumunda bile sequence_output ekle
            data['sequence_output'] = f"ERROR: {str(e)}"
        
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
