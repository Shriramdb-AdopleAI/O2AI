import asyncio
import logging
import time
from typing import Dict, Any, List

from utility.config import Config, setup_logging
from core.ocr_engines import OCREngineFactory
from utility.file_processor import FileProcessor, FileSizeValidator
from core.enhanced_text_processor import EnhancedTextProcessor

class MetricsCollector:
    def __init__(self):
        self.engine = None
        self.processing_time = 0
        self.pages_processed = 0
        self.total_characters = 0
        self.total_tokens = 0
        self.successful_pages = 0
        self.failed_pages = 0
        
    def set_engine(self, engine):
        self.engine = engine
        
    def add_page_result(self, success, char_count=0, token_count=0, text="", ground_truth=""):
        if success:
            self.successful_pages += 1
            self.total_characters += char_count
            self.total_tokens += token_count
        else:
            self.failed_pages += 1
        self.pages_processed += 1
        
    def set_processing_time(self, time):
        self.processing_time = time
        
    def get_summary(self):
        return {
            "engine": self.engine,
            "processing_time_seconds": self.processing_time,
            "pages_processed": self.pages_processed,
            "successful_pages": self.successful_pages,
            "failed_pages": self.failed_pages,
            "total_characters": self.total_characters,
            "total_tokens": self.total_tokens,
            "success_rate": (self.successful_pages / self.pages_processed * 100) if self.pages_processed > 0 else 0
        }

# Setup logging
logger = setup_logging()

async def ocr_from_path(
    file_data: bytes,
    original_filename: str = "",
    ocr_engine: str = "azure_computer_vision",
    ground_truth: str = "",
    apply_preprocessing: bool = True,
    enhance_quality: bool = True
) -> Dict[str, Any]:
    """
    Main OCR processing function that handles the complete workflow.
    Files are passed directly to Document Intelligence without image preprocessing.
    
    Args:
        file_data: Raw file bytes (PDF or image)
        original_filename: Original filename for format detection
        ocr_engine: OCR engine to use ('azure_computer_vision' or 'azure_document_intelligence')
        ground_truth: Optional ground truth text for accuracy evaluation
        apply_preprocessing: Ignored - kept for API compatibility
        enhance_quality: Ignored - kept for API compatibility
        
    Returns:
        Dictionary containing OCR results, structured data, and metrics
    """
    start_time = time.time()
    metrics = MetricsCollector()
    metrics.set_engine(ocr_engine)
    
    logger.info(f"Starting OCR processing with {ocr_engine} engine for {original_filename or 'unknown file'}")
    logger.info("Skipping image preprocessing - passing file directly to Document Intelligence")
    
    try:
        # Validate file size
        if not FileSizeValidator.validate_file_size(file_data, original_filename):
            file_size = FileSizeValidator.get_file_size_mb(file_data)
            raise ValueError(f"File size {file_size:.2f}MB exceeds maximum allowed size of {Config.MAX_FILE_SIZE_MB}MB")
        
        # Create OCR engine
        ocr_engine_instance = OCREngineFactory.create_engine(ocr_engine)
        if not ocr_engine_instance.is_available():
            missing_vars = Config.get_missing_env_vars(ocr_engine)
            raise ValueError(f"OCR engine {ocr_engine} not available. Missing: {missing_vars}")
        
        # Process file directly with OCR (no image preprocessing)
        logger.info(f"Processing file directly with Document Intelligence: {original_filename}")
        ocr_result = await ocr_engine_instance.extract_text(file_data, original_filename)
        
        # Handle both string and dict results for backward compatibility
        if isinstance(ocr_result, dict):
            ocr_text = ocr_result.get('raw_text', '')
            text_blocks = ocr_result.get('text_blocks', [])
            total_pages = len(text_blocks)
        else:
            ocr_text = ocr_result
            text_blocks = []
            total_pages = 1
        
        # Format results for backward compatibility
        all_ocr_results = []
        if text_blocks:
            # If we have page-level blocks, format them
            for i, block in enumerate(text_blocks):
                page_num = block.get('page_number', i + 1)
                page_text = block.get('text', '')
                all_ocr_results.append({
                    'page': page_num,
                    'description': f"{original_filename or 'document'} - Page {page_num}",
                    'text': page_text,
                    'character_count': len(page_text),
                    'text_blocks': [block],
                    'positioning_data': block
                })
                
                # Update metrics
                try:
                    text_processor = EnhancedTextProcessor()
                    token_count = text_processor.count_tokens(page_text) if hasattr(text_processor, 'count_tokens') else len(page_text.split())
                except:
                    token_count = len(page_text.split())  # Fallback to word count
                metrics.add_page_result(True, len(page_text), token_count, page_text, ground_truth)
        else:
            # Single result
            all_ocr_results.append({
                'page': 1,
                'description': original_filename or 'document',
                'text': ocr_text,
                'character_count': len(ocr_text),
                'text_blocks': text_blocks,
                'positioning_data': ocr_result if isinstance(ocr_result, dict) else None
            })
            metrics.add_page_result(True, len(ocr_text), len(ocr_text.split()), ocr_text, ground_truth)
        
        # Combine all OCR text
        combined_text = ocr_text  # Document Intelligence already provides combined text
        
        # Extract key-value pairs and summary using Azure GPT
        # COMMENTED OUT: Key-value pair generator disabled
        # logger.info("Starting key-value extraction and summarization")
        # text_processor = TextProcessor()
        
        # structured_data = {}
        # if text_processor.is_available() and combined_text.strip():
        #     try:
        #         structured_data = await text_processor.extract_key_values_and_summary(combined_text)
        #         logger.info("Key-value extraction completed successfully")
        #     except Exception as e:
        #         logger.error(f"Key-value extraction failed: {e}")
        #         structured_data = {
        #             'key_value_pairs': {'processing_error': str(e)},
        #             'summary': f"Failed to process extracted text: {str(e)}"
        #         }
        # else:
        #     logger.warning("Text processor not available or no text extracted")
        #     structured_data = {
        #         'key_value_pairs': {},
        #         'summary': "No text available for processing"
        #     }
        
        # Simplified structured data without key-value extraction
        structured_data = {
            'key_value_pairs': {},
            'summary': f"OCR completed successfully. Extracted {len(combined_text)} characters from {len(all_ocr_results)} pages."
        }
        
        # Calculate final metrics
        processing_time = time.time() - start_time
        metrics.set_processing_time(processing_time)
        
        # Prepare final result
        result = {
            'success': True,
            'ocr_engine': ocr_engine,
            'raw_ocr_results': all_ocr_results,
            'combined_text': combined_text,
            'structured_data': structured_data,
            'metrics': metrics.get_summary(),
            'processing_time_seconds': round(processing_time, 2)
        }
        
        logger.info(f"OCR processing completed successfully in {processing_time:.2f} seconds")
        return result
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"OCR processing failed after {processing_time:.2f} seconds: {e}")
        
        return {
            'success': False,
            'error': "OCR processing failed",
            'ocr_engine': ocr_engine,
            'processing_time_seconds': round(processing_time, 2),
            'metrics': metrics.get_summary() if 'metrics' in locals() else {}
        }


