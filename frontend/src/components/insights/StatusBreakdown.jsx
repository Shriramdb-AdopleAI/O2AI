// src/components/StatusBreakdown.jsx
import React from 'react';

const StatusBreakdown = ({ 
  data = [
    { label: 'Successful Scans', value: 82, total: 100, color: 'blue' },
    { label: 'Failed / Error Files', value: 6, total: 100, color: 'red' },
    { label: 'Manual Review', value: 12, total: 100, color: 'orange' },
  ]
}) => {
  const getProgressColor = (color) => {
    switch (color) {
      case 'blue': return 'bg-blue-600';
      case 'red': return 'bg-red-600';
      case 'orange': return 'bg-orange-500';
      default: return 'bg-blue-600';
    }
  };

  const getTextColor = (color) => {
    switch (color) {
      case 'blue': return 'text-blue-600';
      case 'red': return 'text-red-600';
      case 'orange': return 'text-orange-600';
      default: return 'text-blue-600';
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm p-10 h-[370px]">
      {/* Title */}
      <h2 className="text-[#111827] font-semibold text-[22px]">Status Breakdown</h2>
      <p className="text-[#6B7280] text-[14px] mb-8">File Scan Status Overview</p>

      {/* Dynamic Progress Bars */}
      <div className="space-y-8">
        {data.map((item, index) => {
          const percentage = item.total ? (item.value / item.total) * 100 : 0;

          return (
            <div key={index}>
              <div className="flex justify-between items-center mb-3">
                <div className="font-medium text-gray-800 text-[16px] w-[250px]">{item.label}:</div>
                <div className={`font-semibold text-lg w-[50px] ${getTextColor(item.color)}`}>
                  {item.value}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-5 overflow-hidden">
                <div
                  className={`${getProgressColor(item.color)} h-full rounded-full transition-all duration-700 ease-out`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
              </div>

              {/* Progress Bar */}
              
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StatusBreakdown;