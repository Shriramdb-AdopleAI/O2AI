# Docker Container Merge - Backend Services

## Overview
The Docker setup has been consolidated to merge three separate containers (backend, celery, redis) into a single unified **backend** container.

## What Changed

### Before:
- **3 separate containers:**
  - `ocr-redis` - Redis server
  - `ocr-backend` - FastAPI backend
  - `ocr-celery` - Celery worker

### After:
- **1 unified container:**
  - `backend` - Contains all three services managed by supervisord

## Architecture

The new `backend` container runs three processes simultaneously using **supervisord**:

1. **Redis** - Runs on localhost:6379 inside the container
2. **Backend API** - FastAPI application on port 8000
3. **Celery Worker** - Async task processing

### Process Management
All processes are managed by supervisord with the following priorities:
- **Priority 1**: Redis (starts first)
- **Priority 2**: Backend API (starts after Redis)
- **Priority 3**: Celery Worker (starts last)

## Files Modified

1. **`deployment/backend/Dockerfile`**
   - Added Redis server installation
   - Added supervisord installation
   - Configured to run supervisord as the main process
   - Increased health check start period to 60s

2. **`deployment/backend/supervisord.conf`** (NEW)
   - Configuration for managing all three processes
   - Separate log files for each service
   - Auto-restart enabled for all services

3. **`deployment/docker-compose.yml`**
   - Removed `redis` service
   - Removed `celery` service
   - Updated `backend` service configuration
   - Changed container name from `ocr-backend` to `backend`
   - Added Redis port exposure (6379) for debugging
   - Updated environment variables (REDIS_HOST=localhost)

## How to Use

### Build and Start
```bash
cd deployment
docker-compose up --build -d
```

### View Logs
```bash
# All services
docker logs -f backend

# Individual service logs (inside container)
docker exec backend tail -f /app/logs/backend.log
docker exec backend tail -f /app/logs/celery.log
docker exec backend tail -f /app/logs/redis.log
docker exec backend tail -f /app/logs/supervisord.log
```

### Check Service Status
```bash
# Check supervisord status
docker exec backend supervisorctl status

# Expected output:
# backend    RUNNING   pid X, uptime 0:XX:XX
# celery     RUNNING   pid X, uptime 0:XX:XX
# redis      RUNNING   pid X, uptime 0:XX:XX
```

### Restart Individual Services
```bash
# Restart specific service without restarting container
docker exec backend supervisorctl restart backend
docker exec backend supervisorctl restart celery
docker exec backend supervisorctl restart redis
```

### Stop and Remove
```bash
docker-compose down
```

## Ports Exposed

- **8001** → Backend API (mapped to container port 8000)
- **6379** → Redis (optional, for external debugging)
- **8080** → Frontend

## Volumes

- `redis-data` - Redis persistence
- `backend-logs` - All service logs
- `../backend/data` - Application data
- `../backend/keys` - Application keys (read-only)

## Benefits

1. **Simplified Deployment** - Single container instead of three
2. **Reduced Network Overhead** - Internal communication via localhost
3. **Easier Management** - One container to monitor
4. **Lower Resource Usage** - Shared base image and dependencies
5. **Faster Startup** - No inter-container dependencies

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs backend

# Check supervisord logs
docker exec backend cat /app/logs/supervisord.log
```

### Service not running
```bash
# Check status
docker exec backend supervisorctl status

# Start specific service
docker exec backend supervisorctl start <service_name>
```

### Redis connection issues
```bash
# Test Redis inside container
docker exec backend redis-cli ping
# Should return: PONG
```

### Backend API not responding
```bash
# Check health endpoint
curl http://localhost:8001/api/v1/health

# Check backend logs
docker exec backend tail -f /app/logs/backend.log
```

## Notes

- All services share the same environment variables from `env.backend`
- Redis data is persisted in the `redis-data` volume
- Logs are separated by service in `/app/logs/`
- Health check waits 60 seconds before starting (to allow all services to initialize)