# Legacy compatibility functions
async def ocr_with_mistral(image_data: bytes, filename: str = "") -> str:
    """
    Legacy function for backward compatibility.
    Use ocr_from_path with mistral_ocr engine instead.
    """
    logger.warning("ocr_with_mistral is deprecated. Use ocr_from_path with 'mistral_ocr' engine")
    
    engine = OCREngineFactory.create_engine("mistral_ocr")
    if not engine.is_available():
        raise ValueError("Mistral OCR engine not available")
    
    return await engine.extract_text(image_data, filename)


async def ocr_with_azure_gpt_vision(image_data: bytes, filename: str = "") -> str:
    """
    Legacy function for backward compatibility.
    Use ocr_from_path with azure_gpt_vision engine instead.
    """
    logger.warning("ocr_with_azure_gpt_vision is deprecated. Use ocr_from_path with 'azure_gpt_vision' engine")
    
    engine = OCREngineFactory.create_engine("azure_gpt_vision")
    if not engine.is_available():
        raise ValueError("Azure GPT Vision OCR engine not available")
    
    return await engine.extract_text(image_data, filename)


def convert_document_to_images(file_data: bytes, original_filename: str = "") -> List[bytes]:
    """
    Legacy function for backward compatibility.
    Use FileProcessor.process_file instead.
    """
    logger.warning("convert_document_to_images is deprecated. Use FileProcessor.process_file")
    
    image_pages = FileProcessor.process_file(file_data, original_filename)
    return [img_data for img_data, _ in image_pages]


