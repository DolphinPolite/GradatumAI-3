"""
Shot Attempt Detector Module

A rule-based basketball shot attempt detection system with optional AI refinement.

Key Features:
    - Rule-based detection (explainable, deterministic)
    - Temporal reasoning with sliding windows
    - Multi-condition validation (jump + release + trajectory)
    - Optional AI confidence refinement
    - Per-player state tracking
    - Comprehensive event logging

Usage:
    >>> from shot_attempt_detector import ShotAttemptDetector, FramePacket
    >>> 
    >>> # Initialize detector
    >>> detector = ShotAttemptDetector()
    >>> 
    >>> # Process frames
    >>> frame = FramePacket(
    ...     timestamp=100,
    ...     player_id=7,
    ...     movement_state="jumping",
    ...     movement_confidence=0.85,
    ...     bbox_height=250.0,
    ...     ball_position=(320, 240),
    ...     has_ball=True
    ... )
    >>> 
    >>> event = detector.process_frame(frame)
    >>> if event:
    ...     print(f"Shot detected: {event}")

Public API:
    Classes:
        - ShotAttemptDetector: Main detection system
        - FramePacket: Input data structure
        - ShotEvent: Output event structure
        - DetectionThresholds: Configuration
    
    Functions:
        - get_default_thresholds(): Default configuration
        - get_strict_thresholds(): High precision config
        - get_permissive_thresholds(): High recall config

Architecture:
    Input (FramePacket) 
        → TemporalBuffer (sliding window)
        → FeatureExtractor (H1-H4 hard conditions, S1-S4 soft scores)
        → Confidence Calculation (rule-based + optional AI)
        → Event Generation (ShotEvent)

Integration:
    This module integrates with:
        - Movement Classifier (movement_state, confidence, bbox)
        - Ball Tracker (ball_position, has_ball)
    
    And provides output to:
        - Game analytics pipeline
        - ML training data collection
        - Coaching feedback systems

Author: Basketball Analytics Pipeline
Version: 1.0.0
Date: 2024-12-16
"""

# Version info
__version__ = "1.0.0"
__author__ = "Basketball Analytics Pipeline"
__date__ = "2024-12-16"

# =============================================================================
# PUBLIC API EXPORTS
# =============================================================================

# Main detector
from .detector import ShotAttemptDetector

# Data structures
from .utils import FramePacket, ShotEvent

# Configuration
from .thresholds import (
    DetectionThresholds,
    get_default_thresholds,
    get_strict_thresholds,
    get_permissive_thresholds
)

# Feature structures (for advanced users)
from .features import ExtractedFeatures, FeatureExtractor

# Temporal buffer (for advanced users)
from .temporal_buffer import TemporalBuffer


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Main classes
    'ShotAttemptDetector',
    'FramePacket',
    'ShotEvent',
    'DetectionThresholds',
    
    # Configuration functions
    'get_default_thresholds',
    'get_strict_thresholds',
    'get_permissive_thresholds',
    
    # Advanced API (optional)
    'ExtractedFeatures',
    'FeatureExtractor',
    'TemporalBuffer',
    
    # Version info
    '__version__',
]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_detector(preset: str = "default",
                   enable_ai: bool = False,
                   verbose: bool = False) -> ShotAttemptDetector:
    """
    Convenience function to create detector with preset configuration.
    
    Args:
        preset: Threshold preset ("default", "strict", "permissive", "training")
        enable_ai: Enable AI confidence refinement
        verbose: Print debug information
    
    Returns:
        Configured ShotAttemptDetector
    
    Example:
        >>> detector = create_detector(preset="strict", verbose=True)
    """
    thresholds = DetectionThresholds.from_preset(preset)
    return ShotAttemptDetector(
        thresholds=thresholds,
        enable_ai_refiner=enable_ai,
        verbose=verbose
    )


# =============================================================================
# MODULE INFO
# =============================================================================

def get_module_info() -> dict:
    """
    Get module information and capabilities.
    
    Returns:
        Dictionary with module metadata
    """
    return {
        'name': 'Shot Attempt Detector',
        'version': __version__,
        'author': __author__,
        'date': __date__,
        'description': 'Rule-based basketball shot attempt detection system',
        'features': [
            'Rule-based detection (explainable)',
            'Temporal reasoning',
            'Multi-condition validation',
            'Optional AI refinement',
            'Per-player tracking',
            'Comprehensive logging'
        ],
        'presets': ['default', 'strict', 'permissive', 'training'],
        'input_requirements': [
            'movement_state (from classifier)',
            'movement_confidence',
            'bbox_height',
            'ball_position (from tracker)',
            'has_ball'
        ],
        'output_format': 'ShotEvent with confidence and reasoning',
        'dependencies': ['numpy (basic operations only)']
    }


# =============================================================================
# VALIDATION
# =============================================================================

def validate_installation() -> bool:
    """
    Validate module installation and dependencies.
    
    Returns:
        True if all checks pass
    """
    try:
        # Check all imports
        from . import detector, utils, thresholds, features, temporal_buffer
        
        # Test basic functionality
        test_detector = ShotAttemptDetector()
        test_packet = FramePacket(
            timestamp=0,
            player_id=1,
            movement_state="idle",
            movement_confidence=0.5,
            bbox_height=100.0
        )
        
        # This should not crash
        is_valid, _ = test_packet.is_valid()
        
        return is_valid
    
    except Exception as e:
        print(f"Validation failed: {e}")
        return False


# =============================================================================
# INITIALIZATION
# =============================================================================

# Validate on import (optional, can be disabled)
_VALIDATE_ON_IMPORT = False

if _VALIDATE_ON_IMPORT:
    if not validate_installation():
        import warnings
        warnings.warn(
            "Shot Attempt Detector validation failed. "
            "Module may not function correctly.",
            RuntimeWarning
        )