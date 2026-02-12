# Epic OAuth Environment Variables Setup

## Critical: Epic OAuth Configuration

Epic requires **EXACT** matching of redirect URIs. The redirect URI in your `.env` file must match **EXACTLY** (character-by-character) what's registered in Epic App Orchard.

## Frontend `.env` File

Create or update `/frontend/.env` with these variables:

```env
# Epic OAuth Configuration
VITE_EPIC_CLIENT_ID=your-epic-client-id-here
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
VITE_EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
VITE_EPIC_SCOPES=openid fhirUser profile
```

### Important Notes:

1. **Redirect URI**: 
   - Must match EXACTLY what's in Epic App Orchard
   - Check if it should have a trailing slash or not
   - Common formats:
     - `https://ai-doc-assist-dev.eastus.cloudapp.azure.com` (no trailing slash)
     - `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/` (with trailing slash)
   - **Copy the exact value from Epic App Orchard**

2. **Client ID**:
   - Get this from Epic App Orchard
   - Must be the exact value (no spaces, no quotes)

3. **Authorization URL**:
   - Default: `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`
   - Your Epic instance might have a different URL
   - Check Epic App Orchard documentation for your instance

4. **Audience (aud)**:
   - Required parameter for Epic OAuth
   - Default: `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4`
   - This is the FHIR server endpoint that the token will be used for
   - Must match your Epic FHIR server URL

5. **Scopes**:
   - Default: `openid fhirUser profile`
   - Epic may require different scopes
   - Check what scopes are approved in Epic App Orchard
   - Separate multiple scopes with spaces

## Backend `.env` File

Create or update `/backend/.env` with these variables:

```env
# Epic OAuth Configuration
EPIC_CLIENT_ID=your-epic-client-id-here
EPIC_CLIENT_SECRET=your-epic-client-secret-here
EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
```

### Important Notes:

1. **Redirect URI**: Must match EXACTLY the frontend redirect URI
2. **Client Secret**: Get this from Epic App Orchard (keep it secret!)
3. **Token URL**: Usually the same as authorization URL but with `/token` instead of `/authorize`

## Verification Steps

1. **Check Epic App Orchard**:
   - Log into Epic App Orchard
   - Find your application
   - Copy the exact redirect URI (check for trailing slash)
   - Copy the Client ID
   - Verify app is approved/active

2. **Update `.env` files**:
   - Frontend: Update `VITE_EPIC_REDIRECT_URI` to match Epic App Orchard exactly
   - Backend: Update `EPIC_REDIRECT_URI` to match exactly
   - Both must be identical

3. **Restart servers**:
   ```bash
   # Stop both frontend and backend servers
   # Then restart them
   cd frontend && npm run dev
   cd backend && python -m uvicorn main:app --reload
   ```

4. **Test**:
   - Open browser DevTools (F12)
   - Go to Console tab
   - Click "Login with Epic"
   - Check console logs for the authorization URL
   - Verify redirect URI in the URL matches Epic App Orchard exactly

## Common Issues

### Issue: "Something went wrong trying to authorize the client"

**Solution**: 
1. Check redirect URI matches EXACTLY (including trailing slash)
2. Verify Client ID is correct
3. Ensure app is approved in Epic App Orchard
4. Check browser console for the exact authorization URL
5. Compare redirect URI in URL with Epic App Orchard

### Issue: Redirect URI mismatch

**Solution**:
- Epic is very strict about redirect URI matching
- Check Epic App Orchard for the exact format
- Common mistake: trailing slash difference
- Common mistake: http vs https
- Common mistake: www vs non-www

### Issue: Client ID not found

**Solution**:
- Verify Client ID in Epic App Orchard
- Check for typos or extra spaces
- Ensure Client ID is active/approved

## Debugging

When you click "Login with Epic", check the browser console for:

```
=== Epic OAuth Configuration ===
Authorization URL: ...
Client ID: ...
Redirect URI: ...
Scopes: ...
Full Authorization URL: ...
================================
```

Compare the "Redirect URI" and "Full Authorization URL" with what's in Epic App Orchard.

## Still Having Issues?

1. **Double-check Epic App Orchard**:
   - Redirect URI must match character-by-character
   - Client ID must be exact
   - App must be approved

2. **Check the authorization URL**:
   - Copy the full authorization URL from console
   - Paste in browser to see Epic's error message
   - Epic might give more specific error details

3. **Contact Epic Support**:
   - They can verify your app configuration
   - They can check if there are any issues on their end

