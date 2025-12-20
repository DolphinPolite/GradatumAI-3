"""
DriblingDetector utility functions.
"""

import math


def calculate_ball_velocity(pos1, pos2, time_delta=1):
    """
    Calculate velocity between two positions.
    
    Args:
        pos1: (x, y) start position
        pos2: (x, y) end position
        time_delta: Time interval (in frames)
    
    Returns:
        float: velocity in pixels/frame
    """
    if pos1 is None or pos2 is None:
        return 0.0
    dist = math.hypot(pos2[0] - pos1[0], pos2[1] - pos1[1])
    return dist / time_delta


def calculate_ball_path_length(positions):
    """
    Calculate total path length from a list of positions.
    
    Args:
        positions: List of (x, y) tuples or dict {timestamp: (x, y)}
    
    Returns:
        float: Total path length
    """
    if isinstance(positions, dict):
        sorted_ts = sorted(positions.keys())
        positions = [positions[ts] for ts in sorted_ts]
    
    if len(positions) < 2:
        return 0.0
    
    total_dist = 0.0
    for i in range(len(positions) - 1):
        dist = math.hypot(
            positions[i + 1][0] - positions[i][0],
            positions[i + 1][1] - positions[i][1]
        )
        total_dist += dist
    
    return total_dist


def is_dribble_direction_change(angle1, angle2, threshold_deg):
    """
    Detect if direction changed significantly.
    
    Args:
        angle1: First movement angle (degrees)
        angle2: Second movement angle (degrees)
        threshold_deg: Direction change threshold
    
    Returns:
        bool: True if direction changed more than threshold
    """
    delta = abs(angle2 - angle1)
    if delta > 180:
        delta = 360 - delta
    return delta > threshold_deg
