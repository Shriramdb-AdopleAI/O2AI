# O2AI OCR Processing Backend

A comprehensive FastAPI-based backend service for advanced OCR (Optical Character Recognition) processing with Azure integration, multi-tenancy support, and intelligent text extraction capabilities.

## Features

- **Multi-Engine OCR Processing**: Azure Computer Vision with advanced text positioning
- **Intelligent Text Processing**: Azure GPT-powered text enhancement and key-value extraction
- **Multi-Tenant Architecture**: Isolated data processing for different users/organizations
- **Template Management**: Customizable document templates for structured data extraction
- **Azure Blob Storage Integration**: Scalable file storage and management
- **Batch Processing**: Process multiple documents simultaneously
- **Excel Export**: Export processed data to Excel format
- **User Authentication**: JWT-based authentication with role management
- **Real-time Processing**: Live progress tracking and status updates
- **Image Preprocessing**: Advanced image enhancement for better OCR accuracy

## Architecture

```
backend/
├── api/                    # API routes and endpoints
│   ├── auth.py            # Authentication endpoints
│   └── router.py          # Main OCR processing routes
├── auth/                  # Authentication utilities
│   ├── admin_setup.py     # Default user creation
│   └── auth_utils.py      # JWT and user management
├── core/                  # Core processing modules
│   ├── agent_flow.py      # AI agent workflow
│   ├── enhanced_text_processor.py  # GPT-powered text processing
│   ├── excel_exporter.py  # Excel export functionality
│   ├── image_preprocessor.py      # Image enhancement
│   └── ocr_engines.py    # OCR engine implementations
├── models/               # Database models
│   └── database.py       # SQLAlchemy models
├── services/             # External service integrations
│   ├── azure_blob_service.py  # Azure Blob Storage
│   └── template_mapper.py    # Template mapping logic
├── utility/              # Utility functions
│   ├── config.py         # Configuration management
│   ├── file_processor.py # File handling utilities
│   └── utils.py          # General utilities
├── main.py               # FastAPI application entry point
└── requirements.txt      # Python dependencies
```

## Tech Stack

- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy** - SQL toolkit and ORM
- **Azure Computer Vision** - OCR processing engine
- **Azure OpenAI** - GPT-powered text enhancement
- **Azure Blob Storage** - File storage and management
- **Pydantic** - Data validation and serialization
- **Uvicorn** - ASGI server
- **Python 3.12+** - Programming language

## Prerequisites

- Python 3.12 or higher
- Azure Computer Vision API access
- Azure OpenAI API access (optional, for enhanced processing)
- Azure Blob Storage account (optional, for file storage)

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd backend
```

2. **Create a virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:
Create a `.env` file in the backend directory:
```env
# Azure Computer Vision (Required)
AZURE_VISION_KEY=your_azure_vision_key
AZURE_VISION_ENDPOINT=your_azure_vision_endpoint

# Azure OpenAI (Optional, for enhanced processing)
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
AZURE_API_VERSION=2024-02-15-preview

# Azure Blob Storage (Optional)
AZURE_STORAGE_ACCOUNT_URL=your_storage_account_url
AZURE_BLOB_CONTAINER=ocr-documents

# Database (SQLite by default)
DATABASE_URL=sqlite:///./ocr_database.db

# JWT Secret
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. **Run the application**:
```bash
python main.py
```

The API will be available at `http://localhost:8888`

## API Documentation

