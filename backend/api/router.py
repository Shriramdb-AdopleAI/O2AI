from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response, Depends, Body
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
import logging
import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from utility.utils import ocr_from_path, calculate_ocr_confidence, calculate_key_value_pair_confidence_scores
from utility.config import setup_logging
from core.enhanced_text_processor import EnhancedTextProcessor
from core.excel_exporter import ExcelExporter
from auth.auth_utils import get_current_active_user
from models.database import User, get_db, ProcessedFile
from sqlalchemy.orm import Session
from services.azure_blob_service import AzureBlobService
from services.template_mapper import TemplateMapper
from services.epic_fhir_service import EpicFHIRService
from core.celery_tasks import process_document, process_batch_documents
from core.celery_app import celery_app
import base64

# logging
logger = setup_logging()

router = APIRouter(prefix="/api/v1")
@router.get("/health")
async def health_check():
    """Lightweight health endpoint for container orchestration."""
    return {"status": "ok"}

@router.get("/epic/status")
async def epic_status_check():
    """Check Epic FHIR service configuration status."""
    try:
        epic_service = EpicFHIRService()
        
        status = {
            "is_available": epic_service.is_available(),
            "client_id": f"{epic_service.client_id[:4]}...{epic_service.client_id[-4:]}" if epic_service.client_id and len(epic_service.client_id) > 8 else "***" if epic_service.client_id else None,
            "has_private_key": bool(epic_service.private_key),
            "has_client_secret": bool(epic_service.client_secret),
            "fhir_server_url": epic_service.fhir_server_url,
            "token_url": epic_service.token_url,
            "jwks_url": epic_service.jwks_url,
            "jwks_key_id": epic_service.jwks_key_id,
            "scope": epic_service.scope
        }
        
        # Try to get an access token
        if epic_service.is_available():
            token = epic_service._get_access_token()
            status["can_get_token"] = bool(token)
            # SECURITY: Never expose access tokens, even partially
            # Removed token_preview to prevent credential leakage
        else:
            status["can_get_token"] = False
            status["error"] = "Service not available - check configuration"
        
        return status
    except Exception as e:
        logger.error(f"Error checking Epic status: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "error": "Failed to check Epic status",
            "is_available": False
        }

@router.get("/epic/jwks", include_in_schema=True)
async def get_epic_jwks():
    """
    Expose JWKS (JSON Web Key Set) for Epic Backend Systems authentication.
    Epic will call this endpoint to validate the JWT signature.
    """
    try:
        epic_service = EpicFHIRService()
        jwks = epic_service.get_jwks()
        
        if not jwks:
            return Response(
                content=json.dumps({"error": "JWKS not available (private key not configured)"}), 
                status_code=500, 
                media_type="application/json"
            )
            
        return jwks
    except Exception as e:
        logger.error(f"Error serving JWKS: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            content=json.dumps({"error": "Failed to serve JWKS"}), 
            status_code=500, 
            media_type="application/json"
        )

def check_blob_access(blob_name: str, current_user: User) -> bool:
    """Check if the current user has access to the specified blob."""
    if current_user.is_admin:
        return True
    
    # Check if the blob path belongs to the current user's tenant
    # Handle new path structure: main/{confidence_folder}/source|processed/{tenant_id}/...
    # Handle legacy path structure: source|processed/{tenant_id}/...
    
    # Decode blob name to handle URL encoded characters (like %20 for space, %25 for %)
    decoded_blob_name = unquote(blob_name)
    
    allowed_prefixes = [
        f"main/Above-95%/source/{current_user.tenant_id}/",
        f"main/Above-95%/processed/{current_user.tenant_id}/",
        f"main/Above-95/source/{current_user.tenant_id}/",  # Handle problematic folder without %
        f"main/Above-95/processed/{current_user.tenant_id}/", # Handle problematic folder without %
        f"main/needs to be reviewed/source/{current_user.tenant_id}/",
        f"main/needs to be reviewed/processed/{current_user.tenant_id}/",
        f"source/{current_user.tenant_id}/",  # Legacy folder
        f"processed/{current_user.tenant_id}/",  # Legacy folder
        f"uploads/blob_data/{current_user.tenant_id}/"  # Legacy folder
    ]
    
    return any(decoded_blob_name.startswith(prefix) for prefix in allowed_prefixes)

# Multi-tenancy support
import uuid
from datetime import datetime

# Get the backend directory (parent of api directory)
BACKEND_DIR = Path(__file__).parent.parent
DATA_DIR = BACKEND_DIR / "data"


def validate_tenant_id(tenant_id: str) -> str:
    """Validate and sanitize tenant_id to prevent path traversal attacks.
    
    Args:
        tenant_id: The tenant ID to validate
        
    Returns:
        Sanitized tenant_id
        
    Raises:
        ValueError: If tenant_id contains invalid characters or path traversal attempts
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    
    # Explicitly reject parent directory traversal sequences
    if ".." in tenant_id:
        raise ValueError(f"Invalid tenant_id: {tenant_id}. Parent directory references are not allowed.")
    
    # Remove any path separators and non-allowed characters
    # Only allow alphanumeric characters, hyphens, and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', tenant_id)
    
    if not sanitized or sanitized != tenant_id:
        raise ValueError(f"Invalid tenant_id: {tenant_id}. Only alphanumeric characters, hyphens, and underscores are allowed.")
    
    # Additional check: ensure the sanitized ID is not empty and doesn't start with a dot
    if sanitized.startswith('.') or len(sanitized) == 0:
        raise ValueError(f"Invalid tenant_id: {tenant_id}")
    
    return sanitized


def get_tenant_dir(validated_tenant_id: str) -> Path:
    """Return a safe tenant directory path under DATA_DIR / 'tenants'.
    
    The input must already have been validated with validate_tenant_id.
    This function additionally enforces that the resulting path is
    contained within the expected base directory.
    """
    tenant_dir = DATA_DIR / "tenants" / validated_tenant_id

    # Verify the resolved path is within the expected directory (defense in depth)
    tenant_dir_resolved = tenant_dir.resolve()
    expected_base = (DATA_DIR / "tenants").resolve()
    try:
        # Ensure tenant_dir_resolved is inside expected_base (or equal to it)
        tenant_dir_resolved.relative_to(expected_base)
    except ValueError as e:
        logger.error(f"Path traversal attempt detected for tenant_id '{validated_tenant_id}': {e}")
        raise HTTPException(status_code=400, detail="Invalid tenant path")

    return tenant_dir


def load_tenant_history(tenant_id: str) -> List[Dict[str, Any]]:
    """Load processing history for a specific tenant from data folder."""
    # Validate tenant_id to prevent path traversal
    try:
        validated_tenant_id = validate_tenant_id(tenant_id)
    except ValueError as e:
        logger.error(f"Invalid tenant_id in load_tenant_history: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Compute a safe tenant directory based on backend data directory
    try:
        tenant_dir = get_tenant_dir(validated_tenant_id)
    except HTTPException:
        # get_tenant_dir already logged the error with details
        raise
    
    history_file = tenant_dir / "processing_history.json"
    
    # Create directory if it doesn't exist
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading history for tenant {validated_tenant_id}: {e}")
            return []
    return []

def save_tenant_history(tenant_id: str, history: List[Dict[str, Any]]):
    """Save processing history for a specific tenant to data folder."""
    # Validate tenant_id to prevent path traversal
    try:
        validated_tenant_id = validate_tenant_id(tenant_id)
    except ValueError as e:
        logger.error(f"Invalid tenant_id in save_tenant_history: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Use absolute path based on backend directory
    tenant_dir = DATA_DIR / "tenants" / validated_tenant_id
    history_file = tenant_dir / "processing_history.json"
    
    # Verify the resolved path is within the expected directory (defense in depth)
    try:
        history_file_resolved = history_file.resolve()
        expected_base = (DATA_DIR / "tenants").resolve()
        # Ensure history_file_resolved is within expected_base
        try:
            # Python 3.9+: use Path.is_relative_to for a clear containment check
            is_relative = history_file_resolved.is_relative_to(expected_base)  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback for Python < 3.9: compare commonpath of the string forms
            common_base = os.path.commonpath(
                [str(history_file_resolved), str(expected_base)]
            )
            is_relative = common_base == str(expected_base)
        
        if not is_relative:
            raise ValueError(f"Path traversal attempt detected: {tenant_id}")
    except (ValueError, OSError) as e:
        logger.error(f"Path validation failed for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid tenant path")
    
    # Create directory if it doesn't exist
    try:
        tenant_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error creating directory {tenant_dir} for tenant {validated_tenant_id}: {e}")
        raise
    
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved {len(history)} history entries to {history_file}")
    except (IOError, OSError, json.JSONEncodeError) as e:
        logger.error(f"Error saving history for tenant {validated_tenant_id} to {history_file}: {e}")
        raise

@router.post("/ocr/enhanced/process")
async def process_enhanced_ocr(
    file: UploadFile = File(..., description="File to process (PDF, PNG, JPG, JPEG)"),
    template_id: Optional[str] = Form(None, description="Optional template ID for structured extraction"),
    apply_preprocessing: bool = Form(True, description="Apply image preprocessing"),
    enhance_quality: bool = Form(True, description="Apply quality enhancements"),
    include_raw_text: bool = Form(True, description="Include raw OCR text in response"),
    include_metadata: bool = Form(True, description="Include processing metadata"),
    use_blob_workflow: bool = Form(True, description="Use source → process → processed workflow"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process uploaded file with enhanced OCR and AI-powered key-value extraction.
    
    Features:
    - Azure Computer Vision OCR with advanced preprocessing
    - AI-powered key-value pair extraction using Azure GPT
    - Optional template-based structured extraction
    - Document classification and summarization
    - Multi-tenant data isolation
    """
    try:
        # Validate file type
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPG, JPEG"
            )
        
        logger.info(f"Processing enhanced OCR for {file.filename} with preprocessing: {apply_preprocessing}, quality enhancement: {enhance_quality}")
        
        # Read file data
        file_data = await file.read()
        logger.info(f"Read file data: {len(file_data)} bytes for {file.filename}")
        
        # Generate processing ID and tenant ID
        processing_id = str(uuid.uuid4())
        tenant_id = getattr(current_user, 'tenant_id', f"tenant_{current_user.id}")
        
        # ===== DEDUPLICATION CHECK (INFO ONLY - NO LONGER BLOCKS PROCESSING) =====
        # Check if this exact file has already been processed (for logging only)
        import hashlib
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        existing_file = db.query(ProcessedFile).filter(
            ProcessedFile.file_hash == file_hash,
            ProcessedFile.tenant_id == tenant_id
        ).first()
        
        if existing_file:
            logger.info(f"⚠️ DUPLICATE FILE DETECTED: {file.filename} (hash: {file_hash[:16]}...)")
            logger.info(f"   Previous processing ID: {existing_file.processing_id}")
            logger.info(f"   First processed: {existing_file.created_at}")
            logger.info(f"   ⚠️ Continuing with new processing and blob upload despite duplicate...")
        else:
            logger.info(f"✓ New file detected: {file.filename} (hash: {file_hash[:16]}...)")
        # ===== END DEDUPLICATION CHECK =====
        
        # Step 1: Upload to source folder if using blob workflow
        source_blob_info = None
        if use_blob_workflow:
            try:
                blob_service = AzureBlobService()
                if blob_service.is_available():
                    source_blob_info = blob_service.upload_source_document(
                        file_data=file_data,
                        filename=file.filename or "unknown",
                        tenant_id=tenant_id,
                        processing_id=processing_id,
                        content_type=file.content_type or "application/octet-stream",
                        skip_duplicate_check=True  # Always upload to blob, even for duplicates
                    )
                    
                    if not source_blob_info.get("success"):
                        logger.warning(f"Failed to upload to source folder: {source_blob_info.get('error')}")
                        # Continue with direct processing if source upload fails
                    else:
                        logger.info(f"File uploaded to source folder: {source_blob_info['blob_path']}")
                else:
                    logger.info("Azure Blob Storage not available - skipping source upload")
                    source_blob_info = {"success": False, "error": "Azure Blob Storage not available", "skipped": True}
                    
            except Exception as e:
                logger.warning(f"Azure Blob Storage error (non-critical): {e}")
                source_blob_info = {"success": False, "error": "Azure Blob Storage error", "skipped": True}
        
        # Step 2: Process with Azure Computer Vision OCR
        result = await ocr_from_path(
            file_data=file_data,
            original_filename=file.filename or "unknown",
            ocr_engine="azure_computer_vision",
            ground_truth="",
            apply_preprocessing=apply_preprocessing,
            enhance_quality=enhance_quality
        )
        
        # Initialize enhanced text processor
        text_processor = EnhancedTextProcessor()
        
        # Process with AI-powered key-value extraction (with or without template)
        if template_id:
            # Load template and process with template
            template_mapper = TemplateMapper()
            tenant_template = template_mapper.get_template(template_id, current_user.tenant_id)
            if not tenant_template:
                raise HTTPException(status_code=404, detail="Template not found for tenant")
            
            # Build fields map: { display name -> { type, description } }
            fields_map = {}
            for f in tenant_template.get("fields", []):
                key = f.get("display_name") or f.get("key")
                if not key:
                    continue
                fields_map[key] = {
                    "type": f.get("data_type", "text"),
                    "description": f.get("description", "")
                }
            llm_template = {
                "name": tenant_template.get("filename", "Template"),
                "description": "Tenant Excel template",
                "fields": fields_map
            }
            
            # Process with template
            processing_result = await text_processor.process_with_template(
                ocr_text=result.get("combined_text", ""),
                template=llm_template,
                filename=file.filename or "unknown"
            )
            
            # Create mapping status/metrics based on LLM output
            document_id = str(uuid.uuid4())
            mapping_result = template_mapper.map_document_to_template(
                template_id=template_id,
                tenant_id=current_user.tenant_id,
                extracted_data=processing_result.key_value_pairs,
                document_id=document_id,
                filename=file.filename or "unknown"
            )
            
            logger.info(f"Processed with template {template_id}: {len(processing_result.key_value_pairs)} fields extracted")
        else:
            # Process without template (original behavior)
            processing_result = await text_processor.process_without_template(
                ocr_text=result.get("combined_text", ""),
                filename=file.filename or "unknown"
            )
            mapping_result = None
            logger.info(f"Processed without template: {len(processing_result.key_value_pairs)} fields extracted")
        
        # Document classification
        document_classification = text_processor.classify_document_type(
            ocr_text=result.get("combined_text", "")
        )
        
        # Calculate OCR confidence from text_blocks
        ocr_confidence_score = calculate_ocr_confidence(result)
        
        # Calculate confidence scores for each key-value pair
        kv_confidence_scores = calculate_key_value_pair_confidence_scores(
            key_value_pairs=processing_result.key_value_pairs,
            ocr_result=result,
            raw_ocr_text=result.get("combined_text", "")
        )
        
        # Identify low-confidence pairs (< 95%) for later manual analysis
        low_confidence_pairs = {}
        low_confidence_scores_filtered = {}
        for key, value in processing_result.key_value_pairs.items():
            conf = kv_confidence_scores.get(key)
            if conf is not None:
                # Normalize confidence if needed
                normalized_conf = conf / 100 if conf > 1 else conf
                if normalized_conf < 0.95:
                    low_confidence_pairs[key] = value
                    low_confidence_scores_filtered[key] = normalized_conf
        
        # Store file as base64 for later low-confidence analysis
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        
        # Log low-confidence pairs count
        if low_confidence_pairs:
            logger.info(f"Identified {len(low_confidence_pairs)} low-confidence pairs for {file.filename} - ready for manual analysis")
        
        # Reorganize source file based on confidence score if it was uploaded
        # FIRST check the confidence score, THEN move the file to the correct folder
        if source_blob_info and source_blob_info.get("success") and source_blob_info.get("blob_path"):
            logger.info(f"[CHECK] Checking confidence score for source file: {ocr_confidence_score}")
            try:
                blob_service = AzureBlobService()
                if blob_service.is_available():
                    new_blob_path = blob_service.reorganize_source_file_by_confidence(
                        blob_path=source_blob_info["blob_path"],
                        tenant_id=tenant_id,
                        processing_id=processing_id,
                        filename=file.filename or "unknown",
                        confidence_score=ocr_confidence_score
                    )
                    if new_blob_path:
                        source_blob_info["blob_path"] = new_blob_path
                        logger.info(f"[SUCCESS] Reorganized source file to: {new_blob_path}")
                    else:
                        logger.warning(f"[WARNING] Failed to reorganize source file - returned None")
                else:
                    logger.warning(f"[WARNING] Azure Blob Storage not available for reorganization")
            except Exception as e:
                logger.error(f"[ERROR] Failed to reorganize source file by confidence: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Calculate total processing time (OCR + extraction)
        ocr_time = result.get("processing_time_seconds", 0) or result.get("processing_time", 0)
        extraction_time = processing_result.processing_time if hasattr(processing_result, 'processing_time') else 0
        total_processing_time = ocr_time + extraction_time
        
        # Step 3: Upload processed JSON data to processed folder (NO original files)
        json_upload_result = None
        try:
            blob_service = AzureBlobService()
            if blob_service.is_available():
                logger.info(f"Uploading JSON data to processed folder for {file.filename}")
                logger.info(f"Tenant ID: {tenant_id}, Processing ID: {processing_id}")
                
                # Upload processed JSON data
                processed_json_data = {
                    "file_info": {
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size_bytes": len(file_data),
                        "pages_processed": len(result.get("raw_ocr_results", []))
                    },
                    "key_value_pairs": processing_result.key_value_pairs,
                    "key_value_pair_confidence_scores": kv_confidence_scores,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score,
                    "ocr_confidence_score": ocr_confidence_score,
                    "document_classification": document_classification,
                    "processing_info": {
                        "processing_time": result.get("processing_time", 0),
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": "AI-powered" if text_processor.is_available() else "Basic pattern matching"
                    },
                    "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
                    "raw_ocr_results": result.get("raw_ocr_results", []),
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "text_length": len(result.get("combined_text", "")),
                        "ai_processing": text_processor.is_available()
                    } if include_metadata else None
                }
                
                json_upload_result = blob_service.upload_processed_json(
                    json_data=processed_json_data,
                    filename=file.filename or "unknown",
                    tenant_id=tenant_id,
                    processing_id=processing_id
                )
                
                if json_upload_result.get("success"):
                    logger.info(f"[SUCCESS] JSON data uploaded to processed folder: {json_upload_result['blob_path']}")
                else:
                    logger.warning(f"[ERROR] Failed to upload JSON data: {json_upload_result.get('error')}")
                    
            else:
                logger.info("Azure Blob Storage not available - skipping JSON upload")
                json_upload_result = {"success": False, "error": "Azure Blob Storage not available", "skipped": True}
        except Exception as e:
            logger.warning(f"Azure Blob Storage error (non-critical): {e}")
            json_upload_result = {"success": False, "error": "Azure Blob Storage error", "skipped": True}
        
        # Store null field tracking data
        try:
            from services.null_field_service import null_field_service
            logger.info(f"Storing null field tracking for {file.filename}...")
            null_field_service.store_null_fields(
                processing_id=processing_id,
                tenant_id=tenant_id,
                filename=file.filename or "unknown",
                extracted_fields=processing_result.key_value_pairs
            )
        except Exception as null_error:
            logger.error(f"✗ Failed to store null field tracking: {null_error}")

        # Store processed file data in database
        try:
            # Get unique_file_id from json_upload_result if available, otherwise use processing_id
            unique_file_id = json_upload_result.get("blob_path") if json_upload_result and json_upload_result.get("success") else processing_id
            
            # Calculate file hash for deduplication
            import hashlib
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Check if file already exists in database (by file_hash to prevent duplicates)
            existing_file = db.query(ProcessedFile).filter(
                ProcessedFile.file_hash == file_hash
            ).first()
            
            if existing_file:
                # Update existing entry
                existing_file.processing_id = unique_file_id
                existing_file.processed_blob_path = unique_file_id if json_upload_result and json_upload_result.get("success") else None
                existing_file.source_blob_path = source_blob_info.get("blob_path") if source_blob_info and source_blob_info.get("success") else None
                existing_file.processed_data = {
                    "key_value_pairs": processing_result.key_value_pairs,
                    "key_value_pair_confidence_scores": kv_confidence_scores,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score,
                    "ocr_confidence_score": ocr_confidence_score,
                    "document_classification": document_classification,
                    "processing_info": {
                        "processing_time": total_processing_time,
                        "ocr_time": ocr_time,
                        "extraction_time": extraction_time,
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": "Template-based AI extraction" if template_id else ("AI-powered" if text_processor.is_available() else "Basic pattern matching")
                    },
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "text_length": len(result.get("combined_text", "")),
                        "ai_processing": text_processor.is_available()
                    } if include_metadata else None
                }
                existing_file.ocr_confidence_score = str(ocr_confidence_score) if ocr_confidence_score else None
                existing_file.processing_time = str(total_processing_time) if total_processing_time else None
                existing_file.updated_at = datetime.utcnow()
                logger.info(f"💾 Updated existing processed file entry for {file.filename} (hash: {file_hash[:16]}...)")
            else:
                # Create new entry
                new_processed_file = ProcessedFile(
                    file_hash=file_hash,
                    processing_id=unique_file_id,
                    tenant_id=tenant_id,
                    filename=file.filename or "unknown",
                    source_blob_path=source_blob_info.get("blob_path") if source_blob_info and source_blob_info.get("success") else None,
                    processed_blob_path=unique_file_id if json_upload_result and json_upload_result.get("success") else None,
                    processed_data={
                        "key_value_pairs": processing_result.key_value_pairs,
                        "key_value_pair_confidence_scores": kv_confidence_scores,
                        "summary": processing_result.summary,
                        "confidence_score": processing_result.confidence_score,
                        "ocr_confidence_score": ocr_confidence_score,
                        "document_classification": document_classification,
                        "processing_info": {
                            "processing_time": total_processing_time,
                            "ocr_time": ocr_time,
                            "extraction_time": extraction_time,
                            "preprocessing_applied": apply_preprocessing,
                            "quality_enhanced": enhance_quality,
                            "extraction_method": "Template-based AI extraction" if template_id else ("AI-powered" if text_processor.is_available() else "Basic pattern matching")
                        },
                        "metadata": {
                            "extraction_timestamp": datetime.now().isoformat(),
                            "text_length": len(result.get("combined_text", "")),
                            "ai_processing": text_processor.is_available()
                        } if include_metadata else None
                    },
                    ocr_confidence_score=str(ocr_confidence_score) if ocr_confidence_score else None,
                    processing_time=str(total_processing_time) if total_processing_time else None,
                    created_at=datetime.utcnow()
                )
                db.add(new_processed_file)
                logger.info(f"💾 Created new processed file entry for {file.filename} (hash: {file_hash[:16]}...)")
            
            db.commit()
            logger.info(f"✓ Successfully saved processed file to database for {file.filename}")
        except Exception as db_error:
            logger.error(f"✗ Failed to save processed file to database: {db_error}", exc_info=True)
            db.rollback()
            # Don't fail the request if database save fails

        return {
            "status": "success",
            "message": f"Enhanced OCR processing completed for {file.filename}" + (f" with template {template_id}" if template_id else ""),
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "size_bytes": len(file_data),
                "pages_processed": len(result.get("raw_ocr_results", []))
            },
            "key_value_pairs": processing_result.key_value_pairs,
            "key_value_pair_confidence_scores": kv_confidence_scores,
            "summary": processing_result.summary,
            "confidence_score": processing_result.confidence_score,
            "ocr_confidence_score": ocr_confidence_score,
            "document_classification": document_classification,
            "processing_time": total_processing_time,  # Add total processing time at top level for frontend
            "template_info": {
                "template_id": template_id,
                "template_name": tenant_template.get("filename", "Unknown") if template_id and 'tenant_template' in locals() else None,
                "mapping_result": mapping_result,
                "fields_extracted": len(processing_result.key_value_pairs) if template_id else None
            } if template_id else None,
            "processing_info": {
                "processing_time": total_processing_time,
                "ocr_time": ocr_time,
                "extraction_time": extraction_time,
                "preprocessing_applied": apply_preprocessing,
                "quality_enhanced": enhance_quality,
                "extraction_method": "Template-based AI extraction" if template_id else ("AI-powered" if text_processor.is_available() else "Basic pattern matching")
            },
            "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
            "raw_ocr_results": result.get("raw_ocr_results", []),
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "text_length": len(result.get("combined_text", "")),
                "ai_processing": text_processor.is_available()
            } if include_metadata else None,
            "blob_storage": {
                "processed_json": json_upload_result,
                "source": source_blob_info if use_blob_workflow else None,
                "workflow_type": "source → process → processed" if use_blob_workflow else "direct processing"
            },
            "low_confidence_data": {
                "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                "low_confidence_pairs": low_confidence_pairs,
                "low_confidence_scores": low_confidence_scores_filtered,
                "source_file_base64": file_base64,
                "source_file_content_type": file.content_type or "application/octet-stream",
                "count": len(low_confidence_pairs)
            } if low_confidence_pairs else None
        }
        
    except Exception as e:
        logger.error(f"Enhanced OCR processing error for {file.filename}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Enhanced OCR processing failed")


