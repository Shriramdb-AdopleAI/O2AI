"""Celery tasks for asynchronous document processing."""

import logging
import uuid
import json
import base64
import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List
from core.celery_app import celery_app
from utility.utils import ocr_from_path, calculate_ocr_confidence, calculate_key_value_pair_confidence_scores
from core.enhanced_text_processor import EnhancedTextProcessor
from services.azure_blob_service import AzureBlobService
from services.template_mapper import TemplateMapper
from services.null_field_service import null_field_service


logger = logging.getLogger(__name__)


def run_async_in_celery(coro):
    """
    Run async coroutines in Celery workers with proper event loop handling.
    Prevents Windows connection errors when using asyncio.run() multiple times.
    
    This function uses nest_asyncio to allow nested event loops,
    which is essential for Windows compatibility with Celery workers.
    """
    # Apply nest_asyncio to allow nested event loops (Windows compatibility)
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        logger.warning("nest_asyncio not installed. Install with: pip install nest-asyncio")
        # Fallback: try to use existing loop
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed() and not loop.is_running():
                return loop.run_until_complete(coro)
        except:
            pass
    
    # Use asyncio.run() - now safe with nest_asyncio applied
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # If there's still an error, create a completely new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@celery_app.task(bind=True, name="process_document", queue="processing")
def process_document(
    self,
    file_data: str,  # Base64 encoded file data (for Celery serialization only)
    filename: str,
    tenant_id: str,
    processing_id: str,
    apply_preprocessing: bool = True,
    enhance_quality: bool = True,
    include_raw_text: bool = True,
    include_metadata: bool = True,
    template_id: str = None,
    content_type: str = "application/octet-stream"
) -> Dict[str, Any]:
    """
    Process a single document with OCR and AI extraction.
    Files are passed directly to Document Intelligence without image preprocessing.
    
    Args:
        self: Task instance
        file_data: Base64 encoded document bytes (for Celery serialization only - decoded before OCR)
        filename: Original filename
        tenant_id: Tenant identifier
        processing_id: Unique processing ID
        apply_preprocessing: Ignored - kept for API compatibility
        enhance_quality: Ignored - kept for API compatibility
        include_raw_text: Include raw OCR text
        include_metadata: Include processing metadata
        template_id: Optional template ID for structured extraction
        content_type: MIME type of the file
        
    Returns:
        Dict with processing results
    """
    try:
        logger.info(f"Processing document: {filename} (ID: {processing_id})")
        
        # Decode base64 file data (base64 is only for Celery message serialization)
        # OCR processing receives raw file bytes directly
        file_bytes = base64.b64decode(file_data)
        
        # Update task state
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Checking for duplicates: {filename}", "step": "duplicate_check"}
        )
        
        # Step 1: Check for duplicate file before processing
        blob_service = AzureBlobService()
        if blob_service.is_available():
            existing_file = blob_service.check_file_exists_by_hash(file_bytes, tenant_id)
            if existing_file and existing_file.get("processed_data"):
                logger.info(f"⚠️ Duplicate file detected: {filename} - Returning existing processed data")
                
                # Return existing processed data
                processed_data = existing_file.get("processed_data", {})
                return {
                    "status": "completed",
                    "duplicate": True,
                    "message": "File already processed - returned existing data",
                    "processing_id": existing_file.get("processing_id"),
                    "file_info": {
                        "filename": filename,
                        "content_type": content_type,
                        "size_bytes": len(file_bytes),
                        "original_filename": existing_file.get("filename"),
                        "first_processed": existing_file.get("created_at")
                    },
                    "key_value_pairs": processed_data.get("key_value_pairs", {}),
                    "key_value_pair_confidence_scores": processed_data.get("key_value_pair_confidence_scores", {}),
                    "summary": processed_data.get("summary", ""),
                    "confidence_score": processed_data.get("confidence_score", 0.0),
                    "ocr_confidence_score": existing_file.get("ocr_confidence_score"),
                    "document_classification": processed_data.get("document_classification", "Unknown"),
                    "processing_info": processed_data.get("processing_info", {}),
                    "metadata": processed_data.get("metadata", {}),
                    "blob_storage": {
                        "source": {"blob_path": existing_file.get("source_blob_path"), "duplicate": True},
                        "processed_json": {"blob_path": existing_file.get("processed_blob_path"), "duplicate": True}
                    }
                }
        
        # Step 2: Upload to source folder (if not duplicate)
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Uploading source file: {filename}", "step": "upload_source"}
        )
        
        source_blob_info = None
        try:
            if blob_service.is_available():
                source_blob_info = blob_service.upload_source_document(
                    file_data=file_bytes,
                    filename=filename,
                    tenant_id=tenant_id,
                    processing_id=processing_id,
                    content_type=content_type
                )
                if source_blob_info.get("duplicate"):
                    logger.info(f"⚠️ Source file already exists: {filename} - Reusing existing blob")
                else:
                    logger.info(f"✓ Uploaded new source file: {filename}")
        except Exception as e:
            logger.warning(f"Azure Blob Storage error (non-critical): {e}")
            source_blob_info = {"success": False, "error": str(e), "skipped": True}
        
        # Step 3: Process with OCR (file passed directly to Document Intelligence)
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Running OCR for {filename}", "step": "ocr"}
        )
        
        # Note: ocr_from_path expects async, but Celery tasks are sync
        # We need to run it in an async context
        # File is passed directly to Document Intelligence without image preprocessing
        ocr_result = run_async_in_celery(ocr_from_path(
            file_data=file_bytes,
            original_filename=filename,
            ocr_engine="azure_computer_vision",
            ground_truth="",
            apply_preprocessing=apply_preprocessing,
            enhance_quality=enhance_quality
        ))
        
        # Step 3: AI-powered extraction
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Extracting data from {filename}", "step": "extraction"}
        )
        
        text_processor = EnhancedTextProcessor()
        processing_result = run_async_in_celery(text_processor.process_without_template(
            ocr_text=ocr_result.get("combined_text", ""),
            filename=filename
        ))
        
        # Step 4: Template mapping if template_id provided
        mapping_result = None
        if template_id:
            try:
                template_mapper = TemplateMapper()
                tenant_template = template_mapper.get_template(template_id, tenant_id)
                if tenant_template:
                    # Build fields map
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
                    template_result = run_async_in_celery(text_processor.process_with_template(
                        ocr_text=ocr_result.get("combined_text", ""),
                        template=llm_template,
                        filename=filename
                    ))
                    
                    # Map to template
                    document_id = str(uuid.uuid4())
                    mapping_result = template_mapper.map_document_to_template(
                        template_id=template_id,
                        tenant_id=tenant_id,
                        extracted_data=template_result.key_value_pairs,
                        document_id=document_id,
                        filename=filename
                    )
            except Exception as e:
                logger.error(f"Template mapping failed: {e}")
        
        # Document classification
        document_classification = text_processor.classify_document_type(
            ocr_text=ocr_result.get("combined_text", "")
        )
        
        # Calculate OCR confidence from text_blocks
        ocr_confidence_score = calculate_ocr_confidence(ocr_result)
        
        # Calculate confidence scores for each key-value pair
        kv_confidence_scores = calculate_key_value_pair_confidence_scores(
            key_value_pairs=processing_result.key_value_pairs,
            ocr_result=ocr_result,
            raw_ocr_text=ocr_result.get("combined_text", "")
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
        
        # Log low-confidence pairs count (file_data is already base64 string)
        if low_confidence_pairs:
            logger.info(f"Identified {len(low_confidence_pairs)} low-confidence pairs for {filename} - ready for manual analysis")
        
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
                        filename=filename,
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
        
        # Step 5: Upload processed JSON
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Uploading results for {filename}", "step": "upload"}
        )
        
        json_upload_result = None
        try:
            blob_service = AzureBlobService()
            if blob_service.is_available():
                processed_json_data = {
                    "file_info": {
                        "filename": filename,
                        "content_type": content_type,
                        "size_bytes": len(file_bytes),
                        "pages_processed": len(ocr_result.get("raw_ocr_results", []))
                    },
                    "key_value_pairs": processing_result.key_value_pairs,
                    "key_value_pair_confidence_scores": kv_confidence_scores,
                    "summary": processing_result.summary,
                    "confidence_score": processing_result.confidence_score,
                    "ocr_confidence_score": ocr_confidence_score,
                    "document_classification": document_classification,
                    "processing_info": {
                        "processing_time": ocr_result.get("processing_time", 0),
                        "preprocessing_applied": apply_preprocessing,
                        "quality_enhanced": enhance_quality,
                        "extraction_method": "AI-powered" if text_processor.is_available() else "Basic pattern matching"
                    },
                    "raw_ocr_text": ocr_result.get("combined_text", "") if include_raw_text else None,
                    "raw_ocr_results": ocr_result.get("raw_ocr_results", []),
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "text_length": len(ocr_result.get("combined_text", "")),
                        "ai_processing": text_processor.is_available()
                    } if include_metadata else None,
                    "low_confidence_data": {
                        "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                        "low_confidence_pairs": low_confidence_pairs,
                        "low_confidence_scores": low_confidence_scores_filtered,
                        "source_file_base64": file_data,  # file_data is already base64 string
                        "source_file_content_type": content_type,
                        "count": len(low_confidence_pairs)
                    } if low_confidence_pairs else None
                }
                
                json_upload_result = blob_service.upload_processed_json(
                    json_data=processed_json_data,
                    filename=filename,
                    tenant_id=tenant_id,
                    processing_id=processing_id
                )
                
                # Store null field tracking data in separate table
                try:
                    logger.info(f"Storing null field tracking for {filename}...")
                    null_field_service.store_null_fields(
                        processing_id=processing_id,
                        tenant_id=tenant_id,
                        filename=filename,
                        extracted_fields=processing_result.key_value_pairs
                    )
                except Exception as null_error:
                    logger.error(f"✗ Failed to store null field tracking: {null_error}")

        except Exception as e:
            logger.error(f"Failed to upload JSON: {e}")
            json_upload_result = {"success": False, "error": str(e)}
        
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
        
        # Calculate total processing time (OCR + extraction)
        ocr_time = ocr_result.get("processing_time_seconds", 0) or ocr_result.get("processing_time", 0)
        extraction_time = processing_result.processing_time if hasattr(processing_result, 'processing_time') else 0
        total_processing_time = ocr_time + extraction_time
        
        # Prepare result
        result = {
            "status": "completed",
            "processing_id": processing_id,
            "file_info": {
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(file_bytes),
                "pages_processed": len(ocr_result.get("raw_ocr_results", []))
            },
            "key_value_pairs": processing_result.key_value_pairs,
            "key_value_pair_confidence_scores": kv_confidence_scores,
            "summary": processing_result.summary,
            "confidence_score": processing_result.confidence_score,
            "ocr_confidence_score": ocr_confidence_score,
            "document_classification": document_classification,
            "processing_time": total_processing_time,  # Add total processing time at top level
            "processing_info": {
                "processing_time": total_processing_time,  # Total time
                "ocr_time": ocr_time,  # OCR time separately
                "extraction_time": extraction_time,  # Extraction time separately
                "preprocessing_applied": apply_preprocessing,
                "quality_enhanced": enhance_quality,
                "extraction_method": extraction_method,
                "is_fallback": is_fallback
            },
            "raw_ocr_text": ocr_result.get("combined_text", "") if include_raw_text else None,
            "raw_ocr_results": ocr_result.get("raw_ocr_results", []),
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "text_length": len(ocr_result.get("combined_text", "")),
                "ai_processing": text_processor.is_available(),
                "extraction_error": extraction_error if is_fallback else None
            } if include_metadata else None,
            "blob_storage": {
                "processed_json": json_upload_result,
                "source": source_blob_info
            },
            "low_confidence_data": {
                "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                "low_confidence_pairs": low_confidence_pairs,
                "low_confidence_scores": low_confidence_scores_filtered,
                "source_file_base64": file_data,  # file_data is already base64 string
                "source_file_content_type": content_type,
                "count": len(low_confidence_pairs)
            } if low_confidence_pairs else None
        }
        
        # Add template mapping results if available
        if mapping_result:
            result["template_info"] = {
                "template_id": template_id,
                "mapping_result": {
                    "document_id": mapping_result.document_id,
                    "mapped_values": mapping_result.mapped_values,
                    "confidence_scores": mapping_result.confidence_scores,
                    "unmapped_fields": mapping_result.unmapped_fields,
                    "processing_timestamp": mapping_result.processing_timestamp
                }
            }
        
        logger.info(f"Document processing completed: {filename}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing document {filename}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "filename": filename}
        )
        raise


