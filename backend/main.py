"""FastAPI main application with uvicorn setup for OCR service."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from api.router import router as ocr_router
from api.auth import router as auth_router
from utility.config import Config, setup_logging
from auth.admin_setup import create_default_admin, create_test_user, create_or_update_admin_email
from core.celery_app import check_redis_connection
from services.epic_fhir_service import EpicFHIRService
from models.database import create_tables

# Setup logging
logger = setup_logging()

# Create FastAPI application
app = FastAPI(
    title="OCR Processing API",
    # description="Dual-engine OCR processing service with Azure GPT Vision and Mistral OCR",
    # version="1.0.0",
    # docs_url="/docs",
    # redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ocr_router)
app.include_router(auth_router)

# Create default admin and test user on startup
@app.on_event("startup")
async def startup_event():
    """Initialize default users and check dependencies on startup."""
    logger.info("Starting up OCR API server...")
    
    # Create database tables
    logger.info("Creating database tables...")
    if create_tables():
        logger.info("Database tables created successfully!")
    else:
        logger.warning("Could not create database tables. The database may be unavailable.")
        logger.warning("The application will continue, but database operations may fail.")
        logger.warning("Please check your database connection settings and network connectivity.")
    
    # Check Redis connection
    logger.info("Checking Redis connection...")
    if not check_redis_connection():
        logger.warning("Redis is not available. Celery tasks will fail until Redis is started.")
        logger.warning("To start Redis on Windows: docker run -d -p 6379:6379 --name redis redis:latest")
    else:
        logger.info("Redis connection verified!")
    
    # Create default users
    logger.info("Creating default admin and test user accounts...")
    try:
        create_default_admin()
        create_test_user()
        create_or_update_admin_email()
        logger.info("User initialization complete!")
    except Exception as e:
        logger.warning(f"Could not create default users: {e}")
        logger.warning("Users may need to be created manually once database is available.")
    
    logger.info("OCR API server ready!")

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "OCR Processing API",
    }

@app.post("/")
async def root_post():
    """Root endpoint POST handler - accepts POST requests to root path."""
    return {
        "message": "OCR Processing API",
        "method": "POST"
    }

@app.get("/.well-known/jwks.json")
async def get_jwks():
    """
    Serve JWKS (JSON Web Key Set) endpoint for Epic FHIR authentication.
    This endpoint is required for Epic to validate JWT signatures.
    Returns an empty JWKS if private key is not configured (for OAuth client credentials flow).
    """
    try:
        epic_service = EpicFHIRService()
        jwks = epic_service.get_jwks()
        
        if jwks is None:
            # Return empty JWKS instead of 503 error
            # This allows the endpoint to be accessible even without private key
            # Epic will only use this if Backend Systems authentication is configured
            logger.info("Serving empty JWKS (private key not configured - using OAuth client credentials flow)")
            return JSONResponse(content={"keys": []})
        
        logger.info("Serving JWKS for Epic FHIR authentication")
        return JSONResponse(content=jwks)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving JWKS: {e}")
        # Return empty JWKS on error instead of 500
        return JSONResponse(content={"keys": []})

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

if __name__ == "__main__":
    # Configuration
    host = "0.0.0.0"
    port = 8000
    
    logger.info(f"Starting OCR API server on {host}:{port}")
    
    # Run uvicorn server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  
        log_level="info"
    )
