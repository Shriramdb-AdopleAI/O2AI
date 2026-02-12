"""
Azure Document Intelligence OCR engine implementation.
This code uses Prebuilt Read operations with the Azure AI Document Intelligence client library.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import numpy as np

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

from utility.config import Config

logger = logging.getLogger(__name__)


def format_bounding_box(bounding_box):
    """Format bounding box coordinates for display."""
    if not bounding_box:
        return "N/A"
    reshaped_bounding_box = np.array(bounding_box).reshape(-1, 2)
    return ", ".join(["[{}, {}]".format(x, y) for x, y in reshaped_bounding_box])


class AzureDocumentIntelligenceOCR:
    """Azure Document Intelligence OCR engine with text positioning."""
    
    def __init__(self):
        """Initialize Azure Document Intelligence OCR engine."""
        self.client = None
        if Config.validate_azure_document_intelligence_config():
            try:
                # Use Document Intelligence endpoint and key from config
                endpoint = Config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
                key = Config.AZURE_DOCUMENT_INTELLIGENCE_KEY
                
                self.client = DocumentIntelligenceClient(
                    endpoint=endpoint,
                    credential=AzureKeyCredential(key)
                )
                logger.info("Azure Document Intelligence OCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Azure Document Intelligence client: {e}")
                self.client = None
        else:
            logger.warning("Azure Document Intelligence configuration invalid - client not initialized")
    
    def is_available(self) -> bool:
        """Check if the OCR engine is available."""
        return self.client is not None
    
    async def extract_text(self, file_data: bytes, filename: str = "") -> Dict[str, Any]:
        """Extract text from file (PDF, image) using Azure Document Intelligence with positioning."""
        if not self.client:
            raise ValueError("Azure Document Intelligence client not initialized")
        
        logger.info(f"Starting Azure Document Intelligence OCR for {filename or 'file'}")
        
        try:
            # Analyze the document using raw file bytes (PDF or image)
            # Azure Document Intelligence accepts PDFs and images directly
            # Run the synchronous call in a thread pool to make it async-compatible
            result = await asyncio.to_thread(
                self._analyze_document_sync,
                file_data
            )
            
            # Extract text with positioning information
            formatted_text = result.content or ""
            text_blocks = []
            
            # Process pages
            if result.pages:
                for page in result.pages:
                    page_lines = []
                    page_text = ""
                    
                    # Process lines
                    if page.lines:
                        for line_idx, line in enumerate(page.lines):
                            line_text = line.content or ""
                            line_words = []
                            
                            # Get actual confidence from Document Intelligence (don't default to 1.0)
                            # Only include confidence if it's actually provided
                            line_confidence = getattr(line, 'confidence', None)
                            
                            # Process words (if available in the line)
                            # Note: Document Intelligence may not have words directly in lines
                            # We'll use page.words if available
                            line_info = {
                                'text': line_text,
                                'bounding_box': format_bounding_box(getattr(line, 'polygon', None)),
                                'words': line_words
                            }
                            # Only add confidence if Document Intelligence provided it
                            if line_confidence is not None:
                                line_info['confidence'] = float(line_confidence)
                            page_lines.append(line_info)
                            page_text += line_text + "\n"
                    
                    # Process words from page level
                    page_words = []
                    if page.words:
                        for word in page.words:
                            # Get actual confidence from Document Intelligence (don't default to 1.0)
                            word_confidence = getattr(word, 'confidence', None)
                            
                            word_info = {
                                'text': word.content or "",
                                'bounding_box': format_bounding_box(getattr(word, 'polygon', None))
                            }
                            # Only add confidence if Document Intelligence provided it
                            if word_confidence is not None:
                                word_info['confidence'] = float(word_confidence)
                            page_words.append(word_info)
                    
                    # Create page block
                    page_block = {
                        'text': page_text.strip(),
                        'confidence': 1.0,
                        'bounding_box': format_bounding_box(None),
                        'lines': page_lines,
                        'words': page_words,
                        'page_number': page.page_number,
                        'width': page.width,
                        'height': page.height,
                        'unit': page.unit
                    }
                    text_blocks.append(page_block)
            
            # Process styles (handwritten detection)
            styles_info = []
            if result.styles:
                for style in result.styles:
                    styles_info.append({
                        'is_handwritten': getattr(style, 'is_handwritten', False)
                    })
            
            # Calculate total words (from page.words which is more accurate)
            total_words = sum(len(block.get('words', [])) for block in text_blocks)
            
            # Create structured result
            result_data = {
                'raw_text': formatted_text.strip(),
                'text_blocks': text_blocks,
                'total_blocks': len(text_blocks),
                'total_lines': sum(len(block.get('lines', [])) for block in text_blocks),
                'total_words': total_words,
                'styles': styles_info,
                'content': result.content
            }
            
            logger.info(f"Azure Document Intelligence OCR completed for {filename}. Extracted {len(formatted_text)} characters from {len(text_blocks)} pages")
            return result_data
            
        except Exception as e:
            logger.error(f"Azure Document Intelligence OCR failed for {filename}: {e}")
            raise
    
    def _analyze_document_sync(self, file_content: bytes):
        """
        Synchronous wrapper for document analysis.
        Passes raw file bytes directly to Document Intelligence - exactly like:
        with open(file_path, "rb") as file:
            file_content = file.read()
        poller = client.begin_analyze_document("prebuilt-read", body=file_content)
        """
        # Pass raw file bytes directly - no preprocessing, no conversion
        poller = self.client.begin_analyze_document(
            "prebuilt-read",
            body=file_content
        )
        return poller.result()


class OCREngineFactory:
    """Factory for creating OCR engines."""
    
    @staticmethod
    def create_engine(engine_type: str):
        """Create an OCR engine instance."""
        if engine_type == "azure_computer_vision" or engine_type == "azure_document_intelligence":
            # Support both names for backward compatibility
            return AzureDocumentIntelligenceOCR()
        else:
            raise ValueError(f"Unsupported OCR engine: {engine_type}")
    
    @staticmethod
    def get_available_engines() -> List[str]:
        """Get list of available OCR engines."""
        available = []
        
        # Check Azure Document Intelligence
        if Config.validate_azure_document_intelligence_config():
            available.append("azure_document_intelligence")
            available.append("azure_computer_vision")  # For backward compatibility
        
        return available
