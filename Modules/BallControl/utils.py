"""
BallControl utility functions.
"""

import math


def distance_2d(pos1, pos2):
    """Calculate Euclidean distance between two 2D points."""
    if pos1 is None or pos2 is None:
        return float('inf')
    return math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])


def smooth_ball_position(positions, window_size=3):
    """
    Smooth ball trajectory using moving average.
    
    Args:
        positions: Dict {timestamp: (x, y), ...}
        window_size: Window size for moving average
    
    Returns:
        Dict of smoothed positions
    """
    if not positions:
        return {}
    
    sorted_ts = sorted(positions.keys())
    smoothed = {}
    
    for i, ts in enumerate(sorted_ts):
        start = max(0, i - window_size // 2)
        end = min(len(sorted_ts), i + window_size // 2 + 1)
        
        window_ts = sorted_ts[start:end]
        xs = [positions[t][0] for t in window_ts]
        ys = [positions[t][1] for t in window_ts]
        
        avg_x = sum(xs) / len(xs)
        avg_y = sum(ys) / len(ys)
        smoothed[ts] = (int(avg_x), int(avg_y))
    
    return smoothed
