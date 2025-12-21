"""
DriblingDetector Module
Detects and analyzes dribbling actions during the match.
"""

from .dribbling_detector import DriblingDetector, DribbleEvent
from .config import (
    DRIBBLE_DISTANCE_TH,
    MIN_DRIBBLE_FRAMES,
    MIN_DRIBBLE_PATH_LENGTH,
    MIN_DRIBBLE_VELOCITY,
    MAX_BALL_GAP_FRAMES,
    DIRECTION_CHANGE_TH,
)

__all__ = [
    'DriblingDetector',
    'DribbleEvent',
    'DRIBBLE_DISTANCE_TH',
    'MIN_DRIBBLE_FRAMES',
    'MIN_DRIBBLE_PATH_LENGTH',
    'MIN_DRIBBLE_VELOCITY',
    'MAX_BALL_GAP_FRAMES',
    'DIRECTION_CHANGE_TH',
]
