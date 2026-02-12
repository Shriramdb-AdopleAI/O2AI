# Azure Cosmos DB for PostgreSQL - Firewall Configuration

## Problem
Connection timeout error when connecting to Cosmos DB for PostgreSQL:
```
Connection timed out
Is the server running on that host and accepting TCP/IP connections?
```

## Solution: Add Firewall Rule

### Step 1: Access Azure Portal
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Cosmos DB for PostgreSQL cluster: **c-o2ai-fax-automation**

### Step 2: Add Firewall Rule
1. In the left menu, click on **Networking** or **Connection security**
2. Under **Firewall rules**, click **Add client IP** or **+ Add**
3. Your current IP address: **172.190.184.110**
4. Add a rule name (e.g., "Development Server")
5. Click **Save**

### Step 3: Allow Azure Services (if running on Azure VM)
If you're connecting from an Azure VM or service:
1. Enable **"Allow Azure services and resources to access this server"**
2. This allows connections from other Azure services

### Step 4: Test Connection Again
```bash
cd backend
python test_db_connection.py
```

## Alternative: Use Azure CLI

If you have Azure CLI installed:

```bash
# Login to Azure
az login

# Add firewall rule for your current IP
az cosmosdb postgresql firewall-rule create \
  --resource-group <your-resource-group> \
  --cluster-name c-o2ai-fax-automation \
  --name "Development-Server" \
  --start-ip-address 172.190.184.110 \
  --end-ip-address 172.190.184.110

# Or allow all Azure services
az cosmosdb postgresql firewall-rule create \
  --resource-group <your-resource-group> \
  --cluster-name c-o2ai-fax-automation \
  --name "AllowAzureServices" \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

## Verify Connection

After adding the firewall rule, wait 1-2 minutes for it to propagate, then test:

```bash
cd backend
python test_db_connection.py
```

## Important Notes

- **IP Changes**: If your public IP changes, you'll need to update the firewall rule
- **Security**: Only add IPs you trust. Don't use 0.0.0.0/0 in production
- **Propagation**: Firewall rule changes can take 1-2 minutes to take effect

## Connection String Format

Your connection string should be:
```
host=c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com
port=5432
dbname=o2ai
user=citus
password=Product@2026
sslmode=require
```

