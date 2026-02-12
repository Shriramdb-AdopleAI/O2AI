// src/components/Header.jsx
import React, { useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ChevronDown, LogOut, Menu } from 'lucide-react';
import { OCRProcessing } from './icon';

const Header = ({
  currentUser,
  tenantId,
  onLogout,
  sidebarOpen,
  setSidebarOpen,
  hasSeenWelcome,
  setHasSeenWelcome,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const getAvatarLetter = () => {
    return currentUser?.username?.charAt(0).toUpperCase() || 'U';
  };

  // NEW: Click logo → show Welcome
  const handleLogoClick = () => {
    localStorage.removeItem('hasSeenWelcome');
    setHasSeenWelcome(false);
    // setSidebarOpen(false); // optional: close sidebar on mobile
  };

  return (
    <header className="px-4 sm:px-6 lg:px-8 pt-4 flex items-center justify-between mb-4">
      {/* LOGOS – CLICKABLE */}
      <button
        onClick={handleLogoClick}
        className="focus:outline-none flex items-center gap-2 sm:gap-3"
        aria-label="Back to Welcome"
      >
        <img
          src="/o2Logo.svg"
          alt="Logo"
          width={100}
          height={42}
          className="hidden sm:block hover:opacity-80 transition-opacity w-20 sm:w-24 lg:w-[100px]"
        />
        <div className="w-[50px] h-[50px] sm:w-[70px] sm:h-[70px] flex items-center justify-center overflow-visible">
          <OCRProcessing size={50} color="" title="OCRProcessing" className="w-full h-full sm:w-[70px] sm:h-[70px]" />
        </div>
      </button>

      {/* Right Side: Avatar + Dropdown + Mobile Menu */}
      <div className="flex items-center space-x-2 sm:space-x-4">
        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* User Avatar + Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex items-center space-x-1 sm:space-x-2 rounded-lg p-1 sm:p-2 transition-colors"
            aria-label="User menu"
          >
            {/* Avatar Circle */}
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs sm:text-sm font-semibold">
              {getAvatarLetter()}
            </div>

            {/* User Info (hidden on mobile) */}
            <div className="hidden sm:flex flex-col items-start leading-[1.2]">
              <span className="text-[14px] sm:text-[16px] text-gray-700 font-medium truncate max-w-[120px] lg:max-w-none">
                {currentUser?.username}
              </span>
              {tenantId && (
                <span className="text-[12px] sm:text-[14px] text-gray-500">
                  {tenantId.substring(0, 8)}...
                </span>
              )}
            </div>

            {/* Down Arrow */}
            <ChevronDown
              className={`h-3 w-3 sm:h-4 sm:w-4 text-gray-600 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''
                }`}
            />
          </button>

          {/* Dropdown Menu */}
          {isDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsDropdownOpen(false)}
              />
              <div className="absolute right-0 mt-2 w-40 sm:w-48 bg-white rounded-md shadow-lg border border-gray-200 z-50">
                <div className="py-1">
                  <button
                    onClick={() => {
                      onLogout();
                      setIsDropdownOpen(false);
                    }}
                    className="w-full px-3 sm:px-4 py-2 text-left text-xs sm:text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                  >
                    <LogOut className="h-3 w-3 sm:h-4 sm:w-4" />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;