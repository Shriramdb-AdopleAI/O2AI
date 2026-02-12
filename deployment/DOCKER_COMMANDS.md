# Docker Quick Reference Commands

## ✅ DEPLOYMENT SUCCESSFUL!

All services are now running. Here are the commands you need:

---

## 🚀 Starting Services

### Option 1: First Time or After Changes (Build + Start)
```powershell
cd deployment
docker-compose up --build -d
```

### Option 2: Start Existing Containers (No Build)
```powershell
cd deployment
docker-compose up -d
```

### Option 3: Use the PowerShell Script
```powershell
cd deployment
.\deploy.ps1
```

---

## 🛑 Stopping Services

### Stop All Services
```powershell
cd deployment
docker-compose down
```

### Stop and Remove Volumes (Clean Reset)
```powershell
cd deployment
docker-compose down -v
```

### Use the PowerShell Script
```powershell
cd deployment
.\stop.ps1
```

---

## 📊 Checking Status

### View Service Status
```powershell
cd deployment
docker-compose ps
```

### View Detailed Status (PowerShell Script)
```powershell
cd deployment
.\status.ps1
```

### Check Container Health
```powershell
docker ps
```

---

## 📝 Viewing Logs

### All Services (Follow Mode)
```powershell
cd deployment
docker-compose logs -f
```

### Specific Service
```powershell
cd deployment
docker-compose logs -f backend
docker-compose logs -f celery
docker-compose logs -f frontend
docker-compose logs -f redis
```

### Last 100 Lines
```powershell
cd deployment
docker-compose logs --tail=100
```

### Using PowerShell Script
```powershell
cd deployment
.\logs.ps1 -Follow
.\logs.ps1 -Service backend -Follow
```

---

## 🔧 Troubleshooting Commands

### Fix "Container Name Already in Use" Error
```powershell
cd deployment
docker-compose down
docker rm -f ocr-redis ocr-backend ocr-celery ocr-frontend
docker-compose up -d
```

### Restart Specific Service
```powershell
cd deployment
docker-compose restart backend
docker-compose restart celery
```

### Rebuild Specific Service
```powershell
cd deployment
docker-compose up --build -d backend
```

### View Container Resource Usage
```powershell
docker stats
```

### Execute Command Inside Container
```powershell
docker-compose exec backend bash
docker-compose exec celery bash
docker-compose exec frontend sh
```

### Check Health Status
```powershell
docker inspect --format='{{.State.Health.Status}}' ocr-backend
docker inspect --format='{{.State.Health.Status}}' ocr-redis
```

---

## 🌐 Access URLs

After deployment, access your application at:

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **API Redoc**: http://localhost:8001/redoc
- **Redis**: localhost:6379

---

## 🧹 Cleanup Commands

### Remove All Stopped Containers
```powershell
docker container prune
```

### Remove Unused Images
```powershell
docker image prune -a
```

### Remove Unused Volumes
```powershell
docker volume prune
```

### Complete System Cleanup
```powershell
docker system prune -a --volumes
```

---

## 🔄 Update Application

### After Code Changes
```powershell
cd deployment
docker-compose down
docker-compose up --build -d
```

### Quick Restart (No Code Changes)
```powershell
cd deployment
docker-compose restart
```

---

## 📦 Backup & Restore

### Backup Volumes
```powershell
# Backup Redis data
docker run --rm -v o2ai-fax-automation_redis-data:/data -v ${PWD}:/backup alpine tar czf /backup/redis-backup.tar.gz /data

# Backup backend data
Copy-Item -Recurse ..\backend\data .\backups\data-$(Get-Date -Format 'yyyyMMdd')
```

### Export Container as Image
```powershell
docker commit ocr-backend my-backend-backup:latest
docker save -o backend-backup.tar my-backend-backup:latest
```

---

## 🐛 Debug Commands

### Check Container Logs (Last 50 Lines)
```powershell
docker logs --tail=50 ocr-backend
docker logs --tail=50 ocr-celery
```

### Check Environment Variables
```powershell
docker-compose exec backend env
```

### Test Backend Health
```powershell
curl http://localhost:8001/api/v1/health
```

### Test Redis Connection
```powershell
docker-compose exec redis redis-cli ping
```

### Check Celery Workers
```powershell
docker-compose exec celery celery -A core.celery_app inspect active
```

---

## 💡 Pro Tips

1. **Always use `docker-compose down` before `docker-compose up`** to avoid conflicts
2. **Use `-d` flag** to run containers in detached mode (background)
3. **Use `--build` flag** when you've made code changes
4. **Check logs** if services aren't working: `docker-compose logs -f`
5. **Use PowerShell scripts** for easier management: `.\deploy.ps1`, `.\status.ps1`, `.\logs.ps1`

---

## 📞 Quick Help

If something goes wrong:

1. Check status: `docker-compose ps`
2. View logs: `docker-compose logs -f`
3. Restart: `docker-compose restart`
4. Clean restart: `docker-compose down && docker-compose up -d`
5. Nuclear option: `docker-compose down -v && docker-compose up --build -d`

---

## Current Status

✅ All services are running!
- Redis: Healthy
- Backend: Healthy  
- Celery: Started
- Frontend: Started

Access your application at: **http://localhost:8080**
