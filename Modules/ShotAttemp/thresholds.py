"""
Shot Attempt Detector - Threshold Configuration

Purpose:
    Centralized threshold management for shot attempt detection.
    All physical constraints and detection parameters defined here.

Design Philosophy:
    - Easy tuning without touching logic
    - Preset system for different scenarios
    - Documented rationale for each threshold
    - Version control friendly (YAML-like structure)

Usage:
    # Use default thresholds
    thresholds = DetectionThresholds()
    
    # Use preset
    thresholds = DetectionThresholds.from_preset("strict")
    
    # Custom configuration
    thresholds = DetectionThresholds(
        jump_confidence_min=0.75,
        ball_upward_velocity_min=2.5
    )

Author: Shot Detection Module
Date: 2024
"""

from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime


@dataclass
class DetectionThresholds:
    """
    Shot attempt detection threshold configuration.
    
    All thresholds are based on physical basketball constraints and
    empirical observations from real game footage.
    
    Categories:
        - Jump Detection: Player vertical motion
        - Ball Ownership: Pre-release control verification
        - Ball Release: Ownership transition
        - Ball Motion: Post-release trajectory
        - Temporal: Event timing constraints
        - Confidence: Scoring weights
    """
    
    # =========================================================================
    # JUMP DETECTION THRESHOLDS
    # =========================================================================
    
    jump_confidence_min: float = 0.70
    """
    Minimum confidence from movement classifier to consider jump valid.
    
    Rationale:
        - 0.70 filters noisy detections
        - Allows some uncertainty (camera angle, occlusion)
        - Higher values (0.80+) cause false negatives
    
    Tuning Guide:
        - Increase: fewer false positives, miss marginal shots
        - Decrease: catch more shots, risk pass/tip-in confusion
    """
    
    jump_bbox_shrink_min: float = 0.05
    """
    Minimum bbox height decrease ratio to confirm jump.
    
    Rationale:
        - Player appears smaller when jumping (camera perspective)
        - 5% = ~10-15 pixels for typical bbox (200-300px)
        - Filters standing reach, fake jumps
    
    Physical Basis:
        - Jump height: 0.3-0.8m (NBA players)
        - Perspective compression: ~5-10%
    
    Formula:
        bbox_height_change / bbox_height < -0.05
    """
    
    jump_min_frames: int = 3
    """
    Minimum consecutive frames in "jumping" state.
    
    Rationale:
        - At 30fps: 3 frames = 100ms
        - Filters single-frame noise
        - Real jumps sustain 5-10 frames typically
    
    Note:
        This is NOT a threshold, but a temporal constraint.
        Enforced in features.py during window analysis.
    """
    
    # =========================================================================
    # BALL OWNERSHIP THRESHOLDS
    # =========================================================================
    
    ownership_lookback_frames: int = 10
    """
    How many frames before jump to check ball control.
    
    Rationale:
        - At 30fps: 10 frames = 333ms
        - Covers gather + shooting motion
        - Too short: miss shots after dribble
        - Too long: false positives from passes
    
    Basketball Context:
        - Gather step: 100-200ms
        - Shot preparation: 200-400ms
        - Total: ~300-600ms → 10-18 frames @ 30fps
    """
    
    ownership_min_frames: int = 5
    """
    Minimum frames of continuous ball control before jump.
    
    Rationale:
        - At 30fps: 5 frames = 167ms
        - Filters deflections, steals
        - Real shot preparation requires sustained control
    
    Edge Cases:
        - Catch-and-shoot: exactly at threshold
        - Tip-ins: should fail this check (good!)
    """
    
    # =========================================================================
    # BALL RELEASE THRESHOLDS
    # =========================================================================
    
    release_gap_max_frames: int = 5
    """
    Maximum frames between jump start and ball release.
    
    Rationale:
        - At 30fps: 5 frames = 167ms
        - Jump apex: ~250-350ms
        - Release typically before apex
        - Too large: catches passes after jump
    
    Physical Constraint:
        - Jump duration: 500-700ms
        - Release timing: 40-60% of jump phase
    """
    
    ball_player_distance_increase_min: float = 10.0
    """
    Minimum pixel distance increase after release (pixels/frame).
    
    Rationale:
        - Shot: ball rapidly separates from player
        - Pass: separation can be slower or lateral
        - 10px/frame @ 30fps = 300px/s
    
    Discriminative Power:
        - Shot: 15-30 px/frame
        - Pass: 5-15 px/frame
        - Rebound tap: 2-8 px/frame
    """
    
    # =========================================================================
    # BALL MOTION THRESHOLDS
    # =========================================================================
    
    ball_upward_velocity_min: float = -2.0
    """
    Minimum upward velocity component (negative = upward in image coords).
    
    Rationale:
        - Image Y-axis: top=0, bottom=height
        - Upward motion: vy < 0
        - Shot: -2.0 to -8.0 pixels/frame
        - Pass: -0.5 to -3.0 pixels/frame
    
    Units: pixels per frame (@ 30fps)
    
    Physical Mapping:
        - -2.0 px/frame ≈ 0.8 m/s (typical court)
        - -5.0 px/frame ≈ 2.0 m/s (strong shot)
    
    Note:
        Actual mapping depends on homography matrix,
        but relative threshold works across camera angles.
    """
    
    ball_upward_acceleration_min: float = -0.5
    """
    Minimum upward acceleration (release impulse detection).
    
    Rationale:
        - Shot release: sudden upward impulse
        - Gravity: continuous downward (positive in image)
        - Need to see initial upward acceleration
    
    Units: pixels per frame²
    """
    
    ball_upward_sustained_frames: int = 3
    """
    Minimum frames of sustained upward motion.
    
    Rationale:
        - At 30fps: 3 frames = 100ms
        - Filters single-frame noise
        - Real shot trajectory smooth for 5-8 frames
    """
    
    # =========================================================================
    # TEMPORAL WINDOW CONFIGURATION
    # =========================================================================
    
    temporal_window_size: int = 15
    """
    Sliding window size for event detection (frames).
    
    Rationale:
        - At 30fps: 15 frames = 500ms
        - Covers: gather (100ms) + jump (250ms) + release (150ms)
        - Too small: miss slow shots
        - Too large: multiple events overlap
    
    Basketball Shot Timeline:
        Frame 0-5:   Gather / preparation
        Frame 5-10:  Jump initiation
        Frame 8-12:  Ball release
        Frame 10-15: Upward motion verification
    """
    
    temporal_window_min: int = 10
    """
    Minimum window size (for edge cases / end of video).
    
    Rationale:
        - Gracefully handle incomplete sequences
        - 10 frames = 333ms minimum
    """
    
    # =========================================================================
    # CONFIDENCE CALCULATION WEIGHTS
    # =========================================================================
    
    # Hard condition weights (must pass all)
    weight_jump_confidence: float = 0.30
    """Jump detection quality (30%)"""
    
    weight_ball_release: float = 0.25
    """Ball release clarity (25%)"""
    
    weight_upward_velocity: float = 0.25
    """Upward motion strength (25%)"""
    
    weight_temporal_consistency: float = 0.20
    """Event timing alignment (20%)"""
    
    # Soft condition bonuses (additive)
    bonus_separation_trend: float = 0.10
    """Ball-player separation score (max +10%)"""
    
    bonus_release_height: float = 0.05
    """High release point (max +5%)"""
    
    bonus_apex_alignment: float = 0.05
    """Release near jump apex (max +5%)"""
    
    # Confidence thresholds
    confidence_min_threshold: float = 0.60
    """
    Minimum confidence to report shot attempt.
    
    Rationale:
        - 0.60: balanced precision/recall
        - Lower: too many false positives
        - Higher: miss marginal shots
    
    Application:
        - Production: 0.65-0.70 (high precision)
        - Training data: 0.50-0.60 (high recall)
    """
    
    confidence_high_threshold: float = 0.85
    """
    High confidence threshold (use for auto-labeling).
    
    Rationale:
        - 0.85+: very clean detections
        - Safe for automatic annotation
    """
    
    # =========================================================================
    # METADATA
    # =========================================================================
    
    preset_name: str = "default"
    """Preset identifier for tracking configuration"""
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    """Timestamp for version control"""
    
    notes: str = ""
    """Custom notes for this configuration"""
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate threshold consistency.
        
        Returns:
            (is_valid, error_message)
        """
        # Check weight sum
        weight_sum = (
            self.weight_jump_confidence +
            self.weight_ball_release +
            self.weight_upward_velocity +
            self.weight_temporal_consistency
        )
        
        if not (0.99 <= weight_sum <= 1.01):
            return False, f"Weights must sum to 1.0, got {weight_sum:.3f}"
        
        # Check temporal constraints
        if self.temporal_window_min > self.temporal_window_size:
            return False, "temporal_window_min > temporal_window_size"
        
        # Check confidence bounds
        if not (0.0 <= self.confidence_min_threshold <= 1.0):
            return False, "confidence_min_threshold out of range [0,1]"
        
        # Check physical constraints
        if self.ball_upward_velocity_min >= 0:
            return False, "ball_upward_velocity_min must be negative (upward)"
        
        return True, ""
    
    # =========================================================================
    # PRESETS
    # =========================================================================
    
    @classmethod
    def from_preset(cls, preset: str) -> 'DetectionThresholds':
        """
        Load preset configuration.
        
        Available presets:
            - "default": Balanced precision/recall
            - "strict": High precision, low false positives
            - "permissive": High recall, catches marginal shots
            - "training": For ML data collection
        
        Args:
            preset: Preset name
        
        Returns:
            DetectionThresholds instance
        
        Example:
            >>> thresholds = DetectionThresholds.from_preset("strict")
        """
        presets = {
            "default": cls(
                preset_name="default",
                notes="Balanced configuration for production use"
            ),
            
            "strict": cls(
                preset_name="strict",
                jump_confidence_min=0.80,
                ownership_min_frames=7,
                ball_upward_velocity_min=-2.5,
                confidence_min_threshold=0.70,
                notes="High precision, minimize false positives"
            ),
            
            "permissive": cls(
                preset_name="permissive",
                jump_confidence_min=0.60,
                ownership_min_frames=3,
                ball_upward_velocity_min=-1.5,
                release_gap_max_frames=7,
                confidence_min_threshold=0.50,
                notes="High recall, catch all potential shots"
            ),
            
            "training": cls(
                preset_name="training",
                jump_confidence_min=0.65,
                confidence_min_threshold=0.55,
                notes="Balanced for ML training data collection"
            ),
        }
        
        if preset not in presets:
            raise ValueError(
                f"Unknown preset: {preset}. "
                f"Available: {list(presets.keys())}"
            )
        
        return presets[preset]
    
    # =========================================================================
    # EXPORT / IMPORT
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'preset_name': self.preset_name,
            'created_at': self.created_at,
            'notes': self.notes,
            
            'jump_detection': {
                'confidence_min': self.jump_confidence_min,
                'bbox_shrink_min': self.jump_bbox_shrink_min,
                'min_frames': self.jump_min_frames
            },
            
            'ball_ownership': {
                'lookback_frames': self.ownership_lookback_frames,
                'min_frames': self.ownership_min_frames
            },
            
            'ball_release': {
                'gap_max_frames': self.release_gap_max_frames,
                'distance_increase_min': self.ball_player_distance_increase_min
            },
            
            'ball_motion': {
                'upward_velocity_min': self.ball_upward_velocity_min,
                'upward_acceleration_min': self.ball_upward_acceleration_min,
                'sustained_frames': self.ball_upward_sustained_frames
            },
            
            'temporal': {
                'window_size': self.temporal_window_size,
                'window_min': self.temporal_window_min
            },
            
            'confidence_weights': {
                'jump': self.weight_jump_confidence,
                'release': self.weight_ball_release,
                'velocity': self.weight_upward_velocity,
                'temporal': self.weight_temporal_consistency,
                'bonus_separation': self.bonus_separation_trend,
                'bonus_height': self.bonus_release_height,
                'bonus_apex': self.bonus_apex_alignment
            },
            
            'confidence_thresholds': {
                'min': self.confidence_min_threshold,
                'high': self.confidence_high_threshold
            }
        }
    
    def __repr__(self) -> str:
        """Pretty string representation."""
        return (
            f"DetectionThresholds(preset='{self.preset_name}', "
            f"window={self.temporal_window_size}f, "
            f"min_conf={self.confidence_min_threshold:.2f})"
        )


# =============================================================================
# QUICK ACCESS FUNCTIONS
# =============================================================================

def get_default_thresholds() -> DetectionThresholds:
    """Get default threshold configuration."""
    return DetectionThresholds()


def get_strict_thresholds() -> DetectionThresholds:
    """Get strict (high precision) threshold configuration."""
    return DetectionThresholds.from_preset("strict")


def get_permissive_thresholds() -> DetectionThresholds:
    """Get permissive (high recall) threshold configuration."""
    return DetectionThresholds.from_preset("permissive")


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Shot Attempt Detection Thresholds ===\n")
    
    # Test default
    default = DetectionThresholds()
    is_valid, msg = default.validate()
    print(f"Default config valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {msg}")
    print(f"  {default}\n")
    
    # Test presets
    for preset_name in ["default", "strict", "permissive", "training"]:
        config = DetectionThresholds.from_preset(preset_name)
        print(f"{preset_name.upper()}:")
        print(f"  Jump confidence: {config.jump_confidence_min}")
        print(f"  Min confidence: {config.confidence_min_threshold}")
        print(f"  Window size: {config.temporal_window_size} frames")
        print()
    
    # Export example
    print("=== Export to Dict ===")
    export = default.to_dict()
    print(f"Keys: {list(export.keys())}")