Once the server is running, you can access:
- **Interactive API docs**: `http://localhost:8888/docs`
- **ReDoc documentation**: `http://localhost:8888/redoc`

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/users` - Get user list (admin only)

#### OCR Processing
- `POST /api/v1/ocr/enhanced/process` - Process single document with full workflow
- `POST /api/v1/ocr/enhanced/batch/process` - Process multiple documents
- `POST /api/v1/ocr/enhanced/process-with-template` - Process document with custom template
- `GET /api/v1/history/{tenant_id}` - Get processing history
- `POST /api/v1/history/save` - Save processing history entry
- `DELETE /api/v1/history/{tenant_id}/{entry_id}` - Delete specific history entry
- `DELETE /api/v1/history/{tenant_id}` - Clear all history for tenant

#### Excel Export
- `POST /api/v1/ocr/export/excel/from-data` - Export single document to Excel
- `POST /api/v1/ocr/export/excel/batch/from-data` - Export multiple documents to Excel

#### Template Management
- `POST /api/v1/templates/upload` - Upload new template
- `GET /api/v1/templates` - Get all templates
- `GET /api/v1/templates/{template_id}` - Get specific template
- `DELETE /api/v1/templates/{template_id}` - Delete template
- `POST /api/v1/templates/{template_id}/map` - Map template to document
- `PUT /api/v1/templates/{template_id}/mappings/{document_id}` - Update template mapping
- `POST /api/v1/templates/{template_id}/export` - Export with template
- `POST /api/v1/templates/{template_id}/map-from-text` - Map template from text
- `POST /api/v1/templates/{template_id}/export/document/excel` - Export document to Excel with template
- `POST /api/v1/templates/{template_id}/export/document/json` - Export document to JSON with template

#### File Management (Azure Blob Storage)
- `GET /api/v1/blob/files/{tenant_id}` - Get files for specific tenant
- `GET /api/v1/blob/files/admin` - Get all files (admin only)
- `GET /api/v1/blob/files` - Get current user's files
- `GET /api/v1/blob/structure/{tenant_id}` - Get folder structure for tenant
- `GET /api/v1/blob/structure` - Get all folder structure (admin only)
- `DELETE /api/v1/blob/files/{blob_name:path}` - Delete blob file
- `GET /api/v1/blob/download/{blob_name:path}` - Download file from blob storage
- `GET /api/v1/blob/stats` - Get blob storage statistics
- `GET /api/v1/blob/status` - Get blob storage status

#### System
- `GET /api/v1/health` - Health check endpoint

## Processing Workflow

1. **File Upload**: Documents are uploaded via `/api/v1/ocr/enhanced/process` endpoint
2. **Blob Storage**: Files are stored in `source/{tenant_id}/{processing_id}/` folder
3. **Preprocessing**: Images are enhanced for better OCR accuracy
4. **OCR Processing**: Azure Computer Vision extracts text with positioning
5. **Text Enhancement**: Azure GPT processes and structures the text
6. **Template Mapping**: Custom templates extract structured data (optional)
7. **JSON Storage**: Processed results stored in `processed/{tenant_id}/{processing_id}/` folder
8. **Response**: Structured JSON response with extracted data and blob storage info

### Folder Structure in Azure Blob Storage

```
ocr-documents/
├── source/
│   └── {tenant_id}/
│       └── {processing_id}/
│           └── {filename}_{timestamp}
├── processed/
│   └── {tenant_id}/
│       └── {processing_id}/
│           └── {filename}_processed_{timestamp}.json
└── templates/
    └── {tenant_id}/
        └── {template_id}/
            └── template.json
```

## Multi-Tenancy

The system supports multiple tenants with:
- **Isolated Data**: Each tenant has separate processing history
- **User Management**: Admin users can manage multiple tenants
- **File Organization**: Blob storage organized by tenant ID
- **Template Sharing**: Templates can be shared across tenants

## Default Users

The system creates default users on startup:

**Admin User**:
- Username: `admin`
- Password: `admin123`
- Email: `admin@o2.ai`
- **Change the default password after first login!**

**Test User**:
- Username: `testuser`
- Password: `test123`
- Email: `test@o2.ai`

## Configuration

### OCR Engine Settings
```python
DEFAULT_OCR_ENGINE = "azure_computer_vision"
SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"]
MAX_FILE_SIZE_MB = 200
```

### Processing Settings
```python
MAX_TOKENS = 128_000
PROMPT_RESERVE = 28_000
MAX_RETRIES = 3
BATCH_SIZE = 3
```

### Logging
- Logs are written to `logs/ocr_processing.log`
- Console output for development
- Configurable log levels

## Deployment

### Docker Deployment
```bash
# Build Docker image
docker build -t ocr-backend .

# Run container
docker run -p 8888:8888 --env-file .env ocr-backend
```

### Production Considerations
- Use PostgreSQL instead of SQLite
- Configure proper CORS origins
- Set up Azure Key Vault for secrets
- Use Azure Container Instances or Kubernetes
- Configure proper logging and monitoring

## Testing

```bash
# Run tests (if available)
python -m pytest tests/

# Test main OCR processing endpoint
curl -X POST "http://localhost:8888/api/v1/ocr/enhanced/process" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_document.pdf"

# Test batch processing
curl -X POST "http://localhost:8888/api/v1/ocr/enhanced/batch/process" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@document1.pdf" \
  -F "files=@document2.png"

# Test template processing
curl -X POST "http://localhost:8888/api/v1/ocr/enhanced/process-with-template" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "template_id=your_template_id"

# Get user files
curl -X GET "http://localhost:8888/api/v1/blob/files" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Download file
curl -X GET "http://localhost:8888/api/v1/blob/download/source/tenant_1/processing_id/filename.pdf" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output downloaded_file.pdf
```

## Monitoring

The application provides:
- **Health Check**: `GET /api/v1/health`
- **Processing Metrics**: Response times and success rates
- **Error Logging**: Comprehensive error tracking
- **Azure Service Status**: Integration health monitoring

### Support

For issues and questions:
- Check the logs in `logs/ocr_processing.log`
- Review API documentation at `/docs`
- Verify environment configuration
- Test with smaller files first
