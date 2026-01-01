"""Ball Control Analyzer - Analyzes ball possession and control"""

class BallControlAnalyzer:
    """Analyzes ball control and possession."""
    
    def __init__(self):
        """Initialize ball control analyzer."""
        self.possessions = []
        self.current_possession = None
    
    def update(self, player_id, team):
        """Update ball possession."""
        if self.current_possession != player_id:
            self.current_possession = player_id
            possession = {
                'player': player_id,
                'team': team
            }
            self.possessions.append(possession)
    
    def get_possessions(self):
        """Get all possession records."""
        return self.possessions
