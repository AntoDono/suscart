# SusCart - Sustainable Shopping System
## Project Requirements Document

### Executive Summary
SusCart is a smart inventory management and customer recommendation system that reduces food waste by connecting grocery stores with customers. Using AI-powered freshness monitoring, the system provides dynamic discounts on items nearing expiration and recommends these deals to customers based on their purchase history.

---

## 1. System Overview

### Core Problem
- Grocery stores waste food that expires on shelves
- Customers want better deals on fresh produce
- Environmental impact from food waste

### Solution
- Real-time fruit freshness monitoring via camera/AI
- Predictive analytics for waste prevention
- Dynamic pricing based on freshness
- Personalized customer recommendations
- Win-win-win: stores reduce waste, customers save money, planet benefits

---

## 2. System Architecture

### 2.1 Technology Stack

**Backend:**
- Python Flask (REST API & WebSocket server)
- Flask-SQLA (Database ORM)
- Flask-Sock (WebSocket support)
- SQLite/PostgreSQL (Database)
- Knot API (Customer purchase tracking)

**Frontend:**
- React.js
- WebSocket client for real-time updates

**AI/Computer Vision:**
- Camera system for fruit monitoring
- ML model for freshness prediction (teammate responsibility)

### 2.2 System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Camera/AI     │────▶│  Flask Backend   │────▶│  React Frontend │
│  (Freshness)    │     │   (API + WS)     │     │  (Dashboard)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │  ▲
                               │  │
                        ┌──────▼──┴───────┐
                        │    Database      │
                        │  (Inventory,     │
                        │   Customers)     │
                        └──────────────────┘
                               │
                        ┌──────▼──────────┐
                        │    Knot API     │
                        │  (Purchase Data) │
                        └─────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Admin Dashboard Features
- **Inventory Management**
  - View all fruit items in stock
  - Real-time freshness status for each item
  - Predicted expiration dates
  - Current discount levels
  - Historical waste data

- **Dynamic Pricing**
  - Automatic discount calculation based on freshness
  - Manual override for discount rates
  - Discount tiers (e.g., 10%, 25%, 50% off)

- **Analytics Dashboard**
  - Total waste prevented
  - Revenue from discounted items
  - Popular items
  - Customer engagement metrics

### 3.2 Customer Features
- **Personalized Recommendations**
  - Items they frequently buy
  - Items on discount that match preferences
  - Optimal shopping times
  - Savings summary

- **Purchase History**
  - Track past purchases (via Knot API)
  - Spending patterns
  - Favorite items

- **Real-time Notifications**
  - Push notifications for matching deals
  - WebSocket updates for live inventory

### 3.3 Freshness Monitoring System
- **Camera Integration**
  - Continuous monitoring of fruit stock
  - Image capture at regular intervals
  - Integration with backend API

- **AI Prediction Model**
  - Analyze fruit condition
  - Predict days until expiration
  - Freshness score (0-100)
  - Confidence level

---

## 4. Database Schema

### 4.1 Core Tables

**stores**
- id (PK)
- name
- location
- contact_info
- created_at

**fruit_inventory**
- id (PK)
- store_id (FK)
- fruit_type (apple, banana, etc.)
- quantity
- batch_number
- arrival_date
- location_in_store
- original_price
- current_price
- created_at
- updated_at

**freshness_status**
- id (PK)
- inventory_id (FK)
- freshness_score (0-100)
- predicted_expiry_date
- confidence_level
- discount_percentage
- status (fresh, warning, critical, expired)
- last_checked
- image_url (optional)
- notes

**customers**
- id (PK)
- knot_customer_id
- name
- email
- phone
- preferences (JSON)
- created_at

**purchase_history**
- id (PK)
- customer_id (FK)
- inventory_id (FK)
- quantity
- price_paid
- discount_applied
- purchase_date
- knot_transaction_id

**recommendations**
- id (PK)
- customer_id (FK)
- inventory_id (FK)
- reason (JSON)
- priority_score
- sent_at
- viewed
- purchased

**waste_log**
- id (PK)
- inventory_id (FK)
- quantity_wasted
- reason
- estimated_value_loss
- logged_at

---

## 5. API Endpoints

### 5.1 Inventory Management
- `GET /api/inventory` - List all inventory items
- `POST /api/inventory` - Add new inventory item
- `GET /api/inventory/:id` - Get specific item details
- `PUT /api/inventory/:id` - Update inventory item
- `DELETE /api/inventory/:id` - Remove inventory item

