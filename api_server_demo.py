"""
Simple Flask API Server for GradatumAI - Demo/Testing version
Minimal dependencies for quick testing without OpenCV/Torch dependencies
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Global state
processing = False
progress = 0
results = {}

# Configuration
CONFIG = {
    'max_file_size': 1024 * 1024 * 1024,  # 1GB
    'allowed_extensions': {'mp4', 'avi', 'mov', 'mkv'},
    'output_dir': 'api_results/'
}

Path(CONFIG['output_dir']).mkdir(parents=True, exist_ok=True)


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
        'version': '1.0 (Demo)',
        'mode': 'lightweight'
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


@app.route('/api/info', methods=['GET'])
def get_info():
    """Get API information"""
    return jsonify({
        'name': 'GradatumAI Basketball Tracking System',
        'version': '1.0',
        'endpoints': [
            {'path': '/api/health', 'method': 'GET', 'description': 'Health check'},
            {'path': '/api/status', 'method': 'GET', 'description': 'Get processing status'},
            {'path': '/api/info', 'method': 'GET', 'description': 'API information'},
            {'path': '/api/demo', 'method': 'GET', 'description': 'Get demo statistics'},
            {'path': '/api/stats/summary', 'method': 'GET', 'description': 'Summary statistics'},
            {'path': '/api/echo', 'method': 'POST', 'description': 'Echo test endpoint'},
        ]
    }), 200


@app.route('/api/demo', methods=['GET'])
def demo_stats():
    """Get demo statistics (sample data)"""
    return jsonify({
        'video_name': 'demo_basketball_match.mp4',
        'duration': 1200,
        'frames_processed': 28800,
        'players_detected': 10,
        'shots_detected': 15,
        'passes_detected': 234,
        'dribbles_detected': 156,
        'average_player_speed': 4.5,  # m/s
        'max_player_speed': 8.2,
        'ball_possession_time': {
            'team_a': 600,
            'team_b': 600
        },
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/stats/summary', methods=['GET'])
def stats_summary():
    """Get summary statistics"""
    return jsonify({
        'status': 'success',
        'data': {
            'total_videos_processed': 5,
            'total_shots': 45,
            'total_passes': 1200,
            'average_game_duration': 1200,  # seconds
            'last_analysis': datetime.now().isoformat()
        }
    }), 200


@app.route('/api/stats/events', methods=['GET'])
def stats_events():
    """Get event statistics"""
    return jsonify({
        'shots': 15,
        'passes': 234,
        'dribbles': 156,
        'rebounds': 45,
        'fouls': 12,
        'turnovers': 8
    }), 200


@app.route('/api/stats/shots', methods=['GET'])
def stats_shots():
    """Get shot statistics"""
    return jsonify({
        'total_shots': 15,
        'made_shots': 8,
        'missed_shots': 7,
        'three_pointers': 3,
        'free_throws': 2,
        'shot_success_rate': 0.533
    }), 200


@app.route('/api/echo', methods=['POST'])
def echo():
    """Echo test endpoint - returns what was sent"""
    data = request.get_json() or {}
    return jsonify({
        'echo': data,
        'timestamp': datetime.now().isoformat(),
        'status': 'ok'
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint - API information"""
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
    print("🏀 GradatumAI Basketball Tracking System - API Server (Demo)")
    print("="*70)
    print("\n✅ Starting Flask API server...")
    print("📍 Running on: http://localhost:5000")
    print("📚 Documentation: http://localhost:5000/api/info")
    print("💓 Health check: http://localhost:5000/api/health")
    print("🎮 Demo stats: http://localhost:5000/api/demo")
    print("\n" + "="*70 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )
