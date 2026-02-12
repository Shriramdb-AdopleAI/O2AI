# Nginx FQDN Domain Mapping Configuration Guide

This guide explains how to configure nginx to map your FQDN (Fully Qualified Domain Name) to the O2AI Fax Automation frontend and backend services.

## Key Changes Required in nginx.conf

### 1. **Update `server_name` Directive**
Replace `your-domain.com` with your actual FQDN in both HTTP and HTTPS server blocks:

```nginx
server_name your-domain.com www.your-domain.com;
```

**Example:**
```nginx
server_name fax-automation.example.com www.fax-automation.example.com;
```

### 2. **SSL Certificate Paths**
Update the SSL certificate paths to point to your actual certificate files:

```nginx
ssl_certificate /etc/nginx/ssl/your-domain.crt;
ssl_certificate_key /etc/nginx/ssl/your-domain.key;
```

**Example:**
```nginx
ssl_certificate /etc/nginx/ssl/fax-automation.example.com.crt;
ssl_certificate_key /etc/nginx/ssl/fax-automation.example.com.key;
```

### 3. **Upstream Server Configuration**

#### If running services directly on the host:
```nginx
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:5173;
}
```

#### If using Docker Compose:
```nginx
upstream backend {
    server backend:8000;  # Docker service name
}

upstream frontend {
    server frontend:80;   # Docker service name and port
}
```

#### If using Docker with host network:
```nginx
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:5173;
}
```

## Installation Steps

### 1. Install Nginx
```bash
sudo apt-get update
sudo apt-get install -y nginx
```

### 2. Copy Configuration File
```bash
sudo cp /home/azureuser/Deploy/O2AI-Fax_Automation/deployment/nginx.conf /etc/nginx/sites-available/o2ai-fax-automation
```

### 3. Edit Configuration
```bash
sudo nano /etc/nginx/sites-available/o2ai-fax-automation
```

**Make these changes:**
- Replace `your-domain.com` with your actual FQDN
- Update SSL certificate paths
- Adjust upstream servers based on your deployment (Docker vs direct)

### 4. Create SSL Certificate Directory (if needed)
```bash
sudo mkdir -p /etc/nginx/ssl
```

### 5. Install SSL Certificates
Place your SSL certificate files in `/etc/nginx/ssl/`:
- Certificate file: `your-domain.crt` (or `.pem`)
- Private key file: `your-domain.key`

**For Let's Encrypt (recommended):**
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 6. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/o2ai-fax-automation /etc/nginx/sites-enabled/
```

### 7. Test Configuration
```bash
sudo nginx -t
```

### 8. Reload Nginx
```bash
sudo systemctl reload nginx
# or
sudo systemctl restart nginx
```

## Configuration Summary

### What This Configuration Does:

1. **HTTP to HTTPS Redirect**: Automatically redirects all HTTP traffic to HTTPS
2. **Frontend Routing**: Serves the React frontend at the root path (`/`)
3. **Backend API Routing**: Proxies all `/api/` requests to the FastAPI backend
4. **SSL/TLS**: Enforces secure connections with modern SSL protocols
5. **Security Headers**: Adds security headers for protection
6. **File Upload Support**: Allows up to 200MB file uploads
7. **WebSocket Support**: Supports WebSocket connections for HMR (Hot Module Replacement)

### Port Mapping:

- **Frontend**: Accessible via domain root (`https://your-domain.com`)
- **Backend API**: Accessible via `/api/` path (`https://your-domain.com/api/`)
- **Health Check**: Available at `/health`

## Alternative: Separate Subdomains

If you prefer to use separate subdomains:
- Frontend: `https://your-domain.com` → serves React app
- Backend API: `https://api.your-domain.com` → serves FastAPI

Uncomment the alternative server block in the nginx.conf file and configure accordingly.

## Troubleshooting

### Check Nginx Status
```bash
sudo systemctl status nginx
```

### View Nginx Logs
```bash
sudo tail -f /var/log/nginx/o2ai-error.log
sudo tail -f /var/log/nginx/o2ai-access.log
```

### Test Upstream Connectivity
```bash
# Test backend
curl http://localhost:8000/

# Test frontend
curl http://localhost:5173/
```

### Verify DNS Resolution
```bash
nslookup your-domain.com
dig your-domain.com
```

## Important Notes

1. **DNS Configuration**: Ensure your domain's DNS A record points to your server's IP address
2. **Firewall**: Make sure ports 80 and 443 are open in your firewall
3. **Backend CORS**: Update your FastAPI backend CORS settings to allow your domain
4. **Frontend API URL**: Update `VITE_API_BASE_URL` in frontend `.env` to use your domain:
   ```
   VITE_API_BASE_URL=https://your-domain.com/api
   ```

## Example Complete Configuration

For domain `fax-automation.example.com`:

```nginx
server {
    listen 443 ssl http2;
    server_name fax-automation.example.com www.fax-automation.example.com;
    
    ssl_certificate /etc/letsencrypt/live/fax-automation.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fax-automation.example.com/privkey.pem;
    
    # ... rest of configuration
}
```

