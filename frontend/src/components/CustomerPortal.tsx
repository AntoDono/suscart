import { useState, useEffect, useRef, Component, useMemo } from 'react';
import type { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AwesomeButton } from 'react-awesome-button';
import 'react-awesome-button/dist/styles.css';
import { IoMdMan, IoMdWoman } from 'react-icons/io';
import { GiStrawberry, GiOrange, GiGrapes, GiCherry, GiBanana, GiWatermelon, GiPineapple, GiLemon, GiPear, GiKiwiFruit, GiPeach } from 'react-icons/gi';
import { MdShoppingCart, MdStore, MdAttachMoney } from 'react-icons/md';
import { FaLink, FaShoppingBag } from 'react-icons/fa';
import { FaAppleWhole } from 'react-icons/fa6';
import FaultyTerminal from './FaultyTerminal';
import GradientText from './GradientText';
import ShoppingAssistant from './ShoppingAssistant';
import './CustomerPortal.css';
import { config } from '../config';
import { mockCustomers, mockRecommendations, mockPurchases, mockKnotTransactions } from '../mockData';
import { createKnotSession, syncKnotTransactions, openKnotAuthModal } from '../knotAuth';

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
          color: '#fe8019',
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
    reasoning?: string;
    ai_reason?: string;
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
  const [showTransactionType, setShowTransactionType] = useState<'edgecart' | 'knot'>('knot');
  const [welcomeStep, setWelcomeStep] = useState(0);
  const [usingRealKnotData, setUsingRealKnotData] = useState(false);
  const [knotConnecting, setKnotConnecting] = useState(false);
  const [knotConnected, setKnotConnected] = useState(false);
  const [showAssistant, setShowAssistant] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  // Welcome animation sequence
  useEffect(() => {
    if (!customerId || !customer) {
      const timer1 = setTimeout(() => setWelcomeStep(1), 3500); // Show login after welcome fades
      return () => {
        clearTimeout(timer1);
      };
    }
  }, [customerId, customer]);

  // Load customer from localStorage on mount
  useEffect(() => {
    const savedCustomerId = localStorage.getItem('edgecart_customer_id');
    const demoUser = localStorage.getItem('edgecart_demo_user');

    if (savedCustomerId && demoUser) {
      // Load demo user from mock data
      const id = parseInt(savedCustomerId);
      const mockCustomer = mockCustomers[demoUser as keyof typeof mockCustomers];

      if (mockCustomer) {
        setCustomerId(id);
        setCustomer(mockCustomer);
        setRecommendations(mockRecommendations[demoUser as keyof typeof mockRecommendations] || []);
        setPurchases(mockPurchases[demoUser as keyof typeof mockPurchases] || []);

        // Fetch real Knot data in background
        fetchRealKnotData(demoUser).then(realKnotData => {
          if (realKnotData.length > 0) {
            console.log('Loaded real Knot data on mount!');
            setKnotTransactions(realKnotData);
            setUsingRealKnotData(true);
          } else {
            setKnotTransactions(mockKnotTransactions[demoUser as keyof typeof mockKnotTransactions] || []);
            setUsingRealKnotData(false);
          }
        });

        console.log('Loaded demo user from localStorage:', demoUser);
      }
    } else if (savedCustomerId) {
      // Load real user from backend
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

      // Fetch EdgeCart purchase history
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
    // Skip WebSocket for demo users
    const demoUser = localStorage.getItem('edgecart_demo_user');
    if (demoUser) {
      console.log('Demo user - skipping WebSocket connection');
      setIsConnected(false);
      return;
    }

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

  const createFadeTransition = (onComplete: () => void) => {
    // Create fade to black overlay
    const fadeOverlay = document.createElement('div');
    fadeOverlay.style.position = 'fixed';
    fadeOverlay.style.top = '0';
    fadeOverlay.style.left = '0';
    fadeOverlay.style.width = '100vw';
    fadeOverlay.style.height = '100vh';
    fadeOverlay.style.backgroundColor = '#000000';
    fadeOverlay.style.opacity = '0';
    fadeOverlay.style.transition = 'opacity 1s ease-in-out';
    fadeOverlay.style.zIndex = '9999';
    fadeOverlay.style.pointerEvents = 'none';

    document.body.appendChild(fadeOverlay);

    // Trigger fade
    setTimeout(() => {
      fadeOverlay.style.opacity = '1';
    }, 10);

    // Execute callback and fade out
    setTimeout(() => {
      onComplete();
      setTimeout(() => {
        fadeOverlay.style.opacity = '0';
        setTimeout(() => {
          if (document.body.contains(fadeOverlay)) {
            document.body.removeChild(fadeOverlay);
          }
        }, 1000);
      }, 100);
    }, 1000);
  };

  const fetchRealKnotData = async (userId: string) => {
    console.log('Fetching real Knot data for user:', userId);

    try {
      // Fetch from Instacart (merchant_id: 40)
      const response = await fetch('https://knot.tunnel.tel/transactions/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          merchant_id: 40,
          external_user_id: userId,
          limit: 10
        })
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Real Knot data received:', data);

        // Transform Knot transactions to our format
        const knotTxs = data.transactions?.map((tx: any) => ({
          id: tx.id || tx.externalId,
          external_id: tx.externalId,
          datetime: tx.dateTime,
          url: tx.url,
          order_status: tx.orderStatus,
          price: {
            sub_total: tx.price?.subTotal || '0.00',
            total: tx.price?.total || '0.00',
            currency: tx.price?.currency || 'USD'
          },
          products: tx.products?.map((p: any) => ({
            external_id: p.externalId,
            name: p.name,
            quantity: p.quantity,
            price: {
              sub_total: p.price?.subTotal || '0.00',
              total: p.price?.total || '0.00',
              unit_price: p.price?.unitPrice || '0.00'
            }
          })) || []
        })) || [];

        return knotTxs;
      } else {
        console.error('Failed to fetch Knot data:', response.status);
        return [];
      }
    } catch (error) {
      console.error('Error fetching real Knot data:', error);
      return [];
    }
  };

  const syncFromKnot = async () => {
    if (!knotUserId.trim()) {
      alert('Please enter a Knot user ID (e.g., "abc" for test)');
      return;
    }

    setSyncLoading(true);

    // Check if this is a demo account
    const isDemoAccount = knotUserId in mockCustomers;

    if (isDemoAccount) {
      // Use mock data for demo accounts, but try to fetch real Knot data too
      console.log('Using demo account with real Knot data:', knotUserId);
      const mockCustomer = mockCustomers[knotUserId as keyof typeof mockCustomers];

      // Fetch real Knot data in parallel
      const realKnotData = await fetchRealKnotData(knotUserId);

      setTimeout(() => {
        createFadeTransition(() => {
          // Save customer ID and demo flag
          setCustomerId(mockCustomer.id);
          localStorage.setItem('edgecart_customer_id', mockCustomer.id.toString());
          localStorage.setItem('edgecart_demo_user', knotUserId);

          // Load mock customer data
          setCustomer(mockCustomer);
          setRecommendations(mockRecommendations[knotUserId as keyof typeof mockRecommendations] || []);
          setPurchases(mockPurchases[knotUserId as keyof typeof mockPurchases] || []);

          // Use real Knot data if available, otherwise fall back to mock
          if (realKnotData.length > 0) {
            console.log('Using real Knot transaction data!');
            setKnotTransactions(realKnotData);
            setUsingRealKnotData(true);
          } else {
            console.log('Falling back to mock Knot data');
            setKnotTransactions(mockKnotTransactions[knotUserId as keyof typeof mockKnotTransactions] || []);
            setUsingRealKnotData(false);
          }
        });
        setSyncLoading(false);
      }, 500);
      return;
    }

    // Try backend for non-demo accounts
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

        // Create fade transition
        createFadeTransition(() => {
          // Save customer ID
          setCustomerId(newCustomerId);
          localStorage.setItem('edgecart_customer_id', newCustomerId.toString());
          localStorage.removeItem('edgecart_demo_user');

          // Load customer data
          loadCustomerData(newCustomerId);

          // Connect WebSocket
          connectWebSocket(newCustomerId);
        });
      } else {
        const error = await response.json();
        alert(`Error: ${error.error || 'Failed to sync from Knot'}`);
      }
    } catch (error) {
      console.error('Error syncing from Knot:', error);
      alert('Failed to connect to backend. Try using demo accounts: abc, def, or ghi');
    } finally {
      setSyncLoading(false);
    }
  };

  const connectKnotAccount = async () => {
    if (!customer) return;

    setKnotConnecting(true);

    try {
      // Create Knot session - don't specify merchant, let user choose
      console.log('Creating Knot session for user:', customer.knot_customer_id || customer.email);
      const session = await createKnotSession(
        customer.knot_customer_id || customer.email
        // No merchant_id - user picks in Knot UI
      );

      console.log('Opening Knot SDK...');
      // Open Knot SDK and wait for completion
      const result = await openKnotAuthModal(session.session_token);

      if (result.success && result.merchantId) {
        console.log('✅ Knot account connected! Syncing transactions...');
        setKnotConnected(true);

        // Sync transactions after successful connection using the merchant ID from auth
        const txData = await syncKnotTransactions(
          customer.knot_customer_id || customer.email,
          result.merchantId,
          undefined,
          20
        );

        // Transform Knot API response to our format
        const knotTxs = txData.transactions?.map((tx: any) => ({
          id: tx.id || tx.externalId,
          external_id: tx.externalId || tx.external_id,
          datetime: tx.dateTime || tx.datetime,
          url: tx.url,
          order_status: tx.orderStatus || tx.order_status,
          price: {
            sub_total: tx.price?.subTotal || tx.price?.sub_total || '0.00',
            total: tx.price?.total || '0.00',
            currency: tx.price?.currency || 'USD'
          },
          products: tx.products?.map((p: any) => ({
            external_id: p.externalId || p.external_id,
            name: p.name,
            quantity: p.quantity,
            price: {
              sub_total: p.price?.subTotal || p.price?.sub_total || '0.00',
              total: p.price?.total || '0.00',
              unit_price: p.price?.unitPrice || p.price?.unit_price || '0.00'
            }
          })) || []
        })) || [];

        setKnotTransactions(knotTxs);
        setUsingRealKnotData(true);
        console.log('✅ Loaded', knotTxs.length, 'real Knot transactions!');
      } else {
        console.log('❌ User cancelled Knot authentication');
      }
    } catch (error) {
      console.error('❌ Error connecting Knot account:', error);
      alert('Failed to connect Knot account. Please try again.');
    } finally {
      setKnotConnecting(false);
    }
  };

  const logout = () => {
    setCustomerId(null);
    setCustomer(null);
    setRecommendations([]);
    setNotifications([]);
    setPurchases([]);
    setKnotTransactions([]);
    setKnotConnected(false);
    setUsingRealKnotData(false);
    localStorage.removeItem('edgecart_customer_id');
    localStorage.removeItem('edgecart_demo_user');
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
    return '#fe8019'; // orange
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

  const getFruitIcon = (fruit: string) => {
    const fruitLower = fruit.toLowerCase();
    if (fruitLower.includes('strawberry') || fruitLower.includes('berry')) return <GiStrawberry />;
    if (fruitLower.includes('orange')) return <GiOrange />;
    if (fruitLower.includes('grape')) return <GiGrapes />;
    if (fruitLower.includes('cherry')) return <GiCherry />;
    if (fruitLower.includes('banana')) return <GiBanana />;
    if (fruitLower.includes('watermelon')) return <GiWatermelon />;
    if (fruitLower.includes('pineapple')) return <GiPineapple />;
    if (fruitLower.includes('lemon') || fruitLower.includes('grapefruit')) return <GiLemon />;
    if (fruitLower.includes('pear')) return <GiPear />;
    if (fruitLower.includes('apple')) return <FaAppleWhole />;
    if (fruitLower.includes('kiwi')) return <GiKiwiFruit />;
    if (fruitLower.includes('peach')) return <GiPeach />;
    if (fruitLower.includes('dragon')) return <GiKiwiFruit />;
    return <FaAppleWhole />; // default
  };

  const getFruitColor = (fruit: string) => {
    const fruitLower = fruit.toLowerCase();
    if (fruitLower.includes('strawberry') || fruitLower.includes('cherry')) return '#ff4757';
    if (fruitLower.includes('orange') || fruitLower.includes('grapefruit')) return '#ffa502';
    if (fruitLower.includes('grape')) return '#a55eea';
    if (fruitLower.includes('banana')) return '#ffd700';
    if (fruitLower.includes('watermelon')) return '#ff6b81';
    if (fruitLower.includes('pineapple')) return '#f9ca24';
    if (fruitLower.includes('lemon')) return '#f9ca24';
    if (fruitLower.includes('pear') || fruitLower.includes('apple')) return '#7bed9f';
    if (fruitLower.includes('kiwi')) return '#7bed9f';
    if (fruitLower.includes('peach')) return '#ffbe76';
    if (fruitLower.includes('dragon')) return '#ff6348';
    if (fruitLower.includes('blueberry')) return '#5f27cd';
    if (fruitLower.includes('spinach') || fruitLower.includes('kale')) return '#2ed573';
    return '#7ECA9C'; // default mint
  };

  // Memoize FaultyTerminal props to prevent re-creation on re-renders
  const terminalGridMul = useMemo(() => [1, 1] as [number, number], []);
  const terminalGradientColors = useMemo(() => ['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C'], []);

  // If not logged in, show welcome screen
  if (!customerId || !customer) {
    return (
      <div className="customer-portal welcome-view">
        {/* Fullscreen FaultyTerminal Background */}
        <div className="welcome-terminal-background">
          <FaultyTerminal
            scale={2.5}
            gridMul={terminalGridMul}
            digitSize={1.8}
            timeScale={1.5}
            pause={false}
            scanlineIntensity={0.7}
            glitchAmount={1}
            flickerAmount={1}
            noiseAmp={1}
            chromaticAberration={0}
            dither={0}
            curvature={0.15}
            tint="#2a4a2a"
            mouseReact={false}
            mouseStrength={0}
            pageLoadAnimation={true}
            brightness={0.35}
          />
        </div>

        {/* Welcome Text - fades out after initial display */}
        <AnimatePresence mode="wait">
          {welcomeStep === 0 ? (
            <motion.div
              key="welcome"
              className="welcome-text-container"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{
                initial: { duration: 0.8, ease: "easeOut" },
                exit: { duration: 1.2, ease: "easeIn" }
              }}
            >
              <h1 className="welcome-title">
                <GradientText
                  colors={terminalGradientColors}
                  animationSpeed={4}
                  showBorder={false}
                >
                  WELCOME TO
                </GradientText>
              </h1>

              <img
                src="/edgecart.png"
                alt="edgecart"
                className="welcome-logo-center"
              />
            </motion.div>
          ) : (
            <motion.div
              key="login"
              className="portal-login-wrapper"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
            >
              <div className="portal-login-content">
                <h2 className="portal-login-title">
                  <GradientText
                    colors={terminalGradientColors}
                    animationSpeed={4}
                    showBorder={false}
                  >
                    CUSTOMER PORTAL
                  </GradientText>
                </h2>

                <div className="portal-terminal">
                  <div className="portal-terminal-header">
                    <div className="terminal-buttons">
                      <span className="terminal-button close"></span>
                      <span className="terminal-button minimize"></span>
                      <span className="terminal-button maximize"></span>
                    </div>
                    <div className="terminal-title">customer@edgecart</div>
                  </div>
                  <div className="portal-terminal-body">
                    <div className="portal-terminal-content">
                      <p className="terminal-prompt">$ connect knot account</p>
                      <p className="terminal-info">sync your purchase history to get personalized deals</p>

                      <div className="terminal-input-group">
                        <span className="terminal-prefix">{'>'}</span>
                        <input
                          type="text"
                          value={knotUserId}
                          onChange={(e) => setKnotUserId(e.target.value)}
                          placeholder="enter knot user id"
                          className="terminal-input"
                          disabled={syncLoading}
                          onKeyDown={(e) => e.key === 'Enter' && syncFromKnot()}
                        />
                      </div>

                      <div className="profile-cards-section">
                        <p className="terminal-hint">or try a demo profile:</p>
                        <div className="profile-cards">
                          <button
                            onClick={() => setKnotUserId('abc')}
                            className="profile-card"
                          >
                            <div className="profile-header">
                              <IoMdWoman className="profile-icon" />
                              <div className="profile-info">
                                <div className="profile-name">sarah chen</div>
                                <div className="profile-id">@abc</div>
                              </div>
                            </div>
                            <div className="profile-bio">health-conscious mom who loves organic berries</div>
                            <div className="profile-likes">
                              <GiStrawberry className="like-icon" />
                              <span>strawberries, blueberries, spinach</span>
                            </div>
                          </button>

                          <button
                            onClick={() => setKnotUserId('def')}
                            className="profile-card"
                          >
                            <div className="profile-header">
                              <IoMdMan className="profile-icon" />
                              <div className="profile-info">
                                <div className="profile-name">marcus lee</div>
                                <div className="profile-id">@def</div>
                              </div>
                            </div>
                            <div className="profile-bio">fitness enthusiast buying citrus for smoothies</div>
                            <div className="profile-likes">
                              <GiOrange className="like-icon" />
                              <span>oranges, grapefruits, kale</span>
                            </div>
                          </button>

                          <button
                            onClick={() => setKnotUserId('ghi')}
                            className="profile-card"
                          >
                            <div className="profile-header">
                              <IoMdWoman className="profile-icon" />
                              <div className="profile-info">
                                <div className="profile-name">emily rodriguez</div>
                                <div className="profile-id">@ghi</div>
                              </div>
                            </div>
                            <div className="profile-bio">foodie exploring exotic fruits and vegetables</div>
                            <div className="profile-likes">
                              <GiGrapes className="like-icon" />
                              <span>grapes, dragon fruit, kiwi</span>
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="portal-login-button-wrapper">
                  <AwesomeButton
                    type="primary"
                    onPress={syncFromKnot}
                    disabled={syncLoading}
                  >
                    <GradientText
                      colors={terminalGradientColors}
                      animationSpeed={4}
                      showBorder={false}
                    >
                      {syncLoading ? 'SYNCING...' : 'CONNECT'}
                    </GradientText>
                  </AwesomeButton>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <div className="customer-portal">
      {/* FaultyTerminal Background */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
        pointerEvents: 'none'
      }}>
        <FaultyTerminal
          scale={2.3}
          gridMul={[1, 1]}
          digitSize={1.8}
          timeScale={1.8}
          pause={false}
          scanlineIntensity={0.7}
          glitchAmount={1}
          flickerAmount={1}
          noiseAmp={1}
          chromaticAberration={0}
          dither={0}
          curvature={0.2}
          tint="#7ECA9C"
          mouseReact={false}
          mouseStrength={0}
          pageLoadAnimation={false}
          brightness={0.2}
        />
        {/* Fade to black gradient */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: '100%',
          height: '50%',
          background: 'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.5) 50%, #000000 100%)',
          pointerEvents: 'none'
        }} />
      </div>

      {/* Header */}
      <header className="portal-header">
        <div className="header-content">
          <img src="/edgecart.png" alt="edgecart" style={{ height: '40px', filter: 'brightness(0) invert(1)' }} />
          <div className="header-actions">
            <div className="connection-status">
              <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
              <span>{isConnected ? 'Live' : 'Offline'}</span>
            </div>
            <button onClick={logout} className="logout-btn">Logout</button>
          </div>
        </div>
      </header>

      {/* Shopping Assistant - Floating */}
      <ShoppingAssistant
        customer={customer}
        recommendations={recommendations}
        isOpen={showAssistant}
        onToggle={() => setShowAssistant(!showAssistant)}
      />

      {/* Main Content */}
      <div className="portal-content">
        {/* Customer Info Section - Terminal Style */}
        <section className="customer-info-section">
          <div className="profile-terminal">
            <div className="portal-terminal-header">
              <div className="terminal-buttons">
                <span className="terminal-button close"></span>
                <span className="terminal-button minimize"></span>
                <span className="terminal-button maximize"></span>
              </div>
              <div className="terminal-title">customer@edgecart:~/{customer.knot_customer_id || 'profile'}</div>
            </div>
            <div className="portal-terminal-body" style={{ padding: '1.5rem' }}>
              <div className="terminal-section">
                <div className="terminal-prompt-line">
                  <span className="terminal-prefix">$</span>
                  <span className="terminal-command">whoami</span>
                </div>

                <div className="profile-header-section">
                  {/* User Avatar */}
                  <div className="user-avatar">
                    <GiOrange className="avatar-icon" />
                  </div>

                  {/* User Info */}
                  <div className="profile-info-grid">
                    <div className="profile-info-item">
                      <div className="info-content">
                        <span className="info-label">name</span>
                        <span className="info-value">{customer.name}</span>
                      </div>
                    </div>
                    <div className="profile-info-item">
                      <div className="info-content">
                        <span className="info-label">email</span>
                        <span className="info-value">{customer.email}</span>
                      </div>
                    </div>
                    {customer.knot_customer_id && (
                      <div className="profile-info-item">
                        <FaLink className="info-icon-small" style={{ color: '#7ECA9C' }} />
                        <div className="info-content">
                          <span className="info-label">knot id</span>
                          <span className="info-value knot-id-value">{customer.knot_customer_id}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Connect Knot Button */}
                <div style={{ marginTop: '1rem' }}>
                  <button
                    onClick={connectKnotAccount}
                    disabled={knotConnecting || knotConnected}
                    className="connect-knot-btn terminal-button-style"
                  >
                    {knotConnecting ? '> connecting...' : knotConnected ? '✓ account connected' : '> connect grocery account'}
                  </button>
                </div>
              </div>

              {/* Shopping Preferences */}
              {customer.preferences && (
                <>
                  <div className="terminal-divider">─────────────────────────────────────</div>

                  <div className="terminal-section">
                    <div className="terminal-prompt-line">
                      <span className="terminal-prefix">$</span>
                      <span className="terminal-command">cat shopping_preferences</span>
                    </div>

                    {customer.preferences.favorite_fruits && customer.preferences.favorite_fruits.length > 0 && (
                      <div className="preference-section">
                        <div className="section-label">favorite fruits</div>
                        <div className="fruit-tags-terminal">
                          {customer.preferences.favorite_fruits.map((fruit, idx) => (
                            <div
                              key={idx}
                              className="fruit-tag-terminal"
                              style={{
                                borderColor: getFruitColor(fruit),
                                color: getFruitColor(fruit)
                              }}
                            >
                              <span className="fruit-icon" style={{ color: getFruitColor(fruit) }}>
                                {getFruitIcon(fruit)}
                              </span>
                              <span className="fruit-name">{fruit}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="stats-grid-terminal">
                      {customer.preferences.average_spend && (
                        <div className="stat-terminal">
                          <MdAttachMoney className="stat-icon" style={{ color: '#7ECA9C' }} />
                          <div className="stat-content">
                            <span className="stat-label">avg spend</span>
                            <span className="stat-value-terminal">${customer.preferences.average_spend.toFixed(2)}</span>
                          </div>
                        </div>
                      )}

                      {customer.preferences.total_transactions && (
                        <div className="stat-terminal">
                          <MdShoppingCart className="stat-icon" style={{ color: '#AAF0D1' }} />
                          <div className="stat-content">
                            <span className="stat-label">total purchases</span>
                            <span className="stat-value-terminal">{customer.preferences.total_transactions}</span>
                          </div>
                        </div>
                      )}

                      {customer.preferences.merchants_used && customer.preferences.merchants_used.length > 0 && (
                        <div className="stat-terminal full-width-terminal">
                          <MdStore className="stat-icon" style={{ color: '#CCFFBD' }} />
                          <div className="stat-content">
                            <span className="stat-label">merchants</span>
                            <span className="stat-value-terminal merchant-list">
                              {customer.preferences.merchants_used.join(', ')}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </section>

        {/* Recommendations Section */}
        <section className="recommendations-section">
          <div className="dark-container orange-container">
            <div className="dark-container-header">
              <h2 className="dark-container-title">
                <GradientText
                  colors={['#ffa502', '#ff6348', '#ff4757', '#ff6348', '#ffa502']}
                  animationSpeed={4}
                  showBorder={false}
                >
                  personalized deals
                </GradientText>
              </h2>
              <span className="deal-count orange-badge">{recommendations.length} deals</span>
            </div>

            {recommendations.length === 0 ? (
              <div className="empty-state-dark">
                <p>no deals right now. we'll notify you when items you like go on sale!</p>
                <p className="hint">connected via knot - we know what you love to buy</p>
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
                    <span className="current-price">
                      <span className="dollar-sign">$</span>{((rec.item as any).current_price || 0).toFixed(2)}
                    </span>
                    <span className="original-price">
                      <span className="dollar-sign">$</span>{((rec.item as any).original_price || 0).toFixed(2)}
                    </span>
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
                    {rec.reason?.reasoning && (
                      <p className="reasoning-text">{rec.reason.reasoning}</p>
                    )}
                    {!rec.reason?.reasoning && rec.reason?.match_type === 'favorite_fruit' && (
                      <p>Recommended because you love {rec.reason.fruit}!</p>
                    )}
                    {rec.reason?.match_type === 'ai_recommendation' && (
                      <p className="from-knot">AI-powered recommendation</p>
                    )}
                    {rec.reason?.match_type === 'favorite_fruit' && (
                      <p className="from-knot">Based on your purchase history</p>
                    )}
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
          </div>
        </section>

        {/* Live Notifications */}
        {notifications.length > 0 && (
          <section className="notifications-section">
            <div className="dark-container">
              <div className="dark-container-header">
                <h2 className="dark-container-title">live updates</h2>
                <span className="deal-count">{notifications.length} updates</span>
              </div>
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
            </div>
          </section>
        )}

        {/* Transaction History */}
        <section className="transactions-section">
          <div className="profile-terminal">
            <div className="portal-terminal-header">
              <div className="terminal-buttons">
                <span className="terminal-button close"></span>
                <span className="terminal-button minimize"></span>
                <span className="terminal-button maximize"></span>
              </div>
              <div className="terminal-title">transactions@edgecart:~/history</div>
            </div>
            <div className="portal-terminal-body" style={{ padding: '1.5rem' }}>
              <div className="terminal-section">
                <div className="terminal-prompt-line">
                  <span className="terminal-prefix">$</span>
                  <span className="terminal-command">ls -la transactions/</span>
                </div>

                {/* Transaction Toggle */}
                <div className="transaction-toggle-terminal">
                  <button
                    className={`toggle-btn-terminal ${showTransactionType === 'knot' ? 'active' : ''}`}
                    onClick={() => setShowTransactionType('knot')}
                  >
                    <MdStore style={{ fontSize: '1.2rem' }} />
                    <span>knot purchases ({knotTransactions.length})</span>
                    {usingRealKnotData && <span className="real-data-badge-terminal">live</span>}
                  </button>
                  <button
                    className={`toggle-btn-terminal ${showTransactionType === 'edgecart' ? 'active' : ''}`}
                    onClick={() => setShowTransactionType('edgecart')}
                  >
                    <FaShoppingBag style={{ fontSize: '1rem' }} />
                    <span>edgecart purchases ({purchases.length})</span>
                  </button>
                </div>
              </div>

              {/* Knot Transactions */}
              {showTransactionType === 'knot' && (
                <div className="transactions-list-terminal">
                  {knotTransactions.length === 0 ? (
                    <div className="empty-state-terminal">
                      <p>no knot transaction history available</p>
                      <p className="hint">connect your knot account to see purchase history</p>
                    </div>
                  ) : (
                    <div className="scrollable-transactions-terminal">
                  {knotTransactions.map((transaction, idx) => (
                    <div key={transaction.id || `knot-tx-${idx}`} className="transaction-card knot-transaction">
                      <div className="transaction-header">
                        <div className="transaction-info">
                          <span className="transaction-id">Order #{transaction.external_id?.substring(0, 8) || transaction.id?.substring(0, 8) || `TX-${idx + 1}`}</span>
                          <span className="transaction-date">
                            {transaction.datetime ? new Date(transaction.datetime).toLocaleDateString() : 'N/A'}
                          </span>
                        </div>
                        <div className="transaction-total">
                          ${transaction.price?.total ? parseFloat(transaction.price.total).toFixed(2) : '0.00'}
                        </div>
                      </div>

                      <div className="transaction-status">
                        <span className={`status-badge ${transaction.order_status?.toLowerCase() || 'unknown'}`}>
                          {transaction.order_status || 'Unknown'}
                        </span>
                        {transaction.url && (
                          <a href={transaction.url} target="_blank" rel="noopener noreferrer" className="order-link">
                            View Order →
                          </a>
                        )}
                      </div>

                      <div className="transaction-products">
                        {transaction.products && transaction.products.length > 0 ? (
                          <>
                            {transaction.products.slice(0, 3).map((product, pIdx) => (
                              <div key={pIdx} className="product-item">
                                <span className="product-name">{product.name || 'Unknown Product'}</span>
                                <span className="product-details">
                                  {product.quantity || 0}x ${product.price?.unit_price ? parseFloat(product.price.unit_price).toFixed(2) : '0.00'}
                                </span>
                              </div>
                            ))}
                            {transaction.products.length > 3 && (
                              <div className="more-products">
                                +{transaction.products.length - 3} more items
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="product-item">No products listed</div>
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

              {/* EdgeCart Purchases */}
              {showTransactionType === 'edgecart' && (
                <div className="transactions-list-terminal">
                  {purchases.length === 0 ? (
                    <div className="empty-state-terminal">
                      <p>no edgecart purchases yet</p>
                      <p className="hint">your purchases from our store will appear here</p>
                    </div>
                  ) : (
                    <div className="scrollable-transactions-terminal">
                  {purchases.map((purchase) => (
                    <div key={purchase.id} className="transaction-card edgecart-transaction">
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

                      <div className="edgecart-badge">
                        EdgeCart Purchase
                      </div>
                    </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

        {/* Savings Summary */}
        <section className="savings-section">
          <div className="dark-container">
            <div className="dark-container-header">
              <h2 className="dark-container-title">
                <GradientText
                  colors={['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C']}
                  animationSpeed={4}
                  showBorder={false}
                >
                  your savings
                </GradientText>
              </h2>
            </div>
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
          </div>
        </section>

        {/* How It Works */}
        <section className="how-it-works">
          <div className="dark-container orange-container">
            <div className="dark-container-header">
              <h2 className="dark-container-title">
                <GradientText
                  colors={['#ffa502', '#ff6348', '#ff4757', '#ff6348', '#ffa502']}
                  animationSpeed={4}
                  showBorder={false}
                >
                  how it works
                </GradientText>
              </h2>
            </div>
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

