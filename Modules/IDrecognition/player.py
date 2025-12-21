class Player:
    def __init__(self, ID, team, color):
        self.ID = ID
        self.team = team
        self.color = color
        self.previous_bb = None
        # dict of tuples {timestamp: (position_x, position_y), ...}
        self.positions = {}
        self.has_ball = False
        # optional: jersey number read from the frame (if OCR is available)
        self.jersey_number = None
        # matching confidence (0-1) for most recent association
        self.match_confidence = 0.0
