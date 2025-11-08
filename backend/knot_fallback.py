"""
Knot API client with automatic fallback
Tries dev/prod first, falls back to tunnel if it fails
"""

from knot_integration import KnotAPIClient
import os


class KnotClientWithFallback:
    """
    Wrapper around KnotAPIClient that tries dev/prod, then falls back to tunnel
    """
    
    def __init__(self):
        self.primary_env = os.getenv('KNOT_ENV', 'dev')
        self.enable_fallback = os.getenv('KNOT_FALLBACK_TO_TUNNEL', 'true').lower() == 'true'
        
        # Create primary client (dev or prod)
        self.primary_client = KnotAPIClient()
        
        # Create fallback client (tunnel)
        if self.enable_fallback and self.primary_env != 'tunnel':
            # Temporarily override env to create tunnel client
            original_env = os.environ.get('KNOT_ENV')
            os.environ['KNOT_ENV'] = 'tunnel'
            self.fallback_client = KnotAPIClient()
            if original_env:
                os.environ['KNOT_ENV'] = original_env
            else:
                os.environ.pop('KNOT_ENV', None)
            
            print(f"   Fallback to tunnel.tel enabled if {self.primary_env} fails")
        else:
            self.fallback_client = None
    
    def sync_customer_data(self, external_user_id, customer_name=None, customer_email=None):
        """
        Try to sync from primary environment, fall back to tunnel if it fails
        """
        # Try primary (dev or prod)
        print(f"\n🔄 Attempting to sync from {self.primary_env.upper()} environment...")
        try:
            result = self.primary_client.sync_customer_data(
                external_user_id, 
                customer_name=customer_name,
                customer_email=customer_email
            )
            if result:
                print(f"✅ Successfully synced from {self.primary_env.upper()}")
                return result
        except Exception as e:
            print(f"⚠️  {self.primary_env.upper()} sync failed: {e}")
        
        # Try fallback to tunnel
        if self.fallback_client:
            print(f"\n🔄 Falling back to TUNNEL environment...")
            try:
                # For tunnel, 'abc' is the test user
                fallback_user = 'abc' if external_user_id in ['234638', 'test_user_001'] else external_user_id
                result = self.fallback_client.sync_customer_data(
                    fallback_user,
                    customer_name=customer_name,
                    customer_email=customer_email
                )
                if result:
                    print(f"✅ Successfully synced from TUNNEL (fallback)")
                    return result
            except Exception as e:
                print(f"⚠️  Tunnel fallback also failed: {e}")
        
        print(f"❌ All sync attempts failed for user {external_user_id}")
        return None
    
    def get_customer_transactions(self, external_user_id, limit=5):
        """Get transactions with fallback"""
        # Try primary
        try:
            result = self.primary_client.get_customer_transactions(external_user_id, limit)
            if result:
                return result
        except:
            pass
        
        # Try fallback
        if self.fallback_client:
            try:
                fallback_user = 'abc' if external_user_id in ['234638', 'test_user_001'] else external_user_id
                return self.fallback_client.get_customer_transactions(fallback_user, limit)
            except:
                pass
        
        return []
    
    def sync_transactions(self, external_user_id, merchant_ids=None, limit=5, cursor=None):
        """Sync transactions with fallback"""
        # Try primary
        try:
            result = self.primary_client.sync_transactions(external_user_id, merchant_ids, limit, cursor)
            if result and result.get('count', 0) > 0:
                return result
        except:
            pass
        
        # Try fallback
        if self.fallback_client:
            try:
                fallback_user = 'abc' if external_user_id in ['234638', 'test_user_001'] else external_user_id
                return self.fallback_client.sync_transactions(fallback_user, merchant_ids, limit, cursor)
            except:
                pass
        
        return {'transactions': [], 'count': 0, 'external_user_id': external_user_id}

