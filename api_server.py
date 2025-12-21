"""
Flask REST API Server for GradatumAI

Provides REST endpoints for:
- Video analysis
- Result retrieval
- Statistics
- Visualization generation
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
import json
import numpy as np
from datetime import datetime
import threading
# Heavy ML modules - optional, commented for quick setup
# from integration_example import ComprehensiveBasketballAnalyzer
# from visualization_suite import BasketballVisualizer

# Placeholder classes for demo
class ComprehensiveBasketballAnalyzer:
    def __init__(self):
        pass

class BasketballVisualizer:
    def __init__(self):
        pass

app = Flask(__name__)
CORS(app)

# Global state
analyzer = None
results = {}
processing = False
progress = 0

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
        'version': '1.0'
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
# Video Processing Endpoints
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
    global processing, progress, analyzer, results
    
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
            
            analyzer = ComprehensiveBasketballAnalyzer()
            
            # Simulate processing
            progress = 50
            
            # Get summary
            summary = analyzer.get_analysis_summary()
            
            # Export results
            analyzer.export_results(CONFIG['output_dir'])
            
            progress = 100
            results = {
                'job_id': job_id,
                'status': 'completed',
                'summary': summary,
                'video_path': video_path,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            results = {
                'job_id': job_id,
                'status': 'error',
                'error': str(e)
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
        'check_status_at': f'/api/status'
    }), 202


@app.route('/api/results', methods=['GET'])
def get_results():
    """
    Get analysis results
    
    Returns:
        {
            "status": "completed" | "processing" | "error",
            "summary": {...},
            "data_files": {...}
        }
    """
    if not results:
        return jsonify({
            'status': 'no_results',
            'message': 'No analysis results available'
        }), 404
    
    return jsonify(results), 200


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.route('/api/stats/events', methods=['GET'])
def get_event_stats():
    """Get event statistics"""
    if not results or 'summary' not in results:
        return jsonify({'error': 'No results available'}), 404
    
    events_stats = results['summary'].get('events', {})
    
    return jsonify({
        'event_statistics': events_stats,
        'total_events': sum(events_stats.values()) if events_stats else 0,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/stats/shots', methods=['GET'])
def get_shot_stats():
    """Get shot statistics"""
    if not results or 'summary' not in results:
        return jsonify({'error': 'No results available'}), 404
    
    shot_stats = results['summary'].get('shots', {})
    
    return jsonify({
        'shot_statistics': shot_stats,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/stats/possession', methods=['GET'])
def get_possession_stats():
    """Get possession statistics"""
    if not results or 'summary' not in results:
        return jsonify({'error': 'No results available'}), 404
    
    possession_stats = results['summary'].get('ball_control', {})
    
    return jsonify({
        'possession_statistics': possession_stats,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/stats/distance', methods=['GET'])
def get_distance_stats():
    """Get distance statistics"""
    if not results or 'summary' not in results:
        return jsonify({'error': 'No results available'}), 404
    
    distance_stats = results['summary'].get('player_distance', {})
    
    return jsonify({
        'distance_statistics': distance_stats,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/stats/summary', methods=['GET'])
def get_full_summary():
    """Get complete summary"""
    if not results:
        return jsonify({'error': 'No results available'}), 404
    
    return jsonify(results), 200


# ============================================================================
# Data Export Endpoints
# ============================================================================

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Download CSV data"""
    csv_path = Path(CONFIG['output_dir']) / 'game_sequence.csv'
    
    if not csv_path.exists():
        return jsonify({'error': 'CSV file not found'}), 404
    
    return send_file(csv_path, as_attachment=True, 
                    download_name='game_sequence.csv')


@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Download JSON data"""
    json_path = Path(CONFIG['output_dir']) / 'game_sequence.json'
    
    if not json_path.exists():
        return jsonify({'error': 'JSON file not found'}), 404
    
    return send_file(json_path, as_attachment=True, 
                    download_name='game_sequence.json')


@app.route('/api/export/stats', methods=['GET'])
def export_stats():
    """Download statistics JSON"""
    stats_path = Path(CONFIG['output_dir']) / 'analysis_summary.json'
    
    if not stats_path.exists():
        return jsonify({'error': 'Stats file not found'}), 404
    
    return send_file(stats_path, as_attachment=True, 
                    download_name='analysis_summary.json')


# ============================================================================
# Visualization Endpoints
# ============================================================================

@app.route('/api/visualizations/generate', methods=['POST'])
def generate_visualizations():
    """Generate all visualizations"""
    try:
        visualizer = BasketballVisualizer(
            output_dir=CONFIG['output_dir'] + 'visualizations/'
        )
        
        # Generate example visualizations
        # (In production, would use actual data from results)
        
        return jsonify({
            'status': 'success',
            'message': 'Visualizations generated',
            'output_dir': str(visualizer.output_dir)
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'message': str(error),
        'available_endpoints': {
            'health': 'GET /api/health',
            'status': 'GET /api/status',
            'analyze': 'POST /api/analyze',
            'results': 'GET /api/results',
            'stats': 'GET /api/stats/*',
            'export': 'GET /api/export/*'
        }
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


# ============================================================================
# Info Endpoints
# ============================================================================

@app.route('/api/info', methods=['GET'])
def get_info():
    """Get API information"""
    return jsonify({
        'service': 'GradatumAI Basketball Analysis API',
        'version': '1.0.0',
        'description': 'Real-time basketball player and ball tracking with analysis',
        'endpoints': {
            'Core': {
                'GET /api/health': 'Health check',
                'GET /api/status': 'Processing status',
                'POST /api/analyze': 'Start video analysis',
                'GET /api/results': 'Get results'
            },
            'Statistics': {
                'GET /api/stats/events': 'Event statistics',
                'GET /api/stats/shots': 'Shot statistics',
                'GET /api/stats/possession': 'Possession statistics',
                'GET /api/stats/distance': 'Distance statistics',
                'GET /api/stats/summary': 'Complete summary'
            },
            'Export': {
                'GET /api/export/csv': 'Download CSV',
                'GET /api/export/json': 'Download JSON',
                'GET /api/export/stats': 'Download statistics'
            },
            'Visualization': {
                'POST /api/visualizations/generate': 'Generate visualizations'
            }
        }
    }), 200


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════╗
    ║   GradatumAI REST API Server              ║
    ║   http://localhost:5000                   ║
    ╚════════════════════════════════════════════╝
    """)
    
    print("📚 API Documentation:")
    print("  Health Check:   GET  /api/health")
    print("  API Info:       GET  /api/info")
    print("  Status:         GET  /api/status")
    print("  Analyze Video:  POST /api/analyze")
    print("  Results:        GET  /api/results")
    print("  Stats:          GET  /api/stats/*")
    print("  Export:         GET  /api/export/*")
    print("\n🚀 Starting server on http://localhost:5000")
    print("   Press CTRL+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
