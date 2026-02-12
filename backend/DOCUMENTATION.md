# Backend API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Modules](#core-modules)
4. [API Endpoints](#api-endpoints)
5. [Services](#services)
6. [Authentication & Authorization](#authentication--authorization)
7. [Database Models](#database-models)
8. [Configuration](#configuration)
9. [Processing Workflow](#processing-workflow)
10. [Error Handling](#error-handling)

---

## Overview

The O2AI Fax Automation backend is a FastAPI-based service that provides OCR (Optical Character Recognition) processing, intelligent text extraction, and document management capabilities. It integrates with Azure services for OCR, AI-powered text processing, and cloud storage.

### Key Features

- **Multi-Engine OCR**: Azure Document Intelligence for high-accuracy text extraction
- **AI-Powered Extraction**: Azure OpenAI GPT for intelligent key-value pair extraction
- **Multi-Tenant Support**: Isolated data processing per tenant
- **Template Management**: Custom Excel templates for structured data extraction
- **Azure Blob Storage**: Scalable file storage with confidence-based organization
- **Asynchronous Processing**: Celery-based background task processing
- **Batch Processing**: Process multiple documents in parallel
- **Excel Export**: Export processed data to Excel format
- **User Authentication**: JWT-based authentication with role management

---

## Architecture

### Directory Structure

```
backend/
├── api/                          # API routes and endpoints
│   ├── auth.py                   # Authentication endpoints
│   └── router.py                 # Main OCR processing routes
├── auth/                         # Authentication utilities
│   ├── admin_setup.py            # Default user creation
│   └── auth_utils.py             # JWT and user management
├── core/                         # Core processing modules
│   ├── agent_flow.py             # LangGraph agent workflow
│   ├── celery_app.py             # Celery configuration
│   ├── celery_tasks.py           # Background task definitions
│   ├── enhanced_text_processor.py # GPT-powered text processing
│   ├── excel_exporter.py         # Excel export functionality
│   ├── image_preprocessor.py     # Image enhancement (currently disabled)
│   ├── layoutlmv3_service.py     # LayoutLMv3 text finding service
│   └── ocr_engines.py            # OCR engine implementations
├── models/                       # Database models
│   └── database.py               # SQLAlchemy models
├── services/                     # External service integrations
│   ├── azure_blob_service.py    # Azure Blob Storage
│   └── template_mapper.py        # Template mapping logic
├── utility/                      # Utility functions
│   ├── config.py                 # Configuration management
│   ├── file_processor.py         # File handling utilities
│   └── utils.py                  # General utilities and OCR functions
├── main.py                       # FastAPI application entry point
└── requirements.txt              # Python dependencies
```

### Technology Stack

- **FastAPI**: Modern, fast web framework
- **SQLAlchemy**: ORM for database operations
- **Celery**: Distributed task queue for async processing
- **Redis**: Message broker and result backend for Celery
- **Azure Document Intelligence**: OCR processing
- **Azure OpenAI**: GPT-powered text processing
- **Azure Blob Storage**: File storage
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server

---

## Core Modules

### 1. Main Application (`main.py`)

The FastAPI application entry point that:
- Initializes the FastAPI app with CORS middleware
- Includes API routers for OCR and authentication
- Sets up startup event handlers for default user creation
- Configures global exception handling
- Checks Redis connection for Celery

**Key Functions:**
- `startup_event()`: Creates default admin and test users, checks Redis connection
- `root()`: Root endpoint returning API information
- `global_exception_handler()`: Catches unhandled exceptions

### 2. OCR Engines (`core/ocr_engines.py`)

Implements the Azure Document Intelligence OCR engine.

**Classes:**
- `AzureDocumentIntelligenceOCR`: Main OCR engine class
  - `is_available()`: Checks if OCR engine is configured
  - `extract_text()`: Extracts text from PDF/image files with positioning data
  - `_analyze_document_sync()`: Synchronous wrapper for document analysis

- `OCREngineFactory`: Factory for creating OCR engines
  - `create_engine()`: Creates an OCR engine instance
  - `get_available_engines()`: Returns list of available engines

**Features:**
- Extracts text with bounding box coordinates
- Provides confidence scores per line and word
- Supports PDF and image formats
- Returns structured data with page-level, line-level, and word-level information

### 3. Enhanced Text Processor (`core/enhanced_text_processor.py`)

AI-powered text processing using Azure OpenAI GPT.

**Classes:**
- `EnhancedTextProcessor`: Main text processing class
  - `is_available()`: Checks if Azure OpenAI is configured
  - `process_without_template()`: Extracts key-value pairs automatically
  - `process_with_template()`: Extracts data based on template structure
  - `correct_value()`: Corrects a specific key-value pair using LLM
  - `analyze_low_confidence_pairs()`: Analyzes low-confidence extractions with vision API
  - `classify_document_type()`: Classifies document type (Medical, Invoice, etc.)

**Features:**
- Automatic key-value extraction from unstructured text
- Template-based structured extraction
- Low-confidence pair analysis with document image
- Document type classification
- Fallback to basic pattern matching if LLM unavailable
- Address formatting with special handling for ordinals

### 4. Celery Tasks (`core/celery_tasks.py`)

Background task processing for asynchronous document handling.

**Tasks:**
- `process_document`: Process a single document
  - Uploads source file to blob storage
  - Runs OCR extraction
  - Performs AI-powered extraction
  - Maps to template if provided
  - Uploads processed JSON
  - Reorganizes files by confidence score

- `process_batch_documents`: Process multiple documents in parallel
  - Submits individual tasks to Celery workers
  - Tracks progress across all files
  - Returns consolidated results

- `process_bulk_file`: Process files from bulk upload folder
  - Downloads from blob storage
  - Processes with OCR and extraction
  - Uploads results to appropriate confidence folder

- `check_bulk_processing_source`: Periodic task (every 5 minutes)
  - Checks bulk processing/source folder for new files
  - Processes new files automatically
  - Skips already processed files

**Features:**
- Asynchronous processing to avoid blocking API requests
- Progress tracking with task state updates
- Error handling and retry logic
- Windows compatibility with nest_asyncio

### 5. Celery Configuration (`core/celery_app.py`)

Configures Celery for distributed task processing.

**Configuration:**
- Redis as message broker and result backend
- Task routing to "processing" queue
- Periodic tasks via Celery Beat
- Windows support with solo worker pool
- Connection retry logic for Redis

**Functions:**
- `check_redis_connection()`: Validates Redis connection and write capability

### 6. Image Preprocessor (`core/image_preprocessor.py`)

**Note**: Currently disabled - files are passed directly to Document Intelligence without preprocessing.

Advanced image preprocessing capabilities (available but not used):
- Resolution enhancement
- Skew correction
- Contrast enhancement
- Binarization
- Noise removal
- Perspective correction

### 7. Excel Exporter (`core/excel_exporter.py`)

Exports processed OCR results to Excel format.

**Classes:**
- `ExcelExporter`: Excel export functionality
  - `export_individual_file()`: Export single file results
  - `export_consolidated_files()`: Export batch results
  - `create_individual_excel()`: Create Excel from processed data
  - `create_individual_excel_files()`: Create ZIP with multiple Excel files

**Excel Structure:**
- Sheet 1: Key-Value Pairs
- Sheet 2: Raw OCR Text (optional)
- Sheet 3: Metadata (optional)
- Sheet 4: Template Mapping (if template used)

### 8. LayoutLMv3 Service (`core/layoutlmv3_service.py`)

Service for finding text positions in documents using OCR data.

**Classes:**
- `LayoutLMv3Service`: Text finding service
  - `find_text_in_document()`: Finds text with bounding boxes
  - `_find_text_from_ocr_data()`: Searches OCR data for text matches

**Features:**
- Uses OCR data from Azure Document Intelligence (not LayoutLMv3 model)
- Returns bounding box coordinates for matched text
- Supports exact phrase matching, substring matching, and word-level matching
- Handles long text with prefix matching

### 9. Agent Flow (`core/agent_flow.py`)

LangGraph-based agent workflow for document processing.

**Components:**
- `AgentState`: TypedDict for agent state
- `node_ocr()`: OCR processing node
- `node_extract()`: Text extraction node
- `node_map_template()`: Template mapping node
- `build_graph()`: Constructs the agent graph
- `run_agent()`: Executes the agent workflow

---

## Services

### 1. Azure Blob Service (`services/azure_blob_service.py`)

Manages file storage in Azure Blob Storage with confidence-based organization.

**Classes:**
- `AzureBlobService`: Blob storage service

**Key Methods:**
- `upload_source_document()`: Uploads source files to blob storage
- `upload_processed_json()`: Uploads processed JSON results
- `reorganize_source_file_by_confidence()`: Moves files based on confidence score
- `list_tenant_files()`: Lists files for a specific tenant
- `download_file()`: Downloads files from blob storage
- `delete_file()`: Deletes files from blob storage
- `find_source_file_from_processed()`: Finds source file from processed file path

**Folder Structure:**
```
main/
├── Above-95%/
│   ├── source/
│   │   └── {tenant_id}/
│   │       └── {filename}_{timestamp}
│   └── processed/
│       └── {tenant_id}/
│           └── {timestamp}_{filename}_extracted_data.json
└── needs to be reviewed/
    ├── source/
    │   └── {tenant_id}/
    │       └── {filename}_{timestamp}
    └── processed/
        └── {tenant_id}/
            └── {timestamp}_{filename}_extracted_data.json
```

**Confidence-Based Organization:**
- Files with OCR confidence >= 95% go to "Above-95%" folder
- Files with OCR confidence < 95% go to "needs to be reviewed" folder
- Automatic reorganization after OCR processing

### 2. Template Mapper (`services/template_mapper.py`)

Manages Excel templates and maps extracted data to template fields.

**Classes:**
- `TemplateMapper`: Template management service
- `TemplateField`: Dataclass for template field definition
- `MappingResult`: Dataclass for mapping results

**Key Methods:**
- `upload_template()`: Uploads and parses Excel template
- `get_template()`: Retrieves template metadata
- `list_templates()`: Lists all templates for a tenant
- `map_document_to_template()`: Maps extracted data to template fields
- `generate_consolidated_excel()`: Generates Excel with all mapped documents
- `delete_template()`: Deletes a template

**Template Structure:**
- Excel files with field definitions
- Supports multiple sheets
- Auto-detects field names from Key/Field columns or headers
- Maps extracted key-value pairs to template fields

---

## API Endpoints

### Authentication Endpoints (`api/auth.py`)

**Base Path**: `/api/v1/auth`

- `POST /register`: Register new user
- `POST /login`: User login (returns JWT token)
- `POST /login/azure-ad`: Azure AD OAuth login
- `POST /logout`: Logout user (deactivates sessions)
- `GET /me`: Get current user information
- `GET /users`: Get all users (admin only)
- `PUT /users/{user_id}`: Update user (admin only)
- `DELETE /users/{user_id}`: Delete user (admin only)
- `GET /sessions`: Get current user's active sessions

### OCR Processing Endpoints (`api/router.py`)

**Base Path**: `/api/v1`

#### Health Check
- `GET /health`: Health check endpoint

#### Document Processing
- `POST /ocr/enhanced/process`: Process single document
  - Parameters: `file`, `template_id` (optional), `apply_preprocessing`, `enhance_quality`, `include_raw_text`, `include_metadata`, `use_blob_workflow`
  - Returns: Processing results with key-value pairs, confidence scores, and blob storage info

- `POST /ocr/enhanced/batch/process`: Process multiple documents
  - Parameters: `files` (list), `template_id` (optional), other processing options
  - Returns: Batch processing results with individual file results

- `POST /ocr/enhanced/process-with-template`: Process document with template
  - Parameters: `file`, `template_id` (required), other processing options
  - Returns: Template-mapped results

- `POST /ocr/enhanced/process-async`: Process document asynchronously (Celery)
  - Parameters: Same as `/process`
  - Returns: Task ID for status tracking

- `POST /ocr/enhanced/batch/process-async`: Process batch asynchronously
  - Parameters: Same as batch process
  - Returns: Task ID for status tracking

#### Task Status
- `GET /ocr/tasks/{task_id}`: Get Celery task status
  - Returns: Task state, progress, and results

#### Excel Export
- `POST /ocr/export/excel/from-data`: Export single document to Excel
- `POST /ocr/export/excel/batch/from-data`: Export batch to Excel (ZIP file)

#### Low Confidence Analysis
- `POST /ocr/analyze-low-confidence`: Analyze low-confidence key-value pairs
  - Parameters: `key_value_pairs`, `confidence_scores`, `ocr_text`, `source_file_base64` (optional)
  - Returns: Analysis results with suggestions

#### Text Finding
- `POST /ocr/find-text`: Find text in document with bounding boxes
  - Parameters: `file`, `search_text`
  - Returns: Bounding box coordinates for matched text

#### History Management
- `GET /history/{tenant_id}`: Get processing history for tenant
- `POST /history/save`: Save processing history entry
- `DELETE /history/{tenant_id}/{entry_id}`: Delete specific history entry
- `DELETE /history/{tenant_id}`: Clear all history for tenant

### Template Management Endpoints

- `POST /templates/upload`: Upload Excel template
- `GET /templates`: List all templates for current tenant
- `GET /templates/{template_id}`: Get specific template
- `DELETE /templates/{template_id}`: Delete template
- `POST /templates/{template_id}/map`: Map template to document
- `PUT /templates/{template_id}/mappings/{document_id}`: Update template mapping
- `POST /templates/{template_id}/export`: Export consolidated Excel with template
- `POST /templates/{template_id}/map-from-text`: Map template from text data
- `POST /templates/{template_id}/export/document/excel`: Export document to Excel with template
- `POST /templates/{template_id}/export/document/json`: Export document to JSON with template

### Blob Storage Endpoints

- `GET /blob/files/{tenant_id}`: Get files for specific tenant
- `GET /blob/files/admin`: Get all files (admin only)
- `GET /blob/files`: Get current user's files
- `GET /blob/structure/{tenant_id}`: Get folder structure for tenant
- `GET /blob/structure`: Get all folder structure (admin only)
- `DELETE /blob/files/{blob_name:path}`: Delete blob file
- `GET /blob/download/{blob_name:path}`: Download file from blob storage
- `GET /blob/stats`: Get blob storage statistics
- `GET /blob/status`: Get blob storage status

---

## Authentication & Authorization

### JWT Authentication

The system uses JWT (JSON Web Tokens) for authentication:

- **Token Format**: Bearer token in Authorization header
- **Token Payload**: Contains `sub` (username), `user_id`, `is_admin`, `tenant_id`
- **Expiration**: Tokens don't expire by default (configurable)

### User Roles

- **Admin**: Full access to all endpoints and tenant data
- **Regular User**: Access limited to their own tenant data

### Default Users

Created automatically on startup:

- **Admin User**:
  - Username: `admin`
  - Password: `admin123`
  - Email: `admin@o2.ai`
  - ⚠️ **Change password after first login!**

- **Test User**:
  - Username: `testuser`
  - Password: `test123`
  - Email: `test@o2.ai`

### Session Management

- Each user gets a stable `tenant_id` (format: `tenant_{user_id}`)
- Sessions are tracked in `UserSession` table
- Logout deactivates all sessions for the user
- Azure AD login creates users automatically

---

## Database Models

### User Model (`models/database.py`)

```python
class User:
    id: int (Primary Key)
    username: str (Unique, Indexed)
    email: str (Unique, Indexed)
    hashed_password: str
    is_active: bool (Default: True)
    is_admin: bool (Default: False)
    created_at: datetime
    last_login: datetime (Nullable)
```

### UserSession Model

```python
class UserSession:
    id: int (Primary Key)
    user_id: int (Foreign Key to User)
    session_token: str (Unique, Indexed)
    tenant_id: str (Unique, Indexed)
    created_at: datetime
    last_activity: datetime
    is_active: bool (Default: True)
```

### Database

- **Type**: SQLite (default) - can be changed to PostgreSQL
- **Location**: `data/users.db`
- **Tables**: Created automatically on startup

---

## Configuration

### Environment Variables (`utility/config.py`)

**Required:**
- `AZURE_DOCUMENT_INTELLIGENCE_KEY`: Azure Document Intelligence API key
- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`: Azure Document Intelligence endpoint

**Optional (for enhanced processing):**
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint
- `AZURE_OPENAI_DEPLOYMENT`: Azure OpenAI deployment name
- `AZURE_API_VERSION`: API version (default: "2024-02-15-preview")

**Optional (for blob storage):**
- `AZURE_STORAGE_CONNECTION_STRING`: Azure Storage connection string
- `AZURE_BLOB_CONTAINER`: Container name (default: "ocr-documents")

**Optional (for Celery):**
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_URL`: Full Redis URL (default: "redis://localhost:6379/0")

**Optional (for LayoutLMv3):**
- `HF_TOKEN`: Hugging Face token

### Configuration Settings

```python
DEFAULT_OCR_ENGINE = "azure_document_intelligence"
SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"]
MAX_FILE_SIZE_MB = 200
MAX_TOKENS = 128_000
PROMPT_RESERVE = 28_000
MAX_RETRIES = 3
BATCH_SIZE = 3
```

---

## Processing Workflow

### Single Document Processing

1. **File Upload**: Document uploaded via API endpoint
2. **Validation**: File type and size validation
3. **Source Upload**: File uploaded to blob storage `source/{tenant_id}/` folder
4. **OCR Processing**: Azure Document Intelligence extracts text with positioning
5. **Text Extraction**: Azure OpenAI GPT extracts key-value pairs
6. **Template Mapping**: (Optional) Maps extracted data to template fields
7. **Confidence Calculation**: Calculates OCR and extraction confidence scores
8. **File Reorganization**: Moves source file to confidence-based folder
9. **JSON Upload**: Processed results uploaded to `processed/{tenant_id}/` folder
10. **Response**: Returns structured JSON with extracted data

### Batch Processing

1. **Files Upload**: Multiple files uploaded
2. **Task Submission**: Each file submitted as separate Celery task
3. **Parallel Processing**: Tasks run in parallel on Celery workers
4. **Progress Tracking**: Task states updated with progress
5. **Result Aggregation**: Individual results collected and returned
6. **Summary**: Batch summary with success/failure counts

### Bulk Processing

1. **File Detection**: Periodic task checks `bulk processing/source/` folder
2. **File Download**: Downloads new files from blob storage
3. **Processing**: Runs OCR and extraction
4. **Result Upload**: Uploads results to confidence-based folder
5. **Tracking**: Marks files as processed to avoid duplicates

---

## Error Handling

### Error Types

1. **Validation Errors**: 400 Bad Request
   - Invalid file type
   - File size exceeded
   - Missing required parameters

2. **Authentication Errors**: 401 Unauthorized
   - Invalid credentials
   - Missing/invalid token
   - Inactive user

3. **Authorization Errors**: 403 Forbidden
   - Insufficient permissions
   - Access to other tenant's data

4. **Not Found Errors**: 404 Not Found
   - Template not found
   - File not found
   - User not found

5. **Server Errors**: 500 Internal Server Error
   - OCR processing failures
   - Azure service errors
   - Database errors

### Error Response Format

```json
{
  "detail": "Error message",
  "error": "Detailed error information"
}
```

### Logging

- **Log Level**: INFO (configurable)
- **Log File**: `logs/ocr_processing.log`
- **Console Output**: Enabled for development
- **Error Tracking**: Comprehensive error logging with stack traces

---

## Utility Functions

### File Processing (`utility/file_processor.py`)

- `FileProcessor.is_supported_file()`: Check if file extension is supported
- `FileProcessor.get_file_type()`: Determine file type from data/filename
- `FileProcessor.convert_pdf_to_images()`: Convert PDF to image bytes
- `FileProcessor.process_file()`: Process file with optional preprocessing
- `FileSizeValidator.validate_file_size()`: Validate file size
- `FileSizeValidator.get_file_size_mb()`: Get file size in MB

### OCR Utilities (`utility/utils.py`)

- `ocr_from_path()`: Main OCR processing function
- `calculate_ocr_confidence()`: Calculate average OCR confidence from text blocks
- `calculate_key_value_pair_confidence_scores()`: Calculate confidence for each key-value pair
- `get_available_engines()`: Get list of available OCR engines

### Configuration (`utility/config.py`)

- `Config.validate_azure_document_intelligence_config()`: Validate Azure DI config
- `Config.validate_azure_openai_config()`: Validate Azure OpenAI config
- `Config.get_missing_env_vars()`: Get missing environment variables
- `setup_logging()`: Configure logging system

---

## Best Practices

### Development

1. **Environment Setup**: Always use virtual environment
2. **Environment Variables**: Never commit `.env` files
3. **Logging**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
4. **Error Handling**: Always catch and log exceptions
5. **Type Hints**: Use type hints for better code documentation

### Production

1. **Security**: Change default admin password
2. **Database**: Use PostgreSQL instead of SQLite
3. **Redis**: Ensure Redis is running and accessible
4. **Azure Services**: Monitor Azure service quotas and limits
5. **File Size**: Enforce file size limits
6. **CORS**: Configure proper CORS origins
7. **Secrets**: Use Azure Key Vault for sensitive data

### Performance

1. **Async Processing**: Use Celery for long-running tasks
2. **Batch Processing**: Process multiple files in parallel
3. **Caching**: Cache template metadata
4. **Connection Pooling**: Use connection pooling for database
5. **File Streaming**: Stream large files instead of loading into memory

---

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Ensure Redis is running: `docker run -d -p 6379:6379 redis:latest`
   - Check `REDIS_URL` environment variable
   - Verify Redis is writable (not a read-only replica)

2. **Azure Service Errors**
   - Verify API keys and endpoints are correct
   - Check Azure service quotas and limits
   - Review Azure service logs

3. **File Upload Failures**
   - Check file size limits
   - Verify file format is supported
   - Check blob storage connection string

4. **Template Mapping Issues**
   - Verify template format is correct
   - Check field names match extracted data
   - Review template parsing logs

5. **Low Confidence Scores**
   - Check image quality
   - Review OCR confidence scores
   - Consider using image preprocessing (if enabled)

---

## API Response Examples

### Successful Processing Response

```json
{
  "status": "completed",
  "processing_id": "uuid",
  "file_info": {
    "filename": "document.pdf",
    "content_type": "application/pdf",
    "size_bytes": 123456,
    "pages_processed": 3
  },
  "key_value_pairs": {
    "Patient Name": "John Doe",
    "Date": "2024-01-15",
    "Address": "123 Main St"
  },
  "key_value_pair_confidence_scores": {
    "Patient Name": 0.95,
    "Date": 0.98,
    "Address": 0.92
  },
  "summary": "Medical document for John Doe",
  "confidence_score": 0.95,
  "ocr_confidence_score": 0.97,
  "document_classification": "Medical Document",
  "processing_time": 5.23,
  "blob_storage": {
    "processed_json": {
      "success": true,
      "blob_path": "main/Above-95%/processed/tenant_1/...",
      "blob_url": "https://..."
    },
    "source": {
      "success": true,
      "blob_path": "main/Above-95%/source/tenant_1/...",
      "blob_url": "https://..."
    }
  }
}
```

### Error Response

```json
{
  "detail": "File size 250MB exceeds maximum allowed size of 200MB",
  "error": "ValueError: File size validation failed"
}
```

---

## Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Azure Document Intelligence**: https://learn.microsoft.com/azure/ai-services/document-intelligence/
- **Azure OpenAI**: https://learn.microsoft.com/azure/ai-services/openai/
- **Celery Documentation**: https://docs.celeryproject.org/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/

---

## Version Information

- **Backend Version**: 1.0.0
- **Python Version**: 3.12+
- **FastAPI Version**: Latest
- **Last Updated**: 2024





