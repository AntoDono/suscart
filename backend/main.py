from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from flask_sock import Sock
from dotenv import load_dotenv
import json
import os
import cv2
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import random
import threading
import time

# Load environment variables
load_dotenv()

# Import our modules
from models import db, Store, FruitInventory, FreshnessStatus, Customer, PurchaseHistory, Recommendation, WasteLog
from database import init_db, seed_sample_data

# Import Knot client with fallback support
try:
    from knot_fallback import KnotClientWithFallback
    use_fallback = os.getenv('KNOT_FALLBACK_TO_TUNNEL', 'true').lower() == 'true'
    if use_fallback and os.getenv('KNOT_ENV', 'tunnel') != 'tunnel' and os.getenv('KNOT_USE_REAL', 'false').lower() == 'true':
        from knot_fallback import KnotClientWithFallback as get_knot_client_class
        def get_knot_client():
            return KnotClientWithFallback()
    else:
        from knot_integration import get_knot_client
except ImportError:
    from knot_integration import get_knot_client
from detect_fruits import (
    detect, 
    load_fresh_detection_model, 
    crop_bounding_box, 
    get_freshness_score,
    get_best_camera_index
)
from utils.image_storage import save_detection_image, get_category_images, get_all_categories, DETECTION_IMAGES_DIR, replace_category_images, delete_category_images, save_thumbnail, mark_image_as_processed, save_processed_image, keep_latest_images   
from blemish_detection.blemish import detect_blemishes
import threading

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
sock = Sock(app)  # Initialize WebSocket support
PORT = os.getenv('PORT', 3000)
# Camera mode: 'local' (use local camera) or 'proxy' (receive frames from proxy)
CAMERA_MODE = os.getenv('CAMERA_MODE', 'local').lower()

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///edgecart.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Seed database with sample data if POPULATE env var is set
if os.getenv('POPULATE', 'false').lower() == 'true':
    with app.app_context():
        # Check if database is empty
        if not Store.query.first():
            print("📊 Database is empty. Seeding sample data...")
            seed_sample_data(app)
        
        # Create fake customer if it doesn't exist
        fake_customer = Customer.query.filter_by(knot_customer_id='FAKE-CUSTOMER-001').first()
        if not fake_customer:
            fake_customer = Customer(
                knot_customer_id='FAKE-CUSTOMER-001',
                name='Fake Customer',
                email='fake@example.com',
                phone='(555) 000-0000'
            )
            fake_customer.set_preferences({
                'favorite_fruits': ['apple', 'banana', 'orange'],
                'max_price': 10.00,
                'preferred_discount': 20
            })
            db.session.add(fake_customer)
            db.session.commit()
            print(f"✅ Created fake customer with ID: {fake_customer.id}")

# Initialize Knot API client
knot_client = get_knot_client()

# WebSocket connections are now managed in utils/helpers.py
# Import them for backward compatibility
from utils.helpers import admin_connections, customer_connections

# Store frontend video stream connections for broadcasting
frontend_video_connections = set()

# Shared proxy state (for proxy mode - shared across all proxy connections)
proxy_state_global = None

# Global in-memory cache for detection images (category -> list of detection dicts with cropped_image)
# Images are stored here before being saved to disk
category_images_memory_cache = {}

# Load fresh detection model globally (once at startup)
fresh_model = None
fresh_device = None
fresh_transform = None
try:
    # Try loading fresh_detector.pth first, fallback to ripe_detector.pth for backward compatibility
    model_path = "./model/fresh_detector.pth"
    if not os.path.exists(model_path) and os.path.exists("./model/ripe_detector.pth"):
        print("⚠️ fresh_detector.pth not found, trying ripe_detector.pth (old model)")
        model_path = "./model/ripe_detector.pth"
    
    fresh_model, fresh_device, fresh_transform = load_fresh_detection_model(model_path)
    print("✅ Fresh detection model loaded successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not load fresh detection model: {e}")
    print("   Video stream will work but without fresh detection")
    import traceback
    traceback.print_exc()

# ============ Import Utility Functions ============
from utils.helpers import (
    admin_connections,
    customer_connections,
    broadcast_to_admins,
    notify_customer,
    notify_quantity_change,
    update_freshness_for_item,
    generate_recommendations_for_item,
    set_app_instance
)

# Set app instance for threading in helpers
set_app_instance(app)

# ============ Import Route Modules ============
from api.routes import register_basic_routes
from api.inventory import register_inventory_routes

# Register routes
register_basic_routes(app)
register_inventory_routes(app)

# Register analytics blueprint
try:
    from api.analytics import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    print("✅ Analytics API registered")
except ImportError as e:
    print(f"⚠️  Analytics API not available: {e}")


# ============ Camera-Specific Helper Functions ============

def update_freshness_from_camera(inventory_id, freshness_score, confidence):
    """
    Update freshness status from camera detection (async)
    Called automatically when camera detects freshness.
    
    Note: This function is specific to camera detection and converts freshness_score (0-100)
    to freshness_score (0-1.0) before calling update_freshness_for_item.
    """
    try:
        with app.app_context():
            # Convert freshness_score from 0-100 scale to 0-1.0 scale
            freshness_score = freshness_score / 100.0 if freshness_score is not None else None
            
            if freshness_score is not None:
                # Use the helper function from utils.helpers
                update_freshness_for_item(inventory_id, freshness_score)
                
                # Also update confidence and predicted expiry
                freshness = FreshnessStatus.query.filter_by(inventory_id=inventory_id).first()
                if freshness:
                    freshness.confidence_level = confidence
                    # Predict expiry based on freshness (simple heuristic)
                    # Lower freshness = closer to expiry
                    days_until_expiry = int(freshness_score * 10)  # 0-10 days
                    freshness.predicted_expiry_date = datetime.utcnow() + timedelta(days=days_until_expiry)
                    freshness.last_checked = datetime.utcnow()
                    db.session.commit()
                    
                    # Broadcast update with source indicator
                    inventory = db.session.get(FruitInventory, inventory_id)
                    if inventory:
                        broadcast_to_admins('freshness_updated', {
                            'inventory_id': inventory_id,
                            'freshness': freshness.to_dict(),
                            'item': inventory.to_dict(),
                            'source': 'camera'
                        })
    
    except Exception as e:
        print(f"❌ Error updating freshness from camera: {e}")
        import traceback
        traceback.print_exc()


