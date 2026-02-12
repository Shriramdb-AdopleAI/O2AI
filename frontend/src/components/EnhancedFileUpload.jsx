// EnhancedFileUpload.jsx
import React, { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadIcon } from './icon';
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  AlertCircle,
  Brain,
  Download,
  Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

// === SVG ICONS ===
const PdfIcon = ({ className = "h-6 w-6" }) => (
 <svg width="37" height="37" viewBox="0 0 37 37" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M30.7129 0H5.41992C2.42658 0 0 2.42658 0 5.41992V30.7129C0 33.7062 2.42658 36.1328 5.41992 36.1328H30.7129C33.7062 36.1328 36.1328 33.7062 36.1328 30.7129V5.41992C36.1328 2.42658 33.7062 0 30.7129 0Z" fill="#C80A0A"/>
 <path d="M16.8682 6.66602C17.8335 6.66613 18.4365 7.2198 18.7842 7.90527C19.126 8.57944 19.2354 9.39978 19.2354 10.0215C19.2353 11.5903 18.7442 13.6264 18.0547 15.7129C18.9515 17.4385 20.1289 19.0027 21.5391 20.3418C22.9015 20.1397 24.0797 20.0039 25.1953 20.0039C26.1615 20.0039 27.0134 20.0938 27.7109 20.2773C28.4038 20.4597 28.9677 20.741 29.3311 21.1436C29.7753 21.6282 29.953 22.3521 29.665 22.9707C29.3709 23.6025 28.6389 24.0321 27.4541 24.0322C26.283 24.0322 23.9361 23.668 21.2441 21.3682C19.1223 21.7583 17.0319 22.3037 14.9902 23.001C14.0794 24.6033 13.0287 26.1937 11.9268 27.3926C10.8173 28.5997 9.60628 29.4667 8.39941 29.4668C7.59442 29.4668 7.04088 29.1762 6.71289 28.7637C6.39198 28.3599 6.30388 27.8592 6.39062 27.4688C6.4569 27.0749 6.68131 26.681 7.0127 26.2959C7.35017 25.9038 7.81307 25.5042 8.37891 25.1045C9.49342 24.3173 11.0331 23.5105 12.874 22.7412C14.2064 20.1398 15.3569 17.4493 16.3164 14.6885C15.6618 13.219 15.2616 11.7823 15.1113 10.5449C14.9593 9.29227 15.0579 8.2044 15.4492 7.5L15.4541 7.49121L15.46 7.4834C15.7764 7.00873 16.2707 6.66602 16.8682 6.66602ZM12.0879 24.1016C10.764 24.6795 9.6713 25.2833 8.8623 25.8643C8.38747 26.2053 8.0162 26.5351 7.75293 26.8408C7.4895 27.1468 7.3474 27.414 7.30469 27.6348L7.2959 27.7607C7.29715 27.892 7.33042 28.0343 7.40234 28.1494C7.48999 28.2896 7.64051 28.4023 7.90527 28.4023C8.11845 28.4023 8.39658 28.3065 8.7373 28.085C9.07432 27.8657 9.45117 27.5367 9.85742 27.1045C10.5509 26.3667 11.3124 25.3447 12.0879 24.1016ZM26.8447 21.0645C26.0985 20.9407 24.4701 20.8717 22.4922 21.126C23.434 21.8461 24.5013 22.5059 25.7344 22.833L26.0244 22.9033L26.0322 22.9053C27.0697 23.1646 27.657 22.7188 27.8076 22.2734C27.8853 22.0438 27.86 21.7936 27.7178 21.5781C27.5759 21.3635 27.3024 21.1605 26.8447 21.0645ZM17.7119 16.8965C17.1514 18.5833 16.4527 20.2206 15.6221 21.792C17.21 21.2685 18.8285 20.8432 20.4688 20.5186C19.4338 19.4038 18.5106 18.1909 17.7119 16.8965ZM17.0469 7.67285C16.7896 7.55593 16.4604 7.63297 16.2354 7.96289C16.0261 8.36087 15.9017 9.10977 15.9961 10.1484C16.0764 11.0323 16.3146 12.104 16.7695 13.3047C17.3293 11.4832 17.6054 9.93761 17.6055 8.96289C17.6055 8.17087 17.3121 7.79347 17.0469 7.67285Z" fill="white" stroke="white" strokeWidth="0.5"/>
</svg>
);

