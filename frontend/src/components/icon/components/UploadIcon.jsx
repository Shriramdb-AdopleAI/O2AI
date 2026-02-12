import React from 'react';
import PropTypes from 'prop-types';

const UploadIcon = ({ size = 24, color = 'currentColor', ...props }) => (
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
    <g filter="url(#filter0_d_4665_91011)">
    <path fillRule="evenodd" clipRule="evenodd" d="M40.4286 34.375C40.4286 27.6095 46.057 22.125 53 22.125C59.9429 22.125 65.5714 27.6095 65.5714 34.375V37.4375H68.7143C74.7894 37.4375 79.7143 42.2364 79.7143 48.1562C79.7143 54.0761 74.7894 58.875 68.7143 58.875H65.5714C63.8356 58.875 62.4286 60.2461 62.4286 61.9375C62.4286 63.6289 63.8356 65 65.5714 65H68.7143C78.261 65 86 57.4589 86 48.1562C86 39.8241 79.7913 32.9049 71.6359 31.5521C70.2423 22.744 62.4295 16 53 16C43.5706 16 35.7577 22.744 34.364 31.5521C26.2087 32.9049 20 39.8241 20 48.1562C20 57.4589 27.7391 65 37.2857 65H40.4286C42.1643 65 43.5714 63.6289 43.5714 61.9375C43.5714 60.2461 42.1643 58.875 40.4286 58.875H37.2857C31.2106 58.875 26.2857 54.0761 26.2857 48.1562C26.2857 42.2364 31.2106 37.4375 37.2857 37.4375H40.4286V34.375ZM64.6509 44.4595L55.2223 35.272C53.995 34.076 52.005 34.076 50.7777 35.272L41.3491 44.4595C40.1217 45.6554 40.1217 47.5946 41.3491 48.7905C42.5765 49.9864 44.5664 49.9864 45.7938 48.7905L49.8571 44.831V61.9375C49.8571 63.6289 51.2642 65 53 65C54.7358 65 56.1429 63.6289 56.1429 61.9375V44.831L60.2063 48.7905C61.4335 49.9864 63.4236 49.9864 64.6509 48.7905C65.8782 47.5946 65.8782 45.6554 64.6509 44.4595Z" fill="white"/>
    </g>
    <defs>
    <filter id="filter0_d_4665_91011" x="0" y="0" width="106" height="89" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
    <feFlood floodOpacity="0" result="BackgroundImageFix"/>
    <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/>
    <feOffset dy="4"/>
    <feGaussianBlur stdDeviation="10"/>
    <feComposite in2="hardAlpha" operator="out"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.2 0"/>
    <feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_4665_91011"/>
    <feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_4665_91011" result="shape"/>
    </filter>
    </defs>
    </svg>
);

UploadIcon.propTypes = {
  size: PropTypes.number,
  color: PropTypes.string,
};

export default UploadIcon;