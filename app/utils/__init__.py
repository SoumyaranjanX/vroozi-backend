"""
Contract Processing System - Utility Module
Provides centralized access to utility functions and classes for contract processing,
data validation, file handling, and date operations.

Version: 1.0.0
"""

# Version information
__version__ = '1.0.0'

# Import string utilities
from .string_utils import (
    normalize_text,
    extract_currency_value,
    clean_ocr_text
)

# Import date utilities
from .date_utils import (
    parse_date,
    format_date,
    convert_timezone
)

# Import validation utilities
from .validators import (
    FileValidator,
    validate_contract_data,
    validate_po_data
)

# Import file handling utilities
from .file_handlers import FileHandler

# Define public interface
__all__ = [
    # Version info
    '__version__',
    
    # String utilities
    'normalize_text',
    'extract_currency_value', 
    'clean_ocr_text',
    
    # Date utilities
    'parse_date',
    'format_date',
    'convert_timezone',
    
    # Validation utilities
    'FileValidator',
    'validate_contract_data',
    'validate_po_data',
    
    # File handling utilities
    'FileHandler'
]

# Module level docstrings for key components
normalize_text.__doc__ = """
Normalize text with OCR error correction and international text support.

Args:
    text (str): Input text to normalize
    lowercase (bool, optional): Convert to lowercase. Defaults to True.
    handle_ocr_errors (bool, optional): Apply OCR error correction. Defaults to True.
    lang_code (str, optional): Language code for specific rules. Defaults to 'en'.

Returns:
    str: Normalized text string

Raises:
    ValidationException: If text normalization fails
"""

FileValidator.__doc__ = """
Secure file validation with format checking and content verification.

Methods:
    validate: Validates file content and type
    
Raises:
    ValidationException: If file validation fails
"""

FileHandler.__doc__ = """
Enterprise-grade file operations handler with security and encryption.

Methods:
    process_upload: Process and validate uploaded files
    prepare_download: Prepare files for secure download
    
Raises:
    ValidationException: If file operations fail
"""

# Validation to ensure all required components are properly imported
def _validate_imports():
    """Validate that all required utility components are properly imported."""
    required_components = {
        'normalize_text': normalize_text,
        'extract_currency_value': extract_currency_value,
        'clean_ocr_text': clean_ocr_text,
        'parse_date': parse_date,
        'format_date': format_date,
        'convert_timezone': convert_timezone,
        'FileValidator': FileValidator,
        'validate_contract_data': validate_contract_data,
        'validate_po_data': validate_po_data,
        'FileHandler': FileHandler
    }
    
    missing = [name for name, comp in required_components.items() if comp is None]
    if missing:
        raise ImportError(f"Failed to import required components: {', '.join(missing)}")

# Perform import validation
_validate_imports()