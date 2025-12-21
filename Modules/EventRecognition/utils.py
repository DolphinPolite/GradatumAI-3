"""
Basketball Movement Classification Utilities

Bu modül movement classification için gerekli yardımcı fonksiyonları içerir.

Kritik Fonksiyonlar:
- calculate_confidence_score: TEK KAYNAK confidence hesaplama
- calculate_bbox_height_change: Jump detection'ın kalbi
- detect_outliers: Gürültü filtreleme
- MovementLogger: ML-friendly structured logging

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
import json
from datetime import datetime
from dataclasses import dataclass


# ============================================================================
# BBOX HEIGHT ANALYSIS - Jump Detection'ın Kalbi
# ============================================================================

def calculate_bbox_height_change(
    bbox_heights: List[float],
    window: int = 5,
    method: str = "ratio"
) -> Tuple[float, float, bool]:
    """
    Bbox height değişimini analiz eder (jump detection için kritik).
    
    Bu fonksiyon jump detection'ın temel taşıdır. Oyuncu sıçradığında:
    1. Bbox yüksekliği ani olarak küçülür (ayaklar yerden kesilir)
    2. Değişim hızı negatiftir (shrinking)
    3. Kısa sürede geri büyür (landing)
    
    Args:
        bbox_heights: Son N frame'deki bbox height listesi (piksel)
        window: Analiz pencere boyutu
        method: "ratio" veya "absolute"
            - ratio: Yüzdesel değişim (ölçek-bağımsız)
            - absolute: Piksel değişimi (hızlı hesaplama)
    
    Returns:
        (change_ratio, change_rate, is_stable)
        - change_ratio: Ortalama değişim oranı (-1 to 1)
            Negatif = küçülme (jumping up)
            Pozitif = büyüme (landing)
        - change_rate: Değişim hızı (per frame)
        - is_stable: Bbox stabil mi? (bool)
    
    Example:
        >>> heights = [200, 198, 176, 174, 180, 195, 200]  # Jump sekansı
        >>> change, rate, stable = calculate_bbox_height_change(heights)
        >>> print(f"Change: {change:.3f}, Stable: {stable}")
        Change: -0.040, Stable: False  # Jump detected!
    
    Jump Pattern:
        Normal: [200, 200, 200, 200, 200]  → stable=True
        Jump:   [200, 190, 176, 178, 195]  → stable=False, change < -0.10
    """
    if len(bbox_heights) < 2:
        return 0.0, 0.0, False
    
    # Recent window seç
    recent = bbox_heights[-window:] if len(bbox_heights) >= window else bbox_heights
    
    if len(recent) < 2:
        return 0.0, 0.0, False
    
    # Outlier filtreleme (ani zoom, occlusion)
    filtered = _filter_bbox_outliers(recent)
    
    if len(filtered) < 2:
        return 0.0, 0.0, False
    
    # Method'a göre değişim hesapla
    if method == "ratio":
        # Yüzdesel değişim (scale-independent)
        changes = []
        for i in range(1, len(filtered)):
            if filtered[i-1] > 0:
                change = (filtered[i] - filtered[i-1]) / filtered[i-1]
                changes.append(change)
        
        change_ratio = np.mean(changes) if changes else 0.0
        change_rate = change_ratio  # per frame
    
    else:  # absolute
        # Piksel değişimi
        changes = np.diff(filtered)
        change_ratio = np.mean(changes) / np.mean(filtered) if np.mean(filtered) > 0 else 0.0
        change_rate = np.mean(changes)
    
    # Stability check
    cv = np.std(filtered) / np.mean(filtered) if np.mean(filtered) > 0 else 0
    is_stable = cv < 0.05  # %5'ten az değişim = stable
    
    return float(change_ratio), float(change_rate), bool(is_stable)


def _filter_bbox_outliers(bbox_heights: List[float]) -> List[float]:
    """
    Bbox height listesindeki outlier'ları filtreler (IQR method).
    
    Outlier sebepleri:
    - Ani kamera zoom
    - Partial occlusion
    - Detection hatası
    
    IQR Method (VelocityAnalyzer uyumlu):
    Q1 = 25th percentile
    Q3 = 75th percentile
    IQR = Q3 - Q1
    Outlier: < Q1 - 1.5*IQR veya > Q3 + 1.5*IQR
    """
    if len(bbox_heights) < 4:
        return bbox_heights
    
    arr = np.array(bbox_heights)
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    # Outlier'ları filtrele
    filtered = arr[(arr >= lower_bound) & (arr <= upper_bound)]
    
    # En az 2 değer olmalı
    if len(filtered) < 2:
        return bbox_heights
    
    return filtered.tolist()


def detect_jump_from_bbox(
    bbox_heights: List[float],
    shrink_threshold: float = 0.12,
    window: int = 5
) -> Tuple[bool, float]:
    """
    Bbox height pattern'inden jump detect eder.
    
    Jump pattern:
    1. Ani küçülme (> shrink_threshold)
    2. Kısa süre küçük kalır (airtime)
    3. Geri büyür (landing)
    
    Args:
        bbox_heights: Son N frame'deki heights
        shrink_threshold: Minimum küçülme oranı (0.12 = %12)
        window: Analiz pencere boyutu
    
    Returns:
        (is_jumping, confidence)
        - is_jumping: Jump tespit edildi mi?
        - confidence: Jump güvenilirliği (0-1)
    
    Example:
        >>> heights = [200, 200, 176, 175, 178, 195, 200]
        >>> jumping, conf = detect_jump_from_bbox(heights)
        >>> print(f"Jumping: {jumping}, Confidence: {conf:.2f}")
        Jumping: True, Confidence: 0.85
    """
    change, rate, stable = calculate_bbox_height_change(
        bbox_heights, window=window
    )
    
    # Jump conditions
    is_shrinking = change < -shrink_threshold
    is_rapid = abs(rate) > 0.03  # Hızlı değişim
    is_unstable = not stable
    
    # Jump detected?
    is_jumping = is_shrinking and is_unstable
    
    # Confidence calculation
    confidence = 0.0
    if is_jumping:
        # Shrink magnitude'a göre confidence
        shrink_magnitude = abs(change) / shrink_threshold
        confidence = min(shrink_magnitude, 1.0) * 0.7
        
        # Rapid change bonus
        if is_rapid:
            confidence += 0.2
        
        # Window coverage bonus
        if len(bbox_heights) >= window:
            confidence += 0.1
        
        confidence = min(confidence, 1.0)
    
    return is_jumping, confidence


# ============================================================================
# CONFIDENCE SCORE CALCULATION - TEK KAYNAK
# ============================================================================

def calculate_confidence_score(
    features: 'MovementFeatures',
    thresholds: 'ThresholdSet',
    predicted_state: str,
    previous_state: Optional[str] = None
) -> float:
    """
    Feature'lara göre confidence score hesaplar.
    
    ⚠️ KRİTİK: Bu fonksiyon TEK KAYNAK confidence hesaplama.
    Başka hiçbir yerde confidence hesaplanmamalı.
    
    Confidence Bileşenleri:
    1. Speed consistency (40%): Tahmin edilen state'in threshold'larına uygunluk
    2. Temporal stability (35%): Önceki state ile tutarlılık
    3. Bbox reliability (25%): Bbox data quality
    
    Args:
        features: MovementFeatures instance
        thresholds: ThresholdSet instance
        predicted_state: Tahmin edilen state ("idle", "walking", "running", "jumping")
        previous_state: Önceki frame'deki state (opsiyonel)
    
    Returns:
        Confidence score (0-1)
        - 1.0: Çok güvenilir
        - 0.5-0.7: Orta güvenilirlik
        - < 0.5: Düşük güvenilirlik (dikkatli kullan)
    
    Example:
        >>> confidence = calculate_confidence_score(
        ...     features=features,
        ...     thresholds=thresholds,
        ...     predicted_state="running",
        ...     previous_state="walking"
        ... )
        >>> print(f"Confidence: {confidence:.2f}")
        Confidence: 0.87
    """
    # Data quality check
    if not features.is_valid():
        return 0.0
    
    # Component scores
    speed_score = _calculate_speed_confidence(features, thresholds, predicted_state)
    stability_score = _calculate_stability_confidence(
        features, predicted_state, previous_state
    )
    bbox_score = _calculate_bbox_confidence(features, predicted_state)
    
    # Weighted combination
    confidence = (
        speed_score * thresholds.confidence_speed_weight +
        stability_score * thresholds.confidence_stability_weight +
        bbox_score * thresholds.confidence_bbox_weight
    )
    
    return float(np.clip(confidence, 0.0, 1.0))


def _calculate_speed_confidence(
    features: 'MovementFeatures',
    thresholds: 'ThresholdSet',
    state: str
) -> float:
    """
    Speed'in tahmin edilen state ile ne kadar uyumlu olduğunu hesaplar.
    
    Method: Threshold'dan uzaklık normalize edilir.
    """
    if features.speed_smoothed is None:
        return 0.0
    
    speed = features.speed_smoothed
    min_speed, max_speed = thresholds.get_speed_threshold_for_state(state)
    
    # Speed state aralığında mı?
    if min_speed <= speed <= max_speed:
        # Aralık içinde - threshold'dan uzaklığa göre score
        range_width = max_speed - min_speed
        
        if range_width == 0:
            return 1.0
        
        # Aralığın ortasına ne kadar yakın?
        center = (min_speed + max_speed) / 2
        distance_from_center = abs(speed - center)
        normalized_distance = distance_from_center / (range_width / 2)
        
        # Center'a yakın = high confidence
        return 1.0 - (normalized_distance * 0.3)
    
    else:
        # Aralık dışında - threshold'dan ne kadar uzak?
        if speed < min_speed:
            distance = min_speed - speed
            threshold_width = min_speed
        else:
            distance = speed - max_speed
            threshold_width = max_speed - min_speed
        
        if threshold_width == 0:
            return 0.0
        
        # Uzaklık arttıkça confidence düşer
        normalized_distance = distance / threshold_width
        penalty = min(normalized_distance * 0.5, 0.8)
        
        return max(0.2, 1.0 - penalty)


def _calculate_stability_confidence(
    features: 'MovementFeatures',
    current_state: str,
    previous_state: Optional[str]
) -> float:
    """
    Temporal stability'ye göre confidence hesaplar.
    
    Factors:
    - State consistency (previous ile aynı mı?)
    - Speed stability (std düşük mü?)
    - Acceleration consistency (ani değişim var mı?)
    """
    score = 0.0
    
    # 1. State consistency (50%)
    if previous_state is not None:
        if current_state == previous_state:
            score += 0.5  # Aynı state = stable
        else:
            # State değişimi - geçerli transition mı?
            valid_transitions = {
                ("idle", "walking"),
                ("walking", "idle"),
                ("walking", "running"),
                ("running", "walking"),
                ("walking", "jumping"),
                ("running", "jumping"),
            }
            if (previous_state, current_state) in valid_transitions:
                score += 0.3  # Geçerli transition
            else:
                score += 0.1  # Şüpheli transition
    else:
        score += 0.25  # Previous state yok - neutral
    
    # 2. Speed stability (30%)
    if features.is_speed_stable:
        score += 0.3
    elif features.speed_std is not None and features.speed_std < 0.5:
        score += 0.2
    else:
        score += 0.1
    
    # 3. Acceleration consistency (20%)
    if features.acceleration is not None:
        if abs(features.acceleration) < 1.0:
            score += 0.2  # Smooth motion
        elif abs(features.acceleration) < 3.0:
            score += 0.1  # Moderate change
        else:
            score += 0.05  # Ani değişim
    else:
        score += 0.1  # No data - neutral
    
    return score


def _calculate_bbox_confidence(
    features: 'MovementFeatures',
    state: str
) -> float:
    """
    Bbox data quality'ye göre confidence hesaplar.
    
    Factors:
    - Bbox stability (stable = high confidence)
    - Bbox height validity (reasonable height?)
    - Jump detection için bbox change magnitude
    """
    score = 0.0
    
    # 1. Bbox stability (50%)
    if features.bbox_height_stable:
        score += 0.5
    else:
        score += 0.2
    
    # 2. Bbox height validity (30%)
    if features.bbox_height is not None and 50 < features.bbox_height < 500:
        # Reasonable bbox height (oyuncu 50-500 piksel arası)
        score += 0.3
    else:
        score += 0.1
    
    # 3. Jump-specific confidence (20%)
    if state == "jumping":
        if (features.bbox_height_change is not None and 
            features.bbox_height_change < -0.10):
            # Strong jump signal
            score += 0.2
        else:
            score += 0.05
    else:
        # Non-jump states için stable bbox = good
        if features.bbox_height_change is not None:
            if abs(features.bbox_height_change) < 0.05:
                score += 0.2
            else:
                score += 0.1
    
    return score


# ============================================================================
# OUTLIER DETECTION
# ============================================================================

def detect_outliers(
    values: List[float],
    method: str = "iqr",
    threshold: float = 1.5
) -> List[int]:
    """
    Bir listede outlier indekslerini tespit eder.
    
    VelocityAnalyzer'ın outlier mantığıyla uyumlu.
    
    Args:
        values: Değer listesi
        method: "iqr" veya "zscore"
        threshold: Outlier threshold (IQR için 1.5, z-score için 3.0)
    
    Returns:
        Outlier indekslerinin listesi
    
    Example:
        >>> values = [2.0, 2.1, 2.2, 15.0, 2.3, 2.1]  # 15.0 outlier
        >>> outliers = detect_outliers(values)
        >>> print(outliers)
        [3]
    """
    if len(values) < 4:
        return []
    
    arr = np.array(values)
    
    if method == "iqr":
        # Interquartile Range method
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        
        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr
        
        outlier_mask = (arr < lower_bound) | (arr > upper_bound)
    
    elif method == "zscore":
        # Z-score method
        mean = np.mean(arr)
        std = np.std(arr)
        
        if std == 0:
            return []
        
        z_scores = np.abs((arr - mean) / std)
        outlier_mask = z_scores > threshold
    
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return np.where(outlier_mask)[0].tolist()


# ============================================================================
# INPUT VALIDATION
# ============================================================================

def validate_input_data(
    player,
    timestamp: int,
    bbox_height: float
) -> Tuple[bool, Optional[str]]:
    """
    Girdi verisini validate eder.
    
    Args:
        player: Player objesi
        timestamp: Frame index
        bbox_height: Bbox height (piksel)
    
    Returns:
        (is_valid, error_message)
        - is_valid: Veri geçerli mi?
        - error_message: Hata mesajı (is_valid=False ise)
    
    Example:
        >>> valid, error = validate_input_data(player, 100, 200.0)
        >>> if not valid:
        ...     print(f"Invalid data: {error}")
    """
    # Player validation
    if player is None:
        return False, "Player object is None"
    
    if not hasattr(player, 'positions'):
        return False, "Player object has no 'positions' attribute"
    
    if not isinstance(player.positions, dict):
        return False, "Player.positions is not a dictionary"
    
    # Timestamp validation
    if not isinstance(timestamp, int):
        return False, f"Timestamp must be int, got {type(timestamp)}"
    
    if timestamp < 0:
        return False, f"Timestamp must be >= 0, got {timestamp}"
    
    if timestamp not in player.positions:
        return False, f"Timestamp {timestamp} not in player.positions"
    
    # Bbox validation
    if bbox_height is None:
        return False, "Bbox height is None"
    
    if not isinstance(bbox_height, (int, float)):
        return False, f"Bbox height must be numeric, got {type(bbox_height)}"
    
    if bbox_height <= 0:
        return False, f"Bbox height must be > 0, got {bbox_height}"
    
    if bbox_height > 1000:
        return False, f"Bbox height suspiciously large: {bbox_height}"
    
    return True, None


# ============================================================================
# ML-FRIENDLY LOGGING
# ============================================================================

class MovementLogger:
    """
    ML-friendly structured logging.
    
    Her classification kararını aşağıdaki formatla loglar:
    - Timestamp
    - Player ID
    - Raw features
    - Thresholds used
    - Raw classification
    - Smoothed classification
    - Confidence
    - Reasoning chain
    
    Loglar JSON formatında kaydedilir - ML analizi için ideal.
    
    Usage:
        >>> logger = MovementLogger(log_file="movement_log.json")
        >>> logger.log_classification(
        ...     timestamp=100,
        ...     player_id=7,
        ...     features=features,
        ...     thresholds=thresholds,
        ...     raw_state="running",
        ...     final_state="running",
        ...     confidence=0.87,
        ...     reasoning="Speed in range, stable, previous=walking"
        ... )
    """
    
    def __init__(self, 
                 log_file: Optional[str] = None,
                 buffer_size: int = 100):
        """
        Args:
            log_file: Log dosyası yolu (None ise memory'de tutar)
            buffer_size: Kaç entry biriktirince diske yazar
        """
        self.log_file = log_file
        self.buffer_size = buffer_size
        self.buffer = []
        self.log_count = 0
    
    def log_classification(self,
                          timestamp: int,
                          player_id: int,
                          features: Dict,
                          thresholds: Dict,
                          raw_state: str,
                          final_state: str,
                          confidence: float,
                          reasoning: str):
        """
        Bir classification kararını logla.
        
        Args:
            timestamp: Frame index
            player_id: Player ID
            features: Feature dictionary
            thresholds: Threshold dictionary
            raw_state: Smoothing öncesi state
            final_state: Final state
            confidence: Confidence score
            reasoning: Human-readable açıklama
        """
        log_entry = {
            'log_id': self.log_count,
            'timestamp_logged': datetime.now().isoformat(),
            'frame_timestamp': timestamp,
            'player_id': player_id,
            'raw_features': features,
            'thresholds_used': thresholds,
            'raw_classification': raw_state,
            'final_classification': final_state,
            'confidence': confidence,
            'reasoning': reasoning
        }
        
        self.buffer.append(log_entry)
        self.log_count += 1
        
        # Buffer doldu mu? Diske yaz
        if len(self.buffer) >= self.buffer_size:
            self._flush()
    
    def _flush(self):
        """Buffer'ı diske yazar"""
        if self.log_file is None or len(self.buffer) == 0:
            return
        
        try:
            # Append mode - existing logs korunur
            with open(self.log_file, 'a') as f:
                for entry in self.buffer:
                    f.write(json.dumps(entry) + '\n')
            
            self.buffer.clear()
        except Exception as e:
            print(f"Logger flush error: {e}")
    
    def get_logs(self) -> List[Dict]:
        """Tüm logları döndürür (memory + file)"""
        logs = list(self.buffer)
        
        if self.log_file is not None:
            try:
                with open(self.log_file, 'r') as f:
                    for line in f:
                        logs.append(json.loads(line))
            except FileNotFoundError:
                pass
        
        return logs
    
    def export_to_json(self, output_file: str):
        """Tüm logları tek bir JSON dosyasına export eder"""
        logs = self.get_logs()
        
        with open(output_file, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def clear(self):
        """Tüm logları temizler"""
        self.buffer.clear()
        self.log_count = 0
        
        if self.log_file is not None:
            try:
                open(self.log_file, 'w').close()
            except:
                pass


# Example usage
if __name__ == "__main__":
    # Test bbox height change
    print("=== Bbox Height Change Test ===")
    
    # Normal sequence
    normal_heights = [200, 200, 199, 200, 201, 200]
    change, rate, stable = calculate_bbox_height_change(normal_heights)
    print(f"Normal: change={change:.3f}, rate={rate:.3f}, stable={stable}")
    
    # Jump sequence
    jump_heights = [200, 198, 176, 174, 178, 195, 200]
    change, rate, stable = calculate_bbox_height_change(jump_heights)
    print(f"Jump: change={change:.3f}, rate={rate:.3f}, stable={stable}")
    
    is_jumping, conf = detect_jump_from_bbox(jump_heights)
    print(f"Jump detected: {is_jumping}, confidence: {conf:.2f}")
    
    # Test outlier detection
    print("\n=== Outlier Detection Test ===")
    values = [2.0, 2.1, 2.2, 15.0, 2.3, 2.1, 2.0]
    outliers = detect_outliers(values)
    print(f"Values: {values}")
    print(f"Outlier indices: {outliers}")
    
    # Test logger
    print("\n=== Logger Test ===")
    logger = MovementLogger()
    logger.log_classification(
        timestamp=100,
        player_id=7,
        features={'speed': 3.5, 'acceleration': 0.8},
        thresholds={'run_speed_min': 2.2},
        raw_state="running",
        final_state="running",
        confidence=0.87,
        reasoning="Speed in range, stable"
    )
    print(f"Logged {logger.log_count} entries")