# This endpoint was redundant because /ocr/enhanced/process already handles the complete workflow.
# @router.post("/ocr/enhanced/process-from-source")
# async def process_from_source_blob(
#     blob_path: str = Form(..., description="Blob path in source folder"),
#     apply_preprocessing: bool = Form(True, description="Apply image preprocessing"),
#     enhance_quality: bool = Form(True, description="Apply quality enhancements"),
#     include_raw_text: bool = Form(True, description="Include raw OCR text in response"),
#     include_metadata: bool = Form(True, description="Include processing metadata"),
#     current_user: User = Depends(get_current_active_user),
#     db: Session = Depends(get_db)
# ) -> Dict[str, Any]:
    """
    Process a file from Azure Blob Storage source folder.
    
    This endpoint implements the source → process → processed workflow:
    1. Downloads file from source folder
    2. Processes with OCR and AI extraction
    3. Uploads processed results to processed folder
    
    Features:
    - Downloads file from Azure Blob Storage source folder
    - Azure Computer Vision OCR with advanced preprocessing
    - AI-powered key-value pair extraction using Azure GPT
    - Document classification and summarization
    - Uploads processed results to processed folder
    """
    # try:
    #     logger.info(f"Processing file from source blob: {blob_path}")
        
    #     # Generate processing ID and tenant ID
    #     processing_id = str(uuid.uuid4())
    #     tenant_id = getattr(current_user, 'tenant_id', f"tenant_{current_user.id}")
        
    #     # Step 1: Download file from source folder
    #     blob_service = AzureBlobService()
    #     if not blob_service.is_available():
    #         raise HTTPException(status_code=503, detail="Azure Blob Storage not available - cannot process from source folder")
        
    #     file_data = blob_service.download_source_file(blob_path)
    #     if not file_data:
    #         raise HTTPException(status_code=404, detail=f"File not found in source folder: {blob_path}")
        
    #     # Extract filename from blob path
    #     filename = blob_path.split('/')[-1] if '/' in blob_path else blob_path
        
    #     logger.info(f"Downloaded file from source: {filename} ({len(file_data)} bytes)")
        
    #     # Step 2: Process with Azure Computer Vision OCR
    #     result = await ocr_from_path(
    #         file_data=file_data,
    #         original_filename=filename,
    #         ocr_engine="azure_computer_vision",
    #         ground_truth="",
    #         apply_preprocessing=apply_preprocessing,
    #         enhance_quality=enhance_quality
    #     )
        
    #     # Initialize enhanced text processor
    #     text_processor = EnhancedTextProcessor()
        
    #     # Process with AI-powered key-value extraction
    #     processing_result = await text_processor.process_without_template(
    #         ocr_text=result.get("combined_text", ""),
    #         filename=filename
    #     )
        
    #     # Document classification
    #     document_classification = text_processor.classify_document_type(
    #         ocr_text=result.get("combined_text", "")
    #     )
        
    #     # Step 3: Upload processed JSON data to processed folder (NO original files)
    #     json_upload_result = None
    #     try:
    #         if blob_service.is_available():
    #             logger.info(f"Uploading JSON data to processed folder for {filename}")
                
    #             # Upload processed JSON data
    #             processed_json_data = {
    #                 "file_info": {
    #                     "filename": filename,
    #                     "source_blob_path": blob_path,
    #                     "size_bytes": len(file_data),
    #                     "pages_processed": len(result.get("raw_ocr_results", []))
    #                 },
    #                 "key_value_pairs": processing_result.key_value_pairs,
    #                 "summary": processing_result.summary,
    #                 "confidence_score": processing_result.confidence_score,
    #                 "document_classification": document_classification,
    #                 "processing_info": {
    #                     "processing_time": result.get("processing_time", 0),
    #                     "preprocessing_applied": apply_preprocessing,
    #                     "quality_enhanced": enhance_quality,
    #                     "extraction_method": "AI-powered" if text_processor.is_available() else "Basic pattern matching"
    #                 },
    #                 "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
    #                 "metadata": {
    #                     "extraction_timestamp": datetime.now().isoformat(),
    #                     "text_length": len(result.get("combined_text", "")),
    #                     "ai_processing": text_processor.is_available()
    #                 } if include_metadata else None
    #             }
                
    #             json_upload_result = blob_service.upload_processed_json(
    #                 json_data=processed_json_data,
    #                 filename=filename,
    #                 tenant_id=tenant_id,
    #                 processing_id=processing_id
    #             )
                
    #             if json_upload_result.get("success"):
    #                 logger.info(f"[SUCCESS] JSON data uploaded to processed folder: {json_upload_result['blob_path']}")
    #             else:
    #                 logger.warning(f"[ERROR] Failed to upload JSON data: {json_upload_result.get('error')}")
                    
    #         else:
    #             logger.info("Azure Blob Storage not available - skipping JSON upload")
    #             json_upload_result = {"success": False, "error": "Azure Blob Storage not available", "skipped": True}
                
    #     except Exception as e:
    #         logger.warning(f"Azure Blob Storage error (non-critical): {e}")
    #         json_upload_result = {"success": False, "error": str(e), "skipped": True}
        
    #     return {
    #         "status": "success",
    #         "message": f"File processed from source folder: {filename}",
    #         "workflow": "source → process → processed",
    #         "file_info": {
    #             "filename": filename,
    #             "source_blob_path": blob_path,
    #             "size_bytes": len(file_data),
    #             "pages_processed": len(result.get("raw_ocr_results", []))
    #         },
    #         "key_value_pairs": processing_result.key_value_pairs,
    #         "summary": processing_result.summary,
    #         "confidence_score": processing_result.confidence_score,
    #         "document_classification": document_classification,
    #         "processing_info": {
    #             "processing_time": result.get("processing_time", 0),
    #             "preprocessing_applied": apply_preprocessing,
    #             "quality_enhanced": enhance_quality,
    #             "extraction_method": "AI-powered" if text_processor.is_available() else "Basic pattern matching"
    #         },
    #         "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
    #         "metadata": {
    #             "extraction_timestamp": datetime.now().isoformat(),
    #             "text_length": len(result.get("combined_text", "")),
    #             "ai_processing": text_processor.is_available()
    #         } if include_metadata else None,
    #         "blob_storage": {
    #             "source": {
    #                 "blob_path": blob_path,
    #                 "success": True,
    #                 "message": "File downloaded from source folder"
    #             },
    #             "processed_json": json_upload_result
    #         }
    #     }
        
    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.error(f"Error processing file from source blob {blob_path}: {e}")
    #     raise HTTPException(status_code=500, detail=f"Processing from source failed: {str(e)}")

