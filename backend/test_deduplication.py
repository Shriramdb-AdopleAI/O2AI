#!/usr/bin/env python3
"""
Test script to demonstrate file deduplication in the OCR system.

This script shows how the system now prevents storing the same file
multiple times in both the database and Azure Blob Storage.
"""

import hashlib
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.azure_blob_service import AzureBlobService
from models.database import ProcessedFile, SessionLocal

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_duplicate_in_database(file_hash: str, tenant_id: str) -> bool:
    """Check if a file with the given hash exists in the database."""
    db = SessionLocal()
    try:
        existing_file = db.query(ProcessedFile).filter(
            ProcessedFile.file_hash == file_hash,
            ProcessedFile.tenant_id == tenant_id
        ).first()
        return existing_file is not None
    finally:
        db.close()

def main():
    print("=" * 60)
    print("File Deduplication Test")
    print("=" * 60)
    print()
    
    # Example: Check if a file would be a duplicate
    test_file = "test_document.pdf"  # Replace with actual file path
    tenant_id = "tenant_2"
    
    if not os.path.exists(test_file):
        print(f"⚠️  Test file '{test_file}' not found.")
        print("   Please provide a valid file path to test deduplication.")
        return
    
    print(f"📄 Testing file: {test_file}")
    print(f"👤 Tenant ID: {tenant_id}")
    print()
    
    # Calculate file hash
    file_hash = calculate_file_hash(test_file)
    print(f"🔐 File hash: {file_hash[:16]}...")
    print()
    
    # Check if duplicate exists in database
    is_duplicate = check_duplicate_in_database(file_hash, tenant_id)
    
    if is_duplicate:
        print("✅ DUPLICATE DETECTED!")
        print("   This file has already been processed.")
        print("   The system will:")
        print("   - Skip uploading to Azure Blob Storage")
        print("   - Skip OCR processing")
        print("   - Return existing processed data")
        print("   - Save processing time and storage costs")
    else:
        print("✅ NEW FILE")
        print("   This file has not been processed before.")
        print("   The system will:")
        print("   - Upload to Azure Blob Storage")
        print("   - Process with OCR")
        print("   - Store results in database")
    
    print()
    print("=" * 60)
    print("How Deduplication Works:")
    print("=" * 60)
    print()
    print("1. When a file is uploaded, the system calculates its SHA256 hash")
    print("2. It checks the database for any existing file with the same hash")
    print("3. If found:")
    print("   - Returns existing processed data immediately")
    print("   - Skips Azure Blob Storage upload")
    print("   - Skips OCR processing")
    print("4. If not found:")
    print("   - Uploads to Azure Blob Storage")
    print("   - Processes with OCR")
    print("   - Stores in database with hash for future deduplication")
    print()
    print("Benefits:")
    print("- Saves Azure storage costs")
    print("- Reduces processing time")
    print("- Prevents duplicate data")
    print("- Maintains data consistency")
    print()

if __name__ == "__main__":
    main()
