"""
Event Recognizer - Detects and classifies game events
"""

class EventRecognizer:
    """Recognizes game events from frame data."""
    
    def __init__(self):
        """Initialize event recognizer."""
        self.events = []
        self.event_count = 0
    
    def update(self, frame_number, timestamp, detections):
        """
        Update with new frame data and detect events.
        
        Args:
            frame_number: Current frame number
            timestamp: Timestamp in seconds
            detections: Detection data (players, ball, etc)
        """
        pass
    
    def get_events(self):
        """Get all detected events."""
        return self.events
    
    def detect_pass(self, from_player, to_player, distance):
        """Detect a pass event."""
        event = {
            'type': 'pass',
            'from_player': from_player,
            'to_player': to_player,
            'distance': distance
        }
        self.events.append(event)
        self.event_count += 1
        return event
    
    def detect_shot(self, player_id, shot_type='field_goal'):
        """Detect a shot event."""
        event = {
            'type': 'shot',
            'player': player_id,
            'shot_type': shot_type
        }
        self.events.append(event)
        self.event_count += 1
        return event
    
    def detect_turnover(self, player_id):
        """Detect a turnover event."""
        event = {
            'type': 'turnover',
            'player': player_id
        }
        self.events.append(event)
        self.event_count += 1
        return event
    
    def get_event_count(self):
        """Get total event count."""
        return self.event_count
