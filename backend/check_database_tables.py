#!/usr/bin/env python3
"""Check if database tables exist and show their structure in a clean format."""

import os
import sys
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
load_dotenv('../deployment/env.backend')

POSTGRES_USER = os.getenv("POSTGRES_USER", "citus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "o2ai")

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_section(title):
    """Print a section divider."""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print("─" * 80)

def format_data_type(data_type, character_maximum_length=None):
    """Format data type with length if applicable."""
    if character_maximum_length:
        return f"{data_type}({character_maximum_length})"
    return data_type

try:
    import psycopg2
    
    conn_string = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} sslmode=require"
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    
    # Print connection info
    print_header("DATABASE CONNECTION INFORMATION")
    print(f"  Host:     {POSTGRES_HOST}")
    print(f"  Port:     {POSTGRES_PORT}")
    print(f"  Database: {POSTGRES_DB}")
    print(f"  User:     {POSTGRES_USER}")
    
    # Get database version
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()[0]
    print(f"  Version:  {db_version.split(',')[0]}")
    
    # Check if tables exist
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    
    if not tables:
        print_section("NO TABLES FOUND")
        print("\n  ⚠️  No tables found in the database.")
        print("\n  To create tables, run:")
        print("    python -c 'from models.database import create_tables; create_tables()'")
        print("    OR")
        print("    python migrate_to_postgres.py")
        cursor.close()
        conn.close()
        sys.exit(0)
    
    # Separate application tables from system tables
    application_tables = []
    system_tables = []
    citus_tables = []
    
    for table in tables:
        table_name = table[0]
        if table_name.startswith('pg_') or table_name.startswith('citus_'):
            if table_name.startswith('citus_'):
                citus_tables.append(table_name)
            else:
                system_tables.append(table_name)
        else:
            application_tables.append(table_name)
    
    # Print summary
    print_header("DATABASE TABLES SUMMARY")
    summary_data = [
        ["Application Tables", len(application_tables)],
        ["Cosmos DB Tables", len(citus_tables)],
        ["System Tables", len(system_tables)],
        ["TOTAL", len(tables)]
    ]
    print(tabulate(summary_data, headers=["Category", "Count"], tablefmt="grid"))
    
    # Print application tables in detail
    if application_tables:
        print_section("APPLICATION TABLES")
        
        for idx, table_name in enumerate(application_tables, 1):
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            
            # Get table size
            cursor.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
            """)
            size = cursor.fetchone()[0]
            
            print(f"\n  [{idx}] {table_name}")
            print(f"      Rows: {count:,}  |  Size: {size}")
            
            # Get column info
            cursor.execute(f"""
                SELECT 
                    column_name, 
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            if columns:
                column_data = []
                for col in columns:
                    col_name, data_type, max_len, nullable, default = col
                    formatted_type = format_data_type(data_type, max_len)
                    null_info = "NULL" if nullable == "YES" else "NOT NULL"
                    default_info = f"DEFAULT {default}" if default else ""
                    column_data.append([
                        col_name,
                        formatted_type,
                        null_info,
                        default_info[:30] if default_info else ""
                    ])
                
                print(f"      Columns ({len(columns)}):")
                print(tabulate(
                    column_data,
                    headers=["Column Name", "Data Type", "Nullable", "Default"],
                    tablefmt="simple",
                    stralign="left"
                ))
    
    # Print Cosmos DB tables
    if citus_tables:
        print_section("COSMOS DB FOR POSTGRESQL TABLES")
        citus_data = []
        for table_name in citus_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            citus_data.append([table_name, f"{count:,} rows"])
        
        print(tabulate(citus_data, headers=["Table Name", "Rows"], tablefmt="grid"))
    
    # Print system tables summary (if any)
    if system_tables:
        print_section("SYSTEM TABLES")
        sys_data = []
        for table_name in system_tables[:10]:  # Show first 10
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            sys_data.append([table_name, f"{count:,} rows"])
        
        print(tabulate(sys_data, headers=["Table Name", "Rows"], tablefmt="simple"))
        if len(system_tables) > 10:
            print(f"\n  ... and {len(system_tables) - 10} more system tables")
    
    cursor.close()
    conn.close()
    
    print_header("DATABASE CHECK COMPLETED")
    print("  ✓ All tables verified successfully!")
    
except ImportError as e:
    if "tabulate" in str(e):
        print("\n⚠️  'tabulate' module not found. Installing...")
        os.system("pip install tabulate")
        print("  Please run the script again.")
    else:
        print(f"\n✗ Import error: {e}")
        print("  Install required packages: pip install psycopg2-binary python-dotenv tabulate")
    sys.exit(1)
except psycopg2.Error as e:
    print_header("DATABASE ERROR")
    print(f"  ✗ {e}")
    sys.exit(1)
except Exception as e:
    print_header("ERROR")
    print(f"  ✗ {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

