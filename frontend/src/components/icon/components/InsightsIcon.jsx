import React from 'react';
import PropTypes from 'prop-types';

const InsightsIcon = ({ size = 24, color = 'currentColor', ...props }) => (
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
    <path d="M20 45C8.90909 45 0 35.8125 0 24.375C0 13.6875 8 4.875 18.1818 3.75V0H20C27.4545 0 34.3636 3.5625 38.9091 9.75L40 11.25L37.0909 13.5C38.9091 16.875 40 20.4375 40 24.375C40 35.8125 31.0909 45 20 45ZM18.1818 7.6875C10 8.625 3.63636 15.75 3.63636 24.375C3.63636 33.75 10.9091 41.25 20 41.25C29.0909 41.25 36.3636 33.75 36.3636 24.375C36.3636 21.375 35.6364 18.375 34.1818 15.75L18.1818 28.125V7.6875ZM21.8182 3.75V20.625L34.9091 10.5C31.4545 6.75 26.7273 4.3125 21.8182 3.75Z" fill="white"/>
</svg>

);

InsightsIcon.propTypes = {
  size: PropTypes.number,
  color: PropTypes.string,
};

export default InsightsIcon;