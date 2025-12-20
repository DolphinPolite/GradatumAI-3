"""
Basketball Movement Temporal Filtering

Bu modül gürültülü (noisy) state sınıflandırmalarını temporal olarak
stabilize eder.

⚠️ KRİTİK SORUMLULUK AYIRIMI:
- TemporalFilter: SADECE gürültü azaltma (smoothing)
- StateMachine: Fiziksel geçerlilik kontrolü (transition validation)

Bu modül şunları YAPMAZ:
❌ Invalid transition blocking
❌ Fiziksel kısıtlar kontrolü
❌ State machine mantığı

Bu modül şunları YAPAR:
✅ Sliding window majority voting
✅ Minimum state duration enforcement
✅ Hysteresis dampening
✅ Flickering önleme

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Deque
from collections import deque, Counter
from dataclasses import dataclass


@dataclass
class TemporalFilterResult:
    """
    Temporal filtering sonucu.
    
    Attributes:
        smoothed_state: Filtrelenmiş state
        confidence: Smoothing confidence (0-1)
        raw_state: Filtering öncesi state
        reasoning: Hangi smoothing teknikleri uygulandı
        votes: Majority voting detayları (debug için)
    """
    smoothed_state: str
    confidence: float
    raw_state: str
    reasoning: str
    votes: Optional[Dict[str, int]] = None
    
    def to_dict(self) -> Dict:
        """ML logging için dictionary export"""
        return {
            'smoothed_state': self.smoothed_state,
            'confidence': self.confidence,
            'raw_state': self.raw_state,
            'reasoning': self.reasoning,
            'votes': self.votes
        }


class TemporalStateFilter:
    """
    Rule-based temporal smoothing - SADECE gürültü azaltma.
    
    Kullanılan teknikler:
    1. Sliding Window Majority Voting
       - Son N frame'deki en çok görünen state seçilir
       
    2. Minimum State Duration Enforcement
       - Bir state en az X frame sürmeli
       - Kısa süreli "blip"ler filtrelenir
       
    3. Hysteresis-Based Transition Dampening
       - Durum değiştirmek için "çift onay" gerekir
       - Flickering önlenir
    
    4. Confidence-Based Weighting
       - Yüksek confidence'lı state'ler daha fazla ağırlık alır
    
    ⚠️ SORUMLULUK: Bu sınıf SADECE smoothing yapar.
    Fiziksel geçerlilik kontrolü StateMachine'de yapılır.
    
    Design Principles:
    - Single Responsibility: Sadece gürültü azaltma
    - ML-Friendly: Her karar reasoning ile birlikte döner
    - Explainable: Hangi teknik uygulandı açık
    """
    
    def __init__(self,
                 window_size: int = 7,
                 min_duration: int = 5,
                 hysteresis_frames: int = 2,
                 use_confidence_weighting: bool = True):
        """
        Args:
            window_size: Majority voting pencere boyutu (tek sayı olmalı)
            min_duration: Minimum state duration (frame)
            hysteresis_frames: Durum değiştirmek için kaç frame "onay" gerekir
            use_confidence_weighting: Confidence skorları kullanılsın mı?
        """
        self.window_size = window_size
        self.min_duration = min_duration
        self.hysteresis_frames = hysteresis_frames
        self.use_confidence_weighting = use_confidence_weighting
        
        # State history buffer (her player için ayrı)
        self._state_history: Dict[int, Deque[Tuple[str, float]]] = {}
        
        # Current state tracking
        self._current_state: Dict[int, str] = {}
        self._state_start_frame: Dict[int, int] = {}
        
        # Hysteresis tracking
        self._transition_candidate: Dict[int, Optional[str]] = {}
        self._transition_vote_count: Dict[int, int] = {}
    
    def _init_player_buffers(self, player_id: int, current_frame: int):
        """Player için buffer'ları initialize eder"""
        if player_id not in self._state_history:
            self._state_history[player_id] = deque(maxlen=self.window_size)
            self._current_state[player_id] = "idle"
            self._state_start_frame[player_id] = current_frame
            self._transition_candidate[player_id] = None
            self._transition_vote_count[player_id] = 0
    
    def apply_smoothing(self,
                       player_id: int,
                       timestamp: int,
                       raw_state: str,
                       raw_confidence: float) -> TemporalFilterResult:
        """
        Temporal smoothing uygula.
        
        Args:
            player_id: Player ID
            timestamp: Frame index
            raw_state: Feature-based raw classification
            raw_confidence: Raw classification confidence (0-1)
        
        Returns:
            TemporalFilterResult with smoothed state
        
        Example:
            >>> filter = TemporalStateFilter()
            >>> result = filter.apply_smoothing(
            ...     player_id=7,
            ...     timestamp=100,
            ...     raw_state="running",
            ...     raw_confidence=0.75
            ... )
            >>> print(f"Smoothed: {result.smoothed_state}")
            >>> print(f"Reasoning: {result.reasoning}")
        """
        # Initialize buffers
        self._init_player_buffers(player_id, timestamp)
        
        # Add to history
        self._state_history[player_id].append((raw_state, raw_confidence))
        
        # Apply smoothing pipeline
        smoothed_state, confidence, reasoning, votes = self._smooth_pipeline(
            player_id, timestamp, raw_state, raw_confidence
        )
        
        return TemporalFilterResult(
            smoothed_state=smoothed_state,
            confidence=confidence,
            raw_state=raw_state,
            reasoning=reasoning,
            votes=votes
        )
    
    def _smooth_pipeline(self,
                        player_id: int,
                        timestamp: int,
                        raw_state: str,
                        raw_confidence: float) -> Tuple[str, float, str, Dict]:
        """
        Smoothing pipeline: majority voting → min duration → hysteresis
        
        Returns:
            (smoothed_state, confidence, reasoning, votes)
        """
        reasoning_steps = []
        
        # 1. MAJORITY VOTING
        majority_state, votes = self._majority_voting(player_id)
        reasoning_steps.append(f"majority={majority_state}")
        
        # 2. MINIMUM DURATION CHECK
        current_state = self._current_state[player_id]
        frames_in_current = timestamp - self._state_start_frame[player_id]
        
        if frames_in_current < self.min_duration:
            # Too short - stay in current state
            if majority_state != current_state:
                reasoning_steps.append(
                    f"min_duration_enforced(frames={frames_in_current}<{self.min_duration})"
                )
                smoothed_state = current_state
            else:
                smoothed_state = majority_state
        else:
            smoothed_state = majority_state
        
        # 3. HYSTERESIS
        if smoothed_state != current_state:
            # Potential transition - apply hysteresis
            smoothed_state, hysteresis_reason = self._apply_hysteresis(
                player_id, smoothed_state, current_state
            )
            reasoning_steps.append(hysteresis_reason)
        else:
            # No transition - reset hysteresis
            self._reset_hysteresis(player_id)
        
        # 4. UPDATE STATE
        if smoothed_state != current_state:
            self._current_state[player_id] = smoothed_state
            self._state_start_frame[player_id] = timestamp
            reasoning_steps.append(f"state_changed({current_state}→{smoothed_state})")
        
        # 5. CONFIDENCE CALCULATION
        confidence = self._calculate_smoothing_confidence(
            player_id, smoothed_state, raw_confidence
        )
        
        reasoning = " | ".join(reasoning_steps)
        
        return smoothed_state, confidence, reasoning, votes
    
    def _majority_voting(self, player_id: int) -> Tuple[str, Dict[str, int]]:
        """
        Sliding window majority voting.
        
        Confidence-weighted ise yüksek confidence'lı state'ler
        daha fazla oy alır.
        
        Returns:
            (majority_state, vote_counts)
        """
        history = self._state_history[player_id]
        
        if len(history) == 0:
            return "idle", {"idle": 1}
        
        if self.use_confidence_weighting:
            # Confidence-weighted voting
            votes = {}
            for state, confidence in history:
                weight = max(0.1, confidence)  # Minimum weight
                votes[state] = votes.get(state, 0) + weight
        else:
            # Simple counting
            states = [state for state, _ in history]
            votes = dict(Counter(states))
        
        # Get majority
        majority_state = max(votes.items(), key=lambda x: x[1])[0]
        
        return majority_state, votes
    
    def _apply_hysteresis(self,
                         player_id: int,
                         candidate_state: str,
                         current_state: str) -> Tuple[str, str]:
        """
        Hysteresis-based transition dampening.
        
        Durum değiştirmek için birden fazla frame "onay" gerekir.
        Bu flickering'i önler.
        
        Args:
            candidate_state: Yeni state adayı
            current_state: Mevcut state
        
        Returns:
            (final_state, reasoning)
        """
        # Transition candidate tracking
        prev_candidate = self._transition_candidate[player_id]
        
        if candidate_state == prev_candidate:
            # Same candidate - increment vote
            self._transition_vote_count[player_id] += 1
            vote_count = self._transition_vote_count[player_id]
            
            if vote_count >= self.hysteresis_frames:
                # Enough votes - allow transition
                self._reset_hysteresis(player_id)
                return (
                    candidate_state,
                    f"hysteresis_passed(votes={vote_count}/{self.hysteresis_frames})"
                )
            else:
                # Not enough votes yet - stay in current
                return (
                    current_state,
                    f"hysteresis_waiting(votes={vote_count}/{self.hysteresis_frames})"
                )
        else:
            # New candidate - reset counter
            self._transition_candidate[player_id] = candidate_state
            self._transition_vote_count[player_id] = 1
            return (
                current_state,
                f"hysteresis_new_candidate({candidate_state})"
            )
    
    def _reset_hysteresis(self, player_id: int):
        """Hysteresis tracking'i sıfırla"""
        self._transition_candidate[player_id] = None
        self._transition_vote_count[player_id] = 0
    
    def _calculate_smoothing_confidence(self,
                                       player_id: int,
                                       smoothed_state: str,
                                       raw_confidence: float) -> float:
        """
        Smoothing sonrası confidence hesapla.
        
        Factors:
        - Raw confidence (50%)
        - Majority strength (30%)
        - State duration stability (20%)
        """
        history = self._state_history[player_id]
        
        if len(history) == 0:
            return raw_confidence
        
        # 1. Raw confidence (50%)
        conf_raw = raw_confidence * 0.5
        
        # 2. Majority strength (30%)
        _, votes = self._majority_voting(player_id)
        total_votes = sum(votes.values())
        majority_votes = votes.get(smoothed_state, 0)
        
        if total_votes > 0:
            majority_strength = majority_votes / total_votes
            conf_majority = majority_strength * 0.3
        else:
            conf_majority = 0.0
        
        # 3. State duration stability (20%)
        current_frame = len(history)
        state_start = self._state_start_frame[player_id]
        duration = current_frame - state_start
        
        # Longer duration = higher confidence
        duration_factor = min(duration / self.min_duration, 1.0)
        conf_duration = duration_factor * 0.2
        
        total_confidence = conf_raw + conf_majority + conf_duration
        
        return float(np.clip(total_confidence, 0.0, 1.0))
    
    def get_current_state(self, player_id: int) -> Optional[str]:
        """Player'ın mevcut smoothed state'ini döndürür"""
        return self._current_state.get(player_id)
    
    def get_state_duration(self, player_id: int, current_frame: int) -> int:
        """Mevcut state'in süresi (frame)"""
        if player_id not in self._state_start_frame:
            return 0
        return current_frame - self._state_start_frame[player_id]
    
    def reset_player(self, player_id: int):
        """Player için tüm buffer'ları sıfırla"""
        if player_id in self._state_history:
            self._state_history[player_id].clear()
        if player_id in self._current_state:
            del self._current_state[player_id]
        if player_id in self._state_start_frame:
            del self._state_start_frame[player_id]
        self._reset_hysteresis(player_id)
    
    def get_history_summary(self, player_id: int) -> Dict:
        """Player için history özetini döndürür (debug için)"""
        if player_id not in self._state_history:
            return {}
        
        history = list(self._state_history[player_id])
        
        return {
            'history_size': len(history),
            'current_state': self._current_state.get(player_id),
            'state_duration': len(history) - self._state_start_frame.get(player_id, 0),
            'recent_states': [state for state, _ in history[-5:]],
            'transition_candidate': self._transition_candidate.get(player_id),
            'transition_votes': self._transition_vote_count.get(player_id, 0)
        }


