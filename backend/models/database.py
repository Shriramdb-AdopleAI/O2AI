from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# PostgreSQL Database URL
# Format: postgresql://username:password@host:port/database
# Azure Cosmos DB for PostgreSQL: postgresql://username:password@host:port/database
# Build connection string from environment variables to safely handle special characters in password
POSTGRES_USER = os.getenv("POSTGRES_USER", "citus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "c-faxautomation.vahdzggsuxl2b7.postgres.cosmos.azure.com")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "citus")

# Safely construct database URL with URL-encoded password
from urllib.parse import quote_plus
DATABASE_URL = f"postgresql://{quote_plus(POSTGRES_USER)}:{quote_plus(POSTGRES_PASSWORD)}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}?sslmode=require"

# Create engine with connection timeout settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,  # Maximum number of connections to keep in the pool
    max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
        "options": "-c statement_timeout=30000"  # 30 second statement timeout
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}', is_admin={self.is_admin})>"

class UserSession(Base):
    """User session model for tracking active sessions."""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    tenant_id = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, tenant_id='{self.tenant_id}')>"

class GroundTruth(Base):
    """Ground truth data for OCR validation and training."""
    __tablename__ = "ground_truth"
    
    id = Column(Integer, primary_key=True, index=True)
    processing_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    ground_truth = Column(Text, nullable=False)
    ocr_text = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)  # Using JSONB for PostgreSQL
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<GroundTruth(processing_id='{self.processing_id}', filename='{self.filename}')>"

class NullFieldTracking(Base):
    """Track which required fields are null for each processed document."""
    __tablename__ = "null_field_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    processing_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    
    # Required fields - True if null, False if has value
    name_is_null = Column(Boolean, default=False)
    dob_is_null = Column(Boolean, default=False)
    member_id_is_null = Column(Boolean, default=False)
    address_is_null = Column(Boolean, default=False)
    gender_is_null = Column(Boolean, default=False)
    insurance_id_is_null = Column(Boolean, default=False)
    
    # Count and list of null fields
    null_field_count = Column(Integer, default=0)
    null_field_names = Column(JSONB, nullable=True)  # Array of null field names
    
    # All extracted data (for reference)
    all_extracted_fields = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<NullFieldTracking(processing_id='{self.processing_id}', filename='{self.filename}', null_count={self.null_field_count})>"

class ProcessedFile(Base):
    """Store complete processed file results including corrections."""
    __tablename__ = "processed_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA256 hash for deduplication
    processing_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    
    # Blob storage paths (for reference to source files)
    source_blob_path = Column(String(1000), nullable=True)
    processed_blob_path = Column(String(1000), nullable=True)
    
    # Complete processed data stored as JSONB
    processed_data = Column(JSONB, nullable=False)  # Full JSON with key_value_pairs, confidence_scores, etc.
    
    # OCR and processing metadata
    ocr_confidence_score = Column(String(10), nullable=True)
    processing_time = Column(String(20), nullable=True)
    
    # Correction tracking
    has_corrections = Column(Boolean, default=False)
    last_corrected_by = Column(String(100), nullable=True)
    last_corrected_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ProcessedFile(file_hash='{self.file_hash[:8]}...', filename='{self.filename}', has_corrections={self.has_corrections})>"



# Create tables
def create_tables():
    """Create all database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create database tables: {e}")
        return False

# Dependency to get database session
def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