@router.post("/ocr/enhanced/batch/process")
async def process_enhanced_batch_ocr(
    files: List[UploadFile] = File(..., description="Files to process (PDF, PNG, JPG, JPEG)"),
    apply_preprocessing: bool = Form(True, description="Apply image preprocessing"),
    enhance_quality: bool = Form(True, description="Apply quality enhancements"),
    include_raw_text: bool = Form(True, description="Include raw OCR text in response"),
    include_metadata: bool = Form(True, description="Include processing metadata"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process multiple files with enhanced OCR and AI-powered key-value extraction.
    
    Features:
    - Batch processing of multiple files
    - AI-powered key-value pair extraction for each file
    - Document classification and summarization
    - Multi-tenant data isolation
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        logger.info(f"Processing enhanced batch OCR for {len(files)} files")
        
        individual_results = []
        total_processing_time = 0
        
        for file in files:
            try:
                # Validate file type
                allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
                if file.content_type not in allowed_types:
                    logger.warning(f"Skipping unsupported file type: {file.content_type} for {file.filename}")
                    continue
                
                logger.info(f"Processing file: {file.filename}")
                
                # Read file data
                file_data = await file.read()
                
                # Process with Azure Computer Vision OCR
                result = await ocr_from_path(
                    file_data=file_data,
                    original_filename=file.filename or "unknown",
                    ocr_engine="azure_computer_vision",
                    ground_truth="",
                    apply_preprocessing=apply_preprocessing,
                    enhance_quality=enhance_quality
                )
                
                # Initialize enhanced text processor
                text_processor = EnhancedTextProcessor()
                
                # Process with AI-powered key-value extraction
                processing_result = await text_processor.process_without_template(
                    ocr_text=result.get("combined_text", ""),
                    filename=file.filename or "unknown"
                )
                
                # Check if result is a fallback (has error flag)
                is_fallback = "_extraction_error" in processing_result.key_value_pairs or "_extraction_method" in processing_result.key_value_pairs
                extraction_error = processing_result.key_value_pairs.get("_extraction_error")
                
                # Determine extraction method
                if is_fallback:
                    extraction_method = "Fallback (Basic pattern matching)"
                elif text_processor.is_available():
                    extraction_method = "AI-powered"
                else:
                    extraction_method = "Basic pattern matching"
                
                # Document classification
                document_classification = text_processor.classify_document_type(
                    ocr_text=result.get("combined_text", "")
                )
                
                # Calculate OCR confidence from text_blocks
                ocr_confidence_score = calculate_ocr_confidence(result)

                # Calculate confidence scores for each key-value pair
                kv_confidence_scores = calculate_key_value_pair_confidence_scores(
                    key_value_pairs=processing_result.key_value_pairs,
                    ocr_result=result,
                    raw_ocr_text=result.get("combined_text", "")
                )

                # Identify low-confidence pairs (< 95%) for later manual analysis
                low_confidence_pairs = {}
                low_confidence_scores_filtered = {}
                for key, value in processing_result.key_value_pairs.items():
                    conf = kv_confidence_scores.get(key)
                    if conf is not None:
                        # Normalize confidence if needed
                        normalized_conf = conf / 100 if conf > 1 else conf
                        if normalized_conf < 0.95:
                            low_confidence_pairs[key] = value
                            low_confidence_scores_filtered[key] = normalized_conf
                
                # Store file as base64 for later low-confidence analysis
                file_base64 = base64.b64encode(file_data).decode('utf-8')
                
                # Log low-confidence pairs count
                if low_confidence_pairs:
                    logger.info(f"Identified {len(low_confidence_pairs)} low-confidence pairs for {file.filename} - ready for manual analysis")
                
                # Upload JSON data to Azure Blob Storage (NO original files)
                json_upload_result = None
                try:
                    blob_service = AzureBlobService()
                    if blob_service.is_available():
                        processing_id = str(uuid.uuid4())
                        
                        # Upload processed JSON data
                        processed_json_data = {
                            "file_info": {
                                "filename": file.filename,
                                "content_type": file.content_type,
                                "size_bytes": len(file_data),
                                "pages_processed": len(result.get("raw_ocr_results", []))
                            },
                            "key_value_pairs": processing_result.key_value_pairs,
                            "summary": processing_result.summary,
                            "confidence_score": processing_result.confidence_score,
                            "ocr_confidence_score": ocr_confidence_score,
                            "document_classification": document_classification,
                            "processing_info": {
                                "processing_time": result.get("processing_time", 0),
                                "preprocessing_applied": apply_preprocessing,
                                "quality_enhanced": enhance_quality,
                                "extraction_method": extraction_method,
                                "is_fallback": is_fallback
                            },
                            "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
                            "raw_ocr_results": result.get("raw_ocr_results", []), 
                            "metadata": {
                                "extraction_timestamp": datetime.now().isoformat(),
                                "text_length": len(result.get("combined_text", "")),
                                "ai_processing": text_processor.is_available(),
                                "extraction_error": extraction_error if is_fallback else None
                            } if include_metadata else None,
                            "low_confidence_data": {
                                "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                                "low_confidence_pairs": low_confidence_pairs,
                                "low_confidence_scores": low_confidence_scores_filtered,
                                "source_file_base64": file_base64,
                                "source_file_content_type": file.content_type or "application/octet-stream",
                                "count": len(low_confidence_pairs)
                            } if low_confidence_pairs else None
                        }
                        
                        json_upload_result = blob_service.upload_processed_json(
                            json_data=processed_json_data,
                            filename=file.filename or "unknown",
                            tenant_id=current_user.tenant_id,
                            processing_id=processing_id
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to upload batch JSON to blob storage: {e}")
                    json_upload_result = {"success": False, "error": str(e)}
                
                # Store null field tracking data
                try:
                    from services.null_field_service import null_field_service
                    logger.info(f"[BATCH] Storing null field tracking for {file.filename}...")
                    null_field_service.store_null_fields(
                        processing_id=processing_id,
                        tenant_id=current_user.tenant_id,
                        filename=file.filename or "unknown",
                        extracted_fields=processing_result.key_value_pairs
                    )
                except Exception as null_error:
                    logger.error(f"[BATCH] ✗ Failed to store null field tracking: {null_error}")

                individual_results.append({
                    "file_info": {
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size_bytes": len(file_data),
                        "pages_processed": len(result.get("raw_ocr_results", []))
                    },
                    "key_value_pairs": processing_result.key_value_pairs,
                    "key_value_pair_confidence_scores": kv_confidence_scores,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score,
                    "ocr_confidence_score": ocr_confidence_score,
                    "document_classification": document_classification,
                    "processing_info": {
                        "processing_time": result.get("processing_time", 0),
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": extraction_method,
                        "is_fallback": is_fallback
                    },
                    "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
                    "raw_ocr_results": result.get("raw_ocr_results", []),
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "text_length": len(result.get("combined_text", "")),
                        "ai_processing": text_processor.is_available(),
                        "extraction_error": extraction_error if is_fallback else None
                    } if include_metadata else None,
                    "blob_storage": {
                        "processed_json": json_upload_result
                    },
                    "low_confidence_data": {
                        "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                        "low_confidence_pairs": low_confidence_pairs,
                        "low_confidence_scores": low_confidence_scores_filtered,
                        "source_file_base64": file_base64,
                        "source_file_content_type": file.content_type or "application/octet-stream",
                        "count": len(low_confidence_pairs)
                    } if low_confidence_pairs else None
                })
                
                total_processing_time += result.get("processing_time", 0)
            
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}")
                individual_results.append({
                    "file_info": {
                        "filename": file.filename,
                        "error": str(e)
                    },
                    "key_value_pairs": {},
                    "summary": f"Error processing file: {str(e)}",
                    "confidence_score": 0.0,
                    "document_classification": "Error",
                    "processing_info": {
                        "processing_time": 0,
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": "Error"
                    }
                })
        
        # Count fallback results
        fallback_count = sum(1 for r in individual_results if r.get("processing_info", {}).get("is_fallback", False))
        
        return {
            "status": "success",
            "message": f"Enhanced batch OCR processing completed for {len(individual_results)} files",
            "batch_info": {
                "total_files": len(files),
                "processed_files": len(individual_results),
                "total_processing_time": total_processing_time,
                "fallback_count": fallback_count,
                "successful_ai_extraction": len(individual_results) - fallback_count
            },
            "individual_results": individual_results
        }
        
    except Exception as e:
        logger.error(f"Enhanced batch OCR processing error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Enhanced batch OCR processing failed")


@router.post("/ocr/enhanced/batch/process/async")
async def process_enhanced_batch_ocr_async(
    files: List[UploadFile] = File(..., description="Files to process (PDF, PNG, JPG, JPEG)"),
    apply_preprocessing: bool = Form(True, description="Apply image preprocessing"),
    enhance_quality: bool = Form(True, description="Apply quality enhancements"),
    include_raw_text: bool = Form(True, description="Include raw OCR text in response"),
    include_metadata: bool = Form(True, description="Include processing metadata"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process multiple files with enhanced OCR using Celery workers for parallel processing.
    
    Features:
    - Batch processing of multiple files
    - Parallel processing using Celery workers
    - AI-powered key-value pair extraction for each file
    - Document classification and summarization
    - Multi-tenant data isolation
    - Returns task ID immediately for status tracking
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        logger.info(f"Processing enhanced batch OCR async for {len(files)} files using Celery")
        
        # Validate and read all files
        files_data = []
        filenames = []
        content_types = []
        
        for file in files:
            # Validate file type
            allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
            if file.content_type not in allowed_types:
                logger.warning(f"Skipping unsupported file type: {file.content_type} for {file.filename}")
                continue
            
            # Read file data
            file_data = await file.read()
            files_data.append(file_data)
            filenames.append(file.filename or "unknown")
            content_types.append(file.content_type or "application/octet-stream")
        
        if not files_data:
            raise HTTPException(status_code=400, detail="No valid files provided")
        
        # Encode all files as base64 for Celery serialization
        files_data_b64 = [base64.b64encode(f).decode('utf-8') for f in files_data]
        
        # Generate individual task IDs for tracking
        task_ids = []
        
        # Submit each file as a SEPARATE TASK to workers (TRUE PARALLEL PROCESSING)
        logger.info(f"Submitting {len(files_data)} individual tasks to Celery workers for parallel processing...")
        
        try:
            for idx, (file_data_b64, filename) in enumerate(zip(files_data_b64, filenames)):
                processing_id = str(uuid.uuid4())
                
                # Submit INDIVIDUAL task for each file - each goes to a separate worker
                individual_task = process_document.delay(
                    file_data=file_data_b64,
                    filename=filename,
                    tenant_id=current_user.tenant_id,
                    processing_id=processing_id,
                    apply_preprocessing=apply_preprocessing,
                    enhance_quality=enhance_quality,
                    include_raw_text=include_raw_text,
                    include_metadata=include_metadata,
                    content_type=content_types[idx] if idx < len(content_types) else "application/octet-stream"
                )
                
                task_ids.append({
                    "task_id": individual_task.id,
                    "filename": filename,
                    "status_url": f"/api/v1/tasks/{individual_task.id}"
                })
                
                logger.info(f"Submitted task {idx + 1}/{len(files_data)}: {filename} -> Worker (Task ID: {individual_task.id})")
        except Exception as celery_error:
            error_msg = str(celery_error).lower()
            if "redis" in error_msg or "connection" in error_msg or "broker" in error_msg:
                logger.error(f"Redis connection error when submitting Celery tasks: {celery_error}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Redis/Celery broker is not available. Please ensure Redis is running. "
                           f"On Windows: docker run -d -p 6379:6379 --name redis redis:latest. "
                           f"Error: {str(celery_error)}"
                )
            else:
                raise
        
        return {
            "status": "accepted",
            "message": f"Batch processing started for {len(files_data)} files in parallel",
            "total_files": len(files_data),
            "individual_tasks": task_ids,
            "note": "Each file is processed independently by separate workers. Check status for each task individually."
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Enhanced batch OCR async processing error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Enhanced batch OCR async processing failed")


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a Celery task.
    
    Returns:
        - PENDING: Task is waiting to be processed
        - PROCESSING: Task is being processed
        - SUCCESS: Task completed successfully
        - FAILURE: Task failed
    """
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'status': 'PENDING',
                'state': task.state,
                'message': 'Task is waiting to be processed'
            }
        elif task.state == 'PROCESSING':
            response = {
                'status': 'PROCESSING',
                'state': task.state,
                'message': 'Task is being processed',
                'info': task.info
            }
        elif task.state == 'SUCCESS':
            result = task.result
            # Normalize result format for frontend compatibility
            if result and isinstance(result, dict):
                # Extract filename from file_info if present
                if 'file_info' in result and 'filename' in result.get('file_info', {}):
                    result['filename'] = result['file_info']['filename']
                # Extract processing_time from processing_info if present
                if 'processing_info' in result and 'processing_time' in result.get('processing_info', {}):
                    result['processing_time'] = result['processing_info']['processing_time']
                # Extract template info if present
                if 'template_info' in result and 'mapping_result' in result.get('template_info', {}):
                    mapping_result = result['template_info']['mapping_result']
                    if 'mapped_values' in mapping_result:
                        result['template_used'] = result['template_info'].get('template_id', 'Unknown')
            response = {
                'status': 'SUCCESS',
                'state': task.state,
                'message': 'Task completed successfully',
                'result': result
            }
        elif task.state == 'FAILURE':
            response = {
                'status': 'FAILURE',
                'state': task.state,
                'message': 'Task failed',
                'error': str(task.info) if task.info else 'Unknown error'
            }
        else:
            response = {
                'status': task.state,
                'state': task.state,
                'info': task.info
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task status")


@router.post("/tasks/batch-status")
async def get_batch_task_status(
    task_ids: List[str] = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get status of multiple Celery tasks at once.
    
    Request body: ["task_id_1", "task_id_2", ...]
    
    Returns status for all tasks in the batch.
    """
    try:
        results = []
        
        for task_id in task_ids:
            try:
                task = celery_app.AsyncResult(task_id)
                task_info = {
                    "task_id": task_id,
                    "state": task.state,
                    "status": task.state
                }
                
                if task.state == 'SUCCESS':
                    try:
                        result = task.result
                        if result is None:
                            logger.warning(f"Task {task_id} state is SUCCESS but result is None")
                            task_info['result'] = None
                        elif isinstance(result, dict):
                            # Normalize result format for frontend compatibility
                            # Extract filename from file_info if present
                            if 'file_info' in result and 'filename' in result.get('file_info', {}):
                                result['filename'] = result['file_info']['filename']
                            # Extract processing_time from processing_info if present
                            if 'processing_info' in result and 'processing_time' in result.get('processing_info', {}):
                                result['processing_time'] = result['processing_info']['processing_time']
                            # Extract template info if present
                            if 'template_info' in result and 'mapping_result' in result.get('template_info', {}):
                                mapping_result = result['template_info']['mapping_result']
                                if 'mapped_values' in mapping_result:
                                    result['template_used'] = result['template_info'].get('template_id', 'Unknown')
                            task_info['result'] = result
                        else:
                            # Result is not a dict, store as-is
                            task_info['result'] = result
                    except Exception as result_error:
                        logger.error(f"Error retrieving result for task {task_id}: {result_error}")
                        task_info['result'] = None
                        task_info['error'] = f"Failed to retrieve result: {str(result_error)}"
                elif task.state == 'FAILURE':
                    task_info['error'] = str(task.info) if task.info else 'Unknown error'
                elif task.state == 'PROCESSING':
                    task_info['info'] = task.info
                
                results.append(task_info)
            except Exception as e:
                results.append({
                    "task_id": task_id,
                    "state": "ERROR",
                    "error": str(e)
                })
        
        # Count by status
        pending = sum(1 for r in results if r['state'] == 'PENDING')
        processing = sum(1 for r in results if r['state'] == 'PROCESSING')
        success = sum(1 for r in results if r['state'] == 'SUCCESS')
        failure = sum(1 for r in results if r['state'] == 'FAILURE')
        
        # Log summary for debugging
        results_with_data = sum(1 for r in results if r.get('result') is not None)
        logger.info(f"Batch status check: {len(task_ids)} tasks - {success} SUCCESS, {failure} FAILED, {pending} PENDING, {processing} PROCESSING, {results_with_data} with results")
        
        return {
            "status": "success",
            "total_tasks": len(task_ids),
            "summary": {
                "pending": pending,
                "processing": processing,
                "completed": success,
                "failed": failure,
                "progress_percent": int((success + failure) / len(task_ids) * 100) if len(task_ids) > 0 else 0
            },
            "tasks": results
        }
        
    except Exception as e:
        logger.error(f"Error getting batch task status: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get batch task status")


@router.post("/ocr/enhanced/process/async")
async def process_enhanced_ocr_async(
    file: UploadFile = File(..., description="File to process (PDF, PNG, JPG, JPEG)"),
    template_id: Optional[str] = Form(None, description="Optional template ID for structured extraction"),
    apply_preprocessing: bool = Form(True, description="Apply image preprocessing"),
    enhance_quality: bool = Form(True, description="Apply quality enhancements"),
    include_raw_text: bool = Form(True, description="Include raw OCR text in response"),
    include_metadata: bool = Form(True, description="Include processing metadata"),
    use_blob_workflow: bool = Form(True, description="Use source → process → processed workflow"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process uploaded file with enhanced OCR using Celery for async processing.
    
    Features:
    - Async processing using Celery workers
    - Azure Computer Vision OCR with advanced preprocessing
    - AI-powered key-value pair extraction using Azure GPT
    - Optional template-based structured extraction
    - Document classification and summarization
    - Multi-tenant data isolation
    - Returns task ID immediately for status tracking
    """
    try:
        # Validate file type
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPG, JPEG"
            )
        
        logger.info(f"Processing enhanced OCR async for {file.filename}")
        
        # Read file data
        file_data = await file.read()
        logger.info(f"Read file data: {len(file_data)} bytes for {file.filename}")
        
        # Generate processing ID and tenant ID
        processing_id = str(uuid.uuid4())
        tenant_id = getattr(current_user, 'tenant_id', f"tenant_{current_user.id}")
        
        # Encode file data as base64 for Celery serialization
        file_data_b64 = base64.b64encode(file_data).decode('utf-8')
        
        # Submit task to Celery
        task = process_document.delay(
            file_data=file_data_b64,
            filename=file.filename or "unknown",
            tenant_id=tenant_id,
            processing_id=processing_id,
            apply_preprocessing=apply_preprocessing,
            enhance_quality=enhance_quality,
            include_raw_text=include_raw_text,
            include_metadata=include_metadata,
            template_id=template_id,
            content_type=file.content_type or "application/octet-stream"
        )
        
        return {
            "status": "accepted",
            "message": f"Processing started for {file.filename}",
            "task_id": task.id,
            "processing_id": processing_id,
            "filename": file.filename,
            "template_id": template_id,
            "check_status_url": f"/api/v1/tasks/{task.id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced OCR async processing error for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Enhanced OCR async processing failed")


# Removed old non-tenant template endpoints to avoid conflicts.

@router.post("/ocr/export/excel/from-data")
async def export_excel_from_data(
    processed_data: Dict[str, Any] = Body(...),
    include_raw_text: bool = Body(True),
    include_metadata: bool = Body(True)
) -> StreamingResponse:
    """Export processed OCR data to Excel file."""
    try:
        exporter = ExcelExporter()
        # Debug incoming payload
        try:
            kv = processed_data.get("key_value_pairs") or processed_data.get("extraction_result", {}).get("key_value_pairs", {})
            logger.info(f"Excel export request received. Keys count: {len(kv) if isinstance(kv, dict) else 0}")
        except Exception:
            pass
        excel_buffer = exporter.create_individual_excel(
            processed_data=processed_data,
            include_raw_text=include_raw_text,
            include_metadata=include_metadata
        )
        
        filename = processed_data.get("file_info", {}).get("filename", "processed_document")
        if not filename.endswith('.xlsx'):
            filename = f"{filename}.xlsx"
        
        return StreamingResponse(
            BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Excel export failed")

@router.post("/ocr/export/excel/batch/from-data")
async def export_batch_excel_from_data(
    batch_data: Dict[str, Any] = Body(...),
    include_raw_text: bool = Body(True),
    include_metadata: bool = Body(True)
) -> StreamingResponse:
    """Export batch processed OCR data to Excel files (ZIP)."""
    try:
        exporter = ExcelExporter()
        zip_buffer = exporter.create_individual_excel_files(
            batch_data=batch_data,
            include_raw_text=include_raw_text,
            include_metadata=include_metadata
        )
        
        return StreamingResponse(
            BytesIO(zip_buffer),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=batch_extracted_documents.zip"}
        )
        
    except Exception as e:
        logger.error(f"Batch Excel export error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Batch Excel export failed")

@router.post("/history/save")
async def save_processing_result(
    result_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save a processing result to history for a specific tenant in data folder."""
    try:
        tenant_id = result_data.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="tenant_id is required")
        
        logger.info(f"Saving processing result to data folder for tenant: {tenant_id}")
        
        # Load existing history from data folder
        history = load_tenant_history(tenant_id)
        logger.info(f"Loaded {len(history)} existing history entries for tenant {tenant_id}")
        
        # Create history entry
        entry = {
            "id": result_data.get("id", int(datetime.now().timestamp() * 1000)),
            "timestamp": result_data.get("timestamp", datetime.now().isoformat()),
            "filename": result_data.get("filename", "Unknown"),
            "result": result_data.get("result", {}),
            "processing_type": result_data.get("processing_type", "single")
        }
        
        # Add to beginning of history (most recent first)
        history.insert(0, entry)
        
        # Keep only last 100 entries to prevent file from growing too large
        if len(history) > 100:
            history = history[:100]
            logger.info(f"Trimmed history to 100 entries for tenant {tenant_id}")
        
        # Save to data folder
        save_tenant_history(tenant_id, history)
        logger.info(f"Successfully saved processing result to data folder for tenant {tenant_id}, entry ID: {entry['id']}")
        
        return {"status": "success", "message": "Result saved to history in data folder", "id": entry["id"]}
        
    except Exception as e:
        logger.error(f"Error saving processing result to data folder: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to save result")

@router.get("/history/{tenant_id}")
async def get_processing_history(
    tenant_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all processing history for a specific tenant from JSON file in data folder."""
    try:
        # Load history from JSON file in data/tenants/{tenant_id}/processing_history.json
        history = load_tenant_history(tenant_id)
        
        # Sort by timestamp (most recent first) if timestamp exists
        if history:
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {"status": "success", "history": history}
    except Exception as e:
        logger.error(f"Error loading history for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load history")

@router.delete("/history/{tenant_id}/{entry_id}")
async def delete_history_entry(
    tenant_id: str, 
    entry_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a specific history entry for a tenant."""
    try:
        history = load_tenant_history(tenant_id)
        history = [entry for entry in history if entry.get("id") != entry_id]
        save_tenant_history(tenant_id, history)
        return {"status": "success", "message": "Entry deleted"}
    except Exception as e:
        logger.error(f"Error deleting history entry {entry_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to delete entry")

@router.delete("/history/{tenant_id}")
async def clear_tenant_history(
    tenant_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Clear all processing history for a specific tenant."""
    try:
        save_tenant_history(tenant_id, [])
        return {"status": "success", "message": "All history cleared for tenant"}
    except Exception as e:
        logger.error(f"Error clearing history for tenant {tenant_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to clear history")


# Azure Blob Storage endpoints
@router.get("/blob/files/{tenant_id}")
async def get_tenant_files(
    tenant_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all files for a specific tenant from Azure Blob Storage."""
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        # Check if user has access to this tenant's files
        if current_user.tenant_id != tenant_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")
        
        files = blob_service.list_tenant_files(tenant_id)
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files": files,
            "count": len(files)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting files for tenant {tenant_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get files")

@router.get("/blob/files/admin")
async def get_all_files_admin(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all files from Azure Blob Storage (admin only)."""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        files = blob_service.list_all_files()
        return {
            "status": "success",
            "files": files,
            "count": len(files)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all files (admin): {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get files")

@router.post("/ocr/enhanced/correct")
async def correct_extracted_value(
    key: str = Body(..., description="The field name to correct"),
    value: str = Body(..., description="The current value"),
    context: str = Body(..., description="The document context (OCR text)"),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Correct a specific extracted value using LLM.
    """
    try:
        text_processor = EnhancedTextProcessor()
        
        # Check availability but don't crash if not available
        if not text_processor.is_available():
            logger.warning("Enhanced text processor not available for correction request")
            return {
                "status": "warning",
                "original_value": value,
                "corrected_value": value,
                "confidence_score": 0.0,
                "reasoning": "LLM service not configured or available"
            }
            
        result = await text_processor.correct_value(key, value, context)
        
        return {
            "status": "success",
            "original_value": value,
            "corrected_value": result.get("corrected_value"),
            "confidence_score": result.get("confidence_score"),
            "reasoning": result.get("reasoning")
        }
        
    except Exception as e:
        logger.error(f"Error correcting value for {key}: {e}")
        # Log full traceback for debugging without exposing it to the client
        import traceback
        logger.error(f"Traceback while correcting value for {key}: {traceback.format_exc()}")
        # Return a valid response instead of 500 to avoid frontend crash,
        # but do not expose internal error details to the client
        return {
            "status": "error",
            "original_value": value,
            "corrected_value": value,
            "confidence_score": 0.0,
            "reasoning": "An unexpected error occurred while processing the correction request."
        }

@router.post("/ocr/enhanced/analyze-low-confidence")
async def analyze_low_confidence_pairs(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze key-value pairs with confidence below 95% and provide suggestions.
    Uses Azure OpenAI Vision API to analyze the original document image.
    
    Request body should contain:
    - key_value_pairs: Dict of extracted key-value pairs
    - confidence_scores: Dict mapping keys to confidence scores (0.0-1.0 or 0-100)
    - ocr_text: Full OCR text for context
    - filename: Optional filename for logging
    - source_file_base64: Optional base64-encoded original file
    - source_file_content_type: Optional content type of the original file
    """
    try:
        key_value_pairs = payload.get("key_value_pairs", {})
        confidence_scores = payload.get("confidence_scores", {})
        ocr_text = payload.get("ocr_text", "")
        filename = payload.get("filename", "unknown")
        source_file_base64 = payload.get("source_file_base64")
        source_file_content_type = payload.get("source_file_content_type")
        
        if not key_value_pairs:
            return {
                "status": "success",
                "message": "No key-value pairs provided",
                "analysis_results": {}
            }
        
        logger.info(f"🔄 Analyzing low-confidence pairs for {filename} - calling LLM")
        
        text_processor = EnhancedTextProcessor()
        
        if not text_processor.is_available():
            logger.warning("Enhanced text processor not available for analysis")
            return {
                "status": "warning",
                "message": "LLM service not configured or available",
                "analysis_results": {}
            }
        
        # Call LLM to analyze
        results = await text_processor.analyze_low_confidence_pairs(
            key_value_pairs=key_value_pairs,
            confidence_scores=confidence_scores,
            ocr_text=ocr_text,
            filename=filename,
            source_file_base64=source_file_base64,
            source_file_content_type=source_file_content_type
        )
        
        # Process results: automatically increase confidence when suggestion matches value
        updated_confidence_scores = {}
        for key, analysis_result in results.items():
            current_value = str(analysis_result.get("current_value", "")).strip()
            suggested_value = str(analysis_result.get("suggested_value", "")).strip()
            current_confidence = analysis_result.get("current_confidence", 0.0)
            
            # Check if suggestion matches the current value (case-insensitive, whitespace-normalized)
            if suggested_value and current_value:
                # Normalize both values for comparison (lowercase, strip whitespace)
                normalized_current = current_value.lower().strip()
                normalized_suggested = suggested_value.lower().strip()
                
                if normalized_current == normalized_suggested:
                    # Suggestion matches value - automatically increase confidence to 0.95 (95%)
                    new_confidence = 0.95
                    updated_confidence_scores[key] = new_confidence
                    analysis_result["auto_confidence_increased"] = True
                    analysis_result["new_confidence"] = new_confidence
                    analysis_result["confidence_increase_reason"] = "Suggestion matches current value"
                    logger.info(f"Auto-increased confidence for '{key}': {current_confidence:.2f} -> {new_confidence:.2f} (suggestion matches value)")
                else:
                    # Suggestion doesn't match - ensure suggestions are shown
                    analysis_result["auto_confidence_increased"] = False
                    # If suggested_value is empty but we have suggestions list, use the first suggestion
                    if not suggested_value and analysis_result.get("suggestions"):
                        suggestions_list = analysis_result.get("suggestions", [])
                        if suggestions_list and len(suggestions_list) > 0:
                            analysis_result["suggested_value"] = suggestions_list[0]
                            logger.info(f"Using first suggestion for '{key}': {suggestions_list[0]}")
            else:
                # No suggestion value - check if we have suggestions list
                if not suggested_value and analysis_result.get("suggestions"):
                    suggestions_list = analysis_result.get("suggestions", [])
                    if suggestions_list and len(suggestions_list) > 0:
                        analysis_result["suggested_value"] = suggestions_list[0]
                        logger.info(f"Using first suggestion for '{key}': {suggestions_list[0]}")
        
        # Add updated confidence scores to results
        if updated_confidence_scores:
            results["_updated_confidence_scores"] = updated_confidence_scores
            logger.info(f"Auto-updated confidence scores for {len(updated_confidence_scores)} fields")
        
        # Remove the internal _updated_confidence_scores from results before returning
        updated_confidence_scores = results.pop("_updated_confidence_scores", {})
        
        # Automatically save analysis results to database cache for fast retrieval
        try:
            unique_file_id = payload.get("unique_file_id")
            if unique_file_id and results:
                import hashlib
                file_hash = hashlib.sha256(unique_file_id.encode('utf-8')).hexdigest()
                
                # Strategy 1: Check by processing_id (if unique_file_id is processing_id)
                cache_entry = db.query(ProcessedFile).filter(
                    ProcessedFile.processing_id == unique_file_id,
                    ProcessedFile.tenant_id == current_user.tenant_id
                ).first()
                
                # Strategy 2: Check by processed_blob_path (most common - blob path is stable)
                if not cache_entry:
                    cache_entry = db.query(ProcessedFile).filter(
                        ProcessedFile.processed_blob_path == unique_file_id,
                        ProcessedFile.tenant_id == current_user.tenant_id
                    ).first()
                    if cache_entry:
                        logger.info(f"✅ Found existing ProcessedFile by blob_path: {unique_file_id}")
                
                # Strategy 3: Check by file_hash
                if not cache_entry:
                    cache_entry = db.query(ProcessedFile).filter(
                        ProcessedFile.file_hash == unique_file_id,
                        ProcessedFile.tenant_id == current_user.tenant_id
                    ).first()
                
                if cache_entry:
                    # Update existing entry
                    # Ensure processed_data is a dict
                    if not isinstance(cache_entry.processed_data, dict):
                        cache_entry.processed_data = {}
                    
                    # Update or create ai_analysis_cache
                    cache_entry.processed_data["ai_analysis_cache"] = {
                        "analysis_results": results,
                        "timestamp": datetime.now().isoformat(),
                        "filename": filename,
                        "file_id": unique_file_id  # Store the unique_file_id for reference
                    }
                    
                    # Update processing_id and processed_blob_path if they're missing
                    if not cache_entry.processing_id:
                        cache_entry.processing_id = unique_file_id
                        logger.info(f"📝 Set processing_id: {unique_file_id}")
                    if not cache_entry.processed_blob_path and unique_file_id.startswith(('blob_main/', 'main/')):
                        cache_entry.processed_blob_path = unique_file_id
                        logger.info(f"📝 Set processed_blob_path: {unique_file_id}")
                    
                    cache_entry.updated_at = datetime.utcnow()
                    logger.info(f"💾 Updated existing cache entry for unique_file_id: {unique_file_id} (processing_id: {cache_entry.processing_id}, processed_blob_path: {cache_entry.processed_blob_path})")
                else:
                    # Create new cache entry
                    new_entry = ProcessedFile(
                        file_hash=file_hash,
                        processing_id=unique_file_id,
                        processed_blob_path=unique_file_id if unique_file_id.startswith(('blob_main/', 'main/')) else None,
                        tenant_id=current_user.tenant_id,
                        filename=filename,
                        processed_data={
                            "ai_analysis_cache": {
                                "analysis_results": results,
                                "timestamp": datetime.now().isoformat(),
                                "filename": filename,
                                "file_id": unique_file_id
                            },
                            "key_value_pairs": key_value_pairs,
                            "confidence_scores": confidence_scores
                        },
                        created_at=datetime.utcnow()
                    )
                    db.add(new_entry)
                    logger.info(f"💾 Created new cache entry for unique_file_id: {unique_file_id}")
                
                # Flush to ensure the data is in the database before commit
                db.flush()
                db.commit()
                logger.info(f"💾 Auto-saved analysis cache for unique_file_id: {unique_file_id} (committed to database)")
        except Exception as e:
            logger.warning(f"Failed to auto-save analysis cache: {e}", exc_info=True)
            db.rollback()
            # Don't fail the request if cache save fails
        
        return {
            "status": "success",
            "message": f"Analyzed {len(results)} low-confidence pairs",
            "analysis_results": results,
            "updated_confidence_scores": updated_confidence_scores  # Include auto-updated confidence scores
        }
        
    except Exception as e:
        logger.error("Error analyzing low-confidence pairs", exc_info=True)
        return {
            "status": "error",
            "message": "Analysis failed due to an internal error.",
            "analysis_results": {}
        }

@router.get("/blob/structure/{tenant_id}")
async def get_folder_structure(
    tenant_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get folder structure for a specific tenant."""
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        # Check if user has access to this tenant's files
        if current_user.tenant_id != tenant_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")
        
        structure = blob_service.get_folder_structure(tenant_id)
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "structure": structure
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting folder structure for tenant {tenant_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get folder structure")

@router.get("/blob/structure")
async def get_all_folder_structure(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get complete folder structure (admin only)."""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        structure = blob_service.get_folder_structure()
        return {
            "status": "success",
            "structure": structure
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all folder structure (admin): {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get folder structure")

@router.delete("/blob/files/{blob_name:path}")
async def delete_blob_file(
    blob_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a file from Azure Blob Storage."""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        success = blob_service.delete_file(blob_name)
        if success:
            return {"status": "success", "message": f"File {blob_name} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete file")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {blob_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to delete file")

@router.get("/blob/source-from-processed/{processed_blob_name:path}")
async def get_source_file_from_processed(
    processed_blob_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get the source file blob path from a processed file blob path."""
    try:
        # FastAPI automatically URL-decodes path parameters, but let's log it to verify
        logger.info(f"Looking for source file from processed file: {processed_blob_name}")
        
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        # Check if user has access to the processed file
        if not check_blob_access(processed_blob_name, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        source_blob_path = blob_service.find_source_file_from_processed(processed_blob_name)
        
        if not source_blob_path:
            logger.warning(f"Source file not found for processed file: {processed_blob_name}")
            raise HTTPException(status_code=404, detail="Source file not found for the processed file")
        
        logger.info(f"Found source file: {source_blob_path} for processed file: {processed_blob_name}")
        
        # Check if user has access to the source file
        if not check_blob_access(source_blob_path, current_user):
            raise HTTPException(status_code=403, detail="Access denied to source file")
        
        return {
            "status": "success",
            "source_blob_path": source_blob_path,
            "processed_blob_path": processed_blob_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source file from processed file {processed_blob_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get source file")

@router.get("/blob/download/{blob_name:path}")
async def download_blob_file(
    blob_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download a file from Azure Blob Storage."""
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        # Check if user has access to this file
        if not check_blob_access(blob_name, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        file_data = blob_service.download_file(blob_name)
        if file_data is None:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get filename from blob path
        filename = blob_name.split('/')[-1]

        # Determine content type from filename
        # Handle filenames with timestamps: filename.ext_timestamp
        # Remove timestamp pattern (YYYYMMDD_HHMMSS at the end)
        timestamp_pattern = r'_\d{8}_\d{6}$'
        clean_filename = re.sub(timestamp_pattern, '', filename)
        
        # Get extension
        if '.' in clean_filename:
            ext = clean_filename.rsplit('.', 1)[-1].lower()
        else:
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        # Map extensions to MIME types
        content_type_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
        }
        
        media_type = content_type_map.get(ext, 'application/octet-stream')
        
        
        return Response(
            content=file_data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {blob_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to download file")

@router.put("/blob/update-confidence-scores/{blob_name:path}")
async def update_confidence_scores(
    blob_name: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update confidence scores in a processed JSON file stored in Azure Blob Storage.
    
    Request body should contain:
    - updated_confidence_scores: Dict mapping field keys to new confidence scores (0.0-1.0)
    - updated_key_value_pairs: Optional dict of updated key-value pairs
    """
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise HTTPException(status_code=503, detail="Azure Blob Storage not available")
        
        # Check if user has access to this file
        if not check_blob_access(blob_name, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Download the current JSON file
        json_data = blob_service.download_file(blob_name)
        if json_data is None:
            raise HTTPException(status_code=404, detail="Processed JSON file not found")
        
        # Parse JSON
        try:
            processed_data = json.loads(json_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from {blob_name}: {e}")
            raise HTTPException(status_code=500, detail="Invalid JSON file")
        
        # Update confidence scores
        updated_confidence_scores = payload.get("updated_confidence_scores", {})
        updated_key_value_pairs = payload.get("updated_key_value_pairs", {})
        correction_metadata = payload.get("correction_metadata", {})  # Per-field metadata
        last_correction = payload.get("last_correction", None)  # Last correction for the file
        
        if updated_confidence_scores:
            # Update individual field confidence scores
            if "key_value_pair_confidence_scores" not in processed_data:
                processed_data["key_value_pair_confidence_scores"] = {}
            
            for key, confidence in updated_confidence_scores.items():
                processed_data["key_value_pair_confidence_scores"][key] = confidence
            
            logger.info(f"Updated {len(updated_confidence_scores)} confidence scores in {blob_name}")
        
        if updated_key_value_pairs:
            # Update key-value pairs
            if "key_value_pairs" not in processed_data:
                processed_data["key_value_pairs"] = {}
            
            for key, value in updated_key_value_pairs.items():
                processed_data["key_value_pairs"][key] = value
            
            logger.info(f"Updated {len(updated_key_value_pairs)} key-value pairs in {blob_name}")
        
        # Save correction metadata (username and timestamp for each field)
        if correction_metadata:
            if "correction_metadata" not in processed_data:
                processed_data["correction_metadata"] = {}
            
            for key, metadata in correction_metadata.items():
                processed_data["correction_metadata"][key] = metadata
            
            logger.info(f"Saved correction metadata for {len(correction_metadata)} fields in {blob_name}")
        
        # Save last correction info (for display under file confidence score)
        if last_correction:
            processed_data["last_correction"] = last_correction
            logger.info(f"Saved last correction info for {blob_name}: {last_correction}")
        
        # Add update timestamp
        processed_data["last_updated"] = datetime.now().isoformat()
        processed_data["updated_by"] = current_user.username
        
        # Upload the updated JSON back to blob storage
        blob_client = blob_service.blob_service_client.get_blob_client(
            container=blob_service.container_name,
            blob=blob_name
        )
        
        updated_json_bytes = json.dumps(processed_data, indent=2).encode('utf-8')
        blob_client.upload_blob(updated_json_bytes, overwrite=True)
        
        logger.info(f"Successfully updated processed JSON: {blob_name}")
        
        return {
            "status": "success",
            "message": "Confidence scores updated successfully",
            "updated_fields": len(updated_confidence_scores),
            "updated_values": len(updated_key_value_pairs),
            "blob_path": blob_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating confidence scores in {blob_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update confidence scores")

@router.get("/blob/stats")
async def get_blob_stats(current_user: User = Depends(get_current_active_user)):
    """Get statistics about uploaded files for the current user."""
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            return {
                "status": "error",
                "message": "Azure Blob Storage not available",
                "stats": {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "files_by_type": {},
                    "recent_uploads": []
                }
            }
        
        # Get all files for the tenant
        files = blob_service.list_files_for_tenant(current_user.tenant_id)
        
        # Calculate statistics
        total_files = len(files)
        total_size_bytes = sum(file.get("size", 0) for file in files)
        
        # Group by file type
        files_by_type = {}
        for file in files:
            content_type = file.get("content_type", "unknown")
            if content_type not in files_by_type:
                files_by_type[content_type] = {"count": 0, "total_size": 0}
            files_by_type[content_type]["count"] += 1
            files_by_type[content_type]["total_size"] += file.get("size", 0)
        
        # Get recent uploads (last 10)
        recent_uploads = sorted(files, key=lambda x: x.get("last_modified", ""), reverse=True)[:10]
        
        return {
            "status": "success",
            "stats": {
                "total_files": total_files,
                "total_size_bytes": total_size_bytes,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
                "files_by_type": files_by_type,
                "recent_uploads": recent_uploads
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting blob statistics: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get blob statistics")

@router.get("/blob/files")
async def get_user_files(current_user: User = Depends(get_current_active_user)):
    """Get all files uploaded by the current user."""
    try:
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            return {
                "status": "error",
                "message": "Azure Blob Storage not available",
                "files": []
            }
        
        files = blob_service.list_files_for_tenant(current_user.tenant_id)
        
        return {
            "status": "success",
            "files": files,
            "count": len(files)
        }
        
    except Exception as e:
        logger.error(f"Error getting user files: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get user files")


@router.get("/blob/status")
async def get_blob_storage_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get Azure Blob Storage status and configuration details."""
    try:
        blob_service = AzureBlobService()
        status = blob_service.get_status()
        
        return {
            "status": "success",
            "blob_storage": status
        }
    except Exception as e:
        logger.error(f"Error getting blob storage status: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get blob storage status")


# ============================================================================
# TEMPLATE MAPPING ENDPOINTS
# ============================================================================

@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload an Excel template file for document mapping"""
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
        
        # Read file data
        file_data = await file.read()
        
        # Initialize template mapper
        template_mapper = TemplateMapper()
        
        # Upload template
        result = template_mapper.upload_template(
            file_data=file_data,
            filename=file.filename,
            tenant_id=current_user.tenant_id
        )
        
        if result["success"]:
            return {
                "status": "success",
                "message": "Template uploaded successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Error uploading template: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to upload template")

@router.get("/templates")
async def list_templates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all templates for the current tenant"""
    try:
        template_mapper = TemplateMapper()
        templates = template_mapper.list_templates(current_user.tenant_id)
        
        return {
            "status": "success",
            "data": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")

@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template details and structure"""
    try:
        template_mapper = TemplateMapper()
        template = template_mapper.get_template(template_id, current_user.tenant_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return {
            "status": "success",
            "data": template
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get template")

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a template"""
    try:
        template_mapper = TemplateMapper()
        result = template_mapper.delete_template(template_id, current_user.tenant_id)
        
        if result["success"]:
            return {
                "status": "success",
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to delete template")

@router.post("/templates/{template_id}/map")
async def map_document_to_template(
    template_id: str,
    extracted_data: Dict[str, Any] = Body(...),
    document_id: str = Body(...),
    filename: str = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Map extracted document data to template fields"""
    try:
        template_mapper = TemplateMapper()
        
        # Map document to template
        mapping_result = template_mapper.map_document_to_template(
            template_id=template_id,
            tenant_id=current_user.tenant_id,
            extracted_data=extracted_data,
            document_id=document_id,
            filename=filename
        )
        
        # Only expose non-empty mapped values; move full mapping payload to a hidden object
        filtered_public_values = {k: v for k, v in mapping_result.mapped_values.items() if (isinstance(v, str) and v.strip() != "") or (v is not None and v != "")}

        return {
            "status": "success",
            "data": {
                "document_id": mapping_result.document_id,
                "filename": mapping_result.filename,
                "extracted_values": filtered_public_values,
                # Hidden detailed mapping for internal use only by the client app
                "_hidden_mapping": {
                    "mapped_values": mapping_result.mapped_values,
                    "confidence_scores": mapping_result.confidence_scores,
                    "unmapped_fields": mapping_result.unmapped_fields,
                    "processing_timestamp": mapping_result.processing_timestamp
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error mapping document to template: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to map document to template")

@router.put("/templates/{template_id}/mappings/{document_id}")
async def update_mapped_values(
    template_id: str,
    document_id: str,
    updated_values: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update mapped values for a document"""
    try:
        template_mapper = TemplateMapper()
        
        result = template_mapper.update_mapped_values(
            template_id=template_id,
            tenant_id=current_user.tenant_id,
            document_id=document_id,
            updated_values=updated_values
        )
        
        if result["success"]:
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error updating mapped values: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to update mapped values")

@router.post("/templates/{template_id}/export")
async def export_consolidated_excel(
    template_id: str,
    mapping_results: List[Dict[str, Any]],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export consolidated Excel with all mapped documents"""
    try:
        template_mapper = TemplateMapper()
        
        # Convert dict results to MappingResult objects
        from services.template_mapper import MappingResult
        results = []
        for result_data in mapping_results:
            result = MappingResult(
                document_id=result_data["document_id"],
                filename=result_data["filename"],
                mapped_values=result_data["mapped_values"],
                confidence_scores=result_data.get("confidence_scores", {}),
                unmapped_fields=result_data.get("unmapped_fields", []),
                processing_timestamp=result_data.get("processing_timestamp", datetime.now().isoformat())
            )
            results.append(result)
        
        # Generate consolidated Excel
        excel_data = template_mapper.generate_consolidated_excel(
            template_id=template_id,
            tenant_id=current_user.tenant_id,
            mapping_results=results
        )
        
        # Return as streaming response
        filename = f"consolidated_mapping_{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            BytesIO(excel_data.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting consolidated Excel: {e}")
        raise HTTPException(status_code=500, detail="Failed to export Excel")

@router.post("/templates/{template_id}/map-from-text")
async def map_from_ocr_text(
    template_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Map already-processed OCR text to a template using the LLM, without re-uploading the file.

    Body expects: { ocr_text: string, filename?: string }
    """
    try:
        ocr_text = payload.get("ocr_text", "")
        filename = payload.get("filename") or "unknown"

        if not isinstance(ocr_text, str) or len(ocr_text.strip()) == 0:
            raise HTTPException(status_code=400, detail="ocr_text is required")

        # Build LLM-friendly template from tenant template
        template_mapper = TemplateMapper()
        tenant_template = template_mapper.get_template(template_id, current_user.tenant_id)
        if not tenant_template:
            raise HTTPException(status_code=404, detail="Template not found for tenant")

        fields_map = {}
        for f in tenant_template.get("fields", []):
            key = f.get("display_name") or f.get("key")
            if not key:
                continue
            fields_map[key] = {
                "type": f.get("data_type", "text"),
                "description": f.get("description", "")
            }
        llm_template = {
            "name": tenant_template.get("filename", "Template"),
            "description": "Tenant Excel template",
            "fields": fields_map
        }

        # Use LLM to map the OCR text to the provided template fields
        text_processor = EnhancedTextProcessor()
        processing_result = await text_processor.process_with_template(
            ocr_text=ocr_text,
            template=llm_template,
            filename=filename
        )

        # Post-process via TemplateMapper to ensure strict key set and confidence
        document_id = str(uuid.uuid4())
        mapping_result = template_mapper.map_document_to_template(
            template_id=template_id,
            tenant_id=current_user.tenant_id,
            extracted_data=processing_result.key_value_pairs,
            document_id=document_id,
            filename=filename
        )

        # Only expose non-empty extracted values; include full details in hidden object
        filtered_public_values = {k: v for k, v in mapping_result.mapped_values.items() if (isinstance(v, str) and v.strip() != "") or (v is not None and v != "")}

        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "extracted_values": filtered_public_values,
            "_hidden_mapping": {
                "template_mapping": {
                    "mapped_values": mapping_result.mapped_values,
                    "confidence_scores": mapping_result.confidence_scores,
                    "unmapped_fields": mapping_result.unmapped_fields,
                    "processing_timestamp": mapping_result.processing_timestamp
                },
                "extraction_result": {
                    "key_value_pairs": processing_result.key_value_pairs,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error mapping OCR text to template: {e}")
        raise HTTPException(status_code=500, detail="Failed to map OCR text")

@router.post("/templates/{template_id}/export/document/excel")
async def export_mapped_document_excel(
    template_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export a single mapped document as a Key-Value Pairs Excel using only visible extracted values."""
    try:
        extracted_values = payload.get("extracted_values") or payload.get("mapped_values") or {}
        filename = payload.get("filename") or payload.get("file_info", {}).get("filename") or "mapped_document"

        # Filter again server-side to ensure only non-empty values are exported
        filtered_values = {k: v for k, v in (extracted_values or {}).items() if (isinstance(v, str) and v.strip() != "") or (v is not None and v != "")}

        processed_data = {
            "file_info": {"filename": filename},
            "key_value_pairs": filtered_values,
            "summary": payload.get("summary", ""),
            "confidence_score": payload.get("confidence_score", 0.0)
        }

        exporter = ExcelExporter()
        excel_buffer = exporter.create_individual_excel(
            processed_data=processed_data,
            include_raw_text=False,
            include_metadata=True
        )

        export_filename = filename if filename.endswith('.xlsx') else f"{Path(filename).stem}_keyvalues.xlsx"

        return StreamingResponse(
            BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={export_filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting mapped document excel: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to export mapped document excel")

@router.post("/templates/{template_id}/export/document/json")
async def export_mapped_document_json(
    template_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export a single mapped document as JSON with only visible extracted key-value pairs."""
    try:
        extracted_values = payload.get("extracted_values") or payload.get("mapped_values") or {}
        filename = payload.get("filename") or payload.get("file_info", {}).get("filename") or "mapped_document"

        # Filter again server-side to ensure only non-empty values are exported
        filtered_values = {k: v for k, v in (extracted_values or {}).items() if (isinstance(v, str) and v.strip() != "") or (v is not None and v != "")}

        json_bytes = json.dumps({"key_value_pairs": filtered_values}, ensure_ascii=False, indent=2).encode("utf-8")
        export_filename = filename if filename.endswith('.json') else f"{Path(filename).stem}_keyvalues.json"

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={export_filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting mapped document json: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to export mapped document json")
@router.post("/ocr/enhanced/process-with-template")
async def process_with_template(
    file: UploadFile = File(...),
    template_id: str = Form(...),
    apply_preprocessing: bool = Form(True),
    enhance_quality: bool = Form(True),
    include_raw_text: bool = Form(False),
    include_metadata: bool = Form(True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Process document with template mapping"""
    try:
        # Validate file type
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
        
        logger.info(f"Processing document with template {template_id}: {file.filename}")
        
        # Read file data
        file_data = await file.read()
        
        # Process with Azure Computer Vision OCR
        result = await ocr_from_path(
            file_data=file_data,
            original_filename=file.filename or "unknown",
            ocr_engine="azure_computer_vision",
            ground_truth="",
            apply_preprocessing=apply_preprocessing,
            enhance_quality=enhance_quality
        )
        
        # Initialize enhanced text processor
        text_processor = EnhancedTextProcessor()
        
        # Load tenant template and build LLM-friendly structure
        template_mapper = TemplateMapper()
        tenant_template = template_mapper.get_template(template_id, current_user.tenant_id)
        if not tenant_template:
            raise HTTPException(status_code=404, detail="Template not found for tenant")
        # Build fields map: { display name -> { type, description } }
        fields_map = {}
        for f in tenant_template.get("fields", []):
            key = f.get("display_name") or f.get("key")
            if not key:
                continue
            fields_map[key] = {
                "type": f.get("data_type", "text"),
                "description": f.get("description", "")
            }
        llm_template = {
            "name": tenant_template.get("filename", "Template"),
            "description": "Tenant Excel template",
            "fields": fields_map
        }
        
        # Prefer LLM-driven extraction mapped to the provided template fields
        processing_result = await text_processor.process_with_template(
            ocr_text=result.get("combined_text", ""),
            template=llm_template,
            filename=file.filename or "unknown"
        )
        
        # Create mapping status/metrics based on LLM output
        document_id = str(uuid.uuid4())
        mapping_result = template_mapper.map_document_to_template(
            template_id=template_id,
            tenant_id=current_user.tenant_id,
            extracted_data=processing_result.key_value_pairs,
            document_id=document_id,
            filename=file.filename or "unknown"
        )
        
        # Calculate OCR confidence from text_blocks
        ocr_confidence_score = calculate_ocr_confidence(result)
        
        # Upload JSON data to blob storage if available (NO original files)
        json_upload_result = None
        try:
            blob_service = AzureBlobService()
            if blob_service.is_available():
                processing_id = str(uuid.uuid4())
                
                # Upload processed JSON data with template mapping
                processed_json_data = {
                    "file_info": {
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size_bytes": len(file_data),
                        "pages_processed": len(result.get("raw_ocr_results", []))
                    },
                    "extracted_values": filtered_public_values,
                    "template_mapping": {
                        "mapped_values": mapping_result.mapped_values,
                        "confidence_scores": mapping_result.confidence_scores,
                        "unmapped_fields": mapping_result.unmapped_fields,
                        "processing_timestamp": mapping_result.processing_timestamp
                    },
                    "extraction_result": {
                        "key_value_pairs": processing_result.key_value_pairs,
                        "summary": processing_result.summary,
                        "confidence_score": processing_result.confidence_score
                    },
                    "confidence_score": processing_result.confidence_score,
                    "ocr_confidence_score": ocr_confidence_score,
                    "processing_info": {
                        "processing_time": result.get("processing_time", 0),
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": "AI-powered with template mapping"
                    },
                    "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
                    "raw_ocr_results": result.get("raw_ocr_results", []),
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "text_length": len(result.get("combined_text", "")),
                        "ai_processing": text_processor.is_available()
                    } if include_metadata else None
                }
                
                json_upload_result = blob_service.upload_processed_json(
                    json_data=processed_json_data,
                    filename=file.filename or "unknown",
                    tenant_id=current_user.tenant_id,
                    processing_id=processing_id
                )
                
                if json_upload_result.get("success"):
                    logger.info(f"[SUCCESS] JSON data uploaded to processed folder: {json_upload_result['blob_path']}")
                else:
                    logger.warning(f"[ERROR] Failed to upload JSON data: {json_upload_result.get('error')}")
                    
        except Exception as e:
            logger.error(f"Failed to upload JSON to blob storage", exc_info=True)
            # Do not expose internal error details or stack traces to the client
            json_upload_result = {
                "success": False,
                "error": "Failed to upload processed data to storage"
            }
        
        # Only expose non-empty extracted values; include full details in a hidden object
        filtered_public_values = {k: v for k, v in mapping_result.mapped_values.items() if (isinstance(v, str) and v.strip() != "") or (v is not None and v != "")}

        return {
            "status": "success",
            "document_id": document_id,
            "filename": file.filename,
            "extracted_values": filtered_public_values,
            # Hidden detailed mapping for internal use only by the client app
            "_hidden_mapping": {
                "template_mapping": {
                    "mapped_values": mapping_result.mapped_values,
                    "confidence_scores": mapping_result.confidence_scores,
                    "unmapped_fields": mapping_result.unmapped_fields,
                    "processing_timestamp": mapping_result.processing_timestamp
                },
                "extraction_result": {
                    "key_value_pairs": processing_result.key_value_pairs,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score
                },
                "processing_info": {
                    "processing_time": result.get("processing_time", 0),
                    "preprocessing_applied": apply_preprocessing,
                    "quality_enhanced": enhance_quality,
                    "extraction_method": "AI-powered with template mapping"
                },
                "raw_ocr_text": result.get("combined_text", "") if include_raw_text else None,
                "raw_ocr_results": result.get("raw_ocr_results", []),
                "metadata": {
                    "extraction_timestamp": datetime.now().isoformat(),
                    "text_length": len(result.get("combined_text", "")),
                    "ai_processing": text_processor.is_available()
                } if include_metadata else None,
                "blob_storage": {
                    "processed_json": json_upload_result
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing document with template: {e}")
        raise HTTPException(status_code=500, detail="Failed to process document")

@router.post("/insights/generate-summary")
async def generate_report_summary(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user)
) -> Response:
    """
    Generate a summary report of the insights table data using LLM.
    
    Request body should contain:
    - table_data: List of file records with their details
    - kpi_data: KPI metrics (totalFiles, completedFiles, etc.)
    - status_breakdown: Status breakdown data
    - confidence_breakdown: Confidence breakdown data
    - selected_date: Selected date for the report
    """
    try:
        table_data = payload.get("table_data", [])
        kpi_data = payload.get("kpi_data", {})
        status_breakdown = payload.get("status_breakdown", [])
        confidence_breakdown = payload.get("confidence_breakdown", [])
        selected_date = payload.get("selected_date", "")
        
        logger.info(f"Generating report summary for {len(table_data)} files")
        
        text_processor = EnhancedTextProcessor()
        
        if not text_processor.is_available():
            logger.warning("LLM service not available, generating basic summary")
            # Generate a basic summary without LLM
            summary = _generate_basic_summary(table_data, kpi_data, status_breakdown, confidence_breakdown, selected_date)
        else:
            # Generate summary using LLM
            summary = await _generate_llm_summary(
                text_processor, table_data, kpi_data, status_breakdown, confidence_breakdown, selected_date
            )
        
        # Generate PDF from summary text
        pdf_content = _generate_pdf_from_summary(summary, kpi_data, status_breakdown, confidence_breakdown, table_data, selected_date)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Report_Summary_{timestamp}.pdf"
        
        # Return as downloadable PDF file
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating report summary: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to generate report summary")

def _generate_basic_summary(
    table_data: List[Dict[str, Any]],
    kpi_data: Dict[str, Any],
    status_breakdown: List[Dict[str, Any]],
    confidence_breakdown: List[Dict[str, Any]],
    selected_date: str
) -> str:
    """Generate a basic summary without LLM."""
    summary_lines = []
    summary_lines.append("=" * 80)
    summary_lines.append("FAX AUTOMATION INSIGHTS - REPORT SUMMARY")
    summary_lines.append("=" * 80)
    summary_lines.append(f"\nReport Date: {selected_date if selected_date else 'All Dates'}")
    summary_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("KEY PERFORMANCE INDICATORS")
    summary_lines.append("=" * 80)
    summary_lines.append(f"Total Files Scanned: {kpi_data.get('totalFiles', 0)}")
    summary_lines.append(f"Completed Files: {kpi_data.get('completedFiles', 0)}")
    summary_lines.append(f"Pending Files: {kpi_data.get('pendingFiles', 0)}")
    summary_lines.append(f"Scanning Accuracy: {kpi_data.get('scanningAccuracy', '0%')}")
    summary_lines.append(f"Last Updated: {kpi_data.get('lastUpdated', 'N/A')} {kpi_data.get('lastUpdatedTime', '')}")
    
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("STATUS BREAKDOWN")
    summary_lines.append("=" * 80)
    for status in status_breakdown:
        summary_lines.append(f"{status.get('label', 'N/A')}: {status.get('value', 0)} ({status.get('total', 0)} total)")
    
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("CONFIDENCE BREAKDOWN")
    summary_lines.append("=" * 80)
    for conf in confidence_breakdown:
        summary_lines.append(f"{conf.get('label', 'N/A')}: {conf.get('value', 0)} files")
    
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("FILE DETAILS")
    summary_lines.append("=" * 80)
    for i, file in enumerate(table_data[:50], 1):  # Limit to first 50 files
        summary_lines.append(f"\n{i}. {file.get('fileName', 'N/A')}")
        summary_lines.append(f"   Status: {file.get('status', 'N/A')}")
        summary_lines.append(f"   Accuracy: {file.get('accuracy', 'N/A')}")
        summary_lines.append(f"   Updated Date: {file.get('updatedDate', 'N/A')}")
    
    if len(table_data) > 50:
        summary_lines.append(f"\n... and {len(table_data) - 50} more files")
    
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("END OF REPORT")
    summary_lines.append("=" * 80)
    
    return "\n".join(summary_lines)

async def _generate_llm_summary(
    text_processor: EnhancedTextProcessor,
    table_data: List[Dict[str, Any]],
    kpi_data: Dict[str, Any],
    status_breakdown: List[Dict[str, Any]],
    confidence_breakdown: List[Dict[str, Any]],
    selected_date: str
) -> str:
    """Generate summary using LLM."""
    try:
        # Prepare data for LLM
        data_summary = {
            "total_files": kpi_data.get('totalFiles', 0),
            "completed_files": kpi_data.get('completedFiles', 0),
            "pending_files": kpi_data.get('pendingFiles', 0),
            "scanning_accuracy": kpi_data.get('scanningAccuracy', '0%'),
            "status_breakdown": status_breakdown,
            "confidence_breakdown": confidence_breakdown,
            "sample_files": table_data[:20]  # Send first 20 files as sample
        }
        
        # Create prompt for LLM
        prompt = f"""You are an AI assistant that generates comprehensive report summaries for fax automation insights.

Based on the following data, create a detailed, professional report summary that includes:
1. Executive Summary with key highlights
2. Performance Metrics Analysis
3. Status Distribution Analysis
4. Confidence Score Analysis
5. Key Findings and Recommendations
6. File Processing Overview

Data:
{json.dumps(data_summary, indent=2)}

Selected Date: {selected_date if selected_date else 'All Dates'}

Generate a comprehensive, well-structured report summary. Use clear sections, bullet points where appropriate, and provide actionable insights.
Format the output as a professional report with clear headings and sections."""

        # Get response from LLM
        response = await text_processor.client.ainvoke(prompt)
        llm_summary = response.content
        
        # Add header and metadata
        final_summary = f"""
{'=' * 80}
FAX AUTOMATION INSIGHTS - AI-GENERATED REPORT SUMMARY
{'=' * 80}

Report Date: {selected_date if selected_date else 'All Dates'}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Files Analyzed: {len(table_data)}

{'=' * 80}

{llm_summary}

{'=' * 80}
END OF REPORT
{'=' * 80}
"""
        return final_summary
        
    except Exception as e:
        logger.error(f"Error generating LLM summary: {e}")
        # Fallback to basic summary
        return _generate_basic_summary(table_data, kpi_data, status_breakdown, confidence_breakdown, selected_date)

def _generate_pdf_from_summary(
    summary_text: str,
    kpi_data: Dict[str, Any],
    status_breakdown: List[Dict[str, Any]],
    confidence_breakdown: List[Dict[str, Any]],
    table_data: List[Dict[str, Any]],
    selected_date: str
) -> bytes:
    """Generate PDF from summary text using ReportLab with professional UI matching website design."""
    try:
        buffer = BytesIO()
        # Professional margins matching website spacing
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter, 
            topMargin=0.5*inch, 
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        # Define professional styles matching website UI
        styles = getSampleStyleSheet()
        
        # Title style - Large, bold, centered, matching website header
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#1E40AF',  # Blue-800 matching website
            spaceAfter=16,
            spaceBefore=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=28
        )
        
        # Section heading style - Professional blue-gray
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor='#1E40AF',  # Blue-800
            spaceAfter=10,
            spaceBefore=16,
            fontName='Helvetica-Bold',
            leading=20,
            borderWidth=0,
            borderPadding=0
        )
        
        # Subheading style for KPI cards
        subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor='#374151',  # Gray-700
            spaceAfter=6,
            spaceBefore=8,
            fontName='Helvetica-Bold',
            leading=16
        )
        
        # Normal text style
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor='#1F2937',  # Gray-800
            spaceAfter=8,
            alignment=TA_LEFT,
            leading=14
        )
        
        # KPI value style - Large, bold numbers
        kpi_value_style = ParagraphStyle(
            'KPIValue',
            parent=styles['Normal'],
            fontSize=20,
            textColor='#2563EB',  # Blue-600 matching website
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=24
        )
        
        # KPI label style
        kpi_label_style = ParagraphStyle(
            'KPILabel',
            parent=styles['Normal'],
            fontSize=9,
            textColor='#6B7280',  # Gray-500
            spaceAfter=0,
            alignment=TA_CENTER,
            leading=12
        )
        
        # Metadata style
        metadata_style = ParagraphStyle(
            'Metadata',
            parent=styles['Normal'],
            fontSize=9,
            textColor='#6B7280',  # Gray-500
            spaceAfter=4,
            alignment=TA_LEFT,
            leading=12
        )
        
        # Table cell styles
        table_cell_style_left = ParagraphStyle(
            'TableCellStyleLeft',
            parent=styles['Normal'],
            fontSize=8,
            textColor='#1F2937',  # Gray-800
            spaceAfter=2,
            spaceBefore=2,
            alignment=TA_LEFT,
            leading=10
        )
        table_cell_style_center = ParagraphStyle(
            'TableCellStyleCenter',
            parent=styles['Normal'],
            fontSize=8,
            textColor='#1F2937',  # Gray-800
            spaceAfter=2,
            spaceBefore=2,
            alignment=TA_CENTER,
            leading=10
        )
        
        # Build PDF content
        story = []
        
        # Professional Header with colored background box
        header_table = Table([
            [Paragraph("FAX AUTOMATION INSIGHTS", title_style)]
        ], colWidths=[7*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EFF6FF')),  # Blue-50
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 16),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 16),
            ('LEFTPADDING', (0, 0), (-1, 0), 0),
            ('RIGHTPADDING', (0, 0), (-1, 0), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Report metadata in a subtle box
        report_date = selected_date if selected_date else 'All Dates'
        generated_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        metadata_table = Table([
            [
                Paragraph(f"<b>Report Date:</b> {report_date}", metadata_style),
                Paragraph(f"<b>Generated:</b> {generated_time}", metadata_style)
            ]
        ], colWidths=[3.5*inch, 3.5*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F9FAFB')),  # Gray-50
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('LEFTPADDING', (0, 0), (-1, 0), 12),
            ('RIGHTPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, 0), 1, colors.HexColor('#E5E7EB')),  # Gray-200 border
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 0.25*inch))
        
        # Key Performance Indicators in card-style layout
        story.append(Paragraph("KEY PERFORMANCE INDICATORS", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # KPI Cards in a grid layout
        kpi_cards = [
            ('Total Files', str(kpi_data.get('totalFiles', 0)), '#2563EB'),  # Blue-600
            ('Completed', str(kpi_data.get('completedFiles', 0)), '#10B981'),  # Green-500
            ('Pending', str(kpi_data.get('pendingFiles', 0)), '#F59E0B'),  # Amber-500
            ('Accuracy', kpi_data.get('scanningAccuracy', '0%'), '#8B5CF6'),  # Purple-500
        ]
        
        kpi_table_data = []
        for label, value, color in kpi_cards:
            kpi_table_data.append([
                Paragraph(f"<font color='{color}' size='18'><b>{value}</b></font>", kpi_value_style),
                Paragraph(label, kpi_label_style)
            ])
        
        kpi_table = Table(kpi_table_data, colWidths=[1.75*inch] * 4)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),  # Gray-200 borders
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#F9FAFB')]),  # Gray-50 background
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Last Updated info
        story.append(Paragraph(
            f"<b>Last Updated:</b> {kpi_data.get('lastUpdated', 'N/A')} {kpi_data.get('lastUpdatedTime', '')}", 
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Status Breakdown with colored badges
        story.append(Paragraph("STATUS BREAKDOWN", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        status_colors = {
            'Successful Scans': '#10B981',  # Green-500
            'Failed / Error Files': '#EF4444',  # Red-500
            'Manual Review': '#F59E0B',  # Amber-500
        }
        
        for status in status_breakdown:
            label = status.get('label', 'N/A')
            value = status.get('value', 0)
            total = status.get('total', 0)
            color = status_colors.get(label, '#6B7280')
            story.append(Paragraph(
                f"<font color='{color}'><b>●</b></font> <b>{label}:</b> {value} ({total} total)", 
                normal_style
            ))
        story.append(Spacer(1, 0.15*inch))
        
        # Confidence Breakdown with colored indicators
        story.append(Paragraph("CONFIDENCE BREAKDOWN", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        confidence_colors = {
            'Green (≥95%)': '#10B981',  # Green-500
            'Amber (90-94.9%)': '#F59E0B',  # Amber-500
            'Red (<89.9%)': '#EF4444',  # Red-500
        }
        
        for conf in confidence_breakdown:
            label = conf.get('label', 'N/A')
            value = conf.get('value', 0)
            color = confidence_colors.get(label, '#6B7280')
            story.append(Paragraph(
                f"<font color='{color}'><b>●</b></font> <b>{label}:</b> {value} files", 
                normal_style
            ))
        story.append(Spacer(1, 0.3*inch))
        
        # Files Table with File Details - Add at the bottom of PDF
        if table_data and len(table_data) > 0:
            story.append(PageBreak())
            story.append(Paragraph("FILES TABLE - FILE DETAILS", heading_style))
            story.append(Spacer(1, 0.15*inch))
            
            # Prepare table data with all files and their details
            table_rows = []
            
            # Create table header with all file detail columns including Missing Fields and Remarks
            table_rows.append([
                'No.',
                'File Name',
                'Status',
                'Accuracy %',
                'Assigned User',
                'Updated Date',
                'Last Update',
                'Missing Fields',
                'Remarks'
            ])
            
            # Add file rows with all details
            for idx, file in enumerate(table_data, 1):
                file_name = file.get('fileName', 'N/A')
                status = file.get('status', 'N/A')
                accuracy = file.get('accuracy', 'N/A')
                assigned_user = file.get('assignedUser', 'N/A')
                assigned_user_value = file.get('assignedUserValue', 'unassigned')
                
                # Handle assigned user display
                if assigned_user == '?' or assigned_user == 'unassigned' or assigned_user_value == 'unassigned':
                    assigned_user = 'Unassigned'
                elif assigned_user and len(assigned_user) == 1:
                    # If it's just an initial, show it
                    assigned_user = assigned_user
                else:
                    assigned_user = assigned_user if assigned_user != 'N/A' else 'Unassigned'
                
                updated_date = file.get('updatedDate', 'N/A')
                last_update = file.get('lastUpdate', 'N/A')
                
                # Handle missing fields
                missing_fields_list = file.get('missingFields', [])
                if isinstance(missing_fields_list, list) and len(missing_fields_list) > 0:
                    missing_fields_str = ', '.join(missing_fields_list)
                    # Don't truncate - let Paragraph handle wrapping
                else:
                    missing_fields_str = 'None'
                
                # Handle remarks
                remarks_text = file.get('remarks', '') or ''
                if not remarks_text:
                    remarks_text = '-'
                # Don't truncate - let Paragraph handle wrapping
                
                # Truncate long file names to fit in table
                if len(file_name) > 35:
                    file_name = file_name[:32] + '...'
                
                table_rows.append([
                    str(idx),
                    file_name,
                    status,
                    accuracy,
                    assigned_user,
                    updated_date,
                    last_update,
                    missing_fields_str,
                    remarks_text
                ])
            
            # Convert table data to Paragraph objects for proper text wrapping
            formatted_table_rows = []
            for row_idx, row in enumerate(table_rows):
                formatted_row = []
                for col_idx, cell_text in enumerate(row):
                    # Escape HTML entities
                    cell_text_escaped = str(cell_text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    # Use Paragraph for text wrapping, especially for long content
                    if row_idx == 0:  # Header row
                        # Header style - use center alignment for most columns, left for text columns
                        if col_idx in [0, 2, 3, 4, 5, 6]:  # Center align columns
                            header_style = ParagraphStyle(
                                'TableHeaderStyleCenter',
                                parent=styles['Normal'],
                                fontSize=8,
                                textColor='#FFFFFF',
                                spaceAfter=2,
                                spaceBefore=2,
                                alignment=TA_CENTER,
                                leading=10,
                                fontName='Helvetica-Bold'
                            )
                        else:  # Left align columns
                            header_style = ParagraphStyle(
                                'TableHeaderStyleLeft',
                                parent=styles['Normal'],
                                fontSize=8,
                                textColor='#FFFFFF',
                                spaceAfter=2,
                                spaceBefore=2,
                                alignment=TA_LEFT,
                                leading=10,
                                fontName='Helvetica-Bold'
                            )
                        formatted_row.append(Paragraph(f"<b>{cell_text_escaped}</b>", header_style))
                    else:  # Data rows
                        # Apply color coding for status column
                        if col_idx == 2:  # Status column
                            status_text = str(cell_text).strip()
                            # Color code statuses matching website
                            status_colors_map = {
                                'Completed': '#10B981',  # Green-600
                                'In Progress': '#2563EB',  # Blue-600
                                'Error': '#EF4444',  # Red-500
                                'Review Needed': '#F59E0B',  # Amber-500
                            }
                            status_color = status_colors_map.get(status_text, '#6B7280')  # Gray-500 default
                            cell_text_escaped = f"<font color='{status_color}'>{cell_text_escaped}</font>"
                            formatted_row.append(Paragraph(cell_text_escaped, table_cell_style_center))
                        # Apply color coding for accuracy column
                        elif col_idx == 3:  # Accuracy column
                            accuracy_text = str(cell_text).strip()
                            # Extract numeric value if possible
                            try:
                                accuracy_num = float(accuracy_text.replace('%', ''))
                                if accuracy_num >= 95:
                                    accuracy_color = '#10B981'  # Green-600
                                elif accuracy_num >= 90:
                                    accuracy_color = '#F59E0B'  # Amber-500
                                else:
                                    accuracy_color = '#EF4444'  # Red-500
                                cell_text_escaped = f"<font color='{accuracy_color}'><b>{cell_text_escaped}</b></font>"
                            except:
                                pass  # Keep original if not numeric
                            formatted_row.append(Paragraph(cell_text_escaped, table_cell_style_center))
                        # Use appropriate style based on column alignment
                        elif col_idx in [0, 4, 5, 6]:  # Center align columns (No., Assigned User, Updated Date, Last Update)
                            formatted_row.append(Paragraph(cell_text_escaped, table_cell_style_center))
                        else:  # Left align columns (File Name, Missing Fields, Remarks)
                            formatted_row.append(Paragraph(cell_text_escaped, table_cell_style_left))
                formatted_table_rows.append(formatted_row)
            
            # Create table with appropriate column widths
            # Total width should be around 7.5 inches (letter width - margins)
            # Adjusted widths to fit all 9 columns with better distribution
            table = Table(formatted_table_rows, colWidths=[
                0.4*inch,   # No. (0)
                1.6*inch,   # File Name (1)
                0.75*inch,  # Status (2)
                0.7*inch,   # Accuracy % (3)
                0.85*inch,  # Assigned User (4)
                0.9*inch,   # Updated Date (5)
                0.9*inch,   # Last Update (6)
                1.2*inch,   # Missing Fields (7)
                1.1*inch    # Remarks (8)
            ], repeatRows=1)  # Repeat header on each page
            
            # Style the table with professional formatting matching website UI
            table.setStyle(TableStyle([
                # Header row styling - Professional blue header matching website
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),  # Blue-600 matching website
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center align row numbers
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),    # Left align File Name
                ('ALIGN', (2, 0), (2, -1), 'CENTER'), # Center align Status
                ('ALIGN', (3, 0), (3, -1), 'CENTER'), # Center align Accuracy %
                ('ALIGN', (4, 0), (4, -1), 'CENTER'), # Center align Assigned User
                ('ALIGN', (5, 0), (5, -1), 'CENTER'), # Center align Updated Date
                ('ALIGN', (6, 0), (6, -1), 'CENTER'), # Center align Last Update
                ('ALIGN', (7, 0), (7, -1), 'LEFT'),   # Left align Missing Fields
                ('ALIGN', (8, 0), (8, -1), 'LEFT'),   # Left align Remarks
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('LEFTPADDING', (0, 0), (-1, 0), 8),
                ('RIGHTPADDING', (0, 0), (-1, 0), 8),
                
                # Data rows styling - Clean white with subtle alternating rows
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1F2937')),  # Gray-800
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),  # Gray-200 grid matching website
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Top align for better text wrapping
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),  # Alternating: white and gray-50
                ('LEFTPADDING', (0, 1), (-1, -1), 8),
                ('RIGHTPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                
                # Special styling for status column (column 2) - Color-coded status badges
                ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),  # Bold status
                # Status colors will be applied in the cell content itself
                
                # Hover effect simulation - subtle border on even rows
                ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#F3F4F6')),  # Gray-100
            ]))
            
            story.append(table)
            story.append(Spacer(1, 0.25*inch))
            
            # Total files summary in a styled box
            total_files_box = Table([
                [Paragraph(f"<b>Total Files:</b> {len(table_data)}", normal_style)]
            ], colWidths=[7*inch])
            total_files_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EFF6FF')),  # Blue-50
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('LEFTPADDING', (0, 0), (-1, 0), 12),
                ('RIGHTPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, 0), 1, colors.HexColor('#DBEAFE')),  # Blue-200 border
            ]))
            story.append(total_files_box)
        
        story.append(Spacer(1, 0.3*inch))
        
        # Professional footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor='#9CA3AF',  # Gray-400
            spaceAfter=0,
            alignment=TA_CENTER,
            leading=12
        )
        story.append(Paragraph("END OF REPORT", footer_style))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(
            f"Generated by Fax Automation System • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
            footer_style
        ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        # Fallback: create a simple PDF with error message
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph("Error Generating PDF Report", styles['Heading1']))
        story.append(Paragraph(f"An error occurred: {str(e)}", styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue


# Analysis cache endpoints for fast AI suggestion retrieval
@router.post("/ocr/enhanced/save-analysis-cache")
async def save_analysis_cache(
    cache_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save AI analysis results to database cache for fast retrieval."""
    try:
        unique_file_id = cache_data.get("unique_file_id")
        if not unique_file_id:
            raise HTTPException(status_code=400, detail="unique_file_id is required")
        
        import hashlib
        file_hash = hashlib.sha256(unique_file_id.encode('utf-8')).hexdigest()
        
        # Check if cache entry already exists
        cache_entry = db.query(ProcessedFile).filter(
            ProcessedFile.processing_id == unique_file_id
        ).first()
        
        if cache_entry:
            # Update existing entry
            if isinstance(cache_entry.processed_data, dict):
                cache_entry.processed_data["ai_analysis_cache"] = {
                    "analysis_results": cache_data.get("analysis_results", {}),
                    "timestamp": cache_data.get("timestamp", datetime.now().isoformat()),
                    "filename": cache_data.get("filename", "unknown")
                }
            else:
                cache_entry.processed_data = {
                    "ai_analysis_cache": {
                        "analysis_results": cache_data.get("analysis_results", {}),
                        "timestamp": cache_data.get("timestamp", datetime.now().isoformat()),
                        "filename": cache_data.get("filename", "unknown")
                    }
                }
            cache_entry.updated_at = datetime.utcnow()
        else:
            # Create new cache entry in ProcessedFile table
            new_entry = ProcessedFile(
                file_hash=file_hash,
                processing_id=unique_file_id,
                tenant_id=current_user.tenant_id,
                filename=cache_data.get("filename", "unknown"),
                processed_data={
                    "ai_analysis_cache": {
                        "analysis_results": cache_data.get("analysis_results", {}),
                        "timestamp": cache_data.get("timestamp", datetime.now().isoformat()),
                        "filename": cache_data.get("filename", "unknown")
                    },
                    "key_value_pairs": cache_data.get("key_value_pairs", {}),
                    "confidence_scores": cache_data.get("confidence_scores", {})
                },
                created_at=datetime.utcnow()
            )
            db.add(new_entry)
        
        db.commit()
        logger.info(f"Saved analysis cache for unique_file_id: {unique_file_id}")
        return {"status": "success", "message": "Analysis cache saved"}
        
    except Exception as e:
        logger.error(f"Error saving analysis cache: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to save analysis cache")


@router.get("/ocr/enhanced/get-analysis-cache/{unique_file_id:path}")
async def get_analysis_cache(
    unique_file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI analysis results from database cache."""
    try:
        # URL decode the unique_file_id
        decoded_unique_file_id = unquote(unique_file_id)
        
        logger.info(f"🔍 Searching for analysis cache with unique_file_id: {decoded_unique_file_id}")
        
        # Strategy 1: Query by processed_blob_path first (most common - this is what gets saved)
        cache_entry = db.query(ProcessedFile).filter(
            ProcessedFile.processed_blob_path == decoded_unique_file_id,
            ProcessedFile.tenant_id == current_user.tenant_id
        ).first()
        if cache_entry:
            logger.info(f"✅ Found cache entry by processed_blob_path (exact): {decoded_unique_file_id}")
        
        # Strategy 2: Query by processing_id (exact match)
        if not cache_entry:
            cache_entry = db.query(ProcessedFile).filter(
                ProcessedFile.processing_id == decoded_unique_file_id,
                ProcessedFile.tenant_id == current_user.tenant_id
            ).first()
            if cache_entry:
                logger.info(f"✅ Found cache entry by processing_id: {decoded_unique_file_id}")
        
        # Strategy 3: Query by file_hash if unique_file_id is a hash
        if not cache_entry and decoded_unique_file_id.startswith("hash_"):
            hash_value = decoded_unique_file_id.replace("hash_", "")
            cache_entry = db.query(ProcessedFile).filter(
                ProcessedFile.file_hash == hash_value,
                ProcessedFile.tenant_id == current_user.tenant_id
            ).first()
            if cache_entry:
                logger.info(f"✅ Found cache entry by file_hash: {hash_value}")
        
        # Strategy 4: Search by stored file_id in ai_analysis_cache (check all entries for this tenant)
        if not cache_entry:
            all_files = db.query(ProcessedFile).filter(
                ProcessedFile.tenant_id == current_user.tenant_id
            ).all()
            
            for pf in all_files:
                if isinstance(pf.processed_data, dict):
                    ai_cache = pf.processed_data.get("ai_analysis_cache", {})
                    stored_file_id = ai_cache.get("file_id")
                    if stored_file_id and stored_file_id == decoded_unique_file_id:
                        cache_entry = pf
                        logger.info(f"✅ Found cache entry by stored file_id in ai_analysis_cache: {stored_file_id}")
                        break
        
        # Strategy 5: Query by filename (exact match)
        if not cache_entry:
            cache_entry = db.query(ProcessedFile).filter(
                ProcessedFile.filename == decoded_unique_file_id,
                ProcessedFile.tenant_id == current_user.tenant_id
            ).first()
            if cache_entry:
                logger.info(f"✅ Found cache entry by filename (exact): {decoded_unique_file_id}")
        
        # Strategy 6: Search by blob path pattern (blob paths may have different timestamps)
        # Extract base path by removing timestamp suffix (e.g., _1766399457152)
        if not cache_entry:
            # Remove timestamp suffix from blob path (format: _1234567890)
            base_path = re.sub(r'_\d+$', '', decoded_unique_file_id)
            
            # Query all files for this tenant and match by base path
            all_files = db.query(ProcessedFile).filter(
                ProcessedFile.tenant_id == current_user.tenant_id
            ).all()
            
            for pf in all_files:
                # Check if blob path base matches (ignoring timestamp suffix)
                if pf.processed_blob_path:
                    pf_base_path = re.sub(r'_\d+$', '', pf.processed_blob_path)
                    if pf_base_path == base_path:
                        if isinstance(pf.processed_data, dict) and pf.processed_data.get("ai_analysis_cache"):
                            cache_entry = pf
                            logger.info(f"✅ Found cache entry by blob path pattern match: {pf.processed_blob_path} (matched base: {base_path})")
                            break
                
                # Also check processing_id and stored file_id in cache
                if not cache_entry:
                    if pf.processing_id and pf.processing_id == decoded_unique_file_id:
                        if isinstance(pf.processed_data, dict) and pf.processed_data.get("ai_analysis_cache"):
                            cache_entry = pf
                            logger.info(f"✅ Found cache entry by processing_id match: {pf.processing_id}")
                            break
                    
                    # Check file_id stored in ai_analysis_cache
                    if isinstance(pf.processed_data, dict):
                        ai_cache = pf.processed_data.get("ai_analysis_cache", {})
                        stored_file_id = ai_cache.get("file_id")
                        if stored_file_id:
                            stored_base = re.sub(r'_\d+$', '', stored_file_id)
                            if stored_base == base_path or stored_file_id == decoded_unique_file_id:
                                cache_entry = pf
                                logger.info(f"✅ Found cache entry by stored file_id: {stored_file_id}")
                                break
        
        if not cache_entry:
            logger.warning(f"❌ Analysis cache not found for unique_file_id: {decoded_unique_file_id}")
            # Debug: Check if any entries exist for this tenant
            count = db.query(ProcessedFile).filter(
                ProcessedFile.tenant_id == current_user.tenant_id
            ).count()
            logger.info(f"🔍 Debug: Found {count} ProcessedFile entries for tenant {current_user.tenant_id}")
            return {"status": "not_found", "message": "Analysis cache not found"}
        
        # Refresh the cache entry to ensure we have the latest data
        db.refresh(cache_entry)
        
        # Check if user has access (same tenant or admin)
        if cache_entry.tenant_id != current_user.tenant_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")
        
        processed_data = cache_entry.processed_data if isinstance(cache_entry.processed_data, dict) else {}
        ai_cache = processed_data.get("ai_analysis_cache", {})
        
        if not ai_cache or not ai_cache.get("analysis_results"):
            logger.warning(f"❌ No analysis_results in cache for: {decoded_unique_file_id}")
            logger.info(f"🔍 Debug: processed_data keys: {list(processed_data.keys()) if isinstance(processed_data, dict) else 'not a dict'}")
            logger.info(f"🔍 Debug: ai_cache keys: {list(ai_cache.keys()) if isinstance(ai_cache, dict) else 'not a dict'}")
            logger.info(f"🔍 Debug: cache_entry.processing_id: {cache_entry.processing_id}")
            logger.info(f"🔍 Debug: cache_entry.processed_blob_path: {cache_entry.processed_blob_path}")
            return {"status": "not_found", "message": "Analysis cache not found"}
        
        logger.info(f"✅ Found analysis cache with {len(ai_cache.get('analysis_results', {}))} results")
        return {
            "status": "success",
            "analysis_results": ai_cache.get("analysis_results", {}),
            "timestamp": ai_cache.get("timestamp"),
            "filename": ai_cache.get("filename", "unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis cache: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get analysis cache")


@router.post("/epic/exchange-token")
async def exchange_epic_token(
    code: str = Body(..., description="Authorization code from Epic"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Exchange Epic authorization code for access token.
    This token is used to write Observation resources to Epic.
    """
    import requests
    
    # Require backend Epic credentials; avoid legacy VITE_* values that point to old app
    raw_client_id = os.getenv('EPIC_FHIR_CLIENT_ID') or os.getenv('EPIC_CLIENT_ID')
    raw_client_secret = os.getenv('EPIC_FHIR_CLIENT_SECRET') or os.getenv('EPIC_CLIENT_SECRET')
    legacy_client_id = os.getenv('VITE_EPIC_CLIENT_ID')
    legacy_client_secret = os.getenv('VITE_EPIC_CLIENT_SECRET')
    if not raw_client_id and legacy_client_id:
        logger.warning("Ignoring VITE_EPIC_CLIENT_ID to prevent use of legacy Epic app. Set EPIC_FHIR_CLIENT_ID or EPIC_CLIENT_ID.")
    if not raw_client_secret and legacy_client_secret:
        logger.warning("Ignoring VITE_EPIC_CLIENT_SECRET to prevent use of legacy Epic app. Set EPIC_FHIR_CLIENT_SECRET or EPIC_CLIENT_SECRET.")
    
    # Sanitize credentials (strip quotes/spaces) - CRITICAL FIX for .env loading
    epic_client_id = raw_client_id.strip().strip("'").strip('"') if raw_client_id else None
    epic_client_secret = raw_client_secret.strip().strip("'").strip('"') if raw_client_secret else None
    
    epic_token_url = os.getenv('EPIC_FHIR_TOKEN_URL') or os.getenv('EPIC_TOKEN_URL') or 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
    epic_redirect_uri = os.getenv('EPIC_REDIRECT_URI')
    
    if not epic_redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="Epic OAuth configuration is missing: EPIC_REDIRECT_URI not set"
        )
    
    if not epic_client_id:
        raise HTTPException(
            status_code=500,
            detail="Epic OAuth configuration is missing: EPIC_CLIENT_ID or EPIC_FHIR_CLIENT_ID not set in environment variables"
        )
    
    if not epic_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Epic OAuth configuration is missing: EPIC_CLIENT_SECRET or EPIC_FHIR_CLIENT_SECRET not set in environment variables"
        )
    
    try:
        # Use Basic Authentication for the request (Standard OAuth 2.0 for Confidential Clients)
        # We allow client_id in body too, as some providers expect it, but secret MUST be in Auth header or body (not both).
        # Requests 'auth' parameter handles the Basic Auth header generation automatically.
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': epic_redirect_uri,
            # Some providers want client_id in body AND header. It's safe to include.
            'client_id': epic_client_id
        }
        
        # Log sanitization check (masked) - SECURITY: Never log credentials in clear text
        safe_client_id = f"{epic_client_id[:4]}...{epic_client_id[-4:]}" if epic_client_id and len(epic_client_id) > 8 else "***"
        safe_secret = f"{epic_client_secret[:3]}...{epic_client_secret[-3:]}" if epic_client_secret and len(epic_client_secret) > 6 else "***"
        logger.info(f"Exchanging Epic Token - Client ID: {safe_client_id}, Redirect: {epic_redirect_uri}")
        
        token_response = requests.post(
            epic_token_url,
            data=token_data,
            auth=(epic_client_id, epic_client_secret),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if token_response.status_code != 200:
            error_detail = token_response.text
            # SECURITY: Log full error server-side, but don't expose it to client (may contain sensitive info)
            logger.error(f"Failed to exchange Epic token (status {token_response.status_code}): {error_detail}")
            raise HTTPException(
                status_code=401,
                detail=f"Failed to exchange Epic authorization code. Status: {token_response.status_code}"
            )
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="Epic OAuth did not return an access token"
            )
        
        return {
            "access_token": access_token,
            "token_type": token_json.get('token_type', 'Bearer'),
            "expires_in": token_json.get('expires_in', 3600)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exchanging Epic token: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to exchange Epic token")