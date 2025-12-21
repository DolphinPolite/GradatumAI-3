"""
BallControl Module Configuration
Analyzes how often and for how long players control the ball during a match.
"""

# Distance threshold: if ball is within this pixels of a player, player has ball control
BALL_DISTANCE_TH = 50  # pixels

# Time threshold: ball must be near player for at least this many frames
MIN_CONTROL_FRAMES = 3

# If ball is not seen for this many consecutive frames, reset control tracking
MAX_MISSING_FRAMES = 10

# Success rate thresholds (for statistics)
CONTROL_QUALITY_TH_HIGH = 0.8  # >80% frames with ball = high control
CONTROL_QUALITY_TH_MID = 0.5   # >50% frames with ball = medium control
CONTROL_QUALITY_TH_LOW = 0.2   # >20% frames with ball = low control
