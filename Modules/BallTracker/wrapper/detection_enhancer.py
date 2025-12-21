"""
Basketball Ball Tracker - Detection Enhancement Module

Purpose:
    Enhances the original ball detection with additional filtering and validation.
    Improves detection accuracy for orange basketball in varying conditions.

ML Pipeline Integration:
    - Provides confidence scores for each detection
    - Filters false positives before they enter tracking
    - Extracts visual features for potential ML augmentation

Usage:
    from wrappers.detection_enhancer import DetectionEnhancer
    
    enhancer = DetectionEnhancer(config, original_detector)
    bbox, confidence = enhancer.detect(frame)

Author: Ball Tracking Team
Date: 2025
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import os


class DetectionEnhancer:
    """
    Enhances ball detection with adaptive thresholding and filtering.
    
    Features:
        - HSV color-based filtering for orange basketball
        - Multi-scale circle detection
        - Adaptive threshold adjustment
        - Size consistency validation
        - Confidence scoring system
    
    Attributes:
        config: Configuration dictionary
        original_detector: Original BallDetectTrack instance
        adaptive_threshold: Current template matching threshold
        last_bbox: Last detected bbox for consistency check
    """
    
    def __init__(self, config: Dict[str, Any], original_detector=None):
        """
        Initialize detection enhancer.
        
        Args:
            config: Configuration from tracker_config.yaml
            original_detector: Original BallDetectTrack instance (optional)
        """
        self.config = config
        self.detection_config = config.get('detection', {})
        self.enhancer_config = config.get('detection_enhancer', {})
        self.original_detector = original_detector
        
        # Adaptive threshold
        self.base_threshold = self.detection_config.get('template_threshold', 0.80)
        self.adaptive_threshold = self.base_threshold
        
        # Adaptive threshold bounds
        adaptive_cfg = self.detection_config.get('adaptive_threshold', {})
        self.min_threshold = adaptive_cfg.get('min_threshold', 0.70)
        self.max_threshold = adaptive_cfg.get('max_threshold', 0.90)
        self.adaptive_enabled = adaptive_cfg.get('enabled', True)
        
        # Color filter settings
        color_cfg = self.detection_config.get('color_filter', {})
        self.color_enabled = color_cfg.get('enabled', True)
        self.hsv_lower = np.array(color_cfg.get('hsv_lower', [5, 100, 100]))
        self.hsv_upper = np.array(color_cfg.get('hsv_upper', [25, 255, 255]))
        self.min_orange_ratio = color_cfg.get('min_orange_ratio', 0.3)
        
        # Size consistency
        size_cfg = self.enhancer_config.get('size_consistency', {})
        self.size_check_enabled = size_cfg.get('enabled', True)
        self.max_size_change = size_cfg.get('max_size_change_ratio', 0.6)
        
        # Edge filtering
        edge_cfg = self.enhancer_config.get('edge_filtering', {})
        self.edge_filter_enabled = edge_cfg.get('enabled', True)
        self.edge_margin = edge_cfg.get('margin_pixels', 50)
        
        # Confidence weights
        self.conf_weights = self.enhancer_config.get('confidence_weights', {
            'template_match': 0.4,
            'color_match': 0.3,
            'size_consistency': 0.2,
            'motion_consistency': 0.1
        })
        
        # State tracking
        self.last_bbox = None
        self.detection_history = []  # For adaptive threshold
    
    # -------------------------------------------------------------------------
    # Main Detection Method
    # -------------------------------------------------------------------------
    
    def detect(self, frame: np.ndarray, 
               search_region: Optional[Tuple[int, int, int, int]] = None
              ) -> Tuple[Optional[Tuple[int, int, int, int]], float]:
        """
        Enhanced ball detection with filtering and validation.
        
        Args:
            frame: Input frame (BGR)
            search_region: Optional region to search (x, y, w, h)
        
        Returns:
            (bbox, confidence) tuple
            - bbox: (x, y, w, h) or None
            - confidence: 0-1 score
        """
        # Extract search region if specified
        if search_region is not None:
            x, y, w, h = search_region
            frame_crop = frame[y:y+h, x:x+w].copy()
            offset = (x, y)
        else:
            frame_crop = frame
            offset = (0, 0)
        
        # Step 1: Find candidates using circle detection
        candidates = self._detect_circles_multiscale(frame_crop)
        
        if candidates is None or len(candidates) == 0:
            return None, 0.0
        
        # Step 2: Filter by color (orange basketball)
        if self.color_enabled:
            candidates = self._filter_by_color(frame_crop, candidates)
            
            if len(candidates) == 0:
                return None, 0.0
        
        # Step 3: Create bounding boxes from circles
        bboxes = self._circles_to_bboxes(candidates)
        
        # Step 4: Filter by edge proximity
        if self.edge_filter_enabled:
            bboxes = [bb for bb in bboxes 
                     if not self._is_near_edge(bb, frame_crop.shape)]
        
        if len(bboxes) == 0:
            return None, 0.0
        
        # Step 5: Template matching validation
        best_bbox, match_score = self._template_match_validation(
            frame_crop, bboxes
        )
        
        if best_bbox is None:
            return None, 0.0
        
        # Step 6: Calculate comprehensive confidence
        confidence = self._calculate_confidence(
            frame_crop, best_bbox, match_score
        )
        
        # Adjust bbox to original frame coordinates
        best_bbox = (
            best_bbox[0] + offset[0],
            best_bbox[1] + offset[1],
            best_bbox[2],
            best_bbox[3]
        )
        
        # Update state
        self.last_bbox = best_bbox
        self.detection_history.append((best_bbox, confidence))
        
        # Adaptive threshold adjustment
        if self.adaptive_enabled:
            self._adjust_threshold(confidence)
        
        return best_bbox, confidence
    
    # -------------------------------------------------------------------------
    # Circle Detection
    # -------------------------------------------------------------------------
    
    def _detect_circles_multiscale(self, frame: np.ndarray
                                   ) -> Optional[np.ndarray]:
        """
        Detect circles at multiple scales.
        
        Args:
            frame: Input frame (BGR)
        
        Returns:
            Array of circles [x, y, radius] or None
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        
        # Get radius ranges from config
        circle_cfg = self.detection_config.get('circle_detection', {})
        radii_ranges = circle_cfg.get('radii_ranges', [[8, 15], [5, 12], [10, 18]])
        
        all_circles = []
        
        for min_r, max_r in radii_ranges:
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=circle_cfg.get('dp', 1),
                minDist=circle_cfg.get('min_dist', 20),
                param1=circle_cfg.get('param1', 50),
                param2=circle_cfg.get('param2', 25),
                minRadius=min_r,
                maxRadius=max_r
            )
            
            if circles is not None:
                circles = np.uint16(np.around(circles[0]))
                all_circles.extend(circles)
        
        if len(all_circles) == 0:
            return None
        
        # Remove duplicates (circles that are too close)
        all_circles = self._remove_duplicate_circles(all_circles)
        
        return np.array(all_circles) if len(all_circles) > 0 else None
    
    def _remove_duplicate_circles(self, circles: List, 
                                  threshold: float = 15.0) -> List:
        """
        Remove duplicate circles that are too close.
        
        Args:
            circles: List of [x, y, r] circles
            threshold: Distance threshold for duplicates
        
        Returns:
            Filtered list of circles
        """
        if len(circles) <= 1:
            return circles
        
        unique = []
        for circle in circles:
            is_duplicate = False
            for existing in unique:
                dist = np.sqrt((circle[0] - existing[0])**2 + 
                             (circle[1] - existing[1])**2)
                if dist < threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(circle)
        
        return unique
    
    # -------------------------------------------------------------------------
    # Color Filtering
    # -------------------------------------------------------------------------
    
    def _filter_by_color(self, frame: np.ndarray, 
                        circles: np.ndarray) -> np.ndarray:
        """
        Filter circles by orange color (basketball).
        
        Args:
            frame: Input frame (BGR)
            circles: Array of circles [x, y, radius]
        
        Returns:
            Filtered circles array
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        valid_circles = []
        
        for circle in circles:
            x, y, r = circle
            
            # Extract circular region
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.circle(mask, (x, y), r, 255, -1)
            
            # Count orange pixels in circle
            orange_mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
            orange_pixels = cv2.bitwise_and(orange_mask, mask)
            
            total_pixels = cv2.countNonZero(mask)
            orange_count = cv2.countNonZero(orange_pixels)
            
            if total_pixels > 0:
                orange_ratio = orange_count / total_pixels
                
                if orange_ratio >= self.min_orange_ratio:
                    valid_circles.append(circle)
        
        return np.array(valid_circles) if len(valid_circles) > 0 else np.array([])
    
    # -------------------------------------------------------------------------
    # Template Matching
    # -------------------------------------------------------------------------
    
    def _circles_to_bboxes(self, circles: np.ndarray, 
                          padding: int = 7) -> List[Tuple[int, int, int, int]]:
        """
        Convert circles to bounding boxes.
        
        Args:
            circles: Array of circles [x, y, radius]
            padding: Extra padding around circle
        
        Returns:
            List of bboxes (x, y, w, h)
        """
        bboxes = []
        
        for circle in circles:
            x, y, r = circle
            bbox = (
                max(0, x - r - padding),
                max(0, y - r - padding),
                2 * (r + padding),
                2 * (r + padding)
            )
            bboxes.append(bbox)
        
        return bboxes
    
    def _template_match_validation(self, frame: np.ndarray,
                                   bboxes: List[Tuple[int, int, int, int]]
                                  ) -> Tuple[Optional[Tuple], float]:
        """
        Validate candidates using template matching.
        
        Args:
            frame: Input frame (BGR)
            bboxes: List of candidate bboxes
        
        Returns:
            (best_bbox, match_score)
        """
        # Load ball templates
        template_dir = "resources/ball/"
        if not os.path.exists(template_dir):
            # Fallback: return first candidate with low confidence
            return bboxes[0] if len(bboxes) > 0 else None, 0.5
        
        templates = []
        for file in os.listdir(template_dir):
            if file.endswith(('.png', '.jpg', '.jpeg')):
                template = cv2.imread(os.path.join(template_dir, file), 0)
                if template is not None:
                    templates.append(template)
        
        if len(templates) == 0:
            return bboxes[0] if len(bboxes) > 0 else None, 0.5
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        best_bbox = None
        best_score = 0.0
        
        for bbox in bboxes:
            x, y, w, h = bbox
            
            # Extract region
            if x < 0 or y < 0 or x+w > frame.shape[1] or y+h > frame.shape[0]:
                continue
            
            roi = gray[y:y+h, x:x+w]
            
            if roi.size == 0:
                continue
            
            # Match against all templates
            for template in templates:
                if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
                    continue
                
                result = cv2.matchTemplate(roi, template, cv2.TM_CCORR_NORMED)
                score = np.max(result)
                
                if score > best_score and score >= self.adaptive_threshold:
                    best_score = score
                    best_bbox = bbox
        
        return best_bbox, best_score
    
    # -------------------------------------------------------------------------
    # Confidence Calculation
    # -------------------------------------------------------------------------
    
    def _calculate_confidence(self, frame: np.ndarray,
                             bbox: Tuple[int, int, int, int],
                             template_score: float) -> float:
        """
        Calculate comprehensive confidence score.
        
        Args:
            frame: Input frame
            bbox: Detected bbox
            template_score: Template match score
        
        Returns:
            Confidence (0-1)
        """
        confidence = 0.0
        
        # Template match component
        confidence += self.conf_weights['template_match'] * template_score
        
        # Color match component
        color_score = self._calculate_color_score(frame, bbox)
        confidence += self.conf_weights['color_match'] * color_score
        
        # Size consistency component
        if self.last_bbox is not None and self.size_check_enabled:
            size_score = self._calculate_size_consistency(bbox)
            confidence += self.conf_weights['size_consistency'] * size_score
        else:
            confidence += self.conf_weights['size_consistency'] * 0.5  # Neutral
        
        # Motion consistency (placeholder - can be improved with velocity)
        confidence += self.conf_weights['motion_consistency'] * 0.5
        
        return np.clip(confidence, 0.0, 1.0)
    
    def _calculate_color_score(self, frame: np.ndarray,
                              bbox: Tuple[int, int, int, int]) -> float:
        """Calculate color match score for orange basketball."""
        x, y, w, h = bbox
        roi = frame[y:y+h, x:x+w]
        
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        orange_mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        orange_ratio = cv2.countNonZero(orange_mask) / (w * h)
        
        # Convert ratio to score (0-1)
        return min(orange_ratio / self.min_orange_ratio, 1.0)
    
    def _calculate_size_consistency(self, bbox: Tuple[int, int, int, int]) -> float:
        """Calculate size consistency with previous detection."""
        if self.last_bbox is None:
            return 0.5
        
        prev_area = self.last_bbox[2] * self.last_bbox[3]
        curr_area = bbox[2] * bbox[3]
        
        if prev_area == 0:
            return 0.0
        
        ratio = abs(curr_area - prev_area) / prev_area
        
        # Convert to score (0 ratio = 1.0 score)
        score = 1.0 - min(ratio / self.max_size_change, 1.0)
        return score
    
    # -------------------------------------------------------------------------
    # Adaptive Threshold
    # -------------------------------------------------------------------------
    
    def _adjust_threshold(self, confidence: float):
        """
        Adjust template matching threshold based on detection confidence.
        
        Args:
            confidence: Latest detection confidence
        """
        # Increase threshold if confident, decrease if struggling
        if confidence > 0.8:
            self.adaptive_threshold = min(
                self.adaptive_threshold + 0.01,
                self.max_threshold
            )
        elif confidence < 0.6:
            self.adaptive_threshold = max(
                self.adaptive_threshold - 0.02,
                self.min_threshold
            )
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def _is_near_edge(self, bbox: Tuple[int, int, int, int],
                     frame_shape: Tuple[int, int]) -> bool:
        """Check if bbox is near frame edge."""
        x, y, w, h = bbox
        frame_h, frame_w = frame_shape[:2]
        
        margin = self.edge_margin
        
        if x < margin or y < margin:
            return True
        if x + w > frame_w - margin or y + h > frame_h - margin:
            return True
        
        return False