#!/usr/bin/env python3
"""Create the o2ai_fax_automation database in Azure PostgreSQL."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../deployment/env.backend')

POSTGRES_USER = os.getenv("POSTGRES_USER", "citus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "o2ai")

print("=" * 60)
print("Creating PostgreSQL Database")
print("=" * 60)
print(f"Host: {POSTGRES_HOST}")
print(f"Database: {POSTGRES_DB}")
print(f"User: {POSTGRES_USER}")
print("=" * 60)

try:
    import psycopg2
    
    # Connect to postgres default database first
    conn_string = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname=postgres user={POSTGRES_USER} password={POSTGRES_PASSWORD} sslmode=require"
    
    print("\nConnecting to postgres default database...")
    conn = psycopg2.connect(conn_string)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("✓ Connected successfully!")
    
    # Check if database exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{POSTGRES_DB}'")
    exists = cursor.fetchone()
    
    if exists:
        print(f"✓ Database '{POSTGRES_DB}' already exists")
    else:
        print(f"Creating database '{POSTGRES_DB}'...")
        cursor.execute(f"CREATE DATABASE {POSTGRES_DB}")
        print(f"✓ Database '{POSTGRES_DB}' created successfully!")
    
    cursor.close()
    conn.close()
    
    # Now test connection to the new database
    print("\nTesting connection to the new database...")
    conn_string = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} sslmode=require"
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print(f"✓ Connected to '{POSTGRES_DB}'")
    print(f"✓ Database version: {db_version[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n✓ All database setup completed successfully!")
    
except psycopg2.Error as e:
    print(f"✗ Database error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
