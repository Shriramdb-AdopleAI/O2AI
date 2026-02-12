// src/components/Sidebar.jsx
import React from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { FaxLogo } from './icon';

const Sidebar = ({
  sidebarOpen,
  setSidebarOpen,
  navigationItems,
  activeTab,
  setActiveTab,
  hasSeenWelcome,
  setHasSeenWelcome,
  isCollapsed,
  setIsCollapsed,
}) => {

  const handleItemClick = (id) => {
    setActiveTab(id);

    // Close on mobile
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }

    // Auto‑dismiss Welcome on first nav click (keep existing logic)
    if (!localStorage.getItem('hasSeenWelcome')) {
      localStorage.setItem('hasSeenWelcome', 'true');
      setHasSeenWelcome(true);
    }
  };

  // NEW: Click logo/title → show Welcome
  const handleLogoClick = () => {
    if (isCollapsed) return; // Don't trigger when collapsed
    localStorage.removeItem('hasSeenWelcome');   // reset flag
    setHasSeenWelcome(false);
    setActiveTab('processing');                  // optional: go to processing
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <>
      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div
        className={`bg-[#0975BB] customeGradian-manu fixed inset-y-0 left-0 z-50 bg-white shadow-lg transform transition-all duration-300 ease-in-out ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          } lg:translate-x-0 ${isCollapsed ? 'lg:w-20 w-64' : 'w-64'}`}
      >
        {/* === LOGO + TITLE (clickable) === */}
        <div className="flex items-center justify-between h-16 px-4 sm:px-6">
          <button
            onClick={handleLogoClick}
            className={`flex items-center gap-2 mt-8 focus:outline-none ${isCollapsed ? 'lg:pointer-events-none' : ''}`}
            aria-label="Back to Welcome"
          >
            <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center">
              <FaxLogo size={24} color="" title="Fax" className="sm:w-8 sm:h-8" />
            </div>
            <h1 className={`text-[#ffffff] font-semibold text-[16px] sm:text-[18px] lg:text-[20px] hover:underline whitespace-nowrap ${isCollapsed ? 'lg:hidden' : ''}`}>
              Fax Automation
            </h1>
          </button>

          {/* Close button (mobile only) */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSidebarOpen(false)}
            className={`lg:hidden text-white hover:bg-white/20 ${isCollapsed ? 'lg:hidden' : ''}`}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* === NAVIGATION === */}
        <nav className="mt-4 flex-1">
          <div className="space-y-1">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full flex items-center ${isCollapsed ? 'lg:justify-center lg:px-2 px-3 sm:px-4' : 'px-3 sm:px-4'
                    } py-3 sm:py-4 transition-colors text-[14px] sm:text-[16px] ${activeTab === item.id
                      ? 'bg-blue-50 text-[#ffffff] menuHighlites font-medium'
                      : 'text-[#ffffff] hover:bg-white/10'
                    }`}
                  title={isCollapsed ? item.name : ''}
                >
                  <Icon className={`h-4 w-4 sm:h-5 sm:w-5 ${isCollapsed ? 'lg:mr-0 mr-2 sm:mr-3' : 'mr-2 sm:mr-3'}`} />
                  <span className={isCollapsed ? 'lg:hidden' : ''}>{item.name}</span>
                </button>
              );
            })}
          </div>
        </nav>

        {/* === TOGGLE BUTTON (bottom, desktop only) === */}
        <div className="absolute bottom-4 left-0 right-0 px-4 hidden lg:block">
          <button
            onClick={toggleCollapse}
            className="w-full flex items-center justify-center py-3 text-white/70 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
            aria-label={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="h-5 w-5" />
            ) : (
              <>
                <ChevronLeft className="h-5 w-5 mr-2" />
                <span className="text-sm">Toggle Sidebar</span>
              </>
            )}
          </button>
        </div>
      </div>
    </>
  );
};

export default Sidebar;