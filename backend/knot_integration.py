"""
Knot API Integration
Handles communication with Knot API for customer transaction data
Documentation: https://docs.knotapi.com/
"""

import requests
from datetime import datetime, timedelta
import os
import base64


class KnotAPIClient:
    """Client for interacting with Knot API"""
    
    # Merchant IDs from Knot API
    MERCHANTS = {
        'amazon': 44,
        'costco': 165,
        'doordash': 19,
        'instacart': 40,
        'target': 12,
        'ubereats': 36,
        'walmart': 45
    }
    
    def __init__(self, client_id=None, secret=None):
        """
        Initialize Knot API client
        
        Args:
            client_id: Knot client ID (defaults to KNOT_CLIENT_ID env variable)
            secret: Knot secret (defaults to KNOT_SECRET env variable)
        """
        self.client_id = client_id or os.getenv('KNOT_CLIENT_ID', 'dda0778d-9486-47f8-bd80-6f2512f9bcdb')
        self.secret = secret or os.getenv('KNOT_SECRET', '884d84e855054c32a8e39d08fcd9845d')
        
        # Use development endpoint (for testing) or production
        self.base_url = os.getenv('KNOT_API_URL', 'https://development.knotapi.com')
        
        # Create Basic Auth header
        credentials = f"{self.client_id}:{self.secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/json'
        }
    
    def sync_transactions(self, external_user_id, merchant_ids=None, limit=100, cursor=None):
        """
        Sync transactions from Knot API
        
        Args:
            external_user_id: Your customer's ID in your system
            merchant_ids: List of merchant IDs to sync (defaults to grocery stores)
            limit: Maximum number of transactions to return (default 100)
            cursor: Pagination cursor for next page
            
        Returns:
            dict: Transaction data from Knot
        """
        # Default to grocery-related merchants if none specified
        if merchant_ids is None:
            merchant_ids = [
                self.MERCHANTS['instacart'],  # Instacart (most relevant for groceries)
                self.MERCHANTS['walmart'],    # Walmart
                self.MERCHANTS['target'],     # Target
                self.MERCHANTS['costco'],     # Costco
                self.MERCHANTS['amazon'],     # Amazon Fresh
            ]
        
        all_transactions = []
        
        # Sync from each merchant
        for merchant_id in merchant_ids:
            try:
                payload = {
                    'merchant_id': merchant_id,
                    'external_user_id': external_user_id,
                    'limit': limit
                }
                
                if cursor:
                    payload['cursor'] = cursor
                
                response = requests.post(
                    f'{self.base_url}/transactions/sync',
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                transactions = data.get('transactions', [])
                all_transactions.extend(transactions)
                
                print(f"✅ Synced {len(transactions)} transactions from merchant {merchant_id}")
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Error syncing from merchant {merchant_id}: {e}")
                continue
        
        return {
            'transactions': all_transactions,
            'count': len(all_transactions),
            'external_user_id': external_user_id
        }
    
    def get_customer_transactions(self, external_user_id, limit=100):
        """
        Convenience method to get all grocery transactions for a customer
        
        Args:
            external_user_id: Your customer's ID
            limit: Max transactions per merchant
            
        Returns:
            list: All transactions
        """
        result = self.sync_transactions(external_user_id, limit=limit)
        return result.get('transactions', [])
    
    def sync_customer_data(self, external_user_id, customer_name=None, customer_email=None):
        """
        Sync customer transaction data from Knot to SusCart
        
        Args:
            external_user_id: Your customer's ID in your system
            customer_name: Customer's name (optional)
            customer_email: Customer's email (optional)
            
        Returns:
            dict: Synchronized customer data ready for SusCart
        """
        # Get transactions from Knot
        transactions = self.get_customer_transactions(external_user_id, limit=100)
        
        if not transactions:
            print(f"⚠️  No transactions found for user {external_user_id}")
            return None
        
        # Analyze purchase patterns from transactions
        preferences = self._analyze_purchase_patterns(transactions)
        
        return {
            'external_user_id': external_user_id,
            'knot_customer_id': external_user_id,  # Use same ID for compatibility
            'name': customer_name or f'Customer {external_user_id}',
            'email': customer_email,
            'phone': None,
            'preferences': preferences,
            'transactions': transactions,
            'transaction_count': len(transactions)
        }
    
    def _analyze_purchase_patterns(self, transactions):
        """
        Analyze customer transaction history to determine preferences
        
        Args:
            transactions: List of transaction data from Knot API
            
        Returns:
            dict: Customer preferences
        """
        if not transactions:
            return {
                'favorite_fruits': [],
                'favorite_products': [],
                'purchase_frequency': 0,
                'average_spend': 0,
                'preferred_discount': 0,
                'max_price': 10.0,
                'merchants_used': []
            }
        
        # Fruit keywords to identify produce
        fruit_keywords = [
            'apple', 'banana', 'orange', 'grape', 'strawberry', 'blueberry',
            'mango', 'pear', 'watermelon', 'peach', 'plum', 'cherry', 'kiwi',
            'pineapple', 'cantaloupe', 'honeydew', 'lemon', 'lime', 'grapefruit',
            'berry', 'fruit', 'produce', 'fresh', 'organic'
        ]
        
        fruit_counts = {}
        product_counts = {}
        total_spend = 0
        merchants = set()
        
        for transaction in transactions:
            # Track merchant
            merchant = transaction.get('merchant', {}).get('name', 'Unknown')
            merchants.add(merchant)
            
            # Get transaction amount
            amount = transaction.get('amount', 0)
            total_spend += abs(amount)  # Use abs in case of refunds
            
            # Analyze SKU data if available
            skus = transaction.get('skus', [])
            description = transaction.get('description', '').lower()
            
            # Check transaction description for fruits
            for keyword in fruit_keywords:
                if keyword in description:
                    fruit_counts[keyword] = fruit_counts.get(keyword, 0) + 1
            
            # Analyze SKUs (line items)
            for sku in skus:
                sku_name = sku.get('name', '').lower()
                sku_category = sku.get('category', '').lower()
                
                # Track product
                if sku_name:
                    product_counts[sku_name] = product_counts.get(sku_name, 0) + 1
                
                # Check if it's a fruit
                if 'produce' in sku_category or 'fruit' in sku_category:
                    for keyword in fruit_keywords:
                        if keyword in sku_name:
                            fruit_counts[keyword] = fruit_counts.get(keyword, 0) + 1
        
        # Get top 5 favorite fruits
        sorted_fruits = sorted(fruit_counts.items(), key=lambda x: x[1], reverse=True)
        favorite_fruits = [fruit for fruit, _ in sorted_fruits[:5]]
        
        # Get top 5 products
        sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)
        favorite_products = [product for product, _ in sorted_products[:5]]
        
        # Calculate averages
        num_transactions = len(transactions)
        average_spend = total_spend / num_transactions if num_transactions > 0 else 0
        
        return {
            'favorite_fruits': favorite_fruits,
            'favorite_products': favorite_products,
            'purchase_frequency': num_transactions / 90,  # transactions per day (assume 90 day window)
            'average_spend': round(average_spend, 2),
            'preferred_discount': 20,  # Default to 20% - adjust based on actual data if available
            'max_price': round(average_spend * 2, 2),  # willing to pay 2x average transaction
            'merchants_used': list(merchants),
            'total_transactions': num_transactions
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
        """Generate mock transaction data in Knot API format"""
        return {
            'user123': {
                'transactions': [
                    {
                        'id': 'txn_mock_001',
                        'merchant': {'id': 40, 'name': 'Instacart'},
                        'amount': -45.67,
                        'date': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                        'description': 'Instacart - Fresh produce delivery',
                        'skus': [
                            {'name': 'Organic Bananas', 'category': 'produce', 'amount': -5.99},
                            {'name': 'Honeycrisp Apples', 'category': 'produce', 'amount': -8.99},
                            {'name': 'Fresh Strawberries', 'category': 'produce', 'amount': -6.99}
                        ]
                    },
                    {
                        'id': 'txn_mock_002',
                        'merchant': {'id': 45, 'name': 'Walmart'},
                        'amount': -32.45,
                        'date': (datetime.utcnow() - timedelta(days=7)).isoformat(),
                        'description': 'Walmart Grocery',
                        'skus': [
                            {'name': 'Navel Oranges 3lb', 'category': 'produce', 'amount': -7.99},
                            {'name': 'Red Grapes', 'category': 'produce', 'amount': -5.49},
                            {'name': 'Mango', 'category': 'produce', 'amount': -2.99}
                        ]
                    },
                    {
                        'id': 'txn_mock_003',
                        'merchant': {'id': 40, 'name': 'Instacart'},
                        'amount': -28.33,
                        'date': (datetime.utcnow() - timedelta(days=14)).isoformat(),
                        'description': 'Instacart - Weekly groceries',
                        'skus': [
                            {'name': 'Organic Blueberries', 'category': 'produce', 'amount': -6.99},
                            {'name': 'Gala Apples', 'category': 'produce', 'amount': -7.49},
                            {'name': 'Bananas', 'category': 'produce', 'amount': -3.99}
                        ]
                    }
                ]
            },
            'user456': {
                'transactions': [
                    {
                        'id': 'txn_mock_004',
                        'merchant': {'id': 12, 'name': 'Target'},
                        'amount': -52.10,
                        'date': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                        'description': 'Target - Grocery run',
                        'skus': [
                            {'name': 'Watermelon', 'category': 'produce', 'amount': -8.99},
                            {'name': 'Pineapple', 'category': 'produce', 'amount': -5.99}
                        ]
                    }
                ]
            }
        }
    
    def sync_transactions(self, external_user_id, merchant_ids=None, limit=100, cursor=None):
        """Return mock transaction data"""
        data = self.mock_data.get(external_user_id)
        if not data:
            return {'transactions': [], 'count': 0, 'external_user_id': external_user_id}
        
        transactions = data.get('transactions', [])
        return {
            'transactions': transactions[:limit],
            'count': len(transactions),
            'external_user_id': external_user_id
        }
    
    def get_customer_transactions(self, external_user_id, limit=100):
        """Return mock transactions"""
        result = self.sync_transactions(external_user_id, limit=limit)
        return result.get('transactions', [])


def get_knot_client():
    """
    Factory function to get appropriate Knot API client
    Uses real client if credentials are configured, otherwise returns mock client
    """
    # Check if custom credentials are provided
    client_id = os.getenv('KNOT_CLIENT_ID')
    secret = os.getenv('KNOT_SECRET')
    use_real = os.getenv('KNOT_USE_REAL', 'false').lower() == 'true'
    
    # If KNOT_USE_REAL is explicitly set to true, use real API with provided/default credentials
    if use_real:
        print("🔗 Using REAL Knot API client")
        print(f"   Client ID: {client_id[:20] if client_id else 'dda0778d-9486-47f8'}...")
        print(f"   Base URL: {os.getenv('KNOT_API_URL', 'https://development.knotapi.com')}")
        return KnotAPIClient(client_id, secret)
    else:
        print("🔗 Using MOCK Knot API client")
        print("   Set KNOT_USE_REAL=true in .env to use real Knot API")
        return MockKnotAPIClient()

