# SusCart Backend

## Overview
This is the Flask backend for SusCart - a sustainable shopping system that reduces food waste by connecting grocery stores with customers through AI-powered freshness monitoring and personalized recommendations.

## Features

### ✅ Implemented
- **Inventory Management** - CRUD operations for fruit inventory
- **Freshness Monitoring** - AI-powered freshness tracking with automatic discount calculation
- **Customer Profiles** - Customer management with preference tracking
- **Knot API Integration** - Sync customer purchase data (with mock fallback)
- **Recommendation Engine** - Personalized recommendations based on preferences and discounts
- **Real-time WebSockets** - Live updates for admin dashboard and customer notifications
- **Analytics** - Waste tracking and prevention metrics
- **SQLite Database** - Persistent storage with SQLAlchemy ORM

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings (optional for development)
# The defaults work fine for local development
```

### 3. Run the Server

```bash
cd backend
python main.py
```

The server will:
- Start on `http://localhost:5000`
- Automatically create database tables
- Seed sample data if database is empty
- Initialize Knot API client (mock mode if no API key)

### 4. Test the API

Visit `http://localhost:5000/routes` to see all available endpoints

## API Endpoints

### Inventory Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | List all inventory (supports filters) |
| GET | `/api/inventory/:id` | Get specific item |
| POST | `/api/inventory` | Add new item |
| PUT | `/api/inventory/:id` | Update item |
| DELETE | `/api/inventory/:id` | Delete item |

**Query Parameters for GET /api/inventory:**
- `store_id` - Filter by store
- `fruit_type` - Filter by fruit type
- `status` - Filter by freshness status (fresh, warning, critical, expired)
- `min_discount` - Minimum discount percentage

**Example:**
```bash
curl http://localhost:5000/api/inventory?status=critical&min_discount=25
```

### Freshness Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/freshness/update` | Update freshness from AI system |
| GET | `/api/freshness/:inventory_id` | Get freshness status |
| GET | `/api/freshness/critical` | Get critical items |

**Example Freshness Update Payload:**
```json
{
  "inventory_id": 1,
  "freshness_score": 65.5,
  "predicted_expiry_date": "2025-11-12T10:00:00",
  "confidence_level": 0.92,
  "image_url": "https://example.com/image.jpg",
  "notes": "Some browning detected"
}
```

The system will:
1. Calculate appropriate discount (0%, 10%, 25%, 50%, 75%)
2. Update inventory price
3. Broadcast to admin dashboards via WebSocket
4. Generate recommendations for matching customers
5. Send alerts if status is critical

### Customer Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers` | List all customers |
| GET | `/api/customers/:id` | Get customer details |
| POST | `/api/customers` | Create new customer |

**Example Customer Creation:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "(555) 123-4567",
  "knot_customer_id": "KNOT-CUST-1234",
  "preferences": {
    "favorite_fruits": ["apple", "banana"],
    "max_price": 5.00,
    "preferred_discount": 20
  }
}
```

### Knot API Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/knot/sync/:knot_customer_id` | Sync customer from Knot |

This endpoint:
1. Fetches customer data from Knot API
2. Retrieves last 90 days of purchase history
3. Analyzes purchase patterns
4. Creates/updates customer profile
5. Sets preferences automatically

**Example:**
```bash
curl -X POST http://localhost:5000/api/knot/sync/KNOT-CUST-1000
```

### Recommendations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recommendations/:customer_id` | Get customer recommendations |
| POST | `/api/recommendations/generate` | Trigger recommendation generation |

Recommendations are automatically generated when:
- Item receives discount >= 20%
- Item matches customer's favorite fruits
- Item price ≤ customer's max price
- Discount ≥ customer's preferred discount

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/waste` | Waste prevention metrics |

## WebSocket Endpoints

### Admin Dashboard (`ws://localhost:5000/ws/admin`)

Receives real-time updates about:
- `inventory_added` - New inventory items
- `inventory_updated` - Inventory changes
- `inventory_deleted` - Items removed
- `freshness_updated` - Freshness status changes
- `freshness_alert` - Critical items
- `new_purchase` - Customer purchases

**Example JavaScript Client:**
```javascript
const ws = new WebSocket('ws://localhost:5000/ws/admin');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Update type:', update.type);
  console.log('Data:', update.data);
};

// Request current stats
ws.send(JSON.stringify({ action: 'get_stats' }));
```

### Customer Notifications (`ws://localhost:5000/ws/customer/:customer_id`)

Receives:
- `new_recommendation` - Personalized deals

**Example:**
```javascript
const customerId = 1;
const ws = new WebSocket(`ws://localhost:5000/ws/customer/${customerId}`);

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  if (notification.type === 'new_recommendation') {
    showNotification(notification.data);
  }
};

