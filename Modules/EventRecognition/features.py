"""
Basketball Movement Feature Extraction

Bu modül VelocityAnalyzer çıktılarını ve bbox verilerini alarak
hareket sınıflandırması için gerekli feature'ları üretir.

VelocityAnalyzer ile entegre çalışır - wheel reinvent etmez.
Yeni ekledikleri:
- Bbox height analysis (jump detection için)
- Rolling statistics (stability metrics)
- Feature normalization ve outlier filtering

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, asdict


@dataclass
class MovementFeatures:
    """
    Bir frame için çıkarılan hareket özellikleri.
    
    Bu dataclass ML-friendly'dir - tüm feature'lar tek bir objede.
    
    Attributes:
        timestamp: Frame index
        
        # SPEED FEATURES (VelocityAnalyzer'dan)
        speed: Anlık hız (m/s)
        speed_smoothed: Smoothed hız (m/s)
        acceleration: İvme (m/s²)
        
        # BBOX FEATURES (yeni)
        bbox_height: Mevcut bbox yüksekliği (piksel)
        bbox_height_change: Bbox yükseklik değişimi oranı (-1 to 1)
        bbox_height_change_rate: Değişim hızı (per frame)
        bbox_height_stable: Bbox stabilitesi (bool)
        
        # ROLLING STATISTICS
        speed_std: Son N frame'deki hız std sapması
        speed_max_recent: Son N frame'deki max hız
        speed_mean_recent: Son N frame'deki ortalama hız
        
        # STABILITY METRICS
        is_speed_stable: Hız istikrarlı mı (bool)
        is_accelerating: İvmelenme var mı (bool)
        is_decelerating: Yavaşlama var mı (bool)
        
        # DATA QUALITY
        data_quality_score: Verinin güvenilirliği (0-1)
        has_outlier: Outlier tespit edildi mi (bool)
        missing_data_ratio: Eksik veri oranı (0-1)
    """
    
    timestamp: int
    
    # Speed features
    speed: Optional[float] = None
    speed_smoothed: Optional[float] = None
    acceleration: Optional[float] = None
    
    # Bbox features
    bbox_height: Optional[float] = None
    bbox_height_change: Optional[float] = None
    bbox_height_change_rate: Optional[float] = None
    bbox_height_stable: bool = False
    
    # Rolling statistics
    speed_std: Optional[float] = None
    speed_max_recent: Optional[float] = None
    speed_mean_recent: Optional[float] = None
    
    # Stability metrics
    is_speed_stable: bool = False
    is_accelerating: bool = False
    is_decelerating: bool = False
    
    # Data quality
    data_quality_score: float = 0.0
    has_outlier: bool = False
    missing_data_ratio: float = 0.0
    
    def to_dict(self) -> Dict:
        """ML logging için dictionary export"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """Feature'ların güvenilir olup olmadığını kontrol eder"""
        return (
            self.data_quality_score >= 0.5 and
            not self.has_outlier and
            self.missing_data_ratio < 0.3
        )


