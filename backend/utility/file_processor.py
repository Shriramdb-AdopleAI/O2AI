import os
import logging
import fitz  
from typing import List, Tuple, Optional
from io import BytesIO
from PIL import Image

from utility.config import Config

# Import preprocessing with fallback options
try:
    from core.image_preprocessor import ImagePreprocessor
    ADVANCED_PREPROCESSING_AVAILABLE = True
    logging.info("Advanced image preprocessing (OpenCV/SciPy) available")
except ImportError as e:
    logging.warning(f"Advanced preprocessing not available: {e}")
    ImagePreprocessor = None
    ADVANCED_PREPROCESSING_AVAILABLE = False

# Lightweight preprocessor disabled for now to avoid dependency conflicts
BASIC_PREPROCESSING_AVAILABLE = False
LightweightImagePreprocessor = None

PREPROCESSING_AVAILABLE = ADVANCED_PREPROCESSING_AVAILABLE

logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles file format detection and conversion."""
    
    @staticmethod
    def is_supported_file(filename: str) -> bool:
        """Check if file extension is supported."""
        if not filename:
            return False
        
        ext = os.path.splitext(filename.lower())[1]
        supported = ext in Config.SUPPORTED_EXTENSIONS
        
        if supported:
            logger.debug(f"File {filename} has supported extension: {ext}")
        else:
            logger.warning(f"File {filename} has unsupported extension: {ext}")
        
        return supported
    
    @staticmethod
    def get_file_type(file_data: bytes, original_filename: str = "") -> str:
        """Determine file type from data and filename."""
        logger.debug(f"Determining file type for {original_filename or 'unknown file'}")
        
        # Check by file extension first if available
        if original_filename:
            ext = os.path.splitext(original_filename.lower())[1]
            if ext in ['.png', '.jpg', '.jpeg', '.tif', '.tiff']:
                logger.debug(f"File type determined by extension: {ext}")
                return 'image'
            elif ext == '.pdf':
                logger.debug("File type determined by extension: pdf")
                return 'pdf'
        
        # Check by file content (magic bytes)
        if file_data[:4] == b'%PDF':
            logger.debug("File type determined by content: pdf")
            return 'pdf'
        elif file_data[:8] == b'\x89PNG\r\n\x1a\n':
            logger.debug("File type determined by content: png")
            return 'image'
        elif file_data[:2] in [b'\xff\xd8', b'\xff\xe0', b'\xff\xe1']:
            logger.debug("File type determined by content: jpeg")
            return 'image'
        elif file_data[:2] in [b'II*\x00', b'MM\x00*']:
            logger.debug("File type determined by content: tiff")
            return 'image'
        
        # Default fallback
        logger.warning("Could not determine file type, defaulting to image")
        return 'image'
    
    @staticmethod
    def convert_pdf_to_images(file_data: bytes, filename: str = "") -> List[bytes]:
        """Convert PDF to list of image bytes using PyMuPDF."""
        logger.info(f"Converting PDF to images: {filename or 'unknown PDF'}")
        
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            images = []
            
            logger.info(f"PDF has {len(pdf_document)} pages")
            
            for page_num in range(len(pdf_document)):
                logger.debug(f"Converting page {page_num + 1}")
                
                # Get page
                page = pdf_document.load_page(page_num)
                
                # Render page as image (2x zoom for better quality)
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to bytes
                img_data = pix.tobytes("png")
                images.append(img_data)
                
                logger.debug(f"Page {page_num + 1} converted to {len(img_data)} bytes")
            
            pdf_document.close()
            
            logger.info(f"Successfully converted PDF to {len(images)} images")
            return images
            
        except Exception as e:
            logger.error(f"Failed to convert PDF {filename}: {e}")
            raise
    
    @staticmethod
    def process_file(file_data: bytes, original_filename: str = "", 
                    apply_preprocessing: bool = True, 
                    enhance_quality: bool = True) -> List[Tuple[bytes, str]]:
        """
        Process a file and return list of (image_data, description) tuples with optional preprocessing.
        
        Args:
            file_data: Raw file bytes
            original_filename: Original filename for type detection
            apply_preprocessing: Whether to apply image preprocessing for OCR enhancement
            enhance_quality: Whether to apply quality enhancement (resolution, skew correction, denoising)
            
        Returns:
            List of (preprocessed_image_bytes, description) tuples
        """
        logger.info(f"Processing file: {original_filename or 'unknown file'}")
        
        if not FileProcessor.is_supported_file(original_filename):
            raise ValueError(f"Unsupported file type: {original_filename}")
        
        # Initialize preprocessor if needed and available
        preprocessor = None
        preprocessing_type = "none"
        
        if apply_preprocessing:
            if ADVANCED_PREPROCESSING_AVAILABLE:
                preprocessor = ImagePreprocessor()
                preprocessing_type = "advanced"
                logger.info("Advanced image preprocessing (OpenCV/SciPy) enabled")
            # elif BASIC_PREPROCESSING_AVAILABLE:
            #     preprocessor = LightweightImagePreprocessor()
            #     preprocessing_type = "basic"
            #     logger.info("Basic image preprocessing (PIL-only) enabled")
            else:
                logger.warning("Image preprocessing requested but not available. Continuing without preprocessing.")
                apply_preprocessing = False
        
        file_type = FileProcessor.get_file_type(file_data, original_filename)
        
        if file_type == 'pdf':
            logger.info("Processing as PDF document")
            images = FileProcessor.convert_pdf_to_images(file_data, original_filename)
            
            # Process each page with preprocessing
            result = []
            for i, img_data in enumerate(images):
                description = f"{original_filename or 'document'} - Page {i + 1}"
                
                if apply_preprocessing:
                    logger.info(f"Applying {preprocessing_type} preprocessing to page {i + 1}")
                    try:
                        processed_img_data = preprocessor.preprocess_image(img_data, enhance_quality)
                        result.append((processed_img_data, description))
                        logger.info(f"Page {i + 1} {preprocessing_type} preprocessing completed")
                    except Exception as e:
                        logger.warning(f"{preprocessing_type} preprocessing failed for page {i + 1}: {e}. Using original.")
                        result.append((img_data, description))
                else:
                    result.append((img_data, description))
                
            logger.info(f"PDF processing complete: {len(result)} pages")
            return result
            
        else:  # image file
            logger.info("Processing as image file")
            description = original_filename or "image"
            
            if apply_preprocessing:
                logger.info(f"Applying {preprocessing_type} preprocessing to image")
                try:
                    processed_img_data = preprocessor.preprocess_image(file_data, enhance_quality)
                    logger.info(f"Image {preprocessing_type} preprocessing completed")
                    return [(processed_img_data, description)]
                except Exception as e:
                    logger.warning(f"{preprocessing_type} preprocessing failed: {e}. Using original image.")
                    return [(file_data, description)]
            else:
                return [(file_data, description)]

class FileSizeValidator:
    """Validates file sizes."""
    
    @staticmethod
    def validate_file_size(file_data: bytes, filename: str = "") -> bool:
        """Validate file size is within limits."""
        size_mb = len(file_data) / (1024 * 1024)
        
        if size_mb > Config.MAX_FILE_SIZE_MB:
            logger.error(f"File {filename} size {size_mb:.2f}MB exceeds limit of {Config.MAX_FILE_SIZE_MB}MB")
            return False
        
        logger.debug(f"File {filename} size {size_mb:.2f}MB is within limits")
        return True
    
    @staticmethod
    def get_file_size_mb(file_data: bytes) -> float:
        """Get file size in MB."""
        return len(file_data) / (1024 * 1024)