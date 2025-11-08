import { useState, useEffect, useRef } from 'react';
import './AdminDashboard.css';
import { config } from '../config';

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
  freshness?: FreshnessData;
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

const InventoryView = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [quantityChanges, setQuantityChanges] = useState<QuantityChange[]>([]);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [defaultStoreId, setDefaultStoreId] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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
    };
  }, []);

  const fetchInventory = async () => {
    try {
      const response = await fetch(`${config.apiUrl}/api/inventory`);
      if (response.ok) {
        const data = await response.json();
        setInventory(data.items || []);
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
    } else if (data.type === 'inventory_added') {
      // Refresh inventory to get new item
      fetchInventory();
    } else if (data.type === 'inventory_updated') {
      // Update inventory item
      if (data.data.id) {
        setInventory(prev => prev.map(item => 
          item.id === data.data.id 
            ? { ...item, ...data.data }
            : item
        ));
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

      <div className="inventory-content">
        <div className="inventory-list-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="section-title">INVENTORY ITEMS</h2>
            <button className="control-btn" onClick={() => setShowCreateModal(true)}>
              + ADD ITEM
            </button>
          </div>
          <div className="inventory-table-container">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Fruit Type</th>
                  <th>Quantity</th>
                  <th>Arrival Date</th>
                  <th>Original Price</th>
                  <th>Current Price</th>
                  <th>Discount %</th>
                  <th>Freshness</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="empty-cell">No inventory items</td>
                  </tr>
                ) : (
                  inventory.map(item => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td className="fruit-type-cell">{item.fruit_type}</td>
                      <td className="quantity-cell">{item.quantity}</td>
                      <td>{item.arrival_date ? new Date(item.arrival_date).toLocaleDateString() : '-'}</td>
                      <td>${item.original_price.toFixed(2)}</td>
                      <td>${item.current_price.toFixed(2)}</td>
                      <td>{item.discount_percentage !== undefined ? `${item.discount_percentage.toFixed(1)}%` : '-'}</td>
                      <td>
                        {item.freshness ? (
                          <div>
                            <div>Score: {(item.freshness.freshness_score * 100).toFixed(1)}%</div>
                            <div style={{ fontSize: '0.85em', color: item.freshness.status === 'fresh' ? '#7ECA9C' : item.freshness.status === 'warning' ? '#FFA500' : item.freshness.status === 'critical' ? '#FF6B6B' : '#999' }}>
                              {item.freshness.status.toUpperCase()}
                            </div>
                          </div>
                        ) : '-'}
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

        <div className="changes-log-section">
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