### 5.2 Freshness Monitoring
- `POST /api/freshness/update` - Receive freshness data from AI
- `GET /api/freshness/:inventory_id` - Get freshness status
- `GET /api/freshness/critical` - Get items nearing expiration

### 5.3 Customer & Recommendations
- `GET /api/customers` - List all customers
- `GET /api/customers/:id` - Get customer details
- `POST /api/customers` - Register new customer
- `GET /api/recommendations/:customer_id` - Get personalized recommendations
- `POST /api/recommendations/generate` - Trigger recommendation generation

### 5.4 Analytics
- `GET /api/analytics/waste` - Waste prevention metrics
- `GET /api/analytics/revenue` - Revenue from discounts
- `GET /api/analytics/customer-engagement` - Customer metrics

### 5.5 Knot API Integration
- `POST /api/knot/sync` - Sync purchase data from Knot
- `GET /api/knot/customer/:knot_id` - Get customer data from Knot

---

## 6. WebSocket Events

### 6.1 Real-time Updates
**Admin Dashboard:**
- `inventory_updated` - Inventory changes
- `freshness_alert` - Item reaching critical freshness
- `new_purchase` - Customer purchase made
- `waste_logged` - Item wasted

**Customer App:**
- `new_recommendation` - New deal matches preferences
- `price_drop` - Watched item price decreased
- `stock_alert` - Favorite item back in stock

---

## 7. Knot API Integration

### 7.1 What is Knot API?
Knot is a unified API that connects to various commerce platforms to retrieve customer purchase data.

### 7.2 Integration Points
1. **Customer Purchase Sync**
   - Periodically fetch purchase history
   - Map Knot customer IDs to SusCart customers
   - Store transaction data

2. **Customer Preferences**
   - Analyze purchase patterns
   - Identify favorite items
   - Determine price sensitivity
   - Calculate purchase frequency

3. **Recommendation Engine**
   - Match discounted items to customer preferences
   - Consider purchase timing
   - Factor in price thresholds

---

## 8. Backend Implementation Priorities

### Phase 1: Core Infrastructure (Week 1)
- [ ] Database setup with SQLAlchemy
- [ ] Basic CRUD endpoints for inventory
- [ ] Freshness status tracking
- [ ] WebSocket real-time updates

### Phase 2: AI Integration (Week 2)
- [ ] Endpoint to receive freshness predictions
- [ ] Automatic discount calculation
- [ ] Alert system for critical items

### Phase 3: Customer Features (Week 3)
- [ ] Knot API integration
- [ ] Customer profile management
- [ ] Purchase history tracking
- [ ] Basic recommendation algorithm

### Phase 4: Advanced Features (Week 4)
- [ ] Advanced recommendation ML model
- [ ] Analytics dashboard
- [ ] Waste tracking and reporting
- [ ] Performance optimization

---

## 9. Data Flow Examples

### 9.1 Freshness Update Flow
```
1. Camera captures fruit image
2. AI model analyzes image → freshness score
3. POST /api/freshness/update with score
4. Backend calculates discount percentage
5. Updates database
6. WebSocket broadcasts update to admin dashboard
7. If discount triggers recommendation, notify customers
```

### 9.2 Customer Recommendation Flow
```
1. Freshness system flags item for discount
2. Backend queries Knot API for customer preferences
3. Matching algorithm finds relevant customers
4. Creates recommendation records
5. WebSocket pushes notification to customer app
6. Customer views and optionally purchases
```

---

## 10. Success Metrics

### Business Metrics
- % reduction in food waste
- Revenue from discounted items
- Customer adoption rate
- Average discount vs full price sales

### Technical Metrics
- API response time < 200ms
- WebSocket latency < 50ms
- Database query optimization
- 99.9% uptime

### Environmental Impact
- Pounds of food waste prevented
- Estimated CO2 reduction
- Water savings

---

## 11. Security & Privacy

- Secure API authentication (JWT tokens)
- Encrypt customer data
- GDPR compliance for EU customers
- Secure WebSocket connections (WSS)
- Rate limiting on API endpoints

---

## 12. Future Enhancements

- Mobile app (iOS/Android)
- Multiple store locations
- Recipe suggestions based on available items
- Delivery integration
- Community food donation for near-expired items
- Gamification (rewards for preventing waste)

---

**Last Updated:** November 8, 2025  
**Version:** 1.0  
**Status:** Active Development

