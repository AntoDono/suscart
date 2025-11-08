"""Helper functions for SusCart backend"""

import json
from datetime import datetime
from models import db, FruitInventory, FreshnessStatus, Customer, Recommendation

# These will be set by the app initialization
# Note: These are module-level variables that will be shared across imports
admin_connections = set()
customer_connections = {}  # {customer_id: ws}


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
        
        # Get freshness score if available
        freshness_score = None
        if item.freshness:
            freshness_score = item.freshness.freshness_score
        
        # Send specific quantity change event
        broadcast_to_admins('quantity_changed', {
            'inventory_id': item.id,
            'fruit_type': item.fruit_type,
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'delta': quantity_delta,
            'change_type': 'increase' if quantity_delta > 0 else 'decrease',
            'freshness_score': freshness_score,
            'item': item_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return item_data
    return item.to_dict()


def update_freshness_for_item(inventory_id, freshness_score):
    """
    Helper function to update freshness score for an inventory item and apply price discount.
    Called from video stream processing.
    """
    try:
        # Get or create freshness status
        freshness = FreshnessStatus.query.filter_by(inventory_id=inventory_id).first()
        
        if not freshness:
            freshness = FreshnessStatus(inventory_id=inventory_id)
            db.session.add(freshness)
        
        # Update freshness data
        freshness.freshness_score = freshness_score
        freshness.confidence_level = 0.9  # Default confidence for video stream
        freshness.last_checked = datetime.utcnow()
        
        # Calculate discount and status using the existing formula
        old_discount = freshness.discount_percentage
        freshness.discount_percentage = freshness.calculate_discount()
        freshness.update_status()
        
        # Update inventory price based on discount formula
        inventory = FruitInventory.query.get(inventory_id)
        if inventory:
            # Apply discount: lower freshness = higher discount = lower price
            new_price = round(
                inventory.original_price * (1 - freshness.discount_percentage / 100),
                2
            )
            inventory.current_price = new_price
            inventory.updated_at = datetime.utcnow()
            
            # Broadcast freshness update
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
            
            # Trigger recommendations if new discount is significant
            if freshness.discount_percentage > old_discount and freshness.discount_percentage >= 20:
                generate_recommendations_for_item(inventory_id)
    
    except Exception as e:
        print(f"Error updating freshness for item {inventory_id}: {e}")
        # Don't raise - allow processing to continue


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

