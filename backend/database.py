"""
Database configuration and initialization
"""

from models import db, Store, FruitInventory, FreshnessStatus, Customer, PurchaseHistory, Recommendation, WasteLog
from datetime import datetime, timedelta
import random


def init_db(app):
    """Initialize the database with the Flask app"""
    db.init_app(app)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully")


def seed_sample_data(app):
    """Populate database with sample data for testing"""
    with app.app_context():
        # Check if data already exists
        if Store.query.first():
            print("⚠️  Database already has data. Skipping seed.")
            return
        
        print("🌱 Seeding sample data...")
        
        # Create a sample store
        store = Store(
            name="Fresh Market Downtown",
            location="123 Main St, San Francisco, CA 94102",
            contact_info="(555) 123-4567"
        )
        db.session.add(store)
        db.session.commit()
        
        # Sample fruit types and varieties
        fruits = [
            {"type": "apple", "variety": "Granny Smith", "price": 2.99},
            {"type": "apple", "variety": "Fuji", "price": 3.49},
            {"type": "banana", "variety": "Cavendish", "price": 1.99},
            {"type": "orange", "variety": "Navel", "price": 2.49},
            {"type": "strawberry", "variety": "Organic", "price": 4.99},
            {"type": "grape", "variety": "Red Seedless", "price": 3.99},
            {"type": "pear", "variety": "Bartlett", "price": 2.79},
            {"type": "mango", "variety": "Ataulfo", "price": 3.99},
            {"type": "blueberry", "variety": "Fresh", "price": 5.99},
            {"type": "watermelon", "variety": "Seedless", "price": 6.99},
        ]
        
        inventory_items = []
        for i, fruit in enumerate(fruits):
            # Create varying arrival dates (some older, some newer)
            days_old = random.randint(1, 10)
            arrival = datetime.utcnow() - timedelta(days=days_old)
            
            # Random quantity
            quantity = random.randint(20, 100)
            
            inventory = FruitInventory(
                store_id=store.id,
                fruit_type=fruit["type"],
                variety=fruit["variety"],
                quantity=quantity,
                batch_number=f"BATCH-{2025}{i+1:03d}",
                arrival_date=arrival,
                location_in_store=f"Aisle {random.randint(1, 8)}",
                original_price=fruit["price"],
                current_price=fruit["price"]
            )
            db.session.add(inventory)
            inventory_items.append(inventory)
        
        db.session.commit()
        
        # Create freshness status for each inventory item
        for item in inventory_items:
            # Calculate freshness based on age
            days_old = (datetime.utcnow() - item.arrival_date).days
            
            # Simulate varying freshness levels
            if days_old <= 2:
                freshness_score = random.uniform(85, 100)
            elif days_old <= 5:
                freshness_score = random.uniform(60, 85)
            elif days_old <= 8:
                freshness_score = random.uniform(30, 60)
            else:
                freshness_score = random.uniform(10, 40)
            
            # Predicted expiry (simulate)
            days_until_expiry = int((freshness_score / 100) * 10)
            predicted_expiry = datetime.utcnow() + timedelta(days=days_until_expiry)
            
            freshness = FreshnessStatus(
                inventory_id=item.id,
                freshness_score=round(freshness_score, 2),
                predicted_expiry_date=predicted_expiry,
                confidence_level=random.uniform(0.8, 0.99),
                last_checked=datetime.utcnow()
            )
            
            # Calculate and apply discount
            freshness.discount_percentage = freshness.calculate_discount()
            freshness.update_status()
            
            # Update inventory price based on discount
            if freshness.discount_percentage > 0:
                item.current_price = round(
                    item.original_price * (1 - freshness.discount_percentage / 100),
                    2
                )
            
            db.session.add(freshness)
        
        db.session.commit()
        
        # Create sample customers
        customers = [
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "phone": "(555) 111-2222",
                "preferences": {
                    "favorite_fruits": ["apple", "banana", "strawberry"],
                    "max_price": 5.00,
                    "preferred_discount": 25
                }
            },
            {
                "name": "Bob Smith",
                "email": "bob@example.com",
                "phone": "(555) 333-4444",
                "preferences": {
                    "favorite_fruits": ["orange", "grape", "watermelon"],
                    "max_price": 7.00,
                    "preferred_discount": 15
                }
            },
            {
                "name": "Carol White",
                "email": "carol@example.com",
                "phone": "(555) 555-6666",
                "preferences": {
                    "favorite_fruits": ["mango", "blueberry", "pear"],
                    "max_price": 6.00,
                    "preferred_discount": 30
                }
            }
        ]
        
        customer_objs = []
        for i, cust_data in enumerate(customers):
            customer = Customer(
                knot_customer_id=f"KNOT-CUST-{1000 + i}",
                name=cust_data["name"],
                email=cust_data["email"],
                phone=cust_data["phone"]
            )
            customer.set_preferences(cust_data["preferences"])
            db.session.add(customer)
            customer_objs.append(customer)
        
        db.session.commit()
        
        # Create some sample purchases
        for customer in customer_objs:
            prefs = customer.get_preferences()
            favorite_fruits = prefs.get("favorite_fruits", [])
            
            # Each customer makes 1-3 purchases
            for _ in range(random.randint(1, 3)):
                # Find an item that matches preferences
                matching_items = [
                    item for item in inventory_items 
                    if item.fruit_type in favorite_fruits and item.quantity > 0
                ]
                
                if matching_items:
                    item = random.choice(matching_items)
                    quantity = random.randint(1, 3)
                    
                    purchase = PurchaseHistory(
                        customer_id=customer.id,
                        inventory_id=item.id,
                        quantity=quantity,
                        price_paid=item.current_price * quantity,
                        discount_applied=item.freshness.discount_percentage if item.freshness else 0,
                        purchase_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                        knot_transaction_id=f"KNOT-TXN-{random.randint(10000, 99999)}"
                    )
                    db.session.add(purchase)
                    
                    # Reduce inventory
                    item.quantity -= quantity
        
        db.session.commit()
        
        print("✅ Sample data seeded successfully!")
        print(f"   - Created {len(inventory_items)} inventory items")
        print(f"   - Created {len(customer_objs)} customers")
        print(f"   - Created purchase history records")


def clear_database(app):
    """Clear all data from database (use with caution!)"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("🗑️  Database cleared and recreated")

