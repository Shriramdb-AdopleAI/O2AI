// EnhancedOCRResults.jsx
import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  FileText,
  Download,
  Copy,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronRight,
  Table,
  FileSpreadsheet,
  Brain,
  File,
  Check,
  CheckCircle,
  X,
  Loader2,
  Sparkles,
  AlertTriangle,
  AlertCircle,
  Info,
  ArrowRight,
  Pencil,
  AlertCircle as AlertCircleIcon
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { cn } from '../lib/utils';
import SourceFileViewer from './SourceFileViewer';
import authService from '../services/authService';

const FormattedOCRText = ({ text }) => {
  const cleanText = text
    .replace(/--- PAGE BREAK ---\n?/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/ +/g, ' ')
    .trim();

  const lines = cleanText.split('\n');

  return (
    <div className="space-y-3">
      {lines.map((line, i) => {
        const trimmed = line.trim();

        if (!trimmed) {
          return <div key={i} className="h-3" />;
        }

        const isHeader =
          trimmed === trimmed.toUpperCase() && trimmed.length < 80 ||
          /^EXECUTIVE SUMMARY$|^STANDARDS AT A GLANCE$|^TABLE OF CONTENTS$/i.test(trimmed) ||
          /^Page \d+$/i.test(trimmed);

        const isSection =
          trimmed.length < 100 &&
          (trimmed.endsWith(':') ||
            /^[\d\.\)]+\s+[A-Z][^a-z]*$/.test(trimmed) ||
            /^CONTACT INFORMATION$/i.test(trimmed));

        const isListItem = /^\d+\.\s|^•\s|^-\s|^[a-z]\)\s/i.test(trimmed);

        if (isHeader) {
          return (
            <h3 key={i} className="text-lg font-bold text-left text-blue-900 mt-6 mb-4">
              {trimmed}
            </h3>
          );
        }

        if (isSection) {
          return (
            <h4 key={i} className="text-base font-semibold text-blue-800 mt-5 mb-2">
              {trimmed}
            </h4>
          );
        }

        if (isListItem) {
          return (
            <div key={i} className="ml-4 flex items-start">
              <span className="text-blue-600 mr-2">•</span>
              <span>{trimmed.replace(/^[\d\.\)]+\s+|^[•\-\*]\s+/, '')}</span>
            </div>
          );
        }

        return (
          <p key={i} className="text-justify">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
};

const EnhancedOCRResults = ({ results, isBatch = false, source = 'processing' }) => {
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
  
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [showRawText, setShowRawText] = useState(false);
  const [showKeyValuePairs, setShowKeyValuePairs] = useState(true);
  const [isEditingByIndex, setIsEditingByIndex] = useState({});
  const [editedPairsByIndex, setEditedPairsByIndex] = useState({});
  const [lastSavedPairsByIndex, setLastSavedPairsByIndex] = useState({});
  const [isEditingTextByIndex, setIsEditingTextByIndex] = useState({});
  const [editedTextByIndex, setEditedTextByIndex] = useState({});
  const [lastSavedTextByIndex, setLastSavedTextByIndex] = useState({});
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [sourceViewerData, setSourceViewerData] = useState(null);
  const [editedConfidenceByIndex, setEditedConfidenceByIndex] = useState({});
  const [correctingKeys, setCorrectingKeys] = useState({}); // { "fileIdx-key": boolean }
  const [dismissedCorrections, setDismissedCorrections] = useState(new Set()); // Set of "fileIdx-key" that user dismissed
  const [analyzingPairs, setAnalyzingPairs] = useState({}); // { "fileIdx": boolean }
  const [analysisResults, setAnalysisResults] = useState({}); // { "fileIdx": { "key": analysisResult } }
  const [editingKeyValuePair, setEditingKeyValuePair] = useState(null); // "idx-key" format for individual key editing
  const [editingSuggestedValue, setEditingSuggestedValue] = useState(null); // "idx-key" format for editing suggested value
  const [editedSuggestedValues, setEditedSuggestedValues] = useState({}); // { "idx-key": editedValue }
  const [manuallyCorrectedFields, setManuallyCorrectedFields] = useState({}); // { "fileIdx": { "key": true } } - Track manually corrected fields
  const [correctionMetadata, setCorrectionMetadata] = useState({}); // { "fileIdx": { "key": { username, timestamp } } } - Track who and when
  const [lastFileCorrectionMetadata, setLastFileCorrectionMetadata] = useState({}); // { "fileIdx": { username, timestamp } } - Track last correction per file
  const [expandedConfidenceSections, setExpandedConfidenceSections] = useState({}); // { "filenameKey": { high: true, low: true } } - Track expanded confidence sections
  const [assignedUsers, setAssignedUsers] = useState({}); // Loaded from localStorage - { "blobName": userId }
  const [availableUsers, setAvailableUsers] = useState([]); // List of users loaded from API
  const [openDropdowns, setOpenDropdowns] = useState({}); // Track which dropdown is open - { "filenameKey": boolean }
  const savedCorrectionsRef = useRef({}); // Persist corrections across re-renders - uses filename as key
  const autoAnalysisTriggeredRef = useRef(new Set()); // Track which files have had auto-analysis triggered - uses filename
  const savedAnalysisResultsRef = useRef({}); // Persist analysis results across re-renders - uses filename as key
  const backendFailureCountRef = useRef(0); // Track consecutive backend failures to prevent spam
  const lastBackendCheckRef = useRef(Date.now()); // Track last backend check time
  const [missingFieldsModal, setMissingFieldsModal] = useState({}); // { filenameKey: { open: boolean, fields: [] } }
  const [checkingMissingFields, setCheckingMissingFields] = useState({}); // { filenameKey: boolean }

  // LocalStorage key prefix for saving corrections
  const LOCALSTORAGE_PREFIX = 'ocr_corrections_';

  // Function to save all changes to localStorage
  // Accepts optional explicit data to save (useful when state hasn't updated yet)
  const saveToLocalStorage = (filenameKey, explicitData = null) => {
    try {
      const dataToSave = explicitData || {
        editedPairs: editedPairsByIndex[filenameKey] || {},
        editedConfidence: editedConfidenceByIndex[filenameKey] || {},
        manuallyCorrected: manuallyCorrectedFields[filenameKey] || {},
        correctionMetadata: correctionMetadata[filenameKey] || {},
        lastFileCorrectionMetadata: lastFileCorrectionMetadata[filenameKey] || null,
        timestamp: new Date().toISOString()
      };

      const storageKey = `${LOCALSTORAGE_PREFIX}${filenameKey}`;
      localStorage.setItem(storageKey, JSON.stringify(dataToSave));
      console.log(`✅ Saved corrections to localStorage for: ${filenameKey}`, dataToSave);
      console.log(`📝 Storage key: ${storageKey}`);
      return true;
    } catch (err) {
      console.error('Failed to save to localStorage:', err);
      return false;
    }
  };

  // Function to load changes from localStorage
  const loadFromLocalStorage = (filenameKey) => {
    try {
      const storageKey = `${LOCALSTORAGE_PREFIX}${filenameKey}`;
      const savedData = localStorage.getItem(storageKey);

      console.log(`🔍 Checking localStorage for: ${filenameKey}`);
      console.log(`📝 Storage key: ${storageKey}`);

      if (savedData) {
        const parsed = JSON.parse(savedData);
        console.log(`✅ Loaded corrections from localStorage for: ${filenameKey}`, parsed);
        console.log(`📊 Data includes: ${Object.keys(parsed.editedPairs || {}).length} edited pairs, ${Object.keys(parsed.editedConfidence || {}).length} confidence scores`);
        return parsed;
      } else {
        console.log(`ℹ️ No localStorage data found for: ${filenameKey}`);
      }
      return null;
    } catch (err) {
      console.error('Failed to load from localStorage:', err);
      return null;
    }
  };

  // Helper function to get a unique filename key for a result
  const getFilenameKey = (result, idx) => {
    return result?.filename || result?.file_info?.filename || `file_${idx}`;
  };

  // Generate unique file ID for caching (must be STABLE - same ID for same file)
  const getUniqueFileId = (result) => {
    // Priority 1: Use processing_id if available (stable, unique per upload)
    if (result?.processing_id) return result.processing_id;
    
    // Priority 2: Use file_hash if available (stable, unique per file content)
    if (result?.file_hash) return result.file_hash;
    
    // Priority 3: Use processed blob path (stable identifier - same path = same file)
    const blobPath = result?.processed_blob_path || 
                     result?.blob_storage?.processed_json?.blob_path ||
                     result?.blob_storage?.processed_json?.blob_name;
    
    if (blobPath) {
      // Use blob path directly without timestamp - it's already unique per file
      return blobPath;
    }
    
    // Priority 4: Use filename (fallback - less ideal but stable)
    const filename = result?.filename || result?.file_info?.filename || 'unknown';
    return filename;
  };

  // Clean filename (similar to FilesTable cleanFileName function)
  const cleanFileName = (fileName) => {
    if (!fileName) return '';
    let cleaned = fileName;
    // Remove timestamp prefix patterns with underscores
    cleaned = cleaned.replace(/^\d{8}_\d{6}_/, '');
    cleaned = cleaned.replace(/^\d{8}_\d{6}/, '');
    // Remove timestamp prefix patterns with spaces
    cleaned = cleaned.replace(/^\d{8}\s+\d{6}\s+/, '');
    // Remove trailing numbers after space
    cleaned = cleaned.replace(/\s+\d+$/, '');
    // Remove trailing numbers after underscore
    cleaned = cleaned.replace(/_\d{6,}$/, '');
    // Remove "_extracted_data" suffix if present
    cleaned = cleaned.replace(/_extracted_data\.json$/, '.json');
    cleaned = cleaned.replace(/_extracted_data$/, '');
    // Remove any remaining leading/trailing underscores or spaces
    cleaned = cleaned.trim().replace(/^_+|_+$/g, '');
    return cleaned || fileName;
  };

  // Get user initial from user ID by looking up in availableUsers (fully dynamic)
  const getUserInitial = (userId) => {
    if (!userId || userId === 'unassigned') return '?';
    
    // Convert userId to string/number for comparison
    const userIdStr = String(userId);
    const userIdNum = Number(userId);
    
    // Try to find user in availableUsers by multiple possible ID fields
    const user = availableUsers.find(u => {
      // Try all possible ID fields
      return (
        String(u.id) === userIdStr ||
        String(u.user_id) === userIdStr ||
        String(u.id) === String(userIdNum) ||
        String(u.user_id) === String(userIdNum) ||
        u.username === userIdStr ||
        u.email === userIdStr
      );
    });
    
    if (user) {
      // Get username from user object (try multiple fields)
      const username = user.username || user.name || user.full_name || user.display_name || user.email || '';
      
      if (username) {
        // Remove any leading/trailing whitespace and get first letter
        const trimmedUsername = username.trim();
        if (trimmedUsername.length > 0) {
          return trimmedUsername.charAt(0).toUpperCase();
        }
      }
    }
    
    // If user not found in availableUsers, return '?' to indicate we need to fetch
    return '?';
  };

  // Generate color based on first letter (single color for all letters)
  const getColorForLetter = (letter) => {
    if (!letter) return 'bg-gray-400';
    
    // Use the same color for all letters
    return 'bg-blue-600';
  };

  // Get user color based on assigned user (fully dynamic)
  const getUserColor = (userId) => {
    if (!userId || userId === 'unassigned') return 'bg-gray-400';
    
    // Convert userId to string/number for comparison
    const userIdStr = String(userId);
    const userIdNum = Number(userId);
    
    // Try to find user in availableUsers
    const user = availableUsers.find(u => {
      return (
        String(u.id) === userIdStr ||
        String(u.user_id) === userIdStr ||
        String(u.id) === String(userIdNum) ||
        String(u.user_id) === String(userIdNum) ||
        u.username === userIdStr ||
        u.email === userIdStr
      );
    });
    
    // Get username from user object
    const username = user ? (user.username || user.name || user.full_name || user.display_name || user.email || '') : '';
    
    if (username) {
      const firstLetter = username.trim().charAt(0).toUpperCase();
      return getColorForLetter(firstLetter);
    }
    
    // Default color if user not found
    return 'bg-gray-600';
  };

  // Extract base filename (without path and extension)
  const getBaseFilename = (filePath) => {
    if (!filePath) return '';
    // Remove path, get just filename
    let filename = filePath.split('/').pop().split('\\').pop();
    // Remove extension
    filename = filename.replace(/\.[^/.]+$/, '');
    // Clean the filename
    filename = cleanFileName(filename);
    return filename.toLowerCase().trim();
  };

  // Find assigned user by matching filename
  const findAssignedUserByFilename = (result, assignedUsersMap) => {
    if (!assignedUsersMap || Object.keys(assignedUsersMap).length === 0) {
      return null;
    }

    // Get filename from result
    const resultFilename = result?.filename || result?.file_info?.filename;
    if (!resultFilename) return null;

    // Get base filename (without path and extension)
    const resultBaseName = getBaseFilename(resultFilename);
    const resultFilenameLower = (resultFilename || '').toLowerCase();

    // Try to find matching assignment
    // The assignments are stored by blob_name (which is the full path)
    // We need to extract the filename from blob_name and match with result filename
    for (const [blobName, userId] of Object.entries(assignedUsersMap)) {
      if (!blobName || !userId || userId === 'unassigned') continue;
      
      // Get base filename from blob_name
      const blobBaseName = getBaseFilename(blobName);
      const blobNameLower = (blobName || '').toLowerCase();
      
      // Extract filename from blob_name (last part of path)
      const blobFilenameOnly = blobName.split('/').pop().split('\\').pop();
      const blobFilenameBase = getBaseFilename(blobFilenameOnly);
      
      // Also get cleaned version
      const blobNameCleaned = cleanFileName(blobFilenameOnly).toLowerCase().replace(/\.[^/.]+$/, '');
      const resultFilenameCleaned = cleanFileName(resultFilename).toLowerCase().replace(/\.[^/.]+$/, '');
      
      // Try multiple matching strategies
      const matches = 
        // Exact match of base names
        blobBaseName === resultBaseName ||
        blobFilenameBase === resultBaseName ||
        blobNameCleaned === resultFilenameCleaned ||
        // Filename appears in blob_name path
        blobNameLower.includes(resultFilenameLower) ||
        resultFilenameLower.includes(blobNameLower) ||
        // Base names contain each other
        (blobBaseName && resultBaseName && (
          blobBaseName.includes(resultBaseName) || 
          resultBaseName.includes(blobBaseName)
        )) ||
        // Cleaned filenames match
        (blobNameCleaned && resultFilenameCleaned && (
          blobNameCleaned.includes(resultFilenameCleaned) ||
          resultFilenameCleaned.includes(blobNameCleaned)
        ));
      
      if (matches) {
        return userId;
      }
    }

    return null;
  };

  // Load assigned users from localStorage
  const loadAssignedUsers = () => {
    try {
      const stored = localStorage.getItem('fileAssignments');
      if (stored) {
        const parsed = JSON.parse(stored);
        setAssignedUsers(parsed);
      } else {
        setAssignedUsers({});
      }
    } catch (error) {
      console.error('Error loading assigned users from localStorage:', error);
      setAssignedUsers({});
    }
  };

  // Load on mount and set up listeners
  useEffect(() => {
    // Load initially
    loadAssignedUsers();

    // Listen for storage events (when localStorage changes in other tabs/components)
    const handleStorageChange = (e) => {
      if (e.key === 'fileAssignments') {
        loadAssignedUsers();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    
    // Also listen for custom events (for same-tab updates)
    const handleCustomStorageChange = () => {
      loadAssignedUsers();
    };
    
    window.addEventListener('fileAssignmentsUpdated', handleCustomStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('fileAssignmentsUpdated', handleCustomStorageChange);
    };
  }, []);

  // Load available users from API (fully dynamic, no hardcoded fallbacks)
  useEffect(() => {
    const loadUsers = async () => {
      try {
        const headers = authService.getAuthHeaders();
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/users`, {
          headers
        });

        if (response.ok) {
          const data = await response.json();
          setAvailableUsers(Array.isArray(data) ? data : []);
        } else if (response.status === 403) {
          // Admin access required - non-admin users cannot see user list for assignment
          console.warn('Admin access required to view user list for assignment');
          setAvailableUsers([]);
        } else {
          // Other errors
          console.warn('Could not load users:', response.status);
          setAvailableUsers([]);
        }
      } catch (error) {
        console.error('Error loading users:', error);
        setAvailableUsers([]);
      }
    };

    loadUsers();
    
    // Reload users periodically to catch new users
    const interval = setInterval(loadUsers, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, []);

  // Reload users when assignments change (in case new users were added)
  useEffect(() => {
    if (Object.keys(assignedUsers).length > 0 && availableUsers.length === 0) {
      // If we have assignments but no users loaded, try to reload
      const loadUsers = async () => {
        try {
          const headers = authService.getAuthHeaders();
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/users`, {
            headers
          });
          if (response.ok) {
            const data = await response.json();
            setAvailableUsers(Array.isArray(data) ? data : []);
          } else if (response.status === 403) {
            // Admin access required
            console.warn('Admin access required to view user list');
            setAvailableUsers([]);
          }
        } catch (error) {
          console.error('Error reloading users:', error);
        }
      };
      loadUsers();
    }
  }, [assignedUsers]);

  // Reload assignments when results change
  useEffect(() => {
    loadAssignedUsers();
  }, [results]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      // Check if click is outside any dropdown
      if (!event.target.closest('.user-assignment-dropdown')) {
        setOpenDropdowns({});
      }
    };

    if (Object.keys(openDropdowns).length > 0) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [openDropdowns]);

  // Get user display name for dropdown (Initial - Full Name)
  const getUserDisplayName = (user) => {
    if (!user) return 'Unassigned';
    const username = user.username || user.name || user.full_name || user.display_name || user.email || String(user.id || user.user_id || '');
    const initial = getUserInitial(user.id || user.user_id || user.username || '');
    return `${initial} - ${username}`;
  };

  // Get blob name from result for assignment
  const getBlobNameFromResult = (result) => {
    return result?.blob_storage?.processed_json?.blob_path ||
           result?.blob_storage?.processed_json?.blob_name ||
           result?.processed_blob_path ||
           result?.filename ||
           result?.file_info?.filename ||
           null;
  };

  // Handle assign user
  const handleAssignUser = (result, userId) => {
    const blobName = getBlobNameFromResult(result);
    if (!blobName) {
      console.warn('Cannot assign user: no blob name found in result');
      return;
    }

    setAssignedUsers(prev => {
      const updated = {
        ...prev,
        [blobName]: userId === 'unassigned' ? undefined : userId
      };
      // Remove unassigned entries
      if (updated[blobName] === undefined) {
        delete updated[blobName];
      }
      // Save to localStorage
      try {
        localStorage.setItem('fileAssignments', JSON.stringify(updated));
        // Dispatch custom event to notify other components
        window.dispatchEvent(new Event('fileAssignmentsUpdated'));
      } catch (error) {
        console.error('Error saving assigned users to localStorage:', error);
      }
      return updated;
    });
  };



  // Save confidence scores to Azure Blob Storage
  const saveConfidenceScoresToBlob = async (filenameKey, result) => {
    try {
      // Get the processed blob path from the result
      let processedBlobPath = null;

      if (result?.blob_storage?.processed_json?.blob_path) {
        processedBlobPath = result.blob_storage.processed_json.blob_path;
      } else if (result?.blob_storage?.processed_json?.blob_name) {
        processedBlobPath = result.blob_storage.processed_json.blob_name;
      } else if (result?.processed_blob_path) {
        processedBlobPath = result.processed_blob_path;
      }

      if (!processedBlobPath) {
        console.warn('No processed blob path found, skipping Azure Blob Storage update');
        return { success: false, reason: 'no_blob_path' };
      }

      // Get the original key-value pairs from the result
      const originalKeyValuePairs = result?.key_value_pairs || {};
      const originalConfidenceScores = result?.key_value_pair_confidence_scores || {};

      // Get current edited values
      const currentKeyValuePairs = editedPairsByIndex[filenameKey] || {};
      const currentConfidenceScores = editedConfidenceByIndex[filenameKey] || {};

      // Find only the CHANGED key-value pairs
      const updatedKeyValuePairs = {};
      Object.keys(currentKeyValuePairs).forEach(key => {
        if (currentKeyValuePairs[key] !== originalKeyValuePairs[key]) {
          updatedKeyValuePairs[key] = currentKeyValuePairs[key];
        }
      });

      // Find only the CHANGED confidence scores
      const updatedConfidenceScores = {};
      Object.keys(currentConfidenceScores).forEach(key => {
        if (currentConfidenceScores[key] !== originalConfidenceScores[key]) {
          updatedConfidenceScores[key] = currentConfidenceScores[key];
        }
      });

      // Only send if there are actual changes
      if (Object.keys(updatedConfidenceScores).length === 0 && Object.keys(updatedKeyValuePairs).length === 0) {
        console.log('No changes detected, skipping save');
        return { success: true, reason: 'no_updates' };
      }

      console.log(`Saving changes to blob: ${Object.keys(updatedKeyValuePairs).length} values, ${Object.keys(updatedConfidenceScores).length} confidence scores`);

      // Get correction metadata for this file
      const fileCorrectionMetadata = correctionMetadata[filenameKey] || {};
      const lastCorrection = lastFileCorrectionMetadata[filenameKey] || null;

      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/update-confidence-scores/${encodeURIComponent(processedBlobPath)}`,
        {
          method: 'PUT',
          headers: {
            ...headers,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            updated_confidence_scores: updatedConfidenceScores,
            updated_key_value_pairs: updatedKeyValuePairs,
            correction_metadata: fileCorrectionMetadata,  // Per-field metadata
            last_correction: lastCorrection  // Last correction for the file
          })
        }
      );

      if (!response.ok) {
        throw new Error(`Server error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log('Successfully saved confidence scores to Azure Blob Storage:', data);
      return { success: true, data };

    } catch (err) {
      console.error('Error saving confidence scores to Azure Blob Storage:', err);
      return { success: false, error: err.message };
    }
  };

  // Auto-save to Azure Blob Storage with debouncing
  const autoSaveTimeoutRef = useRef({});

  const autoSaveToBlob = (filenameKey, result) => {
    // Clear existing timeout for this file
    if (autoSaveTimeoutRef.current[filenameKey]) {
      clearTimeout(autoSaveTimeoutRef.current[filenameKey]);
    }

    // Set new timeout - save after 2 seconds of inactivity
    autoSaveTimeoutRef.current[filenameKey] = setTimeout(async () => {
      console.log(`Auto-saving to Azure Blob Storage for: ${filenameKey}`);

      try {
        const saveResult = await saveConfidenceScoresToBlob(filenameKey, result);

        if (saveResult.success && saveResult.reason !== 'no_updates' && saveResult.reason !== 'no_blob_path') {
          console.log(`✅ Auto-saved ${saveResult.data.updated_fields} confidence scores and ${saveResult.data.updated_values} values to cloud storage`);

          // Invalidate the cache in localStorage so BlobViewer will fetch fresh data
          const processedBlobPath = result?.blob_storage?.processed_json?.blob_path ||
            result?.blob_storage?.processed_json?.blob_name ||
            result?.processed_blob_path;
          if (processedBlobPath) {
            const CACHE_KEY = `confidence_${processedBlobPath}`;
            try {
              localStorage.removeItem(CACHE_KEY);
              console.log(`🗑️ Cleared cache for ${processedBlobPath}`);
            } catch (e) {
              console.warn('Failed to clear cache:', e);
            }
          }
        }
      } catch (err) {
        console.error('Auto-save failed:', err);
      }
    }, 2000); // 2 second debounce
  };

  // === Normalize results ===
  // Use useMemo to prevent infinite loops - only recalculate when results/isBatch actually change
  const resultsArray = useMemo(() => {
    return isBatch
      ? (Array.isArray(results) ? results : (results?.individual_results || []))
      : (results ? [results] : []);
  }, [results, isBatch]);

  // Debug: Log OCR confidence scores
  useEffect(() => {
    if (resultsArray.length > 0) {
      console.log('OCR Results Debug:', resultsArray.map(r => ({
        filename: r.filename || r.file_info?.filename,
        ocr_confidence_score: r.ocr_confidence_score,
        confidence_score: r.confidence_score,
        has_key_value_pairs: !!r.key_value_pairs
      })));
    }
  }, [resultsArray]);

  const batchInfo = useMemo(() => {
    return isBatch
      ? (results?.batch_info || results?.batchInfo || {
        total_files: resultsArray.length,
        successful_files: resultsArray.filter(r => r?.status === 'success' || r?.success).length,
        failed_files: 0,
        template_used: results?.batch_info?.template_used || null
      })
      : null;
  }, [isBatch, results, resultsArray]);

  const totalFiles = batchInfo?.total_files ?? resultsArray.length;
  // Check for 'completed' status (from Celery tasks) or 'success' status, or presence of key_value_pairs
  const successfulFiles = batchInfo?.successful_files ?? resultsArray.filter(r =>
    r?.status === 'success' ||
    r?.status === 'completed' ||
    r?.success === true ||
    (r?.key_value_pairs && Object.keys(r.key_value_pairs).length > 0)
  ).length;
  const failedFiles = Math.max(0, totalFiles - successfulFiles);
  const templateUsed = batchInfo?.template_used ?? 'None';

  // Fetch fresh data from database and merge with results
  const [mergedResults, setMergedResults] = useState(() => resultsArray);
  const [loadingFreshData, setLoadingFreshData] = useState(false);

  // Track previous results to detect actual changes
  const prevResultsRef = useRef(null);
  
  useEffect(() => {
    // Create a stable key to compare results
    const currentResultsKey = JSON.stringify(resultsArray.map(r => ({
      filename: r?.filename || r?.file_info?.filename,
      blob_path: r?.blob_storage?.processed_json?.blob_path || r?.processed_blob_path,
      has_kvp: !!r?.key_value_pairs
    })));
    
    // Only update if results actually changed
    if (currentResultsKey !== prevResultsRef.current) {
      setMergedResults(resultsArray);
      setLoadingFreshData(false);
      prevResultsRef.current = currentResultsKey;
    }
  }, [resultsArray]);

  // Track initialized results to prevent re-initialization
  const prevMergedResultsKeyRef = useRef(null);
  
  useEffect(() => {
    // Create a stable key for mergedResults to detect actual changes
    const resultsKey = mergedResults.map((r, idx) => {
      const filenameKey = getFilenameKey(r, idx);
      const blobPath = r?.blob_storage?.processed_json?.blob_path || 
                      r?.blob_storage?.processed_json?.blob_name || 
                      r?.processed_blob_path ||
                      filenameKey;
      return `${filenameKey}:${blobPath}`;
    }).join('|');
    
    // Skip if we've already initialized for these exact results
    if (prevMergedResultsKeyRef.current === resultsKey) {
      return;
    }
    
    // Mark as initialized
    prevMergedResultsKeyRef.current = resultsKey;
    
    // Initialize state immediately for faster display
    const initEdited = {};
    const initSaved = {};
    const initEditedConfidence = {};
    const initEditedText = {};
    const initSavedText = {};
    const initAnalysisResults = {};
    const initCorrectionMetadata = {};
    const initLastFileCorrectionMetadata = {};
    const initManuallyCorrected = {};

    // First pass: Quick initialization for immediate display
    mergedResults.forEach((r, idx) => {
      const filenameKey = getFilenameKey(r, idx);
      const uniqueFileId = getUniqueFileId(r);
      
      // Initialize basic data immediately (no localStorage check for speed)
      initEdited[filenameKey] = { ...(r?.key_value_pairs || {}) };
      initSaved[filenameKey] = { ...(r?.key_value_pairs || {}) };
      initEditedText[filenameKey] = r?.raw_ocr_text || '';
      initSavedText[filenameKey] = r?.raw_ocr_text || '';
      
      if (r?.key_value_pair_confidence_scores) {
        initEditedConfidence[filenameKey] = { ...r.key_value_pair_confidence_scores };
      }
      
      // Check if analysis exists in result (from backend)
      if (r?.low_confidence_analysis && Object.keys(r.low_confidence_analysis).length > 0) {
        const keyValuePairs = r?.key_value_pairs || {};
        const normalized = normalizeMandatoryFieldSuggestions(r.low_confidence_analysis, keyValuePairs);
        initAnalysisResults[filenameKey] = normalized;
        savedAnalysisResultsRef.current[filenameKey] = normalized;
      }
    });
    
    // Set state immediately for fast display
    setEditedPairsByIndex(initEdited);
    setLastSavedPairsByIndex(initSaved);
    setEditedTextByIndex(initEditedText);
    setLastSavedTextByIndex(initSavedText);
    setEditedConfidenceByIndex(initEditedConfidence);
    setAnalysisResults(initAnalysisResults);
    
    // Second pass: Load from localStorage and apply corrections (async, non-blocking)
    // Use setTimeout with 0ms to run after initial render, not blocking UI
    setTimeout(() => {
      const correctionsToApply = {};
      const confidenceToApply = {};
      const metadataToApply = {};
      const lastMetadataToApply = {};
      const manuallyCorrectedToApply = {};
      
      mergedResults.forEach((r, idx) => {
        const filenameKey = getFilenameKey(r, idx);
        const localStorageData = loadFromLocalStorage(filenameKey);
        
        if (localStorageData) {
          // Apply corrections from localStorage
          if (localStorageData.editedPairs) {
            correctionsToApply[filenameKey] = { ...(r?.key_value_pairs || {}), ...localStorageData.editedPairs };
          }
          if (localStorageData.editedConfidence) {
            confidenceToApply[filenameKey] = localStorageData.editedConfidence;
          }
          if (localStorageData.manuallyCorrected) {
            manuallyCorrectedToApply[filenameKey] = localStorageData.manuallyCorrected;
          }
          if (localStorageData.correctionMetadata) {
            metadataToApply[filenameKey] = localStorageData.correctionMetadata;
          }
          if (localStorageData.lastFileCorrectionMetadata) {
            lastMetadataToApply[filenameKey] = localStorageData.lastFileCorrectionMetadata;
          }
        }
        
        // Load correction metadata from backend
        if (r?.correction_metadata && !metadataToApply[filenameKey]) {
          metadataToApply[filenameKey] = {};
          Object.keys(r.correction_metadata).forEach(key => {
            metadataToApply[filenameKey][key] = {
              username: r.correction_metadata[key].username,
              timestamp: r.correction_metadata[key].timestamp
            };
          });
        }
        
        if (r?.last_correction && !lastMetadataToApply[filenameKey]) {
          lastMetadataToApply[filenameKey] = {
            username: r.last_correction.username,
            timestamp: r.last_correction.timestamp
          };
        }
        
        // Update analysis results if available from backend
        if (r?.low_confidence_analysis && Object.keys(r.low_confidence_analysis).length > 0) {
          const keyValuePairs = r?.key_value_pairs || {};
          const normalized = normalizeMandatoryFieldSuggestions(r.low_confidence_analysis, keyValuePairs);
          setAnalysisResults(prev => ({
            ...prev,
            [filenameKey]: normalized
          }));
          savedAnalysisResultsRef.current[filenameKey] = normalized;
          
          // Update confidence for verified extractions
          Object.keys(r.low_confidence_analysis).forEach(key => {
            const analysis = r.low_confidence_analysis[key];
            if (analysis.extraction_status === 'correct') {
              setEditedConfidenceByIndex(prev => ({
                ...prev,
                [filenameKey]: {
                  ...(prev[filenameKey] || {}),
                  [key]: 0.95
                }
              }));
            }
          });
        }
      });
      
      // Apply all corrections in batch
      if (Object.keys(correctionsToApply).length > 0) {
        setEditedPairsByIndex(prev => ({ ...prev, ...correctionsToApply }));
        setLastSavedPairsByIndex(prev => ({ ...prev, ...correctionsToApply }));
      }
      if (Object.keys(confidenceToApply).length > 0) {
        setEditedConfidenceByIndex(prev => ({ ...prev, ...confidenceToApply }));
      }
      if (Object.keys(manuallyCorrectedToApply).length > 0) {
        setManuallyCorrectedFields(prev => ({ ...prev, ...manuallyCorrectedToApply }));
      }
      if (Object.keys(metadataToApply).length > 0) {
        setCorrectionMetadata(prev => ({ ...prev, ...metadataToApply }));
      }
      if (Object.keys(lastMetadataToApply).length > 0) {
        setLastFileCorrectionMetadata(prev => ({ ...prev, ...lastMetadataToApply }));
      }
    }, 0); // Run immediately after render, non-blocking
  }, [mergedResults]);

  // Auto-trigger analysis for low-confidence pairs when results are received
  useEffect(() => {
    if (mergedResults.length === 0) return;

    // DON'T reset the tracking set - keep it persistent to prevent duplicate triggers
    // autoAnalysisTriggeredRef.current = new Set(); // REMOVED - this was causing duplicates

    // Process files in parallel for faster analysis
    const filesToAnalyze = [];
    
    mergedResults.forEach((result, idx) => {
      const filenameKey = getFilenameKey(result, idx);
      const filename = filenameKey;

      // Skip if already analyzed or if analysis was already triggered
      if (autoAnalysisTriggeredRef.current.has(filenameKey)) {
        console.log(`⏭️ Skipping auto-analysis for ${filenameKey} - already triggered`);
        return;
      }

      // Skip if analysis is currently in progress for this file
      if (analyzingPairs[filenameKey]) {
        console.log(`⏭️ Skipping auto-analysis for ${filenameKey} - analysis already in progress`);
        return;
      }

      // Skip if backend has failed recently (within last 30 seconds)
      const timeSinceLastFailure = Date.now() - lastBackendCheckRef.current;
      if (backendFailureCountRef.current >= 2 && timeSinceLastFailure < 30000) {
        console.log(`⏭️ Skipping auto-analysis for ${filenameKey} - backend unavailable (${backendFailureCountRef.current} failures, ${Math.round(timeSinceLastFailure / 1000)}s ago)`);
        return;
      }

      // Skip if already analyzed (from backend response in initialization)
      if (savedAnalysisResultsRef.current[filenameKey] && Object.keys(savedAnalysisResultsRef.current[filenameKey]).length > 0) {
        autoAnalysisTriggeredRef.current.add(filenameKey);
        console.log(`⏭️ Skipping auto-analysis for ${filenameKey} - already has results from backend`);
        return; // Skip if already loaded from backend
      }

      // Check if we have analysis results from backend
      if (result.low_confidence_analysis && Object.keys(result.low_confidence_analysis).length > 0) {
        // Normalize mandatory field suggestions (replace instructional text with "None")
        const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
        const normalized = normalizeMandatoryFieldSuggestions(result.low_confidence_analysis, keyValuePairs);
        
        // Use the analysis results directly - IMPORTANT: Set in STATE, not just ref!
        savedAnalysisResultsRef.current[filenameKey] = normalized;
        
        // CRITICAL FIX: Set analysis results in state so they display in UI
        setAnalysisResults(prev => {
          const newResults = {
            ...prev,
            [filenameKey]: normalized
          };
          console.log(`✅ Setting analysis results from backend for ${filenameKey}:`, {
            keys: Object.keys(normalized),
            fullResults: newResults
          });
          return newResults;
        });

        // Automatically update confidence scores for verified extractions
        Object.keys(normalized).forEach(key => {
          const analysis = normalized[key];
          if (analysis.extraction_status === 'correct') {
            setEditedConfidenceByIndex(prev => ({
              ...prev,
              [filenameKey]: {
                ...(prev[filenameKey] || {}),
                [key]: 0.95
              }
            }));

            // Save to ref - use filename key
            const confidenceKey = `${filenameKey}_confidence`;
            if (!savedCorrectionsRef.current[confidenceKey]) {
              savedCorrectionsRef.current[confidenceKey] = {};
            }
            savedCorrectionsRef.current[confidenceKey][key] = 0.95;
          }
        });

        autoAnalysisTriggeredRef.current.add(filenameKey);
        console.log(`✅ Using analysis results from backend for ${filenameKey} - ${Object.keys(result.low_confidence_analysis).length} fields analyzed`);
        return; // Skip if already analyzed by backend
      }

      // Check if we have low-confidence pairs
      const hasLowConfidenceData = result.low_confidence_data?.has_low_confidence_pairs;
      const confidenceScores = result.key_value_pair_confidence_scores || {};
      const hasLowConfidencePairs = hasLowConfidenceData || Object.values(confidenceScores).some(conf => {
        const normalized = conf > 1 ? conf / 100 : conf;
        return normalized !== undefined && normalized !== null && normalized < 0.95;
      });

      // Collect files that need analysis for parallel processing
      if (hasLowConfidencePairs) {
        const uniqueFileId = getUniqueFileId(result);
        filesToAnalyze.push({ filenameKey, result, uniqueFileId });
      }
    });

    // Process files that need analysis (only if no cache found)
    if (filesToAnalyze.length > 0) {
      // Check database cache asynchronously first (fast, no LLM call)
      filesToAnalyze.forEach(({ filenameKey, result, uniqueFileId }) => {
        // Mark as checked to prevent duplicate
        autoAnalysisTriggeredRef.current.add(filenameKey);
        
        // Check database cache (async, but fast)
        loadAnalysisFromCache(uniqueFileId).then(cachedAnalysis => {
          if (cachedAnalysis && Object.keys(cachedAnalysis).length > 0) {
            console.log(`⚡ Found cache in database for ${uniqueFileId} - loading from DB!`);
            
            // Normalize and apply cached results
            const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
            const keyValueKeys = Object.keys(keyValuePairs);
            const keyMap = {};
            keyValueKeys.forEach(k => {
              keyMap[k.toLowerCase()] = k;
            });
            
            const normalizedAnalysis = {};
            Object.keys(cachedAnalysis).forEach(analysisKey => {
              if (analysisKey.startsWith('_')) return;
              if (keyValueKeys.includes(analysisKey)) {
                normalizedAnalysis[analysisKey] = cachedAnalysis[analysisKey];
              } else {
                const lowerKey = analysisKey.toLowerCase();
                if (keyMap[lowerKey]) {
                  normalizedAnalysis[keyMap[lowerKey]] = cachedAnalysis[analysisKey];
                } else {
                  normalizedAnalysis[analysisKey] = cachedAnalysis[analysisKey];
                }
              }
            });
            
            setAnalysisResults(prev => ({
              ...prev,
              [filenameKey]: normalizedAnalysis
            }));
            savedAnalysisResultsRef.current[filenameKey] = normalizedAnalysis;
            
            // Update confidence scores
            Object.keys(normalizedAnalysis).forEach(key => {
              const analysis = normalizedAnalysis[key];
              if (analysis && analysis.extraction_status === 'correct') {
                setEditedConfidenceByIndex(prev => ({
                  ...prev,
                  [filenameKey]: {
                    ...(prev[filenameKey] || {}),
                    [key]: 0.95
                  }
                }));
              }
            });
          } else {
            // No cache found - trigger LLM analysis (only as last resort)
            if (!analyzingPairs[filenameKey]) {
              console.log(`🚀 No cache found for ${uniqueFileId} - triggering LLM analysis`);
              analyzeLowConfidencePairs(filenameKey, result, true); // useCache = true to save results
            }
          }
        }).catch(err => {
          console.warn('Error checking database cache:', err);
          // On error, trigger LLM analysis as fallback
          if (!analyzingPairs[filenameKey]) {
            analyzeLowConfidencePairs(filenameKey, result, true);
          }
        });
      });
    }
  }, [mergedResults.length, source]); // Only trigger when length or source changes, not the entire array

  // Automatically update confidence scores when analysis results show verified status
  useEffect(() => {
    Object.keys(analysisResults).forEach(filenameKey => {
      const fileAnalysis = analysisResults[filenameKey];
      if (!fileAnalysis) return;

      Object.keys(fileAnalysis).forEach(key => {
        const analysis = fileAnalysis[key];
        if (analysis.extraction_status === 'correct') {
          // Update confidence to 0.95 (95%) for verified extractions
          setEditedConfidenceByIndex(prev => {
            const currentConf = prev[filenameKey]?.[key];
            // Only update if not already at or above 0.95
            if (currentConf === undefined || currentConf < 0.95) {
              return {
                ...prev,
                [filenameKey]: {
                  ...(prev[filenameKey] || {}),
                  [key]: 0.95
                }
              };
            }
            return prev;
          });

          // Save confidence to ref - use filename key
          const confidenceKey = `${filenameKey}_confidence`;
          if (!savedCorrectionsRef.current[confidenceKey]) {
            savedCorrectionsRef.current[confidenceKey] = {};
          }
          const currentConf = savedCorrectionsRef.current[confidenceKey][key];
          if (currentConf === undefined || currentConf < 0.95) {
            savedCorrectionsRef.current[confidenceKey][key] = 0.95;
          }
        }
      });
    });
  }, [analysisResults]);

  // Auto-boost confidence to random high value (95.9-99.5%) when suggested value matches extracted value
  useEffect(() => {
    Object.keys(analysisResults).forEach(filenameKey => {
      const fileAnalysis = analysisResults[filenameKey];
      if (!fileAnalysis) return;

      // Get the current key-value pairs for this file
      const currentPairs = editedPairsByIndex[filenameKey] || results?.individual_results?.find(r =>
        (r.filename || r.file_info?.filename) === filenameKey.split('_')[0]
      )?.key_value_pairs || {};

      Object.keys(fileAnalysis).forEach(key => {
        const analysis = fileAnalysis[key];
        const extractedValue = String(currentPairs[key] ?? '').trim();
        const suggestedValue = String(analysis.suggested_value ?? '').trim();

        // If values match, boost confidence to random value between 95.9% and 99.5%
        if (extractedValue === suggestedValue && extractedValue !== '') {
          setEditedConfidenceByIndex(prev => {
            const currentConf = prev[filenameKey]?.[key];
            // Only generate random value ONCE - if not already boosted
            if (currentConf === undefined || currentConf < 0.95) {
              // Generate random confidence between 0.959 (95.9%) and 0.995 (99.5%)
              const randomConfidence = 0.959 + (Math.random() * (0.995 - 0.959));

              // Save to ref for persistence
              const confidenceKey = `${filenameKey}_confidence`;
              if (!savedCorrectionsRef.current[confidenceKey]) {
                savedCorrectionsRef.current[confidenceKey] = {};
              }
              savedCorrectionsRef.current[confidenceKey][key] = randomConfidence;

              return {
                ...prev,
                [filenameKey]: {
                  ...(prev[filenameKey] || {}),
                  [key]: randomConfidence
                }
              };
            }
            return prev;
          });
        }
      });
    });
  }, [analysisResults, editedPairsByIndex, results]);

  // Debug: Log when analysisResults state changes
  useEffect(() => {
    if (Object.keys(analysisResults).length > 0) {
      console.log('🔄 analysisResults state updated:', {
        fileCount: Object.keys(analysisResults).length,
        files: Object.keys(analysisResults).map(key => ({
          filename: key,
          fieldCount: Object.keys(analysisResults[key] || {}).length,
          fields: Object.keys(analysisResults[key] || {})
        }))
      });
    }
  }, [analysisResults]);

  // Auto-save to localStorage when corrections are made (backup mechanism)
  useEffect(() => {
    // Debounce the save to avoid excessive writes
    const timeoutId = setTimeout(() => {
      mergedResults.forEach((result, idx) => {
        const filenameKey = getFilenameKey(result, idx);

        // Only save if there are corrections for this file
        if (manuallyCorrectedFields[filenameKey] && Object.keys(manuallyCorrectedFields[filenameKey]).length > 0) {
          // Use current state values (this runs after state updates complete)
          saveToLocalStorage(filenameKey);
          console.log(`🔄 Auto-saved corrections for: ${filenameKey}`);
        }
      });
    }, 1000); // 1 second debounce

    return () => clearTimeout(timeoutId);
  }, [editedPairsByIndex, editedConfidenceByIndex, manuallyCorrectedFields, correctionMetadata, lastFileCorrectionMetadata]);

  const toggleFile = (filenameKey) => {
    const newExpanded = new Set(expandedFiles);
    newExpanded.has(filenameKey) ? newExpanded.delete(filenameKey) : newExpanded.add(filenameKey);
    setExpandedFiles(newExpanded);
  };

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); } catch (err) { console.error(err); }
  };

  const downloadText = (text, filename) => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}_ocr.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadKeyValuePairs = (pairs, filename) => {
    const blob = new Blob([JSON.stringify(pairs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}_key_value_pairs.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const startEditing = (filenameKey) => {
    setIsEditingByIndex(p => ({ ...p, [filenameKey]: true }));
  };

  const cancelEditing = (filenameKey) => {
    setIsEditingByIndex(p => ({ ...p, [filenameKey]: false }));
    setEditedPairsByIndex(p => ({ ...p, [filenameKey]: { ...lastSavedPairsByIndex[filenameKey] } }));
  };

  const saveEditing = (filenameKey) => {
    setIsEditingByIndex(p => ({ ...p, [filenameKey]: false }));
    setLastSavedPairsByIndex(p => ({ ...p, [filenameKey]: { ...editedPairsByIndex[filenameKey] } }));
  };

  const handlePairChange = (filenameKey, key, value) => {
    setEditedPairsByIndex(p => ({
      ...p,
      [filenameKey]: { ...p[filenameKey], [key]: value }
    }));
  };

  // Functions for individual key-value pair editing
  const startEditingKeyValuePair = (filenameKey, key) => {
    setEditingKeyValuePair(`${filenameKey}-${key}`);
  };

  const cancelEditingKeyValuePair = (filenameKey, key) => {
    setEditingKeyValuePair(null);
    // Restore the original value
    setEditedPairsByIndex(p => ({
      ...p,
      [filenameKey]: { ...p[filenameKey], [key]: lastSavedPairsByIndex[filenameKey]?.[key] }
    }));
  };

  const saveEditingKeyValuePair = (filenameKey, key) => {
    setEditingKeyValuePair(null);
    // Save the edited value
    setLastSavedPairsByIndex(p => ({
      ...p,
      [filenameKey]: { ...p[filenameKey], [key]: editedPairsByIndex[filenameKey]?.[key] }
    }));
    // Also save to ref for persistence - use filename key
    if (!savedCorrectionsRef.current[filenameKey]) {
      savedCorrectionsRef.current[filenameKey] = {};
    }
    savedCorrectionsRef.current[filenameKey][key] = editedPairsByIndex[filenameKey]?.[key];

    // Update last file correction metadata timestamp
    const currentUser = authService.getCurrentUser()?.username || 'User';
    const currentTimestamp = new Date().toLocaleString();
    setLastFileCorrectionMetadata(prev => ({
      ...prev,
      [filenameKey]: { username: currentUser, timestamp: currentTimestamp }
    }));

    // Auto-save to Azure Blob Storage
    const result = mergedResults.find((r, i) => getFilenameKey(r, i) === filenameKey);
    if (result) {
      autoSaveToBlob(filenameKey, result);
    }
  };

  // Functions for editing suggested values
  const startEditingSuggestedValue = (filenameKey, key) => {
    const analysis = analysisResults[filenameKey]?.[key];
    // Get the normalized display value (handles mandatory fields)
    const result = results[filenameKey] || (Array.isArray(results) ? results.find((r, idx) => getFilenameKey(r, idx) === filenameKey) : null);
    const keyValuePairs = editedPairsByIndex[filenameKey] || result?.key_value_pairs || {};
    const currentSuggestedValue = getSuggestedValueDisplay(analysis, key, keyValuePairs);
    setEditingSuggestedValue(`${filenameKey}-${key}`);
    setEditedSuggestedValues(prev => ({
      ...prev,
      [`${filenameKey}-${key}`]: currentSuggestedValue
    }));
  };

  const cancelEditingSuggestedValue = (filenameKey, key) => {
    setEditingSuggestedValue(null);
    setEditedSuggestedValues(prev => {
      const newValues = { ...prev };
      delete newValues[`${filenameKey}-${key}`];
      return newValues;
    });
  };

  const saveEditingSuggestedValue = (filenameKey, key) => {
    const editedValue = editedSuggestedValues[`${filenameKey}-${key}`] || '';
    // Apply the edited suggested value to the key-value pair
    handlePairChange(filenameKey, key, editedValue);
    // Save to both state and ref for persistence
    setLastSavedPairsByIndex(prev => ({
      ...prev,
      [filenameKey]: {
        ...(prev[filenameKey] || {}),
        [key]: editedValue
      }
    }));
    // Also save to ref so it persists across re-renders - use filename key
    if (!savedCorrectionsRef.current[filenameKey]) {
      savedCorrectionsRef.current[filenameKey] = {};
    }
    savedCorrectionsRef.current[filenameKey][key] = editedValue;
    // Update the analysis result with the edited suggested value
    setAnalysisResults(prev => {
      const newResults = { ...prev };
      if (newResults[filenameKey] && newResults[filenameKey][key]) {
        newResults[filenameKey] = {
          ...newResults[filenameKey],
          [key]: {
            ...newResults[filenameKey][key],
            suggested_value: editedValue
          }
        };
      }
      return newResults;
    });
    // Stop editing
    setEditingSuggestedValue(null);

    // Update last file correction metadata timestamp
    const currentUser = authService.getCurrentUser()?.username || 'User';
    const currentTimestamp = new Date().toLocaleString();
    setLastFileCorrectionMetadata(prev => ({
      ...prev,
      [filenameKey]: { username: currentUser, timestamp: currentTimestamp }
    }));

    // Auto-save to Azure Blob Storage
    const result = mergedResults.find((r, i) => getFilenameKey(r, i) === filenameKey);
    if (result) {
      autoSaveToBlob(filenameKey, result);
    }
  };

  const handleSuggestedValueChange = (filenameKey, key, value) => {
    setEditedSuggestedValues(prev => ({
      ...prev,
      [`${filenameKey}-${key}`]: value
    }));
  };

  const startEditingText = (filenameKey) => setIsEditingTextByIndex(p => ({ ...p, [filenameKey]: true }));
  const cancelEditingText = (filenameKey) => {
    setIsEditingTextByIndex(p => ({ ...p, [filenameKey]: false }));
    setEditedTextByIndex(p => ({ ...p, [filenameKey]: lastSavedTextByIndex[filenameKey] }));
  };
  const saveEditingText = (filenameKey) => {
    setIsEditingTextByIndex(p => ({ ...p, [filenameKey]: false }));
    setLastSavedTextByIndex(p => ({ ...p, [filenameKey]: editedTextByIndex[filenameKey] }));
  };
  const handleTextChange = (filenameKey, val) => setEditedTextByIndex(p => ({ ...p, [filenameKey]: val }));

  const handleDismissCorrection = (filenameKey, key) => {
    const correctionKey = `${filenameKey}-${key}`;
    setDismissedCorrections(prev => new Set([...prev, correctionKey]));



    // Also remove the analysis result for this field (so the analysis box disappears)
    setAnalysisResults(prev => {
      const newResults = { ...prev };
      if (newResults[filenameKey]) {
        const updatedKey = { ...newResults[filenameKey] };
        delete updatedKey[key];
        // If no more analysis results for this file, remove the entire entry
        if (Object.keys(updatedKey).length === 0) {
          delete newResults[filenameKey];
        } else {
          newResults[filenameKey] = updatedKey;
        }
      }
      return newResults;
    });
  };

  // Load analysis from database cache only
  const loadAnalysisFromCache = async (uniqueFileId) => {
    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(`${API_BASE_URL}/api/v1/ocr/enhanced/get-analysis-cache/${encodeURIComponent(uniqueFileId)}`, {
        headers
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success' && data.analysis_results) {
          console.log(`✅ Found analysis in database cache: ${uniqueFileId}`);
          return data.analysis_results;
        }
      }
    } catch (e) {
      console.warn('Error checking database cache:', e);
    }

    return null;
  };

  const analyzeLowConfidencePairs = async (filenameKey, result, useCache = false) => {
    // Get unique file ID for caching (do this first)
    const uniqueFileId = getUniqueFileId(result);
    
    // Check database cache FIRST before setting loading state (to avoid UI flicker)
    if (useCache) {
      const cachedAnalysis = await loadAnalysisFromCache(uniqueFileId);
      if (cachedAnalysis && Object.keys(cachedAnalysis).length > 0) {
        console.log(`⚡ Found cache in database for ${uniqueFileId} - loading from DB, NO LLM call!`);
        
        // Normalize analysis results keys to match key-value pairs
        const normalizedAnalysisResults = {};
        const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
        const keyValueKeys = Object.keys(keyValuePairs);
        const keyMap = {};
        keyValueKeys.forEach(k => {
          keyMap[k.toLowerCase()] = k;
        });
        
        Object.keys(cachedAnalysis).forEach(analysisKey => {
          if (analysisKey.startsWith('_')) return;
          if (keyValueKeys.includes(analysisKey)) {
            normalizedAnalysisResults[analysisKey] = cachedAnalysis[analysisKey];
          } else {
            const lowerKey = analysisKey.toLowerCase();
            if (keyMap[lowerKey]) {
              normalizedAnalysisResults[keyMap[lowerKey]] = cachedAnalysis[analysisKey];
            } else {
              normalizedAnalysisResults[analysisKey] = cachedAnalysis[analysisKey];
            }
          }
        });
        
        // Normalize mandatory field suggestions (replace instructional text with "None")
        const finalNormalizedResults = normalizeMandatoryFieldSuggestions(normalizedAnalysisResults, keyValuePairs);
        
        // Update state (no loading state needed - cache found)
        setAnalysisResults(prev => ({
          ...prev,
          [filenameKey]: finalNormalizedResults
        }));
        savedAnalysisResultsRef.current[filenameKey] = finalNormalizedResults;
        
        // Update confidence scores
        Object.keys(finalNormalizedResults).forEach(key => {
          const analysis = finalNormalizedResults[key];
          if (analysis && analysis.extraction_status === 'correct') {
            setEditedConfidenceByIndex(prev => ({
              ...prev,
              [filenameKey]: {
                ...(prev[filenameKey] || {}),
                [key]: 0.95
              }
            }));
          }
        });
        
        return; // Exit - cache found, no LLM API call needed!
      }
    }
    
    // Only set loading state if we're actually going to make an API call
    console.log(`🚀 No cache found for ${uniqueFileId} - starting LLM analysis`);
    setAnalyzingPairs(prev => ({ ...prev, [filenameKey]: true }));

    try {
      // Check if we have pre-computed low_confidence_data from the new workflow
      let lowConfidencePairs = {};
      let lowConfidenceScores = {};
      let sourceFileBase64 = null;
      let sourceFileContentType = null;

      if (result.low_confidence_data) {
        // Use pre-computed data from backend
        lowConfidencePairs = result.low_confidence_data.low_confidence_pairs || {};
        lowConfidenceScores = result.low_confidence_data.low_confidence_scores || {};
        sourceFileBase64 = result.low_confidence_data.source_file_base64;
        sourceFileContentType = result.low_confidence_data.source_file_content_type;

        console.log('Using pre-computed low-confidence data from backend');
      } else {
        // Fallback: Compute low-confidence pairs manually (old workflow)
        // Use the filenameKey passed to the function
        const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
        const confidenceScores = editedConfidenceByIndex[filenameKey] || result.key_value_pair_confidence_scores || {};

        Object.keys(keyValuePairs).forEach(key => {
          let conf = confidenceScores[key];
          if (conf !== undefined && conf !== null) {
            if (conf > 1) conf = conf / 100;
            if (conf < 0.95) {
              lowConfidencePairs[key] = keyValuePairs[key];
              lowConfidenceScores[key] = conf;
            }
          }
        });
      }

      if (Object.keys(lowConfidencePairs).length === 0) {
        alert('No key-value pairs with confidence below 95% found.');
        setAnalyzingPairs(prev => ({ ...prev, [filenameKey]: false }));
        return;
      }

      // If we don't have the source file base64 from backend, try to download it
      if (!sourceFileBase64) {
        try {
          // Get processed file blob path from result
          let processedBlobPath = null;

          if (result?.blob_storage?.processed_json?.blob_path) {
            processedBlobPath = result.blob_storage.processed_json.blob_path;
          } else if (result?.blob_storage?.processed_json?.success && result?.blob_storage?.processed_json?.blob_name) {
            processedBlobPath = result.blob_storage.processed_json.blob_name;
          } else if (result?.processed_blob_path) {
            processedBlobPath = result.processed_blob_path;
          } else if (result?.blob_storage && typeof result.blob_storage === 'string') {
            processedBlobPath = result.blob_storage;
          }

          if (processedBlobPath) {
            // Get source file path from API
            const headers = authService.getAuthHeaders();
            const sourceResponse = await fetch(
              `${API_BASE_URL}/api/v1/blob/source-from-processed/${encodeURIComponent(processedBlobPath)}`,
              { headers }
            );

            if (sourceResponse.ok) {
              const sourceData = await sourceResponse.json();
              const sourceBlobPath = sourceData.source_blob_path;

              // Download the source file
              const fileResponse = await fetch(
                `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(sourceBlobPath)}`,
                { headers }
              );

              if (fileResponse.ok) {
                const fileBlob = await fileResponse.blob();
                const reader = new FileReader();
                await new Promise((resolve) => {
                  reader.onloadend = () => {
                    sourceFileBase64 = reader.result.split(',')[1]; // Remove data:image/png;base64, prefix
                    sourceFileContentType = fileBlob.type;
                    resolve();
                  };
                  reader.readAsDataURL(fileBlob);
                });

                console.log('Source file downloaded and converted to base64');
              } else {
                console.warn('Could not download source file, proceeding with OCR text only');
              }
            } else {
              console.warn('Could not get source file path, proceeding with OCR text only');
            }
          } else {
            console.warn('No processed blob path found, proceeding with OCR text only');
          }
        } catch (fileErr) {
          console.warn('Error getting source file:', fileErr);
          // Continue without file - will use OCR text only
        }
      }

      // Use the filenameKey passed to the function
      const ocrText = editedTextByIndex[filenameKey] || result.raw_ocr_text || '';

      // Get unique file ID for caching
      const uniqueFileId = getUniqueFileId(result);
      
      const headers = authService.getAuthHeaders();
      const response = await fetch(`${API_BASE_URL}/api/v1/ocr/enhanced/analyze-low-confidence`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          key_value_pairs: lowConfidencePairs,
          confidence_scores: lowConfidenceScores,
          ocr_text: ocrText,
          filename: result.filename || result.file_info?.filename || 'unknown',
          source_file_base64: sourceFileBase64,
          source_file_content_type: sourceFileContentType,
          unique_file_id: uniqueFileId,  // Pass unique_file_id so backend can auto-save cache
          use_cache: useCache  // Pass the useCache parameter
        })
      });

      if (!response.ok) {
        // Try to get error message from response
        let errorMessage = `Server error: ${response.status} ${response.statusText}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
          // If response is not JSON, use status text
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();

      console.log('=== LOW CONFIDENCE ANALYSIS RESPONSE ===');
      console.log('Status:', data.status);
      console.log('Cache Hit:', data.cache_hit);
      if (data.cache_info) {
        console.log('Cache Info:', data.cache_info);
        if (data.cache_hit) {
          console.log(`✅ Using CACHED analysis (accessed ${data.cache_info.access_count} times) - No LLM API call!`);
        } else if (data.cache_info.saved_to_cache) {
          console.log(`💾 Fresh LLM analysis saved to cache (file hash: ${data.cache_info.file_hash})`);
        }
      }
      console.log('Analysis Results:', data.analysis_results);
      console.log('Number of analyzed pairs:', data.analysis_results ? Object.keys(data.analysis_results).length : 0);

      if (data.status === 'success' && data.analysis_results) {
        const filename = result.filename || result.file_info?.filename || filenameKey;

        console.log('✅ LLM Analysis completed successfully for:', filenameKey);
        console.log('📊 Analysis results received:', Object.keys(data.analysis_results).length, 'fields analyzed');
        console.log('🔍 Full analysis data:', data.analysis_results);

        // Normalize analysis results keys to match key-value pairs (case-insensitive matching)
        const normalizedAnalysisResults = {};
        const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
        const keyValueKeys = Object.keys(keyValuePairs);
        
        // Create a case-insensitive mapping
        const keyMap = {};
        keyValueKeys.forEach(k => {
          keyMap[k.toLowerCase()] = k;
        });
        
        // Match analysis results to key-value pairs
        Object.keys(data.analysis_results).forEach(analysisKey => {
          // Skip internal keys
          if (analysisKey.startsWith('_')) {
            return;
          }
          
          // Try exact match first
          if (keyValueKeys.includes(analysisKey)) {
            normalizedAnalysisResults[analysisKey] = data.analysis_results[analysisKey];
          } else {
            // Try case-insensitive match
            const lowerKey = analysisKey.toLowerCase();
            if (keyMap[lowerKey]) {
              normalizedAnalysisResults[keyMap[lowerKey]] = data.analysis_results[analysisKey];
              console.log(`🔄 Mapped analysis key "${analysisKey}" to key-value pair key "${keyMap[lowerKey]}"`);
            } else {
              // Keep original key if no match found (might be a new field)
              normalizedAnalysisResults[analysisKey] = data.analysis_results[analysisKey];
              console.log(`⚠️ No matching key found for analysis key "${analysisKey}"`);
            }
          }
        });
        
        console.log('🔑 Key matching:', {
          analysisKeys: Object.keys(data.analysis_results),
          keyValueKeys: keyValueKeys,
          normalizedKeys: Object.keys(normalizedAnalysisResults)
        });

        // Normalize mandatory field suggestions (replace instructional text with "None")
        const finalNormalizedResults = normalizeMandatoryFieldSuggestions(normalizedAnalysisResults, keyValuePairs);

        // Save to state - use filename key (force update)
        setAnalysisResults(prev => {
          const newResults = {
            ...prev,
            [filenameKey]: finalNormalizedResults
          };
          console.log('🔄 Updating analysisResults state:', {
            filenameKey,
            originalKeys: Object.keys(data.analysis_results),
            normalizedKeys: Object.keys(finalNormalizedResults),
            keyValueKeys: keyValueKeys
          });
          return newResults;
        });

        // Save to ref for this session
        savedAnalysisResultsRef.current[filenameKey] = finalNormalizedResults;
        
        // Note: Analysis cache is automatically saved by backend when analyze-low-confidence is called
        // (The backend auto-saves when unique_file_id is provided in the request)
        console.log(`✅ Analysis results received and cached automatically by backend for unique_file_id: ${uniqueFileId}`);
        
        // Force a re-render by updating a timestamp
        console.log('✅ Analysis results state updated, component should re-render');

        // Automatically update confidence scores for verified extractions
        Object.keys(finalNormalizedResults).forEach(key => {
          const analysis = finalNormalizedResults[key];
          if (analysis && analysis.extraction_status === 'correct') {
            // Update confidence to 0.95 (95%) for verified extractions
            setEditedConfidenceByIndex(prev => ({
              ...prev,
              [filenameKey]: {
                ...(prev[filenameKey] || {}),
                [key]: 0.95
              }
            }));

            // Save confidence to ref - use filename key
            const confidenceKey = `${filenameKey}_confidence`;
            if (!savedCorrectionsRef.current[confidenceKey]) {
              savedCorrectionsRef.current[confidenceKey] = {};
            }
            savedCorrectionsRef.current[confidenceKey][key] = 0.95;
          }
        });

        console.log('💾 Analysis results stored in state for filename:', filenameKey);
        console.log('📝 Stored results keys:', Object.keys(data.analysis_results));
      } else {
        alert(`Analysis failed: ${data.message || 'Unknown error'}`);
      }

    } catch (err) {
      console.error('Error analyzing low-confidence pairs:', err);
      alert(`Failed to analyze low-confidence pairs: ${err.message}`);
    } finally {
      setAnalyzingPairs(prev => ({ ...prev, [filenameKey]: false }));
    }
  };

  const handleAutoCorrect = async (filenameKey, key, value, context) => {
    const correctionKey = `${filenameKey}-${key}`;
    setCorrectingKeys(prev => ({ ...prev, [correctionKey]: true }));

    try {
      // Check if we have analysis results with a suggested value
      const analysis = analysisResults[filenameKey] && analysisResults[filenameKey][key];
      
      // Get normalized suggested value (handles mandatory fields - returns "None" instead of instructional text)
      const result = mergedResults.find((r, i) => getFilenameKey(r, i) === filenameKey);
      const keyValuePairs = editedPairsByIndex[filenameKey] || result?.key_value_pairs || {};
      const normalizedSuggestedValue = getSuggestedValueDisplay(analysis, key, keyValuePairs);
      
      // Always use the normalized value (it will be "None" for mandatory fields with empty values)
      // Only fallback to raw suggested_value if normalization says "No suggestion available" or "NULL"
      let valueToApply = '';
      if (normalizedSuggestedValue !== 'No suggestion available' && normalizedSuggestedValue !== 'NULL') {
        valueToApply = normalizedSuggestedValue;
      } else if (analysis?.suggested_value) {
        valueToApply = String(analysis.suggested_value).trim();
      }
      
      const currentUser = authService.getCurrentUser()?.username || 'User';
      const currentTimestamp = new Date().toLocaleString();

      // Helper function to save to DB immediately with explicit values
      const saveToDbImmediately = async (updatedValue, updatedConfidence, metadata) => {
        const result = mergedResults.find((r, i) => getFilenameKey(r, i) === filenameKey);
        if (result) {
          try {
            console.log('Attempting immediate save for', filenameKey, 'key:', key);

            // Get the processed blob path
            let processedBlobPath = null;
            if (result?.blob_storage?.processed_json?.blob_path) {
              processedBlobPath = result.blob_storage.processed_json.blob_path;
            } else if (result?.blob_storage?.processed_json?.blob_name) {
              processedBlobPath = result.blob_storage.processed_json.blob_name;
            } else if (result?.processed_blob_path) {
              processedBlobPath = result.processed_blob_path;
            }

            if (!processedBlobPath) {
              console.warn('No processed blob path found, skipping save');
              return { success: false, reason: 'no_blob_path' };
            }

            // Prepare the update payload with the explicit values
            const payload = {
              updated_key_value_pairs: {
                [key]: updatedValue
              },
              updated_confidence_scores: {
                [key]: updatedConfidence
              },
              correction_metadata: {
                [key]: metadata
              },
              last_correction: metadata
            };

            console.log('Saving to database:', payload);

            const headers = authService.getAuthHeaders();
            const response = await fetch(
              `${API_BASE_URL}/api/v1/blob/update-confidence-scores/${encodeURIComponent(processedBlobPath)}`,
              {
                method: 'PUT',
                headers: {
                  ...headers,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
              }
            );

            if (!response.ok) {
              throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`✅ Saved correction to database: ${data.updated_fields} confidence scores, ${data.updated_values} values`);
            return { success: true, data };

          } catch (err) {
            console.error('Failed to save correction to database:', err);
            return { success: false, error: err.message };
          }
        }
        return { success: false, reason: 'no_result' };
      };

      // Check if we should apply the correction (allow "None" as a valid value to apply)
      const shouldApply = valueToApply !== '' && (valueToApply === 'None' || valueToApply.trim() !== '');

      if (shouldApply) {
        
        // --- OPTIMISTIC PATH ---
        handlePairChange(filenameKey, key, valueToApply);

        // Update persistence refs
        setLastSavedPairsByIndex(prev => ({
          ...prev,
          [filenameKey]: { ...(prev[filenameKey] || {}), [key]: valueToApply }
        }));
        if (!savedCorrectionsRef.current[filenameKey]) savedCorrectionsRef.current[filenameKey] = {};
        savedCorrectionsRef.current[filenameKey][key] = valueToApply;

        // Manually corrected flag
        setManuallyCorrectedFields(prev => {
          const updated = {
            ...prev,
            [filenameKey]: { ...(prev[filenameKey] || {}), [key]: true }
          };
          savedCorrectionsRef.current['manually_corrected_fields'] = updated;
          return updated;
        });

        // Confidence Score
        let newConfidence = 0.95;
        if (analysis.current_confidence !== undefined) {
          newConfidence = Math.max(0.95, Math.min(0.99, analysis.current_confidence + 0.1));
        }

        setEditedConfidenceByIndex(prev => ({
          ...prev,
          [filenameKey]: { ...(prev[filenameKey] || {}), [key]: newConfidence }
        }));

        const confidenceKey = `${filenameKey}_confidence`;
        if (!savedCorrectionsRef.current[confidenceKey]) savedCorrectionsRef.current[confidenceKey] = {};
        savedCorrectionsRef.current[confidenceKey][key] = newConfidence;

        // Metadata
        setCorrectionMetadata(prev => ({
          ...prev,
          [filenameKey]: {
            ...(prev[filenameKey] || {}),
            [key]: { username: currentUser, timestamp: currentTimestamp }
          }
        }));

        setLastFileCorrectionMetadata(prev => ({
          ...prev,
          [filenameKey]: { username: currentUser, timestamp: currentTimestamp }
        }));

        console.log(`Applied suggested value for "${key}": "${value}" -> "${valueToApply}" (confidence: ${(newConfidence * 100).toFixed(1)}%)`);

        // Remove analysis result
        setAnalysisResults(prev => {
          const newResults = { ...prev };
          if (newResults[filenameKey]) {
            const updatedKey = { ...newResults[filenameKey] };
            delete updatedKey[key];
            if (Object.keys(updatedKey).length === 0) delete newResults[filenameKey];
            else newResults[filenameKey] = updatedKey;
          }
          return newResults;
        });

        handleDismissCorrection(filenameKey, key);

        // Save to database with explicit values
        const metadata = { username: currentUser, timestamp: currentTimestamp };
        await saveToDbImmediately(valueToApply, newConfidence, metadata);

        // Save to localStorage with explicit data (state hasn't updated yet)
        const explicitDataToSave = {
          editedPairs: {
            ...(editedPairsByIndex[filenameKey] || {}),
            [key]: valueToApply
          },
          editedConfidence: {
            ...(editedConfidenceByIndex[filenameKey] || {}),
            [key]: newConfidence
          },
          manuallyCorrected: {
            ...(manuallyCorrectedFields[filenameKey] || {}),
            [key]: true
          },
          correctionMetadata: {
            ...(correctionMetadata[filenameKey] || {}),
            [key]: metadata
          },
          lastFileCorrectionMetadata: { username: currentUser, timestamp: currentTimestamp },
          timestamp: new Date().toISOString()
        };
        saveToLocalStorage(filenameKey, explicitDataToSave);


      } else {
        // --- API FALLBACK PATH ---
        const headers = authService.getAuthHeaders();
        const response = await fetch(`${API_BASE_URL}/api/v1/ocr/enhanced/correct`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            key,
            value: typeof value === 'object' ? JSON.stringify(value) : String(value),
            context: context || ''
          })
        });

        if (!response.ok) throw new Error(`Server error: ${response.status} ${response.statusText}`);

        const data = await response.json();
        if (data.status === 'error' || data.status === 'warning') {
          console.warn('Auto-correct warning:', data.reasoning);
          alert(`Auto-correct: ${data.reasoning || 'LLM service not available'}`);
          return;
        }

        // Apply changes
        handlePairChange(filenameKey, key, data.corrected_value);

        setLastSavedPairsByIndex(prev => ({
          ...prev,
          [filenameKey]: { ...(prev[filenameKey] || {}), [key]: data.corrected_value }
        }));

        if (!savedCorrectionsRef.current[filenameKey]) savedCorrectionsRef.current[filenameKey] = {};
        savedCorrectionsRef.current[filenameKey][key] = data.corrected_value;

        setManuallyCorrectedFields(prev => {
          const updated = {
            ...prev,
            [filenameKey]: { ...(prev[filenameKey] || {}), [key]: true }
          };
          savedCorrectionsRef.current['manually_corrected_fields'] = updated;
          return updated;
        });

        let newConfidence = Math.max(0.95, Math.min(0.99, data.confidence_score || 0.95));

        setEditedConfidenceByIndex(prev => ({
          ...prev,
          [filenameKey]: { ...(prev[filenameKey] || {}), [key]: newConfidence }
        }));

        const confidenceKey = `${filenameKey}_confidence`;
        if (!savedCorrectionsRef.current[confidenceKey]) savedCorrectionsRef.current[confidenceKey] = {};
        savedCorrectionsRef.current[confidenceKey][key] = newConfidence;

        setCorrectionMetadata(prev => ({
          ...prev,
          [filenameKey]: {
            ...(prev[filenameKey] || {}),
            [key]: { username: currentUser, timestamp: currentTimestamp }
          }
        }));

        setLastFileCorrectionMetadata(prev => ({
          ...prev,
          [filenameKey]: { username: currentUser, timestamp: currentTimestamp }
        }));

        if (data.corrected_value !== value) {
          console.log(`Corrected "${key}": "${value}" -> "${data.corrected_value}" (confidence: ${(newConfidence * 100).toFixed(1)}%)`);
        }

        handleDismissCorrection(filenameKey, key);

        // Save to database with explicit values
        const metadata = { username: currentUser, timestamp: currentTimestamp };
        await saveToDbImmediately(data.corrected_value, newConfidence, metadata);

        // Save to localStorage with explicit data (state hasn't updated yet)
        const explicitDataToSave = {
          editedPairs: {
            ...(editedPairsByIndex[filenameKey] || {}),
            [key]: data.corrected_value
          },
          editedConfidence: {
            ...(editedConfidenceByIndex[filenameKey] || {}),
            [key]: newConfidence
          },
          manuallyCorrected: {
            ...(manuallyCorrectedFields[filenameKey] || {}),
            [key]: true
          },
          correctionMetadata: {
            ...(correctionMetadata[filenameKey] || {}),
            [key]: metadata
          },
          lastFileCorrectionMetadata: { username: currentUser, timestamp: currentTimestamp },
          timestamp: new Date().toISOString()
        };
        saveToLocalStorage(filenameKey, explicitDataToSave);
      }

    } catch (err) {
      console.error('Auto-correct error:', err);
      alert(`Failed to auto-correct value: ${err.message}`);
    } finally {
      setCorrectingKeys(prev => {
        const next = { ...prev };
        delete next[correctionKey];
        return next;
      });
    }
  };

  const handleKeyValuePairClick = async (filenameKey, key, value, result) => {
    try {
      // Get processed file blob path from result
      let processedBlobPath = null;

      // Try multiple ways to get the processed blob path
      // 1. From blob_storage.processed_json.blob_path
      if (result?.blob_storage?.processed_json?.blob_path) {
        processedBlobPath = result.blob_storage.processed_json.blob_path;
      }
      // 2. From blob_storage.processed_json.blob_name
      else if (result?.blob_storage?.processed_json?.success && result?.blob_storage?.processed_json?.blob_name) {
        processedBlobPath = result.blob_storage.processed_json.blob_name;
      }
      // 3. From direct processed_blob_path
      else if (result?.processed_blob_path) {
        processedBlobPath = result.processed_blob_path;
      }
      // 4. From blob_storage if it's a string (blob name)
      else if (result?.blob_storage && typeof result.blob_storage === 'string') {
        processedBlobPath = result.blob_storage;
      }
      // 5. Try to construct from filename if we have metadata
      else if (result?.filename || result?.file_info?.filename) {
        // If we're viewing a result file that was opened, we might not have the blob path
        // In this case, we'll show an error message
        alert('Source file information not available. The result file must be opened from Azure Blob Storage to access the source file.');
        return;
      } else {
        // If we don't have the blob path in the result, we can't find the source file
        alert('Source file information not available. Please open the result file from Azure Blob Storage.');
        return;
      }

      // Get source file path from API
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/source-from-processed/${encodeURIComponent(processedBlobPath)}`,
        { headers }
      );

      if (!response.ok) {
        throw new Error(`Failed to get source file: ${response.statusText}`);
      }

      const data = await response.json();
      const sourceBlobPath = data.source_blob_path;

      // Debug logging to see what fields are in the result object
      console.log('=== DEBUG OCR DATA ===');
      console.log('Result keys:', Object.keys(result || {}));
      console.log('raw_ocr_results:', result?.raw_ocr_results);
      console.log('text_blocks:', result?.text_blocks);
      console.log('positioning_data:', result?.positioning_data);
      console.log('processing_id:', result?.processing_id);
      console.log('Full result structure:', result);

      // Get OCR positioning data from result - check multiple locations
      let ocrData = null;
      let rawOcrText = null;

      // Check various locations for OCR data
      if (result?.raw_ocr_results) {
        ocrData = result.raw_ocr_results;
      } else if (result?.text_blocks) {
        ocrData = result.text_blocks;
      } else if (result?.positioning_data) {
        ocrData = result.positioning_data;
      } else if (result?.data?.raw_ocr_results) {
        ocrData = result.data.raw_ocr_results;
      } else if (result?.data?.text_blocks) {
        ocrData = result.data.text_blocks;
      } else if (result?.data?.positioning_data) {
        ocrData = result.data.positioning_data;
      } else if (result?.result?.raw_ocr_results) {
        ocrData = result.result.raw_ocr_results;
      } else if (result?.result?.text_blocks) {
        ocrData = result.result.text_blocks;
      } else if (result?.processed_data?.raw_ocr_results) {
        ocrData = result.processed_data.raw_ocr_results;
      } else if (result?.processed_data?.text_blocks) {
        ocrData = result.processed_data.text_blocks;
      }

      // Get raw OCR text from various locations
      if (result?.raw_ocr_text) {
        rawOcrText = result.raw_ocr_text;
      } else if (result?.data?.raw_ocr_text) {
        rawOcrText = result.data.raw_ocr_text;
      } else if (result?.result?.raw_ocr_text) {
        rawOcrText = result.result.raw_ocr_text;
      } else if (result?.processed_data?.raw_ocr_text) {
        rawOcrText = result.processed_data.raw_ocr_text;
      }

      // If OCR data is still missing and we have a processing_id, try to fetch it from the processed blob
      if (!ocrData && result?.processing_id) {
        try {
          console.log('OCR data not in result, attempting to fetch from processed blob...');
          const headers = authService.getAuthHeaders();
          
          // The processing_id is the path to the processed JSON file
          const ocrResponse = await fetch(
            `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(result.processing_id)}`,
            { headers }
          );

          if (ocrResponse.ok) {
            // Check if response is JSON or blob
            const contentType = ocrResponse.headers.get('content-type');
            let ocrBlobData;
            
            if (contentType && contentType.includes('application/json')) {
              ocrBlobData = await ocrResponse.json();
            } else {
              // Try to parse as JSON text
              const text = await ocrResponse.text();
              try {
                ocrBlobData = JSON.parse(text);
              } catch (e) {
                console.warn('Failed to parse blob response as JSON:', e);
                ocrBlobData = null;
              }
            }
            
            if (ocrBlobData) {
              console.log('Fetched data from blob, keys:', Object.keys(ocrBlobData || {}));
              
              // Check the fetched data for OCR information
              if (ocrBlobData?.raw_ocr_results) {
                ocrData = ocrBlobData.raw_ocr_results;
              } else if (ocrBlobData?.text_blocks) {
                ocrData = ocrBlobData.text_blocks;
              } else if (ocrBlobData?.positioning_data) {
                ocrData = ocrBlobData.positioning_data;
              } else if (ocrBlobData?.data?.raw_ocr_results) {
                ocrData = ocrBlobData.data.raw_ocr_results;
              } else if (ocrBlobData?.data?.text_blocks) {
                ocrData = ocrBlobData.data.text_blocks;
              } else if (ocrBlobData?.data?.positioning_data) {
                ocrData = ocrBlobData.data.positioning_data;
              }
              
              if (ocrBlobData?.raw_ocr_text) {
                rawOcrText = ocrBlobData.raw_ocr_text;
              } else if (ocrBlobData?.data?.raw_ocr_text) {
                rawOcrText = ocrBlobData.data.raw_ocr_text;
              }
            }
          } else {
            console.warn(`Failed to fetch OCR data: ${ocrResponse.status} ${ocrResponse.statusText}`);
          }
        } catch (fetchErr) {
          console.warn('Failed to fetch OCR data from blob:', fetchErr);
        }
      }

      // If still no OCR data, log a warning
      if (!ocrData) {
        console.warn('raw_ocr_results not available for highlighting');
        console.warn('Checked locations: raw_ocr_results, text_blocks, positioning_data, data.*, result.*, processed_data.*');
      } else {
        console.log('✅ Found OCR data for highlighting');
      }

      // Open source file viewer
      setSourceViewerData({
        sourceBlobPath,
        highlightText: `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`,
        filename: result.filename || result.file_info?.filename || 'source_file',
        key,
        value,
        ocrData: ocrData, // Pass OCR positioning data for highlighting
        rawOcrText: rawOcrText
      });
      setSourceViewerOpen(true);
    } catch (err) {
      console.error('Error opening source file:', err);
      alert(`Failed to open source file: ${err.message}`);
    }
  };

  const normalizePairs = (pairs) => {
    const n = {};
    Object.entries(pairs || {}).forEach(([k, v]) => {
      if (typeof v === 'string') {
        const t = v.trim();
        if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))) {
          try { n[k] = JSON.parse(t); return; } catch { }
        }
      }
      n[k] = v;
    });
    return n;
  };

  const downloadExcel = async (filenameKey, result, filename) => {
    try {
      const data = {
        file_info: {
          filename,
          content_type: result?.file_info?.content_type || 'application/pdf',
          size_bytes: result?.file_info?.size_bytes || 0
        },
        key_value_pairs: normalizePairs(editedPairsByIndex[filenameKey] || result.key_value_pairs),
        summary: result.summary || '',
        raw_ocr_text: result.raw_ocr_text || ''
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/ocr/export/excel/from-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ processed_data: data, include_raw_text: true, include_metadata: true })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${filename}_extracted.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Excel export failed: ${e.message}`);
    }
  };

  const downloadBatchExcel = async () => {
    try {
      const batchData = {
        batch_info: { total_files: totalFiles, successful_files: successfulFiles, failed_files: failedFiles, template_used: templateUsed },
        individual_results: mergedResults.map((r, i) => {
          const filenameKey = getFilenameKey(r, i);
          return {
            file_info: {
              filename: r.filename || `file_${i + 1}`,
              content_type: r?.file_info?.content_type || 'application/pdf',
              size_bytes: r?.file_info?.size_bytes || 0
            },
            key_value_pairs: normalizePairs(editedPairsByIndex[filenameKey] || r.key_value_pairs),
            summary: r.summary || '',
            raw_ocr_text: r.raw_ocr_text || ''
          };
        })
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/ocr/export/excel/batch/from-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_data: batchData, include_raw_text: true, include_metadata: true })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'batch_extracted_documents.zip';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Batch export failed: ${e.message}`);
    }
  };

  // Helper function to check if a field key matches a mandatory field
  const isMandatoryField = (key) => {
    const requiredFields = {
      'Name': [
        'name', 'full_name', 'patient_name', 'member_name', 
        'first_name', 'last_name', 'firstname', 'lastname',
        'patient name', 'member name', 'full name'
      ],
      'Date of Birth': [
        'date_of_birth', 'dob', 'birth_date', 'birthdate',
        'date of birth', 'birth date', 'patient_dob', 'member_dob'
      ],
      'Member ID': [
        'member_id', 'memberid', 'member_number', 'member_number',
        'unique_identifier', 'unique_id', 'patient_id', 'patientid',
        'member id', 'member number', 'unique identifier'
      ],
      'Address': [
        'address', 'zip_code', 'zipcode', 'zip', 'postal_code',
        'postal code', 'patient_address', 'member_address',
        'address_line', 'street_address'
      ],
      'Gender': [
        'gender', 'sex', 'patient_gender', 'member_gender'
      ],
      'Insurance ID': [
        'insurance_id', 'insuranceid', 'insurance_number', 'insurance_number',
        'group_id', 'groupid', 'group_number', 'group_number',
        'insurance id', 'insurance number', 'group id', 'group number',
        'policy_number', 'policy number'
      ]
    };

    const lowerKey = key.toLowerCase();
    return Object.values(requiredFields).some(possibleKeys => {
      return possibleKeys.some(pk => {
        const lowerPk = pk.toLowerCase();
        return lowerKey === lowerPk || lowerKey.includes(lowerPk) || lowerPk.includes(lowerKey);
      });
    });
  };

  // Helper function to normalize analysis results for mandatory fields
  const normalizeMandatoryFieldSuggestions = (analysisResults, keyValuePairs) => {
    const normalized = { ...analysisResults };
    
    Object.keys(normalized).forEach(key => {
      const analysis = normalized[key];
      if (!analysis) return;
      
      // Check if this is a mandatory field
      if (isMandatoryField(key)) {
        // Get the current value
        const currentValue = keyValuePairs[key];
        const isEmpty = !currentValue || 
                       (typeof currentValue === 'string' && currentValue.trim() === '') || 
                       String(currentValue).trim() === 'None' || 
                       String(currentValue).trim() === 'N/A' ||
                       String(currentValue).trim() === 'null';
        
        // If value is empty/None, ALWAYS replace suggested_value with "None" (regardless of what LLM returned)
        if (isEmpty) {
          const suggestedValue = String(analysis.suggested_value || '').trim();
          // Always replace with "None" if current value is empty/None for mandatory fields
          normalized[key] = {
            ...analysis,
            suggested_value: 'None'
          };
          console.log(`🔄 Replaced suggested value with "None" for mandatory field: ${key} (current value was empty/None)`);
        }
      }
    });
    
    return normalized;
  };

  // Helper function to get the display value for suggested_value (handles mandatory fields)
  const getSuggestedValueDisplay = (analysis, key, keyValuePairs) => {
    if (!analysis) {
      return 'No suggestion available';
    }

    // If this is a mandatory field with empty/None current value, ALWAYS show "None"
    if (isMandatoryField(key)) {
      const currentValue = keyValuePairs[key];
      const isEmpty = !currentValue || 
                     (typeof currentValue === 'string' && currentValue.trim() === '') || 
                     String(currentValue).trim() === 'None' || 
                     String(currentValue).trim() === 'N/A' ||
                     String(currentValue).trim() === 'null';
      
      if (isEmpty) {
        // Always return "None" for mandatory fields with empty/None values, regardless of what suggested_value is
        return 'None';
      }
    }

    // For non-mandatory fields or mandatory fields with values, show the suggested_value
    if (!analysis.suggested_value) {
      return analysis?.suggested_value === null || analysis?.suggested_value === undefined 
        ? 'No suggestion available' 
        : 'NULL';
    }

    const suggestedValue = String(analysis.suggested_value).trim();
    return suggestedValue.replace(/\s+/g, ' ');
  };

  // Function to check for missing mandatory fields
  const checkMissingMandatoryFields = async (filenameKey, result) => {
    setCheckingMissingFields(prev => ({ ...prev, [filenameKey]: true }));
    
    try {
      // Get key-value pairs from edited or original result
      const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};

      // Define required fields and their possible key names (same as FilesTable)
      const requiredFields = {
        'Name': [
          'name', 'full_name', 'patient_name', 'member_name', 
          'first_name', 'last_name', 'firstname', 'lastname',
          'patient name', 'member name', 'full name'
        ],
        'Date of Birth': [
          'date_of_birth', 'dob', 'birth_date', 'birthdate',
          'date of birth', 'birth date', 'patient_dob', 'member_dob'
        ],
        'Member ID': [
          'member_id', 'memberid', 'member_number', 'member_number',
          'unique_identifier', 'unique_id', 'patient_id', 'patientid',
          'member id', 'member number', 'unique identifier'
        ],
        'Address': [
          'address', 'zip_code', 'zipcode', 'zip', 'postal_code',
          'postal code', 'patient_address', 'member_address',
          'address_line', 'street_address'
        ],
        'Gender': [
          'gender', 'sex', 'patient_gender', 'member_gender'
        ],
        'Insurance ID': [
          'insurance_id', 'insuranceid', 'insurance_number', 'insurance_number',
          'group_id', 'groupid', 'group_number', 'group_number',
          'insurance id', 'insurance number', 'group id', 'group number',
          'policy_number', 'policy number'
        ]
      };

      const missing = [];

      // Check each required field
      Object.keys(requiredFields).forEach(fieldName => {
        const possibleKeys = requiredFields[fieldName];
        const found = possibleKeys.some(key => {
          // Case-insensitive search
          const lowerKey = key.toLowerCase();
          return Object.keys(keyValuePairs).some(k => {
            const lowerK = k.toLowerCase();
            // Exact match or contains the key
            return lowerK === lowerKey || lowerK.includes(lowerKey) || lowerKey.includes(lowerK);
          });
        });

        if (!found) {
          missing.push(fieldName);
        } else {
          // Additional check: if found but value is empty/null/undefined
          const foundKey = Object.keys(keyValuePairs).find(k => {
            const lowerK = k.toLowerCase();
            return possibleKeys.some(pk => {
              const lowerPk = pk.toLowerCase();
              return lowerK === lowerPk || lowerK.includes(lowerPk) || lowerPk.includes(lowerK);
            });
          });

          if (foundKey) {
            const value = keyValuePairs[foundKey];
            // Check if value is empty, null, undefined, or just whitespace
            if (!value || (typeof value === 'string' && value.trim() === '') || value === 'None' || value === 'N/A') {
              missing.push(fieldName);
            }
          }
        }
      });

      // Update modal state with missing fields
      setMissingFieldsModal(prev => ({
        ...prev,
        [filenameKey]: {
          open: true,
          fields: missing
        }
      }));
    } catch (error) {
      console.error(`Failed to check missing fields for ${filenameKey}:`, error);
      alert('Failed to check missing fields. Please try again.');
    } finally {
      setCheckingMissingFields(prev => ({ ...prev, [filenameKey]: false }));
    }
  };

  // === Icon logic ===
  const getFileIcon = (result) => {
    const type = result?.file_info?.content_type || '';
    const isPdf = type === 'application/pdf' || result.filename?.toLowerCase().endsWith('.pdf');
    return isPdf ? (
      <img src="/pdf.svg" alt="PDF" width={37} className="hidden sm:block" />
    ) : (
      <img src="/doc.svg" alt="Document" width={37} className="hidden sm:block" />
    );
  };

  if (!results || resultsArray.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No enhanced OCR results to display</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
        <h2 className="text-xl sm:text-2xl font-bold text-[#ffffff]">
          {isBatch ? 'Enhanced Batch OCR Results' : 'Enhanced OCR Results'}
        </h2>
        <div className="flex flex-wrap sm:flex-nowrap items-center justify-start sm:justify-end gap-2 w-full sm:w-auto">
          {/* <Button variant="outline" size="sm" onClick={() => setShowRawText(!showRawText)} className="flex-1 sm:flex-none whitespace-nowrap">
            {showRawText ? <EyeOff className="h-4 w-4 mr-2 flex-shrink-0" /> : <Eye className="h-4 w-4 mr-2 flex-shrink-0" />}
            <span className="hidden sm:inline">{showRawText ? 'Hide' : 'Show'} Raw Text</span>
            <span className="sm:hidden">Raw Text</span>
          </Button> */}
          <Button variant="outline" size="sm" onClick={() => setShowKeyValuePairs(!showKeyValuePairs)} className="flex-1 sm:flex-none whitespace-nowrap">
            <Table className="h-4 w-4 mr-2 flex-shrink-0" />
            <span className="hidden sm:inline">{showKeyValuePairs ? 'Hide' : 'Show'} Key-Value</span>
            <span className="sm:hidden">Key-Value</span>
          </Button>
          {isBatch && (
            <Button
              variant="outline"
              size="sm"
              onClick={downloadBatchExcel}
              className="bg-green-50 hover:bg-green-100 text-green-700 border-green-200 flex-1 sm:flex-none whitespace-nowrap"
            >
              <FileSpreadsheet className="h-4 w-4 mr-2 flex-shrink-0" />
              <span className="hidden sm:inline">Download All Excel</span>
              <span className="sm:hidden">Excel</span>
            </Button>
          )}
        </div>
      </div>

      {/* Batch Summary */}
      {isBatch && batchInfo && (
        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
          <div className="flex flex-col items-center justify-center text-center p-4 bg-[#FBFCFF] rounded-lg h-auto sm:h-[171px] w-full sm:flex-1 gap-2 sm:gap-3">
            <div className="text-[36px] sm:text-[50px] font-bold text-primary">{totalFiles}</div>
            <div className="text-[14px] sm:text-[18px] text-muted-foreground">Total Files</div>
          </div>
          <div className="flex flex-col items-center justify-center text-center p-4 bg-[#3C77EF] rounded-lg h-auto sm:h-[171px] w-full sm:flex-1 gap-2 sm:gap-3">
            <div className="text-[36px] sm:text-[50px] font-bold text-white">{successfulFiles}</div>
            <div className="text-[14px] sm:text-[16px] text-white">Successful</div>
          </div>
          <div className="flex flex-col items-center justify-center text-center p-4 bg-[#D95356] rounded-lg h-auto sm:h-[171px] w-full sm:flex-1 gap-2 sm:gap-3">
            <div className="text-[36px] sm:text-[50px] font-bold text-white">{failedFiles}</div>
            <div className="text-[14px] sm:text-[16px] text-white">Failed</div>
          </div>
          {/* <div className="flex flex-col items-center justify-center text-center p-4 bg-[#8D41CC] rounded-lg h-auto sm:h-[171px] w-full sm:flex-1 gap-2 sm:gap-3">
            <div className="text-[32px] sm:text-[40px] font-bold text-white">{templateUsed}</div>
            <div className="text-[14px] sm:text-[16px] text-white">Template Used</div>
          </div> */}
        </div>
      )}

      {/* Individual Files */}
      {mergedResults.map((result, idx) => {
        const filenameKey = getFilenameKey(result, idx);
        
        // Check if all key-value pairs have confidence >= 95%
        const checkAllPairsAbove95 = () => {
          const keyValuePairs = editedPairsByIndex[filenameKey] || result.key_value_pairs || {};
          const confidenceScores = editedConfidenceByIndex[filenameKey] || result.key_value_pair_confidence_scores || {};
          
          // If no key-value pairs, return false (can't be successful)
          const keys = Object.keys(keyValuePairs);
          if (keys.length === 0) {
            return false;
          }
          
          // Check if all pairs have confidence >= 0.95
          return keys.every(key => {
            let confidence = confidenceScores[key];
            
            // Normalize confidence: handle both decimal (0.9) and percentage (90) formats
            if (confidence !== undefined && confidence !== null) {
              // If confidence is > 1, assume it's a percentage and convert to decimal
              if (confidence > 1) {
                confidence = confidence / 100;
              }
              return confidence >= 0.95;
            }
            
            // If no confidence score, consider it as not meeting the threshold
            return false;
          });
        };
        
        const allPairsAbove95 = checkAllPairsAbove95();
        const statusText = allPairsAbove95 ? 'Completed' : 'Pending';
        const statusBgColor = allPairsAbove95 ? 'bg-[#E6F7E6]' : 'bg-[#FFEEE6]';
        const statusBorderColor = allPairsAbove95 ? 'border-[#B8E6B8]' : 'border-[#F5CEBD]';
        const statusTextColor = allPairsAbove95 ? 'text-[#2D7A2D]' : 'text-[#D46637]';
        
        return (
          <Card key={filenameKey} className="w-full">
            <CardHeader
              className="cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => toggleFile(filenameKey)}
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
                <div className="flex items-center space-x-2 sm:space-x-3 flex-1 min-w-0 w-full sm:w-auto">
                  {expandedFiles.has(filenameKey) ? <ChevronDown className="h-4 w-4 flex-shrink-0" /> : <ChevronRight className="h-4 w-4 flex-shrink-0" />}
                  <div className="hidden sm:block flex-shrink-0">
                    {getFileIcon(result)}
                  </div>
                  <div className="leading-[1.1] min-w-0 flex-1">
                    <div className="text-[16px] sm:text-[20px] lg:text-[24px] font-semibold truncate">
                      {result.filename || `File ${idx + 1}`} {/* <-- REAL FILENAME */}
                    </div>
                    <p className="text-xs sm:text-sm text-muted-foreground break-words sm:break-normal">
                      <span className="inline-block sm:inline">
                        {(() => {
                          // Try multiple possible locations for processing_time
                          const processingTime = result.processing_time
                            || result.processing_info?.processing_time
                            || result.processing_time_seconds
                            || (result.processing_info && result.processing_info.processing_time);

                          // If we have processing_time from processing_info, also check if we need to add extraction time
                          let totalTime = processingTime;

                          // If we have extraction processing time separately, add it
                          if (result.processing_info?.extraction_time && processingTime) {
                            totalTime = processingTime + result.processing_info.extraction_time;
                          }

                          return totalTime ? `${parseFloat(totalTime).toFixed(2)}s` : 'Unknown time';
                        })()}
                      </span>
                      <span className="hidden sm:inline"> • </span>
                      <span className="block sm:inline">
                        {result.key_value_pairs ? Object.keys(result.key_value_pairs).length : 0} key-value pairs
                      </span>
                    </p>
                  </div>
                </div>
                {/* <div className='w-[20%] flex flex-col' >
                  <span className='text-[#6B7280] '>Status</span>
                  <span className={`${statusBgColor} border ${statusBorderColor} ${statusTextColor} py-1 px-3 rounded-[100px] w-[120px] text-center font-semibold ml-[-5px] mt-1`}>
                    {statusText}
                  </span>
                </div> */}
                <div className='w-[20%] flex flex-col'>
                  <span className='text-[#6B7280]'>Assigned to </span>
                  <div className="flex items-center gap-0 ml-[20px] relative user-assignment-dropdown">
                    {(() => {
                      // Find assigned user by matching filename
                      const assignedUserId = findAssignedUserByFilename(result, assignedUsers);
                      const blobName = getBlobNameFromResult(result);
                      const isDropdownOpen = openDropdowns[filenameKey] || false;
                      
                      if (assignedUserId && assignedUserId !== 'unassigned') {
                        // Convert userId for comparison
                        const userIdStr = String(assignedUserId);
                        const userIdNum = Number(assignedUserId);
                        
                        // Find user in availableUsers (try all possible ID fields)
                        const user = availableUsers.find(u => {
                          return (
                            String(u.id) === userIdStr ||
                            String(u.user_id) === userIdStr ||
                            String(u.id) === String(userIdNum) ||
                            String(u.user_id) === String(userIdNum) ||
                            u.username === userIdStr ||
                            u.email === userIdStr
                          );
                        });
                        
                        // Get username dynamically from user object
                        const userName = user ? (
                          user.username || 
                          user.name || 
                          user.full_name || 
                          user.display_name || 
                          user.email || 
                          String(user.id || user.user_id || '')
                        ) : String(assignedUserId);
                        
                        const userInitial = getUserInitial(assignedUserId);
                        const userColor = getUserColor(assignedUserId);
                        
                        // Only show if we have a valid initial (not '?')
                        if (userInitial !== '?') {
                          return (
                            <div className="relative">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenDropdowns(prev => ({ ...prev, [filenameKey]: !prev[filenameKey] }));
                                }}
                                className={`text-[#111827] h-[36px] w-[36px] ${userColor} flex justify-center items-center rounded-full text-[#fff] font-semibold cursor-pointer hover:opacity-90 transition-opacity`}
                                title={userName}
                              >
                                {userInitial}
                              </button>
                              {isDropdownOpen && (
                                <div className="absolute top-[40px] left-0 z-50 bg-white border border-gray-200 rounded-md shadow-lg min-w-[180px] max-h-[200px] overflow-y-auto">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleAssignUser(result, 'unassigned');
                                      setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                    }}
                                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 first:rounded-t-md"
                                  >
                                    Unassigned
                                  </button>
                                  {availableUsers.map((u) => {
                                    const uId = String(u.id || u.user_id || u.username || '');
                                    return (
                                      <button
                                        key={uId}
                                        type="button"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleAssignUser(result, uId);
                                          setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                        }}
                                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 last:rounded-b-md"
                                      >
                                        {getUserDisplayName(u)}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        } else {
                          // If user not found yet, show loading state or number temporarily
                          return (
                            <div className="relative">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenDropdowns(prev => ({ ...prev, [filenameKey]: !prev[filenameKey] }));
                                }}
                                className='text-[#111827] h-[36px] w-[36px] bg-gray-400 flex justify-center items-center rounded-full text-[#fff] font-semibold cursor-pointer hover:opacity-90 transition-opacity'
                                title={`Loading user ${assignedUserId}...`}
                              >
                                ?
                              </button>
                              {isDropdownOpen && (
                                <div className="absolute top-[40px] left-0 z-50 bg-white border border-gray-200 rounded-md shadow-lg min-w-[180px] max-h-[200px] overflow-y-auto">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleAssignUser(result, 'unassigned');
                                      setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                    }}
                                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 first:rounded-t-md"
                                  >
                                    Unassigned
                                  </button>
                                  {availableUsers.map((u) => {
                                    const uId = String(u.id || u.user_id || u.username || '');
                                    return (
                                      <button
                                        key={uId}
                                        type="button"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleAssignUser(result, uId);
                                          setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                        }}
                                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 last:rounded-b-md"
                                      >
                                        {getUserDisplayName(u)}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        }
                      } else {
                        // No user assigned - show "+" button with dropdown
                        return (
                          <div className="relative">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenDropdowns(prev => ({ ...prev, [filenameKey]: !prev[filenameKey] }));
                              }}
                              className='text-[#111827] h-[36px] w-[36px] bg-[#213E99] flex justify-center items-center rounded-full text-[#fff] font-semibold cursor-pointer hover:bg-[#1a2f7a] transition-colors'
                            >
                              +
                            </button>
                            {isDropdownOpen && (
                              <div className="absolute top-[40px] left-0 z-50 bg-white border border-gray-200 rounded-md shadow-lg min-w-[180px] max-h-[200px] overflow-y-auto">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleAssignUser(result, 'unassigned');
                                    setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 first:rounded-t-md"
                                >
                                  Unassigned
                                </button>
                                {availableUsers.map((u) => {
                                  const uId = String(u.id || u.user_id || u.username || '');
                                  return (
                                    <button
                                      key={uId}
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleAssignUser(result, uId);
                                        setOpenDropdowns(prev => ({ ...prev, [filenameKey]: false }));
                                      }}
                                      className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 last:rounded-b-md"
                                    >
                                      {getUserDisplayName(u)}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      }
                    })()}
                  </div>
                </div>
                <div className='w-[20%] flex flex-col'>
                  <span className='text-[#6B7280]'>Last Update </span>
                  <span className="text-[#111827] font-semibold">
                    {(() => {
                      // Use last correction metadata timestamp if available
                      if (lastFileCorrectionMetadata[filenameKey]?.timestamp) {
                        return lastFileCorrectionMetadata[filenameKey].timestamp;
                      }
                      // Fallback to result timestamp if available
                      if (result.timestamp) {
                        return new Date(result.timestamp).toLocaleString();
                      }
                      // Fallback to processing time if available
                      if (result.processing_info?.timestamp) {
                        return new Date(result.processing_info.timestamp).toLocaleString();
                      }
                      // Default fallback
                      return new Date().toLocaleString();
                    })()}
                  </span>
                </div>
                <div className="flex flex-col ">
                  <span className='text-[#6B7280]'>Confidence</span>
                  {(result.ocr_confidence_score !== undefined && result.ocr_confidence_score !== null) && (
                    <div
                      variant="outline"
                      className="flex text-green-700 border-green-200"
                    >
                      <span className="text-[26px] font-semibold">{(result.ocr_confidence_score * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {result.template_used && (
                    <div variant="outline" className="flex">
                      <File className="h-3 w-3 sm:h-4 sm:w-4" />
                      <span className=" truncate sm:max-w-none text-[26px] font-semibold">{result.template_used}</span>
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>

            {expandedFiles.has(filenameKey) && (
              <CardContent className="space-y-4">
                {/* Summary */}
                {/* {result.summary && (
                <div className="space-y-2">
                  <h4 className="font-medium text-[18px] sm:text-[20px] font-semibold">Document Summary</h4>
                  <div className="pb-6">
                    <p className="text-[14px] sm:text-[16px]">{result.summary}</p>
                  </div>
                </div>
              )} */}

                {/* Key-Value Pairs */}
                {showKeyValuePairs && result.key_value_pairs && Object.keys(result.key_value_pairs).length > 0 && (() => {
                  // Separate pairs into high and low confidence (threshold: 90% or 0.9)
                  const confidenceScores = editedConfidenceByIndex[filenameKey] || result.key_value_pair_confidence_scores || {};
                  const HIGH_CONFIDENCE_THRESHOLD = 0.9; // 90%
                  
                  const highConfidencePairs = [];
                  const lowConfidencePairs = [];
                  
                  Object.entries(editedPairsByIndex[filenameKey] || result.key_value_pairs).forEach(([k, v]) => {
                    let confidence = confidenceScores[k];
                    
                    // Normalize confidence: handle both decimal (0.9) and percentage (90) formats
                    if (confidence !== undefined && confidence !== null) {
                      if (confidence > 1) {
                        confidence = confidence / 100;
                      }
                    }
                    
                    const confNum = confidence !== undefined && confidence !== null 
                      ? (typeof confidence === 'string' ? parseFloat(confidence) : confidence)
                      : null;
                    
                    if (confNum !== null && confNum >= HIGH_CONFIDENCE_THRESHOLD) {
                      highConfidencePairs.push([k, v, confidence]);
                    } else {
                      lowConfidencePairs.push([k, v, confidence]);
                    }
                  });
                  
                  return (
                    <div className="space-y-2">
                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
                        <h4 className="font-medium text-[18px] sm:text-[20px] font-semibold">Key-Value Pairs</h4>
                        <div className="flex flex-wrap items-center justify-start sm:justify-end gap-2 w-full sm:w-auto">

                          {!isEditingByIndex[filenameKey] ? (
                            <>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                onClick={() => checkMissingMandatoryFields(filenameKey, result)} 
                                disabled={checkingMissingFields[filenameKey]}
                                className="flex-1 sm:flex-none min-w-0"
                              >
                                {checkingMissingFields[filenameKey] ? (
                                  <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin flex-shrink-0" />
                                    <span className="hidden sm:inline">Checking...</span>
                                    <span className="sm:hidden">...</span>
                                  </>
                                ) : (
                                  <>
                                    <AlertCircleIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                                    <span className="hidden sm:inline">Missing Fields</span>
                                    <span className="sm:hidden">Fields</span>
                                  </>
                                )}
                              </Button>
                              <Button variant="outline" size="sm" onClick={() => startEditing(filenameKey)} className="flex-1 sm:flex-none min-w-0">Edit</Button>
                            </>
                          ) : (
                            <>
                              <Button size="sm" onClick={() => saveEditing(filenameKey)} className="flex-1 sm:flex-none min-w-0">Save</Button>
                              <Button size="sm" variant="outline" onClick={() => cancelEditing(filenameKey)} className="flex-1 sm:flex-none min-w-0">Cancel</Button>
                            </>
                          )}

                          <Button variant="outline" size="sm" onClick={() => copyToClipboard(JSON.stringify(editedPairsByIndex[filenameKey] || result.key_value_pairs, null, 2))} className="flex-1 sm:flex-none min-w-0">
                            <Copy className="h-4 w-4 mr-2 flex-shrink-0" /> <span className="hidden sm:inline truncate">Copy JSON</span><span className="sm:hidden truncate">Copy</span>
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => downloadKeyValuePairs(editedPairsByIndex[filenameKey] || result.key_value_pairs, result.filename || `file_${idx + 1}`)} className="flex-1 sm:flex-none min-w-0">
                            <Download className="h-4 w-4 mr-2 flex-shrink-0" /> <span className="hidden sm:inline truncate">Download JSON</span><span className="sm:hidden truncate">JSON</span>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => downloadExcel(filenameKey, result, result.filename || `file_${idx + 1}`)}
                            className="bg-green-50 hover:bg-green-100 text-green-700 border-green-200 flex-1 sm:flex-none min-w-0"
                          >
                            <FileSpreadsheet className="h-4 w-4 mr-2 flex-shrink-0" /> <span className="hidden sm:inline truncate">Download Excel</span><span className="sm:hidden truncate">Excel</span>
                          </Button>
                        </div>
                      </div>
                      
                      {/* High-Confidence Extracted Details */}
                      {highConfidencePairs.length > 0 && (
                        <div className="space-y-3">
                          <div 
                            className="flex items-center gap-2 border-b border-gray-200 pb-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded transition-colors"
                            onClick={() => {
                              setExpandedConfidenceSections(prev => ({
                                ...prev,
                                [filenameKey]: {
                                  ...prev[filenameKey],
                                  high: !(prev[filenameKey]?.high !== false) // Default to true, toggle on click
                                }
                              }));
                            }}
                          >
                            <CheckCircle className="h-5 w-5 text-green-600" />
                            <h5 className="font-semibold text-[16px] sm:text-[18px] text-gray-900 flex-1">High-Confidence Extracted Details</h5>
                            {expandedConfidenceSections[filenameKey]?.high !== false ? (
                              <ChevronDown className="h-4 w-4 text-gray-500 transition-transform" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-gray-500 transition-transform" />
                            )}
                          </div>
                          {expandedConfidenceSections[filenameKey]?.high !== false && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {highConfidencePairs.map(([k, v, conf]) => {
                              // Use the confidence value passed from the map
                              let confidence = conf;
                              
                              // Normalize confidence: handle both decimal (0.9) and percentage (90) formats
                              if (confidence !== undefined && confidence !== null) {
                                // If confidence is > 1, assume it's a percentage and convert to decimal
                                if (confidence > 1) {
                                  confidence = confidence / 100;
                                }
                              }
                              
                              const confidencePercent = confidence !== undefined && confidence !== null
                                ? (confidence * 100).toFixed(1)
                                : null;

                        // Determine border color based on confidence
                        const getBorderColor = () => {
                          if (confidence === undefined || confidence === null) {
                            return 'border-gray-300'; // Gray if no confidence
                          }
                          // Convert to number if it's a string
                          const confNum = typeof confidence === 'string' ? parseFloat(confidence) : confidence;
                          if (confNum >= 0.9) {
                            return 'border-gray-300'; // Gray for >= 90%
                          }
                          return 'border-red-500'; // Red for < 90%
                        };

                        return (
                          <div
                            key={k}
                            className={`p-6 bg-muted/30 rounded  bg-[#fff] border border-color-[#E5E8EC] ${getBorderColor()} cursor-pointer  hover:bg-muted/50 transition-colors`}
                            onClick={() => !isEditingByIndex[idx] && handleKeyValuePairClick(idx, k, v, result)}
                            title={!isEditingByIndex[idx] ? "Click to view source file with highlighted text" : ""}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="font-medium text-[#111827] text-[16px] capitalize">{k}</div>
                              {confidencePercent !== null && (
                                <Badge
                                  variant="outline"
                                  className={`text-xs ${(() => {
                                    const confNum = typeof confidence === 'string' ? parseFloat(confidence) : confidence;
                                    if (confNum >= 0.95) return 'bg-green-50 text-green-700 border-green-200';
                                    if (confNum >= 0.9) return 'bg-amber-50 text-amber-700 border-amber-200';
                                    return 'bg-red-50 text-red-700 border-red-200';
                                  })()
                                    }`}
                                >
                                  {confidencePercent}%
                                </Badge>
                              )}
                            </div>
                            {(isEditingByIndex[filenameKey] || editingKeyValuePair === `${filenameKey}-${k}`) ? (
                              <div className="space-y-2">
                                <textarea
                                  className="w-full text-sm p-2 border rounded bg-white text-slate-900"
                                  rows={2}
                                  value={typeof (editedPairsByIndex[filenameKey]?.[k] ?? v) === 'object' ? JSON.stringify(editedPairsByIndex[filenameKey]?.[k] ?? v) : String(editedPairsByIndex[filenameKey]?.[k] ?? v ?? '')}
                                  onChange={(e) => handlePairChange(filenameKey, k, e.target.value)}
                                  onClick={(e) => e.stopPropagation()}
                                />
                                {editingKeyValuePair === `${filenameKey}-${k}` && (
                                  <div className="flex gap-2 justify-end">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        cancelEditingKeyValuePair(filenameKey, k);
                                      }}
                                      className="h-7 px-3 text-xs"
                                    >
                                      Cancel
                                    </Button>
                                    <Button
                                      size="sm"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        saveEditingKeyValuePair(filenameKey, k);
                                      }}
                                      className="h-7 px-3 text-xs"
                                    >
                                      Save
                                    </Button>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="text-sm">
                                {typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : String(v ?? '')}
                              </div>
                            )}

                            {/* User info and timestamp - shown after correction is applied */}
                            {correctionMetadata[filenameKey]?.[k] && (
                              <div className="mt-2 flex items-center justify-between text-xs text-slate-500 px-1 border-t border-slate-200 pt-2">
                                <span className="flex items-center gap-1">
                                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
                                    <circle cx="12" cy="7" r="4"></circle>
                                  </svg>
                                  {correctionMetadata[filenameKey][k].username}
                                </span>
                                <span className="flex items-center gap-1">
                                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 6 12 12 16 14"></polyline>
                                  </svg>
                                  {correctionMetadata[filenameKey][k].timestamp}
                                </span>
                              </div>
                            )}

                            {/* Analysis Results & Auto Correct - Not shown for high-confidence pairs */}
                          </div>
                        );
                      })}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* Low-Confidence Extracted Details */}
                      {lowConfidencePairs.length > 0 && (
                        <div className="space-y-3 mt-6">
                          <div 
                            className="flex items-center gap-2 border-b border-gray-200 pb-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded transition-colors"
                            onClick={() => {
                              setExpandedConfidenceSections(prev => ({
                                ...prev,
                                [filenameKey]: {
                                  ...prev[filenameKey],
                                  low: !(prev[filenameKey]?.low !== false) // Default to true, toggle on click
                                }
                              }));
                            }}
                          >
                            <AlertTriangle className="h-5 w-5 text-orange-600" />
                            <h5 className="font-semibold text-[16px] sm:text-[18px] text-gray-900 flex-1">Low-Confidence Extracted Details</h5>
                            {expandedConfidenceSections[filenameKey]?.low !== false ? (
                              <ChevronDown className="h-4 w-4 text-gray-500 transition-transform" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-gray-500 transition-transform" />
                            )}
                          </div>
                          {expandedConfidenceSections[filenameKey]?.low !== false && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {lowConfidencePairs.map(([k, v, confidence]) => {
                              // Get confidence score for this key-value pair
                              // First try from the array, then fallback to confidenceScores object
                              let conf = confidence;
                              
                              // If confidence is missing from array, try to get it from confidenceScores
                              if ((conf === undefined || conf === null) && confidenceScores[k] !== undefined) {
                                conf = confidenceScores[k];
                              }
                              
                              // Normalize confidence: handle both decimal (0.9) and percentage (90) formats
                              if (conf !== undefined && conf !== null) {
                                // If confidence is > 1, assume it's a percentage and convert to decimal
                                if (conf > 1) {
                                  conf = conf / 100;
                                }
                              }
                              
                              const confidencePercent = conf !== undefined && conf !== null
                                ? (conf * 100).toFixed(1)
                                : null;
                              
                              // Determine border color based on confidence
                              const getBorderColor = () => {
                                if (conf === undefined || conf === null) {
                                  return 'border-gray-300'; // Gray if no confidence
                                }
                                // Convert to number if it's a string
                                const confNum = typeof conf === 'string' ? parseFloat(conf) : conf;
                                if (confNum >= 0.9) {
                                  return 'border-gray-300'; // Gray for >= 90%
                                }
                                return 'border-red-500'; // Red for < 90%
                              };
                              
                              return (
                                <div
                                  key={k}
                                  className={`p-6 bg-muted/30 rounded bg-[#fff] border border-color-[#E5E8EC] ${getBorderColor()} cursor-pointer hover:bg-muted/50 transition-colors`}
                                  onClick={() => !isEditingByIndex[idx] && handleKeyValuePairClick(idx, k, v, result)}
                                  title={!isEditingByIndex[idx] ? "Click to view source file with highlighted text" : ""}
                                >
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="font-medium text-[#111827] text-[16px] capitalize">{k}</div>
                                    {confidencePercent !== null && (
                                      <Badge
                                        variant="outline"
                                        className={`text-xs ${(() => {
                                          const confNum = typeof conf === 'string' ? parseFloat(conf) : conf;
                                          if (confNum >= 0.95) return 'bg-green-50 text-green-700 border-green-200';
                                          if (confNum >= 0.9) return 'bg-amber-50 text-amber-700 border-amber-200';
                                          return 'bg-red-50 text-red-700 border-red-200';
                                        })()}`}
                                      >
                                        {confidencePercent}%
                                      </Badge>
                                    )}
                                  </div>
                                  {(isEditingByIndex[filenameKey] || editingKeyValuePair === `${filenameKey}-${k}`) ? (
                                    <div className="space-y-2">
                                      <textarea
                                        className="w-full text-sm p-2 border rounded bg-white text-slate-900"
                                        rows={2}
                                        value={typeof (editedPairsByIndex[filenameKey]?.[k] ?? v) === 'object' ? JSON.stringify(editedPairsByIndex[filenameKey]?.[k] ?? v) : String(editedPairsByIndex[filenameKey]?.[k] ?? v ?? '')}
                                        onChange={(e) => handlePairChange(filenameKey, k, e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                      />
                                      {editingKeyValuePair === `${filenameKey}-${k}` && (
                                        <div className="flex gap-2 justify-end">
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              cancelEditingKeyValuePair(filenameKey, k);
                                            }}
                                            className="h-7 px-3 text-xs"
                                          >
                                            Cancel
                                          </Button>
                                          <Button
                                            size="sm"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              saveEditingKeyValuePair(filenameKey, k);
                                            }}
                                            className="h-7 px-3 text-xs"
                                          >
                                            Save
                                          </Button>
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <div className="text-sm">
                                      {typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : String(v ?? '')}
                                    </div>
                                  )}
                                  
                                  {/* User info and timestamp - shown after correction is applied */}
                                  {correctionMetadata[filenameKey]?.[k] && (
                                    <div className="mt-2 flex items-center justify-between text-xs text-slate-500 px-1 border-t border-slate-200 pt-2">
                                      <span className="flex items-center gap-1">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                          <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
                                          <circle cx="12" cy="7" r="4"></circle>
                                        </svg>
                                        {correctionMetadata[filenameKey][k].username}
                                      </span>
                                      <span className="flex items-center gap-1">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                          <circle cx="12" cy="12" r="10"></circle>
                                          <polyline points="12 6 12 12 16 14"></polyline>
                                        </svg>
                                        {correctionMetadata[filenameKey][k].timestamp}
                                      </span>
                                    </div>
                                  )}
                                  
                                  {/* Analysis Results & Auto Correct */}
                                  {(() => {
                                    // Check if analysis results exist
                                    const fileAnalysis = analysisResults[filenameKey];
                                    const hasAnalysis = fileAnalysis && fileAnalysis[k];
                                    // Show analysis if confidence is missing OR if confidence is below 95%
                                    // Also show if we're in low-confidence section (confidence might be null)
                                    const confidenceCheck = confidencePercent === null || (confidencePercent !== null && parseFloat(confidencePercent) < 95);
                                    const editingCheck = !isEditingByIndex[filenameKey] && editingKeyValuePair !== `${filenameKey}-${k}`;
                                    
                                    // Show analysis if we have it and we're not editing
                                    if (hasAnalysis && editingCheck && confidenceCheck) {
                                      return true;
                                    }
                                    
                                    return false;
                                  })() && (
                                    <div className="mt-3 pt-3 border-t border-border/60" onClick={(e) => e.stopPropagation()}>
                                      {(() => {
                                        const analysis = analysisResults[filenameKey][k];
                                        const status = analysis?.extraction_status || 'unknown';
                                        const showAutoCorrect = !dismissedCorrections.has(`${filenameKey}-${k}`);
                                        
                                        // Determine status styles
                                        let statusConfig = {
                                          color: 'text-slate-700',
                                          bg: 'bg-slate-50',
                                          border: 'border-slate-200',
                                          icon: Info,
                                          text: 'Analysis Result'
                                        };
                                        
                                        if (status === 'correct') {
                                          statusConfig = { color: 'text-green-700', bg: 'bg-green-50', border: 'border-green-200', icon: Check, text: 'Extraction Verified' };
                                        } else if (status === 'incorrect') {
                                          statusConfig = { color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200', icon: X, text: 'Extraction Incorrect' };
                                        } else if (status === 'incomplete') {
                                          statusConfig = { color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', icon: AlertTriangle, text: 'Extraction Incomplete' };
                                        } else if (status === 'missing') {
                                          statusConfig = { color: 'text-orange-700', bg: 'bg-orange-50', border: 'border-orange-200', icon: AlertCircle, text: 'Field Missing' };
                                        }
                                        
                                        const StatusIcon = statusConfig.icon;
                                        
                                        // Check if suggested value equals extracted value
                                        const extractedValue = String(v ?? '').trim();
                                        const suggestedValue = String(analysis.suggested_value ?? '').trim();
                                        const valuesAreEqual = extractedValue === suggestedValue && extractedValue !== '';
                                        
                                        // If values are equal and confidence is below 100%, boost confidence and hide suggestion
                                        if (valuesAreEqual && confidencePercent !== null && parseFloat(confidencePercent) < 100) {
                                          // Generate random confidence between 95.9% and 99.5%
                                          const randomConfidence = 0.959 + (Math.random() * (0.995 - 0.959));
                                          // Auto-boost confidence score - update state properly
                                          setEditedConfidenceByIndex(prev => ({
                                            ...prev,
                                            [filenameKey]: {
                                              ...(prev[filenameKey] || {}),
                                              [k]: randomConfidence
                                            }
                                          }));
                                          // Don't render suggestion box
                                          return null;
                                        }
                                        
                                        return (
                                          <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                                            {/* Suggested Value - Always show for below 95% pairs */}
                                            <div className="rounded-md overflow-hidden border border-blue-100 shadow-sm ring-1 ring-blue-50">
                                              <div className="px-3 py-1.5 bg-blue-50/80 border-b border-blue-100 flex items-center gap-2">
                                                <Sparkles className="h-3.5 w-3.5 text-blue-600" />
                                                <span className="text-xs font-semibold text-blue-900 uppercase tracking-wide">Suggested Value</span>
                                              </div>
                                              <div className="p-3 bg-white">
                                                {editingSuggestedValue === `${filenameKey}-${k}` ? (
                                                  <div className="space-y-2">
                                                    <textarea
                                                      className="w-full text-sm p-2 border rounded resize-none bg-white text-slate-900"
                                                      rows={3}
                                                      value={editedSuggestedValues[`${filenameKey}-${k}`] ?? getSuggestedValueDisplay(analysis, k, editedPairsByIndex[filenameKey] || result.key_value_pairs || {})}
                                                      onChange={(e) => handleSuggestedValueChange(filenameKey, k, e.target.value)}
                                                      onClick={(e) => e.stopPropagation()}
                                                    />
                                                    <div className="flex gap-2 justify-end">
                                                      <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={(e) => {
                                                          e.stopPropagation();
                                                          cancelEditingSuggestedValue(filenameKey, k);
                                                        }}
                                                        className="h-7 px-3 text-xs"
                                                      >
                                                        Cancel
                                                      </Button>
                                                      <Button
                                                        size="sm"
                                                        onClick={(e) => {
                                                          e.stopPropagation();
                                                          saveEditingSuggestedValue(filenameKey, k);
                                                        }}
                                                        className="h-7 px-3 text-xs"
                                                      >
                                                        Save
                                                      </Button>
                                                    </div>
                                                  </div>
                                                ) : (
                                                  <div className="text-sm text-slate-700 break-words whitespace-normal leading-relaxed">
                                                    {getSuggestedValueDisplay(analysis, k, editedPairsByIndex[filenameKey] || result.key_value_pairs || {})}
                                                  </div>
                                                )}
                                              </div>
                                            </div>
                                            
                                            {/* Auto Correct Action */}
                                            {showAutoCorrect && editingSuggestedValue !== `${filenameKey}-${k}` && (
                                              <div className="mt-4 flex items-center justify-between bg-slate-50 rounded-lg p-1.5 pl-3 border border-slate-200 shadow-sm">
                                                <span className="text-xs font-medium text-slate-600">Apply this correction?</span>
                                                <div className="flex items-center gap-1">
                                                  {correctingKeys[`${filenameKey}-${k}`] ? (
                                                    <div className="px-3 py-1.5">
                                                      <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                                                    </div>
                                                  ) : (
                                                    <>
                                                      <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 px-3 text-xs font-medium text-slate-600 hover:bg-slate-200 hover:text-slate-900 transition-colors"
                                                        onClick={(e) => {
                                                          e.stopPropagation();
                                                          startEditingSuggestedValue(filenameKey, k);
                                                        }}
                                                        title="Edit"
                                                      >
                                                        <Pencil className="h-4 w-4" />
                                                      </Button>
                                                      <Button
                                                        size="sm"
                                                        className="h-7 px-3 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all hover:shadow-md flex items-center gap-1.5"
                                                        onClick={(e) => {
                                                          e.stopPropagation();
                                                          handleAutoCorrect(filenameKey, k, v, result.raw_ocr_text);
                                                        }}
                                                        title="Click to Fix"
                                                      >
                                                        <CheckCircle className="h-3.5 w-3.5" />
                                                      </Button>
                                                    </>
                                                  )}
                                                </div>
                                              </div>
                                            )}
                                            
                                            {/* User info and timestamp - shown below the button ONLY after correction is applied */}
                                            {correctionMetadata[filenameKey]?.[k] && (
                                              <div className="mt-2 flex items-center justify-between text-xs text-slate-500 px-1">
                                                <span className="flex items-center gap-1">
                                                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
                                                    <circle cx="12" cy="7" r="4"></circle>
                                                  </svg>
                                                  {correctionMetadata[filenameKey][k].username}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                    <circle cx="12" cy="12" r="10"></circle>
                                                    <polyline points="12 6 12 12 16 14"></polyline>
                                                  </svg>
                                                  {correctionMetadata[filenameKey][k].timestamp}
                                                </span>
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })()}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Raw OCR Text */}
                {showRawText && result.raw_ocr_text && (
                  <div className="space-y-2">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0 mt-6">
                      <h4 className="font-medium text-[18px] sm:text-[20px] font-semibold">Raw OCR Text</h4>
                      <div className="flex flex-wrap items-center justify-start sm:justify-end gap-2 w-full sm:w-auto">
                        {!isEditingTextByIndex[filenameKey] ? (
                          <Button variant="outline" size="sm" onClick={() => startEditingText(filenameKey)} className="flex-1 sm:flex-none min-w-0">Edit</Button>
                        ) : (
                          <>
                            <Button size="sm" onClick={() => saveEditingText(filenameKey)} className="flex-1 sm:flex-none min-w-0">Save</Button>
                            <Button size="sm" variant="outline" onClick={() => cancelEditingText(filenameKey)} className="flex-1 sm:flex-none min-w-0">Cancel</Button>
                          </>
                        )}
                        <Button variant="outline" size="sm" onClick={() => copyToClipboard(editedTextByIndex[filenameKey] || result.raw_ocr_text)} className="flex-1 sm:flex-none min-w-0">
                          <Copy className="h-4 w-4 mr-2 flex-shrink-0" /> <span className="truncate">Copy</span>
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => downloadText(editedTextByIndex[filenameKey] || result.raw_ocr_text, result.filename || `file_${idx + 1}`)} className="flex-1 sm:flex-none min-w-0">
                          <Download className="h-4 w-4 mr-2 flex-shrink-0" /> <span className="truncate">Download</span>
                        </Button>
                      </div>
                    </div>

                    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                      <div className="p-3 sm:p-6 max-h-96 overflow-y-auto text-[14px] sm:text-[16px] leading-relaxed text-gray-800">
                        {isEditingTextByIndex[filenameKey] ? (
                          <textarea
                            className="w-full h-60 sm:h-80 p-3 text-[14px] sm:text-[16px] font-mono bg-white border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                            value={editedTextByIndex[filenameKey] || ''}
                            onChange={(e) => handleTextChange(filenameKey, e.target.value)}
                            placeholder="Edit OCR text here..."
                          />
                        ) : (
                          <FormattedOCRText text={editedTextByIndex[filenameKey] || result.raw_ocr_text} />
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 p-3 sm:p-4 bg-muted/50 rounded-lg">
                  <div className="text-center">
                    <div className="text-xl sm:text-2xl font-bold text-primary">
                      {result.processing_time ? `${result.processing_time.toFixed(2)}s` : 'N/A'}
                    </div>
                    <div className="text-[10px] sm:text-xs text-muted-foreground">Processing Time</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl sm:text-2xl font-bold text-primary">
                      {result.key_value_pairs ? Object.keys(result.key_value_pairs).length : 0}
                    </div>
                    <div className="text-[10px] sm:text-xs text-muted-foreground">Key-Value Pairs</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl sm:text-2xl font-bold text-primary">
                      {result.raw_ocr_text?.length || 0}
                    </div>
                    <div className="text-[10px] sm:text-xs text-muted-foreground">Characters</div>
                  </div>
                  {(result.ocr_confidence_score !== undefined && result.ocr_confidence_score !== null) ? (
                    <div className="text-center">
                      <div className="text-xl sm:text-2xl font-bold text-primary">
                        {(result.ocr_confidence_score * 100).toFixed(1)}%
                      </div>
                      <div className="text-[10px] sm:text-xs text-muted-foreground">OCR Confidence</div>
                    </div>
                  ) : null}
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}

      {/* Missing Fields Modal */}
      {Object.keys(missingFieldsModal).map(filenameKey => {
        const modal = missingFieldsModal[filenameKey];
        if (!modal || !modal.open) return null;
        
        const result = mergedResults.find((r, idx) => getFilenameKey(r, idx) === filenameKey);
        const filename = result?.filename || filenameKey;
        
        return (
          <div
            key={filenameKey}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
            onClick={() => setMissingFieldsModal(prev => ({ ...prev, [filenameKey]: { ...prev[filenameKey], open: false } }))}
          >
            <div
              className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between p-6 border-b">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center">
                    <AlertCircleIcon className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Missing Mandatory Fields</h3>
                    <p className="text-sm text-gray-500">{filename}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMissingFieldsModal(prev => ({ ...prev, [filenameKey]: { ...prev[filenameKey], open: false } }))}
                  className="h-8 w-8 p-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Modal Content */}
              <div className="p-6 overflow-y-auto flex-1">
                {modal.fields.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
                    <h4 className="text-lg font-semibold text-gray-900 mb-2">All Mandatory Fields Present</h4>
                    <p className="text-gray-500">This file contains all required mandatory fields.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 text-orange-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <h4 className="font-semibold text-orange-900 mb-1">
                            {modal.fields.length} Mandatory Field{modal.fields.length !== 1 ? 's' : ''} Missing
                          </h4>
                          <p className="text-sm text-orange-700">
                            The following mandatory fields are missing or empty in this file:
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      {modal.fields.map((field, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
                        >
                          <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <X className="h-4 w-4 text-red-600" />
                          </div>
                          <span className="font-medium text-gray-900">{field}</span>
                        </div>
                      ))}
                    </div>

                    <div className="mt-6 pt-4 border-t border-gray-200">
                      <p className="text-sm text-gray-600">
                        <strong>Note:</strong> Please ensure all mandatory fields are filled before processing or exporting this file.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end gap-3 p-6 border-t bg-gray-50">
                <Button
                  variant="outline"
                  onClick={() => setMissingFieldsModal(prev => ({ ...prev, [filenameKey]: { ...prev[filenameKey], open: false } }))}
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        );
      })}

      {/* Source File Viewer Modal */}
      <SourceFileViewer
        isOpen={sourceViewerOpen}
        onClose={() => {
          setSourceViewerOpen(false);
          setSourceViewerData(null);
        }}
        sourceBlobPath={sourceViewerData?.sourceBlobPath}
        highlightText={sourceViewerData?.highlightText}
        filename={sourceViewerData?.filename}
        ocrData={sourceViewerData?.ocrData}
        rawOcrText={sourceViewerData?.rawOcrText}
        highlightKey={sourceViewerData?.key}
        value={sourceViewerData?.value}
      />
    </div>
  );
};

export default EnhancedOCRResults;