@celery_app.task(bind=True, name="process_batch_documents", queue="processing")
def process_batch_documents(
    self,
    files_data: List[str],  # List of base64 encoded file data (for Celery serialization only)
    filenames: List[str],
    tenant_id: str,
    apply_preprocessing: bool = True,
    enhance_quality: bool = True,
    include_raw_text: bool = True,
    include_metadata: bool = True,
    content_types: List[str] = None
) -> Dict[str, Any]:
    """
    Process multiple documents in parallel using Celery workers.
    Files are passed directly to Document Intelligence without image preprocessing.
    
    Args:
        self: Task instance
        files_data: List of base64 encoded document bytes (for Celery serialization only)
        filenames: List of filenames
        tenant_id: Tenant identifier
        apply_preprocessing: Ignored - kept for API compatibility
        enhance_quality: Ignored - kept for API compatibility
        include_raw_text: Include raw OCR text
        include_metadata: Include processing metadata
        content_types: List of MIME types
        
    Returns:
        Dict with batch processing results
    """
    try:
        logger.info(f"Processing batch of {len(files_data)} documents")
        
        # Decode all files (base64 is only for Celery message serialization)
        files_bytes = [base64.b64decode(f) for f in files_data]
        
        total_files = len(files_data)
        task_results = []
        task_ids = []
        
        # Step 1: Submit all tasks to queue without waiting (PARALLEL)
        logger.info(f"Submitting {total_files} tasks to Celery workers for parallel processing...")
        
        for idx, (file_bytes, filename) in enumerate(zip(files_bytes, filenames)):
            try:
                # Generate processing ID for this file
                processing_id = str(uuid.uuid4())
                content_type = (content_types[idx] if content_types and idx < len(content_types) 
                              else "application/octet-stream")
                
                # Encode file as base64 for Celery message serialization only
                # OCR processing receives raw bytes after decoding
                file_data_b64 = base64.b64encode(file_bytes).decode('utf-8')
                
                # Submit task to queue (this returns immediately, doesn't wait)
                async_result = process_document.delay(
                    file_data=file_data_b64,
                    filename=filename,
                    tenant_id=tenant_id,
                    processing_id=processing_id,
                    apply_preprocessing=apply_preprocessing,
                    enhance_quality=enhance_quality,
                    include_raw_text=include_raw_text,
                    include_metadata=include_metadata,
                    content_type=content_type
                )
                
                task_results.append(async_result)
                task_ids.append(async_result.id)
                logger.info(f"Submitted task {idx + 1}/{total_files}: {filename} (Task ID: {async_result.id})")
                
            except Exception as e:
                logger.error(f"Error submitting task for {filename}: {e}")
        
        # Step 2: Update progress - tasks are now running in parallel
        self.update_state(
            state="PROCESSING",
            meta={
                "message": f"Processing {total_files} files in parallel...",
                "current": 0,
                "total": total_files,
                "progress": 0,
                "task_ids": task_ids,
                "parallel_processing": True
            }
        )
        
        # Step 3: Wait for all tasks to complete (they run in parallel)
        logger.info(f"Waiting for {len(task_results)} tasks to complete in parallel...")
        individual_results = []
        total_processing_time = 0
        completed = 0
        
        for idx, result in enumerate(task_results):
            try:
                # Get the result (this will wait for this specific task)
                task_result = result.get(timeout=300)  # 5 minute timeout per task
                
                individual_results.append(task_result)
                total_processing_time += task_result.get("processing_info", {}).get("processing_time", 0)
                completed += 1
                
                # Update progress
                self.update_state(
                    state="PROCESSING",
                    meta={
                        "message": f"Completed {completed}/{total_files} files",
                        "current": completed,
                        "total": total_files,
                        "progress": int((completed / total_files) * 100),
                        "last_completed": filenames[idx]
                    }
                )
                
            except Exception as e:
                logger.error(f"Error getting result for task: {e}")
                individual_results.append({
                    "file_info": {
                        "filename": filenames[idx],
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
        
        batch_result = {
            "status": "completed",
            "message": f"Batch processing completed for {len(individual_results)} files",
            "batch_info": {
                "total_files": total_files,
                "processed_files": len(individual_results),
                "total_processing_time": total_processing_time,
                "fallback_count": fallback_count,
                "successful_ai_extraction": len(individual_results) - fallback_count
            },
            "individual_results": individual_results
        }
        
        if fallback_count > 0:
            logger.warning(f"Batch processing completed with {fallback_count} files in fallback mode (AI extraction failed)")
        else:
            logger.info(f"Batch processing completed: {len(individual_results)} files")
        return batch_result
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="process_bulk_file", queue="processing")
def process_bulk_file(
    self,
    blob_name: str,
    filename: str
) -> Dict[str, Any]:
    """
    Process a single file from bulk processing/source folder.
    
    Args:
        self: Task instance
        blob_name: Full blob path (e.g., "bulk processing/source/file.pdf")
        filename: Original filename
        
    Returns:
        Dict with processing results
    """
    try:
        logger.info(f"[BULK] Processing bulk file: {filename} from {blob_name}")
        
        # Update task state
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Downloading {filename}", "step": "download"}
        )
        
        # Step 1: Download file from blob storage
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            raise ValueError("Azure Blob Storage not available")
        
        file_bytes = blob_service.download_bulk_file(blob_name)
        if not file_bytes:
            raise ValueError(f"Failed to download file: {blob_name}")
        
        logger.info(f"[BULK] Downloaded {filename} ({len(file_bytes)} bytes)")
        
        # Determine content type from filename
        content_type = "application/octet-stream"
        if filename.lower().endswith('.pdf'):
            content_type = "application/pdf"
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_type = f"image/{filename.rsplit('.', 1)[-1].lower()}"
        
        # Step 2: Process with OCR
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Running OCR for {filename}", "step": "ocr"}
        )
        
        ocr_result = run_async_in_celery(ocr_from_path(
            file_data=file_bytes,
            original_filename=filename,
            ocr_engine="azure_computer_vision",
            ground_truth="",
            apply_preprocessing=True,
            enhance_quality=True
        ))
        
        # Step 3: AI-powered extraction
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Extracting data from {filename}", "step": "extraction"}
        )
        
        text_processor = EnhancedTextProcessor()
        processing_result = run_async_in_celery(text_processor.process_without_template(
            ocr_text=ocr_result.get("combined_text", ""),
            filename=filename
        ))
        
        # Document classification
        document_classification = text_processor.classify_document_type(
            ocr_text=ocr_result.get("combined_text", "")
        )
        
        # Calculate OCR confidence from text_blocks
        ocr_confidence_score = calculate_ocr_confidence(ocr_result)
        
        # Calculate confidence scores for each key-value pair
        kv_confidence_scores = calculate_key_value_pair_confidence_scores(
            key_value_pairs=processing_result.key_value_pairs,
            ocr_result=ocr_result,
            raw_ocr_text=ocr_result.get("combined_text", "")
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
        file_base64 = base64.b64encode(file_bytes).decode('utf-8')
        
        # Log low-confidence pairs count
        if low_confidence_pairs:
            logger.info(f"[BULK] Identified {len(low_confidence_pairs)} low-confidence pairs for {filename} - ready for manual analysis")
        
        # Step 4: Upload processed JSON to appropriate folder based on confidence
        self.update_state(
            state="PROCESSING",
            meta={"message": f"Uploading results for {filename}", "step": "upload"}
        )
        
        processed_json_data = {
            "file_info": {
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(file_bytes),
                "pages_processed": len(ocr_result.get("raw_ocr_results", []))
            },
            "key_value_pairs": processing_result.key_value_pairs,
            "key_value_pair_confidence_scores": kv_confidence_scores,
            "summary": processing_result.summary,
            "confidence_score": processing_result.confidence_score,
            "ocr_confidence_score": ocr_confidence_score,
            "document_classification": document_classification,
            "processing_info": {
                "processing_time": ocr_result.get("processing_time", 0),
                "preprocessing_applied": True,
                "quality_enhanced": True,
                "extraction_method": "AI-powered" if text_processor.is_available() else "Basic pattern matching"
            },
            "raw_ocr_text": ocr_result.get("combined_text", ""),
            "raw_ocr_results": ocr_result.get("raw_ocr_results", []),
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "text_length": len(ocr_result.get("combined_text", "")),
                "ai_processing": text_processor.is_available(),
                "source_blob": blob_name
            },
            "low_confidence_data": {
                "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                "low_confidence_pairs": low_confidence_pairs,
                "low_confidence_scores": low_confidence_scores_filtered,
                "source_file_base64": file_base64,
                "source_file_content_type": content_type,
                "count": len(low_confidence_pairs)
            } if low_confidence_pairs else None
        }
        
        # Extract tenant_id from blob_name if available, otherwise use default
        # For bulk uploads, tenant_id might be in the path or we use default
        tenant_id = "tenant_2"  # Default tenant_id for bulk uploads
        # Try to extract from blob_name if it contains tenant info
        if "/" in blob_name:
            path_parts = blob_name.split("/")
            # Check if any part looks like tenant_id (starts with "tenant_")
            for part in path_parts:
                if part.startswith("tenant_"):
                    tenant_id = part
                    break
        
        json_upload_result = blob_service.upload_bulk_processed_json(
            json_data=processed_json_data,
            filename=filename,
            confidence_score=ocr_confidence_score,
            tenant_id=tenant_id
        )
        
        if not json_upload_result.get("success"):
            logger.error(f"[BULK] Failed to upload processed JSON for {filename}: {json_upload_result.get('error')}")
        
        # Store null field tracking data
        try:
            logger.info(f"[BULK] Storing null field tracking for {filename}...")
            # Generate a processing_id for bulk files
            processing_id = f"bulk_{blob_name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            null_field_service.store_null_fields(
                processing_id=processing_id,
                tenant_id=tenant_id,
                filename=filename,
                extracted_fields=processing_result.key_value_pairs
            )
        except Exception as null_error:
            logger.error(f"[BULK] ✗ Failed to store null field tracking: {null_error}")

        result = {
            "status": "completed",
            "filename": filename,
            "blob_name": blob_name,
            "file_info": {
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(file_bytes),
                "pages_processed": len(ocr_result.get("raw_ocr_results", []))
            },
            "key_value_pairs": processing_result.key_value_pairs,
            "key_value_pair_confidence_scores": kv_confidence_scores,
            "summary": processing_result.summary,
            "confidence_score": processing_result.confidence_score,
            "ocr_confidence_score": ocr_confidence_score,
            "document_classification": document_classification,
            "processing_time": ocr_result.get("processing_time", 0),
            "raw_ocr_text": ocr_result.get("combined_text", ""),
            "raw_ocr_results": ocr_result.get("raw_ocr_results", []),
            "blob_storage": {
                "processed_json": json_upload_result
            },
            "low_confidence_data": {
                "has_low_confidence_pairs": len(low_confidence_pairs) > 0,
                "low_confidence_pairs": low_confidence_pairs,
                "low_confidence_scores": low_confidence_scores_filtered,
                "source_file_base64": file_base64,
                "source_file_content_type": content_type,
                "count": len(low_confidence_pairs)
            } if low_confidence_pairs else None
        }
        
        logger.info(f"[BULK] Successfully processed bulk file: {filename} (confidence: {ocr_confidence_score})")
        return result
        
    except Exception as e:
        logger.error(f"[BULK] Error processing bulk file {filename}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "filename": filename}
        )
        raise


