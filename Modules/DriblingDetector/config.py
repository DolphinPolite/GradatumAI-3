"""
DriblingDetector Module Configuration
Detects and analyzes dribbling actions during a match.
"""

# Distance threshold: successive ball positions within this distance = continuous motion (dribble)
DRIBBLE_DISTANCE_TH = 40  # pixels

# Min frames to count as dribble action
MIN_DRIBBLE_FRAMES = 5

# Min distance traveled for a valid dribble
MIN_DRIBBLE_PATH_LENGTH = 100  # pixels

# Velocity threshold for dribble detection (pixels per frame)
MIN_DRIBBLE_VELOCITY = 5.0

# Max gap in ball detection (frames) before resetting dribble counter
MAX_BALL_GAP_FRAMES = 3

# Direction change threshold (degrees) to detect change of direction
DIRECTION_CHANGE_TH = 45  # degrees
