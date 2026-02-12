// src/components/AlertsCard.jsx
import React from 'react';
import { Bell } from 'lucide-react';
import { AlertsIcon } from './../icon';

const AlertsCard = ({ lowConfidenceFiles = [], onJumpToRows }) => {
  const alertCount = lowConfidenceFiles.length;

  return (
    <div className="bg-gradient-to-br from-[#0975BB] to-[#213E99] text-white rounded-2xl p-6 shadow-lg overflow-hidden relative ml-4">
      {/* Header with Bell Icon */}
      <div className="flex gap-2 mb-4 items-center justify-center">
        <div className='h-[50px] w-[50px]'>
            <AlertsIcon size={150} color="" title="AlertsIcon" />
        </div>
        <h3 className="text-2xl font-bold">Alerts</h3>
      </div>

      {/* Main Alert Content */}
      <div className="text-center">
        <div className="mb-4">
          <div className="flex items-center justify-center mb-2">
            <span className="text-[35px] font-bold leading-none mr-2">{alertCount}</span>
            <span className="text-[16px]">
              {alertCount === 1 ? 'File' : 'Files'} with <span className="font-semibold">Low-Confidence</span>
            <p className="text-[16px] opacity-90">pending review</p>
          </span>
          </div>
          
          {/* List of Low-Confidence Files */}
          {alertCount > 0 && (
            <div className="mt-3 max-h-[80px] overflow-y-auto text-left bg-white/10 rounded-lg p-2.5 space-y-1">
              {lowConfidenceFiles.map((file, index) => (
                <div key={index} className="text-sm py-1 border-b border-white/20 last:border-0">
                  <div className="font-medium truncate" title={file.fileName}>
                    {file.fileName}
                  </div>
                  <div className="text-xs opacity-90">
                    Accuracy: {file.accuracy}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* Jump to Rows Button */}
        <button 
          onClick={onJumpToRows}
          className="bg-white text-[#111827] hover:bg-gray-100 px-8 py-3 rounded-full font-semibold text-[14px] transition shadow-md mt-4"
        >
          Jump to rows
        </button>
      </div>

      {/* Optional subtle background shape (mimicking the screenshot) */}
      <div className="absolute bottom-0 right-0 w-48 h-48 bg-blue-800/30 rounded-full -mr-16 -mb-16"></div>
    </div>
  );
};

export default AlertsCard;