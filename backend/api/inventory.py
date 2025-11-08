"""Inventory management API routes"""

from flask import jsonify, request
from datetime import datetime
from models import db, Store, FruitInventory
from utils.helpers import notify_quantity_change, broadcast_to_admins


def register_inventory_routes(app):
    """Register inventory management routes"""
    
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

