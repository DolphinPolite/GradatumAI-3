from dataclasses import dataclass

@dataclass
class MovementConfig:
    """Basketball movement classification config"""
    fps: int = 30
    court_length_meters: float = 28.65  # NBA
    court_width_meters: float = 15.24   # NBA
    debug_mode: bool = False