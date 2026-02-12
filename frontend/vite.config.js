import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables
  const env = loadEnv(mode, process.cwd(), '')

  // Log Azure AD config status (for debugging)
  const tenantMode = (env.VITE_AZURE_TENANT_MODE || 'single').toLowerCase();
  if (!env.VITE_AZURE_CLIENT_ID) {
    console.warn('⚠️  Azure AD Client ID not found!');
    console.warn('   Please create a .env file in the frontend directory with:');
    console.warn('   VITE_AZURE_CLIENT_ID=your_client_id');
    if (tenantMode === 'single' && !env.VITE_AZURE_TENANT_ID) {
      console.warn('   VITE_AZURE_TENANT_ID=your_tenant_id (required for single-tenant mode)');
    }
    console.warn('   VITE_AZURE_TENANT_MODE=single or multi (optional, defaults to single)');
  } else if (tenantMode === 'single' && !env.VITE_AZURE_TENANT_ID) {
    console.warn('⚠️  Single-tenant mode selected but VITE_AZURE_TENANT_ID is missing!');
    console.warn('   Please set VITE_AZURE_TENANT_ID or change VITE_AZURE_TENANT_MODE=multi');
  }

  return {
    plugins: [react()],
    server: {
      host: env.VITE_FRONTEND_HOST || '0.0.0.0',
      port: parseInt(env.VITE_FRONTEND_PORT) || 5173,
      strictPort: true,
      // Allow the development host used by Azure (no trailing slash)
      allowedHosts: [
        'https://o2ai-fax-automation.centralus.cloudapp.azure.com',
        'localhost',
        '.localhost',
        'o2ai-fax-automation.centralus.cloudapp.azure.com'
      ],
      // Configure HMR for proxy setup
      // Disabled by default to prevent WebSocket connection issues
      // Set VITE_ENABLE_HMR=true in your .env file to enable HMR
      hmr: env.VITE_ENABLE_HMR === 'true' ? {
        // Use the public host that the browser sees (through nginx/load balancer)
        host: env.VITE_HMR_HOST || 'o2ai-fax-automation.centralus.cloudapp.azure.com',
        // Use port 443 for HTTPS (or set via env var) - this tells the client where to connect
        // The browser connects via wss:// on port 443, which gets proxied to Vite on port 5173
        clientPort: parseInt(env.VITE_HMR_PORT) || 443,
        // Use wss (secure WebSocket) since the page is served over HTTPS
        protocol: env.VITE_HMR_PROTOCOL || 'wss',
        // Don't show overlay on errors to prevent refresh loops
        overlay: false,
      } : false
    },
    define: {
      // Make environment variables available to the app
      // Ensure HTTPS is used for production domain to avoid mixed content errors
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
        (() => {
          const apiUrl = env.VITE_API_BASE_URL ||
            (mode === 'production'
              ? 'https://o2ai-fax-automation.centralus.cloudapp.azure.com'
              : 'http://localhost:8000');
          // Properly validate the hostname to ensure HTTPS is used for production domain
          // This prevents URL injection attacks (e.g., http://evil.com/o2ai-fax-automation...)
          try {
            const url = new URL(apiUrl);
            if (url.hostname === 'o2ai-fax-automation.centralus.cloudapp.azure.com' &&
              url.protocol === 'http:') {
              url.protocol = 'https:';
              return url.toString();
            }
          } catch (e) {
            // If URL parsing fails, return the original value
            console.warn('Invalid API URL format:', apiUrl);
          }
          return apiUrl;
        })()
      ),
      // Azure AD variables are automatically available via import.meta.env if prefixed with VITE_
    }
  }
})
