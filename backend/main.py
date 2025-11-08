from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sock import Sock
from dotenv import load_dotenv
import json
import os
import cv2
import numpy as np
from datetime import datetime, timedelta
import random
import threading

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
    load_ripe_detection_model, 
    crop_bounding_box, 
    get_ripe_percentage,
    get_best_camera_index
)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
sock = Sock(app)  # Initialize WebSocket support
PORT = os.getenv('PORT', 3000)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///suscart.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Create fake customer if POPULATE env var is set
if os.getenv('POPULATE', 'false').lower() == 'true':
    with app.app_context():
        # Check if fake customer already exists
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

# Store active WebSocket connections for real-time updates
admin_connections = set()
customer_connections = {}  # {customer_id: ws}

# Load ripe detection model globally (once at startup)
ripe_model = None
ripe_device = None
ripe_transform = None
try:
    ripe_model, ripe_device, ripe_transform = load_ripe_detection_model("./model/ripe_detector.pth")
    print("✅ Ripe detection model loaded successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not load ripe detection model: {e}")
    print("   Video stream will work but without ripe detection")

# ============ Utility Functions ============

def broadcast_to_admins(event_type, data):
    """Broadcast message to all connected admin dashboards"""
    message = json.dumps({
        'type': event_type,
        'data': data,
        'timestamp': datetime.utcnow().isoformat()
    })
    
    for ws in admin_connections.copy():
        try:
            ws.send(message)
        except Exception:
            admin_connections.discard(ws)


def notify_customer(customer_id, event_type, data):
    """Send notification to specific customer"""
    if customer_id in customer_connections:
        ws = customer_connections[customer_id]
        try:
            ws.send(json.dumps({
                'type': event_type,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }))
        except Exception:
            del customer_connections[customer_id]


def update_freshness_from_camera(inventory_id, ripe_score, confidence):
    """
    Update freshness status from camera detection (async)
    Called automatically when camera detects ripeness
    """
    try:
        with app.app_context():
            # Get or create freshness status
            freshness = FreshnessStatus.query.filter_by(inventory_id=inventory_id).first()
            
            if not freshness:
                freshness = FreshnessStatus(inventory_id=inventory_id)
                db.session.add(freshness)
            
            # Update freshness data
            freshness.freshness_score = ripe_score
            freshness.confidence_level = confidence
            freshness.last_checked = datetime.utcnow()
            
            # Predict expiry based on ripeness (simple heuristic)
            # Higher ripeness = closer to expiry
            days_until_expiry = int((ripe_score / 100) * 10)  # 0-10 days
            freshness.predicted_expiry_date = datetime.utcnow() + timedelta(days=days_until_expiry)
            
            # Calculate discount and status
            old_discount = freshness.discount_percentage
            freshness.discount_percentage = freshness.calculate_discount()
            freshness.update_status()
            
            # Update inventory price if discount changed
            inventory = FruitInventory.query.get(inventory_id)
            if inventory and freshness.discount_percentage != old_discount:
                inventory.current_price = round(
                    inventory.original_price * (1 - freshness.discount_percentage / 100),
                    2
                )
                inventory.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Broadcast update to admin dashboard
            broadcast_to_admins('freshness_updated', {
                'inventory_id': inventory_id,
                'freshness': freshness.to_dict(),
                'item': inventory.to_dict() if inventory else None,
                'source': 'camera'
            })
            
            # Send alert if critical
            if freshness.status == 'critical':
                broadcast_to_admins('freshness_alert', {
                    'message': f'Camera detected critical ripeness: {inventory.fruit_type}' if inventory else 'Critical item detected',
                    'inventory_id': inventory_id,
                    'freshness_score': freshness.freshness_score
                })
            
            # Trigger recommendations if discount changed and significant
            if freshness.discount_percentage > old_discount and freshness.discount_percentage >= 20:
                print(f"🎯 Triggering recommendations for item {inventory_id} (discount: {freshness.discount_percentage}%)")
                generate_recommendations_for_item(inventory_id)
    
    except Exception as e:
        print(f"❌ Error updating freshness from camera: {e}")
        import traceback
        traceback.print_exc()


