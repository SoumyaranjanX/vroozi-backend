"""
Contract Processing System Test Suite Configuration
Version: 1.0
Purpose: Configures pytest settings, test markers, and common test utilities for automated testing.

This module initializes the test environment and provides the foundation for:
- Unit testing of isolated components
- Integration testing of component interactions  
- API testing of endpoints
- Performance testing of slow operations
- Security testing
- Contract processing specific tests
- Purchase order generation tests
"""

# External imports
import pytest  # version: 7.3+
import logging
import os
from typing import Dict, List

# Test marker definitions with descriptions
TEST_MARKERS: List[str] = [
    'unit: marks unit tests for isolated component testing',
    'integration: marks integration tests for component interaction verification', 
    'api: marks API tests for endpoint validation',
    'slow: marks slow running tests for performance-sensitive operations',
    'security: marks security-related tests',
    'contract: marks contract processing specific tests',
    'po: marks purchase order generation tests'
]

# Environment configuration settings
TEST_ENVIRONMENTS: Dict[str, str] = {
    'development': 'local development environment settings',
    'staging': 'pre-production environment settings',
    'production': 'production environment settings'
}

def pytest_configure(config: pytest.Config) -> None:
    """
    Pytest configuration hook that sets up the test environment, registers custom markers,
    configures logging, and establishes test collection settings.

    Args:
        config (pytest.Config): Pytest configuration object

    Returns:
        None: Configuration is applied directly to pytest environment
    """
    # Register custom markers
    for marker in TEST_MARKERS:
        name, description = marker.split(':', 1)
        config.addinivalue_line('markers', f'{name.strip()}{description}')

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test.log'),
            logging.StreamHandler()
        ]
    )

    # Set test environment variables
    os.environ.setdefault('TEST_ENV', 'development')
    
    # Configure test collection settings
    config.option.verbose = 2  # Detailed test output
    config.option.durations = 10  # Show 10 slowest tests
    config.option.durations_min = 1.0  # Show tests taking longer than 1 second
    
    # Set default timeout for tests
    config.option.timeout = 300  # 5 minutes max per test
    
    # Configure parallel execution settings if xdist plugin is available
    if hasattr(config.option, 'numprocesses'):
        config.option.numprocesses = 'auto'
    
    # Configure test result reporting
    config.option.htmlpath = 'test-reports/report.html'
    config.option.junitxml = 'test-reports/junit.xml'

def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Session initialization hook that sets up test session requirements and resources.

    Args:
        session (pytest.Session): Pytest session object

    Returns:
        None: Session configuration is applied directly
    """
    # Create necessary test directories
    os.makedirs('test-reports', exist_ok=True)
    os.makedirs('test-data', exist_ok=True)
    
    # Initialize test cache
    session.config.cache.set('test_env', os.getenv('TEST_ENV', 'development'))
    
    # Set up test security context
    session.config.cache.set('test_auth_enabled', True)
    
    # Initialize mock services configuration
    mock_services = {
        'google_vision': {'enabled': True, 'port': 9001},
        'document_storage': {'enabled': True, 'port': 9002},
        'notification': {'enabled': True, 'port': 9003}
    }
    session.config.cache.set('mock_services', mock_services)
    
    # Set up test authentication
    session.config.cache.set('test_tokens', {
        'admin': 'test-admin-token',
        'user': 'test-user-token'
    })
    
    # Configure test file storage
    test_storage = {
        'temp_dir': 'test-data/temp',
        'upload_dir': 'test-data/uploads',
        'processed_dir': 'test-data/processed'
    }
    session.config.cache.set('test_storage', test_storage)
    
    # Create storage directories
    for directory in test_storage.values():
        os.makedirs(directory, exist_ok=True)