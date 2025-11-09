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
from utils.image_storage import save_detection_image, get_category_images, get_all_categories, DETECTION_IMAGES_DIR, replace_category_images, delete_category_images, save_thumbnail, mark_image_as_processed   
from blemish_detection.blemish import detect_blemishes
import threading

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
sock = Sock(app)  # Initialize WebSocket support
PORT = os.getenv('PORT', 3000)

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
        images = get_category_images(category.lower())
        # Filter out thumbnail files - they shouldn't be processed for blemish detection
        detection_images = [img for img in images if not img['filename'].startswith('thumbnail.')]
        
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
                    
                    # Mark image as processed so it doesn't get deleted
                    new_path = mark_image_as_processed(image_path)
                    if new_path:
                        # Update image_info with new path and filename
                        image_info['path'] = new_path
                        image_info['filename'] = Path(new_path).name
                        
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


@app.route('/api/detection-images/<category>/stream', methods=['GET'])
def get_detection_images_stream(category):
    """Get detection images with progress updates via Server-Sent Events"""
    def generate():
        try:
            images = get_category_images(category.lower())
            # Filter out thumbnail files - they shouldn't be processed for blemish detection
            detection_images = [img for img in images if not img['filename'].startswith('thumbnail.')]
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
                        
                        # Mark image as processed so it doesn't get deleted
                        new_path = mark_image_as_processed(image_path)
                        if new_path:
                            # Update image_info with new path and filename
                            image_info['path'] = new_path
                            image_info['filename'] = Path(new_path).name
                            image_path = DETECTION_IMAGES_DIR / category.lower() / image_info['filename']
                        
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
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


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


@sock.route('/ws/stream_video')
def stream_video_websocket(ws):
    """WebSocket for video stream - backend activates camera and streams frames with detections"""
    import threading
    import time
    
    camera = None
    streaming = False
    
    try:
        # Send welcome message
        ws.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to video stream endpoint',
            'fresh_model_loaded': fresh_model is not None,
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        def process_frame():
            """Process frames from camera and send to client"""
            nonlocal streaming, camera
            
            # Load initial inventory and get default store
            # Store as dict: {fruit_type: (item_id, current_quantity)}
            inventory_cache = {}
            default_store_id = None
            with app.app_context():
                # Get first store as default, or create one if none exists
                default_store = Store.query.first()
                if not default_store:
                    # Create a default store if none exists
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
                    # Use fruit_type as key, store (item_id, quantity) tuple
                    if item.fruit_type not in inventory_cache:
                        inventory_cache[item.fruit_type] = (item.id, item.quantity)
            
            # Track class counts
            previous_class_counts = {}  # {fruit_type: count}
            current_class_counts = {}   # {fruit_type: count}
            
            # FPS calculation variables
            frame_times = []
            detection_delta = 0.125
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
                        # Run detection
                        result = detect(frame, allowed_classes=['apple', 'banana', 'orange'], save=False, verbose=False)
                        detections = result['detections']
                        
                        # Process each detection and add freshness scores
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
                                    # Freshness will be updated in batched system with delay check
                                else:
                                    print(f"⚠️ Could not crop bounding box for {class_name}")
                            else:
                                # Still crop for image storage even if fresh model not loaded
                                cropped = crop_bounding_box(frame, bbox)
                                global _fresh_model_warning_shown
                                if not _fresh_model_warning_shown:
                                    print(f"⚠️ Fresh model not loaded - freshness scores will be None")
                                    _fresh_model_warning_shown = True
                            
                            # Store cropped image and metadata for later (when counter changes)
                            if cropped is not None:
                                metadata = {
                                    'confidence': float(confidence),
                                    'freshness_score': float(freshness_score) if freshness_score is not None else None,
                                    'timestamp': datetime.utcnow().isoformat(),
                                    'bbox': bbox
                                }
                                processed_detections.append({
                                    'bbox': bbox,  # [x1, y1, x2, y2]
                                    'class': class_name,
                                    'confidence': float(confidence),
                                    'freshness_score': float(freshness_score) if freshness_score is not None else None,
                                    'cropped_image': cropped,  # Store cropped image for later
                                    'metadata': metadata
                                })
                            else:
                                processed_detections.append({
                                    'bbox': bbox,  # [x1, y1, x2, y2]
                                    'class': class_name,
                                    'confidence': float(confidence),
                                    'freshness_score': float(freshness_score) if freshness_score is not None else None
                                })
                        
                        # Update cache and detection time
                        cached_detections = processed_detections
                        last_detection_time = current_time
                        
                        # Count detected classes and collect freshness scores
                        current_class_counts = {}
                        freshness_scores_by_type = {}  # {fruit_type: [freshness_score1, freshness_score2, ...]}
                        
                        for det in processed_detections:
                            class_name = det['class']
                            current_class_counts[class_name] = current_class_counts.get(class_name, 0) + 1
                            
                            # Collect freshness scores for freshness calculation
                            if det.get('freshness_score') is not None:
                                if class_name not in freshness_scores_by_type:
                                    freshness_scores_by_type[class_name] = []
                                freshness_scores_by_type[class_name].append(det['freshness_score'])
                        
                        # Calculate average freshness scores per fruit type
                        # Note: freshness_score from get_freshness_score is already 0-100, but we want 0-1.0
                        # So we need to divide by 100 to convert back to 0-1.0 scale
                        freshness_updates = {}  # {fruit_type: average_freshness_score}
                        for fruit_type, freshness_scores in freshness_scores_by_type.items():
                            # Filter out None values and ensure we have scores
                            valid_scores = [score for score in freshness_scores if score is not None]
                            if valid_scores and len(valid_scores) > 0:
                                # freshness_scores are 0-100 from get_freshness_score, convert to 0-1.0
                                avg_freshness = (sum(valid_scores) / len(valid_scores)) / 100.0
                                freshness_updates[fruit_type] = round(avg_freshness, 4)
                        
                        # Compare with previous counts and update database
                        # Batch all updates to do in a single database transaction
                        updates_to_process = []
                        
                        # Get all fruit types that need to be checked (detected + previously detected)
                        all_fruit_types = set(current_class_counts.keys()) | set(previous_class_counts.keys())
                        
                        # SINGLE UPDATE CHECK - Process all fruits with delay check
                        for fruit_type in all_fruit_types:
                            current_count = current_class_counts.get(fruit_type, 0)
                            previous_count = previous_class_counts.get(fruit_type, 0)
                            
                            # # Check if enough time has passed since last update for this fruit type
                            # print(f"last_updated_time: {last_updated_time} | fruit_type: {fruit_type} | previous_count: {previous_count} | current_count: {current_count}")
                            if last_updated_time.get(fruit_type) is None:
                                # First time seeing this fruit type
                                can_update = True
                                last_updated_time[fruit_type] = current_time
                            else:
                                time_since_last_update = current_time - last_updated_time.get(fruit_type)
                                can_update = time_since_last_update >= update_delta
                                # print(f"time_since_last_update: {time_since_last_update:.2f}s | can_update: {can_update}")
                                if not can_update:
                                    continue  # Skip this fruit type until delay passes
                                else:
                                    last_updated_time[fruit_type] = current_time
                                    # print(f"✅ Updating {fruit_type}: {time_since_last_update:.2f}s >= {update_delta}s")
                            
                            # Handle count changes (including going to 0)
                            if current_count != previous_count:
                                # Handle image storage
                                if current_count > 0:
                                    # Store images for detected fruits
                                    fruit_images = []
                                    for det in processed_detections:
                                        if det.get('class') == fruit_type and 'cropped_image' in det:
                                            fruit_images.append((det['cropped_image'], det.get('metadata', {})))
                                    
                                    if fruit_images:
                                        threading.Thread(
                                            target=replace_category_images,
                                            args=(fruit_images, fruit_type),
                                            daemon=True
                                        ).start()
                                else:
                                    # Clear images when fruit disappears
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
                                        'freshness_score': freshness_updates.get(fruit_type) if current_count > 0 else None
                                    })
                                    # Update cache immediately
                                    inventory_cache[fruit_type] = (item_id, current_count)
                                elif current_count > 0:
                                    # Create new inventory item (store should exist now)
                                    if default_store_id is None:
                                        # This shouldn't happen, but create store if needed
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
                                    
                                    # Get first cropped image for thumbnail if available
                                    thumbnail_image = None
                                    for det in processed_detections:
                                        if det.get('class') == fruit_type and 'cropped_image' in det:
                                            thumbnail_image = det['cropped_image']
                                            break
                                    
                                    updates_to_process.append({
                                        'type': 'create',
                                        'fruit_type': fruit_type,
                                        'quantity': current_count,
                                        'store_id': default_store_id,
                                        'freshness_score': freshness_updates.get(fruit_type),
                                        'thumbnail_image': thumbnail_image
                                    })
                            
                            # Handle freshness-only updates (when count didn't change but freshness did)
                            elif current_count > 0 and fruit_type in freshness_updates:
                                if fruit_type in inventory_cache:
                                    item_id, _ = inventory_cache[fruit_type]
                                    updates_to_process.append({
                                        'type': 'freshness_only',
                                        'item_id': item_id,
                                        'fruit_type': fruit_type,
                                        'freshness_score': freshness_updates[fruit_type]
                                    })
                        
                        # Process all updates in a single database transaction
                        if updates_to_process:
                            with app.app_context():
                                for update in updates_to_process:
                                    if update['type'] == 'update':
                                        db_item = db.session.get(FruitInventory, update['item_id'])
                                        if db_item:
                                            db_item.quantity = update['new_quantity']
                                            db_item.updated_at = datetime.utcnow()
                                            notify_quantity_change(db_item, update['old_quantity'], update['new_quantity'])
                                            
                                            # Update freshness if provided
                                            if update.get('freshness_score') is not None:
                                                update_freshness_for_item(db_item.id, update['freshness_score'])
                                    elif update['type'] == 'create':
                                        # Generate time-based random batch number
                                        timestamp = datetime.utcnow()
                                        random_suffix = random.randint(1000, 9999)
                                        batch_number = f"BATCH-{timestamp.strftime('%Y%m%d')}-{random_suffix}"
                                        
                                        # Save thumbnail if image is available
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
                                        db.session.flush()  # Get the ID without committing
                                        inventory_cache[update['fruit_type']] = (new_item.id, update['quantity'])
                                        
                                        # Update freshness if provided
                                        if update.get('freshness_score') is not None:
                                            update_freshness_for_item(new_item.id, update['freshness_score'])
                                        
                                        # Notify about quantity change (new item = increase from 0)
                                        item_data = notify_quantity_change(new_item, 0, update['quantity'])
                                        
                                        # Also broadcast inventory_added event so frontend can add it to the list
                                        broadcast_to_admins('inventory_added', item_data)
                                    elif update['type'] == 'freshness_only':
                                        # Update freshness without changing quantity
                                        update_freshness_for_item(update['item_id'], update['freshness_score'])
                                
                                # Commit all changes at once
                                db.session.commit()
                            
                            # Update previous counts only for fruits that were actually processed
                            for update in updates_to_process:
                                fruit_type = update.get('fruit_type')
                                if fruit_type:
                                    if update['type'] in ['update', 'create']:
                                        previous_class_counts[fruit_type] = update.get('new_quantity', update.get('quantity', 0))
                                    elif update['type'] == 'freshness_only':
                                        # Keep the same count for freshness-only updates
                                        previous_class_counts[fruit_type] = current_class_counts.get(fruit_type, 0)
                    else:
                        # Use cached detections
                        processed_detections = cached_detections
                    
                    # Calculate FPS
                    current_time = time.time()
                    frame_time = current_time - last_time
                    last_time = current_time
                    
                    frame_times.append(frame_time)
                    if len(frame_times) > window_size:
                        frame_times.pop(0)
                    
                    if len(frame_times) > 0:
                        avg_frame_time = sum(frame_times) / len(frame_times)
                        fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0.0
                    else:
                        fps = 0.0
                    
                    # Encode original frame (non-annotated) to JPEG
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    frame_bytes = buffer.tobytes()
                    
                    # Create clean detections for JSON serialization (remove numpy arrays)
                    clean_detections = []
                    for det in processed_detections:
                        clean_det = {
                            'bbox': det['bbox'],
                            'class': det['class'],
                            'confidence': det['confidence'],
                            'freshness_score': det.get('freshness_score')
                        }
                        clean_detections.append(clean_det)
                    
                    # Send metadata first (detections, fps, frame size)
                    ws.send(json.dumps({
                        'type': 'frame_meta',
                        'detections': clean_detections,
                        'fps': round(fps, 2),
                        'frame_size': len(frame_bytes),
                        'timestamp': datetime.utcnow().isoformat()
                    }))
                    
                    # Send binary frame data (much more efficient than base64)
                    ws.send(frame_bytes)
                    
                    # Adaptive frame rate control - only sleep if processing was fast
                    # Target ~10 FPS, but don't limit if processing is already slow
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
        
        # Listen for commands from client
        while True:
            data = ws.receive()
            if not data:
                continue
            
            try:
                message = json.loads(data)
                command = message.get('command')
                
                if command == 'start':
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
