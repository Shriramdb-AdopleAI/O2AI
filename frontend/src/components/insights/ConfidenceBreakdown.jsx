// src/components/ConfidenceBreakdown.jsx
import React from 'react';

const ConfidenceBreakdown = ({ 
  data = [
    { label: 'High-confidence ≥ 95%', value: 82, color: 'green' },
    { label: 'High-Medium (90-94.9%)', value: 10, color: 'orange' },
    { label: 'Medium-Low < 89.9%', value: 5, color: 'red' },
  ]
}) => {
  const getColorClass = (color) => {
    switch (color) {
      case 'green': return 'text-green-600 stroke-green-500';
      case 'orange': return 'text-orange-600 stroke-orange-500';
      case 'red': return 'text-red-600 stroke-red-500';
      default: return 'text-blue-600 stroke-blue-500';
    }
  };

  const getConfidenceLabel = (color) => {
    switch (color) {
      case 'green': return ['High', 'Confidence', 'File'];
      case 'orange': return ['Medium', 'Confidence', 'File'];
      case 'red': return ['Low', 'Confidence', 'file'];
      default: return ['Confidence', 'File'];
    }
  };

  return (
    <div className="flex gap-6 items-center  h-[300px]">
      <h2 className="text-[22px] font-semibold w-[180px]">Confidence Breakdown Analytics</h2>
      
      <div className="grid grid-cols-3 gap-8">
        {data.map((item, index) => {
          const circumference = 2 * Math.PI * 56; // Circle radius 56
          const progress = circumference - ((item.value / 100) * circumference); // Assuming total 100 for %

          return (
            <div key={index} className="text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg className="w-40 h-40 transform -rotate-90" viewBox="0 0 128 128">
                  {/* Background Circle */}
                  <circle cx="64" cy="64" r="56" stroke="#e5e7eb" strokeWidth="12" fill="none" />
                  
                  {/* Progress Arc */}
                  <circle 
                    cx="64" 
                    cy="64" 
                    r="56" 
                    strokeLinecap="round"
                    strokeWidth="12" 
                    fill="none"
                    strokeDasharray={circumference}
                    strokeDashoffset={progress}
                    className={getColorClass(item.color).split(' ')[1]} // Only stroke class
                  />
                </svg>
                
                {/* Centered Text */}
                <div className="absolute inset-0 flex flex-col items-center justify-center px-2">
                  <span className={`text-4xl font-bold text-gray-700 leading-none mb-1.5`}>
                    {item.value.toString().padStart(2, '0')}
                  </span>
                  <div className="text-xs text-gray-600 text-center leading-tight max-w-[85px]">
                    {getConfidenceLabel(item.color).map((word, idx) => (
                      <div key={idx} className="leading-tight">
                        {word}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* Subtitle Below */}
              <p className="mt-4 text-[16px] text-[#34334B]">{item.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ConfidenceBreakdown;