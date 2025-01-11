"""
Test utilities package for Contract Processing System.
Provides comprehensive test organization, utilities, and fixtures for validating
file handling, security, and data validation functionality.

Version: 1.0
"""

# External imports with version specifications
import pytest  # pytest v7.3+
from pathlib import Path

# Internal imports
from .test_validators import (
    TestFileValidation,
    TestDataValidation,
    TestSecurityValidation,
    test_encryption_key,
    test_user_data
)
from .test_file_handlers import (
    TestFileHandler,
    VALID_FILE_TYPES,
    MAX_FILE_SIZE,
    MAX_BATCH_SIZE,
    ENCRYPTION_ALGORITHM,
    SECURITY_CONTEXT
)
from .test_security import (
    TestSecurityUtils,
    test_encryption_key,
    test_user_data
)

# Global constants
TEST_UTILS_DIR = Path(__file__).parent
__version__ = '1.0.0'

# Test categories for organization
TEST_CATEGORIES = {
    'validation': {
        'description': 'Data and file validation test suites',
        'modules': ['test_validators'],
        'fixtures': ['test_encryption_key', 'test_user_data']
    },
    'file_handling': {
        'description': 'File processing and storage test suites',
        'modules': ['test_file_handlers'],
        'fixtures': ['test_encryption_key']
    },
    'security': {
        'description': 'Security and authentication test suites',
        'modules': ['test_security'],
        'fixtures': ['test_encryption_key', 'test_user_data']
    }
}

# Test configuration
pytest.register_assert_rewrite('tests.test_utils.test_validators')
pytest.register_assert_rewrite('tests.test_utils.test_file_handlers')
pytest.register_assert_rewrite('tests.test_utils.test_security')

# Export public test interfaces
__all__ = [
    # Test Classes
    'TestFileValidation',
    'TestDataValidation',
    'TestSecurityValidation',
    'TestFileHandler',
    'TestSecurityUtils',
    
    # Test Fixtures
    'test_encryption_key',
    'test_user_data',
    
    # Constants
    'VALID_FILE_TYPES',
    'MAX_FILE_SIZE',
    'MAX_BATCH_SIZE',
    'ENCRYPTION_ALGORITHM',
    'SECURITY_CONTEXT',
    'TEST_UTILS_DIR',
    '__version__',
    'TEST_CATEGORIES'
]

# Test metadata
test_metadata = {
    'test_categories': ['validation', 'file_handling', 'security'],
    'test_coverage_target': '95%',
    'test_execution_mode': 'parallel',
    'test_isolation_level': 'function'
}

def pytest_configure(config):
    """
    Configure pytest with custom markers and test organization.
    
    Args:
        config: pytest configuration object
    """
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "security: mark test as security-related"
    )
    config.addinivalue_line(
        "markers",
        "validation: mark test as validation-related"
    )
    config.addinivalue_line(
        "markers",
        "file_handling: mark test as file handling-related"
    )
    
    # Configure test isolation
    config.option.verbose = True
    config.option.strict_markers = True

def pytest_collection_modifyitems(items):
    """
    Modify test collection for proper organization and execution.
    
    Args:
        items: List of collected test items
    """
    for item in items:
        # Add markers based on test path
        if "test_validators" in item.nodeid:
            item.add_marker(pytest.mark.validation)
        elif "test_file_handlers" in item.nodeid:
            item.add_marker(pytest.mark.file_handling)
        elif "test_security" in item.nodeid:
            item.add_marker(pytest.mark.security)