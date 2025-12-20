"""
Basketball Ball Tracker - Multi-Tracker Management Module

Purpose:
    Manages multiple trackers with fallback strategies for robust tracking.
    Switches between tracker types based on performance and conditions.

ML Pipeline Integration:
    - Provides tracking confidence scores
    - Logs tracker failures for system analysis
    - Enables robust tracking for continuous data streams

Usage:
    from wrappers.tracker_manager import TrackerManager
    
    manager = TrackerManager(config)
    manager.init(frame, bbox)
    success, bbox = manager.update(frame)
    
    if not success:
        manager.switch_to_backup()

Author: Ball Tracking Team
Date: 2024
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from collections import defaultdict


class TrackerManager:
    """
    Manages multiple OpenCV trackers with automatic fallback.
    
    Features:
        - Primary-backup cascade strategy
        - Voting-based consensus from multiple trackers
        - Automatic tracker switching on failure
        - Performance-based tracker selection
        - Periodic reset to primary tracker
    
    Attributes:
        trackers: Dictionary of tracker instances
        active_tracker: Currently active tracker name
        tracker_stats: Performance statistics per tracker
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize tracker manager.
        
        Args:
            config: Configuration from tracker_config.yaml
        """
        self.config = config
        self.manager_config = config.get('tracker_manager', {})
        
        # Strategy: "primary_backup" or "voting"
        self.strategy = self.manager_config.get('strategy', 'primary_backup')
        
        # Tracker types from config
        tracker_types = config.get('tracker', {}).get('tracker_types', ['KCF', 'CSRT'])
        
        # Initialize trackers
        self.trackers = {}
        self.tracker_states = {}  # Success/fail state
        for tracker_type in tracker_types:
            self.trackers[tracker_type] = None  # Will be created on init
            self.tracker_states[tracker_type] = 'ready'
        
        # Primary tracker
        self.primary_tracker = tracker_types[0] if tracker_types else 'KCF'
        self.active_tracker = self.primary_tracker
        
        # Fallback management
        self.fallback_timeout = self.manager_config.get('fallback_timeout', 10)
        self.reset_interval = self.manager_config.get('reset_interval', 50)
        self.min_confidence = self.manager_config.get('min_tracker_confidence', 0.5)
        
        # Voting settings
        voting_cfg = self.manager_config.get('voting', {})
        self.min_agreement = voting_cfg.get('min_agreement', 2)
        self.max_bbox_distance = voting_cfg.get('max_bbox_distance', 30)
        
        # State tracking
        self.failure_counts = defaultdict(int)
        self.success_counts = defaultdict(int)
        self.frames_since_init = 0
        self.frames_since_failure = defaultdict(int)
        
        # Current bbox (last successful update)
        self.current_bbox = None
        
        # Initialized flag
        self.is_initialized = False
    
    # -------------------------------------------------------------------------
    # Tracker Creation
    # -------------------------------------------------------------------------
    
    def _create_tracker(self, tracker_type: str):
        """
        Create OpenCV tracker instance.
        
        Args:
            tracker_type: Tracker type ('CSRT', 'KCF', 'MOSSE', etc.)
        
        Returns:
            Tracker instance or None
        """
        tracker_type = tracker_type.upper()
        
        try:
            if tracker_type == 'CSRT':
                return cv2.TrackerCSRT_create()
            elif tracker_type == 'KCF':
                return cv2.TrackerKCF_create()
            elif tracker_type == 'MOSSE':
                return cv2.legacy.TrackerMOSSE_create()
            elif tracker_type == 'MEDIANFLOW':
                return cv2.legacy.TrackerMedianFlow_create()
            elif tracker_type == 'BOOSTING':
                return cv2.legacy.TrackerBoosting_create()
            elif tracker_type == 'MIL':
                return cv2.TrackerMIL_create()
            elif tracker_type == 'TLD':
                return cv2.legacy.TrackerTLD_create()
            else:
                # Default to KCF
                return cv2.TrackerKCF_create()
        except Exception as e:
            print(f"Warning: Could not create {tracker_type} tracker: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------
    
    def init(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Initialize all trackers with frame and bbox.
        
        Args:
            frame: Input frame (BGR)
            bbox: Initial bounding box (x, y, w, h)
        
        Returns:
            True if at least one tracker initialized successfully
        """
        if bbox is None:
            return False
        
        success_count = 0
        
        for tracker_type in self.trackers.keys():
            # Create new tracker instance
            tracker = self._create_tracker(tracker_type)
            
            if tracker is None:
                self.tracker_states[tracker_type] = 'unavailable'
                continue
            
            # Initialize tracker
            try:
                init_success = tracker.init(frame, bbox)
                
                if init_success:
                    self.trackers[tracker_type] = tracker
                    self.tracker_states[tracker_type] = 'active'
                    success_count += 1
                else:
                    self.tracker_states[tracker_type] = 'failed'
            
            except Exception as e:
                print(f"Warning: Failed to init {tracker_type}: {e}")
                self.tracker_states[tracker_type] = 'failed'
        
        if success_count > 0:
            self.is_initialized = True
            self.current_bbox = bbox
            self.frames_since_init = 0
            self.active_tracker = self.primary_tracker
            return True
        
        return False
    
    def reinit(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Reinitialize trackers with new detection.
        
        Args:
            frame: Input frame
            bbox: New bounding box
        
        Returns:
            True if reinitialization successful
        """
        # Reset failure counts
        for tracker_type in self.trackers.keys():
            self.failure_counts[tracker_type] = 0
            self.frames_since_failure[tracker_type] = 0
        
        return self.init(frame, bbox)
    
    # -------------------------------------------------------------------------
    # Update Methods
    # -------------------------------------------------------------------------
    
    def update(self, frame: np.ndarray) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Update tracker(s) based on strategy.
        
        Args:
            frame: Input frame
        
        Returns:
            (success, bbox) tuple
        """
        if not self.is_initialized:
            return False, None
        
        self.frames_since_init += 1
        
        # Update frames since failure for each tracker
        for tracker_type in self.trackers.keys():
            if self.tracker_states[tracker_type] == 'failed':
                self.frames_since_failure[tracker_type] += 1
        
        # Check if we should reset to primary tracker
        if self.frames_since_init % self.reset_interval == 0:
            self._attempt_primary_reset(frame)
        
        # Execute strategy
        if self.strategy == 'primary_backup':
            return self._update_primary_backup(frame)
        elif self.strategy == 'voting':
            return self._update_voting(frame)
        else:
            # Default to primary_backup
            return self._update_primary_backup(frame)
    
    def _update_primary_backup(self, frame: np.ndarray
                              ) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Primary-backup cascade strategy.
        
        Try active tracker, fallback to next on failure.
        """
        # Try active tracker first
        if self.tracker_states[self.active_tracker] == 'active':
            success, bbox = self._update_single_tracker(frame, self.active_tracker)
            
            if success:
                self.current_bbox = bbox
                self.success_counts[self.active_tracker] += 1
                return True, bbox
            else:
                # Active tracker failed
                self.tracker_states[self.active_tracker] = 'failed'
                self.failure_counts[self.active_tracker] += 1
                self.frames_since_failure[self.active_tracker] = 0
        
        # Try to switch to backup
        return self._switch_to_backup(frame)
    
    def _update_voting(self, frame: np.ndarray
                      ) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Voting strategy: run all trackers, use consensus.
        """
        results = []
        
        # Update all active trackers
        for tracker_type, tracker in self.trackers.items():
            if self.tracker_states[tracker_type] == 'active':
                success, bbox = self._update_single_tracker(frame, tracker_type)
                
                if success:
                    results.append((tracker_type, bbox))
                else:
                    self.tracker_states[tracker_type] = 'failed'
                    self.failure_counts[tracker_type] += 1
        
        # Check if we have enough agreements
        if len(results) < self.min_agreement:
            return False, None
        
        # Find consensus bbox
        consensus_bbox = self._find_consensus(results)
        
        if consensus_bbox is not None:
            self.current_bbox = consensus_bbox
            return True, consensus_bbox
        
        return False, None
    
    def _update_single_tracker(self, frame: np.ndarray, tracker_type: str
                              ) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Update a single tracker.
        
        Args:
            frame: Input frame
            tracker_type: Tracker to update
        
        Returns:
            (success, bbox)
        """
        tracker = self.trackers.get(tracker_type)
        
        if tracker is None:
            return False, None
        
        try:
            success, bbox = tracker.update(frame)
            
            if success and bbox is not None:
                # Validate bbox
                bbox = tuple(map(int, bbox))
                
                # Basic sanity check
                if bbox[2] > 0 and bbox[3] > 0:
                    return True, bbox
            
            return False, None
        
        except Exception as e:
            print(f"Warning: Tracker {tracker_type} update failed: {e}")
            return False, None
    
    # -------------------------------------------------------------------------
    # Fallback Management
    # -------------------------------------------------------------------------
    
    def _switch_to_backup(self, frame: np.ndarray
                         ) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Switch to next available backup tracker.
        
        Args:
            frame: Current frame
        
        Returns:
            (success, bbox) from backup tracker
        """
        # Get list of tracker types
        tracker_types = list(self.trackers.keys())
        
        # Try each tracker in order
        for tracker_type in tracker_types:
            if tracker_type == self.active_tracker:
                continue  # Skip current failed tracker
            
            # Check if tracker is ready or has cooled down
            if self.tracker_states[tracker_type] == 'active':
                # Try this tracker
                success, bbox = self._update_single_tracker(frame, tracker_type)
                
                if success:
                    # Switch to this tracker
                    self.active_tracker = tracker_type
                    self.current_bbox = bbox
                    self.success_counts[tracker_type] += 1
                    return True, bbox
            
            elif self.tracker_states[tracker_type] == 'failed':
                # Check if timeout has passed
                if self.frames_since_failure[tracker_type] >= self.fallback_timeout:
                    # Try to reinitialize this tracker
                    if self.current_bbox is not None:
                        tracker = self._create_tracker(tracker_type)
                        if tracker is not None:
                            try:
                                tracker.init(frame, self.current_bbox)
                                self.trackers[tracker_type] = tracker
                                self.tracker_states[tracker_type] = 'active'
                                
                                # Try to update
                                success, bbox = self._update_single_tracker(frame, tracker_type)
                                if success:
                                    self.active_tracker = tracker_type
                                    self.current_bbox = bbox
                                    return True, bbox
                            except:
                                pass
        
        # All trackers failed
        return False, None
    
    def _attempt_primary_reset(self, frame: np.ndarray):
        """
        Attempt to reset to primary tracker if available.
        
        Args:
            frame: Current frame
        """
        if self.active_tracker == self.primary_tracker:
            return  # Already on primary
        
        if self.tracker_states[self.primary_tracker] == 'failed':
            # Try to reinitialize primary
            if self.current_bbox is not None:
                tracker = self._create_tracker(self.primary_tracker)
                if tracker is not None:
                    try:
                        tracker.init(frame, self.current_bbox)
                        self.trackers[self.primary_tracker] = tracker
                        self.tracker_states[self.primary_tracker] = 'active'
                        self.active_tracker = self.primary_tracker
                    except:
                        pass
    
    # -------------------------------------------------------------------------
    # Consensus Methods (for Voting Strategy)
    # -------------------------------------------------------------------------
    
    def _find_consensus(self, results: List[Tuple[str, Tuple[int, int, int, int]]]
                       ) -> Optional[Tuple[int, int, int, int]]:
        """
        Find consensus bounding box from multiple tracker results.
        
        Args:
            results: List of (tracker_type, bbox) tuples
        
        Returns:
            Consensus bbox or None
        """
        if len(results) < self.min_agreement:
            return None
        
        # Calculate center points
        centers = []
        for _, bbox in results:
            cx = bbox[0] + bbox[2] / 2
            cy = bbox[1] + bbox[3] / 2
            centers.append((cx, cy))
        
        # Find clusters of similar positions
        clusters = []
        for i, center in enumerate(centers):
            added_to_cluster = False
            
            for cluster in clusters:
                # Check if center is close to cluster
                cluster_center = np.mean([centers[j] for j in cluster], axis=0)
                dist = np.sqrt((center[0] - cluster_center[0])**2 + 
                             (center[1] - cluster_center[1])**2)
                
                if dist < self.max_bbox_distance:
                    cluster.append(i)
                    added_to_cluster = True
                    break
            
            if not added_to_cluster:
                clusters.append([i])
        
        # Find largest cluster
        largest_cluster = max(clusters, key=len)
        
        if len(largest_cluster) < self.min_agreement:
            return None
        
        # Average bboxes in largest cluster
        cluster_bboxes = [results[i][1] for i in largest_cluster]
        
        avg_x = int(np.mean([b[0] for b in cluster_bboxes]))
        avg_y = int(np.mean([b[1] for b in cluster_bboxes]))
        avg_w = int(np.mean([b[2] for b in cluster_bboxes]))
        avg_h = int(np.mean([b[3] for b in cluster_bboxes]))
        
        return (avg_x, avg_y, avg_w, avg_h)
    
    # -------------------------------------------------------------------------
    # Statistics and State
    # -------------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get tracking statistics for all trackers.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            'active_tracker': self.active_tracker,
            'frames_since_init': self.frames_since_init,
            'trackers': {}
        }
        
        for tracker_type in self.trackers.keys():
            total_attempts = self.success_counts[tracker_type] + self.failure_counts[tracker_type]
            success_rate = (
                self.success_counts[tracker_type] / total_attempts 
                if total_attempts > 0 else 0
            )
            
            stats['trackers'][tracker_type] = {
                'state': self.tracker_states[tracker_type],
                'success_count': self.success_counts[tracker_type],
                'failure_count': self.failure_counts[tracker_type],
                'success_rate': success_rate,
                'frames_since_failure': self.frames_since_failure[tracker_type]
            }
        
        return stats
    
    def get_active_tracker(self) -> str:
        """Get currently active tracker type."""
        return self.active_tracker
    
    def is_tracking_stable(self) -> bool:
        """
        Check if tracking is stable (primary tracker working).
        
        Returns:
            True if on primary tracker with no recent failures
        """
        return (self.active_tracker == self.primary_tracker and 
                self.tracker_states[self.primary_tracker] == 'active')
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def reset(self):
        """Reset all trackers and state."""
        for tracker_type in self.trackers.keys():
            self.trackers[tracker_type] = None
            self.tracker_states[tracker_type] = 'ready'
            self.failure_counts[tracker_type] = 0
            self.success_counts[tracker_type] = 0
            self.frames_since_failure[tracker_type] = 0
        
        self.is_initialized = False
        self.current_bbox = None
        self.frames_since_init = 0
        self.active_tracker = self.primary_tracker