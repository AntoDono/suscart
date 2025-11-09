"""Helper functions for SusCart backend"""

import json
import os
import threading
import time
from datetime import datetime
from models import db, FruitInventory, FreshnessStatus, Customer, Recommendation, QuantityChangeLog

from xai_sdk import Client
from xai_sdk.chat import user, system

# These will be set by the app initialization
# Note: These are module-level variables that will be shared across imports
admin_connections = set()
customer_connections = {}  # {customer_id: ws}

# Rate limiting for AI recommendations
_last_ai_call_time = 0
_ai_call_lock = threading.Lock()
AI_RECOMMENDATION_INTERVAL = 10  # Minimum seconds between AI calls


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
    """Helper function to notify about quantity changes and save to database"""
    quantity_delta = new_quantity - old_quantity
    if quantity_delta != 0:
        # Get freshness score if available
        freshness_score = None
        if item.freshness:
            freshness_score = item.freshness.freshness_score
        
        # Save to database
        try:
            change_log = QuantityChangeLog(
                inventory_id=item.id,
                fruit_type=item.fruit_type,
                old_quantity=old_quantity,
                new_quantity=new_quantity,
                delta=quantity_delta,
                change_type='increase' if quantity_delta > 0 else 'decrease',
                freshness_score=freshness_score
            )
            db.session.add(change_log)
            db.session.commit()
        except Exception as e:
            print(f"Error saving quantity change log: {e}")
            db.session.rollback()
        
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
                generate_recommendations_for_item(inventory_id, algorithm=False, rate_limited=True)
    
    except Exception as e:
        print(f"Error updating freshness for item {inventory_id}: {e}")
        # Don't raise - allow processing to continue


