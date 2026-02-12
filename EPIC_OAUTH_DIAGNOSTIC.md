# Epic OAuth Diagnostic - Error Page Analysis

## Current Situation

**Request URL** (looks correct):
```
https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?
  response_type=code
  &client_id=f139ac22-65b3-4dd4-b10d-0960e6f14850
  &redirect_uri=https%3A%2F%2Fai-doc-assist-dev.eastus.cloudapp.azure.com%2F
  &scope=openid%20profile%20fhirUser
  &aud=https%3A%2F%2Ffhir.epic.com%2Finterconnect-fhir-oauth%2Fapi%2FFHIR%2FR4
  &state=...
```

**Response**: 200 OK with HTML error page showing "OAuth2 Error"

## Root Cause Analysis

Since Epic is returning a 200 OK with an error page (not a redirect with error parameters), this indicates:

1. **Epic is processing the request** but rejecting it
2. **The error is likely a configuration mismatch** in Epic App Orchard
3. **Epic is not redirecting back** with error parameters, which is unusual

## Most Likely Issues

### 1. Client ID Not Active/Approved ⚠️ **MOST LIKELY**
- Client ID `f139ac22-65b3-4dd4-b10d-0960e6f14850` might not be:
  - Active in Epic App Orchard
  - Approved for the environment you're using
  - Associated with the correct app

**Fix**: 
- Log into Epic App Orchard
- Verify the Non-Production Client ID is: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
- Verify it's active and approved
- Check if the app is in "Tested" or "Ready" status

### 2. Redirect URI Mismatch ⚠️ **VERY COMMON**
- Epic requires **EXACT** match (character-by-character)
- Common issues:
  - Trailing slash: `https://example.com` vs `https://example.com/`
  - Protocol: `http://` vs `https://`
  - Case sensitivity
  - Extra spaces or characters

**Fix**:
- In Epic App Orchard, check the exact redirect URI registered
- It should be: `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/` (with trailing slash)
- Verify it matches exactly in both frontend and backend `.env` files

### 3. Scopes Not Approved
- Requested scopes: `openid profile fhirUser`
- All three must be approved in Epic App Orchard

**Fix**:
- In Epic App Orchard, verify these scopes are approved:
  - `openid`
  - `profile`
  - `fhirUser`

### 4. App Status
- App must be in "Tested" or "Ready" status
- App must be active/approved

**Fix**:
- Check app status in Epic App Orchard
- Ensure it's not in "Created" status (needs to be tested)

### 5. Environment Mismatch
- Using Non-Production Client ID but might need Production
- Or vice versa

**Fix**:
- Verify which environment you should be using
- Non-Production: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
- Production: `a2da4cd4-e904-4889-a795-12a36e482026`

## Action Items

### Step 1: Verify Epic App Orchard Configuration

1. **Log into Epic App Orchard**
2. **Find your application** (named "Authentication")
3. **Verify these settings**:

   | Setting | Expected Value | Status |
   |---------|---------------|--------|
   | Non-Production Client ID | `f139ac22-65b3-4dd4-b10d-0960e6f14850` | ⏳ Verify |
   | Redirect URI | `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/` | ⏳ Verify |
   | Application Audience | "Clinicians or Administrative Users" | ⏳ Verify |
   | SMART on FHIR Version | R4 | ⏳ Verify |
   | SMART Scope Version | SMART v2 | ⏳ Verify |
   | Is Confidential Client | Checked | ⏳ Verify |
   | App Status | "Tested" or "Ready" | ⏳ Verify |
   | Approved Scopes | `openid`, `profile`, `fhirUser` | ⏳ Verify |

### Step 2: Check for Specific Error Messages

Since Epic is returning an HTML error page, check:

1. **View Page Source** of the error page
2. **Look for specific error messages** in the HTML
3. **Check browser console** for any JavaScript errors
4. **Check Network tab** for any additional error details

### Step 3: Try Alternative Approaches

1. **Test with Production Client ID** (if available):
   ```env
   VITE_EPIC_CLIENT_ID=a2da4cd4-e904-4889-a795-12a36e482026
   ```

2. **Try without trailing slash** (if Epic App Orchard has it without):
   ```env
   VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
   ```

3. **Try minimal scopes** (just openid):
   ```env
   VITE_EPIC_SCOPES=openid
   ```

### Step 4: Contact Epic Support

If all configuration matches but still getting errors:

1. **Contact Epic Support** with:
   - Your Client ID: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
   - Your Redirect URI: `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/`
   - The error you're seeing
   - Request URL you're using

2. **Ask them to verify**:
   - Is the Client ID active?
   - Is the Redirect URI registered correctly?
   - Are the scopes approved?
   - Is there any issue on their end?

## Debugging Commands

### Check Current Configuration
```bash
# Frontend
cd frontend
cat .env | grep EPIC

# Backend
cd backend
cat .env | grep "^EPIC_"
```

### Verify Configuration Match
```bash
# Client IDs should match
grep -E "CLIENT_ID" frontend/.env backend/.env

# Redirect URIs should match exactly
grep -E "REDIRECT_URI" frontend/.env backend/.env
```

## Expected vs Actual

### Expected Behavior
1. Click "Login with Epic"
2. Browser redirects to Epic authorization page
3. User sees Epic login form
4. User logs in
5. Epic redirects back with authorization code

### Actual Behavior
1. Click "Login with Epic"
2. Browser redirects to Epic
3. Epic shows "OAuth2 Error" page
4. No redirect back to app

## Next Steps

1. ✅ **Verify Epic App Orchard** configuration matches exactly
2. ⏳ **Check error page source** for specific error message
3. ⏳ **Try alternative configurations** (see Step 3 above)
4. ⏳ **Contact Epic Support** if issue persists

## Quick Fix Checklist

- [ ] Client ID matches Epic App Orchard exactly
- [ ] Redirect URI matches Epic App Orchard exactly (check trailing slash!)
- [ ] All scopes are approved in Epic App Orchard
- [ ] App is in "Tested" or "Ready" status
- [ ] App is active/approved
- [ ] Frontend and backend configurations match
- [ ] Both servers restarted after .env changes

