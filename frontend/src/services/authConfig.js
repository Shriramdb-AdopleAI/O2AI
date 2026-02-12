import { LogLevel } from '@azure/msal-browser';

/**
 * MSAL configuration for Azure AD with tenant-mode handling.
 * Reads values from Vite environment variables (VITE_ prefix).
 */

const normalize = (v) => (typeof v === 'string' ? v.trim() : '');

const getClientId = () => {
  const clientId = normalize(import.meta.env.VITE_AZURE_CLIENT_ID || import.meta.env.AZURE_CLIENT_ID || '');
  if (!clientId) console.warn('VITE_AZURE_CLIENT_ID is not set. Please set it in your .env file.');
  return clientId;
};

const getTenantMode = () => {
  const mode = normalize(import.meta.env.VITE_AZURE_TENANT_MODE || 'single').toLowerCase();
  return mode === 'multi' ? 'multi' : 'single';
};

const getTenantId = () => normalize(import.meta.env.VITE_AZURE_TENANT_ID || import.meta.env.AZURE_TENANT_ID || '');

const isLikelyPlaceholder = (v) => {
  if (!v) return false;
  const lowered = v.toLowerCase();
  // common placeholder patterns
  return lowered.includes('your') || lowered.includes('example') || lowered === 'your_tenant_id';
};

const buildAuthority = () => {
  const mode = getTenantMode();
  const tenantId = getTenantId();

  if (mode === 'multi') {
    // Multi-tenant: allow any Azure AD account
    return 'https://login.microsoftonline.com/common';
  }

  // single-tenant
  if (!tenantId || isLikelyPlaceholder(tenantId)) {
    console.warn('VITE_AZURE_TENANT_ID is not set or appears to be a placeholder. Falling back to `common` authority to avoid AADSTS900023. Set VITE_AZURE_TENANT_ID in .env for single-tenant mode to restrict to your tenant.');
    return 'https://login.microsoftonline.com/common';
  }

  // validate tenantId looks like a guid or domain
  const guidRegex = /^[0-9a-fA-F-]{36}$/;
  const domainLike = /^[a-z0-9.-]+\.[a-z]{2,}$/i;

  if (guidRegex.test(tenantId) || domainLike.test(tenantId)) {
    return `https://login.microsoftonline.com/${tenantId}`;
  }

  console.warn('VITE_AZURE_TENANT_ID does not look like a GUID or domain. Falling back to `common` authority.');
  return 'https://login.microsoftonline.com/common';
};

const clientId = getClientId();
const authority = buildAuthority();
const tenantMode = getTenantMode();

if (!clientId) {
  console.error('Azure AD configuration incomplete: missing client ID (VITE_AZURE_CLIENT_ID).');
}

console.log(`Azure AD Configuration: ${tenantMode === 'multi' ? 'Multi-Tenant' : 'Single-Tenant'}`);
if (tenantMode === 'single') {
  console.log(`Tenant ID: ${getTenantId() || 'NOT SET (falling back to common)'}`);
}

export const msalConfig = {
  auth: {
    clientId: clientId || '',
    authority: authority,
    redirectUri: 'https://o2ai-fax-automation.centralus.cloudapp.azure.com/', // Was: window.location.origin
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Info:
            console.info(message);
            return;
          case LogLevel.Verbose:
            console.debug(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
          default:
            return;
        }
      },
    },
  },
};

export const loginRequest = {
  scopes: ['User.Read'],
};

export const graphConfig = {
  graphMeEndpoint: 'https://graph.microsoft.com/v1.0/me',
};
