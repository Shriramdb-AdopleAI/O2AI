import cv2
import numpy as np
import logging
from PIL import Image, ImageEnhance, ImageFilter
from typing import List, Tuple, Optional
import io
import math

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """Advanced image preprocessing for OCR optimization."""
    
    def __init__(self):
        self.min_dpi = 200
        self.target_dpi = 300
        self.max_dpi = 600
        self.enhancement_levels = {
            'basic': ['contrast', 'sharpness'],
            'standard': ['contrast', 'sharpness', 'resolution', 'binarization'],
            'advanced': ['contrast', 'sharpness', 'resolution', 'binarization', 'skew', 'noise'],
            'maximum': ['contrast', 'sharpness', 'resolution', 'binarization', 'skew', 'noise', 'perspective', 'text_enhancement']
        }
    
    def preprocess_image(self, image_data: bytes, enhance_quality: bool = True) -> bytes:
        """
        Apply complete preprocessing pipeline to image.
        
        Args:
            image_data: Raw image bytes
            enhance_quality: Whether to apply quality enhancement steps
            
        Returns:
            Preprocessed image bytes
        """
        try:
            # Convert bytes to PIL Image
            pil_image = Image.open(io.BytesIO(image_data))
            logger.info(f"Original image size: {pil_image.size}, mode: {pil_image.mode}")
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Try OpenCV preprocessing first
            try:
                # Convert to OpenCV format
                cv_image = np.array(pil_image)
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
                
                if enhance_quality:
                    # Step 1: High-Resolution Enhancement & Scaling
                    cv_image = self._enhance_resolution(cv_image)
                    logger.info("Applied resolution enhancement")
                    
                    # Step 2: Skew Correction (De-skewing)
                    cv_image = self._correct_skew(cv_image)
                    logger.info("Applied skew correction")
                
                # Step 3: Binarization and Contrast Enhancement
                cv_image = self._enhance_contrast_and_binarize(cv_image)
                logger.info("Applied contrast enhancement and binarization")
                
                if enhance_quality:
                    # Step 4: Noise Removal and Despeckling
                    cv_image = self._remove_noise(cv_image)
                    logger.info("Applied noise removal")
                
                # Convert back to PIL Image
                if len(cv_image.shape) == 3:
                    cv_image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                else:
                    cv_image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)
                
                pil_processed = Image.fromarray(cv_image_rgb)
                
            except ImportError as ie:
                logger.warning(f"OpenCV not available: {ie}. Using PIL-only preprocessing.")
                # Fallback to PIL-only preprocessing
                pil_processed = self._pil_only_preprocessing(pil_image, enhance_quality)
                
            except Exception as oe:
                logger.warning(f"OpenCV preprocessing failed: {oe}. Using PIL-only preprocessing.")
                # Fallback to PIL-only preprocessing
                pil_processed = self._pil_only_preprocessing(pil_image, enhance_quality)
            
            # Convert to bytes
            output_buffer = io.BytesIO()
            pil_processed.save(output_buffer, format='PNG', quality=95)
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error in image preprocessing: {str(e)}")
            return image_data  # Return original if preprocessing fails
    
    def _pil_only_preprocessing(self, pil_image: Image.Image, enhance_quality: bool) -> Image.Image:
        """
        Fallback preprocessing using only PIL when OpenCV is not available.
        """
        logger.info("Using PIL-only preprocessing fallback")
        
        # Convert to grayscale for processing
        if pil_image.mode != 'L':
            processed = pil_image.convert('L')
        else:
            processed = pil_image.copy()
        
        if enhance_quality:
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(processed)
            processed = enhancer.enhance(1.5)
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(processed)
            processed = enhancer.enhance(1.2)
        
        # Apply unsharp mask for better text clarity
        processed = processed.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
        
        # Convert back to RGB
        if processed.mode != 'RGB':
            processed = processed.convert('RGB')
        
        logger.info("PIL-only preprocessing completed")
        return processed
    
    def _enhance_resolution(self, image: np.ndarray) -> np.ndarray:
        """
        Step 1: High-Resolution Enhancement & Image Scaling
        Upscale low-resolution images and enhance details.
        """
        height, width = image.shape[:2]
        
        # Calculate if image needs upscaling (assuming 96 DPI base)
        estimated_dpi = max(width, height) / 8.5  # Estimate based on letter size
        
        if estimated_dpi < self.min_dpi:
            # Calculate scaling factor to reach target DPI
            scale_factor = self.target_dpi / estimated_dpi
            scale_factor = min(scale_factor, 3.0)  # Cap at 3x to avoid excessive scaling
            
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Use INTER_CUBIC for upscaling (better quality)
            upscaled = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Apply sharpening after upscaling
            kernel = np.array([[-1,-1,-1],
                              [-1, 9,-1],
                              [-1,-1,-1]])
            sharpened = cv2.filter2D(upscaled, -1, kernel)
            
            logger.info(f"Upscaled image from {width}x{height} to {new_width}x{new_height}")
            return sharpened
        
        return image
    
    def _correct_skew(self, image: np.ndarray) -> np.ndarray:
        """
        Step 2: Skew Correction (De-skewing)
        Detect and correct document skew/rotation using Hough Line Transform.
        """
        # Convert to grayscale for skew detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply binary threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Use Hough Line Transform to detect lines
        edges = cv2.Canny(binary, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is None or len(lines) < 5:
            return image  # Not enough lines to determine skew
        
        # Calculate angles from detected lines
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle = theta * 180 / np.pi - 90  # Convert to degrees and normalize
            
            # Keep angles close to horizontal (text lines)
            if -45 < angle < 45:
                angles.append(angle)
        
        if not angles:
            return image
        
        # Use median angle to avoid outliers
        skew_angle = np.median(angles)
        
        # Only correct if skew is significant (> 0.5 degrees)
        if abs(skew_angle) > 0.5:
            # Rotate image to correct skew
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
            
            corrected = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                     flags=cv2.INTER_CUBIC, 
                                     borderMode=cv2.BORDER_REPLICATE)
            
            logger.info(f"Corrected skew by {skew_angle:.2f} degrees")
            return corrected
        
        return image
    
    def _enhance_contrast_and_binarize(self, image: np.ndarray) -> np.ndarray:
        """
        Step 3: Binarization and Contrast Enhancement
        Apply adaptive thresholding and contrast enhancement.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Apply Gaussian blur to reduce noise before thresholding
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Alternative: Otsu's thresholding for comparison
        _, otsu_binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Choose the better result based on text clarity
        adaptive_score = self._calculate_text_clarity_score(binary)
        otsu_score = self._calculate_text_clarity_score(otsu_binary)
        
        result = binary if adaptive_score > otsu_score else otsu_binary
        logger.info(f"Used {'adaptive' if adaptive_score > otsu_score else 'Otsu'} thresholding")
        
        return result
    
    def _remove_noise(self, image: np.ndarray) -> np.ndarray:
        """
        Step 4: Noise Removal and Despeckling
        Remove small artifacts and noise while preserving text.
        """
        if len(image.shape) == 3:
            # Convert to grayscale if colored
            processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            processed = image.copy()
        
        # Ensure we're working with proper binary image
        if processed.max() > 1:
            # Apply median filter to reduce noise
            processed = cv2.medianBlur(processed, 3)
            
            # Apply morphological operations
            # 1. Opening operation to remove small noise
            kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            opened = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel_small)
            
            # 2. Closing operation to fill small gaps in characters  
            kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close)
            
            # 3. Remove small connected components using area filtering
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
            
            # Calculate area threshold (remove components smaller than 0.01% of image)
            min_area = processed.shape[0] * processed.shape[1] * 0.0001
            
            # Create clean image by keeping only significant components
            clean_image = np.zeros_like(closed)
            components_removed = 0
            
            for i in range(1, num_labels):  # Skip background (label 0)
                area = stats[i, cv2.CC_STAT_AREA]
                if area > min_area:
                    clean_image[labels == i] = 255
                else:
                    components_removed += 1
            
            logger.info(f"Removed {components_removed} small noise components")
            return clean_image
        
        return processed
    
    def _calculate_text_clarity_score(self, binary_image: np.ndarray) -> float:
        """
        Calculate a score representing text clarity in binary image.
        Higher score means clearer text separation.
        """
        # Find contours
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 0.0
        
        # Calculate metrics for text clarity
        total_area = binary_image.shape[0] * binary_image.shape[1]
        
        # 1. Ratio of text area to total area (should be balanced)
        text_area = sum(cv2.contourArea(c) for c in contours)
        area_ratio = text_area / total_area
        
        # 2. Number of reasonable-sized contours (more = better text separation)
        min_text_area = total_area * 0.0001  # 0.01% of image
        max_text_area = total_area * 0.1     # 10% of image
        
        good_contours = sum(1 for c in contours 
                           if min_text_area < cv2.contourArea(c) < max_text_area)
        
        # Normalize scores and combine
        area_score = min(area_ratio * 4, 1.0)  # Optimal around 0.25
        contour_score = min(good_contours / 50.0, 1.0)  # Normalize by expected text blocks
        
        return (area_score + contour_score) / 2
    
    def preprocess_pdf_pages(self, pdf_pages: List[Image.Image], enhance_quality: bool = True) -> List[Image.Image]:
        """
        Preprocess multiple PDF pages.
        
        Args:
            pdf_pages: List of PIL Images from PDF pages
            enhance_quality: Whether to apply quality enhancement
            
        Returns:
            List of preprocessed PIL Images
        """
        processed_pages = []
        
        for i, page in enumerate(pdf_pages):
            logger.info(f"Preprocessing PDF page {i+1}/{len(pdf_pages)}")
            
            # Convert PIL to bytes
            buffer = io.BytesIO()
            page.save(buffer, format='PNG')
            page_bytes = buffer.getvalue()
            
            # Preprocess
            processed_bytes = self.preprocess_image(page_bytes, enhance_quality)
            
            # Convert back to PIL
            processed_page = Image.open(io.BytesIO(processed_bytes))
            processed_pages.append(processed_page)
        
        return processed_pages
    
    def preprocess_image_advanced(self, image_data: bytes, enhancement_level: str = 'advanced') -> bytes:
        """
        Apply advanced preprocessing pipeline with configurable enhancement levels.
        
        Args:
            image_data: Raw image bytes
            enhancement_level: Level of enhancement ('basic', 'standard', 'advanced', 'maximum')
            
        Returns:
            Preprocessed image bytes
        """
        try:
            # Convert bytes to PIL Image
            pil_image = Image.open(io.BytesIO(image_data))
            logger.info(f"Advanced preprocessing - Original image size: {pil_image.size}, mode: {pil_image.mode}")
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Get enhancement steps for this level
            steps = self.enhancement_levels.get(enhancement_level, self.enhancement_levels['advanced'])
            logger.info(f"Applying enhancement level '{enhancement_level}' with steps: {steps}")
            
            try:
                # Convert to OpenCV format
                cv_image = np.array(pil_image)
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
                
                # Apply enhancement steps
                if 'resolution' in steps:
                    cv_image = self._enhance_resolution_advanced(cv_image)
                    logger.info("Applied advanced resolution enhancement")
                
                if 'perspective' in steps:
                    cv_image = self._correct_perspective(cv_image)
                    logger.info("Applied perspective correction")
                
                if 'skew' in steps:
                    cv_image = self._correct_skew_advanced(cv_image)
                    logger.info("Applied advanced skew correction")
                
                if 'contrast' in steps:
                    cv_image = self._enhance_contrast_advanced(cv_image)
                    logger.info("Applied advanced contrast enhancement")
                
                if 'binarization' in steps:
                    cv_image = self._adaptive_binarization(cv_image)
                    logger.info("Applied adaptive binarization")
                
                if 'text_enhancement' in steps:
                    cv_image = self._enhance_text_features(cv_image)
                    logger.info("Applied text feature enhancement")
                
                if 'noise' in steps:
                    cv_image = self._remove_noise_advanced(cv_image)
                    logger.info("Applied advanced noise removal")
                
                if 'sharpness' in steps:
                    cv_image = self._enhance_sharpness(cv_image)
                    logger.info("Applied sharpness enhancement")
                
                # Convert back to PIL Image
                if len(cv_image.shape) == 3:
                    cv_image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                else:
                    cv_image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)
                
                pil_processed = Image.fromarray(cv_image_rgb)
                
            except ImportError as ie:
                logger.warning(f"OpenCV not available: {ie}. Using PIL-only preprocessing.")
                pil_processed = self._pil_only_preprocessing(pil_image, True)
                
            except Exception as oe:
                logger.warning(f"OpenCV preprocessing failed: {oe}. Using PIL-only preprocessing.")
                pil_processed = self._pil_only_preprocessing(pil_image, True)
            
            # Convert to bytes
            output_buffer = io.BytesIO()
            pil_processed.save(output_buffer, format='PNG', quality=95)
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error in advanced image preprocessing: {str(e)}")
            return image_data  # Return original if preprocessing fails
    
    def _enhance_resolution_advanced(self, image: np.ndarray) -> np.ndarray:
        """
        Advanced resolution enhancement using super-resolution techniques.
        """
        height, width = image.shape[:2]
        
        # Calculate estimated DPI
        estimated_dpi = max(width, height) / 8.5
        
        if estimated_dpi < self.min_dpi:
            # Use bicubic interpolation with edge enhancement
            scale_factor = min(self.target_dpi / estimated_dpi, 4.0)  # Cap at 4x
            
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Use INTER_LANCZOS4 for better quality upscaling
            upscaled = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            
            # Apply edge-preserving smoothing
            upscaled = cv2.bilateralFilter(upscaled, 9, 75, 75)
            
            # Apply unsharp mask for better text clarity
            gaussian = cv2.GaussianBlur(upscaled, (0, 0), 2.0)
            upscaled = cv2.addWeighted(upscaled, 1.5, gaussian, -0.5, 0)
            
            logger.info(f"Advanced upscaling: {width}x{height} -> {new_width}x{new_height}")
            return upscaled
        
        return image
    
    def _correct_perspective(self, image: np.ndarray) -> np.ndarray:
        """
        Correct perspective distortion in documents.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return image
        
        # Find the largest contour (likely the document)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Approximate the contour to get corners
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # If we have 4 corners, correct perspective
        if len(approx) == 4:
            # Order corners: top-left, top-right, bottom-right, bottom-left
            corners = self._order_points(approx.reshape(4, 2))
            
            # Calculate dimensions of the corrected rectangle
            width_a = np.linalg.norm(corners[0] - corners[1])
            width_b = np.linalg.norm(corners[2] - corners[3])
            max_width = max(int(width_a), int(width_b))
            
            height_a = np.linalg.norm(corners[0] - corners[3])
            height_b = np.linalg.norm(corners[1] - corners[2])
            max_height = max(int(height_a), int(height_b))
            
            # Define destination points
            dst = np.array([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1]
            ], dtype=np.float32)
            
            # Calculate perspective transformation matrix
            matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
            
            # Apply perspective correction
            corrected = cv2.warpPerspective(image, matrix, (max_width, max_height))
            
            logger.info("Applied perspective correction")
            return corrected
        
        return image
    
    def _order_points(self, pts):
        """Order points in the format: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype=np.float32)
        
        # Sum and difference of coordinates
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        
        # Top-left point has smallest sum
        rect[0] = pts[np.argmin(s)]
        
        # Bottom-right point has largest sum
        rect[2] = pts[np.argmax(s)]
        
        # Top-right point has smallest difference
        rect[1] = pts[np.argmin(diff)]
        
        # Bottom-left point has largest difference
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def _correct_skew_advanced(self, image: np.ndarray) -> np.ndarray:
        """
        Advanced skew correction using multiple methods.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Method 1: Hough Line Transform (existing method)
        skew_angle_hough = self._detect_skew_hough(gray)
        
        # Method 2: Projection profile method
        skew_angle_projection = self._detect_skew_projection(gray)
        
        # Method 3: FFT-based method
        skew_angle_fft = self._detect_skew_fft(gray)
        
        # Combine results (weighted average)
        angles = [skew_angle_hough, skew_angle_projection, skew_angle_fft]
        weights = [0.4, 0.3, 0.3]  # Weight Hough more as it's most reliable
        
        valid_angles = [a for a in angles if a is not None and abs(a) < 45]
        
        if valid_angles:
            # Use weighted average of valid angles
            weighted_angle = sum(a * w for a, w in zip(valid_angles, weights[:len(valid_angles)])) / sum(weights[:len(valid_angles)])
            
            # Only correct if skew is significant
            if abs(weighted_angle) > 0.3:
                height, width = image.shape[:2]
                center = (width // 2, height // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, weighted_angle, 1.0)
                
                corrected = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                         flags=cv2.INTER_CUBIC, 
                                         borderMode=cv2.BORDER_REPLICATE)
                
                logger.info(f"Advanced skew correction: {weighted_angle:.2f} degrees")
                return corrected
        
        return image
    
    def _detect_skew_hough(self, gray: np.ndarray) -> Optional[float]:
        """Detect skew using Hough Line Transform."""
        try:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None or len(lines) < 5:
                return None
            
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi - 90
                if -45 < angle < 45:
                    angles.append(angle)
            
            return np.median(angles) if angles else None
        except:
            return None
    
    def _detect_skew_projection(self, gray: np.ndarray) -> Optional[float]:
        """Detect skew using projection profile method."""
        try:
            # Apply binary threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Test different angles
            angles = np.arange(-45, 46, 0.5)
            best_angle = 0
            best_variance = 0
            
            for angle in angles:
                # Rotate image
                height, width = binary.shape
                center = (width // 2, height // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(binary, rotation_matrix, (width, height))
                
                # Calculate horizontal projection
                projection = np.sum(rotated, axis=1)
                
                # Calculate variance (higher variance = better text separation)
                variance = np.var(projection)
                
                if variance > best_variance:
                    best_variance = variance
                    best_angle = angle
            
            return best_angle if abs(best_angle) > 0.1 else None
        except:
            return None
    
    def _detect_skew_fft(self, gray: np.ndarray) -> Optional[float]:
        """Detect skew using FFT-based method."""
        try:
            # Apply binary threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Apply FFT
            f_transform = np.fft.fft2(binary)
            f_shift = np.fft.fftshift(f_transform)
            magnitude_spectrum = np.log(np.abs(f_shift) + 1)
            
            # Convert to uint8 for processing
            magnitude_spectrum = np.uint8(255 * magnitude_spectrum / np.max(magnitude_spectrum))
            
            # Detect lines in frequency domain
            edges = cv2.Canny(magnitude_spectrum, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=50)
            
            if lines is None:
                return None
            
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                if 0 < angle < 180:
                    angles.append(angle)
            
            return np.median(angles) - 90 if angles else None
        except:
            return None
    
    def _enhance_contrast_advanced(self, image: np.ndarray) -> np.ndarray:
        """
        Advanced contrast enhancement using multiple techniques.
        """
        # Convert to grayscale for processing
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Method 1: CLAHE with optimized parameters
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced1 = clahe.apply(gray)
        
        # Method 2: Histogram equalization
        enhanced2 = cv2.equalizeHist(gray)
        
        # Method 3: Gamma correction
        gamma = 1.2  # Adjust gamma for better contrast
        enhanced3 = np.power(gray / 255.0, gamma) * 255.0
        enhanced3 = np.uint8(enhanced3)
        
        # Combine methods using weighted average
        enhanced = cv2.addWeighted(enhanced1, 0.5, enhanced2, 0.3, 0)
        enhanced = cv2.addWeighted(enhanced, 0.8, enhanced3, 0.2, 0)
        
        # Convert back to BGR if original was color
        if len(image.shape) == 3:
            enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            return enhanced_bgr
        
        return enhanced
    
    def _adaptive_binarization(self, image: np.ndarray) -> np.ndarray:
        """
        Advanced adaptive binarization with multiple methods.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Method 1: Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Method 2: Otsu's thresholding
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Method 3: Sauvola's method (if available)
        try:
            from skimage.filters import threshold_sauvola
            sauvola = threshold_sauvola(gray, window_size=15)
            sauvola_binary = (gray > sauvola).astype(np.uint8) * 255
        except ImportError:
            sauvola_binary = adaptive
        
        # Choose the best method based on text clarity
        methods = [adaptive, otsu, sauvola_binary]
        scores = [self._calculate_text_clarity_score(m) for m in methods]
        
        best_method = methods[np.argmax(scores)]
        logger.info(f"Best binarization method: {['adaptive', 'otsu', 'sauvola'][np.argmax(scores)]}")
        
        return best_method
    
    def _enhance_text_features(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance text-specific features for better OCR.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply morphological operations to enhance text
        # 1. Closing to connect broken characters
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel_close)
        
        # 2. Opening to remove small noise
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)
        
        # 3. Apply unsharp mask for better text clarity
        gaussian = cv2.GaussianBlur(opened, (0, 0), 1.0)
        sharpened = cv2.addWeighted(opened, 1.5, gaussian, -0.5, 0)
        
        # Convert back to BGR if original was color
        if len(image.shape) == 3:
            enhanced_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
            return enhanced_bgr
        
        return sharpened
    
    def _remove_noise_advanced(self, image: np.ndarray) -> np.ndarray:
        """
        Advanced noise removal with multiple techniques.
        """
        if len(image.shape) == 3:
            processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            processed = image.copy()
        
        # Method 1: Median filter
        median_filtered = cv2.medianBlur(processed, 3)
        
        # Method 2: Bilateral filter
        bilateral_filtered = cv2.bilateralFilter(processed, 9, 75, 75)
        
        # Method 3: Non-local means denoising
        try:
            nlm_filtered = cv2.fastNlMeansDenoising(processed)
        except:
            nlm_filtered = processed
        
        # Method 4: Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        morph_filtered = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
        
        # Combine methods
        combined = cv2.addWeighted(median_filtered, 0.3, bilateral_filtered, 0.3, 0)
        combined = cv2.addWeighted(combined, 0.7, nlm_filtered, 0.3, 0)
        combined = cv2.addWeighted(combined, 0.8, morph_filtered, 0.2, 0)
        
        # Convert back to BGR if original was color
        if len(image.shape) == 3:
            enhanced_bgr = cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)
            return enhanced_bgr
        
        return combined
    
    def _enhance_sharpness(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance image sharpness for better text clarity.
        """
        # Apply unsharp mask
        gaussian = cv2.GaussianBlur(image, (0, 0), 2.0)
        sharpened = cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
        
        # Apply Laplacian sharpening
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        laplacian_sharpened = image - 0.3 * laplacian
        laplacian_sharpened = np.clip(laplacian_sharpened, 0, 255).astype(np.uint8)
        
        # Combine both methods
        final = cv2.addWeighted(sharpened, 0.7, laplacian_sharpened, 0.3, 0)
        
        return final