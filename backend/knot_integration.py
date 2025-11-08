"""
Knot API Integration
Handles communication with Knot API for customer purchase data
Documentation: https://www.useknotapi.com/docs
"""

import requests
from datetime import datetime, timedelta
import os


class KnotAPIClient:
    """Client for interacting with Knot API"""
    
    def __init__(self, api_key=None):
        """
        Initialize Knot API client
        
        Args:
            api_key: Knot API key (defaults to KNOT_API_KEY env variable)
        """
        self.api_key = api_key or os.getenv('KNOT_API_KEY')
        self.base_url = os.getenv('KNOT_API_URL', 'https://api.useknotapi.com/v1')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_customer(self, knot_customer_id):
        """
        Get customer details from Knot
        
        Args:
            knot_customer_id: Customer ID in Knot system
            
        Returns:
            dict: Customer data
        """
        try:
            response = requests.get(
                f'{self.base_url}/customers/{knot_customer_id}',
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching customer from Knot: {e}")
            return None
    
    def get_customer_purchases(self, knot_customer_id, start_date=None, end_date=None):
        """
        Get customer purchase history from Knot
        
        Args:
            knot_customer_id: Customer ID in Knot system
            start_date: Start date for purchase history (datetime)
            end_date: End date for purchase history (datetime)
            
        Returns:
            list: List of purchase transactions
        """
        try:
            params = {}
            if start_date:
                params['start_date'] = start_date.isoformat()
            if end_date:
                params['end_date'] = end_date.isoformat()
            
            response = requests.get(
                f'{self.base_url}/customers/{knot_customer_id}/purchases',
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('purchases', [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching purchases from Knot: {e}")
            return []
    
    def sync_customer_data(self, knot_customer_id):
        """
        Sync customer data from Knot to SusCart
        
        Args:
            knot_customer_id: Customer ID in Knot system
            
        Returns:
            dict: Synchronized customer data ready for SusCart
        """
        customer_data = self.get_customer(knot_customer_id)
        if not customer_data:
            return None
        
        # Get recent purchases (last 90 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
        purchases = self.get_customer_purchases(knot_customer_id, start_date, end_date)
        
        # Analyze purchase patterns
        preferences = self._analyze_purchase_patterns(purchases)
        
        return {
            'knot_customer_id': knot_customer_id,
            'name': customer_data.get('name', 'Unknown'),
            'email': customer_data.get('email'),
            'phone': customer_data.get('phone'),
            'preferences': preferences,
            'purchases': purchases
        }
    
    def _analyze_purchase_patterns(self, purchases):
        """
        Analyze customer purchase history to determine preferences
        
        Args:
            purchases: List of purchase transactions
            
        Returns:
            dict: Customer preferences
        """
        if not purchases:
            return {
                'favorite_fruits': [],
                'purchase_frequency': 0,
                'average_spend': 0,
                'preferred_discount': 0,
                'max_price': 10.0
            }
        
        # Count fruit purchases
        fruit_counts = {}
        total_spend = 0
        discounted_purchases = 0
        total_discount = 0
        
        for purchase in purchases:
            # Extract fruit type from purchase
            items = purchase.get('items', [])
            for item in items:
                category = item.get('category', '').lower()
                if 'fruit' in category or item.get('type', '').lower() in [
                    'apple', 'banana', 'orange', 'grape', 'strawberry', 
                    'blueberry', 'mango', 'pear', 'watermelon'
                ]:
                    fruit_type = item.get('type', 'unknown').lower()
                    fruit_counts[fruit_type] = fruit_counts.get(fruit_type, 0) + 1
                
                # Track spending
                price = item.get('price', 0)
                total_spend += price
                
                # Track discount preference
                discount = item.get('discount_percentage', 0)
                if discount > 0:
                    discounted_purchases += 1
                    total_discount += discount
        
        # Get top 3 favorite fruits
        sorted_fruits = sorted(fruit_counts.items(), key=lambda x: x[1], reverse=True)
        favorite_fruits = [fruit for fruit, _ in sorted_fruits[:3]]
        
        # Calculate averages
        num_purchases = len(purchases)
        average_spend = total_spend / num_purchases if num_purchases > 0 else 0
        preferred_discount = total_discount / discounted_purchases if discounted_purchases > 0 else 0
        
        return {
            'favorite_fruits': favorite_fruits,
            'purchase_frequency': num_purchases / 90,  # purchases per day
            'average_spend': round(average_spend, 2),
            'preferred_discount': round(preferred_discount, 2),
            'max_price': round(average_spend * 1.5, 2)  # willing to pay 1.5x average
        }
    
    def webhook_handler(self, webhook_data):
        """
        Handle incoming webhooks from Knot
        
        Args:
            webhook_data: Webhook payload from Knot
            
        Returns:
            dict: Processed webhook data
        """
        event_type = webhook_data.get('event_type')
        
        if event_type == 'purchase.created':
            return {
                'type': 'new_purchase',
                'customer_id': webhook_data.get('customer_id'),
                'transaction_id': webhook_data.get('transaction_id'),
                'items': webhook_data.get('items', []),
                'timestamp': webhook_data.get('timestamp')
            }
        elif event_type == 'customer.updated':
            return {
                'type': 'customer_updated',
                'customer_id': webhook_data.get('customer_id'),
                'changes': webhook_data.get('changes', {})
            }
        
        return None


# Mock Knot API for testing (when API key not available)
class MockKnotAPIClient(KnotAPIClient):
    """Mock client for testing without real Knot API access"""
    
    def __init__(self):
        # Don't call parent __init__ to avoid needing API key
        self.base_url = 'mock://knot-api'
        self.mock_data = self._generate_mock_data()
    
    def _generate_mock_data(self):
        """Generate mock customer and purchase data"""
        return {
            'KNOT-CUST-1000': {
                'customer': {
                    'id': 'KNOT-CUST-1000',
                    'name': 'Alice Johnson',
                    'email': 'alice@example.com',
                    'phone': '(555) 111-2222'
                },
                'purchases': [
                    {
                        'transaction_id': 'TXN-001',
                        'date': (datetime.utcnow() - timedelta(days=5)).isoformat(),
                        'items': [
                            {'type': 'apple', 'category': 'fruit', 'quantity': 3, 'price': 8.97, 'discount_percentage': 10},
                            {'type': 'banana', 'category': 'fruit', 'quantity': 6, 'price': 5.94, 'discount_percentage': 0}
                        ]
                    },
                    {
                        'transaction_id': 'TXN-002',
                        'date': (datetime.utcnow() - timedelta(days=15)).isoformat(),
                        'items': [
                            {'type': 'strawberry', 'category': 'fruit', 'quantity': 2, 'price': 7.98, 'discount_percentage': 25}
                        ]
                    }
                ]
            },
            'KNOT-CUST-1001': {
                'customer': {
                    'id': 'KNOT-CUST-1001',
                    'name': 'Bob Smith',
                    'email': 'bob@example.com',
                    'phone': '(555) 333-4444'
                },
                'purchases': [
                    {
                        'transaction_id': 'TXN-003',
                        'date': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                        'items': [
                            {'type': 'orange', 'category': 'fruit', 'quantity': 5, 'price': 12.45, 'discount_percentage': 15}
                        ]
                    }
                ]
            }
        }
    
    def get_customer(self, knot_customer_id):
        """Return mock customer data"""
        data = self.mock_data.get(knot_customer_id)
        return data['customer'] if data else None
    
    def get_customer_purchases(self, knot_customer_id, start_date=None, end_date=None):
        """Return mock purchase data"""
        data = self.mock_data.get(knot_customer_id)
        return data['purchases'] if data else []


def get_knot_client():
    """
    Factory function to get appropriate Knot API client
    Uses real client if API key is available, otherwise returns mock client
    """
    api_key = os.getenv('KNOT_API_KEY')
    
    if api_key and api_key != 'your_knot_api_key_here':
        print("🔗 Using real Knot API client")
        return KnotAPIClient(api_key)
    else:
        print("🔗 Using mock Knot API client (set KNOT_API_KEY for real integration)")
        return MockKnotAPIClient()

