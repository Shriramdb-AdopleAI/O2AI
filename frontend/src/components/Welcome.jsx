import React from 'react';
import { FaxLogo, LoganimationsIconWhite } from './icon';

const Welcome = ({ onStartProcessing }) => {
  return (
    <div className="flex flex-col lg:flex-row items-center mx-auto w-full gap-6 lg:gap-12 height-full-calc px-4 sm:px-6 lg:px-0">
      {/* Left image */}
      <div className="flex-shrink-0 w-full lg:w-[45%] width-100-fix flex items-center justify-center" >
        <div className='customewelcomImg w-full flex items-center justify-center'>
          <img
            src="/welcomPage.png"
            alt="Welcome illustration"
            width={500}
            className="hidden sm:block w-full h-auto max-w-md mx-auto lg:max-w-none"
          />
        </div>
      </div>

      {/* Right content */}
      <div className="flex flex-col w-full lg:w-[55%] justify-center text-center lg:text-left px-2 sm:px-4 lg:px-0">
       <div className="flex justify-center lg:justify-start mb-4 sm:mb-6">
         <LoganimationsIconWhite size={70} animationSpeed={6} className="sm:w-[90px] sm:h-[90px] w-[70px] h-[70px]" />
       </div>

        <h2 className="text-[28px] sm:text-[36px] lg:text-[48px] xl:text-[60px] text-white leading-[1.2] font-bold mb-4 sm:mb-6">
          Welcome to Fax <br className="hidden sm:block" />Automation Platform
        </h2>

        <p className="text-[14px] sm:text-[15px] lg:text-[16px] text-white/95 mt-2 sm:mt-4 max-w-2xl mx-auto lg:mx-0 leading-relaxed">
          Transform Traditional Faxing into a Smart Digital Workflow. AI-powered scanning converts printed and handwritten fax content into text. Trace documents, extract insights, and summarize multiple files instantly.
        </p>

        {/* Button now triggers processing */}
        <button
          onClick={onStartProcessing}
          className="bg-white py-3 px-6 sm:px-8 mt-6 sm:mt-8 rounded-md text-[14px] sm:text-[16px] font-medium text-[#192D4E] hover:bg-gray-100 transition-colors self-center lg:self-start w-full sm:w-auto max-w-xs sm:max-w-none"
        >
          Processing Fax Automations
        </button>
      </div>
    </div>
  );
};

export default Welcome;