class MovementFeatureExtractor:
    """
    VelocityAnalyzer ve bbox verilerinden movement classification
    için özellik çıkarır.
    
    VelocityAnalyzer ile entegre çalışır - onun metodlarını kullanır.
    
    Design Principles:
    - VelocityAnalyzer'ı wrap eder, tekrar hesaplama yapmaz
    - Bbox height analysis ekler (VelocityAnalyzer'da yok)
    - Rolling statistics ekler (temporal window)
    - Feature quality control yapar
    
    Attributes:
        velocity_analyzer: Mevcut VelocityAnalyzer instance
        window_size: Rolling statistics için pencere boyutu
        bbox_stability_threshold: Bbox'ın stabil sayılması için eşik
        speed_stability_threshold: Hız'ın stabil sayılması için eşik
    """
    
    def __init__(self,
                 velocity_analyzer,
                 window_size: int = 7,
                 bbox_stability_threshold: float = 0.05,
                 speed_stability_threshold: float = 0.3):
        """
        Args:
            velocity_analyzer: VelocityAnalyzer instance
            window_size: Rolling statistics pencere boyutu (tek sayı olmalı)
            bbox_stability_threshold: Bbox değişim eşiği (0-1 ratio)
            speed_stability_threshold: Hız std eşiği (m/s)
        """
        self.velocity_analyzer = velocity_analyzer
        self.window_size = window_size
        self.bbox_stability_threshold = bbox_stability_threshold
        self.speed_stability_threshold = speed_stability_threshold
        
        # Bbox history buffer (her player için ayrı)
        self._bbox_history: Dict[int, deque] = {}
        
        # Speed history buffer (her player için ayrı)
        self._speed_history: Dict[int, deque] = {}
    
    def _init_player_buffers(self, player_id: int):
        """Player için buffer'ları initialize eder"""
        if player_id not in self._bbox_history:
            self._bbox_history[player_id] = deque(maxlen=self.window_size)
        if player_id not in self._speed_history:
            self._speed_history[player_id] = deque(maxlen=self.window_size)
    
    def extract_features(self,
                        player,
                        timestamp: int,
                        bbox_height: float,
                        player_id: Optional[int] = None) -> MovementFeatures:
        """
        Bir frame için tüm özellikleri çıkarır.
        
        Args:
            player: Player objesi (VelocityAnalyzer uyumlu - positions dict)
            timestamp: Frame index
            bbox_height: Oyuncunun bbox yüksekliği (piksel)
            player_id: Player ID (buffer tracking için)
            
        Returns:
            MovementFeatures dataclass instance
            
        Example:
            >>> extractor = MovementFeatureExtractor(velocity_analyzer)
            >>> features = extractor.extract_features(
            ...     player=player_obj,
            ...     timestamp=150,
            ...     bbox_height=320.5,
            ...     player_id=7
            ... )
            >>> print(f"Speed: {features.speed:.2f} m/s")
            >>> print(f"Jumping: {features.bbox_height_change < -0.12}")
        """
        # Player ID fallback
        if player_id is None:
            player_id = getattr(player, 'id', 0)
        
        # Initialize buffers
        self._init_player_buffers(player_id)
        
        # Feature extraction
        features = MovementFeatures(timestamp=timestamp)
        
        # 1. SPEED FEATURES (VelocityAnalyzer'dan)
        features.speed = self._extract_speed(player, timestamp)
        features.speed_smoothed = self._extract_speed_smoothed(player, timestamp)
        features.acceleration = self._extract_acceleration(player, timestamp)
        
        # 2. BBOX FEATURES (yeni)
        features.bbox_height = bbox_height
        features.bbox_height_change = self._calculate_bbox_change(
            player_id, bbox_height
        )
        features.bbox_height_change_rate = self._calculate_bbox_change_rate(
            player_id
        )
        features.bbox_height_stable = self._is_bbox_stable(player_id)
        
        # 3. ROLLING STATISTICS
        if features.speed is not None:
            self._speed_history[player_id].append(features.speed)
        
        features.speed_std = self._calculate_speed_std(player_id)
        features.speed_max_recent = self._calculate_speed_max(player_id)
        features.speed_mean_recent = self._calculate_speed_mean(player_id)
        
        # 4. STABILITY METRICS
        features.is_speed_stable = self._check_speed_stability(player_id)
        features.is_accelerating = (
            features.acceleration > 0.5 if features.acceleration else False
        )
        features.is_decelerating = (
            features.acceleration < -0.5 if features.acceleration else False
        )
        
        # 5. DATA QUALITY
        features.data_quality_score = self._calculate_data_quality(
            player, timestamp, features
        )
        features.has_outlier = self._detect_outlier(features)
        features.missing_data_ratio = self._calculate_missing_ratio(
            player, timestamp
        )
        
        return features
    
    def _extract_speed(self, player, timestamp: int) -> Optional[float]:
        """
        VelocityAnalyzer'dan anlık hızı alır.
        
        VelocityAnalyzer'ın calculate_speed metodunu kullanır.
        """
        try:
            return self.velocity_analyzer.calculate_speed(
                player, timestamp, window=1
            )
        except Exception as e:
            return None
    
    def _extract_speed_smoothed(self, player, timestamp: int) -> Optional[float]:
        """
        VelocityAnalyzer'dan smoothed hızı alır.
        
        VelocityAnalyzer'ın calculate_speed_smoothed metodunu kullanır.
        """
        try:
            return self.velocity_analyzer.calculate_speed_smoothed(
                player, timestamp, window=5
            )
        except Exception as e:
            return None
    
    def _extract_acceleration(self, player, timestamp: int) -> Optional[float]:
        """
        VelocityAnalyzer'dan ivmeyi alır.
        
        VelocityAnalyzer'ın calculate_acceleration metodunu kullanır.
        """
        try:
            return self.velocity_analyzer.calculate_acceleration(
                player, timestamp, window=3
            )
        except Exception as e:
            return None
    
    def _calculate_bbox_change(self, 
                               player_id: int, 
                               current_height: float) -> Optional[float]:
        """
        Bbox height değişimini hesaplar (jump detection için kritik).
        
        Returns:
            Değişim oranı (-1 to 1)
            Negatif = küçülme (jumping up)
            Pozitif = büyüme (landing)
            
        Example:
            Oyuncu 200px → 176px
            change = (176 - 200) / 200 = -0.12 (-%12 küçülme)
        """
        bbox_history = self._bbox_history[player_id]
        
        if len(bbox_history) == 0:
            bbox_history.append(current_height)
            return 0.0
        
        previous_height = bbox_history[-1]
        
        # Outlier protection
        if previous_height <= 0 or current_height <= 0:
            return None
        
        # Change ratio
        change = (current_height - previous_height) / previous_height
        
        # Update history
        bbox_history.append(current_height)
        
        return change
    
    def _calculate_bbox_change_rate(self, player_id: int) -> Optional[float]:
        """
        Bbox değişim hızını hesaplar (per frame).
        
        Returns:
            Değişim hızı (örn: -0.04 / frame)
        """
        bbox_history = self._bbox_history[player_id]
        
        if len(bbox_history) < 3:
            return 0.0
        
        # Son 3 frame'deki değişimi hesapla
        recent = list(bbox_history)[-3:]
        changes = []
        
        for i in range(1, len(recent)):
            if recent[i-1] > 0:
                change = (recent[i] - recent[i-1]) / recent[i-1]
                changes.append(change)
        
        return np.mean(changes) if changes else 0.0
    
    def _is_bbox_stable(self, player_id: int) -> bool:
        """
        Bbox'ın stabil olup olmadığını kontrol eder.
        
        Stabil = son N frame'de değişim < threshold
        """
        bbox_history = self._bbox_history[player_id]
        
        if len(bbox_history) < 3:
            return False
        
        recent = np.array(list(bbox_history)[-5:])
        
        if len(recent) < 2:
            return False
        
        # Coefficient of variation
        mean_height = np.mean(recent)
        std_height = np.std(recent)
        
        if mean_height == 0:
            return False
        
        cv = std_height / mean_height
        
        return cv < self.bbox_stability_threshold
    
    def _calculate_speed_std(self, player_id: int) -> Optional[float]:
        """Son N frame'deki hız std sapmasını hesaplar"""
        speed_history = self._speed_history[player_id]
        
        if len(speed_history) < 3:
            return None
        
        return float(np.std(list(speed_history)))
    
    def _calculate_speed_max(self, player_id: int) -> Optional[float]:
        """Son N frame'deki maksimum hızı döndürür"""
        speed_history = self._speed_history[player_id]
        
        if len(speed_history) == 0:
            return None
        
        return float(np.max(list(speed_history)))
    
    def _calculate_speed_mean(self, player_id: int) -> Optional[float]:
        """Son N frame'deki ortalama hızı döndürür"""
        speed_history = self._speed_history[player_id]
        
        if len(speed_history) == 0:
            return None
        
        return float(np.mean(list(speed_history)))
    
    def _check_speed_stability(self, player_id: int) -> bool:
        """
        Hızın stabil olup olmadığını kontrol eder.
        
        Stabil = son N frame'de std < threshold
        """
        speed_std = self._calculate_speed_std(player_id)
        
        if speed_std is None:
            return False
        
        return speed_std < self.speed_stability_threshold
    
    def _calculate_data_quality(self,
                                player,
                                timestamp: int,
                                features: MovementFeatures) -> float:
        """
        Feature verilerinin kalitesini değerlendirir.
        
        Quality score (0-1):
        - 1.0: Tüm feature'lar mevcut ve güvenilir
        - 0.5: Bazı feature'lar eksik ama kullanılabilir
        - 0.0: Veri kullanılamaz
        
        Returns:
            Quality score (0-1)
        """
        score = 0.0
        
        # Speed data quality (40%)
        if features.speed is not None:
            score += 0.2
        if features.speed_smoothed is not None:
            score += 0.2
        
        # Bbox data quality (30%)
        if features.bbox_height is not None and features.bbox_height > 0:
            score += 0.15
        if features.bbox_height_change is not None:
            score += 0.15
        
        # Acceleration data quality (20%)
        if features.acceleration is not None:
            score += 0.2
        
        # Temporal data quality (10%)
        if len(self._speed_history.get(
            getattr(player, 'id', 0), []
        )) >= 3:
            score += 0.1
        
        return min(score, 1.0)
    
    def _detect_outlier(self, features: MovementFeatures) -> bool:
        """
        Feature'larda outlier olup olmadığını kontrol eder.
        
        Outlier conditions:
        - Speed > 12 m/s (fiziksel limit)
        - Acceleration > 10 m/s² (fiziksel limit)
        - Bbox change > 50% (muhtemelen detection hatası)
        """
        # Speed outlier
        if features.speed is not None and features.speed > 12.0:
            return True
        
        # Acceleration outlier
        if features.acceleration is not None and abs(features.acceleration) > 10.0:
            return True
        
        # Bbox outlier
        if (features.bbox_height_change is not None and 
            abs(features.bbox_height_change) > 0.5):
            return True
        
        return False
    
    def _calculate_missing_ratio(self, player, timestamp: int) -> float:
        """
        Son N frame'de eksik veri oranını hesaplar.
        
        Returns:
            Missing ratio (0-1)
        """
        if not hasattr(player, 'positions'):
            return 1.0
        
        # Son window_size frame'e bak
        expected_frames = list(range(
            max(0, timestamp - self.window_size + 1),
            timestamp + 1
        ))
        
        available_frames = [
            t for t in expected_frames if t in player.positions
        ]
        
        if len(expected_frames) == 0:
            return 1.0
        
        return 1.0 - (len(available_frames) / len(expected_frames))
    
    def reset_player_history(self, player_id: int):
        """
        Bir player için buffer'ları sıfırlar.
        
        Kullanım: Player sahadan çıktığında veya yeni maç başladığında
        """
        if player_id in self._bbox_history:
            self._bbox_history[player_id].clear()
        if player_id in self._speed_history:
            self._speed_history[player_id].clear()
    
    def get_feature_summary(self, player_id: int) -> Dict:
        """
        Bir player için feature özetini döndürür (debug için).
        
        Returns:
            {
                'bbox_history_size': int,
                'speed_history_size': int,
                'recent_bbox_mean': float,
                'recent_speed_mean': float
            }
        """
        bbox_hist = self._bbox_history.get(player_id, deque())
        speed_hist = self._speed_history.get(player_id, deque())
        
        return {
            'bbox_history_size': len(bbox_hist),
            'speed_history_size': len(speed_hist),
            'recent_bbox_mean': np.mean(list(bbox_hist)) if bbox_hist else None,
            'recent_speed_mean': np.mean(list(speed_hist)) if speed_hist else None
        }


