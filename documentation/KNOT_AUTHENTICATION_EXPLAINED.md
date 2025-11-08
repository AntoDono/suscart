# 🔐 Knot Authentication: Current State vs. Real Production

## 🎯 **Current Status**

### **What's Working Now:**
- ✅ Backend can call Knot API
- ✅ Can fetch transaction data from Knot
- ✅ Can analyze transactions to extract preferences
- ✅ Can display transaction history in UI

### **What's NOT Working (The Issues You Found):**

1. **All Users See Same Data** ❌
   - **Why:** You're using `knot.tunnel.tel` endpoint
   - **Problem:** This is a **public test endpoint** that returns the **same test data** for ANY `external_user_id`
   - **Result:** Whether you use "abc", "user123", or "alice", you get identical transactions

2. **No Real Authentication** ❌
   - **Why:** Currently just passing a string ID (like "abc") to Knot
   - **Problem:** In real life, users need to **log into their actual merchant accounts** (Amazon, Instacart, etc.)
   - **Result:** No way to verify the user actually owns those accounts

---

## 🔍 **How It Currently Works (Tunnel Mode)**

### **Current Flow:**
```
1. User enters "abc" in frontend
2. Frontend calls: POST /api/knot/sync/abc
3. Backend calls: Knot API with external_user_id="abc"
4. Knot returns: SAME test data (regardless of "abc" or "xyz")
5. Backend stores: Customer with knot_customer_id="abc"
6. All customers see: Identical transaction data
```

### **Why This Happens:**
- `knot.tunnel.tel` is a **public demo endpoint**
- It's designed for testing without authentication
- It returns **hardcoded test data** for demonstration
- It doesn't actually connect to real merchant accounts

---

## 🚀 **How Real Production Works**

### **Real Authentication Flow:**

```
1. User clicks "Connect Your Amazon Account" button
   ↓
2. Knot SDK (JavaScript) opens a modal/popup
   ↓
3. User logs into their Amazon account (OAuth)
   ↓
4. Amazon asks: "Allow Knot to access your orders?"
   ↓
5. User clicks "Allow"
   ↓
6. Knot receives OAuth token from Amazon
   ↓
7. Knot stores: Your user ID → Amazon token
   ↓
8. Knot sends webhook to your backend:
   {
     "external_user_id": "your_customer_123",
     "event": "account_linked",
     "merchant": "amazon"
   }
   ↓
9. Your backend stores: Customer 123 → Knot linked
   ↓
10. Knot automatically syncs transactions from Amazon
    ↓
11. Knot sends webhook with real transaction data:
    {
      "external_user_id": "your_customer_123",
      "transactions": [...real Amazon orders...]
    }
    ↓
12. Your backend updates customer preferences
    ↓
13. Customer sees THEIR real purchase history
```

### **Key Differences:**

| Current (Tunnel) | Real Production |
|-----------------|-----------------|
| Just pass string ID | User must authenticate |
| Same data for everyone | Unique data per user |
| No OAuth flow | OAuth with merchants |
| Test endpoint | Production endpoint |
| No account verification | Verified merchant accounts |

---

## 🛠️ **What You Need for Real Authentication**

### **Step 1: Integrate Knot SDK**

Knot provides a JavaScript SDK that handles the OAuth flow:

```html
<!-- In your frontend -->
<script src="https://cdn.knotapi.com/knot-link.js"></script>
```

### **Step 2: Create Session First**

Before showing the connect button, create a Knot session:

```javascript
// Frontend: Create session
const response = await fetch('/api/knot/session/create', {
  method: 'POST',
  body: JSON.stringify({
    external_user_id: currentCustomerId.toString()
  })
});

const { session_id } = await response.json();
```

### **Step 3: Initialize Knot Link Widget**

```javascript
// Frontend: Show connect button
const knotLink = new KnotLink({
  sessionId: session_id,
  merchantId: 44, // Amazon, or let user choose
  onSuccess: (result) => {
    console.log('Account connected!', result);
    // Refresh customer data
    loadCustomerData(currentCustomerId);
  },
  onError: (error) => {
    console.error('Connection failed:', error);
  }
});

// Show the widget
knotLink.open();
```

### **Step 4: Handle Webhooks**

Knot will send webhooks to your backend when:
- Account is linked
- New transactions arrive
- Transactions are updated

