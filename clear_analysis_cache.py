#!/usr/bin/env python3
"""
Clear Analysis Cache Database

This script clears all cached LLM analysis results from the database.
Use this to force fresh LLM analysis for all files.
"""

import sqlite3
import os

# Database path
DB_PATH = "backend/data/users.db"

def clear_analysis_cache():
    """Clear all entries from the analysis_cache table."""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        return
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM analysis_cache")
        count_before = cursor.fetchone()[0]
        
        if count_before == 0:
            print("ℹ️  Analysis cache is already empty!")
            conn.close()
            return
        
        # Show what will be deleted
        print(f"\n📊 Found {count_before} cached analysis entries:")
        cursor.execute("SELECT file_hash, filename, access_count FROM analysis_cache")
        for row in cursor.fetchall():
            print(f"  - {row[1]} (hash: {row[0][:16]}..., accessed {row[2]}x)")
        
        # Ask for confirmation
        print(f"\n⚠️  This will delete ALL {count_before} cached analysis results!")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("❌ Cancelled. No changes made.")
            conn.close()
            return
        
        # Delete all entries
        cursor.execute("DELETE FROM analysis_cache")
        conn.commit()
        
        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM analysis_cache")
        count_after = cursor.fetchone()[0]
        
        print(f"\n✅ Successfully deleted {count_before} entries!")
        print(f"📊 Remaining entries: {count_after}")
        print("\n💡 Next time you process files, LLM will generate fresh analysis results.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Clear Analysis Cache Database")
    print("=" * 60)
    clear_analysis_cache()
