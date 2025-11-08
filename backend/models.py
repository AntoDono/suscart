"""
Database models for SusCart
Tracks inventory, freshness, customers, and recommendations
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Store(db.Model):
    """Store/Location information"""
    __tablename__ = 'stores'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(500))
    contact_info = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    inventory = db.relationship('FruitInventory', back_populates='store', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'contact_info': self.contact_info,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FruitInventory(db.Model):
    """Inventory tracking for fruit items"""
    __tablename__ = 'fruit_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    fruit_type = db.Column(db.String(100), nullable=False)  # apple, banana, orange, etc.
    variety = db.Column(db.String(100))  # e.g., Granny Smith, Cavendish
    quantity = db.Column(db.Integer, nullable=False, default=0)
    batch_number = db.Column(db.String(100))
    arrival_date = db.Column(db.DateTime, default=datetime.utcnow)
    location_in_store = db.Column(db.String(100))  # Aisle/Section
    original_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    store = db.relationship('Store', back_populates='inventory')
    freshness = db.relationship('FreshnessStatus', back_populates='inventory', uselist=False, cascade='all, delete-orphan')
    purchases = db.relationship('PurchaseHistory', back_populates='inventory', cascade='all, delete-orphan')
    recommendations = db.relationship('Recommendation', back_populates='inventory', cascade='all, delete-orphan')
    waste_logs = db.relationship('WasteLog', back_populates='inventory', cascade='all, delete-orphan')
    
    def to_dict(self, include_freshness=True):
        data = {
            'id': self.id,
            'store_id': self.store_id,
            'fruit_type': self.fruit_type,
            'variety': self.variety,
            'quantity': self.quantity,
            'batch_number': self.batch_number,
            'arrival_date': self.arrival_date.isoformat() if self.arrival_date else None,
            'location_in_store': self.location_in_store,
            'original_price': self.original_price,
            'current_price': self.current_price,
            'discount_percentage': round(((self.original_price - self.current_price) / self.original_price * 100), 2) if self.original_price > 0 else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_freshness and self.freshness:
            data['freshness'] = self.freshness.to_dict()
            
        return data


class FreshnessStatus(db.Model):
    """AI-generated freshness monitoring for each inventory item"""
    __tablename__ = 'freshness_status'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False, unique=True)
    freshness_score = db.Column(db.Float, nullable=False)  # 0-100 scale
    predicted_expiry_date = db.Column(db.DateTime)
    confidence_level = db.Column(db.Float)  # 0-1 scale
    discount_percentage = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='fresh')  # fresh, warning, critical, expired
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(500))
    notes = db.Column(db.Text)
    
    # Relationships
    inventory = db.relationship('FruitInventory', back_populates='freshness')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inventory_id': self.inventory_id,
            'freshness_score': self.freshness_score,
            'predicted_expiry_date': self.predicted_expiry_date.isoformat() if self.predicted_expiry_date else None,
            'confidence_level': self.confidence_level,
            'discount_percentage': self.discount_percentage,
            'status': self.status,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'image_url': self.image_url,
            'notes': self.notes
        }
    
    def calculate_discount(self):
        """
        Calculate discount based on freshness score using a dynamic formula.
        Lower freshness = higher discount.
        Formula: discount = max_discount * (1 - freshness_score^power)
        This creates a smooth curve where:
        - freshness_score = 1.0 → discount = 0%
        - freshness_score = 0 → discount = max_discount%
        Note: freshness_score is 0-1.0 scale (not 0-100)
        """
        # Maximum discount at 0 freshness (75%)
        max_discount = 75.0
        # Power factor controls the curve shape (higher = more aggressive discounting at lower freshness)
        # Using 1.5 for a moderate curve that discounts more aggressively as freshness decreases
        power = 1.5
        
        # Clamp freshness_score between 0 and 1.0
        freshness = max(0.0, min(1.0, self.freshness_score))
        
        # Calculate discount: starts at 0% for 1.0 freshness, increases as freshness decreases
        # Using inverse relationship: discount increases as freshness decreases
        discount = max_discount * (1 - (freshness ** power))
        
        return round(discount, 2)
    
    def update_status(self):
        """Update status based on freshness score (0-1.0 scale)"""
        if self.freshness_score >= 0.7:
            self.status = 'fresh'
        elif self.freshness_score >= 0.4:
            self.status = 'warning'
        elif self.freshness_score >= 0.1:
            self.status = 'critical'
        else:
            self.status = 'expired'


class Customer(db.Model):
    """Customer profile and preferences"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    knot_customer_id = db.Column(db.String(200), unique=True)  # ID from Knot API
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True)
    phone = db.Column(db.String(50))
    preferences = db.Column(db.Text)  # JSON string of preferences
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    purchases = db.relationship('PurchaseHistory', back_populates='customer', cascade='all, delete-orphan')
    recommendations = db.relationship('Recommendation', back_populates='customer', cascade='all, delete-orphan')
    
    def to_dict(self, include_preferences=True):
        data = {
            'id': self.id,
            'knot_customer_id': self.knot_customer_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }
        
        if include_preferences and self.preferences:
            try:
                data['preferences'] = json.loads(self.preferences)
            except:
                data['preferences'] = {}
        
        return data
    
    def get_preferences(self):
        """Parse preferences JSON"""
        if self.preferences:
            try:
                return json.loads(self.preferences)
            except:
                return {}
        return {}
    
    def set_preferences(self, prefs_dict):
        """Set preferences from dictionary"""
        self.preferences = json.dumps(prefs_dict)


