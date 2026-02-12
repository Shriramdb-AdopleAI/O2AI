# Epic OAuth Troubleshooting Guide

## Error: "Something went wrong trying to authorize the client"

This error typically occurs due to one of the following issues:

### 1. Redirect URI Mismatch (Most Common)

**Problem**: The redirect URI in your request doesn't match exactly what's registered in Epic App Orchard.

**Solution**:
- Check your Epic App Orchard settings
- Ensure the redirect URI is EXACTLY: `https://ai-doc-assist-dev.eastus.cloudapp.azure.com`
- Note: Epic is case-sensitive and trailing slashes matter
- The redirect URI in your `.env` file must match EXACTLY what's in Epic App Orchard

**Check in your `.env` file:**
```
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
```
(No trailing slash)

### 2. Client ID Not Found

**Problem**: The Client ID doesn't exist or is incorrect.

**Solution**:
- Verify `VITE_EPIC_CLIENT_ID` in your frontend `.env` file matches the Client ID from Epic App Orchard
- Check that the Client ID is active/approved in Epic App Orchard
- Ensure there are no extra spaces or characters

**Check in your `.env` file:**
```
VITE_EPIC_CLIENT_ID=your-actual-client-id-here
```

### 3. Incorrect Authorization URL

**Problem**: The authorization URL doesn't match your Epic instance.

**Solution**:
- Different Epic instances have different authorization URLs
- Check your Epic App Orchard documentation for the correct authorization URL
- Default is: `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`
- But your instance might be different (e.g., `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`)

**Check in your `.env` file:**
```
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
```

### 4. Incorrect Scopes

**Problem**: The scopes requested don't match what's configured in Epic App Orchard.

**Solution**:
- Check what scopes are approved for your app in Epic App Orchard
- Common scopes: `openid`, `fhirUser`, `profile`, `launch`, `offline_access`
- The scopes in the code are: `['openid', 'fhirUser', 'profile', 'launch']`
- If your Epic app requires different scopes, update them in `epicAuthConfig.js`

### 5. App Not Approved

**Problem**: Your app might not be approved/activated in Epic App Orchard.

**Solution**:
- Log into Epic App Orchard
- Check that your app status is "Ready" or "Active"
- Ensure all required configurations are complete

## Debugging Steps

1. **Check Browser Console**:
   - Open browser DevTools (F12)
   - Go to Console tab
   - Look for "Epic OAuth Configuration" logs
   - Check the "Epic OAuth Authorization URL" that's being generated

2. **Verify Environment Variables**:
   - Frontend `.env` file should have:
     ```
     VITE_EPIC_CLIENT_ID=your-client-id
     VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
     VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
     ```
   - Backend `.env` file should have:
     ```
     EPIC_CLIENT_ID=your-client-id
     EPIC_CLIENT_SECRET=your-client-secret
     EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
     EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
     ```

3. **Test the Authorization URL**:
   - Copy the authorization URL from the console
   - Paste it in a new browser tab
   - See if you get a different error message

4. **Check Epic App Orchard**:
   - Log into Epic App Orchard
   - Verify:
     - Client ID matches exactly
     - Redirect URI matches exactly (no trailing slash)
     - App is approved/active
     - Scopes are configured correctly

## Common Fixes

### Fix 1: Remove Trailing Slash
```javascript
// In epicAuthConfig.js, the redirect URI is automatically trimmed
// But double-check your .env file has no trailing slash:
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
// NOT: https://ai-doc-assist-dev.eastus.cloudapp.azure.com/
```

### Fix 2: Verify Client ID
```bash
# Check your .env file
cat .env | grep EPIC
# Should show your actual Client ID, not a placeholder
```

### Fix 3: Restart Development Server
After changing `.env` file:
```bash
# Stop the server (Ctrl+C)
# Restart it
npm run dev
```

## Still Having Issues?

1. Check Epic App Orchard documentation
2. Contact Epic support
3. Verify your Epic instance URL is correct
4. Check if your organization has specific Epic OAuth requirements