def _generate_recommendations_with_ai(inventory_id):
    """Generate recommendations using xAI (Grok)"""
    try:
        api_key = os.getenv('XAI_API_KEY')
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable not set")
        
        # Get the item
        item = FruitInventory.query.get(inventory_id)
        if not item or not item.freshness:
            return []
        
        # Only recommend if there's a decent discount
        if item.freshness.discount_percentage < 15:
            return []
        
        # Get all customers
        customers = Customer.query.all()
        if not customers:
            return []
        
        # Get all discounted items (for context)
        all_discounted_items = FruitInventory.query.join(FreshnessStatus).filter(
            FreshnessStatus.discount_percentage >= 15,
            FruitInventory.quantity > 0
        ).all()
        
        # Format customer data
        customers_data = []
        for customer in customers:
            prefs = customer.get_preferences()
            customers_data.append({
                'id': customer.id,
                'name': customer.name,
                'favorite_fruits': prefs.get('favorite_fruits', []),
                'favorite_products': prefs.get('favorite_products', []),
                'max_price': prefs.get('max_price', 10.0),
                'preferred_discount': prefs.get('preferred_discount', 20),
                'average_spend': prefs.get('average_spend', 0),
                'purchase_frequency': prefs.get('purchase_frequency', 0)
            })
        
        # Format item data
        item_data = {
            'id': item.id,
            'fruit_type': item.fruit_type,
            'variety': item.variety,
            'quantity': item.quantity,
            'original_price': item.original_price,
            'current_price': item.current_price,
            'discount_percentage': item.freshness.discount_percentage,
            'freshness_score': item.freshness.freshness_score,
            'status': item.freshness.status
        }
        
        # Calculate days until expiration if available
        days_until_expiration = None
        if item.freshness.predicted_expiry_date:
            delta = item.freshness.predicted_expiry_date - datetime.utcnow()
            days_until_expiration = max(0, delta.days)
        
        # Format available items for context
        available_items = []
        for avail_item in all_discounted_items[:10]:  # Limit to top 10 for context
            if avail_item.freshness:
                available_items.append({
                    'fruit_type': avail_item.fruit_type,
                    'current_price': avail_item.current_price,
                    'discount_percentage': avail_item.freshness.discount_percentage
                })
        
        # Create enhanced prompt
        prompt = f"""You are an intelligent grocery recommendation system that understands customer behavior patterns and timing. Your goal is to match discounted items with customers who will genuinely benefit from and appreciate the recommendation.

CURRENT DISCOUNTED ITEM:
{json.dumps(item_data, indent=2)}

AVAILABLE CUSTOMERS:
{json.dumps(customers_data, indent=2)}

OTHER AVAILABLE DISCOUNTED ITEMS (for context):
{json.dumps(available_items, indent=2)}

CURRENT CONTEXT:
- Day of week: {datetime.now().strftime('%A')}
- Time of day: {datetime.now().strftime('%H:%M')}
{f'- Days until item expires: {days_until_expiration}' if days_until_expiration is not None else ''}

Analyze each customer using these MULTI-DIMENSIONAL CRITERIA:

1. **Purchase Pattern Analysis**
   - Does their purchase_frequency suggest they're due for a shopping trip?
   - Is this item type something they buy regularly vs occasionally?
   - Would this complement their typical basket (e.g., apples for someone who buys peanut butter)?

2. **Timing Relevance**
   - Weekend shoppers vs weekday shoppers
   - Bulk buyers who might want larger quantities
   - Last-minute shoppers who appreciate quick deals

3. **Value Perception Beyond Price**
   - Does the discount percentage exceed their typical threshold?
   - How does current_price compare to their average_spend patterns?
   - Would they perceive this as a "stock up" opportunity vs immediate consumption?

4. **Behavioral Triggers**
   - New variety they haven't tried but aligns with preferences
   - Seasonal relevance (e.g., citrus in winter, berries in summer)
   - Health-conscious choices for nutrition-focused customers

5. **Urgency Factors**
   - Item freshness_score and time sensitivity
   - Limited quantity creating scarcity
   - How this deal compares to typical discounts they respond to

For each recommended customer, provide SPECIFIC, VARIED reasoning that would be compelling to THAT customer. Examples of good reasoning:
- "Perfect for meal prep Sunday - matches weekly buying pattern, 30% discount exceeds usual 20% threshold"
- "Haven't purchased apples in 2 weeks (usual cycle: 10 days), premium variety at everyday price"
- "Complements recent granola purchase, ideal breakfast pairing at 40% off"
- "Last 5 units available, historically purchases when inventory <10"
- "New variety to explore, aligns with adventurous buying pattern, priced below comfort zone"

Return a JSON array of customer IDs who have priority scores reflecting MULTIPLE factors who should receive recommendations. Format:
[
  {{
    "customer_id": 1,
    "priority_score": 85,
    "reason": "Due for weekly apple purchase (last bought 8 days ago), Honeycrisp variety preference match, 35% discount exceeds typical 20% response threshold, perfect for meal prep Sunday routine"
  }},
  {{
    "customer_id": 3,
    "priority_score": 72,
    "reason": "Opportunistic bulk buyer pattern detected, current 5kg quantity matches typical purchase size, hasn't tried this premium variety but loves discovering new fruits, price point 40% below usual premium fruit spending"
  }}
]

Priority score calculation guide:
- 80-100: Perfect match across multiple dimensions
- 60-79: Strong match with compelling reasons
- 40-59: Moderate match, worth notifying
- Below 40: Don't include

If no customers score above 20, return an empty array: []

Focus on creating DIVERSE, SPECIFIC reasons that show you understand each customer's unique shopping behavior. Avoid generic phrases like "good value" or "likes fruit". Each reason should tell a story about WHY this deal matters to THIS specific customer RIGHT NOW.

Only return valid JSON, no additional text."""

        # Call xAI
        client = Client(api_key=api_key)
        chat = client.chat.create(model="grok-4-fast-non-reasoning")
        chat.append(system("You are a helpful grocery recommendation assistant. Always return valid JSON only."))
        chat.append(user(prompt))
        response = chat.sample()
        
        # Parse response
        response_text = response.content.strip()
        
        # Try to extract JSON from response (in case there's extra text)
        try:
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                recommendations = json.loads(json_str)
            else:
                recommendations = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse AI response: {e}")
            print(f"Response was: {response_text}")
            return []
        
        # Create recommendations
        created_recommendations = []
        for rec in recommendations:
            customer_id = rec.get('customer_id')
            priority_score = rec.get('priority_score', item.freshness.discount_percentage)
            reason_text = rec.get('reason', 'AI recommendation')
            
            # Verify customer exists
            customer = Customer.query.get(customer_id)
            if not customer:
                continue
            
            # Create recommendation
            recommendation = Recommendation(
                customer_id=customer_id,
                inventory_id=inventory_id,
                priority_score=priority_score
            )
            
            recommendation.set_reason({
                'match_type': 'ai_recommendation',
                'fruit': item.fruit_type,
                'discount': item.freshness.discount_percentage,
                'price': item.current_price,
                'original_price': item.original_price,
                'reasoning': reason_text,
                'ai_reason': reason_text  # Keep for backward compatibility
            })
            
            db.session.add(recommendation)
            created_recommendations.append((customer_id, recommendation))
        
        db.session.commit()
        
        # Notify customers
        for customer_id, recommendation in created_recommendations:
            notify_customer(customer_id, 'new_recommendation', recommendation.to_dict())
        
        print(f"✅ AI generated {len(created_recommendations)} recommendations for item {inventory_id}")
        return created_recommendations
    
    except Exception as e:
        print(f"❌ Error generating AI recommendations: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return []


def _generate_recommendations_simple(inventory_id):
    """Generate recommendations using simple matching algorithm"""
    try:
        item = FruitInventory.query.get(inventory_id)
        if not item or not item.freshness:
            return []
        
        # Only recommend if there's a decent discount
        if item.freshness.discount_percentage < 15:
            return []
        
        # Find customers who like this fruit type
        customers = Customer.query.all()
        created_recommendations = []
        
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
                    'original_price': item.original_price,
                    'reasoning': 'Algorithm said so'
                })
                
                db.session.add(recommendation)
                created_recommendations.append((customer.id, recommendation))
                
                # Notify customer
                notify_customer(customer.id, 'new_recommendation', recommendation.to_dict())
        
        db.session.commit()
        return created_recommendations
    
    except Exception as e:
        print(f"Error generating recommendations: {e}")
        db.session.rollback()
        return []


