# Azure PostgreSQL Setup Guide

## Changes Made

### 1. Uninstalled Local PostgreSQL
Local PostgreSQL has been removed from the system using:
```bash
sudo apt-get remove --purge postgresql postgresql-* -y
```

### 2. Updated Database Connection Configuration

The following files have been updated to use Azure PostgreSQL:

#### [backend/models/database.py](backend/models/database.py)
- Changed `DATABASE_URL` default from local `localhost:5432` to Azure PostgreSQL server
- Connection string now points to: `o2aifaxautomationdatabaseserver.postgres.database.azure.com`
- SSL mode is enabled (`sslmode=require`)

#### [deployment/env.backend](deployment/env.backend)
- Added `DATABASE_URL` environment variable with Azure PostgreSQL connection string
- Added individual PostgreSQL configuration variables:
  - `POSTGRES_HOST`: o2aifaxautomationdatabaseserver.postgres.database.azure.com
  - `POSTGRES_PORT`: 5432
  - `POSTGRES_DB`: o2ai_fax_automation
  - `POSTGRES_USER`: username@o2aifaxautomationdatabaseserver
  - `POSTGRES_PASSWORD`: your_password_here

#### [backend/migrate_to_postgres.py](backend/migrate_to_postgres.py)
- Updated default connection parameters to use Azure PostgreSQL server
- Added SSL mode requirement for Azure connections

## Configuration Steps

### 1. Update Environment Variables

Update the following environment variables in `deployment/env.backend`:

```env
POSTGRES_USER=your_username@o2aifaxautomationdatabaseserver
POSTGRES_PASSWORD=your_actual_password
DATABASE_URL=postgresql://your_username@o2aifaxautomationdatabaseserver:your_password@o2aifaxautomationdatabaseserver.postgres.database.azure.com:5432/o2ai_fax_automation?sslmode=require
```

### 2. Azure PostgreSQL Server Details

**Server Name:** o2aifaxautomationdatabaseserver  
**Host:** o2aifaxautomationdatabaseserver.postgres.database.azure.com  
**Port:** 5432  
**Database:** o2ai_fax_automation  
**Username Format:** username@o2aifaxautomationdatabaseserver  

### 3. Connection String Format

For Azure PostgreSQL, the username must include the server name:
```
username@o2aifaxautomationdatabaseserver
```

### 4. Database Setup

Before running the application, ensure:

1. **Create the database** (if not already created):
   ```sql
   CREATE DATABASE o2ai_fax_automation;
   ```

2. **Run migrations** using the updated `migrate_to_postgres.py`:
   ```bash
   cd backend
   python migrate_to_postgres.py
   ```

3. **Verify connection**:
   ```bash
   python -c "from models.database import engine; print('Connection successful!' if engine.connect() else 'Connection failed')"
   ```

## Important Notes

- **SSL Required:** Azure PostgreSQL requires SSL connections. The `sslmode=require` parameter is included in the connection string.
- **Credentials:** Keep your `POSTGRES_PASSWORD` secure. Never commit it to version control.
- **Alternative:** Use environment variables instead of hardcoding credentials.
- **Testing:** Before deploying, test the connection with the credentials you set up in Azure.

## Troubleshooting

If you encounter connection issues:

1. Verify the username includes the server name: `username@o2aifaxautomationdatabaseserver`
2. Ensure SSL mode is enabled in your connection string
3. Check Azure firewall rules allow your IP address
4. Verify the database `o2ai_fax_automation` exists on the server
5. Test connection manually:
   ```bash
   psql "postgresql://user@server:password@server.postgres.database.azure.com:5432/o2ai_fax_automation?sslmode=require"
   ```

## Running the Application

To start the backend with Azure PostgreSQL:

```bash
cd backend
export DATABASE_URL="postgresql://username@o2aifaxautomationdatabaseserver:password@o2aifaxautomationdatabaseserver.postgres.database.azure.com:5432/o2ai_fax_automation?sslmode=require"
python main.py
```

Or use the environment file:
```bash
cd deployment
docker-compose up
```
