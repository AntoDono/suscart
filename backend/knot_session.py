"""
Knot Session Management for Development Environment
Required for dev/prod environments that need session-based auth
"""

import requests
import os
from datetime import datetime


class KnotSessionManager:
    """
    Manages Knot sessions for transaction linking
    Required for dev/prod environments
    """
    
    def __init__(self, client_id=None, secret=None):
        # SECURITY: Credentials should ONLY be in .env file (gitignored)
        # Never commit credentials to code
        self.client_id = client_id or os.getenv('KNOT_CLIENT_ID')
        self.secret = secret or os.getenv('KNOT_SECRET')
        
        knot_env = os.getenv('KNOT_ENV', 'dev')
        
        if knot_env == 'prod':
            self.base_url = 'https://api.knotapi.com'
        else:
            self.base_url = 'https://development.knotapi.com'
        
        # Create Basic Auth header
        import base64
        credentials = f"{self.client_id}:{self.secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/json',
            'X-Knot-Version': '2024-01-01'
        }
    
    def create_session(self, external_user_id):
        """
        Create a Knot session for transaction linking
        
        Args:
            external_user_id: Your customer's unique ID
            
        Returns:
            dict: Session data with session_id
        """
        try:
            payload = {
                'type': 'transaction_link',
                'external_user_id': external_user_id
            }
            
            response = requests.post(
                f'{self.base_url}/sessions',
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            session_data = response.json()
            print(f"✅ Created session: {session_data.get('session_id', 'N/A')}")
            
            return session_data
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating session: {e}")
            if hasattr(e.response, 'text'):
                print(f"   Response: {e.response.text}")
            return None
    
    def get_session(self, session_id):
        """
        Get session details
        
        Args:
            session_id: Session ID from create_session
            
        Returns:
            dict: Session details
        """
        try:
            response = requests.get(
                f'{self.base_url}/sessions/{session_id}',
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting session: {e}")
            return None
    
    def list_merchants(self):
        """
        List all available merchants
        
        Returns:
            list: Available merchants
        """
        try:
            response = requests.get(
                f'{self.base_url}/merchants',
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            merchants = response.json()
            print(f"✅ Found {len(merchants.get('merchants', []))} merchants")
            return merchants
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error listing merchants: {e}")
            return None


# Example usage for testing
if __name__ == '__main__':
    """
    Test script to create a Knot session
    """
    manager = KnotSessionManager()
    
    # List available merchants
    print("\n=== Listing Merchants ===")
    merchants = manager.list_merchants()
    if merchants:
        for merchant in merchants.get('merchants', [])[:10]:
            print(f"  {merchant.get('id')}: {merchant.get('name')}")
    
    # Create a session
    print("\n=== Creating Session ===")
    session = manager.create_session(external_user_id='test_user_001')
    if session:
        print(f"Session ID: {session.get('session_id')}")
        print(f"Client Token: {session.get('client_token', 'N/A')[:50]}...")
        print("\nNext steps:")
        print("1. Use this session_id with Knot SDK")
        print("2. User logs in with: user_good_transactions / pass_good")
        print("3. Wait for NEW_TRANSACTIONS_AVAILABLE webhook")
        print("4. Then call /transactions/sync")

