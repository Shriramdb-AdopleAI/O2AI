# Docker Deployment Scripts

## Prerequisites
- Docker Desktop installed and running
- Docker Compose v2.x or higher
- At least 4GB RAM available for Docker
- Ports 6379, 8001, and 8080 available

## Quick Start

### 1. Build and Start All Services
```powershell
cd deployment
docker-compose up --build -d
```

### 2. Check Service Status
```powershell
docker-compose ps
```

### 3. View Logs
```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery
docker-compose logs -f frontend
docker-compose logs -f redis
```

### 4. Stop Services
```powershell
docker-compose down
```

### 5. Stop and Remove Volumes (Clean Reset)
```powershell
docker-compose down -v
```

## Service URLs

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Redis**: localhost:6379

## Configuration

### Environment Variables

1. **Docker Compose Variables** (`.env` file):
   - `VITE_API_BASE_URL`: Frontend API endpoint (default: http://localhost:8001)
   - Change this to your server's public IP or domain for production

2. **Backend Variables** (`env.backend` file):
   - Azure OpenAI credentials
   - Database connection strings
   - Epic FHIR configuration
   - Redis connection (automatically configured for Docker)

### Customizing the Deployment

#### Change API URL for Production
Edit `deployment/.env`:
```env
VITE_API_BASE_URL=http://your-server-ip:8001
```

#### Adjust Celery Concurrency
Edit `deployment/docker-compose.yml`, celery service:
```yaml
command: >
  celery -A core.celery_app worker
  --concurrency=8  # Change this number
```

#### Change Exposed Ports
Edit `deployment/docker-compose.yml`:
```yaml
services:
  backend:
    ports:
      - "8001:8000"  # Change left side (host port)
  frontend:
    ports:
      - "8080:80"    # Change left side (host port)
```

## Troubleshooting

### Services Not Starting

1. **Check Docker is running**:
   ```powershell
   docker info
   ```

2. **Check port availability**:
   ```powershell
   netstat -ano | findstr "6379 8001 8080"
   ```

3. **View detailed logs**:
   ```powershell
   docker-compose logs --tail=100
   ```

### Backend Health Check Failing

1. **Check backend logs**:
   ```powershell
   docker-compose logs backend
   ```

2. **Verify environment variables**:
   ```powershell
   docker-compose exec backend env | grep -E "REDIS|AZURE"
   ```

3. **Test health endpoint manually**:
   ```powershell
   docker-compose exec backend wget -qO- http://localhost:8000/api/v1/health
   ```

### Celery Worker Not Processing Tasks

1. **Check Celery logs**:
   ```powershell
   docker-compose logs celery
   ```

2. **Verify Redis connection**:
   ```powershell
   docker-compose exec celery redis-cli -h redis ping
   ```

3. **Check Celery worker status**:
   ```powershell
   docker-compose exec celery celery -A core.celery_app inspect active
   ```

### Redis Connection Issues

1. **Check Redis is running**:
   ```powershell
   docker-compose ps redis
   ```

2. **Test Redis connection**:
   ```powershell
   docker-compose exec redis redis-cli ping
   ```

3. **Check Redis logs**:
   ```powershell
   docker-compose logs redis
   ```

### Frontend Not Loading

1. **Check frontend logs**:
   ```powershell
   docker-compose logs frontend
   ```

2. **Verify nginx is running**:
   ```powershell
   docker-compose exec frontend nginx -t
   ```

3. **Check if files were built**:
   ```powershell
   docker-compose exec frontend ls -la /usr/share/nginx/html
   ```

## Maintenance Commands

### Rebuild Specific Service
```powershell
docker-compose up --build -d backend
```

### Restart Service
```powershell
docker-compose restart backend
```

### Execute Command in Container
```powershell
docker-compose exec backend bash
docker-compose exec celery bash
docker-compose exec frontend sh
```

### View Resource Usage
```powershell
docker stats
```

### Clean Up Unused Resources
```powershell
docker system prune -a
```

## Data Persistence

The following data is persisted in Docker volumes:

- **redis-data**: Redis cache and queue data
- **backend-logs**: Backend application logs
- **celery-logs**: Celery worker logs

The following data is mounted from the host:

- **backend/data**: Uploaded files, templates, tenant data
- **backend/keys**: Epic FHIR private keys (read-only)

## Production Deployment

### Security Checklist

1. ✅ Change default passwords in `env.backend`
2. ✅ Use HTTPS with reverse proxy (nginx/traefik)
3. ✅ Restrict CORS origins in backend
4. ✅ Enable firewall rules
5. ✅ Use secrets management (Docker secrets/Azure Key Vault)
6. ✅ Regular backups of volumes and data directories

### Recommended Production Setup

1. **Use a reverse proxy** (nginx, Traefik, or Caddy) for SSL/TLS
2. **Set up monitoring** (Prometheus + Grafana)
3. **Configure log aggregation** (ELK stack or Azure Monitor)
4. **Enable automatic backups** for volumes and database
5. **Use Docker Swarm or Kubernetes** for high availability

### Example Nginx Reverse Proxy Config

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review this documentation
3. Check Docker and Docker Compose versions
4. Ensure all prerequisites are met
