# Epic OAuth Complete Setup Guide

This guide provides step-by-step instructions for setting up Epic OAuth integration, including generating RSA keys and configuring all required credentials.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Generate RSA Key Pair](#generate-rsa-key-pair)
3. [Epic App Orchard Configuration](#epic-app-orchard-configuration)
4. [Environment Variable Configuration](#environment-variable-configuration)
5. [Verification Steps](#verification-steps)

---

## Prerequisites

- Access to **Epic App Orchard** account
- OpenSSL installed (comes with Git Bash on Windows, or use WSL)
- Your application registered in Epic App Orchard

---

## Generate RSA Key Pair

### Step 1: Create Keys Directory

```bash
# Navigate to your backend directory
cd c:\Users\admin\Downloads\O2AI\Deploy\O2AI-Fax_Automation\backend

# Create keys directory if it doesn't exist
mkdir keys
```

### Step 2: Generate Private Key

```bash
# Generate a 2048-bit RSA private key
openssl genrsa -out keys/epic_fhir_private_key.pem 2048
```

**Output:**
```
Generating RSA private key, 2048 bit long modulus
.....+++
.....+++
e is 65537 (0x10001)
```

### Step 3: Generate Public Key from Private Key

```bash
# Extract the public key from the private key
openssl rsa -in keys/epic_fhir_private_key.pem -pubout -out keys/epic_fhir_public_key.pem
```

**Output:**
```
writing RSA key
```

### Step 4: View the Public Key (for Epic Upload)

```bash
# Display the public key content
cat keys/epic_fhir_public_key.pem
```

**Example Output:**
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
...
-----END PUBLIC KEY-----
```

**Important:** Copy this entire output (including the BEGIN and END lines) - you'll need it for Epic App Orchard.

### Step 5: Secure the Private Key

```bash
# Set appropriate permissions (Linux/Mac)
chmod 600 keys/epic_fhir_private_key.pem

# On Windows, you can skip this step or use:
# icacls keys\epic_fhir_private_key.pem /inheritance:r /grant:r "%USERNAME%:F"
```

---

## Epic App Orchard Configuration

### Step 1: Log into Epic App Orchard

1. Go to **[Epic App Orchard](https://apporchard.epic.com/)**
2. Sign in with your credentials
3. Navigate to **"My Apps"**

### Step 2: Select or Create Your Application

1. Click on your existing app (e.g., "O2AI Fax Automation")
2. Or click **"Create New App"** if you haven't created one yet

### Step 3: Configure OAuth Settings

1. Go to **"Build"** tab
2. Click **"OAuth 2.0"** or **"SMART on FHIR"**
3. Configure the following:

   **Application Type:**
   - Select: **"Confidential Client"** (for backend authentication)

   **SMART on FHIR Version:**
   - Select: **"R4"**

   **Application Audience:**
   - Select: **"Clinicians or Administrative Users"**

### Step 4: Add Redirect URI

1. In the **"Redirect URIs"** section, click **"Add"**
2. Enter your redirect URI **exactly** as it will be in your application:
   ```
   https://o2ai-fax-automation.centralus.cloudapp.azure.com/
   ```
   **Note:** Pay attention to trailing slashes - they must match exactly!

### Step 5: Configure Scopes

1. In the **"Scopes"** section, select the following:
   - ✅ `openid`
   - ✅ `profile`
   - ✅ `fhirUser`
   - ✅ `Patient.Read`
   - ✅ `Encounter.Read`
   - ✅ `DocumentReference.Create`

2. Click **"Save"** or **"Request Approval"** for each scope

### Step 6: Upload Public Key (Certificates & Secrets)

1. Navigate to **"Certificates & Secrets"** section
2. Click **"Add Public Key"** or **"Upload Certificate"**
3. Paste the **entire public key** content from Step 4 above:
   ```
   -----BEGIN PUBLIC KEY-----
   MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
   -----END PUBLIC KEY-----
   ```
4. Click **"Save"**

### Step 7: Generate Client Secret (Optional - for Confidential Clients)

1. In the **"Certificates & Secrets"** section
2. Click **"Generate New Client Secret"**
3. **IMPORTANT:** Copy the secret immediately - you won't be able to see it again!
   ```
   Example: zUlfi9rCFjjL9324YULQ4ObvaJiD**************************qOpamQjVo4IHpr1PnEuLJg==
   ```
4. Store it securely

### Step 8: Copy Your Client ID

1. In the **"Overview"** or **"Details"** section
2. Copy your **Client ID** (also called Application ID)
   ```
   Example: 8a3e9014*********62eabcf2642e
   ```

### Step 9: Configure JWKS URL (if required)

1. In the **"OAuth 2.0"** settings
2. Find **"JWKS URL"** or **"Public Key URL"** field
3. Enter your JWKS endpoint:
   ```
   https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json
   ```

---

## Environment Variable Configuration

### Backend Configuration

Edit `backend/.env` or `deployment/env.backend`:

```bash
# Epic OAuth Configuration
EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_FHIR_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
EPIC_CLIENT_SECRET="zUlfi9rCFjjL9324YULQ4ObvaJiDXZAJw9LZTFwFRjmI3CYuev1BXIVZVO5he1E9qOpamQjVo4IHpr1PnEuLJg=="
EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_SCOPES="openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create"

# Epic FHIR Private Key Path
EPIC_FHIR_PRIVATE_KEY_PATH=c:\Users\admin\Downloads\O2AI\Deploy\O2AI-Fax_Automation\backend\keys\epic_fhir_private_key.pem

# Base URL for JWKS endpoint
BASE_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com

# JWKS URL
EPIC_FHIR_JWKS_URL=https://o2ai-fax-automation.centralus.cloudapp.azure.com/.well-known/jwks.json
```

### Frontend Configuration

Edit `frontend/.env`:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Epic OAuth Configuration
VITE_EPIC_CLIENT_ID=8a3e9014-7a92-43bb-ae3a-62eabcf2642e
VITE_EPIC_REDIRECT_URI=https://o2ai-fax-automation.centralus.cloudapp.azure.com/
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
VITE_EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
VITE_EPIC_SCOPES=openid profile fhirUser Patient.Read Encounter.Read DocumentReference.Create
```

---

## Verification Steps

### Step 1: Verify Key Files Exist

```bash
# Check if keys were created
ls -la backend/keys/

# Expected output:
# epic_fhir_private_key.pem
# epic_fhir_public_key.pem
```

### Step 2: Verify Private Key Format

```bash
# View the private key (should show BEGIN RSA PRIVATE KEY)
openssl rsa -in backend/keys/epic_fhir_private_key.pem -check -noout
```

**Expected Output:**
```
RSA key ok
```

### Step 3: Verify Public Key Format

```bash
# View the public key
openssl rsa -pubin -in backend/keys/epic_fhir_public_key.pem -text -noout
```

**Expected Output:**
```
Public-Key: (2048 bit)
Modulus:
    00:...
Exponent: 65537 (0x10001)
```

### Step 4: Test JWKS Endpoint (After Starting Backend)

```bash
# Start your backend server first
cd backend
python -m uvicorn main:app --reload

# In another terminal, test the JWKS endpoint
curl http://localhost:8000/.well-known/jwks.json
```

**Expected Output:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "...",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

### Step 5: Verify Environment Variables Loaded

```bash
# In your backend, add a test endpoint or check logs
# The backend should log the loaded configuration on startup
```

---

## Quick Reference Commands

### Generate New Keys (if needed)

```bash
# Full command sequence
cd backend
mkdir -p keys
openssl genrsa -out keys/epic_fhir_private_key.pem 2048
openssl rsa -in keys/epic_fhir_private_key.pem -pubout -out keys/epic_fhir_public_key.pem
cat keys/epic_fhir_public_key.pem
```

### View Public Key for Epic Upload

```bash
cat backend/keys/epic_fhir_public_key.pem
```

### Verify Key Pair Match

```bash
# Generate fingerprints - they should match
openssl rsa -in backend/keys/epic_fhir_private_key.pem -pubout -outform PEM | openssl md5
openssl rsa -pubin -in backend/keys/epic_fhir_public_key.pem -pubout -outform PEM | openssl md5
```

---

## Troubleshooting

### Issue: "OpenSSL not found"

**Windows:**
```bash
# Use Git Bash (comes with Git for Windows)
# Or install OpenSSL from: https://slproweb.com/products/Win32OpenSSL.html
```

**Linux/Mac:**
```bash
# OpenSSL is usually pre-installed
# If not, install it:
sudo apt-get install openssl  # Ubuntu/Debian
brew install openssl          # Mac
```

### Issue: "Permission denied" when reading private key

```bash
# Fix permissions
chmod 600 backend/keys/epic_fhir_private_key.pem
```

### Issue: "Invalid key format" in Epic App Orchard

- Ensure you copied the **entire** public key including:
  - `-----BEGIN PUBLIC KEY-----`
  - All the encoded content
  - `-----END PUBLIC KEY-----`
- No extra spaces or line breaks

### Issue: "JWKS endpoint not accessible"

1. Verify backend is running
2. Check the endpoint: `http://localhost:8000/.well-known/jwks.json`
3. Ensure `EPIC_FHIR_PRIVATE_KEY_PATH` points to the correct file
4. Check backend logs for errors

---

## Security Best Practices

1. ✅ **Never commit private keys** to version control
   ```bash
   # Add to .gitignore
   echo "backend/keys/*.pem" >> .gitignore
   ```

2. ✅ **Secure file permissions**
   ```bash
   chmod 600 backend/keys/epic_fhir_private_key.pem
   ```

3. ✅ **Use environment variables** for secrets (never hardcode)

4. ✅ **Rotate keys periodically** (generate new keys every 6-12 months)

5. ✅ **Backup private keys securely** (encrypted storage)

6. ✅ **Use different keys** for development and production

---

## Summary Checklist

- [ ] Generated RSA private key (`epic_fhir_private_key.pem`)
- [ ] Generated RSA public key (`epic_fhir_public_key.pem`)
- [ ] Uploaded public key to Epic App Orchard
- [ ] Copied Client ID from Epic App Orchard
- [ ] Generated and copied Client Secret from Epic App Orchard
- [ ] Configured Redirect URI in Epic App Orchard
- [ ] Configured Scopes in Epic App Orchard
- [ ] Set JWKS URL in Epic App Orchard
- [ ] Updated `backend/.env` with all Epic variables
- [ ] Updated `frontend/.env` with Epic client configuration
- [ ] Verified JWKS endpoint is accessible
- [ ] Tested Epic OAuth login flow

---

**Status:** Ready for Epic OAuth integration testing!
