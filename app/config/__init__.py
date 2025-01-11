"""
Configuration Package Initialization
Version: 1.0
Purpose: Centralizes access to core system configuration and logging setup with thread-safe initialization

This module implements a thread-safe singleton pattern for settings management and provides
comprehensive validation on startup. It serves as the central point for accessing application
configuration throughout the system.
"""

# External imports - version specified for production deployment
from threading import Lock  # threading v3.9+

# Internal imports
from app.config.settings import Settings
from app.config.logging_config import configure_logging

# Thread synchronization lock for settings initialization
_settings_lock = Lock()

# Singleton instance holder
_settings_instance: Settings | None = None

def get_settings() -> Settings:
    """
    Thread-safe singleton accessor for Settings instance.
    Ensures only one Settings instance is created and validated across all threads.
    
    Returns:
        Settings: Initialized and validated Settings instance
    
    Raises:
        RuntimeError: If settings validation fails
    """
    global _settings_instance
    
    # Fast path for already initialized settings
    if _settings_instance is not None:
        return _settings_instance
    
    # Thread-safe initialization
    with _settings_lock:
        # Double-check pattern to prevent race conditions
        if _settings_instance is None:
            # Create new settings instance
            _settings_instance = Settings()
            
            # Validate core configuration
            if not _settings_instance.validate_security_settings():
                raise RuntimeError("Security configuration validation failed")
            
            # Validate MongoDB settings by attempting to get configuration
            try:
                _settings_instance.get_mongodb_settings()
            except Exception as e:
                raise RuntimeError(f"MongoDB configuration validation failed: {str(e)}")
            
            # Validate Redis settings by attempting to get configuration
            try:
                _settings_instance.get_redis_settings()
            except Exception as e:
                raise RuntimeError(f"Redis configuration validation failed: {str(e)}")
            
            # Log successful initialization
            import logging
            logging.info(
                "Settings initialized successfully",
                extra={
                    "environment": _settings_instance.ENVIRONMENT,
                    "debug_mode": _settings_instance.DEBUG
                }
            )
    
    return _settings_instance

# Initialize settings singleton
settings = get_settings()

# Export core configuration objects and functions
__all__ = [
    'settings',  # Global settings instance
    'configure_logging',  # Logging configuration function
]