"""
Shot Attempt Detector - Temporal Buffer Module

Purpose:
    Manage sliding temporal windows for shot attempt detection.
    Store frame history per player for temporal reasoning.

Design Philosophy:
    - Player-based buffering (separate history per player)
    - Fixed-size circular buffer (memory efficient)
    - Event-centric window extraction
    - Ball data is global (shared timeline)

Key Responsibilities:
    - Store recent frames per player
    - Provide sliding window views
    - Detect state transitions
    - Track ownership changes

Usage:
    >>> buffer = TemporalBuffer(window_size=15)
    >>> buffer.add_frame(player_id=7, frame_packet=packet)
    >>> window = buffer.get_window(player_id=7, size=10)
    >>> if buffer.has_jump_in_window(player_id=7):
    ...     print("Jump detected!")

Author: Shot Detection Module
Date: 2024
"""

from typing import List, Optional, Dict, Tuple
from collections import deque

from .utils import FramePacket


class TemporalBuffer:
    """
    Player-based temporal buffer for shot attempt detection.
    
    This class maintains separate frame histories for each player,
    enabling efficient temporal reasoning and event detection.
    
    Architecture:
        - Each player has a deque (circular buffer)
        - Fixed size prevents memory growth
        - Ball data is stored with frames (global timeline)
    
    Attributes:
        window_size: Maximum frames to store per player
        player_buffers: Dict[player_id, deque[FramePacket]]
    """
    
    def __init__(self, window_size: int = 15):
        """
        Initialize temporal buffer.
        
        Args:
            window_size: Maximum frames to store per player
        """
        self.window_size = window_size
        self.player_buffers: Dict[int, deque] = {}
    
    # =========================================================================
    # BUFFER MANAGEMENT
    # =========================================================================
    
    def add_frame(self, player_id: int, frame: FramePacket):
        """
        Add new frame to player's buffer.
        
        Args:
            player_id: Player identifier
            frame: FramePacket to add
        
        Note:
            If buffer full, oldest frame is automatically removed.
        """
        # Initialize buffer if first frame for this player
        if player_id not in self.player_buffers:
            self.player_buffers[player_id] = deque(maxlen=self.window_size)
        
        # Add frame (auto-removes oldest if full)
        self.player_buffers[player_id].append(frame)
    
    def get_window(self, 
                   player_id: int,
                   size: Optional[int] = None) -> List[FramePacket]:
        """
        Get recent frames for player (sliding window).
        
        Args:
            player_id: Player identifier
            size: Number of frames to return (None = all)
        
        Returns:
            List of FramePackets (oldest to newest)
        
        Example:
            >>> window = buffer.get_window(player_id=7, size=10)
            >>> print(f"Got {len(window)} frames")
        """
        if player_id not in self.player_buffers:
            return []
        
        buffer = self.player_buffers[player_id]
        
        if size is None or size >= len(buffer):
            return list(buffer)
        else:
            # Return last 'size' frames
            return list(buffer)[-size:]
    
    def get_event_window(self,
                        player_id: int,
                        center_frame: int,
                        before: int = 5,
                        after: int = 5) -> List[FramePacket]:
        """
        Get window centered around specific frame.
        
        Useful for analyzing events (e.g., frames around jump).
        
        Args:
            player_id: Player identifier
            center_frame: Timestamp to center on
            before: Frames before center
            after: Frames after center
        
        Returns:
            List of FramePackets around center_frame
        
        Example:
            >>> # Get 5 frames before and after jump
            >>> window = buffer.get_event_window(
            ...     player_id=7,
            ...     center_frame=100,
            ...     before=5,
            ...     after=5
            ... )
        """
        if player_id not in self.player_buffers:
            return []
        
        buffer = self.player_buffers[player_id]
        
        # Find center frame index
        center_idx = None
        for i, frame in enumerate(buffer):
            if frame.timestamp == center_frame:
                center_idx = i
                break
        
        if center_idx is None:
            return []
        
        # Extract window
        start_idx = max(0, center_idx - before)
        end_idx = min(len(buffer), center_idx + after + 1)
        
        return list(buffer)[start_idx:end_idx]
    
    def clear_player(self, player_id: int):
        """
        Clear buffer for specific player.
        
        Args:
            player_id: Player identifier
        """
        if player_id in self.player_buffers:
            self.player_buffers[player_id].clear()
    
    def clear_all(self):
        """Clear all player buffers."""
        for buffer in self.player_buffers.values():
            buffer.clear()
    
    def get_buffer_size(self, player_id: int) -> int:
        """
        Get current number of frames in player's buffer.
        
        Args:
            player_id: Player identifier
        
        Returns:
            Number of frames stored
        """
        if player_id not in self.player_buffers:
            return 0
        return len(self.player_buffers[player_id])
    
    # =========================================================================
    # STATE TRANSITION DETECTION
    # =========================================================================
    
    def find_state_transition(self,
                             player_id: int,
                             from_state: str,
                             to_state: str,
                             lookback: Optional[int] = None) -> Optional[int]:
        """
        Find frame where state transition occurred.
        
        Args:
            player_id: Player identifier
            from_state: Previous movement state
            to_state: New movement state
            lookback: How many frames to search (None = all)
        
        Returns:
            Timestamp of transition frame, or None if not found
        
        Example:
            >>> # Find when player started jumping
            >>> jump_frame = buffer.find_state_transition(
            ...     player_id=7,
            ...     from_state="idle",
            ...     to_state="jumping"
            ... )
        """
        window = self.get_window(player_id, size=lookback)
        
        for i in range(len(window) - 1):
            if (window[i].movement_state == from_state and
                window[i+1].movement_state == to_state):
                return window[i+1].timestamp
        
        return None
    
    def has_state_in_window(self,
                           player_id: int,
                           state: str,
                           min_frames: int = 1) -> bool:
        """
        Check if state appears in window for minimum duration.
        
        Args:
            player_id: Player identifier
            state: Movement state to check
            min_frames: Minimum consecutive frames required
        
        Returns:
            True if state sustained for min_frames
        
        Example:
            >>> # Check if player jumped for at least 3 frames
            >>> has_jump = buffer.has_state_in_window(
            ...     player_id=7,
            ...     state="jumping",
            ...     min_frames=3
            ... )
        """
        window = self.get_window(player_id)
        
        consecutive = 0
        for frame in window:
            if frame.movement_state == state:
                consecutive += 1
                if consecutive >= min_frames:
                    return True
            else:
                consecutive = 0
        
        return False
    
    # =========================================================================
    # BALL OWNERSHIP TRACKING
    # =========================================================================
    
    def find_ownership_change(self,
                             player_id: int,
                             from_state: bool,
                             to_state: bool,
                             lookback: Optional[int] = None) -> Optional[int]:
        """
        Find frame where ball ownership changed.
        
        Args:
            player_id: Player identifier
            from_state: Previous has_ball value
            to_state: New has_ball value
            lookback: How many frames to search
        
        Returns:
            Timestamp of ownership change, or None
        
        Example:
            >>> # Find when player released ball
            >>> release_frame = buffer.find_ownership_change(
            ...     player_id=7,
            ...     from_state=True,  # Had ball
            ...     to_state=False    # Released
            ... )
        """
        window = self.get_window(player_id, size=lookback)
        
        for i in range(len(window) - 1):
            if (window[i].has_ball == from_state and
                window[i+1].has_ball == to_state):
                return window[i+1].timestamp
        
        return None
    
    def count_ownership_frames(self,
                              player_id: int,
                              has_ball: bool,
                              lookback: Optional[int] = None) -> int:
        """
        Count frames where player had/didn't have ball.
        
        Args:
            player_id: Player identifier
            has_ball: Ownership state to count
            lookback: How many frames to search
        
        Returns:
            Number of frames matching ownership state
        """
        window = self.get_window(player_id, size=lookback)
        return sum(1 for f in window if f.has_ball == has_ball)
    
    # =========================================================================
    # BALL TRAJECTORY ANALYSIS
    # =========================================================================
    
    def get_ball_positions(self,
                          player_id: int,
                          lookback: Optional[int] = None) -> List[Tuple[int, Tuple[float, float]]]:
        """
        Get ball position history with timestamps.
        
        Args:
            player_id: Player identifier
            lookback: How many frames to retrieve
        
        Returns:
            List of (timestamp, (x, y)) tuples
        
        Example:
            >>> positions = buffer.get_ball_positions(player_id=7, lookback=5)
            >>> for t, (x, y) in positions:
            ...     print(f"Frame {t}: ball at ({x}, {y})")
        """
        window = self.get_window(player_id, size=lookback)
        
        positions = []
        for frame in window:
            if frame.ball_position is not None:
                positions.append((frame.timestamp, frame.ball_position))
        
        return positions
    
    def calculate_ball_velocities(self,
                                 player_id: int,
                                 lookback: Optional[int] = None) -> List[Tuple[int, Tuple[float, float]]]:
        """
        Calculate ball velocity history.
        
        Args:
            player_id: Player identifier
            lookback: How many frames to analyze
        
        Returns:
            List of (timestamp, (vx, vy)) tuples
        
        Note:
            Velocity calculated using finite difference between consecutive frames.
        """
        positions = self.get_ball_positions(player_id, lookback)
        
        if len(positions) < 2:
            return []
        
        velocities = []
        for i in range(len(positions) - 1):
            t1, (x1, y1) = positions[i]
            t2, (x2, y2) = positions[i+1]
            
            dt = t2 - t1
            if dt > 0:
                vx = (x2 - x1) / dt
                vy = (y2 - y1) / dt
                velocities.append((t2, (vx, vy)))
        
        return velocities
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get buffer statistics for all players.
        
        Returns:
            Dictionary with buffer stats
        """
        stats = {
            'num_players': len(self.player_buffers),
            'window_size': self.window_size,
            'player_stats': {}
        }
        
        for player_id, buffer in self.player_buffers.items():
            stats['player_stats'][player_id] = {
                'frames_stored': len(buffer),
                'timestamp_range': (
                    buffer[0].timestamp if len(buffer) > 0 else None,
                    buffer[-1].timestamp if len(buffer) > 0 else None
                )
            }
        
        return stats


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Temporal Buffer Test ===\n")
    
    from .utils import FramePacket
    
    # Initialize buffer
    buffer = TemporalBuffer(window_size=15)
    
    # Simulate frame sequence
    print("1. Adding frames...")
    for i in range(20):
        state = "idle"
        has_ball = True
        
        # Jump sequence
        if 5 <= i < 10:
            state = "jumping"
        
        # Release at frame 8
        if i >= 8:
            has_ball = False
        
        frame = FramePacket(
            timestamp=100 + i,
            player_id=7,
            movement_state=state,
            movement_confidence=0.85,
            bbox_height=200.0 if state != "jumping" else 185.0,
            bbox_height_change=-15.0 if state == "jumping" else 0.0,
            ball_position=(300.0 + i*10, 200.0),
            has_ball=has_ball
        )
        
        buffer.add_frame(player_id=7, frame=frame)
    
    print(f"   Added 20 frames (buffer stores last {buffer.window_size})")
    print(f"   Current buffer size: {buffer.get_buffer_size(player_id=7)}")
    
    # Test window retrieval
    print("\n2. Getting recent window...")
    window = buffer.get_window(player_id=7, size=10)
    print(f"   Retrieved {len(window)} frames")
    print(f"   Timestamp range: {window[0].timestamp} - {window[-1].timestamp}")
    
    # Test state transition
    print("\n3. Finding state transitions...")
    jump_start = buffer.find_state_transition(
        player_id=7,
        from_state="idle",
        to_state="jumping"
    )
    print(f"   Jump started at frame: {jump_start}")
    
    # Test ownership change
    print("\n4. Finding ownership changes...")
    release_frame = buffer.find_ownership_change(
        player_id=7,
        from_state=True,
        to_state=False
    )
    print(f"   Ball released at frame: {release_frame}")
    
    # Test ball trajectory
    print("\n5. Analyzing ball trajectory...")
    velocities = buffer.calculate_ball_velocities(player_id=7, lookback=5)
    print(f"   Calculated {len(velocities)} velocity samples")
    if len(velocities) > 0:
        last_t, (vx, vy) = velocities[-1]
        print(f"   Last velocity: vx={vx:.2f}, vy={vy:.2f} px/frame")
    
    # Statistics
    print("\n6. Buffer statistics...")
    stats = buffer.get_statistics()
    print(f"   Players tracked: {stats['num_players']}")
    print(f"   Window size: {stats['window_size']}")
    for pid, pstats in stats['player_stats'].items():
        print(f"   Player {pid}: {pstats['frames_stored']} frames")