// Mark recommendation as viewed
ws.send(JSON.stringify({
  action: 'view_recommendation',
  recommendation_id: 5
}));
```

## Database Schema

The system uses SQLAlchemy ORM with the following models:

- **Store** - Store locations
- **FruitInventory** - Inventory items
- **FreshnessStatus** - AI-generated freshness data
- **Customer** - Customer profiles and preferences
- **PurchaseHistory** - Transaction records
- **Recommendation** - Personalized recommendations
- **WasteLog** - Waste tracking

See `models.py` for detailed schema.

## Database Management

### Initialize Database
```bash
flask init-db
```

### Seed Sample Data
```bash
flask seed-db
```

### Clear Database
```bash
flask clear-db
```

Or use the automatic seeding when running `python main.py` for the first time.

## Knot API Integration

### Real Knot API
To use the real Knot API:
1. Sign up at https://www.useknotapi.com/
2. Get your API key
3. Set `KNOT_API_KEY` in `.env`

### Mock Mode (Default)
When no API key is configured, the system uses `MockKnotAPIClient` which provides:
- Sample customer data
- Mock purchase history
- Purchase pattern analysis

This allows development without requiring Knot API access.

## Freshness Scoring & Discount Logic

The system calculates discounts based on freshness score (0-100):

| Freshness Score | Status | Discount |
|----------------|---------|----------|
| 80-100 | Fresh | 0% |
| 60-79 | Fresh | 10% |
| 40-59 | Warning | 25% |
| 20-39 | Critical | 50% |
| 0-19 | Critical | 75% |

Status indicators:
- **Fresh** (≥70) - Good condition
- **Warning** (40-69) - Monitor closely
- **Critical** (10-39) - Deep discount needed
- **Expired** (<10) - Remove from sale

## Recommendation Algorithm

The recommendation engine matches items to customers based on:

1. **Fruit Preference Match** - Item is in customer's favorite fruits
2. **Price Threshold** - Item price ≤ customer's max price
3. **Discount Preference** - Discount ≥ customer's preferred discount
4. **Priority Score** - Higher discount = higher priority

## Integration with Frontend

Your React frontend teammate should connect to:

### REST API
- Base URL: `http://localhost:5000/api`
- All endpoints return JSON
- Use standard HTTP methods (GET, POST, PUT, DELETE)

### WebSockets
- Admin Dashboard: `ws://localhost:5000/ws/admin`
- Customer App: `ws://localhost:5000/ws/customer/:id`

### Example React Integration
```javascript
// API calls
const getInventory = async () => {
  const response = await fetch('http://localhost:5000/api/inventory');
  return await response.json();
};

// WebSocket
const connectWebSocket = (customerId) => {
  const ws = new WebSocket(`ws://localhost:5000/ws/customer/${customerId}`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Update React state
  };
  return ws;
};
```

## Integration with AI/Camera System

Your teammate working on the camera/AI system should send freshness updates to:

**Endpoint:** `POST /api/freshness/update`

**Payload:**
```json
{
  "inventory_id": 1,
  "freshness_score": 75.5,
  "predicted_expiry_date": "2025-11-15T10:00:00",
  "confidence_level": 0.95,
  "image_url": "path/to/image.jpg",
  "notes": "Optional notes about condition"
}
```

The backend will handle:
- Discount calculation
- Price updates
- Admin notifications
- Customer recommendations

## Testing

### Test API Endpoints
```bash
# Health check
curl http://localhost:5000/health

# List all routes
curl http://localhost:5000/routes

# Get inventory
curl http://localhost:5000/api/inventory

# Get critical items
curl http://localhost:5000/api/freshness/critical

# Sync from Knot (mock mode)
curl -X POST http://localhost:5000/api/knot/sync/KNOT-CUST-1000
```

### Test WebSockets
Use the provided test client:
- Open browser to `http://localhost:5000/`
- Or use `backend/ws_test_client.html`

## Production Deployment

### Database
Switch to PostgreSQL:
```bash
# In .env
DATABASE_URL=postgresql://username:password@localhost/suscart
```

### Security
1. Change `SECRET_KEY` in `.env`
2. Set `FLASK_ENV=production`
3. Set `FLASK_DEBUG=False`
4. Use WSS (secure WebSockets)
5. Enable HTTPS
6. Add authentication/authorization

### Scaling
- Use Gunicorn for production server
- Redis for WebSocket pub/sub
- Celery for background tasks
- Load balancer for multiple instances

## Troubleshooting

### Database Errors
```bash
# Reset database
flask clear-db
flask init-db
flask seed-db
```

### Import Errors
Make sure you're in the backend directory and venv is activated:
```bash
cd backend
source ../venv/bin/activate
python main.py
```

### Port Already in Use
Change port in `.env` or:
```bash
export PORT=5001
python main.py
```

## Architecture Diagram

```
┌─────────────────────────┐
│   Camera/AI System      │
│   (Teammate's code)     │
└──────────┬──────────────┘
           │
           │ POST /api/freshness/update
           ▼
┌─────────────────────────┐     WebSocket
│    Flask Backend        │◄────────────┐
│    (This code)          │              │
│                         │              │
│  • REST API             │              │
│  • WebSocket Server     │              │
│  • Database (SQLite)    │              │
│  • Knot Integration     │              │
└──────────┬──────────────┘              │
           │                             │
           │ REST API + WebSocket        │
           ▼                             │
┌─────────────────────────┐              │
│   React Frontend        │              │
│   (Teammate's code)     │──────────────┘
│                         │
│  • Admin Dashboard      │
│  • Customer App         │
└─────────────────────────┘
           │
           │ API Calls
           ▼
┌─────────────────────────┐
│     Knot API            │
│  (External Service)     │
└─────────────────────────┘
```

## Next Steps

1. ✅ Backend infrastructure complete
2. 🔄 Integrate with camera/AI system for real freshness data
3. 🔄 Connect React frontend
4. ⏳ Enhance recommendation algorithm with ML
5. ⏳ Add authentication/authorization
6. ⏳ Deploy to production

## Support

For questions about:
- **Backend APIs** - Check this README and `/routes` endpoint
- **Knot API** - Visit https://www.useknotapi.com/docs
- **Database Schema** - See `models.py`

## License

MIT License - SusCart Team 2025

