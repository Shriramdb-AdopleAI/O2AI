import React from 'react';
import PropTypes from 'prop-types';

const AlertsIcon = ({ size = 24, color = 'currentColor', ...props }) => (
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
  <path fillRule="evenodd" clipRule="evenodd" d="M14.4599 25.1018C12.7506 27.7011 9.54648 28.624 7.31851 27.1589C5.09054 25.6938 4.66847 22.3862 6.3778 19.7869L14.4599 25.1018ZM25.5607 0.885905L24.5014 2.49672C28.7496 5.86896 29.4211 12.6205 25.8919 17.9872L23.3083 21.916C22.1684 23.6494 22.4497 25.8536 23.9354 26.8307L22.902 28.4022L0.00264608 13.3434L1.03609 11.7719C2.52185 12.7489 4.65714 12.1338 5.79703 10.4004L8.38066 6.47163C11.9099 1.10488 18.3749 -0.95357 23.1544 1.61091L24.2137 9.14603e-05L25.5607 0.885914L25.5607 0.885905Z" fill="white"/>
</svg>

);

AlertsIcon.propTypes = {
  size: PropTypes.number,
  color: PropTypes.string,
};

export default AlertsIcon;