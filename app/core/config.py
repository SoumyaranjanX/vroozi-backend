"""
Core configuration module for the Contract Processing System.
Provides a centralized, thread-safe, and type-safe configuration management system
with enhanced caching, security validation, and environment-specific settings.

Version: 1.0
"""

# External imports with version specifications
from pydantic import ValidationError  # pydantic v1.10+
from functools import lru_cache  # built-in
from typing import Dict, Optional  # built-in
import threading  # built-in

# Internal imports
from app.config.settings import Settings, get_settings as get_base_settings

# Global thread-safety locks
_settings_lock = threading.Lock()
_settings_instance: Optional[Settings] = None

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Thread-safe singleton function to return cached application settings instance with validation.
    Uses double-checked locking pattern for thread safety and performance.
    
    Returns:
        Settings: Validated global settings instance
    
    Raises:
        ValidationError: If settings validation fails
    """
    global _settings_instance
    
    if _settings_instance is None:
        with _settings_lock:
            if _settings_instance is None:
                try:
                    _settings_instance = get_base_settings()
                    # Validate security settings on initialization
                    if not _settings_instance.validate_security_settings():
                        raise ValidationError("Security validation failed")
                except Exception as e:
                    raise ValidationError(f"Failed to initialize settings: {str(e)}")
    
    return _settings_instance

def configure_app_settings(env_name: str) -> Dict:
    """
    Configures and validates initial application settings based on environment with security checks.
    
    Args:
        env_name: Environment name (development, staging, production)
    
    Returns:
        Dict: Dictionary of validated configuration settings
    
    Raises:
        ValueError: If environment name is invalid
        ValidationError: If configuration validation fails
    """
    settings = get_settings()
    
    # Validate environment
    if env_name not in ["development", "staging", "production"]:
        raise ValueError(f"Invalid environment: {env_name}")
    
    # Configure environment-specific settings
    config = {
        "environment": env_name,
        "debug": env_name == "development",
        "mongodb": settings.get_mongodb_settings(),
        "redis": settings.get_redis_settings(),
        "aws": settings.get_aws_settings(),
        "email": settings.get_email_settings(),
    }
    
    return config

class AppConfig:
    """
    Enhanced application configuration class with secure access patterns and validation.
    Provides thread-safe access to configuration settings with comprehensive security checks.
    """
    
    def __init__(self):
        """Initialize thread-safe application configuration."""
        self._access_lock = threading.Lock()
        self._settings = get_settings()
        
        # Validate initial configuration
        if not self._settings.validate_security_settings():
            raise ValidationError("Security validation failed during initialization")
    
    def get_mongodb_config(self) -> Dict:
        """
        Returns validated MongoDB configuration settings with security checks.
        
        Returns:
            Dict: Validated MongoDB configuration dictionary
        """
        with self._access_lock:
            config = self._settings.get_mongodb_settings()
            return config
    
    def get_redis_config(self) -> Dict:
        """
        Returns validated Redis configuration settings with security checks.
        
        Returns:
            Dict: Validated Redis configuration dictionary
        """
        with self._access_lock:
            config = self._settings.get_redis_settings()
            return config
    
    def get_aws_config(self) -> Dict:
        """
        Returns validated AWS configuration settings with credential management.
        
        Returns:
            Dict: Validated AWS configuration dictionary
        """
        with self._access_lock:
            config = self._settings.get_aws_settings()
            return config
    
    def get_email_config(self) -> Dict:
        """
        Returns validated email configuration settings with security checks.
        
        Returns:
            Dict: Validated email configuration dictionary
        """
        with self._access_lock:
            config = self._settings.get_email_settings()
            return config
    
    def validate_security_config(self) -> bool:
        """
        Validates security-related configurations and encryption settings.
        
        Returns:
            bool: Validation result
        """
        with self._access_lock:
            return self._settings.validate_security_settings()

# Export public interfaces
__all__ = [
    'get_settings',
    'configure_app_settings',
    'AppConfig',
]