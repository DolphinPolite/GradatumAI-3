"""Sequence Parser - Records and parses game sequences"""

class SequenceRecorder:
    """Records game sequences."""
    
    def __init__(self):
        """Initialize sequence recorder."""
        self.sequences = []
        self.current_sequence = []
    
    def record_event(self, event):
        """Record an event in the sequence."""
        self.current_sequence.append(event)
    
    def end_sequence(self):
        """End current sequence."""
        if self.current_sequence:
            self.sequences.append(self.current_sequence)
            self.current_sequence = []
    
    def get_sequences(self):
        """Get all recorded sequences."""
        return self.sequences


class SequenceParser:
    """Parses game sequences."""
    
    def __init__(self):
        """Initialize sequence parser."""
        self.patterns = {}
    
    def parse(self, sequence):
        """Parse a sequence."""
        return {
            'length': len(sequence),
            'events': sequence
        }
    
    def find_patterns(self, sequences):
        """Find patterns in sequences."""
        patterns = {}
        for seq in sequences:
            seq_key = str(seq)
            patterns[seq_key] = patterns.get(seq_key, 0) + 1
        return patterns
