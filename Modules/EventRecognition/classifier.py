"""
Basketball Movement Classifier - Main Orchestrator

Bu modül tüm alt modülleri bir araya getirir ve hareket sınıflandırması yapar.

Pipeline:
1. VelocityAnalyzer → speed, acceleration
2. MovementFeatureExtractor → features + bbox analysis
3. Raw Classification → threshold'lara göre ilk tahmin
4. TemporalFilter → smoothing (gürültü azaltma)
5. StateMachine → validation (fiziksel geçerlilik)
6. Final Output → confidence score + reasoning

Public API:
- classify_frame(): Tek bir frame sınıflandır
- classify_batch(): Batch processing (offline analysis)
- export_state_timeline(): ML analizi için export
- reset(): Buffer'ları temizle

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime

# Internal imports
from .config import MovementConfig
from .thresholds import ThresholdSet
from .features import MovementFeatureExtractor, MovementFeatures
from .temporal_filter import TemporalStateFilter
from .state_machine import MovementStateMachine
from .utils import (
    calculate_confidence_score,
    validate_input_data,
    MovementLogger
)


class BasicMovementClassifier:
    """
    Basketball oyuncu hareket sınıflandırıcı (rule-based).
    
    Bu sınıf tüm modülleri orchestrate eder ve tek bir entry point sağlar.
    
    Pipeline:
    1. VelocityAnalyzer ile hız/ivme hesapla (mevcut sistem)
    2. MovementFeatureExtractor ile feature'ları çıkar
    3. Threshold'lara göre raw classification yap
    4. TemporalFilter ile stabilize et (smoothing)
    5. StateMachine ile validate et (fiziksel geçerlilik)
    6. Confidence score hesapla (utils.py - TEK KAYNAK)
    
    Mevcut sisteme entegrasyon:
    - VelocityAnalyzer instance'ı parametre olarak alır
    - Player objesiyle çalışır (positions dict içermeli)
    - Frame-by-frame çağrılabilir (real-time uyumlu)
    - Batch processing desteği (offline analysis)
    
    ML Compatibility:
    - Tüm intermediate sonuçları loglar
    - Feature importance analizi için export metodu
    - Structured logging (JSON)
    - Reasoning chain (explainability)
    
    Design Principles:
    - Single Responsibility: Her modül kendi işini yapar
    - Explainable: Her karar reasoning ile döner
    - Production-ready: Error handling, logging, validation
    
    Example:
        >>> # Initialize
        >>> from velocity_analyzer import VelocityAnalyzer
        >>> va = VelocityAnalyzer(fps=30, ...)
        >>> classifier = BasicMovementClassifier(
        ...     velocity_analyzer=va,
        ...     player_id=7
        ... )
        >>> 
        >>> # Classify single frame
        >>> result = classifier.classify_frame(
        ...     player=player_obj,
        ...     timestamp=100,
        ...     bbox_height=320.5
        ... )
        >>> print(f"State: {result['movement_state']}")
        >>> print(f"Confidence: {result['confidence']:.2f}")
    """
    
    def __init__(self,
                 velocity_analyzer,
                 player_id: int,
                 config: Optional[MovementConfig] = None,
                 thresholds: Optional[ThresholdSet] = None,
                 enable_logging: bool = False,
                 log_file: Optional[str] = None):
        """
        Args:
            velocity_analyzer: VelocityAnalyzer instance (mevcut sistem)
            player_id: Player ID (tracking ve logging için)
            config: MovementConfig instance (None ise default)
            thresholds: ThresholdSet instance (None ise default)
            enable_logging: Logging aktif olsun mu?
            log_file: Log dosyası yolu (None ise memory'de)
        """
        self.velocity_analyzer = velocity_analyzer
        self.player_id = player_id
        
        # Config and thresholds
        self.config = config or MovementConfig()
        self.thresholds = thresholds or ThresholdSet.from_preset("default")
        
        # Initialize sub-modules
        self.feature_extractor = MovementFeatureExtractor(
            velocity_analyzer=self.velocity_analyzer,
            window_size=self.thresholds.temporal_window_size
        )
        
        self.temporal_filter = TemporalStateFilter(
            window_size=self.thresholds.temporal_window_size,
            min_duration=self.thresholds.min_state_duration_frames,
            hysteresis_frames=2
        )
        
        self.state_machine = MovementStateMachine(
            player_id=self.player_id,
            allow_landing_state=True,
            strict_mode=False
        )
        
        # Logging
        self.enable_logging = enable_logging
        self.logger = MovementLogger(log_file=log_file) if enable_logging else None
        
        # Statistics
        self.frame_count = 0
        self.classification_stats = {
            'total_frames': 0,
            'valid_transitions': 0,
            'invalid_transitions': 0,
            'state_counts': {},
            'low_confidence_frames': 0
        }
    
    def classify_frame(self,
                      player,
                      timestamp: int,
                      bbox_height: float) -> Dict:
        """
        Tek bir frame için hareket sınıflandırması.
        
        Bu fonksiyon tüm pipeline'ı çalıştırır:
        1. Input validation
        2. Feature extraction
        3. Raw classification
        4. Temporal smoothing
        5. State machine validation
        6. Confidence calculation
        7. Logging (opsiyonel)
        
        Args:
            player: Player objesi (VelocityAnalyzer uyumlu)
                Must have: positions dict
            timestamp: Frame index
            bbox_height: Oyuncunun bounding box yüksekliği (piksel)
        
        Returns:
            {
                'player_id': int,
                'timestamp': int,
                'movement_state': str,      # idle/walking/running/jumping/landing
                'confidence': float,        # 0-1
                'raw_state': str,          # Smoothing öncesi
                'smoothed_state': str,     # Temporal filter sonrası
                'is_valid_transition': bool,
                'features': dict,          # Debug için
                'reasoning': str,          # ML interpretability
                'data_quality': float      # Feature quality
            }
        
        Raises:
            ValueError: Geçersiz input data
        
        Example:
            >>> result = classifier.classify_frame(
            ...     player=player_obj,
            ...     timestamp=100,
            ...     bbox_height=320.5
            ... )
            >>> if result['confidence'] > 0.7:
            ...     print(f"High confidence: {result['movement_state']}")
        """
        # 1. INPUT VALIDATION
        is_valid, error_msg = validate_input_data(player, timestamp, bbox_height)
        if not is_valid:
            raise ValueError(f"Invalid input: {error_msg}")
        
        # 2. FEATURE EXTRACTION
        features = self.feature_extractor.extract_features(
            player=player,
            timestamp=timestamp,
            bbox_height=bbox_height,
            player_id=self.player_id
        )
        
        # Check feature quality
        if not features.is_valid():
            # Low quality features - return low confidence idle
            return self._create_low_quality_result(timestamp, features)
        
        # 3. RAW CLASSIFICATION
        raw_state = self._classify_from_features(features)
        raw_confidence = self._calculate_raw_confidence(features, raw_state)
        
        # 4. TEMPORAL SMOOTHING
        temporal_result = self.temporal_filter.apply_smoothing(
            player_id=self.player_id,
            timestamp=timestamp,
            raw_state=raw_state,
            raw_confidence=raw_confidence
        )
        
        smoothed_state = temporal_result.smoothed_state
        smoothed_confidence = temporal_result.confidence
        
        # 5. STATE MACHINE VALIDATION
        fsm_result = self.state_machine.update(
            timestamp=timestamp,
            candidate_state=smoothed_state,
            features=features.to_dict()
        )
        
        final_state = fsm_result.state
        is_valid_transition = fsm_result.is_valid_transition
        
        # 6. CONFIDENCE CALCULATION (TEK KAYNAK)
        final_confidence = calculate_confidence_score(
            features=features,
            thresholds=self.thresholds,
            predicted_state=final_state,
            previous_state=fsm_result.previous_state
        )
        
        # 7. REASONING CHAIN
        reasoning = self._build_reasoning_chain(
            features=features,
            raw_state=raw_state,
            smoothed_state=smoothed_state,
            final_state=final_state,
            temporal_reasoning=temporal_result.reasoning,
            fsm_result=fsm_result
        )
        
        # 8. CREATE RESULT
        result = {
            'player_id': self.player_id,
            'timestamp': timestamp,
            'movement_state': final_state,
            'confidence': final_confidence,
            'raw_state': raw_state,
            'smoothed_state': smoothed_state,
            'is_valid_transition': is_valid_transition,
            'features': features.to_dict(),
            'reasoning': reasoning,
            'data_quality': features.data_quality_score
        }
        
        # 9. UPDATE STATISTICS
        self._update_stats(result)
        
        # 10. LOGGING
        if self.enable_logging and self.logger:
            self.logger.log_classification(
                timestamp=timestamp,
                player_id=self.player_id,
                features=features.to_dict(),
                thresholds=self.thresholds.to_dict(),
                raw_state=raw_state,
                final_state=final_state,
                confidence=final_confidence,
                reasoning=reasoning
            )
        
        return result
    
    def _classify_from_features(self, features: MovementFeatures) -> str:
        """
        Feature'lardan raw state classification.
        
        Threshold'lara göre state belirler:
        1. Jump detection (priority - bbox analysis)
        2. Speed-based classification (idle/walking/running)
        """
        # 1. JUMP DETECTION (highest priority)
        if features.bbox_height_change is not None:
            # Jumping up (bbox shrinking)
            if features.bbox_height_change < -self.thresholds.jump_bbox_shrink_min:
                if features.speed is not None and features.speed >= self.thresholds.jump_speed_min:
                    return "jumping"
        
        # 2. SPEED-BASED CLASSIFICATION
        if features.speed_smoothed is not None:
            speed = features.speed_smoothed
            
            # Running
            if speed >= self.thresholds.run_speed_min:
                return "running"
            
            # Walking
            elif speed >= self.thresholds.walk_speed_min:
                return "walking"
            
            # Idle
            else:
                return "idle"
        
        # 3. FALLBACK (no valid features)
        return "idle"
    
    def _calculate_raw_confidence(self, 
                                  features: MovementFeatures,
                                  raw_state: str) -> float:
        """
        Raw classification için basit confidence hesabı.
        
        Final confidence calculate_confidence_score() ile yapılır.
        Bu sadece temporal filter için intermediate confidence.
        """
        if not features.is_valid():
            return 0.3
        
        confidence = features.data_quality_score
        
        # Speed stability bonus
        if features.is_speed_stable:
            confidence += 0.1
        
        # Bbox stability bonus
        if features.bbox_height_stable:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _build_reasoning_chain(self,
                              features: MovementFeatures,
                              raw_state: str,
                              smoothed_state: str,
                              final_state: str,
                              temporal_reasoning: str,
                              fsm_result) -> str:
        """
        ML interpretability için reasoning chain oluşturur.
        
        Returns:
            Human-readable reasoning string
        """
        parts = []
        
        # 1. Feature summary
        if features.speed_smoothed is not None:
            parts.append(f"speed={features.speed_smoothed:.2f}m/s")
        if features.acceleration is not None:
            parts.append(f"accel={features.acceleration:.2f}m/s²")
        if features.bbox_height_change is not None:
            parts.append(f"bbox_change={features.bbox_height_change:.3f}")
        
        # 2. Classification pipeline
        parts.append(f"raw={raw_state}")
        
        if smoothed_state != raw_state:
            parts.append(f"smoothed={smoothed_state}({temporal_reasoning[:30]}...)")
        
        if final_state != smoothed_state:
            if fsm_result.transition_info:
                parts.append(f"fsm={final_state}({fsm_result.transition_info.reason})")
        
        # 3. State duration
        parts.append(f"duration={fsm_result.duration_frames}f")
        
        return " | ".join(parts)
    
    def _create_low_quality_result(self,
                                  timestamp: int,
                                  features: MovementFeatures) -> Dict:
        """
        Düşük kaliteli feature'lar için fallback result.
        """
        return {
            'player_id': self.player_id,
            'timestamp': timestamp,
            'movement_state': 'idle',
            'confidence': 0.2,
            'raw_state': 'idle',
            'smoothed_state': 'idle',
            'is_valid_transition': True,
            'features': features.to_dict(),
            'reasoning': f"low_quality_data(quality={features.data_quality_score:.2f})",
            'data_quality': features.data_quality_score
        }
    
    def _update_stats(self, result: Dict):
        """İstatistikleri güncelle"""
        self.frame_count += 1
        self.classification_stats['total_frames'] += 1
        
        # State counts
        state = result['movement_state']
        self.classification_stats['state_counts'][state] = \
            self.classification_stats['state_counts'].get(state, 0) + 1
        
        # Transition validity
        if result['is_valid_transition']:
            self.classification_stats['valid_transitions'] += 1
        else:
            self.classification_stats['invalid_transitions'] += 1
        
        # Low confidence tracking
        if result['confidence'] < self.thresholds.confidence_threshold_min:
            self.classification_stats['low_confidence_frames'] += 1
    
    def classify_batch(self,
                      player,
                      start_frame: int,
                      end_frame: int,
                      bbox_height_dict: Dict[int, float]) -> List[Dict]:
        """
        Bir zaman aralığı için batch sınıflandırma.
        
        Offline analysis ve ML training için kullanışlı.
        
        Args:
            player: Player objesi
            start_frame: Başlangıç frame
            end_frame: Bitiş frame (inclusive)
            bbox_height_dict: {timestamp: bbox_height} dictionary
        
        Returns:
            List of classification results
        
        Example:
            >>> bbox_dict = {i: 200.0 for i in range(100, 200)}
            >>> results = classifier.classify_batch(
            ...     player=player_obj,
            ...     start_frame=100,
            ...     end_frame=199,
            ...     bbox_height_dict=bbox_dict
            ... )
            >>> print(f"Classified {len(results)} frames")
        """
        results = []
        
        for timestamp in range(start_frame, end_frame + 1):
            if timestamp not in bbox_height_dict:
                continue
            
            try:
                result = self.classify_frame(
                    player=player,
                    timestamp=timestamp,
                    bbox_height=bbox_height_dict[timestamp]
                )
                results.append(result)
            except Exception as e:
                # Log error but continue processing
                print(f"Error at frame {timestamp}: {e}")
                continue
        
        return results
    
    def export_state_timeline(self,
                            start_frame: int,
                            end_frame: int) -> Dict:
        """
        ML analizi için state timeline export.
        
        Returns:
            {
                'player_id': int,
                'start_frame': int,
                'end_frame': int,
                'thresholds': dict,
                'frames': [int],
                'states': [str],
                'confidences': [float],
                'transitions': [
                    {
                        'from': str,
                        'to': str,
                        'frame': int,
                        'reason': str
                    }
                ],
                'statistics': dict
            }
        """
        # Get state history from state machine
        state_timeline = self.state_machine.get_state_timeline()
        
        # Filter by frame range
        filtered_timeline = [
            (frame, state) for frame, state in state_timeline
            if start_frame <= frame <= end_frame
        ]
        
        if len(filtered_timeline) == 0:
            return {
                'player_id': self.player_id,
                'start_frame': start_frame,
                'end_frame': end_frame,
                'frames': [],
                'states': [],
                'confidences': [],
                'transitions': []
            }
        
        frames = [frame for frame, _ in filtered_timeline]
        states = [state for _, state in filtered_timeline]
        
        # Get transitions
        transitions = []
        transition_history = self.state_machine.get_transition_history()
        
        for trans in transition_history:
            if start_frame <= trans.timestamp <= end_frame:
                transitions.append({
                    'from': trans.from_state,
                    'to': trans.to_state,
                    'frame': trans.timestamp,
                    'reason': trans.reason,
                    'valid': trans.is_valid
                })
        
        return {
            'player_id': self.player_id,
            'start_frame': start_frame,
            'end_frame': end_frame,
            'thresholds': {
                'preset': self.thresholds.preset_name,
                'created_at': self.thresholds.created_at
            },
            'frames': frames,
            'states': states,
            'transitions': transitions,
            'statistics': self.get_statistics()
        }
    
    def get_statistics(self) -> Dict:
        """Sınıflandırma istatistiklerini döndürür"""
        stats = dict(self.classification_stats)
        
        # Add percentages
        if stats['total_frames'] > 0:
            stats['valid_transition_rate'] = (
                stats['valid_transitions'] / stats['total_frames']
            )
            stats['low_confidence_rate'] = (
                stats['low_confidence_frames'] / stats['total_frames']
            )
        
        return stats
    
    def reset(self):
        """
        Tüm buffer'ları ve state'leri sıfırla.
        
        Kullanım:
        - Yeni maç başlangıcı
        - Player sahadan çıktı
        - Pipeline'ı sıfırlamak gerekiyor
        """
        self.feature_extractor.reset_player_history(self.player_id)
        self.temporal_filter.reset_player(self.player_id)
        self.state_machine.reset()
        
        self.frame_count = 0
        self.classification_stats = {
            'total_frames': 0,
            'valid_transitions': 0,
            'invalid_transitions': 0,
            'state_counts': {},
            'low_confidence_frames': 0
        }
        
        if self.logger:
            self.logger.clear()
    
    def export_config(self) -> Dict:
        """
        Classifier konfigürasyonunu export eder (reproducibility için).
        
        Returns:
            Full config dictionary
        """
        return {
            'player_id': self.player_id,
            'config': {
                'fps': self.velocity_analyzer.fps,
                'temporal_window': self.thresholds.temporal_window_size,
                'min_state_duration': self.thresholds.min_state_duration_frames
            },
            'thresholds': self.thresholds.to_dict(),
            'state_machine': self.state_machine.export_transition_matrix(),
            'created_at': datetime.now().isoformat()
        }
    
    def save_config(self, filepath: str):
        """Konfigürasyonu JSON dosyasına kaydet"""
        config = self.export_config()
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)


# Convenience function for quick classification
def classify_player_movement(
    velocity_analyzer,
    player,
    timestamp: int,
    bbox_height: float,
    player_id: int,
    preset: str = "default"
) -> Dict:
    """
    Tek satırda classification (quick usage).
    
    Example:
        >>> from classifier import classify_player_movement
        >>> result = classify_player_movement(
        ...     velocity_analyzer=va,
        ...     player=player_obj,
        ...     timestamp=100,
        ...     bbox_height=320.5,
        ...     player_id=7
        ... )
        >>> print(result['movement_state'])
    """
    thresholds = ThresholdSet.from_preset(preset)
    
    classifier = BasicMovementClassifier(
        velocity_analyzer=velocity_analyzer,
        player_id=player_id,
        thresholds=thresholds
    )
    
    return classifier.classify_frame(player, timestamp, bbox_height)


# Example usage
if __name__ == "__main__":
    print("=== Basic Movement Classifier Test ===\n")
    
    # Mock VelocityAnalyzer
    class MockVelocityAnalyzer:
        def __init__(self):
            self.fps = 30
        
        def calculate_speed(self, player, timestamp, window=1):
            # Simulate varying speeds
            if timestamp < 10:
                return 0.3  # idle
            elif timestamp < 20:
                return 1.5  # walking
            elif timestamp < 30:
                return 6.0  # running
            else:
                return 2.0  # walking back
        
        def calculate_speed_smoothed(self, player, timestamp, window=5):
            return self.calculate_speed(player, timestamp, window)
        
        def calculate_acceleration(self, player, timestamp, window=3):
            return 0.5
    
    # Mock Player
    class MockPlayer:
        def __init__(self):
            self.id = 7
            self.positions = {i: (100 + i*2, 200) for i in range(100)}
    
    # Initialize
    va = MockVelocityAnalyzer()
    player = MockPlayer()
    
    classifier = BasicMovementClassifier(
        velocity_analyzer=va,
        player_id=7,
        enable_logging=False
    )
    
    # Test classification
    print("Frame | State    | Confidence | Reasoning")
    print("-" * 70)
    
    for timestamp in range(0, 35, 5):
        result = classifier.classify_frame(
            player=player,
            timestamp=timestamp,
            bbox_height=200.0
        )
        
        print(f"{timestamp:5d} | {result['movement_state']:8s} | "
              f"{result['confidence']:10.2f} | {result['reasoning'][:40]}...")
    
    # Statistics
    print("\n=== Statistics ===")
    stats = classifier.get_statistics()
    print(f"Total frames: {stats['total_frames']}")
    print(f"Valid transitions: {stats['valid_transitions']}")
    print(f"State distribution:")
    for state, count in stats['state_counts'].items():
        print(f"  {state}: {count}")
    
    # Export timeline
    print("\n=== Export Timeline ===")
    timeline = classifier.export_state_timeline(0, 34)
    print(f"Frames: {len(timeline['frames'])}")
    print(f"Transitions: {len(timeline['transitions'])}")
    print(f"States: {timeline['states']}")