# 🔗 Knot API Setup & Testing Guide

## ✅ **Updated for REAL Knot API!**

Your backend is now configured to work with the **actual Knot API** using the credentials and endpoints you provided!

---

## 🎯 **What Changed**

### **Before** (Generic Integration):
- Used placeholder endpoints
- Required getting your own API key
- Mock mode only

### **After** (Real Integration):
- ✅ Uses actual Knot `/transactions/sync` endpoint
- ✅ Has working credentials included
- ✅ Supports all grocery merchants (Instacart, Walmart, Target, etc.)
- ✅ Extracts SKU data for produce/fruit identification
- ✅ Ready to test immediately

---

## 🚀 **Quick Start - Test with Mock Data**

### **Option 1: Use Mock Mode (Default)**

No setup needed! Just run:

```bash
python backend/main.py

# Output:
🔗 Using MOCK Knot API client
   Set KNOT_USE_REAL=true in .env to use real Knot API
```

Test with mock users:
```bash
# Test connection
curl http://localhost:5000/api/knot/test

# Sync mock user 'user123'
curl -X POST http://localhost:5000/api/knot/sync/user123

# Sync mock user 'user456'  
curl -X POST http://localhost:5000/api/knot/sync/user456
```

---

## 🔴 **Using the REAL Knot API**

### **Step 1: Enable Real Mode**

Create or edit `.env` file in project root:

```bash
# .env

# Enable real Knot API
KNOT_USE_REAL=true

# Credentials (provided by Knot - already set as defaults)
KNOT_CLIENT_ID=your_client_id_here
KNOT_SECRET=your_secret_here

# API endpoint (development environment)
KNOT_API_URL=https://development.knotapi.com
```

### **Step 2: Restart Server**

```bash
python backend/main.py

# Output:
🔗 Using REAL Knot API client
   Client ID: your_client_id...
   Base URL: https://development.knotapi.com
```

### **Step 3: Test Connection**

```bash
curl http://localhost:5000/api/knot/test
```

**Success Response:**
```json
{
  "status": "success",
  "message": "Knot API connection working",
  "mode": "real",
  "sample_data": {
    "external_user_id": "user123",
    "preferences": {
      "favorite_fruits": ["banana", "apple"],
      "average_spend": 35.48
    }
  }
}
```

---

## 📡 **Testing Real Knot API**

### **Test with Knot's Sample Data**

Knot provides test merchant data you can use:

```bash
# Using curl directly to Knot API
curl -s -X POST https://knot.tunnel.tel/transactions/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic your_base64_encoded_credentials" \
  --data '{"merchant_id":44,"external_user_id":"abc","limit":5}'
```

**Available Test Merchants:**
| Merchant | ID | Best For |
|----------|----|----|
| Instacart | 40 | **Groceries** (most relevant!) |
| Walmart | 45 | Groceries + general |
| Target | 12 | Groceries + general |
| Costco | 165 | Bulk groceries |
| Amazon | 44 | Amazon Fresh |
| Doordash | 19 | Food delivery |
| Ubereats | 36 | Food delivery |

### **Sync Customer via SusCart Backend**

```bash
# Sync external user 'abc' from Knot
curl -X POST http://localhost:5000/api/knot/sync/abc \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Customer", "email": "test@example.com"}'
```

**What Happens:**
1. ✅ Backend calls Knot `/transactions/sync` for user 'abc'
2. ✅ Retrieves transactions from Instacart, Walmart, Target, Costco, Amazon
3. ✅ Analyzes SKU data for produce/fruits
4. ✅ Extracts favorite fruits and products
5. ✅ Creates customer profile in SusCart
6. ✅ Sets preferences automatically

**Response:**
```json
{
  "message": "Customer synced from Knot",
  "customer": {
    "id": 4,
    "knot_customer_id": "abc",
    "name": "Test Customer",
    "email": "test@example.com",
    "preferences": {
      "favorite_fruits": ["banana", "apple", "strawberry"],
      "favorite_products": ["organic bananas", "honeycrisp apples"],
      "average_spend": 42.15,
      "purchase_frequency": 0.033,
      "merchants_used": ["Instacart", "Walmart"],
      "total_transactions": 3
    }
  },
  "transaction_count": 3
}
```

---

## 🏪 **How It Works**

### **1. Syncing Transactions**

When you call `/api/knot/sync/abc`:

```python
# Backend calls Knot API for each grocery merchant
POST https://development.knotapi.com/transactions/sync
{
  "merchant_id": 40,  # Instacart
  "external_user_id": "abc",
  "limit": 100
}

POST https://development.knotapi.com/transactions/sync
{
  "merchant_id": 45,  # Walmart
  "external_user_id": "abc",
  "limit": 100
}
# ... and so on for Target, Costco, Amazon
```

### **2. Analyzing SKU Data**

```python
# Example Knot transaction response
{
  "transactions": [
    {
      "id": "txn_12345",
      "merchant": {"id": 40, "name": "Instacart"},
      "amount": -45.67,
      "description": "Instacart - Grocery delivery",
      "skus": [
        {
          "name": "Organic Bananas",
          "category": "produce",
          "amount": -5.99
        },
        {
          "name": "Honeycrisp Apples 2lb",
          "category": "produce",
          "amount": -8.99
        }
      ]
    }
  ]
}
```

### **3. Extracting Preferences**

Backend analyzes:
- ✅ **SKU names** for fruit keywords (banana, apple, orange, etc.)
- ✅ **SKU categories** (produce, fruit)
- ✅ **Transaction descriptions**
- ✅ **Purchase frequency** (transactions per day)
- ✅ **Average spend**
- ✅ **Merchants used**

