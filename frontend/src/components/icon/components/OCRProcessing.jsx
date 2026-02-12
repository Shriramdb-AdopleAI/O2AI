import React from 'react';
import PropTypes from 'prop-types';

const OCRProcessing = ({ size = 24, color = 'currentColor', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    fill="none"
    viewBox="0 0 106 89"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path fillRule="evenodd" clipRule="evenodd" d="M13 12C13 7.58172 16.5817 4 21 4C25.4182 4 29 7.58172 29 12V14H31C34.866 14 38 17.134 38 21C38 24.866 34.866 28 31 28H29C27.8954 28 27 28.8954 27 30C27 31.1046 27.8954 32 29 32H31C37.0752 32 42 27.0752 42 21C42 15.5586 38.049 11.0399 32.8592 10.1565C31.9724 4.40426 27.0006 0 21 0C14.9995 0 10.0276 4.40426 9.14072 10.1565C3.95102 11.0399 0 15.5586 0 21C0 27.0752 4.92486 32 11 32H13C14.1046 32 15 31.1046 15 30C15 28.8954 14.1046 28 13 28H11C7.134 28 4 24.866 4 21C4 17.134 7.134 14 11 14H13V12ZM28.4142 18.5858L22.4142 12.5858C21.6332 11.8047 20.3668 11.8047 19.5858 12.5858L13.5858 18.5858C12.8047 19.3668 12.8047 20.6332 13.5858 21.4142C14.3668 22.1952 15.6332 22.1952 16.4142 21.4142L19 18.8284V30C19 31.1046 19.8954 32 21 32C22.1046 32 23 31.1046 23 30V18.8284L25.5858 21.4142C26.3668 22.1952 27.6332 22.1952 28.4142 21.4142C29.1952 20.6332 29.1952 19.3668 28.4142 18.5858Z" fill="white"/>
</svg>

);

OCRProcessing.propTypes = {
  size: PropTypes.number,
  color: PropTypes.string,
};

export default OCRProcessing;