```python
# Backend: Webhook endpoint
@app.route('/api/knot/webhook', methods=['POST'])
def knot_webhook():
    data = request.get_json()
    external_user_id = data.get('external_user_id')
    event = data.get('event')
    
    if event == 'account_linked':
        # Update customer record
        customer = Customer.query.filter_by(
            knot_customer_id=external_user_id
        ).first()
        customer.knot_linked = True
        db.session.commit()
    
    elif event == 'new_transactions':
        # Sync new transactions
        transactions = data.get('transactions', [])
        sync_transactions_to_customer(external_user_id, transactions)
    
    return jsonify({'status': 'ok'}), 200
```

### **Step 5: Update Frontend UI**

Replace the simple "Enter Knot ID" input with:

```tsx
// Frontend: Real connect flow
const connectMerchantAccount = async (merchantId: number) => {
  // 1. Create session
  const sessionRes = await fetch('/api/knot/session/create', {
    method: 'POST',
    body: JSON.stringify({
      external_user_id: customerId.toString()
    })
  });
  const { session_id } = await sessionRes.json();
  
  // 2. Initialize Knot Link
  const knotLink = new KnotLink({
    sessionId: session_id,
    merchantId: merchantId,
    onSuccess: () => {
      alert('Account connected! Syncing transactions...');
      // Backend will receive webhook and update data
    }
  });
  
  // 3. Open modal
  knotLink.open();
};

// UI: Show merchant buttons
<button onClick={() => connectMerchantAccount(44)}>
  Connect Amazon Account
</button>
<button onClick={() => connectMerchantAccount(40)}>
  Connect Instacart Account
</button>
```

---

## 📋 **Implementation Checklist**

### **For Real Authentication:**

- [ ] **Install Knot SDK** in frontend
  ```bash
  npm install @knotapi/knot-link
  ```

- [ ] **Add session creation endpoint** (already exists: `/api/knot/session/create`)

- [ ] **Update frontend** to use Knot Link widget instead of text input

- [ ] **Add webhook endpoint** to receive real-time updates

- [ ] **Switch to production Knot endpoint** in `.env`:
  ```bash
  KNOT_ENV=prod
  KNOT_CLIENT_ID=your_prod_client_id
  KNOT_SECRET=your_prod_secret
  ```

- [ ] **Test with real merchant accounts** (your own Amazon/Instacart)

- [ ] **Handle OAuth callbacks** from Knot

---

## 🎯 **Why Only Knot ID is Needed Now**

Currently, you're just passing an `external_user_id` string because:

1. **Tunnel mode doesn't require auth** - It's a public test endpoint
2. **No real accounts** - You're not actually connecting to merchant accounts
3. **Demo mode** - Designed for quick testing without setup

### **In Real Production:**
- User must **authenticate with their merchant account**
- Knot handles the OAuth flow
- Your `external_user_id` is just **your identifier** for that user
- Knot maps: `your_user_id` → `merchant_oauth_token` → `real_transactions`

---

## 🔧 **Quick Fix for Current Issue**

If you want different data per user **right now** (without real auth):

### **Option 1: Use Dev Environment**
```bash
# .env
KNOT_USE_REAL=true
KNOT_ENV=dev
KNOT_CLIENT_ID=your_dev_client_id
KNOT_SECRET=your_dev_secret
```

Then create sessions and use test credentials:
- `user_good_transactions` / `pass_good` (generates 205 transactions)

### **Option 2: Mock Different Data**
Modify `knot_integration.py` to return different mock data based on `external_user_id`:

```python
def sync_transactions(self, external_user_id, ...):
    if external_user_id == "alice":
        return alice_mock_transactions
    elif external_user_id == "bob":
        return bob_mock_transactions
    # etc.
```

---

## 📚 **Resources**

- **Knot SDK Docs:** https://docs.knotapi.com/sdk/web
- **Knot Link Widget:** https://docs.knotapi.com/products/transaction-link
- **Webhook Guide:** https://docs.knotapi.com/webhooks
- **OAuth Flow:** https://docs.knotapi.com/authentication

---

## 🎬 **Summary**

**Current State:**
- ✅ Backend integration works
- ❌ All users see same data (tunnel endpoint limitation)
- ❌ No real authentication (just string IDs)

**For Real Production:**
- ✅ Need Knot SDK integration
- ✅ Need OAuth flow with merchants
- ✅ Need webhook handling
- ✅ Need production Knot credentials

**The `external_user_id` is YOUR identifier** - Knot uses it to map to the user's actual merchant accounts after they authenticate.

