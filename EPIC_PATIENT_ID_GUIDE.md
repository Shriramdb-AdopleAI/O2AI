# How to Get Epic Patient IDs

## Overview
Epic Patient IDs are alphanumeric identifiers (e.g., `eUEKdnYPKuCXlSq8WIYaPTA3`) that uniquely identify patients in Epic's FHIR system. They are different from member IDs (numeric like "555", "1234567890").

## Methods to Get Epic Patient IDs

### Method 1: Search Epic FHIR API (If Patient.Read Permission Available)

If your Epic app has `Patient.Read` permission, you can search for patients by member ID or other identifiers:

```bash
# Search by member ID
GET https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient?identifier=MB|555

# Search by Medicare ID
GET https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient?identifier=http://hl7.org/fhir/sid/us-medicare|1234567890

# Search by name and DOB
GET https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient?name=Smith&birthdate=1990-01-01
```

**Response Example:**
```json
{
  "resourceType": "Bundle",
  "entry": [{
    "resource": {
      "resourceType": "Patient",
      "id": "eUEKdnYPKuCXlSq8WIYaPTA3",  // ← This is the Epic Patient ID
      "identifier": [{
        "system": "MB",
        "value": "555"  // ← Member ID
      }]
    }
  }]
}
```

### Method 2: From Epic User Interface (MyChart, Epic Hyperspace)

1. **Log into Epic Hyperspace** (if you have access)
2. **Search for a patient** by name, DOB, or member ID
3. **Open the patient's chart**
4. **Look at the URL** - the Patient ID is often in the URL:
   ```
   https://epic.example.com/Chart/Patient/eUEKdnYPKuCXlSq8WIYaPTA3
   ```
   The ID `eUEKdnYPKuCXlSq8WIYaPTA3` is the Epic Patient ID.

### Method 3: From Epic FHIR Test Patient (Sandbox/Development)

If you're using Epic's sandbox/test environment:

1. **Epic App Orchard** → **Test Patients**
2. **Select a test patient**
3. **View Patient Details** → The Patient ID is displayed

**Common Test Patient IDs (Epic Sandbox):**
- `eUEKdnYPKuCXlSq8WIYaPTA3` (example format)
- Check Epic's documentation for current test patient IDs

### Method 4: Create a Mapping Table

If you have access to Epic's database or can query patient data:

1. **Query Epic's database** (if you have access) to get:
   - Member ID → Epic Patient ID mapping
2. **Store in a mapping table** in your application:
   ```json
   {
     "555": "eUEKdnYPKuCXlSq8WIYaPTA3",
     "1234567890": "eKvkb8V4sgTKL9nm3MtDjXw3"
   }
   ```
3. **Use the mapping** before sending to Epic:
   ```python
   member_id = "555"
   epic_patient_id = mapping_table.get(member_id)
   if epic_patient_id:
       # Use epic_patient_id for Epic storage
   ```

### Method 5: Request from Epic Support/IT Team

If you don't have direct access:

1. **Contact your Epic IT team** or **Epic support**
2. **Request a list of Patient IDs** mapped to member IDs
3. **Or request Patient.Read permission** to search for patients programmatically

## How to Use Epic Patient IDs in Your Code

### Option 1: Manual Override (Recommended)
```json
{
  "response_data": {
    "epic_patient_id": "eUEKdnYPKuCXlSq8WIYaPTA3",
    "epic_encounter_id": "eKvkb8V4sgTKL9nm3MtDjXw3",
    "key_value_pairs": {
      "Member ID": "555",
      "Name": "John Doe",
      // ... other fields
    }
  },
  "access_token": "your_epic_token"
}
```

### Option 2: In patient_reference Field
```json
{
  "response_data": {
    "patient_reference": "Patient/eUEKdnYPKuCXlSq8WIYaPTA3",
    "key_value_pairs": { ... }
  }
}
```

### Option 3: In Key-Value Pairs
```json
{
  "response_data": {
    "key_value_pairs": {
      "Epic Patient ID": "eUEKdnYPKuCXlSq8WIYaPTA3",
      "Member ID": "555",
      // ... other fields
    }
  }
}
```

## Automatic Patient ID Search (If Patient.Read Permission Available)

The code already attempts to search for Epic Patient IDs automatically:

1. **Detects numeric Patient IDs** (member IDs like "555")
2. **Searches Epic FHIR API** using multiple identifier systems
3. **Maps member ID to Epic Patient ID** if found
4. **Uses the real Epic Patient ID** for storage

**To enable this:**
- Add `Patient.Read` to your Epic app's scopes/permissions
- Update `EPIC_SCOPES` environment variable:
  ```
  EPIC_SCOPES=openid profile fhirUser system/DocumentReference.write Patient.Read
  ```

## Troubleshooting

### Error: "Invalid subject received"
- **Cause**: Patient ID doesn't exist in Epic's system
- **Solution**: Use a real Epic Patient ID that exists in Epic

### Error: "403 Forbidden" when searching for patients
- **Cause**: `Patient.Read` permission not in scope
- **Solution**: Add `Patient.Read` to your Epic app permissions in Epic App Orchard

### Error: "Patient not found"
- **Cause**: Member ID doesn't exist in Epic, or identifier system is different
- **Solution**: Verify the member ID exists in Epic, or use a different identifier system

## Next Steps

1. **Check your Epic app permissions** in Epic App Orchard
2. **Add Patient.Read permission** if you want automatic patient search
3. **Get test patient IDs** from Epic's sandbox/test environment
4. **Create a mapping table** if you have access to Epic's patient data
5. **Contact Epic support** if you need help getting Patient IDs

