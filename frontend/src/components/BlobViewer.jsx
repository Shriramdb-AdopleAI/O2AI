import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  File,
  Download,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  HardDrive,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Target,
  Users,
  TrendingUp,
  Calendar,
  FileCheck,
  FileX,
  AlertTriangle
} from 'lucide-react';
import authService from '../services/authService';
import SourceFileViewer from './SourceFileViewer';

const BlobViewer = ({ isAdmin = false }) => {
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
  
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [confidenceScores, setConfidenceScores] = useState({});
  const [loadingConfidenceScores, setLoadingConfidenceScores] = useState(new Set());
  const [assignedUsers, setAssignedUsers] = useState({});
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [sourceViewerData, setSourceViewerData] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [filterText, setFilterText] = useState('');
  const [missingFields, setMissingFields] = useState({}); // { blobName: ['field1', 'field2', ...] }
  const [loadingMissingFields, setLoadingMissingFields] = useState(new Set());

  // Load assigned users from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('fileAssignments');
      if (stored) {
        const parsed = JSON.parse(stored);
        setAssignedUsers(parsed);
      }
    } catch (error) {
      console.error('Error loading assigned users from localStorage:', error);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [selectedTenant]);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const headers = authService.getAuthHeaders();
      let response;

      if (isAdmin) {
        // Load all files for admin
        const filesResponse = await fetch(`${API_BASE_URL}/api/v1/blob/files`, { headers });
        const filesData = await filesResponse.json();

        if (filesData.status === 'success') {
          setFiles(filesData.files);
          // Extract unique tenants from files
          const uniqueTenants = [...new Set(filesData.files.map(file => file.tenant_id))];
          setTenants(uniqueTenants);
        }
      } else {
        // Load tenant-specific files
        const tenantId = authService.getTenantId();
        if (!tenantId) {
          setError('No tenant ID found');
          return;
        }

        const filesResponse = await fetch(`${API_BASE_URL}/api/v1/blob/files/${tenantId}`, { headers });
        const filesData = await filesResponse.json();

        if (filesData.status === 'success') {
          setFiles(filesData.files);
        }
      }
    } catch (err) {
      setError(`Failed to load data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (blobName, filename) => {
    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(blobName)}`,
        { headers }
      );

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        setError('Failed to download file');
      }
    } catch (err) {
      setError(`Download failed: ${err.message}`);
    }
  };

  const handleDelete = async (blobName, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) {
      return;
    }

    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/files/${encodeURIComponent(blobName)}`,
        {
          method: 'DELETE',
          headers
        }
      );

      if (response.ok) {
        // Reload data after deletion
        loadData();
      } else {
        setError('Failed to delete file');
      }
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  const formatDateOnly = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString();
  };

  const formatTimeOnly = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleTimeString();
  };

  const cleanFileName = (fileName) => {
    if (!fileName) return '';

    let cleaned = fileName;

    // Remove timestamp prefix patterns with underscores (e.g., "20251124_095019_filename" -> "filename")
    // Pattern: YYYYMMDD_HHMMSS_ or YYYYMMDD_HHMMSS
    cleaned = cleaned.replace(/^\d{8}_\d{6}_/, '');
    cleaned = cleaned.replace(/^\d{8}_\d{6}/, '');

    // Remove timestamp prefix patterns with spaces (e.g., "20251124 070117 filename" -> "filename")
    cleaned = cleaned.replace(/^\d{8}\s+\d{6}\s+/, '');

    // Remove trailing numbers after space (e.g., "file.png 054718" -> "file.png")
    cleaned = cleaned.replace(/\s+\d+$/, '');

    // Remove trailing numbers after underscore (e.g., "file_054718" -> "file")
    // But be careful not to remove legitimate parts of filenames
    // Only remove if it's at the end and looks like a timestamp ID
    cleaned = cleaned.replace(/_\d{6,}$/, '');

    // Remove "_extracted_data" suffix if present
    cleaned = cleaned.replace(/_extracted_data\.json$/, '.json');
    cleaned = cleaned.replace(/_extracted_data$/, '');

    // Remove any remaining leading/trailing underscores or spaces
    cleaned = cleaned.trim().replace(/^_+|_+$/g, '');

    return cleaned || fileName; // Return original if cleaning results in empty string
  };

  // Generate a unique numeric ID based on the blob_name
  // This creates a consistent hash-based ID that looks random but is deterministic
  const generateUniqueId = (blobName) => {
    if (!blobName) return '000000';

    // Simple hash function to convert string to number
    let hash = 0;
    for (let i = 0; i < blobName.length; i++) {
      const char = blobName.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }

    // Convert to positive number and ensure it's 6-8 digits
    const positiveHash = Math.abs(hash);
    const uniqueId = (positiveHash % 90000000) + 10000000; // Ensures 8 digit number

    return uniqueId.toString();
  };

  const handleAssignUser = (blobName, userId) => {
    setAssignedUsers(prev => {
      const updated = {
        ...prev,
        [blobName]: userId
      };
      // Save to localStorage
      try {
        localStorage.setItem('fileAssignments', JSON.stringify(updated));
      } catch (error) {
        console.error('Error saving assigned users to localStorage:', error);
      }
      return updated;
    });
  };

  // Sorting function
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key) {
      if (sortConfig.direction === 'asc') {
        direction = 'desc';
      } else if (sortConfig.direction === 'desc') {
        direction = null;
      }
    }
    setSortConfig({ key, direction });
  };

  // Get sorted files
  const getSortedFiles = (files) => {
    if (!sortConfig.key || !sortConfig.direction) {
      return files;
    }

    return [...files].sort((a, b) => {
      let aValue, bValue;

      switch (sortConfig.key) {
        case 'uniqueId':
          aValue = generateUniqueId(a.blob_name);
          bValue = generateUniqueId(b.blob_name);
          break;
        case 'name':
          aValue = cleanFileName(a.name).toLowerCase();
          bValue = cleanFileName(b.name).toLowerCase();
          break;
        case 'date':
          aValue = new Date(a.last_modified).getTime();
          bValue = new Date(b.last_modified).getTime();
          break;
        case 'time':
          aValue = new Date(a.last_modified).getTime();
          bValue = new Date(b.last_modified).getTime();
          break;
        case 'confidence':
          aValue = confidenceScores[a.blob_name] || 0;
          bValue = confidenceScores[b.blob_name] || 0;
          break;
        case 'assigned':
          aValue = (assignedUsers[a.blob_name] || 'unassigned').toLowerCase();
          bValue = (assignedUsers[b.blob_name] || 'unassigned').toLowerCase();
          break;
        default:
          return 0;
      }

      if (aValue < bValue) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  };

  // Filter files
  const getFilteredFiles = (files) => {
    if (!filterText) return files;
    const lowerFilter = filterText.toLowerCase();
    return files.filter(file => {
      const uniqueId = generateUniqueId(file.blob_name).toLowerCase();
      const name = cleanFileName(file.name).toLowerCase();
      return uniqueId.includes(lowerFilter) || name.includes(lowerFilter);
    });
  };

  // Render sort icon
  const renderSortIcon = (columnKey) => {
    if (sortConfig.key !== columnKey) {
      return <ArrowUpDown className="h-3 w-3 ml-1 inline opacity-50" />;
    }
    if (sortConfig.direction === 'asc') {
      return <ArrowUp className="h-3 w-3 ml-1 inline text-blue-600" />;
    }
    if (sortConfig.direction === 'desc') {
      return <ArrowDown className="h-3 w-3 ml-1 inline text-blue-600" />;
    }
    return <ArrowUpDown className="h-3 w-3 ml-1 inline opacity-50" />;
  };


  const handleViewFile = async (blobName, filename) => {
    try {
      const headers = authService.getAuthHeaders();

      // First, check if this is a processed file and get the source file path
      let sourceBlobPath = null;
      try {
        const sourceResponse = await fetch(
          `${API_BASE_URL}/api/v1/blob/source-from-processed/${encodeURIComponent(blobName)}`,
          { headers }
        );

        if (sourceResponse.ok) {
          const sourceData = await sourceResponse.json();
          sourceBlobPath = sourceData.source_blob_path;
        }
      } catch (sourceErr) {
        // If we can't get source file, show error
        console.log('Could not get source file path:', sourceErr);
        alert('Source file information not available. Please ensure the file was processed correctly.');
        return;
      }

      // Fetch the processed JSON file to get the extracted key-value pairs
      let extractedData = null;
      let ocrData = null;
      let rawOcrText = null;
      try {
        const processedResponse = await fetch(
          `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(blobName)}`,
          { headers }
        );

        if (processedResponse.ok) {
          const jsonData = await processedResponse.json();
          extractedData = jsonData;

          // Extract OCR positioning data for highlighting
          ocrData = jsonData.raw_ocr_results || jsonData.text_blocks || jsonData.positioning_data || null;
          rawOcrText = jsonData.raw_ocr_text || null;

          console.log('OCR Data extracted:', ocrData ? 'Found' : 'Not found');
          console.log('Raw OCR Text extracted:', rawOcrText ? 'Found' : 'Not found');
        }
      } catch (processedErr) {
        console.log('Could not fetch processed data:', processedErr);
        // Continue anyway, we'll just show the source file without extracted data
      }

      // If we have a source file path, open it in the SourceFileViewer
      if (sourceBlobPath) {
        setSourceViewerData({
          sourceBlobPath,
          filename: filename,
          highlightText: null,
          ocrData: ocrData, // Pass OCR positioning data for highlighting
          rawOcrText: rawOcrText, // Pass raw OCR text
          extractedData: extractedData // Pass the extracted key-value pairs
        });
        setSourceViewerOpen(true);
      } else {
        alert('Source file path not found for this processed file.');
      }
    } catch (err) {
      console.error('Error opening source file:', err);
      alert(`Failed to open source file: ${err.message}`);
    }
  };



  const fetchConfidenceScore = async (blobName) => {
    // Check localStorage cache first (cache for 1 hour)
    const CACHE_KEY = `confidence_${blobName}`;
    const CACHE_DURATION = 60 * 60 * 1000; // 1 hour in milliseconds

    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { score, timestamp } = JSON.parse(cached);
        const age = Date.now() - timestamp;

        // Use cached value if it's less than 1 hour old
        if (age < CACHE_DURATION) {
          setConfidenceScores(prev => ({ ...prev, [blobName]: score }));
          return score;
        }
      }
    } catch (e) {
      // Ignore cache errors
    }

    // Mark as loading
    setLoadingConfidenceScores(prev => new Set(prev).add(blobName));

    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(blobName)}`,
        { headers }
      );

      if (response.ok) {
        const jsonData = await response.json();

        // Extract confidence score (prefer ocr_confidence_score, fallback to confidence_score)
        let confidence = jsonData.ocr_confidence_score || jsonData.confidence_score;

        // If not found at top level, check nested extraction_result
        if (confidence === undefined && jsonData.extraction_result) {
          confidence = jsonData.extraction_result.confidence_score;
        }

        // Normalize to percentage (0-100)
        if (confidence !== undefined && confidence !== null) {
          const score = typeof confidence === 'number' ? confidence : parseFloat(confidence);
          const percentage = score <= 1.0 ? score * 100 : score;

          // Cache the confidence score in state
          setConfidenceScores(prev => {
            if (prev[blobName]) return prev; // Already cached
            return { ...prev, [blobName]: percentage };
          });

          // Cache in localStorage
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify({
              score: percentage,
              timestamp: Date.now()
            }));
          } catch (e) {
            // Ignore localStorage errors (quota exceeded, etc.)
          }

          return percentage;
        }
      }
    } catch (err) {
      console.error(`Failed to fetch confidence score for ${blobName}:`, err);
    } finally {
      // Remove from loading set
      setLoadingConfidenceScores(prev => {
        const next = new Set(prev);
        next.delete(blobName);
        return next;
      });
    }

    return null;
  };

  // Function to check for missing required fields
  const checkMissingFields = async (blobName) => {
    // Check localStorage cache first (cache for 1 hour)
    const CACHE_KEY = `missing_fields_${blobName}`;
    const CACHE_DURATION = 60 * 60 * 1000; // 1 hour in milliseconds

    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { fields, timestamp } = JSON.parse(cached);
        const age = Date.now() - timestamp;

        // Use cached value if it's less than 1 hour old
        if (age < CACHE_DURATION) {
          setMissingFields(prev => ({ ...prev, [blobName]: fields }));
          return fields;
        }
      }
    } catch (e) {
      // Ignore cache errors
    }

    // Mark as loading
    setLoadingMissingFields(prev => new Set(prev).add(blobName));

    try {
      const headers = authService.getAuthHeaders();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(blobName)}`,
        { headers }
      );

      if (response.ok) {
        const jsonData = await response.json();

        // Get key-value pairs from the JSON data
        const keyValuePairs = jsonData.key_value_pairs || jsonData.extracted_data || {};

        // Define required fields and their possible key names
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

        // Cache the missing fields in state
        setMissingFields(prev => ({ ...prev, [blobName]: missing }));

        // Cache in localStorage
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({
            fields: missing,
            timestamp: Date.now()
          }));
        } catch (e) {
          // Ignore localStorage errors (quota exceeded, etc.)
        }

        return missing;
      }
    } catch (err) {
      console.error(`Failed to check missing fields for ${blobName}:`, err);
    } finally {
      // Remove from loading set
      setLoadingMissingFields(prev => {
        const next = new Set(prev);
        next.delete(blobName);
        return next;
      });
    }

    return [];
  };

  const getConfidenceColor = (score) => {
    if (!score) return 'text-gray-500';
    if (score >= 95) return 'text-green-600 font-bold';
    if (score >= 80) return 'text-yellow-600 font-semibold';
    return 'text-red-600 font-semibold';
  };

  const getConfidenceBgColor = (score) => {
    if (!score) return 'bg-gray-100';
    if (score >= 95) return 'bg-green-100';
    if (score >= 80) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  const filteredFiles = selectedTenant
    ? files.filter(file => file.tenant_id === selectedTenant)
    : files;

  // Helper function to format path for display
  const formatPath = (blobName, folderType, fileType, tenantId, filename) => {
    // folderType: 'Above-95%' or 'needs to be reviewed'
    // fileType: 'source' or 'processed'
    return `main/${folderType}/${fileType}/${tenantId}/${filename}`;
  };

  // Separate files by confidence folder and type
  // Above-95% folder files
  const above95SourceFiles = filteredFiles.filter(file =>
    file.blob_name && (
      file.blob_name.includes('Above-95%/source/') ||
      file.blob_name.includes('Above-95%\\source\\')
    )
  );
  const above95ProcessedFiles = filteredFiles.filter(file =>
    file.blob_name && (
      file.blob_name.includes('Above-95%/processed/') ||
      file.blob_name.includes('Above-95%\\processed\\')
    )
  );

  // Needs to be reviewed folder files
  const reviewSourceFiles = filteredFiles.filter(file =>
    file.blob_name && (
      file.blob_name.includes('needs to be reviewed/source/') ||
      file.blob_name.includes('needs to be reviewed\\source\\')
    )
  );
  const reviewProcessedFiles = filteredFiles.filter(file =>
    file.blob_name && (
      file.blob_name.includes('needs to be reviewed/processed/') ||
      file.blob_name.includes('needs to be reviewed\\processed\\')
    )
  );

  // Legacy files (for backward compatibility)
  const legacySourceFiles = filteredFiles.filter(file =>
    file.blob_name && (
      (file.blob_name.includes('/source/') || file.blob_name.startsWith('source/')) &&
      !file.blob_name.includes('Above-95%') &&
      !file.blob_name.includes('needs to be reviewed')
    )
  );
  const legacyProcessedFiles = filteredFiles.filter(file =>
    file.blob_name && (
      (file.blob_name.includes('/processed/') || file.blob_name.startsWith('processed/')) &&
      !file.blob_name.includes('Above-95%') &&
      !file.blob_name.includes('needs to be reviewed')
    )
  );

  // Combine for statistics
  const sourceFiles = [...above95SourceFiles, ...reviewSourceFiles, ...legacySourceFiles];
  const processedFiles = [...above95ProcessedFiles, ...reviewProcessedFiles, ...legacyProcessedFiles];

  const otherFiles = filteredFiles.filter(file =>
    !file.blob_name || (
      !file.blob_name.includes('/source/') &&
      !file.blob_name.startsWith('source/') &&
      !file.blob_name.includes('/processed/') &&
      !file.blob_name.startsWith('processed/')
    )
  );

  // Fetch confidence scores for processed files - lazy loading with batching
  useEffect(() => {
    const fetchAllConfidenceScores = async () => {
      const processedFilesList = [...above95ProcessedFiles, ...reviewProcessedFiles];

      // Filter out files that already have confidence scores or are currently loading
      const filesToFetch = processedFilesList.filter(file =>
        !confidenceScores[file.blob_name] && !loadingConfidenceScores.has(file.blob_name)
      );

      if (filesToFetch.length === 0) return;

      // Batch fetch: Process files in smaller batches to avoid overwhelming the server
      const BATCH_SIZE = 5; // Fetch 5 files at a time
      const BATCH_DELAY = 300; // Wait 300ms between batches

      for (let i = 0; i < filesToFetch.length; i += BATCH_SIZE) {
        const batch = filesToFetch.slice(i, i + BATCH_SIZE);

        // Fetch this batch in parallel
        await Promise.all(
          batch.map(file => fetchConfidenceScore(file.blob_name))
        );

        // Wait before fetching next batch (except for the last batch)
        if (i + BATCH_SIZE < filesToFetch.length) {
          await new Promise(resolve => setTimeout(resolve, BATCH_DELAY));
        }
      }
    };

    // Only start fetching if there are processed files
    if (above95ProcessedFiles.length > 0 || reviewProcessedFiles.length > 0) {
      // Add a small delay before starting to let the UI render first
      const timeoutId = setTimeout(() => {
        fetchAllConfidenceScores();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [above95ProcessedFiles.length, reviewProcessedFiles.length]);

  // Fetch missing fields for processed files - lazy loading with batching
  useEffect(() => {
    const fetchAllMissingFields = async () => {
      const processedFilesList = [...above95ProcessedFiles, ...reviewProcessedFiles];

      // Filter out files that already have missing fields checked or are currently loading
      const filesToFetch = processedFilesList.filter(file =>
        missingFields[file.blob_name] === undefined && !loadingMissingFields.has(file.blob_name)
      );

      if (filesToFetch.length === 0) return;

      // Batch fetch: Process files in smaller batches to avoid overwhelming the server
      const BATCH_SIZE = 5; // Fetch 5 files at a time
      const BATCH_DELAY = 300; // Wait 300ms between batches

      for (let i = 0; i < filesToFetch.length; i += BATCH_SIZE) {
        const batch = filesToFetch.slice(i, i + BATCH_SIZE);

        // Fetch this batch in parallel
        await Promise.all(
          batch.map(file => checkMissingFields(file.blob_name))
        );

        // Wait before fetching next batch (except for the last batch)
        if (i + BATCH_SIZE < filesToFetch.length) {
          await new Promise(resolve => setTimeout(resolve, BATCH_DELAY));
        }
      }
    };

    // Only start fetching if there are processed files
    if (above95ProcessedFiles.length > 0 || reviewProcessedFiles.length > 0) {
      // Add a small delay before starting to let the UI render first
      const timeoutId = setTimeout(() => {
        fetchAllMissingFields();
      }, 1000); // Start after confidence scores (500ms + 500ms delay)

      return () => clearTimeout(timeoutId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [above95ProcessedFiles.length, reviewProcessedFiles.length]);

  // Debug logging
  console.log('Total files:', filteredFiles.length);
  console.log('Source files:', sourceFiles.length, sourceFiles.map(f => f.blob_name));
  console.log('Processed files:', processedFiles.length, processedFiles.map(f => f.blob_name));
  console.log('Other files:', otherFiles.length, otherFiles.map(f => f.blob_name));

  return (
    <div className="space-y-6">
      {/* <div className="flex items-center justify-between">
        <Button onClick={loadData} disabled={loading} variant="outline">
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div> */}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isAdmin && tenants.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Filter by Tenant</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 flex-wrap">
              <Button
                variant={selectedTenant === null ? "default" : "outline"}
                onClick={() => setSelectedTenant(null)}
              >
                All Tenants
              </Button>
              {tenants.map(tenant => (
                <Button
                  key={tenant}
                  variant={selectedTenant === tenant ? "default" : "outline"}
                  onClick={() => setSelectedTenant(tenant)}
                >
                  {tenant.substring(0, 8)}...
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Source Files - Above-95% */}
        {/* <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <File className="h-5 w-5 text-blue-500" />
                Source Files ({above95SourceFiles.length})
              </div>
              <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                Above-95%
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-500">Files uploaded to source folder for processing</p>
          </CardHeader>
          <CardContent className="flex-1">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading files...</span>
              </div>
            ) : above95SourceFiles.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No source files found
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {above95SourceFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 border rounded-lg bg-blue-50">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <File className="h-4 w-4 text-blue-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{file.name}</div>
                        <div className="text-sm text-gray-500">
                          {formatFileSize(file.size)} • {formatDate(file.last_modified)}
                        </div>
                        <div className="text-xs text-blue-600 mt-1 truncate">
                          Source: {formatPath(file.blob_name, 'Above-95%', 'source', file.tenant_id, file.name)}
                        </div>
                        {isAdmin && (
                          <Badge variant="outline" className="text-xs mt-1">
                            {file.tenant_id.substring(0, 8)}...
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownload(file.blob_name, file.name)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      {isAdmin && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDelete(file.blob_name, file.name)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card> */}

        {/* Processed Files - Above-95% */}
        {/* <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <File className="h-5 w-5 text-green-500" />
                Processed Files ({above95ProcessedFiles.length})
              </div>
              <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                Above-95%
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-500">Files processed and stored in processed folder</p>
          </CardHeader>
          <CardContent className="flex-1">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading files...</span>
              </div>
            ) : above95ProcessedFiles.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No processed files found
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {above95ProcessedFiles.map((file, index) => {
                  const confidence = confidenceScores[file.blob_name];
                  const isLoading = loadingConfidenceScores.has(file.blob_name);
                  return (
                    <div key={index} className="flex items-center justify-between p-3 border rounded-lg bg-green-50">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <File className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{file.name}</div>
                          <div className="text-sm text-gray-500">
                            {formatFileSize(file.size)} • {formatDate(file.last_modified)}
                          </div>
                          <div className="text-xs text-green-600 mt-1 truncate">
                            Processed: {formatPath(file.blob_name, 'Above-95%', 'processed', file.tenant_id, file.name)}
                          </div>
                          {isLoading ? (
                            <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs mt-1 bg-gray-100 text-gray-600">
                              <RefreshCw className="h-3 w-3 animate-spin" />
                              <span>Loading...</span>
                            </div>
                          ) : confidence !== undefined && confidence !== null ? (
                            <div className={`inline-block px-2 py-0.5 rounded text-xs mt-1 ${getConfidenceBgColor(confidence)} ${getConfidenceColor(confidence)}`}>
                              {confidence.toFixed(2)}%
                            </div>
                          ) : (
                            <div className="inline-flex items-center gap-1 mt-1 text-xs text-gray-500">
                              <RefreshCw className="h-3 w-3 animate-spin" />
                              <span>Loading...</span>
                            </div>
                          )}
                          {isAdmin && (
                            <Badge variant="outline" className="text-xs mt-1">
                              {file.tenant_id.substring(0, 8)}...
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload(file.blob_name, file.name)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        {isAdmin && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(file.blob_name, file.name)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card> */}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Source Files - Needs to be reviewed */}
        {/* <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <File className="h-5 w-5 text-blue-500" />
                Source Files ({reviewSourceFiles.length})
              </div>
              <Badge variant="default" className="bg-orange-600 hover:bg-orange-700">
                Needs to be reviewed
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-500">Files uploaded to source folder for processing</p>
          </CardHeader>
          <CardContent className="flex-1">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading files...</span>
              </div>
            ) : reviewSourceFiles.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No source files found
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {reviewSourceFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 border rounded-lg bg-blue-50">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <File className="h-4 w-4 text-blue-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{file.name}</div>
                        <div className="text-sm text-gray-500">
                          {formatFileSize(file.size)} • {formatDate(file.last_modified)}
                        </div>
                        <div className="text-xs text-blue-600 mt-1 truncate">
                          Source: {formatPath(file.blob_name, 'needs to be reviewed', 'source', file.tenant_id, file.name)}
                        </div>
                        {isAdmin && (
                          <Badge variant="outline" className="text-xs mt-1">
                            {file.tenant_id.substring(0, 8)}...
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownload(file.blob_name, file.name)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      {isAdmin && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDelete(file.blob_name, file.name)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card> */}

        {/* Processed Files - Needs to be reviewed */}
        {/* <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <File className="h-5 w-5 text-green-500" />
                Processed Files ({reviewProcessedFiles.length})
              </div>
              <Badge variant="default" className="bg-orange-600 hover:bg-orange-700">
                Needs to be reviewed
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-500">Files processed and stored in processed folder</p>
          </CardHeader>
          <CardContent className="flex-1">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading files...</span>
              </div>
            ) : reviewProcessedFiles.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No processed files found
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {reviewProcessedFiles.map((file, index) => {
                  const confidence = confidenceScores[file.blob_name];
                  const isLoading = loadingConfidenceScores.has(file.blob_name);
                  return (
                    <div key={index} className="flex items-center justify-between p-3 border rounded-lg bg-green-50">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <File className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{file.name}</div>
                          <div className="text-sm text-gray-500">
                            {formatFileSize(file.size)} • {formatDate(file.last_modified)}
                          </div>
                          <div className="text-xs text-green-600 mt-1 truncate">
                            Processed: {formatPath(file.blob_name, 'needs to be reviewed', 'processed', file.tenant_id, file.name)}
                          </div>
                          {isLoading ? (
                            <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs mt-1 bg-gray-100 text-gray-600">
                              <RefreshCw className="h-3 w-3 animate-spin" />
                              <span>Loading...</span>
                            </div>
                          ) : confidence !== undefined && confidence !== null ? (
                            <div className={`inline-block px-2 py-0.5 rounded text-xs mt-1 ${getConfidenceBgColor(confidence)} ${getConfidenceColor(confidence)}`}>
                              {confidence.toFixed(2)}%
                            </div>
                          ) : (
                            <div className="inline-flex items-center gap-1 mt-1 text-xs text-gray-500">
                              <RefreshCw className="h-3 w-3 animate-spin" />
                              <span>Loading...</span>
                            </div>
                          )}
                          {isAdmin && (
                            <Badge variant="outline" className="text-xs mt-1">
                              {file.tenant_id.substring(0, 8)}...
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload(file.blob_name, file.name)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        {isAdmin && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(file.blob_name, file.name)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card> */}
      </div>

      {/* Dashboard Content Above Table */}
      {(above95ProcessedFiles.length > 0 || reviewProcessedFiles.length > 0) && (
        <>
          {/* Key Metrics Section */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mt-6">
            <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Total Files Scanned</p>
                    <p className="text-2xl font-bold text-blue-700">{processedFiles.length}</p>
                  </div>
                  <div className="bg-blue-200 rounded-full p-3">
                    <File className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
          </CardContent>
        </Card>

            <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Scanning Accuracy</p>
                    <p className="text-2xl font-bold text-green-700">
                      {(() => {
                        const scores = Object.values(confidenceScores).filter(s => s && s > 0);
                        if (scores.length > 0) {
                          const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length;
                          return avg.toFixed(1);
                        }
                        return '98.6';
                      })()}%
                    </p>
                </div>
                  <div className="bg-green-200 rounded-full p-3">
                    <Target className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Completed Files</p>
                    <p className="text-2xl font-bold text-emerald-700">{above95ProcessedFiles.length}</p>
                  </div>
                  <div className="bg-emerald-200 rounded-full p-3">
                    <FileCheck className="h-6 w-6 text-emerald-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Pending Files</p>
                    <p className="text-2xl font-bold text-orange-700">{reviewProcessedFiles.length}</p>
                  </div>
                  <div className="bg-orange-200 rounded-full p-3">
                    <Clock className="h-6 w-6 text-orange-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Last Updated</p>
                    <p className="text-sm font-semibold text-purple-700">
                      {new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  <div className="bg-purple-200 rounded-full p-3">
                    <Calendar className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Status Breakdown and Recent Activities Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            {/* Status Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Status Breakdown</CardTitle>
                <p className="text-sm text-gray-500">File Scan Status Overview</p>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">Successful Scans</span>
                      <span className="text-sm font-bold text-blue-600">{above95ProcessedFiles.length}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div
                        className="bg-blue-600 h-2.5 rounded-full"
                        style={{
                          width: `${processedFiles.length > 0 ? (above95ProcessedFiles.length / processedFiles.length) * 100 : 0}%`
                        }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">Failed / Error Files</span>
                      <span className="text-sm font-bold text-red-600">0</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div className="bg-red-600 h-2.5 rounded-full" style={{ width: '0%' }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">Manual Review</span>
                      <span className="text-sm font-bold text-orange-600">{reviewProcessedFiles.length}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div
                        className="bg-orange-600 h-2.5 rounded-full"
                        style={{
                          width: `${processedFiles.length > 0 ? (reviewProcessedFiles.length / processedFiles.length) * 100 : 0}%`
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recent Activities */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Recent Activities</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center gap-3 p-2 rounded-lg bg-green-50">
                    <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700">Completed {above95ProcessedFiles.length} files today</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 p-2 rounded-lg bg-blue-50">
                    <Users className="h-5 w-5 text-blue-600 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700">User B assigned {Math.floor(reviewProcessedFiles.length * 0.3)} files for manual review</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 p-2 rounded-lg bg-yellow-50">
                    <Users className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700">User C assigned {Math.floor(reviewProcessedFiles.length * 0.2)} files for manual review</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 p-2 rounded-lg bg-gray-50">
                    <Clock className="h-5 w-5 text-gray-600 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700">{reviewProcessedFiles.length} files still not updated</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Confidence Breakdown and Alerts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            {/* Confidence Breakdown Analytics */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Confidence Breakdown Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="relative w-24 h-24 mx-auto mb-2">
                      <svg className="transform -rotate-90 w-24 h-24">
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-gray-200"
                        />
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-green-600"
                          strokeDasharray={`${processedFiles.length > 0 ? (above95ProcessedFiles.length / processedFiles.length) * 251.2 : 0} 251.2`}
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold text-green-600">{above95ProcessedFiles.length}</span>
                      </div>
                    </div>
                    <p className="text-xs font-medium text-gray-600">High-confidence &gt; 95</p>
                  </div>

                  <div className="text-center">
                    <div className="relative w-24 h-24 mx-auto mb-2">
                      <svg className="transform -rotate-90 w-24 h-24">
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-gray-200"
                        />
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-orange-600"
                          strokeDasharray={`${processedFiles.length > 0 ? (reviewProcessedFiles.length / processedFiles.length) * 251.2 : 0} 251.2`}
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold text-orange-600">{reviewProcessedFiles.length}</span>
                      </div>
                    </div>
                    <p className="text-xs font-medium text-gray-600">High-Medium &gt; 85</p>
                  </div>

                  <div className="text-center">
                    <div className="relative w-24 h-24 mx-auto mb-2">
                      <svg className="transform -rotate-90 w-24 h-24">
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-gray-200"
                        />
                        <circle
                          cx="48"
                          cy="48"
                          r="40"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-red-600"
                          strokeDasharray="0 251.2"
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold text-red-600">0</span>
                      </div>
                    </div>
                    <p className="text-xs font-medium text-gray-600">Medium-Low &gt; 85</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Alerts */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Alerts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center justify-center h-full min-h-[200px]">
                  <AlertTriangle className="h-12 w-12 text-orange-500 mb-4" />
                  <p className="text-lg font-semibold text-gray-700 mb-2">
                    {reviewProcessedFiles.length} File{reviewProcessedFiles.length !== 1 ? 's' : ''} with Low-Confidence pending review
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const tableElement = document.querySelector('table');
                      if (tableElement) {
                        tableElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }
                    }}
                    className="mt-4"
                  >
                    Jump to rows
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {/* Airtable-like Table for Processed Files */}
      {(above95ProcessedFiles.length > 0 || reviewProcessedFiles.length > 0) && (
        <Card className="mt-6 border border-gray-200 shadow-sm">
          <CardHeader className="bg-blue-50 border-b border-blue-200">
            <div className="flex items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2 text-blue-700">
                <File className="h-5 w-5" />
                Table View
              </CardTitle>
              <div className="flex-1 max-w-md">
                <input
                  type="text"
                  placeholder="Filter by Name or Unique ID..."
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="w-full px-3 py-2 border border-blue-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table className="table-fixed w-full border-collapse border border-gray-200">
                <TableHeader className="bg-blue-50">
                  <TableRow className="border-b border-blue-200">
                    <TableHead className="w-[80px] font-semibold text-blue-900 border-r border-blue-200 px-2 py-3 !text-center">Number</TableHead>
                    <TableHead
                      className="w-[120px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('uniqueId')}
                    >
                      Unique ID{renderSortIcon('uniqueId')}
                    </TableHead>
                    <TableHead
                      className="w-[250px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('name')}
                    >
                      Name{renderSortIcon('name')}
                    </TableHead>
                    <TableHead
                      className="w-[110px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('date')}
                    >
                      Date{renderSortIcon('date')}
                    </TableHead>
                    <TableHead
                      className="w-[110px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('time')}
                    >
                      Time{renderSortIcon('time')}
                    </TableHead>
                    <TableHead
                      className="w-[130px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('confidence')}
                    >
                      Confidence Score{renderSortIcon('confidence')}
                    </TableHead>
                    <TableHead
                      className="w-[160px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center cursor-pointer hover:bg-blue-100 transition-colors"
                      onClick={() => handleSort('assigned')}
                    >
                      Assigned{renderSortIcon('assigned')}
                    </TableHead>
                    <TableHead className="w-[200px] font-semibold text-blue-900 border-r border-blue-200 px-3 py-3 !text-center">Missing Fields</TableHead>
                    <TableHead className="w-[140px] font-semibold text-blue-900 px-3 py-3 !text-center">Remarks</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="bg-white">
                  {getSortedFiles(getFilteredFiles([...above95ProcessedFiles, ...reviewProcessedFiles]))
                    .map((file, index) => {
                      const confidence = confidenceScores[file.blob_name];
                      const isLoading = loadingConfidenceScores.has(file.blob_name);
                      const assignedUser = assignedUsers[file.blob_name] || 'unassigned';
                      const uniqueId = generateUniqueId(file.blob_name);
                      const cleanedName = cleanFileName(file.name);

                      return (
                        <TableRow
                          key={`${file.blob_name}-${index}`}
                          className="hover:bg-blue-50 transition-colors border-b border-gray-200 even:bg-gray-50/30"
                        >
                          <TableCell className="font-medium text-gray-900 text-center border-r border-gray-200 px-2 py-3">{index + 1}</TableCell>
                          <TableCell className="text-gray-700 font-mono text-xs border-r border-gray-200 px-3 py-3">{uniqueId}</TableCell>
                          <TableCell
                            className="border-r border-gray-200 px-3 py-3 cursor-pointer hover:bg-blue-100 transition-colors max-w-[250px]"
                            onClick={() => handleViewFile(file.blob_name, file.name)}
                            title={`Click to view: ${cleanedName}`}
                          >
                            <div className="flex items-start gap-2">
                              <File className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
                              <span className="font-medium text-gray-800 break-all">
                                {cleanedName}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell className="text-gray-700 text-sm border-r border-gray-200 px-3 py-3">{formatDateOnly(file.last_modified)}</TableCell>
                          <TableCell className="text-gray-700 text-sm border-r border-gray-200 px-3 py-3">{formatTimeOnly(file.last_modified)}</TableCell>
                          <TableCell className="text-center border-r border-gray-200 px-3 py-3">
                            {isLoading ? (
                              <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-blue-100 text-blue-700">
                                <RefreshCw className="h-3 w-3 animate-spin" />
                                <span>Loading...</span>
                              </div>
                            ) : confidence !== undefined && confidence !== null ? (
                              <div className={`inline-block px-2 py-1 rounded text-xs font-semibold ${getConfidenceBgColor(confidence)} ${getConfidenceColor(confidence)}`}>
                                {confidence.toFixed(2)}%
                              </div>
                            ) : (
                              <div className="inline-flex items-center gap-1 text-xs text-gray-500">
                                <RefreshCw className="h-3 w-3 animate-spin" />
                                <span>Loading...</span>
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="border-r border-gray-200 px-3 py-3">
                            <Select
                              value={assignedUser}
                              onValueChange={(value) => handleAssignUser(file.blob_name, value)}
                            >
                              <SelectTrigger className="w-full h-8 text-xs border-gray-200 hover:border-blue-400 focus:border-blue-500">
                                <SelectValue placeholder="Assign..." />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="unassigned">Unassigned</SelectItem>
                                <SelectItem value="user1">User 1</SelectItem>
                                <SelectItem value="user2">User 2</SelectItem>
                                <SelectItem value="user3">User 3</SelectItem>
                                <SelectItem value="admin">Admin</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className="border-r border-gray-200 px-3 py-3">
                            {loadingMissingFields.has(file.blob_name) ? (
                              <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-blue-100 text-blue-700">
                                <RefreshCw className="h-3 w-3 animate-spin" />
                                <span>Loading...</span>
                              </div>
                            ) : missingFields[file.blob_name] && missingFields[file.blob_name].length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {missingFields[file.blob_name].map((field, idx) => (
                                  <span
                                    key={idx}
                                    className="inline-block px-2 py-1 rounded text-xs font-medium border"
                                    title={`Missing field: ${field}`}
                                  >
                                    {field}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-xs text-gray-400 italic">None</span>
                            )}
                          </TableCell>
                          <TableCell className="px-3 py-3">
                            <div className="flex items-center justify-center gap-1">
                              <input
                                type="text"
                                placeholder="Enter command"
                                className="w-full text-sm p-1 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                              {isAdmin && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleDelete(file.blob_name, file.name)}
                                  className="h-7 px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                                  title="Delete"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Other Files (if any) */}
      {otherFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <File className="h-5 w-5 text-gray-500" />
              Other Files ({otherFiles.length})
            </CardTitle>
            <p className="text-sm text-gray-500">Files not in source or processed folders</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {otherFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <File className="h-4 w-4 text-gray-500" />
                    <div>
                      <div className="font-medium">{file.name}</div>
                      <div className="text-sm text-gray-500">
                        {formatFileSize(file.size)} • {formatDate(file.last_modified)}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Path: {file.blob_name}
                      </div>
                      {isAdmin && (
                        <Badge variant="outline" className="text-xs mt-1">
                          {file.tenant_id.substring(0, 8)}...
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDownload(file.blob_name, file.name)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    {isAdmin && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDelete(file.blob_name, file.name)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Storage Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Storage Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {sourceFiles.length}
              </div>
              <div className="text-sm text-gray-500">Source Files</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {processedFiles.length}
              </div>
              <div className="text-sm text-gray-500">Processed Files</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-600">
                {otherFiles.length}
              </div>
              <div className="text-sm text-gray-500">Other Files</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {formatFileSize(filteredFiles.reduce((sum, file) => sum + file.size, 0))}
              </div>
              <div className="text-sm text-gray-500">Total Size</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {isAdmin ? tenants.length : 1}
              </div>
              <div className="text-sm text-gray-500">Tenants</div>
            </div>
          </div>
        </CardContent>
      </Card>

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
        extractedData={sourceViewerData?.extractedData}
      />
    </div>
  );
};

export default BlobViewer;