class HysteresisManager:
    """
    Durum geçişlerinde hysteresis uygular (standalone kullanım).
    
    Hysteresis: Geriye dönüş için farklı eşik kullanır.
    
    Örnek: walk → run geçişi için 2.5 m/s eşiği varsa,
    geri dönüş (run → walk) için 2.2 m/s kullanılır.
    
    Bu flickering'i önler.
    
    ⚠️ NOT: Bu sınıf genelde TemporalStateFilter içinde kullanılır.
    Standalone kullanım nadirdir.
    """
    
    def __init__(self, margin_ratio: float = 0.1):
        """
        Args:
            margin_ratio: Hysteresis margin oranı (0-1)
                0.1 = %10 margin (2.5 m/s → 2.25 m/s geri dönüş için)
        """
        self.margin_ratio = margin_ratio
        self._last_state: Dict[int, str] = {}
    
    def apply_hysteresis_to_threshold(self,
                                     player_id: int,
                                     current_state: str,
                                     candidate_state: str,
                                     threshold_value: float) -> float:
        """
        Threshold'a hysteresis uygula.
        
        Args:
            player_id: Player ID
            current_state: Mevcut state
            candidate_state: Aday state
            threshold_value: Base threshold
        
        Returns:
            Adjusted threshold (hysteresis uygulanmış)
        
        Example:
            >>> manager = HysteresisManager(margin_ratio=0.1)
            >>> # walk → run: normal threshold
            >>> adjusted = manager.apply_hysteresis_to_threshold(
            ...     player_id=7,
            ...     current_state="walking",
            ...     candidate_state="running",
            ...     threshold_value=2.5
            ... )
            >>> print(adjusted)  # 2.5
            >>>
            >>> # run → walk: reduced threshold
            >>> adjusted = manager.apply_hysteresis_to_threshold(
            ...     player_id=7,
            ...     current_state="running",
            ...     candidate_state="walking",
            ...     threshold_value=2.5
            ... )
            >>> print(adjusted)  # 2.25 (10% reduction)
        """
        last_state = self._last_state.get(player_id, current_state)
        
        # State değişimi var mı?
        if candidate_state != current_state:
            # Ascending transition (idle → walk → run)
            if self._is_ascending_transition(current_state, candidate_state):
                adjusted = threshold_value
            # Descending transition (run → walk → idle)
            else:
                margin = threshold_value * self.margin_ratio
                adjusted = threshold_value - margin
        else:
            # No transition
            adjusted = threshold_value
        
        # Update last state
        self._last_state[player_id] = current_state
        
        return adjusted
    
    def _is_ascending_transition(self, from_state: str, to_state: str) -> bool:
        """Ascending transition mı? (activity arttı mı?)"""
        state_order = {
            "idle": 0,
            "walking": 1,
            "running": 2,
            "jumping": 3
        }
        
        from_level = state_order.get(from_state, 0)
        to_level = state_order.get(to_state, 0)
        
        return to_level > from_level


