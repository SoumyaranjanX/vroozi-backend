"""
API Test Package Initialization
Version: 1.0

Configures test settings, imports common test utilities, and provides shared test fixtures
for API endpoint testing with enhanced security and validation features.
"""

# External imports with versions
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
from typing import AsyncGenerator, Dict, Any
from httpx import AsyncClient

# Internal imports
from tests.conftest import test_app, async_client

# Global test constants
API_TEST_PREFIX = "/api/v1"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"

def pytest_configure(config: Any) -> None:
    """
    Configures pytest settings specific to API tests with enhanced security and validation.
    
    Args:
        config: Pytest configuration object
    """
    # Register custom markers for API test categories
    config.addinivalue_line(
        "markers",
        "api: mark test as API integration test"
    )
    config.addinivalue_line(
        "markers",
        "api_security: mark test as API security test"
    )
    config.addinivalue_line(
        "markers",
        "api_performance: mark test as API performance test"
    )
    config.addinivalue_line(
        "markers",
        "api_validation: mark test as API data validation test"
    )

@pytest.fixture(scope="function")
async def api_test_client(async_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture providing configured async HTTP client for API testing with enhanced security.
    
    Args:
        async_client: Base async HTTP client from conftest
        
    Returns:
        AsyncClient: Configured async HTTP test client with security context
    """
    # Configure base URL with API prefix
    async_client.base_url = str(async_client.base_url) + API_TEST_PREFIX
    
    # Set default security headers
    async_client.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": "test-request",
        "X-Test-Client": "true"
    })
    
    # Initialize request logging
    from app.core.logging import get_request_logger
    logger = get_request_logger(
        trace_id="test-trace",
        context={"test_client": "api_test_client"}
    )
    
    try:
        yield async_client
    finally:
        # Cleanup and log test execution
        logger.info("API test client session completed")
        await async_client.aclose()

@pytest.fixture(scope="function")
async def authenticated_client(api_test_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture providing authenticated async HTTP client with enhanced security features.
    
    Args:
        api_test_client: Base API test client
        
    Returns:
        AsyncClient: Authenticated async HTTP test client with security context
    """
    # Perform test user login
    login_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    
    response = await api_test_client.post("/auth/login", json=login_data)
    assert response.status_code == 200
    
    # Extract and validate token
    token_data = response.json()
    assert "access_token" in token_data
    
    # Configure authentication headers
    api_test_client.headers.update({
        "Authorization": f"Bearer {token_data['access_token']}",
        "X-User-ID": token_data.get("user_id", "test-user"),
        "X-User-Role": "test-role"
    })
    
    try:
        yield api_test_client
    finally:
        # Clear authentication and security context
        api_test_client.headers.pop("Authorization", None)
        api_test_client.headers.pop("X-User-ID", None)
        api_test_client.headers.pop("X-User-Role", None)

# Export fixtures for test modules
__all__ = [
    'api_test_client',
    'authenticated_client',
    'API_TEST_PREFIX',
    'TEST_USER_EMAIL',
    'TEST_USER_PASSWORD'
]