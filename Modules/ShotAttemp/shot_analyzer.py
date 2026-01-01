"""Shot Analyzer - Detects and analyzes shot attempts"""

class ShotAnalyzer:
    """Analyzes shot attempts."""
    
    def __init__(self):
        """Initialize shot analyzer."""
        self.shots = []
    
    def detect_shot(self, player_id, shot_type='field_goal', distance=0):
        """Detect a shot."""
        shot = {
            'player': player_id,
            'type': shot_type,
            'distance': distance
        }
        self.shots.append(shot)
        return shot
    
    def get_shots(self):
        """Get all detected shots."""
        return self.shots
