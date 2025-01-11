"""
Initialization module for backend service layer test suites.
Provides comprehensive test utilities, fixtures, and base classes for testing service layer components.

Version: 1.0
"""

# External imports with versions
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

# Internal imports
from app.core.logging import get_request_logger
from app.core.security import SecurityContext
from app.core.exceptions import BaseAPIException

# Global constants
TEST_SERVICES_DIR = Path(__file__).parent

class BaseServiceTest:
    """
    Base class providing comprehensive functionality for service layer testing
    including test isolation, data management, security context handling, and monitoring integration.
    """

    @property
    def service_name(self) -> str:
        """Service name for test identification and logging"""
        return self.__class__.__name__.replace('Test', '')

    @property
    def test_data_dir(self) -> Path:
        """Directory path for service-specific test data"""
        return TEST_SERVICES_DIR / 'test_data' / self.service_name.lower()

    @property
    def test_config(self) -> Dict[str, Any]:
        """Test configuration including security context and monitoring settings"""
        return {
            'environment': 'test',
            'trace_id': f'test_{datetime.utcnow().timestamp()}',
            'user_id': 'test_user',
            'roles': ['admin'],
            'monitoring_enabled': True
        }

    @property
    def test_logger(self) -> logging.Logger:
        """Logger instance for test execution monitoring"""
        return get_request_logger(
            trace_id=self.test_config['trace_id'],
            context=self.test_config
        )

    def __init__(self):
        """
        Initialize base service test class with test configuration and monitoring setup.
        """
        # Create test data directory if it doesn't exist
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize test logger
        self.test_logger.info(f"Initializing {self.service_name} test suite")

        # Set up test monitoring
        self._setup_test_monitoring()

    def _setup_test_monitoring(self):
        """Configure test execution monitoring and metrics collection"""
        self._test_metrics = {
            'start_time': None,
            'end_time': None,
            'error_count': 0,
            'success_count': 0
        }

    def setup_method(self, method):
        """
        Setup method called before each test to ensure proper test isolation and state.

        Args:
            method: Test method being executed
        """
        try:
            # Record test start time
            self._test_metrics['start_time'] = datetime.utcnow()

            # Set up test security context
            self._setup_security_context()

            # Initialize test data state
            self._init_test_data()

            # Configure test monitoring
            self.test_logger.info(
                f"Starting test: {method.__name__}",
                extra={'test_name': method.__name__}
            )

        except Exception as e:
            self.test_logger.error(f"Test setup failed: {str(e)}")
            raise

    def teardown_method(self, method):
        """
        Cleanup method called after each test to ensure proper resource cleanup.

        Args:
            method: Test method that was executed
        """
        try:
            # Record test end time
            self._test_metrics['end_time'] = datetime.utcnow()

            # Clean up test data
            self._cleanup_test_data()

            # Clear security context
            self._clear_security_context()

            # Log test completion metrics
            self._log_test_metrics(method.__name__)

            # Reset test state
            self._reset_test_state()

        except Exception as e:
            self.test_logger.error(f"Test teardown failed: {str(e)}")
            raise

    def _setup_security_context(self):
        """Initialize security context for test execution"""
        SecurityContext.set_trace_id(self.test_config['trace_id'])
        SecurityContext.set_current_user_id(self.test_config['user_id'])

    def _clear_security_context(self):
        """Clear security context after test execution"""
        SecurityContext.clear()

    def _init_test_data(self):
        """Initialize test data state from test_data directory"""
        try:
            # Load any test data files
            if self.test_data_dir.exists():
                for data_file in self.test_data_dir.glob('*.json'):
                    self.test_logger.debug(f"Loading test data: {data_file.name}")

        except Exception as e:
            self.test_logger.error(f"Failed to initialize test data: {str(e)}")
            raise

    def _cleanup_test_data(self):
        """Clean up test data and reset database state"""
        try:
            # Clean up any test-generated files
            for test_file in self.test_data_dir.glob('test_*'):
                test_file.unlink()

        except Exception as e:
            self.test_logger.error(f"Failed to cleanup test data: {str(e)}")
            raise

    def _reset_test_state(self):
        """Reset test state and monitoring metrics"""
        self._test_metrics = {
            'start_time': None,
            'end_time': None,
            'error_count': 0,
            'success_count': 0
        }

    def _log_test_metrics(self, test_name: str):
        """
        Log test execution metrics and performance data.

        Args:
            test_name: Name of the test method
        """
        try:
            duration = (
                self._test_metrics['end_time'] - self._test_metrics['start_time']
            ).total_seconds()

            self.test_logger.info(
                f"Test completed: {test_name}",
                extra={
                    'test_name': test_name,
                    'duration': duration,
                    'error_count': self._test_metrics['error_count'],
                    'success_count': self._test_metrics['success_count']
                }
            )

        except Exception as e:
            self.test_logger.error(f"Failed to log test metrics: {str(e)}")