const DocIcon = ({ className = "h-6 w-6" }) => (
 <svg width="37" height="34" viewBox="0 0 37 34" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M35.4186 2.19523e-06H10.178C9.97117 -0.000169605 9.76631 0.039979 9.57514 0.118156C9.38397 0.196333 9.21023 0.311007 9.06384 0.45563C8.91746 0.600254 8.80129 0.771995 8.72197 0.961048C8.64265 1.1501 8.60174 1.35276 8.60156 1.55746V8.5L23.2284 12.75L36.9964 8.5V1.55746C36.9962 1.35265 36.9553 1.14988 36.8759 0.960745C36.7965 0.771607 36.6802 0.599808 36.5336 0.455167C36.3871 0.310527 36.2132 0.19588 36.0219 0.11778C35.8306 0.0396803 35.6256 -0.000341519 35.4186 2.19523e-06Z" fill="#41A5EE"/>
<path d="M36.9964 8.5H8.60156V17L23.2284 19.55L36.9964 17V8.5Z" fill="#2B7CD3"/>
<path d="M8.60156 17V25.5L22.3682 27.2L36.9964 25.5V17H8.60156Z" fill="#185ABD"/>
<path d="M10.178 34H35.4173C35.6244 34.0005 35.8295 33.9606 36.021 33.8826C36.2124 33.8046 36.3865 33.69 36.5332 33.5453C36.6798 33.4006 36.7962 33.2288 36.8757 33.0396C36.9552 32.8503 36.9962 32.6475 36.9964 32.4425V25.5H8.60156V32.4425C8.60174 32.6472 8.64265 32.8499 8.72197 33.039C8.80129 33.228 8.91746 33.3997 9.06384 33.5444C9.21023 33.689 9.38397 33.8037 9.57514 33.8818C9.76631 33.96 9.97117 34.0002 10.178 34Z" fill="#103F91"/>
<path opacity="0.1" d="M19.0699 6.7998H8.60156V28.0498H19.0699C19.487 28.0477 19.8866 27.8831 20.1819 27.5916C20.4772 27.3001 20.6446 26.9051 20.6477 26.4923V8.35727C20.6446 7.94448 20.4772 7.54953 20.1819 7.25801C19.8866 6.96648 19.487 6.80186 19.0699 6.7998Z" fill="black"/>
<path opacity="0.2" d="M18.2097 7.6499H8.60156V28.8999H18.2097C18.6268 28.8978 19.0263 28.7332 19.3216 28.4417C19.617 28.1502 19.7843 27.7552 19.7874 27.3424V9.20736C19.7843 8.79458 19.617 8.39963 19.3216 8.10811C19.0263 7.81658 18.6268 7.65195 18.2097 7.6499Z" fill="black"/>
<path opacity="0.2" d="M18.2097 7.6499H8.60156V27.1999H18.2097C18.6268 27.1978 19.0263 27.0332 19.3216 26.7417C19.617 26.4502 19.7843 26.0552 19.7874 25.6424V9.20736C19.7843 8.79458 19.617 8.39963 19.3216 8.10811C19.0263 7.81658 18.6268 7.65195 18.2097 7.6499Z" fill="black"/>
<path opacity="0.2" d="M17.3494 7.6499H8.60156V27.1999H17.3494C17.7665 27.1978 18.1661 27.0332 18.4614 26.7417C18.7567 26.4502 18.9241 26.0552 18.9272 25.6424V9.20736C18.9241 8.79458 18.7567 8.39963 18.4614 8.10811C18.1661 7.81658 17.7665 7.65195 17.3494 7.6499Z" fill="black"/>
<path d="M1.57778 7.6499H17.353C17.7709 7.64956 18.1718 7.81341 18.4676 8.10545C18.7635 8.3975 18.9301 8.79383 18.9308 9.20737V24.7924C18.9301 25.206 18.7635 25.6023 18.4676 25.8944C18.1718 26.1864 17.7709 26.3502 17.353 26.3499H1.57778C1.37082 26.3502 1.16582 26.3102 0.974497 26.2321C0.783173 26.154 0.609278 26.0394 0.46275 25.8947C0.316221 25.7501 0.199933 25.5783 0.120532 25.3892C0.0411311 25.2 0.000173334 24.9973 0 24.7924V9.20737C0.000173334 9.00256 0.0411311 8.79979 0.120532 8.61065C0.199933 8.42151 0.316221 8.24971 0.46275 8.10507C0.609278 7.96043 0.783173 7.84578 0.974497 7.76768C1.16582 7.68958 1.37082 7.64956 1.57778 7.6499Z" fill="url(#paint0_linear_4792_88734)"/>
<path d="M6.47169 19.5998C6.50209 19.8404 6.52323 20.0497 6.53248 20.2288H6.56948C6.58269 20.0588 6.61176 19.8535 6.65537 19.6142C6.69898 19.3749 6.7373 19.1722 6.77298 19.0061L8.43137 11.9354H10.5774L12.2952 18.9002C12.3953 19.331 12.4668 19.7678 12.5093 20.2079H12.5384C12.5699 19.7795 12.6295 19.3536 12.7168 18.9329L14.0897 11.9263H16.0415L13.6312 22.0583H11.3491L9.71447 15.355C9.6669 15.1615 9.61317 14.9096 9.55326 14.5992C9.49336 14.2888 9.45636 14.0622 9.44226 13.9192H9.41451C9.39601 14.084 9.35901 14.3285 9.30351 14.6528C9.24801 14.9784 9.2044 15.2177 9.17137 15.3747L7.63455 22.0622H5.31412L2.89062 11.9354H4.87277L6.3673 19.0205C6.41191 19.2117 6.44675 19.4051 6.47169 19.5998Z" fill="white"/>
<defs>
<linearGradient id="paint0_linear_4792_88734" x1="3.29564" y1="6.4259" x2="15.4428" y2="27.6838" gradientUnits="userSpaceOnUse">
<stop stopColor="#2368C4"/>
<stop offset="0.5" stopColor="#1A5DBE"/>
<stop offset="1" stopColor="#1146AC"/>
</linearGradient>
</defs>
</svg>

);
// === END SVG ICONS ===

