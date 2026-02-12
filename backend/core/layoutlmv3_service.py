import logging
import os
import re
from typing import Dict, Any, List, Optional
from PIL import Image
# import torch
# from transformers import AutoProcessor, AutoModelForTokenClassification
from utility.config import Config

logger = logging.getLogger(__name__)


class LayoutLMv3Service:
    """Service for using LayoutLMv3 to find and understand text in documents."""

    def __init__(self):
        """Initialize LayoutLMv3 service."""
        self.model_name = "microsoft/layoutlmv3-large"
        self.processor = None
        self.model = None
        # self.device = torch.device("cuda" if torch.cud-is_available() else "cpu")
        self.device = "cpu" # Default to CPU
        self._initialized = False

        # Skip model initialization - we use OCR data from Azure Document Intelligence instead
        # LayoutLMv3 requires tesseract which may not be installed
        # The service is still "available" if HF_TOKEN is set, but we won't load the model
        if Config.HF_TOKEN:
            logger.info("LayoutLMv3 service available (using OCR data, not model)")
            self._initialized = True  # Mark as available but don't load model
        else:
            logger.warning("HF_TOKEN not set - LayoutLMv3 service unavailable")

    def _initialize_model(self):
        """Initialize the LayoutLMv3 model and processor."""
        if self._initialized:
            return

        try:
            logger.info(f"Initializing LayoutLMv3 model: {self.model_name}")
            logger.info(f"Using device: {self.device}")
            logger.info("Note: LayoutLMv3 initialization is optional - we primarily use OCR data from Azure Document Intelligence")

            # Note: We don't actually need to initialize LayoutLMv3 for text finding
            # since we use OCR data from Azure Document Intelligence instead
            # The model initialization is kept for potential future use but won't be used for OCR
            # as it requires tesseract which may not be installed

            # Skip initialization to avoid tesseract requirement
            # If you need LayoutLMv3 for other tasks, you can enable this:
            # from transformers import AutoProcessor, AutoModelForTokenClassification
            # self.processor = AutoProcessor.from_pretrained(
            #     self.model_name,
            #     token=Config.HF_TOKEN,
            #     trust_remote_code=True
            # )
            # self.model = AutoModelForTokenClassification.from_pretrained(
            #     self.model_name,
            #     token=Config.HF_TOKEN,
            #     trust_remote_code=True
            # )
            # self.model.to(self.device)
            # self.model.eval()

            # For now, mark as initialized but don't actually load (we use OCR data instead)
            self._initialized = True
            logger.info("LayoutLMv3 service marked as available (using OCR data instead of model)")

        except Exception as e:
            logger.error(f"Error initializing LayoutLMv3 model: {e}")
            # Don't raise - we can still use OCR data
            self._initialized = False

    def is_service_available(self) -> bool:
        """Check if the service is available."""
        # Service is available if we have HF_TOKEN (we use OCR data, not the model)
        return Config.HF_TOKEN is not None and Config.HF_TOKEN != ""

    def find_text_in_document(
        self,
        image: Image.Image,
        search_text: str,
        ocr_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find text in a document image using OCR data (preferred) or LayoutLMv3.

        Args:
            image: PIL Image object of the document (not used if OCR data is available)
            search_text: Text to search for
            ocr_data: Optional OCR data with bounding boxes from Azure Document Intelligence

        Returns:
            List of dictionaries with bounding box information:
            [{
                'bbox': [x1, y1, x2, y2, x3, y3, x4, y4],
                'text': 'matched text',
                'confidence': 0.95,
                'page': 1
            }]
        """
        # Always prefer OCR data - it's more accurate and doesn't require tesseract
        if ocr_data:
            logger.info("Using OCR data for text finding (preferred method - no tesseract required)")
            try:
                return self._find_text_from_ocr_data(search_text, ocr_data)
            except Exception as e:
                logger.error(f"Error finding text in OCR data: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return []

        # If no OCR data, we can't find text accurately without bounding boxes
        # LayoutLMv3 requires tesseract for OCR which may not be installed
        logger.warning("No OCR data available - cannot find text without bounding boxes. LayoutLMv3 requires tesseract which is not installed.")
        return []

    def _find_text_from_ocr_data(
        self,
        search_text: str,
        ocr_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find text using OCR data (from Azure Document Intelligence).
        This provides accurate bounding boxes.
        """
        if not ocr_data or not search_text:
            return []

        boxes = []
        search_text_lower = search_text.lower().strip()

        # Extract just the value part if it's in "Key: Value" format
        # Remove common key prefixes like "Hospital Name: ", "Patient Name: ", etc.
        # Pattern to match "Key: Value" format and extract just the value
        key_value_pattern = r'^[^:]+:\s*(.+)$'
        match = re.match(key_value_pattern, search_text_lower)
        if match:
            search_text_lower = match.group(1).strip()
            logger.info(f"Extracted value from key-value pair: '{search_text_lower}'")

        # Normalize search text
        def normalize_text(text):
            if not text:
                return ''
            # Remove punctuation and normalize whitespace
            text = re.sub(r'[.,;:!?\'"`]', '', text.lower())
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        normalized_search = normalize_text(search_text_lower)

        # Extract text blocks from OCR data
        text_blocks = []
        if isinstance(ocr_data, list):
            for page_result in ocr_data:
                if isinstance(page_result, dict):
                    if 'text_blocks' in page_result:
                        text_blocks.extend(page_result['text_blocks'])
                    elif 'positioning_data' in page_result:
                        pos_data = page_result['positioning_data']
                        if isinstance(pos_data, list):
                            text_blocks.extend(pos_data)
                        elif isinstance(pos_data, dict) and 'text_blocks' in pos_data:
                            text_blocks.extend(pos_data['text_blocks'])
                    elif 'words' in page_result or 'lines' in page_result:
                        # Direct page result with words/lines
                        text_blocks.append(page_result)
        elif isinstance(ocr_data, dict):
            if 'text_blocks' in ocr_data:
                text_blocks = ocr_data['text_blocks']
            elif 'positioning_data' in ocr_data:
                pos_data = ocr_data['positioning_data']
                if isinstance(pos_data, list):
                    text_blocks = pos_data
                elif isinstance(pos_data, dict) and 'text_blocks' in pos_data:
                    text_blocks = pos_data['text_blocks']
            elif 'words' in ocr_data or 'lines' in ocr_data:
                # Single block structure
                text_blocks = [ocr_data]

        logger.info(f"Searching for text: '{search_text}' (normalized: '{normalized_search}') in {len(text_blocks)} text blocks")

        search_words = normalized_search.split()
        logger.info(f"Search words: {len(search_words)} words")

        # For very long text (100+ words), use a different strategy - match first 20 words
        if len(search_words) > 100:
            logger.info(f"Very long search text ({len(search_words)} words), using first 20 words for matching")
            search_words = search_words[:20]
            normalized_search = ' '.join(search_words)

        # Search through words and lines
        for block_idx, block in enumerate(text_blocks):
            words = block.get('words', [])
            lines = block.get('lines', [])
            page_number = block.get('page_number', block.get('page', 1))
            page_width = block.get('width', 1)
            page_height = block.get('height', 1)

            logger.debug(f"Block {block_idx}: {len(lines)} lines, {len(words)} words, page {page_number}")

            # Strategy 1: Search for exact phrase match using word sequences (most accurate)
            if len(search_words) > 0:
                # Try to find consecutive words that match the search phrase exactly
                best_match = None
                best_match_score = 0

                # For phone numbers and similar text, we need to match character-by-character or use substring matching
                # First, try exact word sequence matching
                if len(search_words) > 1:
                    for start_idx in range(len(words) - len(search_words) + 1):
                        # Check if the next N words match our search phrase exactly
                        word_sequence = []
                        word_bboxes_sequence = []
                        match_count = 0

                        for i in range(len(search_words)):
                            if start_idx + i < len(words):
                                word_obj = words[start_idx + i]
                                word_text = word_obj.get('text', '')
                                normalized_word = normalize_text(word_text)

                                if normalized_word == search_words[i]:
                                    word_sequence.append(word_text)
                                    bbox = word_obj.get('bounding_box')
                                    if bbox:
                                        bbox_array = self._parse_bbox(bbox)
                                        if bbox_array:
                                            word_bboxes_sequence.append(bbox_array)
                                    match_count += 1
                                else:
                                    break

                        # If all words matched exactly, we found the phrase
                        if match_count == len(search_words) and word_bboxes_sequence and len(word_bboxes_sequence) == len(search_words):
                            # Verify words are actually consecutive by checking bounding box positions
                            # Words should be in left-to-right order with reasonable spacing
                            is_consecutive = True
                            for i in range(len(word_bboxes_sequence) - 1):
                                curr_bbox = word_bboxes_sequence[i]
                                next_bbox = word_bboxes_sequence[i + 1]

                                # Get right edge of current word and left edge of next word
                                curr_right = max(curr_bbox[0], curr_bbox[2]) if len(curr_bbox) >= 4 else curr_bbox[0]
                                next_left = min(next_bbox[0], next_bbox[2]) if len(next_bbox) >= 4 else next_bbox[0]

                                # Check if next word is to the right of current word (with some tolerance)
                                # Allow a small gap (e.g., up to 20 pixels) for natural word spacing, but not too much
                                if next_left < curr_right - 10 or next_left > curr_right + 50: # Adjust tolerance here
                                    is_consecutive = False
                                    break

                            if not is_consecutive:
                                logger.debug(f"Skipping non-consecutive word sequence: {' '.join(word_sequence)}")
                                continue

                            # Calculate bounding box dynamically based on actual word positions
                            word_boxes_with_pos = []
                            for i, bbox_arr in enumerate(word_bboxes_sequence):
                                if len(bbox_arr) >= 8:
                                    x_coords = [bbox_arr[0], bbox_arr[2], bbox_arr[4], bbox_arr[6]]
                                    y_coords = [bbox_arr[1], bbox_arr[3], bbox_arr[5], bbox_arr[7]]
                                    left_x = min(x_coords)
                                    right_x = max(x_coords)
                                elif len(bbox_arr) >= 4:
                                    left_x = min(bbox_arr[0], bbox_arr[2])
                                    right_x = max(bbox_arr[0], bbox_arr[2])
                                    y_coords = [bbox_arr[1], bbox_arr[3]]
                                else:
                                    continue

                                word_boxes_with_pos.append({
                                    'left': left_x,
                                    'right': right_x,
                                    'bbox': bbox_arr,
                                    'y_coords': y_coords if 'y_coords' in locals() else [bbox_arr[1], bbox_arr[3]]
                                })

                            # Sort by left x-coordinate
                            word_boxes_with_pos.sort(key=lambda w: w['left'])

                            if word_boxes_with_pos:
                                # Get boundaries from first and last words
                                min_x = word_boxes_with_pos[0]['left']
                                max_x = word_boxes_with_pos[-1]['right']

                                all_y = []
                                for w in word_boxes_with_pos:
                                    all_y.extend(w['y_coords'])
                                min_y = min(all_y)
                                max_y = max(all_y)

                                if max_x > min_x and max_y > min_y:
                                    # Validate: calculate expected width dynamically based on actual word sizes
                                    matched_text = ' '.join(word_sequence)

                                    # Calculate average character width from actual word boxes
                                    total_word_width = sum(w['right'] - w['left'] for w in word_boxes_with_pos)
                                    total_word_chars = sum(len(word) for word in word_sequence)
                                    avg_char_width = total_word_width / total_word_chars if total_word_chars > 0 else 8

                                    # Account for spaces between words
                                    num_spaces = len(word_sequence) - 1
                                    space_width = avg_char_width * 0.5
                                    expected_width = total_word_width + (num_spaces * space_width)

                                    actual_width = max_x - min_x

                                    # Allow tolerance for spacing variations, but reject if too large
                                    # Reduced tolerance for tighter fit (1.3x instead of 1.5x)
                                    if actual_width > expected_width * 1.3:
                                        logger.debug(f"Skipping short phrase match - box too wide (stricter): actual={actual_width:.1f}, expected={expected_width:.1f}, text='{matched_text[:50]}'")
                                        continue

                                    # Create precise bounding box - dynamically sized to match text
                                    combined_bbox = [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y]
                                    # Score: prefer matches with all words and tighter boxes
                                    box_width = max_x - min_x
                                    box_height = max_y - min_y
                                    match_score = len(word_bboxes_sequence) * 1000 - box_width - box_height

                                    if match_score > best_match_score:
                                        best_match = {
                                            'bbox': combined_bbox,
                                            'text': ' '.join(word_sequence),
                                            'confidence': 0.95,
                                            'page': page_number,
                                            'width': page_width,
                                            'height': page_height
                                        }
                                        best_match_score = match_score
                                        logger.debug(f"Short phrase match candidate: '{' '.join(word_sequence)}' (score: {match_score}, bbox: [{min_x:.1f}, {min_y:.1f}, {max_x:.1f}, {max_y:.1f}], width={box_width:.1f})")

                if best_match:
                    logger.info(f"Found phrase match on page {page_number}: '{best_match['text']}' (searching for: '{normalized_search}')")
                    boxes.append(best_match)
                    # Don't continue to other strategies if we found a match
                    continue

                # Strategy 1b: For phone numbers and text with special characters, find exact substring match
                # This handles cases where the text might span multiple words but we need exact match
                if not best_match: # Only run if no exact word sequence match was found
                    # Try to find the search text as a substring in lines, then get exact word bounding boxes
                    for line_idx, line in enumerate(lines):
                        line_text = line.get('text', '')
                        if not line_text:
                            continue

                        normalized_line = normalize_text(line_text)

                        # Check if the search text appears in this line
                        if normalized_search in normalized_line:
                            # Find character positions in normalized line
                            search_start = normalized_line.find(normalized_search)
                            search_end = search_start + len(normalized_search)

                            # Map back to actual words by building character positions
                            # Use a more precise method that accounts for actual word boundaries
                            line_words = line_text.split()
                            matching_word_indices = []

                            # Build character position map with word boundaries
                            # Track where each word starts and ends in the normalized line
                            word_boundaries = []
                            char_pos = 0
                            for word_idx, word in enumerate(line_words):
                                normalized_word = normalize_text(word)
                                word_start = char_pos
                                word_end = char_pos + len(normalized_word)
                                word_boundaries.append({
                                    'idx': word_idx,
                                    'start': word_start,
                                    'end': word_end,
                                    'word': word,
                                    'normalized': normalized_word
                                })
                                char_pos = word_end + 1  # +1 for space after word

                            # Find words that are COMPLETELY within the search range
                            # A word is included only if it's fully contained in the search text
                            words_in_range = []
                            for boundary in word_boundaries:
                                # Word is included if:
                                # 1. Word starts at or after search_start
                                # 2. Word ends at or before search_end
                                # 3. Word is fully contained in the search range
                                if boundary['start'] >= search_start and boundary['end'] <= search_end:
                                    words_in_range.append(boundary['idx'])

                            # If no words are fully contained, try to find words that overlap significantly
                            # (at least 70% of the word must be in the search range - stricter to avoid extra words)
                            if not words_in_range:
                                for boundary in word_boundaries:
                                    overlap_start = max(boundary['start'], search_start)
                                    overlap_end = min(boundary['end'], search_end)
                                    if overlap_start < overlap_end:
                                        overlap_length = overlap_end - overlap_start
                                        word_length = boundary['end'] - boundary['start']
                                        # Include if at least 70% of word overlaps (stricter threshold)
                                        if overlap_length >= word_length * 0.7:
                                            words_in_range.append(boundary['idx'])

                            matching_word_indices = sorted(list(set(words_in_range)))

                            # Verify these words actually contain the search text
                            if matching_word_indices:
                                # Try to find the minimal set of words that contain the search text
                                # Start with the words in range and verify they contain the search text
                                words_text = ' '.join([line_words[i] for i in matching_word_indices])
                                normalized_words_text = normalize_text(words_text)

                                # Check if search text is in these words
                                if normalized_search in normalized_words_text:
                                    # Try to find a tighter match - only include words that are necessary
                                    # Find the start and end positions of the search text in the normalized words
                                    search_pos_in_words = normalized_words_text.find(normalized_search)
                                    tight_word_indices = matching_word_indices  # Default to all matching words

                                    if search_pos_in_words != -1:
                                        # Calculate which words are actually needed
                                        char_count = 0
                                        start_word_idx = 0
                                        end_word_idx = len(matching_word_indices) - 1

                                        # Find the starting word
                                        for i, word_idx in enumerate(matching_word_indices):
                                            word = line_words[word_idx]
                                            normalized_word = normalize_text(word)
                                            if char_count <= search_pos_in_words < char_count + len(normalized_word) + 1:
                                                start_word_idx = i
                                                break
                                            char_count += len(normalized_word) + 1

                                        # Find the ending word
                                        char_count = 0
                                        search_end_in_words = search_pos_in_words + len(normalized_search)
                                        for i, word_idx in enumerate(matching_word_indices):
                                            word = line_words[word_idx]
                                            normalized_word = normalize_text(word)
                                            word_end = char_count + len(normalized_word)
                                            if char_count <= search_end_in_words <= word_end:
                                                end_word_idx = i
                                                break
                                            char_count += len(normalized_word) + 1

                                        # Use only the words from start to end (inclusive)
                                        tight_word_indices = matching_word_indices[start_word_idx:end_word_idx + 1]

                                    # Get bounding boxes for ONLY these tight matching words
                                    word_bboxes_for_match = []
                                    actual_matched_words = []

                                    # Match words in order, ensuring they are consecutive
                                    prev_word_idx_in_ocr = -1
                                    for word_idx in tight_word_indices:
                                        if word_idx < len(line_words):
                                            word_text = line_words[word_idx]
                                            # Find this exact word in the words array - match by position and text
                                            found_word = False

                                            # Start searching from where we left off to maintain order
                                            search_start_in_ocr = max(0, prev_word_idx_in_ocr + 1) if prev_word_idx_in_ocr >= 0 else 0

                                            for i in range(search_start_in_ocr, len(words)):
                                                word_obj = words[i]
                                                obj_text = word_obj.get('text', '').strip()
                                                # Match by normalized text
                                                if normalize_text(obj_text) == normalize_text(word_text):
                                                    bbox = word_obj.get('bounding_box')
                                                    if bbox:
                                                        bbox_array = self._parse_bbox(bbox)
                                                        if bbox_array:
                                                            # Verify words are consecutive (or at least close)
                                                            # Allow small gaps (up to 1 word) for OCR spacing issues - stricter
                                                            if prev_word_idx_in_ocr >= 0:
                                                                gap = i - prev_word_idx_in_ocr - 1
                                                                if gap > 1:
                                                                    # Gap too large, might be wrong word instance - skip
                                                                    continue

                                                            word_bboxes_for_match.append(bbox_array)
                                                            actual_matched_words.append(word_text)
                                                            prev_word_idx_in_ocr = i
                                                            found_word = True
                                                            break

                                            # If we didn't find the word, skip it to avoid including wrong words
                                            if not found_word:
                                                logger.debug(f"Could not find bounding box for word: '{word_text}' at position {word_idx}")
                                                break  # Stop if we can't find a word - ensures accuracy

                                    # Only create bounding box if we found word boxes for ALL tight matching words
                                    # This ensures we only highlight the exact matched text, not surrounding words
                                    if word_bboxes_for_match and len(word_bboxes_for_match) == len(tight_word_indices):
                                        # Calculate bounding box dynamically based on actual word positions
                                        # Sort words by their x-coordinate to ensure proper order
                                        word_boxes_with_pos = []
                                        for i, bbox_arr in enumerate(word_bboxes_for_match[:len(tight_word_indices)]):
                                            if len(bbox_arr) >= 8:
                                                x_coords = [bbox_arr[0], bbox_arr[2], bbox_arr[4], bbox_arr[6]]
                                                y_coords = [bbox_arr[1], bbox_arr[3], bbox_arr[5], bbox_arr[7]]
                                                left_x = min(x_coords)
                                                right_x = max(x_coords)
                                            elif len(bbox_arr) >= 4:
                                                left_x = min(bbox_arr[0], bbox_arr[2])
                                                right_x = max(bbox_arr[0], bbox_arr[2])
                                                y_coords = [bbox_arr[1], bbox_arr[3]]
                                            else:
                                                continue

                                            word_boxes_with_pos.append({
                                                'left': left_x,
                                                'right': right_x,
                                                'bbox': bbox_arr,
                                                'y_coords': y_coords if 'y_coords' in locals() else [bbox_arr[1], bbox_arr[3]]
                                            })

                                        # Sort by left x-coordinate to process words in order
                                        word_boxes_with_pos.sort(key=lambda w: w['left'])

                                        if word_boxes_with_pos:
                                            # Get the leftmost and rightmost edges from the first and last words
                                            min_x = word_boxes_with_pos[0]['left']
                                            max_x = word_boxes_with_pos[-1]['right']

                                            # Get min/max y from all words
                                            all_y = []
                                            for w in word_boxes_with_pos:
                                                all_y.extend(w['y_coords'])
                                            min_y = min(all_y)
                                            max_y = max(all_y)

                                            if max_x > min_x and max_y > min_y:
                                                # Validate: ensure bounding box matches text content size dynamically
                                                matched_text = ' '.join(actual_matched_words)

                                                # Calculate expected width based on actual word widths from OCR
                                                total_word_width = sum(w['right'] - w['left'] for w in word_boxes_with_pos)
                                                total_word_chars = sum(len(word) for word in actual_matched_words)
                                                avg_char_width = total_word_width / total_word_chars if total_word_chars > 0 else 8

                                                # Account for spaces between words (typically 0.5 character width)
                                                num_spaces = len(actual_matched_words) - 1
                                                space_width = avg_char_width * 0.5
                                                expected_width = total_word_width + (num_spaces * space_width)

                                                actual_width = max_x - min_x

                                                # Allow tolerance (1.3x) for natural spacing variations
                                                # But reject if way too large (might include extra content)
                                                if actual_width > expected_width * 1.3:
                                                    logger.debug(f"Skipping match - box too wide (stricter): actual={actual_width:.1f}, expected={expected_width:.1f}, text='{matched_text[:50]}'")
                                                    continue

                                                # Create precise bounding box - dynamically sized to match text content
                                                # Use exact word boundaries, no extra padding
                                                combined_bbox = [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y]

                                                # Score: prefer matches with exact word count and minimal box size
                                                box_width = max_x - min_x
                                                box_height = max_y - min_y
                                                match_score = len(word_bboxes_for_match) * 1000 - box_width - box_height

                                                if match_score > best_match_score:
                                                    best_match = {
                                                        'bbox': combined_bbox,
                                                        'text': ' '.join(actual_matched_words),
                                                        'confidence': 0.9,
                                                        'page': page_number,
                                                        'width': page_width,
                                                        'height': page_height
                                                    }
                                                    best_match_score = match_score
                                                    logger.debug(f"Substring match in line: '{best_match['text']}' (words: {len(actual_matched_words)}), bbox: [{min_x:.1f}, {min_y:.1f}, {max_x:.1f}, {max_y:.1f}], width={box_width:.1f}, height={box_height:.1f}")

                    if best_match:
                        logger.info(f"Found phrase match on page {page_number}: '{best_match['text']}' (searching for: '{normalized_search}')")
                        boxes.append(best_match)
                        # Don't continue to other strategies if we found a match
                        continue

                # Strategy 2: For long text (20+ words), use substring matching with first portion
                # This strategy is designed to find matches in long blocks of text
                if len(search_words) > 20 and not boxes:
                    # For very long text, match the first portion (first 15 words)
                    search_prefix = ' '.join(search_words[:15])
                    logger.info(f"Long text search - using first 15 words: '{search_prefix}'")

                    best_long_match = None
                    best_long_score = 0

                    for line_idx, line in enumerate(lines):
                        line_text = line.get('text', '')
                        if not line_text:
                            continue

                        normalized_line = normalize_text(line_text)

                        # Check if the prefix appears in this line
                        if search_prefix in normalized_line:
                            # Find the position
                            prefix_start = normalized_line.find(search_prefix)
                            prefix_end = prefix_start + len(search_prefix)

                            # Map to words
                            line_words = line_text.split()
                            char_to_word = {}
                            char_pos = 0
                            for word_idx, word in enumerate(line_words):
                                normalized_word = normalize_text(word)
                                for i in range(len(normalized_word)):
                                    if char_pos + i < len(normalized_line):
                                        char_to_word[char_pos + i] = word_idx
                                char_pos += len(normalized_word) + 1

                            # Get words in range
                            words_in_range = set()
                            for char_idx in range(prefix_start, min(prefix_end, len(normalized_line))):
                                if char_idx in char_to_word:
                                    words_in_range.add(char_to_word[char_idx])

                            matching_word_indices = sorted(list(words_in_range))

                            if matching_word_indices:
                                # Get bounding boxes for these words
                                word_bboxes_long = []
                                actual_words_long = []

                                prev_word_idx_in_ocr = -1
                                for word_idx in matching_word_indices:
                                    if word_idx < len(line_words):
                                        word_text = line_words[word_idx]
                                        found_word = False
                                        search_start_in_ocr = max(0, prev_word_idx_in_ocr + 1) if prev_word_idx_in_ocr >= 0 else 0

                                        for i in range(search_start_in_ocr, len(words)):
                                            word_obj = words[i]
                                            obj_text = word_obj.get('text', '').strip()
                                            if normalize_text(obj_text) == normalize_text(word_text):
                                                if prev_word_idx_in_ocr >= 0:
                                                    gap = i - prev_word_idx_in_ocr - 1
                                                    if gap > 1: # Stricter gap for long text
                                                        continue

                                                bbox = word_obj.get('bounding_box')
                                                if bbox:
                                                    bbox_array = self._parse_bbox(bbox)
                                                    if bbox_array:
                                                        word_bboxes_long.append(bbox_array)
                                                        actual_words_long.append(word_text)
                                                        prev_word_idx_in_ocr = i
                                                        found_word = True
                                                        break
                                        if not found_word:
                                            logger.debug(f"Could not find bounding box for word (long text): '{word_text}'")
                                            break # Stop if a word is missing

                                if word_bboxes_long and len(word_bboxes_long) == len(matching_word_indices):
                                    # Calculate bounding box dynamically for long text
                                    word_boxes_with_pos_long = []
                                    for i, bbox_arr in enumerate(word_bboxes_long):
                                        if len(bbox_arr) >= 8:
                                            x_coords = [bbox_arr[0], bbox_arr[2], bbox_arr[4], bbox_arr[6]]
                                            y_coords = [bbox_arr[1], bbox_arr[3], bbox_arr[5], bbox_arr[7]]
                                            left_x = min(x_coords)
                                            right_x = max(x_coords)
                                        elif len(bbox_arr) >= 4:
                                            left_x = min(bbox_arr[0], bbox_arr[2])
                                            right_x = max(bbox_arr[0], bbox_arr[2])
                                            y_coords = [bbox_arr[1], bbox_arr[3]]
                                        else:
                                            continue

                                        word_boxes_with_pos_long.append({
                                            'left': left_x,
                                            'right': right_x,
                                            'bbox': bbox_arr,
                                            'y_coords': y_coords if 'y_coords' in locals() else [bbox_arr[1], bbox_arr[3]]
                                        })

                                    word_boxes_with_pos_long.sort(key=lambda w: w['left'])

                                    if word_boxes_with_pos_long:
                                        min_x_long = word_boxes_with_pos_long[0]['left']
                                        max_x_long = word_boxes_with_pos_long[-1]['right']

                                        all_y_long = []
                                        for w in word_boxes_with_pos_long:
                                            all_y_long.extend(w['y_coords'])
                                        min_y_long = min(all_y_long)
                                        max_y_long = max(all_y_long)

                                        if max_x_long > min_x_long and max_y_long > min_y_long:
                                            matched_text_long = ' '.join(actual_words_long)
                                            total_word_width_long = sum(w['right'] - w['left'] for w in word_boxes_with_pos_long)
                                            total_word_chars_long = sum(len(word) for word in actual_words_long)
                                            avg_char_width_long = total_word_width_long / total_word_chars_long if total_word_chars_long > 0 else 8
                                            num_spaces_long = len(actual_words_long) - 1
                                            space_width_long = avg_char_width_long * 0.5
                                            expected_width_long = total_word_width_long + (num_spaces_long * space_width_long)
                                            actual_width_long = max_x_long - min_x_long

                                            if actual_width_long > expected_width_long * 1.3: # Stricter tolerance
                                                logger.debug(f"Skipping long phrase match - box too wide (stricter): actual={actual_width_long:.1f}, expected={expected_width_long:.1f}, text='{matched_text_long[:50]}'")
                                                continue

                                            combined_bbox_long = [min_x_long, min_y_long, max_x_long, min_y_long, max_x_long, max_y_long, min_x_long, max_y_long]

                                            long_match_score = len(word_bboxes_long) * 1000 - actual_width_long - (max_y_long - min_y_long)

                                            if long_match_score > best_long_score:
                                                best_long_match = {
                                                    'bbox': combined_bbox_long,
                                                    'text': matched_text_long,
                                                    'confidence': 0.85,
                                                    'page': page_number,
                                                    'width': page_width,
                                                    'height': page_height
                                                }
                                                best_long_score = long_match_score
                                                logger.debug(f"Long phrase match candidate: '{matched_text_long[:50]}...' (score: {long_match_score}, bbox: [{min_x_long:.1f}, {min_y_long:.1f}, {max_x_long:.1f}, {max_y_long:.1f}], width={actual_width_long:.1f})")
                    if best_long_match:
                        logger.info(f"Found long phrase match on page {page_number}: '{best_long_match['text'][:50]}...' (searching for: '{normalized_search}')")
                        boxes.append(best_long_match)
                        continue


                # Strategy 3: Search for single word or short phrase matches (2-3 words)
                if len(search_words) <= 3 and not boxes: # Only run if no better match found yet
                    # For short searches, find exact word matches
                    if len(search_words) == 1:
                        search_word = search_words[0]
                        best_single_word_match = None
                        best_single_word_confidence = 0

                        # First try to find exact word match
                        for word_idx, word in enumerate(words):
                            word_text = word.get('text', '')
                            if not word_text:
                                continue

                            normalized_word = normalize_text(word_text)

                            # Exact match is best
                            if normalized_word == search_word:
                                bbox = word.get('bounding_box')
                                if bbox:
                                    bbox_array = self._parse_bbox(bbox)
                                    if bbox_array and len(bbox_array) >= 4:
                                        confidence = word.get('confidence', 0.9)
                                        if confidence > best_single_word_confidence:
                                            best_single_word_match = {
                                                'bbox': bbox_array,
                                                'text': word_text,
                                                'confidence': confidence,
                                                'page': page_number,
                                                'width': page_width,
                                                'height': page_height
                                            }
                                            best_single_word_confidence = confidence

                        # If exact match found, use it
                        if best_single_word_match:
                            logger.info(f"Found exact single word match on page {page_number}: '{best_single_word_match['text']}'")
                            boxes.append(best_single_word_match)
                            continue

                    # For 2-3 word phrases, try to find consecutive matches
                    if len(search_words) >= 2 and len(search_words) <= 3:
                        best_short_phrase_match = None
                        best_short_phrase_score = 0

                        for start_idx in range(len(words) - len(search_words) + 1):
                            word_sequence = []
                            word_bboxes_sequence = []
                            match_count = 0

                            # Check if words are consecutive (no gaps)
                            for i in range(len(search_words)):
                                if start_idx + i < len(words):
                                    word_obj = words[start_idx + i]
                                    word_text = word_obj.get('text', '')
                                    normalized_word = normalize_text(word_text)

                                    if normalized_word == search_words[i]:
                                        word_sequence.append(word_text)
                                        bbox = word_obj.get('bounding_box')
                                        if bbox:
                                            bbox_array = self._parse_bbox(bbox)
                                            if bbox_array:
                                                word_bboxes_sequence.append(bbox_array)
                                        match_count += 1
                                    else:
                                        break

                            # If all words matched exactly AND they are consecutive, create tight bounding box
                            if match_count == len(search_words) and word_bboxes_sequence and len(word_bboxes_sequence) == len(search_words):
                                # Verify words are actually consecutive by checking bounding box positions
                                is_consecutive = True
                                for i in range(len(word_bboxes_sequence) - 1):
                                    curr_bbox = word_bboxes_sequence[i]
                                    next_bbox = word_bboxes_sequence[i + 1]

                                    curr_right = max(curr_bbox[0], curr_bbox[2]) if len(curr_bbox) >= 4 else curr_bbox[0]
                                    next_left = min(next_bbox[0], next_bbox[2]) if len(next_bbox) >= 4 else next_bbox[0]

                                    if next_left < curr_right - 10 or next_left > curr_right + 50: # Same tolerance as before
                                        is_consecutive = False
                                        break

                                if not is_consecutive:
                                    logger.debug(f"Skipping non-consecutive short phrase: {' '.join(word_sequence)}")
                                    continue

                                # Calculate bounding box dynamically based on actual word positions
                                word_boxes_with_pos = []
                                for i, bbox_arr in enumerate(word_bboxes_sequence):
                                    if len(bbox_arr) >= 8:
                                        x_coords = [bbox_arr[0], bbox_arr[2], bbox_arr[4], bbox_arr[6]]
                                        y_coords = [bbox_arr[1], bbox_arr[3], bbox_arr[5], bbox_arr[7]]
                                        left_x = min(x_coords)
                                        right_x = max(x_coords)
                                    elif len(bbox_arr) >= 4:
                                        left_x = min(bbox_arr[0], bbox_arr[2])
                                        right_x = max(bbox_arr[0], bbox_arr[2])
                                        y_coords = [bbox_arr[1], bbox_arr[3]]
                                    else:
                                        continue

                                    word_boxes_with_pos.append({
                                        'left': left_x,
                                        'right': right_x,
                                        'bbox': bbox_arr,
                                        'y_coords': y_coords if 'y_coords' in locals() else [bbox_arr[1], bbox_arr[3]]
                                    })

                                word_boxes_with_pos.sort(key=lambda w: w['left'])

                                if word_boxes_with_pos:
                                    min_x = word_boxes_with_pos[0]['left']
                                    max_x = word_boxes_with_pos[-1]['right']

                                    all_y = []
                                    for w in word_boxes_with_pos:
                                        all_y.extend(w['y_coords'])
                                    min_y = min(all_y)
                                    max_y = max(all_y)

                                    if max_x > min_x and max_y > min_y:
                                        matched_text = ' '.join(word_sequence)

                                        total_word_width = sum(w['right'] - w['left'] for w in word_boxes_with_pos)
                                        total_word_chars = sum(len(word) for word in word_sequence)
                                        avg_char_width = total_word_width / total_word_chars if total_word_chars > 0 else 8
                                        num_spaces = len(word_sequence) - 1
                                        space_width = avg_char_width * 0.5
                                        expected_width = total_word_width + (num_spaces * space_width)
                                        actual_width = max_x - min_x

                                        if actual_width > expected_width * 1.3: # Stricter tolerance
                                            logger.debug(f"Skipping short phrase match - box too wide (stricter): actual={actual_width:.1f}, expected={expected_width:.1f}, text='{matched_text[:50]}'")
                                            continue

                                        combined_bbox = [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y]
                                        box_width = max_x - min_x
                                        box_height = max_y - min_y
                                        match_score = len(word_bboxes_sequence) * 1000 - box_width - box_height

                                        if match_score > best_short_phrase_score:
                                            best_short_phrase_match = {
                                                'bbox': combined_bbox,
                                                'text': ' '.join(word_sequence),
                                                'confidence': 0.95,
                                                'page': page_number,
                                                'width': page_width,
                                                'height': page_height
                                            }
                                            best_short_phrase_score = match_score
                                            logger.debug(f"Short phrase match candidate: '{' '.join(word_sequence)}' (score: {match_score}, bbox: [{min_x:.1f}, {min_y:.1f}, {max_x:.1f}, {max_y:.1f}], width={box_width:.1f})")

                        if best_short_phrase_match:
                            logger.info(f"Found short phrase match on page {page_number}: '{best_short_phrase_match['text']}'")
                            boxes.append(best_short_phrase_match)
                            continue  # Found match, don't try other strategies

            logger.info(f"Found {len(boxes)} matching bounding boxes for text: '{search_text}'")

            # If we found multiple matches, prefer the most accurate one
            # For exact phrase matches, prefer those with word-level bounding boxes
            if len(boxes) > 1:
                # Sort by: 1) confidence, 2) text length match, 3) smaller box size
                def match_quality(box):
                    # Prefer higher confidence
                    score = box.get('confidence', 0) * 1000

                    # Reward exact text length match (to avoid partial matches with same confidence)
                    matched_text = normalize_text(box.get('text', ''))
                    if matched_text == normalized_search:
                        score += 500 # Boost for exact text match

                    # Penalize larger boxes (prefer tighter matches)
                    bbox_coords = box.get('bbox', [])
                    if len(bbox_coords) >= 4:
                        if len(bbox_coords) >= 8:
                            width = max(bbox_coords[0], bbox_coords[2], bbox_coords[4], bbox_coords[6]) - min(bbox_coords[0], bbox_coords[2], bbox_coords[4], bbox_coords[6])
                            height = max(bbox_coords[1], bbox_coords[3], bbox_coords[5], bbox_coords[7]) - min(bbox_coords[1], bbox_coords[3], bbox_coords[5], bbox_coords[7])
                        else: # Rectangle
                            width = abs(bbox_coords[2] - bbox_coords[0])
                            height = abs(bbox_coords[3] - bbox_coords[1])
                        score -= (width + height) * 0.1 # Small penalty for size

                    return score

                boxes.sort(key=match_quality, reverse=True)
                logger.info(f"Selected best match from {len(boxes)} candidates with score {match_quality(boxes[0]):.1f}: '{boxes[0].get('text', '')}'")
                # Return only the best match to avoid highlighting wrong positions
                return [boxes[0]]

            return boxes

    def _parse_bbox(self, bbox: Any) -> Optional[List[float]]:
        """Parse bounding box from various formats."""
        if isinstance(bbox, list):
            return bbox
        elif isinstance(bbox, str):
            # Parse string format: "[x1, y1], [x2, y2], [x3, y3], [x4, y4]"
            try:
                coord_pattern = re.compile(r'\[([\d.]+),\s*([\d.]+)\]')
                matches = coord_pattern.findall(bbox)
                if len(matches) >= 4:
                    # Return as [x1, y1, x2, y2, x3, y3, x4, y4]
                    return [float(coord) for match in matches for coord in match]
                else:
                    # Fallback: try old method (comma-separated list of numbers)
                    cleaned = bbox.replace('[', '').replace(']', '').strip()
                    parts = [float(p.strip()) for p in cleaned.split(',') if p.strip()]
                    if len(parts) >= 4:
                        return parts
            except Exception as e:
                logger.warning(f"Error parsing bbox string: {e}")
        return None

    def _find_text_with_layoutlmv3(
        self,
        image: Image.Image,
        search_text: str
    ) -> List[Dict[str, Any]]:
        """
        Find text using LayoutLMv3 model directly.
        Note: This method is not used as it requires tesseract for OCR.
        We prefer using OCR data from Azure Document Intelligence instead.
        """
        # LayoutLMv3's processor requires tesseract for OCR, which may not be installed
        # We skip this method and use OCR data instead
        logger.warning("LayoutLMv3 direct text finding skipped - requires tesseract. Use OCR data instead.")
        return []


# Global service instance
_layoutlmv3_service = None


def get_layoutlmv3_service() -> LayoutLMv3Service:
    """Get or create the global LayoutLMv3 service instance."""
    global _layoutlmv3_service
    if _layoutlmv3_service is None:
        _layoutlmv3_service = LayoutLMv3Service()
    return _layoutlmv3_service
