/**
 * Authentication service for persistent user sessions.
 * Uses database storage instead of browser cache.
 */
class AuthService {
  constructor() {
    // Use environment variable for API base URL, fallback to localhost
    let apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8888';
    
    // If page is served over HTTPS, ensure API URL also uses HTTPS to avoid mixed content errors
    if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
      if (apiBaseUrl.startsWith('http://') && !apiBaseUrl.includes('localhost')) {
        apiBaseUrl = apiBaseUrl.replace('http://', 'https://');
      }
    }
    
    this.baseURL = `${apiBaseUrl}/api/v1`;
    this.currentUser = null;
    this.authToken = null;
    this.tenantId = null;
  }

  /**
   * Login user and create persistent session
   */
  async login(username, password) {
    try {
      const response = await fetch(`${this.baseURL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const data = await response.json();

        // Store session data in memory
        this.authToken = data.access_token;
        this.currentUser = data.user;
        this.tenantId = data.tenant_id;

        // Persist in localStorage across browser sessions
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('currentUser', JSON.stringify(data.user));
        localStorage.setItem('tenantId', data.tenant_id);

        return { success: true, user: data.user, tenantId: data.tenant_id };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Login failed' };
      }
    } catch (error) {
      return { success: false, error: 'Login error: ' + error.message };
    }
  }

  /**
   * Register new user
   */
  async register(username, email, password) {
    try {
      const response = await fetch(`${this.baseURL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, email, password }),
      });

      if (response.ok) {
        // Auto-login after registration
        return await this.login(username, password);
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Registration failed' };
      }
    } catch (error) {
      return { success: false, error: 'Registration error: ' + error.message };
    }
  }

  /**
   * Logout user and clear session
   */
  async logout() {
    try {
      if (this.authToken) {
        await fetch(`${this.baseURL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.authToken}`,
            'Content-Type': 'application/json',
          },
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear all session data
      this.authToken = null;
      this.currentUser = null;
      this.tenantId = null;

      // Clear storage
      localStorage.removeItem('authToken');
      localStorage.removeItem('currentUser');
      localStorage.removeItem('tenantId');
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!(this.authToken && this.currentUser && this.tenantId);
  }

  /**
   * Get current user
   */
  getCurrentUser() {
    return this.currentUser;
  }

  /**
   * Get tenant ID
   */
  getTenantId() {
    return this.tenantId;
  }

  /**
   * Get auth token
   */
  getAuthToken() {
    return this.authToken;
  }

  /**
   * Restore session from sessionStorage (for page refresh)
   */
  restoreSession() {
    const token = localStorage.getItem('authToken');
    const user = localStorage.getItem('currentUser');
    const tenant = localStorage.getItem('tenantId');

    if (token && user && tenant && token !== 'null' && token !== 'undefined') {
      try {
        this.authToken = token;
        this.currentUser = JSON.parse(user);
        this.tenantId = tenant;
        return true;
      } catch (error) {
        console.error('Failed to restore session:', error);
        // Clear corrupted data
        this.logout();
        return false;
      }
    }
    return false;
  }

  /**
   * Get auth headers for API calls
   */
  getAuthHeaders() {
    if (!this.authToken) {
      console.error('No auth token available');
      return {
        'Content-Type': 'application/json',
      };
    }
    return {
      'Authorization': `Bearer ${this.authToken}`,
      'Content-Type': 'application/json',
    };
  }

  /**
   * Get only Authorization header (use for FormData/multipart requests)
   */
  getAuthHeadersAuthOnly() {
    return {
      'Authorization': `Bearer ${this.authToken}`,
    };
  }

  /**
   * Check if user is admin
   */
  isAdmin() {
    return this.currentUser?.is_admin || false;
  }

  /**
   * Update user info (for profile updates)
   */
  updateUserInfo(userInfo) {
    this.currentUser = { ...this.currentUser, ...userInfo };
    localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
  }
}

// Create singleton instance
const authService = new AuthService();

export default authService;
