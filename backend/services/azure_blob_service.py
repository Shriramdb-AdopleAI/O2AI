"""
Azure Blob Storage service for file management and organization.
"""

import os
import uuid
import re
from datetime import datetime
from typing import List, Dict, Optional, BinaryIO, Any
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
import logging

logger = logging.getLogger(__name__)

class AzureBlobService:
    """Service for managing files in Azure Blob Storage with organized folder structure."""
    
    def __init__(self):
        self.connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.container_name = os.getenv('AZURE_BLOB_CONTAINER', 'ocr-documents')
        self.blob_service_client = None
        self.container_client = None
        self.initialization_error = None
        
        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
                self._ensure_container_exists()
                logger.info(f"Azure Blob Storage service initialized successfully with container: {self.container_name}")
            except Exception as e:
                self.initialization_error = str(e)
                logger.error(f"Failed to initialize Azure Blob Storage: {e}")
                # Don't set blob_service_client to None here, keep it for retry attempts
        else:
            logger.warning("Azure Blob Storage connection string not provided")
    
    def _ensure_container_exists(self):
        """Ensure the container exists, create if it doesn't."""
        try:
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            self.container_client.get_container_properties()
        except ResourceNotFoundError:
            try:
                self.container_client = self.blob_service_client.create_container(self.container_name)
                logger.info(f"Created container: {self.container_name}")
            except Exception as e:
                logger.error(f"Failed to create container: {e}")
                raise
    
    def is_available(self) -> bool:
        """Check if Azure Blob Storage is available."""
        return (self.blob_service_client is not None and 
                self.container_client is not None and 
                self.initialization_error is None)
    
    def get_status(self) -> Dict[str, any]:
        """Get detailed status of the Azure Blob Storage service."""
        return {
            "available": self.is_available(),
            "connection_string_provided": bool(self.connection_string),
            "container_name": self.container_name,
            # Do not expose raw initialization error details to clients
            "initialization_error": "Initialization error occurred" if self.initialization_error else None,
            "blob_service_client": self.blob_service_client is not None,
            "container_client": self.container_client is not None
        }
    
    def check_file_exists_by_hash(self, file_data: bytes, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if a file with the same hash already exists in the database.
        
        Args:
            file_data: The file content as bytes
            tenant_id: Tenant ID to check within
            
        Returns:
            Dictionary with existing file info if found, None otherwise
        """
        try:
            import hashlib
            from models.database import ProcessedFile, SessionLocal
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Check database for existing file with same hash
            db = SessionLocal()
            try:
                existing_file = db.query(ProcessedFile).filter(
                    ProcessedFile.file_hash == file_hash,
                    ProcessedFile.tenant_id == tenant_id
                ).first()
                
                if existing_file:
                    logger.info(f"✓ Found existing file with hash {file_hash[:16]}... - Skipping upload")
                    return {
                        "exists": True,
                        "file_hash": file_hash,
                        "processing_id": existing_file.processing_id,
                        "filename": existing_file.filename,
                        "source_blob_path": existing_file.source_blob_path,
                        "processed_blob_path": existing_file.processed_blob_path,
                        "processed_data": existing_file.processed_data,
                        "ocr_confidence_score": existing_file.ocr_confidence_score,
                        "created_at": existing_file.created_at.isoformat() if existing_file.created_at else None
                    }
                else:
                    logger.info(f"✓ File hash {file_hash[:16]}... not found in database - Proceeding with upload")
                    return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error checking file existence by hash: {e}")
            return None
    
    def upload_source_document(self, file_data: bytes, filename: str, tenant_id: str, 
                             processing_id: str, content_type: str = "application/octet-stream",
                             confidence_score: Optional[float] = None, 
                             skip_duplicate_check: bool = False) -> Dict[str, str]:
        """
        Upload a source document to Azure Blob Storage source folder.
        
        NOTE: Duplicate checking is disabled - files are ALWAYS uploaded to blob storage
        even if they are duplicates. This ensures all files are stored in blob after
        credential changes.
        
        Args:
            file_data: The file content as bytes
            filename: Original filename
            tenant_id: Tenant ID for organization
            processing_id: Unique processing ID
            content_type: MIME type of the file
            confidence_score: Optional confidence score (0-100) to determine folder path
            skip_duplicate_check: Ignored - kept for backwards compatibility (always uploads)
            
        Returns:
            Dictionary with upload information
        """
        if not self.is_available():
            return {"success": False, "error": "Azure Blob Storage not available"}
        
        try:
            # ALWAYS upload to blob storage - duplicate checking is disabled
            # Even if file is duplicate, upload with new path to blob storage
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Determine folder based on confidence score
            # New path structure: main/{confidence_folder}/source/tenant_id/{filename}
            # Check confidence score and place in appropriate folder
            # Note: Source files are initially uploaded without confidence, then moved after OCR processing
            if confidence_score is not None:
                # Normalize confidence score: if it's between 0-1, treat as decimal (0.95 = 95%)
                # If it's > 1, treat as percentage (95 = 95%)
                if confidence_score <= 1.0:
                    # Confidence is in 0-1 format, compare with 0.95
                    threshold = 0.95
                    score_display = f"{confidence_score * 100:.2f}%"
                else:
                    # Confidence is in 0-100 format, compare with 95.0
                    threshold = 95.0
                    score_display = f"{confidence_score:.2f}%"
                
                # Compare confidence score with threshold
                if confidence_score >= threshold:
                    confidence_folder = "Above-95%"
                    logger.info(f"Source file confidence score {score_display} >= 95% - placing in Above-95% folder")
                else:
                    confidence_folder = "needs to be reviewed"
                    logger.info(f"Source file confidence score {score_display} < 95% - placing in needs to be reviewed folder")
            else:
                # Default to "needs to be reviewed" if confidence score not provided (will be moved after OCR)
                confidence_folder = "needs to be reviewed"
                logger.info(f"Confidence score not provided for source file {filename} - initially placing in needs to be reviewed (will reorganize after OCR)")
            
            # Extract basename from filename (remove any folder paths like "sample/file.jpg" -> "file.jpg")
            # This ensures bulk uploads with folder structure don't create nested folders
            filename_basename = os.path.basename(filename) if filename else filename
            # Also handle forward slashes for cross-platform compatibility
            if '/' in filename_basename:
                filename_basename = filename_basename.split('/')[-1]
            if '\\' in filename_basename:
                filename_basename = filename_basename.split('\\')[-1]
            
            # New path structure: main/{confidence_folder}/source/tenant_id/{filename_basename}_{timestamp}
            blob_path = f"main/{confidence_folder}/source/{tenant_id}/{filename_basename}_{timestamp}"
            
            logger.info(f"Uploading source file to blob storage: {filename} ({len(file_data)} bytes) to {blob_path}")
            
            # Validate file data
            if not file_data or len(file_data) == 0:
                raise ValueError("File data is empty")
            
            # Upload the file
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.upload_blob(
                file_data,
                content_type=content_type,
                overwrite=True
            )
            
            # Get blob URL
            blob_url = blob_client.url
            
            logger.info(f"Successfully uploaded source file: {filename} to {blob_path}")
            
            return {
                "success": True,
                "blob_path": blob_path,
                "blob_url": blob_url,
                "filename": filename,
                "tenant_id": tenant_id,
                "processing_id": processing_id,
                "folder": "source",
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"Failed to upload source file {filename}: {e}")
            return {
                "success": False,
                "error": "Failed to upload source file"
            }

    
    def list_tenant_files(self, tenant_id: str) -> List[Dict[str, str]]:
        """
        List all files for a specific tenant from all folders (source, processed, and legacy uploads).
        
        Args:
            tenant_id: Tenant ID to filter files
            
        Returns:
            List of file information dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            files = []
            
            # List files from new path structure and legacy folders
            prefixes = [
                f"main/Above-95%/source/{tenant_id}/",
                f"main/Above-95%/processed/{tenant_id}/",
                f"main/needs to be reviewed/source/{tenant_id}/",
                f"main/needs to be reviewed/processed/{tenant_id}/",
                f"source/{tenant_id}/",  # Legacy folder
                f"processed/{tenant_id}/",  # Legacy folder
                f"uploads/blob_data/{tenant_id}/"  # Legacy folder
            ]
            
            for prefix in prefixes:
                blob_list = self.container_client.list_blobs(name_starts_with=prefix)
                
                for blob in blob_list:
                    # Extract processing_id and filename from path
                    # Handle new format: main/{confidence_folder}/source|processed/{tenant_id}/{filename}
                    # Handle legacy format: source|processed/{tenant_id}/.../{filename}
                    path_parts = blob.name.split('/')
                    processing_id = "unknown"
                    filename = path_parts[-1] if len(path_parts) > 0 else "unknown"
                    
                    # Check if it's the new format (starts with "main")
                    if len(path_parts) >= 4 and path_parts[0] == "main":
                        # New format: main/{confidence_folder}/source|processed/{tenant_id}/{filename}
                        # processing_id is not in the path for new format, use filename as identifier
                        processing_id = filename.rsplit('_', 1)[0] if '_' in filename else filename
                    elif len(path_parts) >= 3:
                        # Legacy format: source|processed/{tenant_id}/.../{filename}
                        # Check if path contains confidence folder (Above-95% or Below-95%)
                        if len(path_parts) >= 4 and (path_parts[2] == "Above-95%" or path_parts[2] == "Below-95%" or path_parts[2] == "needs to be reviewed"):
                            processing_id = path_parts[3] if len(path_parts) > 3 else "unknown"
                        else:
                            processing_id = path_parts[2] if len(path_parts) > 2 else "unknown"
                    
                    # Generate the blob URL properly
                    blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}"
                    files.append({
                        "name": filename,
                        "blob_name": blob.name,
                        "url": blob_url,
                        "size": blob.size,
                        "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                        "content_type": blob.content_settings.content_type if blob.content_settings else None,
                        "processing_id": processing_id,
                        "tenant_id": tenant_id
                    })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files for tenant {tenant_id}: {e}")
            return []
    
    def list_files_for_tenant(self, tenant_id: str) -> List[Dict[str, str]]:
        """
        Alias for list_tenant_files to maintain backward compatibility.
        
        Args:
            tenant_id: Tenant ID to filter files
            
        Returns:
            List of file information dictionaries
        """
        return self.list_tenant_files(tenant_id)
    
    def list_all_files(self) -> List[Dict[str, str]]:
        """
        List all files in the blob storage from all folders (admin only).
        
        Returns:
            List of all file information dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            files = []
            
            # List files from new path structure and legacy folders
            prefixes = [
                "main/Above-95%/source/",
                "main/Above-95%/processed/",
                "main/needs to be reviewed/source/",
                "main/needs to be reviewed/processed/",
                "source/",  # Legacy folder
                "processed/",  # Legacy folder
                "uploads/blob_data/"  # Legacy folder
            ]
            
            for prefix in prefixes:
                blob_list = self.container_client.list_blobs(name_starts_with=prefix)
                
                for blob in blob_list:
                    # Extract tenant_id and processing_id from path
                    # Handle new format: main/{confidence_folder}/source|processed/{tenant_id}/{filename}
                    # Handle legacy format: source|processed/{tenant_id}/.../{filename}
                    path_parts = blob.name.split('/')
                    tenant_id = "unknown"
                    processing_id = "unknown"
                    filename = path_parts[-1] if len(path_parts) > 0 else "unknown"
                    
                    # Check if it's the new format (starts with "main")
                    if len(path_parts) >= 4 and path_parts[0] == "main":
                        # New format: main/{confidence_folder}/source|processed/{tenant_id}/{filename}
                        tenant_id = path_parts[3] if len(path_parts) > 3 else "unknown"
                        processing_id = filename.rsplit('_', 1)[0] if '_' in filename else filename
                    elif len(path_parts) >= 3:
                        # Legacy format: source|processed/{tenant_id}/.../{filename}
                        tenant_id = path_parts[1]
                        # Check if path contains confidence folder
                        if len(path_parts) >= 4 and (path_parts[2] == "Above-95%" or path_parts[2] == "Below-95%" or path_parts[2] == "needs to be reviewed"):
                            processing_id = path_parts[3] if len(path_parts) > 3 else "unknown"
                        else:
                            processing_id = path_parts[2] if len(path_parts) > 2 else "unknown"
                    
                    # Generate the blob URL properly
                    blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}"
                    files.append({
                        "name": filename,
                        "blob_name": blob.name,
                        "url": blob_url,
                        "size": blob.size,
                        "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                        "content_type": blob.content_settings.content_type if blob.content_settings else None,
                        "processing_id": processing_id,
                        "tenant_id": tenant_id
                    })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list all files: {e}")
            return []
    
    def get_folder_structure(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get organized folder structure for blob storage.
        
        Args:
            tenant_id: Optional tenant ID to filter structure
            
        Returns:
            Nested dictionary representing folder structure
        """
        if not self.is_available():
            return {}
        
        try:
            structure = {}
            
            # Define folder prefixes to include (new structure and legacy)
            if tenant_id:
                prefixes = [
                    f"main/Above-95%/source/{tenant_id}/",
                    f"main/Above-95%/processed/{tenant_id}/",
                    f"main/needs to be reviewed/source/{tenant_id}/",
                    f"main/needs to be reviewed/processed/{tenant_id}/",
                    f"source/{tenant_id}/",  # Legacy folder
                    f"processed/{tenant_id}/",  # Legacy folder
                    f"uploads/blob_data/{tenant_id}/"  # Legacy folder
                ]
            else:
                prefixes = [
                    "main/Above-95%/source/",
                    "main/Above-95%/processed/",
                    "main/needs to be reviewed/source/",
                    "main/needs to be reviewed/processed/",
                    "source/",  # Legacy folder
                    "processed/",  # Legacy folder
                    "uploads/blob_data/"  # Legacy folder
                ]
            
            for prefix in prefixes:
                blob_list = self.container_client.list_blobs(name_starts_with=prefix)
                
                for blob in blob_list:
                    path_parts = blob.name.split('/')
                    
                    # Navigate/create folder structure
                    current = structure
                    for i, part in enumerate(path_parts):
                        if i == len(path_parts) - 1:  # Last part is filename
                            # Generate the blob URL properly
                            blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}"
                            current[part] = {
                                "type": "file",
                                "url": blob_url,
                                "size": blob.size,
                                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                                "folder_type": path_parts[0] if path_parts else "unknown"
                            }
                        else:
                            if part not in current:
                                current[part] = {"type": "folder", "contents": {}}
                            current = current[part]["contents"]
            
            return structure
            
        except Exception as e:
            logger.error(f"Failed to get folder structure: {e}")
            return {}
    
    def delete_file(self, blob_name: str) -> bool:
        """
        Delete a file from blob storage.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Successfully deleted {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {blob_name}: {e}")
            return False
    
    def move_blob(self, source_blob_name: str, destination_blob_name: str) -> bool:
        """
        Move a blob from one path to another in Azure Blob Storage.
        This is done by copying the blob and then deleting the source.
        
        Args:
            source_blob_name: Current blob path
            destination_blob_name: New blob path
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            import time
            
            source_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=source_blob_name
            )
            destination_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=destination_blob_name
            )
            
            # Copy blob to new location
            copy_props = destination_client.start_copy_from_url(source_client.url)
            logger.info(f"Started copy from {source_blob_name} to {destination_blob_name}")
            
            # Wait for copy to complete (with timeout)
            max_wait_time = 30  # seconds
            wait_interval = 0.5  # seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                props = destination_client.get_blob_properties()
                copy_status = props.copy.status if props.copy else None
                
                if copy_status == "success":
                    logger.info(f"Copy completed successfully: {destination_blob_name}")
                    break
                elif copy_status == "pending":
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    continue
                else:
                    # Copy failed or aborted
                    logger.error(f"Copy failed with status: {copy_status}")
                    return False
            
            if elapsed_time >= max_wait_time:
                logger.warning(f"Copy operation timed out for {destination_blob_name}, but continuing with delete")
            
            # Delete source blob
            source_client.delete_blob()
            logger.info(f"Deleted source blob: {source_blob_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to move blob from {source_blob_name} to {destination_blob_name}: {e}")
            return False
    
    def reorganize_source_file_by_confidence(self, blob_path: str, tenant_id: str, 
                                             processing_id: str, filename: str, 
                                             confidence_score: float) -> Optional[str]:
        """
        Move a source file to the appropriate folder based on confidence score.
        FIRST checks the confidence score, THEN moves the file to the correct folder.
        
        Args:
            blob_path: Current blob path of the source file
            tenant_id: Tenant ID
            processing_id: Processing ID
            filename: Original filename
            confidence_score: Confidence score (0-1.0 for decimal or 0-100 for percentage)
            
        Returns:
            New blob path if successful, None otherwise
        """
        if not self.is_available():
            logger.error("Azure Blob Storage not available for reorganization")
            return None
        
        try:
            # STEP 1: Validate and normalize confidence score
            if confidence_score is None:
                logger.error(f"Cannot reorganize {filename}: confidence_score is None")
                return None
            
            try:
                confidence_score = float(confidence_score)
            except (ValueError, TypeError) as e:
                logger.error(f"Cannot reorganize {filename}: invalid confidence_score {confidence_score}: {e}")
                return None
            
            # STEP 2: Normalize confidence score and determine target folder
            # Normalize confidence score: if it's between 0-1, treat as decimal (0.95 = 95%)
            # If it's > 1, treat as percentage (95 = 95%)
            if confidence_score <= 1.0:
                # Confidence is in 0-1 format, compare with 0.95
                threshold = 0.95
                score_display = f"{confidence_score * 100:.2f}%"
                is_above_95 = confidence_score >= 0.95
            else:
                # Confidence is in 0-100 format, compare with 95.0
                threshold = 95.0
                score_display = f"{confidence_score:.2f}%"
                is_above_95 = confidence_score >= 95.0
            
            # STEP 3: Determine target folder based on confidence score
            if is_above_95:
                confidence_folder = "Above-95%"
                logger.info(f"[CHECK] Confidence score for {filename}: {score_display} >= 95% -> Moving to Above-95% folder")
            else:
                confidence_folder = "needs to be reviewed"
                logger.info(f"[CHECK] Confidence score for {filename}: {score_display} < 95% -> Moving to needs to be reviewed folder")
            
            # STEP 4: Extract timestamp from current blob path
            # Handle both old format (source/tenant_id/...) and new format (main/.../source/tenant_id/...)
            path_parts = blob_path.split('/')
            timestamp_part = None
            
            # Find the filename part which should contain timestamp
            if len(path_parts) > 0:
                last_part = path_parts[-1]
                # Extract timestamp from filename_timestamp format
                if '_' in last_part:
                    parts = last_part.rsplit('_', 1)
                    if len(parts) == 2:
                        timestamp_part = parts[1]
            
            # If we couldn't extract timestamp, generate a new one
            if not timestamp_part:
                timestamp_part = datetime.now().strftime("%Y%m%d_%H%M%S")
                logger.warning(f"Could not extract timestamp from {blob_path}, generating new one: {timestamp_part}")
            
            # STEP 5: Extract basename from filename (remove any folder paths like "sample/file.jpg" -> "file.jpg")
            # This ensures bulk uploads with folder structure don't create nested folders
            filename_basename = os.path.basename(filename) if filename else filename
            # Also handle forward slashes for cross-platform compatibility
            if '/' in filename_basename:
                filename_basename = filename_basename.split('/')[-1]
            if '\\' in filename_basename:
                filename_basename = filename_basename.split('\\')[-1]
            
            # STEP 6: Construct new blob path with correct confidence folder
            # New path structure: main/{confidence_folder}/source/tenant_id/{filename_basename}_{timestamp}
            new_blob_path = f"main/{confidence_folder}/source/{tenant_id}/{filename_basename}_{timestamp_part}"
            
            # STEP 7: Move file if path is different
            if blob_path != new_blob_path:
                logger.info(f"[MOVE] Moving file from {blob_path} to {new_blob_path} (confidence: {score_display})")
                if self.move_blob(blob_path, new_blob_path):
                    logger.info(f"[SUCCESS] Successfully moved file to {new_blob_path} based on confidence {score_display}")
                    return new_blob_path
                else:
                    logger.error(f"[FAILED] Failed to move file from {blob_path} to {new_blob_path}")
                    return None
            else:
                logger.info(f"[SKIP] File already in correct location: {blob_path} (confidence: {score_display})")
                return blob_path
                
        except Exception as e:
            logger.error(f"[ERROR] Failed to reorganize source file {blob_path}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def download_source_file(self, blob_name: str) -> Optional[bytes]:
        """
        Download a file from Azure Blob Storage source folder.
        
        Args:
            blob_name: Name of the blob to download (can be full path or just filename)
            
        Returns:
            File content as bytes, or None if not found
        """
        if not self.is_available():
            logger.warning("Azure Blob Storage not available")
            return None
        
        try:
            # Ensure blob_name starts with source/ if it's a full path
            if not blob_name.startswith("source/"):
                blob_name = f"source/{blob_name}"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Download the blob
            download_stream = blob_client.download_blob()
            file_data = download_stream.readall()
            
            logger.info(f"Successfully downloaded source file: {blob_name} ({len(file_data)} bytes)")
            return file_data
            
        except ResourceNotFoundError:
            logger.warning(f"Source file not found: {blob_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to download source file {blob_name}: {e}")
            return None

    def download_file(self, blob_name: str) -> Optional[bytes]:
        """
        Download a file from blob storage.
        
        Args:
            blob_name: Name of the blob to download
            
        Returns:
            File content as bytes, or None if failed
        """
        if not self.is_available():
            return None
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            return blob_client.download_blob().readall()
            
        except Exception as e:
            logger.error(f"Failed to download {blob_name}: {e}")
            return None
    
    def upload_processed_json(self, json_data: Dict[str, Any], filename: str, tenant_id: str, 
                             processing_id: str) -> Dict[str, str]:
        """
        Upload processed JSON data to blob storage in the processed folder.
        
        Args:
            json_data: The processed JSON data to upload (should contain confidence_score or ocr_confidence_score)
            filename: Original filename (used to generate JSON filename)
            tenant_id: Tenant ID for organization
            processing_id: Processing ID for organization
            
        Returns:
            Dictionary with upload result information
        """
        if not self.is_available():
            raise ValueError("Azure Blob Storage not available")
        
        try:
            import json as json_module
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Extract confidence score from json_data (prefer ocr_confidence_score, fallback to confidence_score)
            # Also check nested extraction_result.confidence_score for template-based processing
            confidence_score = None
            if isinstance(json_data, dict):
                # First try ocr_confidence_score (preferred)
                confidence_score = json_data.get("ocr_confidence_score")
                # Mask filename to prevent PHI/PII leakage
                file_ext = os.path.splitext(filename)[1] if filename else ""
                masked_filename = f"***{file_ext}"
                logger.debug(f"Extracted ocr_confidence_score for {masked_filename}")
                
                # If not found, try confidence_score
                if confidence_score is None:
                    confidence_score = json_data.get("confidence_score")
                    logger.debug(f"Extracted confidence_score for {masked_filename}")
                
                # If not found at top level, check nested extraction_result
                if confidence_score is None and "extraction_result" in json_data:
                    extraction_result = json_data.get("extraction_result", {})
                    if isinstance(extraction_result, dict):
                        confidence_score = extraction_result.get("confidence_score")
                        logger.debug(f"Extracted confidence_score from extraction_result for {masked_filename}")
            
            # STEP 1: Check and validate confidence score
            # Mask filename to prevent PHI/PII leakage
            file_ext = os.path.splitext(filename)[1] if filename else ""
            masked_filename = f"***{file_ext}"
            logger.info(
                f"[CHECK] Final confidence score extracted for {masked_filename}: "
                f"{'present' if confidence_score is not None else 'missing'}"
            )
            
            if confidence_score is None:
                # Default to "needs to be reviewed" if confidence score not found
                confidence_folder = "needs to be reviewed"
                logger.warning(f"[CHECK] Confidence score not found in json_data for {filename}, defaulting to needs to be reviewed")
            else:
                # STEP 2: Normalize confidence score format
                # Normalize confidence score: if it's between 0-1, treat as decimal (0.95 = 95%)
                # If it's > 1, treat as percentage (95 = 95%)
                try:
                    confidence_score = float(confidence_score)
                    if confidence_score <= 1.0:
                        # Confidence is in 0-1 format, compare with 0.95
                        threshold = 0.95
                        score_display = f"{confidence_score * 100:.2f}%"
                        is_above_95 = confidence_score >= 0.95
                    else:
                        # Confidence is in 0-100 format, compare with 95.0
                        threshold = 95.0
                        score_display = f"{confidence_score:.2f}%"
                        is_above_95 = confidence_score >= 95.0
                    
                    # STEP 3: Determine folder based on confidence score check
                    if is_above_95:
                        confidence_folder = "Above-95%"
                        logger.info(f"[CHECK] Confidence score {score_display} >= 95% -> Placing in Above-95% folder")
                    else:
                        confidence_folder = "needs to be reviewed"
                        logger.info(f"[CHECK] Confidence score {score_display} < 95% -> Placing in needs to be reviewed folder")
                except (ValueError, TypeError) as e:
                    logger.error(f"[ERROR] Invalid confidence score value for {masked_filename}: {e}")
                    confidence_folder = "needs to be reviewed"
                    logger.warning(f"[CHECK] Using default needs to be reviewed folder due to invalid confidence score")
            
            # Extract basename from filename (remove any folder paths like "sample/file.jpg" -> "file.jpg")
            # This ensures bulk uploads with folder structure don't create nested folders
            filename_basename = os.path.basename(filename) if filename else filename
            # Also handle forward slashes for cross-platform compatibility
            if '/' in filename_basename:
                filename_basename = filename_basename.split('/')[-1]
            if '\\' in filename_basename:
                filename_basename = filename_basename.split('\\')[-1]
            
            # Generate JSON filename from basename
            base_filename = filename_basename.rsplit('.', 1)[0] if '.' in filename_basename else filename_basename
            json_filename = f"{base_filename}_extracted_data.json"
            # New path structure: main/{confidence_folder}/processed/tenant_id/{timestamp}_{json_filename}
            blob_path = f"main/{confidence_folder}/processed/{tenant_id}/{timestamp}_{json_filename}"
            
            logger.info(f"Uploading processed JSON data to blob storage: {json_filename} to {blob_path}")
            
            # Convert dict to JSON bytes
            json_bytes = json_module.dumps(json_data, ensure_ascii=False, indent=2).encode('utf-8')
            
            # Upload the JSON data
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.upload_blob(
                json_bytes,
                content_type="application/json",
                overwrite=True
            )
            
            # Get blob URL
            blob_url = blob_client.url
            
            logger.info(f"Successfully uploaded processed JSON: {json_filename} to {blob_path}")
            
            return {
                "success": True,
                "blob_path": blob_path,
                "blob_url": blob_url,
                "filename": json_filename,
                "tenant_id": tenant_id,
                "processing_id": processing_id,
                "folder": "processed",
                "timestamp": timestamp,
                "size_bytes": len(json_bytes)
            }
            
        except Exception as e:
            logger.error(f"Failed to upload processed JSON {filename}: {e}")
            return {
                "success": False,
                "error": "Failed to upload processed JSON data"
            }
    
    def list_bulk_source_files(self) -> List[Dict[str, str]]:
        """
        List all files in the bulk processing/source folder.
        
        Returns:
            List of file information dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            files = []
            prefix = "bulk processing/source/"
            
            blob_list = self.container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blob_list:
                # Skip folders (blobs ending with /)
                if blob.name.endswith('/'):
                    continue
                
                filename = blob.name.split('/')[-1]
                blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}"
                
                files.append({
                    "name": filename,
                    "blob_name": blob.name,
                    "url": blob_url,
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None
                })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list bulk source files: {e}")
            return []
    
    def check_file_processed(self, blob_name: str) -> bool:
        """
        Check if a file has already been processed by checking if it exists in processed folders.
        Checks for files with timestamp prefixes (e.g., 20240101_120000_filename_extracted_data.json).
        
        Args:
            blob_name: Full blob path (e.g., "bulk processing/source/file.pdf")
            
        Returns:
            True if file has been processed, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Extract filename from blob path
            filename = blob_name.split('/')[-1]
            base_filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            # Check if processed JSON exists in either Above-95% or needs to be reviewed folders
            # Look for files matching the pattern: {timestamp}_{base_filename}_extracted_data.json
            processed_prefixes = [
                "bulk processing/Above-95%/processed/",
                "bulk processing/needs to be reviewed/processed/"
            ]
            
            for prefix in processed_prefixes:
                try:
                    # List all blobs in the processed folder
                    blob_list = self.container_client.list_blobs(name_starts_with=prefix)
                    
                    for blob in blob_list:
                        # Check if this blob matches our file (with timestamp prefix)
                        blob_filename = blob.name.split('/')[-1]
                        # Pattern: {timestamp}_{base_filename}_extracted_data.json
                        if blob_filename.endswith(f"{base_filename}_extracted_data.json"):
                            logger.debug(f"File {filename} already processed (found at {blob.name})")
                            return True
                except Exception as e:
                    logger.warning(f"Error checking processed folder {prefix}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check if file {blob_name} is processed: {e}")
            return False
    
    def upload_bulk_processed_json(self, json_data: Dict[str, Any], filename: str, 
                                   confidence_score: float, tenant_id: str = "tenant_2") -> Dict[str, str]:
        """
        Upload processed JSON data to bulk processing folder based on confidence score.
        
        Args:
            json_data: The processed JSON data to upload
            filename: Original filename (used to generate JSON filename)
            confidence_score: Confidence score (0-1.0 for decimal or 0-100 for percentage)
            tenant_id: Tenant ID for organization (defaults to "tenant_2" if not provided)
            
        Returns:
            Dictionary with upload result information
        """
        if not self.is_available():
            return {"success": False, "error": "Azure Blob Storage not available"}
        
        try:
            import json as json_module
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Normalize confidence score and determine folder
            if confidence_score <= 1.0:
                threshold = 0.95
                score_display = f"{confidence_score * 100:.2f}%"
                is_above_95 = confidence_score >= 0.95
            else:
                threshold = 95.0
                score_display = f"{confidence_score:.2f}%"
                is_above_95 = confidence_score >= 95.0
            
            # Determine target folder based on confidence score
            if is_above_95:
                confidence_folder = "Above-95%"
                logger.info(f"[BULK] Confidence score {score_display} >= 95% -> Placing in Above-95% folder")
            else:
                confidence_folder = "needs to be reviewed"
                logger.info(f"[BULK] Confidence score {score_display} < 95% -> Placing in needs to be reviewed folder")
            
            # Extract basename from filename (remove any folder paths like "sample/file.jpg" -> "file.jpg")
            # This ensures bulk uploads with folder structure don't create nested folders
            filename_basename = os.path.basename(filename) if filename else filename
            # Also handle forward slashes for cross-platform compatibility
            if '/' in filename_basename:
                filename_basename = filename_basename.split('/')[-1]
            if '\\' in filename_basename:
                filename_basename = filename_basename.split('\\')[-1]
            
            # Generate JSON filename from basename
            base_filename = filename_basename.rsplit('.', 1)[0] if '.' in filename_basename else filename_basename
            json_filename = f"{base_filename}_extracted_data.json"
            
            # Path structure: main/{confidence_folder}/processed/{tenant_id}/{timestamp}_{json_filename}
            # Changed from "bulk processing" to "main" to match single file upload structure
            blob_path = f"main/{confidence_folder}/processed/{tenant_id}/{timestamp}_{json_filename}"
            
            logger.info(f"[BULK] Uploading processed JSON to: {blob_path}")
            
            # Convert dict to JSON bytes
            json_bytes = json_module.dumps(json_data, ensure_ascii=False, indent=2).encode('utf-8')
            
            # Upload the JSON data
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.upload_blob(
                json_bytes,
                content_type="application/json",
                overwrite=True
            )
            
            # Get blob URL
            blob_url = blob_client.url
            
            logger.info(f"[BULK] Successfully uploaded processed JSON: {json_filename} to {blob_path}")
            
            return {
                "success": True,
                "blob_path": blob_path,
                "blob_url": blob_url,
                "filename": json_filename,
                "folder": confidence_folder,
                "timestamp": timestamp,
                "size_bytes": len(json_bytes)
            }
            
        except Exception as e:
            logger.error(f"[BULK] Failed to upload processed JSON {filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def download_bulk_file(self, blob_name: str) -> Optional[bytes]:
        """
        Download a file from bulk processing source folder.
        
        Args:
            blob_name: Full blob path (e.g., "bulk processing/source/file.pdf")
            
        Returns:
            File content as bytes, or None if failed
        """
        if not self.is_available():
            return None
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            return blob_client.download_blob().readall()
            
        except Exception as e:
            logger.error(f"[BULK] Failed to download {blob_name}: {e}")
            return None    
    def find_source_file_from_processed(self, processed_blob_name: str) -> Optional[str]:
        """
        Find the source file path from a processed file blob name.
        
        Args:
            processed_blob_name: Full blob path of the processed JSON file
                (e.g., "main/Above-95%/processed/tenant_2/20251113_102709_pdf-sl-report-270237207-pdf_compress_extracted_data.json")
            
        Returns:
            Source file blob path if found, None otherwise
        """
        if not self.is_available():
            logger.error("Azure Blob Storage not available")
            return None
        
        try:
            # Extract filename from blob path
            processed_filename = processed_blob_name.split('/')[-1]
            logger.info(f"Searching for source file matching processed file: {processed_filename}")
            
            # Extract tenant_id from path
            path_parts = processed_blob_name.split('/')
            tenant_id = None
            confidence_folder = None
            
            # Check if it's new format: main/{confidence_folder}/processed/{tenant_id}/{filename}
            if len(path_parts) >= 4 and path_parts[0] == "main":
                confidence_folder = path_parts[1] if len(path_parts) > 1 else None
                tenant_id = path_parts[3] if len(path_parts) > 3 else None
            elif len(path_parts) >= 2:
                # Legacy format: processed/{tenant_id}/.../{filename}
                tenant_id = path_parts[1] if len(path_parts) > 1 else None
            
            if not tenant_id:
                logger.error(f"Could not extract tenant_id from processed blob path: {processed_blob_name}")
                return None
            
            # Parse processed filename to extract timestamp and base filename
            timestamp = None
            base_filename_without_ext = None
            
            # Try new format first: {timestamp}_{base_filename}_extracted_data.json
            if processed_filename.endswith('_extracted_data.json'):
                # Remove _extracted_data.json suffix
                name_without_suffix = processed_filename.replace('_extracted_data.json', '')
                # Timestamp pattern: YYYYMMDD_HHMMSS (8 digits, underscore, 6 digits)
                timestamp_match = re.match(r'^(\d{8}_\d{6})_(.+)$', name_without_suffix)
                if timestamp_match:
                    timestamp = timestamp_match.group(1)
                    base_filename_without_ext = timestamp_match.group(2)
                else:
                    # Fallback: split by first underscore
                    parts = name_without_suffix.split('_', 1)
                    if len(parts) >= 2:
                        timestamp = parts[0]
                        base_filename_without_ext = parts[1]
                    else:
                        base_filename_without_ext = name_without_suffix
            # Try legacy format
            elif '_processed_' in processed_filename:
                # Format: {base_filename}_processed_{timestamp}.json
                name_without_ext = processed_filename.replace('.json', '')
                parts = name_without_ext.split('_processed_')
                if len(parts) == 2:
                    base_filename_without_ext = parts[0]
                    timestamp = parts[1]
            
            if not base_filename_without_ext:
                logger.error(f"Could not extract base filename from processed filename: {processed_filename}")
                return None
            
            logger.info(f"Extracted - timestamp: {timestamp}, base_filename: {base_filename_without_ext}, tenant_id: {tenant_id}")
            
            # Search for source files in both new and legacy locations
            search_prefixes = []
            
            if confidence_folder:
                # New format: main/{confidence_folder}/source/{tenant_id}/
                search_prefixes.append(f"main/{confidence_folder}/source/{tenant_id}/")
            else:
                # Try both confidence folders if confidence_folder not found
                search_prefixes.append(f"main/Above-95%/source/{tenant_id}/")
                search_prefixes.append(f"main/needs to be reviewed/source/{tenant_id}/")
            
            # Legacy format: source/{tenant_id}/
            search_prefixes.append(f"source/{tenant_id}/")
            
            # Search for matching source files
            for prefix in search_prefixes:
                try:
                    blob_list = self.container_client.list_blobs(name_starts_with=prefix)
                    best_match = None
                    
                    for blob in blob_list:
                        source_filename = blob.name.split('/')[-1]
                        
                        # Check if source filename starts with base filename
                        if source_filename.startswith(base_filename_without_ext):
                            if timestamp:
                                # If timestamp is provided, check if it's in the filename
                                if timestamp in source_filename:
                                    logger.info(f"Found exact match: {blob.name}")
                                    return blob.name
                                else:
                                    # Store as best match if no exact match found yet
                                    if not best_match:
                                        best_match = blob.name
                            else:
                                # No timestamp to match, return first match
                                logger.info(f"Found match (no timestamp): {blob.name}")
                                return blob.name
                    
                    # If we found a best match but no exact match, return it
                    if best_match:
                        logger.info(f"Found best match: {best_match}")
                        return best_match
                        
                except Exception as e:
                    logger.error(f"Error searching for source files with prefix {prefix}: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
            
            logger.warning(f"No source file found for processed file: {processed_blob_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding source file from processed file {processed_blob_name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

            return None