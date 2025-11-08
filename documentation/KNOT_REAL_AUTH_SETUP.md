# 🔐 Real Knot Authentication Setup Guide

## ✅ **What's Been Implemented**

Real Knot authentication is now set up! Here's what was added:

### **Backend:**
1. ✅ **Webhook Endpoint** (`/api/knot/webhook`)
   - Handles `account_linked` events
   - Handles `new_transactions` events
   - Handles `updated_transactions` events
   - Automatically syncs customer data when webhooks arrive

2. ✅ **Session Creation** (already existed)
   - `/api/knot/session/create` - Creates Knot sessions

3. ✅ **Merchant Listing** (already existed)
   - `/api/knot/merchants` - Lists available merchants

### **Frontend:**
1. ✅ **Knot SDK Integration**
   - Added Knot SDK script to `index.html`
   - TypeScript types for Knot SDK

2. ✅ **Knot Link Widget**
   - Merchant connection buttons
   - OAuth flow integration
   - Real-time connection status

3. ✅ **Fallback Mode**
   - Test mode (tunnel) still available for development

---

## 🚀 **How to Use**

### **Step 1: Configure Environment**

Make sure your `.env` file has Knot credentials:

```bash
# For Development
KNOT_USE_REAL=true
KNOT_ENV=dev
KNOT_CLIENT_ID=your_dev_client_id
KNOT_SECRET=your_dev_secret

# For Production
KNOT_USE_REAL=true
KNOT_ENV=prod
KNOT_CLIENT_ID=your_prod_client_id
KNOT_SECRET=your_prod_secret
```

### **Step 2: Start Backend**

```bash
cd backend
python main.py
```

You should see:
```
📡 Using Knot API: https://development.knotapi.com (with auth)
✅ Created session: ...
```

### **Step 3: Start Frontend**

```bash
cd frontend
npm run dev
```

### **Step 4: Test Real Authentication**

1. **Open Customer Portal:**
   ```
   http://localhost:5173/#user
   ```

2. **Click a Merchant Button:**
   - You'll see buttons for Amazon, Instacart, Walmart, etc.
   - Click one (e.g., "Amazon")

3. **OAuth Flow:**
   - Knot SDK opens a modal
   - User logs into their merchant account
   - User authorizes Knot to access transactions
   - Modal closes automatically

4. **Automatic Sync:**
   - Knot sends webhook to your backend
   - Backend syncs transactions
   - Customer data updates automatically
   - User sees their real purchase history!

---

## 🔄 **How It Works**

### **Flow Diagram:**

```
1. User clicks "Connect Amazon" button
   ↓
2. Frontend calls: POST /api/knot/session/create
   ↓
3. Backend creates Knot session → returns session_id
   ↓
4. Frontend initializes Knot Link widget with session_id
   ↓
5. Knot Link opens OAuth modal
   ↓
6. User logs into Amazon account
   ↓
7. User authorizes Knot
   ↓
8. Knot sends webhook: POST /api/knot/webhook
   {
     "event": "account_linked",
     "external_user_id": "123"
   }
   ↓
9. Backend receives webhook → updates customer
   ↓
10. Knot automatically syncs transactions
    ↓
11. Knot sends webhook: POST /api/knot/webhook
    {
      "event": "new_transactions",
      "external_user_id": "123"
    }
    ↓
12. Backend syncs transactions → updates preferences
    ↓
13. Frontend refreshes → shows real data!
```

---

## 🧪 **Testing with Dev Environment**

For development/testing, Knot provides test credentials:

### **Test Credentials:**
- **Username:** `user_good_transactions`
- **Password:** `pass_good`

### **What Happens:**
1. User clicks merchant button
2. Knot Link modal opens
3. User enters test credentials
4. Knot generates 205 test transactions
5. Webhook fires with new transactions
6. Your backend syncs them automatically

---

## 📋 **Webhook Events**

Your backend handles these webhook events:

### **1. `account_linked`**
```json
{
  "event": "account_linked",
  "external_user_id": "123"
}
```
- **Action:** Updates customer's `last_active` timestamp

### **2. `new_transactions`**
```json
{
  "event": "new_transactions",
  "external_user_id": "123"
}
```
- **Action:** 
  - Syncs transactions from Knot
  - Updates customer preferences
  - Sends WebSocket notification to customer

### **3. `updated_transactions`**
```json
{
  "event": "updated_transactions",
  "external_user_id": "123"
}
```
- **Action:** Re-syncs transactions and updates preferences

---

## 🔧 **Configuration**

### **Webhook URL Setup**

In production, you need to configure your webhook URL in Knot dashboard:

```
https://your-domain.com/api/knot/webhook
```

For local development, use a tool like:
- **ngrok:** `ngrok http 3000`
- **localtunnel:** `lt --port 3000`

Then set webhook URL in Knot dashboard to:
```
https://your-ngrok-url.ngrok.io/api/knot/webhook
```

---

## 🐛 **Troubleshooting**

### **Issue: "Knot SDK not loaded"**
- **Fix:** Refresh the page. The SDK loads from CDN.

### **Issue: "Failed to create session"**
- **Check:** Are your `KNOT_CLIENT_ID` and `KNOT_SECRET` correct?
- **Check:** Is `KNOT_ENV` set to `dev` or `prod`?

### **Issue: "No merchants showing"**
- **Check:** Is `/api/knot/merchants` endpoint working?
- **Check:** Are you using dev/prod environment? (tunnel doesn't support merchants endpoint)

### **Issue: "Webhook not received"**
- **Check:** Is your webhook URL configured in Knot dashboard?
- **Check:** Is your server accessible from the internet? (use ngrok for local dev)

---

## 📚 **Next Steps**

1. **Configure Webhook URL** in Knot dashboard
2. **Test with real merchant accounts** (your own Amazon/Instacart)
3. **Monitor webhook logs** in backend console
4. **Set up production environment** with production Knot credentials

---

## 🎯 **Summary**

✅ Real Knot authentication is **fully implemented**!

- Users can connect their merchant accounts via OAuth
- Transactions sync automatically via webhooks
- Each user sees their own unique data
- No more shared test data!

The old tunnel mode is still available as a fallback for testing.

