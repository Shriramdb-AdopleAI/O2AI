#!/usr/bin/env python3
"""
View Null Field Tracking Data
Shows which documents have null required fields.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.null_field_service import null_field_service
from models.database import SessionLocal, NullFieldTracking
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)

def view_all_null_tracking():
    """View all null field tracking records."""
    print_header("NULL FIELD TRACKING - ALL DOCUMENTS")
    
    session = SessionLocal()
    try:
        records = session.query(NullFieldTracking).order_by(NullFieldTracking.created_at.desc()).all()
        
        if not records:
            print("\nNo records found.")
            return
        
        print(f"\nTotal documents: {len(records)}")
        
        for i, record in enumerate(records, 1):
            print(f"\n{'-' * 100}")
            print(f"Record {i}:")
            print(f"  Filename: {record.filename}")
            print(f"  Processing ID: {record.processing_id}")
            print(f"  Tenant ID: {record.tenant_id}")
            print(f"  Null Field Count: {record.null_field_count}")
            
            if record.null_field_count > 0:
                print(f"  Null Fields:")
                if record.name_is_null:
                    print(f"    ✗ Name (First, Middle, Last)")
                if record.dob_is_null:
                    print(f"    ✗ Date of Birth")
                if record.member_id_is_null:
                    print(f"    ✗ Member ID")
                if record.address_is_null:
                    print(f"    ✗ Address")
                if record.gender_is_null:
                    print(f"    ✗ Gender")
                if record.insurance_id_is_null:
                    print(f"    ✗ Insurance ID")
            else:
                print(f"  ✓ All required fields have values")
            
            print(f"  Created: {record.created_at}")
    
    finally:
        session.close()

def view_documents_with_nulls():
    """View only documents that have null fields."""
    print_header("DOCUMENTS WITH NULL REQUIRED FIELDS")
    
    records = null_field_service.get_documents_with_null_fields()
    
    if not records:
        print("\n✓ No documents with null fields found!")
        print("All processed documents have all required fields.")
        return
    
    print(f"\nFound {len(records)} documents with null fields:\n")
    
    for i, record in enumerate(records, 1):
        print(f"{i}. {record.filename}")
        print(f"   Null fields ({record.null_field_count}):")
        
        null_fields = []
        if record.name_is_null:
            null_fields.append("Name")
        if record.dob_is_null:
            null_fields.append("Date of Birth")
        if record.member_id_is_null:
            null_fields.append("Member ID")
        if record.address_is_null:
            null_fields.append("Address")
        if record.gender_is_null:
            null_fields.append("Gender")
        if record.insurance_id_is_null:
            null_fields.append("Insurance ID")
        
        for field in null_fields:
            print(f"     ✗ {field}")
        
        print(f"   Created: {record.created_at}")
        print()

def view_statistics():
    """View statistics about null fields."""
    print_header("NULL FIELD STATISTICS")
    
    stats = null_field_service.get_null_field_statistics()
    
    if not stats or stats.get("total_documents", 0) == 0:
        print("\nNo data available yet.")
        return
    
    print(f"\n📊 Total Documents: {stats['total_documents']}")
    print(f"⚠️  Documents with null fields: {stats['documents_with_null_fields']}")
    print(f"✅ Documents with all fields: {stats['documents_with_all_fields']}")
    
    if stats.get('null_field_counts'):
        print(f"\n--- NULL FIELD BREAKDOWN ---")
        for field, count in stats['null_field_counts'].items():
            if count > 0:
                percentage = (count / stats['total_documents']) * 100
                print(f"  {field}: {count} documents ({percentage:.1f}%)")
    
    if stats.get('most_common_null_field'):
        print(f"\n🔴 Most common null field: {stats['most_common_null_field']}")

def main():
    """Main function."""
    print("\n" + "🔍" * 50)
    print("NULL FIELD TRACKING VIEWER")
    print("🔍" * 50)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "all":
            view_all_null_tracking()
        elif command == "nulls":
            view_documents_with_nulls()
        elif command == "stats":
            view_statistics()
        else:
            print(f"\n❌ Unknown command: {command}")
            print_usage()
    else:
        print_usage()

def print_usage():
    """Print usage instructions."""
    print("\nUsage:")
    print("  python3 view_null_fields.py all      - View all tracking records")
    print("  python3 view_null_fields.py nulls    - View only documents with null fields")
    print("  python3 view_null_fields.py stats    - View statistics")
    print("\nExamples:")
    print("  python3 view_null_fields.py stats")
    print("  python3 view_null_fields.py nulls")
    print("  python3 view_null_fields.py all")

if __name__ == "__main__":
    main()
