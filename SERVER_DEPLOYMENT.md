# Server Deployment Documentation

This document consolidates all server deployment documentation for the O2AI Fax Automation system.

## Table of Contents

1. [Quick Start Guide](#quick-start-guide)
2. [Docker Deployment](#docker-deployment)
3. [Azure Cosmos DB for PostgreSQL Setup](#azure-cosmos-db-for-postgresql-setup)
4. [Epic OAuth Configuration](#epic-oauth-configuration)
5. [Environment Variables](#environment-variables)
6. [Database Migration](#database-migration)
7. [Nginx Configuration](#nginx-configuration)
8. [Production Deployment](#production-deployment)

---

## Quick Start Guide

### Prerequisites

- Docker service running in the background
- Python 3.12+ installed
- Node.js 20+ and npm installed
- Required environment variables configured

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the backend server:**
   ```bash
   python -B main.py
   ```
   Server runs on `http://localhost:8000`

### Redis Setup

**For Windows:**
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

**For Linux:**
```bash
sudo apt install redis-server
sudo service redis-server start
```

### Celery Worker Setup

**For Windows:**
```bash
backend\start_celery_worker_windows.bat
```

**For Linux:**
```bash
cd backend
./start_celery_worker.sh
```

### Celery Beat (Optional - for Bulk Processing)

**For Bulk Processing:** If you need the bulk processing feature that checks Azure Blob every 5 minutes, start Celery Beat in a **new Terminal**:

**Windows:**
```bash
cd backend
celery -A core.celery_app beat --loglevel=info
```

**Linux:**
```bash
cd backend
celery -A core.celery_app beat --loglevel=info
```

**Note:** Celery Beat must run in a separate terminal on Windows. Keep both the worker and beat terminals running for bulk processing to work.

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the dev server:**
   ```bash
   npm run dev
   ```
   Frontend runs on `http://localhost:5173`

### Default Login Credentials

- **Admin:** `admin` / `admin123`
- **Test User:** `testuser` / `test123`

---

## Docker Deployment

### Docker Compose (Recommended)

The project includes a complete Docker Compose setup for production deployment.

**Location:** `deployment/docker-compose.yml`

**Services:**
- **Redis:** Message broker for Celery (port 6379)
- **Backend:** FastAPI application (port 8000)
- **Celery:** Background task worker
- **Frontend:** React application (port 5173, served on 80 in container)

### Deploy with Docker Compose

1. **Navigate to deployment directory:**
   ```bash
   cd deployment
   ```

2. **Configure environment variables:**
   - Update `env.backend` with your configuration
   - Set `VITE_API_BASE_URL` for frontend (defaults to `http://backend:8000` in Docker)

3. **Start all services:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **View specific service logs:**
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f celery
   docker-compose logs -f frontend
   docker-compose logs -f redis
   ```

6. **Stop services:**
   ```bash
   docker-compose down
   ```

7. **Rebuild and restart:**
   ```bash
   docker-compose up -d --build
   ```

### Individual Docker Containers

**Backend:**
```bash
cd backend
docker build -t ocr-backend -f ../deployment/backend/Dockerfile .
docker run -p 8000:8000 --env-file ../deployment/env.backend ocr-backend
```

**Frontend:**
```bash
cd frontend
docker build -t ocr-frontend -f ../deployment/frontend/Dockerfile --build-arg VITE_API_BASE_URL=http://localhost:8000 .
docker run -p 5173:80 ocr-frontend
```

---

## Azure Cosmos DB for PostgreSQL Setup

### Cluster Details

**Cluster Name:** c-o2ai-fax-automation  
**Host:** c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com  
**Port:** 5432  
**Database:** postgres (or o2ai)  
**User:** citus  
**Password:** Product@2026  

**Note:** The application uses environment variables `PGHOST`, `PGUSER`, `PGPORT`, `PGDATABASE`, and `PGPASSWORD` for database connection.

### Configuration Steps

1. **Update Environment Variables**

   Update `deployment/env.backend` or create `.env` in backend directory:

   ```env
   # Azure Cosmos DB for PostgreSQL Configuration
   PGHOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
   PGUSER=citus
   PGPORT=5432
   PGDATABASE=postgres
   PGPASSWORD="Fax@12345"
   
   # Alternative format (for SQLAlchemy)
   POSTGRES_HOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
   POSTGRES_PORT=5432
   POSTGRES_DB=postgres
   POSTGRES_USER=citus
   POSTGRES_PASSWORD=Fax@12345
   
   # Connection string (URL-encode special characters in password)
   DATABASE_URL=postgresql://citus:%40Fax%4012345@o2aifaxautomationdatabaseserver.postgres.database.azure.com:5432/postgres?sslmode=require
   ```

2. **Important Notes:**
   - **SSL Required:** Azure Cosmos DB for PostgreSQL requires SSL connections. The `sslmode=require` parameter is included in the connection string.
   - **Password Encoding:** Special characters in passwords (like `@`) must be URL-encoded in connection strings (`@` becomes `%40`)
   - **Credentials:** Keep your `PGPASSWORD` secure. Never commit it to version control.
   - **Connection Pooling:** The application uses SQLAlchemy with connection pooling (pool_size=10, max_overflow=20)

3. **Database Setup**

   The application automatically creates tables on startup. Tables include:
   - `users` - User authentication
   - `user_sessions` - Active user sessions
   - `ground_truth` - OCR validation data
   - `null_field_tracking` - Required field tracking
   - `processed_files` - Complete processed file results

4. **Verify Connection**

   ```bash
   cd backend
   python -c "from models.database import engine; print('Connection successful!' if engine.connect() else 'Connection failed')"
   ```

   Or use the test script:
   ```bash
   python test_db_connection.py
   ```

### Firewall Configuration

#### Problem
Connection timeout error when connecting to Cosmos DB for PostgreSQL:
```
Connection timed out
Is the server running on that host and accepting TCP/IP connections?
```

#### Solution: Add Firewall Rule

**Step 1: Access Azure Portal**
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Cosmos DB for PostgreSQL cluster: **c-o2ai-fax-automation**

**Step 2: Add Firewall Rule**
1. In the left menu, click on **Networking** or **Connection security**
2. Under **Firewall rules**, click **Add client IP** or **+ Add**
3. Add your current IP address
4. Add a rule name (e.g., "Development Server")
5. Click **Save**

**Step 3: Allow Azure Services (if running on Azure VM)**
If you're connecting from an Azure VM or service:
1. Enable **"Allow Azure services and resources to access this server"**
2. This allows connections from other Azure services

**Step 4: Test Connection**
```bash
cd backend
python test_db_connection.py
```

#### Alternative: Use Azure CLI

```bash
# Login to Azure
az login

# Add firewall rule for your current IP
az cosmosdb postgresql firewall-rule create \
  --resource-group <your-resource-group> \
  --cluster-name c-o2ai-fax-automation \
  --name "Development-Server" \
  --start-ip-address <your-ip-address> \
  --end-ip-address <your-ip-address>

# Or allow all Azure services
az cosmosdb postgresql firewall-rule create \
  --resource-group <your-resource-group> \
  --cluster-name c-o2ai-fax-automation \
  --name "AllowAzureServices" \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

#### Connection String Format

```
host=o2aifaxautomationdatabaseserver.postgres.database.azure.com
port=5432
dbname=postgres
user=citus
password=Fax@12345
sslmode=require
```

#### Important Notes

- **IP Changes:** If your public IP changes, you'll need to update the firewall rule
- **Security:** Only add IPs you trust. Don't use 0.0.0.0/0 in production
- **Propagation:** Firewall rule changes can take 1-2 minutes to take effect
- **Password Special Characters:** Use URL encoding in connection strings (`@` = `%40`, `#` = `%23`, etc.)

### Troubleshooting

- Verify the username and password are correct
- Ensure SSL mode is enabled in your connection string
- Check Azure firewall rules allow your IP address
- Verify the database exists on the server
- Check connection timeout settings (default: 10 seconds)
- Verify network connectivity to Azure

---

## Epic OAuth Configuration

### Critical: Epic OAuth Configuration

Epic requires **EXACT** matching of redirect URIs. The redirect URI in your `.env` file must match **EXACTLY** (character-by-character) what's registered in Epic App Orchard.

### Current Production Configuration

**Base URL:** `https://o2ai-fax-automation.centralus.cloudapp.azure.com`  
**Client ID:** `8a3e9014-7a92-43bb-ae3a-62eabcf2642e`  
**JWKS URL:** `https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json`

### Frontend `.env` File

Create or update `/frontend/.env` with these variables:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Epic OAuth Configuration
VITE_EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
VITE_EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
VITE_EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
VITE_EPIC_SCOPES=openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create
```

### Backend `.env` File

Create or update `/backend/.env` or `deployment/env.backend` with these variables:

```env
# Epic OAuth Configuration
EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_FHIR_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_CLIENT_SECRET="zUlfi9rCFjjL9324YULQ4ObvaJiDXZAJw9LZTFwFRjmI3CYuev1BXIVZVO5he1E9qOpamQjVo4IHpr1PnEuLJg=="
EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_SCOPES="openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create"

# Epic FHIR Private Key for JWKS (Backend Systems Authentication)
EPIC_FHIR_PRIVATE_KEY_PATH=/home/azureuser/Deploy/O2AI-Fax_Automation/backend/keys/epic_fhir_private_key.pem

# Base URL for JWKS endpoint - MUST match the domain Epic is configured to use
BASE_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com

# JWKS URL - MUST match what's configured in Epic App Orchard
EPIC_FHIR_JWKS_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json

# Fallback IDs for testing (if needed)
EPIC_FALLBACK_ENCOUNTER_ID=eH9J7LxX2Qf0R3ABC123
EPIC_FALLBACK_PATIENT_ID=erXuFYUfucBZaryVksYEcMg3
```

### Important Notes

1. **Redirect URI:**
   - Must match EXACTLY what's in Epic App Orchard
   - Check if it should have a trailing slash or not
   - Current production: `https://o2ai-fax-automation.centralus.cloudapp.azure.com/` (with trailing slash)
   - **Copy the exact value from Epic App Orchard**

2. **Client ID:**
   - Current: `8a3e9014-7a92-43bb-ae3a-62eabcf2642e`
   - Must be the exact value (no spaces, no quotes)

3. **Authorization URL:**
   - Default: `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`
   - Your Epic instance might have a different URL
   - Check Epic App Orchard documentation for your instance

4. **Audience (aud):**
   - Required parameter for Epic OAuth
   - Default: `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4`
   - This is the FHIR server endpoint that the token will be used for
   - Must match your Epic FHIR server URL

5. **Scopes:**
   - Current: `openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create`
   - Epic may require different scopes
   - Check what scopes are approved in Epic App Orchard
   - Separate multiple scopes with spaces

6. **JWKS Endpoint:**
   - The backend serves JWKS at `/.well-known/jwks.json`
   - This is required for Backend Systems Authentication (JWT-based)
   - Must be accessible from Epic's servers
   - Configured in Epic App Orchard

### Verification Steps

1. **Check Epic App Orchard:**
   - Log into Epic App Orchard
   - Find your application
   - Copy the exact redirect URI (check for trailing slash)
   - Copy the Client ID
   - Verify app is approved/active
   - Verify JWKS URL is configured correctly

2. **Update `.env` files:**
   - Frontend: Update `VITE_EPIC_REDIRECT_URI` to match Epic App Orchard exactly
   - Backend: Update `EPIC_REDIRECT_URI` to match exactly
   - Both must be identical

3. **Restart servers:**
   ```bash
   # Stop both frontend and backend servers
   # Then restart them
   cd frontend && npm run dev
   cd backend && python -B main.py
   ```

4. **Test JWKS Endpoint:**
   ```bash
   curl https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json
   ```

### Common Issues

**Issue: "Something went wrong trying to authorize the client"**

**Solution:**
1. Check redirect URI matches EXACTLY (including trailing slash)
2. Verify Client ID is correct
3. Ensure app is approved in Epic App Orchard
4. Check browser console for the exact authorization URL
5. Compare redirect URI in URL with Epic App Orchard

**Issue: Redirect URI mismatch**

**Solution:**
- Epic is very strict about redirect URI matching
- Check Epic App Orchard for the exact format
- Common mistake: trailing slash difference
- Common mistake: http vs https
- Common mistake: www vs non-www

**Issue: JWKS endpoint not accessible**

**Solution:**
1. Verify the endpoint is publicly accessible
2. Check Nginx configuration routes `/.well-known/jwks.json` to backend
3. Verify the private key file exists at the configured path
4. Check backend logs for errors when serving JWKS

---

## Environment Variables

### Backend Environment Variables

Create `.env` file in `backend/` directory or update `deployment/env.backend`:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_openai_api_key
AZURE_OPENAI_ENDPOINT=https://eastus2.api.cognitive.microsoft.com/
OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure Document Intelligence (OCR)
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_document_intelligence_key
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://ocr-processor-engine.cognitiveservices.azure.com/

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=documentblobstorage01;AccountKey=...;EndpointSuffix=core.windows.net"
AZURE_STORAGE_ACCOUNT_URL=https://documentblobstorage01.blob.core.windows.net

# Database Configuration (Azure Cosmos DB for PostgreSQL)
PGHOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
PGUSER=citus
PGPORT=5432
PGDATABASE=postgres
PGPASSWORD="Fax@12345"

# Alternative PostgreSQL format
POSTGRES_HOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=citus
POSTGRES_PASSWORD=Fax@12345

# Epic OAuth Configuration
EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_FHIR_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_CLIENT_SECRET="your-epic-client-secret-here"
EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_SCOPES="openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create"

# Epic FHIR Private Key for JWKS
EPIC_FHIR_PRIVATE_KEY_PATH=/path/to/backend/keys/epic_fhir_private_key.pem

# Base URL and JWKS
BASE_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com
EPIC_FHIR_JWKS_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json

# Admin Email Configuration
EMAIL=["krish@elevancesystems.com","test@o2.ai"]
```

### Frontend Environment Variables

Create `.env` file in `frontend/` directory:

```env
# API Base URL
VITE_API_BASE_URL=http://localhost:8000

# Epic OAuth Configuration
VITE_EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
VITE_EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
VITE_EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
VITE_EPIC_SCOPES=openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create
```

**Note:** For Docker deployment, set `VITE_API_BASE_URL` as a build argument in the Dockerfile.

---

## Database Migration

### Automatic Table Creation

The application automatically creates all required tables on startup using SQLAlchemy. No manual migration is required.

**Tables Created:**
- `users` - User authentication and management
- `user_sessions` - Active user session tracking
- `ground_truth` - OCR validation and training data
- `null_field_tracking` - Required field null tracking
- `processed_files` - Complete processed file results with deduplication

### Manual Migration (if needed)

If you need to migrate from SQLite or another database:

1. **Install Dependencies:**
   ```bash
   pip install psycopg2-binary
   ```

2. **Set Environment Variables:**
   ```bash
   export PGHOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com
   export PGUSER=citus
   export PGPORT=5432
   export PGDATABASE=postgres
   export PGPASSWORD="Fax@12345"
   ```

3. **Run Migration Script:**
   ```bash
   cd backend
   python migrate_to_postgres.py
   ```

4. **Verify Migration:**
   The migration script will automatically verify the data. You should see output like:
   ```
   ✓ users: Source=5, PostgreSQL=5
   ✓ user_sessions: Source=7, PostgreSQL=7
   ✓ ground_truth: Source=372, PostgreSQL=372
   ```

### Database Schema

The application uses PostgreSQL with JSONB columns for flexible data storage:
- `ground_truth.metadata_json` - JSONB for metadata
- `null_field_tracking.null_field_names` - JSONB array
- `null_field_tracking.all_extracted_fields` - JSONB for extracted data
- `processed_files.processed_data` - JSONB for complete processed results

---

## Nginx Configuration

### Production Setup

The project includes an Nginx configuration file for production deployment.

**Location:** `deployment/nginx.conf`

### Configuration Details

**Server Name:** `o2ai-fax-automation.centralus.cloudapp.azure.com`  
**Port:** 80 (HTTP)  
**Client Max Body Size:** 500M (for large file uploads)

### Routing

- **Frontend (Root):** `http://frontend` (localhost:5173)
- **Backend API:** `http://backend` (localhost:8000) at `/api/`
- **JWKS Endpoint:** `/.well-known/jwks.json` → Backend
- **Health Check:** `/health` → Backend

### Setup Instructions

1. **Install Nginx:**
   ```bash
   sudo apt update
   sudo apt install nginx
   ```

2. **Copy Configuration:**
   ```bash
   sudo cp deployment/nginx.conf /etc/nginx/sites-available/o2ai-fax-automation
   sudo ln -s /etc/nginx/sites-available/o2ai-fax-automation /etc/nginx/sites-enabled/
   ```

3. **Test Configuration:**
   ```bash
   sudo nginx -t
   ```

4. **Restart Nginx:**
   ```bash
   sudo systemctl restart nginx
   ```

5. **Enable Auto-start:**
   ```bash
   sudo systemctl enable nginx
   ```

### SSL/HTTPS Configuration (Recommended)

For production, configure SSL certificates:

1. **Install Certbot:**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   ```

2. **Obtain Certificate:**
   ```bash
   sudo certbot --nginx -d o2ai-fax-automation.centralus.cloudapp.azure.com
   ```

3. **Auto-renewal:**
   Certbot automatically sets up auto-renewal. Test with:
   ```bash
   sudo certbot renew --dry-run
   ```

### Important Notes

- **File Upload Size:** Configured for 500M maximum upload size
- **WebSocket Support:** Enabled for Vite HMR in development
- **Timeouts:** Extended timeouts (300s) for large file processing
- **CORS:** Handled by FastAPI backend, not Nginx

---

## Production Deployment

### Security Best Practices

1. **Use strong passwords** for all services
2. **Restrict network access** - only allow necessary IPs
3. **Use SSL/TLS** for all database connections
4. **Regular backups** - set up automated backups
5. **Environment variables** - never commit secrets to version control
6. **Firewall rules** - only allow trusted IPs
7. **HTTPS** - use SSL certificates for production
8. **Private keys** - secure Epic FHIR private key file

### Connection Pooling

The application uses SQLAlchemy connection pooling:
- **Pool Size:** 10 connections
- **Max Overflow:** 20 connections
- **Connection Timeout:** 10 seconds
- **Statement Timeout:** 30 seconds

### Monitoring

- Monitor application logs:
  ```bash
  docker-compose logs -f backend
  docker-compose logs -f celery
  ```
- Monitor database performance
- Set up alerts for critical errors
- Regular health checks at `/health` endpoint

### Backup Strategy

**PostgreSQL Backup:**
```bash
# Backup to file
pg_dump -h o2aifaxautomationdatabaseserver.postgres.database.azure.com \
  -U citus \
  -d postgres \
  -F c \
  -f backup_$(date +%Y%m%d_%H%M%S).dump

# Or with connection string
PGPASSWORD="Fax@12345" pg_dump \
  -h o2aifaxautomationdatabaseserver.postgres.database.azure.com \
  -U citus \
  -d postgres \
  > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore:**
```bash
# From SQL file
PGPASSWORD="Fax@12345" psql \
  -h o2aifaxautomationdatabaseserver.postgres.database.azure.com \
  -U citus \
  -d postgres \
  < backup_20231205_120000.sql

# From custom format
pg_restore -h o2aifaxautomationdatabaseserver.postgres.database.azure.com \
  -U citus \
  -d postgres \
  backup_20231205_120000.dump
```

### Performance Optimization

```sql
-- Create additional indexes for better query performance
CREATE INDEX idx_ground_truth_created_at ON ground_truth(created_at);
CREATE INDEX idx_ground_truth_tenant_id ON ground_truth(tenant_id);
CREATE INDEX idx_analysis_cache_created_at ON analysis_cache(created_at);
CREATE INDEX idx_processed_files_tenant_id ON processed_files(tenant_id);
CREATE INDEX idx_processed_files_created_at ON processed_files(created_at);

-- Analyze tables for query optimization
ANALYZE users;
ANALYZE user_sessions;
ANALYZE ground_truth;
ANALYZE null_field_tracking;
ANALYZE processed_files;
```

### Health Checks

**Backend Health:**
```bash
curl http://localhost:8000/
curl http://localhost:8000/.well-known/jwks.json
```

**Frontend Health:**
```bash
curl http://localhost:5173/
```

**Database Health:**
```bash
cd backend
python test_db_connection.py
```

---

## API Documentation

- **Interactive Docs:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Root Endpoint:** `http://localhost:8000/`
- **Health Check:** `http://localhost:8000/health`

---

## Troubleshooting

### Backend Issues

- Check Azure API credentials in `deployment/env.backend`
- Verify Python version (3.12+)
- Check logs in terminal output or Docker logs
- Verify database connection
- Check Redis is running
- Verify Epic OAuth configuration

### Frontend Issues

- Verify backend is running on port 8000
- Check `VITE_API_BASE_URL` in frontend `.env`
- Clear browser cache if needed
- Check browser console for errors
- Verify Epic OAuth environment variables

### Database Connection Issues

- Verify PostgreSQL/Cosmos DB is running
- Check firewall rules (for Azure)
- Verify credentials (PGPASSWORD, POSTGRES_PASSWORD)
- Check SSL mode is enabled (for Azure)
- Verify database exists
- Check connection timeout settings
- Verify special characters in password are properly encoded

### Epic OAuth Issues

- Verify redirect URI matches EXACTLY
- Check Client ID is correct
- Ensure app is approved in Epic App Orchard
- Check browser console for authorization URL
- Compare redirect URI with Epic App Orchard
- Verify JWKS endpoint is accessible
- Check private key file exists and is readable

### Docker Issues

- Verify Docker is running
- Check `docker-compose logs` for errors
- Ensure environment variables are set in `env.backend`
- Verify ports are not already in use
- Check Docker network connectivity

### Celery Issues

- Verify Redis is running and accessible
- Check Celery worker logs
- Ensure Redis connection string is correct
- Verify tasks are being queued properly
- Check for task timeouts

---

## Support

For detailed documentation:
- Backend: See `backend/README.md`
- Frontend: See `frontend/README.md`
- API: Visit `http://localhost:8000/docs`

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Azure Cosmos DB for PostgreSQL Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/)
- [Epic App Orchard](https://apporchard.epic.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
