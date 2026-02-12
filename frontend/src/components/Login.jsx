import React, { useState } from 'react';
import { useMsal } from '@azure/msal-react';
import { loginRequest } from '../services/authConfig';
import { initiateEpicLogin } from '../services/epicAuthConfig';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { User, Lock, Mail, Eye, EyeOff } from 'lucide-react';

const Login = ({ onLogin, onRegister, isLoading = false, authError = '', onMicrosoftLogin, onEpicLogin }) => {
  // MSAL hook
  let msalContext = null;
  try {
    msalContext = useMsal();
  } catch (e) {
    // Not in MSALProvider context
    msalContext = null;
  }

  const handleMicrosoftLogin = async () => {
    if (!msalContext) return;
    try {
      // Force account chooser every time by setting prompt: 'select_account'
      // Use loginRedirect to ensure users are correctly directed to the authorized production domain
      await msalContext.instance.loginRedirect({
        ...loginRequest,
        prompt: 'select_account'
      });
      // Note: onMicrosoftLogin callback is not called here because the page redirects
    } catch (error) {
      console.error('Microsoft login error:', error);
    }
  };

  const handleEpicLogin = () => {
    try {
      // Check if Epic is configured
      const epicClientId = import.meta.env.VITE_EPIC_CLIENT_ID;
      const epicRedirectUri = import.meta.env.VITE_EPIC_REDIRECT_URI;

      if (!epicClientId || epicClientId.trim() === '') {
        const errorMsg = 'Epic OAuth is not configured.\n\nPlease set VITE_EPIC_CLIENT_ID in your frontend .env file.\n\nCheck EPIC_ENV_SETUP.md for setup instructions.';
        alert(errorMsg);
        console.error('Epic Client ID is missing');
        return;
      }

      if (!epicRedirectUri || epicRedirectUri.trim() === '') {
        const errorMsg = 'Epic Redirect URI is not configured.\n\nPlease set VITE_EPIC_REDIRECT_URI in your frontend .env file.\n\nIMPORTANT: This must match EXACTLY what is registered in Epic App Orchard (including trailing slash).\n\nCheck EPIC_ENV_SETUP.md for setup instructions.';
        alert(errorMsg);
        console.error('Epic Redirect URI is missing');
        return;
      }

      // Show configuration for debugging
      console.log('=== Epic Login Configuration Check ===');
      console.log('Client ID:', epicClientId ? 'SET' : 'NOT SET');
      console.log('Redirect URI:', epicRedirectUri);
      console.log('Authorization URL:', import.meta.env.VITE_EPIC_AUTHORIZATION_URL || 'Using default');
      console.log('=====================================');
      console.log('\n⚠️  IMPORTANT: Verify the Redirect URI above matches EXACTLY what is registered in Epic App Orchard.');
      console.log('   Even a trailing slash difference will cause the error you are seeing.\n');

      if (onEpicLogin) {
        onEpicLogin();
      } else {
        initiateEpicLogin();
      }
    } catch (error) {
      console.error('Error initiating Epic login:', error);
      alert('Failed to initiate Epic login. Please check the console for details.');
    }
  };
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!isLoginMode) {
      if (!formData.email.trim()) {
        newErrors.email = 'Email is required';
      } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
        newErrors.email = 'Email is invalid';
      }
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    } else if (formData.password.length > 72) {
      newErrors.password = 'Password cannot be longer than 72 characters';
    }

    if (!isLoginMode && formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      if (isLoginMode) {
        await onLogin(formData.username, formData.password);
      } else {
        await onRegister(formData.username, formData.email, formData.password);
      }
    } catch (error) {
      console.error('Authentication error:', error);
    }
  };

  const toggleMode = () => {
    setIsLoginMode(!isLoginMode);
    setFormData({
      username: '',
      email: '',
      password: '',
      confirmPassword: ''
    });
    setErrors({});
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 bg-blue-600 rounded-full flex items-center justify-center">
            <User className="h-6 w-6 text-white" />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
            {isLoginMode ? 'Sign in to your account' : 'Create your account'}
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            {isLoginMode
              ? 'Access your OCR processing dashboard'
              : 'Start processing documents with AI-powered OCR'
            }
          </p>
        </div>

        {/* Microsoft Login Button */}
        <div className="flex flex-col gap-2">
          {!msalContext && (
            <Alert variant="destructive" className="mb-2">
              <AlertDescription>
                Microsoft login is not available. Please use HTTPS or localhost to enable Azure AD authentication.
              </AlertDescription>
            </Alert>
          )}
          <Button
            type="button"
            className="w-full bg-blue-700 hover:bg-blue-800 text-white"
            onClick={handleMicrosoftLogin}
            disabled={isLoading || !msalContext}
            title={!msalContext ? "Microsoft login requires HTTPS or localhost" : ""}
          >
            <span className="flex items-center justify-center gap-2">
              <svg width="20" height="20" viewBox="0 0 24 24"><rect fill="#F35325" x="1" y="1" width="10" height="10" /><rect fill="#81BC06" x="13" y="1" width="10" height="10" /><rect fill="#05A6F0" x="1" y="13" width="10" height="10" /><rect fill="#FFBA08" x="13" y="13" width="10" height="10" /></svg>
              Login with Microsoft
            </span>
          </Button>
          <Button
            type="button"
            className="w-full bg-purple-700 hover:bg-purple-800 text-white"
            onClick={handleEpicLogin}
            disabled={isLoading}
          >
            <span className="flex items-center justify-center gap-2">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></svg>
              Login with Epic
            </span>
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-center">
              {isLoginMode ? 'Login' : 'Register'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Auth Error Display */}
              {authError && (
                <Alert variant="destructive">
                  <AlertDescription>{authError}</AlertDescription>
                </Alert>
              )}
              {/* Username */}
              <div>
                <Label htmlFor="username">Username</Label>
                <div className="mt-1 relative">
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    value={formData.username}
                    onChange={handleInputChange}
                    className={errors.username ? 'border-red-500' : ''}
                    placeholder="Enter your username"
                    disabled={isLoading}
                  />
                </div>
                {errors.username && (
                  <p className="mt-1 text-sm text-red-600">{errors.username}</p>
                )}
              </div>
              {/* Email (only for registration) */}
              {!isLoginMode && (
                <div>
                  <Label htmlFor="email">Email</Label>
                  <div className="mt-1 relative">
                    <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      className={`pl-10 ${errors.email ? 'border-red-500' : ''}`}
                      placeholder="Enter your email"
                      disabled={isLoading}
                    />
                  </div>
                  {errors.email && (
                    <p className="mt-1 text-sm text-red-600">{errors.email}</p>
                  )}
                </div>
              )}
              {/* Password */}
              <div>
                <Label htmlFor="password">Password</Label>
                <div className="mt-1 relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={handleInputChange}
                    className={`pl-10 pr-10 ${errors.password ? 'border-red-500' : ''}`}
                    placeholder="Enter your password"
                    maxLength={72}
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-3 h-4 w-4 text-gray-400 hover:text-gray-600"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-sm text-red-600">{errors.password}</p>
                )}
              </div>
              {/* Confirm Password (only for registration) */}
              {!isLoginMode && (
                <div>
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <div className="mt-1 relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      value={formData.confirmPassword}
                      onChange={handleInputChange}
                      className={`pl-10 ${errors.confirmPassword ? 'border-red-500' : ''}`}
                      placeholder="Confirm your password"
                      maxLength={72}
                      disabled={isLoading}
                    />
                  </div>
                  {errors.confirmPassword && (
                    <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
                  )}
                </div>
              )}
              {/* Submit Button */}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    {isLoginMode ? 'Signing in...' : 'Creating account...'}
                  </div>
                ) : (
                  isLoginMode ? 'Sign In' : 'Create Account'
                )}
              </Button>
              {/* Toggle Mode */}
              <div className="text-center">
                <button
                  type="button"
                  onClick={toggleMode}
                  className="text-sm text-blue-600 hover:text-blue-500"
                  disabled={isLoading}
                >
                  {isLoginMode
                    ? "Don't have an account? Sign up"
                    : "Already have an account? Sign in"
                  }
                </button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Login;