async def extract_kv_and_summary_chunked(ocr_text: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Use EnhancedTextProcessor instead.
    """
    logger.warning("extract_kv_and_summary_chunked is deprecated. Use EnhancedTextProcessor")
    
    try:
        text_processor = EnhancedTextProcessor()
        if hasattr(text_processor, 'process_without_template'):
            result = await text_processor.process_without_template(ocr_text, "legacy")
            return {
                'key_value_pairs': result.get('key_value_pairs', {}),
                'summary': result.get('summary', ''),
                'confidence_score': result.get('confidence_score', 0.0)
            }
        else:
            raise ValueError("EnhancedTextProcessor not available")
    except Exception as e:
        logger.error(f"EnhancedTextProcessor processing failed: {e}")
        return {
            'key_value_pairs': {},
            'summary': f"Processing failed: {str(e)}",
            'confidence_score': 0.0
        }


def get_available_engines() -> List[str]:
    """Get list of available OCR engines based on configuration."""
    return OCREngineFactory.get_available_engines()


def calculate_ocr_confidence(ocr_result: Dict[str, Any]) -> float:
    """
    Calculate average OCR confidence from Document Intelligence text_blocks.
    Aggregates confidence scores from lines and words in text_blocks.
    The structure is: raw_ocr_results -> each page -> text_blocks -> lines/words -> confidence
    """
    try:
        all_confidences = []
        raw_ocr_results = ocr_result.get('raw_ocr_results', [])
        
        if not raw_ocr_results:
            logger.debug("No raw_ocr_results found in OCR result, trying alternative structure")
            # Try to get text_blocks directly from ocr_result (from ocr_engine)
            text_blocks = ocr_result.get('text_blocks', [])
            if text_blocks:
                raw_ocr_results = [{'text_blocks': text_blocks}]
        
        if not raw_ocr_results:
            logger.debug("No OCR results found for confidence calculation")
            return 0.0
        
        # Process each page result in raw_ocr_results
        for page_result in raw_ocr_results:
            if not isinstance(page_result, dict):
                continue
                
            # Get text_blocks from the page result
            # Structure: page_result -> text_blocks -> [block] -> lines/words -> confidence
            text_blocks = page_result.get('text_blocks', [])
            
            # Also try positioning_data which contains the same structure
            if not text_blocks:
                positioning_data = page_result.get('positioning_data')
                if isinstance(positioning_data, dict):
                    text_blocks = positioning_data.get('text_blocks', [])
                elif isinstance(positioning_data, list):
                    text_blocks = positioning_data
            
            # Process each text block (page-level block)
            for block in text_blocks:
                if not isinstance(block, dict):
                    continue
                    
                # Get confidence from lines (Document Intelligence provides confidence per line)
                lines = block.get('lines', [])
                for line in lines:
                    if isinstance(line, dict):
                        conf = line.get('confidence')
                        if conf is not None and isinstance(conf, (int, float)):
                            # Document Intelligence confidence is typically 0.0-1.0
                            all_confidences.append(float(conf))
                
                # Get confidence from words (Document Intelligence provides confidence per word)
                words = block.get('words', [])
                for word in words:
                    if isinstance(word, dict):
                        conf = word.get('confidence')
                        if conf is not None and isinstance(conf, (int, float)):
                            # Document Intelligence confidence is typically 0.0-1.0
                            all_confidences.append(float(conf))
        
        # Calculate average confidence
        if all_confidences:
            avg_confidence = sum(all_confidences) / len(all_confidences)
            # Ensure it's between 0 and 1
            avg_confidence = max(0.0, min(1.0, avg_confidence))
            logger.debug(f"Calculated OCR confidence: {avg_confidence} from {len(all_confidences)} confidence scores")
            return round(avg_confidence, 4)
        else:
            logger.debug(f"No confidence scores found in OCR result. Checked {len(raw_ocr_results)} page results")
            return 0.0
            
    except Exception as e:
        logger.warning(f"Error calculating OCR confidence: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return 0.0


def calculate_key_value_pair_confidence_scores(
    key_value_pairs: Dict[str, Any],
    ocr_result: Dict[str, Any],
    raw_ocr_text: str = ""
) -> Dict[str, float]:
    """
    Calculate confidence scores for each key-value pair based on OCR confidence.
    For each value, find the corresponding text in OCR results and calculate average confidence.
    
    Args:
        key_value_pairs: Dictionary of extracted key-value pairs
        ocr_result: OCR result containing raw_ocr_results with confidence scores
        raw_ocr_text: Raw OCR text for fallback matching
        
    Returns:
        Dictionary mapping each key to its confidence score (0.0-1.0)
    """
    confidence_scores = {}
    
    try:
        # Get OCR confidence data
        all_confidences_by_text = {}
        raw_ocr_results = ocr_result.get('raw_ocr_results', [])
        
        if not raw_ocr_results:
            text_blocks = ocr_result.get('text_blocks', [])
            if text_blocks:
                raw_ocr_results = [{'text_blocks': text_blocks}]
        
        # Build a map of text to confidence scores
        for page_result in raw_ocr_results:
            if not isinstance(page_result, dict):
                continue
                
            text_blocks = page_result.get('text_blocks', [])
            if not text_blocks:
                positioning_data = page_result.get('positioning_data')
                if isinstance(positioning_data, dict):
                    text_blocks = positioning_data.get('text_blocks', [])
                elif isinstance(positioning_data, list):
                    text_blocks = positioning_data
            
            for block in text_blocks:
                if not isinstance(block, dict):
                    continue
                
                # Process lines
                lines = block.get('lines', [])
                for line in lines:
                    if isinstance(line, dict):
                        line_text = line.get('text', '').strip().lower()
                        conf = line.get('confidence')
                        if line_text and conf is not None and isinstance(conf, (int, float)):
                            if line_text not in all_confidences_by_text:
                                all_confidences_by_text[line_text] = []
                            all_confidences_by_text[line_text].append(float(conf))
                
                # Process words
                words = block.get('words', [])
                for word in words:
                    if isinstance(word, dict):
                        word_text = word.get('text', '').strip().lower()
                        conf = word.get('confidence')
                        if word_text and conf is not None and isinstance(conf, (int, float)):
                            if word_text not in all_confidences_by_text:
                                all_confidences_by_text[word_text] = []
                            all_confidences_by_text[word_text].append(float(conf))
        
        # Calculate confidence for each key-value pair
        for key, value in key_value_pairs.items():
            # Skip internal keys
            if key.startswith('_'):
                confidence_scores[key] = 0.5  # Default for internal keys
                continue
            
            value_str = str(value).strip().lower()
            if not value_str:
                confidence_scores[key] = 0.0
                continue
            
            # Try to find matching text in OCR confidence data
            matching_confidences = []
            
            # Direct match
            if value_str in all_confidences_by_text:
                matching_confidences.extend(all_confidences_by_text[value_str])
            
            # Partial match - check if value appears in any OCR text
            for ocr_text, confidences in all_confidences_by_text.items():
                if value_str in ocr_text or ocr_text in value_str:
                    matching_confidences.extend(confidences)
            
            # Word-level matching for multi-word values
            if not matching_confidences and len(value_str.split()) > 1:
                value_words = value_str.split()
                for word in value_words:
                    if word in all_confidences_by_text:
                        matching_confidences.extend(all_confidences_by_text[word])
            
            # Calculate average confidence
            if matching_confidences:
                avg_confidence = sum(matching_confidences) / len(matching_confidences)
                confidence_scores[key] = max(0.0, min(1.0, avg_confidence))
            else:
                # Fallback: use overall OCR confidence if available
                overall_confidence = calculate_ocr_confidence(ocr_result)
                if overall_confidence > 0:
                    confidence_scores[key] = overall_confidence * 0.8  # Slightly lower for unmatched
                else:
                    confidence_scores[key] = 0.5  # Default confidence
        
        logger.debug(f"Calculated confidence scores for {len(confidence_scores)} key-value pairs")
        return confidence_scores
        
    except Exception as e:
        logger.warning(f"Error calculating key-value pair confidence scores: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        # Return default confidence scores
        return {key: 0.5 for key in key_value_pairs.keys()}


# def validate_configuration(engine: str = None) -> Dict[str, Any]:
#     """
#     Validate configuration for specified engine or all engines.
    
#     Args:
#         engine: Specific engine to validate, or None for all
        
#     Returns:
#         Dictionary with validation results
#     """
#     result = {
#         'valid': True,
#         'engines': {},
#         'missing_variables': []
#     }
    
#     engines_to_check = [engine] if engine else Config.SUPPORTED_ENGINES
    
#     for engine_name in engines_to_check:
#         missing_vars = Config.get_missing_env_vars(engine_name)
        
#         result['engines'][engine_name] = {
#             'available': len(missing_vars) == 0,
#             'missing_variables': missing_vars
#         }
        
#         if missing_vars:
#             result['valid'] = False
#             result['missing_variables'].extend(missing_vars)
    
#     # Remove duplicates
#     result['missing_variables'] = list(set(result['missing_variables']))
    
#     return result


# Legacy compatibility - compute metrics function
def compute_metrics(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Return a small set of metrics derived from OCR metadata."""
    return {
        "engine": metadata.get("engine"),
        "duration_seconds": metadata.get("duration_seconds"),
        "pages": metadata.get("pages"),
        "avg_confidence": metadata.get("avg_confidence"),
        "bytes": metadata.get("bytes"),
    }
