// src/components/RecentActivities.jsx
import React, { useMemo, useState, useEffect } from 'react';
import { CheckCircle2, UserCheck, AlertTriangle, RefreshCw } from 'lucide-react';
import authService from '../../services/authService';

const RecentActivities = ({ files = [] }) => {
  // Get API base URL - ensure HTTPS when page is served over HTTPS
  const getApiBaseUrl = () => {
    let apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8888';
    // If page is served over HTTPS, ensure API URL also uses HTTPS to avoid mixed content errors
    if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
      if (apiBaseUrl.startsWith('http://') && !apiBaseUrl.includes('localhost')) {
        apiBaseUrl = apiBaseUrl.replace('http://', 'https://');
      }
    }
    return apiBaseUrl;
  };
  const API_BASE_URL = getApiBaseUrl();
  
  const [availableUsers, setAvailableUsers] = useState([]);

  // Load users from database (admin only)
  useEffect(() => {
    const loadUsers = async () => {
      // Only make the request if user is admin
      if (!authService.isAdmin()) {
        setAvailableUsers([]);
        return;
      }

      try {
        const headers = authService.getAuthHeaders();
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/users`, {
          headers
        });

        if (response.ok) {
          const data = await response.json();
          setAvailableUsers(Array.isArray(data) ? data : []);
        } else {
          setAvailableUsers([]);
        }
      } catch (error) {
        console.error('Error loading users:', error);
        setAvailableUsers([]);
      }
    };

    loadUsers();
  }, []);

  // Get user initial from user ID by fetching from database
  const getUserInitial = (userId) => {
    if (!userId || userId === 'unassigned') return '?';
    
    // Convert userId to string/number for comparison
    const userIdStr = String(userId);
    const userIdNum = Number(userId);
    
    // Try to find user in availableUsers by multiple possible ID fields
    const user = availableUsers.find(u => {
      return (
        String(u.id) === userIdStr ||
        String(u.user_id) === userIdStr ||
        String(u.id) === String(userIdNum) ||
        String(u.user_id) === String(userIdNum) ||
        u.username === userIdStr ||
        u.email === userIdStr
      );
    });
    
    if (user) {
      // Get username from user object (try multiple fields)
      const username = user.username || user.name || user.full_name || user.display_name || user.email || '';
      
      if (username) {
        // Remove any leading/trailing whitespace and get first letter
        const trimmedUsername = username.trim();
        if (trimmedUsername.length > 0) {
          return trimmedUsername.charAt(0).toUpperCase();
        }
      }
    }
    
    // If user not found, return '?' to indicate we need to fetch
    return '?';
  };

  // Calculate dynamic statistics
  const stats = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    // Files completed today
    const completedToday = files.filter(file => {
      if (file.status !== 'Completed') return false;
      if (!file.lastModified) return false;
      const fileDate = new Date(file.lastModified);
      fileDate.setHours(0, 0, 0, 0);
      return fileDate.getTime() === today.getTime();
    }).length;

    // Group files by assigned user for manual review
    const userReviewCounts = {};
    files.forEach(file => {
      if (file.status === 'Review Needed' && file.assignedUserValue && file.assignedUserValue !== 'unassigned') {
        const userId = file.assignedUserValue;
        if (!userReviewCounts[userId]) {
          // Fetch user initial from database using userId
          const userInitial = getUserInitial(userId);
          userReviewCounts[userId] = {
            userId: userId,
            userInitial: userInitial,
            count: 0
          };
        }
        userReviewCounts[userId].count++;
      }
    });

    // Convert to array and sort by count (descending)
    const userReviewList = Object.values(userReviewCounts)
      .sort((a, b) => b.count - a.count)
      .slice(0, 5); // Show top 5 users

    // Files not updated (unassigned or in progress)
    const notUpdated = files.filter(file => 
      file.assignedUserValue === 'unassigned' || 
      file.status === 'In Progress' ||
      (!file.assignedUserValue && file.status !== 'Completed')
    ).length;

    return {
      completedToday,
      userReviewList,
      notUpdated
    };
  }, [files, availableUsers]);

  return (
    <div className="bg-gradient-to-br from-[#213E99]  to-[#039FD3] text-white rounded-2xl shadow-lg overflow-hidden relative h-[370px]">
      {/* Header */}
      <h2 className="text-[22px] font-bold mb-6 py-8 px-10 bg-[#2F2AB1] relative">Recent Activities
        <img src="/shadow-bt.png" alt="Recent Activities Icon" className="inline-block w-[100%] h-6 ml-3 mb-1 absolute left-0 right-0 bottom-[-2px] m-auto " />
      </h2>
    
      {/* Activity List */}
      <div className="space-y-2 mb-8 px-10">
        {/* Completed Today */}
        <div className="flex items-start gap-3">
          <CheckCircle2 className="w-7 h-7 text-white mt-0.5 flex-shrink-0" />
          <p className="text-[16px]">
            <span className="font-semibold">Completed {stats.completedToday} file{stats.completedToday !== 1 ? 's' : ''} today</span>
          </p>
        </div>

        {/* User Assignments for Manual Review */}
        {stats.userReviewList.map((user, index) => (
          <div key={user.userId || index} className="flex items-start gap-3">
            {index === 0 ? (
              <UserCheck className="w-7 h-7 text-white mt-0.5 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-7 h-7 text-yellow-300 mt-0.5 flex-shrink-0" />
            )}
            <p className="text-[16px]">
              User{' '}
              <span className="inline-flex items-center justify-center w-8 h-8 bg-blue-500 rounded-full font-bold text-white mx-1">
                {user.userInitial}
              </span>{' '}
              {user.count} file{user.count !== 1 ? 's' : ''} for manual review
            </p>
          </div>
        ))}

        {/* Show message if no users have files for review */}
        {stats.userReviewList.length === 0 && (
          <div className="flex items-start gap-3">
            <UserCheck className="w-7 h-7 text-white mt-0.5 flex-shrink-0" />
            <p className="text-[16px]">
              <span className="font-semibold">No files assigned for manual review</span>
            </p>
          </div>
        )}

        {/* Pending Updates */}
        <div className="flex items-start gap-3">
          <RefreshCw className="w-7 h-7 text-white mt-0.5 flex-shrink-0" />
          <p className="text-[16px]">
            <span className="">{stats.notUpdated} file{stats.notUpdated !== 1 ? 's' : ''} still not updated</span>
          </p>
        </div>
      </div>

      {/* Illustration at the bottom right */}
      <div className="flex justify-end absolute  right-[30px] bottom-[25px] m-auto">
        <img src="/recentActivities.png" alt="Recent Activities" className="w-full rounded-lg w-[127px]"  />
        {/* If you prefer SVG or local asset, replace the src above */}
      </div>
    </div>
  );
};

export default RecentActivities;