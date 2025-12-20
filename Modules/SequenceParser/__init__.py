"""
SequenceParser Module
Parses and organizes detected game events into coherent sequences.
"""

from .sequence_parser import SequenceParser, GameEvent, EventSequence
from .config import (
    EVENT_TYPES,
    MIN_SEQUENCE_LENGTH,
    MAX_SEQUENCE_GAP,
    TEMPORAL_SMOOTH_WINDOW,
    MIN_EVENT_CONFIDENCE,
)

__all__ = [
    'SequenceParser',
    'GameEvent',
    'EventSequence',
    'EVENT_TYPES',
    'MIN_SEQUENCE_LENGTH',
    'MAX_SEQUENCE_GAP',
    'TEMPORAL_SMOOTH_WINDOW',
    'MIN_EVENT_CONFIDENCE',
]
