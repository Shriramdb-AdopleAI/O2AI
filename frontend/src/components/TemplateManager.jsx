import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Upload, FileSpreadsheet, Trash2, Eye, Download, Edit3, Save, X } from 'lucide-react';
import authService from '../services/authService';

const TemplateManager = () => {
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
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [editingValues, setEditingValues] = useState({});
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    // Load templates only when authenticated token exists
    if (authService.getAuthToken() || authService.restoreSession()) {
      loadTemplates();
    }
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/v1/templates`, {
        headers: authService.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to load templates');
      }

      const data = await response.json();
      const rawList = data.data || data.templates || [];
      // Normalize list to expected shape
      const normalized = (Array.isArray(rawList) ? rawList : []).map((t, idx) => ({
        template_id: t.template_id || t.id || t.templateId || `${t.filename || 'template'}_${idx}`,
        filename: t.filename || t.name || `Template ${idx + 1}`,
        created_at: t.created_at || t.createdAt || null,
        total_columns: typeof t.total_columns === 'number' ? t.total_columns : (Array.isArray(t.fields_preview) ? (t.fields_preview.length) : (Array.isArray(t.fields) ? t.fields.length : 0)),
        fields_preview: t.fields_preview || (Array.isArray(t.fields) ? t.fields.slice(0,5).map(f => f.key || f.display_name || String(f)) : [])
      }));
      setTemplates(normalized);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateUpload = async (e) => {
    e.preventDefault();
    
    if (!uploadFile) {
      setError('Please select a file to upload');
      return;
    }

    if (!uploadFile.name.match(/\.(xlsx|xls)$/)) {
      setError('Please upload an Excel file (.xlsx or .xls)');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const formData = new FormData();
      formData.append('file', uploadFile);

      const response = await fetch(`${API_BASE_URL}/api/v1/templates/upload`, {
        method: 'POST',
        headers: authService.getAuthHeadersAuthOnly(),
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload template');
      }

      const data = await response.json();
      setSuccess('Template uploaded successfully!');
      setUploadFile(null);
      loadTemplates();
      
      // Reset file input
      const fileInput = document.getElementById('template-file');
      if (fileInput) fileInput.value = '';
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplateDetails = async (templateId) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/v1/templates/${templateId}`, {
        headers: authService.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to load template details');
      }

      const data = await response.json();
      setSelectedTemplate(data.data);
      setEditingValues({});
      setIsEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteTemplate = async (templateId) => {
    if (!confirm('Are you sure you want to delete this template?')) {
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/v1/templates/${templateId}`, {
        method: 'DELETE',
        headers: authService.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to delete template');
      }

      setSuccess('Template deleted successfully!');
      loadTemplates();
      if (selectedTemplate && selectedTemplate.template_id === templateId) {
        setSelectedTemplate(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startEditing = () => {
    if (selectedTemplate) {
      setEditingValues(selectedTemplate.fields.reduce((acc, field) => {
        acc[field.key] = field.display_name;
        return acc;
      }, {}));
      setIsEditing(true);
    }
  };

  const saveEdits = () => {
    // In a real implementation, you would save the edited field names
    setSelectedTemplate(prev => ({
      ...prev,
      fields: prev.fields.map(field => ({
        ...field,
        display_name: editingValues[field.key] || field.display_name
      }))
    }));
    setIsEditing(false);
  };

  const cancelEditing = () => {
    setEditingValues({});
    setIsEditing(false);
  };

  const handleValueChange = (fieldKey, value) => {
    setEditingValues(prev => ({
      ...prev,
      [fieldKey]: value
    }));
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

  return (
    <div className="container mx-auto p-0 space-y-6">
      {/* <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[24px] font-bold text-[#ffffff]">Template Manager</h1>
          <p className="text-muted-foreground">
            Upload Excel templates and manage document mapping structures
          </p>
        </div>
      </div> */}

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
        <TabsList className="flex flex-wrap w-full sm:w-auto">
          <TabsTrigger value="upload" className="flex-1 sm:flex-none text-xs sm:text-sm">Upload Template</TabsTrigger>
          <TabsTrigger value="manage" className="flex-1 sm:flex-none text-xs sm:text-sm">Manage Templates</TabsTrigger>
          {selectedTemplate && (
            <TabsTrigger value="details" className="flex-1 sm:flex-none text-xs sm:text-sm">Template Details</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="upload" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Upload Excel Template
              </CardTitle>
              <CardDescription>
                Upload an Excel file to create a template for document mapping. 
                The first row should contain the field names/headers.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleTemplateUpload} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="template-file">Select Excel File</Label>
                  <Input
                    id="template-file"
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                    required
                  />
                  <p className="text-sm text-muted-foreground">
                    Supported formats: .xlsx, .xls
                  </p>
                </div>

                <Button type="submit" disabled={loading || !uploadFile} className="w-full">
                  {loading ? 'Uploading...' : 'Upload Template'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="manage" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Your Templates</CardTitle>
              <CardDescription>
                Manage your uploaded templates
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading && templates.length === 0 ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                  <p className="mt-2 text-muted-foreground">Loading templates...</p>
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-8">
                  <FileSpreadsheet className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No templates uploaded yet</p>
                  <p className="text-sm text-muted-foreground">
                    Upload your first template to get started
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Template Name</TableHead>
                      <TableHead>Fields</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {templates.map((template) => (
                      <TableRow key={template.template_id}>
                        <TableCell className="font-medium">
                          {template.filename}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {(template.fields_preview || []).map((field, index) => (
                              <Badge key={index} variant="secondary" className="text-xs">
                                {field}
                              </Badge>
                            ))}
                            {template.total_columns > 5 && (
                              <Badge variant="outline" className="text-xs">
                                +{template.total_columns - 5} more
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {template.created_at ? formatDate(template.created_at) : '—'}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => template.template_id && loadTemplateDetails(template.template_id)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => deleteTemplate(template.template_id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {selectedTemplate && (
          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{selectedTemplate.filename}</CardTitle>
                    <CardDescription>
                      Template ID: {selectedTemplate.template_id}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    {!isEditing ? (
                      <Button onClick={startEditing} size="sm">
                        <Edit3 className="h-4 w-4 mr-2" />
                        Edit Fields
                      </Button>
                    ) : (
                      <>
                        <Button onClick={saveEdits} size="sm">
                          <Save className="h-4 w-4 mr-2" />
                          Save
                        </Button>
                        <Button onClick={cancelEditing} size="sm" variant="outline">
                          <X className="h-4 w-4 mr-2" />
                          Cancel
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Total Fields:</span>
                      <p>{selectedTemplate.total_columns}</p>
                    </div>
                    <div>
                      <span className="font-medium">Created:</span>
                      <p>{formatDate(selectedTemplate.created_at)}</p>
                    </div>
                    <div>
                      <span className="font-medium">Status:</span>
                      <p className="text-green-600">Active</p>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-medium mb-3">Template Fields</h3>
                    <div className="grid gap-3">
                      {(selectedTemplate.fields || []).map((field, index) => (
                        <div key={index} className="flex items-center gap-3 p-3 border rounded-lg">
                          <div className="flex-1">
                            {isEditing ? (
                              <Input
                                value={editingValues[field.key] || field.display_name}
                                onChange={(e) => handleValueChange(field.key, e.target.value)}
                                placeholder="Field display name"
                              />
                            ) : (
                              <div>
                                <p className="font-medium">{field.display_name}</p>
                                <p className="text-sm text-muted-foreground">
                                  Key: {field.key} | Type: {field.data_type}
                                </p>
                              </div>
                            )}
                          </div>
                          <Badge variant="secondary">{field.data_type}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
};

export default TemplateManager;
