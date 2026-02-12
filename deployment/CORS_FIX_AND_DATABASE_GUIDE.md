# CORS Issue Fixed - Summary & Database Connection Guide

## ✅ CORS Issue - FIXED!

### Problem
The frontend was getting CORS errors and then a 404 error with double `/api` in the URL:
- Error: `POST http://localhost:8080/api/api/v1/auth/login 404 (Not Found)`

### Root Cause
The `VITE_API_BASE_URL` was set to `/api`, but the frontend code was adding `/api/v1` to it, resulting in `/api/api/v1`.

### Solution Applied
Changed `docker-compose.yml` to set `VITE_API_BASE_URL` to empty string:
```yaml
args:
  - VITE_API_BASE_URL=
```

This allows the frontend code to construct the correct path: `${apiBaseUrl}/api/v1` → `/api/v1`

### How Nginx Proxy Works
1. Frontend makes request to: `/api/v1/auth/login`
2. Nginx intercepts requests to `/api` and proxies them to `backend:8000`
3. Backend receives: `http://backend:8000/api/v1/auth/login`
4. No CORS issues because everything goes through the same origin (localhost:8080)

---

## 🗄️ Database Connection Status

### Current Configuration
Your `deployment/env.backend` file has Azure PostgreSQL configured:

```env
PGHOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
PGUSER=citus
PGPORT=5432
PGDATABASE=postgres
PGPASSWORD="Fax@12345"
```

### Current Issue
The backend is experiencing database connection timeouts:
```
connection to server at "c-faxautomation.vahdzggsuxl2b7.postgres.cosmos.azure.com" 
(20.80.72.173), port 5432 failed: timeout expired
```

### Why This Happens
1. **Azure Firewall**: Azure PostgreSQL has a firewall that blocks connections by default
2. **Docker Network**: The container's IP address is not in the allowed list
3. **SSL Required**: Azure PostgreSQL requires SSL connections

---

## 🔧 How to Fix Database Connection

### Option 1: Allow Docker Container IP (Recommended for Testing)

1. **Find your public IP**:
   ```powershell
   (Invoke-WebRequest -Uri "https://api.ipify.org").Content
   ```

2. **Add to Azure PostgreSQL Firewall**:
   - Go to Azure Portal → Your PostgreSQL Server
   - Navigate to "Connection security" or "Networking"
   - Add a firewall rule:
     - Name: `Docker-Local`
     - Start IP: Your public IP
     - End IP: Your public IP
   - Click "Save"

3. **Restart backend container**:
   ```powershell
   cd deployment
   docker-compose restart backend
   ```

### Option 2: Add SSL Parameters to Connection String

Update `deployment/env.backend` to include SSL parameters:

```env
# Add this line (uncomment the DATABASE_URL line)
DATABASE_URL=postgresql://citus:Fax%4012345@o2aifaxautomationdatabaseserver.postgres.database.azure.com:5432/postgres?sslmode=require

# Or keep the PG* variables and add:
PGSSLMODE=require
```

Then rebuild:
```powershell
cd deployment
docker-compose up --build -d backend
```

### Option 3: Allow All Azure Services (Production - Use with Caution)

In Azure Portal:
1. Go to your PostgreSQL server
2. Navigate to "Connection security"
3. Toggle "Allow access to Azure services" to ON
4. Save

This allows all Azure services to connect, which includes your Docker containers if they're running on Azure.

### Option 4: Use Azure Private Endpoint (Production - Most Secure)

For production deployments, use Azure Private Endpoint to connect securely without exposing the database to the internet.

---

## 🧪 Testing Database Connection

### Test from Docker Container
```powershell
# Test database connection from backend container
docker-compose exec backend python -c "from models.database import engine; print(engine.connect())"
```

### Check Backend Logs
```powershell
cd deployment
docker-compose logs backend --tail=50
```

Look for:
- ✅ Success: "Database tables created successfully!"
- ❌ Error: "timeout expired" or "connection refused"

---

## 📋 Current Status Summary

### ✅ Working
- Docker containers: All running
- Frontend: Accessible at http://localhost:8080
- Backend API: Accessible at http://localhost:8001
- Nginx Proxy: Working correctly
- Redis: Healthy
- CORS: Fixed!

### ⚠️ Needs Attention
- Database Connection: Timing out (firewall issue)

---

## 🚀 Next Steps

1. **Fix Database Connection** (Choose one option above)
2. **Test Login** - Once database is connected:
   - Go to http://localhost:8080
   - Try logging in
   - Default credentials should be created automatically

3. **Verify Everything Works**:
   ```powershell
   cd deployment
   .\status.ps1
   docker-compose logs backend --tail=20
   ```

---

## 💡 Quick Commands

### Restart Backend (After Config Changes)
```powershell
cd deployment
docker-compose restart backend
```

### Rebuild Backend (After Code Changes)
```powershell
cd deployment
docker-compose up --build -d backend
```

### View All Logs
```powershell
cd deployment
docker-compose logs -f
```

### Check Database Connection
```powershell
docker-compose exec backend python -c "import psycopg2; conn = psycopg2.connect(host='o2aifaxautomationdatabaseserver.postgres.database.azure.com', user='citus', password='Fax@12345', database='postgres', sslmode='require'); print('Connected!'); conn.close()"
```

---

## 📞 Support

If you continue to have issues:

1. Check Azure PostgreSQL firewall settings
2. Verify the database credentials are correct
3. Ensure SSL is enabled if required
4. Check backend logs: `docker-compose logs backend`

---

## 🎉 Success Criteria

You'll know everything is working when:
- ✅ Frontend loads at http://localhost:8080
- ✅ Login page appears
- ✅ You can log in successfully
- ✅ Backend logs show: "Database tables created successfully!"
- ✅ No timeout errors in logs
