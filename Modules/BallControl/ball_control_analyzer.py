"""
Ball Control Analyzer
Tracks which player has the ball and analyzes ball control statistics.
"""

import math
from .config import (
    BALL_DISTANCE_TH, MIN_CONTROL_FRAMES, MAX_MISSING_FRAMES,
    CONTROL_QUALITY_TH_HIGH, CONTROL_QUALITY_TH_MID, CONTROL_QUALITY_TH_LOW
)


class BallControlAnalyzer:
    """Analyzes ball control per player."""
    
    def __init__(self):
        # track: {player_id: {'frames_with_ball': int, 'total_frames': int, 'last_control_ts': int}}
        self.player_control_stats = {}
        self.ball_carrier = None
        self.frames_without_ball = 0
    
    def update(self, timestamp, ball_pos, players):
        """
        Update ball control state for the current frame.
        
        Args:
            timestamp: Frame number
            ball_pos: (x, y) tuple of ball position (2D map coords), or None if not detected
            players: List of Player objects with positions[timestamp]
        """
        if ball_pos is None:
            self.frames_without_ball += 1
            if self.frames_without_ball > MAX_MISSING_FRAMES:
                self.ball_carrier = None
            return
        
        self.frames_without_ball = 0
        
        # find closest player to ball
        closest_dist = float('inf')
        closest_player = None
        
        for player in players:
            if player.team == 'referee' or timestamp not in player.positions:
                continue
            player_pos = player.positions[timestamp]
            dist = math.hypot(ball_pos[0] - player_pos[0], ball_pos[1] - player_pos[1])
            if dist < closest_dist:
                closest_dist = dist
                closest_player = player
        
        # update ball carrier if within threshold
        if closest_player is not None and closest_dist <= BALL_DISTANCE_TH:
            if closest_player.ID not in self.player_control_stats:
                self.player_control_stats[closest_player.ID] = {
                    'frames_with_ball': 0,
                    'total_frames': 0,
                    'last_control_ts': timestamp,
                    'player_ref': closest_player
                }
            self.player_control_stats[closest_player.ID]['frames_with_ball'] += 1
            self.player_control_stats[closest_player.ID]['last_control_ts'] = timestamp
            self.ball_carrier = closest_player.ID
        else:
            self.ball_carrier = None
        
        # update total frames for all players
        for player in players:
            if player.team != 'referee':
                if player.ID not in self.player_control_stats:
                    self.player_control_stats[player.ID] = {
                        'frames_with_ball': 0,
                        'total_frames': 0,
                        'last_control_ts': timestamp,
                        'player_ref': player
                    }
                self.player_control_stats[player.ID]['total_frames'] += 1
    
    def get_control_quality(self, player_id):
        """
        Get ball control quality rating for a player.
        Returns: 'high', 'mid', 'low', or 'none'
        """
        if player_id not in self.player_control_stats:
            return 'none'
        
        stats = self.player_control_stats[player_id]
        if stats['total_frames'] == 0:
            return 'none'
        
        ratio = stats['frames_with_ball'] / float(stats['total_frames'])
        
        if ratio >= CONTROL_QUALITY_TH_HIGH:
            return 'high'
        elif ratio >= CONTROL_QUALITY_TH_MID:
            return 'mid'
        elif ratio >= CONTROL_QUALITY_TH_LOW:
            return 'low'
        else:
            return 'none'
    
    def get_stats(self):
        """Return all player control statistics."""
        return self.player_control_stats