# Helper function for external use
def extract_features_from_velocity_analyzer(
    velocity_analyzer,
    player,
    timestamp: int,
    bbox_height: float,
    player_id: Optional[int] = None,
    window_size: int = 7
) -> MovementFeatures:
    """
    Convenience function - tek satırda feature extraction.
    
    Example:
        >>> from features import extract_features_from_velocity_analyzer
        >>> features = extract_features_from_velocity_analyzer(
        ...     velocity_analyzer=va,
        ...     player=player_obj,
        ...     timestamp=100,
        ...     bbox_height=310.5
        ... )
    """
    extractor = MovementFeatureExtractor(
        velocity_analyzer=velocity_analyzer,
        window_size=window_size
    )
    return extractor.extract_features(
        player=player,
        timestamp=timestamp,
        bbox_height=bbox_height,
        player_id=player_id
    )


# Example usage
if __name__ == "__main__":
    # Mock VelocityAnalyzer için placeholder
    class MockVelocityAnalyzer:
        def calculate_speed(self, player, timestamp, window=1):
            return 3.5  # m/s
        
        def calculate_speed_smoothed(self, player, timestamp, window=5):
            return 3.4  # m/s
        
        def calculate_acceleration(self, player, timestamp, window=3):
            return 0.8  # m/s²
    
    # Mock Player
    class MockPlayer:
        def __init__(self):
            self.id = 7
            self.positions = {i: (100 + i, 200) for i in range(100)}
    
    # Test
    va = MockVelocityAnalyzer()
    extractor = MovementFeatureExtractor(va)
    player = MockPlayer()
    
    features = extractor.extract_features(
        player=player,
        timestamp=50,
        bbox_height=200.0,
        player_id=7
    )
    
    print("Extracted Features:")
    print(f"Speed: {features.speed} m/s")
    print(f"Acceleration: {features.acceleration} m/s²")
    print(f"Bbox Height: {features.bbox_height} px")
    print(f"Data Quality: {features.data_quality_score:.2f}")
    print(f"Is Valid: {features.is_valid()}")