# Convenience function
def smooth_state_sequence(
    states: List[str],
    confidences: List[float],
    window_size: int = 7,
    min_duration: int = 5
) -> List[str]:
    """
    Batch smoothing - state dizisini smooth eder.
    
    Offline analysis için kullanışlı.
    
    Args:
        states: Raw state listesi
        confidences: Confidence listesi
        window_size: Smoothing pencere boyutu
        min_duration: Minimum state duration
    
    Returns:
        Smoothed state listesi
    
    Example:
        >>> raw = ["idle", "walk", "idle", "walk", "walk", "walk", "run"]
        >>> conf = [0.7, 0.6, 0.5, 0.8, 0.8, 0.9, 0.7]
        >>> smoothed = smooth_state_sequence(raw, conf)
        >>> print(smoothed)
        ['idle', 'idle', 'idle', 'walk', 'walk', 'walk', 'run']
    """
    if len(states) != len(confidences):
        raise ValueError("States and confidences must have same length")
    
    filter = TemporalStateFilter(
        window_size=window_size,
        min_duration=min_duration
    )
    
    smoothed = []
    player_id = 0  # Dummy player ID
    
    for timestamp, (state, conf) in enumerate(zip(states, confidences)):
        result = filter.apply_smoothing(
            player_id=player_id,
            timestamp=timestamp,
            raw_state=state,
            raw_confidence=conf
        )
        smoothed.append(result.smoothed_state)
    
    return smoothed


