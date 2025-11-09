"""Inventory management API routes"""

from flask import jsonify, request, Response, stream_with_context
from datetime import datetime
from models import db, Store, FruitInventory, QuantityChangeLog
from utils.helpers import notify_quantity_change, broadcast_to_admins
import json
import cv2
from pathlib import Path
from blemish_detection.blemish import detect_blemishes
from utils.image_storage import DETECTION_IMAGES_DIR, get_category_images, mark_image_as_processed


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
            status = request.args.get('status')  # fresh, ripe, clearance
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
    
    @app.route('/api/inventory/<int:item_id>/actual-freshness', methods=['POST'])
    def add_actual_freshness_score(item_id):
        """Add an actual freshness score to an inventory item"""
        try:
            item = FruitInventory.query.get_or_404(item_id)
            data = request.get_json()
            
            score = data.get('score')
            if score is None:
                return jsonify({'error': 'Score is required'}), 400
            
            # Validate score is between 0 and 1
            try:
                score = float(score)
                if score < 0 or score > 1:
                    return jsonify({'error': 'Score must be between 0 and 1'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Score must be a valid number'}), 400
            
            # Add score to the list
            item.add_actual_freshness_score(score)
            item.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Broadcast update to admin dashboards
            broadcast_to_admins('inventory_updated', item.to_dict())
            
            return jsonify({
                'message': 'Actual freshness score added',
                'item': item.to_dict(),
                'average': item.get_actual_freshness_avg()
            }), 200
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/inventory/analyze-optimize', methods=['GET'])
    def analyze_and_optimize():
        """Analyze all inventory items without actual freshness scores and calculate them"""
        def generate():
            try:
                with app.app_context():
                    # Get all inventory items that don't have actual freshness scores
                    items = FruitInventory.query.all()
                    items_to_process = [
                        item for item in items 
                        if not item.get_actual_freshness_scores() or len(item.get_actual_freshness_scores()) == 0
                    ]
                    
                    total_items = len(items_to_process)
                    
                    if total_items == 0:
                        yield f"data: {json.dumps({'type': 'complete', 'progress': 100, 'message': 'All items already analyzed'})}\n\n"
                        return
                    
                    yield f"data: {json.dumps({'type': 'start', 'total': total_items, 'message': f'Analyzing {total_items} items...'})}\n\n"
                    
                    for idx, item in enumerate(items_to_process):
                        fruit_type = item.fruit_type.lower()
                        
                        # Send progress update
                        progress = int((idx / total_items) * 100)
                        yield f"data: {json.dumps({'type': 'progress', 'progress': progress, 'current': idx + 1, 'total': total_items, 'item': item.fruit_type, 'message': f'Processing {item.fruit_type}...'})}\n\n"
                        
                        # Get detection images for this fruit type
                        images = get_category_images(fruit_type)
                        detection_images = [img for img in images if not img['filename'].startswith('thumbnail.')]
                        
                        if not detection_images:
                            yield f"data: {json.dumps({'type': 'item_complete', 'item': item.fruit_type, 'message': f'No images found for {item.fruit_type}'})}\n\n"
                            continue
                        
                        # Process each image
                        scores = []
                        for img_info in detection_images:
                            image_path = DETECTION_IMAGES_DIR / fruit_type / img_info['filename']
                            
                            # Run blemish detection if not already done
                            blemishes_data = None
                            if img_info.get('metadata') and 'blemishes' in img_info['metadata']:
                                blemishes_data = img_info['metadata']['blemishes']
                            else:
                                try:
                                    blemish_result = detect_blemishes(str(image_path))
                                    blemishes_data = {
                                        'bboxes': blemish_result['bboxes'],
                                        'labels': blemish_result['labels'],
                                        'count': len(blemish_result['bboxes'])
                                    }
                                    
                                    # Save metadata
                                    if not img_info.get('metadata'):
                                        img_info['metadata'] = {}
                                    img_info['metadata']['blemishes'] = blemishes_data
                                    metadata_path = image_path.with_suffix('.json')
                                    with open(metadata_path, 'w') as f:
                                        json.dump(img_info['metadata'], f, indent=2, default=str)
                                    
                                    # Mark image as processed so it doesn't get deleted
                                    new_path = mark_image_as_processed(image_path)
                                    if new_path:
                                        # Update image_path reference - new_path is relative like "detection_images/category/filename"
                                        image_path = Path(new_path)
                                        
                                except Exception as e:
                                    print(f"Error detecting blemishes for {image_path}: {e}")
                                    continue
                            
                            # Calculate actual freshness score
                            if blemishes_data and blemishes_data.get('bboxes'):
                                # Load image to get dimensions
                                img = cv2.imread(str(image_path))
                                if img is not None:
                                    height, width = img.shape[:2]
                                    
                                    # Calculate score (same logic as frontend)
                                    blemishes = blemishes_data['bboxes']
                                    total_blemish_area = 0
                                    for bbox in blemishes:
                                        if bbox.get('box_2d') and len(bbox['box_2d']) == 4:
                                            ymin, xmin, ymax, xmax = bbox['box_2d']
                                            bbox_width = ((xmax - xmin) / 1000) * width
                                            bbox_height = ((ymax - ymin) / 1000) * height
                                            total_blemish_area += bbox_width * bbox_height
                                    
                                    image_area = width * height
                                    blemish_cover_percent = (total_blemish_area / image_area) * 100 if image_area > 0 else 0
                                    blemish_count = len(blemishes)
                                    
                                    count_penalty = min(blemish_count * 0.03, 0.30)
                                    coverage_penalty = min(blemish_cover_percent * 0.004, 0.40)
                                    total_penalty = count_penalty + coverage_penalty
                                    freshness_score = max(0, 1.0 - total_penalty)
                                    
                                    scores.append(freshness_score)
                        
                        # Save scores to database
                        if scores:
                            for score in scores:
                                item.add_actual_freshness_score(score)
                            item.updated_at = datetime.utcnow()
                            db.session.commit()
                            
                            # Broadcast update
                            broadcast_to_admins('inventory_updated', item.to_dict())
                            
                            yield f"data: {json.dumps({'type': 'item_complete', 'item': item.fruit_type, 'scores_count': len(scores), 'average': item.get_actual_freshness_avg()})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'item_complete', 'item': item.fruit_type, 'message': 'No valid scores calculated'})}\n\n"
                    
                    # Final completion
                    yield f"data: {json.dumps({'type': 'complete', 'progress': 100, 'message': 'Analysis complete!'})}\n\n"
                    
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    @app.route('/api/inventory/quantity-history', methods=['GET'])
    def get_quantity_history():
        """Get quantity change history with optional filters"""
        try:
            # Query parameters
            fruit_type = request.args.get('fruit_type')
            inventory_id = request.args.get('inventory_id', type=int)
            limit = request.args.get('limit', type=int, default=1000)
            change_type = request.args.get('change_type')  # 'increase' or 'decrease'
            
            query = QuantityChangeLog.query
            
            if fruit_type:
                query = query.filter_by(fruit_type=fruit_type)
            if inventory_id:
                query = query.filter_by(inventory_id=inventory_id)
            if change_type:
                query = query.filter_by(change_type=change_type)
            
            # Order by most recent first
            changes = query.order_by(QuantityChangeLog.timestamp.desc()).limit(limit).all()
            
            return jsonify({
                'count': len(changes),
                'changes': [change.to_dict() for change in changes]
            }), 200
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/inventory/quantity-statistics', methods=['GET'])
    def get_quantity_statistics():
        """Get statistics about quantity changes by fruit type"""
        try:
            from sqlalchemy import func, case
            
            # First, check if there are any records at all
            total_count = QuantityChangeLog.query.count()
            print(f"Total quantity change logs in database: {total_count}")
            
            # Get statistics grouped by fruit_type
            stats_query = db.session.query(
                QuantityChangeLog.fruit_type,
                func.count(QuantityChangeLog.id).label('total_changes'),
                func.sum(case((QuantityChangeLog.change_type == 'increase', QuantityChangeLog.delta), else_=0)).label('total_increases'),
                func.sum(case((QuantityChangeLog.change_type == 'decrease', func.abs(QuantityChangeLog.delta)), else_=0)).label('total_decreases'),
                func.count(case((QuantityChangeLog.change_type == 'increase', 1), else_=None)).label('increase_count'),
                func.count(case((QuantityChangeLog.change_type == 'decrease', 1), else_=None)).label('decrease_count')
            ).group_by(QuantityChangeLog.fruit_type).all()
            
            print(f"Stats query returned {len(stats_query)} groups")
            
            statistics = []
            for stat in stats_query:
                fruit_type, total_changes, total_increases, total_decreases, increase_count, decrease_count = stat
                print(f"Processing stat: {fruit_type}, changes: {total_changes}, increases: {total_increases}, decreases: {total_decreases}")
                statistics.append({
                    'fruit_type': fruit_type,
                    'total_changes': total_changes or 0,
                    'total_increases': int(total_increases or 0),
                    'total_decreases': int(total_decreases or 0),
                    'increase_count': increase_count or 0,
                    'decrease_count': decrease_count or 0,
                    'net_change': int((total_increases or 0) - (total_decreases or 0))
                })
            
            # Sort by total changes (most popular first)
            statistics.sort(key=lambda x: x['total_changes'], reverse=True)
            
            print(f"Returning {len(statistics)} statistics")
            
            return jsonify({
                'statistics': statistics,
                'most_popular': statistics[0]['fruit_type'] if statistics else None
            }), 200
        
        except Exception as e:
            print(f"Error in get_quantity_statistics: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

