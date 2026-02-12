import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Users, 
  UserPlus, 
  Edit, 
  Trash2, 
  Shield, 
  ShieldOff, 
  CheckCircle, 
  XCircle,
  RefreshCw
} from 'lucide-react';
import authService from '../services/authService';

const AdminDashboard = ({ onLogout }) => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingUser, setEditingUser] = useState(null);
  
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
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    is_admin: false
  });

  // Load users on component mount
  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');
      
      // Ensure session is restored
      if (!authService.getAuthToken()) {
        authService.restoreSession();
      }
      
      const headers = authService.getAuthHeaders();
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/users`, {
        headers: headers
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data);
        setError(''); // Clear any previous errors
      } else {
        // Try to get error message from response
        let errorMessage = `Failed to load users (${response.status})`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
          // If response is not JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }
        
        // If 403, provide more helpful message
        if (response.status === 403) {
          errorMessage = 'Access denied: Admin privileges required. Please ensure you are logged in as an admin user.';
        }
        
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setError('Error loading users: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newUser)
      });

      if (response.ok) {
        setSuccess('User created successfully');
        setNewUser({ username: '', email: '', password: '', is_admin: false });
        setShowAddUser(false);
        loadUsers();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to create user');
      }
    } catch (error) {
      setError('Error creating user: ' + error.message);
    }
  };

  const handleUpdateUser = async (userId, updates) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/users/${userId}`, {
        method: 'PUT',
        headers: authService.getAuthHeaders(),
        body: JSON.stringify(updates)
      });

      if (response.ok) {
        setSuccess('User updated successfully');
        setEditingUser(null);
        loadUsers();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to update user');
      }
    } catch (error) {
      setError('Error updating user: ' + error.message);
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!confirm('Are you sure you want to delete this user?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/users/${userId}`, {
        method: 'DELETE',
        headers: authService.getAuthHeaders()
      });

      if (response.ok) {
        setSuccess('User deleted successfully');
        loadUsers();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to delete user');
      }
    } catch (error) {
      setError('Error deleting user: ' + error.message);
    }
  };

  const toggleUserStatus = (user) => {
    handleUpdateUser(user.id, { is_active: !user.is_active });
  };

  const toggleAdminStatus = (user) => {
    handleUpdateUser(user.id, { is_admin: !user.is_admin });
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
              <p className="text-gray-600 mt-2">Manage users and system settings</p>
            </div>
            <div className="flex space-x-3">
              <Button onClick={loadUsers} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <Button onClick={onLogout} variant="outline">
                Logout
              </Button>
            </div>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <XCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="mb-6 border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">{success}</AlertDescription>
          </Alert>
        )}

        {/* Add User Form */}
        {showAddUser && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center">
                <UserPlus className="h-5 w-5 mr-2" />
                Add New User
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAddUser} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      value={newUser.username}
                      onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={newUser.email}
                      onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      value={newUser.password}
                      onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                      required
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="is_admin"
                      checked={newUser.is_admin}
                      onChange={(e) => setNewUser({...newUser, is_admin: e.target.checked})}
                      className="rounded"
                    />
                    <Label htmlFor="is_admin">Admin User</Label>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <Button type="submit">Create User</Button>
                  <Button type="button" variant="outline" onClick={() => setShowAddUser(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Users List */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Users ({users.length})
              </CardTitle>
              <Button onClick={() => setShowAddUser(true)}>
                <UserPlus className="h-4 w-4 mr-2" />
                Add User
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-gray-400" />
                <p className="text-gray-500">Loading users...</p>
              </div>
            ) : (
              <div className="space-y-4">
                {users.map((user) => (
                  <div key={user.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3">
                        <div>
                          <h3 className="font-medium text-gray-900">{user.username}</h3>
                          <p className="text-sm text-gray-500">{user.email}</p>
                        </div>
                        <div className="flex space-x-2">
                          <Badge variant={user.is_active ? "default" : "secondary"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </Badge>
                          {user.is_admin && (
                            <Badge variant="destructive">Admin</Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Created: {new Date(user.created_at).toLocaleDateString()}
                        {user.last_login && (
                          <span className="ml-4">
                            Last login: {new Date(user.last_login).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleUserStatus(user)}
                        className={user.is_active ? "text-red-600" : "text-green-600"}
                      >
                        {user.is_active ? (
                          <ShieldOff className="h-4 w-4" />
                        ) : (
                          <Shield className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleAdminStatus(user)}
                        className={user.is_admin ? "text-orange-600" : "text-blue-600"}
                      >
                        {user.is_admin ? "Remove Admin" : "Make Admin"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteUser(user.id)}
                        className="text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AdminDashboard;
