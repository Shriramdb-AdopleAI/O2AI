#!/usr/bin/env python3
"""Check application tables and display their data in a clean format."""

import os
import sys
from dotenv import load_dotenv
from tabulate import tabulate
from datetime import datetime

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

def format_value(value, max_length=30):
    """Format a value for display, truncating if too long."""
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        import json
        json_str = json.dumps(value, default=str)
        if len(json_str) > max_length:
            return json_str[:max_length] + "..."
        return json_str
    value_str = str(value)
    if len(value_str) > max_length:
        return value_str[:max_length] + "..."
    return value_str

def format_datetime(dt):
    """Format datetime for display."""
    if dt is None:
        return "NULL"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

def get_table_data(cursor, table_name, limit=10):
    """Get data from a table with a limit."""
    try:
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        total_count = cursor.fetchone()[0]
        
        if total_count == 0:
            return None, [], 0
        
        # Get column names
        cursor.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        columns = [col[0] for col in cursor.fetchall()]
        
        # Get data with limit - try to order by id if exists, otherwise just limit
        try:
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit};")
        except:
            # If no id column, just get first N rows
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        
        rows = cursor.fetchall()
        
        return columns, rows, total_count
    except Exception as e:
        return None, [], 0

def display_table_data(cursor, table_name, table_display_name=None):
    """Display data from a specific table."""
    if table_display_name is None:
        table_display_name = table_name
    
    print_section(f"TABLE: {table_display_name.upper()}")
    
    columns, rows, total_count = get_table_data(cursor, table_name)
    if columns is None:
        print(f"\n  ⚠️  No data found in '{table_name}' table.")
        return
    
    print(f"\n  Total Rows: {total_count:,}")
    print(f"  Showing: {min(len(rows), total_count)} row(s)")
    
    if total_count == 0:
        print(f"\n  Table is empty.")
        return
    
    # Define column width limits based on column type
    def get_col_max_width(col_name, col_index):
        """Get maximum width for a column based on its name/type."""
        col_lower = col_name.lower()
        
        # ID columns - short
        if col_name == 'id':
            return 8
        
        # Hash columns - medium
        if 'hash' in col_lower:
            return 20
        
        # Timestamp columns - medium
        if 'created_at' in col_lower or 'updated_at' in col_lower or 'last_' in col_lower:
            return 20
        
        # Boolean columns - short
        if 'is_' in col_lower or 'has_' in col_lower:
            return 10
        
        # Tenant/processing IDs - medium
        if 'tenant_id' in col_lower or 'processing_id' in col_lower:
            return 25
        
        # Filename - medium
        if 'filename' in col_lower:
            return 30
        
        # Path columns - longer
        if 'path' in col_lower:
            return 40
        
        # JSON/Text columns - shorter to prevent overflow
        if 'json' in col_lower or 'data' in col_lower or 'text' in col_lower:
            return 35
        
        # Count columns - short
        if 'count' in col_lower:
            return 12
        
        # Default for other columns
        return 25
    
    # Format data for display with proper column widths
    display_data = []
    col_widths = []
    
    for i, col_name in enumerate(columns):
        col_widths.append(get_col_max_width(col_name, i))
    
    for row in rows:
        formatted_row = []
        for i, value in enumerate(row):
            col_name = columns[i]
            max_width = col_widths[i]
            
            # Special formatting for certain column types
            if 'password' in col_name.lower():
                formatted_row.append("***HIDDEN***")
            elif 'created_at' in col_name or 'updated_at' in col_name or 'last_' in col_name:
                formatted_row.append(format_datetime(value))
            elif isinstance(value, (dict, list)):
                formatted_row.append(format_value(value, max_length=max_width))
            elif isinstance(value, str) and len(str(value)) > max_width:
                formatted_row.append(format_value(value, max_length=max_width))
            else:
                formatted_row.append(format_value(value, max_length=max_width))
        display_data.append(formatted_row)
    
    # Display table with proper column widths
    print(f"\n  Data:")
    
    # Truncate headers and data to fit column widths
    display_headers = []
    for i, header in enumerate(columns):
        max_width = col_widths[i]
        if len(header) > max_width:
            display_headers.append(header[:max_width-3] + "...")
        else:
            display_headers.append(header)
    
    # Ensure all data fits within column widths
    final_display_data = []
    for row in display_data:
        formatted_row = []
        for i, cell in enumerate(row):
            max_width = col_widths[i]
            cell_str = str(cell)
            if len(cell_str) > max_width:
                formatted_row.append(cell_str[:max_width-3] + "...")
            else:
                formatted_row.append(cell_str)
        final_display_data.append(formatted_row)
    
    # Use simple table format for better alignment
    try:
        print(tabulate(
            final_display_data,
            headers=display_headers,
            tablefmt="grid",
            stralign="left",
            numalign="left"
        ))
    except Exception as e:
        # Fallback - simple table without grid
        print(tabulate(
            final_display_data,
            headers=display_headers,
            tablefmt="simple",
            stralign="left"
        ))
    
    if total_count > len(rows):
        print(f"\n  ... and {total_count - len(rows)} more row(s) (showing first {len(rows)})")
        print(f"  Use LIMIT in SQL query to see more rows.")

try:
    import psycopg2
    
    conn_string = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} sslmode=require"
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    
    # Print connection info
    print_header("DATABASE CONNECTION")
    print(f"  Host:     {POSTGRES_HOST}")
    print(f"  Database: {POSTGRES_DB}")
    print(f"  User:     {POSTGRES_USER}")
    
    # Get application tables (exclude system tables)
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_name NOT LIKE 'pg_%'
        AND table_name NOT LIKE 'citus_%'
        ORDER BY table_name;
    """)
    
    application_tables = [row[0] for row in cursor.fetchall()]
    
    if not application_tables:
        print_section("NO APPLICATION TABLES FOUND")
        print("\n  ⚠️  No application tables found in the database.")
        cursor.close()
        conn.close()
        sys.exit(0)
    
    # Print summary
    print_header("APPLICATION TABLES SUMMARY")
    summary_data = []
    for table_name in application_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        summary_data.append([table_name, f"{count:,}"])
    
    print(tabulate(
        summary_data, 
        headers=["Table Name", "Row Count"], 
        tablefmt="grid",
        stralign="left"
    ))
    
    # Display data for each table
    print_header("TABLE DATA")
    
    for table_name in application_tables:
        display_table_data(cursor, table_name)
        print()  # Add spacing between tables
    
    cursor.close()
    conn.close()
    
    print_header("DATA CHECK COMPLETED")
    print("  ✓ All application tables checked successfully!")
    
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

