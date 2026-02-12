# Epic Login Credentials Guide

## ✅ Good News: OAuth Flow is Working!

The OAuth authorization request is **working correctly**! Epic accepted your request and is showing the login page. The issue now is with the **Epic user credentials** (username/password).

## Understanding Epic OAuth Flow

Epic OAuth has **two types of credentials**:

### 1. OAuth Client Credentials (✅ You have these)
- **Client ID**: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
- **Client Secret**: (configured in backend)
- **Purpose**: Identifies your application to Epic

### 2. Epic User Credentials (❌ You need these)
- **Username**: Epic user ID (e.g., `O2aicorp`)
- **Password**: Epic user password
- **Purpose**: Authenticates the actual user logging in

## What Credentials Do You Need?

For Epic FHIR OAuth, you need **valid Epic user credentials** that:

1. **Have access to Epic FHIR API**
2. **Are authorized** for your Epic instance
3. **Match the environment** you're using (sandbox vs production)

## Where to Get Epic User Credentials

### Option 1: Epic App Orchard Sandbox (Recommended for Testing)

1. **Log into Epic App Orchard**
2. **Go to your application** ("Authentication")
3. **Check the "Sandbox" or "Testing" section**
4. **Look for test credentials** provided by Epic
5. **Common locations**:
   - App documentation
   - Sandbox access section
   - Testing credentials tab

### Option 2: Contact Epic Support

1. **Contact Epic Support** through App Orchard
2. **Request sandbox/test credentials** for your app
3. **Provide your Client ID**: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
4. **Ask for**: Test user credentials for FHIR API access

### Option 3: Contact Your Epic Administrator

If you're integrating with a specific Epic instance:

1. **Contact the Epic administrator** for that organization
2. **Request FHIR-enabled user credentials**
3. **Explain**: You need credentials for OAuth testing
4. **Provide**: Your Client ID and app details

### Option 4: Epic MyChart Test Accounts (If Applicable)

If your app uses MyChart integration:

1. **Check Epic MyChart documentation**
2. **Look for test patient accounts**
3. **Use MyChart test credentials**

## Common Epic Credential Formats

### Username Formats:
- **User ID**: `O2aicorp` (what you're using)
- **Email**: `user@example.com`
- **Epic User ID**: Usually alphanumeric

### Password:
- **Case-sensitive**
- **May have special requirements** (length, complexity)
- **May expire** (check if password needs reset)

## Troubleshooting "Invalid Credentials" Error

The error message shows:
```
"You entered an invalid user ID, password, or other type of authentication credential."
LoginModeUserID: "O2aicorp"
```

### Possible Issues:

1. **Wrong Password** ⚠️
   - Password might be incorrect
   - Password might have expired
   - Password might need to be reset

2. **Wrong Username Format** ⚠️
   - Username might need to be in different format
   - Might need email instead of user ID
   - Might need domain prefix (e.g., `domain\O2aicorp`)

3. **User Not Authorized** ⚠️
   - User might not have FHIR API access
   - User might not be active
   - User might not be in correct department/role

4. **Environment Mismatch** ⚠️
   - Using production credentials in sandbox (or vice versa)
   - Credentials don't match the Epic instance

5. **Account Locked** ⚠️
   - Too many failed login attempts
   - Account might be locked
   - Need to contact Epic admin to unlock

## Steps to Resolve

### Step 1: Verify Username Format
Try different username formats:
- `O2aicorp` (current)
- `O2AICORP` (uppercase)
- `o2aicorp` (lowercase)
- Email format if applicable

### Step 2: Check Password
- Verify password is correct
- Check if password has expired
- Try resetting password (if possible)

### Step 3: Contact Epic Support
1. **Log into Epic App Orchard**
2. **Go to Support section**
3. **Create a support ticket** with:
   - Your Client ID: `f139ac22-65b3-4dd4-b10d-0960e6f14850`
   - Your app name: "Authentication"
   - Issue: Need test user credentials for OAuth login
   - Current username: `O2aicorp`

### Step 4: Check Epic Documentation
1. **Review Epic FHIR documentation**
2. **Look for "Testing" or "Sandbox" section**
3. **Check for test credentials** or sandbox access

## For Development/Testing

If you're in development/testing phase:

1. **Use Epic Sandbox** (if available)
2. **Request test credentials** from Epic
3. **Use Epic-provided test accounts** (not production accounts)

## Important Notes

⚠️ **Do NOT use production user credentials** for testing unless:
- You have explicit permission
- You're testing in production environment
- You understand the security implications

✅ **Use sandbox/test credentials** for development

## Next Steps

1. ✅ **OAuth flow is working** - No code changes needed
2. ⏳ **Get valid Epic user credentials** from Epic Support or administrator
3. ⏳ **Test login** with correct credentials
4. ⏳ **Verify user has FHIR API access**

## Summary

- **OAuth Configuration**: ✅ Working correctly
- **Authorization Request**: ✅ Accepted by Epic
- **Login Page**: ✅ Displaying correctly
- **User Credentials**: ❌ Need valid Epic user credentials

The issue is **not with your code** - it's that you need valid Epic user credentials to complete the login. Contact Epic Support or your Epic administrator to get test credentials for your app.

