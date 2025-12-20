"""
Basketball Ball Tracker - Input/Output Validation Layer

Purpose:
    Validates all inputs and outputs to prevent crashes and data corruption.
    Acts as a defensive layer around the core tracking logic.

ML Pipeline Integration:
    - Ensures clean data for downstream models
    - Catches edge cases that could corrupt training data
    - Provides sanitized bounding boxes

Usage:
    from wrappers.validation_layer import ValidationLayer
    
    validator = ValidationLayer(config)
    
    # Validate before processing
    is_valid, error = validator.validate_frame(frame)
    bbox = validator.sanitize_bbox(raw_bbox, frame.shape)

Author: Ball Tracking Team
Date: 2025
"""

import numpy as np
import cv2
from typing import Tuple, Optional, List, Any, Dict


class ValidationLayer:
    """
    Validates and sanitizes data for ball tracking system.
    
    Features:
        - Frame validation (shape, type, values)
        - Bounding box validation and clipping
        - Homography matrix validation
        - Player data validation
        - Motion validation (velocity, acceleration)
    
    Attributes:
        config: Configuration dictionary with validation parameters
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validation layer.
        
        Args:
            config: Configuration from tracker_config.yaml
        """
        self.config = config
        self.val_config = config.get('validation', {})
        
        # Extract validation parameters
        self.min_bbox_size = self.val_config.get('min_bbox_size', 8)
        self.max_bbox_size = self.val_config.get('max_bbox_size', 120)
        self.max_position_jump = self.val_config.get('max_position_jump', 200)
        self.max_velocity = self.val_config.get('max_velocity', 80.0)
        self.max_acceleration = self.val_config.get('max_acceleration', 15.0)
        
        self.min_frame_width = self.val_config.get('min_frame_width', 320)
        self.min_frame_height = self.val_config.get('min_frame_height', 240)
    
    # -------------------------------------------------------------------------
    # Frame Validation
    # -------------------------------------------------------------------------
    
    def validate_frame(self, frame: np.ndarray) -> Tuple[bool, Optional[str]]:
        """
        Validate video frame.
        
        Args:
            frame: Input frame (numpy array)
        
        Returns:
            (is_valid, error_message)
            - is_valid: True if frame is valid
            - error_message: None if valid, error string otherwise
        """
        # Check if None
        if frame is None:
            return False, "Frame is None"
        
        # Check if numpy array
        if not isinstance(frame, np.ndarray):
            return False, f"Frame must be numpy array, got {type(frame)}"
        
        # Check dimensions
        if frame.ndim not in [2, 3]:
            return False, f"Frame must be 2D or 3D, got {frame.ndim}D"
        
        # Check shape
        height, width = frame.shape[:2]
        if height < self.min_frame_height or width < self.min_frame_width:
            return False, f"Frame too small: {width}x{height}"
        
        # Check data type
        if frame.dtype not in [np.uint8, np.float32, np.float64]:
            return False, f"Unsupported dtype: {frame.dtype}"
        
        # Check if BGR (3 channels)
        if frame.ndim == 3 and frame.shape[2] != 3:
            return False, f"Expected 3 channels (BGR), got {frame.shape[2]}"
        
        return True, None
    
    # -------------------------------------------------------------------------
    # Bounding Box Validation
    # -------------------------------------------------------------------------
    
    def validate_bbox(self, bbox: Optional[Tuple[int, int, int, int]], 
                     frame_shape: Tuple[int, int]) -> Tuple[bool, Optional[str]]:
        """
        Validate bounding box.
        
        Args:
            bbox: Bounding box (x, y, w, h) or None
            frame_shape: Frame shape (height, width)
        
        Returns:
            (is_valid, error_message)
        """
        # Check if None
        if bbox is None:
            return False, "Bbox is None"
        
        # Check tuple length
        if len(bbox) != 4:
            return False, f"Bbox must have 4 elements, got {len(bbox)}"
        
        x, y, w, h = bbox
        frame_h, frame_w = frame_shape[:2]
        
        # Check for negative or zero dimensions
        if w <= 0 or h <= 0:
            return False, f"Bbox dimensions must be positive: w={w}, h={h}"
        
        # Check size constraints
        if w < self.min_bbox_size or h < self.min_bbox_size:
            return False, f"Bbox too small: {w}x{h} (min: {self.min_bbox_size})"
        
        if w > self.max_bbox_size or h > self.max_bbox_size:
            return False, f"Bbox too large: {w}x{h} (max: {self.max_bbox_size})"
        
        # Check if completely outside frame
        if x + w < 0 or y + h < 0 or x >= frame_w or y >= frame_h:
            return False, f"Bbox completely outside frame: ({x},{y},{w},{h})"
        
        return True, None
    
    def sanitize_bbox(self, bbox: Tuple[int, int, int, int],
                     frame_shape: Tuple[int, int]) -> Optional[Tuple[int, int, int, int]]:
        """
        Clip and fix bounding box to be within frame boundaries.
        
        Args:
            bbox: Raw bounding box (x, y, w, h)
            frame_shape: Frame shape (height, width)
        
        Returns:
            Sanitized bbox or None if bbox is invalid
        """
        if bbox is None:
            return None
        
        x, y, w, h = map(int, bbox)
        frame_h, frame_w = frame_shape[:2]
        
        # Ensure positive dimensions
        if w <= 0 or h <= 0:
            return None
        
        # Clip to frame boundaries
        x = max(0, min(x, frame_w - 1))
        y = max(0, min(y, frame_h - 1))
        
        # Adjust width and height to fit frame
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        
        # Check minimum size after clipping
        if w < self.min_bbox_size or h < self.min_bbox_size:
            return None
        
        return (x, y, w, h)
    
    def bbox_overlap_ratio(self, bbox1: Tuple[int, int, int, int],
                          bbox2: Tuple[int, int, int, int]) -> float:
        """
        Calculate overlap ratio between two bounding boxes (IoU).
        
        Args:
            bbox1: First bbox (x, y, w, h)
            bbox2: Second bbox (x, y, w, h)
        
        Returns:
            IoU value (0-1)
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    # -------------------------------------------------------------------------
    # Homography Validation
    # -------------------------------------------------------------------------
    
    def validate_homography(self, M: Optional[np.ndarray]) -> Tuple[bool, Optional[str]]:
        """
        Validate homography matrix.
        
        Args:
            M: 3x3 homography matrix
        
        Returns:
            (is_valid, error_message)
        """
        if M is None:
            return False, "Homography matrix is None"
        
        if not isinstance(M, np.ndarray):
            return False, f"Matrix must be numpy array, got {type(M)}"
        
        if M.shape != (3, 3):
            return False, f"Matrix must be 3x3, got {M.shape}"
        
        # Check if matrix is singular
        det = np.linalg.det(M)
        if abs(det) < 1e-6:
            return False, f"Matrix is singular (det={det})"
        
        # Check for NaN or Inf
        if np.any(np.isnan(M)) or np.any(np.isinf(M)):
            return False, "Matrix contains NaN or Inf values"
        
        return True, None
    
    def transform_point_safe(self, point: Tuple[int, int], 
                            M: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Safely transform point using homography.
        
        Args:
            point: Point (x, y)
            M: 3x3 homography matrix
        
        Returns:
            Transformed point or None if transformation fails
        """
        # Validate homography
        is_valid, _ = self.validate_homography(M)
        if not is_valid:
            return None
        
        try:
            # Convert to homogeneous coordinates
            point_h = np.array([point[0], point[1], 1.0]).reshape(3, 1)
            
            # Transform
            result = M @ point_h
            
            # Check for zero division
            if abs(result[2, 0]) < 1e-6:
                return None
            
            # Convert back to Cartesian
            x = int(result[0, 0] / result[2, 0])
            y = int(result[1, 0] / result[2, 0])
            
            return (x, y)
        
        except Exception:
            return None
    
    # -------------------------------------------------------------------------
    # Motion Validation
    # -------------------------------------------------------------------------
    
    def validate_motion(self, prev_bbox: Tuple[int, int, int, int],
                       curr_bbox: Tuple[int, int, int, int],
                       dt: float = 1.0) -> Tuple[bool, Optional[str]]:
        """
        Validate motion between two bounding boxes.
        
        Args:
            prev_bbox: Previous bbox (x, y, w, h)
            curr_bbox: Current bbox (x, y, w, h)
            dt: Time difference in frames (default: 1)
        
        Returns:
            (is_valid, error_message)
        """
        # Calculate center displacement
        prev_center = (prev_bbox[0] + prev_bbox[2]//2, prev_bbox[1] + prev_bbox[3]//2)
        curr_center = (curr_bbox[0] + curr_bbox[2]//2, curr_bbox[1] + curr_bbox[3]//2)
        
        dx = curr_center[0] - prev_center[0]
        dy = curr_center[1] - prev_center[1]
        distance = np.sqrt(dx**2 + dy**2)
        
        # Check position jump
        if distance > self.max_position_jump:
            return False, f"Position jump too large: {distance:.1f}px (max: {self.max_position_jump})"
        
        # Calculate velocity
        velocity = distance / dt
        if velocity > self.max_velocity:
            return False, f"Velocity too high: {velocity:.1f}px/frame (max: {self.max_velocity})"
        
        return True, None
    
    def validate_size_consistency(self, prev_bbox: Tuple[int, int, int, int],
                                 curr_bbox: Tuple[int, int, int, int],
                                 max_ratio: float = 0.6) -> Tuple[bool, Optional[str]]:
        """
        Validate bbox size consistency between frames.
        
        Args:
            prev_bbox: Previous bbox (x, y, w, h)
            curr_bbox: Current bbox (x, y, w, h)
            max_ratio: Maximum size change ratio (default: 0.6 = 60%)
        
        Returns:
            (is_valid, error_message)
        """
        prev_area = prev_bbox[2] * prev_bbox[3]
        curr_area = curr_bbox[2] * curr_bbox[3]
        
        if prev_area == 0:
            return False, "Previous bbox has zero area"
        
        ratio = abs(curr_area - prev_area) / prev_area
        
        if ratio > max_ratio:
            return False, f"Size change too large: {ratio:.1%} (max: {max_ratio:.1%})"
        
        return True, None
    
    # -------------------------------------------------------------------------
    # Player Data Validation
    # -------------------------------------------------------------------------
    
    def validate_players(self, players: List[Any], 
                        timestamp: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate player list and their positions.
        
        Args:
            players: List of player objects
            timestamp: Current timestamp
        
        Returns:
            (is_valid, error_message)
        """
        if players is None:
            return False, "Players list is None"
        
        if not isinstance(players, list):
            return False, f"Players must be list, got {type(players)}"
        
        if len(players) == 0:
            return False, "Players list is empty"
        
        # Check if players have required attributes
        for i, player in enumerate(players):
            if not hasattr(player, 'positions'):
                return False, f"Player {i} missing 'positions' attribute"
            
            if not hasattr(player, 'team'):
                return False, f"Player {i} missing 'team' attribute"
            
            # Check if position exists for current timestamp
            try:
                if timestamp not in player.positions:
                    # This is not necessarily an error, player might not be visible
                    pass
            except (TypeError, AttributeError):
                return False, f"Player {i} positions not accessible"
        
        return True, None
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def is_bbox_near_edge(self, bbox: Tuple[int, int, int, int],
                         frame_shape: Tuple[int, int],
                         margin: int = 50) -> bool:
        """
        Check if bounding box is near frame edge.
        
        Args:
            bbox: Bounding box (x, y, w, h)
            frame_shape: Frame shape (height, width)
            margin: Margin in pixels
        
        Returns:
            True if bbox is near edge
        """
        x, y, w, h = bbox
        frame_h, frame_w = frame_shape[:2]
        
        if x < margin or y < margin:
            return True
        if x + w > frame_w - margin or y + h > frame_h - margin:
            return True
        
        return False