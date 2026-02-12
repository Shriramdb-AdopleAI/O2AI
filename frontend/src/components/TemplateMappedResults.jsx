import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { 
  FileSpreadsheet, 
  Edit3, 
  Save, 
  X, 
  Download, 
  Upload, 
  CheckCircle, 
  AlertCircle,
  Eye,
  EyeOff
} from 'lucide-react';
import authService from '../services/authService';

const TemplateMappedResults = () => {
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
  
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [processingResults, setProcessingResults] = useState([]);
  const [editingDocument, setEditingDocument] = useState(null);
  const [editingValues, setEditingValues] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showRawData, setShowRawData] = useState({});

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/templates`, {
        headers: authService.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to load templates');
      }

      const data = await response.json();
      const rawList = data.data || data.templates || [];
      const normalized = (Array.isArray(rawList) ? rawList : []).map((t, idx) => ({
        template_id: t.template_id || t.id || t.templateId || `${t.filename || 'template'}_${idx}`,
        filename: t.filename || t.name || `Template ${idx + 1}`,
        created_at: t.created_at || t.createdAt || null,
        total_columns: typeof t.total_columns === 'number' ? t.total_columns : (Array.isArray(t.fields) ? t.fields.length : 0),
      }));
      setTemplates(normalized);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    
    if (!uploadFile) {
      setError('Please select a file to upload');
      return;
    }

    if (!selectedTemplate) {
      setError('Please select a template');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('template_id', selectedTemplate);
      formData.append('apply_preprocessing', 'true');
      formData.append('enhance_quality', 'true');
      formData.append('include_raw_text', 'true');
      formData.append('include_metadata', 'true');

      const response = await fetch(`${API_BASE_URL}/api/v1/ocr/enhanced/process-with-template`, {
        method: 'POST',
        // IMPORTANT: do not set Content-Type manually for FormData
        headers: authService.getAuthHeadersAuthOnly(),
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        let message = 'Failed to process document';
        if (errorData && errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            message = errorData.detail.map((d) => (d?.msg || d?.detail || JSON.stringify(d))).join('; ');
          } else if (typeof errorData.detail === 'string') {
            message = errorData.detail;
          } else {
            message = JSON.stringify(errorData.detail);
          }
        }
        throw new Error(message);
      }

      const data = await response.json();

      // Normalize API response (supports legacy and new shapes)
      const normalizeResult = (api) => {
        if (!api || typeof api !== 'object') return {};
        const hidden = api._hidden_mapping || {};
        const extracted = api.extracted_values || (api.template_mapping && api.template_mapping.mapped_values) || {};
        const mapping = api.template_mapping || hidden.template_mapping || {};
        const confidence_scores = mapping.confidence_scores || {};
        const unmapped_fields = mapping.unmapped_fields || [];
        const processing_timestamp = mapping.processing_timestamp || api.processing_timestamp || new Date().toISOString();
        const filename = api.filename || (api.file_info && api.file_info.filename) || 'unknown';
        const document_id = api.document_id || api.id || `${Date.now()}`;
        const extraction_result = api.extraction_result || hidden.extraction_result || { key_value_pairs: extracted };

        // Force UI to operate on visible extracted values only
        const template_mapping = {
          mapped_values: extracted || {},
          confidence_scores,
          unmapped_fields,
          processing_timestamp
        };

        return {
          document_id,
          filename,
          template_mapping,
          extraction_result,
          _hidden_mapping: hidden
        };
      };

      const normalized = normalizeResult(data);
      
      // Add the new result to the list (normalized)
      setProcessingResults(prev => [normalized, ...prev]);
      setSuccess('Document processed and mapped successfully!');
      setUploadFile(null);
      
      // Reset file input
      const fileInput = document.getElementById('document-file');
      if (fileInput) fileInput.value = '';
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startEditing = (documentId, mappedValues) => {
    setEditingDocument(documentId);
    setEditingValues({ ...mappedValues });
  };

  const saveEdits = async () => {
    if (!editingDocument || !selectedTemplate) return;

    try {
      setLoading(true);
      
      const response = await fetch(
        `${API_BASE_URL}/api/v1/templates/${selectedTemplate}/mappings/${editingDocument}`,
        {
          method: 'PUT',
          headers: {
            ...authService.getAuthHeaders(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(editingValues)
        }
      );

      if (!response.ok) {
        throw new Error('Failed to save changes');
      }

      // Update the local state
      setProcessingResults(prev => 
        prev.map(result => 
          result.document_id === editingDocument 
            ? {
                ...result,
                template_mapping: {
                  ...result.template_mapping,
                  mapped_values: editingValues
                }
              }
            : result
        )
      );

      setSuccess('Changes saved successfully!');
      setEditingDocument(null);
      setEditingValues({});
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const cancelEditing = () => {
    setEditingDocument(null);
    setEditingValues({});
  };

  const handleValueChange = (fieldKey, value) => {
    setEditingValues(prev => ({
      ...prev,
      [fieldKey]: value
    }));
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-50';
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getConfidenceIcon = (confidence) => {
    if (confidence >= 0.8) return <CheckCircle className="h-4 w-4" />;
    if (confidence >= 0.6) return <AlertCircle className="h-4 w-4" />;
    return <X className="h-4 w-4" />;
  };

  const exportConsolidatedExcel = async () => {
    if (!selectedTemplate || processingResults.length === 0) return;

    try {
      setLoading(true);
      
      const mappingResults = processingResults.map(result => ({
        document_id: result.document_id,
        filename: result.filename,
        mapped_values: result.template_mapping.mapped_values,
        confidence_scores: result.template_mapping.confidence_scores,
        unmapped_fields: result.template_mapping.unmapped_fields,
        processing_timestamp: result.template_mapping.processing_timestamp
      }));

      const response = await fetch(
        `${API_BASE_URL}/api/v1/templates/${selectedTemplate}/export`,
        {
          method: 'POST',
          headers: {
            ...authService.getAuthHeaders(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(mappingResults)
        }
      );

      if (!response.ok) {
        throw new Error('Failed to export Excel');
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `consolidated_mapping_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccess('Excel file exported successfully!');
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const toggleRawData = (documentId) => {
    setShowRawData(prev => ({
      ...prev,
      [documentId]: !prev[documentId]
    }));
  };

  return (
    <div className="container mx-auto p-0">
      <div className="flex items-center justify-between">
        {/* <div>
          <h1 className="text-[24px] font-bold text-[#ffffff]">Template Mapping</h1>
          <p className="text-muted-foreground">
            Process documents with templates and edit mapped values
          </p>
        </div> */}
        {processingResults.length > 0 && selectedTemplate && (
          <Button onClick={exportConsolidatedExcel} disabled={loading}>
            <Download className="h-4 w-4 mr-2" />
            Export Consolidated Excel
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="border-green-200 bg-green-50">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="upload" className="space-y-4">
        <TabsList>
          <TabsTrigger value="upload">Process Document</TabsTrigger>
          <TabsTrigger value="results">Mapped Results</TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Process Document with Template
              </CardTitle>
              <CardDescription>
                Upload a document and process it using a selected template for mapping
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleFileUpload} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="template-select">Select Template</Label>
                  <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a template" />
                    </SelectTrigger>
                    <SelectContent>
                      {templates.map((template) => (
                        <SelectItem key={template.template_id} value={template.template_id}>
                          {template.filename} ({template.total_columns} fields)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="document-file">Select Document</Label>
                  <Input
                    id="document-file"
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                    required
                  />
                  <p className="text-sm text-muted-foreground">
                    Supported formats: PDF, PNG, JPG, JPEG
                  </p>
                </div>

                <Button 
                  type="submit" 
                  disabled={loading || !uploadFile || !selectedTemplate} 
                  className="w-full"
                >
                  {loading ? 'Processing...' : 'Process Document'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="results" className="space-y-4">
          {processingResults.length === 0 ? (
            <Card>
              <CardContent className="text-center py-8">
                <FileSpreadsheet className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No processed documents yet</p>
                <p className="text-sm text-muted-foreground">
                  Upload and process documents to see mapped results
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {processingResults.map((result, index) => (
                <Card key={result.document_id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {result.filename}
                          <Badge variant="secondary">
                            {Object.keys((result.template_mapping && result.template_mapping.mapped_values) || {}).length} fields
                          </Badge>
                        </CardTitle>
                        <CardDescription>
                          Processed: {formatDate(result.template_mapping.processing_timestamp)}
                        </CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => toggleRawData(result.document_id)}
                        >
                          {showRawData[result.document_id] ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                        {editingDocument === result.document_id ? (
                          <>
                            <Button onClick={saveEdits} size="sm" disabled={loading}>
                              <Save className="h-4 w-4 mr-2" />
                              Save
                            </Button>
                            <Button onClick={cancelEditing} size="sm" variant="outline">
                              <X className="h-4 w-4 mr-2" />
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <Button
                            onClick={() => startEditing(result.document_id, result.template_mapping.mapped_values)}
                            size="sm"
                          >
                            <Edit3 className="h-4 w-4 mr-2" />
                            Edit Values
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {/* Mapped Values */}
                      <div>
                        <h3 className="font-medium mb-3">Mapped Values</h3>
                        <div className="grid gap-3">
                          {Object.entries((result.template_mapping && result.template_mapping.mapped_values) || {}).map(([fieldKey, value]) => {
                            const confidence = (result.template_mapping && result.template_mapping.confidence_scores && result.template_mapping.confidence_scores[fieldKey]) || 0;
                            const isEditing = editingDocument === result.document_id;
                            
                            return (
                              <div key={fieldKey} className="flex items-center gap-3 p-3 border rounded-lg">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <Label className="font-medium">{fieldKey}</Label>
                                    <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${getConfidenceColor(confidence)}`}>
                                      {getConfidenceIcon(confidence)}
                                      <span>{Math.round(confidence * 100)}%</span>
                                    </div>
                                  </div>
                                  {isEditing ? (
                                    <Input
                                      value={editingValues[fieldKey] || ''}
                                      onChange={(e) => handleValueChange(fieldKey, e.target.value)}
                                      placeholder="Enter value"
                                    />
                                  ) : (
                                    <p className="text-sm text-muted-foreground">
                                      {value || <span className="italic">No value mapped</span>}
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Unmapped Fields */}
                      {Array.isArray(result.template_mapping && result.template_mapping.unmapped_fields) && (result.template_mapping.unmapped_fields.length > 0) && (
                        <div>
                          <h3 className="font-medium mb-3 text-orange-600">Unmapped Fields</h3>
                          <div className="flex flex-wrap gap-2">
                            {result.template_mapping.unmapped_fields.map((field) => (
                              <Badge key={field} variant="outline" className="text-orange-600">
                                {field}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Raw Data Toggle */}
                      {showRawData[result.document_id] && (
                        <div>
                          <h3 className="font-medium mb-3">Raw Extraction Data</h3>
                          <div className="bg-gray-50 p-4 rounded-lg">
                            <pre className="text-sm whitespace-pre-wrap">
                              {JSON.stringify(result.extraction_result || result._hidden_mapping || {}, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default TemplateMappedResults;
