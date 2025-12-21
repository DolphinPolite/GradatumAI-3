#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple REST API for Video Analysis with Real Detectron2"""

import json
import os
import sys
import threading
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global state
results = {}
analysis_history = {}

def process_video_with_detectron2(video_path, job_id):
    """Process video with Detectron2 (real analysis)"""
    try:
        logger.info(f"Starting real analysis for {video_path} with job {job_id}")
        
        # Import detectron2 here to avoid loading it at startup
        from detectron2 import model_zoo
        from detectron2.engine import DefaultPredictor
        from detectron2.config import get_cfg
        import cv2
        
        # Setup detectron2 config - use simpler model for faster loading
        logger.info("Loading Detectron2 config...")
        cfg = get_cfg()
        
        # Try to use a faster model (ResNet-50 instead of ResNet-101)
        try:
            cfg.merge_from_file(model_zoo.get_config_file("COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml"))
        except:
            logger.warning("Could not load faster_rcnn config, trying mask_rcnn...")
            try:
                cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
            except:
                logger.warning("Could not load mask_rcnn config either. Using demo mode.")
                raise Exception("Could not load Detectron2 config files")
        
        cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
        cfg.MODEL.DEVICE = "cpu"  # Use CPU
        cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(cfg.MODEL.WEIGHTS)
        
        logger.info("Initializing Detectron2 predictor...")
        # Initialize predictor
        try:
            predictor = DefaultPredictor(cfg)
            logger.info("Predictor initialized successfully")
        except Exception as e:
            logger.error(f"Could not initialize predictor: {e}. Using demo mode.")
            raise
        
        # Read video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = 0
        player_detections = []
        ball_detections = 0
        
        # Process frames
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            # Only process every 10th frame for speed
            if frame_count % 10 == 0:
                try:
                    outputs = predictor(frame)
                    instances = outputs["instances"]
                    
                    # Count person detections (players)
                    person_mask = instances.pred_classes == 0  # COCO class 0 is person
                    player_count = person_mask.sum().item()
                    
                    if player_count > 0:
                        player_detections.append({
                            "frame": frame_count,
                            "players": player_count,
                            "confidence": float(instances.scores[person_mask].mean())
                        })
                except Exception as e:
                    logger.warning(f"Error processing frame {frame_count}: {e}")
        
        cap.release()
        
        # Compile results
        result = {
            "status": "success",
            "job_id": job_id,
            "video_path": video_path,
            "timestamp": datetime.datetime.now().isoformat(),
            "mode": "detectron2_real",
            "detections": {
                "players_detected": len(player_detections),
                "avg_players_per_frame": sum([p['players'] for p in player_detections]) / max(len(player_detections), 1) if player_detections else 0,
                "ball_detections": ball_detections,
                "frames_processed": frame_count,
                "total_frames": total_frames
            },
            "player_tracking": player_detections[:50]  # First 50 frames with detections
        }
        
        results[job_id] = result
        analysis_history[job_id] = result
        logger.info(f"Analysis complete for job {job_id}")
        
    except Exception as e:
        error_result = {
            "status": "error",
            "job_id": job_id,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }
        results[job_id] = error_result
        logger.error(f"Error analyzing video: {e}")

# ==================== API Routes ====================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0",
        "mode": "real_detectron2"
    })

@app.route('/api/info', methods=['GET'])
def info():
    """API information"""
    return jsonify({
        "name": "GradatumAI Video Analysis API",
        "version": "1.0",
        "description": "Real-time basketball video analysis with Detectron2",
        "endpoints": {
            "health": "GET /api/health",
            "analyze": "POST /api/analyze",
            "results": "GET /api/results?job_id=<id>",
            "history": "GET /api/history"
        }
    })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start video analysis"""
    data = request.get_json()
    video_path = data.get('video_path')
    
    if not video_path:
        return jsonify({"error": "Missing video_path"}), 400
    
    if not os.path.exists(video_path):
        return jsonify({"error": f"Video not found: {video_path}"}), 400
    
    # Create job ID
    job_id = f"job_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Start background analysis
    thread = threading.Thread(
        target=process_video_with_detectron2,
        args=(video_path, job_id),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "status": "accepted",
        "job_id": job_id,
        "message": "Analysis started"
    }), 202

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get analysis results"""
    job_id = request.args.get('job_id')
    
    if not job_id:
        return jsonify({"error": "Missing job_id parameter"}), 400
    
    if job_id not in results:
        return jsonify({
            "status": "pending",
            "job_id": job_id,
            "message": "Analysis in progress"
        }), 202
    
    return jsonify(results[job_id])

@app.route('/api/history', methods=['GET'])
def history():
    """Get analysis history"""
    return jsonify({
        "count": len(analysis_history),
        "jobs": list(analysis_history.keys())
    })

# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ==================== Main ====================

if __name__ == '__main__':
    print("=" * 50)
    print("GradatumAI Video Analysis API")
    print("=" * 50)
    print("\nAPI Endpoints:")
    print("  Health: GET /api/health")
    print("  Analyze: POST /api/analyze")
    print("  Results: GET /api/results?job_id=<id>")
    print("  History: GET /api/history")
    print("\nServer: http://localhost:5000")
    print("=" * 50)
    
    # Set environment variable to suppress warning
    os.environ['FLASK_ENV'] = 'production'
    
    # Run server
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
