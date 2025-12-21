"""
Comprehensive Module Integration Example

This script demonstrates how to use all modules together in a complete pipeline.
Shows initialization, data flow, and result analysis.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config_loader import load_config
from Modules.IDrecognition.player_detection import FeetDetector
from Modules.BallTracker.ball_detect_track import BallDetectTrack
from Modules.SpeedAcceleration.velocity_analyzer import VelocityAnalyzer
from Modules.PlayerDistance.distance_analyzer import DistanceAnalyzer
from Modules.DriblingDetector.dribbling_detector import DribblingDetector
from Modules.EventRecognition.event_recognizer import EventRecognizer
from Modules.ShotAttemp.shot_analyzer import ShotAnalyzer
from Modules.BallControl.ball_control import BallControlAnalyzer
from Modules.SequenceParser.sequence_parser import SequenceRecorder, SequenceParser

import cv2
import numpy as np


class ComprehensiveBasketballAnalyzer:
    """
    Comprehensive analyzer combining all modules for complete game analysis.
    """
    
    def __init__(self, config_path: str = 'config/main_config.yaml'):
        """Initialize all modules with configuration"""
        
        # Load configuration
        self.config = load_config(config_path)
        
        print("🏀 Initializing GradatumAI Basketball Tracking System")
        print("=" * 60)
        
        # Initialize core modules
        print("✓ Loading configuration...")
        
        # Player detection
        print("✓ Initializing player detection (Detectron2)...")
        self.player_detector = FeetDetector(config=self.config)
        
        # Ball tracking
        print("✓ Initializing ball detection & tracking...")
        self.ball_tracker = BallDetectTrack()
        
        # Analysis modules
        print("✓ Initializing velocity analyzer...")
        self.velocity_analyzer = VelocityAnalyzer(config=self.config)
        
        print("✓ Initializing distance analyzer...")
        self.distance_analyzer = DistanceAnalyzer(
            pixel_to_meter=self.config.get('player_distance.pixel_to_meter', 0.1),
            proximity_threshold=self.config.get('player_distance.proximity_threshold', 3.0)
        )
        
        print("✓ Initializing dribbling detector...")
        self.dribbling_detector = DribblingDetector(
            min_possession_frames=self.config.get('dribbling.min_possession_frames', 5),
            speed_threshold=self.config.get('dribbling.speed_threshold', 1.0)
        )
        
        print("✓ Initializing event recognizer...")
        self.event_recognizer = EventRecognizer(
            min_pass_distance=self.config.get('event_recognition.pass_detection.min_pass_distance', 2.0),
            max_shot_frames=self.config.get('event_recognition.shot_detection.max_shot_frames', 60)
        )
        
        print("✓ Initializing shot analyzer...")
        self.shot_analyzer = ShotAnalyzer(
            three_point_line_distance=self.config.get('shot_attempt.three_point_line_distance', 7.24),
            hoop_position=tuple(self.config.get('shot_attempt.hoop_position', [14.0, 7.5]))
        )
        
        print("✓ Initializing ball control analyzer...")
        self.ball_control = BallControlAnalyzer(
            proximity_threshold=self.config.get('player_distance.proximity_threshold', 3.0)
        )
        
        print("✓ Initializing sequence recorder...")
        self.sequence_recorder = SequenceRecorder(
            fps=self.config.get('video.fps', 30)
        )
        
        print("\n✅ All modules initialized successfully!")
        print("=" * 60)
    
    def process_frame(self,
                      frame: np.ndarray,
                      frame_number: int,
                      homography: np.ndarray,
                      M1: np.ndarray,
                      timestamp: float):
        """
        Process a single frame through all analysis modules.
        
        Args:
            frame: Input frame (BGR)
            frame_number: Frame index
            homography: Court homography matrix
            M1: Court-to-2D map transformation
            timestamp: Frame timestamp
        """
        
        # Detect players
        players, map_2d = self.player_detector.get_players_pos(
            frame, homography, M1, frame_number
        )
        
        # Detect ball
        ball_position = self.ball_tracker.detect_and_track_ball(
            frame, players, map_2d
        )
        
        if ball_position is None:
            return
        
        # Analyze ball control/possession
        possession_info = self.ball_control.analyze_possession(
            ball_position, players, frame_number, timestamp
        )
        
        # Calculate velocities
        for player_id, player in players.items():
            velocity = self.velocity_analyzer.calculate_velocity(
                player_id, player.get('position', (0, 0)), frame_number
            )
        
        # Analyze distances between players
        if len(players) > 1:
            player_list = list(players.values())
            positions = [p.get('position', (0, 0)) for p in player_list]
            
            for i in range(len(player_list)):
                for j in range(i+1, len(player_list)):
                    pair_info = self.distance_analyzer.analyze_player_pair(
                        positions[i], positions[j],
                        player_list[i].get('team'),
                        player_list[j].get('team')
                    )
        
        # Record frame data
        frame_data = {
            player_id: {
                'team': player.get('team'),
                'position': player.get('position'),
                'velocity': player.get('velocity', (0, 0))
            }
            for player_id, player in players.items()
        }
        
        self.sequence_recorder.record_frame(
            frame_number=frame_number,
            timestamp=timestamp,
            players=frame_data,
            ball_position=ball_position,
            ball_possessor_id=possession_info.possessor_id,
            game_state=possession_info.possession_type.value
        )
    
    def get_analysis_summary(self) -> Dict:
        """Get comprehensive analysis summary"""
        
        summary = {
            'player_distance': self.distance_analyzer.get_distance_statistics(),
            'dribbling': self.dribbling_detector.get_dribbling_statistics(),
            'events': self.event_recognizer.get_event_statistics(),
            'shots': self.shot_analyzer.get_shooting_statistics(),
            'ball_control': self.ball_control.get_possession_statistics(),
            'sequence': self.sequence_recorder.get_frame_count()
        }
        
        return summary
    
    def export_results(self, output_dir: str = 'results/'):
        """Export all analysis results"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print("\n📊 Exporting results...")
        print("=" * 60)
        
        # Export sequence data
        parser = SequenceParser()
        
        csv_path = output_path / "game_sequence.csv"
        parser.export_to_csv(
            self.sequence_recorder.records,
            str(csv_path),
            include_timestamps=True,
            include_teams=True
        )
        print(f"✓ Exported sequence to {csv_path}")
        
        json_path = output_path / "game_sequence.json"
        parser.export_to_json(
            self.sequence_recorder.records,
            str(json_path),
            include_timestamps=True,
            include_teams=True
        )
        print(f"✓ Exported sequence to {json_path}")
        
        # Export statistics
        import json
        stats_path = output_path / "analysis_summary.json"
        summary = self.get_analysis_summary()
        with open(stats_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✓ Exported analysis summary to {stats_path}")
        
        print("=" * 60)
        print("✅ Export complete!")
        
        return summary


def main():
    """Example usage"""
    
    # Initialize analyzer
    analyzer = ComprehensiveBasketballAnalyzer(
        config_path='config/main_config.yaml'
    )
    
    # Example: Process a video
    # This would be called in a video processing loop:
    #
    # cap = cv2.VideoCapture('resources/VideoProject.mp4')
    # frame_number = 0
    # while cap.isOpened():
    #     ret, frame = cap.read()
    #     if not ret:
    #         break
    #     
    #     timestamp = frame_number / 30.0  # Assuming 30 FPS
    #     analyzer.process_frame(
    #         frame, frame_number,
    #         homography_matrix, 
    #         M1_matrix,
    #         timestamp
    #     )
    #     frame_number += 1
    # cap.release()
    
    # Get and export results
    summary = analyzer.get_analysis_summary()
    print("\n📈 Analysis Summary:")
    print(json.dumps(summary, indent=2, default=str))
    
    # Export all results
    analyzer.export_results('results/')


if __name__ == '__main__':
    main()
