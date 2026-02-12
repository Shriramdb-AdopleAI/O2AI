// src/components/FilesTable.jsx
import React, { useState, useEffect, useMemo } from 'react';
import { Search, Download, FileText, RefreshCw, ChevronLeft, ChevronRight, ChevronUp, ChevronDown } from 'lucide-react';
import authService from '../../services/authService';
import SourceFileViewer from '../SourceFileViewer';

const FilesTable = ({
  isAdmin = false,
  selectedFromDate,
  selectedToDate,
  onKpiDataChange,
  onStatusBreakdownChange,
  onConfidenceBreakdownChange,
  onLowConfidenceFilesChange,
  onJumpToLowConfidenceRef,
  onFilesDataChange
}) => {
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
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [assignedUserFilter, setAssignedUserFilter] = useState('all');
  const [dateRangeFilter, setDateRangeFilter] = useState('all');
  const [updateTypeFilter, setUpdateTypeFilter] = useState('all');
  const [highlightLowConfidence, setHighlightLowConfidence] = useState(false);
  const [confidenceScores, setConfidenceScores] = useState({});
  const [loadingConfidenceScores, setLoadingConfidenceScores] = useState(new Set());
  const [assignedUsers, setAssignedUsers] = useState({});
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [availableUsers, setAvailableUsers] = useState([]); // List of users for dropdown
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [missingFields, setMissingFields] = useState({}); // { blobName: ['field1', 'field2', ...] }
  const [loadingMissingFields, setLoadingMissingFields] = useState(new Set());
  const [remarks, setRemarks] = useState({}); // { blobName: 'remark text' }
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'desc' });
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [sourceViewerData, setSourceViewerData] = useState(null);

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

  // Load remarks from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('fileRemarks');
      if (stored) {
        const parsed = JSON.parse(stored);
        setRemarks(parsed);
      }
    } catch (error) {
      console.error('Error loading remarks from localStorage:', error);
    }
  }, []);

  useEffect(() => {
    loadData();
    loadUsers();
  }, [selectedTenant]);

  // Load available users for dropdown (admin only)
  // Load available users for dropdown
  const loadUsers = async () => {
    try {
      setLoadingUsers(true);
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
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load users' }));
        console.error('Error loading users:', response.status, errorData);
        setAvailableUsers([]);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setAvailableUsers([]);
    } finally {
      setLoadingUsers(false);
    }
  };

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

  // Fetch confidence score for a file
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

  // Clean file name (similar to BlobViewer)
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

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  // Determine status based on confidence and folder
  const getFileStatus = (file, confidence) => {
    if (!file.blob_name) return 'Error';

    const isAbove95 = file.blob_name.includes('Above-95%');
    const isReview = file.blob_name.includes('needs to be reviewed');
    const isProcessed = file.blob_name.includes('/processed/') || file.blob_name.includes('\\processed\\');

    if (!isProcessed) return 'In Progress';

    if (isAbove95 && confidence && confidence >= 95) {
      return 'Completed';
    } else if (isReview || (confidence && confidence < 95)) {
      return 'Review Needed';
    } else if (confidence === null || confidence === undefined) {
      return 'In Progress';
    } else {
      return 'Error';
    }
  };

  // Get user color based on assigned user
  const getUserColor = (user) => {
    const colors = {
      'A': 'bg-blue-600',
      'B': 'bg-blue-600',
      'C': 'bg-purple-600',
      'D': 'bg-green-600',
      'user1': 'bg-blue-600',
      'user2': 'bg-purple-600',
      'user3': 'bg-green-600',
      'admin': 'bg-red-600',
    };
    return colors[user] || 'bg-gray-600';
  };

  // Get user initial
  const getUserInitial = (user) => {
    if (!user || user === 'unassigned') return '?';
    if (user.length === 1) return user.toUpperCase();
    if (user.startsWith('user')) return user.slice(-1).toUpperCase();
    return user.charAt(0).toUpperCase();
  };

  // Get user display name for dropdown (Initial - Full Name)
  const getUserDisplayName = (user) => {
    if (!user) return 'Unassigned';
    const username = user.username || user.name || user.id || '';
    const initial = getUserInitial(username);
    return `${initial} - ${username}`;
  };

  // Handle download
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

  // Handle download all JSON files
  const handleDownloadAll = async () => {
    if (filteredFiles.length === 0) {
      setError('No files to download');
      return;
    }

    setError(null);
    const headers = authService.getAuthHeaders();
    const DOWNLOAD_DELAY = 300; // Delay between downloads to avoid browser blocking

    try {
      for (let i = 0; i < filteredFiles.length; i++) {
        const file = filteredFiles[i];
        try {
          const response = await fetch(
            `${API_BASE_URL}/api/v1/blob/download/${encodeURIComponent(file.blobName)}`,
            { headers }
          );

          if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            // Ensure filename ends with .json
            const filename = file.fileName.endsWith('.json') ? file.fileName : `${file.fileName}.json`;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
          }

          // Add delay between downloads (except for the last one)
          if (i < filteredFiles.length - 1) {
            await new Promise(resolve => setTimeout(resolve, DOWNLOAD_DELAY));
          }
        } catch (err) {
          console.error(`Failed to download ${file.fileName}:`, err);
        }
      }
    } catch (err) {
      setError(`Download failed: ${err.message}`);
    }
  };

  // Handle assign user
  const handleAssignUser = (blobName, userId) => {
    setAssignedUsers(prev => {
      const updated = {
        ...prev,
        [blobName]: userId
      };
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

  // Handle remarks change
  const handleRemarksChange = (blobName, remarkText) => {
    setRemarks(prev => {
      const updated = {
        ...prev,
        [blobName]: remarkText
      };
      // Save to localStorage
      try {
        localStorage.setItem('fileRemarks', JSON.stringify(updated));
      } catch (error) {
        console.error('Error saving remarks to localStorage:', error);
      }
      return updated;
    });
  };

  const handleViewFile = async (blobName, filename) => {
    try {
      const headers = authService.getAuthHeaders();

      // First, try to resolve the original source blob path
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
        console.log('Could not get source file path:', sourceErr);
        alert('Source file information not available. Please ensure the file was processed correctly.');
        return;
      }

      // Fetch the processed JSON to get OCR/extracted data for highlighting
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
          ocrData = jsonData.raw_ocr_results || jsonData.text_blocks || jsonData.positioning_data || null;
          rawOcrText = jsonData.raw_ocr_text || null;
        }
      } catch (processedErr) {
        console.log('Could not fetch processed data:', processedErr);
      }

      if (sourceBlobPath) {
        setSourceViewerData({
          sourceBlobPath,
          filename,
          highlightText: null,
          ocrData,
          rawOcrText,
          extractedData
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

  // Helper: parse MM/DD/YYYY (USA format) to Date
  const parseSelectedDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      // Handle MM/DD/YYYY format (USA format)
      if (dateStr.includes('/')) {
        const [month, day, year] = dateStr.split('/').map(Number);
        return new Date(year, month - 1, day);
      }
      // Backward compatibility: Handle DD-MM-YYYY format
      else if (dateStr.includes('-')) {
        const [day, month, year] = dateStr.split('-').map(Number);
        return new Date(year, month - 1, day);
      }
      return null;
    } catch (e) {
      return null;
    }
  };

  // Get processed files only
  const processedFiles = useMemo(() => {
    return files.filter(file => {
      const isProcessed = file.blob_name && (
        file.blob_name.includes('/processed/') ||
        file.blob_name.includes('\\processed\\') ||
        file.blob_name.startsWith('processed/')
      );

      // Filter by tenant if selected
      if (isAdmin && selectedTenant) {
        if (!isProcessed || file.tenant_id !== selectedTenant) return false;
      } else if (!isProcessed) {
        return false;
      }

      // Filter by selected from/to date (check last_modified)
      if ((selectedFromDate || selectedToDate) && file.last_modified) {
        const fileDate = new Date(file.last_modified);

        // Get file date in EST timezone (date only, no time) - format as MM/DD/YYYY
        const fileDateESTStr = fileDate.toLocaleDateString('en-US', {
          timeZone: 'America/New_York',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        });

        // Parse selected dates (already in MM/DD/YYYY format)
        const from = selectedFromDate ? selectedFromDate : null;
        const to = selectedToDate ? selectedToDate : null;

        // Compare date strings directly (MM/DD/YYYY format)
        if (from) {
          // Compare as strings: "MM/DD/YYYY" format
          const fromParts = from.split('/').map(Number);
          const fileParts = fileDateESTStr.split('/').map(Number);

          // Compare: year, then month, then day
          if (fileParts[2] < fromParts[2] ||
            (fileParts[2] === fromParts[2] && fileParts[0] < fromParts[0]) ||
            (fileParts[2] === fromParts[2] && fileParts[0] === fromParts[0] && fileParts[1] < fromParts[1])) {
            return false;
          }
        }

        if (to) {
          // Compare as strings: "MM/DD/YYYY" format
          const toParts = to.split('/').map(Number);
          const fileParts = fileDateESTStr.split('/').map(Number);

          // Compare: year, then month, then day
          if (fileParts[2] > toParts[2] ||
            (fileParts[2] === toParts[2] && fileParts[0] > toParts[0]) ||
            (fileParts[2] === toParts[2] && fileParts[0] === toParts[0] && fileParts[1] > toParts[1])) {
            return false;
          }
        }
      }

      return true;
    });
  }, [files, isAdmin, selectedTenant, selectedFromDate, selectedToDate]);

  // Fetch confidence scores for processed files
  useEffect(() => {
    const fetchAllConfidenceScores = async () => {
      const filesToFetch = processedFiles.filter(file =>
        !confidenceScores[file.blob_name] && !loadingConfidenceScores.has(file.blob_name)
      );

      if (filesToFetch.length === 0) return;

      // Batch fetch: Process files in smaller batches
      const BATCH_SIZE = 5;
      const BATCH_DELAY = 300;

      for (let i = 0; i < filesToFetch.length; i += BATCH_SIZE) {
        const batch = filesToFetch.slice(i, i + BATCH_SIZE);

        await Promise.all(
          batch.map(file => fetchConfidenceScore(file.blob_name))
        );

        if (i + BATCH_SIZE < filesToFetch.length) {
          await new Promise(resolve => setTimeout(resolve, BATCH_DELAY));
        }
      }
    };

    if (processedFiles.length > 0) {
      const timeoutId = setTimeout(() => {
        fetchAllConfidenceScores();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processedFiles.length]);

  // Fetch missing fields for processed files
  useEffect(() => {
    const fetchAllMissingFields = async () => {
      const filesToFetch = processedFiles.filter(file =>
        missingFields[file.blob_name] === undefined && !loadingMissingFields.has(file.blob_name)
      );

      if (filesToFetch.length === 0) return;

      // Batch fetch: Process files in smaller batches
      const BATCH_SIZE = 5;
      const BATCH_DELAY = 300;

      for (let i = 0; i < filesToFetch.length; i += BATCH_SIZE) {
        const batch = filesToFetch.slice(i, i + BATCH_SIZE);

        await Promise.all(
          batch.map(file => checkMissingFields(file.blob_name))
        );

        if (i + BATCH_SIZE < filesToFetch.length) {
          await new Promise(resolve => setTimeout(resolve, BATCH_DELAY));
        }
      }
    };

    if (processedFiles.length > 0) {
      const timeoutId = setTimeout(() => {
        fetchAllMissingFields();
      }, 1000); // Start after confidence scores

      return () => clearTimeout(timeoutId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processedFiles.length]);

  // Transform files to table format
  const transformedFiles = useMemo(() => {
    return processedFiles.map(file => {
      const confidence = confidenceScores[file.blob_name];
      const status = getFileStatus(file, confidence);
      const assignedUser = assignedUsers[file.blob_name] || 'unassigned';
      const userInitial = getUserInitial(assignedUser);
      const userColor = getUserColor(assignedUser);
      const missingFieldsList = missingFields[file.blob_name] || [];
      const remarksText = remarks[file.blob_name] || '';

      return {
        blobName: file.blob_name,
        fileName: cleanFileName(file.name),
        status: status,
        accuracy: confidence !== null && confidence !== undefined ? `${confidence.toFixed(0)}%` : '-',
        assignedUser: userInitial,
        userColor: userColor,
        updatedDate: formatDate(file.last_modified),
        lastModified: file.last_modified, // Keep original date for filtering
        lastUpdate: assignedUser !== 'unassigned' ? 'User Updated' : 'Auto-updated',
        confidence: confidence,
        assignedUserValue: assignedUser,
        missingFields: missingFieldsList,
        remarks: remarksText,
      };
    });
  }, [processedFiles, confidenceScores, assignedUsers, missingFields, remarks]);

  // Function to jump to low-confidence files
  const jumpToLowConfidence = () => {
    // Clear other filters and set to show low-confidence files
    setSearchTerm('');
    setStatusFilter('all');
    setAssignedUserFilter('all');
    setDateRangeFilter('all');
    setUpdateTypeFilter('all');
    setHighlightLowConfidence(true);

    // Scroll to table
    setTimeout(() => {
      const tableElement = document.querySelector('[data-table-section]');
      if (tableElement) {
        tableElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 100);
  };

  // Expose jump function via ref
  useEffect(() => {
    if (onJumpToLowConfidenceRef) {
      onJumpToLowConfidenceRef.current = jumpToLowConfidence;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onJumpToLowConfidenceRef]);

  // Filter files based on search and filters
  const filteredFiles = transformedFiles.filter(file => {
    // Search filter
    const matchesSearch = file.fileName.toLowerCase().includes(searchTerm.toLowerCase());

    // Status filter
    const matchesStatus = statusFilter === 'all' || file.status === statusFilter;

    // Assigned user filter
    const matchesUser = assignedUserFilter === 'all' || file.assignedUserValue === assignedUserFilter;

    // Date range filter
    let matchesDate = true;
    if (dateRangeFilter !== 'all' && file.lastModified) {
      const fileDate = new Date(file.lastModified);
      const now = new Date();
      const daysDiff = Math.floor((now - fileDate) / (1000 * 60 * 60 * 24));

      if (dateRangeFilter === '7days' && daysDiff > 7) matchesDate = false;
      if (dateRangeFilter === '30days' && daysDiff > 30) matchesDate = false;
    }

    // Update type filter (User Updated vs Auto-updated)
    const matchesUpdateType = updateTypeFilter === 'all' ||
      (updateTypeFilter === 'user' && file.lastUpdate === 'User Updated') ||
      (updateTypeFilter === 'auto' && file.lastUpdate === 'Auto-updated');

    // Low-confidence filter (when highlightLowConfidence is true) - Red category (<90%)
    const matchesLowConfidence = !highlightLowConfidence ||
      (file.confidence !== null && file.confidence !== undefined && file.confidence < 90);

    return matchesSearch && matchesStatus && matchesUser && matchesDate && matchesUpdateType && matchesLowConfidence;
  });

  const sortedFiles = useMemo(() => {
    if (!sortConfig.key) return filteredFiles;

    const sorted = [...filteredFiles].sort((a, b) => {
      let aVal;
      let bVal;

      if (sortConfig.key === 'accuracy') {
        aVal = typeof a.confidence === 'number' ? a.confidence : -Infinity;
        bVal = typeof b.confidence === 'number' ? b.confidence : -Infinity;
      } else if (sortConfig.key === 'updatedDate') {
        aVal = a.lastModified ? new Date(a.lastModified).getTime() : 0;
        bVal = b.lastModified ? new Date(b.lastModified).getTime() : 0;
      } else {
        aVal = 0;
        bVal = 0;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return a.fileName.localeCompare(b.fileName);
    });

    return sorted;
  }, [filteredFiles, sortConfig]);

  const handleSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        const nextDirection = prev.direction === 'asc' ? 'desc' : 'asc';
        return { key, direction: nextDirection };
      }
      return { key, direction: 'desc' };
    });
  };

  const SortIcon = ({ columnKey }) => {
    if (sortConfig.key !== columnKey) {
      return <span className="inline-flex items-center text-gray-300 ml-1 text-xs">↕</span>;
    }
    return sortConfig.direction === 'asc' ? (
      <ChevronUp className="w-3 h-3 inline ml-1 text-gray-600" />
    ) : (
      <ChevronDown className="w-3 h-3 inline ml-1 text-gray-600" />
    );
  };

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter, assignedUserFilter, dateRangeFilter, updateTypeFilter, highlightLowConfidence, selectedFromDate, selectedToDate]);

  // Calculate pagination
  const totalPages = Math.ceil(sortedFiles.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedFiles = sortedFiles.slice(startIndex, endIndex);

  // Calculate KPI metrics and notify parent
  useEffect(() => {
    if (onKpiDataChange && transformedFiles.length > 0) {
      // Calculate total files
      const totalFiles = transformedFiles.length;

      // Calculate completed files
      const completedFiles = transformedFiles.filter(file => file.status === 'Completed').length;

      // Calculate pending files (In Progress)
      const pendingFiles = transformedFiles.filter(file => file.status === 'In Progress').length;

      // Calculate scanning accuracy (average of all confidence scores)
      const filesWithConfidence = transformedFiles.filter(file =>
        file.confidence !== null && file.confidence !== undefined
      );
      let scanningAccuracy = '0%';
      if (filesWithConfidence.length > 0) {
        const totalConfidence = filesWithConfidence.reduce((sum, file) => sum + file.confidence, 0);
        const averageConfidence = totalConfidence / filesWithConfidence.length;
        scanningAccuracy = `${averageConfidence.toFixed(1)}%`;
      }

      // Calculate last updated (most recent lastModified)
      let lastUpdated = 'N/A';
      let lastUpdatedTime = 'N/A';
      const filesWithDates = transformedFiles
        .filter(file => file.lastModified)
        .sort((a, b) => new Date(b.lastModified) - new Date(a.lastModified));

      if (filesWithDates.length > 0) {
        const mostRecent = new Date(filesWithDates[0].lastModified);
        lastUpdated = mostRecent.toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        });
        lastUpdatedTime = mostRecent.toLocaleTimeString('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true
        });
      }

      onKpiDataChange({
        totalFiles,
        completedFiles,
        pendingFiles,
        scanningAccuracy,
        lastUpdated,
        lastUpdatedTime
      });

      // Calculate status breakdown data
      if (onStatusBreakdownChange) {
        const successfulScans = transformedFiles.filter(file => file.status === 'Completed').length;
        const failedErrorFiles = transformedFiles.filter(file => file.status === 'Error').length;
        const manualReview = transformedFiles.filter(file => file.status === 'Review Needed').length;

        onStatusBreakdownChange([
          { label: 'Successful Scans', value: successfulScans, total: totalFiles, color: 'blue' },
          { label: 'Failed / Error Files', value: failedErrorFiles, total: totalFiles, color: 'red' },
          { label: 'Manual Review', value: manualReview, total: totalFiles, color: 'orange' },
        ]);
      }

      // Calculate confidence breakdown data
      if (onConfidenceBreakdownChange) {
        const green = transformedFiles.filter(file =>
          file.confidence !== null && file.confidence !== undefined && file.confidence >= 95
        ).length;
        const amber = transformedFiles.filter(file =>
          file.confidence !== null && file.confidence !== undefined && file.confidence >= 90 && file.confidence < 95
        ).length;
        const red = transformedFiles.filter(file =>
          file.confidence !== null && file.confidence !== undefined && file.confidence < 90
        ).length;

        onConfidenceBreakdownChange([
          { label: 'Green (≥95%)', value: green, color: 'green' },
          { label: 'Amber (90-94.9%)', value: amber, color: 'orange' },
          { label: 'Red (<89.9%)', value: red, color: 'red' },
        ]);
      }

      // Calculate low-confidence files (accuracy below 90% - Red category)
      if (onLowConfidenceFilesChange) {
        const lowConfidenceFilesList = transformedFiles
          .filter(file =>
            file.confidence !== null &&
            file.confidence !== undefined &&
            file.confidence < 90
          )
          .map(file => ({
            fileName: file.fileName,
            accuracy: file.accuracy,
            confidence: file.confidence
          }));
        onLowConfidenceFilesChange(lowConfidenceFilesList);
      }
    } else if (onKpiDataChange) {
      // Reset to defaults when no data
      onKpiDataChange({
        totalFiles: 0,
        completedFiles: 0,
        pendingFiles: 0,
        scanningAccuracy: '0%',
        lastUpdated: 'N/A',
        lastUpdatedTime: 'N/A'
      });

      // Reset status breakdown when no data
      if (onStatusBreakdownChange) {
        onStatusBreakdownChange([
          { label: 'Successful Scans', value: 0, total: 0, color: 'blue' },
          { label: 'Failed / Error Files', value: 0, total: 0, color: 'red' },
          { label: 'Manual Review', value: 0, total: 0, color: 'orange' },
        ]);
      }

      // Reset confidence breakdown when no data
      if (onConfidenceBreakdownChange) {
        onConfidenceBreakdownChange([
          { label: 'Green (≥95%)', value: 0, color: 'green' },
          { label: 'Amber (90-94.9%)', value: 0, color: 'orange' },
          { label: 'Red (<89.9%)', value: 0, color: 'red' },
        ]);
      }

      // Reset low-confidence files when no data
      if (onLowConfidenceFilesChange) {
        onLowConfidenceFilesChange([]);
      }
    }

    // Expose file data to parent for RecentActivities
    if (onFilesDataChange) {
      onFilesDataChange(transformedFiles);
    }
  }, [transformedFiles, onKpiDataChange, onStatusBreakdownChange, onConfidenceBreakdownChange, onLowConfidenceFilesChange, onFilesDataChange]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'Completed': return 'text-green-600';
      case 'In Progress': return 'text-blue-600';
      case 'Error': return 'text-red-600';
      case 'Review Needed': return 'text-orange-600';
      default: return 'text-gray-600';
    }
  };

  // Reset highlight when filters change manually
  useEffect(() => {
    if (highlightLowConfidence && (searchTerm || statusFilter !== 'all' || assignedUserFilter !== 'all' || dateRangeFilter !== 'all' || updateTypeFilter !== 'all')) {
      setHighlightLowConfidence(false);
    }
  }, [searchTerm, statusFilter, assignedUserFilter, dateRangeFilter, updateTypeFilter, highlightLowConfidence]);

  return (
    <div className="bg-white rounded-2xl shadow-sm overflow-hidden" data-table-section>
      {/* Header: Search + Filters + Download */}
      <div className="p-4 sm:p-6 border-b">
        <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 flex-1 min-w-0">
            {/* Search Input */}
            <div className="relative w-full sm:w-auto flex-shrink-0">
              <Search className="absolute left-3 top-3.5 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 sm:py-3 border border-gray-300 rounded-lg w-full sm:w-[350px] focus:outline-none focus:ring-2 focus:ring-blue-500 text-[14px]"
              />
            </div>

            {/* Filter Dropdowns */}
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 flex-wrap min-w-0">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 sm:py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-[14px] w-full sm:w-auto"
              >
                <option value="all">Status</option>
                <option value="Completed">Completed</option>
                <option value="In Progress">In Progress</option>
                <option value="Error">Error</option>
                <option value="Review Needed">Review Needed</option>
              </select>

              <select
                value={assignedUserFilter}
                onChange={(e) => setAssignedUserFilter(e.target.value)}
                className="px-4 py-2 sm:py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-[14px] w-full sm:w-auto"
              >
                <option value="all">Assigned User</option>
                <option value="unassigned">Unassigned</option>
                {availableUsers.map((user) => (
                  <option key={user.id || user.username} value={user.id || user.username}>
                    {getUserDisplayName(user)}
                  </option>
                ))}
              </select>

              <select
                value={dateRangeFilter}
                onChange={(e) => setDateRangeFilter(e.target.value)}
                className="px-4 py-2 sm:py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-[14px] w-full sm:w-auto"
              >
                <option value="all">Date Range</option>
                <option value="7days">Last 7 days</option>
                <option value="30days">Last 30 days</option>
              </select>

              <select
                value={updateTypeFilter}
                onChange={(e) => setUpdateTypeFilter(e.target.value)}
                className="px-4 py-2 sm:py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-[14px] w-full sm:w-auto"
              >
                <option value="all">Update Type</option>
                <option value="user">User Updated</option>
                <option value="auto">Auto-updated</option>
              </select>
            </div>
          </div>

          {/* Download Button */}
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={handleDownloadAll}
              disabled={loading || filteredFiles.length === 0}
              className="bg-blue-600 text-white px-5 py-3 rounded-lg flex items-center gap-2 hover:bg-blue-700 transition disabled:opacity-50 whitespace-nowrap flex-shrink-0"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-3 sm:p-4 bg-red-50 border-b border-red-200">
          <p className="text-red-600 text-xs sm:text-sm">{error}</p>
        </div>
      )}

      {/* Tenant Filter (Admin only) */}
      {isAdmin && tenants.length > 0 && (
        <div className="p-3 sm:p-4 border-b bg-gray-50">
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setSelectedTenant(null)}
              className={`px-3 py-1.5 rounded text-xs sm:text-sm ${selectedTenant === null
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-100'
                }`}
            >
              All Tenants
            </button>
            {tenants.map(tenant => (
              <button
                key={tenant}
                onClick={() => setSelectedTenant(tenant)}
                className={`px-3 py-1.5 rounded text-xs sm:text-sm ${selectedTenant === tenant
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-100'
                  }`}
              >
                {tenant.substring(0, 8)}...
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Table - Desktop View */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full" style={{ tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '18%' }} />
            <col style={{ width: '9%' }} />
            <col style={{ width: '9%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '16%' }} />
            <col style={{ width: '15%' }} />
          </colgroup>
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">File Name</th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">Status</th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">
                <button
                  type="button"
                  onClick={() => handleSort('accuracy')}
                  className="flex items-center justify-center gap-1 mx-auto"
                >
                  Accuracy %
                  <SortIcon columnKey="accuracy" />
                </button>
              </th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">Assigned User</th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">
                <button
                  type="button"
                  onClick={() => handleSort('updatedDate')}
                  className="flex items-center justify-center gap-1 mx-auto"
                >
                  Updated Date
                  <SortIcon columnKey="updatedDate" />
                </button>
              </th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">Last Update</th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">Missing Fields</th>
              <th className="text-center py-2 px-3 font-medium text-gray-700 text-xs align-middle">Remarks</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="8" className="text-center py-10 text-gray-500 align-middle">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Loading files...</span>
                  </div>
                </td>
              </tr>
            ) : filteredFiles.length === 0 ? (
              <tr>
                <td colSpan="8" className="text-center py-10 text-gray-500 align-middle">
                  No files found matching your search.
                </td>
              </tr>
            ) : (
              paginatedFiles.map((file, index) => {
                const isLowConfidence = file.confidence !== null && file.confidence !== undefined && file.confidence < 90;
                return (
                  <tr
                    key={`${file.blobName}-${index}`}
                    className={`border-b hover:bg-gray-50 transition ${isLowConfidence && highlightLowConfidence ? 'bg-yellow-50 border-yellow-200' : ''}`}
                  >
                    <td className="py-2 px-3 align-middle">
                      <button
                        type="button"
                        onClick={() => handleViewFile(file.blobName, file.fileName)}
                        className="w-full text-left hover:text-blue-600 focus:outline-none"
                      >
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                          <span className="font-medium text-xs truncate">{file.fileName}</span>
                        </div>
                      </button>
                    </td>
                    <td className="py-2 px-3 align-middle">
                      <span className={`font-medium text-xs ${getStatusColor(file.status)}`}>
                        {file.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-gray-700 text-xs align-middle text-center">
                      {loadingConfidenceScores.has(file.blobName) ? (
                        <span className="text-gray-400 text-xs">Loading...</span>
                      ) : (
                        file.accuracy
                      )}
                    </td>
                    <td className="py-2 px-3 align-middle">
                      <select
                        value={file.assignedUserValue || 'unassigned'}
                        onChange={(e) => handleAssignUser(file.blobName, e.target.value)}
                        className="px-2 py-1 border border-gray-300 rounded-lg bg-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 w-full"
                      >
                        <option value="unassigned">Unassigned</option>
                        {availableUsers.map((user) => (
                          <option key={user.id || user.username} value={user.id || user.username}>
                            {getUserDisplayName(user)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 px-3 text-gray-700 text-xs align-middle text-center">{file.updatedDate}</td>
                    <td className="py-2 px-3 text-gray-500 text-xs align-middle text-center">{file.lastUpdate}</td>
                    <td className="py-2 px-3 align-middle">
                      {loadingMissingFields.has(file.blobName) ? (
                        <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 text-gray-600">
                          <RefreshCw className="h-3 w-3 animate-spin" />
                          <span>Loading...</span>
                        </div>
                      ) : missingFields[file.blobName] && missingFields[file.blobName].length > 0 ? (
                        <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
                          {missingFields[file.blobName].map((field, idx) => (
                            <span
                              key={idx}
                              className="inline-block px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 border border-gray-300"
                              title={`Missing field: ${field}`}
                            >
                              {field}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400 italic">None</span>
                      )}
                    </td>
                    <td className="py-2 px-3 align-middle">
                      <textarea
                        rows={2}
                        placeholder="Add remarks..."
                        value={remarks[file.blobName] || ''}
                        onChange={(e) => handleRemarksChange(file.blobName, e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <div className="flex items-center justify-center gap-2">
              <RefreshCw className="w-5 h-5 animate-spin" />
              <span>Loading files...</span>
            </div>
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No files found matching your search.
          </div>
        ) : (
          <div className="divide-y">
            {paginatedFiles.map((file, index) => {
              const isLowConfidence = file.confidence !== null && file.confidence !== undefined && file.confidence < 90;
              return (
                <div
                  key={`${file.blobName}-${index}`}
                  className={`p-4 hover:bg-gray-50 transition ${isLowConfidence && highlightLowConfidence ? 'bg-yellow-50 border-l-4 border-yellow-400' : ''}`}
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                      <span className="font-medium text-sm truncate">{file.fileName}</span>
                    </div>
                    <span className={`font-medium text-xs px-2 py-1 rounded ${getStatusColor(file.status)} bg-opacity-10 flex-shrink-0`}>
                      {file.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-500 text-xs">Accuracy:</span>
                      <div className="font-medium text-gray-700">
                        {loadingConfidenceScores.has(file.blobName) ? (
                          <span className="text-gray-400 text-xs">Loading...</span>
                        ) : (
                          file.accuracy
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-gray-500 text-xs">Assigned User:</span>
                      <select
                        value={file.assignedUserValue || 'unassigned'}
                        onChange={(e) => handleAssignUser(file.blobName, e.target.value)}
                        className="mt-1 px-3 py-2 border border-gray-300 rounded-lg bg-white text-xs w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="unassigned">Unassigned</option>
                        {availableUsers.map((user) => (
                          <option key={user.id || user.username} value={user.id || user.username}>
                            {getUserDisplayName(user)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <span className="text-gray-500 text-xs">Updated Date:</span>
                      <div className="font-medium text-gray-700 text-xs">{file.updatedDate}</div>
                    </div>

                    <div>
                      <span className="text-gray-500 text-xs">Last Update:</span>
                      <div className="text-gray-600 text-xs">{file.lastUpdate}</div>
                    </div>

                    <div className="col-span-2">
                      <span className="text-gray-500 text-xs">Missing Fields:</span>
                      <div className="mt-1">
                        {loadingMissingFields.has(file.blobName) ? (
                          <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 text-gray-600">
                            <RefreshCw className="h-3 w-3 animate-spin" />
                            <span>Loading...</span>
                          </div>
                        ) : missingFields[file.blobName] && missingFields[file.blobName].length > 0 ? (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {missingFields[file.blobName].map((field, idx) => (
                              <span
                                key={idx}
                                className="inline-block px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 border border-gray-300"
                                title={`Missing field: ${field}`}
                              >
                                {field}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400 italic">None</span>
                        )}
                      </div>
                    </div>

                    <div className="col-span-2">
                      <span className="text-gray-500 text-xs">Remarks:</span>
                      <textarea
                        rows={3}
                        placeholder="Add remarks..."
                        value={remarks[file.blobName] || ''}
                        onChange={(e) => handleRemarksChange(file.blobName, e.target.value)}
                        className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {filteredFiles.length > 0 && (
        <div className="p-4 sm:p-6 border-t bg-gray-50">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Items per page selector */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700">Show:</span>
              <select
                value={itemsPerPage}
                onChange={(e) => {
                  setItemsPerPage(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="px-3 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              >
                <option value="10">10</option>
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
              <span className="text-sm text-gray-700">per page</span>
            </div>

            {/* Page info */}
            <div className="text-sm text-gray-700">
              Showing {startIndex + 1} to {Math.min(endIndex, filteredFiles.length)} of {filteredFiles.length} files
            </div>

            {/* Pagination controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                aria-label="Previous page"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>

              {/* Page numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }

                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`px-3 py-1.5 text-sm rounded-lg transition ${currentPage === pageNum
                          ? 'bg-blue-600 text-white'
                          : 'border border-gray-300 hover:bg-gray-100 text-gray-700'
                        }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>

              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                aria-label="Next page"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}
      <SourceFileViewer
        isOpen={sourceViewerOpen}
        onClose={() => {
          setSourceViewerOpen(false);
          setSourceViewerData(null);
        }}
        sourceBlobPath={sourceViewerData?.sourceBlobPath}
        highlightText={sourceViewerData?.highlightText || null}
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

export default FilesTable;