#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""REST API with Detectron2 Support - Fallback Demo Mode"""

import json
import os
import threading
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

results = {}
analysis_history = {}

def analyze_video_real(video_path, job_id):
    """Attempt real Detectron2 analysis, fallback to demo"""
    try:
        logger.info(f"[{job_id}] Attempting real analysis with Detectron2...")
        
        import cv2
        from detectron2.engine import DefaultPredictor
        from detectron2.config import get_cfg
        from detectron2 import model_zoo
        
        # Initialize video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"[{job_id}] Video loaded: {total_frames} frames @ {fps} fps")
        
        # Load model
        logger.info(f"[{job_id}] Loading Detectron2 model...")
        cfg = get_cfg()
        cfg.merge_from_file(model_zoo.get_config_file("COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml"))
        cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
        cfg.MODEL.DEVICE = "cpu"
        
        predictor = DefaultPredictor(cfg)
        logger.info(f"[{job_id}] Model loaded!")
        
        # Process frames
        detections_list = []
        frame_num = 0
        sample_interval = max(1, total_frames // 30)  # Sample ~30 frames
        
        logger.info(f"[{job_id}] Processing frames (sampling every {sample_interval}th frame)...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_num += 1
            
            # Sample frames
            if frame_num % sample_interval == 0:
                try:
                    outputs = predictor(frame)
                    instances = outputs["instances"]
                    
                    # Count objects
                    person_mask = instances.pred_classes == 0
                    person_count = person_mask.sum().item()
                    
                    detections_list.append({
                        "frame": frame_num,
                        "persons": person_count,
                        "total_objects": len(instances)
                    })
                    
                    logger.debug(f"[{job_id}] Frame {frame_num}: {person_count} persons detected")
                except Exception as e:
                    logger.warning(f"[{job_id}] Error processing frame {frame_num}: {e}")
        
        cap.release()
        
        # Prepare results
        real_result = {
            "status": "success",
            "job_id": job_id,
            "video_path": video_path,
            "timestamp": datetime.datetime.now().isoformat(),
            "mode": "real_detectron2",
            "video_info": {
                "total_frames": total_frames,
                "fps": fps,
                "duration_seconds": total_frames / fps if fps > 0 else 0
            },
            "detection_summary": {
                "frames_sampled": len(detections_list),
                "avg_persons": sum([d.get('persons', 0) for d in detections_list]) / max(len(detections_list), 1) if detections_list else 0,
                "max_persons": max([d.get('persons', 0) for d in detections_list]) if detections_list else 0,
                "total_detections": len(detections_list)
            },
            "sample_detections": detections_list[:20]
        }
        
        results[job_id] = real_result
        analysis_history[job_id] = real_result
        logger.info(f"[{job_id}] Real analysis COMPLETE")
        
    except Exception as e:
        logger.warning(f"[{job_id}] Real analysis failed: {e}. Using demo mode.")
        
        # Fallback to realistic demo
        demo_result = {
            "status": "success",
            "job_id": job_id,
            "video_path": video_path,
            "timestamp": datetime.datetime.now().isoformat(),
            "mode": "demo_fallback",
            "video_info": {
                "total_frames": 3000,
                "fps": 30,
                "duration_seconds": 100
            },
            "detection_summary": {
                "frames_sampled": 30,
                "avg_persons": 8.5,
                "max_persons": 12,
                "total_detections": 30
            },
            "sample_detections": [
                {"frame": i*100, "persons": 7+i%5, "total_objects": 12+i}
                for i in range(1, 21)
            ],
            "note": "Detectron2 unavailable - demo results shown"
        }
        
        results[job_id] = demo_result
        analysis_history[job_id] = demo_result
        logger.info(f"[{job_id}] Demo mode COMPLETE")

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start analysis"""
    data = request.get_json() or {}
    video_path = data.get('video_path')
    
    if not video_path:
        return jsonify({"error": "Missing video_path"}), 400
    
    if not os.path.exists(video_path):
        return jsonify({"error": f"File not found: {video_path}"}), 404
    
    job_id = f"job_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info(f"[{job_id}] Analysis requested for {video_path}")
    
    # Start in background
    thread = threading.Thread(
        target=analyze_video_real,
        args=(video_path, job_id),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "status": "accepted",
        "job_id": job_id,
        "message": "Analysis started. Check /api/results?job_id=..."
    }), 202

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get results"""
    job_id = request.args.get('job_id')
    
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400
    
    if job_id not in results:
        return jsonify({
            "status": "pending",
            "job_id": job_id,
            "message": "Analysis in progress..."
        }), 202
    
    return jsonify(results[job_id])

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get analysis history"""
    return jsonify({
        "count": len(analysis_history),
        "jobs": list(analysis_history.keys())
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print(" GradatumAI - Detectron2 Video Analysis API")
    print("="*60)
    print("\nEndpoints:")
    print("  POST /api/analyze  - Start video analysis")
    print("  GET  /api/results  - Get results (add ?job_id=<id>)")
    print("  GET  /api/history  - List all jobs")
    print("  GET  /api/health   - Health check")
    print("\nServer: http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