# ============ Freshness Monitoring API ============

@app.route('/api/freshness/update', methods=['POST'])
def update_freshness():
    """
    Receive freshness update from AI/Camera system
    Expected payload:
    {
        "inventory_id": 1,
        "freshness_score": 75.5,
        "predicted_expiry_date": "2025-11-15T10:00:00",
        "confidence_level": 0.95,
        "image_url": "https://..."
    }
    """
    try:
        data = request.get_json()
        inventory_id = data['inventory_id']
        
        # Get or create freshness status
        freshness = FreshnessStatus.query.filter_by(inventory_id=inventory_id).first()
        
        if not freshness:
            freshness = FreshnessStatus(inventory_id=inventory_id)
            db.session.add(freshness)
        
        # Update freshness data
        freshness.freshness_score = data['freshness_score']
        freshness.confidence_level = data.get('confidence_level', 0.9)
        freshness.last_checked = datetime.utcnow()
        
        if 'predicted_expiry_date' in data:
            freshness.predicted_expiry_date = datetime.fromisoformat(data['predicted_expiry_date'])
        
        if 'image_url' in data:
            freshness.image_url = data['image_url']
        
        if 'notes' in data:
            freshness.notes = data['notes']
        
        # Calculate discount and status
        old_discount = freshness.discount_percentage
        freshness.discount_percentage = freshness.calculate_discount()
        freshness.update_status()
        
        # Update inventory price if discount changed
        inventory = db.session.get(FruitInventory, inventory_id)
        if inventory and freshness.discount_percentage != old_discount:
            inventory.current_price = round(
                inventory.original_price * (1 - freshness.discount_percentage / 100),
                2
            )
            inventory.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Broadcast update
        if inventory:
            broadcast_to_admins('freshness_updated', {
                'inventory_id': inventory_id,
                'freshness': freshness.to_dict(),
                'item': inventory.to_dict()
            })
        
        # Send alert if ripe or clearance
        if freshness.status in ['ripe', 'clearance']:
            broadcast_to_admins('freshness_alert', {
                'message': f'Item {inventory.fruit_type} needs attention!',
                'inventory_id': inventory_id,
                'freshness_score': freshness.freshness_score
            })
        
        # Trigger recommendations if new discount
        if freshness.discount_percentage > old_discount and freshness.discount_percentage >= 20:
            generate_recommendations_for_item(inventory_id)
        
        return jsonify({
            'message': 'Freshness updated successfully',
            'freshness': freshness.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/freshness/<int:inventory_id>', methods=['GET'])
def get_freshness(inventory_id):
    """Get freshness status for inventory item"""
    try:
        freshness = FreshnessStatus.query.filter_by(inventory_id=inventory_id).first_or_404()
        return jsonify(freshness.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/freshness/critical', methods=['GET'])
def get_critical_items():
    """Get all items with ripe or clearance freshness"""
    try:
        critical_items = FreshnessStatus.query.filter(
            FreshnessStatus.status.in_(['ripe', 'clearance'])
        ).all()
        
        result = []
        for freshness in critical_items:
            if freshness.inventory:
                item_data = freshness.inventory.to_dict()
                result.append(item_data)
        
        return jsonify({
            'count': len(result),
            'items': result
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ Detection Images API ============

@app.route('/api/detection-images/<category>', methods=['GET'])
def get_detection_images(category):
    """Get all detection images for a category and run blemish detection"""
    try:
        # FIRST: Save images from memory to disk before fetching
        _save_memory_images_to_disk(category)
        
        images = get_category_images(category.lower())
        # Only get processed images (images stay in memory until processed)
        detection_images = [img for img in images if img['filename'].startswith('processed_')]
        
        # Limit to top 3 images for blemish processing
        detection_images = detection_images[:3]
        
        # Run blemish detection on each image
        images_with_blemishes = []
        for image_info in detection_images:
            image_path = DETECTION_IMAGES_DIR / category.lower() / image_info['filename']
            
            # Check if blemish detection already exists in metadata
            if not (image_info.get('metadata') and 'blemishes' in image_info['metadata']):
                # Run blemish detection
                try:
                    blemish_result = detect_blemishes(str(image_path))
                    
                    # Update metadata with blemish results
                    if not image_info.get('metadata'):
                        image_info['metadata'] = {}
                    
                    image_info['metadata']['blemishes'] = {
                        'bboxes': blemish_result['bboxes'],
                        'labels': blemish_result['labels'],
                        'count': len(blemish_result['bboxes'])
                    }
                    
                    # Save updated metadata
                    metadata_path = image_path.with_suffix('.json')
                    with open(metadata_path, 'w') as f:
                        json.dump(image_info['metadata'], f, indent=2, default=str)
                    
                    # Image is already processed (starts with processed_), cleanup old images
                    keep_latest_images(DETECTION_IMAGES_DIR / category.lower(), max_images=100)
                        
                except Exception as e:
                    print(f"Error running blemish detection on {image_path}: {e}")
                    # Continue without blemish data if detection fails
                    if not image_info.get('metadata'):
                        image_info['metadata'] = {}
                    image_info['metadata']['blemishes'] = {
                        'error': str(e),
                        'count': 0
                    }
            
            images_with_blemishes.append(image_info)
        
        return jsonify({
            'category': category,
            'count': len(images_with_blemishes),
            'images': images_with_blemishes
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _save_memory_images_to_disk(category: str):
    """Save images from memory cache to disk before fetching"""
    category_lower = category.lower()
    if category_lower not in category_images_memory_cache:
        return
    
    memory_images = category_images_memory_cache[category_lower]
    if not memory_images:
        return
    
    # Save each image from memory to disk
    for detection in memory_images:
        if 'cropped_image' in detection and detection['cropped_image'] is not None:
            # Save to disk as processed image
            save_processed_image(
                detection['cropped_image'],
                category_lower,
                detection.get('metadata')
            )
    
    # Clear memory cache after saving (images are now on disk)
    category_images_memory_cache[category_lower] = []


@app.route('/api/detection-images/<category>/stream', methods=['GET'])
def get_detection_images_stream(category):
    """Get detection images with progress updates via Server-Sent Events"""
    def generate():
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE connection established'})}\n\n"
            
            # FIRST: Save images from memory to disk before fetching
            _save_memory_images_to_disk(category)
            
            images = get_category_images(category.lower())
            # Only get processed images (images stay in memory until processed)
            detection_images = [img for img in images if img['filename'].startswith('processed_')]
            
            # Limit to top 3 images for blemish processing
            detection_images = detection_images[:3]
            total_images = len(detection_images)
            
            if total_images == 0:
                yield f"data: {json.dumps({'type': 'complete', 'progress': 100, 'images': []})}\n\n"
                return
            
            images_with_blemishes = []
            for idx, image_info in enumerate(detection_images):
                image_path = DETECTION_IMAGES_DIR / category.lower() / image_info['filename']
                
                # Send progress update before processing
                progress = int((idx / total_images) * 100)
                yield f"data: {json.dumps({'type': 'progress', 'progress': progress, 'current': idx + 1, 'total': total_images, 'filename': image_info['filename']})}\n\n"
                
                # Check if blemish detection already exists in metadata
                if not (image_info.get('metadata') and 'blemishes' in image_info['metadata']):
                    # Run blemish detection
                    try:
                        blemish_result = detect_blemishes(str(image_path))
                        
                        # Update metadata with blemish results
                        if not image_info.get('metadata'):
                            image_info['metadata'] = {}
                        
                        image_info['metadata']['blemishes'] = {
                            'bboxes': blemish_result['bboxes'],
                            'labels': blemish_result['labels'],
                            'count': len(blemish_result['bboxes'])
                        }
                        
                        # Save updated metadata
                        metadata_path = image_path.with_suffix('.json')
                        with open(metadata_path, 'w') as f:
                            json.dump(image_info['metadata'], f, indent=2, default=str)
                        
                        # Image is already processed (starts with processed_), cleanup old images
                        keep_latest_images(DETECTION_IMAGES_DIR / category.lower(), max_images=100)
                        
                    except Exception as e:
                        print(f"Error running blemish detection on {image_path}: {e}")
                        # Continue without blemish data if detection fails
                        if not image_info.get('metadata'):
                            image_info['metadata'] = {}
                        image_info['metadata']['blemishes'] = {
                            'error': str(e),
                            'count': 0
                        }
                
                images_with_blemishes.append(image_info)
                
                # Send progress update after processing
                progress = int(((idx + 1) / total_images) * 100)
                yield f"data: {json.dumps({'type': 'progress', 'progress': progress, 'current': idx + 1, 'total': total_images, 'filename': image_info['filename']})}\n\n"
            
            # Send final result
            yield f"data: {json.dumps({'type': 'complete', 'progress': 100, 'category': category, 'count': len(images_with_blemishes), 'images': images_with_blemishes})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    # Create response with proper SSE headers
    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable buffering for nginx if used
        }
    )
    return response


@app.route('/api/detection-images', methods=['GET'])
def get_all_detection_categories():
    """Get all categories that have detection images"""
    try:
        categories = get_all_categories()
        return jsonify({
            'count': len(categories),
            'categories': categories
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/detection_images/<path:filename>')
def serve_detection_image(filename):
    """Serve detection images"""
    try:
        return send_from_directory('detection_images', filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


# ============ Customer Management API ============

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Get all customers"""
    try:
        customers = Customer.query.all()
        return jsonify({
            'count': len(customers),
            'customers': [c.to_dict() for c in customers]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Get customer details"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        return jsonify(customer.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/customers/<int:customer_id>/purchases', methods=['GET'])
def get_customer_purchases(customer_id):
    """Get customer's purchase history"""
    try:
        # Verify customer exists
        customer = Customer.query.get_or_404(customer_id)
        
        # Get purchases ordered by most recent first
        purchases = PurchaseHistory.query.filter_by(
            customer_id=customer_id
        ).order_by(PurchaseHistory.purchase_date.desc()).all()
        
        return jsonify({
            'count': len(purchases),
            'customer': {
                'id': customer.id,
                'name': customer.name
            },
            'purchases': [p.to_dict() for p in purchases]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/customers/<int:customer_id>/knot-transactions', methods=['GET'])
def get_customer_knot_transactions(customer_id):
    """Get customer's original Knot transaction data"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        if not customer.knot_customer_id:
            return jsonify({
                'error': 'Customer not connected to Knot',
                'transactions': []
            }), 200
        
        # Fetch fresh transactions from Knot
        transactions = knot_client.get_customer_transactions(
            customer.knot_customer_id,
            limit=25
        )
        
        return jsonify({
            'count': len(transactions),
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'knot_customer_id': customer.knot_customer_id
            },
            'transactions': transactions
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/customers/<int:customer_id>/notify', methods=['POST'])
def notify_customer_api(customer_id):
    """API endpoint to send notification to a customer via WebSocket"""
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'custom_message')
        notification_data = data.get('data', {})
        
        # Use the notify_customer function
        notify_customer(customer_id, event_type, notification_data)
        
        return jsonify({
            'message': f'Notification sent to customer {customer_id}',
            'event_type': event_type,
            'customer_id': customer_id
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/customers', methods=['POST'])
def create_customer():
    """Create new customer"""
    try:
        data = request.get_json()
        
        customer = Customer(
            knot_customer_id=data.get('knot_customer_id'),
            name=data['name'],
            email=data['email'],
            phone=data.get('phone')
        )
        
        if 'preferences' in data:
            customer.set_preferences(data['preferences'])
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'message': 'Customer created',
            'customer': customer.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============ Knot API Integration ============

@app.route('/api/knot/sync/<external_user_id>', methods=['POST'])
def sync_from_knot(external_user_id):
    """
    Sync customer data from Knot API
    
    For mock mode: Use 'user123' or 'user456'
    For real mode: Use your customer's ID
    
    Optional JSON body: {"name": "...", "email": "..."}
    """
    try:
        # Get optional customer info from request
        data = request.get_json() if request.is_json else {}
        customer_name = data.get('name')
        customer_email = data.get('email')
        
        # Get transaction data from Knot
        sync_data = knot_client.sync_customer_data(
            external_user_id,
            customer_name=customer_name,
            customer_email=customer_email
        )
        
        if not sync_data:
            return jsonify({'error': 'No transactions found for this user in Knot'}), 404
        
        # Check if customer exists
        customer = Customer.query.filter_by(knot_customer_id=external_user_id).first()
        
        if not customer:
            # Create new customer
            customer = Customer(
                knot_customer_id=external_user_id,
                name=sync_data['name'],
                email=sync_data.get('email'),
                phone=sync_data.get('phone')
            )
            db.session.add(customer)
        else:
            # Update existing customer
            customer.name = sync_data['name']
            if sync_data.get('email'):
                customer.email = sync_data['email']
            customer.last_active = datetime.utcnow()
        
        # Update preferences
        customer.set_preferences(sync_data['preferences'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Customer synced from Knot',
            'customer': customer.to_dict(),
            'transaction_count': sync_data.get('transaction_count', sync_data.get('order_count', 0)),
            'preferences': sync_data['preferences']
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/knot/test', methods=['GET'])
def test_knot_connection():
    """Test Knot API connection"""
    try:
        # Determine which test user to use based on environment
        knot_env = os.getenv('KNOT_ENV', 'tunnel')
        
        if knot_env == 'tunnel':
            test_user = 'abc'
        elif knot_env in ['dev', 'prod']:
            test_user = '234638'
        else:
            test_user = 'user123'
        
        sync_data = knot_client.sync_customer_data(test_user)
        
        if sync_data:
            return jsonify({
                'status': 'success',
                'message': 'Knot API connection working',
                'mode': 'mock' if hasattr(knot_client, 'mock_data') else 'real',
                'environment': knot_env,
                'test_user': test_user,
                'sample_data': sync_data
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'No data returned from Knot API',
                'environment': knot_env,
                'test_user': test_user,
                'note': 'Dev/Prod environments may require session creation first. See /api/knot/session/create'
            }), 500
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'environment': os.getenv('KNOT_ENV', 'tunnel')
        }), 500


@app.route('/api/knot/session/create', methods=['POST'])
def create_knot_session():
    """
    Create a Knot session for transaction linking (required for dev/prod)
    
    POST body: {"external_user_id": "your_user_id"}
    """
    try:
        from knot_session import KnotSessionManager
        
        data = request.get_json()
        external_user_id = data.get('external_user_id', 'test_user_001')
        
        manager = KnotSessionManager()
        session = manager.create_session(external_user_id)
        
        if session:
            return jsonify({
                'status': 'success',
                'message': 'Session created. Use session_id with Knot SDK.',
                'session': session,
                'next_steps': [
                    'Invoke Knot SDK with this session_id',
                    'User logs in with test credentials: user_good_transactions / pass_good',
                    'Wait for transactions to be generated',
                    'Then call /api/knot/sync/{external_user_id}'
                ]
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create session'
            }), 500
    
    except ImportError:
        return jsonify({
            'status': 'error',
            'message': 'Session manager not available. Use tunnel mode or install SDK.'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/knot/merchants', methods=['GET'])
def list_knot_merchants():
    """List all available Knot merchants"""
    try:
        from knot_session import KnotSessionManager
        
        manager = KnotSessionManager()
        merchants = manager.list_merchants()
        
        if merchants:
            return jsonify(merchants), 200
        else:
            return jsonify({
                'error': 'Failed to list merchants'
            }), 500
    
    except ImportError:
        return jsonify({
            'error': 'Session manager not available. Use tunnel mode.'
        }), 500
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


# ============ Recommendations API ============
@app.route('/api/recommendations/<int:customer_id>', methods=['GET'])
def get_recommendations(customer_id):
    """Get personalized recommendations for customer"""
    try:
        recommendations = Recommendation.query.filter_by(
            customer_id=customer_id,
            purchased=False
        ).order_by(Recommendation.priority_score.desc()).all()
        
        return jsonify({
            'count': len(recommendations),
            'recommendations': [r.to_dict() for r in recommendations]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommendations/generate', methods=['POST'])
def trigger_recommendations():
    """Manually trigger recommendation generation for all discounted items"""
    try:
        # Get all items with discount >= 20%
        items = FruitInventory.query.join(FreshnessStatus).filter(
            FreshnessStatus.discount_percentage >= 20
        ).all()
        
        for item in items:
            generate_recommendations_for_item(item.id)
        
        return jsonify({
            'message': f'Generated recommendations for {len(items)} items'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ Analytics API ============

@app.route('/api/analytics/waste', methods=['GET'])
def get_waste_analytics():
    """Get waste prevention metrics"""
    try:
        waste_logs = WasteLog.query.all()
        
        total_wasted = sum(log.quantity_wasted for log in waste_logs)
        total_value_loss = sum(log.estimated_value_loss or 0 for log in waste_logs)
        
        # Count items by discount that were sold (not wasted)
        discounted_items = FruitInventory.query.join(FreshnessStatus).filter(
            FreshnessStatus.discount_percentage > 0
        ).all()
        
        items_saved = sum(1 for item in discounted_items if item.quantity == 0)
        
        return jsonify({
            'total_wasted': total_wasted,
            'total_value_loss': total_value_loss,
            'items_saved': items_saved,
            'waste_logs': [log.to_dict() for log in waste_logs[:10]]  # Last 10
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ WebSocket Endpoints ============

@sock.route('/ws/admin')
def admin_websocket(ws):
    """WebSocket for admin dashboard - real-time updates"""
    admin_connections.add(ws)
    try:
        # Send welcome message
        ws.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to admin dashboard',
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        # Keep connection alive and listen for messages
        while True:
            data = ws.receive()
            if data:
                # Admin can request real-time data
                try:
                    request_data = json.loads(data)
                    if request_data.get('action') == 'get_stats':
                        # Send current stats
                        inventory_count = FruitInventory.query.count()
                        critical_count = FreshnessStatus.query.filter(FreshnessStatus.status.in_(['ripe', 'clearance'])).count()
                        
                        ws.send(json.dumps({
                            'type': 'stats',
                            'data': {
                                'inventory_count': inventory_count,
                                'critical_count': critical_count
                            }
                        }))
                except json.JSONDecodeError:
                    pass
    
    except Exception as e:
        print(f"Admin WebSocket error: {e}")
    finally:
        admin_connections.discard(ws)


@sock.route('/ws/customer/<int:customer_id>')
def customer_websocket(ws, customer_id):
    """WebSocket for customer app - real-time notifications"""
    print(f"🔌 Customer {customer_id} connecting to WebSocket...")
    customer_connections[customer_id] = ws
    
    try:
        # Send welcome message
        ws.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to SusCart notifications',
            'customer_id': customer_id,
            'timestamp': datetime.utcnow().isoformat()
        }))
        print(f"✅ Customer {customer_id} WebSocket connected")
        
        # Keep connection alive and listen for messages
        while True:
            data = ws.receive()
            if data:
                # Customer can acknowledge recommendations
                try:
                    action_data = json.loads(data)
                    if action_data.get('action') == 'view_recommendation':
                        rec_id = action_data.get('recommendation_id')
                        with app.app_context():
                            rec = db.session.get(Recommendation, rec_id)
                            if rec:
                                rec.viewed = True
                                db.session.commit()
                                print(f"✓ Customer {customer_id} viewed recommendation {rec_id}")
                except json.JSONDecodeError as e:
                    print(f"⚠️  Customer {customer_id} sent invalid JSON: {e}")
    
    except Exception as e:
        print(f"❌ Customer {customer_id} WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if customer_id in customer_connections:
            del customer_connections[customer_id]
        print(f"🔌 Customer {customer_id} WebSocket disconnected")


# ============ Video Streaming Helper Functions ============

def _initialize_proxy_state():
    """Initialize global proxy state for camera proxy mode"""
    global proxy_state_global
    if proxy_state_global is None:
        proxy_state_global = {
            'inventory_cache': {},
            'default_store_id': None,
            'previous_class_counts': {},
            'last_updated_time': {},
            'last_detection_time': 0,
            'cached_detections': [],
            'frame_times': [],
            'last_frame_time': time.time(),
            'fps_window_size': 30
        }
        
        # Load initial inventory and get default store
        with app.app_context():
            default_store = Store.query.first()
            if not default_store:
                default_store = Store(
                    name="Default Store",
                    location="Camera Detection",
                    contact_info="N/A"
                )
                db.session.add(default_store)
                db.session.commit()
                print(f"✅ Created default store with ID: {default_store.id}")
            proxy_state_global['default_store_id'] = default_store.id
            
            items = FruitInventory.query.all()
            for item in items:
                if item.fruit_type not in proxy_state_global['inventory_cache']:
                    proxy_state_global['inventory_cache'][item.fruit_type] = (item.id, item.quantity)
    
    return proxy_state_global


def _initialize_local_camera_state():
    """Initialize state for local camera mode"""
    inventory_cache = {}
    default_store_id = None
    
    with app.app_context():
        default_store = Store.query.first()
        if not default_store:
            default_store = Store(
                name="Default Store",
                location="Camera Detection",
                contact_info="N/A"
            )
            db.session.add(default_store)
            db.session.commit()
            print(f"✅ Created default store with ID: {default_store.id}")
        default_store_id = default_store.id
        
        items = FruitInventory.query.all()
        for item in items:
            if item.fruit_type not in inventory_cache:
                inventory_cache[item.fruit_type] = (item.id, item.quantity)
    
    return inventory_cache, default_store_id


def _process_detections(frame, detections, min_confidence=0.6):
    """Process YOLO detections and add freshness scores"""
    processed_detections = []
    
    for detection in detections:
        if detection['confidence'] < min_confidence:
            continue
        
        bbox = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']
        
        # Get freshness score if model is loaded
        freshness_score = None
        cropped = None
        if fresh_model is not None:
            cropped = crop_bounding_box(frame, bbox)
            if cropped is not None:
                freshness_score = get_freshness_score(cropped, fresh_model, fresh_device, fresh_transform)
        else:
            cropped = crop_bounding_box(frame, bbox)
            global _fresh_model_warning_shown
            if not _fresh_model_warning_shown:
                print(f"⚠️ Fresh model not loaded - freshness scores will be None")
                _fresh_model_warning_shown = True
        
        # Store cropped image and metadata
        if cropped is not None:
            metadata = {
                'confidence': float(confidence),
                'freshness_score': float(freshness_score) if freshness_score is not None else None,
                'timestamp': datetime.utcnow().isoformat(),
                'bbox': bbox
            }
            detection_dict = {
                'bbox': bbox,
                'class': class_name,
                'confidence': float(confidence),
                'freshness_score': float(freshness_score) if freshness_score is not None else None,
                'cropped_image': cropped,
                'metadata': metadata
            }
            processed_detections.append(detection_dict)
            
            # Store in global memory cache (images stay in memory until processed)
            category = class_name.lower()
            if category not in category_images_memory_cache:
                category_images_memory_cache[category] = []
            category_images_memory_cache[category].append(detection_dict)
        else:
            processed_detections.append({
                'bbox': bbox,
                'class': class_name,
                'confidence': float(confidence),
                'freshness_score': float(freshness_score) if freshness_score is not None else None
            })
    
    return processed_detections


def _calculate_freshness_updates(processed_detections):
    """Calculate average freshness scores per fruit type"""
    freshness_scores_by_type = {}
    
    for det in processed_detections:
        class_name = det['class']
        if det.get('freshness_score') is not None:
            if class_name not in freshness_scores_by_type:
                freshness_scores_by_type[class_name] = []
            freshness_scores_by_type[class_name].append(det['freshness_score'])
    
    freshness_updates = {}
    for fruit_type, freshness_scores in freshness_scores_by_type.items():
        valid_scores = [score for score in freshness_scores if score is not None]
        if valid_scores and len(valid_scores) > 0:
            # freshness_scores are 0-100 from get_freshness_score, convert to 0-1.0
            avg_freshness = (sum(valid_scores) / len(valid_scores)) / 100.0
            freshness_updates[fruit_type] = round(avg_freshness, 4)
    
    return freshness_updates


def _count_detected_classes(processed_detections):
    """Count detected classes from processed detections"""
    current_class_counts = {}
    for det in processed_detections:
        class_name = det['class']
        current_class_counts[class_name] = current_class_counts.get(class_name, 0) + 1
    return current_class_counts


def _calculate_fps(frame_times, window_size=30):
    """Calculate FPS from frame times"""
    if len(frame_times) > window_size:
        frame_times.pop(0)
    
    if len(frame_times) > 0:
        avg_frame_time = sum(frame_times) / len(frame_times)
        return 1.0 / avg_frame_time if avg_frame_time > 0 else 0.0
    return 0.0


def _broadcast_frame_to_frontend(frame, detections, fps):
    """Broadcast frame and detections to all frontend connections"""
    clean_detections = []
    for det in detections:
        clean_detections.append({
            'bbox': det['bbox'],
            'class': det['class'],
            'confidence': det['confidence'],
            'freshness_score': det.get('freshness_score')
        })
    
    # Encode frame to JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_bytes = buffer.tobytes()
    
    # Broadcast to all frontend connections
    num_connections = len(frontend_video_connections)
    if num_connections > 0:
        for frontend_ws in list(frontend_video_connections):
            try:
                metadata_json = json.dumps({
                    'type': 'frame_meta',
                    'detections': clean_detections,
                    'fps': round(fps, 2),
                    'frame_size': len(frame_bytes),
                    'timestamp': datetime.utcnow().isoformat()
                })
                frontend_ws.send(metadata_json)
                frontend_ws.send(frame_bytes)
            except Exception as e:
                frontend_video_connections.discard(frontend_ws)
                print(f"⚠️ Removed dead frontend connection: {e}")


def _get_thumbnail_for_fruit_type(processed_detections, fruit_type):
    """Get thumbnail image for a specific fruit type from detections"""
    for det in processed_detections:
        if det.get('class') == fruit_type and 'cropped_image' in det:
            return det['cropped_image']
    return None


def _prepare_inventory_updates(current_class_counts, previous_class_counts, freshness_updates, 
                               processed_detections, inventory_cache, default_store_id, 
                               last_updated_time, current_time, update_delta):
    """Prepare inventory updates based on detection changes"""
    updates_to_process = []
    all_fruit_types = set(current_class_counts.keys()) | set(previous_class_counts.keys())
    
    for fruit_type in all_fruit_types:
        current_count = current_class_counts.get(fruit_type, 0)
        previous_count = previous_class_counts.get(fruit_type, 0)
        
        # Check if enough time has passed since last update
        if last_updated_time.get(fruit_type) is None:
            last_updated_time[fruit_type] = current_time
        else:
            time_since_last_update = current_time - last_updated_time.get(fruit_type)
            if time_since_last_update < update_delta:
                continue
            last_updated_time[fruit_type] = current_time
        
        # Handle count changes
        if current_count != previous_count:
            # Only delete images when count goes to 0 (images are now kept in memory until processed)
            if current_count == 0:
                threading.Thread(
                    target=delete_category_images,
                    args=(fruit_type,),
                    daemon=True
                ).start()
            
            # Prepare database update
            if fruit_type in inventory_cache:
                item_id, old_quantity = inventory_cache[fruit_type]
                updates_to_process.append({
                    'type': 'update',
                    'item_id': item_id,
                    'fruit_type': fruit_type,
                    'old_quantity': old_quantity,
                    'new_quantity': current_count,
                    'freshness_score': freshness_updates.get(fruit_type) if current_count > 0 else None,
                    'thumbnail_image': _get_thumbnail_for_fruit_type(processed_detections, fruit_type)
                })
                inventory_cache[fruit_type] = (item_id, current_count)
            elif current_count > 0:
                updates_to_process.append({
                    'type': 'create',
                    'fruit_type': fruit_type,
                    'quantity': current_count,
                    'store_id': default_store_id,
                    'freshness_score': freshness_updates.get(fruit_type),
                    'thumbnail_image': _get_thumbnail_for_fruit_type(processed_detections, fruit_type)
                })
        
        # Handle freshness-only updates
        elif current_count > 0 and fruit_type in freshness_updates:
            if fruit_type in inventory_cache:
                item_id, _ = inventory_cache[fruit_type]
                updates_to_process.append({
                    'type': 'freshness_only',
                    'item_id': item_id,
                    'fruit_type': fruit_type,
                    'freshness_score': freshness_updates[fruit_type]
                })
    
    return updates_to_process


def _apply_inventory_updates(updates_to_process, inventory_cache, processed_detections, default_store_id=None):
    """Apply inventory updates to database"""
    if not updates_to_process:
        return
    
    with app.app_context():
        for update in updates_to_process:
            if update['type'] == 'update':
                db_item = db.session.get(FruitInventory, update['item_id'])
                if db_item:
                    db_item.quantity = update['new_quantity']
                    db_item.updated_at = datetime.utcnow()
                    notify_quantity_change(db_item, update['old_quantity'], update['new_quantity'])
                    
                    # Update thumbnail if provided
                    if update.get('thumbnail_image') is not None:
                        thumbnail_path = save_thumbnail(update['thumbnail_image'], update['fruit_type'])
                        db_item.thumbnail_path = thumbnail_path
                    
                    if update.get('freshness_score') is not None:
                        update_freshness_for_item(db_item.id, update['freshness_score'])
                    
                    inventory_cache[update['fruit_type']] = (db_item.id, update['new_quantity'])
                else:
                    # Item was deleted, create new one
                    inventory_cache.pop(update['fruit_type'], None)
                    thumbnail_image = update.get('thumbnail_image')
                    if not thumbnail_image:
                        thumbnail_image = _get_thumbnail_for_fruit_type(processed_detections, update['fruit_type'])
                    
                    timestamp = datetime.utcnow()
                    random_suffix = random.randint(1000, 9999)
                    batch_number = f"BATCH-{timestamp.strftime('%Y%m%d')}-{random_suffix}"
                    
                    thumbnail_path = None
                    if thumbnail_image is not None:
                        thumbnail_path = save_thumbnail(thumbnail_image, update['fruit_type'])
                    
                    new_item = FruitInventory(
                        store_id=default_store_id or update.get('store_id'),
                        fruit_type=update['fruit_type'],
                        quantity=update['new_quantity'],
                        original_price=5.99,
                        current_price=5.99,
                        location_in_store="Camera Detection",
                        batch_number=batch_number,
                        thumbnail_path=thumbnail_path
                    )
                    db.session.add(new_item)
                    db.session.flush()
                    inventory_cache[update['fruit_type']] = (new_item.id, update['new_quantity'])
                    
                    if update.get('freshness_score') is not None:
                        update_freshness_for_item(new_item.id, update['freshness_score'])
                    
                    item_data = notify_quantity_change(new_item, 0, update['new_quantity'])
                    broadcast_to_admins('inventory_added', item_data)
            
            elif update['type'] == 'create':
                timestamp = datetime.utcnow()
                random_suffix = random.randint(1000, 9999)
                batch_number = f"BATCH-{timestamp.strftime('%Y%m%d')}-{random_suffix}"
                
                thumbnail_path = None
                if update.get('thumbnail_image') is not None:
                    thumbnail_path = save_thumbnail(update['thumbnail_image'], update['fruit_type'])
                
                new_item = FruitInventory(
                    store_id=update['store_id'],
                    fruit_type=update['fruit_type'],
                    quantity=update['quantity'],
                    original_price=5.99,
                    current_price=5.99,
                    location_in_store="Camera Detection",
                    batch_number=batch_number,
                    thumbnail_path=thumbnail_path
                )
                db.session.add(new_item)
                db.session.flush()
                inventory_cache[update['fruit_type']] = (new_item.id, update['quantity'])
                
                if update.get('freshness_score') is not None:
                    update_freshness_for_item(new_item.id, update['freshness_score'])
                
                item_data = notify_quantity_change(new_item, 0, update['quantity'])
                broadcast_to_admins('inventory_added', item_data)
            
            elif update['type'] == 'freshness_only':
                update_freshness_for_item(update['item_id'], update['freshness_score'])
        
        db.session.commit()


@sock.route('/ws/stream_video')
def stream_video_websocket(ws):
    """WebSocket for video stream - backend activates camera and streams frames with detections"""
    import threading
    import time
    
    camera = None
    streaming = False
    
    try:
        # Register this frontend connection for proxy broadcasting
        frontend_video_connections.add(ws)
        
        # Check if we're in proxy mode
        is_proxy_mode = CAMERA_MODE == 'proxy'
        
        # Send welcome message
        ws.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to video stream endpoint',
            'fresh_model_loaded': fresh_model is not None,
            'camera_mode': CAMERA_MODE,
            'proxy_mode': is_proxy_mode,
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        # Initialize shared state for proxy mode (if in proxy mode)
        global proxy_state_global
        if is_proxy_mode:
            _initialize_proxy_state()
            print("📹 Proxy mode: Waiting for frames from camera proxy...")
            ws.send(json.dumps({
                'type': 'info',
                'message': 'Proxy mode enabled - ready to receive frames'
            }))
        
        def process_frame():
            """Process frames from camera and send to client"""
            nonlocal streaming, camera
            
            inventory_cache, default_store_id = _initialize_local_camera_state()
            
            # Track class counts
            previous_class_counts = {}  # {fruit_type: count}
            current_class_counts = {}   # {fruit_type: count}
            
            # FPS calculation variables
            frame_times = []
            detection_delta = 0.25
            update_delta = 1
            last_updated_time = {}
            min_confidence = 0.6
            cached_detections = []
            window_size = 30
            last_time = time.time()
            last_detection_time = 0  # Track when detection last ran
            
            while streaming:
                try:
                    # Check if camera is still available
                    if camera is None or not camera.isOpened():
                        break
                    
                    frame_start_time = time.time()
                    ret, frame = camera.read()
                    if not ret:
                        ws.send(json.dumps({
                            'type': 'error',
                            'message': 'Failed to capture frame'
                        }))
                        break
                    
                    # Check if we need to run detection (only if detection_delta seconds have passed)
                    current_time = time.time()
                    time_since_last_detection = current_time - last_detection_time
                    
                    if time_since_last_detection >= detection_delta:
                        # Run detection and process
                        result = detect(frame, allowed_classes=['apple', 'banana', 'orange'], save=False, verbose=False)
                        processed_detections = _process_detections(frame, result['detections'], min_confidence)
                        
                        # Update cache and detection time
                        cached_detections = processed_detections
                        last_detection_time = current_time
                        
                        # Count classes and calculate freshness updates
                        current_class_counts = _count_detected_classes(processed_detections)
                        freshness_updates = _calculate_freshness_updates(processed_detections)
                        
                        # Prepare and apply inventory updates
                        updates_to_process = _prepare_inventory_updates(
                            current_class_counts, previous_class_counts, freshness_updates,
                            processed_detections, inventory_cache, default_store_id,
                            last_updated_time, current_time, update_delta
                        )
                        
                        _apply_inventory_updates(updates_to_process, inventory_cache, processed_detections, default_store_id)
                        
                        # Update previous counts
                        for update in updates_to_process:
                            fruit_type = update.get('fruit_type')
                            if fruit_type:
                                if update['type'] in ['update', 'create']:
                                    previous_class_counts[fruit_type] = update.get('new_quantity', update.get('quantity', 0))
                                elif update['type'] == 'freshness_only':
                                    previous_class_counts[fruit_type] = current_class_counts.get(fruit_type, 0)
                    else:
                        # Use cached detections
                        processed_detections = cached_detections
                    
                    # Calculate FPS
                    current_time = time.time()
                    frame_time = current_time - last_time
                    last_time = current_time
                    frame_times.append(frame_time)
                    fps = _calculate_fps(frame_times, window_size)
                    
                    # Broadcast frame to frontend
                    _broadcast_frame_to_frontend(frame, processed_detections, fps)
                    
                    # Adaptive frame rate control
                    elapsed = time.time() - frame_start_time
                    target_frame_time = 0.05  # 15 FPS
                    if elapsed < target_frame_time:
                        time.sleep(target_frame_time - elapsed)
                    
                except Exception as e:
                    if streaming:  # Only send error if still streaming
                        ws.send(json.dumps({
                            'type': 'error',
                            'message': f'Error processing frame: {str(e)}'
                        }))
                    break
        
        # Shared function to process proxy frames (used when in proxy mode)
        def process_proxy_frame(frame_data_base64, state):
            """Process frame from proxy and broadcast to frontend connections"""
            import base64
            import numpy as np
            
            try:
                # Decode base64 frame
                frame_bytes = base64.b64decode(frame_data_base64)
                nparr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    print("⚠️ Failed to decode frame from proxy")
                    return
                
                # Rate limit detection (only run every 0.25 seconds)
                current_time = time.time()
                detection_delta = 0.25
                update_delta = 1.0
                time_since_last_detection = current_time - state['last_detection_time']
                
                if time_since_last_detection >= detection_delta:
                    # Run detection and process
                    result = detect(frame, allowed_classes=['apple', 'banana', 'orange'], save=False, verbose=False)
                    processed_detections = _process_detections(frame, result['detections'], min_confidence=0.6)
                    
                    # Update cache and detection time
                    state['cached_detections'] = processed_detections
                    state['last_detection_time'] = current_time
                    
                    # Count classes and calculate freshness updates
                    current_class_counts = _count_detected_classes(processed_detections)
                    freshness_updates = _calculate_freshness_updates(processed_detections)
                    
                    # Prepare and apply inventory updates
                    updates_to_process = _prepare_inventory_updates(
                        current_class_counts, state['previous_class_counts'], freshness_updates,
                        processed_detections, state['inventory_cache'], state['default_store_id'],
                        state['last_updated_time'], current_time, update_delta
                    )
                    
                    _apply_inventory_updates(updates_to_process, state['inventory_cache'], processed_detections, state['default_store_id'])
                    
                    # Update previous counts
                    for update in updates_to_process:
                        fruit_type = update.get('fruit_type')
                        if fruit_type:
                            if update['type'] in ['update', 'create']:
                                state['previous_class_counts'][fruit_type] = update.get('new_quantity', update.get('quantity', 0))
                            elif update['type'] == 'freshness_only':
                                state['previous_class_counts'][fruit_type] = current_class_counts.get(fruit_type, 0)
                else:
                    # Use cached detections
                    processed_detections = state['cached_detections']
                
                # Calculate FPS
                current_frame_time = time.time()
                frame_time = current_frame_time - state['last_frame_time']
                state['last_frame_time'] = current_frame_time
                state['frame_times'].append(frame_time)
                fps = _calculate_fps(state['frame_times'], state.get('fps_window_size', 30))
                
                # Broadcast frame to frontend
                _broadcast_frame_to_frontend(frame, processed_detections, fps)
                
            except Exception as e:
                print(f"❌ Error processing proxy frame: {e}")
                import traceback
                traceback.print_exc()
        
        # Listen for commands from client (or frames from proxy if in proxy mode)
        while True:
            data = ws.receive()
            if not data:
                continue
            
            try:
                message = json.loads(data)
                msg_type = message.get('type')
                command = message.get('command')
                
                # Handle proxy frames (when in proxy mode)
                if is_proxy_mode and msg_type == 'frame':
                    frame_data = message.get('data')
                    if frame_data and proxy_state_global:
                        threading.Thread(
                            target=process_proxy_frame,
                            args=(frame_data, proxy_state_global),
                            daemon=True
                        ).start()
                    continue
                
                # Handle proxy connection acknowledgment
                if is_proxy_mode and msg_type == 'proxy_connected':
                    ws.send(json.dumps({
                        'type': 'ack',
                        'message': 'Proxy connection acknowledged'
                    }))
                    continue
                
                # Handle ping/pong
                if msg_type == 'ping':
                    ws.send(json.dumps({'type': 'pong'}))
                    continue
                
                # Handle frontend commands (local mode only)
                if not is_proxy_mode and command == 'start':
                    if camera is not None:
                        ws.send(json.dumps({
                            'type': 'error',
                            'message': 'Camera already started'
                        }))
                        continue
                    
                    # Open camera - use highest available camera index (prefers USB cameras)
                    camera_index = get_best_camera_index()
                    camera = cv2.VideoCapture(camera_index)
                    if not camera.isOpened():
                        ws.send(json.dumps({
                            'type': 'error',
                            'message': 'Failed to open camera'
                        }))
                        continue
                    
                    streaming = True
                    ws.send(json.dumps({
                        'type': 'started',
                        'message': 'Camera started, streaming frames'
                    }))
                    
                    # Start processing frames in a separate thread
                    thread = threading.Thread(target=process_frame, daemon=True)
                    thread.start()
                    
                elif command == 'stop':
                    streaming = False
                    # Give the thread a moment to finish its current iteration
                    time.sleep(0.1)
                    if camera is not None:
                        try:
                            camera.release()
                        except Exception:
                            pass
                        camera = None
                    ws.send(json.dumps({
                        'type': 'stopped',
                        'message': 'Camera stopped'
                    }))
            
            except json.JSONDecodeError:
                ws.send(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                ws.send(json.dumps({
                    'type': 'error',
                    'message': f'Unexpected error: {str(e)}'
                }))
    
    except Exception as e:
        print(f"Video stream WebSocket error: {e}")
    finally:
        # Unregister frontend connection
        frontend_video_connections.discard(ws)
        
        # Properly cleanup: stop streaming first, wait for thread, then release camera
        streaming = False
        # Give the processing thread time to exit its loop
        time.sleep(0.2)
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
            camera = None
        print("Video stream WebSocket disconnected")


# ============ Error Handlers ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Resource not found',
        'message': str(error)
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


# ============ Database Initialization Command ============

@app.cli.command('init-db')
def init_database():
    """Initialize database with tables"""
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")


@app.cli.command('seed-db')
def seed_database():
    """Seed database with sample data"""
    seed_sample_data(app)


@app.cli.command('clear-db')
def clear_database():
    """Clear all data from database"""
    with app.app_context():
        from database import clear_database
        clear_database(app)


# ============ Main ============

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        
        # Seed sample data only if POPULATE is set to true
        if os.getenv('POPULATE', 'false').lower() == 'true':
            if not Store.query.first():
                print("📊 Database is empty. Seeding sample data...")
                seed_sample_data(app)
    
    print("\n" + "="*50)
    print("🛒 SusCart Backend Server Starting...")
    print("="*50)
    print(f"📍 Server: http://localhost:{PORT}")
    print(f"📚 API Routes: http://localhost:{PORT}/routes")
    print(f"🏥 Health Check: http://localhost:{PORT}/health")
    print("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=True
    )
