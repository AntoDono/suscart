# Knot API Integration Guide for SusCart

## What is Knot API?

Knot (https://www.useknotapi.com/) is a unified API that connects to various e-commerce and retail platforms to retrieve customer purchase data. Instead of integrating with each platform separately (Shopify, WooCommerce, Square, etc.), you can use Knot's single API to access purchase history from multiple sources.

## Why Use Knot for SusCart?

SusCart needs to understand:
- What fruits customers like to buy
- How often they purchase
- What price ranges they prefer
- When they typically shop

This data powers the recommendation engine to match discounted items with the right customers.

## How SusCart Uses Knot

### 1. Customer Sync
When a new customer signs up or an existing customer needs updating:

```python
# Endpoint: POST /api/knot/sync/:knot_customer_id

# What happens:
# 1. Fetches customer profile from Knot
# 2. Retrieves last 90 days of purchase history
# 3. Analyzes purchase patterns
# 4. Updates/creates customer in SusCart database
# 5. Sets preferences automatically
```

### 2. Purchase Pattern Analysis
The backend automatically analyzes Knot purchase data to determine:

```python
{
  "favorite_fruits": ["apple", "banana", "strawberry"],  # Most purchased
  "purchase_frequency": 0.5,  # Purchases per day (e.g., every 2 days)
  "average_spend": 15.50,     # Average transaction value
  "preferred_discount": 20,    # Average discount on past purchases
  "max_price": 23.25          # Willing to pay (1.5x average)
}
```

### 3. Recommendation Matching
When items get discounted, the system:
1. Checks which customers have matching preferences
2. Creates personalized recommendations
3. Sends WebSocket notifications to those customers

## Mock Mode vs Real Integration

### Mock Mode (Default)
The backend includes `MockKnotAPIClient` which provides:
- Sample customer data
- Fake purchase history
- Full analysis pipeline

This allows development without a real Knot API key.

**When to use:** Development, testing, demos

### Real Integration
To use the actual Knot API:

1. **Sign up for Knot**
   - Visit https://www.useknotapi.com/
   - Create an account
   - Get your API key from the dashboard

2. **Configure Environment**
   ```env
   # In .env file
   KNOT_API_KEY=knot_live_xxxxxxxxxxxxx
   KNOT_API_URL=https://api.useknotapi.com/v1
   ```

3. **Restart Backend**
   ```bash
   python backend/main.py
   ```
   
   You'll see: "🔗 Using real Knot API client"

## Knot API Endpoints Used

### Get Customer
```http
GET https://api.useknotapi.com/v1/customers/{customer_id}
Authorization: Bearer {api_key}
```

Returns:
```json
{
  "id": "KNOT-CUST-1234",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "(555) 123-4567",
  "platform": "shopify",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### Get Customer Purchases
```http
GET https://api.useknotapi.com/v1/customers/{customer_id}/purchases
Authorization: Bearer {api_key}
Query Params:
  - start_date: ISO 8601 date
  - end_date: ISO 8601 date
```

Returns:
```json
{
  "purchases": [
    {
      "transaction_id": "TXN-001",
      "date": "2025-10-15T14:30:00Z",
      "total": 25.50,
      "items": [
        {
          "id": "PROD-123",
          "name": "Organic Apples",
          "type": "apple",
          "category": "fruit",
          "quantity": 3,
          "price": 8.97,
          "discount_percentage": 10
        }
      ]
    }
  ]
}
```

## Testing Knot Integration

### With Mock Client (No API Key)
```bash
# Sync customer from mock data
curl -X POST http://localhost:5000/api/knot/sync/KNOT-CUST-1000

# Response includes analyzed preferences
{
  "message": "Customer synced from Knot",
  "customer": {
    "id": 1,
    "knot_customer_id": "KNOT-CUST-1000",
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "preferences": {
      "favorite_fruits": ["apple", "banana", "strawberry"],
      "purchase_frequency": 0.022,
      "average_spend": 7.95,
      "preferred_discount": 17.5,
      "max_price": 11.92
    }
  }
}
```

### With Real Knot API
```bash
# Set your API key
export KNOT_API_KEY=knot_live_xxxxxxxxxxxxx

# Start server
python backend/main.py

# Sync real customer
curl -X POST http://localhost:5000/api/knot/sync/actual_knot_customer_id
```

## Code Structure

### `knot_integration.py`

```
KnotAPIClient
├── get_customer()              # Fetch customer profile
├── get_customer_purchases()    # Fetch purchase history
├── sync_customer_data()        # Full sync + analysis
├── _analyze_purchase_patterns() # Calculate preferences
└── webhook_handler()           # Handle Knot webhooks

MockKnotAPIClient
├── Inherits from KnotAPIClient
├── _generate_mock_data()       # Create sample data
└── Overrides API calls with mock responses
```

## Webhooks (Future Enhancement)

Knot can send real-time webhooks when:
- Customer makes a purchase → `purchase.created`
- Customer profile updates → `customer.updated`

To enable webhooks:
1. Configure webhook URL in Knot dashboard
2. Add webhook endpoint in `main.py`
3. Use `knot_client.webhook_handler()` to process

Example:
```python
@app.route('/api/knot/webhook', methods=['POST'])
def knot_webhook():
    webhook_data = request.get_json()
    processed = knot_client.webhook_handler(webhook_data)
    
    if processed['type'] == 'new_purchase':
        # Update customer purchase history
        # Regenerate recommendations
        pass
    
    return jsonify({'status': 'received'}), 200
```

## Error Handling

The integration gracefully handles:
- Missing API key → Falls back to mock client
- Network errors → Returns None/empty list
- Invalid customer IDs → Returns 404
- API rate limits → Logs error, continues

## Best Practices

1. **Cache Results**
   - Store customer data in SusCart database
   - Only sync periodically (e.g., daily or on customer login)
   - Don't query Knot API on every request

2. **Handle Missing Data**
   - Not all customers will have Knot IDs
   - Allow manual preference entry
   - Use defaults when purchase history is empty

3. **Privacy**
   - Only sync necessary data
   - Follow GDPR/privacy regulations
   - Allow customers to opt out

4. **Rate Limiting**
   - Knot APIs have rate limits
   - Batch sync operations
   - Use webhooks instead of polling

## Alternatives to Knot

If you don't want to use Knot, you can:

1. **Manual Entry**
   - Customers select preferences during signup
   - Track purchases within SusCart only

2. **Direct Integration**
   - Integrate directly with your store's POS system
   - Connect to Shopify, Square, etc. APIs

3. **Import CSV**
   - Export purchase data from existing system
   - Import into SusCart database

## Summary

**Current State:**
- ✅ Mock Knot client working
- ✅ Purchase pattern analysis complete
- ✅ Recommendation matching implemented
- ✅ Easy switch to real Knot API (just add key)

**To Use Real Knot:**
1. Get API key from https://www.useknotapi.com/
2. Add to `.env`: `KNOT_API_KEY=knot_live_xxx`
3. Restart server

**For Development:**
- Mock mode works perfectly
- No API key needed
- Full functionality available

The integration is designed to work seamlessly whether using mock or real data, allowing you to develop and test without external dependencies.

