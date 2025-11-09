import { useState, useEffect, useRef } from 'react';
import './AdminDashboard.css';
import { config } from '../config';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { format, parseISO, getMinutes, getHours } from 'date-fns';

interface FreshnessData {
  id: number;
  inventory_id: number;
  freshness_score: number;
  predicted_expiry_date?: string | null;
  confidence_level?: number;
  discount_percentage: number;
  status: string;
  last_checked?: string;
  image_url?: string | null;
  notes?: string | null;
}

interface InventoryItem {
  id: number;
  store_id: number;
  fruit_type: string;
  variety?: string;
  quantity: number;
  batch_number?: string;
  location_in_store?: string;
  arrival_date?: string;
  original_price: number;
  current_price: number;
  discount_percentage?: number;
  thumbnail_path?: string | null;
  freshness?: FreshnessData;
  actual_freshness_scores?: number[];
  actual_freshness_avg?: number | null;
  created_at: string;
  updated_at: string;
}

interface QuantityChange {
  inventory_id: number;
  fruit_type: string;
  old_quantity: number;
  new_quantity: number;
  delta: number;
  change_type: 'increase' | 'decrease';
  freshness_score?: number | null;
  timestamp: string;
}

interface DetectionImage {
  path: string;
  filename: string;
  timestamp: string;
  metadata?: {
    confidence?: number;
    freshness_score?: number;
    bbox?: number[];
    blemishes?: {
      bboxes?: Array<{
        box_2d: [number, number, number, number];
        label: string;
      }>;
      labels?: string[];
      count?: number;
      error?: string;
    };
  };
}

