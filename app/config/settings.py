# settings.py
# Version: 1.0
# Purpose: Core settings module for secure application configuration management using Pydantic

# External imports - versions specified for production deployments
from pydantic import BaseSettings, validator, SecretStr, AnyHttpUrl  # pydantic v1.10+
from typing import Dict, List, Optional, Any
from pathlib import Path
import os
import logging
from functools import lru_cache

# Configure logger
logger = logging.getLogger(__name__)

# Global constants
BASE_DIR = Path(__file__).parent.parent.parent
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
CONFIG_VERSION = "1.0"
PROJECT_NAME = os.getenv("PROJECT_NAME", "Contract Processing System")
API_V1_PREFIX = os.getenv("API_V1_PREFIX", "/api/v1")
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

class Settings(BaseSettings):
    """
    Enhanced settings management using Pydantic BaseSettings.
    Provides secure configuration handling with comprehensive validation.
    """
    
    # Core Application Settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "Contract Processing System"
    API_V1_PREFIX: str = "/api/v1"
    READ_ONLY_MODE: bool = False
    
    # Security Settings
    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # MongoDB Configuration
    MONGODB_URL: SecretStr
    MONGODB_DB_NAME: str = "contract_processing"
    
    # Redis Configuration
    USE_REDIS: bool = False
    REDIS_HOST: Optional[str] = "localhost"
    REDIS_PORT: Optional[int] = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: SecretStr
    AWS_SECRET_ACCESS_KEY: SecretStr
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str
    AWS_ENDPOINT_URL: Optional[str] = None  # Added AWS endpoint URL setting
    
    # Google Vision API Configuration
    GOOGLE_VISION_CREDENTIALS: SecretStr
    
    # Upload Settings
    MAX_UPLOAD_SIZE: int = 25 * 1024 * 1024  # 25MB
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:4200"]
    
    # Email Configuration
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USER: SecretStr
    SMTP_PASSWORD: SecretStr
    EMAIL_FROM_ADDRESS: str
    
    # Security Headers
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Logging
    LOG_LEVEL: str = "INFO"

    @validator("ENVIRONMENT")
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        allowed_environments = ["development", "staging", "production"]
        if v not in allowed_environments:
            raise ValueError(f"Environment must be one of {allowed_environments}")
        return v

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v: SecretStr) -> SecretStr:
        """Validate secret key strength."""
        if len(v.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @validator("MONGODB_URL")
    def validate_mongodb_url(cls, v: SecretStr) -> SecretStr:
        """Validate MongoDB URL format."""
        url = v.get_secret_value()
        if not url.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("Invalid MongoDB URL format")
        return v

    @validator("AWS_ENDPOINT_URL")
    def validate_aws_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate AWS endpoint URL format."""
        if v is not None:
            if not v.startswith(("http://", "https://")):
                raise ValueError("AWS endpoint URL must start with http:// or https://")
            # Remove trailing slash if present
            v = v.rstrip('/')
        return v

    def get_mongodb_settings(self) -> Dict[str, Any]:
        """
        Returns secure MongoDB connection settings.
        """
        return {
            "host": self.MONGODB_URL.get_secret_value(),
            "db": self.MONGODB_DB_NAME,
            "connect_timeout_ms": 5000,
            "server_selection_timeout_ms": 5000,
            "max_pool_size": 100,
            "min_pool_size": 10,
            "ssl": self.ENVIRONMENT == "production",
            "ssl_cert_reqs": "CERT_REQUIRED" if self.ENVIRONMENT == "production" else None,
        }

    def get_redis_settings(self) -> Optional[Dict[str, Any]]:
        """
        Get Redis configuration settings with secure password handling.
        Returns None if Redis is disabled.
        """
        if not self.USE_REDIS:
            return None
            
        return {
            "host": self.REDIS_HOST,
            "port": self.REDIS_PORT,
            "password": self.REDIS_PASSWORD.get_secret_value() if self.REDIS_PASSWORD else None
        }

    def get_aws_settings(self) -> Dict[str, Any]:
        """
        Returns secure AWS configuration settings.
        """
        logger.debug(f"Loading AWS settings. Endpoint URL: {self.AWS_ENDPOINT_URL}")
        settings = {
            "aws_access_key_id": self.AWS_ACCESS_KEY_ID.get_secret_value(),
            "aws_secret_access_key": self.AWS_SECRET_ACCESS_KEY.get_secret_value(),
            "region_name": self.AWS_REGION,
            "bucket_name": self.S3_BUCKET_NAME,
            "use_ssl": True,
            "verify": True,
            "endpoint_url": self.AWS_ENDPOINT_URL  # Use endpoint URL from settings
        }
        logger.debug(f"AWS settings loaded: {settings['endpoint_url']}")
        return settings

    def get_email_settings(self) -> Dict[str, Any]:
        """
        Returns secure email configuration settings.
        """
        return {
            "host": self.SMTP_HOST,
            "port": self.SMTP_PORT,
            "username": self.SMTP_USER.get_secret_value(),
            "password": self.SMTP_PASSWORD.get_secret_value(),
            "from_address": self.EMAIL_FROM_ADDRESS,
            "use_tls": True,
            "validate_certs": True,
            "timeout": 10,
        }

    def validate_security_settings(self) -> bool:
        """
        Validates security-related configurations.
        """
        try:
            # Validate secret key
            if not self.SECRET_KEY:
                return False
            
            # Validate JWT settings
            if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
                return False
            
            # Validate secure connections
            if self.ENVIRONMENT == "production":
                if not all(origin.startswith("https://") for origin in self.CORS_ORIGINS):
                    return False
                
                # Validate security headers
                required_headers = ["X-Frame-Options", "X-Content-Type-Options", "Strict-Transport-Security"]
                if not all(header in self.SECURITY_HEADERS for header in required_headers):
                    return False
            
            return True
        except Exception as e:
            logging.error(f"Security validation failed: {str(e)}")
            return False

    class Config:
        """Pydantic configuration class."""
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        validate_assignment = True
        extra = "forbid"

        # Add environment variable mappings
        fields = {
            'AWS_ENDPOINT_URL': {
                'env': 'AWS_ENDPOINT_URL'
            },
            'AWS_ACCESS_KEY_ID': {
                'env': 'AWS_ACCESS_KEY_ID'
            },
            'AWS_SECRET_ACCESS_KEY': {
                'env': 'AWS_SECRET_ACCESS_KEY'
            },
            'AWS_REGION': {
                'env': 'AWS_REGION'
            },
            'S3_BUCKET_NAME': {
                'env': 'S3_BUCKET_NAME'
            }
        }

@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Uses lru_cache to prevent multiple environment variable reads.
    """
    return Settings()

# Export settings
__all__ = [
    'Settings', 'get_settings', 'ENVIRONMENT', 'DEBUG', 'PROJECT_NAME', 
    'API_V1_PREFIX', 'MONGODB_URL', 'CONFIG_VERSION', 'get_mongodb_settings'
]

# Export settings instance
settings = get_settings()

def get_mongodb_settings() -> Dict[str, Any]:
    """
    Returns secure MongoDB connection settings.
    """
    settings = get_settings()
    return {
        "host": settings.MONGODB_URL.get_secret_value() if hasattr(settings.MONGODB_URL, 'get_secret_value') else settings.MONGODB_URL,
        "db": settings.MONGODB_DB_NAME,
        "connect_timeout_ms": 5000,
        "server_selection_timeout_ms": 5000,
        "max_pool_size": 100,
        "min_pool_size": 10,
        "ssl": settings.ENVIRONMENT == "production",
        "ssl_cert_reqs": "CERT_REQUIRED" if settings.ENVIRONMENT == "production" else None,
    }

# Initialize logging configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)