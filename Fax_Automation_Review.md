Fax Automation Review 

 

1. Overview 

The Fax Automation system is an AI-powered document processing solution that automatically extracts structured data from fax documents and medical forms. The system uses advanced OCR (Optical Character Recognition) technology to convert scanned documents into machine-readable text, then employs intelligent key-value extraction to identify and extract critical information such as patient demographics, medical data, insurance information, and other structured fields. 

The extracted data is automatically validated, processed, and stored in Epic FHIR (Fast Healthcare Interoperability Resources) as Document Reference resources, enabling seamless integration with healthcare information systems. The system supports multi-tenant architecture with role-based access control, allowing different organizations to securely process and manage their documents independently. 

Key features include automated document processing, intelligent field extraction, null field tracking for quality assurance, template-based mapping for standardized documents, bulk processing capabilities, and comprehensive audit trails. The system helps healthcare organizations reduce manual data entry, improve accuracy, ensure compliance with healthcare data standards, and accelerate the integration of faxed documents into electronic health records. 

 

2. Architectural Diagram 

┌─────────────────────────────────────────────────────────────┐ 
│                    FAX AUTOMATION Frontend                  │ 
│              (React + Vite + Azure MSAL)                    │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│     Authentication via Azure AD (OAuth 2.0 / OpenID)        │ 
│              + Local User Authentication                    │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 

 
┌─────────────────────────────────────────────────────────────┐ 
│              Document Upload (PDF, PNG, JPG)                │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   Stored in Azure Blob Storage                              │ 
│   (Data Encryption at Rest + Access Control)                │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   OCR Processing (Azure Document Intelligence)              │ 
│   + LayoutLMv3 for Document Understanding                   │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   Key-Value Extraction (Azure OpenAI GPT-4o)                │ 
│   + LangChain Orchestration                                 │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   Data Validation & Template Mapping                        │ 
│   + Null Field Tracking                                     │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   Epic FHIR Integration (DocumentReference)                  │ 
│   Patient & Encounter Matching                              │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   PostgreSQL Database Storage                               │ 
│   (Processed Files, Users, Sessions, Ground Truth)          │ 
└───────────────────────┬─────────────────────────────────────┘ 
                        │ 
                        ▼ 
┌─────────────────────────────────────────────────────────────┐ 
│   Results Available in Frontend                             │ 
│   + Export to Excel/JSON                                    │ 
└─────────────────────────────────────────────────────────────┘ 

 

 

3. Tech Stack 

Framework 

Application 

Version 

Port 

Estimated cost (Azure List price) 

Language 

Python & FastAPI 

3.12+ / 0.115.12 

8000 (Default) 

No cost 

LLM 

Azure OpenAI GPT 

gpt-4o / 2024-02-15-preview 

- 

Input tokens: about 0.005 USD per 1,000 tokens. 
Output tokens: about 0.015 USD per 1,000 tokens. 

OCR Engine 

Azure Document Intelligence 

2024-02-01 

- 

$1.50 per 1,000 pages (prebuilt) 

Cloud service 

Microsoft Azure 

- 

- 

App Service P1v3 (4 vCPU, 14GB RAM): ~$292/month 

LLM Orchestration 

LangChain 

0.1.0+ 

- 

No cost 

Authentication 

OAuth 2.0 (Azure AD), MSAL, Local Auth 

- 

- 

Azure AD Free tier: Free (up to 50,000 MAU) 

Document Storage 

Azure Blob Storage 

- 

443 (HTTPS) 

Hot tier: ~$21/month (1TB storage) + $0.05/10K transactions 

Database 

PostgreSQL 

14+ 

5432 

No cost 

Task Queue 

Celery + Redis 

5.3.0+ / 5.0.0+ 

6379 

No cost 

Frontend Framework 

React + Vite 

18.3.1 / 5.4.8 

5173 

No cost 

Healthcare Integration 

Epic FHIR API 

R4 

443 (HTTPS) 

No cost but business mail is required 

PDF Processing 

PyMuPDF, pdf2image 

- 

- 

No cost 

Excel Export 

openpyxl, pandas 

3.1.0+ / 2.0.0+ 

- 

