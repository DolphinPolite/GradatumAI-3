import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
from scipy.spatial.distance import cdist
import networkx as nx

@dataclass
class PlayerPair:
    """İki oyuncu çifti için mesafe bilgisi"""
    player1_id: int
    player2_id: int
    distance: float
    timestamp: int
    player1_team: str
    player2_team: str
    same_team: bool

@dataclass
class ProximityInfo:
    """Bir oyuncunun yakınlık bilgileri"""
    player_id: int
    timestamp: int
    closest_teammate: Optional[int]
    closest_teammate_distance: Optional[float]
    closest_opponent: Optional[int]
    closest_opponent_distance: Optional[float]
    teammates_within_3m: List[int]
    opponents_within_3m: List[int]
    avg_teammate_distance: Optional[float]
    avg_opponent_distance: Optional[float]


class DistanceAnalyzer:
    """
    Oyuncular arası mesafe analizi modülü.
    Basketbol dijital ikiz için optimize edilmiş.
    """
    
    def __init__(self, 
                 pixel_to_meter: float = 0.1,
                 court_width_meters: float = 28.0,  # NBA: 28.65m
                 court_length_meters: float = 15.0,  # NBA: 15.24m
                 proximity_threshold: float = 3.0):   # Yakınlık eşiği (metre)
        """
        Args:
            pixel_to_meter: Piksel-metre dönüşüm oranı
            court_width_meters: Saha genişliği
            court_length_meters: Saha uzunluğu
            proximity_threshold: "Yakın" sayılacak maksimum mesafe
        """
        self.pixel_to_meter = pixel_to_meter
        self.court_width = court_width_meters
        self.court_length = court_length_meters
        self.proximity_threshold = proximity_threshold
        
        # Önbellekleme
        self._distance_cache = {}
        self._proximity_cache = {}
    
    def _pixels_to_meters(self, pixel_distance: float) -> float:
        """Piksel mesafesini metreye çevirir"""
        return pixel_distance * self.pixel_to_meter
    
    def calculate_pairwise_distance(self,
                                   player1,
                                   player2,
                                   timestamp: int) -> Optional[float]:
        """
        İki oyuncu arasındaki mesafeyi hesaplar.
        
        Returns:
            Mesafe (metre) veya None
        """
        # Cache key
        cache_key = (min(player1.ID, player2.ID), 
                    max(player1.ID, player2.ID), 
                    timestamp)
        
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]
        
        if (timestamp not in player1.positions or 
            timestamp not in player2.positions):
            return None
        
        pos1 = np.array(player1.positions[timestamp])
        pos2 = np.array(player2.positions[timestamp])
        
        pixel_distance = np.linalg.norm(pos1 - pos2)
        meter_distance = self._pixels_to_meters(pixel_distance)
        
        # Cache et
        self._distance_cache[cache_key] = meter_distance
        
        return meter_distance
    
    def get_all_pairwise_distances(self,
                                   players: List,
                                   timestamp: int,
                                   include_referees: bool = False) -> List[PlayerPair]:
        """
        Tüm oyuncu çiftleri arasındaki mesafeleri hesaplar.
        
        Args:
            players: Player objelerinin listesi
            timestamp: Hangi frame
            include_referees: Hakemleri dahil et mi?
        
        Returns:
            PlayerPair objelerinin listesi
        """
        distances = []
        
        # Aktif oyuncuları filtrele
        active_players = [p for p in players 
                         if timestamp in p.positions and 
                         (include_referees or p.team != 'referee')]
        
        # Tüm çiftleri hesapla
        for i in range(len(active_players)):
            for j in range(i + 1, len(active_players)):
                p1 = active_players[i]
                p2 = active_players[j]
                
                distance = self.calculate_pairwise_distance(p1, p2, timestamp)
                
                if distance is not None:
                    pair = PlayerPair(
                        player1_id=p1.ID,
                        player2_id=p2.ID,
                        distance=distance,
                        timestamp=timestamp,
                        player1_team=p1.team,
                        player2_team=p2.team,
                        same_team=(p1.team == p2.team)
                    )
                    distances.append(pair)
        
        return distances
    
    def get_proximity_info(self,
                          player,
                          all_players: List,
                          timestamp: int) -> Optional[ProximityInfo]:
        """
        Bir oyuncunun yakınlık bilgilerini döndürür.
        
        Returns:
            ProximityInfo objesi veya None
        """
        if timestamp not in player.positions:
            return None
        
        # Cache kontrolü
        cache_key = (player.ID, timestamp)
        if cache_key in self._proximity_cache:
            return self._proximity_cache[cache_key]
        
        # Diğer oyuncularla mesafeleri hesapla
        teammates_distances = []
        opponents_distances = []
        
        teammates_close = []
        opponents_close = []
        
        closest_teammate = (None, float('inf'))
        closest_opponent = (None, float('inf'))
        
        for other_player in all_players:
            if (other_player.ID == player.ID or 
                other_player.team == 'referee' or
                timestamp not in other_player.positions):
                continue
            
            distance = self.calculate_pairwise_distance(player, other_player, timestamp)
            
            if distance is None:
                continue
            
            # Aynı takım mı karşı takım mı?
            if other_player.team == player.team:
                teammates_distances.append(distance)
                
                if distance < closest_teammate[1]:
                    closest_teammate = (other_player.ID, distance)
                
                if distance <= self.proximity_threshold:
                    teammates_close.append(other_player.ID)
            else:
                opponents_distances.append(distance)
                
                if distance < closest_opponent[1]:
                    closest_opponent = (other_player.ID, distance)
                
                if distance <= self.proximity_threshold:
                    opponents_close.append(other_player.ID)
        
        # ProximityInfo oluştur
        info = ProximityInfo(
            player_id=player.ID,
            timestamp=timestamp,
            closest_teammate=closest_teammate[0],
            closest_teammate_distance=closest_teammate[1] if closest_teammate[0] else None,
            closest_opponent=closest_opponent[0],
            closest_opponent_distance=closest_opponent[1] if closest_opponent[0] else None,
            teammates_within_3m=teammates_close,
            opponents_within_3m=opponents_close,
            avg_teammate_distance=np.mean(teammates_distances) if teammates_distances else None,
            avg_opponent_distance=np.mean(opponents_distances) if opponents_distances else None
        )
        
        # Cache et
        self._proximity_cache[cache_key] = info
        
        return info
    
    def get_distance_matrix(self,
                           players: List,
                           timestamp: int) -> Tuple[np.ndarray, List[int]]:
        """
        Tüm oyuncular için mesafe matrisi oluşturur.
        
        Returns:
            (distance_matrix, player_ids) tuple
            - distance_matrix: NxN numpy array (N = oyuncu sayısı)
            - player_ids: Her satır/sütunun hangi oyuncuya karşılık geldiği
        """
        # Aktif oyuncuları filtrele
        active_players = [p for p in players 
                         if timestamp in p.positions and p.team != 'referee']
        
        if len(active_players) == 0:
            return np.array([]), []
        
        # Pozisyonları topla
        positions = np.array([p.positions[timestamp] for p in active_players])
        player_ids = [p.ID for p in active_players]
        
        # Euclidean distance matrix (piksel cinsinden)
        distance_matrix_pixels = cdist(positions, positions, metric='euclidean')
        
        # Metreye çevir
        distance_matrix_meters = distance_matrix_pixels * self.pixel_to_meter
        
        return distance_matrix_meters, player_ids
    
    def get_team_spacing(self,
                        players: List,
                        team: str,
                        timestamp: int) -> Optional[Dict[str, float]]:
        """
        Bir takımın spacing metriklerini hesaplar.
        
        Returns:
            Dict: {
                'avg_spacing': float,      # Ortalama takım arkadaşı mesafesi
                'min_spacing': float,      # En yakın iki oyuncu arası mesafe
                'max_spacing': float,      # En uzak iki oyuncu arası mesafe
                'std_spacing': float,      # Standart sapma
                'spread_x': float,         # X ekseninde yayılma
                'spread_y': float,         # Y ekseninde yayılma
                'centroid': tuple          # Takım merkezi (x, y)
            }
        """
        team_players = [p for p in players 
                       if p.team == team and timestamp in p.positions]
        
        if len(team_players) < 2:
            return None
        
        # Pozisyonları topla
        positions = np.array([p.positions[timestamp] for p in team_players])
        
        # Takım içi mesafeler
        team_distances = []
        for i in range(len(team_players)):
            for j in range(i + 1, len(team_players)):
                dist = self.calculate_pairwise_distance(
                    team_players[i], team_players[j], timestamp
                )
                if dist:
                    team_distances.append(dist)
        
        if not team_distances:
            return None
        
        # Metrikler
        positions_meters = positions * self.pixel_to_meter
        
        return {
            'avg_spacing': np.mean(team_distances),
            'min_spacing': np.min(team_distances),
            'max_spacing': np.max(team_distances),
            'std_spacing': np.std(team_distances),
            'spread_x': np.ptp(positions_meters[:, 0]),  # peak-to-peak
            'spread_y': np.ptp(positions_meters[:, 1]),
            'centroid': tuple(np.mean(positions_meters, axis=0))
        }
    
    def get_defensive_pressure(self,
                              offensive_player,
                              defensive_players: List,
                              timestamp: int) -> Optional[Dict[str, any]]:
        """
        Bir hücum oyuncusuna yapılan savunma baskısını ölçer.
        
        Returns:
            Dict: {
                'closest_defender': int,           # En yakın savunmacı ID
                'closest_defender_distance': float,# Mesafe
                'defenders_within_2m': list,       # 2m içindeki savunmacılar
                'pressure_score': float            # 0-1 arası baskı skoru
            }
        """
        if timestamp not in offensive_player.positions:
            return None
        
        defenders_info = []
        
        for defender in defensive_players:
            if timestamp not in defender.positions:
                continue
            
            distance = self.calculate_pairwise_distance(
                offensive_player, defender, timestamp
            )
            
            if distance:
                defenders_info.append((defender.ID, distance))
        
        if not defenders_info:
            return None
        
        # En yakın savunmacı
        defenders_info.sort(key=lambda x: x[1])
        closest = defenders_info[0]
        
        # 2m içindekiler
        within_2m = [d[0] for d in defenders_info if d[1] <= 2.0]
        
        # Pressure score (en yakın 3 savunmacıya göre)
        # Daha yakın = daha yüksek skor
        pressure_score = 0.0
        for i, (_, dist) in enumerate(defenders_info[:3]):
            weight = 1.0 / (i + 1)  # İlk savunmacı daha önemli
            pressure_score += weight * (1.0 - min(dist / 5.0, 1.0))
        
        pressure_score = min(pressure_score, 1.0)
        
        return {
            'closest_defender': closest[0],
            'closest_defender_distance': closest[1],
            'defenders_within_2m': within_2m,
            'pressure_score': pressure_score
        }
    
    def export_to_dataframe(self,
                           players: List,
                           start_timestamp: int,
                           end_timestamp: int) -> pd.DataFrame:
        """
        Belirtilen zaman aralığındaki tüm mesafe verilerini DataFrame'e çevirir.
        Dijital İkiz için ML input olarak kullanılabilir.
        
        Returns:
            DataFrame with columns:
            - timestamp, player1_id, player2_id, distance, same_team
        """
        data = []
        
        for timestamp in range(start_timestamp, end_timestamp + 1):
            pairs = self.get_all_pairwise_distances(players, timestamp)
            
            for pair in pairs:
                data.append({
                    'timestamp': pair.timestamp,
                    'player1_id': pair.player1_id,
                    'player2_id': pair.player2_id,
                    'distance': pair.distance,
                    'same_team': pair.same_team,
                    'player1_team': pair.player1_team,
                    'player2_team': pair.player2_team
                })
        
        return pd.DataFrame(data)
    
    def export_proximity_to_dataframe(self,
                                     players: List,
                                     start_timestamp: int,
                                     end_timestamp: int) -> pd.DataFrame:
        """
        Her oyuncunun proximity bilgilerini DataFrame'e çevirir.
        
        Returns:
            DataFrame with columns per player per timestamp
        """
        data = []
        
        for timestamp in range(start_timestamp, end_timestamp + 1):
            for player in players:
                if player.team == 'referee':
                    continue
                
                info = self.get_proximity_info(player, players, timestamp)
                
                if info:
                    data.append({
                        'timestamp': info.timestamp,
                        'player_id': info.player_id,
                        'closest_teammate': info.closest_teammate,
                        'closest_teammate_dist': info.closest_teammate_distance,
                        'closest_opponent': info.closest_opponent,
                        'closest_opponent_dist': info.closest_opponent_distance,
                        'teammates_within_3m_count': len(info.teammates_within_3m),
                        'opponents_within_3m_count': len(info.opponents_within_3m),
                        'avg_teammate_dist': info.avg_teammate_distance,
                        'avg_opponent_dist': info.avg_opponent_distance
                    })
        
        return pd.DataFrame(data)
    
    def clear_cache(self):
        """Cache'i temizle (memory management için)"""
        self._distance_cache.clear()
        self._proximity_cache.clear()