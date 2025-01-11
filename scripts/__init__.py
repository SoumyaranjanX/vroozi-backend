"""
Backend Utility Scripts Package
Version: 1.0.0

This package provides initialization and common utilities for development and maintenance scripts
with standardized logging configuration and path management capabilities.

Exports:
    - __version__: Package version following semantic versioning
    - setup_script_logging: Function to configure standardized logging
    - get_script_dir: Function to access scripts directory path
"""

# Standard library imports - built-in
import logging
from pathlib import Path

# Internal imports
from app.config.settings import PROJECT_NAME, API_VERSION

# Package version following semantic versioning
__version__ = "1.0.0"

# Global constants
SCRIPTS_DIR = Path(__file__).parent.resolve()

# Initialize package logger
logger = logging.getLogger(__name__)

def setup_script_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configures standardized logging for utility scripts with consistent formatting.
    
    Args:
        log_level (str): Desired logging level (default: "INFO")
                        Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    Returns:
        logging.Logger: Configured logger instance with console handler and formatted output
    
    Example:
        >>> logger = setup_script_logging("DEBUG")
        >>> logger.debug("Debug message")
        2024-01-01 12:00:00,000 - script_name - DEBUG - Debug message
    """
    # Create formatter with ISO timestamp format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create console handler if not already present
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Configure package logger
    logger = logging.getLogger(__name__)
    logger.info(f"Initializing {PROJECT_NAME} utility scripts (API Version: {API_VERSION})")
    
    return logger

def get_script_dir() -> Path:
    """
    Provides the absolute path to the scripts directory for cross-platform file operations.
    
    Returns:
        Path: Resolved Path object pointing to absolute scripts directory location
    
    Example:
        >>> script_dir = get_script_dir()
        >>> config_file = script_dir / "config" / "settings.json"
    """
    return SCRIPTS_DIR

# Initialize package with default logging configuration
setup_script_logging()

# Define package exports
__all__ = [
    "__version__",
    "setup_script_logging",
    "get_script_dir"
]