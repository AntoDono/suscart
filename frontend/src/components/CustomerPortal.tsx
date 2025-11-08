import { useState, useEffect, useRef, Component } from 'react';
import type { ReactNode } from 'react';
import './CustomerPortal.css';
import { config } from '../config';

// Error Boundary Component
class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('React Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '2rem', 
          color: '#ef4444', 
          background: '#1a0a0a',
          minHeight: '100vh'
        }}>
          <h1>⚠️ Something went wrong</h1>
          <p>Error: {this.state.error?.message}</p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#7ECA9C',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              marginTop: '1rem'
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

interface Customer {
  id: number;
  knot_customer_id: string;
  name: string;
  email: string;
  preferences: {
    favorite_fruits?: string[];
    favorite_products?: string[];
    average_spend?: number;
    merchants_used?: string[];
    total_transactions?: number;
    max_price?: number;
    preferred_discount?: number;
  };
}

interface Recommendation {
  id: number;
  inventory_id: number;
  priority_score: number;
  sent_at: string;
  viewed: boolean;
  purchased: boolean;
  item: {
    id: number;
    fruit_type: string;
    variety: string;
    quantity: number;
    original_price: number;
    current_price: number;
    discount_percentage: number;
    freshness?: {
      freshness_score: number;
      status: string;
      predicted_expiry_date: string;
    };
  };
  reason: {
    match_type: string;
    fruit?: string;
    discount?: number;
    price?: number;
    original_price?: number;
  };
}

interface WebSocketNotification {
  type: string;
  data: any;
  timestamp: string;
}

interface Purchase {
  id: number;
  inventory_id: number;
  quantity: number;
  price_paid: number;
  discount_applied: number;
  purchase_date: string;
  knot_transaction_id: string | null;
  fruit_type: string;
}

interface KnotTransaction {
  id: string;
  external_id: string;
  datetime: string;
  url: string;
  order_status: string;
  price: {
    sub_total: string;
    total: string;
    currency: string;
  };
  products: {
    external_id: string;
    name: string;
    quantity: number;
    price: {
      sub_total: string;
      total: string;
      unit_price: string;
    };
  }[];
}

