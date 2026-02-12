// src/App.jsx
import React, { useState, useEffect } from 'react';
import {
  FileText, Zap, CheckCircle, Brain, Table, FileSpreadsheet, PieChart,
  Menu, X, Upload, BarChart3, User, LogOut, HardDrive, MapPin, Home
} from 'lucide-react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import EnhancedFileUpload from './components/EnhancedFileUpload';
import EnhancedOCRResults from './components/EnhancedOCRResults';
import BlobViewer from './components/BlobViewer';
import TemplateManager from './components/TemplateManager';
import TemplateMappedResults from './components/TemplateMappedResults';
import Login from './components/Login';
import { useMsal } from '@azure/msal-react';
import AdminDashboard from './components/AdminDashboard';
import authService from './services/authService';
import Header from './components/Header';
import Welcome from './components/Welcome';
import Footer from './components/Footer';
import ProcessingTab from './components/ProcessingTab';
import ResultsTab from './components/ResultsTab';
import Sidebar from './components/Sidebar';
import { OCRProcessing, InsightsIcon } from './components/icon';
import FaxAutomationInsights from './components/insights/FaxAutomationInsights';
import { initiateEpicLogin, handleEpicCallback } from './services/epicAuthConfig';

function App() {
  const [activeTab, setActiveTab] = useState('processing');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [files, setFiles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [enhancedResults, setEnhancedResults] = useState(null);
  const [resultsHistory, setResultsHistory] = useState([]);
  const [currentFile, setCurrentFile] = useState('');
  const [progress, setProgress] = useState(0);
  const [errors, setErrors] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [tenantId, setTenantId] = useState(null);
  const [settings, setSettings] = useState({
    applyPreprocessing: true,
    enhanceQuality: true,
    provider: 'azure_computer_vision'
  });
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [mappedEditingValues, setMappedEditingValues] = useState({});
  const [isEditingMapped, setIsEditingMapped] = useState(false);
  const [lastTemplateMappingMeta, setLastTemplateMappingMeta] = useState(null);

  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  // Welcome screen state – persists across sessions
  const [hasSeenWelcome, setHasSeenWelcome] = useState(() => {
    return localStorage.getItem('hasSeenWelcome') === 'true';
  });

  // Get API base URL - ensure HTTPS when page is served over HTTPS
  const getApiBaseUrl = () => {
    let apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8888';
    // If page is served over HTTPS, ensure API URL also uses HTTPS to avoid mixed content errors
    if (window.location.protocol === 'https:') {
      if (apiBaseUrl.startsWith('http://') && !apiBaseUrl.includes('localhost')) {
        apiBaseUrl = apiBaseUrl.replace('http://', 'https://');
      }
    }
    return apiBaseUrl;
  };
  const API_BASE_URL = getApiBaseUrl();

  // Load templates and history
  useEffect(() => {
    if (!isAuthenticated) return;

    const loadTemplates = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/templates`, {
          headers: authService.getAuthHeaders()
        });
        if (response.status === 401) {
          await authService.logout();
          setIsAuthenticated(false);
          setCurrentUser(null);
          setTenantId(null);
          return;
        }
        if (response.ok) {
          const data = await response.json();
          setTemplates(data.data || data.templates || []);
        }
      } catch (error) {
        console.error('Failed to load templates:', error);
      }
    };

    const loadHistory = async () => {
      if (!tenantId) return;
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
          headers: authService.getAuthHeaders()
        });
        if (response.status === 401) {
          await authService.logout();
          setIsAuthenticated(false);
          setCurrentUser(null);
          setTenantId(null);
          return;
        }
        if (response.ok) {
          const data = await response.json();
          setResultsHistory(data.history || []);
        }
      } catch (error) {
        console.error('Failed to load history:', error);
      }
    };

    loadTemplates();
    loadHistory();
  }, [isAuthenticated, tenantId]);

  // Reload templates on processing tab
  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'processing') return;

    const loadTemplates = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/templates`, {
          headers: authService.getAuthHeaders()
        });
        if (response.ok) {
          const data = await response.json();
          setTemplates(data.data || data.templates || []);
        }
      } catch (error) {
        console.error('Failed to reload templates:', error);
      }
    };

    loadTemplates();
  }, [activeTab, isAuthenticated]);

  // Reset isProcessing when results are cleared (e.g., "Upload Another File" clicked)
  useEffect(() => {
    if (enhancedResults === null) {
      setIsProcessing(false);
    }
  }, [enhancedResults]);

  // Clear results when switching away from processing tab
  useEffect(() => {
    if (activeTab !== 'processing' && enhancedResults !== null) {
      setEnhancedResults(null);
    }
  }, [activeTab]);

  const handleFilesChange = (newFiles) => {
    setFiles(newFiles);
    setEnhancedResults(null);
    setErrors([]);
  };

  const pollTaskStatus = async (taskId, isSingleFile) => {
    const maxAttempts = 120;
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}`, {
          headers: authService.getAuthHeaders()
        });
        const status = await response.json();

        if (status.state === 'SUCCESS') {
          setProgress(100);
          return status.result;
        } else if (status.state === 'FAILURE') {
          throw new Error(status.error || 'Task failed');
        } else if (status.state === 'PROCESSING') {
          setProgress(attempts * 100 / maxAttempts);
          await new Promise(resolve => setTimeout(resolve, 1000));
        } else {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      } catch (error) {
        console.error('Error polling task status:', error);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      attempts++;
    }

    throw new Error('Task timeout - processing took too long');
  };

  const pollBatchTaskStatus = async (taskIds) => {
    const maxAttempts = 240;
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/tasks/batch-status`, {
          method: 'POST',
          headers: { ...authService.getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify(taskIds)
        });
        const status = await response.json();

        const completedCount = status.summary.completed + status.summary.failed;
        setProgress((completedCount / taskIds.length) * 100);

        if (completedCount === taskIds.length) {
          return {
            status: 'completed',
            batch_info: status.summary,
            individual_results: status.tasks.map(t => t.result).filter(r => r)
          };
        } else {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      } catch (error) {
        console.error('Error polling batch status:', error);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      attempts++;
    }

    throw new Error('Batch task timeout - processing took too long');
  };

  const processFiles = async (formData) => {
    setIsProcessing(true);
    setProgress(0);
    setErrors([]);
    setCurrentFile('');

    try {
      const hasFile = formData.has('file');
      const hasFiles = formData.has('files');

      if (selectedTemplateId) {
        formData.append('template_id', selectedTemplateId);
      }

      const endpoint = hasFile
        ? `${API_BASE_URL}/api/v1/ocr/enhanced/process`
        : `${API_BASE_URL}/api/v1/ocr/enhanced/batch/process/async`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: authService.getAuthHeadersAuthOnly(),
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 413) {
          throw new Error(`File too large! The file exceeds the maximum upload size. Please use a smaller file or compress it.`);
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      let processedResult;
      if (result.task_id || result.individual_tasks) {
        if (result.task_id) {
          processedResult = await pollTaskStatus(result.task_id, hasFile);
        } else {
          processedResult = await pollBatchTaskStatus(result.individual_tasks.map(t => t.task_id));
        }
        setEnhancedResults(processedResult);
      } else {
        processedResult = result;
        setEnhancedResults(result);
      }

      if (processedResult?.template_info?.mapping_result) {
        setMappedEditingValues(processedResult.template_info.mapping_result.mapped_values || {});
        setIsEditingMapped(false);
        setLastTemplateMappingMeta({
          documentId: processedResult.template_info.mapping_result.document_id,
          filename: processedResult.file_info?.filename || 'Unknown',
          confidenceScores: processedResult.template_info.mapping_result.confidence_scores || {},
          unmappedFields: processedResult.template_info.mapping_result.unmapped_fields || [],
          processingTimestamp: processedResult.template_info.mapping_result.processing_timestamp
        });
      }

      const historyEntry = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        result: processedResult,
        filename: hasFile ? processedResult.file_info?.filename || 'Unknown' : 'Batch Processing',
        processing_type: hasFile ? 'single' : 'batch',
        tenant_id: tenantId
      };

      try {
        const saveResponse = await fetch(`${API_BASE_URL}/api/v1/history/save`, {
          method: 'POST',
          headers: authService.getAuthHeaders(),
          body: JSON.stringify(historyEntry),
        });

        if (saveResponse.ok) {
          const historyResponse = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
            headers: authService.getAuthHeaders()
          });
          if (historyResponse.ok) {
            const historyData = await historyResponse.json();
            setResultsHistory(historyData.history || []);
          }
        }
      } catch (error) {
        console.error('Failed to save to history:', error);
        setResultsHistory(prev => [historyEntry, ...prev]);
      }


      setProgress(100);
    } catch (error) {
      console.error('Processing error:', error);
      setErrors([error.message]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleMappedValueChange = (fieldKey, value) => {
    setMappedEditingValues(prev => ({ ...prev, [fieldKey]: value }));
  };

  const saveMappedEdits = async () => {
    try {
      if (!selectedTemplateId || !lastTemplateMappingMeta?.documentId) return;
      const response = await fetch(
        `${API_BASE_URL}/api/v1/templates/${selectedTemplateId}/mappings/${lastTemplateMappingMeta.documentId}`,
        {
          method: 'PUT',
          headers: {
            ...authService.getAuthHeaders(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(mappedEditingValues)
        }
      );
      if (!response.ok) throw new Error('Failed to save mapped edits');
      setEnhancedResults(prev => prev ? {
        ...prev,
        template_mapping: {
          ...prev.template_mapping,
          mapped_values: { ...mappedEditingValues }
        }
      } : prev);
      setIsEditingMapped(false);
    } catch (e) {
      console.error(e);
    }
  };

  const exportMappedExcel = async () => {
    try {
      if (!selectedTemplateId || !enhancedResults?.template_mapping) return;
      const mappingResults = [{
        document_id: lastTemplateMappingMeta?.documentId,
        filename: lastTemplateMappingMeta?.filename,
        mapped_values: mappedEditingValues,
        confidence_scores: lastTemplateMappingMeta?.confidenceScores || {},
        unmapped_fields: lastTemplateMappingMeta?.unmappedFields || [],
        processing_timestamp: lastTemplateMappingMeta?.processingTimestamp
      }];
      const response = await fetch(
        `${API_BASE_URL}/api/v1/templates/${selectedTemplateId}/export`,
        {
          method: 'POST',
          headers: {
            ...authService.getAuthHeaders(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(mappingResults)
        }
      );
      if (!response.ok) throw new Error('Failed to export Excel');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `mapped_${lastTemplateMappingMeta?.filename || 'document'}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    }
  };

  const exportToExcel = async (processedData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/ocr/export/excel/from-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          processed_data: processedData,
          include_raw_text: true,
          include_metadata: true
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${processedData.file_info?.filename || 'document'}_extracted.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Excel export error:', error);
      alert(`Excel export failed: ${error.message}`);
    }
  };

  const exportBatchToExcel = async (batchData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/ocr/export/excel/batch/from-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_data: batchData,
          include_raw_text: true,
          include_metadata: true
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_extracted_documents.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Batch Excel export error:', error);
      alert(`Batch Excel export failed: ${error.message}`);
    }
  };

  // Authentication
  const handleLogin = async (username, password) => {
    setIsLoading(true);
    setAuthError('');
    const result = await authService.login(username, password);
    if (result.success) {
      setCurrentUser(result.user);
      setTenantId(result.tenantId);
      setIsAuthenticated(true);
    } else {
      setAuthError(result.error);
    }
    setIsLoading(false);
  };

  const handleRegister = async (username, email, password) => {
    setIsLoading(true);
    setAuthError('');
    const result = await authService.register(username, email, password);
    if (result.success) {
      setCurrentUser(result.user);
      setTenantId(result.tenantId);
      setIsAuthenticated(true);
    } else {
      setAuthError(result.error);
    }
    setIsLoading(false);
  };

  const handleLogout = async () => {
    await authService.logout();
    setIsAuthenticated(false);
    setCurrentUser(null);
    setTenantId(null);
    setResultsHistory([]);
    setEnhancedResults(null);

    // Clear Epic OAuth state and used codes
    sessionStorage.removeItem('epic_oauth_state');
    sessionStorage.removeItem('epic_used_codes');
    localStorage.removeItem('epic_oauth_debug');

    // Clear URL parameters (code, state, error, etc.)
    if (window.location.search) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  // Restore session
  useEffect(() => {
    if (authService.restoreSession()) {
      setCurrentUser(authService.getCurrentUser());
      setTenantId(authService.getTenantId());
      setIsAuthenticated(true);
    }
  }, []);

  // Handle window resize to prevent alignment issues
  useEffect(() => {
    const handleResize = () => {
      // On mobile view, always expand sidebar
      if (window.innerWidth < 1024) {
        setIsCollapsed(false);
      }
    };

    // Add event listener
    window.addEventListener('resize', handleResize);

    // Call once on mount to set initial state
    handleResize();

    // Cleanup
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Welcome screen handler
  const handleStartProcessing = () => {
    localStorage.setItem('hasSeenWelcome', 'true');
    setHasSeenWelcome(true);
    setActiveTab('processing');
  };

  // Back to Home (Welcome screen)
  const handleBackToHome = () => {
    localStorage.removeItem('hasSeenWelcome');
    setHasSeenWelcome(false);
    setActiveTab('processing'); // optional: reset to default tab
  };

  const navigationItems = [
    { id: 'processing', name: 'OCR Processing', icon: Upload, description: 'Upload and process documents' },
    { id: 'results', name: 'Results', icon: BarChart3, description: 'View extraction results' },
    // { id: 'blob-storage', name: 'Blob Storage', icon: HardDrive, description: 'View uploaded files in Azure Blob Storage' },
    { id: 'template-manager', name: 'Template Manager', icon: FileSpreadsheet, description: 'Upload and manage Excel templates' },
    { id: 'template-mapping', name: 'Template Mapping', icon: MapPin, description: 'Process documents with template mapping' },
    { id: 'insights', name: 'Insights', icon: PieChart, description: 'Fax scanning and processing dashboard' }
  ];

  // Microsoft login handler
  const handleMicrosoftLogin = async (msalResponse) => {
    setIsLoading(true);
    setAuthError('');

    try {
      // Extract user info from MSAL response
      const email = msalResponse.account?.username || msalResponse.account?.localAccountId;
      const username = msalResponse.account?.name || email?.split('@')[0];
      const accountId = msalResponse.account?.homeAccountId;

      // Send to backend for user creation/login
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login/azure-ad`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          username: username,
          account_id: accountId,
        }),
      });

      if (response.ok) {
        const data = await response.json();

        // Store authentication info
        authService.authToken = data.access_token;
        authService.currentUser = data.user;
        authService.tenantId = data.tenant_id;

        // Persist in localStorage
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('currentUser', JSON.stringify(data.user));
        localStorage.setItem('tenantId', data.tenant_id);
        localStorage.setItem('msal_id_token', msalResponse.idToken);

        setCurrentUser(data.user);
        setTenantId(data.tenant_id);
        setIsAuthenticated(true);
      } else {
        const errorData = await response.json();
        setAuthError(errorData.detail || 'Microsoft login failed');
      }
    } catch (error) {
      console.error('Microsoft login error:', error);
      setAuthError('Microsoft login error: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Epic login handler
  const handleEpicLogin = () => {
    initiateEpicLogin();
  };

  // Handle Epic OAuth callback
  useEffect(() => {
    if (isAuthenticated) {
      // If already authenticated, clear any OAuth parameters from URL
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has('code') || urlParams.has('state') || urlParams.has('error')) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
      return; // Don't process callback if already authenticated
    }

    // Check if there's a valid OAuth state in sessionStorage
    // If not, ignore any codes in URL (they're from a previous session)
    const storedState = sessionStorage.getItem('epic_oauth_state');
    const urlParams = new URLSearchParams(window.location.search);
    const urlCode = urlParams.get('code');
    const urlState = urlParams.get('state');

    // If there's a code in URL but no matching state, it's an old/stale code - ignore it
    if (urlCode && (!urlState || !storedState || urlState !== storedState)) {
      console.log('Ignoring stale OAuth code from previous session');
      // Clear the URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    // Show debug info if available (after redirect)
    try {
      const debugInfo = localStorage.getItem('epic_oauth_debug');
      if (debugInfo) {
        console.log('=== Epic OAuth Debug Info (After Redirect) ===');
        console.log('Type: epicDebug() in console to view full debug info');
        console.log('Or check localStorage: localStorage.getItem("epic_oauth_debug")');
      }
    } catch (e) {
      // Ignore
    }

    const epicCallback = handleEpicCallback();
    if (epicCallback) {
      if (epicCallback.error) {
        // Show detailed error message
        let errorMessage = epicCallback.error;
        if (epicCallback.errorDescription) {
          errorMessage += `: ${epicCallback.errorDescription}`;
        }
        setAuthError(errorMessage);
        console.error('Epic OAuth Error:', epicCallback.error);
        if (epicCallback.errorDescription) {
          console.error('Error Description:', epicCallback.errorDescription);
        }
        if (epicCallback.rawError) {
          console.error('Raw Error Code:', epicCallback.rawError);
        }

        // Special handling for Epic error page
        if (epicCallback.rawError === 'oauth2_error_page') {
          console.error('');
          console.error('═══════════════════════════════════════════════════════');
          console.error('EPIC OAUTH2 ERROR PAGE DETECTED');
          console.error('═══════════════════════════════════════════════════════');
          console.error('');
          console.error('Epic returned an error page instead of redirecting.');
          console.error('This means Epic rejected the request before showing login.');
          console.error('');
          console.error('VERIFY IN EPIC APP ORCHARD:');
          console.error('1. Client ID: f139ac22-65b3-4dd4-b10d-0960e6f14850');
          console.error('   → Is it active and approved?');
          console.error('');
          console.error('2. Redirect URI: https://ai-doc-assist-dev.eastus.cloudapp.azure.com/');
          console.error('   → Does it match EXACTLY (including trailing slash)?');
          console.error('');
          console.error('3. Scopes: openid, profile, fhirUser');
          console.error('   → Are all three approved?');
          console.error('');
          console.error('4. App Status: Must be "Tested" or "Ready"');
          console.error('   → Is the app approved and active?');
          console.error('');
          console.error('═══════════════════════════════════════════════════════');
        }

        console.log('💡 Type: epicDebug() in console to see what was sent to Epic');
        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
      }

      if (epicCallback.code) {
        // Exchange authorization code for token via backend
        // Clear the code from URL immediately to prevent reuse
        window.history.replaceState({}, document.title, window.location.pathname);
        handleEpicCallbackCode(epicCallback.code);
      }
    }
  }, [isAuthenticated]);

  const handleEpicCallbackCode = async (code) => {
    setIsLoading(true);
    setAuthError('');

    try {
      // Track used codes to prevent reuse (store in sessionStorage)
      const usedCodes = JSON.parse(sessionStorage.getItem('epic_used_codes') || '[]');
      if (usedCodes.includes(code)) {
        console.warn('Authorization code already used, ignoring');
        setAuthError('This authorization code has already been used. Please try logging in again.');
        // Clear OAuth state
        sessionStorage.removeItem('epic_oauth_state');
        return;
      }

      // Send authorization code to backend for token exchange
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login/epic`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          code: code,
        }),
      });

      if (response.ok) {
        const data = await response.json();

        // Mark code as used
        usedCodes.push(code);
        // Keep only last 10 codes to prevent storage bloat
        if (usedCodes.length > 10) {
          usedCodes.shift();
        }
        sessionStorage.setItem('epic_used_codes', JSON.stringify(usedCodes));

        // Store authentication info
        authService.authToken = data.access_token;
        authService.currentUser = data.user;
        authService.tenantId = data.tenant_id;

        // Persist in localStorage
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('currentUser', JSON.stringify(data.user));
        localStorage.setItem('tenantId', data.tenant_id);

        // Store Epic FHIR token for write operations
        // The backend now returns epic_fhir_token in the response
        if (data.epic_fhir_token) {
          const { setEpicWriteToken } = await import('./services/epicWriteService');
          setEpicWriteToken(data.epic_fhir_token);
          console.log('═══════════════════════════════════════════════════════');
          console.log('✅ EPIC FHIR TOKEN STORED');
          console.log('═══════════════════════════════════════════════════════');
          console.log('✓ Epic write token stored for FHIR operations');
          console.log('🔑 Token preview:', data.epic_fhir_token.substring(0, 20) + '...');
          console.log('═══════════════════════════════════════════════════════');
        } else {
          console.warn('⚠️  Epic login response did not include epic_fhir_token');
          console.log('🔄 Attempting to exchange code for write token...');
          // Try to exchange the code again for a write token
          try {
            const { exchangeEpicToken, setEpicWriteToken } = await import('./services/epicWriteService');
            const tokenData = await exchangeEpicToken(code);
            if (tokenData.access_token) {
              setEpicWriteToken(tokenData.access_token);
              console.log('✅ Epic write token obtained and stored via exchange');
            } else {
              console.warn('⚠️  Token exchange did not return access_token');
            }
          } catch (tokenError) {
            console.error('❌ Could not obtain Epic write token:', tokenError);
            console.log('💡 You may need to login again with write scopes to store data in Epic');
          }
        }

        setCurrentUser(data.user);
        setTenantId(data.tenant_id);
        setIsAuthenticated(true);

        // Clear OAuth state after successful login
        sessionStorage.removeItem('epic_oauth_state');
        localStorage.removeItem('epic_oauth_debug');

        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
      } else {
        const errorData = await response.json();
        // Suppress invalid_grant errors - they often occur when code is reused
        if (errorData.error === 'invalid_grant' ||
          (errorData.detail && errorData.detail.includes('invalid_grant'))) {
          console.log('Epic token exchange warning (suppressed): invalid_grant - code may have been reused');
          // Clear OAuth state and prompt for new login
          sessionStorage.removeItem('epic_oauth_state');
          setAuthError('Please try logging in again. The authorization code has expired or was already used.');
        } else {
          setAuthError(errorData.detail || 'Epic login failed');
        }
        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    } catch (error) {
      console.error('Epic login error:', error);
      // Suppress invalid_grant errors in catch block as well
      if (error.message && error.message.includes('invalid_grant')) {
        console.log('Epic token exchange warning (suppressed): invalid_grant');
        sessionStorage.removeItem('epic_oauth_state');
        setAuthError('Please try logging in again. The authorization code has expired or was already used.');
      } else {
        setAuthError('Epic login error: ' + error.message);
      }
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } finally {
      setIsLoading(false);
    }
  };

  // Login screen
  if (!isAuthenticated) {
    return (
      <Login
        onLogin={handleLogin}
        onRegister={handleRegister}
        isLoading={isLoading}
        authError={authError}
        onMicrosoftLogin={handleMicrosoftLogin}
        onEpicLogin={handleEpicLogin}
      />
    );
  }

  // Admin dashboard
  if (currentUser?.is_admin) {
    return <AdminDashboard onLogout={handleLogout} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        navigationItems={navigationItems}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasSeenWelcome={hasSeenWelcome}
        setHasSeenWelcome={setHasSeenWelcome}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
      />
      {/* Main Content */}
      <div className={`transition-all duration-300 ${sidebarOpen ? (isCollapsed ? 'lg:ml-20' : 'lg:ml-64') : 'ml-0'}`}>
        <Header
          currentUser={currentUser}
          tenantId={tenantId}
          onLogout={handleLogout}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          hasSeenWelcome={hasSeenWelcome}
          setHasSeenWelcome={setHasSeenWelcome}
        />

        <main className="py-4 px-4 sm:py-6 sm:px-6 lg:py-8 lg:px-8 main-contentner-bg mx-2 sm:mx-4 lg:mx-8 rounded-xl">
          {/* === WELCOME (first time only) === */}
          {!hasSeenWelcome && (
            <div className="py-8 sm:py-12 lg:py-16">
              <Welcome onStartProcessing={handleStartProcessing} />
            </div>
          )}

          {/* === TAB HEADER (only after Welcome) === */}
          {hasSeenWelcome && (

            <div className="flex gap-3 items-center mb-10">
              <div className="w-[70px] h-[70px] overflow-visible">
                {activeTab === 'insights' ? (
                  <InsightsIcon size={20} color="" title="Insights" className="w-[70px] h-[70px] sm:w-[150px] sm:h-[150px]" />
                ) : (
                  <OCRProcessing size={20} color="" title="OCRProcessing" className="sm:w-[150px] sm:h-[150px]" />
                )}
              </div>
              <div>
                <h2 className="text-[20px] sm:text-[24px] font-semibold text-white">
                  {navigationItems.find(i => i.id === activeTab)?.name || 'OCR Processing'}
                </h2>
                <p className="text-[14px] sm:text-[16px] text-white opacity-90">
                  {navigationItems.find(i => i.id === activeTab)?.description}
                </p>
              </div>
            </div>
          )}

          {/* === TAB CONTENT – ALWAYS RENDERED AFTER WELCOME === */}
          {hasSeenWelcome && (
            <>
              {activeTab === 'processing' && (
                <ProcessingTab
                  handleBackToHome={handleBackToHome}
                  handleFilesChange={handleFilesChange}
                  processFiles={processFiles}
                  isProcessing={isProcessing}
                  enhancedResults={enhancedResults}
                  exportToExcel={exportToExcel}
                  exportMappedExcel={exportMappedExcel}
                  templates={templates}
                  selectedTemplateId={selectedTemplateId}
                  setSelectedTemplateId={setSelectedTemplateId}
                  progress={progress}
                  currentFile={currentFile}
                  errors={errors}
                  isEditingMapped={isEditingMapped}
                  setIsEditingMapped={setIsEditingMapped}
                  mappedEditingValues={mappedEditingValues}
                  setMappedEditingValues={setMappedEditingValues}
                  handleMappedValueChange={handleMappedValueChange}
                  saveMappedEdits={saveMappedEdits}
                  setEnhancedResults={setEnhancedResults}
                  setErrors={setErrors}
                />
              )}

              {activeTab === 'results' && (
                <ResultsTab
                  resultsHistory={resultsHistory}
                  tenantId={tenantId}
                  API_BASE_URL={API_BASE_URL}
                  authService={authService}
                  setResultsHistory={setResultsHistory}
                  exportToExcel={exportToExcel}
                  setActiveTab={setActiveTab}
                />
              )}

              {activeTab === 'blob-storage' && <BlobViewer isAdmin={currentUser?.is_admin} />}
              {activeTab === 'template-manager' && <TemplateManager />}
              {activeTab === 'template-mapping' && <TemplateMappedResults />}
              {activeTab === 'insights' && <FaxAutomationInsights />}
            </>
          )}


        </main>
        <Footer />
      </div>
    </div>
  );
}

export default App;