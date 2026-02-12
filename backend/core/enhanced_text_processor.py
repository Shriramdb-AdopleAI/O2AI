import json
import re
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from utility.config import Config
from utility.config import setup_logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logger = setup_logging()

@dataclass
class ProcessingResult:
    """Result of text processing."""
    raw_text: str
    key_value_pairs: Dict[str, str]
    summary: str
    confidence_score: float
    processing_time: float
    template_mapping: Optional[Dict[str, str]] = None

class EnhancedTextProcessor:
    """Enhanced text processor with template support and improved key-value extraction."""
    
    def __init__(self):
        """Initialize enhanced text processor."""
        self.client = None
        
        # Debug configuration
        logger.info(f"Azure OpenAI Config Check:")
        logger.info(f"  API Key: {'Set' if Config.AZURE_OPENAI_API_KEY else 'Not Set'}")
        logger.info(f"  Endpoint: {'Set' if Config.AZURE_OPENAI_ENDPOINT else 'Not Set'}")
        logger.info(f"  Deployment: {'Set' if Config.AZURE_OPENAI_DEPLOYMENT else 'Not Set'}")
        logger.info(f"  API Version: {Config.AZURE_API_VERSION}")
        
        if Config.validate_azure_openai_config():
            try:
                self.client = AzureChatOpenAI(
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                    api_key=Config.AZURE_OPENAI_API_KEY,
                    api_version=Config.AZURE_API_VERSION,
                    azure_deployment=Config.AZURE_OPENAI_DEPLOYMENT,
                    temperature=0.0,  # Set to 0 for maximum determinism and consistency
                    max_tokens=4096,  # Maximum supported by the model 
                )
                logger.info("Enhanced text processor initialized with Azure GPT")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced text processor: {e}")
                self.client = None
        else:
            logger.warning("Azure OpenAI configuration invalid - enhanced text processor not available")
            logger.warning(f"Missing: {[var for var in ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT'] if not getattr(Config, var, None)]}")
    
    def is_available(self) -> bool:
        """Check if text processor is available."""
        return self.client is not None
    
    async def test_connection(self) -> bool:
        """Test the LLM connection."""
        if not self.client:
            return False
        
        try:
            # Simple test prompt
            test_prompt = "Hello, please respond with 'Connection successful'"
            response = await self.client.ainvoke(test_prompt)
            logger.info(f"LLM connection test successful: {response.content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False
    
    async def process_without_template(self, ocr_text: str, filename: str = "") -> ProcessingResult:
        """
        Process OCR text without template - extract key-value pairs automatically.
        
        Args:
            ocr_text: Raw OCR text
            filename: Original filename for context
            
        Returns:
            ProcessingResult with extracted data
        """
        logger.info(f"Processing text without template for {filename} ({len(ocr_text)} characters)")
        
        # Test LLM connection first
        if not self.client:
            error_msg = "Azure OpenAI client not available - check configuration"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_result(ocr_text, filename, error_reason=error_msg)
        
        # Test connection
        connection_ok = await self.test_connection()
        if not connection_ok:
            error_msg = "LLM connection test failed - check Azure OpenAI configuration"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_result(ocr_text, filename, error_reason=error_msg)
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create prompt for automatic key-value extraction
            prompt = self._create_automatic_extraction_prompt(ocr_text, filename)
            logger.info(f"Created prompt for LLM processing ({len(prompt)} characters)")
            
            # Get response from Azure GPT
            logger.info("Sending request to Azure GPT...")
            response = await self.client.ainvoke(prompt)
            response_text = response.content
            logger.info(f"Received response from Azure GPT ({len(response_text)} characters)")
            
            # Parse the response
            parsed_result = self._parse_enhanced_response(response_text, ocr_text)
            
            # Post-extraction validation: check for important fields that might have been missed
            extracted_pairs = parsed_result.get('key_value_pairs', {})
            
            # Define required fields
            required_fields = [
                "Name (First, Middle, Last)",
                "Date of Birth",
                "Member ID",
                "Address",
                "Gender",
                "Insurance ID"
            ]
            
            # Ensure all required fields are present (add with null if missing)
            for field in required_fields:
                if field not in extracted_pairs:
                    extracted_pairs[field] = None
                    logger.warning(f"Required field '{field}' not found in extraction, setting to null")
            
            # Log extraction results
            logger.info(f"=" * 80)
            logger.info(f"EXTRACTION RESULTS FOR: {filename}")
            logger.info(f"=" * 80)
            logger.info(f"Total fields extracted: {len(extracted_pairs)}")
            
            # Log required fields first
            logger.info(f"\n--- REQUIRED FIELDS ---")
            for field in required_fields:
                value = extracted_pairs.get(field)
                # Check if value is None, empty string, or the string "None"/"null"
                is_null = (
                    value is None or 
                    value == "" or 
                    (isinstance(value, str) and value.strip().lower() in ["none", "null"])
                )
                if is_null:
                    logger.warning(f"  [{field}]: None (not found in document)")
                else:
                    logger.info(f"  [{field}]: {value}")

            
            # Log additional fields
            additional_fields = {k: v for k, v in extracted_pairs.items() if k not in required_fields}
            if additional_fields:
                logger.info(f"\n--- ADDITIONAL FIELDS ({len(additional_fields)}) ---")
                for key, value in additional_fields.items():
                    logger.info(f"  [{key}]: {value}")
            else:
                logger.info(f"\n--- ADDITIONAL FIELDS ---")
                logger.info(f"  No additional fields extracted")
            
            logger.info(f"=" * 80)
            
            self._validate_extraction_completeness(extracted_pairs, ocr_text, filename)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"LLM processing completed in {processing_time:.2f} seconds. Extracted {len(extracted_pairs)} key-value pairs")
            
            return ProcessingResult(
                raw_text=ocr_text,
                key_value_pairs=extracted_pairs,
                summary=parsed_result.get('summary', ''),
                confidence_score=parsed_result.get('confidence_score', 0.5),
                processing_time=processing_time,
                template_mapping={}
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced processing for {filename}: {e}")
            processing_time = asyncio.get_event_loop().time() - start_time
            
            # Return fallback result on error with error details
            error_msg = f"LLM processing error: {str(e)}"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_result(ocr_text, filename, error_reason=error_msg)
    
    async def process_with_template(self, ocr_text: str, template: Dict[str, Any], filename: str = "") -> ProcessingResult:
        """
        Process OCR text with template mapping.
        
        Args:
            ocr_text: Raw OCR text
            template: Template configuration
            filename: Original filename for context
            
        Returns:
            ProcessingResult with template-mapped data
        """
        logger.info(f"Processing text with template for {filename} ({len(ocr_text)} characters)")
        
        # Test LLM connection first
        if not self.client:
            error_msg = "Azure OpenAI client not available - check configuration"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_template_result(ocr_text, template, filename, error_reason=error_msg)
        
        # Test connection
        connection_ok = await self.test_connection()
        if not connection_ok:
            error_msg = "LLM connection test failed - check Azure OpenAI configuration"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_template_result(ocr_text, template, filename, error_reason=error_msg)
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create intelligent prompt for comprehensive extraction tied to explicit template fields
            prompt = self._create_intelligent_extraction_prompt(ocr_text, template, filename)
            logger.info(f"Created template prompt for LLM processing ({len(prompt)} characters)")
            
            # Get response from Azure GPT
            logger.info("Sending template request to Azure GPT...")
            response = await self.client.ainvoke(prompt)
            response_text = response.content
            logger.info(f"Received template response from Azure GPT ({len(response_text)} characters)")
            
            # Parse the response
            parsed_result = self._parse_enhanced_response(response_text, ocr_text)
            
            # Enforce exact target fields with empty string for missing
            template_mapping = {}
            template_fields = template.get('fields', {})  # { field_name: {type, description} }
            extracted_fields = parsed_result.get('key_value_pairs', {})

            normalized_extracted = {}
            for field_name in template_fields.keys():
                value = extracted_fields.get(field_name)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    normalized_extracted[field_name] = ""
                    template_mapping[field_name] = "not_found"
                else:
                    normalized_extracted[field_name] = value
                    template_mapping[field_name] = "found_in_document"
            
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Template processing completed in {processing_time:.2f} seconds")
            
            return ProcessingResult(
                raw_text=ocr_text,
                key_value_pairs=normalized_extracted,
                summary=parsed_result.get('summary', ''),
                confidence_score=parsed_result.get('confidence_score', 0.8),
                processing_time=processing_time,
                template_mapping=template_mapping
            )
            
        except Exception as e:
            logger.error(f"Error in template-based processing for {filename}: {e}")
            processing_time = asyncio.get_event_loop().time() - start_time
            
            # Return fallback result on error with error details
            error_msg = f"LLM processing error: {str(e)}"
            logger.error(f"[FALLBACK] {error_msg} for {filename}")
            return self._create_fallback_template_result(ocr_text, template, filename, error_reason=error_msg)
    
    async def correct_value(self, key: str, current_value: str, context: str) -> Dict[str, Any]:
        """
        Correct a specific key-value pair using the LLM and context.
        
        Args:
            key: The field name
            current_value: The current (potentially incorrect) value
            context: The surrounding text or full OCR text
            
        Returns:
            Dict containing 'corrected_value' and 'confidence_score'
        """
        logger.info(f"Correcting value for key: {key}, current: {current_value}")
        
        if not self.client:
            logger.error("Azure OpenAI client not available for correction")
            return {"corrected_value": current_value, "confidence_score": 0.0, "error": "LLM not available"}
            
        try:
            prompt = f"""
            You are an expert document data correction specialist.
            
            TASK: Verify and correct a specific extracted value based on the provided document context.
            
            FIELD: "{key}"
            CURRENT VALUE: "{current_value}"
            
            DOCUMENT CONTEXT:
            {context}
            
            ADDRESS CORRECTION RULES:
            - If the field is an address, pay special attention to "Cross", "Main", "Block", "Stage", "Phase".
            - Ensure these components are present if they appear in the text.
            - Correct common abbreviations (e.g., "Crs" -> "Cross", "Blk" -> "Block").
            - Ensure "Cross", "Main", "Block" are capitalized correctly.
            - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.
            
            INSTRUCTIONS:
            1. Search the document context for the field "{key}".
            2. Determine the correct value for this field.
            3. If the current value is correct, return it as is.
            4. If the current value is incorrect (e.g. OCR error, typo, truncation), provide the correct value.
            5. If the value cannot be found in the context, return the current value.
            6. Assign a confidence score (0.0 to 1.0) to your correction.
            
            OUTPUT FORMAT (JSON only):
            {{
                "corrected_value": "The correct value",
                "confidence_score": 0.95,
                "reasoning": "Brief explanation of why this value was chosen"
            }}
            """
            
            response = await self.client.ainvoke(prompt)
            response_text = response.content
            
            # Parse JSON response
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            result = json.loads(response_text)
            
            return {
                "corrected_value": result.get("corrected_value", current_value),
                "confidence_score": result.get("confidence_score", 0.5),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"Error correcting value: {e}")
            # Return a generic error message to avoid exposing internal details
            return {
                "corrected_value": current_value,
                "confidence_score": 0.0,
                "reasoning": "An error occurred while correcting the value. The original value is retained."
            }
    
    async def analyze_low_confidence_pairs(
        self, 
        key_value_pairs: Dict[str, Any], 
        confidence_scores: Dict[str, float],
        ocr_text: str,
        filename: str = "",
        source_file_base64: Optional[str] = None,
        source_file_content_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze key-value pairs with confidence below 95% and provide suggestions.
        Uses Azure OpenAI Vision API to analyze the original document image.
        
        Args:
            key_value_pairs: Dictionary of extracted key-value pairs
            confidence_scores: Dictionary mapping keys to confidence scores (0.0-1.0)
            ocr_text: Full OCR text for context
            filename: Original filename for logging
            source_file_base64: Optional base64-encoded original file
            source_file_content_type: Optional content type of the original file
            
        Returns:
            Dictionary mapping keys to analysis results with suggestions
        """
        logger.info(f"Analyzing low-confidence pairs for {filename}")
        
        if not self.client:
            logger.error("Azure OpenAI client not available for analysis")
            return {}
        
        # Filter pairs with confidence < 0.95
        low_confidence_pairs = {}
        for key, value in key_value_pairs.items():
            conf = confidence_scores.get(key)
            if conf is not None:
                # Normalize confidence if needed
                if conf > 1:
                    conf = conf / 100
                if conf < 0.95:
                    low_confidence_pairs[key] = {
                        "value": value,
                        "confidence": conf
                    }
        
        if not low_confidence_pairs:
            logger.info(f"No low-confidence pairs found for {filename}")
            return {}
        
        logger.info(f"Found {len(low_confidence_pairs)} low-confidence pairs to analyze")
        
        # Analyze each low-confidence pair
        results = {}
        for key, pair_data in low_confidence_pairs.items():
            try:
                value = pair_data["value"]
                confidence = pair_data["confidence"]
                
                # Build messages for vision API if we have the source file
                messages = []
                
                if source_file_base64 and self.client:
                    # Use vision API to analyze the document image
                    # Determine image format from content type
                    image_format = "png"
                    if source_file_content_type:
                        if "jpeg" in source_file_content_type.lower() or "jpg" in source_file_content_type.lower():
                            image_format = "jpeg"
                        elif "png" in source_file_content_type.lower():
                            image_format = "png"
                        elif "pdf" in source_file_content_type.lower():
                            # For PDF, we'll use OCR text only as vision API doesn't support PDF directly
                            image_format = None
                    
                    if image_format:
                        # Use vision API with image
                        image_url = f"data:image/{image_format};base64,{source_file_base64}"
                        
                        prompt_text = f"""
                        You are an expert document data validation specialist with access to the original document image.
                        
                        TASK: Analyze a low-confidence extracted key-value pair by examining the ORIGINAL DOCUMENT IMAGE and determine:
                        1. If the extraction is correct or incorrect
                        2. What might be missing or wrong
                        3. Provide suggestions for improvement
                        
                        FIELD NAME: "{key}"
                        EXTRACTED VALUE: "{value}"
                        CONFIDENCE SCORE: {confidence * 100:.1f}%
                        
                        PREVIOUS OCR TEXT (for reference):
                        {ocr_text[:4000]}
                        
                        **IMPORTANT**: Low confidence does NOT automatically mean the extraction is incorrect. 
                        The value may be perfectly correct but have low confidence due to image quality, unusual formatting, or complex field types.
                        
                        **VALIDATION RULES**:
                        1. ONLY mark as "incorrect" if you can SEE CLEAR EVIDENCE in the image that the value is wrong
                        2. If the extracted value matches what you see in the image EXACTLY, it is CORRECT (even with low confidence)
                        3. For alphanumeric IDs, codes, or mixed-case values (e.g., "xyzAGC1234"), verify character-by-character from the image
                        4. Do NOT assume OCR errors without clear visual evidence from the image
                        5. Do NOT suggest corrections for valid alphanumeric codes, IDs, or properly formatted values that match the image
                        
                        **ADDRESS CORRECTION**:
                        - If the field is an address, pay special attention to "Cross", "Main", "Block", "Stage", "Phase".
                        - Ensure these components are present if visible in the image.
                        - Correct common abbreviations (e.g., "Crs" -> "Cross", "Blk" -> "Block").
                        - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.
                        
                        INSTRUCTIONS:
                        1. Look at the ORIGINAL DOCUMENT IMAGE provided below
                        2. Find the field "{key}" in the document image
                        3. Read the actual value for this field directly from the image character-by-character
                        4. Compare the extracted value "{value}" with what you see in the image
                        5. Determine if the extraction is:
                           - CORRECT: The value matches EXACTLY what's visible in the document image (even if confidence is low)
                           - INCORRECT: The value is clearly wrong with visual evidence from the image (OCR error, wrong field, etc.)
                           - INCOMPLETE: The value is partially correct but missing information that is visible in the image
                           - MISSING: The field exists in the image but wasn't extracted properly
                        6. **CRITICAL**: If the value matches the image or you cannot see clear evidence of an error, mark it as CORRECT
                        7. ONLY suggest corrections if you can see clear visual evidence in the image that the value is wrong
                        8. If marking as incorrect, describe the specific visual evidence from the image
                        
                        OUTPUT FORMAT (JSON only):
                        {{
                            "is_correct": true/false,
                            "extraction_status": "correct" | "incorrect" | "incomplete" | "missing",
                            "suggested_value": "The exact value as seen in the image ONLY if you have clear visual evidence it's wrong (empty string if correct or uncertain)",
                            "missing_information": "Description of what might be missing based on the image (empty if nothing missing)",
                            "issues": ["Specific issue with visual evidence from image", ...],
                            "suggestions": ["Specific suggestion based on what you see in the image", ...],
                            "reasoning": "Detailed explanation with specific visual evidence from the document image"
                        }}
                        
                        **EXAMPLES**:
                        - If extracted value is "xyzAGC1234" and image shows "xyzAGC1234" → CORRECT (even if low confidence)
                        - If extracted value is "John Doe" and image shows "John Doe" → CORRECT
                        - If extracted value is "123 Main St" and image shows "123 Main Street, Block A" → INCOMPLETE
                        - If extracted value is "Dr. Smith" and image shows "Dr. Johnson" → INCORRECT
                        """
                        
                        messages = [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt_text
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": image_url
                                        }
                                    }
                                ]
                            }
                        ]
                    else:
                        # PDF - fall back to text-only analysis
                        messages = None
                else:
                    # No image - use text-only analysis
                    messages = None
                
                # If we don't have vision messages, use text-only prompt
                if messages is None:
                    prompt = f"""
                    You are an expert document data validation specialist.
                    
                    TASK: Analyze a low-confidence extracted key-value pair and determine:
                    1. If the extraction is correct or incorrect
                    2. What might be missing or wrong
                    3. Provide suggestions for improvement
                    
                    FIELD NAME: "{key}"
                    EXTRACTED VALUE: "{value}"
                    CONFIDENCE SCORE: {confidence * 100:.1f}%
                    
                    FULL DOCUMENT TEXT:
                    {ocr_text[:8000]}
                    
                    **IMPORTANT**: Low confidence does NOT automatically mean the extraction is incorrect. 
                    The value may be perfectly correct but have low confidence due to OCR quality, unusual formatting, or complex field types.
                    
                    **VALIDATION RULES**:
                    1. ONLY mark as "incorrect" if you find CLEAR EVIDENCE that the value is wrong
                    2. If the extracted value appears EXACTLY in the document text, it is CORRECT (even with low confidence)
                    3. For alphanumeric IDs, codes, or mixed-case values (e.g., "xyzAGC1234"), these are often CORRECT as-is
                    4. Do NOT assume OCR errors without clear evidence
                    5. Do NOT suggest corrections for valid alphanumeric codes, IDs, or properly formatted values
                    
                    **ADDRESS CORRECTION**:
                    - If the field is an address, pay special attention to "Cross", "Main", "Block", "Stage", "Phase".
                    - Ensure these components are present if they appear in the text.
                    - Correct common abbreviations (e.g., "Crs" -> "Cross", "Blk" -> "Block").
                    - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.
                    
                    INSTRUCTIONS:
                    1. Search the document text for the field "{key}"
                    2. Compare the extracted value "{value}" with what appears in the document
                    3. Determine if the extraction is:
                       - CORRECT: The value matches what's in the document (even if confidence is low)
                       - INCORRECT: The value is clearly wrong with evidence (OCR error, wrong field, etc.)
                       - INCOMPLETE: The value is partially correct but missing information that exists in the document
                       - MISSING: The field should exist but wasn't extracted
                    4. **CRITICAL**: If the value appears correct or you cannot find clear evidence of an error, mark it as CORRECT
                    5. ONLY suggest corrections if you have clear evidence the value is wrong
                    6. If marking as incorrect, provide specific evidence from the document text
                    
                    OUTPUT FORMAT (JSON only):
                    {{
                        "is_correct": true/false,
                        "extraction_status": "correct" | "incorrect" | "incomplete" | "missing",
                        "suggested_value": "The correct value ONLY if you have clear evidence it's wrong (empty string if correct or uncertain)",
                        "missing_information": "Description of what might be missing (empty if nothing missing)",
                        "issues": ["Specific issue with evidence from document", ...],
                        "suggestions": ["Specific suggestion based on document evidence", ...],
                        "reasoning": "Detailed explanation with specific evidence from the document"
                    }}
                    
                    **EXAMPLES**:
                    - If extracted value is "xyzAGC1234" and this appears in the document → CORRECT (even if low confidence)
                    - If extracted value is "John Doe" and document shows "John Doe" → CORRECT
                    - If extracted value is "123 Main St" and document shows "123 Main Street, Block A" → INCOMPLETE
                    - If extracted value is "Dr. Smith" and document shows "Dr. Johnson" → INCORRECT
                    """
                    messages = [{"role": "user", "content": prompt}]
                
                # Invoke the model
                if isinstance(messages[0].get("content"), list):
                    # Vision API call - use messages with image
                    from langchain_core.messages import HumanMessage
                    vision_message = HumanMessage(content=messages[0]["content"])
                    response = await self.client.ainvoke([vision_message])
                else:
                    # Text-only call
                    response = await self.client.ainvoke(messages[0]["content"])
                
                response_text = response.content
                
                # Parse JSON response
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
                
                analysis = json.loads(response_text)
                
                results[key] = {
                    "is_correct": analysis.get("is_correct", False),
                    "extraction_status": analysis.get("extraction_status", "unknown"),
                    "suggested_value": analysis.get("suggested_value", ""),
                    "missing_information": analysis.get("missing_information", ""),
                    "issues": analysis.get("issues", []),
                    "suggestions": analysis.get("suggestions", []),
                    "reasoning": analysis.get("reasoning", ""),
                    "current_value": value,
                    "current_confidence": confidence
                }
                
            except Exception as e:
                logger.error(f"Error analyzing pair {key}: {e}")
                results[key] = {
                    "is_correct": None,
                    "extraction_status": "error",
                    "suggested_value": "",
                    "missing_information": f"Error during analysis: {str(e)}",
                    "issues": ["Analysis failed"],
                    "suggestions": [],
                    "reasoning": f"Could not analyze this pair: {str(e)}",
                    "current_value": value,
                    "current_confidence": confidence
                }
        
        return results

    def _create_automatic_extraction_prompt(self, text: str, filename: str) -> str:
        """Create prompt for automatic key-value extraction with required fields check."""
        return f"""
        You are an expert document data extraction specialist with deep knowledge of various document types and structures.

        **TASK**: Extract ALL clearly defined and meaningful key-value pairs from this document. Your goal is COMPREHENSIVE extraction - extract EVERY valid field present in the document. Do not leave any important information behind.

        **REQUIRED FIELDS (MUST ALWAYS CHECK AND INCLUDE)**:
        These 6 fields MUST always be present in your output. If not found in the document, set the value to null:
        1. "Name (First, Middle, Last)" - Full name with all parts if available
        2. "Date of Birth" - DOB in any format found  
        3. "Member ID" - Any unique identifier, member ID, patient ID, or similar
        4. "Address" - Complete address with at least zip code if available
        5. "Gender" - Gender/Sex of the person
        6. "Insurance ID" - Insurance ID, group number, or insurance information
        
        **IMPORTANT**: Even if these fields are not found in the document, you MUST include them in the output with null value.

        **CRITICAL EXTRACTION PRIORITY**:
        1. FIRST, search for the 6 REQUIRED FIELDS listed above
        2. Extract EVERY other field that has a clear label and valid value - be thorough and comprehensive
        3. Scan the ENTIRE document systematically - do not skip any sections
        4. Extract ALL instances of personal information, medical data, dates, and administrative fields
        5. If a field appears multiple times or in different formats, extract the most complete version
        6. For medical documents, pay special attention to: Patient Name (full name), Gender/Sex, Age, Address (complete), Phone, Email, Lab Name, Doctor Names, Test Results, Dates, Times, and all other labeled fields
        7. Extract ALL pathologist names, medical lab technician names, and healthcare provider information
        8. Extract complete addresses including pincodes/postal codes
        9. Extract all dates and times exactly as they appear
        10. Do NOT truncate names or values - extract them completely

        **CRITICAL VALIDATION RULES - ONLY EXTRACT IF**:
        1. The field has a clear, professional label (e.g., "Patient Name:", "Hospital No:", "Date:", "Address:")
        2. The value is clearly associated with its label in the document structure
        3. The value is readable, meaningful text (NOT random characters, OCR errors, or incomplete words)
        4. The value makes logical sense for its field type
        5. The data is NOT crossed out, cancelled, or modified with strikethrough marks
        6. The field and value form a complete, logical unit
        7. **CRITICAL**: The text is FULLY VISIBLE and NOT obscured, covered, hidden, or partially blocked by any overlay, paper, sticker, or other object
        8. **CRITICAL**: The text is COMPLETE and NOT cut off at document edges or margins
        9. **CRITICAL**: The text is LEGIBLE with clear, readable characters (not blurred, faded, or distorted beyond recognition)

        **STRICT VISIBILITY REQUIREMENTS - DO NOT EXTRACT IF**:
        - The field value is covered or obscured by another piece of paper, sticker, overlay, or any object
        - The field value is partially hidden or blocked from view
        - The field value is cut off at the edge of the document or image
        - The field value is too blurred, faded, or low quality to read with certainty
        - The field value appears to be underneath another layer or object
        - Only fragments or partial characters of the value are visible
        - The value area shows signs of being intentionally hidden or redacted
        - You cannot see the complete text clearly and unambiguously
        - **IMPORTANT**: If you see a label (e.g., "Name") but the value area is covered, obscured, or unclear, DO NOT extract that field at all. Leave it out completely rather than guessing or hallucinating.

        **VALIDATION CRITERIA FOR EXTRACTED VALUES**:
        - Value must be at least 2 characters long (unless it's a single letter initial)
        - Value must contain actual words, numbers, or recognizable data
        - Value must NOT be just random characters like "et", "xabten", "noete", "xalten", "aber"
        - Value must NOT be cancelled, crossed out, or marked as invalid in the document
        - Value must make contextual sense (e.g., "Patient Name" should be a name, not a medication)
        - Value must have at least one vowel or digit (for strings longer than 2 characters)
        - Value must NOT be OCR garbage (random consonants like "xabten", "xalten")
        - Value must be FULLY VISIBLE and CLEARLY READABLE in the document
        - Value must NOT be a hallucination or guess based on partial/obscured text
        
        **EXAMPLES OF INVALID VALUES TO REJECT**:
        - "et", "xabten", "noete", "xalten", "aber" - OCR garbage or hallucinated text
        - "G- xalten" - incomplete/random text  
        - Single characters like "e", "t", "n" (unless it's a valid initial)
        - Values with 4+ consecutive consonants without vowels/digits
        - Any text that is covered, obscured, or not fully visible
        - Any text extracted from areas that appear to be hidden or blocked

        **TYPES OF FIELDS TO EXTRACT** (extract ALL of these if present AND fully visible):
        - Personal Information: Name (FULL name, not truncated), ID, Date of Birth, Gender/Sex, Age, Address (complete with pincode), Phone, Email
        - Medical Information: Case ID, Diagnosis, Symptoms, Allergies, Medications, Doctor Name, Pathologist Name, Medical Lab Technician
        - Laboratory Information: Test Name, Test Type, Collection Date, Collection Time, Result, Status, Lab Name, Sample ID, Sample Number
        - Dates: Admission Date, Discharge Date, Collection Date, Generated Date, Result Date, Reported Date, Registered Date
        - Times: Collection Time, Report Time, etc.
        - Administrative: District, Block, Department, Insurance, Total Charges, Sample Number, PID, Ref. By
        - Clinical Data: Blood Pressure, Heart Rate, Temperature, Weight, Height, BMI, Lab Values, Test Results
        - Healthcare Providers: Pathologist 1, Pathologist 2, Doctor Name, Medical Lab Technician, etc.

        **EXTRACTION RULES**:
        - Extract EVERY field that has BOTH a clear label and a CLEAR, VALID, FULLY VISIBLE value
        - Use EXACT wording from the document - no interpretation or inference
        - Extract data as flat key-value pairs only (no nested structures)
        - Include units of measurement when present
        - Preserve exact text formatting for important details
        - Extract COMPLETE values - do not truncate names, addresses, or other important information
        - For names, extract the FULL name (e.g., "Yash M. Patel" not just "Yash M.")
        - For addresses, include the complete address with pincode/postal code
        - For times, extract exactly as shown (e.g., "03:11 PM" not just "PM")
        - DO NOT extract headers, footers, page numbers, or navigation text
        - DO NOT extract OCR artifacts, random characters, incomplete words, or garbled text
        - DO NOT extract fields where the value is missing, unclear, or invalid
        - DO NOT include fields that are only partially visible or cut off
        - DO NOT extract cancelled, crossed-out, or strikethrough text
        - DO NOT extract prescription items as billing fields
        - DO NOT extract text that is covered, obscured, hidden, or blocked by any object
        - DO NOT guess or hallucinate values for fields where the text is not fully visible
        - DO NOT extract values from areas that appear to be intentionally hidden or redacted
        - If a value is ambiguous, unclear, or doesn't make sense, DO NOT include that field
        - If you see a field label but the value is covered/obscured, SKIP that field entirely
        - Skip noise, signatures, stamps, or decorative elements
        - Skip cancelled or modified entries (e.g., prescriptions crossed out)
        - Do NOT invent or assume missing information
        - Only extract information that is explicitly stated in the document AND is valid AND is fully visible

        **OUTPUT FORMAT** (JSON only):
        {{
            "key_value_pairs": {{
                "Name (First, Middle, Last)": "Complete full name OR null if not found",
                "Date of Birth": "DOB in any format OR null if not found",
                "Member ID": "Unique identifier/Patient ID/Member ID OR null if not found",
                "Address": "Complete address with zip code OR null if not found",
                "Gender": "Gender/Sex OR null if not found",
                "Insurance ID": "Insurance ID/Group number OR null if not found",
                "Field Name 1": "Complete Value 1 from document (additional fields)",
                "Field Name 2": "Complete Value 2 from document (additional fields)",
                "Field Name 3": "Complete Value 3 from document (additional fields)"
            }},
            "summary": "Brief summary of key findings from the document",
            "confidence_score": 0.85
        }}
        
        **NOTE**: 
        - The first 6 fields (Name, DOB, Member ID, Address, Gender, Insurance ID) are REQUIRED and MUST always be present
        - If a required field is not found, set its value to null (not empty string, but actual null)
        - After the required fields, include ALL other valid fields found in the document
        - The key_value_pairs object should contain the 6 required fields PLUS multiple additional entries for all other valid fields found

        **IMPORTANT INSTRUCTIONS**:
        1. **ALWAYS include the 6 REQUIRED fields first** (even if null)
        2. Extract ALL other fields that are clearly labeled and have VALID, meaningful, FULLY VISIBLE values - be thorough
        3. Include EVERY additional field from the document that has a clear label and valid value
        4. Use field names that match the labels used in the document (e.g., if document says "Hospital Name:", use "Hospital Name")
        5. Extract COMPLETE values - do not truncate or shorten important information
        6. DO NOT include fields with empty, ambiguous, or invalid values like "et", "xabten", "aber"
        7. DO NOT create composite or inferred fields
        8. DO NOT add metadata or processing information
        9. Keep field names simple and descriptive
        10. For required fields: if not found or unclear, use null (not empty string)
        11. For additional fields: only include if both the key AND value are clearly present, VALID, and FULLY VISIBLE
        12. Validate each value: it must be real data, not OCR garbage, not hallucinated, not from obscured areas
        13. DO NOT extract prescription medications as billing amounts
        14. Skip any text that is crossed out or cancelled
        15. Skip any text that is covered, obscured, or not fully visible
        16. The output should include the 6 REQUIRED fields PLUS MULTIPLE additional key-value pairs for all other valid fields found
        17. Scan the document multiple times to ensure nothing is missed
        18. Extract ALL healthcare provider names (Pathologist 1, Pathologist 2, Medical Lab Technician, etc.)
        19. **CRITICAL**: If a required field's value is covered by paper, sticker, or any overlay, set it to null
        20. **CRITICAL**: Never guess or hallucinate values. Only extract what you can clearly see and read, or use null for required fields

        **ADDRESS FORMATTING RULES**:
        - Ensure address components like "Cross", "Main", "Block", "Stage", "Phase", "Layout" are preserved and correctly formatted.
        - If an address contains "35th" followed by "Cross" or "Block" in the document, ensure "Cross" or "Block" is included.
        - Do not drop "Cross", "Main", "Block" etc. from addresses.
        - Correct common OCR errors in address suffixes (e.g., "Crs" -> "Cross", "Blk" -> "Block" if clear from context).
        - Ensure "Cross", "Main", "Block" are capitalized correctly.
        - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.
        
        **ORDINAL NUMBER FORMATTING** (for addresses only):
        - Convert ordinal superscripts: "22ª" → "22nd", "4ª" → "4th"
        - Convert asterisk placeholders: "6* Street" → "6th Street"
        - Only apply formatting to address fields when ordinals are clearly present

        **DOCUMENT TEXT**:
        {text}

        **CRITICAL VALIDATION**: 
        - Return ONLY valid JSON
        - **ALWAYS include the 6 REQUIRED fields** (Name, DOB, Member ID, Address, Gender, Insurance ID) even if null
        - Extract ONLY factual, clearly labeled data with VALID, FULLY VISIBLE values for additional fields
        - Extract COMPREHENSIVELY - do not skip important fields that are visible
        - Extract COMPLETE values - do not truncate names, addresses, or other information
        - Ensure each value is meaningful (not OCR garbage, not crossed out, not incomplete, not obscured)
        - If a value looks like random characters or doesn't make sense, DO NOT include it (except required fields use null)
        - If a required field value is covered, obscured, or not fully visible, set it to null
        - If an additional field value is covered, obscured, or not fully visible, DO NOT include it
        - Never hallucinate or guess values - only extract what is clearly visible, or use null for required fields
        - Review your extraction to ensure you've captured the 6 REQUIRED fields AND ALL important additional fields from the document
        """
    
    def _create_template_extraction_prompt(self, text: str, template: Dict[str, Any], filename: str) -> str:
        """Create prompt for template-based extraction."""
        template_name = template.get('name', 'Unknown')
        fields_description = ""
        
        for field_name, field_config in template.get('fields', {}).items():
            field_type = field_config.get('type', 'text')
            field_description = field_config.get('description', '')
            fields_description += f"- {field_name} ({field_type}): {field_description}\n"
        
        return f"""
        You are an expert medical document data extraction specialist with deep knowledge of healthcare terminology and document structures.

        **TASK**: Extract ALL meaningful information from this medical document as structured key-value pairs.

        **EXTRACTION GUIDELINES**:
        1. **Patient Information**: Name, ID, DOB, Age, Gender, Address, Phone, Emergency Contact
        2. **Medical Details**: Diagnosis, Chief Complaint, History, Symptoms, Allergies, Medications
        3. **Vital Signs**: Blood Pressure, Heart Rate, Temperature, Respiratory Rate, Oxygen Saturation, Weight, Height, BMI
        4. **Laboratory Results**: All lab values with units (e.g., "Hemoglobin: 12.5 g/dL", "WBC Count: 8000/μL")
        5. **Clinical Findings**: Physical examination results, assessment, plan
        6. **Treatment**: Procedures performed, medications prescribed, dosages, frequencies
        7. **Billing Information**: Charges, amounts, insurance details, payment information
        8. **Dates & Times**: Admission, discharge, procedure dates, follow-up appointments
        9. **Healthcare Providers**: Doctor names, specialties, departments, contact information
        10. **Discharge Instructions**: Care plans, medications, follow-up requirements

        **EXTRACTION RULES**:
        - Extract EVERY identifiable piece of information, no matter how small
        - Use exact medical terminology from the document
        - For tables/lists, extract each row as separate key-value pairs
        - Combine related information under descriptive keys
        - Include units of measurement for lab values and vitals
        - Preserve exact text formatting for important details
        - If information spans multiple lines, combine it intelligently
        - Extract both explicit labels and implicit information

        **ADDRESS FORMATTING RULES**:
        - Ensure address components like "Cross", "Main", "Block", "Stage", "Phase", "Layout" are preserved and correctly formatted.
        - If an address contains "35th" followed by "Cross" or "Block" in the document, ensure "Cross" or "Block" is included.
        - Do not drop "Cross", "Main", "Block" etc. from addresses.
        - Correct common OCR errors in address suffixes (e.g., "Crs" -> "Cross", "Blk" -> "Block" if clear from context).
        - Ensure "Cross", "Main", "Block" are capitalized correctly.
        - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.

        **ORDINAL NUMBER AND STREET NAME FORMATTING**:
        - Convert ordinal numbers to proper format: 1st → 1st, 2nd → 2nd, 3rd → 3rd, 4th → 4th, 5th → 5th, etc.
        - For street names with ordinal numbers, format as: "4th Street" → "4th Street", "22nd Street" → "22nd Street"
        - Handle special ordinal formats: "22ª" → "22nd", "4ª" → "4th", "5ª" → "5th" (convert superscript ordinals to standard format)
        - Handle asterisk placeholders: "6* Street" → "6th Street", "4* Street" → "4th Street" (convert asterisk placeholders to proper ordinals)
        - Preserve the ordinal format in the extracted output (e.g., "111 22nd Street" should remain "111 22nd Street")
        - Handle common ordinal patterns: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th, 15th, 16th, 17th, 18th, 19th, 20th, 21st, 22nd, 23rd, 24th, 25th, etc.
        - For addresses, maintain the original ordinal format as it appears in the document, but convert superscript ordinals and asterisk placeholders to standard format

        **OUTPUT FORMAT** (JSON only):
        {{
            "key_value_pairs": {{
                "Patient Name": "exact name from document",
                "Date of Birth": "DOB if present",
                "Gender": "gender if present",
                "Age": "age if present",
                "Address": "address if present",
                "Mobile": "mobile number if present",
                "Case ID": "case ID if present",
                "District": "district if present",
                "Block": "block if present",
                "Total Samples": "total samples if present",
                "Sample Number": "sample number if present",
                "Lab Name": "lab name if present",
                "Test Type": "test type if present",
                "Sample ID": "sample ID if present",
                "Collection Date": "collection date if present",
                "Receiving Date": "receiving date if present",
                "Status": "status if present",
                "Lab Result": "lab result if present",
                "Lab Result Date": "lab result date if present",
                "Primary Diagnosis": "diagnosis text if present",
                "Blood Pressure": "blood pressure if present",
                "Heart Rate": "heart rate if present",
                "Temperature": "temperature if present",
                "Lab Results": "all lab values found if present",
                "Medications": "all medications listed if present",
                "Doctor Name": "physician name if present",
                "Department": "department if present",
                "Total Charges": "amount if present",
                "Insurance": "insurance details if present",
                "Discharge Instructions": "care instructions if present",
                "Disclaimer": "disclaimer if present",
                "Other": "any other important fields if present"
            }},
            "summary": "Comprehensive medical summary including patient condition, test results, and outcomes",
            "confidence_score": 0.95
        }}

        **DOCUMENT TO ANALYZE**:
        {text}

        **IMPORTANT**: Return ONLY valid JSON. Extract maximum information with high accuracy.
        """
    
    def _create_intelligent_extraction_prompt(self, text: str, template: Dict[str, Any], filename: str) -> str:
        """Create a prompt that asks the LLM to map exactly the given template fields.
        Any missing field must be returned with an empty string.
        """
        fields_map = template.get('fields', {})  # { name: {type, description} }
        fields_list = []
        for name, cfg in fields_map.items():
            desc = cfg.get('description', '')
            typ = cfg.get('type', 'text')
            fields_list.append(f"- {name} ({typ}): {desc}")

        fields_bulleted = "\n".join(fields_list) if fields_list else "-"

        return f"""
        You are an expert information extraction system.

        TASK: Read the raw OCR text of a document and RETURN JSON that maps EXACTLY the requested target fields to values.
        - Use the ORIGINAL values from the text (preserve units and formatting where applicable).
        - If a field is NOT present in the text, return an empty string "" for that field.
        - Do NOT invent or infer values that aren't present.
        - Do NOT include any extra keys other than the target fields listed below.

        **ADDRESS FORMATTING RULES**:
        - Ensure address components like "Cross", "Main", "Block", "Stage", "Phase", "Layout" are preserved and correctly formatted.
        - If an address contains "35th" followed by "Cross" or "Block" in the document, ensure "Cross" or "Block" is included.
        - Do not drop "Cross", "Main", "Block" etc. from addresses.
        - Correct common OCR errors in address suffixes (e.g., "Crs" -> "Cross", "Blk" -> "Block" if clear from context).
        - Ensure "Cross", "Main", "Block" are capitalized correctly.
        - **CRITICAL**: Look for alphanumeric identifiers for Block/Cross (e.g., "A Block", "T Block", "4th T Block", "12th A Cross"). Ensure the letter identifier is INCLUDED.

        **ORDINAL NUMBER AND STREET NAME FORMATTING**:
        - Convert ordinal numbers to proper format: 1st → 1st, 2nd → 2nd, 3rd → 3rd, 4th → 4th, 5th → 5th, etc.
        - For street names with ordinal numbers, format as: "4th Street" → "4th Street", "22nd Street" → "22nd Street"
        - Handle special ordinal formats: "22ª" → "22nd", "4ª" → "4th", "5ª" → "5th" (convert superscript ordinals to standard format)
        - Handle asterisk placeholders: "6* Street" → "6th Street", "4* Street" → "4th Street" (convert asterisk placeholders to proper ordinals)
        - Preserve the ordinal format in the extracted output (e.g., "111 22nd Street" should remain "111 22nd Street")
        - Handle common ordinal patterns: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th, 15th, 16th, 17th, 18th, 19th, 20th, 21st, 22nd, 23rd, 24th, 25th, etc.
        - For addresses, maintain the original ordinal format as it appears in the document, but convert superscript ordinals and asterisk placeholders to standard format

        TARGET FIELDS (name (type): description):
        {fields_bulleted}

        OUTPUT FORMAT (JSON only, keys must be EXACTLY the field names above):
        {{
          "key_value_pairs": {{
            "<Field 1>": "<exact value or empty string>",
            "<Field 2>": "<exact value or empty string>",
            "...": "..."
          }},
          "summary": "Short summary of what was extracted (optional)",
          "confidence_score": 0.9
        }}

        **EXAMPLE OF ORDINAL FORMATTING**:
        If the document contains: "111 22ª Street, Salem, MA 33333" and "987 6* Street, Boston, MA 33333"
        Extract as: "Doctor Address": "111 22nd Street, Salem, MA 33333" and "Patient Address": "987 6th Street, Boston, MA 33333"

        RAW OCR TEXT (filename: {filename}):
        {text}

        IMPORTANT:
        - Return ONLY valid JSON.
        - Include ALL target fields as keys in key_value_pairs.
        - If a field is missing in the document, set its value to an empty string.
        """
    
    def _flatten_json(self, data: Any, parent_key: str = '', sep: str = '_') -> Dict[str, str]:
        """Flatten nested JSON into flat key-value pairs."""
        items: List[tuple] = []
        if isinstance(data, dict):
            for k, v in data.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                items.extend(self._flatten_json(v, new_key, sep=sep).items())
        elif isinstance(data, list):
            for i, v in enumerate(data):
                new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
                items.extend(self._flatten_json(v, new_key, sep=sep).items())
        else:
            items.append((parent_key, str(data)))
        return dict(items)

    def _validate_extraction_completeness(self, extracted_pairs: Dict[str, Any], ocr_text: str, filename: str) -> None:
        """
        Validate that important fields haven't been missed in extraction.
        Logs warnings if common fields are missing but present in the text.
        """
        if not extracted_pairs:
            return
        
        # Common important field patterns that should be checked
        important_patterns = {
            'Patient Name': [r'patient\s+name[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]*)+)', r'name[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]*)+)'],
            'Gender': [r'gender[:]?\s*([MF]|male|female)', r'sex[:]?\s*([MF]|male|female)', r'sex/gender[:]?\s*([MF]|male|female)'],
            'Pathologist': [r'pathologist\s+(\d+)?[:]?\s*(Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)'],
            'Medical Lab Technician': [r'medical\s+lab\s+technician[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)', r'MLT[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)'],
            'Address Pincode': [r'pincode[:]?\s*(\d{4,6})', r'pin\s+code[:]?\s*(\d{4,6})', r'postal\s+code[:]?\s*(\d{4,6})'],
        }
        
        # Check if any important patterns are in text but not in extracted pairs
        text_lower = ocr_text.lower()
        missing_fields = []
        
        for field_name, patterns in important_patterns.items():
            # Check if field is already extracted (case-insensitive)
            field_found = any(key.lower() in field_name.lower() or field_name.lower() in key.lower() 
                            for key in extracted_pairs.keys())
            
            if not field_found:
                # Check if pattern exists in text
                for pattern in patterns:
                    import re
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    if matches:
                        missing_fields.append(field_name)
                        logger.warning(f"Potential missing field '{field_name}' detected in document {filename}. "
                                     f"Pattern found in text but not extracted. Consider reviewing extraction.")
                        break
        
        if missing_fields:
            logger.info(f"Extraction completeness check for {filename}: {len(extracted_pairs)} fields extracted, "
                       f"but {len(missing_fields)} potentially important fields may be missing: {', '.join(missing_fields)}")
        else:
            logger.debug(f"Extraction completeness check for {filename}: All important patterns accounted for")
    
    def _validate_and_filter_key_value_pairs(self, kv_pairs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and filter out ONLY obvious OCR garbage - be very conservative."""
        import re
        
        valid_pairs = {}
        invalid_count = 0
        
        # ONLY filter out these specific known garbage values
        known_garbage_words = [
            'et', 'no', 'te', 'ne',  # Common 2-letter OCR garbage
            'xabten', 'xalten', 'noete',  # Known OCR errors from examples
            'xal', 'noe', 'xab', 'noet',  # Variants of above
            'xalde', 'noele',  # Additional variants
            'aber', 'abe', 'abr',  # Hallucinated/OCR errors for obscured text
        ]
        
        for key, value in kv_pairs.items():
            # Skip metadata fields
            if key.lower() in ['document_type', 'filename', 'extraction_date', 'text_length', 'extraction_status', 'extraction_method']:
                valid_pairs[key] = value
                continue
            
            # Convert value to string
            value_str = str(value).strip()
            
            # Skip COMPLETELY empty values only
            if not value_str or len(value_str) == 0:
                invalid_count += 1
                logger.debug(f"Filtered empty value for key: {key}")
                continue
            
            # ONLY filter known garbage words - be very conservative
            if value_str.lower() in known_garbage_words:
                invalid_count += 1
                logger.debug(f"Filtered garbage value '{value_str}' for key: {key}")
                continue
            
            # ONLY filter 1-character values (except common initials)
            if len(value_str) == 1 and value_str.lower() not in ['m', 'f', 'a', 'o', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:
                invalid_count += 1
                logger.debug(f"Filtered 1-character value '{value_str}' for key: {key}")
                continue
            
            # Keep everything else that has content
            valid_pairs[key] = value_str
        
        if invalid_count > 0:
            logger.info(f"Filtered out {invalid_count} invalid key-value pairs, kept {len(valid_pairs)} valid pairs")
        
        return valid_pairs

    def _parse_enhanced_response(self, response_text: str, original_text: str) -> Dict[str, Any]:
        """Parse the enhanced extraction response from Azure GPT, flatten nested key_value_pairs."""
        try:
            cleaned_response = response_text.strip()

            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', cleaned_response, re.DOTALL)
            if json_match:
                cleaned_response = json_match.group(1)

            result = json.loads(cleaned_response)

            if 'key_value_pairs' in result and isinstance(result['key_value_pairs'], (dict, list)):
                result['key_value_pairs'] = self._flatten_json(result['key_value_pairs'])

            if not isinstance(result.get('key_value_pairs', {}), dict):
                raise ValueError("key_value_pairs must be a dictionary")
            if not isinstance(result.get('summary', ''), str):
                raise ValueError("summary must be a string")
            if not isinstance(result.get('confidence_score', 0), (int, float)):
                raise ValueError("confidence_score must be a number")

            # VALIDATE AND FILTER OUT INVALID KEY-VALUE PAIRS
            result['key_value_pairs'] = self._validate_and_filter_key_value_pairs(result['key_value_pairs'])

            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}...")

            return {
                'key_value_pairs': {
                    'document_type': 'Processed Document',
                    'extraction_status': 'completed',
                    'extraction_method': 'fallback'
                },
                'summary': response_text[:500] + "..." if len(response_text) > 500 else response_text,
                'confidence_score': 0.5
            }
    
    def _create_fallback_result(self, ocr_text: str, filename: str = "", error_reason: str = None) -> ProcessingResult:
        """Create fallback result when Azure OpenAI is not available - use simple text analysis."""
        from datetime import datetime
        
        # Simple text analysis without regex patterns
        key_value_pairs = {}
        
        # Basic text analysis to find obvious fields
        lines = ocr_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for obvious patterns in text
            if 'Patient Name' in line or 'Name' in line:
                # Extract name after colon or dash
                if ':' in line:
                    name = line.split(':', 1)[1].strip()
                elif '-' in line:
                    name = line.split('-', 1)[1].strip()
                else:
                    name = line
                if name and len(name) > 1:
                    key_value_pairs['Patient Name'] = name
                    
            elif 'Case ID' in line:
                if ':' in line:
                    case_id = line.split(':', 1)[1].strip()
                elif '-' in line:
                    case_id = line.split('-', 1)[1].strip()
                else:
                    case_id = line
                if case_id and len(case_id) > 1:
                    key_value_pairs['Case ID'] = case_id
                    
            elif 'Gender' in line:
                if ':' in line:
                    gender = line.split(':', 1)[1].strip()
                elif '-' in line:
                    gender = line.split('-', 1)[1].strip()
                else:
                    gender = line
                if gender and len(gender) > 1:
                    key_value_pairs['Gender'] = gender
                    
            elif 'Age' in line:
                if ':' in line:
                    age = line.split(':', 1)[1].strip()
                elif '-' in line:
                    age = line.split('-', 1)[1].strip()
                else:
                    age = line
                if age and len(age) > 1:
                    key_value_pairs['Age'] = age
                    
            elif 'Mobile' in line or 'Phone' in line:
                if ':' in line:
                    mobile = line.split(':', 1)[1].strip()
                elif '-' in line:
                    mobile = line.split('-', 1)[1].strip()
                else:
                    mobile = line
                if mobile and len(mobile) > 1:
                    key_value_pairs['Mobile'] = mobile
                    
            elif 'Address' in line:
                if ':' in line:
                    address = line.split(':', 1)[1].strip()
                elif '-' in line:
                    address = line.split('-', 1)[1].strip()
                else:
                    address = line
                if address and len(address) > 1:
                    key_value_pairs['Address'] = address
                    
            elif 'District' in line:
                if ':' in line:
                    district = line.split(':', 1)[1].strip()
                elif '-' in line:
                    district = line.split('-', 1)[1].strip()
                else:
                    district = line
                if district and len(district) > 1:
                    key_value_pairs['District'] = district
                    
            elif 'Block' in line:
                if ':' in line:
                    block = line.split(':', 1)[1].strip()
                elif '-' in line:
                    block = line.split('-', 1)[1].strip()
                else:
                    block = line
                if block and len(block) > 1:
                    key_value_pairs['Block'] = block
        
        # Add document metadata
        key_value_pairs["document_type"] = "Extracted Document"
        key_value_pairs["filename"] = filename
        key_value_pairs["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key_value_pairs["text_length"] = len(ocr_text)
        
        # Create simple summary with error indication
        if error_reason:
            summary = f"[FALLBACK MODE] Basic text analysis completed - {len(key_value_pairs)} fields extracted from {filename}"
            if len(ocr_text) > 100:
                summary += f" ({len(ocr_text)} characters analyzed)"
            summary += f" - ERROR: {error_reason} - For comprehensive extraction, Azure OpenAI configuration is required"
        else:
            summary = f"Basic text analysis completed - {len(key_value_pairs)} fields extracted from {filename}"
            if len(ocr_text) > 100:
                summary += f" ({len(ocr_text)} characters analyzed)"
            summary += " - Note: For comprehensive extraction, Azure OpenAI configuration is required"
        
        # Add error flag to key_value_pairs for detection
        if error_reason:
            key_value_pairs["_extraction_error"] = error_reason
            key_value_pairs["_extraction_method"] = "fallback"
        
        # Calculate confidence based on number of fields found
        confidence_score = min(0.5, len(key_value_pairs) * 0.05)
        
        return ProcessingResult(
            raw_text=ocr_text,
            key_value_pairs=key_value_pairs,
            summary=summary,
            confidence_score=confidence_score,
            processing_time=0.1,
            template_mapping={}
        )
    
    def _create_fallback_template_result(self, ocr_text: str, template: Dict[str, Any], filename: str = "", error_reason: str = None) -> ProcessingResult:
        """Create fallback template result when Azure OpenAI is not available."""
        from datetime import datetime
        
        # Use simple text analysis for template fallback
        key_value_pairs = {}
        
        # Basic text analysis to find obvious fields
        lines = ocr_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for obvious patterns in text
            if 'Patient Name' in line or 'Name' in line:
                if ':' in line:
                    name = line.split(':', 1)[1].strip()
                elif '-' in line:
                    name = line.split('-', 1)[1].strip()
                else:
                    name = line
                if name and len(name) > 1:
                    key_value_pairs['Patient Name'] = name
                    
            elif 'Case ID' in line:
                if ':' in line:
                    case_id = line.split(':', 1)[1].strip()
                elif '-' in line:
                    case_id = line.split('-', 1)[1].strip()
                else:
                    case_id = line
                if case_id and len(case_id) > 1:
                    key_value_pairs['Case ID'] = case_id
                    
            elif 'Gender' in line:
                if ':' in line:
                    gender = line.split(':', 1)[1].strip()
                elif '-' in line:
                    gender = line.split('-', 1)[1].strip()
                else:
                    gender = line
                if gender and len(gender) > 1:
                    key_value_pairs['Gender'] = gender
                    
            elif 'Age' in line:
                if ':' in line:
                    age = line.split(':', 1)[1].strip()
                elif '-' in line:
                    age = line.split('-', 1)[1].strip()
                else:
                    age = line
                if age and len(age) > 1:
                    key_value_pairs['Age'] = age
        
        # Create template mapping
        template_mapping = {}
        template_fields = template.get('fields', {})
        
        for field_name, field_config in template_fields.items():
            field_description = field_config.get('description', '')
            field_type = field_config.get('type', 'text')
            
            # Find the best match from extracted data
            best_match = self._find_best_field_match(field_name, field_description, field_type, key_value_pairs)
            
            if best_match:
                template_mapping[field_name] = "found_in_document"
                # Update the extracted data with the template field name
                if best_match != field_name and best_match in key_value_pairs:
                    key_value_pairs[field_name] = key_value_pairs.pop(best_match)
            else:
                template_mapping[field_name] = "not_found"
        
        # Add document metadata
        key_value_pairs["document_type"] = "Template Document"
        key_value_pairs["filename"] = filename
        key_value_pairs["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key_value_pairs["text_length"] = len(ocr_text)
        
        # Create simple summary with error indication
        if error_reason:
            summary = f"[FALLBACK MODE] Template-based extraction completed for {filename} using template '{template.get('name', 'Unknown')}' - {len(key_value_pairs)} fields mapped"
            summary += f" - ERROR: {error_reason} - For comprehensive extraction, Azure OpenAI configuration is required"
        else:
            summary = f"Template-based extraction completed for {filename} using template '{template.get('name', 'Unknown')}' - {len(key_value_pairs)} fields mapped"
            summary += " - Note: For comprehensive extraction, Azure OpenAI configuration is required"
        
        # Add error flag to key_value_pairs for detection
        if error_reason:
            key_value_pairs["_extraction_error"] = error_reason
            key_value_pairs["_extraction_method"] = "fallback"
        
        confidence_score = 0.5
        
        return ProcessingResult(
            raw_text=ocr_text,
            key_value_pairs=key_value_pairs,
            summary=summary,
            confidence_score=confidence_score,
            processing_time=0.1,
            template_mapping=template_mapping
        )
    
    def _intelligent_field_extraction(self, ocr_text: str, field_name: str, field_description: str, field_type: str) -> str:
        """Simple field extraction without regex patterns."""
        # Simple text analysis to find field values
        lines = ocr_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for field name or description in the line
            if field_name.lower() in line.lower() or field_description.lower() in line.lower():
                # Extract value after colon or dash
                if ':' in line:
                    value = line.split(':', 1)[1].strip()
                elif '-' in line:
                    value = line.split('-', 1)[1].strip()
                else:
                    value = line
                    
                if value and len(value) > 1:
                    return value
        
        # If nothing found, return a generic message
        return f"Not found in document"
    
    def _find_best_field_match(self, field_name: str, field_description: str, field_type: str, extracted_fields: Dict[str, str]) -> str:
        """Find the best match for a template field from extracted data."""
        field_name_lower = field_name.lower()
        field_description_lower = field_description.lower()
        
        # Create search terms for matching
        search_terms = []
        
        # Extract key terms from field name and description
        if 'name' in field_name_lower or 'name' in field_description_lower:
            search_terms.extend(['patient name', 'name', 'patient'])
        if 'id' in field_name_lower or 'id' in field_description_lower:
            search_terms.extend(['patient id', 'id', 'number', 'reference'])
        if 'date' in field_name_lower or 'date' in field_description_lower:
            if 'birth' in field_description_lower:
                search_terms.extend(['date of birth', 'birth', 'dob'])
            elif 'admission' in field_description_lower:
                search_terms.extend(['admission date', 'admission', 'admitted'])
            elif 'discharge' in field_description_lower:
                search_terms.extend(['discharge date', 'discharge', 'discharged'])
            else:
                search_terms.extend(['date', 'time'])
        if 'diagnosis' in field_name_lower or 'diagnosis' in field_description_lower:
            search_terms.extend(['diagnosis', 'condition', 'disease'])
        if 'physician' in field_name_lower or 'doctor' in field_description_lower:
            search_terms.extend(['doctor name', 'physician', 'doctor', 'consultant'])
        if 'treatment' in field_name_lower or 'treatment' in field_description_lower:
            search_terms.extend(['treatment', 'therapy', 'medication'])
        
        # Find the best match from extracted fields
        best_match = None
        best_score = 0
        
        for extracted_key, extracted_value in extracted_fields.items():
            extracted_key_lower = extracted_key.lower()
            
            # Calculate match score
            score = 0
            for term in search_terms:
                if term in extracted_key_lower:
                    score += 1
                if term in extracted_value.lower():
                    score += 0.5
            
            # Also check for partial matches
            for term in search_terms:
                if any(word in extracted_key_lower for word in term.split()):
                    score += 0.5
            
            if score > best_score:
                best_score = score
                best_match = extracted_key
        
        return best_match if best_score > 0 else None
    
    def classify_document_type(self, ocr_text: str) -> str:
        """
        Classify document type using LLM for intelligent analysis.
        
        Args:
            ocr_text: Raw OCR text to analyze
            
        Returns:
            Document type classification
        """
        if not self.client:
            # Fallback to simple pattern matching if no LLM available
            return self._classify_document_fallback(ocr_text)
        
        try:
            # Create classification prompt for LLM
            prompt = self._create_document_classification_prompt(ocr_text)
            
            # Get response from Azure GPT
            response = self.client.invoke(prompt)
            response_text = response.content.strip()
            
            # Parse the response
            return self._parse_classification_response(response_text)
            
        except Exception as e:
            logger.error(f"Error in LLM document classification: {e}")
            # Fallback to simple pattern matching
            return self._classify_document_fallback(ocr_text)
    
    def _create_document_classification_prompt(self, ocr_text: str) -> str:
        """Create prompt for document classification."""
        return f"""
        Analyze the following OCR text and classify the document type.
        
        IMPORTANT: Respond with ONLY the document type name, no additional text.
        
        Available document types:
        - Medical Document (discharge summaries, lab reports, prescriptions, medical records)
        - Invoice (bills, invoices, receipts, payment documents)
        - Contract (agreements, contracts, legal documents, terms and conditions)
        - Legal Document (court documents, legal notices, compliance documents)
        - Financial Document (financial statements, balance sheets, accounting documents)
        - Government Document (forms, applications, official documents)
        - Educational Document (transcripts, certificates, academic records)
        - Insurance Document (policies, claims, coverage documents)
        - Real Estate Document (deeds, leases, property documents)
        - General Document (if none of the above categories fit)
        
        OCR Text:
        {ocr_text[:3000]}...
        
        Document Type:
        """
    
    def _parse_classification_response(self, response_text: str) -> str:
        """Parse LLM classification response."""
        # Clean the response
        response_clean = response_text.strip().lower()
        
        # Map common variations to standard types
        classification_map = {
            'medical': 'Medical Document',
            'medical document': 'Medical Document',
            'invoice': 'Invoice',
            'bill': 'Invoice',
            'receipt': 'Invoice',
            'contract': 'Contract',
            'agreement': 'Contract',
            'legal': 'Legal Document',
            'legal document': 'Legal Document',
            'financial': 'Financial Document',
            'financial document': 'Financial Document',
            'government': 'Government Document',
            'government document': 'Government Document',
            'educational': 'Educational Document',
            'education': 'Educational Document',
            'insurance': 'Insurance Document',
            'real estate': 'Real Estate Document',
            'property': 'Real Estate Document',
            'general': 'General Document',
            'other': 'General Document'
        }
        
        # Find the best match
        for key, value in classification_map.items():
            if key in response_clean:
                return value
        
        # Default to General Document if no clear match
        return 'General Document'
    
    def _classify_document_fallback(self, ocr_text: str) -> str:
        """Fallback classification using simple pattern matching."""
        import re
        
        # Convert to lowercase for analysis
        text_lower = ocr_text.lower()
        
        # Medical document indicators
        medical_indicators = [
            'patient', 'diagnosis', 'treatment', 'medical', 'hospital', 'doctor', 'physician',
            'discharge', 'admission', 'lab results', 'blood test', 'prescription', 'medication',
            'symptoms', 'condition', 'health', 'clinic', 'nurse', 'medical record'
        ]
        
        # Invoice indicators
        invoice_indicators = [
            'invoice', 'bill', 'payment', 'amount', 'total', 'subtotal', 'tax', 'due date',
            'customer', 'vendor', 'invoice number', 'billing', 'payment terms', 'account',
            'balance', 'charges', 'fees', 'cost', 'price', 'receipt'
        ]
        
        # Contract indicators
        contract_indicators = [
            'contract', 'agreement', 'terms', 'conditions', 'party', 'signature', 'effective date',
            'expiration', 'legal', 'obligation', 'liability', 'warranty', 'indemnification',
            'clause', 'section', 'whereas', 'therefore', 'hereby', 'herein'
        ]
        
        # Legal document indicators
        legal_indicators = [
            'court', 'judge', 'plaintiff', 'defendant', 'case', 'lawsuit', 'legal action',
            'attorney', 'lawyer', 'counsel', 'jurisdiction', 'statute', 'regulation',
            'compliance', 'violation', 'penalty', 'fine', 'legal notice'
        ]
        
        # Financial document indicators
        financial_indicators = [
            'financial', 'statement', 'balance sheet', 'income', 'expense', 'revenue',
            'profit', 'loss', 'assets', 'liabilities', 'equity', 'cash flow',
            'audit', 'accounting', 'fiscal', 'budget', 'forecast'
        ]
        
        # Count matches for each category
        medical_score = sum(1 for indicator in medical_indicators if indicator in text_lower)
        invoice_score = sum(1 for indicator in invoice_indicators if indicator in text_lower)
        contract_score = sum(1 for indicator in contract_indicators if indicator in text_lower)
        legal_score = sum(1 for indicator in legal_indicators if indicator in text_lower)
        financial_score = sum(1 for indicator in financial_indicators if indicator in text_lower)
        
        # Find the category with the highest score
        scores = {
            'Medical Document': medical_score,
            'Invoice': invoice_score,
            'Contract': contract_score,
            'Legal Document': legal_score,
            'Financial Document': financial_score
        }
        
        max_score = max(scores.values())
        
        # If no clear classification, return generic
        if max_score == 0:
            return 'General Document'
        
        # Return the category with the highest score
        for category, score in scores.items():
            if score == max_score:
                return category
        
        return 'General Document'

class TemplateManager:
    """Manages document templates for structured extraction."""
    
    def __init__(self):
        """Initialize template manager."""
        self.templates = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default templates."""
        # Medical Document Template
        medical_template = {
            "name": "Medical Document",
            "description": "Template for medical documents like discharge summaries, lab reports, etc.",
            "fields": {
                "patient_name": {
                    "type": "text",
                    "description": "Patient's full name",
                    "required": True
                },
                "patient_id": {
                    "type": "text",
                    "description": "Patient ID or medical record number",
                    "required": True
                },
                "date_of_birth": {
                    "type": "date",
                    "description": "Patient's date of birth",
                    "required": False
                },
                "admission_date": {
                    "type": "date",
                    "description": "Date of admission",
                    "required": False
                },
                "discharge_date": {
                    "type": "date",
                    "description": "Date of discharge",
                    "required": False
                },
                "diagnosis": {
                    "type": "text",
                    "description": "Primary diagnosis",
                    "required": False
                },
                "treatment": {
                    "type": "text",
                    "description": "Treatment provided",
                    "required": False
                },
                "physician_name": {
                    "type": "text",
                    "description": "Attending physician name",
                    "required": False
                }
            }
        }
        
        # Invoice Template
        invoice_template = {
            "name": "Invoice",
            "description": "Template for invoices and billing documents",
            "fields": {
                "invoice_number": {
                    "type": "text",
                    "description": "Invoice number",
                    "required": True
                },
                "invoice_date": {
                    "type": "date",
                    "description": "Invoice date",
                    "required": True
                },
                "due_date": {
                    "type": "date",
                    "description": "Payment due date",
                    "required": False
                },
                "vendor_name": {
                    "type": "text",
                    "description": "Vendor or company name",
                    "required": True
                },
                "customer_name": {
                    "type": "text",
                    "description": "Customer or client name",
                    "required": True
                },
                "total_amount": {
                    "type": "currency",
                    "description": "Total invoice amount",
                    "required": True
                },
                "tax_amount": {
                    "type": "currency",
                    "description": "Tax amount",
                    "required": False
                },
                "payment_terms": {
                    "type": "text",
                    "description": "Payment terms",
                    "required": False
                }
            }
        }
        
        # Contract Template
        contract_template = {
            "name": "Contract",
            "description": "Template for contracts and legal documents",
            "fields": {
                "contract_number": {
                    "type": "text",
                    "description": "Contract number",
                    "required": True
                },
                "contract_date": {
                    "type": "date",
                    "description": "Contract date",
                    "required": True
                },
                "effective_date": {
                    "type": "date",
                    "description": "Effective date",
                    "required": False
                },
                "expiration_date": {
                    "type": "date",
                    "description": "Expiration date",
                    "required": False
                },
                "party_a": {
                    "type": "text",
                    "description": "First party name",
                    "required": True
                },
                "party_b": {
                    "type": "text",
                    "description": "Second party name",
                    "required": True
                },
                "contract_value": {
                    "type": "currency",
                    "description": "Contract value",
                    "required": False
                },
                "contract_type": {
                    "type": "text",
                    "description": "Type of contract",
                    "required": False
                }
            }
        }
        
        self.templates = {
            "medical_document": medical_template,
            "invoice": invoice_template,
            "contract": contract_template
        }
        
        logger.info(f"Loaded {len(self.templates)} default templates")
    
    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Get template by name."""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List available template names."""
        return list(self.templates.keys())
    
    def get_template_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get template information without fields."""
        template = self.templates.get(name)
        if template:
            return {
                "name": template["name"],
                "description": template["description"],
                "field_count": len(template.get("fields", {}))
            }
        return None
    
    def add_template(self, name: str, template: Dict[str, Any]) -> bool:
        """Add a new template."""
        try:
            if self.validate_template(template):
                self.templates[name] = template
                logger.info(f"Added template: {name}")
                return True
        except Exception as e:
            logger.error(f"Failed to add template {name}: {e}")
        return False
    
    def validate_template(self, template: Dict[str, Any]) -> bool:
        """Validate template structure."""
        required_fields = ['name', 'description', 'fields']
        return all(field in template for field in required_fields)
