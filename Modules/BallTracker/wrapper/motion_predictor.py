"""
Basketball Ball Tracker - Motion Prediction Module

Purpose:
    Predicts ball position during occlusion using Kalman filter.
    Detects basketball bounces for dribbling analysis.

ML Pipeline Integration:
    - Provides smoothed velocity/acceleration features
    - Detects bounce events for action recognition
    - Fills gaps in trajectory for complete sequences

Usage:
    from wrappers.motion_predictor import MotionPredictor
    
    predictor = MotionPredictor(config)
    predictor.update(bbox, timestamp)
    predicted_bbox = predictor.predict()
    
    if predictor.detect_bounce():
        print("Ball bounced!")

Author: Ball Tracking Team
Date: 2024
"""

import numpy as np
from collections import deque
from typing import Optional, Tuple, List, Dict, Any


class MotionPredictor:
    """
    Kalman filter-based motion prediction for basketball tracking.
    
    Features:
        - 6-state Kalman filter (x, y, vx, vy, ax, ay)
        - Trajectory smoothing and interpolation
        - Basketball bounce detection
        - Search region generation for detection
        - Physics-based validation
    
    Attributes:
        kf: Kalman filter state
        trajectory: Recent ball positions
        velocities: Calculated velocities
        bounce_events: Detected bounce timestamps
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize motion predictor.
        
        Args:
            config: Configuration from tracker_config.yaml
        """
        self.config = config
        self.predictor_config = config.get('motion_predictor', {})
        self.bounce_config = self.predictor_config.get('bounce_detection', {})
        
        self.enabled = self.predictor_config.get('enabled', True)
        self.buffer_size = self.predictor_config.get('buffer_size', 30)
        self.max_occlusion = self.predictor_config.get('max_occlusion_frames', 8)
        self.interp_threshold = self.predictor_config.get('interpolation_threshold', 3)
        
        # Kalman filter parameters
        kalman_cfg = self.predictor_config.get('kalman', {})
        self.process_noise = kalman_cfg.get('process_noise', 0.01)
        self.measurement_noise = kalman_cfg.get('measurement_noise', 0.1)
        
        # Bounce detection parameters
        self.bounce_enabled = self.bounce_config.get('enabled', True)
        self.min_velocity_change = self.bounce_config.get('min_velocity_change', 20.0)
        self.min_bounce_interval = self.bounce_config.get('min_bounce_interval', 3)
        self.min_acceleration = self.bounce_config.get('min_acceleration', 5.0)
        self.gravity = self.bounce_config.get('gravity_constant', 0.5)
        
        # State tracking
        self.trajectory = deque(maxlen=self.buffer_size)
        self.velocities = deque(maxlen=self.buffer_size)
        self.accelerations = deque(maxlen=self.buffer_size)
        self.bounce_events = []
        
        # Kalman filter initialization
        self._init_kalman_filter()
        
        # Prediction state
        self.frames_since_update = 0
        self.is_predicting = False
        self.last_bounce_frame = -999
    
    # -------------------------------------------------------------------------
    # Kalman Filter Setup
    # -------------------------------------------------------------------------
    
    def _init_kalman_filter(self):
        """Initialize 6-state Kalman filter for 2D motion."""
        # State: [x, y, vx, vy, ax, ay]
        self.state = np.zeros((6, 1), dtype=np.float32)
        
        # State transition matrix (constant acceleration model)
        # x_new = x + vx*dt + 0.5*ax*dt^2
        dt = 1.0  # Assuming 1 frame interval
        self.F = np.array([
            [1, 0, dt, 0, 0.5*dt*dt, 0],
            [0, 1, 0, dt, 0, 0.5*dt*dt],
            [0, 0, 1, 0, dt, 0],
            [0, 0, 0, 1, 0, dt],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)
        
        # Measurement matrix (we measure only position)
        self.H = np.array([
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0]
        ], dtype=np.float32)
        
        # Process noise covariance
        q = self.process_noise
        self.Q = np.eye(6, dtype=np.float32) * q
        self.Q[4:, 4:] *= 10  # Higher noise for acceleration
        
        # Measurement noise covariance
        r = self.measurement_noise
        self.R = np.eye(2, dtype=np.float32) * r
        
        # Error covariance
        self.P = np.eye(6, dtype=np.float32) * 1.0
        
        # Initialized flag
        self.kf_initialized = False
    
    # -------------------------------------------------------------------------
    # Update and Prediction
    # -------------------------------------------------------------------------
    
    def update(self, bbox: Tuple[int, int, int, int], 
               timestamp: Optional[int] = None):
        """
        Update predictor with new measurement.
        
        Args:
            bbox: Detected bbox (x, y, w, h)
            timestamp: Frame timestamp
        """
        if not self.enabled:
            return
        
        # Calculate center position
        center = (bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2)
        
        # Add to trajectory
        self.trajectory.append({
            'timestamp': timestamp,
            'bbox': bbox,
            'center': center
        })
        
        # Calculate velocity
        if len(self.trajectory) >= 2:
            self._update_velocity()
        
        # Calculate acceleration
        if len(self.velocities) >= 2:
            self._update_acceleration()
        
        # Kalman filter update
        measurement = np.array([[center[0]], [center[1]]], dtype=np.float32)
        
        if not self.kf_initialized:
            # Initialize state
            self.state[0:2] = measurement
            self.kf_initialized = True
        else:
            # Kalman update step
            self._kalman_update(measurement)
        
        # Bounce detection
        if self.bounce_enabled and len(self.velocities) >= 3:
            self._check_for_bounce(timestamp)
        
        # Reset prediction state
        self.frames_since_update = 0
        self.is_predicting = False
    
    def predict(self, steps: int = 1) -> Optional[Tuple[int, int, int, int]]:
        """
        Predict ball position for next frame(s).
        
        Args:
            steps: Number of frames to predict ahead
        
        Returns:
            Predicted bbox (x, y, w, h) or None
        """
        if not self.enabled or not self.kf_initialized:
            return None
        
        if self.frames_since_update >= self.max_occlusion:
            return None
        
        # Kalman prediction step
        predicted_state = self.state.copy()
        for _ in range(steps):
            predicted_state = self.F @ predicted_state
        
        # Extract position
        x = int(predicted_state[0, 0])
        y = int(predicted_state[1, 0])
        
        # Use last known size
        if len(self.trajectory) > 0:
            last_bbox = self.trajectory[-1]['bbox']
            w, h = last_bbox[2], last_bbox[3]
        else:
            w, h = 20, 20  # Default size
        
        predicted_bbox = (x - w//2, y - h//2, w, h)
        
        self.frames_since_update += 1
        self.is_predicting = True
        
        return predicted_bbox
    
    def _kalman_update(self, measurement: np.ndarray):
        """Kalman filter update step."""
        # Prediction
        state_pred = self.F @ self.state
        P_pred = self.F @ self.P @ self.F.T + self.Q
        
        # Innovation
        y = measurement - self.H @ state_pred
        S = self.H @ P_pred @ self.H.T + self.R
        
        # Kalman gain
        K = P_pred @ self.H.T @ np.linalg.inv(S)
        
        # Update
        self.state = state_pred + K @ y
        self.P = (np.eye(6) - K @ self.H) @ P_pred
    
    # -------------------------------------------------------------------------
    # Velocity and Acceleration
    # -------------------------------------------------------------------------
    
    def _update_velocity(self):
        """Calculate velocity from last two positions."""
        if len(self.trajectory) < 2:
            return
        
        curr = self.trajectory[-1]['center']
        prev = self.trajectory[-2]['center']
        
        vx = curr[0] - prev[0]
        vy = curr[1] - prev[1]
        
        self.velocities.append((vx, vy))
    
    def _update_acceleration(self):
        """Calculate acceleration from last two velocities."""
        if len(self.velocities) < 2:
            return
        
        curr_v = self.velocities[-1]
        prev_v = self.velocities[-2]
        
        ax = curr_v[0] - prev_v[0]
        ay = curr_v[1] - prev_v[1]
        
        self.accelerations.append((ax, ay))
    
    def get_current_velocity(self) -> Tuple[float, float]:
        """Get current velocity estimate."""
        if len(self.velocities) > 0:
            return self.velocities[-1]
        return (0.0, 0.0)
    
    def get_current_acceleration(self) -> Tuple[float, float]:
        """Get current acceleration estimate."""
        if len(self.accelerations) > 0:
            return self.accelerations[-1]
        return (0.0, 0.0)
    
    # -------------------------------------------------------------------------
    # Bounce Detection
    # -------------------------------------------------------------------------
    
    def _check_for_bounce(self, timestamp: Optional[int]):
        """
        Detect basketball bounce from velocity changes.
        
        Basketball bounce signature:
        - Large upward acceleration (negative vy becomes less negative)
        - Occurs at local minimum y position
        - Vertical velocity reversal
        """
        if len(self.velocities) < 3:
            return
        
        # Check minimum frame interval since last bounce
        if timestamp is not None:
            if timestamp - self.last_bounce_frame < self.min_bounce_interval:
                return
        
        # Get recent velocities
        v_curr = self.velocities[-1]
        v_prev = self.velocities[-2]
        v_prev2 = self.velocities[-3]
        
        # Vertical velocity change
        vy_change = v_curr[1] - v_prev[1]
        
        # Check for upward acceleration (bounce)
        # In image coordinates: y increases downward, so bounce = negative acceleration
        if vy_change < -self.min_velocity_change:
            # Verify this is near a local minimum (ball was going down, now going up)
            if v_prev[1] > 0 and v_curr[1] < v_prev[1]:
                # Calculate vertical acceleration
                ay = abs(vy_change)
                
                if ay >= self.min_acceleration:
                    # Bounce detected!
                    self.bounce_events.append({
                        'timestamp': timestamp,
                        'position': self.trajectory[-1]['center'],
                        'velocity_before': v_prev[1],
                        'velocity_after': v_curr[1],
                        'acceleration': ay
                    })
                    
                    self.last_bounce_frame = timestamp if timestamp else 0
    
    def get_bounce_events(self) -> List[Dict]:
        """Get all detected bounce events."""
        return self.bounce_events
    
    def clear_bounce_events(self):
        """Clear bounce event history."""
        self.bounce_events.clear()
    
    # -------------------------------------------------------------------------
    # Interpolation
    # -------------------------------------------------------------------------
    
    def interpolate_trajectory(self, gap_start: int, gap_end: int
                              ) -> List[Tuple[int, int, int, int]]:
        """
        Interpolate missing trajectory during short occlusion.
        
        Args:
            gap_start: Frame ID where occlusion started
            gap_end: Frame ID where ball reappeared
        
        Returns:
            List of interpolated bboxes
        """
        gap_length = gap_end - gap_start - 1
        
        if gap_length <= 0 or gap_length > self.interp_threshold:
            return []
        
        if len(self.trajectory) < 2:
            return []
        
        # Get positions before and after gap
        # (Assuming trajectory is updated when ball reappears)
        pos_after = self.trajectory[-1]['center']
        bbox_after = self.trajectory[-1]['bbox']
        
        # Find position before gap
        pos_before = None
        bbox_before = None
        for entry in reversed(list(self.trajectory)[:-1]):
            if entry['timestamp'] < gap_start:
                pos_before = entry['center']
                bbox_before = entry['bbox']
                break
        
        if pos_before is None:
            return []
        
        # Linear interpolation
        interpolated = []
        for i in range(1, gap_length + 1):
            t = i / (gap_length + 1)
            
            x = int(pos_before[0] + t * (pos_after[0] - pos_before[0]))
            y = int(pos_before[1] + t * (pos_after[1] - pos_before[1]))
            
            w = int(bbox_before[2] + t * (bbox_after[2] - bbox_before[2]))
            h = int(bbox_before[3] + t * (bbox_after[3] - bbox_before[3]))
            
            bbox = (x - w//2, y - h//2, w, h)
            interpolated.append(bbox)
        
        return interpolated
    
    # -------------------------------------------------------------------------
    # Search Region Generation
    # -------------------------------------------------------------------------
    
    def get_search_region(self, margin: int = 50
                         ) -> Optional[Tuple[int, int, int, int]]:
        """
        Generate search region for detection based on prediction.
        
        Args:
            margin: Margin around predicted position (pixels)
        
        Returns:
            Search region bbox (x, y, w, h) or None
        """
        predicted_bbox = self.predict()
        
        if predicted_bbox is None:
            return None
        
        x, y, w, h = predicted_bbox
        
        # Expand region
        search_x = max(0, x - margin)
        search_y = max(0, y - margin)
        search_w = w + 2 * margin
        search_h = h + 2 * margin
        
        return (search_x, search_y, search_w, search_h)
    
    # -------------------------------------------------------------------------
    # Trajectory Smoothing
    # -------------------------------------------------------------------------
    
    def get_smoothed_trajectory(self, window_size: int = 5
                               ) -> List[Tuple[int, int]]:
        """
        Get smoothed trajectory using moving average.
        
        Args:
            window_size: Smoothing window size
        
        Returns:
            List of smoothed (x, y) positions
        """
        if len(self.trajectory) < window_size:
            return [entry['center'] for entry in self.trajectory]
        
        smoothed = []
        traj_list = list(self.trajectory)
        
        for i in range(len(traj_list)):
            start = max(0, i - window_size // 2)
            end = min(len(traj_list), i + window_size // 2 + 1)
            
            window = traj_list[start:end]
            
            avg_x = sum(entry['center'][0] for entry in window) / len(window)
            avg_y = sum(entry['center'][1] for entry in window) / len(window)
            
            smoothed.append((int(avg_x), int(avg_y)))
        
        return smoothed
    
    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    
    def validate_measurement(self, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Validate if new measurement is physically plausible.
        
        Args:
            bbox: New measurement bbox
        
        Returns:
            True if measurement is valid
        """
        if len(self.trajectory) == 0:
            return True
        
        # Check position jump
        last_center = self.trajectory[-1]['center']
        new_center = (bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2)
        
        dx = new_center[0] - last_center[0]
        dy = new_center[1] - last_center[1]
        distance = np.sqrt(dx**2 + dy**2)
        
        max_jump = self.config.get('validation', {}).get('max_position_jump', 200)
        
        if distance > max_jump:
            return False
        
        # Check velocity
        if len(self.velocities) > 0:
            max_vel = self.config.get('validation', {}).get('max_velocity', 80.0)
            if distance > max_vel:
                return False
        
        return True
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def reset(self):
        """Reset predictor state."""
        self.trajectory.clear()
        self.velocities.clear()
        self.accelerations.clear()
        self.bounce_events.clear()
        self._init_kalman_filter()
        self.frames_since_update = 0
        self.is_predicting = False
    
    def get_state_dict(self) -> Dict[str, Any]:
        """
        Get current state for logging/debugging.
        
        Returns:
            Dictionary with current state information
        """
        return {
            'trajectory_length': len(self.trajectory),
            'current_position': self.trajectory[-1]['center'] if self.trajectory else None,
            'current_velocity': self.get_current_velocity(),
            'current_acceleration': self.get_current_acceleration(),
            'bounce_count': len(self.bounce_events),
            'frames_since_update': self.frames_since_update,
            'is_predicting': self.is_predicting
        }