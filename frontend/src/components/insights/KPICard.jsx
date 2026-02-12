// src/components/KPICard.jsx
import React from 'react';

const KPICard = ({
  title,
  value,
  subtitle,
  icon: Icon,          // Lucide icon component
  valueSize = 'text-[36px]',  // Default large for most, smaller for Last Updated
}) => {
  return (
    <div className="bg-white/20 backdrop-blur rounded-xl p-6 transition-all hover:bg-white/30">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-blue-100 text-[16px] font-semibold">{title}</p>
          <p className={`${valueSize} font-semibold text-white h-[54px] content-center`}>{value}</p>
          <p className="text-blue-200 text-[14px] ">{subtitle}</p>
        </div>
        <div className='w-[60px] h-[70px] overflow-hidden'>
            {Icon && <Icon  size={110} color="" />}
        </div>
      </div>
    </div>
  );
};

export default KPICard;