def notify_quantity_change(item, old_quantity, new_quantity):
    """Helper function to notify about quantity changes"""
    quantity_delta = new_quantity - old_quantity
    if quantity_delta != 0:
        item_data = item.to_dict()
        item_data['quantity_change'] = {
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'delta': quantity_delta,
            'change_type': 'increase' if quantity_delta > 0 else 'decrease'
        }
        
        # Send specific quantity change event
        broadcast_to_admins('quantity_changed', {
            'inventory_id': item.id,
            'fruit_type': item.fruit_type,
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'delta': quantity_delta,
            'change_type': 'increase' if quantity_delta > 0 else 'decrease',
            'item': item_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return item_data
    return item.to_dict()


# ============ Basic Routes ============

@app.route('/')
def index():
    """Serve the WebSocket test client"""
    return send_from_directory(os.path.dirname(__file__), 'ws_test_client.html')


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
    
    return jsonify({
        'api_routes': sorted(routes, key=lambda x: x['path']),
        'websockets': [
            'ws://localhost:5000/ws/admin - Admin dashboard updates',
            'ws://localhost:5000/ws/customer/<customer_id> - Customer notifications',
            'ws://localhost:5000/ws/stream_video - Video stream'
        ]
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'SusCart backend is running',
        'database': 'connected',
        'knot_api': 'mock' if hasattr(knot_client, 'mock_data') else 'connected'
    }), 200


# ============ Inventory Management API ============

@app.route('/api/stores', methods=['GET'])
def get_stores():
    """Get all stores"""
    try:
        stores = Store.query.all()
        return jsonify({
            'stores': [store.to_dict() for store in stores]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Get all inventory items with optional filters"""
    try:
        # Query parameters for filtering
        store_id = request.args.get('store_id', type=int)
        fruit_type = request.args.get('fruit_type')
        status = request.args.get('status')  # fresh, warning, critical, expired
        min_discount = request.args.get('min_discount', type=float)
        
        query = FruitInventory.query
        
        if store_id:
            query = query.filter_by(store_id=store_id)
        if fruit_type:
            query = query.filter_by(fruit_type=fruit_type)
        
        items = query.all()
        
        # Apply freshness filters
        if status or min_discount is not None:
            filtered_items = []
            for item in items:
                if item.freshness:
                    if status and item.freshness.status != status:
                        continue
                    if min_discount is not None and item.freshness.discount_percentage < min_discount:
                        continue
                filtered_items.append(item)
            items = filtered_items
        
        return jsonify({
            'count': len(items),
            'items': [item.to_dict() for item in items]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inventory/<int:item_id>', methods=['GET'])
def get_inventory_item(item_id):
    """Get specific inventory item details"""
    try:
        item = FruitInventory.query.get_or_404(item_id)
        return jsonify(item.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/inventory', methods=['POST'])
def create_inventory_item():
    """Add new inventory item"""
    try:
        data = request.get_json()
        
        item = FruitInventory(
            store_id=data['store_id'],
            fruit_type=data['fruit_type'],
            variety=data.get('variety'),
            quantity=data['quantity'],
            batch_number=data.get('batch_number'),
            location_in_store=data.get('location_in_store'),
            original_price=data['original_price'],
            current_price=data.get('current_price', data['original_price'])
        )
        
        db.session.add(item)
        db.session.commit()
        
        # Notify about quantity change (new item = increase from 0)
        item_data = notify_quantity_change(item, 0, item.quantity)
        
        # Broadcast to admin dashboards
        broadcast_to_admins('inventory_added', item_data)
        
        return jsonify({
            'message': 'Inventory item created',
            'item': item_data
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Update inventory item"""
    try:
        item = FruitInventory.query.get_or_404(item_id)
        data = request.get_json()
        
        # Track quantity changes
        old_quantity = item.quantity
        
        # Update fields
        if 'quantity' in data:
            item.quantity = data['quantity']
        if 'fruit_type' in data:
            item.fruit_type = data['fruit_type']
        if 'variety' in data:
            item.variety = data['variety']
        if 'batch_number' in data:
            item.batch_number = data['batch_number']
        if 'location_in_store' in data:
            item.location_in_store = data['location_in_store']
        if 'original_price' in data:
            item.original_price = data['original_price']
        if 'current_price' in data:
            item.current_price = data['current_price']
        
        item.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Notify about quantity change if it changed
        update_data = notify_quantity_change(item, old_quantity, item.quantity)
        
        # Also send general inventory update
        broadcast_to_admins('inventory_updated', update_data)
        
        return jsonify({
            'message': 'Inventory item updated',
            'item': update_data
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
    """Delete inventory item"""
    try:
        item = FruitInventory.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        
        broadcast_to_admins('inventory_deleted', {'id': item_id})
        
        return jsonify({'message': 'Inventory item deleted'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


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
        inventory = FruitInventory.query.get(inventory_id)
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
        
        # Send alert if critical
        if freshness.status == 'critical':
            broadcast_to_admins('freshness_alert', {
                'message': f'Item {inventory.fruit_type} is in critical condition!',
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
    """Get all items with critical or warning freshness"""
    try:
        critical_items = FreshnessStatus.query.filter(
            FreshnessStatus.status.in_(['critical', 'warning'])
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

def generate_recommendations_for_item(inventory_id):
    """Generate recommendations for a discounted item"""
    try:
        item = FruitInventory.query.get(inventory_id)
        if not item or not item.freshness:
            print(f"⚠️  Item {inventory_id} not found or has no freshness data")
            return
        
        # Only recommend if there's a decent discount
        if item.freshness.discount_percentage < 15:
            print(f"⚠️  Item {inventory_id} discount too low ({item.freshness.discount_percentage}%), skipping recommendations")
            return
        
        print(f"🔍 Finding customers who like {item.fruit_type} (discount: {item.freshness.discount_percentage}%)")
        
        # Find customers who like this fruit type
        customers = Customer.query.all()
        recommendations_created = []
        
        for customer in customers:
            prefs = customer.get_preferences()
            favorite_fruits = prefs.get('favorite_fruits', [])
            max_price = prefs.get('max_price', 10.0)
            preferred_discount = prefs.get('preferred_discount', 20)
            
            print(f"  Checking customer {customer.id} ({customer.name}): favorites={favorite_fruits}")
            
            # Check if this item matches customer preferences
            if (item.fruit_type in favorite_fruits and 
                item.current_price <= max_price and
                item.freshness.discount_percentage >= preferred_discount):
                
                print(f"  ✅ Match! Creating recommendation for customer {customer.id}")
                
                # Create recommendation
                recommendation = Recommendation(
                    customer_id=customer.id,
                    inventory_id=inventory_id,
                    priority_score=item.freshness.discount_percentage
                )
                
                recommendation.set_reason({
                    'match_type': 'favorite_fruit',
                    'fruit': item.fruit_type,
                    'discount': item.freshness.discount_percentage,
                    'price': item.current_price,
                    'original_price': item.original_price
                })
                
                db.session.add(recommendation)
                db.session.flush()  # Get ID without committing
                
                # Store for notification after commit
                recommendations_created.append({
                    'customer_id': customer.id,
                    'recommendation': recommendation
                })
        
        # Commit all recommendations at once
        db.session.commit()
        
        # NOW send notifications (after commit, so data is in DB)
        for rec_info in recommendations_created:
            customer_id = rec_info['customer_id']
            recommendation = rec_info['recommendation']
            
            print(f"📨 Sending notification to customer {customer_id} for recommendation {recommendation.id}")
            
            # Send notification with full data
            notify_customer(customer_id, 'new_recommendation', {
                'recommendation_id': recommendation.id,
                'item': recommendation.to_dict()
            })
        
        print(f"✅ Created {len(recommendations_created)} recommendations for item {inventory_id}")
    
    except Exception as e:
        print(f"❌ Error generating recommendations: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()


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
                        critical_count = FreshnessStatus.query.filter_by(status='critical').count()
                        
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
                            rec = Recommendation.query.get(rec_id)
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
            'ripe_model_loaded': ripe_model is not None,
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
                # Get first store as default
                default_store = Store.query.first()
                if default_store:
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
                        result = detect(frame, allowed_classes=['*'], save=False, verbose=False)
                        detections = result['detections']
                        
                        # Process each detection and add ripe scores
                        processed_detections = []
                        
                        for detection in detections:
                            if detection['confidence'] < min_confidence:
                                continue
                            
                            bbox = detection['bbox']
                            class_name = detection['class']
                            confidence = detection['confidence']
                            
                            # Get ripe percentage if model is loaded
                            ripe_score = None
                            if ripe_model is not None:
                                cropped = crop_bounding_box(frame, bbox)
                                if cropped is not None:
                                    ripe_score = get_ripe_percentage(cropped, ripe_model, ripe_device, ripe_transform)
                                    
                                    # 🎯 INTEGRATION: Update freshness in database automatically!
                                    # Check if this fruit is in our inventory
                                    if class_name in inventory_cache and ripe_score is not None:
                                        item_id, _ = inventory_cache[class_name]
                                        # Update freshness asynchronously to not block video stream
                                        threading.Thread(
                                            target=update_freshness_from_camera,
                                            args=(item_id, ripe_score, confidence),
                                            daemon=True
                                        ).start()
                            
                            processed_detections.append({
                                'bbox': bbox,  # [x1, y1, x2, y2]
                                'class': class_name,
                                'confidence': float(confidence),
                                'ripe_score': float(ripe_score) if ripe_score is not None else None
                            })
                        
                        # Update cache and detection time
                        cached_detections = processed_detections
                        last_detection_time = current_time
                        
                        # Count detected classes
                        current_class_counts = {}
                        for det in processed_detections:
                            class_name = det['class']
                            current_class_counts[class_name] = current_class_counts.get(class_name, 0) + 1
                        
                        # Compare with previous counts and update database
                        # Batch all updates to do in a single database transaction
                        updates_to_process = []
                        
                        # First, handle all currently detected fruits
                        for fruit_type, current_count in current_class_counts.items():
                            previous_count = previous_class_counts.get(fruit_type, 0)
                            if current_count != previous_count:
                                # Count changed - prepare update
                                if fruit_type in inventory_cache:
                                    item_id, old_quantity = inventory_cache[fruit_type]
                                    updates_to_process.append({
                                        'type': 'update',
                                        'item_id': item_id,
                                        'fruit_type': fruit_type,
                                        'old_quantity': old_quantity,
                                        'new_quantity': current_count
                                    })
                                    # Update cache immediately
                                    inventory_cache[fruit_type] = (item_id, current_count)
                                elif default_store_id is not None:
                                    # Fruit type not in inventory - prepare creation
                                    updates_to_process.append({
                                        'type': 'create',
                                        'fruit_type': fruit_type,
                                        'quantity': current_count,
                                        'store_id': default_store_id
                                    })
                        
                        # Handle fruits that were previously detected but are no longer detected (count = 0)
                        for fruit_type, previous_count in previous_class_counts.items():
                            if fruit_type not in current_class_counts and previous_count > 0:
                                # Fruit no longer detected - set quantity to 0
                                if fruit_type in inventory_cache:
                                    item_id, old_quantity = inventory_cache[fruit_type]
                                    updates_to_process.append({
                                        'type': 'update',
                                        'item_id': item_id,
                                        'fruit_type': fruit_type,
                                        'old_quantity': old_quantity,
                                        'new_quantity': 0
                                    })
                                    # Update cache immediately
                                    inventory_cache[fruit_type] = (item_id, 0)
                        
                        # Process all updates in a single database transaction
                        if updates_to_process:
                            with app.app_context():
                                for update in updates_to_process:
                                    if update['type'] == 'update':
                                        db_item = FruitInventory.query.get(update['item_id'])
                                        if db_item:
                                            db_item.quantity = update['new_quantity']
                                            db_item.updated_at = datetime.utcnow()
                                            notify_quantity_change(db_item, update['old_quantity'], update['new_quantity'])
                                    elif update['type'] == 'create':
                                        # Generate time-based random batch number
                                        timestamp = datetime.utcnow()
                                        random_suffix = random.randint(1000, 9999)
                                        batch_number = f"BATCH-{timestamp.strftime('%Y%m%d')}-{random_suffix}"
                                        
                                        new_item = FruitInventory(
                                            store_id=update['store_id'],
                                            fruit_type=update['fruit_type'],
                                            quantity=update['quantity'],
                                            original_price=5.99,
                                            current_price=5.99,
                                            location_in_store="Camera Detection",
                                            batch_number=batch_number
                                        )
                                        db.session.add(new_item)
                                        db.session.flush()  # Get the ID without committing
                                        inventory_cache[update['fruit_type']] = (new_item.id, update['quantity'])
                                        
                                        # Notify about quantity change (new item = increase from 0)
                                        item_data = notify_quantity_change(new_item, 0, update['quantity'])
                                        
                                        # Also broadcast inventory_added event so frontend can add it to the list
                                        broadcast_to_admins('inventory_added', item_data)
                                
                                # Commit all changes at once
                                db.session.commit()
                        
                        # Update previous counts for next comparison
                        previous_class_counts = current_class_counts.copy()
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
                    
                    # Send metadata first (detections, fps, frame size)
                    ws.send(json.dumps({
                        'type': 'frame_meta',
                        'detections': processed_detections,
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
        
        # Seed sample data if database is empty
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