class PurchaseHistory(db.Model):
    """Track all customer purchases"""
    __tablename__ = 'purchase_history'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_paid = db.Column(db.Float, nullable=False)
    discount_applied = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    knot_transaction_id = db.Column(db.String(200))  # ID from Knot API
    
    # Relationships
    customer = db.relationship('Customer', back_populates='purchases')
    inventory = db.relationship('FruitInventory', back_populates='purchases')
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'inventory_id': self.inventory_id,
            'quantity': self.quantity,
            'price_paid': self.price_paid,
            'discount_applied': self.discount_applied,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'knot_transaction_id': self.knot_transaction_id,
            'fruit_type': self.inventory.fruit_type if self.inventory else None
        }


class Recommendation(db.Model):
    """Personalized recommendations for customers"""
    __tablename__ = 'recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False)
    reason = db.Column(db.Text)  # JSON string explaining why recommended
    priority_score = db.Column(db.Float, default=0)  # Higher = more relevant
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    viewed = db.Column(db.Boolean, default=False)
    purchased = db.Column(db.Boolean, default=False)
    
    # Relationships
    customer = db.relationship('Customer', back_populates='recommendations')
    inventory = db.relationship('FruitInventory', back_populates='recommendations')
    
    def to_dict(self):
        data = {
            'id': self.id,
            'customer_id': self.customer_id,
            'inventory_id': self.inventory_id,
            'priority_score': self.priority_score,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'viewed': self.viewed,
            'purchased': self.purchased
        }
        
        if self.reason:
            try:
                data['reason'] = json.loads(self.reason)
            except:
                data['reason'] = self.reason
        
        if self.inventory:
            data['item'] = self.inventory.to_dict(include_freshness=True)
        
        return data
    
    def set_reason(self, reason_dict):
        """Set reason from dictionary"""
        self.reason = json.dumps(reason_dict)


class WasteLog(db.Model):
    """Track wasted inventory for analytics"""
    __tablename__ = 'waste_log'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False)
    quantity_wasted = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(500))
    estimated_value_loss = db.Column(db.Float)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    inventory = db.relationship('FruitInventory', back_populates='waste_logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inventory_id': self.inventory_id,
            'quantity_wasted': self.quantity_wasted,
            'reason': self.reason,
            'estimated_value_loss': self.estimated_value_loss,
            'logged_at': self.logged_at.isoformat() if self.logged_at else None,
            'fruit_type': self.inventory.fruit_type if self.inventory else None
        }