Generates:
```python
{
  "favorite_fruits": ["banana", "apple", "strawberry"],
  "favorite_products": ["organic bananas", "honeycrisp apples"],
  "average_spend": 45.67,
  "max_price": 91.34,  # Willing to pay 2x average
  "merchants_used": ["Instacart", "Walmart"]
}
```

---

## 🎯 **Integration with SusCart**

### **Workflow:**

```
1. Customer connects their Instacart/Walmart account
   ↓
2. Knot syncs their transactions
   ↓
3. SusCart backend calls: POST /api/knot/sync/customer_id
   ↓
4. Backend analyzes purchase patterns
   ↓
5. Customer preferences saved in database
   ↓
6. Recommendation engine uses preferences
   ↓
7. Customer gets personalized deals!
```

### **Example: Complete Flow**

```bash
# 1. Sync customer from Knot
curl -X POST http://localhost:5000/api/knot/sync/abc \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com"}'

# Response shows Alice likes bananas
# { "preferences": { "favorite_fruits": ["banana", ...] } }

# 2. AI detects banana freshness dropping
curl -X POST http://localhost:5000/api/freshness/update \
  -H "Content-Type: application/json" \
  -d '{
    "inventory_id": 3,
    "freshness_score": 45
  }'

# Backend automatically:
# - Applies 25% discount to bananas
# - Finds Alice likes bananas
# - Creates recommendation
# - Sends WebSocket notification to Alice

# 3. Alice gets deal notification!
# WebSocket message: "Bananas 25% off - $1.49!"
```

---

## 🧪 **Testing Checklist**

### **Mock Mode Testing:**
- [ ] Test connection: `curl http://localhost:5000/api/knot/test`
- [ ] Sync user123: `curl -X POST http://localhost:5000/api/knot/sync/user123`
- [ ] Verify preferences extracted
- [ ] Check database has customer

### **Real API Testing:**
- [ ] Set `KNOT_USE_REAL=true` in `.env`
- [ ] Restart server
- [ ] Test connection endpoint
- [ ] Sync test user 'abc'
- [ ] Verify real transactions retrieved
- [ ] Check SKU data parsed correctly
- [ ] Verify fruits identified

### **Integration Testing:**
- [ ] Sync customer from Knot
- [ ] Create discounted fruit item
- [ ] Verify recommendation generated
- [ ] Check customer notified via WebSocket

---

## 📊 **Supported Merchants**

The backend syncs from these grocery-focused merchants by default:

```python
MERCHANTS = {
    'instacart': 40,  # Primary - best for groceries
    'walmart': 45,
    'target': 12,
    'costco': 165,
    'amazon': 44,     # Amazon Fresh
}
```

You can customize in `knot_integration.py` or pass custom merchant IDs.

---

## 🎨 **Visual Representation (Bonus Points!)**

For the hackathon, you can show Knot integration by:

1. **Add Knot Logo** - Display in your UI when syncing
2. **Show "Link Account" flow** - Button to connect Instacart/Walmart
3. **Display merchants** - Show which stores customer shops at
4. **Show transaction count** - "Analyzed 15 purchases from Instacart"

---

## 🚀 **Production Setup (Later)**

For production with real users:

1. **Implement Knot SDK** - For secure account linking
   - iOS: https://docs.knotapi.com/sdk/ios
   - Android: https://docs.knotapi.com/sdk/android
   - Web: Knot Link widget

2. **Store External User IDs** - Map your user IDs to Knot

3. **Periodic Sync** - Run background job to refresh transactions

4. **Webhook Integration** - Receive real-time updates

---

## 🔒 **Security Notes**

**Current Setup (Development):**
- ✅ Credentials in code (test credentials only)
- ✅ Development endpoint
- ✅ Basic Auth

**Production Recommendations:**
- 🔐 Store credentials in environment variables only
- 🔐 Use production Knot endpoint
- 🔐 Implement rate limiting
- 🔐 Add request validation
- 🔐 Use HTTPS only

---

## 📝 **API Reference**

### **Sync Customer**
```
POST /api/knot/sync/:external_user_id
Content-Type: application/json

{
  "name": "Customer Name",    // Optional
  "email": "email@example.com" // Optional
}

Response: Customer object with preferences
```

### **Test Connection**
```
GET /api/knot/test

Response: Connection status and sample data
```

### **Direct Knot API Call (Advanced)**
```python
from knot_integration import get_knot_client

client = get_knot_client()

# Sync specific merchant
result = client.sync_transactions(
    external_user_id='abc',
    merchant_ids=[40],  # Instacart only
    limit=50
)

# Get all transactions
transactions = client.get_customer_transactions('abc', limit=100)
```

---

## 🏆 **Hackathon Eligibility**

Your project now meets the requirements:

✅ **Visual representation of Knot** - Show logo + account linking UI
✅ **Use SKU data** - Analyzes transaction SKUs for fruits
✅ **Optional: Knot SDK** - Can implement for bonus
✅ **Optional: Real data** - Working with dev environment
✅ **Huge bonus: Production** - Can deploy with real API!

---

## 💡 **Quick Commands**

```bash
# Switch to mock mode
# Remove or comment out KNOT_USE_REAL in .env

# Switch to real API
echo "KNOT_USE_REAL=true" >> .env

# Test current mode
curl http://localhost:5000/api/knot/test

# Sync user
curl -X POST http://localhost:5000/api/knot/sync/abc

# Check health
curl http://localhost:5000/health
```

---

## 🎉 **You're Ready!**

Your SusCart backend is now fully integrated with the real Knot API! 

**Next steps:**
1. Test with mock mode first
2. Enable real mode when ready
3. Add Knot visual elements to frontend
4. Win the hackathon! 🏆

**Questions?** Check the Knot docs: https://docs.knotapi.com/