# Store app reference for threading (set by main.py)
_app_instance = None

def set_app_instance(app):
    """Set the Flask app instance for use in threads"""
    global _app_instance
    _app_instance = app


def _generate_recommendations_threaded(inventory_id, algorithm, rate_limited):
    """Internal function to run recommendation generation in a thread with app context"""
    if not _app_instance:
        print("❌ App instance not set, cannot run recommendation in thread")
        return
    
    with _app_instance.app_context():
        try:
            if algorithm:
                _generate_recommendations_simple(inventory_id)
            else:
                if rate_limited:
                    global _last_ai_call_time
                    
                    with _ai_call_lock:
                        current_time = time.time()
                        time_since_last_call = current_time - _last_ai_call_time
                        
                        if time_since_last_call < AI_RECOMMENDATION_INTERVAL:
                            # Skip this call, not enough time has passed
                            # print(f"⏸️  Skipping AI recommendation (last call {time_since_last_call:.1f}s ago, need {AI_RECOMMENDATION_INTERVAL}s)")
                            return
                        
                        # Update last call time before making the call
                        _last_ai_call_time = current_time
                    
                    # Make the AI call
                    _generate_recommendations_with_ai(inventory_id)
                else:
                    _generate_recommendations_with_ai(inventory_id)
        except Exception as e:
            print(f"❌ Error in recommendation thread: {e}")
            import traceback
            traceback.print_exc()


def generate_recommendations_for_item(inventory_id, algorithm=True, rate_limited=False, threaded=True):
    """
    Generate recommendations for a discounted item
    
    Args:
        inventory_id: ID of the inventory item
        algorithm: If True, use simple matching. If False, use AI (xAI/Grok)
        rate_limited: If True and algorithm=False, only call AI if enough time has passed since last call
        threaded: If True, run in background thread (non-blocking). If False, run synchronously.
    """
    if threaded:
        # Run in background thread
        thread = threading.Thread(
            target=_generate_recommendations_threaded,
            args=(inventory_id, algorithm, rate_limited),
            daemon=True
        )
        thread.start()
        return []
    else:
        # Run synchronously (for testing or when blocking is acceptable)
        if algorithm:
            return _generate_recommendations_simple(inventory_id)
        else:
            if rate_limited:
                global _last_ai_call_time
                
                with _ai_call_lock:
                    current_time = time.time()
                    time_since_last_call = current_time - _last_ai_call_time
                    
                    if time_since_last_call < AI_RECOMMENDATION_INTERVAL:
                        # Skip this call, not enough time has passed
                        # print(f"⏸️  Skipping AI recommendation (last call {time_since_last_call:.1f}s ago, need {AI_RECOMMENDATION_INTERVAL}s)")
                        return []
                    
                    # Update last call time before making the call
                    _last_ai_call_time = current_time
                
                # Make the AI call
                return _generate_recommendations_with_ai(inventory_id)
            else:
                return _generate_recommendations_with_ai(inventory_id)