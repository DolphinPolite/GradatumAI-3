import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d
from typing import Dict, List, Optional, Tuple

class VelocityAnalyzer:
    """
    Player pozisyonlarından hız ve ivme hesaplayan modül.
    FeetDetector'dan bağımsız çalışır.
    """
    
    def __init__(self, 
                 fps: int = 30,
                 field_width_meters: float = 105.0,
                 field_height_meters: float = 68.0,
                 map_width_pixels: int = 1050,
                 map_height_pixels: int = 680,
                 max_speed_mps: float = 12.0,
                 min_frames_for_calc: int = 3):
        """
        Args:
            fps: Video frame rate
            field_width_meters: Gerçek saha genişliği (metre)
            field_height_meters: Gerçek saha yüksekliği (metre)
            map_width_pixels: 2D map genişliği (piksel)
            map_height_pixels: 2D map yüksekliği (piksel)
            max_speed_mps: Maksimum fiziksel hız (m/s) - outlier filtreleme için
            min_frames_for_calc: Hız hesabı için minimum frame sayısı
        """
        self.fps = fps
        self.time_delta = 1.0 / fps
        
        # Piksel-metre dönüşümü
        self.pixel_to_meter_x = field_width_meters / map_width_pixels
        self.pixel_to_meter_y = field_height_meters / map_height_pixels
        self.pixel_to_meter = (self.pixel_to_meter_x + self.pixel_to_meter_y) / 2
        
        self.max_speed = max_speed_mps
        self.min_frames = min_frames_for_calc
    
    def _pixels_to_meters(self, pixel_displacement: float) -> float:
        """Piksel cinsinden mesafeyi metreye çevirir"""
        return pixel_displacement * self.pixel_to_meter
    
    def calculate_speed(self, 
                       player, 
                       timestamp: int, 
                       window: int = 1) -> Optional[float]:
        """
        Oyuncunun anlık hızını hesaplar.
        
        Args:
            player: Player objesi (positions dict'i olan)
            timestamp: Hesaplama yapılacak frame
            window: Kaç frame geriye bakılacak (smoothing için)
        
        Returns:
            Hız (m/s) veya None
        """
        if not hasattr(player, 'positions') or len(player.positions) < self.min_frames:
            return None
        
        speeds = []
        for i in range(window):
            t_current = timestamp - i
            t_previous = t_current - 1
            
            if t_current in player.positions and t_previous in player.positions:
                pos_current = np.array(player.positions[t_current])
                pos_previous = np.array(player.positions[t_previous])
                
                # Piksel cinsinden yer değiştirme
                displacement_pixels = np.linalg.norm(pos_current - pos_previous)
                
                # Metre cinsine çevir
                displacement_meters = self._pixels_to_meters(displacement_pixels)
                
                # Hız (m/s)
                speed = displacement_meters / self.time_delta
                
                # Outlier filtresi
                if speed <= self.max_speed:
                    speeds.append(speed)
        
        return np.mean(speeds) if len(speeds) > 0 else None
    
    def calculate_speed_smoothed(self, 
                                 player, 
                                 timestamp: int,
                                 window: int = 5) -> Optional[float]:
        """
        Smoothing uygulanmış hız hesabı (daha robust).
        
        Args:
            window: Smoothing pencere boyutu (tek sayı olmalı)
        """
        # Önce pozisyonları smooth et, sonra hız hesapla
        timestamps = sorted([t for t in player.positions.keys() 
                           if t <= timestamp and t >= timestamp - window])
        
        if len(timestamps) < self.min_frames:
            return None
        
        positions = np.array([player.positions[t] for t in timestamps])
        
        # Savitzky-Golay filter (eğer yeterli veri varsa)
        if len(timestamps) >= 5:
            try:
                positions_smooth = savgol_filter(positions, 
                                                window_length=min(5, len(timestamps)),
                                                polyorder=2, 
                                                axis=0)
                
                # Son iki pozisyon arasındaki hızı hesapla
                displacement_pixels = np.linalg.norm(positions_smooth[-1] - positions_smooth[-2])
                displacement_meters = self._pixels_to_meters(displacement_pixels)
                speed = displacement_meters / self.time_delta
                
                return speed if speed <= self.max_speed else None
            except:
                # Smoothing başarısızsa basit hesaplamaya dön
                return self.calculate_speed(player, timestamp, window=3)
        else:
            return self.calculate_speed(player, timestamp, window=min(3, len(timestamps)))
    
    def calculate_acceleration(self, 
                              player, 
                              timestamp: int,
                              window: int = 3) -> Optional[float]:
        """
        Oyuncunun ivmesini hesaplar.
        
        Args:
            window: Hız değişimini hesaplamak için geriye bakılacak frame sayısı
        
        Returns:
            İvme (m/s²) veya None
        """
        speed_current = self.calculate_speed_smoothed(player, timestamp, window)
        speed_previous = self.calculate_speed_smoothed(player, timestamp - 1, window)
        
        if speed_current is not None and speed_previous is not None:
            acceleration = (speed_current - speed_previous) / self.time_delta
            
            # Fiziksel ivme limiti (örn: ±5 m/s² sprint ivmesi)
            if abs(acceleration) <= 5.0:
                return acceleration
        
        return None
    
    def calculate_distance_traveled(self, 
                                   player, 
                                   start_timestamp: int, 
                                   end_timestamp: int) -> Optional[float]:
        """
        Belirtilen zaman aralığında oyuncunun kat ettiği toplam mesafeyi hesaplar.
        
        Returns:
            Toplam mesafe (metre) veya None
        """
        timestamps = sorted([t for t in player.positions.keys() 
                           if start_timestamp <= t <= end_timestamp])
        
        if len(timestamps) < 2:
            return None
        
        total_distance = 0.0
        for i in range(1, len(timestamps)):
            pos_current = np.array(player.positions[timestamps[i]])
            pos_previous = np.array(player.positions[timestamps[i-1]])
            
            displacement_pixels = np.linalg.norm(pos_current - pos_previous)
            displacement_meters = self._pixels_to_meters(displacement_pixels)
            
            total_distance += displacement_meters
        
        return total_distance
    
    def get_speed_profile(self, 
                         player, 
                         start_timestamp: int, 
                         end_timestamp: int,
                         smooth: bool = True) -> Tuple[List[int], List[float]]:
        """
        Zaman aralığı boyunca hız profilini döndürür.
        
        Returns:
            (timestamps, speeds) tuple
        """
        timestamps = sorted([t for t in player.positions.keys() 
                           if start_timestamp <= t <= end_timestamp])
        
        speeds = []
        valid_timestamps = []
        
        for t in timestamps:
            if smooth:
                speed = self.calculate_speed_smoothed(player, t)
            else:
                speed = self.calculate_speed(player, t)
            
            if speed is not None:
                speeds.append(speed)
                valid_timestamps.append(t)
        
        return valid_timestamps, speeds
    
    def calculate_player_distance(self,
                                 player1,
                                 player2,
                                 timestamp: int) -> Optional[float]:
        """
        İki oyuncu arasındaki mesafeyi hesaplar.
        
        Returns:
            Mesafe (metre) veya None
        """
        if (timestamp not in player1.positions or 
            timestamp not in player2.positions):
            return None
        
        pos1 = np.array(player1.positions[timestamp])
        pos2 = np.array(player2.positions[timestamp])
        
        pixel_distance = np.linalg.norm(pos1 - pos2)
        return self._pixels_to_meters(pixel_distance)
    
    def get_max_speed(self, 
                     player, 
                     start_timestamp: int, 
                     end_timestamp: int) -> Optional[float]:
        """Belirtilen zaman aralığındaki maksimum hızı döndürür"""
        _, speeds = self.get_speed_profile(player, start_timestamp, end_timestamp)
        return max(speeds) if len(speeds) > 0 else None
    
    def get_average_speed(self, 
                         player, 
                         start_timestamp: int, 
                         end_timestamp: int) -> Optional[float]:
        """Belirtilen zaman aralığındaki ortalama hızı döndürür"""
        _, speeds = self.get_speed_profile(player, start_timestamp, end_timestamp)
        return np.mean(speeds) if len(speeds) > 0 else None