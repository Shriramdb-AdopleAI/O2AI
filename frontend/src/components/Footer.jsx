// src/components/Footer.jsx
import React from 'react';

const Footer = () => {
  return (
    <footer className="text-center p-2 sm:p-4 mt-auto text-xs sm:text-sm subtitle opacity-90 bacgroundColorSt">
      <div className="mt-2 text-center px-2 sm:px-4 text-gray-500 max-w-6xl mx-auto flex flex-col items-center">
        <span className="font-medium">Warning: Disclaimer:</span>
        <span className="text-[10px] sm:text-xs">
          This content is AI-generated. Please review carefully and use your judgment before making decisions.
        </span>
      </div>
      <p className="text-gray-500 text-[10px] sm:text-xs mt-1">© 2026. All rights reserved.</p>
    </footer>
  );
};

export default Footer;