@celery_app.task(bind=True, name="check_bulk_processing_source", queue="processing")
def check_bulk_processing_source(self) -> Dict[str, Any]:
    """
    Periodic task to check bulk processing/source folder for new files and process them.
    This task runs every 5 minutes via Celery Beat.
    
    Returns:
        Dict with processing summary
    """
    try:
        logger.info("[BULK] Checking bulk processing/source folder for new files...")
        
        blob_service = AzureBlobService()
        if not blob_service.is_available():
            logger.warning("[BULK] Azure Blob Storage not available, skipping bulk processing check")
            return {
                "status": "skipped",
                "reason": "Azure Blob Storage not available",
                "files_processed": 0
            }
        
        # List all files in bulk processing/source
        source_files = blob_service.list_bulk_source_files()
        
        if not source_files:
            logger.info("[BULK] No files found in bulk processing/source folder")
            return {
                "status": "completed",
                "files_found": 0,
                "files_processed": 0,
                "files_skipped": 0
            }
        
        logger.info(f"[BULK] Found {len(source_files)} file(s) in bulk processing/source folder")
        
        # Filter out already processed files
        new_files = []
        skipped_files = []
        
        for file_info in source_files:
            blob_name = file_info["blob_name"]
            filename = file_info["name"]
            
            if blob_service.check_file_processed(blob_name):
                logger.info(f"[BULK] Skipping {filename} - already processed")
                skipped_files.append(filename)
            else:
                logger.info(f"[BULK] New file found: {filename}")
                new_files.append(file_info)
        
        if not new_files:
            logger.info(f"[BULK] All {len(source_files)} file(s) have already been processed")
            return {
                "status": "completed",
                "files_found": len(source_files),
                "files_processed": 0,
                "files_skipped": len(skipped_files),
                "skipped_files": skipped_files
            }
        
        # Process new files
        logger.info(f"[BULK] Processing {len(new_files)} new file(s)...")
        processed_results = []
        failed_files = []
        
        for file_info in new_files:
            blob_name = file_info["blob_name"]
            filename = file_info["name"]
            
            try:
                # Submit processing task
                task_result = process_bulk_file.delay(blob_name=blob_name, filename=filename)
                logger.info(f"[BULK] Submitted processing task for {filename} (Task ID: {task_result.id})")
                processed_results.append({
                    "filename": filename,
                    "task_id": task_result.id,
                    "status": "submitted"
                })
            except Exception as e:
                logger.error(f"[BULK] Failed to submit processing task for {filename}: {e}")
                failed_files.append({
                    "filename": filename,
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "files_found": len(source_files),
            "files_processed": len(processed_results),
            "files_skipped": len(skipped_files),
            "files_failed": len(failed_files),
            "processed_files": processed_results,
            "skipped_files": skipped_files,
            "failed_files": failed_files
        }
        
    except Exception as e:
        logger.error(f"[BULK] Error checking bulk processing source: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        return {
            "status": "failed",
            "error": str(e),
            "files_processed": 0
        }

