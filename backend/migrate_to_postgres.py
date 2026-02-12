#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL.
This script exports all data from the SQLite database and imports it into PostgreSQL.
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import json
import sys
import os
from datetime import datetime

# Database configurations
SQLITE_DB_PATH = "data/users.db"
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "c-o2ai-fax-automation.3pxzxnihh342f2.postgres.cosmos.azure.com"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "o2ai"),
    "user": os.getenv("POSTGRES_USER", "citus"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "sslmode": "require"
}

def connect_sqlite():
    """Connect to SQLite database."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        print(f"✓ Connected to SQLite database: {SQLITE_DB_PATH}")
        return conn
    except sqlite3.Error as e:
        print(f"✗ Error connecting to SQLite: {e}")
        sys.exit(1)

def connect_postgres():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        print(f"✓ Connected to PostgreSQL database: {POSTGRES_CONFIG['database']}")
        return conn
    except psycopg2.Error as e:
        print(f"✗ Error connecting to PostgreSQL: {e}")
        print("\nMake sure PostgreSQL is running and the database exists.")
        print(f"You can create it with: createdb {POSTGRES_CONFIG['database']}")
        sys.exit(1)

def export_table_data(sqlite_conn, table_name):
    """Export all data from a SQLite table."""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    if rows:
        columns = [description[0] for description in cursor.description]
        data = [dict(row) for row in rows]
        print(f"  Exported {len(data)} rows from {table_name}")
        return columns, data
    else:
        print(f"  No data found in {table_name}")
        return None, []

def import_users(pg_conn, columns, data):
    """Import users data to PostgreSQL."""
    if not data:
        return
    
    cursor = pg_conn.cursor()
    
    # Clear existing data
    cursor.execute("TRUNCATE TABLE users CASCADE")
    
    # Prepare insert query
    insert_query = """
        INSERT INTO users (id, username, email, hashed_password, is_active, is_admin, created_at, last_login)
        VALUES %s
    """
    
    values = [
        (
            row['id'],
            row['username'],
            row['email'],
            row['hashed_password'],
            bool(row['is_active']),  # Convert SQLite integer to boolean
            bool(row['is_admin']),   # Convert SQLite integer to boolean
            row['created_at'],
            row['last_login']
        )
        for row in data
    ]
    
    execute_values(cursor, insert_query, values)
    
    # Update sequence
    cursor.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
    
    pg_conn.commit()
    print(f"  ✓ Imported {len(data)} users")

def import_user_sessions(pg_conn, columns, data):
    """Import user sessions data to PostgreSQL."""
    if not data:
        return
    
    cursor = pg_conn.cursor()
    
    # Clear existing data
    cursor.execute("TRUNCATE TABLE user_sessions CASCADE")
    
    # Get valid user IDs
    cursor.execute("SELECT id FROM users")
    valid_user_ids = set(row[0] for row in cursor.fetchall())
    
    # Filter out sessions with invalid user_id
    valid_sessions = [row for row in data if row['user_id'] in valid_user_ids]
    invalid_count = len(data) - len(valid_sessions)
    
    if invalid_count > 0:
        print(f"  ⚠ Skipping {invalid_count} sessions with invalid user_id references")
    
    if not valid_sessions:
        print(f"  ⚠ No valid sessions to import")
        return
    
    # Prepare insert query
    insert_query = """
        INSERT INTO user_sessions (id, user_id, session_token, tenant_id, created_at, last_activity, is_active)
        VALUES %s
    """
    
    values = [
        (
            row['id'],
            row['user_id'],
            row['session_token'],
            row['tenant_id'],
            row['created_at'],
            row['last_activity'],
            bool(row['is_active'])  # Convert SQLite integer to boolean
        )
        for row in valid_sessions
    ]
    
    execute_values(cursor, insert_query, values)
    
    # Update sequence
    cursor.execute("SELECT setval('user_sessions_id_seq', (SELECT MAX(id) FROM user_sessions))")
    
    pg_conn.commit()
    print(f"  ✓ Imported {len(valid_sessions)} user sessions")


def import_ground_truth(pg_conn, columns, data):
    """Import ground truth data to PostgreSQL."""
    if not data:
        return
    
    cursor = pg_conn.cursor()
    
    # Clear existing data
    cursor.execute("TRUNCATE TABLE ground_truth CASCADE")
    
    # Prepare insert query
    insert_query = """
        INSERT INTO ground_truth (id, processing_id, tenant_id, filename, ground_truth, ocr_text, metadata_json, created_at, updated_at)
        VALUES %s
    """
    
    values = []
    for row in data:
        # Convert JSON string to JSONB
        metadata = row.get('metadata_json')
        if metadata and isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = None
        
        values.append((
            row['id'],
            row['processing_id'],
            row['tenant_id'],
            row['filename'],
            row['ground_truth'],
            row['ocr_text'],
            json.dumps(metadata) if metadata else None,
            row['created_at'],
            row['updated_at']
        ))
    
    execute_values(cursor, insert_query, values)
    
    # Update sequence
    cursor.execute("SELECT setval('ground_truth_id_seq', (SELECT MAX(id) FROM ground_truth))")
    
    pg_conn.commit()
    print(f"  ✓ Imported {len(data)} ground truth entries")

def verify_migration(sqlite_conn, pg_conn):
    """Verify that all data was migrated correctly."""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    tables = ['users', 'user_sessions', 'ground_truth']
    
    for table in tables:
        # Count SQLite rows
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cursor.fetchone()[0]
        
        # Count PostgreSQL rows
        pg_cursor = pg_conn.cursor()
        pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        pg_count = pg_cursor.fetchone()[0]
        
        status = "✓" if sqlite_count == pg_count else "✗"
        print(f"{status} {table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")

def main():
    """Main migration function."""
    print("="*60)
    print("SQLite to PostgreSQL Migration")
    print("="*60)
    print()
    
    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"✗ SQLite database not found: {SQLITE_DB_PATH}")
        sys.exit(1)
    
    # Connect to databases
    sqlite_conn = connect_sqlite()
    pg_conn = connect_postgres()
    
    try:
        # Migration steps
        tables = {
            'users': import_users,
            'user_sessions': import_user_sessions,
            'ground_truth': import_ground_truth
        }
        
        print("\n" + "="*60)
        print("MIGRATION")
        print("="*60)
        
        for table_name, import_func in tables.items():
            print(f"\nMigrating {table_name}...")
            columns, data = export_table_data(sqlite_conn, table_name)
            if columns:
                import_func(pg_conn, columns, data)
        
        # Verify migration
        verify_migration(sqlite_conn, pg_conn)
        
        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("1. Update your .env file with DATABASE_URL")
        print("2. Backup your SQLite database: cp data/users.db data/users.db.backup")
        print("3. Test your application with PostgreSQL")
        print("4. Once verified, you can remove the SQLite database")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
        sys.exit(1)
    
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main()
