/**
 * Epic FHIR Write Service
 * Handles token exchange and storing Observation resources in Epic FHIR system
 */

const EPIC_WRITE_TOKEN_KEY = 'epic_write_token';

// Get API base URL from environment
const getApiBaseUrl = () => {
  let apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8888';
  
  // If page is served over HTTPS, ensure API URL also uses HTTPS to avoid mixed content errors
  if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
    if (apiBaseUrl.startsWith('http://') && !apiBaseUrl.includes('localhost')) {
      apiBaseUrl = apiBaseUrl.replace('http://', 'https://');
    }
  }
  
  return `${apiBaseUrl}/api/v1`;
};

/**
 * Get stored Epic write token from localStorage
 */
export const getEpicWriteToken = () => {
  try {
    return localStorage.getItem(EPIC_WRITE_TOKEN_KEY);
  } catch (e) {
    console.warn('Failed to get Epic write token from localStorage:', e);
    return null;
  }
};

/**
 * Store Epic write token in localStorage
 */
export const setEpicWriteToken = (token) => {
  try {
    if (token) {
      localStorage.setItem(EPIC_WRITE_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(EPIC_WRITE_TOKEN_KEY);
    }
  } catch (e) {
    console.warn('Failed to store Epic write token in localStorage:', e);
  }
};

/**
 * Exchange Epic authorization code for access token
 * @param {string} code - Authorization code from Epic OAuth callback
 * @returns {Promise<{access_token: string, token_type?: string, expires_in?: number}>}
 */
export const exchangeEpicToken = async (code) => {
  const apiBaseUrl = getApiBaseUrl();
  
  try {
    // Get auth token from authService if available
    const authHeaders = {};
    try {
      const authService = (await import('./authService')).default;
      const headers = authService.getAuthHeaders();
      Object.assign(authHeaders, headers);
    } catch (e) {
      // authService not available, continue without auth headers
      console.warn('Could not get auth headers:', e);
    }

    const response = await fetch(`${apiBaseUrl}/epic/exchange-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Failed to exchange token: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error exchanging Epic token:', error);
    throw error;
  }
};


