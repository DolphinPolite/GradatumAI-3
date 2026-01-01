"""
Dribbling Detector
Detects dribbling actions and analyzes dribble characteristics.
"""

import math
from .config import (
    DRIBBLE_DISTANCE_TH, MIN_DRIBBLE_FRAMES, MIN_DRIBBLE_PATH_LENGTH,
    MIN_DRIBBLE_VELOCITY, MAX_BALL_GAP_FRAMES, DIRECTION_CHANGE_TH
)


class DribbleEvent:
    """Represents a dribble action."""
    
    def __init__(self, start_ts, player_id, start_pos):
        self.start_ts = start_ts
        self.player_id = player_id
        self.start_pos = start_pos
        self.end_ts = start_ts
        self.end_pos = start_pos
        self.distance_traveled = 0.0
        self.frames_count = 0
        self.avg_velocity = 0.0
        self.completed = False
    
    def __repr__(self):
        return f"Dribble(player={self.player_id}, ts={self.start_ts}-{self.end_ts}, dist={self.distance_traveled:.1f})"


class DribblingDetector:
    """Detects and tracks dribbling events."""
    
    def __init__(self):
        self.current_dribble = None
        self.dribble_events = []
        self.frames_without_ball = 0
        self.last_ball_pos = None
    
    def update(self, timestamp, ball_pos, ball_carrier):
        """
        Update dribbling state.
        
        Args:
            timestamp: Frame number
            ball_pos: (x, y) tuple or None
            ball_carrier: Player object who has the ball, or None
        """
        if ball_pos is None:
            self.frames_without_ball += 1
            if self.frames_without_ball > MAX_BALL_GAP_FRAMES:
                self._finalize_dribble()
            return
        
        self.frames_without_ball = 0
        
        # start new dribble or continue existing one
        if ball_carrier is None:
            self._finalize_dribble()
            self.last_ball_pos = ball_pos
            return
        
        if self.current_dribble is None:
            # start new dribble
            self.current_dribble = DribbleEvent(timestamp, ball_carrier.ID, ball_pos)
            self.last_ball_pos = ball_pos
        elif self.current_dribble.player_id == ball_carrier.ID:
            # continue existing dribble
            if self.last_ball_pos is not None:
                dist = math.hypot(
                    ball_pos[0] - self.last_ball_pos[0],
                    ball_pos[1] - self.last_ball_pos[1]
                )
                if dist <= DRIBBLE_DISTANCE_TH:
                    self.current_dribble.end_ts = timestamp
                    self.current_dribble.end_pos = ball_pos
                    self.current_dribble.distance_traveled += dist
                    self.current_dribble.frames_count += 1
                else:
                    # ball jumped too far, finalize current dribble
                    self._finalize_dribble()
                    self.current_dribble = DribbleEvent(timestamp, ball_carrier.ID, ball_pos)
            self.last_ball_pos = ball_pos
        else:
            # ball carrier changed
            self._finalize_dribble()
            self.current_dribble = DribbleEvent(timestamp, ball_carrier.ID, ball_pos)
            self.last_ball_pos = ball_pos
    
    def _finalize_dribble(self):
        """Finalize and record the current dribble event if valid."""
        if self.current_dribble is None:
            return
        
        if self.current_dribble.frames_count >= MIN_DRIBBLE_FRAMES and \
           self.current_dribble.distance_traveled >= MIN_DRIBBLE_PATH_LENGTH:
            self.current_dribble.completed = True
            if self.current_dribble.frames_count > 0:
                self.current_dribble.avg_velocity = (
                    self.current_dribble.distance_traveled / self.current_dribble.frames_count
                )
            self.dribble_events.append(self.current_dribble)
        
        self.current_dribble = None
    
    def get_dribbles_by_player(self, player_id):
        """Get all dribble events for a specific player."""
        return [d for d in self.dribble_events if d.player_id == player_id]
    
    def get_all_dribbles(self):
        """Get all recorded dribble events."""
        return self.dribble_events
    
    def get_dribble_stats(self, player_id):
        """Get dribbling statistics for a player."""
        dribbles = self.get_dribbles_by_player(player_id)
        if not dribbles:
            return None
        
        total_distance = sum(d.distance_traveled for d in dribbles)
        avg_distance = total_distance / len(dribbles)
        avg_velocity = sum(d.avg_velocity for d in dribbles) / len(dribbles)
        
        return {
            'player_id': player_id,
            'total_dribbles': len(dribbles),
            'total_distance': total_distance,
            'avg_distance': avg_distance,
            'avg_velocity': avg_velocity,
        }
