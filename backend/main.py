from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sock import Sock
from dotenv import load_dotenv
import json
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Import our modules
from models import db, Store, FruitInventory, FreshnessStatus, Customer, PurchaseHistory, Recommendation, WasteLog
from database import init_db, seed_sample_data
from knot_integration import get_knot_client

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
sock = Sock(app)  # Initialize WebSocket support

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///suscart.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Initialize Knot API client
knot_client = get_knot_client()

# Store active WebSocket connections for real-time updates
admin_connections = set()
customer_connections = {}  # {customer_id: ws}

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
            'ws://localhost:5000/ws/customer/<customer_id> - Customer notifications'
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
        
        # Broadcast to admin dashboards
        broadcast_to_admins('inventory_added', item.to_dict())
        
        return jsonify({
            'message': 'Inventory item created',
            'item': item.to_dict()
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
        
        # Update fields
        if 'quantity' in data:
            item.quantity = data['quantity']
        if 'location_in_store' in data:
            item.location_in_store = data['location_in_store']
        if 'current_price' in data:
            item.current_price = data['current_price']
        
        item.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Broadcast update
        broadcast_to_admins('inventory_updated', item.to_dict())
        
        return jsonify({
            'message': 'Inventory item updated',
            'item': item.to_dict()
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
        broadcast_to_admins('freshness_updated', {
            'inventory_id': inventory_id,
            'freshness': freshness.to_dict(),
            'item': inventory.to_dict() if inventory else None
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

@app.route('/api/knot/sync/<knot_customer_id>', methods=['POST'])
def sync_from_knot(knot_customer_id):
    """Sync customer data from Knot API"""
    try:
        # Get data from Knot
        sync_data = knot_client.sync_customer_data(knot_customer_id)
        
        if not sync_data:
            return jsonify({'error': 'Customer not found in Knot'}), 404
        
        # Check if customer exists
        customer = Customer.query.filter_by(knot_customer_id=knot_customer_id).first()
        
        if not customer:
            # Create new customer
            customer = Customer(
                knot_customer_id=knot_customer_id,
                name=sync_data['name'],
                email=sync_data['email'],
                phone=sync_data['phone']
            )
            db.session.add(customer)
        else:
            # Update existing customer
            customer.name = sync_data['name']
            customer.email = sync_data['email']
            customer.phone = sync_data['phone']
            customer.last_active = datetime.utcnow()
        
        # Update preferences
        customer.set_preferences(sync_data['preferences'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Customer synced from Knot',
            'customer': customer.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============ Recommendations API ============

def generate_recommendations_for_item(inventory_id):
    """Generate recommendations for a discounted item"""
    try:
        item = FruitInventory.query.get(inventory_id)
        if not item or not item.freshness:
            return
        
        # Only recommend if there's a decent discount
        if item.freshness.discount_percentage < 15:
            return
        
        # Find customers who like this fruit type
        customers = Customer.query.all()
        
        for customer in customers:
            prefs = customer.get_preferences()
            favorite_fruits = prefs.get('favorite_fruits', [])
            max_price = prefs.get('max_price', 10.0)
            preferred_discount = prefs.get('preferred_discount', 20)
            
            # Check if this item matches customer preferences
            if (item.fruit_type in favorite_fruits and 
                item.current_price <= max_price and
                item.freshness.discount_percentage >= preferred_discount):
                
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
                
                # Notify customer
                notify_customer(customer.id, 'new_recommendation', recommendation.to_dict())
        
        db.session.commit()
    
    except Exception as e:
        print(f"Error generating recommendations: {e}")
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
    customer_connections[customer_id] = ws
    try:
        # Send welcome message
        ws.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to SusCart notifications',
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        # Keep connection alive
        while True:
            data = ws.receive()
            if data:
                # Customer can acknowledge recommendations
                try:
                    action_data = json.loads(data)
                    if action_data.get('action') == 'view_recommendation':
                        rec_id = action_data.get('recommendation_id')
                        rec = Recommendation.query.get(rec_id)
                        if rec:
                            rec.viewed = True
                            db.session.commit()
                except json.JSONDecodeError:
                    pass
    
    except Exception as e:
        print(f"Customer WebSocket error: {e}")
    finally:
        if customer_id in customer_connections:
            del customer_connections[customer_id]


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
    print("📍 Server: http://localhost:5000")
    print("📚 API Routes: http://localhost:5000/routes")
    print("🏥 Health Check: http://localhost:5000/health")
    print("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
