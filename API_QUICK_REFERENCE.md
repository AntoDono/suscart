# SusCart API Quick Reference

## 🚀 Server
```bash
cd backend && python main.py
# Runs on http://localhost:5000
```

---

## 📡 REST API Endpoints

### Inventory

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | List all items |
| GET | `/api/inventory?status=critical` | Filter by freshness |
| GET | `/api/inventory?min_discount=25` | Filter by discount |
| GET | `/api/inventory/:id` | Get specific item |
| POST | `/api/inventory` | Add new item |
| PUT | `/api/inventory/:id` | Update item |
| DELETE | `/api/inventory/:id` | Delete item |

### Freshness (AI Integration)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/freshness/update` | **AI sends updates here** |
| GET | `/api/freshness/:inventory_id` | Get freshness status |
| GET | `/api/freshness/critical` | Get critical items |

### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers` | List all customers |
| GET | `/api/customers/:id` | Get customer details |
| POST | `/api/customers` | Create customer |

### Knot Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/knot/sync/:knot_customer_id` | Sync from Knot API |

### Recommendations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recommendations/:customer_id` | Get customer deals |
| POST | `/api/recommendations/generate` | Trigger generation |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/waste` | Waste metrics |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | WebSocket test client |
| GET | `/health` | Health check |
| GET | `/routes` | List all routes |

---

## 🔌 WebSocket Endpoints

### Admin Dashboard
```
ws://localhost:5000/ws/admin
```

**Receives:**
- `inventory_updated` - Stock changes
- `freshness_alert` - Critical items
- `inventory_added` - New items
- `inventory_deleted` - Removed items

### Customer App
```
ws://localhost:5000/ws/customer/:customer_id
```

**Receives:**
- `new_recommendation` - Personalized deals
- `connected` - Connection status

---

## 📝 Common Request Examples

### Get All Inventory
```bash
curl http://localhost:5000/api/inventory
```

### Get Critical Items Only
```bash
curl "http://localhost:5000/api/inventory?status=critical"
```

### AI Freshness Update
```bash
curl -X POST http://localhost:5000/api/freshness/update \
  -H "Content-Type: application/json" \
  -d '{
    "inventory_id": 1,
    "freshness_score": 45.5,
    "predicted_expiry_date": "2025-11-12T10:00:00",
    "confidence_level": 0.92
  }'
```

### Add New Inventory Item
```bash
curl -X POST http://localhost:5000/api/inventory \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": 1,
    "fruit_type": "apple",
    "variety": "Honeycrisp",
    "quantity": 50,
    "original_price": 3.99,
    "location_in_store": "Aisle 3"
  }'
```

### Create Customer
```bash
curl -X POST http://localhost:5000/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "(555) 999-8888",
    "preferences": {
      "favorite_fruits": ["apple", "pear"],
      "max_price": 6.00,
      "preferred_discount": 20
    }
  }'
```

### Sync from Knot
```bash
curl -X POST http://localhost:5000/api/knot/sync/KNOT-CUST-1000
```

### Get Customer Recommendations
```bash
curl http://localhost:5000/api/recommendations/1
```

---

## 🎨 JavaScript Examples

### Fetch Inventory (React/Frontend)
```javascript
fetch('http://localhost:5000/api/inventory')
  .then(res => res.json())
  .then(data => console.log(data.items));
```

### WebSocket Connection (Admin Dashboard)
```javascript
const ws = new WebSocket('ws://localhost:5000/ws/admin');

ws.onopen = () => console.log('Connected');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Update:', update.type, update.data);
  
  // Handle different event types
  switch(update.type) {
    case 'freshness_alert':
      alert('Item needs attention!');
      break;
    case 'inventory_updated':
      refreshInventory();
      break;
  }
};

ws.onclose = () => console.log('Disconnected');
```

### WebSocket Connection (Customer App)
```javascript
const customerId = 1;
const ws = new WebSocket(`ws://localhost:5000/ws/customer/${customerId}`);

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  
  if (notification.type === 'new_recommendation') {
    showDealNotification(notification.data);
  }
};
```

---

## 📦 Response Formats

### Inventory Item
```json
{
  "id": 1,
  "store_id": 1,
  "fruit_type": "apple",
  "variety": "Granny Smith",
  "quantity": 45,
  "batch_number": "BATCH-20251001",
  "location_in_store": "Aisle 3",
  "original_price": 2.99,
  "current_price": 2.24,
  "discount_percentage": 25,
  "freshness": {
    "freshness_score": 55.0,
    "status": "warning",
    "discount_percentage": 25,
    "predicted_expiry_date": "2025-11-10T10:00:00"
  }
}
```

### Customer
```json
{
  "id": 1,
  "knot_customer_id": "KNOT-CUST-1000",
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "phone": "(555) 111-2222",
  "preferences": {
    "favorite_fruits": ["apple", "banana", "strawberry"],
    "max_price": 5.00,
    "preferred_discount": 25
  }
}
```

### Recommendation
```json
{
  "id": 1,
  "customer_id": 1,
  "inventory_id": 3,
  "priority_score": 50,
  "viewed": false,
  "purchased": false,
  "item": {
    "fruit_type": "banana",
    "current_price": 0.99,
    "discount_percentage": 50,
    "freshness": {...}
  },
  "reason": {
    "match_type": "favorite_fruit",
    "discount": 50,
    "price": 0.99
  }
}
```

---

## 🔧 Discount Calculation

| Freshness Score | Status | Discount |
|----------------|---------|----------|
| 80-100 | Fresh | 0% |
| 60-79 | Fresh | 10% |
| 40-59 | Warning | 25% |
| 20-39 | Critical | 50% |
| 0-19 | Critical | 75% |

---

## ⚡ Quick Commands

```bash
# Start server
cd backend && python main.py

# Health check
curl http://localhost:5000/health

# List all routes
curl http://localhost:5000/routes

# View inventory
curl http://localhost:5000/api/inventory

# Test WebSocket
open http://localhost:5000/

# Reset database
rm backend/suscart.db && python backend/main.py
```

---

## 🎯 Integration Checklist

### For AI/Camera System
- [ ] Send POST to `/api/freshness/update`
- [ ] Include: inventory_id, freshness_score, predicted_expiry_date
- [ ] Backend handles rest automatically

### For Frontend
- [ ] Connect to REST API at `http://localhost:5000/api`
- [ ] Connect WebSocket for admin: `ws://localhost:5000/ws/admin`
- [ ] Connect WebSocket for customers: `ws://localhost:5000/ws/customer/:id`
- [ ] Handle real-time updates

### For Knot Integration
- [ ] Get API key from https://www.useknotapi.com/
- [ ] Set in `.env`: `KNOT_API_KEY=...`
- [ ] Or use mock mode (works without key)

---

**Need more details?** See `backend/README.md` for complete documentation.