const CustomerPortalContent = () => {
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [notifications, setNotifications] = useState<WebSocketNotification[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [knotUserId, setKnotUserId] = useState('');
  const [syncLoading, setSyncLoading] = useState(false);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [knotTransactions, setKnotTransactions] = useState<KnotTransaction[]>([]);
  const [showTransactionType, setShowTransactionType] = useState<'suscart' | 'knot'>('knot');
  
  const wsRef = useRef<WebSocket | null>(null);

  // Load customer from localStorage on mount
  useEffect(() => {
    const savedCustomerId = localStorage.getItem('suscart_customer_id');
    if (savedCustomerId) {
      const id = parseInt(savedCustomerId);
      setCustomerId(id);
      loadCustomerData(id);
      connectWebSocket(id);
    }
  }, []);

  // Helper function to normalize recommendation data and filter
  const normalizeAndFilterRecommendations = (recs: Recommendation[]): Recommendation[] => {
    // Normalize discount_percentage - use freshness discount if item discount is missing
    const normalized = recs.map(rec => {
      const item = rec.item || {} as any;
      const freshness = (item as any)?.freshness || {} as any;
      
      // Use freshness discount if item discount is 0 or missing
      const discount = (item as any).discount_percentage ?? (freshness as any).discount_percentage ?? 0;
      
      return {
        ...rec,
        item: {
          ...item,
          discount_percentage: discount,
          // Ensure current_price is calculated if missing
          current_price: (item as any).current_price ?? ((item as any).original_price ? (item as any).original_price * (1 - discount / 100) : 0)
        }
      };
    });
    
    // Filter out 0% discounts
    const withDiscount = normalized.filter(rec => {
      const discount = (rec.item as any)?.discount_percentage ?? 0;
      return discount > 0;
    });
    
    // Remove duplicates by inventory_id (keep the newest one)
    const seen = new Map<number, Recommendation>();
    withDiscount.forEach(rec => {
      const invId = rec.inventory_id;
      if (!seen.has(invId) || (rec.id > (seen.get(invId)?.id ?? 0))) {
        seen.set(invId, rec);
      }
    });
    
    return Array.from(seen.values());
  };

  const loadCustomerData = async (id: number) => {
    try {
      console.log(`Loading data for customer ${id}...`);
      
      // Fetch customer details
      const customerResponse = await fetch(`${config.apiUrl}/api/customers/${id}`);
      if (customerResponse.ok) {
        const customerData = await customerResponse.json();
        console.log('Customer data loaded:', customerData);
        setCustomer(customerData);
      } else {
        console.error('Failed to fetch customer:', customerResponse.status);
      }

      // Fetch recommendations
      const recsResponse = await fetch(`${config.apiUrl}/api/recommendations/${id}`);
      if (recsResponse.ok) {
        const recsData = await recsResponse.json();
        console.log('Recommendations loaded:', recsData.count || 0);
        const filtered = normalizeAndFilterRecommendations(recsData.recommendations || []);
        console.log('Filtered recommendations:', filtered.length);
        setRecommendations(filtered);
      } else {
        console.error('Failed to fetch recommendations:', recsResponse.status);
        setRecommendations([]);
      }

      // Fetch SusCart purchase history
      const purchasesResponse = await fetch(`${config.apiUrl}/api/customers/${id}/purchases`);
      if (purchasesResponse.ok) {
        const purchasesData = await purchasesResponse.json();
        console.log('Purchases loaded:', purchasesData.count || 0);
        setPurchases(purchasesData.purchases || []);
      } else {
        console.error('Failed to fetch purchases:', purchasesResponse.status);
        setPurchases([]);
      }

      // Fetch Knot transactions
      const knotResponse = await fetch(`${config.apiUrl}/api/customers/${id}/knot-transactions`);
      if (knotResponse.ok) {
        const knotData = await knotResponse.json();
        console.log('Knot transactions loaded:', knotData.count || 0);
        setKnotTransactions(knotData.transactions || []);
      } else {
        console.error('Failed to fetch Knot transactions:', knotResponse.status);
        setKnotTransactions([]);
      }
      
      console.log('✅ All customer data loaded successfully');
    } catch (error) {
      console.error('❌ Error loading customer data:', error);
      // Set empty states to prevent crashes
      setRecommendations([]);
      setPurchases([]);
      setKnotTransactions([]);
    }
  };

  const connectWebSocket = (id: number) => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        console.log('Error closing previous WebSocket:', e);
      }
    }

    console.log(`Connecting to WebSocket for customer ${id}...`);
    
    try {
      const ws = new WebSocket(`${config.wsUrl}/ws/customer/${id}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('✅ Connected to customer WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('📨 WebSocket message:', data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        console.log('🔌 Disconnected from customer WebSocket', event.code, event.reason);
        
        // Attempt to reconnect after 3 seconds if it wasn't a normal closure
        if (event.code !== 1000 && event.code !== 1001) {
          console.log('Will attempt to reconnect in 3 seconds...');
          setTimeout(() => {
            if (id === customerId) {
              console.log('Attempting to reconnect...');
              connectWebSocket(id);
            }
          }, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setIsConnected(false);
      };
    } catch (error) {
      console.error('❌ Failed to create WebSocket:', error);
      setIsConnected(false);
    }
  };

  const handleWebSocketMessage = (data: any) => {
    console.log('WebSocket message received:', data);
    
    try {
      // Add to notifications
      setNotifications(prev => {
        const newNotifications = [data, ...prev].slice(0, 20);
        console.log('Updated notifications:', newNotifications.length);
        return newNotifications;
      });

      // Handle different message types
      if (data.type === 'new_recommendation') {
        console.log('New recommendation received!', data.data);
        
        // Reload the page to ensure all updates are reflected
        console.log('Reloading page to show updated discounts...');
        setTimeout(() => {
          window.location.reload();
        }, 500); // Small delay to ensure WebSocket message is processed
      } else if (data.type === 'connected') {
        console.log('WebSocket connection confirmed');
      } else if (data.type === 'keepalive') {
        // Ignore keepalive messages
      } else {
        console.log('Unhandled message type:', data.type);
      }
    } catch (error) {
      console.error('Error handling WebSocket message:', error, data);
      // Don't let errors crash the component
    }
  };

  const syncFromKnot = async () => {
    if (!knotUserId.trim()) {
      alert('Please enter a Knot user ID (e.g., "abc" for test)');
      return;
    }

    setSyncLoading(true);
    try {
      const response = await fetch(`${config.apiUrl}/api/knot/sync/${knotUserId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Customer ${knotUserId}`,
          email: `${knotUserId}@example.com`
        })
      });

      if (response.ok) {
        const data = await response.json();
        const newCustomerId = data.customer.id;
        
        // Save customer ID
        setCustomerId(newCustomerId);
        localStorage.setItem('suscart_customer_id', newCustomerId.toString());
        
        // Load customer data
        await loadCustomerData(newCustomerId);
        
        // Connect WebSocket
        connectWebSocket(newCustomerId);
        
        alert(`Synced from Knot! Found ${data.transaction_count || 0} transactions`);
      } else {
        const error = await response.json();
        alert(`Error: ${error.error || 'Failed to sync from Knot'}`);
      }
    } catch (error) {
      console.error('Error syncing from Knot:', error);
      alert('Failed to connect to backend');
    } finally {
      setSyncLoading(false);
    }
  };

  const logout = () => {
    setCustomerId(null);
    setCustomer(null);
    setRecommendations([]);
    setNotifications([]);
    localStorage.removeItem('suscart_customer_id');
    if (wsRef.current) {
      wsRef.current.close();
    }
    window.location.hash = '';
  };

  const markAsViewed = async (recommendationId: number) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'view_recommendation',
        recommendation_id: recommendationId
      }));
    }
  };

  const getFreshnessColor = (score: number) => {
    if (score >= 70) return '#4ade80'; // green
    if (score >= 40) return '#fbbf24'; // yellow
    return '#ef4444'; // red
  };

  const getFreshnessLabel = (status: string) => {
    const labels: { [key: string]: string } = {
      'fresh': 'Fresh',
      'warning': 'Warning',
      'critical': 'Critical',
      'expired': 'Expired'
    };
    return labels[status] || status;
  };

  // If not logged in, show sync interface
  if (!customerId || !customer) {
    return (
      <div className="customer-portal login-view">
        <div className="login-container">
          <h1>Welcome to SusCart</h1>
          <p className="subtitle">Get personalized deals based on your shopping history</p>
          
          <div className="knot-sync-section">
            <h2>Connect Your Account</h2>
            <p>Link your grocery purchase history via Knot API</p>
            
            <div className="sync-form">
              <input
                type="text"
                value={knotUserId}
                onChange={(e) => setKnotUserId(e.target.value)}
                placeholder="Enter Knot user ID (e.g., 'abc')"
                className="knot-input"
              />
              <button 
                onClick={syncFromKnot} 
                disabled={syncLoading}
                className="sync-button"
              >
                {syncLoading ? 'Syncing...' : 'Connect with Knot'}
              </button>
            </div>
            
            <div className="test-users">
              <p className="hint">Test Users:</p>
              <button onClick={() => setKnotUserId('abc')} className="test-user-btn">
                Use 'abc' (Test Data)
              </button>
              <button onClick={() => setKnotUserId('user123')} className="test-user-btn">
                Use 'user123' (Mock)
              </button>
            </div>
          </div>

          <div className="or-divider">
            <span>OR</span>
          </div>

          <div className="existing-users">
            <h2>Existing Customers</h2>
            <p>Demo with pre-loaded customers</p>
            <div className="user-buttons">
              <button onClick={() => { 
                setCustomerId(1); 
                localStorage.setItem('suscart_customer_id', '1');
                loadCustomerData(1); 
                connectWebSocket(1); 
              }} className="user-btn">
                Alice Johnson (Likes: Apple, Banana, Strawberry)
              </button>
              <button onClick={() => { 
                setCustomerId(2); 
                localStorage.setItem('suscart_customer_id', '2');
                loadCustomerData(2); 
                connectWebSocket(2); 
              }} className="user-btn">
                Bob Smith (Likes: Orange, Grape, Watermelon)
              </button>
              <button onClick={() => { 
                setCustomerId(3); 
                localStorage.setItem('suscart_customer_id', '3');
                loadCustomerData(3); 
                connectWebSocket(3); 
              }} className="user-btn">
                Carol White (Likes: Mango, Blueberry, Pear)
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="customer-portal">
      {/* Header */}
      <header className="portal-header">
        <div className="header-content">
          <h1>SusCart</h1>
          <div className="header-actions">
            <div className="connection-status">
              <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
              <span>{isConnected ? 'Live' : 'Offline'}</span>
            </div>
            <button onClick={logout} className="logout-btn">Logout</button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="portal-content">
        {/* Customer Info Section */}
        <section className="customer-info-section">
          <div className="info-card">
            <h2>Your Profile</h2>
            <div className="customer-details">
              <p><strong>Name:</strong> {customer.name}</p>
              <p><strong>Email:</strong> {customer.email}</p>
              {customer.knot_customer_id && (
                <p className="knot-badge">
                  Connected via Knot API
                </p>
              )}
            </div>
          </div>

          {/* Preferences from Knot */}
          {customer.preferences && (
            <div className="info-card preferences-card">
              <h2>Your Shopping Profile</h2>
              
              {customer.preferences.favorite_fruits && customer.preferences.favorite_fruits.length > 0 && (
                <div className="preference-section">
                  <h3>Favorite Fruits</h3>
                  <div className="fruit-tags">
                    {customer.preferences.favorite_fruits.map((fruit, idx) => (
                      <span key={idx} className="fruit-tag">
                        {fruit}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="stats-grid">
                {customer.preferences.average_spend && (
                  <div className="stat">
                    <span className="stat-label">Avg. Spend</span>
                    <span className="stat-value">${customer.preferences.average_spend.toFixed(2)}</span>
                  </div>
                )}
                
                {customer.preferences.total_transactions && (
                  <div className="stat">
                    <span className="stat-label">Purchases</span>
                    <span className="stat-value">{customer.preferences.total_transactions}</span>
                  </div>
                )}

                {customer.preferences.merchants_used && customer.preferences.merchants_used.length > 0 && (
                  <div className="stat full-width">
                    <span className="stat-label">Shops At</span>
                    <span className="stat-value merchant-list">
                      {customer.preferences.merchants_used.join(', ')}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Recommendations Section */}
        <section className="recommendations-section">
          <h2>Personalized Deals for You</h2>
          
          {recommendations.length === 0 ? (
            <div className="empty-state">
              <p>No deals right now. We'll notify you when items you like go on sale!</p>
              <p className="hint">Connected via Knot - we know what you love to buy</p>
            </div>
          ) : (
            <div className="recommendations-grid">
              {recommendations.map((rec) => (
                <div 
                  key={rec.id} 
                  className={`recommendation-card ${rec.viewed ? 'viewed' : 'new'}`}
                  onClick={() => !rec.viewed && markAsViewed(rec.id)}
                >
                  {!rec.viewed && <span className="new-badge">NEW</span>}
                  
                  <div className="rec-header">
                    <h3>{rec.item.fruit_type}</h3>
                    {rec.item.variety && <span className="variety">{rec.item.variety}</span>}
                  </div>

                  <div className="price-display">
                    <span className="current-price">${((rec.item as any).current_price || 0).toFixed(2)}</span>
                    <span className="original-price">${((rec.item as any).original_price || 0).toFixed(2)}</span>
                    <span className="discount-badge">{((rec.item as any).discount_percentage || 0).toFixed(0)}% OFF</span>
                  </div>

                  {rec.item?.freshness && (
                    <div className="freshness-info">
                      <div 
                        className="freshness-bar" 
                        style={{ 
                          width: `${rec.item.freshness.freshness_score || 0}%`,
                          backgroundColor: getFreshnessColor(rec.item.freshness.freshness_score || 0)
                        }}
                      ></div>
                      <span className="freshness-label">
                        {getFreshnessLabel(rec.item.freshness.status)} - {(rec.item.freshness.freshness_score || 0).toFixed(0)}%
                      </span>
                    </div>
                  )}

                  <div className="rec-reason">
                    {rec.reason?.match_type === 'favorite_fruit' && (
                      <p>Recommended because you love {rec.reason.fruit}!</p>
                    )}
                    <p className="from-knot">Based on your purchase history</p>
                  </div>

                  <div className="rec-details">
                    <span>{rec.item?.quantity || 0} available</span>
                    {rec.item?.freshness?.predicted_expiry_date && (
                      <span>
                        Until {new Date(rec.item.freshness.predicted_expiry_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  {rec.purchased && (
                    <div className="purchased-badge">Purchased</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Live Notifications */}
        {notifications.length > 0 && (
          <section className="notifications-section">
            <h2>Live Updates</h2>
            <div className="notifications-list">
              {notifications.map((notif, idx) => (
                <div key={idx} className="notification-item">
                  <span className="notif-type">{notif.type}</span>
                  <span className="notif-time">
                    {new Date(notif.timestamp).toLocaleTimeString()}
                  </span>
                  <pre className="notif-data">
                    {JSON.stringify(notif.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Transaction History */}
        <section className="transactions-section">
          <div className="section-header">
            <h2>Transaction History</h2>
            <div className="transaction-toggle">
              <button 
                className={`toggle-btn ${showTransactionType === 'knot' ? 'active' : ''}`}
                onClick={() => setShowTransactionType('knot')}
              >
                Knot Purchases ({knotTransactions.length})
              </button>
              <button 
                className={`toggle-btn ${showTransactionType === 'suscart' ? 'active' : ''}`}
                onClick={() => setShowTransactionType('suscart')}
              >
                SusCart Purchases ({purchases.length})
              </button>
            </div>
          </div>

          {/* Knot Transactions */}
          {showTransactionType === 'knot' && (
            <div className="transactions-list">
              {knotTransactions.length === 0 ? (
                <div className="empty-state">
                  <p>No Knot transaction history available</p>
                  <p className="hint">Connect your Knot account to see purchase history</p>
                </div>
              ) : (
                <div className="scrollable-transactions">
                  {knotTransactions.map((transaction) => (
                    <div key={transaction.id} className="transaction-card knot-transaction">
                      <div className="transaction-header">
                        <div className="transaction-info">
                          <span className="transaction-id">Order #{transaction.external_id?.substring(0, 8) || transaction.id.substring(0, 8)}</span>
                          <span className="transaction-date">
                            {new Date(transaction.datetime).toLocaleDateString()}
                          </span>
                        </div>
                        <div className="transaction-total">
                          ${parseFloat(transaction.price.total).toFixed(2)}
                        </div>
                      </div>

                      <div className="transaction-status">
                        <span className={`status-badge ${transaction.order_status.toLowerCase()}`}>
                          {transaction.order_status}
                        </span>
                        <a href={transaction.url} target="_blank" rel="noopener noreferrer" className="order-link">
                          View Order →
                        </a>
                      </div>

                      <div className="transaction-products">
                        {transaction.products.slice(0, 3).map((product, idx) => (
                          <div key={idx} className="product-item">
                            <span className="product-name">{product.name}</span>
                            <span className="product-details">
                              {product.quantity}x ${parseFloat(product.price.unit_price).toFixed(2)}
                            </span>
                          </div>
                        ))}
                        {transaction.products.length > 3 && (
                          <div className="more-products">
                            +{transaction.products.length - 3} more items
                          </div>
                        )}
                      </div>

                      <div className="knot-source">
                        From Knot API
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SusCart Purchases */}
          {showTransactionType === 'suscart' && (
            <div className="transactions-list">
              {purchases.length === 0 ? (
                <div className="empty-state">
                  <p>No SusCart purchases yet</p>
                  <p className="hint">Your purchases from our store will appear here</p>
                </div>
              ) : (
                <div className="scrollable-transactions">
                  {purchases.map((purchase) => (
                    <div key={purchase.id} className="transaction-card suscart-transaction">
                      <div className="transaction-header">
                        <div className="transaction-info">
                          <div>
                            <div className="purchase-fruit">{purchase.fruit_type}</div>
                            <div className="purchase-date">
                              {new Date(purchase.purchase_date).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        <div className="purchase-total">
                          ${purchase.price_paid.toFixed(2)}
                        </div>
                      </div>

                      <div className="purchase-details">
                        <div className="detail-row">
                          <span>Quantity:</span>
                          <span>{purchase.quantity}x</span>
                        </div>
                        {purchase.discount_applied > 0 && (
                          <div className="detail-row discount-row">
                            <span>Discount:</span>
                            <span className="discount-value">{purchase.discount_applied}% OFF</span>
                          </div>
                        )}
                        <div className="detail-row">
                          <span>You Saved:</span>
                          <span className="savings-value">
                            ${((purchase.price_paid / (1 - purchase.discount_applied / 100)) - purchase.price_paid).toFixed(2)}
                          </span>
                        </div>
                      </div>

                      <div className="suscart-badge">
                        SusCart Purchase
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        {/* Savings Summary */}
        <section className="savings-section">
          <h2>💰 Your Savings</h2>
          <div className="savings-grid">
            <div className="saving-card">
              <div className="saving-value">
                ${recommendations.reduce((sum, rec) => 
                  sum + (rec.item.original_price - rec.item.current_price) * (rec.purchased ? 1 : 0), 0
                ).toFixed(2)}
              </div>
              <div className="saving-label">Total Saved</div>
            </div>
            
            <div className="saving-card">
              <div className="saving-value">
                {recommendations.filter(r => r.purchased).length}
              </div>
              <div className="saving-label">Deals Used</div>
            </div>
            
            <div className="saving-card">
              <div className="saving-value">
                {recommendations.filter(r => !r.purchased && !r.viewed).length}
              </div>
              <div className="saving-label">New Deals</div>
            </div>

            <div className="saving-card impact">
              <div className="saving-value">🌍</div>
              <div className="saving-label">
                Helping reduce food waste
              </div>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="how-it-works">
          <h2>How SusCart Helps You Save</h2>
          <div className="steps-grid">
            <div className="step">
              <h3>1. Connect Accounts</h3>
              <p>We analyze your Instacart & grocery purchases via Knot</p>
            </div>
            <div className="step">
              <h3>2. Learn Preferences</h3>
              <p>Discover what fruits you love to buy</p>
            </div>
            <div className="step">
              <h3>3. Monitor Freshness</h3>
              <p>Camera AI detects when fruits are getting ripe</p>
            </div>
            <div className="step">
              <h3>4. Get Deals</h3>
              <p>Receive notifications for discounts on items you actually buy!</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

// Wrap with Error Boundary
const CustomerPortal = () => {
  return (
    <ErrorBoundary>
      <CustomerPortalContent />
    </ErrorBoundary>
  );
};

export default CustomerPortal;

