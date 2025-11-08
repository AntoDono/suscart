"""Basic routes for SusCart API"""

from flask import jsonify, send_from_directory
import os


def register_basic_routes(app):
    """Register basic routes"""
    
    @app.route('/')
    def index():
        """Serve the WebSocket test client"""
        return send_from_directory(os.path.dirname(__file__), '../ws_test_client.html')
    
    @app.route('/routes', methods=['GET'])
    def list_routes():
        """List all available routes and WebSocket endpoints"""
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                routes.append({
                    'endpoint': rule.endpoint,
                    'methods': sorted(list(rule.methods - {'HEAD', 'OPTIONS'})),
                    'path': str(rule)
                })
        
        port = os.getenv('PORT', 3000)
        return jsonify({
            'api_routes': sorted(routes, key=lambda x: x['path']),
            'websockets': [
            f'ws://localhost:{port}/ws/admin - Admin dashboard updates',
            f'ws://localhost:{port}/ws/customer/<customer_id> - Customer notifications',
            f'ws://localhost:{port}/ws/stream_video - Video stream'
            ]
        }), 200
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        knot_client = getattr(app, 'knot_client', None)
        return jsonify({
            'status': 'healthy',
            'message': 'SusCart backend is running',
            'database': 'connected',
            'knot_api': 'mock' if knot_client and hasattr(knot_client, 'mock_data') else 'connected'
        }), 200

