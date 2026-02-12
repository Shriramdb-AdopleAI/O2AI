#!/usr/bin/env python3
"""Test PostgreSQL connection to Azure."""

import os
import sys
from urllib.parse import quote_plus

# Load environment variables
from dotenv import load_dotenv
load_dotenv('../deployment/env.backend')

def get_current_ip():
    """Get current public IP address."""
    try:
        import urllib.request
        ip = urllib.request.urlopen('https://ifconfig.me').read().decode('utf-8').strip()
        return ip
    except:
        return None

POSTGRES_USER = os.getenv("POSTGRES_USER", "citus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "o2ai")

print("=" * 60)
print("PostgreSQL Connection Test")
print("=" * 60)
print(f"Host: {POSTGRES_HOST}")
print(f"Port: {POSTGRES_PORT}")
print(f"Database: {POSTGRES_DB}")
print(f"User: {POSTGRES_USER}")
print(f"Password: {'*' * len(POSTGRES_PASSWORD)} (length: {len(POSTGRES_PASSWORD)})")
print("=" * 60)

try:
    import psycopg2
    
    # Try connection (use dbname instead of database for psycopg2)
    conn_string = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} sslmode=require"
    
    print("\nAttempting connection...")
    conn = psycopg2.connect(conn_string)
    
    print("✓ Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print(f"✓ Database version: {db_version[0]}")
    
    cursor.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"✗ Connection failed: {e}")
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING:")
    print("=" * 60)
    
    # Check if it's a timeout/connection error
    error_str = str(e).lower()
    if "timeout" in error_str or "connection" in error_str:
        print("\n⚠️  FIREWALL ISSUE DETECTED")
        print("\nYour IP address needs to be added to Azure firewall rules:")
        print("1. Go to Azure Portal → Cosmos DB for PostgreSQL → c-o2ai-fax-automation")
        print("2. Navigate to 'Networking' or 'Connection security'")
        print("3. Click 'Add client IP' or manually add:")
        current_ip = get_current_ip()
        if current_ip:
            print(f"   IP Address: {current_ip}")
        else:
            print("   IP Address: (check with: curl ifconfig.me)")
        print("4. Save and wait 1-2 minutes for propagation")
        print("\n📄 See COSMOS_DB_FIREWALL_SETUP.md for detailed instructions")
    else:
        print("1. Verify credentials in Azure Portal")
        print("2. Check that the database 'o2ai' exists")
        print("3. Ensure your IP is allowed in Azure firewall rules")
        print("4. Verify Cosmos DB for PostgreSQL connection string")
    
    sys.exit(1)

except ImportError:
    print("✗ psycopg2 not installed. Installing...")
    os.system("pip install psycopg2-binary")
    sys.exit(1)

print("\n✓ All checks passed!")
