"""
Basketball Ball Tracker - Structured Logging System

Purpose:
    Provides centralized logging for debugging, monitoring, and ML pipeline integration.
    Logs are structured for easy parsing by downstream analysis tools.

ML Pipeline Integration:
    - Logs can be exported to JSON for training data analysis
    - Tracks detection/tracking failures for model improvement
    - Provides performance metrics for optimization

Usage:
    from utils.logger import BallTrackerLogger
    
    logger = BallTrackerLogger(config)
    logger.log_detection("template_match", confidence=0.87, bbox=(10, 20, 30, 40))
    logger.log_warning("bbox_out_of_bounds", frame_id=125, bbox=(1920, 1080, 50, 50))
    
Author: Ball Tracking Team
Date: 2025
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


class BallTrackerLogger:
    """
    Centralized logging system for basketball ball tracking.
    
    Features:
        - Structured logging with context information
        - Automatic log file management
        - Separate channels for errors, warnings, and metrics
        - JSON export for ML pipeline
    
    Attributes:
        config (dict): Configuration dictionary from tracker_config.yaml
        logger (logging.Logger): Main logger instance
        metrics_log (list): Accumulated metrics for export
    """
    
    def __init__(self, config: Dict[str, Any], logger_name: str = "BallTracker"):
        """
        Initialize the logging system.
        
        Args:
            config: Configuration dictionary containing logging settings
            logger_name: Name for the logger instance
        """
        self.config = config.get('logging', {})
        self.logger_name = logger_name
        self.metrics_log = []
        
        # Create logger
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self._get_log_level())
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Setup handlers
        self._setup_console_handler()
        
        if self.config.get('save_to_file', True):
            self._setup_file_handler()
        
        self.logger.info("="*60)
        self.logger.info("Ball Tracker Logger Initialized")
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.info("="*60)
    
    def _get_log_level(self) -> int:
        """Convert string log level to logging constant."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        level_str = self.config.get('level', 'INFO').upper()
        return level_map.get(level_str, logging.INFO)
    
    def _setup_console_handler(self):
        """Setup console (stdout) handler with formatting."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._get_log_level())
        
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self):
        """Setup file handler for persistent logging."""
        log_dir = Path(self.config.get('log_directory', 'logs/ball_tracking'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"tracker_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)  # File gets all levels
        
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.info(f"Log file created: {log_file}")
    
    # -------------------------------------------------------------------------
    # Core Logging Methods
    # -------------------------------------------------------------------------
    
    def log_detection(self, method: str, confidence: float, bbox: tuple, 
                      frame_id: Optional[int] = None, **kwargs):
        """
        Log a successful ball detection event.
        
        Args:
            method: Detection method used (e.g., 'template_match', 'color_filter')
            confidence: Detection confidence score (0-1)
            bbox: Bounding box (x, y, w, h)
            frame_id: Optional frame identifier
            **kwargs: Additional context (e.g., match_score, color_score)
        """
        msg = f"Detection: method={method}, confidence={confidence:.3f}, bbox={bbox}"
        if frame_id is not None:
            msg += f", frame={frame_id}"
        
        self.logger.info(msg)
        
        if self.config.get('log_metrics', True):
            self.metrics_log.append({
                'event': 'detection',
                'method': method,
                'confidence': confidence,
                'bbox': bbox,
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def log_tracking(self, tracker_type: str, bbox: tuple, success: bool,
                     frame_id: Optional[int] = None, **kwargs):
        """
        Log a tracking update event.
        
        Args:
            tracker_type: Tracker type (e.g., 'CSRT', 'KCF', 'MOSSE')
            bbox: Updated bounding box (x, y, w, h)
            success: Whether tracking was successful
            frame_id: Optional frame identifier
            **kwargs: Additional context
        """
        status = "SUCCESS" if success else "FAILED"
        msg = f"Tracking: tracker={tracker_type}, status={status}, bbox={bbox}"
        if frame_id is not None:
            msg += f", frame={frame_id}"
        
        log_func = self.logger.info if success else self.logger.warning
        log_func(msg)
        
        if self.config.get('log_metrics', True):
            self.metrics_log.append({
                'event': 'tracking',
                'tracker_type': tracker_type,
                'bbox': bbox,
                'success': success,
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def log_warning(self, warning_type: str, message: str = "", **context):
        """
        Log a warning event with context.
        
        Args:
            warning_type: Type of warning (e.g., 'bbox_invalid', 'low_confidence')
            message: Optional warning message
            **context: Additional context data
        """
        ctx_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        full_msg = f"WARNING [{warning_type}]: {message}"
        if ctx_str:
            full_msg += f" | Context: {ctx_str}"
        
        self.logger.warning(full_msg)
    
    def log_error(self, error_type: str, exception: Optional[Exception] = None, 
                  **context):
        """
        Log an error event with exception details.
        
        Args:
            error_type: Type of error (e.g., 'tracker_init_failed', 'homography_error')
            exception: Optional exception object
            **context: Additional context data
        """
        ctx_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        msg = f"ERROR [{error_type}]"
        
        if exception:
            msg += f": {type(exception).__name__} - {str(exception)}"
        
        if ctx_str:
            msg += f" | Context: {ctx_str}"
        
        self.logger.error(msg, exc_info=(exception is not None))
    
    def log_metric(self, metric_name: str, value: float, 
                   frame_id: Optional[int] = None, **tags):
        """
        Log a metric value for performance monitoring.
        
        Args:
            metric_name: Name of the metric (e.g., 'fps', 'detection_time')
            value: Metric value
            frame_id: Optional frame identifier
            **tags: Additional tags for filtering
        """
        msg = f"METRIC: {metric_name}={value:.4f}"
        if frame_id is not None:
            msg += f", frame={frame_id}"
        
        self.logger.debug(msg)
        
        if self.config.get('log_metrics', True):
            self.metrics_log.append({
                'event': 'metric',
                'name': metric_name,
                'value': value,
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                **tags
            })
    
    def log_bounce_event(self, frame_id: int, position: tuple, 
                        velocity_before: float, velocity_after: float):
        """
        Log basketball bounce event (specific to basketball tracking).
        
        Args:
            frame_id: Frame where bounce occurred
            position: Ball position (x, y)
            velocity_before: Vertical velocity before bounce
            velocity_after: Vertical velocity after bounce
        """
        energy_loss = 1.0 - abs(velocity_after / velocity_before)
        msg = (f"BOUNCE DETECTED: frame={frame_id}, position={position}, "
               f"v_before={velocity_before:.2f}, v_after={velocity_after:.2f}, "
               f"energy_loss={energy_loss:.2%}")
        
        self.logger.info(msg)
        
        if self.config.get('log_metrics', True):
            self.metrics_log.append({
                'event': 'bounce',
                'frame_id': frame_id,
                'position': position,
                'velocity_before': velocity_before,
                'velocity_after': velocity_after,
                'energy_loss': energy_loss,
                'timestamp': datetime.now().isoformat()
            })
    
    # -------------------------------------------------------------------------
    # Export Methods
    # -------------------------------------------------------------------------
    
    def export_metrics(self, filepath: Optional[str] = None) -> str:
        """
        Export accumulated metrics to JSON file.
        
        Args:
            filepath: Optional output file path (defaults to log directory)
        
        Returns:
            Path to the exported file
        """
        if not self.metrics_log:
            self.logger.warning("No metrics to export")
            return ""
        
        if filepath is None:
            log_dir = Path(self.config.get('log_directory', 'logs/ball_tracking'))
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = log_dir / f"metrics_{timestamp}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.metrics_log, f, indent=2)
        
        self.logger.info(f"Metrics exported to: {filepath}")
        return str(filepath)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Generate summary statistics from logged metrics.
        
        Returns:
            Dictionary containing summary statistics
        """
        if not self.metrics_log:
            return {}
        
        # Count events by type
        event_counts = {}
        detection_confidences = []
        tracking_successes = []
        bounce_count = 0
        
        for entry in self.metrics_log:
            event_type = entry.get('event')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if event_type == 'detection':
                detection_confidences.append(entry.get('confidence', 0))
            elif event_type == 'tracking':
                tracking_successes.append(entry.get('success', False))
            elif event_type == 'bounce':
                bounce_count += 1
        
        summary = {
            'total_events': len(self.metrics_log),
            'event_counts': event_counts,
            'detection_stats': {
                'count': len(detection_confidences),
                'avg_confidence': sum(detection_confidences) / len(detection_confidences) if detection_confidences else 0
            },
            'tracking_stats': {
                'count': len(tracking_successes),
                'success_rate': sum(tracking_successes) / len(tracking_successes) if tracking_successes else 0
            },
            'bounce_count': bounce_count
        }
        
        return summary
    
    def clear_metrics(self):
        """Clear accumulated metrics from memory."""
        self.metrics_log.clear()
        self.logger.debug("Metrics log cleared")