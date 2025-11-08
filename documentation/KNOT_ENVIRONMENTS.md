# 🔗 Knot API Environments Guide

## 📊 **Available Environments**

SusCart supports **4 modes** for Knot integration:

| Mode | Use Case | Auth Required | User ID |
|------|----------|---------------|---------|
| **Mock** | Development/Offline | ❌ No | user123, user456 |
| **Tunnel** | Testing with real API | ❌ No | abc |
| **Dev** | Development environment | ✅ Yes | Your test users |
| **Prod** | Production | ✅ Yes | Real customer IDs |

---

## 🎯 **Quick Start by Environment**

### **1. Mock Mode (Default - No Internet)**

Perfect for: Development, offline demos, controlled testing

```bash
# Don't create .env file, or set:
KNOT_USE_REAL=false
```

**Run:**
```bash
python backend/main.py

# Test with:
curl -X POST http://localhost:5000/api/knot/sync/user123
```

**Features:**
- ✅ No API key needed
- ✅ Works offline
- ✅ Hardcoded fruit purchase data
- ✅ Fast and predictable

---

### **2. Tunnel Mode (Test API - No Auth)**

Perfect for: Testing real API without credentials, hackathon demos

```bash
# Create .env file
cat > .env << EOF
KNOT_USE_REAL=true
KNOT_ENV=tunnel
EOF
```

**Run:**
```bash
python backend/main.py

# You'll see:
📡 Using Knot API: https://knot.tunnel.tel (no auth needed)

# Test with Knot's test user:
curl -X POST http://localhost:5000/api/knot/sync/abc
```

**Features:**
- ✅ Real Knot API endpoint
- ✅ No authentication needed
- ✅ Real transaction data
- ✅ Test user 'abc' available

---

### **3. Development Mode (Dev API - With Auth)**

Perfect for: Development with your own test data

```bash
# Create .env file
cat > .env << EOF
KNOT_USE_REAL=true
KNOT_ENV=dev
KNOT_CLIENT_ID=
KNOT_SECRET=
EOF
```

**Run:**
```bash
python backend/main.py

# You'll see:
📡 Using Knot API: https://development.knotapi.com (with auth)

# Test with your user ID:
curl -X POST http://localhost:5000/api/knot/sync/YOUR_USER_ID
```

**Features:**
- ✅ Development environment
- ✅ Your test users
- ✅ Full API features
- ✅ Safe for testing

---

### **4. Production Mode (Prod API - With Auth)** 🚀

Perfect for: Live application with real customers

```bash
# Create .env file
cat > .env << EOF
KNOT_USE_REAL=true
KNOT_ENV=prod
KNOT_CLIENT_ID=your_production_client_id
KNOT_SECRET=your_production_secret
EOF
```

**Run:**
```bash
python backend/main.py

# You'll see:
📡 Using Knot API: https://api.knotapi.com (with auth)

# Sync real customer:
curl -X POST http://localhost:5000/api/knot/sync/REAL_CUSTOMER_ID \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'
```

**Features:**
- ✅ Production Knot API
- ✅ Real customer data
- ✅ Live transactions
- ✅ Production credentials

---

## 🔧 **Environment Variable Reference**

### **KNOT_USE_REAL**
- `false` (default) - Use mock data
- `true` - Use real Knot API

### **KNOT_ENV**
- `tunnel` (default) - https://knot.tunnel.tel (no auth)
- `dev` - https://development.knotapi.com (with auth)
- `prod` - https://api.knotapi.com (with auth)

### **KNOT_CLIENT_ID**
- Your Knot client ID
- Default provided for dev/tunnel testing

### **KNOT_SECRET**
- Your Knot secret
- Default provided for dev/tunnel testing

### **KNOT_API_URL** (Optional)
- Manually override API URL
- Overrides KNOT_ENV setting

---

## 📝 **Complete .env Examples**

### **For Hackathon Demo (Tunnel)**
```env
KNOT_USE_REAL=true
KNOT_ENV=tunnel
```

### **For Development (Dev)**
```env
KNOT_USE_REAL=true
KNOT_ENV=dev
KNOT_CLIENT_ID=your_client_id_here
KNOT_SECRET=your_secret_here
```

### **For Production**
```env
KNOT_USE_REAL=true
KNOT_ENV=prod
KNOT_CLIENT_ID=your_prod_client_id
KNOT_SECRET=your_prod_secret
DATABASE_URL=postgresql://user:pass@localhost/suscart
FLASK_ENV=production
FLASK_DEBUG=False
```

