# Epic FHIR Data Storage - Configuration & Requirements

## What Data We Store in Epic

### DocumentReference Resource
The system stores extracted fax/document data in Epic as **DocumentReference** resources containing:

1. **Extracted Key-Value Pairs** (Base64-encoded JSON)
   - Patient demographics (Name, DOB, etc.)
   - Medical data (diagnoses, medications, vitals, etc.)
   - Document metadata (dates, provider info, etc.)
   - All fields extracted from the fax/document

2. **File Information**
   - Filename
   - Processing timestamp
   - Document type (LOINC code: 51847-2 "Document Analysis Result")

3. **Template Mapping** (if applicable)
   - Mapped values from template matching

## Required Epic Fields (MANDATORY)

Epic FHIR requires these fields for DocumentReference:

### 1. Patient ID (`subject.reference`)
- **Format**: `Patient/{EPIC_PATIENT_ID}`
- **Must be**: A real Epic Patient ID that exists in Epic's system
- **Example**: `Patient/e0w0LEDCYtfckT6N.CkJKCw3`

### 2. Encounter ID (`context.encounter`)
- **Format**: `Encounter/{EPIC_ENCOUNTER_ID}`
- **Must be**: A real Epic Encounter ID that exists in Epic's system
- **Example**: `Encounter/eVj5R7HsU-Q3MNZlIcnWJBQ3`

### 3. Other Required Fields
- `status`: "current"
- `docStatus`: "final"
- `type`: Document type with LOINC coding
- `content`: Base64-encoded data

## How We Find Patient ID (Priority Order)

1. **Manual Override** - `epic_patient_id` in request (highest priority)
2. **Patient Reference** - `patient_reference` in request
3. **Extract from Key-Value Pairs** - Searches for:
   - "Patient ID", "PatientID", "Epic Patient ID"
   - "Member ID", "MemberID"
   - "PID", "FHIR Patient ID"
4. **Search by Member ID** - If numeric ID found, searches Epic for real Patient ID
5. **Search by Demographics** - Uses Name + Date of Birth to find patient
6. **Fallback** - Uses valid patient: `erXuFYUfucBZaryVksYEcMg3`

## How We Find Encounter ID (Priority Order)

1. **Manual Override** - `epic_encounter_id` in request (highest priority)
2. **Encounter Reference** - `encounter_reference`, `encounter`, or `encounter_id` in request
3. **Extract from Key-Value Pairs** - Searches for:
   - "Encounter ID", "EncounterID", "Epic Encounter ID"
   - "Visit ID", "VisitID"
   - "Appointment ID", "EID"
4. **Automatic Search** - **NEW!** Searches Epic's Encounter API
   - Uses: `GET /Encounter?patient={patient_id}`
   - Finds encounters belonging to the Patient
   - Selects the first encounter found
   - Ensures Encounter and Patient belong together
5. **Fallback** - Uses configured encounter: `eH9J7LxX2Qf0R3ABC123`
   - ⚠️ **Warning**: May fail if it doesn't belong to the patient!

## Environment Variables

Set these in your `.env` file to customize the fallback Patient ID:

```bash
# Epic Fallback Patient ID (used when no patient found in document)
# MRN: 203712, External ID: Z6128
EPIC_FALLBACK_PATIENT_ID=eIXesllypH3M9tAA5WdJftQ3
```

**Note**: Encounter ID is no longer hardcoded. The system automatically searches Epic's Encounter API to find encounters belonging to the patient, ensuring they always match.

## Common Errors & Solutions

### Error: "Invalid subject received"
**Cause**: Patient ID doesn't exist in Epic's system
**Solution**: 
- Provide a real Epic Patient ID in request
- Ensure Member IDs are mapped to Epic Patient IDs
- Check that fallback Patient ID is valid for your Epic environment

### Error: "Invalid encounter received"
**Cause**: Encounter ID doesn't exist in Epic's system
**Solution**:
- Provide a real Epic Encounter ID in request
- Extract Encounter ID from document
- Ensure fallback Encounter ID is valid for your Epic environment
- **DO NOT use generated UUIDs** - Epic validates existence

## How to Provide IDs in Request

### Option 1: In Request Body
```json
{
  "response_data": { ... },
  "access_token": "...",
  "epic_patient_id": "REAL_EPIC_PATIENT_ID",
  "epic_encounter_id": "REAL_EPIC_ENCOUNTER_ID"
}
```

### Option 2: In Key-Value Pairs
Include these fields in your extracted data:
- "Patient ID" or "Epic Patient ID"
- "Encounter ID" or "Visit ID"

## Production Deployment

For production use:

1. **Update Fallback IDs**: Set environment variables to real production Epic IDs
2. **Extract IDs from Documents**: Ensure OCR extracts Patient ID and Encounter ID
3. **Implement ID Mapping**: Map Member IDs to Epic Patient IDs using Epic's Patient search API
4. **Validate Before Sending**: Check that IDs exist in Epic before attempting storage

## Testing in Epic Sandbox

Current test data (Patient and Encounter belong together):
- **Patient**: Derrick Marshall (ID: `erXuFYUfucBZaryVksYEcMg3`)
- **Encounter**: Valid encounter for this patient (ID: `eH9J7LxX2Qf0R3ABC123`)

These IDs belong to the same patient in Epic's system and will work for testing.