# Example usage
if __name__ == "__main__":
    print("=== Temporal Filter Test ===\n")
    
    # Test data: noisy state sequence
    raw_states = [
        "idle", "idle", "walking", "idle", "walking",  # Noisy start
        "walking", "walking", "running", "walking", "running",  # Flickering
        "running", "running", "running", "jumping", "running",  # Short blip
        "running", "walking", "walking", "walking", "idle"  # Transition
    ]
    
    confidences = [
        0.7, 0.8, 0.6, 0.5, 0.7,
        0.8, 0.9, 0.7, 0.6, 0.8,
        0.9, 0.9, 0.9, 0.5, 0.8,
        0.9, 0.8, 0.9, 0.8, 0.7
    ]
    
    # Apply filtering
    filter = TemporalStateFilter(
        window_size=7,
        min_duration=5,
        hysteresis_frames=2
    )
    
    player_id = 7
    smoothed_states = []
    
    print("Frame | Raw State | Smoothed | Reasoning")
    print("-" * 80)
    
    for timestamp, (raw_state, conf) in enumerate(zip(raw_states, confidences)):
        result = filter.apply_smoothing(
            player_id=player_id,
            timestamp=timestamp,
            raw_state=raw_state,
            raw_confidence=conf
        )
        
        smoothed_states.append(result.smoothed_state)
        
        print(f"{timestamp:5d} | {raw_state:9s} | {result.smoothed_state:9s} | "
              f"{result.reasoning[:50]}...")
    
    print("\n=== Summary ===")
    print(f"Raw states:      {' '.join(raw_states)}")
    print(f"Smoothed states: {' '.join(smoothed_states)}")
    
    # Count changes
    raw_changes = sum(1 for i in range(1, len(raw_states)) 
                     if raw_states[i] != raw_states[i-1])
    smoothed_changes = sum(1 for i in range(1, len(smoothed_states)) 
                          if smoothed_states[i] != smoothed_states[i-1])
    
    print(f"\nState changes:")
    print(f"  Raw: {raw_changes}")
    print(f"  Smoothed: {smoothed_changes}")
    print(f"  Reduction: {(1 - smoothed_changes/raw_changes)*100:.1f}%")