#!/usr/bin/env python3
"""
Script to check data in the PostgreSQL database using server credentials.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json

# Database configuration from server
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "o2aifaxautomationdatabaseserver.postgres.database.azure.com"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "o2ai_fax_automation"),
    "user": os.getenv("POSTGRES_USER", "adople"),
    "password": os.getenv("POSTGRES_PASSWORD", "Product@2026"),
    "sslmode": "require"
}

def connect_postgres():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        print(f"✓ Connected to PostgreSQL database: {POSTGRES_CONFIG['database']}")
        return conn
    except psycopg2.Error as e:
        print(f"✗ Error connecting to PostgreSQL: {e}")
        return None

def get_table_info(conn):
    """Get all tables in the database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables

def count_rows(conn, table_name):
    """Count rows in a table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    cursor.close()
    return count

def get_sample_data(conn, table_name, limit=5):
    """Get sample data from a table."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"  Error fetching data from {table_name}: {e}")
        return []
    finally:
        cursor.close()

def format_value(value):
    """Format a value for display."""
    if value is None:
        return "NULL"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    if isinstance(value, str) and len(value) > 100:
        return value[:100] + "..."
    return str(value)

def print_table_summary(conn, table_name):
    """Print summary of a table."""
    count = count_rows(conn, table_name)
    print(f"\n{'='*80}")
    print(f"Table: {table_name}")
    print(f"{'='*80}")
    print(f"Total rows: {count}")
    
    if count > 0:
        print(f"\nSample data (last {min(5, count)} rows):")
        print("-" * 80)
        sample_data = get_sample_data(conn, table_name, limit=5)
        
        for idx, row in enumerate(sample_data, 1):
            print(f"\nRow {idx}:")
            for key, value in row.items():
                formatted_value = format_value(value)
                print(f"  {key}: {formatted_value}")

def main():
    """Main function to check database data."""
    print("="*80)
    print("PostgreSQL Database Data Check")
    print("="*80)
    print(f"\nConnecting to:")
    print(f"  Host: {POSTGRES_CONFIG['host']}")
    print(f"  Database: {POSTGRES_CONFIG['database']}")
    print(f"  User: {POSTGRES_CONFIG['user']}")
    
    conn = connect_postgres()
    if not conn:
        return
    
    try:
        # Get all tables
        print("\n" + "="*80)
        print("DATABASE OVERVIEW")
        print("="*80)
        tables = get_table_info(conn)
        print(f"\nFound {len(tables)} tables:")
        for table in tables:
            count = count_rows(conn, table)
            print(f"  - {table}: {count} rows")
        
        # Print detailed information for each table
        for table in tables:
            print_table_summary(conn, table)
        
        # Additional queries for specific insights
        print("\n" + "="*80)
        print("ADDITIONAL INSIGHTS")
        print("="*80)
        
        # Check users
        if 'users' in tables:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT username, email, is_admin, is_active, created_at FROM users")
            users = cursor.fetchall()
            print(f"\nUsers ({len(users)} total):")
            for user in users:
                print(f"  - {user['username']} ({user['email']}) - Admin: {user['is_admin']}, Active: {user['is_active']}, Created: {user['created_at']}")
            cursor.close()
        
        # Check user sessions
        if 'user_sessions' in tables:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_active = true) as active FROM user_sessions")
            stats = cursor.fetchone()
            print(f"\nUser Sessions:")
            print(f"  - Total: {stats['total']}")
            print(f"  - Active: {stats['active']}")
            cursor.close()
        
        # Check processed files
        if 'processed_files' in tables:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE has_corrections = true) as with_corrections,
                    COUNT(DISTINCT tenant_id) as unique_tenants
                FROM processed_files
            """)
            stats = cursor.fetchone()
            print(f"\nProcessed Files:")
            print(f"  - Total: {stats['total']}")
            print(f"  - With corrections: {stats['with_corrections']}")
            print(f"  - Unique tenants: {stats['unique_tenants']}")
            cursor.close()
        
        # Check null field tracking
        if 'null_field_tracking' in tables:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(null_field_count) as avg_null_fields,
                    COUNT(DISTINCT tenant_id) as unique_tenants
                FROM null_field_tracking
            """)
            stats = cursor.fetchone()
            print(f"\nNull Field Tracking:")
            print(f"  - Total records: {stats['total']}")
            if stats['avg_null_fields']:
                print(f"  - Average null fields per record: {float(stats['avg_null_fields']):.2f}")
            print(f"  - Unique tenants: {stats['unique_tenants']}")
            cursor.close()
        
        # Check ground truth
        if 'ground_truth' in tables:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT tenant_id) as unique_tenants,
                    COUNT(DISTINCT processing_id) as unique_processing_ids
                FROM ground_truth
            """)
            stats = cursor.fetchone()
            print(f"\nGround Truth:")
            print(f"  - Total records: {stats['total']}")
            print(f"  - Unique tenants: {stats['unique_tenants']}")
            print(f"  - Unique processing IDs: {stats['unique_processing_ids']}")
            cursor.close()
        
        print("\n" + "="*80)
        print("✓ Database check completed successfully!")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error checking database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()

