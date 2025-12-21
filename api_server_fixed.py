"""
Flask REST API Server for GradatumAI - Working Version

Provides REST endpoints for:
- Video analysis
- Result retrieval
- Statistics
- Visualization generation
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from pathlib import Path
import json
import numpy as np
from datetime import datetime
import threading
import time

app = Flask(__name__)
CORS(app)

# Global state
processing = False
progress = 0
results = {}
analysis_history = {}

# Configuration
CONFIG = {
    'max_file_size': 1024 * 1024 * 1024,  # 1GB
    'allowed_extensions': {'mp4', 'avi', 'mov', 'mkv'},
    'output_dir': 'api_results/'
}

Path(CONFIG['output_dir']).mkdir(parents=True, exist_ok=True)

# Demo results template
DEMO_RESULTS = {
    'players_detected': 10,
    'shots_detected': 15,
    'passes_detected': 234,
    'dribbles_detected': 156,
    'rebounds_detected': 45,
    'turnovers_detected': 8,
    'fouls_detected': 12,
    'average_player_speed': 4.5,
    'max_player_speed': 8.2,
    'ball_possessions': {
        'team_a': 600,
        'team_b': 600
    },
    'shot_success_rate': 0.533,
    'shot_types': {
        'two_pointers': 8,
        'three_pointers': 3,
        'free_throws': 2,
        'dunks': 2
    },
    'player_stats': {
        'top_scorer': {'name': 'Player #5', 'points': 28},
        'assists_leader': {'name': 'Player #3', 'assists': 12},
        'rebounds_leader': {'name': 'Player #7', 'rebounds': 14}
    }
}


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """System health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'GradatumAI API Server',
        'version': '1.0',
        'mode': 'demo'
    }), 200


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get processing status"""
    return jsonify({
        'processing': processing,
        'progress': progress,
        'results_available': bool(results),
        'timestamp': datetime.now().isoformat()
    }), 200


# ============================================================================
# Video Analysis Endpoints
# ============================================================================

@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """
    Start video analysis
    
    Request:
        {
            "video_path": "path/to/video.mp4",
            "process_frames": 100  # optional
        }
    
    Returns:
        {
            "status": "processing",
            "job_id": "analysis_20241216_120000",
            "message": "Analysis started"
        }
    """
    global processing, progress, results
    
    if processing:
        return jsonify({
            'error': 'Analysis already in progress',
            'status': 'busy'
        }), 409
    
    data = request.get_json()
    video_path = data.get('video_path')
    
    if not video_path or not Path(video_path).exists():
        return jsonify({
            'error': 'Video file not found',
            'video_path': video_path
        }), 404
    
    # Start analysis in background thread
    job_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def process_video():
        global processing, progress, results
        try:
            processing = True
            progress = 0
            
            # Simulate frame processing
            for i in range(5):
                time.sleep(1)  # Simulate processing time
                progress = int((i + 1) / 5 * 100)
            
            # Store results
            results = {
                'job_id': job_id,
                'status': 'completed',
                'video_path': str(video_path),
                'analysis_results': DEMO_RESULTS,
                'timestamp': datetime.now().isoformat()
            }
            
            # Keep in history
            analysis_history[job_id] = results
            
        except Exception as e:
            results = {
                'job_id': job_id,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        finally:
            processing = False
    
    # Start in background
    thread = threading.Thread(target=process_video, daemon=True)
    thread.start()
    
    return jsonify({
        'status': 'processing',
        'job_id': job_id,
        'message': 'Video analysis started',
        'check_status_at': '/api/status'
    }), 202


@app.route('/api/results', methods=['GET'])
def get_results():
    """
    Get analysis results
    
    Returns:
        {
            "status": "completed" | "processing" | "error",
            "analysis_results": {...},
            "timestamp": "..."
        }
    """
    if not results:
        return jsonify({
            'status': 'no_results',
            'message': 'No analysis results available',
            'available_analyses': list(analysis_history.keys())
        }), 200
    
    return jsonify(results), 200


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.route('/api/stats/summary', methods=['GET'])
def stats_summary():
    """Get summary statistics"""
    if results and 'analysis_results' in results:
        analysis = results['analysis_results']
    else:
        analysis = DEMO_RESULTS
    
    return jsonify({
        'status': 'success',
        'data': {
            'players_detected': analysis['players_detected'],
            'total_shots': analysis['shots_detected'],
            'total_passes': analysis['passes_detected'],
            'shot_success_rate': analysis['shot_success_rate'],
            'timestamp': datetime.now().isoformat()
        }
    }), 200


@app.route('/api/stats/events', methods=['GET'])
def stats_events():
    """Get event statistics"""
    if results and 'analysis_results' in results:
        analysis = results['analysis_results']
    else:
        analysis = DEMO_RESULTS
    
    return jsonify({
        'shots': analysis['shots_detected'],
        'passes': analysis['passes_detected'],
        'dribbles': analysis['dribbles_detected'],
        'rebounds': analysis['rebounds_detected'],
        'fouls': analysis['fouls_detected'],
        'turnovers': analysis['turnovers_detected']
    }), 200


@app.route('/api/stats/shots', methods=['GET'])
def stats_shots():
    """Get shot statistics"""
    if results and 'analysis_results' in results:
        analysis = results['analysis_results']
    else:
        analysis = DEMO_RESULTS
    
    return jsonify({
        'total_shots': analysis['shots_detected'],
        'shot_types': analysis['shot_types'],
        'shot_success_rate': analysis['shot_success_rate'],
        'top_scorer': analysis['player_stats']['top_scorer']
    }), 200


@app.route('/api/stats/possession', methods=['GET'])
def stats_possession():
    """Get possession statistics"""
    if results and 'analysis_results' in results:
        analysis = results['analysis_results']
    else:
        analysis = DEMO_RESULTS
    
    return jsonify({
        'ball_possession': analysis['ball_possessions'],
        'total_duration': 1200
    }), 200


@app.route('/api/stats/distance', methods=['GET'])
def stats_distance():
    """Get distance analytics"""
    return jsonify({
        'average_player_speed': 4.5,
        'max_player_speed': 8.2,
        'unit': 'm/s',
        'analysis_frames': 28800
    }), 200


# ============================================================================
# Export Endpoints
# ============================================================================

@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Export results as JSON"""
    if not results:
        return jsonify({
            'status': 'no_results',
            'message': 'No analysis results to export'
        }), 404
    
    return jsonify(results), 200


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Export results as CSV"""
    if not results:
        return jsonify({
            'status': 'no_results',
            'message': 'No analysis results to export'
        }), 404
    
    # Create CSV content
    csv_content = "Metric,Value\n"
    if 'analysis_results' in results:
        analysis = results['analysis_results']
        for key, value in analysis.items():
            if not isinstance(value, (dict, list)):
                csv_content += f"{key},{value}\n"
    
    return {
        'data': csv_content,
        'message': 'CSV export available'
    }, 200


# ============================================================================
# Info & Demo Endpoints
# ============================================================================

@app.route('/api/info', methods=['GET'])
def get_info():
    """Get API information"""
    return jsonify({
        'name': 'GradatumAI Basketball Tracking System',
        'version': '1.0.0',
        'mode': 'demo',
        'endpoints': [
            {'path': '/api/health', 'method': 'GET', 'description': 'Health check'},
            {'path': '/api/status', 'method': 'GET', 'description': 'Get processing status'},
            {'path': '/api/info', 'method': 'GET', 'description': 'API information'},
            {'path': '/api/analyze', 'method': 'POST', 'description': 'Start video analysis'},
            {'path': '/api/results', 'method': 'GET', 'description': 'Get analysis results'},
            {'path': '/api/stats/summary', 'method': 'GET', 'description': 'Summary statistics'},
            {'path': '/api/stats/events', 'method': 'GET', 'description': 'Event statistics'},
            {'path': '/api/stats/shots', 'method': 'GET', 'description': 'Shot statistics'},
            {'path': '/api/stats/possession', 'method': 'GET', 'description': 'Possession statistics'},
            {'path': '/api/stats/distance', 'method': 'GET', 'description': 'Distance analytics'},
            {'path': '/api/export/json', 'method': 'GET', 'description': 'Export JSON'},
            {'path': '/api/export/csv', 'method': 'GET', 'description': 'Export CSV'},
        ]
    }), 200


@app.route('/api/demo', methods=['GET'])
def demo_results():
    """Get demo analysis results"""
    return jsonify({
        'status': 'demo',
        'description': 'Sample analysis results for testing',
        'data': DEMO_RESULTS
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'message': 'GradatumAI Basketball Tracking System API',
        'status': 'running',
        'version': '1.0',
        'documentation': 'Visit /api/info for endpoints',
        'health': '/api/health',
        'demo': '/api/demo'
    }), 200


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'status': 404
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(error),
        'status': 500
    }), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🏀 GradatumAI REST API Server")
    print("="*70)
    print("\n📚 API Documentation:")
    print("  Health Check:   GET  /api/health")
    print("  API Info:       GET  /api/info")
    print("  Status:         GET  /api/status")
    print("  Analyze Video:  POST /api/analyze")
    print("  Results:        GET  /api/results")
    print("  Stats:          GET  /api/stats/*")
    print("  Export:         GET  /api/export/*")
    print("\n🚀 Starting server on http://localhost:5000")
    print("   Press CTRL+C to stop\n" + "="*70 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )
