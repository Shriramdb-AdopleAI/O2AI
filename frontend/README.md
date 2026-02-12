# O2AI OCR Processing Frontend

A modern, comprehensive React frontend for the O2AI OCR Processing System, featuring advanced document processing, multi-tenant support, template management, and real-time OCR results visualization.

## Features

- ** User Authentication**: Secure login/logout with JWT tokens
- ** Advanced File Upload**: Drag & drop with batch processing support
- ** Real-time OCR Processing**: Live progress tracking and status updates
- ** Enhanced Results Display**: Interactive OCR results with text positioning
- ** Inline Text Editing**: Edit OCR text directly in the interface
- ** Template Management**: Create and manage document templates
- ** Multi-Tenant Support**: Isolated workspaces for different organizations
- ** Admin Dashboard**: User management and system monitoring
- ** Azure Blob Integration**: File storage and management
- ** Export Capabilities**: Download results in multiple formats
- ** Responsive Design**: Works seamlessly on desktop and mobile
- ** Modern UI**: Clean, intuitive interface with dark/light themes

## Architecture

```
frontend/
├── src/
│   ├── components/           # React components
│   │   ├── ui/              # Reusable UI components
│   │   │   ├── alert.jsx
│   │   │   ├── badge.jsx
│   │   │   ├── button.jsx
│   │   │   ├── card.jsx
│   │   │   ├── input.jsx
│   │   │   ├── label.jsx
│   │   │   ├── progress.jsx
│   │   │   ├── select.jsx
│   │   │   ├── table.jsx
│   │   │   └── tabs.jsx
│   │   ├── AdminDashboard.jsx      # Admin user management
│   │   ├── BlobViewer.jsx          # Azure Blob file browser
│   │   ├── EnhancedFileUpload.jsx  # Advanced file upload
│   │   ├── EnhancedOCRResults.jsx  # OCR results display
│   │   ├── Login.jsx               # Authentication
│   │   ├── TemplateManager.jsx    # Template management
│   │   └── TemplateMappedResults.jsx # Template-based results
│   ├── services/
│   │   └── authService.js    # Authentication service
│   ├── lib/
│   │   └── utils.js         # Utility functions
│   ├── App.jsx              # Main application component
│   ├── main.jsx             # Application entry point
│   └── index.css            # Global styles
├── public/                  # Static assets
├── package.json            # Dependencies and scripts
├── vite.config.js          # Vite configuration
├── tailwind.config.js       # Tailwind CSS configuration
└── README.md               # This file
```

## Tech Stack

- **React 18** - Modern React with hooks and functional components
- **Vite** - Fast build tool and development server
- **Tailwind CSS** - Utility-first CSS framework
- **Radix UI** - Accessible component primitives
- **Lucide React** - Beautiful icon library
- **React Dropzone** - Drag & drop file upload
- **Class Variance Authority** - Component variant management

## Prerequisites

- Node.js 18+ 
- npm or yarn
- Backend API running on `http://localhost:8888`

## Installation

1. **Install dependencies**:
```bash
npm install
```

2. **Start the development server**:
```bash
npm run dev
```

3. **Open your browser** and navigate to `http://localhost:5173`

### Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Usage Guide

### 1. Authentication
- **Login**: Use the default admin credentials (`admin`/`admin123`) or create a new account
- **Multi-tenant**: Each user gets their own isolated workspace
- **Admin Access**: Admin users can manage other users and system settings

### 2. Document Processing
1. **Upload Files**: Drag and drop or click to select PDF, PNG, JPG, or JPEG files
2. **Configure Settings**: 
   - Enable/disable image preprocessing
   - Choose quality enhancement options
   - Select processing templates
3. **Process**: Click "Process" to start OCR processing
4. **Monitor Progress**: Watch real-time progress updates
5. **View Results**: Explore extracted text with positioning data

### 3. Results Management
- **Edit OCR Text**: Click "Edit" to modify extracted text inline
- **Export Data**: Download results as JSON or Excel
- **Copy to Clipboard**: Quick copy functionality
- **Save Changes**: Edit and save OCR corrections

### 4. Template Management
- **Create Templates**: Define custom document structures
- **Map Fields**: Associate template fields with extracted data
- **Apply Templates**: Use templates for structured data extraction
- **Manage Templates**: Edit, delete, and organize templates

### 5. File Management
- **Browse Files**: View all processed files in Azure Blob Storage
- **Download Files**: Access original and processed documents
- **Delete Files**: Remove unwanted files from storage
- **Folder Structure**: Navigate organized file hierarchies

## API Integration

The frontend connects to the FastAPI backend and uses these key endpoints:

### Authentication
- `POST /api/v1/auth/login` - User authentication
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/users` - Get user list (admin)

### OCR Processing
- `POST /api/v1/ocr/enhanced` - Process single document
- `POST /api/v1/ocr/batch` - Process multiple documents
- `GET /api/v1/history/{tenant_id}` - Get processing history

### Template Management
- `GET /api/v1/templates` - Get all templates
- `POST /api/v1/templates` - Create new template
- `PUT /api/v1/templates/{id}` - Update template
- `DELETE /api/v1/templates/{id}` - Delete template

### File Management
- `GET /api/v1/blob/files/{tenant_id}` - Get tenant files
- `GET /api/v1/blob/structure/{tenant_id}` - Get folder structure
- `DELETE /api/v1/blob/files/{blob_name}` - Delete file
- `GET /api/v1/blob/download/{blob_name}` - Download file

## UI Components

### Core Components

#### EnhancedFileUpload
- Drag & drop file upload
- Multiple file selection
- File validation (type and size)
- Progress tracking
- Error handling

#### EnhancedOCRResults
- **Interactive Results**: Click to expand/collapse sections
- **Inline Editing**: Edit OCR text directly in the interface
- **Export Options**: Copy, download, and export functionality
- **Batch Support**: Handle multiple file results
- **Template Mapping**: Display structured data extraction

#### TemplateManager
- Template creation and editing
- Field mapping interface
- Template preview
- Import/export templates

#### AdminDashboard
- User management interface
- System statistics
- Tenant management
- Access control

### UI Design System

The application uses a consistent design system:

- **Colors**: Modern color palette with light/dark mode support
- **Typography**: Clean, readable fonts with proper hierarchy
- **Spacing**: Consistent spacing using Tailwind utilities
- **Components**: Reusable UI components with consistent styling
- **Icons**: Lucide React icons for consistent iconography
- **Responsive**: Mobile-first responsive design

## Configuration

### Environment Variables
Create a `.env` file in the frontend directory:
```env
VITE_API_BASE_URL=http://localhost:8888
VITE_APP_NAME=O2AI OCR Processing
```

### Tailwind Configuration
The `tailwind.config.js` file includes:
- Custom color palette
- Component-specific styling
- Responsive breakpoints
- Dark mode support

### Vite Configuration
The `vite.config.js` includes:
- React plugin configuration
- Development server settings
- Build optimization
- Proxy configuration for API calls

## Development

### Project Structure
```
src/
├── components/          # React components
│   ├── ui/             # Reusable UI components
│   └── [Feature].jsx   # Feature-specific components
├── services/           # API services
├── lib/               # Utility functions
├── App.jsx            # Main app component
└── main.jsx           # Entry point
```

### Adding New Features

1. **Create Components**: Add new components in the `components/` directory
2. **Use UI Components**: Leverage existing UI components from `components/ui/`
3. **Follow Patterns**: Use established patterns for state management
4. **API Integration**: Add new API calls in the `services/` directory
5. **Styling**: Use Tailwind classes for consistent styling

## Testing

```bash
# Run linting
npm run lint

# Preview production build
npm run preview

```

## Deployment

### Production Build
```bash
npm run build
```

### Static Hosting
Deploy the `dist/` folder to:
- **Vercel**: Connect GitHub repository
- **Netlify**: Drag & drop dist folder
- **AWS S3**: Upload dist contents
- **Azure Static Web Apps**: Connect repository

### Environment Configuration
Update API endpoints for production:
```env
VITE_API_BASE_URL=https://your-api-domain.com
```

## Security Considerations

- **JWT Tokens**: Secure authentication with token expiration
- **CORS**: Properly configured cross-origin requests
- **File Validation**: Client-side file type and size validation
- **Input Sanitization**: Proper handling of user inputs
- **HTTPS**: Use HTTPS in production environments
