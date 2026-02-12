
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider } from '@azure/msal-react';
import { msalConfig } from './services/authConfig';

// Check if crypto is available (required for MSAL)
const isCryptoAvailable = () => {
  return (
    typeof window !== 'undefined' &&
    (window.crypto || window.msCrypto) &&
    (window.crypto?.subtle || window.msCrypto?.subtle)
  );
};

// Check if we're in a secure context (HTTPS or localhost)
const isSecureContext = () => {
  return (
    window.isSecureContext ||
    window.location.protocol === 'https:' ||
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname === '[::1]'
  );
};

// Initialize MSAL instance with error handling
let msalInstance = null;

try {
  // Check crypto availability before initializing MSAL
  if (!isCryptoAvailable()) {
    console.warn('Crypto API is not available. MSAL authentication may not work properly.');
    console.warn('Please ensure you are using HTTPS or running on localhost.');
    console.warn('Current protocol:', window.location.protocol);
  } else if (!isSecureContext()) {
    console.warn('Not in a secure context. MSAL requires HTTPS or localhost.');
    console.warn('Current protocol:', window.location.protocol);
    console.warn('Current hostname:', window.location.hostname);
  } else {
    // Initialize MSAL only if crypto is available and in secure context
    try {
      msalInstance = new PublicClientApplication(msalConfig);
      console.log('MSAL instance created successfully');
    } catch (initError) {
      console.error('Error creating MSAL instance:', initError);
      msalInstance = null;
    }
  }
} catch (error) {
  console.error('Error during MSAL setup:', error);
  console.error('MSAL will not be available. Authentication features may not work.');
  msalInstance = null;
}

// Render the app
const root = createRoot(document.getElementById('root'));

// Render function
const renderApp = (withMsal = false) => {
  if (withMsal && msalInstance) {
    root.render(
      <StrictMode>
        <MsalProvider instance={msalInstance}>
          <App />
        </MsalProvider>
      </StrictMode>
    );
  } else {
    root.render(
      <StrictMode>
        <App />
      </StrictMode>
    );
  }
};

if (msalInstance) {
  // Initialize MSAL asynchronously, then update render
  msalInstance.initialize()
    .then(() => {
      console.log('MSAL initialized successfully');
      // Re-render with MSAL provider after initialization
      renderApp(true);
    })
    .catch((error) => {
      console.error('MSAL initialization error:', error);
      // Render without MSAL provider if initialization fails
      renderApp(false);
    });
  
  // Render immediately without MSAL (will update after init)
  renderApp(false);
} else {
  // Render without MSAL provider if crypto is not available
  console.warn('Rendering app without MSAL provider due to crypto unavailability');
  renderApp(false);
}
