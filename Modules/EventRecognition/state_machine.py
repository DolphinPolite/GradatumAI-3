"""
Basketball Movement State Machine

Bu modül oyuncu hareket state'lerinin fiziksel geçerliliğini kontrol eder.

⚠️ KRİTİK SORUMLULUK AYIRIMI:
- TemporalFilter: Gürültü azaltma (smoothing)
- StateMachine: Fiziksel geçerlilik kontrolü (BU DOSYA)

Bu modül şunları YAPAR:
✅ Invalid transition blocking
✅ Fiziksel kısıtlar kontrolü
✅ State transition matrix
✅ State duration tracking
✅ Landing detection (jumping → landing → idle/walk/run)

Bu modül şunları YAPMAZ:
❌ Temporal smoothing → TemporalFilter'da
❌ Feature extraction → Features.py'de
❌ Confidence calculation → Utils.py'de

Author: Basketball Analytics Pipeline
Version: 1.0.0
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class MovementState(Enum):
    """
    Oyuncu hareket state'leri.
    
    Enum kullanımı type safety sağlar.
    """
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    JUMPING = "jumping"
    LANDING = "landing"  # Jump'tan sonra geçiş state'i
    
    def __str__(self):
        return self.value


@dataclass
class StateTransition:
    """
    State transition bilgisi.
    
    Attributes:
        from_state: Önceki state
        to_state: Yeni state
        timestamp: Geçiş zamanı (frame)
        is_valid: Transition fiziksel olarak geçerli mi?
        reason: Transition sebebi veya red sebebi
    """
    from_state: str
    to_state: str
    timestamp: int
    is_valid: bool
    reason: str
    
    def to_dict(self) -> Dict:
        """ML logging için dictionary export"""
        return {
            'from_state': self.from_state,
            'to_state': self.to_state,
            'timestamp': self.timestamp,
            'is_valid': self.is_valid,
            'reason': self.reason
        }


@dataclass
class StateMachineResult:
    """
    State machine validation sonucu.
    
    Attributes:
        state: Final validated state
        is_valid_transition: Transition geçerli miydi?
        previous_state: Önceki state
        duration_frames: Mevcut state'te kaç frame
        transition_info: Transition detayları (opsiyonel)
    """
    state: str
    is_valid_transition: bool
    previous_state: Optional[str]
    duration_frames: int
    transition_info: Optional[StateTransition] = None
    
    def to_dict(self) -> Dict:
        """ML logging için dictionary export"""
        result = {
            'state': self.state,
            'is_valid_transition': self.is_valid_transition,
            'previous_state': self.previous_state,
            'duration_frames': self.duration_frames
        }
        if self.transition_info:
            result['transition'] = self.transition_info.to_dict()
        return result


class MovementStateMachine:
    """
    Basketball oyuncu hareket state machine.
    
    Finite State Machine (FSM) implementasyonu.
    Fiziksel olarak geçerli state transition'ları enforce eder.
    
    States:
    - IDLE: Durağan (standing still)
    - WALKING: Yürüme (slow movement)
    - RUNNING: Koşma (fast movement)
    - JUMPING: Sıçrama (airborne)
    - LANDING: İniş (jump'tan sonra geçiş)
    
    Valid Transitions:
    - idle ↔ walking
    - walking ↔ running
    - walking → jumping
    - running → jumping
    - jumping → landing
    - landing → idle/walking/running
    
    Invalid Transitions (fiziksel olarak imkansız):
    - idle → running (direkt sprint olamaz)
    - idle → jumping (durağandan direkt sıçranmaz)
    - jumping → running (landing olmadan sprint olamaz)
    - running → idle (ani durma, önce walking olmalı)
    
    Design Principles:
    - Fiziksel gerçekçilik (basketbol biomechanics)
    - Explainable transitions (her red için sebep)
    - ML-friendly (transition matrix export edilebilir)
    """
    
    def __init__(self,
                 player_id: int,
                 allow_landing_state: bool = True,
                 strict_mode: bool = False):
        """
        Args:
            player_id: Player ID (tracking için)
            allow_landing_state: Landing state kullanılsın mı?
                True: jumping → landing → walk/run (gerçekçi)
                False: jumping → walk/run direkt (basit)
            strict_mode: Strict fiziksel kısıtlar
                True: running → idle geçişi yasak
                False: running → idle izinli (ani durma)
        """
        self.player_id = player_id
        self.allow_landing_state = allow_landing_state
        self.strict_mode = strict_mode
        
        # Current state
        self.current_state = MovementState.IDLE.value
        self.state_start_frame = 0
        
        # State history
        self.state_history: List[Tuple[int, str]] = []  # (timestamp, state)
        self.transition_history: List[StateTransition] = []
        
        # Jump tracking
        self.jump_start_frame: Optional[int] = None
        self.is_in_landing_phase = False
        
        # Transition matrix (geçerli transition'lar)
        self.transition_matrix = self._build_transition_matrix()
    
    def _build_transition_matrix(self) -> Dict[str, Set[str]]:
        """
        Valid state transition matrix'i oluşturur.
        
        Returns:
            {from_state: {valid_to_states}}
        
        Example:
            {
                "idle": {"idle", "walking"},
                "walking": {"idle", "walking", "running", "jumping"},
                ...
            }
        """
        # Base transitions (her mod için geçerli)
        matrix = {
            "idle": {"idle", "walking"},
            "walking": {"idle", "walking", "running", "jumping"},
            "running": {"walking", "running", "jumping"},
            "jumping": {"jumping"},  # Can only go to landing/walking/running
        }
        
        # Landing state handling
        if self.allow_landing_state:
            matrix["jumping"].add("landing")
            matrix["landing"] = {"landing", "idle", "walking", "running"}
        else:
            matrix["jumping"].update({"walking", "running"})
        
        # Strict mode adjustments
        if not self.strict_mode:
            # Allow running → idle in non-strict mode
            matrix["running"].add("idle")
        
        return matrix
    
    def update(self,
              timestamp: int,
              candidate_state: str,
              features: Optional[Dict] = None) -> StateMachineResult:
        """
        State machine'i güncelle ve transition'ı validate et.
        
        Pipeline:
        1. Candidate state'i kontrol et
        2. Transition geçerliliğini validate et
        3. Special case'leri handle et (landing detection)
        4. State'i güncelle veya reddet
        
        Args:
            timestamp: Frame index
            candidate_state: TemporalFilter'dan gelen smoothed state
            features: Opsiyonel feature dict (landing detection için)
        
        Returns:
            StateMachineResult with validated state
        
        Example:
            >>> fsm = MovementStateMachine(player_id=7)
            >>> result = fsm.update(
            ...     timestamp=100,
            ...     candidate_state="running",
            ...     features={'speed': 6.5, 'bbox_height_change': -0.02}
            ... )
            >>> print(f"State: {result.state}")
            >>> print(f"Valid: {result.is_valid_transition}")
        """
        previous_state = self.current_state
        
        # 1. LANDING DETECTION (special case)
        if self.allow_landing_state and self.current_state == "jumping":
            landing_detected = self._detect_landing(timestamp, features)
            
            if landing_detected:
                candidate_state = "landing"
        
        # 2. TRANSITION VALIDATION
        is_valid, reason = self._validate_transition(
            from_state=previous_state,
            to_state=candidate_state,
            timestamp=timestamp,
            features=features
        )
        
        # 3. STATE UPDATE
        if is_valid:
            final_state = candidate_state
            
            # State değişti mi?
            if final_state != previous_state:
                self._update_state(timestamp, final_state)
                
                # Log transition
                transition = StateTransition(
                    from_state=previous_state,
                    to_state=final_state,
                    timestamp=timestamp,
                    is_valid=True,
                    reason=reason
                )
                self.transition_history.append(transition)
            else:
                transition = None
        else:
            # Invalid transition - stay in previous state
            final_state = previous_state
            
            # Log rejected transition
            transition = StateTransition(
                from_state=previous_state,
                to_state=candidate_state,
                timestamp=timestamp,
                is_valid=False,
                reason=reason
            )
            self.transition_history.append(transition)
        
        # 4. DURATION CALCULATION
        duration = timestamp - self.state_start_frame
        
        return StateMachineResult(
            state=final_state,
            is_valid_transition=is_valid,
            previous_state=previous_state,
            duration_frames=duration,
            transition_info=transition
        )
    
    def _validate_transition(self,
                            from_state: str,
                            to_state: str,
                            timestamp: int,
                            features: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        State transition'ın fiziksel olarak geçerli olup olmadığını kontrol eder.
        
        Returns:
            (is_valid, reason)
        """
        # Same state - always valid
        if from_state == to_state:
            return True, "same_state"
        
        # Check transition matrix
        valid_targets = self.transition_matrix.get(from_state, set())
        
        if to_state not in valid_targets:
            return False, f"invalid_transition({from_state}→{to_state})"
        
        # Special validations
        
        # 1. IDLE → WALKING: Always OK
        if from_state == "idle" and to_state == "walking":
            return True, "idle_to_walking"
        
        # 2. WALKING → RUNNING: Check speed requirement
        if from_state == "walking" and to_state == "running":
            if features and 'speed' in features:
                if features['speed'] < 2.0:  # Too slow for running
                    return False, "insufficient_speed_for_running"
            return True, "walking_to_running"
        
        # 3. WALKING/RUNNING → JUMPING: Check minimum speed
        if to_state == "jumping":
            if features and 'speed' in features:
                if features['speed'] < 0.8:  # Too slow to jump
                    return False, "insufficient_speed_for_jumping"
            
            # Check bbox shrink (jump signal)
            if features and 'bbox_height_change' in features:
                if features['bbox_height_change'] > -0.08:  # Not enough shrink
                    return False, "no_jump_bbox_signal"
            
            # Update jump tracking
            self.jump_start_frame = timestamp
            return True, f"{from_state}_to_jumping"
        
        # 4. JUMPING → LANDING: Check duration
        if from_state == "jumping" and to_state == "landing":
            if self.jump_start_frame is not None:
                jump_duration = timestamp - self.jump_start_frame
                
                if jump_duration < 8:  # Too short (< 0.27s @ 30fps)
                    return False, f"jump_too_short({jump_duration})"
                
                if jump_duration > 30:  # Too long (> 1s @ 30fps)
                    return False, f"jump_too_long({jump_duration})"
            
            self.is_in_landing_phase = True
            return True, "jumping_to_landing"
        
        # 5. LANDING → IDLE/WALKING/RUNNING: Always OK after landing
        if from_state == "landing":
            self.is_in_landing_phase = False
            self.jump_start_frame = None
            return True, f"landing_to_{to_state}"
        
        # 6. RUNNING → WALKING: Always OK (deceleration)
        if from_state == "running" and to_state == "walking":
            return True, "running_to_walking"
        
        # 7. RUNNING → IDLE: Strict mode check
        if from_state == "running" and to_state == "idle":
            if self.strict_mode:
                return False, "running_to_idle_blocked_in_strict_mode"
            else:
                return True, "running_to_idle(sudden_stop)"
        
        # Default: allow if in transition matrix
        return True, f"{from_state}_to_{to_state}"
    
    def _detect_landing(self,
                       timestamp: int,
                       features: Optional[Dict]) -> bool:
        """
        Jump'tan sonra landing detect eder.
        
        Landing indicators:
        - Bbox height büyümeye başladı (growing)
        - Jump duration reasonable (8-30 frames)
        - Speed azalıyor (deceleration)
        
        Returns:
            True if landing detected
        """
        if not features:
            return False
        
        # Check jump duration
        if self.jump_start_frame is None:
            return False
        
        jump_duration = timestamp - self.jump_start_frame
        
        if jump_duration < 8:  # Too early
            return False
        
        # Check bbox growing (landing signal)
        if 'bbox_height_change' in features:
            bbox_change = features['bbox_height_change']
            
            if bbox_change > 0.08:  # Growing > %8
                return True
        
        # Check if jump lasted long enough (max duration reached)
        if jump_duration >= 25:  # ~0.83s @ 30fps
            return True  # Force landing
        
        return False
    
    def _update_state(self, timestamp: int, new_state: str):
        """State'i güncelle ve history'e kaydet"""
        self.state_history.append((timestamp, self.current_state))
        self.current_state = new_state
        self.state_start_frame = timestamp
    
    def get_current_state(self) -> str:
        """Mevcut state'i döndürür"""
        return self.current_state
    
    def get_state_duration(self, current_frame: int) -> int:
        """Mevcut state'in süresi (frame)"""
        return current_frame - self.state_start_frame
    
    def is_valid_transition_pair(self, from_state: str, to_state: str) -> bool:
        """İki state arasındaki transition geçerli mi? (query için)"""
        valid_targets = self.transition_matrix.get(from_state, set())
        return to_state in valid_targets
    
    def get_valid_next_states(self, from_state: str) -> Set[str]:
        """Bir state'ten geçilebilecek state'leri döndürür"""
        return self.transition_matrix.get(from_state, set())
    
    def get_transition_history(self) -> List[StateTransition]:
        """Tüm transition history'sini döndürür"""
        return self.transition_history
    
    def get_state_timeline(self) -> List[Tuple[int, str]]:
        """State timeline'ını döndürür (timestamp, state)"""
        timeline = list(self.state_history)
        timeline.append((self.state_start_frame, self.current_state))
        return timeline
    
    def export_transition_matrix(self) -> Dict:
        """
        Transition matrix'i export eder (ML analizi için).
        
        Returns:
            {
                'player_id': int,
                'allow_landing_state': bool,
                'strict_mode': bool,
                'matrix': {from: [to1, to2, ...]}
            }
        """
        # Convert sets to lists for JSON serialization
        matrix_serializable = {
            state: list(targets) 
            for state, targets in self.transition_matrix.items()
        }
        
        return {
            'player_id': self.player_id,
            'allow_landing_state': self.allow_landing_state,
            'strict_mode': self.strict_mode,
            'matrix': matrix_serializable
        }
    
    def reset(self):
        """State machine'i sıfırla"""
        self.current_state = MovementState.IDLE.value
        self.state_start_frame = 0
        self.state_history.clear()
        self.transition_history.clear()
        self.jump_start_frame = None
        self.is_in_landing_phase = False


class TransitionValidator:
    """
    Standalone transition validator (utility class).
    
    StateMachine dışında transition geçerliliğini kontrol etmek için.
    
    Usage:
        >>> validator = TransitionValidator()
        >>> is_valid = validator.validate("idle", "jumping")
        >>> print(is_valid)
        False  # Can't jump from idle directly
    """
    
    def __init__(self, allow_landing_state: bool = True):
        """
        Args:
            allow_landing_state: Landing state kullanılsın mı?
        """
        self.allow_landing_state = allow_landing_state
        self.transition_rules = self._build_rules()
    
    def _build_rules(self) -> Dict[Tuple[str, str], bool]:
        """
        Transition rules dictionary'si oluşturur.
        
        Returns:
            {(from_state, to_state): is_valid}
        """
        rules = {}
        
        # Valid transitions
        valid_pairs = [
            ("idle", "idle"),
            ("idle", "walking"),
            ("walking", "idle"),
            ("walking", "walking"),
            ("walking", "running"),
            ("walking", "jumping"),
            ("running", "walking"),
            ("running", "running"),
            ("running", "jumping"),
            ("running", "idle"),  # Allowed in non-strict
        ]
        
        if self.allow_landing_state:
            valid_pairs.extend([
                ("jumping", "jumping"),
                ("jumping", "landing"),
                ("landing", "landing"),
                ("landing", "idle"),
                ("landing", "walking"),
                ("landing", "running"),
            ])
        else:
            valid_pairs.extend([
                ("jumping", "jumping"),
                ("jumping", "walking"),
                ("jumping", "running"),
            ])
        
        # Mark valid pairs
        for pair in valid_pairs:
            rules[pair] = True
        
        return rules
    
    def validate(self, from_state: str, to_state: str) -> bool:
        """
        Transition geçerli mi?
        
        Returns:
            True if valid transition
        """
        return self.transition_rules.get((from_state, to_state), False)
    
    def get_invalid_transitions(self) -> List[Tuple[str, str]]:
        """
        Tüm geçersiz transition'ları listeler.
        
        Returns:
            [(from, to), ...] listesi
        """
        states = ["idle", "walking", "running", "jumping"]
        if self.allow_landing_state:
            states.append("landing")
        
        invalid = []
        for from_state in states:
            for to_state in states:
                if not self.validate(from_state, to_state):
                    invalid.append((from_state, to_state))
        
        return invalid


# Example usage
if __name__ == "__main__":
    print("=== State Machine Test ===\n")
    
    # Initialize state machine
    fsm = MovementStateMachine(
        player_id=7,
        allow_landing_state=True,
        strict_mode=False
    )
    
    # Test transitions
    test_sequence = [
        (0, "idle", {'speed': 0.2}),
        (5, "walking", {'speed': 1.5}),
        (10, "walking", {'speed': 2.0}),
        (15, "running", {'speed': 6.0}),
        (20, "running", {'speed': 6.5}),
        (25, "jumping", {'speed': 5.0, 'bbox_height_change': -0.15}),
        (30, "jumping", {'speed': 4.5, 'bbox_height_change': -0.12}),
        (35, "landing", {'speed': 3.0, 'bbox_height_change': 0.10}),
        (40, "walking", {'speed': 1.8}),
        (45, "idle", {'speed': 0.3}),
    ]
    
    print("Frame | Candidate | Final State | Valid | Reason")
    print("-" * 75)
    
    for timestamp, candidate, features in test_sequence:
        result = fsm.update(
            timestamp=timestamp,
            candidate_state=candidate,
            features=features
        )
        
        valid_str = "✓" if result.is_valid_transition else "✗"
        reason = result.transition_info.reason if result.transition_info else "same_state"
        
        print(f"{timestamp:5d} | {candidate:9s} | {result.state:11s} | "
              f"{valid_str:5s} | {reason}")
    
    # Test invalid transition
    print("\n=== Invalid Transition Test ===")
    fsm.reset()
    
    # Try: idle → jumping (should fail)
    result = fsm.update(
        timestamp=100,
        candidate_state="jumping",
        features={'speed': 5.0, 'bbox_height_change': -0.15}
    )
    
    print(f"Attempt: idle → jumping")
    print(f"Result: {result.state}")
    print(f"Valid: {result.is_valid_transition}")
    print(f"Reason: {result.transition_info.reason if result.transition_info else 'N/A'}")
    
    # Export transition matrix
    print("\n=== Transition Matrix ===")
    matrix = fsm.export_transition_matrix()
    print(f"Player ID: {matrix['player_id']}")
    print(f"Allow Landing: {matrix['allow_landing_state']}")
    print(f"Strict Mode: {matrix['strict_mode']}")
    print("\nValid Transitions:")
    for from_state, to_states in matrix['matrix'].items():
        print(f"  {from_state:8s} → {', '.join(to_states)}")
    
    # Test TransitionValidator
    print("\n=== Transition Validator Test ===")
    validator = TransitionValidator()
    
    test_pairs = [
        ("idle", "walking"),      # Valid
        ("idle", "jumping"),      # Invalid
        ("walking", "running"),   # Valid
        ("running", "idle"),      # Valid (non-strict)
        ("jumping", "running"),   # Invalid (without landing)
    ]
    
    for from_state, to_state in test_pairs:
        is_valid = validator.validate(from_state, to_state)
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"{from_state:8s} → {to_state:8s}: {status}")