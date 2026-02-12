import React, { useState, useRef } from 'react';
import DatePickerButton from './DatePickerButton';
import RecentActivities from './RecentActivities';
import KPICard from './KPICard';
import AlertsCard from './AlertsCard';
import StatusBreakdown from './StatusBreakdown';
import ConfidenceBreakdown from './ConfidenceBreakdown';
import FilesTable from './FilesTable';
import { TotalFilesScannedIcon, LastUpdatedIcon, PendingFilesIcon, CompletedFilesIcon, ScanningAccuracyIcon } from './../icon';
import authService from '../../services/authService';
import {
  FileText,
  Scan,
  AlertTriangle,
  Search,
  Filter,
  Download,
  FileCheck,
  FileX,
  UserCheck,
  Users,
  Bell,
  PieChart,
  Activity,
  CheckCircle,
  Clock,
  Calendar  // Added PieChart icon
} from 'lucide-react';

export default function FaxAutomationInsights() {
  // Get current date in MM/DD/YYYY format (USA format)
  const getCurrentDateString = () => {
    const today = new Date();
    // Convert to EST timezone
    const estDate = new Date(today.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const month = String(estDate.getMonth() + 1).padStart(2, '0');
    const day = String(estDate.getDate()).padStart(2, '0');
    const year = estDate.getFullYear();
    return `${month}/${day}/${year}`;
  };

  // Format date to MM/DD/YYYY with current time in EST
  const formatDateWithTimeEST = (dateString) => {
    try {
      // Get current time in EST timezone
      const now = new Date();
      const estTimeString = now.toLocaleString('en-US', {
        timeZone: 'America/New_York',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });

      return `${dateString} ${estTimeString} EST`;
    } catch (e) {
      return dateString;
    }
  };

  const [fromDate, setFromDate] = useState(getCurrentDateString());
  const [toDate, setToDate] = useState(getCurrentDateString());
  const [kpiData, setKpiData] = useState({
    totalFiles: 0,
    completedFiles: 0,
    pendingFiles: 0,
    scanningAccuracy: '0%',
    lastUpdated: 'N/A',
    lastUpdatedTime: 'N/A'
  });
  const [statusBreakdownData, setStatusBreakdownData] = useState([
    { label: 'Successful Scans', value: 0, total: 0, color: 'blue' },
    { label: 'Failed / Error Files', value: 0, total: 0, color: 'red' },
    { label: 'Manual Review', value: 0, total: 0, color: 'orange' },
  ]);
  const [confidenceBreakdownData, setConfidenceBreakdownData] = useState([
    { label: 'Green (≥95%)', value: 0, color: 'green' },
    { label: 'Amber (90-94.9%)', value: 0, color: 'orange' },
    { label: 'Red (<89.9%)', value: 0, color: 'red' },
  ]);
  const [lowConfidenceFiles, setLowConfidenceFiles] = useState([]);
  const [filesData, setFilesData] = useState([]);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const jumpToLowConfidenceRef = useRef(null);

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

  // Handle download report summary
  const handleDownloadReportSummary = async () => {
    setIsGeneratingSummary(true);
    try {
      const headers = authService.getAuthHeaders();

      // Prepare the payload with all necessary data
      const payload = {
        table_data: filesData,
        kpi_data: kpiData,
        status_breakdown: statusBreakdownData,
        confidence_breakdown: confidenceBreakdownData,
        selected_date: `${fromDate} - ${toDate}`,
        selected_from_date: fromDate,
        selected_to_date: toDate,
      };

      console.log('Generating report summary...');

      const response = await fetch(
        `${API_BASE_URL}/api/v1/insights/generate-summary`,
        {
          method: 'POST',
          headers: {
            ...headers,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to generate summary: ${response.status} ${response.statusText}`);
      }

      // Check content type
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        // If server returned JSON instead of PDF, log it and throw error
        const jsonResponse = await response.json();
        console.error('Server returned JSON instead of PDF:', jsonResponse);
        throw new Error('Server returned JSON instead of PDF file');
      }

      // Get the PDF blob from response
      const blob = await response.blob();

      // Force blob type to PDF to ensure browser recognizes it
      const pdfBlob = new Blob([blob], { type: 'application/pdf' });

      if (pdfBlob.size === 0) {
        throw new Error('Generated PDF is empty');
      }

      // Create a blob URL and download
      const url = window.URL.createObjectURL(pdfBlob);
      const a = document.createElement('a');
      a.href = url;
      a.style.display = 'none'; // Ensure element is hidden

      // Generate filename with current date and time
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      const timestamp = `${year}${month}${day}_${hours}${minutes}${seconds}`;
      const filename = `Report_Summary_${timestamp}.pdf`;

      a.download = filename;
      document.body.appendChild(a);
      a.click();

      // Cleanup with a small delay to ensure click processed
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        console.log('Report summary downloaded successfully');
      }, 100);

    } catch (error) {
      console.error('Error downloading report summary:', error);
      alert(`Failed to generate report summary: ${error.message}`);
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  return (
    <>
      <div className="">
        {/* Header */}
        <div className="text-white pt-10 rounded-b-3xl">
          <div className="flex justify-end items-center mb-4 mt-[-120px] px-4 sm:px-0">
            <div className="flex items-center gap-3 sm:gap-4">
              {/* From Date */}
              <div className="flex flex-col items-start">
                <span className="text-[11px] sm:text-xs text-white/80 mb-1">From</span>
                <DatePickerButton
                  date={fromDate}
                  onDateChange={(newDate) => {
                    // Format as MM/DD/YYYY (USA format)
                    const formatted = newDate.toLocaleDateString('en-US', {
                      month: '2-digit',
                      day: '2-digit',
                      year: 'numeric',
                    });
                    setFromDate(formatted);
                    console.log('Selected from date:', formatted);
                  }}
                />
              </div>

              {/* To Date */}
              <div className="flex flex-col items-start">
                <span className="text-[11px] sm:text-xs text-white/80 mb-1">To</span>
                <DatePickerButton
                  date={toDate}
                  onDateChange={(newDate) => {
                    // Format as MM/DD/YYYY (USA format)
                    const formatted = newDate.toLocaleDateString('en-US', {
                      month: '2-digit',
                      day: '2-digit',
                      year: 'numeric',
                    });
                    setToDate(formatted);
                    console.log('Selected to date:', formatted);
                  }}
                />
              </div>
            </div>
            {/* Display date range with time in EST */}
            {/* <div className="ml-4 text-white/90 text-sm whitespace-nowrap">
              From {formatDateWithTimeEST(fromDate)} To {formatDateWithTimeEST(toDate)}
            </div> */}
          </div>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mt-8 border-t-2 border-[#ffffff2e] pt-6 px-4 sm:px-0">
            <KPICard
              title="Total Files Scanned"
              value={kpiData.totalFiles.toString()}
              subtitle="Files Processed"
              icon={TotalFilesScannedIcon}
            />

            <KPICard
              title="Scanning Accuracy"
              value={kpiData.scanningAccuracy}
              subtitle="Overall Accuracy"
              icon={ScanningAccuracyIcon}
            />

            <KPICard
              title="Completed Files"
              value={kpiData.completedFiles.toString()}
              subtitle="Files Completed"
              icon={CompletedFilesIcon}
            />

            <KPICard
              title="Pending Files"
              value={kpiData.pendingFiles.toString()}
              subtitle="Files In Queue"
              icon={PendingFilesIcon}
            />

            <KPICard
              title="Last Updated"
              value={kpiData.lastUpdated}
              subtitle={kpiData.lastUpdatedTime}
              icon={LastUpdatedIcon}
              valueSize="text-2xl"  // Smaller value as in original design
            />
          </div>
        </div>

        {/* Rest of the component remains unchanged */}
        <div className="w-[100%] mx-auto mt-6 px-4 sm:px-0">
          {/* Status Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 mb-6">
            {/* Left Column */}
            <div className="lg:col-span-2 space-y-4 sm:space-y-6">
              <StatusBreakdown data={statusBreakdownData} />
            </div>
            {/* Right Column*/}
            <div className="space-y-4 sm:space-y-6">
              <RecentActivities files={filesData} />
            </div>
          </div>
          {/* Confidence Breakdown Analytics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 bg-[#fff] py-6 sm:py-8 px-4 sm:px-10 rounded-2xl mb-6">
            {/* Left Column */}
            <div className="lg:col-span-2 space-y-4 sm:space-y-6">
              {/* Confidence Breakdown */}
              <ConfidenceBreakdown
                data={confidenceBreakdownData}
              />
            </div>
            {/* Right Column - Recent Activities & Alerts unchanged */}
            <div className="space-y-4 sm:space-y-6">
              <AlertsCard
                lowConfidenceFiles={lowConfidenceFiles}
                onJumpToRows={() => {
                  if (jumpToLowConfidenceRef.current) {
                    jumpToLowConfidenceRef.current();
                  }
                }}
              />
            </div>
          </div>
          {/* Table */}
          <FilesTable
            selectedFromDate={fromDate}
            selectedToDate={toDate}
            onKpiDataChange={setKpiData}
            onStatusBreakdownChange={setStatusBreakdownData}
            onConfidenceBreakdownChange={setConfidenceBreakdownData}
            onLowConfidenceFilesChange={setLowConfidenceFiles}
            onJumpToLowConfidenceRef={jumpToLowConfidenceRef}
            onFilesDataChange={setFilesData}
          />

          {/* Download Report Summary Button */}
          <div className="flex justify-center mt-8 mb-6">
            <button
              onClick={handleDownloadReportSummary}
              disabled={isGeneratingSummary || filesData.length === 0}
              className="flex items-center gap-2 bg-white text-gray-700 px-6 py-3 rounded-lg shadow-md hover:shadow-lg transition-shadow font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGeneratingSummary ? (
                <>
                  <div className="w-4 h-4 border-2 border-gray-700 border-t-transparent rounded-full animate-spin"></div>
                  <span>Generating Summary...</span>
                </>
              ) : (
                <>
                  <Download size={18} className="text-gray-700" />
                  <span>Download Report Summary</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}