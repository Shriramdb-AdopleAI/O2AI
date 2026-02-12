// src/components/ResultsTab.jsx
import React, { useEffect, useState } from 'react';
import { FileText, BarChart3, Upload, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader } from './ui/card';
import EnhancedOCRResults from './EnhancedOCRResults';

const ResultsTab = ({
  resultsHistory,
  tenantId,
  API_BASE_URL,
  authService,
  setResultsHistory,
  exportToExcel,
  setActiveTab,
}) => {
  const [isLoading, setIsLoading] = useState(false);

  // Load history from data folder when component mounts or tenantId changes
  useEffect(() => {
    const loadHistory = async () => {
      if (!tenantId) return;
      
      setIsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
          headers: authService.getAuthHeaders()
        });
        if (response.status === 401) {
          await authService.logout();
          return;
        }
        if (response.ok) {
          const data = await response.json();
          setResultsHistory(data.history || []);
        }
      } catch (error) {
        console.error('Failed to load history:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadHistory();
  }, [tenantId, API_BASE_URL, authService, setResultsHistory]);

  // Refresh history function
  const handleRefresh = async () => {
    if (!tenantId) return;
    
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
        headers: authService.getAuthHeaders()
      });
      if (response.status === 401) {
        await authService.logout();
        return;
      }
      if (response.ok) {
        const data = await response.json();
        setResultsHistory(data.history || []);
      }
    } catch (error) {
      console.error('Failed to refresh history:', error);
    } finally {
      setIsLoading(false);
    }
  };
  const handleClearAll = async () => {
    if (!confirm('Are you sure you want to clear all history?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
        method: 'DELETE',
        headers: authService.getAuthHeaders(),
      });
      if (response.ok) {
        setResultsHistory([]);
      }
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  const handleDeleteEntry = async (entryId) => {
    if (!confirm('Are you sure you want to delete this entry?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}/${entryId}`, {
        method: 'DELETE',
        headers: authService.getAuthHeaders(),
      });
      if (response.ok) {
        const historyResponse = await fetch(`${API_BASE_URL}/api/v1/history/${tenantId}`, {
          headers: authService.getAuthHeaders(),
        });
        if (historyResponse.ok) {
          const data = await historyResponse.json();
          setResultsHistory(data.history || []);
        }
      }
    } catch (error) {
      console.error('Failed to delete entry:', error);
    }
  };

  return (
    <div className="space-y-6">
      {isLoading && resultsHistory.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <RefreshCw className="h-12 w-12 text-gray-400 mx-auto mb-4 animate-spin" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Loading Processing History</h3>
            <p className="text-gray-500">
              Please wait while we fetch your processing history from data folder...
            </p>
          </CardContent>
        </Card>
      ) : resultsHistory.length > 0 ? (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
            <div className='flex flex-col sm:flex-row gap-2 sm:gap-3'>
              <h2 className="text-[#ffffff] font-semibold text-[18px] sm:text-[20px]">Processing History</h2>
              {tenantId && (
                <p className="text-[14px] sm:text-[16px] text-[#ffffff] mt-0 sm:mt-1">
                  Session ID: {tenantId.substring(0, 8)}...
                </p>
              )}
            </div>
            <div className="flex flex-col items-end gap-2 w-full sm:w-auto">
              <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs text-[#ffffff] opacity-80">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded border border-gray-300 bg-green-500"></span>
                  <span>Green (≥95%)</span>
                </span>
                <span>|</span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded border border-gray-300 bg-amber-500"></span>
                  <span>Amber (90-94.9%)</span>
                </span>
                <span>|</span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded border border-gray-300 bg-red-500"></span>
                  <span>Red ({'<'}89.9%)</span>
                </span>
              </div>
              <div className="flex items-center space-x-2 sm:space-x-3 w-full sm:w-auto">
                <Badge variant="secondary" className="text-xs sm:text-sm">
                  {resultsHistory.length} {resultsHistory.length === 1 ? 'result' : 'results'}
                </Badge>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={handleRefresh} 
                  disabled={isLoading}
                  className="flex-1 sm:flex-none"
                >
                  <RefreshCw className={`h-3 w-3 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
                <Button variant="outline" size="sm" onClick={handleClearAll} className="flex-1 sm:flex-none">
                  Clear All
                </Button>
              </div>
            </div>
          </div>

          {resultsHistory.map((entry) => (
            <Card key={entry.id} className="border-l-4 border-l-blue-500">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                      <FileText className="h-4 w-4 text-blue-600" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-medium text-gray-900 text-sm sm:text-base truncate">{entry.filename}</h3>
                      <p className="text-xs sm:text-sm text-gray-500">
                        Processed on {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 w-full sm:w-auto justify-end sm:justify-start">
                    <Badge variant="outline" className="text-xs">
                      {Array.isArray(entry.result.individual_results) ? 'Batch' : 'Single'}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteEntry(entry.id)}
                      className="text-red-600 hover:text-red-700 text-xs sm:text-sm"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <EnhancedOCRResults
                  results={entry.result}
                  isBatch={Array.isArray(entry.result.individual_results)}
                  onExportExcel={exportToExcel}
                  source="results"
                />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-12 text-center">
            <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Processing History</h3>
            <p className="text-gray-500 mb-4">
              Process some documents first to see extraction results here.
            </p>
            <Button onClick={() => setActiveTab('processing')}>
              <Upload className="h-4 w-4 mr-2" />
              Go to Processing
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ResultsTab;