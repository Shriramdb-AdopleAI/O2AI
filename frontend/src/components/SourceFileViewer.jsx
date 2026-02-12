import React, { useState, useEffect, useRef } from 'react';
import { X, Download, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import authService from '../services/authService';
import * as pdfjsLib from 'pdfjs-dist';

// Set up PDF.js worker - use local worker file from public folder
// The worker file is copied from node_modules/pdfjs-dist/build/pdf.worker.min.mjs to public/
// In Vite, files in public folder are served from root path
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const SourceFileViewer = ({ isOpen, onClose, sourceBlobPath, highlightText, filename, ocrData, rawOcrText, highlightKey, value, extractedData }) => {
  // Get API base URL - ensure HTTPS when page is served over HTTPS
  const getApiBaseUrl = () => {
    let apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8888';
    // If page is served over HTTPS, ensure API URL also uses HTTPS to avoid mixed content errors
    if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
      if (apiBaseUrl.startsWith('http://') && !apiBaseUrl.includes('localhost')) {
        apiBaseUrl = apiBaseUrl.replace('http://', 'https://');
      }
    }
    return apiBaseUrl;
  };
  const API_BASE_URL = getApiBaseUrl();

  const [fileData, setFileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [highlightBoxes, setHighlightBoxes] = useState([]);
  const [previousHighlightBoxes, setPreviousHighlightBoxes] = useState([]);
  const [isHighlighting, setIsHighlighting] = useState(false);
  const [pdfDocument, setPdfDocument] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [pdfPages, setPdfPages] = useState([]);
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [localHighlightText, setLocalHighlightText] = useState(null);
  const containerRef = useRef(null);
  const imageRef = useRef(null);
  const pdfRef = useRef(null);
  const canvasRef = useRef(null);
  const previousCanvasRef = useRef(null);
  const pdfCanvasRefs = useRef({});
  const pdfOverlayRefs = useRef({}); // Overlay canvases for highlights
  const pdfPreviousCanvasRefs = useRef({});
  const pdfContainerRef = useRef(null);
  const pdfRenderTasks = useRef({}); // Track render tasks to cancel them if needed
  const badgeRef = useRef(null);
  const tooltipRef = useRef(null);
  const highlightTimeoutRef = useRef(null);
  const previousHighlightBoxesRef = useRef([]);
  const previousHighlightTextRef = useRef(null);

  useEffect(() => {
    if (isOpen && sourceBlobPath) {
      loadSourceFile();
    } else {
      setFileData(null);
      setError(null);
      setZoom(1);
      setHighlightBoxes([]);
      setPdfDocument(null);
      setCurrentPage(1);
      setTotalPages(0);
      setPdfPages([]);
      // Clear canvas if it exists
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
      // Cancel any ongoing render tasks
      Object.keys(pdfRenderTasks.current).forEach(pageNum => {
        try {
          pdfRenderTasks.current[pageNum].cancel();
        } catch (e) {
          // Ignore cancellation errors
        }
      });
      pdfRenderTasks.current = {};

      // Clear PDF canvases and overlays
      Object.values(pdfCanvasRefs.current).forEach(canvas => {
        if (canvas && canvas.parentNode) {
          const container = canvas.parentNode;
          // Remove the entire container (which includes both canvas and overlay)
          if (container.parentNode) {
            container.parentNode.removeChild(container);
          }
        }
      });
      pdfCanvasRefs.current = {};
      pdfOverlayRefs.current = {};
      if (pdfContainerRef.current) {
        pdfContainerRef.current.innerHTML = '';
      }
    }
  }, [isOpen, sourceBlobPath]);

  useEffect(() => {
    // Clear any pending highlight timeout
    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current);
      highlightTimeoutRef.current = null;
    }

    // Use either the prop highlightText or the local state
    const activeHighlight = highlightText || localHighlightText;

    if (fileData && activeHighlight) {
      setIsHighlighting(true);

      // Save current highlights as previous for seamless transition when highlightText changes
      const isHighlightTextChange = previousHighlightTextRef.current !== activeHighlight && previousHighlightTextRef.current !== null;
      if (isHighlightTextChange && highlightBoxes.length > 0) {
        previousHighlightBoxesRef.current = [...highlightBoxes];
        setPreviousHighlightBoxes([...highlightBoxes]);
      }

      // Update the ref to track current highlightText
      previousHighlightTextRef.current = activeHighlight;

      // Determine delay: shorter for follow-up highlights, longer for initial load
      const isInitialLoad = !isHighlightTextChange || (highlightBoxes.length === 0 && previousHighlightBoxesRef.current.length === 0);
      
      // Check if file is ready (for images, check if loaded; for PDFs, check if pages are rendered)
      const isFileReady = () => {
        if (fileData.type === 'image') {
          return imageRef.current && imageRef.current.complete && 
                 imageRef.current.naturalWidth > 0 && imageRef.current.naturalHeight > 0;
        } else if (fileData.type === 'pdf') {
          return pdfDocument && pdfPages.length > 0;
        }
        return true;
      };

      const attemptHighlight = (retryCount = 0) => {
        if (!isFileReady() && retryCount < 10) {
          // File not ready yet, retry after a short delay
          highlightTimeoutRef.current = setTimeout(() => {
            attemptHighlight(retryCount + 1);
          }, 200);
          return;
        }

        // File is ready or max retries reached, proceed with highlighting
        const delay = isInitialLoad
          ? (fileData.type === 'pdf' ? 500 : 300) // Reduced initial delay
          : (fileData.type === 'pdf' ? 100 : 50); // Much shorter for follow-up highlights

        highlightTimeoutRef.current = setTimeout(() => {
          findAndHighlightText();
        }, delay);
      };

      attemptHighlight();
    } else {
      // Clear highlights when highlightText is removed
      previousHighlightTextRef.current = null;
      previousHighlightBoxesRef.current = [];
      setPreviousHighlightBoxes([]);
      setHighlightBoxes([]);
      setIsHighlighting(false);
    }

    return () => {
      if (highlightTimeoutRef.current) {
        clearTimeout(highlightTimeoutRef.current);
        highlightTimeoutRef.current = null;
      }
    };
  }, [fileData, highlightText, localHighlightText, ocrData, rawOcrText, highlightKey, value, pdfDocument, pdfPages]);

  // Track highlightBoxes changes to update ref for seamless transitions
  useEffect(() => {
    // When highlightBoxes changes, the previous value is already saved in previousHighlightBoxesRef
    // This effect ensures the ref stays in sync
    if (highlightBoxes.length === 0 && previousHighlightBoxes.length > 0) {
      // Highlights were cleared, clear the ref too
      previousHighlightBoxesRef.current = [];
    }
  }, [highlightBoxes, previousHighlightBoxes]);

  const loadSourceFile = async () => {
    setLoading(true);
    setError(null);

    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(sourceBlobPath)}`,
        { headers }
      );

      if (!response.ok) {
        throw new Error(`Failed to load file: ${response.statusText}`);
      }

      const blob = await response.blob();

      // Try multiple methods to determine file type
      let fileType = blob.type;
      const contentType = response.headers.get('content-type');

      // If blob type is generic, try content-type header
      if (!fileType || fileType === 'application/octet-stream') {
        fileType = contentType || null;
      }

      // If still not determined, try filename
      if (!fileType || fileType === 'application/octet-stream') {
        fileType = getFileTypeFromFilename(filename || sourceBlobPath);
      }

      // If still generic, try to detect from file content (magic bytes)
      if (!fileType || fileType === 'application/octet-stream') {
        fileType = await detectFileTypeFromContent(blob);
      }

      console.log('Detected file type:', fileType, 'from blob:', blob.type, 'content-type:', contentType);

      if (fileType === 'application/pdf') {
        // For PDF, load with pdf.js
        const url = URL.createObjectURL(blob);
        const arrayBuffer = await blob.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const pdf = await loadingTask.promise;

        setPdfDocument(pdf);
        setTotalPages(pdf.numPages);
        setFileData({ type: 'pdf', url, blob });

        // Render first page
        renderPdfPage(pdf, 1);
      } else if (fileType && fileType.startsWith('image/')) {
        // For images, create object URL
        const url = URL.createObjectURL(blob);
        setFileData({ type: 'image', url, blob });
      } else {
        // For unknown types, still try to display as PDF or image if possible
        // Check file signature
        const detectedType = await detectFileTypeFromContent(blob);
        if (detectedType === 'application/pdf' || detectedType?.startsWith('image/')) {
          const url = URL.createObjectURL(blob);
          setFileData({ type: detectedType === 'application/pdf' ? 'pdf' : 'image', url, blob });
        } else {
          throw new Error(`Unsupported file type: ${fileType || 'unknown'}. Supported types: PDF and images (PNG, JPG, JPEG, GIF, WEBP)`);
        }
      }
    } catch (err) {
      console.error('Error loading source file:', err);
      setError(err.message || 'Failed to load source file');
    } finally {
      setLoading(false);
    }
  };

  const getFileTypeFromFilename = (filename) => {
    if (!filename) return 'application/octet-stream';

    // Handle filenames with timestamps: filename.ext_timestamp
    // Example: Discharge-Summary-For-Surgery.pdf_20251112_172536
    // We need to extract the extension before the timestamp

    // Remove timestamp pattern (YYYYMMDD_HHMMSS at the end)
    const timestampPattern = /_\d{8}_\d{6}$/;
    let cleanFilename = filename.replace(timestampPattern, '');

    // If no timestamp pattern found, try to find the last valid extension
    // Split by dots and find the extension
    const parts = cleanFilename.split('.');

    // Common file extensions
    const validExtensions = ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff', 'tif'];

    // Try to find a valid extension
    for (let i = parts.length - 1; i >= 0; i--) {
      const ext = parts[i]?.toLowerCase();
      if (ext && validExtensions.includes(ext)) {
        if (ext === 'pdf') return 'application/pdf';
        if (ext === 'jpg') return 'image/jpeg';
        return `image/${ext}`;
      }
    }

    // Fallback: try the last part as extension
    const ext = parts[parts.length - 1]?.toLowerCase();
    if (ext === 'pdf') return 'application/pdf';
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff', 'tif'].includes(ext)) {
      return `image/${ext === 'jpg' ? 'jpeg' : ext}`;
    }

    return 'application/octet-stream';
  };

  const detectFileTypeFromContent = async (blob) => {
    try {
      // Read first few bytes to detect file signature
      const arrayBuffer = await blob.slice(0, 12).arrayBuffer();
      const bytes = new Uint8Array(arrayBuffer);

      // PDF signature: %PDF
      if (bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46) {
        return 'application/pdf';
      }

      // PNG signature: 89 50 4E 47
      if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47) {
        return 'image/png';
      }

      // JPEG signature: FF D8 FF
      if (bytes[0] === 0xFF && bytes[1] === 0xD8 && bytes[2] === 0xFF) {
        return 'image/jpeg';
      }

      // GIF signature: GIF87a or GIF89a
      if (bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x38) {
        return 'image/gif';
      }

      // WEBP signature: RIFF...WEBP
      if (bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46) {
        // Check for WEBP at offset 8
        const webpCheck = await blob.slice(8, 12).arrayBuffer();
        const webpBytes = new Uint8Array(webpCheck);
        const webpStr = String.fromCharCode(...webpBytes);
        if (webpStr === 'WEBP') {
          return 'image/webp';
        }
      }

      return null;
    } catch (err) {
      console.error('Error detecting file type from content:', err);
      return null;
    }
  };

  const findAndHighlightText = async () => {
    // Use either the prop highlightText or the local state
    const activeHighlight = highlightText || localHighlightText;

    if (!activeHighlight || !sourceBlobPath) {
      console.log('No highlight text or source blob path available');
      console.log('activeHighlight:', activeHighlight);
      console.log('sourceBlobPath:', sourceBlobPath);
      setIsHighlighting(false);
      return;
    }

    try {
      // Extract the value text to search for
      // The activeHighlight is in "Key: Value" format, extract just the value part
      let searchText = activeHighlight;

      // If value prop is provided, use it directly (from EnhancedOCRResults)
      if (value !== undefined && value !== null) {
        searchText = typeof value === 'object' ? JSON.stringify(value) : String(value);
      } else {
        // Otherwise parse from the activeHighlight string (from click in BlobViewer)
        // Improved regex to handle cases where value contains colons
        // Match "Key: Value" but be smarter about it
        const colonIndex = activeHighlight.indexOf(':');
        if (colonIndex > 0 && colonIndex < activeHighlight.length - 1) {
          // Extract everything after the first colon
          searchText = activeHighlight.substring(colonIndex + 1).trim();
          console.log(`Extracted value from key-value pair: "${searchText}"`);
        } else {
          // If no colon found, use the whole string
          searchText = activeHighlight.trim();
        }
      }

      searchText = searchText.trim();
      
      // Remove JSON formatting if present (for object values)
      if (searchText.startsWith('{') || searchText.startsWith('[')) {
        try {
          const parsed = JSON.parse(searchText);
          // If it's a simple object/array, try to extract meaningful text
          if (typeof parsed === 'object') {
            // For objects, try to extract string values
            if (Array.isArray(parsed)) {
              // For arrays, join string values
              searchText = parsed.filter(v => typeof v === 'string').join(' ');
            } else {
              // For objects, extract string values
              const stringValues = Object.values(parsed).filter(v => typeof v === 'string');
              if (stringValues.length > 0) {
                searchText = stringValues.join(' ');
              } else {
                searchText = JSON.stringify(parsed);
              }
            }
          }
        } catch (e) {
          // Not valid JSON, use as is
        }
      }
      
      const cleanSearchText = searchText;

      console.log('Searching for text in OCR data:', cleanSearchText);
      console.log('OCR Data available:', ocrData ? 'Yes' : 'No');
      console.log('Raw OCR Text available:', rawOcrText ? 'Yes' : 'No');
      if (ocrData) {
        console.log('OCR Data type:', Array.isArray(ocrData) ? 'Array' : typeof ocrData);
        console.log('OCR Data length/keys:', Array.isArray(ocrData) ? ocrData.length : Object.keys(ocrData || {}).length);
      }

      // Use OCR-based text finding
      let boxes = findTextBoundingBoxes(cleanSearchText, ocrData, rawOcrText);

      // If no boxes found and we have a longer search text, try with a shorter version
      // But be more intelligent about it - try meaningful chunks
      if (boxes.length === 0 && cleanSearchText.length > 30) {
        // Try with first meaningful chunk (first 30 characters or first sentence)
        const firstSentence = cleanSearchText.split(/[.!?]/)[0].trim();
        const shortText = firstSentence.length >= 10 && firstSentence.length < cleanSearchText.length
          ? firstSentence
          : cleanSearchText.substring(0, 30).trim();
        
        if (shortText.length >= 5) {
          console.log(`Trying shorter search text: "${shortText}"`);
          boxes = findTextBoundingBoxes(shortText, ocrData, rawOcrText);
        }
      }

      // If still no boxes, try removing special characters and searching again
      // But preserve important characters like numbers and common separators
      if (boxes.length === 0) {
        const cleanedText = cleanSearchText
          .replace(/[^\w\s\d\-.,]/g, ' ') // Remove special chars but keep alphanumeric, spaces, digits, hyphens, dots, commas
          .replace(/\s+/g, ' ')
          .trim();
        if (cleanedText.length >= 5 && cleanedText !== cleanSearchText) {
          console.log(`Trying cleaned search text: "${cleanedText}"`);
          boxes = findTextBoundingBoxes(cleanedText, ocrData, rawOcrText);
        }
      }

      // Last resort: try with just the first few words (if multi-word)
      if (boxes.length === 0 && cleanSearchText.split(/\s+/).length > 2) {
        const firstWords = cleanSearchText.split(/\s+/).slice(0, 3).join(' ');
        if (firstWords.length >= 5) {
          console.log(`Trying first few words: "${firstWords}"`);
          boxes = findTextBoundingBoxes(firstWords, ocrData, rawOcrText);
        }
      }

      if (boxes.length > 0) {
        setHighlightBoxes(boxes);
        console.log('Found', boxes.length, 'matching text regions');
        boxes.forEach((box, idx) => {
          console.log(`Box ${idx + 1}: page=${box.page}, bbox=${JSON.stringify(box.bbox)}, ` +
                     `width=${box.width}, height=${box.height}, text="${box.text?.substring(0, 50)}..."`);
        });

        // Navigate to the page containing the highlight and scroll to the exact position
        if (fileData?.type === 'pdf' && boxes.length > 0 && boxes[0].page && pdfDocument) {
          const targetPage = boxes[0].page;
          const highlightBox = boxes[0]; // Use first box for navigation
          
          // Update current page if needed
          if (targetPage !== currentPage) {
            setCurrentPage(targetPage);
          }
          
          // Ensure the target page is rendered, then scroll
          const navigateAndScroll = async () => {
            if (!pdfPages.includes(targetPage)) {
              await renderPdfPage(pdfDocument, targetPage);
              // Wait longer if page was just rendered
              setTimeout(() => {
                scrollToPdfHighlight(highlightBox, targetPage);
              }, 500);
            } else {
              // Page already rendered, scroll after a shorter delay
              setTimeout(() => {
                scrollToPdfHighlight(highlightBox, targetPage);
              }, 300);
            }
          };
          
          navigateAndScroll();
        }

        // For images, scroll to the highlighted area
        if (fileData?.type === 'image' && boxes.length > 0 && imageRef.current && containerRef.current) {
          const img = imageRef.current;
          const box = boxes[0]; // Use first box

          // Wait for image to load and highlights to be drawn, then scroll
          const scrollToHighlight = () => {
            if (!img.complete || img.naturalWidth === 0 || img.naturalHeight === 0) {
              // Retry if image not loaded
              setTimeout(scrollToHighlight, 200);
              return;
            }
            // Small delay to ensure highlights are drawn
            setTimeout(() => {
              scrollToImageHighlight(box, img);
            }, 100);
          };
          
          // Start scrolling after a short delay to ensure image is ready
          setTimeout(scrollToHighlight, 500);
        }

        // Draw highlights on canvas overlay with smooth transition
        setTimeout(() => {
          drawHighlights(boxes, true); // true = fade in new highlights
          setIsHighlighting(false);

          // Fade out previous highlights after new ones are visible
          setTimeout(() => {
            previousHighlightBoxesRef.current = [];
            setPreviousHighlightBoxes([]);
          }, 300);
        }, 50); // Reduced delay for faster response
      } else {
        console.log('No matching text found');
        setHighlightBoxes([]);
        setIsHighlighting(false);
        // Fade out previous highlights
        setTimeout(() => {
          previousHighlightBoxesRef.current = [];
          setPreviousHighlightBoxes([]);
        }, 300);
      }
    } catch (err) {
      console.error('Error finding text:', err);
      setIsHighlighting(false);
      setHighlightBoxes([]);
      // Fade out previous highlights
      setTimeout(() => {
        previousHighlightBoxesRef.current = [];
        setPreviousHighlightBoxes([]);
      }, 300);
    }
  };

  const findTextBoundingBoxes = (searchText, ocrData, rawOcrText) => {
    const boxes = [];

    if (!searchText || searchText.length < 1) {
      console.log('Search text is empty or too short');
      return boxes;
    }

    // Normalize search text: handle spacing differences, numbers, and punctuation
    // This handles cases like "1 -0 1 x" vs "1-01 x" vs "1-0-1 x"
    const normalizeText = (text) => {
      if (!text) return '';
      return text.toLowerCase()
        .replace(/[.,;:!?'"`]/g, '') // Remove common punctuation
        .replace(/\s*-\s*/g, '-') // Normalize spaces around dashes: "1 - 0" -> "1-0"
        .replace(/\s+/g, ' ') // Normalize multiple spaces to single space
        .replace(/\s*-\s*/g, '-') // Handle cases like "1 -0" -> "1-0"
        .trim();
    };

    // More precise normalization that preserves word boundaries but handles spacing
    const normalizeTextPrecise = (text) => {
      if (!text) return '';
      return text.toLowerCase()
        .replace(/\s*-\s*/g, '-') // Normalize spaces around dashes
        .replace(/\s+/g, ' ') // Normalize whitespace
        .trim();
    };
    
    // Ultra-flexible normalization for matching numbers and dashes
    const normalizeTextFlexible = (text) => {
      if (!text) return '';
      return text.toLowerCase()
        .replace(/\s*-\s*/g, '') // Remove all dashes and spaces around them: "1 - 0 1" -> "101"
        .replace(/\s+/g, '') // Remove all spaces: "1 0 1" -> "101"
        .replace(/[.,;:!?'"`]/g, '') // Remove punctuation
        .trim();
    };

    // Check match quality and return score (higher = better match)
    // Returns { match: boolean, score: number }
    const getMatchScore = (searchText, ocrText) => {
      if (!searchText || !ocrText) return { match: false, score: 0 };

      const normalizedSearch = normalizeText(searchText);
      const normalizedOcr = normalizeText(ocrText);
      const preciseSearch = normalizeTextPrecise(searchText);
      const preciseOcr = normalizeTextPrecise(ocrText);
      const flexibleSearch = normalizeTextFlexible(searchText);
      const flexibleOcr = normalizeTextFlexible(ocrText);

      // 1. Exact match after normalization (score: 100) - highest priority
      if (normalizedSearch === normalizedOcr) {
        return { match: true, score: 100 };
      }

      // 1.5. Exact match with precise normalization (preserves punctuation) - very high priority
      if (preciseSearch === preciseOcr) {
        return { match: true, score: 98 };
      }
      
      // 1.6. Flexible match for numbers and dashes (handles "1 -0 1" vs "1-01" vs "1-0-1")
      if (flexibleSearch.length >= 3 && flexibleOcr.includes(flexibleSearch)) {
        return { match: true, score: 90 }; // High score for flexible number/dash matches
      }
      if (flexibleSearch.includes(flexibleOcr) && flexibleOcr.length >= flexibleSearch.length * 0.7) {
        return { match: true, score: 85 };
      }

      // 2. Check if search text appears as a complete phrase/substring in OCR text
      const searchWords = normalizedSearch.split(/\s+/).filter(w => w.length > 0);
      if (searchWords.length === 0) return { match: false, score: 0 };

      // For single word, check exact word match or partial match
      if (searchWords.length === 1) {
        const ocrWords = normalizedOcr.split(/\s+/);
        const searchWord = searchWords[0];
        
        // Exact word match (highest priority for single word)
        if (ocrWords.includes(searchWord)) {
          return { match: true, score: 95 };
        }
        
        // Check if the word is a substring of any OCR word (for partial matches)
        // But require at least 70% of the search word to match
        const minMatchLength = Math.ceil(searchWord.length * 0.7);
        for (const ocrWord of ocrWords) {
          if (ocrWord.length >= minMatchLength) {
            if (ocrWord.includes(searchWord) || searchWord.includes(ocrWord)) {
              // Prefer longer matches
              const matchRatio = Math.min(ocrWord.length, searchWord.length) / Math.max(ocrWord.length, searchWord.length);
              if (matchRatio >= 0.7) {
                return { match: true, score: 80 }; // Partial word match with good ratio
              }
            }
          }
        }
        return { match: false, score: 0 };
      }

      // For multiple words, verify they appear consecutively as a phrase
      const ocrWords = normalizedOcr.split(/\s+/);
      
      // 2.1. Exact phrase match (consecutive words in order)
      for (let i = 0; i <= ocrWords.length - searchWords.length; i++) {
        const phrase = ocrWords.slice(i, i + searchWords.length).join(' ');
        if (phrase === normalizedSearch) {
          return { match: true, score: 96 }; // Exact phrase match
        }
      }

      // 2.2. Check if search text is contained as substring (score: 85)
      // But require it to be at word boundaries or significant portion
      if (normalizedOcr.includes(normalizedSearch)) {
        // Check if it's at word boundary or significant match
        const index = normalizedOcr.indexOf(normalizedSearch);
        const beforeChar = index > 0 ? normalizedOcr[index - 1] : ' ';
        const afterChar = index + normalizedSearch.length < normalizedOcr.length 
          ? normalizedOcr[index + normalizedSearch.length] 
          : ' ';
        
        // If surrounded by spaces or at start/end, it's a good match
        if (beforeChar === ' ' && afterChar === ' ') {
          return { match: true, score: 85 };
        }
        // Still a match but slightly lower score
        return { match: true, score: 80 };
      }

      // 2.3. Check if OCR text is contained in search text (for cases where OCR has less text)
      // But require at least 60% of search text to be in OCR
      if (normalizedSearch.includes(normalizedOcr) && normalizedOcr.length >= normalizedSearch.length * 0.6) {
        return { match: true, score: 75 };
      }

      // 3. Word-order matching with minimal gaps (score: 50-75)
      // This is more strict - words must appear in order with minimal gaps
      let searchIdx = 0;
      let lastMatchIdx = -1;
      let totalGaps = 0;
      let consecutiveMatches = 0;
      let maxConsecutive = 0;

      for (let i = 0; i < ocrWords.length && searchIdx < searchWords.length; i++) {
        // Check for exact match first
        if (ocrWords[i] === searchWords[searchIdx]) {
          consecutiveMatches++;
          maxConsecutive = Math.max(maxConsecutive, consecutiveMatches);
          if (lastMatchIdx >= 0) {
            const gap = i - lastMatchIdx - 1;
            if (gap > 2) { // Stricter gap tolerance
              return { match: false, score: 0 }; // Gap too large
            }
            totalGaps += gap;
          }
          lastMatchIdx = i;
          searchIdx++;
        } else if (ocrWords[i].includes(searchWords[searchIdx]) || searchWords[searchIdx].includes(ocrWords[i])) {
          // Partial word match - lower score
          consecutiveMatches = 1;
          if (lastMatchIdx >= 0) {
            const gap = i - lastMatchIdx - 1;
            if (gap > 2) {
              return { match: false, score: 0 };
            }
            totalGaps += gap;
          }
          lastMatchIdx = i;
          searchIdx++;
        } else {
          consecutiveMatches = 0;
        }
      }

      if (searchIdx === searchWords.length) {
        // Score based on gaps and consecutive matches
        const gapPenalty = totalGaps * 8; // Higher penalty for gaps
        const consecutiveBonus = maxConsecutive * 2; // Bonus for consecutive matches
        const score = Math.max(50, 75 - gapPenalty + consecutiveBonus);
        return { match: true, score };
      }

      // 4. Check if at least 70% of words match (stricter than before)
      let matchedWords = 0;
      const usedOcrIndices = new Set();
      
      for (const searchWord of searchWords) {
        for (let i = 0; i < ocrWords.length; i++) {
          if (usedOcrIndices.has(i)) continue;
          
          const ocrWord = ocrWords[i];
          if (ocrWord === searchWord) {
            matchedWords++;
            usedOcrIndices.add(i);
            break;
          } else if (ocrWord.includes(searchWord) || searchWord.includes(ocrWord)) {
            // Only count if significant match (at least 70% overlap)
            const minLen = Math.min(ocrWord.length, searchWord.length);
            const maxLen = Math.max(ocrWord.length, searchWord.length);
            if (minLen >= maxLen * 0.7) {
              matchedWords++;
              usedOcrIndices.add(i);
              break;
            }
          }
        }
      }
      
      const matchRatio = matchedWords / searchWords.length;
      if (matchRatio >= 0.7) {
        // Score based on match ratio
        return { match: true, score: Math.round(40 + (matchRatio - 0.7) * 30) }; // 40-70 score range
      }

      return { match: false, score: 0 };
    };

    // Simplified matching function for backward compatibility
    const textMatches = (searchText, ocrText) => {
      return getMatchScore(searchText, ocrText).match;
    };

    // Validate that a match is actually correct by checking similarity
    const validateMatch = (searchText, matchedText, minScore = 40) => {
      if (!searchText || !matchedText) return false;
      const result = getMatchScore(searchText, matchedText);
      return result.match && result.score >= minScore;
    };

    const searchTextLower = normalizeText(searchText);
    const searchWords = searchTextLower.split(/\s+/).filter(w => w.length > 0);

    console.log('Searching for normalized text:', searchTextLower);
    console.log('OCR Data structure:', ocrData ? (Array.isArray(ocrData) ? `Array[${ocrData.length}]` : Object.keys(ocrData)) : 'null');

    // Try to find text in OCR positioning data
    if (ocrData) {
      // Handle different OCR data structures
      let textBlocks = [];

      if (Array.isArray(ocrData)) {
        // Array of page results
        ocrData.forEach((pageResult, idx) => {
          console.log(`Page ${idx} structure:`, Object.keys(pageResult || {}));
          if (pageResult && typeof pageResult === 'object') {
            if (pageResult.text_blocks) {
              textBlocks.push(...(Array.isArray(pageResult.text_blocks) ? pageResult.text_blocks : [pageResult.text_blocks]));
            } else if (pageResult.positioning_data) {
              if (Array.isArray(pageResult.positioning_data)) {
                textBlocks.push(...pageResult.positioning_data);
              } else if (pageResult.positioning_data.text_blocks) {
                const blocks = pageResult.positioning_data.text_blocks;
                textBlocks.push(...(Array.isArray(blocks) ? blocks : [blocks]));
              } else {
                // positioning_data might be a single block
                textBlocks.push(pageResult.positioning_data);
              }
            } else if (pageResult.words || pageResult.lines) {
              // Direct page result with words/lines
              textBlocks.push(pageResult);
            } else if (pageResult.pages) {
              // Nested pages structure
              if (Array.isArray(pageResult.pages)) {
                pageResult.pages.forEach(page => {
                  if (page.text_blocks) {
                    textBlocks.push(...(Array.isArray(page.text_blocks) ? page.text_blocks : [page.text_blocks]));
                  } else if (page.words || page.lines) {
                    textBlocks.push(page);
                  }
                });
              }
            }
          }
        });
      } else if (ocrData && typeof ocrData === 'object') {
        if (ocrData.text_blocks) {
          const blocks = ocrData.text_blocks;
          textBlocks = Array.isArray(blocks) ? blocks : [blocks];
        } else if (ocrData.words || ocrData.lines) {
          // Single block structure
          textBlocks = [ocrData];
        } else if (ocrData.pages) {
          // Pages structure
          if (Array.isArray(ocrData.pages)) {
            ocrData.pages.forEach(page => {
              if (page.text_blocks) {
                textBlocks.push(...(Array.isArray(page.text_blocks) ? page.text_blocks : [page.text_blocks]));
              } else if (page.words || page.lines) {
                textBlocks.push(page);
              }
            });
          }
        } else if (ocrData.content) {
          // Some OCR formats have content field
          if (Array.isArray(ocrData.content)) {
            textBlocks = ocrData.content;
          } else {
            textBlocks = [ocrData.content];
          }
        }
      }

      console.log(`Found ${textBlocks.length} text blocks to search`);

      // Search through words and lines
      textBlocks.forEach((block, blockIdx) => {
        if (!block || typeof block !== 'object') {
          console.warn(`Skipping invalid block at index ${blockIdx}`);
          return;
        }
        
        const words = Array.isArray(block.words) ? block.words : (block.words ? [block.words] : []);
        const lines = Array.isArray(block.lines) ? block.lines : (block.lines ? [block.lines] : []);
        const pageWidth = block.width || block.page_width || 1;
        const pageHeight = block.height || block.page_height || 1;
        const pageNumber = block.page_number || block.page || block.pageNum || 1;

        // Search in lines first (for multi-word matches like "dr. anand mbbs, md.")
        // Also handle multi-line content (paragraphs)
        // Track best matches to avoid multiple highlights
        let bestLineMatch = null;
        let bestLineScore = 0;
        let bestLineText = '';

        lines.forEach((line, lineIdx) => {
          const lineText = line.text || '';
          if (lineText) {
            const matchResult = getMatchScore(searchText, lineText);
            if (!matchResult.match) {
              return; // Skip if not a match
            }

            // Only keep the best match (highest score)
            // If scores are equal, prefer shorter matches (more precise)
            if (matchResult.score > bestLineScore || 
                (matchResult.score === bestLineScore && lineText.length < bestLineText.length)) {
              bestLineScore = matchResult.score;
              bestLineMatch = { line, lineIdx };
              bestLineText = lineText;
            }
          }
        });

        // Add only the best line match if score is high enough (at least 40 for more lenient matching)
        if (bestLineMatch && bestLineMatch.line.bounding_box && bestLineScore >= 40) {
          const line = bestLineMatch.line;
          const bbox = line.bounding_box;

          // Handle different bbox formats
          let bboxArray = bbox;
          if (typeof bbox === 'string') {
            // Parse string format: "[x1, y1], [x2, y2], [x3, y3], [x4, y4]"
            try {
              // Match coordinate pairs: [x, y]
              const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
              const matches = [...bbox.matchAll(coordPattern)];
              if (matches.length >= 4) {
                // Extract all coordinates in order: [x1, y1, x2, y2, x3, y3, x4, y4]
                bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
              } else {
                // Fallback: try old method
                const cleaned = bbox.replace(/[\[\]]/g, '').trim();
                const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                if (parts.length >= 4) {
                  bboxArray = parts;
                }
              }
            } catch (e) {
              console.warn('Error parsing bounding box string:', e);
            }
          }

          if (Array.isArray(bboxArray) && bboxArray.length >= 4) {
            // Validate the match before adding
            if (validateMatch(searchText, line.text, 40)) {
              console.log(`Found best match in line ${bestLineMatch.lineIdx} on page ${pageNumber} (score: ${bestLineScore}):`, line.text);
              boxes.push({
                page: pageNumber,
                bbox: bboxArray,
                width: pageWidth,
                height: pageHeight,
                text: line.text
              });
            } else {
              console.log(`Match validation failed for line: "${line.text}" (score: ${bestLineScore})`);
            }
          }
        }

        // For big content (paragraphs) that might span multiple lines, try to match across lines
        // Removed the 3+ word requirement to allow matching shorter phrases across lines
        if (boxes.length === 0 && searchWords.length > 0 && lines.length > 1) {
          // Try to find the search text across multiple consecutive lines
          // Combine text from multiple lines and check if search text appears
          for (let startLineIdx = 0; startLineIdx < lines.length; startLineIdx++) {
            // Try combining 2 to 5 consecutive lines to find the match
            for (let numLines = 2; numLines <= Math.min(5, lines.length - startLineIdx); numLines++) {
              const combinedLines = lines.slice(startLineIdx, startLineIdx + numLines);
              const combinedText = combinedLines.map(l => l.text || '').join(' ');

              // Use flexible matching instead of simple includes check
              if (textMatches(searchText, combinedText)) {
                // Find the position of the search text in the normalized combined text
                const normalizedCombined = normalizeText(combinedText);
                const searchIndex = normalizedCombined.indexOf(searchTextLower);
                if (searchIndex !== -1) {
                  // Calculate which words from which lines are part of the match
                  let charCount = 0;
                  let startLine = startLineIdx;
                  let endLine = startLineIdx + numLines - 1;
                  let startWordIdx = -1;
                  let endWordIdx = -1;

                  // Find the starting and ending words
                  for (let lineIdx = startLineIdx; lineIdx < startLineIdx + numLines; lineIdx++) {
                    const line = lines[lineIdx];
                    const lineText = normalizeText(line.text || '');
                    const lineWords = lineText.split(/\s+/);

                    for (const word of lineWords) {
                      const wordStart = charCount;
                      const wordEnd = charCount + word.length;

                      if (startWordIdx === -1 && wordEnd > searchIndex) {
                        startWordIdx = lineIdx - startLineIdx;
                        startLine = lineIdx;
                      }
                      if (wordStart < searchIndex + searchTextLower.length && wordEnd >= searchIndex + searchTextLower.length) {
                        endWordIdx = lineIdx - startLineIdx;
                        endLine = lineIdx;
                      }

                      charCount += word.length + 1; // +1 for space
                    }
                  }

                  // Collect bounding boxes from the matching lines
                  const matchingLineBoxes = [];
                  for (let lineIdx = startLine; lineIdx <= endLine; lineIdx++) {
                    const line = lines[lineIdx];
                    if (line.bounding_box) {
                      let bboxArray = line.bounding_box;
                      if (typeof bboxArray === 'string') {
                        try {
                          // Match coordinate pairs: [x, y]
                          const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
                          const matches = [...bboxArray.matchAll(coordPattern)];
                          if (matches.length >= 4) {
                            // Extract all coordinates in order: [x1, y1, x2, y2, x3, y3, x4, y4]
                            bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
                          } else {
                            // Fallback: try old method
                            const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
                            const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                            if (parts.length >= 4) {
                              bboxArray = parts;
                            }
                          }
                        } catch (e) {
                          continue;
                        }
                      }
                      if (Array.isArray(bboxArray) && bboxArray.length >= 4) {
                        matchingLineBoxes.push(bboxArray);
                      }
                    }
                  }

                  // Combine all bounding boxes
                  if (matchingLineBoxes.length > 0) {
                    const allX = matchingLineBoxes.flatMap(bbox => {
                      if (bbox.length >= 8) {
                        return [bbox[0], bbox[2], bbox[4], bbox[6]];
                      } else {
                        return [bbox[0], bbox[2]];
                      }
                    });
                    const allY = matchingLineBoxes.flatMap(bbox => {
                      if (bbox.length >= 8) {
                        return [bbox[1], bbox[3], bbox[5], bbox[7]];
                      } else {
                        return [bbox[1], bbox[3]];
                      }
                    });

                    const minX = Math.min(...allX);
                    const maxX = Math.max(...allX);
                    const minY = Math.min(...allY);
                    const maxY = Math.max(...allY);

                    const combinedText = combinedLines.map(l => l.text).join(' ');
                    // Validate the match before adding
                    if (validateMatch(searchText, combinedText, 40)) {
                      console.log(`Found multi-line match on page ${pageNumber} from line ${startLine} to ${endLine}`);
                      boxes.push({
                        page: pageNumber,
                        bbox: [minX, minY, maxX, minY, maxX, maxY, minX, maxY],
                        width: pageWidth,
                        height: pageHeight,
                        text: combinedText
                      });
                    } else {
                      console.log(`Match validation failed for multi-line: "${combinedText.substring(0, 50)}..."`);
                    }
                    break;
                  }
                }
              }
            }
            if (boxes.length > 0) break; // Found match, stop searching
          }
        }

        // Search in words (only if no line match found, and use best match)
        if (boxes.length === 0) {
          let bestWordMatch = null;
          let bestWordScore = 0;
          let bestWordText = '';

          words.forEach((word, idx) => {
            const wordText = word.text || '';
            if (wordText) {
              const matchResult = getMatchScore(searchText, wordText);
              if (matchResult.match) {
                // If scores are equal, prefer shorter matches (more precise)
                if (matchResult.score > bestWordScore || 
                    (matchResult.score === bestWordScore && wordText.length < bestWordText.length)) {
                  bestWordScore = matchResult.score;
                  bestWordMatch = word;
                  bestWordText = wordText;
                }
              }
            }
          });

          // Add only the best word match if score is high enough (at least 40)
          if (bestWordMatch && bestWordMatch.bounding_box && bestWordScore >= 40) {
            const bbox = bestWordMatch.bounding_box;
            let bboxArray = bbox;
            if (typeof bbox === 'string') {
              try {
                // Match coordinate pairs: [x, y]
                const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
                const matches = [...bbox.matchAll(coordPattern)];
                if (matches.length >= 4) {
                  // Extract all coordinates in order: [x1, y1, x2, y2, x3, y3, x4, y4]
                  bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
                } else {
                  // Fallback: try old method
                  const cleaned = bbox.replace(/[\[\]]/g, '').trim();
                  const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                  if (parts.length >= 4) {
                    bboxArray = parts;
                  }
                }
              } catch (e) {
                console.warn('Error parsing bounding box string:', e);
              }
            }

            if (Array.isArray(bboxArray) && bboxArray.length >= 4) {
              // Validate the match before adding
              if (validateMatch(searchText, bestWordMatch.text, 40)) {
                console.log(`Found best word match on page ${pageNumber} (score: ${bestWordScore}):`, bestWordMatch.text);
                boxes.push({
                  page: pageNumber,
                  bbox: bboxArray,
                  width: pageWidth,
                  height: pageHeight,
                  text: bestWordMatch.text
                });
              } else {
                console.log(`Match validation failed for word: "${bestWordMatch.text}" (score: ${bestWordScore})`);
              }
            }
          }
        }

        // If no matches in words/lines, try to find multi-word phrases by combining consecutive words
        // Use scoring to find the best phrase match
        if (boxes.length === 0 && searchWords.length > 0 && words.length >= searchWords.length) {
          let bestPhraseMatch = null;
          let bestPhraseScore = 0;
          let bestPhraseText = '';

          // Try different phrase lengths to find matches
          // Start with exact length, then try slightly longer
          for (let phraseLength = searchWords.length; phraseLength <= Math.min(searchWords.length + 2, words.length); phraseLength++) {
            for (let i = 0; i <= words.length - phraseLength; i++) {
              const phraseWords = words.slice(i, i + phraseLength);
              const phraseText = phraseWords.map(w => w.text || '').join(' ');

              // Use scoring to find best match
              const matchResult = getMatchScore(searchText, phraseText);
              if (matchResult.match) {
                // If scores are equal, prefer shorter phrases (more precise)
                if (matchResult.score > bestPhraseScore || 
                    (matchResult.score === bestPhraseScore && phraseText.length < bestPhraseText.length)) {
                  bestPhraseScore = matchResult.score;
                  bestPhraseMatch = phraseWords;
                  bestPhraseText = phraseText;
                }
              }
            }
          }

          // Add only the best phrase match if score is high enough (at least 40)
          if (bestPhraseMatch && bestPhraseMatch.length > 0 && bestPhraseScore >= 40) {
            // Combine bounding boxes of all words in the phrase
            const phraseBoxes = bestPhraseMatch
              .map(w => {
                let bbox = w.bounding_box;
                if (typeof bbox === 'string') {
                  try {
                    // Match coordinate pairs: [x, y]
                    const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
                    const matches = [...bbox.matchAll(coordPattern)];
                    if (matches.length >= 4) {
                      // Extract all coordinates in order: [x1, y1, x2, y2, x3, y3, x4, y4]
                      return matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
                    } else {
                      // Fallback: try old method
                      const cleaned = bbox.replace(/[\[\]]/g, '').trim();
                      const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                      if (parts.length >= 4) {
                        return parts;
                      }
                    }
                  } catch (e) {
                    return null;
                  }
                }
                return bbox;
              })
              .filter(bbox => bbox && Array.isArray(bbox) && bbox.length >= 4);

            if (phraseBoxes.length > 0) {
              // Calculate combined bounding box
              const allX = phraseBoxes.flatMap(bbox => {
                if (bbox.length >= 8) {
                  return [bbox[0], bbox[2], bbox[4], bbox[6]];
                } else {
                  return [bbox[0], bbox[2]];
                }
              });
              const allY = phraseBoxes.flatMap(bbox => {
                if (bbox.length >= 8) {
                  return [bbox[1], bbox[3], bbox[5], bbox[7]];
                } else {
                  return [bbox[1], bbox[3]];
                }
              });

              const minX = Math.min(...allX);
              const maxX = Math.max(...allX);
              const minY = Math.min(...allY);
              const maxY = Math.max(...allY);

              const phraseText = bestPhraseMatch.map(w => w.text).join(' ');
              // Validate the match before adding
              if (validateMatch(searchText, phraseText, 40)) {
                console.log(`Found best phrase match on page ${pageNumber} (score: ${bestPhraseScore}):`, phraseText);
                boxes.push({
                  page: pageNumber,
                  bbox: [minX, minY, maxX, minY, maxX, maxY, minX, maxY],
                  width: pageWidth,
                  height: pageHeight,
                  text: phraseText
                });
              } else {
                console.log(`Match validation failed for phrase: "${phraseText}" (score: ${bestPhraseScore})`);
              }
            }
          }
        }
      });
    }

    // Fallback: try to find text in raw OCR text and approximate position
    if (boxes.length === 0 && rawOcrText) {
      // Use flexible matching for fallback as well
      if (textMatches(searchText, rawOcrText)) {
        // Approximate position based on text position
        // This is a fallback when we don't have bounding boxes
        console.log('Found text in raw OCR but no bounding boxes available');
        // Try to find approximate position in raw text
        const normalizedRaw = normalizeText(rawOcrText);
        const normalizedSearch = normalizeText(searchText);
        const index = normalizedRaw.indexOf(normalizedSearch);
        if (index !== -1) {
          // Estimate position (rough approximation)
          const textLength = rawOcrText.length;
          const positionRatio = index / textLength;
          // Create a rough bounding box in the center area where text might be
          // This is a last resort fallback
          console.log(`Approximate text position found at ${(positionRatio * 100).toFixed(1)}% of document`);
        }
      }
    }

    // If still no boxes found, try a more aggressive search with partial matching
    if (boxes.length === 0 && ocrData && textBlocks.length > 0) {
      console.log('No matches found with standard search, trying partial matching...');
      // Try searching for individual words or shorter phrases
      const searchWords = searchTextLower.split(/\s+/).filter(w => w.length > 2);
      if (searchWords.length > 0) {
        // Try to find at least one word match by searching textBlocks directly
        for (const word of searchWords) {
          for (const block of textBlocks) {
            if (!block || typeof block !== 'object') continue;
            
            const words = Array.isArray(block.words) ? block.words : (block.words ? [block.words] : []);
            const lines = Array.isArray(block.lines) ? block.lines : (block.lines ? [block.lines] : []);
            const pageWidth = block.width || block.page_width || 1;
            const pageHeight = block.height || block.page_height || 1;
            const pageNumber = block.page_number || block.page || block.pageNum || 1;

            // Search in lines first
            for (const line of lines) {
              if (line && line.text && textMatches(word, line.text) && line.bounding_box) {
                let bboxArray = line.bounding_box;
                if (typeof bboxArray === 'string') {
                  try {
                    const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
                    const matches = [...bboxArray.matchAll(coordPattern)];
                    if (matches.length >= 4) {
                      bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
                    } else {
                      const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
                      const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                      if (parts.length >= 4) {
                        bboxArray = parts;
                      }
                    }
                  } catch (e) {
                    continue;
                  }
                }
                if (Array.isArray(bboxArray) && bboxArray.length >= 4) {
                  // Validate the match before adding (lower threshold for partial matches)
                  if (validateMatch(word, line.text, 40)) {
                    console.log(`Found partial match for word "${word}" in line on page ${pageNumber}`);
                    boxes.push({
                      page: pageNumber,
                      bbox: bboxArray,
                      width: pageWidth,
                      height: pageHeight,
                      text: line.text
                    });
                    break;
                  } else {
                    console.log(`Partial match validation failed for word "${word}" in line: "${line.text}"`);
                  }
                }
              }
            }
            if (boxes.length > 0) break;
          }
          if (boxes.length > 0) break;
        }
      }
    }

    console.log(`Total boxes found: ${boxes.length}`);
    return boxes;
  };

  // Helper function to scroll to highlighted area in image
  const scrollToImageHighlight = (box, img) => {
    if (!box || !box.bbox || !img || !containerRef.current) return;

    try {
      // Parse bounding box
      let bboxArray = box.bbox;
      if (typeof bboxArray === 'string') {
        try {
          const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
          const matches = [...bboxArray.matchAll(coordPattern)];
          if (matches.length >= 4) {
            bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
          } else {
            const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
            const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
            if (parts.length >= 8) {
              bboxArray = parts;
            } else if (parts.length >= 4) {
              bboxArray = parts;
            } else {
              return;
            }
          }
        } catch (e) {
          return;
        }
      }

      if (!Array.isArray(bboxArray) || bboxArray.length < 4) return;

      // Get image dimensions and position
      const imgRect = img.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();

      // Get OCR dimensions
      const ocrWidth = box.width || img.naturalWidth;
      const ocrHeight = box.height || img.naturalHeight;

      // Calculate scale factors
      const scaleX = imgRect.width / ocrWidth;
      const scaleY = imgRect.height / ocrHeight;

      // Calculate highlight center position
      let centerX, centerY;
      if (bboxArray.length >= 8) {
        const xs = [bboxArray[0], bboxArray[2], bboxArray[4], bboxArray[6]];
        const ys = [bboxArray[1], bboxArray[3], bboxArray[5], bboxArray[7]];
        centerX = (Math.min(...xs) + Math.max(...xs)) / 2 * scaleX;
        centerY = (Math.min(...ys) + Math.max(...ys)) / 2 * scaleY;
      } else {
        const x1 = bboxArray[0];
        const y1 = bboxArray[1];
        const x2 = bboxArray[2];
        const y2 = bboxArray[3];
        centerX = (Math.min(x1, x2) + Math.max(x1, x2)) / 2 * scaleX;
        centerY = (Math.min(y1, y2) + Math.max(y1, y2)) / 2 * scaleY;
      }

      // Calculate position relative to container
      const imgOffsetX = imgRect.left - containerRect.left;
      const imgOffsetY = imgRect.top - containerRect.top;

      // Calculate target scroll position (center the highlight)
      const targetScrollLeft = containerRef.current.scrollLeft + (imgOffsetX + centerX) - (containerRect.width / 2);
      const targetScrollTop = containerRef.current.scrollTop + (imgOffsetY + centerY) - (containerRect.height / 2);

      // Scroll to the highlight position
      containerRef.current.scrollTo({
        left: Math.max(0, targetScrollLeft),
        top: Math.max(0, targetScrollTop),
        behavior: 'smooth'
      });
    } catch (err) {
      console.error('Error scrolling to image highlight:', err);
    }
  };

  // Helper function to scroll to highlighted area in PDF
  const scrollToPdfHighlight = async (box, pageNum, retryCount = 0) => {
    if (!box || !box.bbox || !containerRef.current || !pdfDocument) return;

    try {
      // Get the canvas for this page
      const canvas = pdfCanvasRefs.current[pageNum];
      if (!canvas) {
        // If canvas doesn't exist and we haven't retried too many times, try again
        if (retryCount < 5) {
          await renderPdfPage(pdfDocument, pageNum);
          // Wait a bit for rendering to complete
          setTimeout(() => scrollToPdfHighlight(box, pageNum, retryCount + 1), 300);
        }
        return;
      }

      // Ensure canvas is visible and has dimensions
      if (canvas.width === 0 || canvas.height === 0) {
        if (retryCount < 5) {
          setTimeout(() => scrollToPdfHighlight(box, pageNum, retryCount + 1), 200);
        }
        return;
      }

      // Parse bounding box
      let bboxArray = box.bbox;
      if (typeof bboxArray === 'string') {
        try {
          const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
          const matches = [...bboxArray.matchAll(coordPattern)];
          if (matches.length >= 4) {
            bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
          } else {
            const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
            const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
            if (parts.length >= 8) {
              bboxArray = parts;
            } else if (parts.length >= 4) {
              bboxArray = parts;
            } else {
              return;
            }
          }
        } catch (e) {
          return;
        }
      }

      if (!Array.isArray(bboxArray) || bboxArray.length < 4) return;

      // Get page and viewport to calculate coordinates
      const page = await pdfDocument.getPage(pageNum);
      const viewport = page.getViewport({ scale: zoom });
      const originalViewport = page.getViewport({ scale: 1.0 });
      const INCHES_TO_POINTS = 72;

      // Get OCR dimensions and determine unit
      const ocrWidth = box.width;
      const ocrHeight = box.height;
      const isLikelyInches = ocrWidth && ocrHeight && ocrWidth < 100 && ocrHeight < 100;
      const unitMultiplier = isLikelyInches ? INCHES_TO_POINTS : 1;
      const referenceWidthPoints = originalViewport.width;
      const referenceHeightPoints = originalViewport.height;
      const ocrWidthPoints = ocrWidth ? (ocrWidth * unitMultiplier) : referenceWidthPoints;
      const ocrHeightPoints = ocrHeight ? (ocrHeight * unitMultiplier) : referenceHeightPoints;
      const scaleX = viewport.width / ocrWidthPoints;
      const scaleY = viewport.height / ocrHeightPoints;

      // Calculate highlight center position in canvas coordinates
      let centerX, centerY;
      if (bboxArray.length >= 8) {
        const xs = [bboxArray[0] * unitMultiplier, bboxArray[2] * unitMultiplier,
                    bboxArray[4] * unitMultiplier, bboxArray[6] * unitMultiplier];
        const ys = [bboxArray[1] * unitMultiplier, bboxArray[3] * unitMultiplier,
                    bboxArray[5] * unitMultiplier, bboxArray[7] * unitMultiplier];
        centerX = (Math.min(...xs) + Math.max(...xs)) / 2 * scaleX;
        centerY = (Math.min(...ys) + Math.max(...ys)) / 2 * scaleY;
      } else {
        const x1 = bboxArray[0] * unitMultiplier;
        const y1 = bboxArray[1] * unitMultiplier;
        const x2 = bboxArray[2] * unitMultiplier;
        const y2 = bboxArray[3] * unitMultiplier;
        centerX = (Math.min(x1, x2) + Math.max(x1, x2)) / 2 * scaleX;
        centerY = (Math.min(y1, y2) + Math.max(y1, y2)) / 2 * scaleY;
      }

      // Get canvas and container positions
      const canvasRect = canvas.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();

      // Calculate position relative to container
      const canvasOffsetX = canvasRect.left - containerRect.left + containerRef.current.scrollLeft;
      const canvasOffsetY = canvasRect.top - containerRect.top + containerRef.current.scrollTop;

      // Calculate target scroll position (center the highlight)
      const targetScrollLeft = canvasOffsetX + centerX - (containerRect.width / 2);
      const targetScrollTop = canvasOffsetY + centerY - (containerRect.height / 2);

      // Scroll to the highlight position
      containerRef.current.scrollTo({
        left: Math.max(0, targetScrollLeft),
        top: Math.max(0, targetScrollTop),
        behavior: 'smooth'
      });

      // Also ensure the canvas is in view (fallback)
      setTimeout(() => {
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    } catch (err) {
      console.error('Error scrolling to PDF highlight:', err);
      // Fallback: just scroll the canvas into view
      const canvas = pdfCanvasRefs.current[pageNum];
      if (canvas && containerRef.current) {
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  };

  // Helper function to draw highlight boxes with opacity
  const drawHighlightBoxes = (ctx, boxes, img, displayedWidth, displayedHeight, opacity = 0.8) => {
    boxes.forEach(box => {
      if (box.bbox && box.bbox.length >= 4) {
        // Parse bounding box - handle string format from Azure Document Intelligence
        let bboxArray = box.bbox;
        if (typeof bboxArray === 'string') {
          try {
            // Match coordinate pairs: [x, y]
            const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
            const matches = [...bboxArray.matchAll(coordPattern)];
            if (matches.length >= 4) {
              // Extract all coordinates in order: [x1, y1, x2, y2, x3, y3, x4, y4]
              bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
            } else {
              // Fallback: try old method
              const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
              const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
              if (parts.length >= 8) {
                // Polygon: [x1, y1, x2, y2, x3, y3, x4, y4]
                bboxArray = parts;
              } else if (parts.length >= 4) {
                // Rectangle: [x1, y1, x2, y2]
                bboxArray = parts;
              } else {
                return;
              }
            }
          } catch (e) {
            return;
          }
        }

        // Azure Document Intelligence coordinates for images are in pixels
        const referenceWidthPixels = img.naturalWidth;
        const referenceHeightPixels = img.naturalHeight;

        // Get OCR page dimensions
        const ocrWidth = box.width || referenceWidthPixels;
        const ocrHeight = box.height || referenceHeightPixels;

        // Calculate scale factors from OCR coordinate space (pixels) to displayed size
        const scaleX = displayedWidth / ocrWidth;
        const scaleY = displayedHeight / ocrHeight;

        // Get bounding box coordinates
        let x, y, width, height;
        if (bboxArray.length >= 8) {
          // Polygon format: [x1, y1, x2, y2, x3, y3, x4, y4]
          const xs = [bboxArray[0], bboxArray[2], bboxArray[4], bboxArray[6]];
          const ys = [bboxArray[1], bboxArray[3], bboxArray[5], bboxArray[7]];
          const minX = Math.min(...xs);
          const maxX = Math.max(...xs);
          const minY = Math.min(...ys);
          const maxY = Math.max(...ys);

          // Scale to displayed size
          x = minX * scaleX;
          y = minY * scaleY;
          width = (maxX - minX) * scaleX;
          height = (maxY - minY) * scaleY;
        } else if (bboxArray.length >= 4) {
          // Rectangle format: [x1, y1, x2, y2]
          const x1 = bboxArray[0];
          const y1 = bboxArray[1];
          const x2 = bboxArray[2];
          const y2 = bboxArray[3];

          // Scale to displayed size
          x = Math.min(x1, x2) * scaleX;
          y = Math.min(y1, y2) * scaleY;
          width = Math.abs(x2 - x1) * scaleX;
          height = Math.abs(y2 - y1) * scaleY;
        } else {
          return;
        }

        // Ensure valid dimensions
        if (width <= 0 || height <= 0 || isNaN(x) || isNaN(y) || x < 0 || y < 0) {
          return;
        }

        // Validate: ensure bounding box is reasonable for the text
        // Estimate expected width based on text length (roughly 8-10 pixels per character)
        const boxText = box.text || '';
        const expectedWidth = boxText.length * 8; // Conservative estimate
        const actualWidth = width / scaleX; // Convert back to OCR coordinates for comparison

        // If the box is suspiciously large (more than 4x expected), it might include extra content
        // Log a warning but still draw it (backend should have caught this, but double-check)
        if (actualWidth > expectedWidth * 4) {
          console.warn(`Suspiciously large bounding box detected: width=${actualWidth.toFixed(1)}px, expected=${expectedWidth.toFixed(1)}px for text "${boxText.substring(0, 50)}..."`);
          // Still draw it, but the backend validation should prevent this
        }

        // Draw border with specified opacity - use exact coordinates, no padding
        ctx.strokeStyle = `rgba(255, 200, 0, ${opacity})`;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, width, height);
      }
    });
  };

  const drawHighlights = (boxes, fadeIn = false) => {
    if (!fileData) return;

    // For images, draw on canvas overlay
    if (fileData.type === 'image' && imageRef.current) {
      const img = imageRef.current;

      // Wait for image to be fully loaded with retry mechanism
      if (!img.complete || img.naturalWidth === 0 || img.naturalHeight === 0) {
        // Retry with exponential backoff (max 5 retries = ~3 seconds total)
        const retryCount = (drawHighlights.retryCount || 0) + 1;
        if (retryCount < 5) {
          drawHighlights.retryCount = retryCount;
          setTimeout(() => drawHighlights(boxes, fadeIn), 200 * retryCount);
        } else {
          drawHighlights.retryCount = 0;
        }
        return;
      }
      drawHighlights.retryCount = 0; // Reset on success

      let canvas = canvasRef.current;

      if (!canvas) {
        // Create canvas overlay if it doesn't exist
        canvas = document.createElement('canvas');
        canvas.style.position = 'absolute';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '10';
        canvas.style.transition = 'opacity 0.3s ease-in-out';
        canvasRef.current = canvas;

        const container = img.parentElement;
        if (container) {
          container.style.position = 'relative';
          container.appendChild(canvas);
        }
      }

      // Update canvas size to match image display size
      // Get the actual displayed image dimensions
      const imgRect = img.getBoundingClientRect();
      const containerRect = img.parentElement?.getBoundingClientRect();

      // Get actual displayed dimensions (accounting for zoom and CSS transforms)
      const displayedWidth = imgRect.width;
      const displayedHeight = imgRect.height;

      // Calculate image position relative to container
      const imgOffsetX = imgRect.left - (containerRect?.left || 0);
      const imgOffsetY = imgRect.top - (containerRect?.top || 0);

      // Position canvas to match image exactly
      canvas.style.top = `${imgOffsetY}px`;
      canvas.style.left = `${imgOffsetX}px`;


      // Set canvas to match displayed image size exactly
      canvas.width = displayedWidth;
      canvas.height = displayedHeight;
      canvas.style.width = `${displayedWidth}px`;
      canvas.style.height = `${displayedHeight}px`;

      const ctx = canvas.getContext('2d');

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw previous highlights with fade-out opacity (if transitioning)
      if (previousHighlightBoxes.length > 0 && fadeIn && boxes.length > 0) {
        drawHighlightBoxes(ctx, previousHighlightBoxes, img, displayedWidth, displayedHeight, 0.3); // Fade out opacity
      }

      // Draw new highlights with fade-in effect
      if (boxes.length > 0) {
        const opacity = fadeIn ? 0.4 : 0.8; // Start at lower opacity if fading in
        drawHighlightBoxes(ctx, boxes, img, displayedWidth, displayedHeight, opacity);

        // If fading in, animate to full opacity
        if (fadeIn) {
          setTimeout(() => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            // Redraw previous highlights (fading out)
            if (previousHighlightBoxes.length > 0) {
              drawHighlightBoxes(ctx, previousHighlightBoxes, img, displayedWidth, displayedHeight, 0.15);
            }
            // Draw new highlights at full opacity
            drawHighlightBoxes(ctx, boxes, img, displayedWidth, displayedHeight, 0.8);
          }, 50);
        }
      }
    }

    // For PDFs, we can't easily draw overlays on iframes
    // We'll show a message or use PDF.js for more advanced highlighting
    if (fileData.type === 'pdf') {
      console.log('PDF highlighting requires PDF.js library for advanced features');
      // Don't auto-scroll when highlighting - let user control the view
    }
  };

  const handleDownload = () => {
    // If extractedData is available, download as Excel (CSV)
    if (extractedData && extractedData.key_value_pairs) {
      const keyValuePairs = extractedData.key_value_pairs;

      // Convert to CSV format (Excel-compatible)
      // Add UTF-8 BOM for Excel to recognize encoding
      const BOM = '\uFEFF';
      let csvContent = BOM + "Field,Value\n";

      for (const [key, value] of Object.entries(keyValuePairs)) {
        // Escape quotes and handle special characters
        const escapedKey = String(key).replace(/"/g, '""');
        const escapedValue = String(value).replace(/"/g, '""');
        csvContent += `"${escapedKey}","${escapedValue}"\n`;
      }

      // Create blob and download as CSV file (Excel will open it)
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // Create filename from original filename
      const csvFilename = (filename || 'extracted_data').replace(/\.(json|pdf|png|jpg|jpeg)$/i, '') + '_data.csv';
      a.download = csvFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else if (fileData?.blob) {
      // Download source file as-is
      const url = URL.createObjectURL(fileData.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'source_file';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.25, 3));
    // Redraw highlights after zoom
    setTimeout(() => {
      if (highlightBoxes.length > 0) {
        drawHighlights(highlightBoxes);
      }
    }, 100);
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.min(prev - 0.25, 3));
    // Redraw highlights after zoom
    setTimeout(() => {
      if (highlightBoxes.length > 0) {
        drawHighlights(highlightBoxes);
      }
    }, 100);
  };


  const renderPdfPage = async (pdf, pageNum, forceNewCanvas = false) => {
    try {
      // Cancel any existing render task for this page
      if (pdfRenderTasks.current[pageNum]) {
        try {
          pdfRenderTasks.current[pageNum].cancel();
          // Wait for cancellation to complete - catch the promise rejection
          await pdfRenderTasks.current[pageNum].promise.catch(() => {
            // Expected rejection when cancelled
          });
        } catch (e) {
          // Ignore cancellation errors
        }
        delete pdfRenderTasks.current[pageNum];
      }

      const page = await pdf.getPage(pageNum);
      const viewport = page.getViewport({ scale: zoom });

      // Get or create canvas for this page
      let canvas = pdfCanvasRefs.current[pageNum];
      let overlayCanvas = pdfOverlayRefs.current[pageNum];
      const pdfContainer = pdfContainerRef.current || containerRef.current?.querySelector('.pdf-pages-container');

      // If forceNewCanvas is true or canvas dimensions don't match, recreate canvas
      if (forceNewCanvas || !canvas || canvas.height !== viewport.height || canvas.width !== viewport.width) {
        // Remove old canvas and overlay if they exist
        if (canvas && canvas.parentNode) {
          canvas.parentNode.removeChild(canvas);
        }
        if (overlayCanvas && overlayCanvas.parentNode) {
          overlayCanvas.parentNode.removeChild(overlayCanvas);
        }

        // Create container div for canvas and overlay
        const canvasContainer = document.createElement('div');
        canvasContainer.className = 'relative mb-4 mx-auto inline-block';
        canvasContainer.style.position = 'relative';

        // Create new canvas
        canvas = document.createElement('canvas');
        canvas.className = 'pdf-page-canvas block shadow-lg';
        canvas.id = `pdf-page-${pageNum}`;
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        pdfCanvasRefs.current[pageNum] = canvas;
        canvasContainer.appendChild(canvas);

        // Create overlay canvas for highlights
        overlayCanvas = document.createElement('canvas');
        overlayCanvas.className = 'pdf-overlay-canvas';
        overlayCanvas.id = `pdf-overlay-${pageNum}`;
        overlayCanvas.height = viewport.height;
        overlayCanvas.width = viewport.width;
        // Set CSS size to match canvas size
        overlayCanvas.style.width = `${viewport.width}px`;
        overlayCanvas.style.height = `${viewport.height}px`;
        overlayCanvas.style.position = 'absolute';
        overlayCanvas.style.top = '0';
        overlayCanvas.style.left = '0';
        overlayCanvas.style.pointerEvents = 'none';
        overlayCanvas.style.zIndex = '10';
        overlayCanvas.style.imageRendering = 'pixelated'; // Prevent blurring
        pdfOverlayRefs.current[pageNum] = overlayCanvas;
        canvasContainer.appendChild(overlayCanvas);

        // Add container to PDF container
        if (pdfContainer) {
          pdfContainer.appendChild(canvasContainer);
        }
      } else {
        // Canvas exists, but ensure overlay exists too
        if (!overlayCanvas) {
          // Find the canvas container or create one
          let canvasContainer = canvas.parentElement;
          if (!canvasContainer || canvasContainer.tagName !== 'DIV') {
            // Create container if it doesn't exist
            canvasContainer = document.createElement('div');
            canvasContainer.className = 'relative mb-4 mx-auto inline-block';
            canvasContainer.style.position = 'relative';
            canvas.parentNode.insertBefore(canvasContainer, canvas);
            canvasContainer.appendChild(canvas);
          }
          
          // Create overlay canvas
          overlayCanvas = document.createElement('canvas');
          overlayCanvas.className = 'pdf-overlay-canvas';
          overlayCanvas.id = `pdf-overlay-${pageNum}`;
          overlayCanvas.height = viewport.height;
          overlayCanvas.width = viewport.width;
          // Set CSS size to match canvas size
          overlayCanvas.style.width = `${viewport.width}px`;
          overlayCanvas.style.height = `${viewport.height}px`;
          overlayCanvas.style.position = 'absolute';
          overlayCanvas.style.top = '0';
          overlayCanvas.style.left = '0';
          overlayCanvas.style.pointerEvents = 'none';
          overlayCanvas.style.zIndex = '10';
          overlayCanvas.style.imageRendering = 'pixelated'; // Prevent blurring
          pdfOverlayRefs.current[pageNum] = overlayCanvas;
          canvasContainer.appendChild(overlayCanvas);
        } else {
          // Update overlay canvas dimensions if they don't match
          if (overlayCanvas.height !== viewport.height || overlayCanvas.width !== viewport.width) {
            overlayCanvas.height = viewport.height;
            overlayCanvas.width = viewport.width;
          }
        }
      }

      // Get 2D context
      const context = canvas.getContext('2d');

      // Clear canvas before rendering
      context.clearRect(0, 0, canvas.width, canvas.height);

      // Render PDF page to canvas
      const renderContext = {
        canvasContext: context,
        viewport: viewport
      };

      // Start render and track the task
      const renderTask = page.render(renderContext);
      pdfRenderTasks.current[pageNum] = renderTask;

      // Wait for render to complete
      await renderTask.promise;

      // Clear the task reference after completion
      delete pdfRenderTasks.current[pageNum];

      // Update pages array
      setPdfPages(prev => {
        const newPages = [...prev];
        if (!newPages.includes(pageNum)) {
          newPages.push(pageNum);
          newPages.sort((a, b) => a - b);
        }
        return newPages;
      });

      // Draw highlights if available (after a short delay to ensure rendering is complete)
      if (highlightBoxes.length > 0) {
        setTimeout(() => drawPdfHighlights(canvas, page, viewport, pageNum), 200);
      }
    } catch (err) {
      // Ignore cancellation errors
      if (err.name !== 'RenderingCancelledException' &&
        err.message !== 'Rendering cancelled' &&
        !err.message?.includes('cancelled')) {
        console.error(`Error rendering PDF page ${pageNum}:`, err);
      }
      // Clear the task reference on error
      delete pdfRenderTasks.current[pageNum];
    }
  };

  // Helper function to draw PDF highlight boxes with opacity
  const drawPdfHighlightBoxes = (ctx, page, viewport, boxes, opacity = 0.8) => {
    const originalViewport = page.getViewport({ scale: 1.0 });
    const INCHES_TO_POINTS = 72;

    boxes.forEach(box => {
      if (box.bbox && box.bbox.length >= 4) {
        // Parse bounding box
        let bboxArray = box.bbox;
        if (typeof bboxArray === 'string') {
          try {
            const coordPattern = /\[([\d.]+),\s*([\d.]+)\]/g;
            const matches = [...bboxArray.matchAll(coordPattern)];
            if (matches.length >= 4) {
              bboxArray = matches.flatMap(m => [parseFloat(m[1]), parseFloat(m[2])]);
            } else {
              const cleaned = bboxArray.replace(/[\[\]]/g, '').trim();
              const parts = cleaned.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
              if (parts.length >= 8) {
                bboxArray = parts;
              } else if (parts.length >= 4) {
                bboxArray = parts;
              } else {
                return;
              }
            }
          } catch (e) {
            return;
          }
        }

        const ocrWidth = box.width;
        const ocrHeight = box.height;
        
        // Try to determine coordinate system
        // PDF coordinates are typically in points (1/72 inch)
        // OCR coordinates might be in pixels, inches, or points
        const isLikelyInches = ocrWidth && ocrHeight && ocrWidth < 100 && ocrHeight < 100;
        const isLikelyPixels = ocrWidth && ocrHeight && ocrWidth > 500 && ocrHeight > 500;
        
        // Get PDF page dimensions in points (at scale 1.0)
        const referenceWidthPoints = originalViewport.width;
        const referenceHeightPoints = originalViewport.height;
        
        let unitMultiplier = 1;
        let ocrWidthPoints, ocrHeightPoints;
        
        if (isLikelyInches) {
          // OCR coordinates are in inches, convert to points
          unitMultiplier = INCHES_TO_POINTS;
          ocrWidthPoints = ocrWidth ? (ocrWidth * unitMultiplier) : referenceWidthPoints;
          ocrHeightPoints = ocrHeight ? (ocrHeight * unitMultiplier) : referenceHeightPoints;
        } else if (isLikelyPixels && ocrWidth && ocrHeight) {
          // OCR coordinates are in pixels, need to scale to PDF points
          // Assume OCR was done at a certain DPI (typically 300 DPI for documents)
          // But we'll use the ratio of PDF dimensions to OCR dimensions
          ocrWidthPoints = referenceWidthPoints;
          ocrHeightPoints = referenceHeightPoints;
          // Scale coordinates by the ratio
          unitMultiplier = referenceWidthPoints / ocrWidth;
        } else {
          // Assume OCR coordinates are already in the same units as PDF (points)
          // Or use the provided dimensions directly
          ocrWidthPoints = ocrWidth || referenceWidthPoints;
          ocrHeightPoints = ocrHeight || referenceHeightPoints;
          unitMultiplier = 1;
        }
        
        const scaleX = viewport.width / ocrWidthPoints;
        const scaleY = viewport.height / ocrHeightPoints;
        
        console.log(`PDF Highlight coords: ocrWidth=${ocrWidth}, ocrHeight=${ocrHeight}, ` +
                   `pdfWidth=${referenceWidthPoints}, pdfHeight=${referenceHeightPoints}, ` +
                   `viewportWidth=${viewport.width}, viewportHeight=${viewport.height}, ` +
                   `scaleX=${scaleX.toFixed(3)}, scaleY=${scaleY.toFixed(3)}, unitMultiplier=${unitMultiplier}`);

        let x, y, width, height;
        if (bboxArray.length >= 8) {
          const xs = [bboxArray[0] * unitMultiplier, bboxArray[2] * unitMultiplier,
          bboxArray[4] * unitMultiplier, bboxArray[6] * unitMultiplier];
          const ys = [bboxArray[1] * unitMultiplier, bboxArray[3] * unitMultiplier,
          bboxArray[5] * unitMultiplier, bboxArray[7] * unitMultiplier];
          const minX = Math.min(...xs);
          const maxX = Math.max(...xs);
          const minY = Math.min(...ys);
          const maxY = Math.max(...ys);
          x = minX * scaleX;
          width = (maxX - minX) * scaleX;
          y = minY * scaleY;
          height = (maxY - minY) * scaleY;
        } else if (bboxArray.length >= 4) {
          const x1 = bboxArray[0] * unitMultiplier;
          const y1 = bboxArray[1] * unitMultiplier;
          const x2 = bboxArray[2] * unitMultiplier;
          const y2 = bboxArray[3] * unitMultiplier;
          x = x1 * scaleX;
          width = (x2 - x1) * scaleX;
          y = Math.min(y1, y2) * scaleY;
          height = Math.abs(y2 - y1) * scaleY;
        } else {
          return;
        }

        if (width <= 0 || height <= 0 || isNaN(x) || isNaN(y)) {
          console.warn(`Invalid highlight dimensions: x=${x}, y=${y}, width=${width}, height=${height}`);
          return;
        }

        // Ensure coordinates are within canvas bounds
        const canvasWidth = ctx.canvas.width;
        const canvasHeight = ctx.canvas.height;
        
        // Clamp coordinates to canvas bounds
        const clampedX = Math.max(0, Math.min(x, canvasWidth));
        const clampedY = Math.max(0, Math.min(y, canvasHeight));
        const clampedWidth = Math.min(width, canvasWidth - clampedX);
        const clampedHeight = Math.min(height, canvasHeight - clampedY);
        
        if (x !== clampedX || y !== clampedY || width !== clampedWidth || height !== clampedHeight) {
          console.warn(`Highlight adjusted: original x=${x.toFixed(1)}, y=${y.toFixed(1)}, w=${width.toFixed(1)}, h=${height.toFixed(1)} -> ` +
                     `clamped x=${clampedX.toFixed(1)}, y=${clampedY.toFixed(1)}, w=${clampedWidth.toFixed(1)}, h=${clampedHeight.toFixed(1)}`);
        }

        if (clampedWidth <= 0 || clampedHeight <= 0) {
          console.warn(`Invalid highlight dimensions after clamping: w=${clampedWidth}, h=${clampedHeight}`);
          return;
        }

        // Draw border only (no fill) - use a more visible color
        ctx.strokeStyle = `rgba(255, 200, 0, ${opacity})`;
        ctx.lineWidth = 3; // Slightly thicker for better visibility
        ctx.strokeRect(clampedX, clampedY, clampedWidth, clampedHeight);
        
        console.log(`✓ Drew highlight at x=${clampedX.toFixed(1)}, y=${clampedY.toFixed(1)}, w=${clampedWidth.toFixed(1)}, h=${clampedHeight.toFixed(1)}, opacity=${opacity}`);
      }
    });
  };

  const drawPdfHighlights = (canvas, page, viewport, pageNum, fadeIn = false) => {
    // Use overlay canvas instead of main canvas for highlights
    let overlayCanvas = pdfOverlayRefs.current[pageNum];
    
    // If overlay doesn't exist, create it
    if (!overlayCanvas && canvas) {
      const canvasContainer = canvas.parentElement;
      if (canvasContainer) {
        overlayCanvas = document.createElement('canvas');
        overlayCanvas.className = 'pdf-overlay-canvas';
        overlayCanvas.id = `pdf-overlay-${pageNum}`;
        overlayCanvas.height = viewport.height;
        overlayCanvas.width = viewport.width;
        // Set CSS size to match canvas size
        overlayCanvas.style.width = `${viewport.width}px`;
        overlayCanvas.style.height = `${viewport.height}px`;
        overlayCanvas.style.position = 'absolute';
        overlayCanvas.style.top = '0';
        overlayCanvas.style.left = '0';
        overlayCanvas.style.pointerEvents = 'none';
        overlayCanvas.style.zIndex = '10';
        overlayCanvas.style.imageRendering = 'pixelated'; // Prevent blurring
        pdfOverlayRefs.current[pageNum] = overlayCanvas;
        canvasContainer.appendChild(overlayCanvas);
      } else {
        // If container doesn't exist, wait and retry
        setTimeout(() => {
          drawPdfHighlights(canvas, page, viewport, pageNum, fadeIn);
        }, 100);
        return;
      }
    }
    
    if (!overlayCanvas) {
      return;
    }

    // Ensure overlay dimensions match viewport
    if (overlayCanvas.width !== viewport.width || overlayCanvas.height !== viewport.height) {
      overlayCanvas.width = viewport.width;
      overlayCanvas.height = viewport.height;
    }
    
    // Ensure overlay is visible and properly positioned
    if (overlayCanvas.style.position !== 'absolute') {
      overlayCanvas.style.position = 'absolute';
      overlayCanvas.style.top = '0';
      overlayCanvas.style.left = '0';
      overlayCanvas.style.pointerEvents = 'none';
      overlayCanvas.style.zIndex = '10';
    }
    
    // Verify overlay is in the DOM
    if (!overlayCanvas.parentElement) {
      console.error(`Overlay canvas for page ${pageNum} is not in DOM!`);
      const canvasContainer = canvas.parentElement;
      if (canvasContainer) {
        canvasContainer.appendChild(overlayCanvas);
        console.log(`Re-attached overlay canvas for page ${pageNum}`);
      } else {
        console.error(`Cannot attach overlay - no container found for page ${pageNum}`);
        return;
      }
    }

    const ctx = overlayCanvas.getContext('2d');
    const pageBoxes = highlightBoxes.filter(box => box.page === pageNum);
    const previousPageBoxes = previousHighlightBoxes.filter(box => box.page === pageNum);
    
    console.log(`Page ${pageNum}: Found ${pageBoxes.length} highlight box(es) to draw`);

    // Ensure overlay canvas CSS size matches the main canvas
    const mainCanvas = pdfCanvasRefs.current[pageNum];
    if (mainCanvas) {
      const mainRect = mainCanvas.getBoundingClientRect();
      overlayCanvas.style.width = `${mainRect.width}px`;
      overlayCanvas.style.height = `${mainRect.height}px`;
    }

    // Clear overlay canvas
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    // Draw previous highlights with fade-out opacity (if transitioning)
    if (previousPageBoxes.length > 0 && fadeIn && pageBoxes.length > 0) {
      drawPdfHighlightBoxes(ctx, page, viewport, previousPageBoxes, 0.3);
    }

    if (pageBoxes.length === 0) {
      console.log(`No highlights to draw for page ${pageNum}`);
      return;
    }

    console.log(`Drawing ${pageBoxes.length} highlight(s) on page ${pageNum}`);
    
    // Draw new highlights with fade-in effect
    const opacity = fadeIn ? 0.4 : 0.8;
    drawPdfHighlightBoxes(ctx, page, viewport, pageBoxes, opacity);
    
    // Force browser to repaint the overlay
    overlayCanvas.style.opacity = '0.99';
    setTimeout(() => {
      overlayCanvas.style.opacity = '1';
    }, 10);

    // If fading in, animate to full opacity
    if (fadeIn) {
      setTimeout(() => {
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        // Redraw previous highlights (fading out)
        if (previousPageBoxes.length > 0) {
          drawPdfHighlightBoxes(ctx, page, viewport, previousPageBoxes, 0.15);
        }
        // Draw new highlights at full opacity
        drawPdfHighlightBoxes(ctx, page, viewport, pageBoxes, 0.8);
      }, 50);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      const newPage = currentPage - 1;
      setCurrentPage(newPage);
      if (pdfDocument) {
        renderPdfPage(pdfDocument, newPage);
        // Scroll to page
        const canvas = pdfCanvasRefs.current[newPage];
        if (canvas && containerRef.current) {
          canvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      const newPage = currentPage + 1;
      setCurrentPage(newPage);
      if (pdfDocument) {
        renderPdfPage(pdfDocument, newPage);
        // Scroll to page
        const canvas = pdfCanvasRefs.current[newPage];
        if (canvas && containerRef.current) {
          canvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    }
  };

  // Render PDF pages when zoom changes
  useEffect(() => {
    if (pdfDocument && pdfPages.length > 0) {
      // Render pages sequentially to avoid canvas conflicts
      // Force new canvas creation when zoom changes to avoid conflicts
      const reRenderPages = async () => {
        for (const pageNum of pdfPages) {
          await renderPdfPage(pdfDocument, pageNum, true); // true = force new canvas
          // Redraw highlights after re-rendering
          if (highlightBoxes.length > 0) {
            const canvas = pdfCanvasRefs.current[pageNum];
            if (canvas) {
              pdfDocument.getPage(pageNum).then(page => {
                const viewport = page.getViewport({ scale: zoom });
                drawPdfHighlights(canvas, page, viewport, pageNum);
              });
            }
          }
        }
      };
      reRenderPages();
    }
  }, [zoom]);

  // Render all PDF pages on load
  useEffect(() => {
    if (pdfDocument && fileData?.type === 'pdf' && totalPages > 0) {
      // Clear existing canvases
      const pdfContainer = pdfContainerRef.current || containerRef.current?.querySelector('.pdf-pages-container');
      if (pdfContainer) {
        pdfContainer.innerHTML = '';
      }
      pdfCanvasRefs.current = {};
      setPdfPages([]);

      // Render all pages sequentially
      const renderAllPages = async () => {
        for (let i = 1; i <= totalPages; i++) {
          await renderPdfPage(pdfDocument, i);
        }
      };
      renderAllPages();
    }
  }, [pdfDocument, totalPages, fileData?.type]);

  // Draw highlights on PDF pages when highlightBoxes change
  useEffect(() => {
    if (pdfDocument && highlightBoxes.length > 0 && pdfPages.length > 0) {
      const drawHighlightsOnPages = async () => {
        for (const pageNum of pdfPages) {
          const canvas = pdfCanvasRefs.current[pageNum];
          if (canvas) {
            try {
              const page = await pdfDocument.getPage(pageNum);
              const viewport = page.getViewport({ scale: zoom });
              // Use fadeIn=true for seamless transitions when highlights change
              drawPdfHighlights(canvas, page, viewport, pageNum, true);
            } catch (err) {
              console.error(`Error drawing highlights on page ${pageNum}:`, err);
            }
          }
        }
      };
      setTimeout(() => drawHighlightsOnPages(), 300);
    }
  }, [highlightBoxes, pdfDocument, pdfPages, zoom]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        margin: 0,
        padding: '1rem'
      }}
    >
      <Card className={`w-full ${extractedData ? 'max-w-[95vw]' : 'max-w-6xl'} h-full flex flex-col`}>
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex flex-col gap-2 flex-1 min-w-0 overflow-hidden">
            <h3 className="text-lg font-semibold flex-shrink-0">
              Source File: {filename || sourceBlobPath?.split('/').pop() || 'Unknown'}
            </h3>
            {(highlightText || localHighlightText) && (
              <div className="relative">
                <div
                  ref={badgeRef}
                  className="flex items-center gap-2 px-3 py-1.5 bg-black dark:bg-black rounded-md border border-gray-700 shadow-sm min-w-0 max-w-md overflow-hidden cursor-help transition-all hover:border-gray-500"
                  onMouseEnter={() => {
                    if (badgeRef.current) {
                      const activeText = highlightText || localHighlightText;
                      const rect = badgeRef.current.getBoundingClientRect();
                      const tooltipWidth = Math.min(600, Math.max(300, activeText.length * 8));
                      const left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
                      const top = rect.bottom + 12;

                      // Ensure tooltip stays within viewport
                      const viewportWidth = window.innerWidth;
                      const viewportHeight = window.innerHeight;
                      const adjustedLeft = Math.max(16, Math.min(left, viewportWidth - tooltipWidth - 16));
                      const adjustedTop = top + 200 > viewportHeight ? rect.top - 200 : top;

                      setTooltipPosition({
                        top: adjustedTop,
                        left: adjustedLeft
                      });
                      setShowTooltip(true);
                    }
                  }}
                  onMouseLeave={() => setShowTooltip(false)}
                >
                  <span className="text-xs font-semibold text-white flex-shrink-0">Highlighting:</span>
                  <span className="text-sm text-white font-mono truncate min-w-0">
                    {highlightText || localHighlightText}
                  </span>
                </div>
                {showTooltip && (
                  <div
                    ref={tooltipRef}
                    className="fixed z-[100] px-4 py-3 bg-gray-900 text-white text-sm rounded-lg shadow-2xl border border-gray-700 animate-in fade-in-0 zoom-in-95 duration-200"
                    style={{
                      minWidth: '300px',
                      maxWidth: '600px',
                      wordBreak: 'break-word',
                      top: `${tooltipPosition.top}px`,
                      left: `${tooltipPosition.left}px`,
                      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.2)'
                    }}
                    onMouseEnter={() => setShowTooltip(true)}
                    onMouseLeave={() => setShowTooltip(false)}
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-semibold mb-2 text-gray-300 uppercase tracking-wide">
                        Full Text
                      </div>
                      <div className="text-sm font-mono text-white leading-relaxed whitespace-pre-wrap break-words">
                        {highlightText || localHighlightText}
                      </div>
                    </div>
                    {/* Arrow pointing up to badge */}
                    <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
                      <div className="border-4 border-transparent border-b-gray-900"></div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {fileData && (
              <>
                <Button variant="outline" size="sm" onClick={handleZoomOut}>
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <span className="text-sm">{Math.round(zoom * 100)}%</span>
                <Button variant="outline" size="sm" onClick={handleZoomIn}>
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" onClick={handleDownload}>
                  <Download className="h-4 w-4" />
                </Button>
              </>
            )}
            <Button variant="outline" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className={`flex-1 ${extractedData ? 'grid grid-cols-[60%_40%]' : 'flex flex-col'} overflow-hidden`}>
          {/* Left side: Source File Viewer */}
          <div
            className={`${extractedData ? 'border-r' : ''} overflow-auto p-4 h-full`}
            ref={containerRef}
          >
            {loading && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                  <p>Loading source file...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-red-500">
                  <p className="text-lg font-semibold mb-2">Error</p>
                  <p>{error}</p>
                </div>
              </div>
            )}

            {fileData && !loading && !error && (
              <div className="flex flex-col items-center justify-center min-h-full relative w-full">
                {fileData.type === 'pdf' && (
                  <>
                    {/* PDF Navigation Controls */}
                    {totalPages > 0 && (
                      <div className="flex items-center gap-4 mb-4 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handlePreviousPage}
                          disabled={currentPage <= 1}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <span className="text-sm font-medium text-white">
                          Page {currentPage} of {totalPages}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleNextPage}
                          disabled={currentPage >= totalPages}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                    {/* PDF Pages Container */}
                    <div
                      ref={pdfContainerRef}
                      className="w-full overflow-auto pdf-pages-container"
                      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px', minHeight: '100%' }}
                    >
                      {/* PDF pages are rendered as canvases and appended here dynamically */}
                    </div>
                  </>
                )}
                {fileData.type === 'image' && (
                  <div className="relative inline-block w-full flex justify-center items-start">
                    <img
                      ref={imageRef}
                      src={fileData.url}
                      alt="Source document"
                      className="object-contain"
                      style={{
                        transform: `scale(${zoom})`,
                        transition: 'transform 0.2s',
                        maxWidth: '100%',
                        height: 'auto'
                      }}
                      onLoad={() => {
                        // Redraw highlights when image loads
                        if (highlightBoxes.length > 0) {
                          setTimeout(() => drawHighlights(highlightBoxes), 100);
                        }
                      }}
                    />
                    <canvas
                      ref={canvasRef}
                      className="absolute top-0 left-0 pointer-events-none"
                      style={{ zIndex: 10 }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right side: Key-Value Pairs */}
          {extractedData && (
            <div className="overflow-auto p-4 bg-gray-50 h-full">
              <h3 className="text-lg font-semibold mb-4 top-0 bg-gray-50 pb-2 border-b">
                Extracted Data
              </h3>
              <div className="space-y-3">
                {extractedData.key_value_pairs && Object.keys(extractedData.key_value_pairs).length > 0 ? (
                  Object.entries(extractedData.key_value_pairs).map(([key, value]) => (
                    <div
                      key={key}
                      className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
                      onClick={() => {
                        const valueStr = typeof value === 'object' ? JSON.stringify(value) : String(value || '');
                        setLocalHighlightText(`${key}: ${valueStr}`);
                      }}
                      title="Click to highlight this field in the source document"
                    >
                      <div className="text-sm font-semibold text-gray-600 mb-1">
                        {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                      <div className="text-base text-gray-900 break-words">
                        {typeof value === 'object' ? (
                          <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                            {JSON.stringify(value, null, 2)}
                          </pre>
                        ) : (
                          String(value || '-')
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    No extracted data available
                  </div>
                )}
              </div>

              {/* Show confidence score if available */}
              {(extractedData.ocr_confidence_score !== undefined || extractedData.confidence_score !== undefined) && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="text-sm font-semibold text-blue-900 mb-1">
                    Confidence Score
                  </div>
                  <div className="text-2xl font-bold text-blue-600">
                    {(() => {
                      const score = extractedData.ocr_confidence_score !== undefined
                        ? extractedData.ocr_confidence_score
                        : extractedData.confidence_score;
                      // If score is between 0-1, multiply by 100, otherwise use as is
                      const percentage = score <= 1 ? score * 100 : score;
                      return percentage.toFixed(2);
                    })()}%
                  </div>
                </div>
              )}

              {/* Show document classification if available */}
              {extractedData.document_classification && (
                <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-200">
                  <div className="text-sm font-semibold text-green-900 mb-1">
                    Document Type
                  </div>
                  <div className="text-base font-medium text-green-700">
                    {extractedData.document_classification}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

export default SourceFileViewer;

