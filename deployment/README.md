# O2AI Fax Automation - Docker Deployment

This directory contains all the necessary files to deploy the O2AI Fax Automation system using Docker.

## 🚀 Quick Start

### Option 1: Using PowerShell Scripts (Recommended for Windows)

```powershell
# Deploy all services
.\deploy.ps1

# Check service status
.\status.ps1

# View logs
.\logs.ps1

# Stop all services
.\stop.ps1
```

### Option 2: Using Docker Compose Directly

```powershell
# Build and start all services
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📋 Prerequisites

- ✅ Docker Desktop for Windows (latest version)
- ✅ Docker Compose v2.x or higher
- ✅ At least 4GB RAM available for Docker
- ✅ Ports 6379, 8001, and 8080 available

## 🏗️ Architecture

The deployment consists of 4 services:

1. **Redis** (Port 6379) - Cache and message broker
2. **Backend** (Port 8001) - FastAPI application
3. **Celery** - Async task worker
4. **Frontend** (Port 8080) - React + Nginx

## 🔧 Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main orchestration file |
| `.env` | Docker Compose environment variables |
| `env.backend` | Backend application configuration |
| `backend/Dockerfile` | Backend container definition |
| `frontend/Dockerfile` | Frontend container definition |
| `celery-entrypoint.sh` | Celery worker startup script |

## 🌐 Access URLs

After deployment, access the application at:

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **API Redoc**: http://localhost:8001/redoc

## 📝 PowerShell Scripts

### deploy.ps1
Builds and starts all Docker services with pre-flight checks.

```powershell
.\deploy.ps1
```

### status.ps1
Shows detailed status of all services including health checks.

```powershell
.\status.ps1
```

### logs.ps1
View logs from services.

```powershell
# All services (last 100 lines)
.\logs.ps1

# Follow all services
.\logs.ps1 -Follow

# Specific service
.\logs.ps1 -Service backend

# Follow specific service
.\logs.ps1 -Service backend -Follow
```

### stop.ps1
Stops all running services.

```powershell
.\stop.ps1
```

## 🔍 Troubleshooting

### Services won't start

1. Check Docker is running:
   ```powershell
   docker info
   ```

2. Check port availability:
   ```powershell
   netstat -ano | findstr "6379 8001 8080"
   ```

3. View logs:
   ```powershell
   .\logs.ps1 -Follow
   ```

### Backend health check failing

```powershell
# Check backend logs
docker-compose logs backend

# Test health endpoint
docker-compose exec backend wget -qO- http://localhost:8000/api/v1/health
```

### Celery not processing tasks

```powershell
# Check Celery logs
docker-compose logs celery

# Verify Redis connection
docker-compose exec celery redis-cli -h redis ping
```

### Clean restart

```powershell
# Stop and remove everything
docker-compose down -v

# Rebuild and start
.\deploy.ps1
```

## 🔐 Production Deployment

For production deployment:

1. **Update `.env` file**:
   ```env
   VITE_API_BASE_URL=http://your-server-ip:8001
   ```

2. **Secure `env.backend`**:
   - Change default passwords
   - Use Azure Key Vault for secrets
   - Update database connection strings

3. **Enable HTTPS**:
   - Use a reverse proxy (nginx, Traefik, Caddy)
   - Configure SSL certificates
   - Update CORS settings

4. **Configure firewall**:
   - Only expose necessary ports
   - Use Azure NSG or Windows Firewall

5. **Set up monitoring**:
   - Enable Docker logging
   - Configure health checks
   - Set up alerts

## 📚 Documentation

- [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) - Comprehensive deployment guide
- [NGINX_FQDN_SETUP.md](./NGINX_FQDN_SETUP.md) - Nginx configuration for production

## 🆘 Support

If you encounter issues:

1. Check service status: `.\status.ps1`
2. View logs: `.\logs.ps1 -Follow`
3. Review [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
4. Ensure all prerequisites are met

## 📦 Data Persistence

Data is persisted in:

- **Docker Volumes**:
  - `redis-data` - Redis cache
  - `backend-logs` - Backend logs
  - `celery-logs` - Celery logs

- **Host Mounts**:
  - `../backend/data` - Uploaded files and templates
  - `../backend/keys` - Epic FHIR keys (read-only)

## 🔄 Updates

To update the application:

```powershell
# Pull latest code
git pull

# Rebuild and restart
docker-compose up --build -d

# Or use the deploy script
.\deploy.ps1
```

## 🧹 Cleanup

```powershell
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Clean up Docker system
docker system prune -a
```
