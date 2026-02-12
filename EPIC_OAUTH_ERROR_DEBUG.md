# Epic OAuth "OAuth2 Error" Debugging Guide

## Error Message
**"OAuth2 Error: Something went wrong trying to authorize the client."**

This error is coming from **Epic's authorization server**, not from your application code. It means Epic is rejecting the authorization request before it even gets to the callback.

## Root Causes

### 1. Client ID Mismatch ⚠️ **MOST COMMON**
- **Symptom**: Error appears immediately when clicking "Login with Epic"
- **Cause**: Client ID in `.env` doesn't match what's registered in Epic App Orchard
- **Fix**: 
  - Verify Client ID in Epic App Orchard
  - Update `.env` to match exactly
  - **Frontend**: `VITE_EPIC_CLIENT_ID`
  - **Backend**: `EPIC_CLIENT_ID` (must match frontend)

### 2. Redirect URI Mismatch ⚠️ **VERY COMMON**
- **Symptom**: Error appears immediately
- **Cause**: Redirect URI doesn't match **EXACTLY** (character-by-character) what's in Epic App Orchard
- **Common Issues**:
  - Trailing slash difference: `https://example.com` vs `https://example.com/`
  - http vs https
  - www vs non-www
  - Extra spaces or characters
- **Fix**:
  - Check Epic App Orchard for exact redirect URI
  - Update both frontend and backend `.env` to match exactly
  - **Frontend**: `VITE_EPIC_REDIRECT_URI`
  - **Backend**: `EPIC_REDIRECT_URI` (must match frontend exactly)

### 3. Unapproved Scopes
- **Symptom**: Error appears immediately
- **Cause**: Requested scopes aren't approved in Epic App Orchard
- **Fix**:
  - Check which scopes are approved in Epic App Orchard
  - Remove unapproved scopes from `VITE_EPIC_SCOPES`
  - Default safe scopes: `openid profile fhirUser`

### 4. App Not Active/Approved
- **Symptom**: Error appears immediately
- **Cause**: App is not in "Tested" or "Ready" status in Epic App Orchard
- **Fix**: 
  - Verify app status in Epic App Orchard
  - Ensure app is approved/active

### 5. Client Secret Mismatch (Backend Token Exchange)
- **Symptom**: Authorization succeeds but token exchange fails
- **Cause**: `EPIC_CLIENT_SECRET` in backend doesn't match the client ID
- **Fix**: 
  - Verify client secret in Epic App Orchard
  - Update backend `.env`: `EPIC_CLIENT_SECRET`

## Current Configuration Check

### Frontend `.env` (Expected)
```env
VITE_EPIC_CLIENT_ID=f139ac22-65b3-4dd4-b10d-0960e6f14850
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com/
VITE_EPIC_SCOPES=openid profile fhirUser
```

### Backend `.env` (Expected)
```env
EPIC_CLIENT_ID=f139ac22-65b3-4dd4-b10d-0960e6f14850
EPIC_CLIENT_SECRET="your-client-secret-here"
EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com/
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
```

## Debugging Steps

### Step 1: Check Browser Console
1. Open DevTools (F12)
2. Go to Console tab
3. Click "Login with Epic"
4. Look for the authorization URL
5. Type: `epicDebug()` to see full debug info

### Step 2: Verify Authorization URL Parameters
The authorization URL should show:
```
https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?
  response_type=code
  &client_id=f139ac22-65b3-4dd4-b10d-0960e6f14850
  &redirect_uri=https%3A%2F%2Fai-doc-assist-dev.eastus.cloudapp.azure.com%2F
  &scope=openid%20profile%20fhirUser
  &aud=https%3A%2F%2Ffhir.epic.com%2Finterconnect-fhir-oauth%2Fapi%2FFHIR%2FR4
```

### Step 3: Compare with Epic App Orchard
1. Log into Epic App Orchard
2. Find your application
3. Compare:
   - **Client ID**: Must match exactly
   - **Redirect URI**: Must match exactly (check trailing slash!)
   - **Scopes**: All requested scopes must be approved
   - **App Status**: Must be "Tested" or "Ready"

### Step 4: Check Backend Configuration
```bash
cd backend
cat .env | grep EPIC
```

Verify:
- `EPIC_CLIENT_ID` matches frontend `VITE_EPIC_CLIENT_ID`
- `EPIC_REDIRECT_URI` matches frontend `VITE_EPIC_REDIRECT_URI` exactly
- `EPIC_CLIENT_SECRET` is set and correct

### Step 5: Test Authorization URL Directly
1. Copy the full authorization URL from browser console
2. Paste in a new browser tab
3. Epic will show a more specific error message
4. Use that error message to identify the exact issue

## Common Error Scenarios

### Scenario 1: "Invalid Client"
- **Cause**: Client ID not found in Epic system
- **Fix**: Verify Client ID in Epic App Orchard matches exactly

### Scenario 2: "Invalid Redirect URI"
- **Cause**: Redirect URI doesn't match Epic App Orchard
- **Fix**: Check trailing slash, http/https, exact match

### Scenario 3: "Invalid Scope"
- **Cause**: Requested scope not approved
- **Fix**: Remove unapproved scopes or request approval in Epic

### Scenario 4: "Access Denied"
- **Cause**: User cancelled or app not approved
- **Fix**: Verify app is approved in Epic App Orchard

## Quick Fix Checklist

- [ ] Frontend `VITE_EPIC_CLIENT_ID` matches Epic App Orchard
- [ ] Backend `EPIC_CLIENT_ID` matches frontend
- [ ] Frontend `VITE_EPIC_REDIRECT_URI` matches Epic App Orchard exactly (including trailing slash)
- [ ] Backend `EPIC_REDIRECT_URI` matches frontend exactly
- [ ] All scopes in `VITE_EPIC_SCOPES` are approved in Epic App Orchard
- [ ] Backend `EPIC_CLIENT_SECRET` is set and correct
- [ ] App is in "Tested" or "Ready" status in Epic App Orchard
- [ ] Restarted frontend server after `.env` changes
- [ ] Restarted backend server after `.env` changes

## Restart Servers After Changes

After updating `.env` files, **restart both servers**:

```bash
# Frontend
cd frontend
# Stop server (Ctrl+C)
npm run dev

# Backend
cd backend
# Stop server (Ctrl+C)
python -m uvicorn main:app --reload
```

## Still Not Working?

1. **Check Epic App Orchard**:
   - Verify all settings match exactly
   - Check for any pending approvals
   - Verify app is active

2. **Check Browser Console**:
   - Look for specific error messages
   - Check the authorization URL
   - Use `epicDebug()` function

3. **Check Backend Logs**:
   - Look for token exchange errors
   - Verify backend has correct configuration

4. **Contact Epic Support**:
   - They can verify your app configuration
   - They can check if there are issues on their end

