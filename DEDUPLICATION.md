# File Deduplication Implementation

## Overview

The OCR system has been enhanced to prevent storing duplicate files in both the database and Azure Blob Storage. This saves storage costs, reduces processing time, and maintains data consistency.

## How It Works

### 1. **File Hash Calculation**
When a file is uploaded, the system calculates its SHA256 hash:
```python
file_hash = hashlib.sha256(file_data).hexdigest()
```

### 2. **Duplicate Detection**
The system checks if a file with the same hash already exists in the database:
```python
existing_file = db.query(ProcessedFile).filter(
    ProcessedFile.file_hash == file_hash,
    ProcessedFile.tenant_id == tenant_id
).first()
```

### 3. **Smart Handling**

#### If Duplicate Found:
- ✅ Returns existing processed data immediately
- ✅ Skips Azure Blob Storage upload
- ✅ Skips OCR processing
- ✅ Saves processing time and costs

#### If New File:
- ✅ Uploads to Azure Blob Storage
- ✅ Processes with OCR
- ✅ Stores in database with hash for future deduplication

## Changes Made

### 1. **Azure Blob Service** (`services/azure_blob_service.py`)

#### New Method: `check_file_exists_by_hash()`
```python
def check_file_exists_by_hash(self, file_data: bytes, tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a file with the same hash already exists in the database.
    
    Returns:
        Dictionary with existing file info if found, None otherwise
    """
```

#### Updated Method: `upload_source_document()`
- Added `skip_duplicate_check` parameter
- Checks for duplicates before uploading
- Returns existing file info if duplicate found

### 2. **Celery Tasks** (`core/celery_tasks.py`)

#### Updated: `process_document()`
- Checks for duplicates before processing
- Returns existing processed data if duplicate found
- Skips OCR processing for duplicates

## Benefits

### 💰 **Cost Savings**
- Reduces Azure Blob Storage costs by not storing duplicate files
- Saves on OCR API calls (Azure Document Intelligence)

### ⚡ **Performance**
- Instant response for duplicate files (no OCR processing)
- Reduced server load

### 📊 **Data Consistency**
- Single source of truth for each unique file
- Prevents data fragmentation

### 🔒 **Storage Efficiency**
- No duplicate files in Azure Blob Storage
- No duplicate records in database (enforced by unique file_hash)

## Usage Examples

### Example 1: Upload Same File Twice

**First Upload:**
```
📤 Uploading file: invoice_001.pdf
🔐 Calculating hash: a1b2c3d4e5f6...
✅ New file - Processing with OCR
⏱️  Processing time: 5.2 seconds
💾 Stored in database and Azure
```

**Second Upload (Same File):**
```
📤 Uploading file: invoice_001_copy.pdf
🔐 Calculating hash: a1b2c3d4e5f6...
⚠️  Duplicate detected!
✅ Returning existing data
⏱️  Processing time: 0.1 seconds
💾 No new storage used
```

### Example 2: API Response for Duplicate

```json
{
  "status": "completed",
  "duplicate": true,
  "message": "File already processed - returned existing data",
  "processing_id": "existing-processing-id",
  "file_info": {
    "filename": "invoice_001_copy.pdf",
    "original_filename": "invoice_001.pdf",
    "first_processed": "2026-01-15T10:30:00Z"
  },
  "key_value_pairs": { ... },
  "blob_storage": {
    "source": {
      "blob_path": "main/Above-95%/source/tenant_2/invoice_001.pdf",
      "duplicate": true
    }
  }
}
```

## Configuration

### Disable Deduplication (if needed)
You can disable deduplication for specific uploads:

```python
source_blob_info = blob_service.upload_source_document(
    file_data=file_bytes,
    filename=filename,
    tenant_id=tenant_id,
    processing_id=processing_id,
    content_type=content_type,
    skip_duplicate_check=True  # Disable deduplication
)
```

## Database Schema

The `ProcessedFile` table includes:
- `file_hash` (String, unique, indexed) - SHA256 hash for deduplication
- `processing_id` (String) - Unique processing identifier
- `tenant_id` (String) - Tenant isolation
- `source_blob_path` (String) - Azure Blob Storage path for source file
- `processed_blob_path` (String) - Azure Blob Storage path for processed JSON
- `processed_data` (JSONB) - Complete processed results

## Testing

Run the test script to verify deduplication:

```bash
cd backend
python test_deduplication.py
```

## Monitoring

### Log Messages

**Duplicate Detected:**
```
✓ Found existing file with hash a1b2c3d4... - Skipping upload
⚠️ Duplicate file detected: invoice.pdf - Returning existing processed data
```

**New File:**
```
✓ File hash a1b2c3d4... not found in database - Proceeding with upload
✓ Uploaded new source file: invoice.pdf
```

## Performance Metrics

### Before Deduplication
- Same file uploaded 10 times
- Storage used: 10x file size
- Processing time: 10x OCR time
- API calls: 10x

### After Deduplication
- Same file uploaded 10 times
- Storage used: 1x file size (90% reduction)
- Processing time: 1x OCR time + 9x instant responses (95% reduction)
- API calls: 1x (90% reduction)

## Troubleshooting

### Issue: Duplicate not detected
**Cause:** File content changed (even slightly)
**Solution:** SHA256 hash is content-based. Any change in file content results in a different hash.

### Issue: Want to reprocess a file
**Solution:** Use `skip_duplicate_check=True` parameter

### Issue: Database shows duplicate but Azure doesn't
**Cause:** Database deduplication working, but Azure upload happened before check
**Solution:** System now checks before Azure upload - this is fixed

## Migration Notes

### Existing Files
- Files uploaded before this update will not have deduplication
- Only new uploads will benefit from deduplication
- Consider running a migration script to calculate hashes for existing files

### Backward Compatibility
- All existing API endpoints work unchanged
- Duplicate detection is transparent to clients
- Response includes `duplicate: true` flag for awareness

## Future Enhancements

1. **Content-based deduplication** - Detect similar files (not just identical)
2. **Cross-tenant deduplication** - Share common files across tenants (with proper access control)
3. **Automatic cleanup** - Remove orphaned blobs without database entries
4. **Deduplication metrics** - Dashboard showing storage savings

## Summary

The file deduplication feature significantly improves the OCR system by:
- ✅ Preventing duplicate storage in Azure Blob Storage
- ✅ Preventing duplicate processing with OCR
- ✅ Reducing costs and improving performance
- ✅ Maintaining data consistency
- ✅ Providing instant responses for duplicate files

All changes are backward compatible and transparent to existing clients.