No cost 

 

 

 

4. Database Schema 

users 

Column 

Type 

Description 

id (PK) 

INTEGER 

Primary Key (Identity) 

username (UK) 

VARCHAR(50) 

Unique username for login 

email (UK) 

VARCHAR(100) 

Unique email address 

hashed_password 

VARCHAR(255) 

Bcrypt hashed password 

is_active 

BOOLEAN 

Account active status 

is_admin 

BOOLEAN 

Administrator flag 

created_at 

TIMESTAMP 

Account creation timestamp 

last_login 

TIMESTAMP 

Last login timestamp 

 

user_sessions 

Column 

Type 

Description 

id (PK) 

INTEGER 

Primary Key (Identity) 

user_id (FK) 

INTEGER 

Foreign Key to users.id 

session_token (UK) 

VARCHAR(255) 

Unique session token 

tenant_id (UK) 

VARCHAR(255) 

Unique tenant identifier 

created_at 

TIMESTAMP 

Session creation timestamp 

last_activity 

TIMESTAMP 

Last activity timestamp 

is_active 

BOOLEAN 

Session active status 

 

processed_files 

Column 

Type 

Description 

id (PK) 

INTEGER 

Primary Key (Identity) 

file_hash (UK) 

VARCHAR(64) 

SHA256 hash for deduplication 

processing_id 

VARCHAR(255) 

Unique processing identifier 

tenant_id 

VARCHAR(255) 

Tenant identifier 

filename 

VARCHAR(500) 

Original filename 

source_blob_path 

VARCHAR(1000) 

Azure Blob source path 

processed_blob_path 

VARCHAR(1000) 

Azure Blob processed path 

processed_data 

JSONB 

Complete extracted data (key-value pairs, confidence scores) 

ocr_confidence_score 

VARCHAR(10) 

OCR confidence score 

processing_time 

VARCHAR(20) 

Processing duration 

has_corrections 

BOOLEAN 

Whether manual corrections were made 

last_corrected_by 

VARCHAR(100) 

User who made last correction 

last_corrected_at 

TIMESTAMP 

Last correction timestamp 

created_at 

TIMESTAMP 

Record creation timestamp 

updated_at 

TIMESTAMP 

Last update timestamp 

 

ground_truth 

Column 

Type 

Description 

id (PK) 

INTEGER 

Primary Key (Identity) 

processing_id 

VARCHAR(255) 

Processing identifier 

tenant_id 

VARCHAR(255) 

Tenant identifier 

filename 

VARCHAR(500) 

Document filename 

ground_truth 

TEXT 

Validated ground truth data 

ocr_text 

TEXT 

Extracted OCR text 

metadata_json 

JSONB 

Additional metadata 

created_at 

TIMESTAMP 

Record creation timestamp 

updated_at 

TIMESTAMP 

Last update timestamp 

 

null_field_tracking 

Column 

Type 

Description 

id (PK) 

INTEGER 

Primary Key (Identity) 

processing_id 

VARCHAR(255) 

Processing identifier 

tenant_id 

VARCHAR(255) 

Tenant identifier 

filename 

VARCHAR(500) 

Document filename 

name_is_null 

BOOLEAN 

Patient name missing flag 

dob_is_null 

BOOLEAN 

Date of birth missing flag 

member_id_is_null 

BOOLEAN 

Member ID missing flag 

address_is_null 

BOOLEAN 

Address missing flag 

gender_is_null 

BOOLEAN 

Gender missing flag 

insurance_id_is_null 

BOOLEAN 

Insurance ID missing flag 

null_field_count 

INTEGER 

Total count of null fields 

null_field_names 

JSONB 

Array of null field names 

all_extracted_fields 

JSONB 

Complete extracted data for reference 

created_at 

TIMESTAMP 

Record creation timestamp 

 

 

 

Relationships 

- users and user_sessions: One-to-Many relationship (One user can have multiple active sessions) 

- processed_files: Independent table (no foreign keys, uses tenant_id for multi-tenancy) 

- ground_truth: Independent table (linked by processing_id, not foreign key) 

- null_field_tracking: Independent table (linked by processing_id, not foreign key) 

 