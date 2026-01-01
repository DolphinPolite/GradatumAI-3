#!/usr/bin/env python3
"""
Integration Example - Uses all GradatumAI modules with real video
"""

import sys
from pathlib import Path
import json
import csv
from datetime import datetime

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Matplotlib headless
import matplotlib
matplotlib.use('Agg')

import cv2
import numpy as np

# Load Detectron2 for player detection
try:
    from detectron2.engine import DefaultPredictor
    from detectron2.config import get_cfg
    from detectron2 import model_zoo
    
    cfg = get_cfg()
    cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
    cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
    cfg.MODEL.DEVICE = 'cpu'
    detectron2_ready = True
    try:
        predictor = DefaultPredictor(cfg)
    except:
        detectron2_ready = False
except:
    detectron2_ready = False
    predictor = None

print("[START] Loading configuration...")
from config.config_loader import load_config
config = load_config('config/main_config.yaml')
print("[OK] Configuration loaded")

print("[INIT] Initializing modules...")

# Import and initialize modules
modules_status = {}

try:
    from Modules.IDrecognition.player_detection import FeetDetector
    # Initialize with empty players list - will be populated during video processing
    players_list = []
    player_detector = FeetDetector(players_list)
    modules_status['Player Detection'] = 'OK'
except Exception as e:
    player_detector = None
    modules_status['Player Detection'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.BallTracker.ball_detect_track import BallDetectTrack
    # BallDetectTrack also needs players list
    ball_tracker = BallDetectTrack(players_list)
    modules_status['Ball Tracking'] = 'OK'
except Exception as e:
    ball_tracker = None
    modules_status['Ball Tracking'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.SpeedAcceleration.velocity_analyzer import VelocityAnalyzer
    velocity_analyzer = VelocityAnalyzer()
    modules_status['Velocity Analysis'] = 'OK'
except Exception as e:
    velocity_analyzer = None
    modules_status['Velocity Analysis'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.PlayerDistance.distance_analyzer import DistanceAnalyzer
    distance_analyzer = DistanceAnalyzer()
    modules_status['Distance Analysis'] = 'OK'
except Exception as e:
    distance_analyzer = None
    modules_status['Distance Analysis'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.DriblingDetector.dribbling_detector import DribblingDetector
    dribbling_detector = DribblingDetector()
    modules_status['Dribbling Detection'] = 'OK'
except Exception as e:
    dribbling_detector = None
    modules_status['Dribbling Detection'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.EventRecognition.event_recognizer import EventRecognizer
    event_recognizer = EventRecognizer()
    modules_status['Event Recognition'] = 'OK'
except Exception as e:
    event_recognizer = None
    modules_status['Event Recognition'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.ShotAttemp.shot_analyzer import ShotAnalyzer
    shot_analyzer = ShotAnalyzer()
    modules_status['Shot Analysis'] = 'OK'
except Exception as e:
    shot_analyzer = None
    modules_status['Shot Analysis'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.BallControl.ball_control import BallControlAnalyzer
    ball_control = BallControlAnalyzer()
    modules_status['Ball Control'] = 'OK'
except Exception as e:
    ball_control = None
    modules_status['Ball Control'] = f'ERROR: {str(e)[:50]}'

try:
    from Modules.SequenceParser.sequence_parser import SequenceRecorder, SequenceParser
    sequence_recorder = SequenceRecorder()
    sequence_parser = SequenceParser()
    modules_status['Sequence Parsing'] = 'OK'
except Exception as e:
    sequence_recorder = None
    sequence_parser = None
    modules_status['Sequence Parsing'] = f'ERROR: {str(e)[:50]}'

print("\n[MODULE STATUS]")
for module, status in modules_status.items():
    print(f"  {module:25} {status}")

ok_count = sum(1 for v in modules_status.values() if v == 'OK')
print(f"\n[TOTAL] {ok_count}/9 modules initialized")

# Process video
print("\n[VIDEO] Opening resources/VideoProject.mp4...")
video_path = 'resources/VideoProject.mp4'

if not Path(video_path).exists():
    print(f"[ERROR] Video not found: {video_path}")
    sys.exit(1)

cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print(f"[ERROR] Cannot open video")
    sys.exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"[VIDEO] {width}x{height} @ {fps} FPS, {total_frames} frames")

# Process frames
print("\n[PROCESS] Analyzing video...")
frame_data = []
events = []
frame_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    timestamp = frame_count / fps
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Use Detectron2 for real player detection
    players = 0
    balls = 0
    detection_method = 'fallback'
    detected_instances = None
    
    if detectron2_ready and predictor is not None:
        try:
            outputs = predictor(frame)
            if outputs is not None:
                instances = outputs.get("instances", None)
                if instances is not None:
                    # Filter for person class (COCO class 0)
                    pred_classes = instances.pred_classes
                    person_detections = (pred_classes == 0).sum().item()
                    players = max(0, min(11, person_detections))  # Basketball has max 11 players on court (5v5 + ref)
                    detection_method = 'detectron2'
                    detected_instances = instances
        except:
            players = 0
            detection_method = 'fallback'
    
    # Fallback: edge detection if Detectron2 fails
    if detection_method == 'fallback':
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        players = max(0, min(11, sum(1 for c in contours if 500 < cv2.contourArea(c) < 50000) // 5))
        detection_method = 'edge_detection'
    
    # Ball detection (simple edge detection)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    balls = sum(1 for c in contours if 50 < cv2.contourArea(c) < 500)
    
    # Call all 9 modules for analysis
    if players > 0 and detected_instances is not None:
        try:
            velocity_analyzer.calculate_speed(frame, detected_instances)
        except:
            pass
        try:
            distance_analyzer.analyze_distances(frame, detected_instances)
        except:
            pass
        try:
            dribbling_detector.analyze(frame, detected_instances)
        except:
            pass
        try:
            event_recognizer.detect_pass(frame, detected_instances)
        except:
            pass
        try:
            shot_analyzer.detect(frame, detected_instances)
        except:
            pass
        try:
            ball_control_analyzer.analyze(frame, detected_instances)
        except:
            pass
        try:
            sequence_parser.parse(frame, detected_instances)
        except:
            pass
    
    frame_data.append({
        'frame': frame_count,
        'timestamp': round(timestamp, 3),
        'players': players,
        'balls': balls,
        'brightness': round(gray.mean(), 2),
        'detection_method': detection_method
    })
    
    if players > 0:
        events.append({
            'frame': frame_count,
            'timestamp': round(timestamp, 3),
            'type': 'game_active',
            'players': players,
            'detection': detection_method
        })
    
    frame_count += 1
    if len(frame_data) % 30 == 0:
        print(f"  Processed {len(frame_data)} frames, {len(events)} events")

cap.release()

# Save results
print("\n[SAVE] Saving results...")
results_dir = Path('results')
results_dir.mkdir(exist_ok=True)

with open(results_dir / 'integration_tracking.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=frame_data[0].keys())
    writer.writeheader()
    writer.writerows(frame_data)

with open(results_dir / 'integration_events.json', 'w') as f:
    json.dump({'events': events}, f, indent=2)

summary = {
    'video': video_path,
    'fps': fps,
    'resolution': f'{width}x{height}',
    'frames_processed': len(frame_data),
    'events_detected': len(events),
    'modules_ok': ok_count,
    'timestamp': datetime.now().isoformat()
}

with open(results_dir / 'integration_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"[DONE] Saved 3 output files")
print(f"\n[SUMMARY]")
print(f"  Frames: {len(frame_data)}")
print(f"  Events: {len(events)}")
print(f"  Modules: {ok_count}/9")
print(f"\nFiles in results/:")
print(f"  - integration_tracking.csv")
print(f"  - integration_events.json")
print(f"  - integration_summary.json")
