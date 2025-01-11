"""
PyTest configuration file for Contract Processing System.
Provides comprehensive test fixtures and setup for backend testing environment
with enhanced security context, database isolation, and logging capabilities.

Version: 1.0
"""

# External imports with versions
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
import mongomock  # mongomock v4.1+
import fakeredis  # fakeredis v2.10+
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Internal imports
from app.db.mongodb import get_database
from app.db.redis_client import RedisCache
from app.core.security import SecurityContext
from app.core.config import get_settings
from app.core.logging import setup_logging

# Global test constants
TEST_DB_NAME = "test_db"
TEST_REDIS_URL = "redis://localhost:6379/1"
TEST_LOG_LEVEL = "DEBUG"
TEST_SECURITY_ENABLED = True
TEST_ISOLATION_LEVEL = "function"

def pytest_configure(config):
    """
    Enhanced PyTest configuration hook for setting up test environment
    with comprehensive logging and security context.
    """
    try:
        # Configure test logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.setLevel(TEST_LOG_LEVEL)

        # Register custom markers
        config.addinivalue_line(
            "markers",
            "integration: mark test as integration test"
        )
        config.addinivalue_line(
            "markers",
            "security: mark test as security test"
        )

        # Set test environment variables
        os.environ["ENVIRONMENT"] = "test"
        os.environ["MONGODB_DB_NAME"] = TEST_DB_NAME
        os.environ["REDIS_URL"] = TEST_REDIS_URL

        logger.info("Test environment configured successfully")

    except Exception as e:
        logging.error(f"Test configuration failed: {str(e)}")
        raise

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope=TEST_ISOLATION_LEVEL)
async def mongodb_client():
    """
    Provides isolated MongoDB test client with comprehensive cleanup.
    Uses mongomock for test isolation.
    """
    try:
        # Initialize mock MongoDB client
        client = mongomock.MongoClient()
        db = client[TEST_DB_NAME]

        # Set up test collections
        await db.create_collection("contracts")
        await db.create_collection("users")
        await db.create_collection("audit_logs")

        yield client

        # Cleanup test data
        for collection in await db.list_collection_names():
            await db[collection].delete_many({})

        client.close()

    except Exception as e:
        logging.error(f"MongoDB test client error: {str(e)}")
        raise

@pytest_asyncio.fixture(scope=TEST_ISOLATION_LEVEL)
async def redis_client():
    """
    Provides isolated Redis test client with comprehensive cleanup.
    Uses fakeredis for test isolation.
    """
    try:
        # Initialize fake Redis client
        client = fakeredis.FakeRedis(decode_responses=True)
        
        # Configure test namespace
        client.connection_pool.connection_kwargs['db'] = 1

        yield client

        # Cleanup test data
        await client.flushdb()
        client.close()

    except Exception as e:
        logging.error(f"Redis test client error: {str(e)}")
        raise

@pytest_asyncio.fixture
async def redis_cache(redis_client):
    """Provides RedisCache instance for testing."""
    cache = RedisCache()
    cache._client = redis_client
    return cache

@pytest.fixture
def security_context():
    """
    Provides test security context with authentication.
    """
    try:
        context = {
            "user_id": "test_user",
            "roles": ["admin"],
            "trace_id": "test_trace_123",
            "timestamp": datetime.utcnow().isoformat()
        }
        return context

    except Exception as e:
        logging.error(f"Security context creation failed: {str(e)}")
        raise

@pytest_asyncio.fixture
async def test_app(mongodb_client, redis_client, security_context):
    """
    Provides configured FastAPI test application with security context.
    """
    from app.main import app
    
    # Configure test dependencies
    app.state.mongodb = mongodb_client[TEST_DB_NAME]
    app.state.redis = redis_client
    app.state.security_context = security_context

    return app

@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides async HTTP client for API testing with error handling.
    """
    async with AsyncClient(
        app=test_app,
        base_url="http://test",
        headers={"Content-Type": "application/json"}
    ) as client:
        yield client

@pytest.fixture
def test_client(test_app) -> TestClient:
    """
    Provides synchronous test client for API testing.
    """
    return TestClient(test_app)

def pytest_sessionstart(session):
    """
    Enhanced session startup hook for initializing test resources
    with proper isolation.
    """
    try:
        # Initialize test logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting test session")

        # Create test directories
        os.makedirs("tests/temp", exist_ok=True)
        os.makedirs("tests/logs", exist_ok=True)

    except Exception as e:
        logging.error(f"Session start failed: {str(e)}")
        raise

def pytest_sessionfinish(session, exitstatus):
    """
    Enhanced session cleanup hook with comprehensive resource management.
    """
    try:
        logger = logging.getLogger(__name__)
        
        # Clean up test directories
        import shutil
        shutil.rmtree("tests/temp", ignore_errors=True)
        
        # Log test session summary
        logger.info(f"Test session finished with status: {exitstatus}")

    except Exception as e:
        logging.error(f"Session cleanup failed: {str(e)}")
        raise