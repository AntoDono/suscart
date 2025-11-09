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
    thumbnail_path = db.Column(db.String(500))  # Path to thumbnail image
    actual_freshness_scores = db.Column(db.Text)  # JSON array of actual freshness scores from blemish detection
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    store = db.relationship('Store', back_populates='inventory')
    freshness = db.relationship('FreshnessStatus', back_populates='inventory', uselist=False, cascade='all, delete-orphan')
    purchases = db.relationship('PurchaseHistory', back_populates='inventory', cascade='all, delete-orphan')
    recommendations = db.relationship('Recommendation', back_populates='inventory', cascade='all, delete-orphan')
    waste_logs = db.relationship('WasteLog', back_populates='inventory', cascade='all, delete-orphan')
    quantity_changes = db.relationship('QuantityChangeLog', back_populates='inventory', cascade='all, delete-orphan')
    
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
            'thumbnail_path': self.thumbnail_path,
            'actual_freshness_scores': self.get_actual_freshness_scores(),
            'actual_freshness_avg': self.get_actual_freshness_avg(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_freshness and self.freshness:
            data['freshness'] = self.freshness.to_dict()
            
        return data
    
    def get_actual_freshness_scores(self):
        """Parse actual_freshness_scores JSON"""
        if self.actual_freshness_scores:
            try:
                return json.loads(self.actual_freshness_scores)
            except:
                return []
        return []
    
    def set_actual_freshness_scores(self, scores_list):
        """Set actual_freshness_scores from list"""
        self.actual_freshness_scores = json.dumps(scores_list)
    
    def add_actual_freshness_score(self, score: float):
        """Add a new actual freshness score to the list"""
        scores = self.get_actual_freshness_scores()
        scores.append(score)
        self.set_actual_freshness_scores(scores)
    
    def get_actual_freshness_avg(self):
        """Get average of actual freshness scores, or None if no scores"""
        scores = self.get_actual_freshness_scores()
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)


class FreshnessStatus(db.Model):
    """AI-generated freshness monitoring for each inventory item"""
    __tablename__ = 'freshness_status'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False, unique=True)
    freshness_score = db.Column(db.Float, nullable=False)  # 0-100 scale
    predicted_expiry_date = db.Column(db.DateTime)
    confidence_level = db.Column(db.Float)  # 0-1 scale
    discount_percentage = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='fresh')  # fresh, ripe, clearance
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
        if self.freshness_score >= 0.6:
            self.status = 'fresh'
        elif self.freshness_score >= 0.2:
            self.status = 'ripe'
        else:
            self.status = 'clearance'


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


class QuantityChangeLog(db.Model):
    """Track all quantity changes for inventory items"""
    __tablename__ = 'quantity_change_log'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('fruit_inventory.id'), nullable=False)
    fruit_type = db.Column(db.String(100), nullable=False)  # Store fruit_type for historical tracking
    old_quantity = db.Column(db.Integer, nullable=False)
    new_quantity = db.Column(db.Integer, nullable=False)
    delta = db.Column(db.Integer, nullable=False)  # new_quantity - old_quantity
    change_type = db.Column(db.String(20), nullable=False)  # 'increase' or 'decrease'
    freshness_score = db.Column(db.Float)  # Freshness at time of change
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    inventory = db.relationship('FruitInventory', back_populates='quantity_changes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inventory_id': self.inventory_id,
            'fruit_type': self.fruit_type,
            'old_quantity': self.old_quantity,
            'new_quantity': self.new_quantity,
            'delta': self.delta,
            'change_type': self.change_type,
            'freshness_score': self.freshness_score,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


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


# --- Models for Personalized Buy-Probability + Markov Estimator ---

class PriceCurve(db.Model):
    """Population price-response curves per category"""
    __tablename__ = 'price_curves'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), unique=True, nullable=False)  # e.g., 'apple', 'banana'
    x_discount_bins = db.Column(db.JSON, nullable=False)  # List of discount percentages [0, 10, 25, 50, 75]
    y_pbuy = db.Column(db.JSON, nullable=False)  # List of buy probabilities [0.05, 0.15, 0.45, 0.75, 0.90]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'x_discount_bins': self.x_discount_bins,
            'y_pbuy': self.y_pbuy
        }
    
    def __repr__(self):
        return f"<PriceCurve {self.category}>"


class UserDiscountStat(db.Model):
    """User-specific discount acceptance statistics"""
    __tablename__ = 'user_discount_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    product_name = db.Column(db.String(80), nullable=False)  # e.g., 'apple', 'banana'
    bin_low = db.Column(db.Float, nullable=False)  # Lower bound of discount bin
    bin_high = db.Column(db.Float, nullable=False)  # Upper bound of discount bin
    trials = db.Column(db.Integer, default=0, nullable=False)  # Number of times user saw this discount
    buys = db.Column(db.Integer, default=0, nullable=False)  # Number of times user bought at this discount
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    customer = db.relationship('Customer', backref=db.backref('discount_stats', lazy=True))
    
    # Unique constraint: one stat per user/product/bin combination
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_name', 'bin_low', 'bin_high', name='_user_product_bin_uc'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_name': self.product_name,
            'bin_low': self.bin_low,
            'bin_high': self.bin_high,
            'trials': self.trials,
            'buys': self.buys,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<UserDiscountStat User:{self.user_id} Product:{self.product_name} Bin:[{self.bin_low}-{self.bin_high}]>"


class ProductLCA(db.Model):
    """Product lifecycle assessment data for CO2e calculations"""
    __tablename__ = 'product_lca'
    
    product_name = db.Column(db.String(80), primary_key=True)  # e.g., 'apple', 'banana'
    mass_kg = db.Column(db.Float, nullable=False)  # Average mass per unit in kg
    ef_prod_kgco2e_perkg = db.Column(db.Float, nullable=False)  # Production emission factor (kg CO2e per kg)
    ef_disposal_kgco2e_perunit = db.Column(db.Float, nullable=False)  # Disposal emission factor (kg CO2e per unit)
    displacement = db.Column(db.Float, nullable=False, default=1.0)  # Displacement factor (0-1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'product_name': self.product_name,
            'mass_kg': self.mass_kg,
            'ef_prod_kgco2e_perkg': self.ef_prod_kgco2e_perkg,
            'ef_disposal_kgco2e_perunit': self.ef_disposal_kgco2e_perunit,
            'displacement': self.displacement
        }
    
    def __repr__(self):
        return f"<ProductLCA {self.product_name}>"

