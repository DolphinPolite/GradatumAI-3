import numpy as np
from typing import Tuple


class KalmanFilter2D:
    """Simple 2D constant-velocity Kalman filter.

    State vector: [x, y, vx, vy]^T
    Measurements: [x, y]
    """

    def __init__(self, dt: float = 1.0, process_var: float = 1.0, meas_var: float = 1.0):
        self.dt = dt
        # State transition
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=float)

        # Measurement matrix
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=float)

        # Process noise covariance
        q = process_var
        self.Q = q * np.eye(4)

        # Measurement noise covariance
        r = meas_var
        self.R = r * np.eye(2)

        # Initialize state and covariance
        self.x = np.zeros((4, 1), dtype=float)
        self.P = np.eye(4, dtype=float)

    def initialize(self, pos: Tuple[float, float], vel: Tuple[float, float] = (0.0, 0.0)) -> None:
        self.x = np.array([[pos[0]], [pos[1]], [vel[0]], [vel[1]]], dtype=float)
        self.P = np.eye(4, dtype=float)

    def predict(self) -> Tuple[float, float]:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return float(self.x[0, 0]), float(self.x[1, 0])

    def update(self, meas: Tuple[float, float]) -> Tuple[float, float]:
        z = np.array([[meas[0]], [meas[1]]], dtype=float)
        y = z - (self.H @ self.x)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(self.P.shape[0])
        self.P = (I - K @ self.H) @ self.P
        return float(self.x[0, 0]), float(self.x[1, 0])


class KalmanTracker:
    """Lightweight tracker using KalmanFilter2D for player tracking.

    Usage:
        k = KalmanTracker(initial_pos=(x,y))
        k.predict()
        k.update((x_meas, y_meas))
        pos = k.position
    """

    def __init__(self, initial_pos: Tuple[float, float] = (0.0, 0.0), dt: float = 1.0):
        self.kf = KalmanFilter2D(dt=dt)
        self.kf.initialize(initial_pos)

    @property
    def position(self) -> Tuple[float, float]:
        return float(self.kf.x[0, 0]), float(self.kf.x[1, 0])

    def predict(self) -> Tuple[float, float]:
        return self.kf.predict()

    def update(self, meas: Tuple[float, float]) -> Tuple[float, float]:
        return self.kf.update(meas)