const InventoryView = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [quantityChanges, setQuantityChanges] = useState<QuantityChange[]>([]);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [defaultStoreId, setDefaultStoreId] = useState<number | null>(null);
  const [selectedItemImages, setSelectedItemImages] = useState<DetectionImage[]>([]);
  const [selectedItemCategory, setSelectedItemCategory] = useState<string | null>(null);
  const [showImageModal, setShowImageModal] = useState(false);
  const [loadingImages, setLoadingImages] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [analyzingProgress, setAnalyzingProgress] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzingMessage, setAnalyzingMessage] = useState('');
  const [expandedImage, setExpandedImage] = useState<DetectionImage | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [savedScores, setSavedScores] = useState<Set<string>>(new Set()); // Track saved scores by image path
  const [discountedItems, setDiscountedItems] = useState<InventoryItem[]>([]);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historyData, setHistoryData] = useState<QuantityChange[]>([]);
  const [historyStatistics, setHistoryStatistics] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

  // Calculate status from freshness score (0-1.0 scale)
  const getStatusFromFreshness = (freshnessScore: number): string => {
    if (freshnessScore >= 0.6) {
      return 'fresh';
    } else if (freshnessScore >= 0.2) {
      return 'ripe';
    } else {
      return 'clearance';
    }
  };

  // Get status label for display
  const getStatusLabel = (status: string): string => {
    if (status === 'clearance') {
      return 'CLEARANCE';
    }
    return status.toUpperCase();
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    if (status === 'fresh') return '#7ECA9C';
    if (status === 'ripe') return '#FFA500';
    if (status === 'clearance') return '#FFA500';
    return '#FFA500'; // default
  };

  // Calculate actual freshness score based purely on blemish detection
  const calculateBlemishBasedFreshnessScore = (
    blemishes: Array<{ box_2d: [number, number, number, number] }> | undefined,
    imageWidth: number,
    imageHeight: number
  ): number => {
    if (!blemishes || blemishes.length === 0) {
      return 1.0; // 100% fresh if no blemishes
    }

    // Calculate total blemish area (bboxes are in normalized 0-1000 coordinates)
    let totalBlemishArea = 0;
    blemishes.forEach((bbox) => {
      if (bbox.box_2d && bbox.box_2d.length === 4) {
        const [ymin, xmin, ymax, xmax] = bbox.box_2d;
        // Convert normalized coordinates to pixel area
        const width = ((xmax - xmin) / 1000) * imageWidth;
        const height = ((ymax - ymin) / 1000) * imageHeight;
        totalBlemishArea += width * height;
      }
    });

    const imageArea = imageWidth * imageHeight;
    const blemishCoveragePercent = (totalBlemishArea / imageArea) * 100;
    const blemishCount = blemishes.length;

    // Start from 100% and apply penalties:
    // - Each blemish reduces score by 3%
    // - Coverage percentage reduces score proportionally (up to 40% penalty for 100% coverage)
    const countPenalty = Math.min(blemishCount * 0.03, 0.30); // Max 30% penalty for count
    const coveragePenalty = Math.min(blemishCoveragePercent * 0.004, 0.40); // Max 40% penalty for coverage
    
    const totalPenalty = countPenalty + coveragePenalty;
    const freshnessScore = Math.max(0, 1.0 - totalPenalty);

    return freshnessScore;
  };

  // Impact statistics state
  const [foodWasteSaved, setFoodWasteSaved] = useState<number | null>(null);
  const [co2Saved, setCo2Saved] = useState<number | null>(null);
  const [additionalRevenue, setAdditionalRevenue] = useState<number | null>(null);
  const [statsLoading, setStatsLoading] = useState<boolean>(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  // Fetch impact statistics
  useEffect(() => {
    const fetchImpactStats = async () => {
      setStatsLoading(true);
      setStatsError(null);
      try {
        const response = await fetch(`${config.apiUrl}/api/analytics/v1/metrics/aggregate`);
        if (response.ok) {
          const data = await response.json();
          setFoodWasteSaved(data.waste_saved_kg || data.units_saved || 0);
          setCo2Saved(data.co2e_saved || data.co2_saved_kg || 0);
          setAdditionalRevenue(data.revenue_generated || data.additional_revenue_generated || 0);
        } else {
          // Silently fail - don't set error, just don't show the section
          setFoodWasteSaved(null);
          setCo2Saved(null);
          setAdditionalRevenue(null);
        }
      } catch (err) {
        // Silently fail - don't show error, just don't display the section
        console.error('Error fetching impact metrics:', err);
        setFoodWasteSaved(null);
        setCo2Saved(null);
        setAdditionalRevenue(null);
      } finally {
        setStatsLoading(false);
      }
    };

    fetchImpactStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchImpactStats, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Load initial inventory
    fetchInventory();
    fetchDefaultStore();

    // Connect to admin WebSocket
    const websocket = new WebSocket(`${config.wsUrl}/ws/admin`);
    wsRef.current = websocket;

    websocket.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
      // Request current stats to get initial data
      websocket.send(JSON.stringify({ action: 'get_stats' }));
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    websocket.onclose = () => {
      setIsConnected(false);
    };

    websocket.onerror = () => {
      setConnectionError('WebSocket connection error');
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  // Save actual freshness score when calculated
  useEffect(() => {
    if (expandedImage && imageDimensions && expandedImage.metadata?.blemishes?.bboxes && 
        expandedImage.metadata.blemishes.bboxes.length > 0 && selectedItemCategory) {
      const imageKey = expandedImage.path;
      
      // Only save if we haven't saved this score yet
      if (!savedScores.has(imageKey)) {
        const actualFreshnessScore = calculateBlemishBasedFreshnessScore(
          expandedImage.metadata.blemishes.bboxes,
          imageDimensions.width,
          imageDimensions.height
        );
        
        saveActualFreshnessScore(actualFreshnessScore, selectedItemCategory);
        setSavedScores(prev => new Set(prev).add(imageKey));
      }
    }
  }, [expandedImage, imageDimensions, selectedItemCategory]);

  const fetchInventory = async () => {
    try {
      const response = await fetch(`${config.apiUrl}/api/inventory`);
      if (response.ok) {
        const data = await response.json();
        setInventory(data.items || []);
        
        // Filter discounted items based on actual freshness ONLY (require actual freshness)
        const discounted = (data.items || []).filter((item: InventoryItem) => {
          if (!item.quantity || item.quantity <= 0) return false;
          
          // Only include items with actual freshness scores
          if (item.actual_freshness_avg === null || item.actual_freshness_avg === undefined) {
            return false;
          }
          
          const freshnessScore = item.actual_freshness_avg;
          
          // Calculate discount based on freshness (lower freshness = higher discount)
          const maxDiscount = 75.0;
          const power = 1.5;
          const discount = maxDiscount * (1 - (freshnessScore ** power));
          
          return discount > 0;
        });
        
        // Sort by actual freshness (lowest first = highest discount)
        discounted.sort((a: InventoryItem, b: InventoryItem) => {
          const aScore = a.actual_freshness_avg || 1.0;
          const bScore = b.actual_freshness_avg || 1.0;
          return aScore - bScore; // Lower freshness = higher priority
        });
        setDiscountedItems(discounted);
      }
    } catch (e) {
      console.error('Failed to fetch inventory:', e);
    }
  };

  const fetchDefaultStore = async () => {
    try {
      const response = await fetch(`${config.apiUrl}/api/stores`);
      if (response.ok) {
        const data = await response.json();
        if (data.stores && data.stores.length > 0) {
          setDefaultStoreId(data.stores[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch stores:', e);
    }
  };

  const fetchCategoryImages = async (category: string) => {
    setLoadingImages(true);
    setLoadingProgress(0);
    setSelectedItemCategory(category);
    setShowImageModal(true); // Open modal immediately to show loading state
    
    // Close any existing EventSource connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    try {
      // Use Server-Sent Events for progress updates
      // Note: EventSource doesn't support custom headers, so CORS must be handled server-side
      const eventSource = new EventSource(`${config.apiUrl}/api/detection-images/${category}/stream`);
      eventSourceRef.current = eventSource;
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'progress') {
            setLoadingProgress(data.progress);
          } else if (data.type === 'complete') {
            setLoadingProgress(100);
            setSelectedItemImages(data.images || []);
            setTimeout(() => {
              setLoadingImages(false);
              setLoadingProgress(0);
              eventSource.close();
              eventSourceRef.current = null;
            }, 300); // Small delay to show 100%
          } else if (data.type === 'error') {
            console.error('Error loading images:', data.error);
            setSelectedItemImages([]);
            setLoadingImages(false);
            setLoadingProgress(0);
            eventSource.close();
            eventSourceRef.current = null;
          }
        } catch (e) {
          console.error('Failed to parse SSE message:', e);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        eventSource.close();
        eventSourceRef.current = null;
        // Fallback to regular API call
        fetch(`${config.apiUrl}/api/detection-images/${category}`)
          .then(response => response.json())
          .then(data => {
            setSelectedItemImages(data.images || []);
            setLoadingImages(false);
            setLoadingProgress(0);
          })
          .catch(e => {
            console.error('Failed to fetch category images:', e);
            setSelectedItemImages([]);
            setLoadingImages(false);
            setLoadingProgress(0);
          });
      };
      
    } catch (e) {
      console.error('Failed to setup SSE connection:', e);
      // Fallback to regular API call
    try {
      const response = await fetch(`${config.apiUrl}/api/detection-images/${category}`);
      if (response.ok) {
        const data = await response.json();
        setSelectedItemImages(data.images || []);
      } else {
        setSelectedItemImages([]);
      }
      } catch (fetchError) {
        console.error('Failed to fetch category images:', fetchError);
      setSelectedItemImages([]);
    } finally {
      setLoadingImages(false);
        setLoadingProgress(0);
      }
    }
  };

  const handleFruitTypeClick = (fruitType: string) => {
    fetchCategoryImages(fruitType.toLowerCase());
  };

  const handleExpandImage = (image: DetectionImage) => {
    setExpandedImage(image);
    setImageDimensions(null); // Reset dimensions when changing images
  };

  const saveActualFreshnessScore = async (score: number, fruitType: string) => {
    try {
      // Find all inventory items of this fruit type
      const matchingItems = inventory.filter(item => 
        item.fruit_type.toLowerCase() === fruitType.toLowerCase()
      );
      
      if (matchingItems.length === 0) {
        console.warn(`No inventory items found for fruit type: ${fruitType}`);
        return;
      }
      
      // Save score to all matching inventory items
      const savePromises = matchingItems.map(item =>
        fetch(`${config.apiUrl}/api/inventory/${item.id}/actual-freshness`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ score }),
        })
      );
      
      await Promise.all(savePromises);
      console.log(`Saved actual freshness score ${score} to ${matchingItems.length} inventory item(s)`);
      
      // Refresh inventory to get updated scores
      fetchInventory();
    } catch (error) {
      console.error('Error saving actual freshness score:', error);
    }
  };

  const handleAnalyzeAndOptimize = async () => {
    setIsAnalyzing(true);
    setAnalyzingProgress(0);
    setAnalyzingMessage('Starting analysis...');

    const eventSource = new EventSource(`${config.apiUrl}/api/inventory/analyze-optimize`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'start') {
          setAnalyzingMessage(`Analyzing ${data.total} items...`);
        } else if (data.type === 'progress') {
          setAnalyzingProgress(data.progress);
          setAnalyzingMessage(data.message || `Processing ${data.current}/${data.total}...`);
        } else if (data.type === 'item_complete') {
          setAnalyzingMessage(`Completed ${data.item}...`);
          // Refresh inventory to get updated scores
          fetchInventory();
        } else if (data.type === 'complete') {
          setAnalyzingProgress(100);
          setAnalyzingMessage('Analysis complete!');
          setTimeout(() => {
            setIsAnalyzing(false);
            eventSource.close();
            fetchInventory();
          }, 1000);
        } else if (data.type === 'error') {
          console.error('Analysis error:', data.error);
          setAnalyzingMessage(`Error: ${data.error}`);
          setTimeout(() => {
            setIsAnalyzing(false);
            eventSource.close();
          }, 3000);
        }
      } catch (e) {
        console.error('Error parsing SSE data:', e);
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      setIsAnalyzing(false);
      eventSource.close();
    };
  };

  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      // Fetch both history and statistics
      const [historyResponse, statsResponse] = await Promise.all([
        fetch(`${config.apiUrl}/api/inventory/quantity-history?limit=500`),
        fetch(`${config.apiUrl}/api/inventory/quantity-statistics`)
      ]);

      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        setHistoryData(historyData.changes || []);
      }

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        console.log('Statistics data:', statsData); // Debug log
        console.log('Statistics array:', statsData.statistics); // Debug log
        console.log('Statistics length:', statsData.statistics?.length); // Debug log
        setHistoryStatistics(statsData.statistics || []);
      } else {
        const errorText = await statsResponse.text();
        console.error('Failed to fetch statistics:', statsResponse.status, errorText);
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleOpenHistory = () => {
    setShowHistoryModal(true);
    fetchHistory();
  };

  // Helper functions to process data for charts
  const processTimeSeriesData = () => {
    if (!historyData.length) return [];
    
    // Group by 10-minute intervals
    const intervalData: { [key: string]: { time: string; increases: number; decreases: number; net: number } } = {};
    
    historyData.forEach(change => {
      const date = parseISO(change.timestamp);
      const minutes = getMinutes(date);
      const hours = getHours(date);
      // Round down to nearest 10-minute interval
      const roundedMinutes = Math.floor(minutes / 10) * 10;
      const timeKey = `${format(date, 'yyyy-MM-dd')}T${String(hours).padStart(2, '0')}:${String(roundedMinutes).padStart(2, '0')}`;
      // Format for display: MM/dd HH:mm (with padded minutes)
      const displayTime = `${format(date, 'MM/dd')} ${String(hours).padStart(2, '0')}:${String(roundedMinutes).padStart(2, '0')}`;
      
      if (!intervalData[timeKey]) {
        intervalData[timeKey] = { time: displayTime, increases: 0, decreases: 0, net: 0 };
      }
      
      if (change.change_type === 'increase') {
        intervalData[timeKey].increases += change.delta;
        intervalData[timeKey].net += change.delta;
      } else {
        intervalData[timeKey].decreases += Math.abs(change.delta);
        intervalData[timeKey].net -= Math.abs(change.delta);
      }
    });
    
    return Object.values(intervalData).sort((a, b) => {
      // Sort by time string (which is already formatted as date/time)
      return a.time.localeCompare(b.time);
    });
  };

  const processFruitTypeChartData = () => {
    if (!historyStatistics || historyStatistics.length === 0) return [];
    return historyStatistics.map(stat => ({
      name: stat.fruit_type.charAt(0).toUpperCase() + stat.fruit_type.slice(1),
      increases: stat.total_increases,
      decreases: stat.total_decreases,
      total: stat.total_changes
    }));
  };

  const handleCreate = async (itemData: Partial<InventoryItem>) => {
    if (!defaultStoreId) {
      alert('No store available. Please create a store first.');
      return;
    }
    try {
      const response = await fetch(`${config.apiUrl}/api/inventory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          store_id: defaultStoreId,
          fruit_type: itemData.fruit_type,
          variety: itemData.variety || '',
          quantity: itemData.quantity || 0,
          batch_number: itemData.batch_number || '',
          location_in_store: itemData.location_in_store || '',
          original_price: itemData.original_price || 0,
          current_price: itemData.current_price || itemData.original_price || 0,
        }),
      });
      if (response.ok) {
        setShowCreateModal(false);
        fetchInventory();
      } else {
        const error = await response.json();
        alert(`Failed to create item: ${error.error || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Failed to create item:', e);
      alert('Failed to create item');
    }
  };

  const handleUpdate = async (itemId: number, itemData: Partial<InventoryItem>) => {
    try {
      const response = await fetch(`${config.apiUrl}/api/inventory/${itemId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(itemData),
      });
      if (response.ok) {
        setEditingItem(null);
        fetchInventory();
      } else {
        const error = await response.json();
        alert(`Failed to update item: ${error.error || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Failed to update item:', e);
      alert('Failed to update item');
    }
  };

  const handleDelete = async (itemId: number) => {
    try {
      const response = await fetch(`${config.apiUrl}/api/inventory/${itemId}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        fetchInventory();
      } else {
        const error = await response.json();
        alert(`Failed to delete item: ${error.error || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Failed to delete item:', e);
      alert('Failed to delete item');
    }
  };

  const handleWebSocketMessage = (data: any) => {
    if (data.type === 'quantity_changed') {
      // Add to quantity changes log
      const change: QuantityChange = {
        inventory_id: data.data.inventory_id,
        fruit_type: data.data.fruit_type,
        old_quantity: data.data.old_quantity,
        new_quantity: data.data.new_quantity,
        delta: data.data.delta,
        change_type: data.data.change_type,
        freshness_score: data.data.freshness_score,
        timestamp: data.timestamp || new Date().toISOString()
      };
      
      setQuantityChanges(prev => [change, ...prev].slice(0, 100)); // Keep last 100 changes
      
      // Update inventory item if it exists, otherwise refresh to get new items
      setInventory(prev => {
        const itemExists = prev.some(item => item.id === change.inventory_id);
        if (itemExists) {
          return prev.map(item => 
            item.id === change.inventory_id 
              ? { ...item, quantity: change.new_quantity }
              : item
          );
        } else {
          // Item doesn't exist yet, refresh to get it
          fetchInventory();
          return prev;
        }
      });
    } else if (data.type === 'freshness_updated') {
      // Update freshness score in real-time
      const inventoryId = data.data.inventory_id;
      const freshness = data.data.freshness;
      const item = data.data.item;
      
      setInventory(prev => {
        const updated = prev.map(invItem => {
          if (invItem.id === inventoryId) {
            // Update freshness and also update price/discount if item data is provided
            return {
              ...invItem,
              freshness: freshness,
              // Update price and discount if provided in item data
              ...(item && {
                current_price: item.current_price,
                discount_percentage: item.discount_percentage
              })
            };
          }
          return invItem;
        });
        
        // Update discounted items list - only include items with actual freshness
        const discounted = updated.filter((item: InventoryItem) => {
          if (!item.quantity || item.quantity <= 0) return false;
          
          // Only include items with actual freshness scores
          if (item.actual_freshness_avg === null || item.actual_freshness_avg === undefined) {
            return false;
          }
          
          const freshnessScore = item.actual_freshness_avg;
          
          // Calculate discount based on freshness
          const maxDiscount = 75.0;
          const power = 1.5;
          const discount = maxDiscount * (1 - (freshnessScore ** power));
          
          return discount > 0;
        });
        
        // Sort by actual freshness (lowest first = highest discount)
        discounted.sort((a: InventoryItem, b: InventoryItem) => {
          const aScore = a.actual_freshness_avg || 1.0;
          const bScore = b.actual_freshness_avg || 1.0;
          return aScore - bScore;
        });
        setDiscountedItems(discounted);
        
        return updated;
      });
      
      console.log(`Freshness updated for item ${inventoryId}: ${freshness.freshness_score}%`);
    } else if (data.type === 'inventory_added') {
      // Refresh inventory to get new item
      fetchInventory();
    } else if (data.type === 'inventory_updated') {
      // Update inventory item
      if (data.data.id) {
        setInventory(prev => {
          const updated = prev.map(item => 
            item.id === data.data.id 
              ? { ...item, ...data.data }
              : item
          );
          
          // Recalculate discounted items - only include items with actual freshness
          const discounted = updated.filter((item: InventoryItem) => {
            if (!item.quantity || item.quantity <= 0) return false;
            
            // Only include items with actual freshness scores
            if (item.actual_freshness_avg === null || item.actual_freshness_avg === undefined) {
              return false;
            }
            
            const freshnessScore = item.actual_freshness_avg;
            
            const maxDiscount = 75.0;
            const power = 1.5;
            const discount = maxDiscount * (1 - (freshnessScore ** power));
            
            return discount > 0;
          });
          
          discounted.sort((a: InventoryItem, b: InventoryItem) => {
            const aScore = a.actual_freshness_avg || 1.0;
            const bScore = b.actual_freshness_avg || 1.0;
            return aScore - bScore;
          });
          setDiscountedItems(discounted);
          
          return updated;
        });
      }
    } else if (data.type === 'inventory_deleted') {
      // Remove item from inventory
      setInventory(prev => prev.filter(item => item.id !== data.data.id));
    }
  };

  const goBack = () => {
    window.location.hash = '#admin';
  };

  return (
    <div className="admin-dashboard inventory-view">
      <div className="admin-dashboard-header">
        <h1 className="admin-dashboard-title">INVENTORY MANAGEMENT</h1>
        <div className="status-indicators">
          <span className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
          <button className="control-btn" onClick={goBack} style={{ marginLeft: '1rem' }}>
            BACK TO DASHBOARD
          </button>
        </div>
      </div>

      {connectionError && (
        <div className="connection-error">
          <span className="error-icon">⚠️</span>
          <span className="error-message">{connectionError}</span>
        </div>
      )}

      <div className="inventory-content" style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        <div className="inventory-list-section" style={{ flex: 2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="section-title">INVENTORY ITEMS</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button 
                className="control-btn" 
                onClick={handleAnalyzeAndOptimize}
                disabled={isAnalyzing}
                style={{ 
                  background: isAnalyzing ? '#555' : '#7ECA9C',
                  opacity: isAnalyzing ? 0.6 : 1,
                  cursor: isAnalyzing ? 'not-allowed' : 'pointer'
                }}
              >
                {isAnalyzing ? 'ANALYZING...' : 'ANALYZE & OPTIMIZE'}
              </button>
              <button className="control-btn" onClick={handleOpenHistory}>
                HISTORY
              </button>
              <button className="control-btn" onClick={() => setShowCreateModal(true)}>
                + ADD ITEM
              </button>
            </div>
          </div>
          {isAnalyzing && (
            <div style={{ 
              marginBottom: '1rem', 
              padding: '1rem', 
              background: '#1a1a1a', 
              borderRadius: '4px',
              border: '1px solid #333'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ color: '#7ECA9C', fontWeight: 'bold' }}>{analyzingMessage || 'Analyzing...'}</span>
                <span style={{ color: '#999' }}>{analyzingProgress}%</span>
              </div>
              <div style={{ 
                width: '100%', 
                height: '8px', 
                background: '#333', 
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{ 
                  width: `${analyzingProgress}%`, 
                  height: '100%', 
                  background: '#7ECA9C',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          )}
          <div className="inventory-table-container">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Thumbnail</th>
                  <th>ID</th>
                  <th>Fruit Type</th>
                  <th>Quantity</th>
                  <th>Arrival Date</th>
                  <th>Original Price</th>
                  <th>Current Price</th>
                  <th>Discount %</th>
                  <th>Approx. Freshness</th>
                  <th>Actual Freshness</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="empty-cell">No inventory items</td>
                  </tr>
                ) : (
                  inventory.map(item => (
                    <tr key={item.id}>
                      <td>
                        {item.thumbnail_path ? (
                          <img 
                            src={`${config.apiUrl}/${item.thumbnail_path}`}
                            alt={item.fruit_type}
                            style={{
                              width: '50px',
                              height: '50px',
                              objectFit: 'cover',
                              borderRadius: '4px',
                              border: '1px solid #333'
                            }}
                            onError={(e) => {
                              // Hide image if it fails to load
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        ) : (
                          <div style={{
                            width: '50px',
                            height: '50px',
                            backgroundColor: '#1a1a1a',
                            border: '1px solid #333',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#666',
                            fontSize: '0.75em'
                          }}>
                            No img
                          </div>
                        )}
                      </td>
                      <td>{item.id}</td>
                      <td 
                        className="fruit-type-cell" 
                        onClick={() => handleFruitTypeClick(item.fruit_type)}
                        style={{ cursor: 'pointer', textDecoration: 'underline' }}
                        title="Click to view detection images"
                      >
                        {item.fruit_type}
                      </td>
                      <td className="quantity-cell">{item.quantity}</td>
                      <td>{item.arrival_date ? new Date(item.arrival_date).toLocaleDateString() : '-'}</td>
                      <td>${item.original_price.toFixed(2)}</td>
                      <td>${item.current_price.toFixed(2)}</td>
                      <td>{item.discount_percentage !== undefined ? `${item.discount_percentage.toFixed(1)}%` : '-'}</td>
                      <td>
                        {item.freshness ? (
                          <div>
                            {(item.freshness.freshness_score * 100).toFixed(1)}%
                          </div>
                        ) : '-'}
                      </td>
                      <td>
                        {item.actual_freshness_avg !== null && item.actual_freshness_avg !== undefined ? (
                          <div style={{ color: '#7ECA9C', fontWeight: 'bold' }}>
                            {(item.actual_freshness_avg * 100).toFixed(1)}%
                          </div>
                        ) : (
                          <div style={{ color: '#999', fontStyle: 'italic', fontSize: '0.9em' }}>
                            N/A
                          </div>
                        )}
                      </td>
                      <td>
                        {(() => {
                          // Use actual freshness if available, otherwise use approximate
                          const freshnessScore = item.actual_freshness_avg !== null && item.actual_freshness_avg !== undefined
                            ? item.actual_freshness_avg
                            : (item.freshness?.freshness_score || null);
                          
                          if (freshnessScore === null) {
                            return '-';
                          }
                          
                          const status = getStatusFromFreshness(freshnessScore);
                          const statusLabel = getStatusLabel(status);
                          const statusColor = getStatusColor(status);
                          const isEstimated = item.actual_freshness_avg === null || item.actual_freshness_avg === undefined;
                          
                          return (
                            <div style={{ fontSize: '0.85em', color: statusColor }}>
                              {isEstimated ? `ESTIMATED ${statusLabel}` : statusLabel}
                            </div>
                          );
                        })()}
                      </td>
                      <td>
                        <button 
                          className="inventory-action-btn edit-btn" 
                          onClick={() => setEditingItem(item)}
                          style={{ marginRight: '0.5rem' }}
                        >
                          EDIT
                        </button>
                        <button 
                          className="inventory-action-btn delete-btn" 
                          onClick={() => handleDelete(item.id)}
                        >
                          DELETE
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Impact Statistics Panel - Only show if successfully loaded */}
        {!statsLoading && !statsError && (foodWasteSaved !== null || co2Saved !== null || additionalRevenue !== null) && (
          <div className="stats-panel" style={{ 
            flex: 1, 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '15px',
            minWidth: '250px'
          }}>
            <h2 className="section-title" style={{ marginBottom: '10px' }}>IMPACT STATISTICS</h2>
            <div className="stat-box" style={{ 
              background: '#1a1a1a', 
              padding: '15px', 
              borderRadius: '4px', 
              border: '1px solid #7ECA9C',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px'
            }}>
              <h4 style={{ color: '#fff', margin: 0, fontSize: '0.9em', fontWeight: 'normal' }}>FOOD WASTE SAVED</h4>
              <p style={{ color: '#7ECA9C', fontSize: '1.5em', margin: 0, fontWeight: 'bold' }}>
                {foodWasteSaved !== null ? `${foodWasteSaved.toFixed(2)} kg` : 'N/A'}
              </p>
            </div>
            <div className="stat-box" style={{ 
              background: '#1a1a1a', 
              padding: '15px', 
              borderRadius: '4px', 
              border: '1px solid #7ECA9C',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px'
            }}>
              <h4 style={{ color: '#fff', margin: 0, fontSize: '0.9em', fontWeight: 'normal' }}>CO₂ SAVED</h4>
              <p style={{ color: '#7ECA9C', fontSize: '1.5em', margin: 0, fontWeight: 'bold' }}>
                {co2Saved !== null ? `${co2Saved.toFixed(2)} kg` : 'N/A'}
              </p>
            </div>
            <div className="stat-box" style={{ 
              background: '#1a1a1a', 
              padding: '15px', 
              borderRadius: '4px', 
              border: '1px solid #7ECA9C',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px'
            }}>
              <h4 style={{ color: '#fff', margin: 0, fontSize: '0.9em', fontWeight: 'normal' }}>ADDITIONAL REVENUE</h4>
              <p style={{ color: '#7ECA9C', fontSize: '1.5em', margin: 0, fontWeight: 'bold' }}>
                {additionalRevenue !== null ? `$${additionalRevenue.toFixed(2)}` : 'N/A'}
              </p>
            </div>
          </div>
        )}

        <div className="changes-log-section" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100vh' }}>
          {/* Quantity Changes Log - Top Half */}
          <div style={{ height: '50vh', display: 'flex', flexDirection: 'column' }}>
            <h2 className="section-title">QUANTITY CHANGES LOG</h2>
            <div className="changes-log-container">
              {quantityChanges.length === 0 ? (
                <div className="empty-log">No quantity changes yet</div>
              ) : (
                quantityChanges.map((change, index) => (
                  <div key={index} className={`change-log-item ${change.change_type}`}>
                    <div className="change-log-header">
                      <span className="change-fruit-type">{change.fruit_type}</span>
                      <span className="change-timestamp">
                        {new Date(change.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="change-log-details">
                      <span className="change-delta">
                        {change.change_type === 'increase' ? '+' : ''}{change.delta}
                      </span>
                      <span className="change-quantities">
                        {change.old_quantity} → {change.new_quantity}
                      </span>
                      {change.freshness_score !== null && change.freshness_score !== undefined && (
                        <span className="change-freshness" style={{ marginLeft: '1rem', fontSize: '0.9em', color: '#7ECA9C' }}>
                          Freshness: {(change.freshness_score * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Discounted Items / Optimization - Bottom Half */}
          <div style={{ height: '50vh', display: 'flex', flexDirection: 'column' }}>
            <h2 className="section-title">AUTOMATED OPTIMIZATION</h2>
            <div className="changes-log-container">
              {discountedItems.length === 0 ? (
                <div className="empty-log">No discounted items currently</div>
              ) : (
                discountedItems.slice(0, 10).map((item) => {
                  // Calculate discount based on actual freshness (only items with actual freshness are included)
                  const freshnessScore = item.actual_freshness_avg!; // Safe to use ! since we filter for it
                  
                  const maxDiscount = 75.0;
                  const power = 1.5;
                  const calculatedDiscount = maxDiscount * (1 - (freshnessScore ** power));
                  const displayPrice = item.original_price * (1 - calculatedDiscount / 100);
                  
                  return (
                    <div key={item.id} className="change-log-item" style={{ 
                      borderLeftColor: calculatedDiscount >= 30 ? '#ff6b6b' : '#7ECA9C',
                      background: '#1a1f1a'
                    }}>
                      <div className="change-log-header">
                        <span className="change-fruit-type" style={{ textTransform: 'capitalize' }}>
                          {item.fruit_type}
                          {item.variety && ` (${item.variety})`}
                        </span>
                        <span style={{ 
                          color: '#ff6b6b', 
                          fontWeight: '600',
                          fontSize: '0.9rem'
                        }}>
                          {calculatedDiscount.toFixed(0)}% OFF
                        </span>
                      </div>
                      <div className="change-log-details" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.25rem' }}>
                        <div style={{ display: 'flex', gap: '1rem', width: '100%', justifyContent: 'space-between' }}>
                          <span style={{ color: '#CCFFBD' }}>
                            <span style={{ textDecoration: 'line-through', opacity: 0.6 }}>
                              ${item.original_price.toFixed(2)}
                            </span>
                            {' '}
                            <span style={{ color: '#7ECA9C', fontWeight: '600' }}>
                              ${displayPrice.toFixed(2)}
                            </span>
                          </span>
                          <span style={{ color: '#AAF0D1', fontSize: '0.85em' }}>
                            Qty: {item.quantity}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8em', color: '#999', marginTop: '0.25rem' }}>
                          Actual Freshness: <span style={{ color: '#7ECA9C', fontWeight: 'bold' }}>{(item.actual_freshness_avg! * 100).toFixed(1)}%</span>
                        </div>
                        <div style={{ fontSize: '0.75em', color: '#7ECA9C', marginTop: '0.25rem', fontStyle: 'italic' }}>
                          Being promoted to customers via automated recommendations
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingItem) && (
        <InventoryModal
          item={editingItem}
          onClose={() => {
            setShowCreateModal(false);
            setEditingItem(null);
          }}
          onSave={(itemData) => {
            if (editingItem) {
              handleUpdate(editingItem.id, itemData);
            } else {
              handleCreate(itemData);
            }
          }}
        />
      )}

      {/* Image Modal */}
      {showImageModal && (
        <div className="modal-overlay" onClick={() => {
          setShowImageModal(false);
          setExpandedImage(null);
        }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto' }}>
            <div className="modal-header">
              <h2>Detection Images: {selectedItemCategory?.toUpperCase()}</h2>
              <button className="modal-close" onClick={() => {
                setShowImageModal(false);
                setExpandedImage(null);
              }}>×</button>
            </div>
            <div className="modal-body">
              {loadingImages ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#7ECA9C' }}>
                  <div style={{ fontSize: '1.2rem', marginBottom: '1.5rem' }}>Loading images and detecting blemishes...</div>
                  
                  {/* Progress Bar */}
                  <div style={{ 
                    width: '100%',
                    maxWidth: '500px',
                    margin: '0 auto 1rem',
                    background: 'rgba(126, 202, 156, 0.1)',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    border: '1px solid rgba(126, 202, 156, 0.3)',
                    height: '24px'
                  }}>
                    <div style={{
                      width: `${loadingProgress}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, #7ECA9C 0%, #AAF0D1 100%)',
                      transition: 'width 0.3s ease',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      paddingRight: '8px',
                      boxShadow: '0 0 10px rgba(126, 202, 156, 0.5)'
                    }}>
                      {loadingProgress > 15 && (
                        <span style={{
                          fontSize: '0.75rem',
                          color: '#000',
                          fontWeight: '600',
                          fontFamily: '"Geist Mono", monospace'
                        }}>
                          {Math.round(loadingProgress)}%
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div style={{ 
                    fontSize: '0.875rem',
                    color: 'rgba(126, 202, 156, 0.7)',
                    fontFamily: '"Geist Mono", monospace'
                  }}>
                    {loadingProgress < 100 ? 'Processing images...' : 'Complete!'}
                  </div>
                </div>
              ) : selectedItemImages.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#999' }}>
                  No detection images found for this category yet.
                  <br />
                  Images will appear here as fruits are detected by the camera.
                </div>
              ) : (
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
                  gap: '1rem',
                  padding: '1rem'
                }}>
                  {selectedItemImages.map((image: DetectionImage, idx: number) => (
                    <div 
                      key={idx} 
                      onClick={() => handleExpandImage(image)}
                      style={{ 
                        border: '1px solid #333', 
                        borderRadius: '4px',
                        overflow: 'hidden',
                        background: '#1a1a1a',
                        cursor: 'pointer',
                        transition: 'transform 0.2s, border-color 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'scale(1.05)';
                        e.currentTarget.style.borderColor = '#7ECA9C';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'scale(1)';
                        e.currentTarget.style.borderColor = '#333';
                      }}
                    >
                      <img 
                        src={`${config.apiUrl}/${image.path}`}
                        alt={`${selectedItemCategory} detection ${idx + 1}`}
                        style={{ 
                          width: '100%', 
                          height: '200px', 
                          objectFit: 'cover',
                          display: 'block'
                        }}
                      />
                      <div style={{ padding: '0.5rem', fontSize: '0.85em' }}>
                        {image.metadata?.confidence && (
                          <div>Confidence: {(image.metadata.confidence * 100).toFixed(1)}%</div>
                        )}
                        {image.metadata?.freshness_score !== undefined && image.metadata.freshness_score !== null && (
                          <div>Freshness: {typeof image.metadata.freshness_score === 'number' && image.metadata.freshness_score <= 1 
                            ? (image.metadata.freshness_score * 100).toFixed(1) 
                            : image.metadata.freshness_score.toFixed(1)}%</div>
                        )}
                        {image.metadata?.blemishes && (
                          <div style={{ marginTop: '0.25rem' }}>
                            {image.metadata.blemishes.error ? (
                              <div style={{ color: '#ff6b6b', fontSize: '0.8em' }}>
                                Blemish detection error
                              </div>
                            ) : (
                              <div>
                                <div style={{ 
                                  color: (image.metadata.blemishes.count || 0) > 0 ? '#ff6b6b' : '#7ECA9C',
                                  fontWeight: 'bold'
                                }}>
                                  Blemishes: {image.metadata.blemishes.count || 0}
                                </div>
                                {image.metadata.blemishes.labels && image.metadata.blemishes.labels.length > 0 && (
                                  <div style={{ fontSize: '0.75em', color: '#999', marginTop: '0.25rem' }}>
                                    {image.metadata.blemishes.labels.slice(0, 3).join(', ')}
                                    {image.metadata.blemishes.labels.length > 3 && '...'}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                        <div style={{ fontSize: '0.75em', color: '#999', marginTop: '0.25rem' }}>
                          {new Date(image.timestamp).toLocaleString()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Expanded Image Modal with Blemish Annotations */}
      {expandedImage && (
        <div className="modal-overlay" onClick={() => {
          setExpandedImage(null);
          setImageDimensions(null);
        }} style={{ zIndex: 1001 }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ 
            maxWidth: '95vw', 
            maxHeight: '95vh', 
            overflow: 'auto',
            position: 'relative'
          }}>
            <div className="modal-header">
              <h2>Blemish Detection: {selectedItemCategory?.toUpperCase()}</h2>
              <button className="modal-close" onClick={() => {
                setExpandedImage(null);
                setImageDimensions(null);
              }}>×</button>
            </div>
            <div className="modal-body" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ position: 'relative', maxWidth: '100%', marginBottom: '1rem' }}>
                <img 
                  id={`expanded-image-${expandedImage.filename}`}
                  src={`${config.apiUrl}/${expandedImage.path}`}
                  alt="Expanded detection"
                  crossOrigin="anonymous"
                  style={{ 
                    maxWidth: '600px',
                    maxHeight: '400px',
                    width: 'auto',
                    height: 'auto',
                    display: 'block',
                    margin: '0 auto'
                  }}
                  onLoad={(e) => {
                    // Draw blemish bounding boxes on the image
                    const img = e.currentTarget;
                    
                    // Skip if this is already a canvas data URL (to prevent infinite loop)
                    if (img.src.startsWith('data:')) {
                      return;
                    }
                    
                    // Wait for image to be fully loaded with dimensions
                    if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                      // Store image dimensions for weighted freshness calculation
                      setImageDimensions({
                        width: img.naturalWidth,
                        height: img.naturalHeight
                      });
                      
                      const canvas = document.createElement('canvas');
                      canvas.width = img.naturalWidth;
                      canvas.height = img.naturalHeight;
                      const ctx = canvas.getContext('2d');
                      
                      if (!ctx) {
                        console.error('Failed to get canvas context');
                        return;
                      }
                      
                      if (!expandedImage.metadata?.blemishes?.bboxes || expandedImage.metadata.blemishes.bboxes.length === 0) {
                        console.log('No blemishes to draw');
                        return;
                      }
                      
                      // Draw the image on canvas
                      ctx.drawImage(img, 0, 0);
                      
                      console.log(`Drawing ${expandedImage.metadata.blemishes.bboxes.length} blemishes on image ${img.naturalWidth}x${img.naturalHeight}`);
                      
                      // Draw bounding boxes for blemishes
                      expandedImage.metadata.blemishes.bboxes.forEach((bbox: any, idx: number) => {
                        if (!bbox.box_2d || !Array.isArray(bbox.box_2d) || bbox.box_2d.length !== 4) {
                          console.warn('Invalid bbox format:', bbox);
                          return;
                        }
                        
                        const [ymin, xmin, ymax, xmax] = bbox.box_2d;
                        const label = bbox.label || expandedImage.metadata?.blemishes?.labels?.[idx] || 'blemish';
                        
                        // Convert normalized coordinates (0-1000) to pixel coordinates
                        const x1 = (xmin / 1000) * img.naturalWidth;
                        const y1 = (ymin / 1000) * img.naturalHeight;
                        const x2 = (xmax / 1000) * img.naturalWidth;
                        const y2 = (ymax / 1000) * img.naturalHeight;
                        const width = x2 - x1;
                        const height = y2 - y1;
                        
                        console.log(`Blemish ${idx + 1}: [${xmin}, ${ymin}, ${xmax}, ${ymax}] -> [${x1.toFixed(1)}, ${y1.toFixed(1)}, ${x2.toFixed(1)}, ${y2.toFixed(1)}] (${width.toFixed(1)}x${height.toFixed(1)})`);
                        
                        // Only draw if coordinates are valid
                        if (width > 0 && height > 0) {
                          // Draw bounding box
                          ctx.strokeStyle = '#ff6b6b';
                          ctx.lineWidth = 3;
                          ctx.strokeRect(x1, y1, width, height);
                          
                          // Draw label background
                          ctx.fillStyle = 'rgba(255, 107, 107, 0.8)';
                          ctx.font = 'bold 16px "Geist Mono", monospace';
                          const textMetrics = ctx.measureText(label);
                          const textWidth = textMetrics.width;
                          const textHeight = 20;
                          const labelY = Math.max(textHeight + 4, y1);
                          ctx.fillRect(x1, labelY - textHeight - 4, textWidth + 8, textHeight);
                          
                          // Draw label text
                          ctx.fillStyle = '#ffffff';
                          ctx.fillText(label, x1 + 4, labelY - 8);
                        } else {
                          console.warn(`Invalid dimensions for blemish ${idx + 1}: ${width}x${height}`);
                        }
                      });
                      
                      // Replace img src with canvas data URL
                      img.src = canvas.toDataURL();
                      console.log('Canvas drawn and applied to image');
                    } else {
                      console.warn('Image not fully loaded:', { naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight });
                    }
                  }}
                />
              </div>
              <div style={{ 
                width: '100%', 
                padding: '1rem', 
                background: '#1a1a1a', 
                borderRadius: '4px',
                border: '1px solid #333'
              }}>
                <h3 style={{ marginTop: 0, marginBottom: '0.5rem', color: '#7ECA9C' }}>Image Details</h3>
                {expandedImage.metadata?.confidence && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>Confidence:</strong> {(expandedImage.metadata.confidence * 100).toFixed(1)}%
                  </div>
                )}
                {expandedImage.metadata?.freshness_score !== undefined && expandedImage.metadata.freshness_score !== null && (
                  <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ flex: '1', minWidth: '250px', padding: '0.75rem', background: 'rgba(255, 165, 0, 0.1)', borderRadius: '4px', border: '1px solid rgba(255, 165, 0, 0.3)' }}>
                      <div style={{ marginBottom: '0.25rem' }}>
                        <strong style={{ color: '#FFA500' }}>Approximate Freshness:</strong>
                      </div>
                      <div style={{ fontSize: '1.2em', fontWeight: 'bold', color: '#FFA500' }}>
                        {typeof expandedImage.metadata.freshness_score === 'number' && expandedImage.metadata.freshness_score <= 1 
                          ? (expandedImage.metadata.freshness_score * 100).toFixed(1) 
                          : expandedImage.metadata.freshness_score.toFixed(1)}%
                      </div>
                      <div style={{ fontSize: '0.85em', color: '#999', marginTop: '0.25rem', fontStyle: 'italic' }}>
                        Model-based estimation
                      </div>
                    </div>
                    {expandedImage.metadata?.blemishes?.bboxes && 
                     expandedImage.metadata.blemishes.bboxes.length > 0 && 
                     imageDimensions && (() => {
                       // Calculate blemish area
                       let totalBlemishArea = 0;
                       expandedImage.metadata.blemishes.bboxes.forEach((bbox: any) => {
                         if (bbox.box_2d && bbox.box_2d.length === 4) {
                           const [ymin, xmin, ymax, xmax] = bbox.box_2d;
                           const width = ((xmax - xmin) / 1000) * imageDimensions.width;
                           const height = ((ymax - ymin) / 1000) * imageDimensions.height;
                           totalBlemishArea += width * height;
                         }
                       });
                       const imageArea = imageDimensions.width * imageDimensions.height;
                       const blemishCoveragePercent = (totalBlemishArea / imageArea) * 100;
                       
                       const actualFreshnessScore = calculateBlemishBasedFreshnessScore(
                         expandedImage.metadata.blemishes.bboxes,
                         imageDimensions.width,
                         imageDimensions.height
                       );
                       
                       return (
                         <div style={{ flex: '1', minWidth: '250px', padding: '0.75rem', background: 'rgba(126, 202, 156, 0.1)', borderRadius: '4px', border: '1px solid rgba(126, 202, 156, 0.3)' }}>
                           <div style={{ marginBottom: '0.25rem' }}>
                             <strong style={{ color: '#7ECA9C' }}>Actual Freshness:</strong>
                           </div>
                           <div style={{ fontSize: '1.2em', fontWeight: 'bold', color: '#7ECA9C' }}>
                             {(actualFreshnessScore * 100).toFixed(1)}%
                           </div>
                           <div style={{ fontSize: '0.85em', color: '#999', marginTop: '0.5rem' }}>
                             <div>Blemish Count: {expandedImage.metadata.blemishes.count || 0}</div>
                             <div>Coverage Area: {blemishCoveragePercent.toFixed(2)}% of image</div>
                             <div style={{ marginTop: '0.25rem', fontStyle: 'italic' }}>
                               Calculated purely from blemish, rot, whatever spots with segmentation masking detection
                             </div>
                           </div>
                         </div>
                       );
                     })()}
                  </div>
                )}
                {expandedImage.metadata?.blemishes && (
                  <div style={{ marginTop: '1rem' }}>
                    {expandedImage.metadata.blemishes.error ? (
                      <div style={{ color: '#ff6b6b' }}>
                        <strong>Blemish Detection Error:</strong> {expandedImage.metadata.blemishes.error}
                      </div>
                    ) : (
                      <>
                        <div style={{ 
                          marginBottom: '0.5rem',
                          color: (expandedImage.metadata.blemishes.count || 0) > 0 ? '#ff6b6b' : '#7ECA9C',
                          fontWeight: 'bold',
                          fontSize: '1.1em'
                        }}>
                          Blemishes Detected: {expandedImage.metadata.blemishes.count || 0}
                        </div>
                        {expandedImage.metadata.blemishes.bboxes && expandedImage.metadata.blemishes.bboxes.length > 0 && (
                          <div style={{ marginTop: '0.5rem' }}>
                            <strong>Blemish Details:</strong>
                            <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem' }}>
                              {expandedImage.metadata?.blemishes?.bboxes?.map((bbox: any, idx: number) => (
                                <li key={idx} style={{ marginBottom: '0.25rem' }}>
                                  <span style={{ color: '#ff6b6b' }}>{bbox.label || expandedImage.metadata?.blemishes?.labels?.[idx] || 'Blemish'}</span>
                                  {' '}(Box: [{bbox.box_2d[0]}, {bbox.box_2d[1]}, {bbox.box_2d[2]}, {bbox.box_2d[3]}])
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {expandedImage.metadata.blemishes.labels && expandedImage.metadata.blemishes.labels.length > 0 && (
                          <div style={{ marginTop: '0.5rem' }}>
                            <strong>Labels:</strong> {expandedImage.metadata.blemishes.labels.join(', ')}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
                <div style={{ marginTop: '1rem', fontSize: '0.9em', color: '#999' }}>
                  <strong>Timestamp:</strong> {new Date(expandedImage.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && (
        <div className="modal-overlay" onClick={() => setShowHistoryModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto' }}>
            <div className="modal-header">
              <h2>QUANTITY CHANGE HISTORY</h2>
              <button className="modal-close" onClick={() => setShowHistoryModal(false)}>×</button>
            </div>
            
            {loadingHistory ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#7ECA9C' }}>
                Loading history...
              </div>
            ) : (
              <div style={{ padding: '1rem' }}>
                {/* Statistics Section */}
                <div style={{ marginBottom: '2rem' }}>
                  <h3 style={{ color: '#7ECA9C', marginBottom: '1rem', fontSize: '1.2em' }}>STATISTICS BY FRUIT TYPE</h3>
                  {historyStatistics.length === 0 ? (
                    <div style={{ color: '#999', fontStyle: 'italic' }}>No statistics available</div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
                      {historyStatistics.map((stat, idx) => (
                        <div 
                          key={stat.fruit_type} 
                          style={{ 
                            padding: '1rem', 
                            background: idx === 0 ? 'rgba(126, 202, 156, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                            border: idx === 0 ? '2px solid #7ECA9C' : '1px solid #333',
                            borderRadius: '8px'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <h4 style={{ color: idx === 0 ? '#7ECA9C' : '#fff', fontSize: '1.1em', textTransform: 'capitalize' }}>
                              {stat.fruit_type}
                              {idx === 0 && <span style={{ marginLeft: '0.5rem', fontSize: '0.8em', color: '#FFA500' }}>MOST POPULAR</span>}
                            </h4>
                          </div>
                          <div style={{ fontSize: '0.9em', color: '#ccc', lineHeight: '1.6' }}>
                            <div>Total Changes: <strong style={{ color: '#fff' }}>{stat.total_changes}</strong></div>
                            <div>Increases: <strong style={{ color: '#7ECA9C' }}>+{stat.total_increases}</strong> ({stat.increase_count} times)</div>
                            <div>Decreases: <strong style={{ color: '#ff6b6b' }}>-{stat.total_decreases}</strong> ({stat.decrease_count} times)</div>
                            <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid #333' }}>
                              Net Change: <strong style={{ color: stat.net_change >= 0 ? '#7ECA9C' : '#ff6b6b' }}>
                                {stat.net_change >= 0 ? '+' : ''}{stat.net_change}
                              </strong>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Charts Section */}
                {historyData.length > 0 && (
                  <div style={{ marginBottom: '2rem' }}>
                    <h3 style={{ color: '#7ECA9C', marginBottom: '1.5rem', fontSize: '1.2em' }}>VISUAL ANALYTICS</h3>
                    
                    {/* Two Chart Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                      {/* Quantity Changes Over Time */}
                      <div style={{ padding: '1.5rem', background: '#101111', borderRadius: '4px', border: '1px solid #333' }}>
                        <h4 style={{ color: '#7ECA9C', marginBottom: '1rem', fontSize: '1em', fontWeight: '600' }}>QUANTITY CHANGES OVER TIME</h4>
                        <ResponsiveContainer width="100%" height={300}>
                          <AreaChart data={processTimeSeriesData()}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1a1f1a" />
                            <XAxis 
                              dataKey="time" 
                              stroke="#7ECA9C" 
                              tick={{ fill: '#999', fontSize: '0.7em' }}
                              style={{ fontFamily: 'inherit' }}
                              angle={-45}
                              textAnchor="end"
                              height={80}
                            />
                            <YAxis 
                              stroke="#7ECA9C" 
                              tick={{ fill: '#999', fontSize: '0.75em' }}
                              style={{ fontFamily: 'inherit' }}
                            />
                            <Tooltip 
                              contentStyle={{ 
                                background: '#1a1f1a', 
                                border: '1px solid #333', 
                                color: '#fff',
                                borderRadius: '4px'
                              }}
                              labelStyle={{ color: '#7ECA9C', fontWeight: '600' }}
                            />
                            <Legend 
                              wrapperStyle={{ color: '#999', fontSize: '0.85em' }}
                            />
                            <Area 
                              type="monotone" 
                              dataKey="increases" 
                              stackId="1" 
                              stroke="#7ECA9C" 
                              fill="#7ECA9C" 
                              fillOpacity={0.3} 
                              name="Increases" 
                            />
                            <Area 
                              type="monotone" 
                              dataKey="decreases" 
                              stackId="1" 
                              stroke="#ff6b6b" 
                              fill="#ff6b6b" 
                              fillOpacity={0.3} 
                              name="Decreases" 
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Changes by Fruit Type */}
                      {historyStatistics.length > 0 ? (
                        <div style={{ padding: '1.5rem', background: '#101111', borderRadius: '4px', border: '1px solid #333' }}>
                          <h4 style={{ color: '#7ECA9C', marginBottom: '1rem', fontSize: '1em', fontWeight: '600' }}>CHANGES BY FRUIT TYPE</h4>
                          <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={processFruitTypeChartData()}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#1a1f1a" />
                              <XAxis 
                                dataKey="name" 
                                stroke="#7ECA9C" 
                                tick={{ fill: '#999', fontSize: '0.75em' }}
                                style={{ fontFamily: 'inherit' }}
                              />
                              <YAxis 
                                stroke="#7ECA9C" 
                                tick={{ fill: '#999', fontSize: '0.75em' }}
                                style={{ fontFamily: 'inherit' }}
                              />
                              <Tooltip 
                                contentStyle={{ 
                                  background: '#1a1f1a', 
                                  border: '1px solid #333', 
                                  color: '#fff',
                                  borderRadius: '4px'
                                }}
                                labelStyle={{ color: '#7ECA9C', fontWeight: '600' }}
                              />
                              <Legend 
                                wrapperStyle={{ color: '#999', fontSize: '0.85em' }}
                              />
                              <Bar dataKey="increases" fill="#7ECA9C" name="Increases" radius={[4, 4, 0, 0]} />
                              <Bar dataKey="decreases" fill="#ff6b6b" name="Decreases" radius={[4, 4, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <div style={{ padding: '1.5rem', background: '#101111', borderRadius: '4px', border: '1px solid #333', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
                          <div style={{ color: '#999', fontStyle: 'italic', textAlign: 'center' }}>
                            No statistics available for chart
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Full History Log */}
                <div>
                  <h3 style={{ color: '#7ECA9C', marginBottom: '1rem', fontSize: '1.2em' }}>FULL HISTORY LOG</h3>
                  {historyData.length === 0 ? (
                    <div style={{ color: '#999', fontStyle: 'italic' }}>No history available</div>
                  ) : (
                    <div className="changes-log-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      {historyData.map((change) => (
                        <div key={change.inventory_id + change.timestamp} className={`change-log-item ${change.change_type}`}>
                          <div className="change-log-header">
                            <span className="change-fruit-type" style={{ textTransform: 'capitalize' }}>{change.fruit_type}</span>
                            <span className="change-timestamp">
                              {new Date(change.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div className="change-log-details">
                            <span className="change-delta">
                              {change.change_type === 'increase' ? '+' : ''}{change.delta}
                            </span>
                            <span className="change-quantities">
                              {change.old_quantity} → {change.new_quantity}
                            </span>
                            {change.freshness_score !== null && change.freshness_score !== undefined && (
                              <span className="change-freshness" style={{ marginLeft: '1rem', fontSize: '0.9em', color: '#7ECA9C' }}>
                                Freshness: {(change.freshness_score * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

interface InventoryModalProps {
  item: InventoryItem | null;
  onClose: () => void;
  onSave: (itemData: Partial<InventoryItem>) => void;
}

const InventoryModal = ({ item, onClose, onSave }: InventoryModalProps) => {
  const [formData, setFormData] = useState<Partial<InventoryItem>>({
    fruit_type: item?.fruit_type || '',
    variety: item?.variety || '',
    quantity: item?.quantity || 0,
    batch_number: item?.batch_number || '',
    location_in_store: item?.location_in_store || '',
    original_price: item?.original_price || 0,
    current_price: item?.current_price || item?.original_price || 0,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      ...formData,
      quantity: Number(formData.quantity) || 0,
      original_price: Number(formData.original_price) || 0,
      current_price: Number(formData.current_price) || 0,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{item ? 'EDIT ITEM' : 'CREATE ITEM'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="inventory-form">
          <div className="form-row">
            <div className="form-group">
              <label>Fruit Type *</label>
              <input
                type="text"
                value={formData.fruit_type}
                onChange={(e) => setFormData({ ...formData, fruit_type: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Variety</label>
              <input
                type="text"
                value={formData.variety}
                onChange={(e) => setFormData({ ...formData, variety: e.target.value })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Quantity *</label>
              <input
                type="number"
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 0 })}
                required
                min="0"
              />
            </div>
            <div className="form-group">
              <label>Batch Number</label>
              <input
                type="text"
                value={formData.batch_number}
                onChange={(e) => setFormData({ ...formData, batch_number: e.target.value })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Location</label>
              <input
                type="text"
                value={formData.location_in_store}
                onChange={(e) => setFormData({ ...formData, location_in_store: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Original Price *</label>
              <input
                type="number"
                step="0.01"
                value={formData.original_price}
                onChange={(e) => setFormData({ ...formData, original_price: parseFloat(e.target.value) || 0 })}
                required
                min="0"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Current Price *</label>
              <input
                type="number"
                step="0.01"
                value={formData.current_price}
                onChange={(e) => setFormData({ ...formData, current_price: parseFloat(e.target.value) || 0 })}
                required
                min="0"
              />
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="control-btn" onClick={onClose}>
              CANCEL
            </button>
            <button type="submit" className="control-btn" style={{ marginLeft: '1rem' }}>
              {item ? 'UPDATE' : 'CREATE'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default InventoryView;

