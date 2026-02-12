import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for the OCR application."""
    
    # OCR Engine Settings
    DEFAULT_OCR_ENGINE = "azure_document_intelligence"
    SUPPORTED_ENGINES = ["azure_document_intelligence", "azure_computer_vision"]
    SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"]
    MAX_FILE_SIZE_MB = 200
    MAX_TOKENS = 128_000     # Set For Azure Gpt-4o -- can be changed for other model
    PROMPT_RESERVE = 28_000
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    BATCH_SIZE = 3
    DELAY_BETWEEN_BATCHES = 2.0
    
    # Azure Document Intelligence (primary OCR engine)
    AZURE_DOCUMENT_INTELLIGENCE_KEY: Optional[str] = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or os.getenv("AZURE_VISION_KEY")
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: Optional[str] = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or os.getenv("AZURE_VISION_ENDPOINT")
    
    # Azure Computer Vision (legacy support)
    AZURE_VISION_KEY: Optional[str] = os.getenv("AZURE_VISION_KEY")
    AZURE_VISION_ENDPOINT: Optional[str] = os.getenv("AZURE_VISION_ENDPOINT")

    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_API_VERSION: Optional[str] = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    # Hugging Face Token for LayoutLMv3
    HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")
    
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'logs/ocr_processing.log'
    
    @classmethod
    def validate_azure_document_intelligence_config(cls) -> bool:
        """Validate Azure Document Intelligence configuration."""
        return bool(cls.AZURE_DOCUMENT_INTELLIGENCE_KEY and cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT)
    
    @classmethod
    def validate_azure_vision_config(cls) -> bool:
        """Validate Azure Computer Vision configuration (legacy)."""
        return bool(cls.AZURE_VISION_KEY and cls.AZURE_VISION_ENDPOINT)
    
    @classmethod
    def validate_azure_openai_config(cls) -> bool:
        """Validate Azure OpenAI configuration."""
        return bool(cls.AZURE_OPENAI_API_KEY and cls.AZURE_OPENAI_ENDPOINT and cls.AZURE_OPENAI_DEPLOYMENT)
    
    @classmethod
    def get_missing_env_vars(cls, engine: str) -> list:
        """Get list of missing environment variables for specified engine."""
        missing = []
        
        if engine == "azure_document_intelligence" or engine == "azure_computer_vision":
            # For backward compatibility, support both engine names
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_KEY:
                missing.append("AZURE_DOCUMENT_INTELLIGENCE_KEY (or AZURE_VISION_KEY)")
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
                missing.append("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT (or AZURE_VISION_ENDPOINT)")
        
        return missing

def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration."""
    import os
    from pathlib import Path
    
    handlers = [logging.StreamHandler()]
    
    if log_file or Config.LOG_FILE:
        # Get the log file path and ensure directory exists
        log_path = Path(log_file or Config.LOG_FILE)
        
        # If relative path, make it relative to the project root
        if not log_path.is_absolute():
            # Go up from backend/utility/ to project root, then to logs
            project_root = Path(__file__).parent.parent.parent
            log_path = project_root / log_path.name if log_path.name else project_root / "logs" / "ocr_processing.log"
        
        # Create the logs directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handlers.append(logging.FileHandler(str(log_path)))
    
    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format=Config.LOG_FORMAT,
        handlers=handlers,
        force=True 
    )
    
    return logging.getLogger(__name__)