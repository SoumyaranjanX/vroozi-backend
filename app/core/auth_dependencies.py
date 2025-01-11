"""
Authentication dependencies and shared utilities.

Version: 1.0
"""

from fastapi import HTTPException, status
from redis import Redis
import logging
from typing import Optional

from app.config.settings import get_settings
from app.core.exceptions import (
    CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION,
    INVALID_CREDENTIALS_EXCEPTION,
    RATE_LIMIT_EXCEPTION,
    TOKEN_BLACKLISTED_EXCEPTION
)

# Configure security logger
security_logger = logging.getLogger("security")

# Redis client for token blacklisting
settings = get_settings()

def get_redis_client() -> Optional[Redis]:
    """Get Redis client if Redis is enabled."""
    if settings.USE_REDIS:
        try:
            return Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else None,
                decode_responses=True
            )
        except Exception as e:
            logging.warning(f"Failed to initialize Redis client: {str(e)}")
            return None
    return None

# Initialize Redis client
redis_client = get_redis_client()

class SecurityLogger:
    """Security event logging utility."""
    
    def __init__(self):
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        # Add file handler if not already present
        if not self.logger.handlers:
            fh = logging.FileHandler("security.log")
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
    
    def log_security_event(self, event_type: str, details: dict = None):
        """Log security event with details."""
        self.logger.info(
            f"Security event: {event_type}",
            extra={"details": details or {}}
        )

# Initialize security logger
security_logger = SecurityLogger() 