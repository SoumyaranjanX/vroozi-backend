"""
Comprehensive test suite for authentication API endpoints.
Tests OAuth 2.0 with JWT tokens, account security, and role-based access control.

Version: 1.0
"""

# External imports with version specifications
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
import httpx  # httpx v0.24+
from faker import Faker  # faker v18.9+
from datetime import datetime, timedelta
import jwt
import json
from typing import Dict, Any

# Internal imports
from app.api.v1.endpoints.auth import router as auth_router
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token
)
from app.models.user import User
from app.schemas.user import UserCreate, UserInDB
from app.core.config import get_settings

# Initialize Faker for test data generation
fake = Faker()

# Test constants
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "Test@123456"
TEST_USER_ROLES = ["contract_manager", "reviewer", "basic_user"]
MAX_LOGIN_ATTEMPTS = 5

@pytest.fixture
async def test_user(mongodb_client) -> Dict[str, Any]:
    """
    Fixture to create a test user with secure password hashing.
    
    Args:
        mongodb_client: MongoDB test client
        
    Returns:
        Dict containing test user data
    """
    user_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "role": "contract_manager",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Hash password securely
    user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
    
    # Insert user into test database
    await mongodb_client["users"].insert_one(user_data)
    return user_data

@pytest.mark.asyncio
@pytest.mark.auth
async def test_successful_login(async_client, test_user):
    """
    Test successful user authentication with valid credentials.
    Verifies JWT token generation and role assignment.
    """
    # Prepare login data
    login_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    
    # Send login request
    response = await async_client.post("/auth/login", json=login_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Validate response structure
    assert "access_token" in data
    assert "token_type" in data
    assert "user" in data
    assert data["token_type"] == "bearer"
    
    # Verify JWT token
    settings = get_settings()
    token_data = jwt.decode(
        data["access_token"],
        settings.SECRET_KEY.get_secret_value(),
        algorithms=["RS256"]
    )
    
    # Validate token claims
    assert token_data["sub"] == str(test_user["_id"])
    assert token_data["role"] == test_user["role"]
    assert "exp" in token_data
    assert "iat" in token_data
    
    # Verify refresh token cookie
    assert "refresh_token" in response.cookies
    assert response.cookies["refresh_token"]["httponly"]
    assert response.cookies["refresh_token"]["secure"]
    assert response.cookies["refresh_token"]["samesite"] == "strict"

@pytest.mark.asyncio
@pytest.mark.auth
@pytest.mark.security
async def test_account_lockout(async_client, test_user):
    """
    Test account lockout mechanism after multiple failed login attempts.
    Verifies progressive delay and security logging.
    """
    # Prepare invalid login data
    invalid_login = {
        "email": TEST_USER_EMAIL,
        "password": "WrongPassword@123"
    }
    
    # Attempt multiple failed logins
    for i in range(MAX_LOGIN_ATTEMPTS):
        response = await async_client.post("/auth/login", json=invalid_login)
        assert response.status_code == 401
        
        # Verify error message
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Incorrect email or password"
        
        # Add delay to simulate real-world scenario
        if i < MAX_LOGIN_ATTEMPTS - 1:
            await asyncio.sleep(0.1)
    
    # Verify account lockout
    response = await async_client.post("/auth/login", json=invalid_login)
    assert response.status_code == 429
    data = response.json()
    assert "detail" in data
    assert "Too many login attempts" in data["detail"]
    
    # Verify correct credentials are also rejected during lockout
    valid_login = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    response = await async_client.post("/auth/login", json=valid_login)
    assert response.status_code == 429

@pytest.mark.asyncio
@pytest.mark.auth
async def test_token_refresh(async_client, test_user):
    """
    Test token refresh mechanism with security validations.
    Verifies token rotation and security headers.
    """
    # First login to get refresh token
    login_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    login_response = await async_client.post("/auth/login", json=login_data)
    assert login_response.status_code == 200
    
    # Extract refresh token from cookie
    refresh_token = login_response.cookies["refresh_token"]
    
    # Test token refresh
    response = await async_client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_token}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify security headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in response.headers

@pytest.mark.asyncio
@pytest.mark.auth
async def test_secure_logout(async_client, test_user):
    """
    Test secure logout functionality with token invalidation.
    Verifies token blacklisting and cookie clearing.
    """
    # First login to get tokens
    login_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    login_response = await async_client.post("/auth/login", json=login_data)
    assert login_response.status_code == 200
    
    # Get access token and refresh token
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.cookies["refresh_token"]
    
    # Perform logout
    response = await async_client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={"refresh_token": refresh_token}
    )
    
    # Verify logout success
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully logged out"
    
    # Verify refresh token cookie is cleared
    assert "refresh_token" in response.cookies
    assert not response.cookies["refresh_token"].value
    
    # Verify tokens are invalidated by attempting to use them
    refresh_response = await async_client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 401

class TestAuthAPI:
    """Test class for authentication API endpoints with security focus."""
    
    @pytest.fixture(autouse=True)
    async def setup_method(self, mongodb_client, redis_client):
        """
        Setup method run before each test.
        Initializes test database and security contexts.
        """
        # Clear test collections
        await mongodb_client["users"].delete_many({})
        
        # Clear rate limiting data
        await redis_client.flushall()
        
        # Create test user
        self.test_user_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "role": "contract_manager"
        }
        user = await User.create_user(self.test_user_data)
        self.test_user = user
        
        yield
        
        # Cleanup after test
        await mongodb_client["users"].delete_many({})
        await redis_client.flushall()

    async def test_invalid_credentials(self, async_client):
        """Test login with invalid credentials."""
        invalid_credentials = [
            {"email": "wrong@email.com", "password": TEST_USER_PASSWORD},
            {"email": TEST_USER_EMAIL, "password": "WrongPass@123"},
            {"email": "invalid_email", "password": TEST_USER_PASSWORD},
            {"email": TEST_USER_EMAIL, "password": "short"}
        ]
        
        for creds in invalid_credentials:
            response = await async_client.post("/auth/login", json=creds)
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

    async def test_inactive_user(self, async_client, mongodb_client):
        """Test login attempt with inactive user account."""
        # Deactivate test user
        await mongodb_client["users"].update_one(
            {"email": TEST_USER_EMAIL},
            {"$set": {"is_active": False}}
        )
        
        # Attempt login
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        response = await async_client.post("/auth/login", json=login_data)
        
        # Verify response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "inactive" in data["detail"].lower()

    async def test_role_based_access(self, async_client):
        """Test role-based access control for different user roles."""
        # Test access for different roles
        for role in TEST_USER_ROLES:
            # Update user role
            self.test_user.role = role
            await self.test_user.save()
            
            # Login with updated role
            login_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
            response = await async_client.post("/auth/login", json=login_data)
            
            # Verify role in token
            assert response.status_code == 200
            data = response.json()
            settings = get_settings()
            token_data = jwt.decode(
                data["access_token"],
                settings.SECRET_KEY.get_secret_value(),
                algorithms=["RS256"]
            )
            assert token_data["role"] == role