// src/components/ProcessingTab.jsx
import React from 'react';
import {
  Upload, BarChart3, FileSpreadsheet, X, ArrowLeft
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import EnhancedFileUpload from './EnhancedFileUpload';
import EnhancedOCRResults from './EnhancedOCRResults';

const ProcessingTab = ({
  // From App.jsx
  handleBackToHome,
  handleFilesChange,
  processFiles,
  isProcessing,
  enhancedResults,
  exportToExcel,
  exportMappedExcel,
  templates,
  selectedTemplateId,
  setSelectedTemplateId,
  errors,
  isEditingMapped,
  setIsEditingMapped,
  mappedEditingValues,
  setMappedEditingValues,
  handleMappedValueChange,
  saveMappedEdits,

  // NEW: Required to reset results
  setEnhancedResults,
  setErrors,
}) => {
  // Reset everything and go back to Welcome
  const handleResetAndBack = () => {
    setEnhancedResults(null);     // Hide OCR & template results
    setErrors([]);                // Clear errors
    setIsEditingMapped(false);    // Exit edit mode
    setMappedEditingValues({});   // Clear mapped values
    handleBackToHome();           // Show Welcome screen
  };

  return (
    <div className="space-y-6">

      {/* === BACK TO HOME BUTTON (resets + shows upload) === */}
      <div className="flex justify-start">
        <button
          variant="outline"
          size="sm"
          onClick={handleResetAndBack}
          className="flex items-center text-[#ffffff] bg-transparent gap-2 text-sm sm:text-base transition-colors transpertant-blurBg rounded-lg px-3 py-1 b-[#ffffff24] border-color=[#cccccc2e]"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Home</span>
        </button>
      </div>

      {/* === UPLOAD: ONLY SHOW IF NO RESULTS === */}
      {!enhancedResults && (
        <EnhancedFileUpload
          onFilesSelected={handleFilesChange}
          onProcessFiles={processFiles}
          processing={isProcessing}
          results={enhancedResults}
          processedData={enhancedResults}
          onExportExcel={exportToExcel}
          templates={templates}
          selectedTemplateId={selectedTemplateId}
          onSelectTemplate={setSelectedTemplateId}
        />
      )}

      {/* === ERRORS === */}
      {errors.length > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6">
            <div className="flex items-center space-x-2 text-red-700">
              <X className="h-5 w-5" />
              <span className="font-medium">Processing Errors</span>
            </div>
            <ul className="mt-2 space-y-1">
              {errors.map((error, index) => (
                <li key={index} className="text-sm text-red-600">{error}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* === OCR RESULTS (no template) === */}
      {enhancedResults && !enhancedResults.template_mapping && (
        <div>
          <EnhancedOCRResults
            results={enhancedResults}
            isBatch={Array.isArray(enhancedResults.individual_results)}
            onExportExcel={exportToExcel}
            source="processing"
          />
          <div className="flex justify-end mt-4">
            <Button
              onClick={() => setEnhancedResults(null)}
              size="sm"
              variant="outline"
            >
              Upload Another File
            </Button>
          </div>
        </div>
      )}

      {/* === TEMPLATE MAPPING RESULTS === */}
      {enhancedResults?.template_mapping && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileSpreadsheet className="h-5 w-5" />
              <span>Template Mapped Values</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {!isEditingMapped ? (
                  <Button onClick={() => setIsEditingMapped(true)} size="sm" className="w-full sm:w-auto">
                    Edit Values
                  </Button>
                ) : (
                  <>
                    <Button onClick={saveMappedEdits} size="sm" className="w-full sm:w-auto">Save</Button>
                    <Button
                      onClick={() => {
                        setIsEditingMapped(false);
                        setMappedEditingValues(enhancedResults.template_mapping.mapped_values || {});
                      }}
                      size="sm"
                      variant="outline"
                      className="w-full sm:w-auto"
                    >
                      Cancel
                    </Button>
                  </>
                )}
                <Button onClick={exportMappedExcel} size="sm" variant="outline" className="w-full sm:w-auto">
                  Export Excel
                </Button>
              </div>

              <div className="grid gap-3">
                {Object.entries(mappedEditingValues).map(([fieldKey, value]) => (
                  <div key={fieldKey} className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 p-3 border rounded-lg">
                    <div className="w-full sm:w-48 lg:w-64 text-sm font-medium break-words">{fieldKey}</div>
                    <div className="flex-1 w-full sm:w-auto">
                      {isEditingMapped ? (
                        <Input
                          value={value || ''}
                          onChange={(e) => handleMappedValueChange(fieldKey, e.target.value)}
                          className="w-full"
                        />
                      ) : (
                        <div className="text-sm text-muted-foreground break-words">
                          {value || <span className="italic">No value</span>}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ProcessingTab;