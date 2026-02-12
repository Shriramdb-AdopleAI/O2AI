// src/components/DatePickerButton.jsx
import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import { Calendar, ChevronDown } from 'lucide-react';

import 'react-datepicker/dist/react-datepicker.css'; // Import the styles

const DatePickerButton = ({
  date: initialDate, // Passed date string (optional)
  onDateChange,                     // Callback when user selects a new date
  className = '',
}) => {
  // Get current date in MM/DD/YYYY format (USA format)
  const getCurrentDateString = () => {
    const today = new Date();
    // Convert to EST timezone
    const estDate = new Date(today.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const month = String(estDate.getMonth() + 1).padStart(2, '0');
    const day = String(estDate.getDate()).padStart(2, '0');
    const year = estDate.getFullYear();
    return `${month}/${day}/${year}`;
  };

  // Convert initial date string (e.g., "12/18/2025" or "MM/DD/YYYY") to Date object
  const parseDate = (dateStr) => {
    if (!dateStr) return new Date();
    try {
      // Handle both MM/DD/YYYY and DD-MM-YYYY formats for backward compatibility
      if (dateStr.includes('/')) {
        const [month, day, year] = dateStr.split('/').map(Number);
        return new Date(year, month - 1, day); // month is 0-indexed
      } else if (dateStr.includes('-')) {
        // Legacy format support
        const [day, month, year] = dateStr.split('-').map(Number);
        return new Date(year, month - 1, day);
      }
      return new Date();
    } catch (e) {
      return new Date();
    }
  };

  // Use current date as default if no initialDate is provided
  const defaultDate = initialDate || getCurrentDateString();
  const [selectedDate, setSelectedDate] = useState(parseDate(defaultDate));
  const [isOpen, setIsOpen] = useState(false);

  // Sync selectedDate with the date prop when it changes
  useEffect(() => {
    if (initialDate) {
      const parsedDate = parseDate(initialDate);
      setSelectedDate(parsedDate);
    }
  }, [initialDate]);

  const handleClick = (e) => {
    e.preventDefault();
    setIsOpen(!isOpen); // Toggle calendar visibility
  };

  const handleDateChange = (date) => {
    setSelectedDate(date);
    setIsOpen(false); // Close calendar after selection

    // Optional: call parent callback
    if (onDateChange) {
      onDateChange(date);
    }
  };

  const formatDate = (date) => {
    // Format as MM/DD/YYYY (USA format)
    return date.toLocaleDateString('en-US', {
      month: '2-digit',
      day: '2-digit',
      year: 'numeric',
    });
  };

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        className={`bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg flex items-center gap-2 transition backdrop-blur ${className}`}
      >
        <Calendar className="w-5 h-5" />
        <span className='text-[14px]'>{formatDate(selectedDate)}</span>
        <ChevronDown className="w-4 h-4" />
      </button>

      {isOpen && (
        <div className="absolute top-full mt-2 left-0 z-50">
          <DatePicker
            selected={selectedDate}
            onChange={handleDateChange}
            inline                      // Shows calendar directly (no input field)
            calendarClassName="border shadow-lg rounded-lg bg-white"
          />
        </div>
      )}
    </div>
  );
};

export default DatePickerButton;