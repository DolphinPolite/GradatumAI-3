"""
Basketball Movement Classification Thresholds

Bu modül basketbol oyuncu hareket sınıflandırması için kullanılan 
tüm eşik değerlerini tanımlar.

Threshold'lar literatür ve gerçek basketbol verilerine dayanır:
- NBA oyuncu ortalama hızları (Stats LLC, 2023)
- Biomechanics of Basketball Movement (Ziv & Lidor, 2009)
- Video-based player tracking studies

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
import json


@dataclass
class ThresholdSet:
    """
    Basketbol hareket sınıflandırma eşikleri.
    
    Tüm hız değerleri metre/saniye (m/s) cinsindendir.
    Tüm ivme değerleri metre/saniye² (m/s²) cinsindendir.
    
    Attributes:
        preset_name: Kullanılan preset adı ("default", "aggressive", "conservative")
        created_at: Threshold set oluşturulma zamanı (ML tracking için)
        
        # SPEED THRESHOLDS
        idle_speed_max: Maksimum idle hızı (m/s)
        walk_speed_min: Minimum yürüme hızı (m/s)
        walk_speed_max: Maksimum yürüme hızı (m/s)
        run_speed_min: Minimum koşma hızı (m/s)
        run_speed_max: Maksimum fiziksel koşma hızı (m/s)
        
        # JUMP DETECTION THRESHOLDS
        jump_bbox_shrink_min: Minimum bbox küçülme oranı (0-1)
        jump_bbox_grow_min: Minimum bbox büyüme oranı (landing)
        jump_speed_min: Jump için minimum hız (m/s)
        jump_duration_min_frames: Minimum jump süresi (frame)
        jump_duration_max_frames: Maksimum jump süresi (frame)
        
        # HYSTERESIS (state geçişlerinde flickering önleme)
        hysteresis_margin: Durum değiştirmek için ekstra güvenlik marjı (m/s)
        
        # TEMPORAL CONSTRAINTS
        min_state_duration_frames: Bir state'in minimum süresi
        temporal_window_size: Smoothing için pencere boyutu
        
        # CONFIDENCE
        confidence_threshold_min: Minimum güven skoru (0-1)
        confidence_speed_weight: Hız'ın güven skorundaki ağırlığı
        confidence_stability_weight: Stabilite'nin ağırlığı
        confidence_bbox_weight: Bbox'ın ağırlığı
    """
    
    # Metadata
    preset_name: str = "default"
    created_at: str = None
    
    # Speed thresholds (m/s)
    idle_speed_max: float = 0.5
    walk_speed_min: float = 0.4  # hysteresis ile overlap
    walk_speed_max: float = 2.5
    run_speed_min: float = 2.2   # hysteresis ile overlap
    run_speed_max: float = 8.0
    
    # Jump thresholds
    jump_bbox_shrink_min: float = 0.12  # %12 küçülme
    jump_bbox_grow_min: float = 0.10    # %10 büyüme (landing)
    jump_speed_min: float = 0.8         # Durağandan sıçranmaz
    jump_duration_min_frames: int = 8   # ~0.27 saniye @ 30fps
    jump_duration_max_frames: int = 25  # ~0.83 saniye @ 30fps
    
    # Hysteresis
    hysteresis_margin: float = 0.3
    
    # Temporal
    min_state_duration_frames: int = 5
    temporal_window_size: int = 7
    
    # Confidence
    confidence_threshold_min: float = 0.6
    confidence_speed_weight: float = 0.4
    confidence_stability_weight: float = 0.35
    confidence_bbox_weight: float = 0.25
    
    def __post_init__(self):
        """Initialization sonrası validasyon ve metadata ekleme"""
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        
        # Validasyon
        self._validate_thresholds()
    
    def _validate_thresholds(self):
        """
        Threshold'ların fiziksel olarak mantıklı olduğunu kontrol eder.
        
        Raises:
            ValueError: Geçersiz threshold kombinasyonu
        """
        # Speed progression mantıklı mı?
        if not (self.idle_speed_max < self.walk_speed_max < self.run_speed_max):
            raise ValueError(
                f"Speed thresholds must be increasing: "
                f"idle={self.idle_speed_max}, walk={self.walk_speed_max}, "
                f"run={self.run_speed_max}"
            )
        
        # Hysteresis overlap var mı?
        if self.walk_speed_min >= self.idle_speed_max + self.hysteresis_margin:
            raise ValueError(
                f"Walk speed min ({self.walk_speed_min}) must overlap with "
                f"idle max ({self.idle_speed_max}) for hysteresis"
            )
        
        if self.run_speed_min >= self.walk_speed_max + self.hysteresis_margin:
            raise ValueError(
                f"Run speed min ({self.run_speed_min}) must overlap with "
                f"walk max ({self.walk_speed_max}) for hysteresis"
            )
        
        # Jump duration mantıklı mı?
        if self.jump_duration_min_frames >= self.jump_duration_max_frames:
            raise ValueError(
                f"Jump duration min ({self.jump_duration_min_frames}) must be "
                f"less than max ({self.jump_duration_max_frames})"
            )
        
        # Confidence weights toplamı 1 mi?
        weight_sum = (self.confidence_speed_weight + 
                     self.confidence_stability_weight + 
                     self.confidence_bbox_weight)
        if not (0.99 <= weight_sum <= 1.01):
            raise ValueError(
                f"Confidence weights must sum to 1.0, got {weight_sum}"
            )
        
        # Bbox thresholds mantıklı mı?
        if not (0 < self.jump_bbox_shrink_min < 0.5):
            raise ValueError(
                f"Jump bbox shrink must be between 0 and 0.5, "
                f"got {self.jump_bbox_shrink_min}"
            )
    
    def get_speed_threshold_for_state(self, state: str) -> tuple:
        """
        Bir state için hız aralığını döndürür.
        
        Args:
            state: "idle", "walking", "running"
            
        Returns:
            (min_speed, max_speed) tuple
            
        Example:
            >>> thresholds.get_speed_threshold_for_state("walking")
            (0.4, 2.5)
        """
        thresholds_map = {
            "idle": (0.0, self.idle_speed_max),
            "walking": (self.walk_speed_min, self.walk_speed_max),
            "running": (self.run_speed_min, self.run_speed_max),
            "jumping": (self.jump_speed_min, self.run_speed_max)
        }
        
        if state not in thresholds_map:
            raise ValueError(f"Unknown state: {state}")
        
        return thresholds_map[state]
    
    def get_hysteresis_threshold(self, 
                                from_state: str, 
                                to_state: str) -> float:
        """
        İki state arasındaki geçiş için hysteresis uygular.
        
        Hysteresis: Geriye dönüş için farklı eşik kullanır.
        Örnek: walk → run için 2.5 m/s, run → walk için 2.2 m/s
        
        Args:
            from_state: Mevcut state
            to_state: Hedef state
            
        Returns:
            Adjusted threshold (m/s)
            
        Example:
            >>> # Normal: walking → running @ 2.5 m/s
            >>> thresholds.get_hysteresis_threshold("walking", "running")
            2.5
            >>> # Hysteresis: running → walking @ 2.2 m/s
            >>> thresholds.get_hysteresis_threshold("running", "walking")
            2.2
        """
        # Ascending transition (idle → walk → run)
        if from_state == "idle" and to_state == "walking":
            return self.walk_speed_min
        elif from_state == "walking" and to_state == "running":
            return self.run_speed_min
        
        # Descending transition (run → walk → idle) - apply hysteresis
        elif from_state == "running" and to_state == "walking":
            return self.run_speed_min - self.hysteresis_margin
        elif from_state == "walking" and to_state == "idle":
            return self.walk_speed_min - self.hysteresis_margin
        
        # Jump transitions (özel durum)
        elif to_state == "jumping":
            return self.jump_speed_min
        
        # Unknown transition
        else:
            return 0.0
    
    def to_dict(self) -> Dict:
        """
        ML logging için dictionary export.
        
        Returns:
            Tüm threshold'ları içeren dict
        """
        return {
            "preset_name": self.preset_name,
            "created_at": self.created_at,
            "speed_thresholds": {
                "idle_max": self.idle_speed_max,
                "walk_min": self.walk_speed_min,
                "walk_max": self.walk_speed_max,
                "run_min": self.run_speed_min,
                "run_max": self.run_speed_max
            },
            "jump_thresholds": {
                "bbox_shrink_min": self.jump_bbox_shrink_min,
                "bbox_grow_min": self.jump_bbox_grow_min,
                "speed_min": self.jump_speed_min,
                "duration_min_frames": self.jump_duration_min_frames,
                "duration_max_frames": self.jump_duration_max_frames
            },
            "hysteresis_margin": self.hysteresis_margin,
            "temporal": {
                "min_state_duration": self.min_state_duration_frames,
                "window_size": self.temporal_window_size
            },
            "confidence": {
                "threshold_min": self.confidence_threshold_min,
                "weights": {
                    "speed": self.confidence_speed_weight,
                    "stability": self.confidence_stability_weight,
                    "bbox": self.confidence_bbox_weight
                }
            }
        }
    
    def export_json(self, filepath: str):
        """Threshold'ları JSON dosyasına export eder"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def from_preset(cls, preset: str = "default") -> 'ThresholdSet':
        """
        Predefined preset'lerden birini yükler.
        
        Args:
            preset: "default", "aggressive", "conservative"
            
        Returns:
            ThresholdSet instance
            
        Preset Açıklamaları:
            - default: Balanced, genel kullanım
            - aggressive: Daha hızlı state transition (highlight detection)
            - conservative: Daha stabil, gürültüye dayanıklı (tactical analysis)
        """
        if preset == "default":
            return cls(preset_name="default")
        
        elif preset == "aggressive":
            return cls(
                preset_name="aggressive",
                # Daha düşük eşikler = daha erken transition
                idle_speed_max=0.4,
                walk_speed_min=0.3,
                walk_speed_max=2.2,
                run_speed_min=2.0,
                jump_bbox_shrink_min=0.10,
                jump_duration_min_frames=6,
                hysteresis_margin=0.2,
                min_state_duration_frames=3,
                temporal_window_size=5,
                confidence_threshold_min=0.5
            )
        
        elif preset == "conservative":
            return cls(
                preset_name="conservative",
                # Daha yüksek eşikler = daha geç transition
                idle_speed_max=0.6,
                walk_speed_min=0.5,
                walk_speed_max=2.8,
                run_speed_min=2.5,
                jump_bbox_shrink_min=0.15,
                jump_duration_min_frames=10,
                hysteresis_margin=0.4,
                min_state_duration_frames=8,
                temporal_window_size=9,
                confidence_threshold_min=0.7
            )
        
        else:
            raise ValueError(
                f"Unknown preset: {preset}. "
                f"Available: 'default', 'aggressive', 'conservative'"
            )


# Convenience functions

def get_default_thresholds() -> ThresholdSet:
    """Default threshold set döndürür"""
    return ThresholdSet.from_preset("default")


def get_aggressive_thresholds() -> ThresholdSet:
    """Aggressive threshold set döndürür (highlight detection için)"""
    return ThresholdSet.from_preset("aggressive")


def get_conservative_thresholds() -> ThresholdSet:
    """Conservative threshold set döndürür (tactical analysis için)"""
    return ThresholdSet.from_preset("conservative")


# Example usage
if __name__ == "__main__":
    # Test default thresholds
    thresholds = get_default_thresholds()
    print("Default Thresholds:")
    print(json.dumps(thresholds.to_dict(), indent=2))
    
    # Test hysteresis
    print("\nHysteresis Test:")
    print(f"walking → running: {thresholds.get_hysteresis_threshold('walking', 'running')} m/s")
    print(f"running → walking: {thresholds.get_hysteresis_threshold('running', 'walking')} m/s")
    
    # Test preset comparison
    print("\nPreset Comparison:")
    for preset in ["default", "aggressive", "conservative"]:
        t = ThresholdSet.from_preset(preset)
        print(f"{preset}: run_speed_min = {t.run_speed_min} m/s")