---

## 🧪 **Testing Each Environment**

### **Test Mock:**
```bash
# No .env needed
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/user123
```

### **Test Tunnel:**
```bash
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=tunnel" > .env
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/abc
```

### **Test Dev:**
```bash
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=dev" > .env
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/abc
```

### **Test Prod:**
```bash
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=prod" > .env
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/YOUR_CUSTOMER_ID
```

---

## 🔄 **Switching Environments**

### **Quick Switch Commands:**

```bash
# Switch to Mock
echo "KNOT_USE_REAL=false" > .env

# Switch to Tunnel
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=tunnel" > .env

# Switch to Dev
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=dev" > .env

# Switch to Prod
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=prod" > .env

# Then restart server
python backend/main.py
```

---

## 🎯 **Which Environment Should I Use?**

### **For Your Hackathon:**
→ **Tunnel Mode** ✅

**Why:**
- ✅ Real API integration to show judges
- ✅ No auth setup needed
- ✅ Works immediately
- ✅ Real transaction data
- ✅ Knot approved for hackathons

```bash
echo -e "KNOT_USE_REAL=true\nKNOT_ENV=tunnel" > .env
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/abc
```

### **For Local Development:**
→ **Mock Mode** ✅

**Why:**
- ✅ Works offline
- ✅ Fast
- ✅ Predictable data
- ✅ No API limits

```bash
# No .env needed
python backend/main.py
curl -X POST http://localhost:5000/api/knot/sync/user123
```

### **For Production Deployment:**
→ **Prod Mode** ✅

**Why:**
- ✅ Real customer data
- ✅ Production credentials
- ✅ Live transactions

```bash
# Configure production credentials
KNOT_ENV=prod
KNOT_CLIENT_ID=your_prod_id
KNOT_SECRET=your_prod_secret
```

---

## 🔐 **Getting Production Credentials**

To use production Knot API:

1. **Sign up at Knot:**
   - Visit https://www.knotapi.com/
   - Create production account

2. **Get Credentials:**
   - Dashboard → API Keys
   - Copy Client ID and Secret

3. **Configure:**
   ```bash
   echo -e "KNOT_USE_REAL=true\nKNOT_ENV=prod\nKNOT_CLIENT_ID=your_id\nKNOT_SECRET=your_secret" > .env
   ```

4. **Test:**
   ```bash
   python backend/main.py
   curl -X POST http://localhost:5000/api/knot/test
   ```

---

## 📊 **Comparison Table**

| Feature | Mock | Tunnel | Dev | Prod |
|---------|------|--------|-----|------|
| Internet Required | ❌ | ✅ | ✅ | ✅ |
| Auth Required | ❌ | ❌ | ✅ | ✅ |
| Real Data | ❌ | ✅ | ✅ | ✅ |
| Test Users | user123 | abc | Custom | Real |
| Rate Limits | ❌ | Maybe | ✅ | ✅ |
| Cost | Free | Free | Free | Paid |
| Best For | Dev | Demo | Testing | Production |

---

## 🚨 **Troubleshooting**

### **"Using MOCK client" when I want real:**
```bash
# Make sure KNOT_USE_REAL is set
echo "KNOT_USE_REAL=true" >> .env
```

### **401 Unauthorized:**
```bash
# Check credentials for dev/prod
echo "KNOT_CLIENT_ID=your_id" >> .env
echo "KNOT_SECRET=your_secret" >> .env
```

### **404 Not Found:**
```bash
# Check environment is correct
echo "KNOT_ENV=tunnel" >> .env  # or dev/prod
```

### **Connection Error:**
```bash
# Check internet connection
# Try tunnel mode first (simplest)
echo "KNOT_ENV=tunnel" >> .env
```

---

## 💡 **Pro Tips**

1. **Start with Tunnel** - Easiest to test
2. **Use Mock for development** - Faster, offline
3. **Test with Dev before Prod** - Safer
4. **Monitor rate limits** - Especially in prod
5. **Log API calls** - For debugging

---

## 📞 **Quick Command Reference**

```bash
# Check current configuration
cat .env

# Test connection
curl http://localhost:5000/api/knot/test

# View server logs
python backend/main.py  # Watch for 📡 line

# Sync user
curl -X POST http://localhost:5000/api/knot/sync/USER_ID

# Check health
curl http://localhost:5000/health
```

---

**You're all set to use any Knot environment!** 🎉

Choose the right environment for your use case and configure `.env` accordingly!