const EnhancedFileUpload = ({
  onFilesSelected,
  onProcessFiles,
  onExportExcel,
  processing = false,
  results = null,
  processedData = null,
  templates = [],
  selectedTemplateId = '',
  onSelectTemplate = () => {}
}) => {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [includeRawText, setIncludeRawText] = useState(true);
  const [includeMetadata, setIncludeMetadata] = useState(true);
  const [applyPreprocessing, setApplyPreprocessing] = useState(true);
  const [enhanceQuality, setEnhanceQuality] = useState(true);

  const [isFolderMode, setIsFolderMode] = useState(false);
  const folderInputRef = useRef(null);

  const handleModeSwitch = (newIsFolderMode) => {
    if (isFolderMode !== newIsFolderMode) {
      setIsFolderMode(newIsFolderMode);
      if (selectedFiles.length > 0) {
        setSelectedFiles([]);
        onFilesSelected([]);
      }
    }
  };

  const onDrop = useCallback(
    (acceptedFiles) => {
      if (isFolderMode) return;

      const newFiles = acceptedFiles.map((file) => ({
        file,
        id: Math.random().toString(36).substr(2, 9),
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'Pending',
        path: file.path || file.webkitRelativePath || ''
      }));

      setSelectedFiles((prev) => [...prev, ...newFiles]);
      onFilesSelected([...selectedFiles, ...newFiles]);
    },
    [selectedFiles, onFilesSelected, isFolderMode]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg']
    },
    multiple: true,
    noClick: isFolderMode,
    noKeyboard: isFolderMode
  });

  const handleFolderInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      const allowedTypes = [
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/jpg'
      ];

      const filteredFiles = filesArray.filter((file) => {
        const baseType = file.type || '';
        const extension = file.name.toLowerCase().split('.').pop();
        return (
          allowedTypes.includes(baseType) ||
          ['pdf', 'png', 'jpg', 'jpeg'].includes(extension)
        );
      });

      const newFiles = filteredFiles.map((file) => ({
        file,
        id: Math.random().toString(36).substr(2, 9),
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'Pending',
        path: file.path || file.webkitRelativePath || ''
      }));

      setSelectedFiles((prev) => [...prev, ...newFiles]);
      onFilesSelected([...selectedFiles, ...newFiles]);

      e.target.value = '';
    }
  };

  const handleFolderClick = (e) => {
    e.stopPropagation();
    folderInputRef.current?.click();
  };

  const removeFile = (fileId) => {
    const updatedFiles = selectedFiles.filter((f) => f.id !== fileId);
    setSelectedFiles(updatedFiles);
    onFilesSelected(updatedFiles);
  };

  const handleProcess = async () => {
    if (selectedFiles.length === 0) return;

    const formData = new FormData();

    if (selectedFiles.length === 1) {
      formData.append('file', selectedFiles[0].file);
    } else {
      selectedFiles.forEach((fileObj) => {
        formData.append('files', fileObj.file);
      });
    }

    formData.append('provider', 'azure_computer_vision');
    formData.append('apply_preprocessing', applyPreprocessing.toString());
    formData.append('enhance_quality', enhanceQuality.toString());
    formData.append('include_raw_text', includeRawText.toString());
    formData.append('include_metadata', includeMetadata.toString());

    await onProcessFiles(formData);
  };

  const handleExportExcel = async () => {
    if (selectedFiles.length === 0) return;
    if (processedData) {
      await onExportExcel(processedData);
    } else {
      console.log('No processed data available for export');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Updated: Returns SVG React component
  const getFileIcon = (fileType) => {
    if (fileType === 'application/pdf') {
      return <PdfIcon className="h-8 w-8 text-red-600" />;
    }
    if (fileType.startsWith('image/')) {
      return <DocIcon className="h-8 w-8 text-blue-600" />;
    }
    return <DocIcon className="h-8 w-8 text-gray-600" />;
  };

  return (
    <div className="w-full max-w-[900px] mx-auto px-2 sm:px-4">
      {/* Header: Mode Switch */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-3 sm:gap-0">
        <div className="text-[20px] sm:text-[24px] text-[#ffffff] font-semibold">Upload Files</div>
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <span className="text-sm text-[#ffffff] text-[14px] sm:text-[16px]">Mode:</span>
          <Button
            type="button"
            variant={!isFolderMode ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleModeSwitch(false)}
            disabled={processing}
            className="flex-1 sm:flex-none"
          >
            Files
          </Button>
          <Button
            type="button"
            variant={isFolderMode ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleModeSwitch(true)}
            disabled={processing}
            className="flex-1 sm:flex-none"
          >
            Folder
          </Button>
        </div>
      </div>

      {/* Dropzone / Folder Picker */}
      {isFolderMode ? (
        <div
          onClick={handleFolderClick}
          className={cn(
            'transpertant-blurBg rounded-lg p-4 sm:p-6 lg:p-8 text-center cursor-pointer transition-colors relative mt-3 flex flex-col items-center justify-center h-[250px] sm:h-[280px] lg:h-[300px]',
            processing && 'opacity-50 cursor-not-allowed'
          )}
        >
          <input
            ref={folderInputRef}
            type="file"
            webkitdirectory="true"
            directory=""
            multiple
            onChange={handleFolderInputChange}
            style={{ display: 'none' }}
            disabled={processing}
          />
          <UploadIcon size={80} color="" title="UploadIcon" className="sm:w-[106px] sm:h-[106px]" />
          <p className="font-medium mb-2 text-[#ffffff] text-[20px] sm:text-[24px] lg:text-[30px] font-semibold px-2">
            Click to select a folder
          </p>
          <p className="text-xs sm:text-sm italic text-[#ffffff] px-2">
            All supported files (PDF, PNG, JPG, JPEG) in the folder will be processed
          </p>
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={cn(
            'rounded-lg p-4 sm:p-6 lg:p-8 text-center cursor-pointer transition-colors transpertant-blurBg relative mt-3 flex flex-col items-center justify-center mb-3 h-[250px] sm:h-[280px] lg:h-[300px]',
            isDragActive && 'border-blue-500 bg-blue-50',
            processing && 'opacity-50 cursor-not-allowed'
          )}
        >
          <input {...getInputProps()} disabled={processing} />
          <UploadIcon size={80} color="" title="UploadIcon" className="sm:w-[106px] sm:h-[106px]" />
          <p className="text-[#ffffff] font-medium mb-2 text-[18px] sm:text-[20px] lg:text-[24px] px-2">
            {isDragActive ? 'Drop here...' : 'Drag & drop files here, or click to select'}
          </p>
          <p className="text-[#ffffff] italic text-[14px] sm:text-[16px] mb-4 px-2">
            Supports PDF, PNG, JPG, JPEG files
          </p>
        </div>
      )}

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-2 gap-2 sm:gap-0">
            <div className="text-[18px] sm:text-[20px] text-[#ffffff] font-semibold">
              Selected Files ({selectedFiles.length})
            </div>
            <button
              onClick={() => {
                setSelectedFiles([]);
                onFilesSelected([]);
              }}
              disabled={processing}
              className="text-[#fff] py-2 px-4 text-sm font-medium hover:underline"
            >
              Clear All
            </button>
          </div>

          <div className="space-y-2 max-h-[350px] overflow-y-auto">
            {selectedFiles.map((fileObj) => (
              <div
                key={fileObj.id}
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between py-3 sm:py-4 px-4 sm:px-6 bg-[#ffffff] rounded-lg shadow-sm gap-3 sm:gap-0"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0 w-full sm:w-auto">
                  {getFileIcon(fileObj.type)}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-[16px] sm:text-[18px] truncate text-[#111827]">
                      {fileObj.name}
                    </div>
                    <div className="text-[14px] sm:text-[16px] text-[#8180AA]">
                      {formatFileSize(fileObj.size)} • {fileObj.type}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2 flex-shrink-0 w-full sm:w-auto justify-between sm:justify-start">
                  <div className="text-[14px] sm:text-[16px] text-[#ffffff] font-medium bg-[#E4A316] py-2 px-4 sm:px-6 rounded-lg">
                    {fileObj.status}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeFile(fileObj.id)}
                    disabled={processing}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Action Buttons */}
      {selectedFiles.length > 0 && (
        <div className="w-full max-w-[250px] mx-auto mt-6">
          <button
            onClick={handleProcess}
            disabled={processing || selectedFiles.length === 0}
            className="bg-[#ffffff] text-[#192D4E] py-3 px-8 sm:px-12 text-[16px] sm:text-[18px] border-none rounded-lg font-semibold w-full hover:bg-[#E4E6EB] transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg flex items-center justify-center"
          >
            {processing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              'Process Files'
            )}
          </button>

          {processedData && (
            <div className="mt-4 p-3 bg-green-50 rounded-lg">
              <div className="flex items-center space-x-2 text-green-800">
                <CheckCircle className="h-4 w-4" />
                <span className="text-sm font-medium">
                  Processing complete - Excel export available
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EnhancedFileUpload;