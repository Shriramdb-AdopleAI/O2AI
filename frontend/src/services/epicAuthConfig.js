/**
 * Epic OAuth configuration.
 * Reads values from Vite environment variables (VITE_ prefix).
 */

const normalize = (v) => (typeof v === 'string' ? v.trim() : '');

const getClientId = () => {
  const clientId = normalize(import.meta.env.VITE_EPIC_CLIENT_ID || '');
  if (!clientId) console.warn('VITE_EPIC_CLIENT_ID is not set. Please set it in your .env file.');
  return clientId;
};

const getRedirectUri = () => {
  // Epic requires EXACT match - use exactly as provided in .env
  // NO default value - must be explicitly set to avoid using wrong redirect URI
  let redirectUri = normalize(import.meta.env.VITE_EPIC_REDIRECT_URI || '');

  // Validate it's a proper URL
  if (!redirectUri || redirectUri.trim() === '') {
    console.error('VITE_EPIC_REDIRECT_URI is not set in .env file');
    return '';
  }

  try {
    const url = new URL(redirectUri);
    // Ensure it's HTTPS (Epic requires HTTPS)
    if (url.protocol !== 'https:') {
      console.warn('Redirect URI should use HTTPS for Epic OAuth');
    }
  } catch (e) {
    console.error('Invalid redirect URI format:', redirectUri, e);
    return '';
  }

  return redirectUri;
};

