# Epic FHIR Write Implementation

This document describes the implementation of storing processed document data in Epic using POST /Observation.

## Overview

When a user uploads a document and clicks "Process", the system will:
1. Process the document with OCR and AI extraction
2. Automatically store the results in Epic as an Observation resource
3. The Observation will be visible in Epic's UI under "Results / Chart Review"

## Implementation Details

### 1. Frontend Changes

#### Updated Scopes (`frontend/src/services/epicAuthConfig.js`)
- Added `patient/Observation.write` to the default scopes
- This scope must be approved in Epic App Orchard

#### New Epic Write Service (`frontend/src/services/epicWriteService.js`)
- `exchangeEpicToken(code)`: Exchanges authorization code for access token with write permission
- `storeObservationInEpic(observationData, accessToken)`: Stores Observation in Epic FHIR
- `buildObservationData(processedResult, filename)`: Builds Observation data from processed results
- Token management functions for storing/retrieving Epic write tokens

#### Updated Processing Flow (`frontend/src/App.jsx`)
- After processing completes, automatically checks for Epic write token
- If token exists, stores Observation in Epic
- If token doesn't exist, logs a message (user can login with Epic to enable storage)

### 2. Backend Changes

#### New Endpoints (`backend/api/router.py`)

**POST `/api/v1/epic/exchange-token`**
- Exchanges Epic authorization code for access token with write permission
- Requires: `code` (authorization code from Epic)
- Returns: `access_token`, `token_type`, `expires_in`

**POST `/api/v1/epic/store-observation`**
- Stores Observation resource in Epic FHIR
- Requires:
  - `observation_data`: Object containing key-value pairs, filename, processing_id, etc.
  - `access_token`: Epic access token with write permission
- Returns: Success status, FHIR ID, and Observation resource

#### Observation Structure
The Observation is structured for visibility in Epic's UI:
- **Category**: Imaging (appears in Results / Chart Review)
- **Code**: LOINC 36626-4 (AI Analysis Result)
- **Value**: Formatted key-value pairs as readable string
- **Component**: Full JSON data in structured component
- **Subject**: Patient reference (from processed data or user tenant)

## Configuration

### Environment Variables

**Frontend (.env)**
```env
VITE_EPIC_SCOPES=openid profile fhirUser patient/Observation.write
VITE_EPIC_CLIENT_ID=your-client-id
VITE_EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
VITE_EPIC_AUTHORIZATION_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
VITE_EPIC_AUDIENCE=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
```

**Backend (.env)**
```env
EPIC_CLIENT_ID=your-client-id
EPIC_CLIENT_SECRET=your-client-secret
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_REDIRECT_URI=https://ai-doc-assist-dev.eastus.cloudapp.azure.com
EPIC_FHIR_SERVER_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
```

### Epic App Orchard Configuration

**Required Settings:**
1. **Application Audience**: User-authorized write (SMART on FHIR)
2. **Scopes**: Must include `patient/Observation.write`
3. **Status**: Must be "Ready" or "Active"
4. **Incoming APIs**: `Observation.Create` must be selected

## Usage Flow

### 1. User Login with Epic
- User clicks "Login with Epic"
- Redirected to Epic login page
- After login, Epic redirects back with authorization code
- System exchanges code for access token (with write permission)
- Token is stored in localStorage for future use

### 2. Document Processing
- User uploads document
- User clicks "Process" button
- Document is processed with OCR and AI extraction
- After processing completes:
  - System checks for Epic write token
  - If token exists, automatically stores Observation in Epic
  - If token doesn't exist, logs message (processing still succeeds)

### 3. Viewing Data in Epic
- Observation appears in Epic's UI under:
  - **Results / Chart Review**
- Observation contains:
  - Formatted key-value pairs (readable format)
  - Full JSON data in component
  - Document filename and processing metadata

## Error Handling

- If Epic token exchange fails, processing continues (data not stored in Epic)
- If Epic store fails, processing continues (data not stored in Epic)
- Errors are logged to console for debugging
- User is not blocked from using the application if Epic operations fail

## Testing

### Test Epic Write Flow

1. **Login with Epic**
   - Click "Login with Epic"
   - Complete Epic login
   - Verify token is stored (check browser console)

2. **Process Document**
   - Upload a document
   - Click "Process"
   - Wait for processing to complete
   - Check browser console for Epic store success message

3. **Verify in Epic**
   - Log into Epic Hyperspace
   - Navigate to patient chart
   - Check "Results / Chart Review"
   - Verify Observation appears with extracted data

## Troubleshooting

### Data Not Stored in Epic

1. **Check Epic Token**
   - Open browser console
   - Check for Epic write token: `localStorage.getItem('epic_write_token')`
   - If null, user needs to login with Epic again

2. **Check Scopes**
   - Verify `patient/Observation.write` is in scopes
   - Verify scope is approved in Epic App Orchard

3. **Check Backend Logs**
   - Look for Epic store errors
   - Check token exchange errors
   - Verify FHIR server URL is correct

4. **Check Epic App Orchard**
   - Verify app is "Ready" or "Active"
   - Verify `Observation.Create` is in Incoming APIs
   - Verify redirect URI matches exactly

### Observation Not Visible in Epic UI

1. **Check Patient Reference**
   - Verify patient ID is correct in Observation
   - Check if patient exists in Epic

2. **Check Observation Structure**
   - Verify category is "imaging"
   - Verify code is LOINC 36626-4
   - Verify status is "final"

3. **Check Epic Permissions**
   - Verify user has permission to view Observations
   - Check Epic user role and permissions

## Security Notes

- Epic write tokens are stored in localStorage (browser only)
- Tokens expire after 1 hour (Epic default)
- Tokens are not sent to backend except for Epic API calls
- Authorization codes are tracked to prevent reuse
- All Epic API calls use HTTPS

## Future Enhancements

- Add UI notification when data is stored in Epic
- Add option to manually trigger Epic store
- Add support for storing multiple Observations (batch)
- Add support for DiagnosticReport and DocumentReference resources
- Add Epic patient ID selection UI
- Add Epic store status indicator in UI

