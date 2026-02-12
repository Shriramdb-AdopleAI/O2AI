# Epic OAuth Debugging Guide

## What Happens Behind the Scenes

When you click "Login with Epic", here's what happens:

### Step 1: Frontend Redirects to Epic
```
Your App → Epic Authorization Server
URL: https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?...
```

**What Epic Checks:**
1. ✅ Does the `client_id` exist?
2. ✅ Does the `redirect_uri` match EXACTLY what's registered?
3. ✅ Are the `scopes` approved for this app?
4. ✅ Is the app approved/active?
5. ✅ Is the `aud` (audience) correct?

**If ANY of these fail → "OAuth2 Error"**

### Step 2: Epic Validates Everything
Epic compares your request with what's in Epic App Orchard:
- Client ID must match character-by-character
- Redirect URI must match EXACTLY (including trailing slash)
- All scopes must be in the approved list
- App must be in "Ready" or "Active" status

### Step 3: If Validation Passes
Epic shows login page → User logs in → Epic redirects back with `code`

### Step 4: If Validation Fails
Epic shows: "OAuth2 Error: Something went wrong trying to authorize the client"

## How to Break Down and Debug

### Method 1: Check Browser Console

1. Open DevTools (F12) → Console tab
2. Click "Login with Epic"
3. Look for the detailed logs showing:
   - Decoded parameters
   - Exact redirect URI
   - All scopes

### Method 2: Compare with Epic App Orchard

**In Epic App Orchard, check:**

1. **Client ID:**
   - Your console shows: `e5ce7227-159f-43f4-bf16-8a37cdc91928`
   - Epic App Orchard should show: `e5ce7227-159f-43f4-bf16-8a37cdc91928`
   - Must match EXACTLY (no spaces, no dashes in wrong places)

2. **Redirect URI:**
   - Your console shows: `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/`
   - Epic App Orchard should show: `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/`
   - **CRITICAL:** Check if it has trailing slash `/` or not
   - Must match EXACTLY

3. **Scopes:**
   - Your console shows: `openid profile fhirUser patient/*.read`
   - Epic App Orchard should have ALL of these approved:
     - `openid` ✓
     - `profile` ✓
     - `fhirUser` ✓
     - `patient/*.read` ✓

4. **App Status:**
   - Should be "Ready" or "Active"
   - Not "Pending" or "Inactive"

### Method 3: Test Redirect URI Variations

Try both versions in your `.env`:

**Version 1 (with trailing slash):**
```env
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com/
```

**Version 2 (without trailing slash):**
```env
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
```

Restart server after each change and test.

### Method 4: Test with Minimal Scopes

Try with just the required scopes:

```env
VITE_EPIC_SCOPES=openid fhirUser profile
```

Remove `patient/*.read` temporarily to see if that scope is causing issues.

### Method 5: Check Epic App Orchard Logs

1. Log into Epic App Orchard
2. Go to your application
3. Check for any error logs or audit trails
4. Look for failed authorization attempts

## Common Issues and Solutions

### Issue 1: Redirect URI Mismatch (90% of cases)

**Symptom:** OAuth2 Error immediately

**Solution:**
1. Copy the EXACT redirect URI from Epic App Orchard
2. Paste it in your `.env` file (don't modify it)
3. Restart server
4. Test again

### Issue 2: Client ID Not Found

**Symptom:** OAuth2 Error immediately

**Solution:**
1. Verify Client ID in Epic App Orchard
2. Check for typos
3. Ensure no extra spaces

### Issue 3: Scopes Not Approved

**Symptom:** OAuth2 Error immediately

**Solution:**
1. Check approved scopes in Epic App Orchard
2. Remove any unapproved scopes from `.env`
3. Start with minimal: `openid fhirUser profile`

### Issue 4: App Not Approved

**Symptom:** OAuth2 Error immediately

**Solution:**
1. Check app status in Epic App Orchard
2. Wait for approval if pending
3. Contact Epic support if needed

## Step-by-Step Debugging Process

1. **Check Console Logs:**
   - Open browser DevTools → Console
   - Click "Login with Epic"
   - Copy the "Decoded Parameters" section

2. **Compare with Epic App Orchard:**
   - Log into Epic App Orchard
   - Find your application
   - Compare each parameter:
     - Client ID ✓
     - Redirect URI ✓ (check trailing slash!)
     - Scopes ✓ (all must be approved)

3. **Fix Mismatches:**
   - Update `.env` file to match Epic App Orchard EXACTLY
   - Restart server
   - Test again

4. **If Still Failing:**
   - Try minimal scopes: `openid fhirUser profile`
   - Try redirect URI without trailing slash
   - Contact Epic support with your Client ID

## What to Tell Epic Support

If nothing works, contact Epic support with:

1. **Client ID:** `e5ce7227-159f-43f4-bf16-8a37cdc91928`
2. **Redirect URI:** `https://ai-doc-assist-dev.eastus.cloudapp.azure.com/`
3. **Error Message:** "OAuth2 Error: Something went wrong trying to authorize the client"
4. **Authorization URL:** (copy from console)
5. **App Status:** (from Epic App Orchard)

They can check their logs and tell you exactly what's wrong.