const getAuthorizationUrl = () => {
  const authUrl = normalize(import.meta.env.VITE_EPIC_AUTHORIZATION_URL || 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize');
  return authUrl;
};

const getAudience = () => {
  // Epic requires 'aud' (audience) parameter - the FHIR server endpoint
  const audience = normalize(import.meta.env.VITE_EPIC_AUDIENCE || 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4');
  return audience;
};

const clientId = getClientId();
const redirectUri = getRedirectUri();
const authorizationUrl = getAuthorizationUrl();
const audience = getAudience();

if (!clientId) {
  console.error('Epic OAuth configuration incomplete: missing client ID (VITE_EPIC_CLIENT_ID).');
}

console.log(`Epic OAuth Configuration:`);
console.log(`Client ID: ${clientId ? 'SET' : 'NOT SET'}`);
console.log(`Redirect URI: ${redirectUri}`);
console.log(`Authorization URL: ${authorizationUrl}`);
console.log(`Audience (aud): ${audience}`);

// Get scopes from environment or use defaults
const getScopes = () => {
  const envScopes = normalize(import.meta.env.VITE_EPIC_SCOPES || '');
  if (envScopes) {
    // If scopes are provided in env, split by space or comma
    return envScopes.split(/[\s,]+/).filter(s => s.length > 0);
  }
  // Default Epic FHIR OAuth scopes for user authentication
  // Common scopes: openid, fhirUser, profile, launch, offline_access
  // Try minimal scopes first - Epic may reject if scopes aren't approved
  return ['openid', 'fhirUser', 'profile'];
};

export const epicConfig = {
  clientId: clientId || '',
  redirectUri: redirectUri,
  authorizationUrl: authorizationUrl,
  audience: audience,
  scopes: getScopes(),
};

/**
 * Generate Epic OAuth authorization URL
 * Epic requires exact parameter formatting and URL encoding
 */
export const getEpicAuthUrl = (state = null) => {
  // Epic requires exact redirect URI match - use as configured
  // Don't modify it - it must match exactly what's in Epic App Orchard
  const redirectUri = epicConfig.redirectUri;

  // Validate required parameters before building URL
  if (!epicConfig.clientId || epicConfig.clientId.trim() === '') {
    throw new Error('Epic Client ID is not configured. Set VITE_EPIC_CLIENT_ID in .env');
  }

  if (!redirectUri || redirectUri.trim() === '') {
    throw new Error('Epic Redirect URI is not configured. Set VITE_EPIC_REDIRECT_URI in .env');
  }

  if (!epicConfig.audience || epicConfig.audience.trim() === '') {
    throw new Error('Epic Audience (aud) is not configured. Set VITE_EPIC_AUDIENCE in .env');
  }

  // Build parameters object (matching Epic OAuth format)
  // Epic requires these exact parameter names
  const params = {
    response_type: 'code',
    client_id: epicConfig.clientId.trim(),
    redirect_uri: redirectUri.trim(),
    scope: epicConfig.scopes.join(' ').trim(),
    aud: epicConfig.audience.trim()
  };

  // Add state if provided (for CSRF protection)
  if (state) {
    params.state = state;
  }

  // Build URL with properly encoded parameters
  const queryString = Object.entries(params)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');

  const authUrl = `${epicConfig.authorizationUrl}?${queryString}`;

  // Detailed debugging - decode URL to show exact values
  const decodedParams = {
    response_type: 'code',
    client_id: epicConfig.clientId,
    redirect_uri: redirectUri,
    scope: epicConfig.scopes.join(' '),
    aud: epicConfig.audience,
    state: state ? state : 'NOT SET'
  };

  // Save debug info to localStorage so it persists after redirect
  const debugInfo = {
    timestamp: new Date().toISOString(),
    authorizationUrl: epicConfig.authorizationUrl,
    clientId: epicConfig.clientId,
    redirectUri: redirectUri,
    redirectUriEncoded: encodeURIComponent(redirectUri),
    scopes: epicConfig.scopes.join(' '),
    audience: epicConfig.audience,
    fullAuthUrl: authUrl,
    decodedParams: decodedParams
  };

  try {
    localStorage.setItem('epic_oauth_debug', JSON.stringify(debugInfo, null, 2));
  } catch (e) {
    console.warn('Could not save debug info to localStorage:', e);
  }

  // Log for debugging
  console.log('=== Epic OAuth Configuration ===');
  console.log('Authorization URL:', epicConfig.authorizationUrl);
  console.log('Client ID:', epicConfig.clientId);
  console.log('Redirect URI (decoded):', redirectUri);
  console.log('Redirect URI (encoded):', encodeURIComponent(redirectUri));
  console.log('Scopes:', epicConfig.scopes.join(' '));
  console.log('Audience (aud):', epicConfig.audience);
  console.log('State:', state ? 'SET' : 'NOT SET');
  console.log('');
  console.log('=== Decoded Parameters (for Epic App Orchard comparison) ===');
  console.log('1. Client ID:', decodedParams.client_id);
  console.log('2. Redirect URI:', decodedParams.redirect_uri);
  console.log('   ⚠️  MUST match EXACTLY in Epic App Orchard (check trailing slash)');
  console.log('3. Scopes:', decodedParams.scope);
  console.log('   ⚠️  All scopes must be approved in Epic App Orchard');
  console.log('4. Audience (aud):', decodedParams.aud);
  console.log('');
  console.log('=== Full Authorization URL ===');
  console.log(authUrl);
  console.log('');
  console.log('=== Troubleshooting Checklist ===');
  console.log('□ Redirect URI matches Epic App Orchard EXACTLY (with/without trailing slash)');
  console.log('□ Client ID matches Epic App Orchard EXACTLY');
  console.log('□ App is approved/active in Epic App Orchard');
  console.log('□ All scopes are approved in Epic App Orchard');
  console.log('□ No extra spaces or characters in any parameter');
  console.log('');
  console.log('💾 Debug info saved to localStorage. Type: epicDebug() in console to view after redirect.');
  console.log('================================');

  return authUrl;
};

/**
 * Initiate Epic OAuth login by redirecting to Epic authorization server
 */
export const initiateEpicLogin = () => {
  // Validate configuration before redirecting
  if (!epicConfig.clientId || epicConfig.clientId.trim() === '') {
    const errorMsg = 'Epic Client ID is not configured. Please set VITE_EPIC_CLIENT_ID in your .env file.';
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  if (!epicConfig.redirectUri || epicConfig.redirectUri.trim() === '') {
    const errorMsg = 'Epic Redirect URI is not configured. Please set VITE_EPIC_REDIRECT_URI in your .env file.';
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  if (!epicConfig.authorizationUrl || epicConfig.authorizationUrl.trim() === '') {
    const errorMsg = 'Epic Authorization URL is not configured. Please set VITE_EPIC_AUTHORIZATION_URL in your .env file.';
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  if (!epicConfig.audience || epicConfig.audience.trim() === '') {
    const errorMsg = 'Epic Audience (aud) is not configured. Please set VITE_EPIC_AUDIENCE in your .env file. This is REQUIRED for Epic OAuth.';
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  // Validate redirect URI is a proper URL
  try {
    new URL(epicConfig.redirectUri);
  } catch (e) {
    const errorMsg = `Invalid redirect URI format: ${epicConfig.redirectUri}. Please check VITE_EPIC_REDIRECT_URI in your .env file.`;
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  // Clear any old OAuth state before starting new login (but keep used codes to prevent reuse)
  sessionStorage.removeItem('epic_oauth_state');

  // Generate a state parameter for CSRF protection
  const state = btoa(JSON.stringify({ timestamp: Date.now(), random: Math.random() }));
  sessionStorage.setItem('epic_oauth_state', state);

  // Get the authorization URL with error handling
  let authUrl;
  try {
    authUrl = getEpicAuthUrl(state);
  } catch (error) {
    const errorMsg = `Failed to generate Epic authorization URL: ${error.message}`;
    console.error(errorMsg);
    alert(errorMsg);
    return;
  }

  console.log('Redirecting to Epic authorization server...');
  console.log('Authorization URL:', authUrl);

  // Redirect to Epic authorization server
  window.location.href = authUrl;
};

/**
 * Handle Epic OAuth callback
 * Extracts authorization code from URL and returns it
 */
export const handleEpicCallback = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');
  const error = urlParams.get('error');
  const errorDescription = urlParams.get('error_description');

  // Check if we're on an Epic error page (Epic sometimes returns HTML error pages)
  // This happens when Epic rejects the request before showing the login page
  if (document.title && document.title.includes('OAuth2 Error')) {
    console.error('Epic returned an OAuth2 Error page');
    console.error('This usually means:');
    console.error('1. Client ID is not active/approved in Epic App Orchard');
    console.error('2. Redirect URI does not match exactly in Epic App Orchard');
    console.error('3. Scopes are not approved in Epic App Orchard');
    console.error('4. App is not in "Tested" or "Ready" status');
    console.error('');
    console.error('💡 Check Epic App Orchard configuration against your current VITE_* env values (client ID, redirect URI, scopes, status).');

    return {
      error: 'Epic OAuth2 Error',
      errorDescription: 'Epic rejected the authorization request. Please verify your Epic App Orchard configuration matches exactly. Check: Client ID, Redirect URI (including trailing slash), Approved Scopes, and App Status.',
      rawError: 'oauth2_error_page',
      rawErrorDescription: 'Epic returned an HTML error page instead of redirecting with error parameters'
    };
  }

  // Verify state parameter
  const storedState = sessionStorage.getItem('epic_oauth_state');
  if (state && storedState && state !== storedState) {
    console.error('State parameter mismatch - possible CSRF attack');
    return { error: 'Invalid state parameter', errorDescription: 'State mismatch detected' };
  }

  // Clear state from sessionStorage
  sessionStorage.removeItem('epic_oauth_state');

  if (error) {
    // Provide user-friendly error messages
    let userFriendlyError = error;
    let userFriendlyDescription = errorDescription || '';

    // Check for "Invalid OAuth 2.0 request" specifically
    if (error === 'invalid_request' || errorDescription?.toLowerCase().includes('invalid oauth')) {
      userFriendlyError = 'Invalid OAuth 2.0 Request';
      userFriendlyDescription = 'Epic rejected the authorization request. Common causes:\n' +
        '1. Redirect URI does not match EXACTLY (check trailing slash)\n' +
        '2. Client ID does not match Epic App Orchard\n' +
        '3. Missing or invalid required parameters\n' +
        '4. App not approved/active in Epic App Orchard\n\n' +
        'Check your VITE_EPIC_* environment variables and verify they match Epic App Orchard exactly.';
      
      // Log detailed debug info
      console.error('=== Invalid OAuth 2.0 Request Debug Info ===');
      try {
        const debugInfo = localStorage.getItem('epic_oauth_debug');
        if (debugInfo) {
          const debug = JSON.parse(debugInfo);
          console.error('Client ID used:', debug.clientId);
          console.error('Redirect URI used:', debug.redirectUri);
          console.error('Redirect URI (encoded):', debug.redirectUriEncoded);
          console.error('Scopes used:', debug.scopes);
          console.error('Audience used:', debug.audience);
          console.error('Full Auth URL:', debug.fullAuthUrl);
          console.error('\n⚠️  Compare these values EXACTLY with Epic App Orchard:');
          console.error('   - Client ID must match character-for-character');
          console.error('   - Redirect URI must match EXACTLY (including trailing slash)');
          console.error('   - All scopes must be approved in Epic App Orchard');
        }
      } catch (e) {
        console.error('Could not load debug info:', e);
      }
      console.error('===========================================');
    }

    switch (error) {
      case 'access_denied':
        userFriendlyError = 'Login Cancelled';
        userFriendlyDescription = 'You cancelled the Epic login. Please try again if you want to log in.';
        break;
      case 'invalid_request':
        userFriendlyError = 'Invalid Request';
        userFriendlyDescription = 'The login request was invalid. Please check your Epic OAuth configuration.';
        break;
      case 'invalid_client':
        userFriendlyError = 'Invalid Client';
        userFriendlyDescription = 'The Client ID is invalid or not found in Epic App Orchard. Please verify your VITE_EPIC_CLIENT_ID.';
        break;
      case 'invalid_scope':
        userFriendlyError = 'Invalid Scope';
        userFriendlyDescription = 'One or more requested scopes are not approved. Please check your scopes in Epic App Orchard.';
        break;
      case 'server_error':
        userFriendlyError = 'Epic Server Error';
        userFriendlyDescription = 'Epic server encountered an error. Please try again later.';
        break;
      case 'temporarily_unavailable':
        userFriendlyError = 'Epic Service Unavailable';
        userFriendlyDescription = 'Epic service is temporarily unavailable. Please try again later.';
        break;
      default:
        userFriendlyError = `Epic Login Error: ${error}`;
        userFriendlyDescription = errorDescription || 'An unknown error occurred during Epic login.';
    }

    console.error('Epic OAuth Error:', error);
    console.error('Error Description:', errorDescription);

    return {
      error: userFriendlyError,
      errorDescription: userFriendlyDescription,
      rawError: error,
      rawErrorDescription: errorDescription
    };
  }

  if (code) {
    return { code: code };
  }

  return null;
};

/**
 * Display Epic OAuth debug information (persists after redirect)
 * Call this in browser console: epicDebug()
 */
export const epicDebug = () => {
  try {
    const debugInfo = localStorage.getItem('epic_oauth_debug');
    if (debugInfo) {
      const info = JSON.parse(debugInfo);
      console.log('=== Epic OAuth Debug Info (Saved Before Redirect) ===');
      console.log('Timestamp:', info.timestamp);
      console.log('');
      console.log('=== Configuration ===');
      console.log('Authorization URL:', info.authorizationUrl);
      console.log('Client ID:', info.clientId);
      console.log('Redirect URI (decoded):', info.redirectUri);
      console.log('Redirect URI (encoded):', info.redirectUriEncoded);
      console.log('Scopes:', info.scopes);
      console.log('Audience (aud):', info.audience);
      console.log('');
      console.log('=== Decoded Parameters (Compare with Epic App Orchard) ===');
      console.log('1. Client ID:', info.decodedParams.client_id);
      console.log('   → Check in Epic App Orchard: Does this match EXACTLY?');
      console.log('');
      console.log('2. Redirect URI:', info.decodedParams.redirect_uri);
      console.log('   → Check in Epic App Orchard: Does this match EXACTLY?');
      console.log('   → ⚠️  CRITICAL: Check trailing slash (with / or without /)');
      console.log('');
      console.log('3. Scopes:', info.decodedParams.scope);
      console.log('   → Check in Epic App Orchard: Are ALL these scopes approved?');
      console.log('   → Scopes list:', info.scopes.split(' '));
      console.log('');
      console.log('=== Full Authorization URL ===');
      console.log(info.fullAuthUrl);
      console.log('');
      console.log('=== Troubleshooting Checklist ===');
      console.log('□ Redirect URI matches Epic App Orchard EXACTLY (with/without trailing slash)');
      console.log('□ Client ID matches Epic App Orchard EXACTLY');
      console.log('□ App is approved/active in Epic App Orchard');
      console.log('□ All scopes are approved in Epic App Orchard');
      console.log('□ No extra spaces or characters in any parameter');
      console.log('');
      console.log('=== Copy These Values to Compare ===');
      console.log('Client ID:', info.clientId);
      console.log('Redirect URI:', info.redirectUri);
      console.log('Scopes:', info.scopes);
      console.log('====================================');
      return info;
    } else {
      console.log('No Epic OAuth debug info found. Click "Login with Epic" first to generate debug info.');
      return null;
    }
  } catch (e) {
    console.error('Error reading debug info:', e);
    return null;
  }
};

// Make epicDebug available globally for easy access
if (typeof window !== 'undefined') {
  window.epicDebug = epicDebug;
}

