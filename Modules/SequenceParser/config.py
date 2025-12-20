"""
SequenceParser Module Configuration
Parses and sequences events detected during a match.
"""

# Event types recognized
EVENT_TYPES = [
    'pass',
    'shot',
    'dribble',
    'tackle',
    'foul',
    'ball_control',
    'turnover',
    'clearance',
    'corner',
    'throw_in',
]

# Min sequence length to be considered a "sequence"
MIN_SEQUENCE_LENGTH = 2

# Max time gap (frames) between events in same sequence
MAX_SEQUENCE_GAP = 150  # ~5 seconds at 30 fps

# Temporal smoothing window (frames)
TEMPORAL_SMOOTH_WINDOW = 5

# Confidence threshold for accepting an event in sequence
MIN_EVENT_CONFIDENCE = 0.5
