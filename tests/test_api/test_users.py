# External imports with version specifications
import pytest  # v7.3+
import pytest_asyncio  # v0.21+
from fastapi import HTTPException  # v0.95.0
import bcrypt  # v4.0.1
from datetime import datetime, timedelta
import json
from typing import Dict, Any

# Internal imports
from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserInDB, 
    ROLE_CHOICES, PASSWORD_REGEX, MAX_LOGIN_ATTEMPTS
)
from app.core.security import (
    get_password_hash, verify_password, 
    create_access_token, encrypt_data
)

# Test data constants
TEST_USER_DATA = {
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "password": "Test123!@#",
    "role": "basic_user",
    "mfa_enabled": False
}

TEST_ADMIN_DATA = {
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "password": "Admin123!@#",
    "role": "admin",
    "mfa_enabled": True
}

# Test fixtures
@pytest.fixture
async def create_test_user(async_client):
    """
    Fixture to create a test user with security configurations.
    """
    # Create user with encrypted sensitive data
    user_data = TEST_USER_DATA.copy()
    user_data["password"] = get_password_hash(user_data["password"])
    user_data["email"] = encrypt_data(user_data["email"])
    
    response = await async_client.post(
        "/api/v1/users/",
        json=user_data
    )
    assert response.status_code == 201
    created_user = response.json()
    
    yield created_user
    
    # Cleanup: Securely delete test user
    await async_client.delete(f"/api/v1/users/{created_user['id']}")

@pytest.fixture
async def create_admin_user(async_client):
    """
    Fixture to create an admin user with enhanced security.
    """
    # Create admin with MFA enabled
    admin_data = TEST_ADMIN_DATA.copy()
    admin_data["password"] = get_password_hash(admin_data["password"])
    admin_data["email"] = encrypt_data(admin_data["email"])
    
    response = await async_client.post(
        "/api/v1/users/",
        json=admin_data
    )
    assert response.status_code == 201
    created_admin = response.json()
    
    yield created_admin
    
    # Cleanup: Securely delete admin user
    await async_client.delete(f"/api/v1/users/{created_admin['id']}")

# Test cases
@pytest.mark.asyncio
@pytest.mark.users
async def test_create_user_success(async_client, test_app):
    """Test successful user creation with valid data and security requirements."""
    # Prepare test data
    user_data = TEST_USER_DATA.copy()
    
    # Test user creation
    response = await async_client.post(
        "/api/v1/users/",
        json=user_data
    )
    
    # Verify response
    assert response.status_code == 201
    created_user = response.json()
    
    # Validate security attributes
    assert "password" not in created_user
    assert verify_password(user_data["password"], created_user["hashed_password"])
    assert created_user["login_attempts"] == 0
    assert created_user["is_active"] is True
    
    # Verify audit log creation
    audit_response = await async_client.get(f"/api/v1/audit-logs/user/{created_user['id']}")
    assert audit_response.status_code == 200
    audit_log = audit_response.json()
    assert audit_log["action"] == "user_created"

@pytest.mark.asyncio
@pytest.mark.users
async def test_create_user_invalid_data(async_client, test_app):
    """Test user creation with invalid data including security violations."""
    # Test weak password
    weak_password_data = TEST_USER_DATA.copy()
    weak_password_data["password"] = "weak"
    response = await async_client.post(
        "/api/v1/users/",
        json=weak_password_data
    )
    assert response.status_code == 422
    
    # Test invalid email format
    invalid_email_data = TEST_USER_DATA.copy()
    invalid_email_data["email"] = "invalid_email"
    response = await async_client.post(
        "/api/v1/users/",
        json=invalid_email_data
    )
    assert response.status_code == 422
    
    # Test invalid role
    invalid_role_data = TEST_USER_DATA.copy()
    invalid_role_data["role"] = "invalid_role"
    response = await async_client.post(
        "/api/v1/users/",
        json=invalid_role_data
    )
    assert response.status_code == 422

@pytest.mark.asyncio
@pytest.mark.users
async def test_user_login_security(async_client, create_test_user):
    """Test login security features including account lockout."""
    login_data = {
        "email": TEST_USER_DATA["email"],
        "password": "wrong_password"
    }
    
    # Test account lockout after max failed attempts
    for i in range(MAX_LOGIN_ATTEMPTS):
        response = await async_client.post(
            "/api/v1/auth/login",
            json=login_data
        )
        assert response.status_code == 401
    
    # Verify account is locked
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER_DATA["email"], "password": TEST_USER_DATA["password"]}
    )
    assert response.status_code == 403
    assert "Account locked" in response.json()["detail"]

@pytest.mark.asyncio
@pytest.mark.users
async def test_user_role_based_access(async_client, create_test_user, create_admin_user):
    """Test role-based access control implementation."""
    # Test basic user access restrictions
    basic_user_token = create_access_token({"sub": create_test_user["id"], "role": "basic_user"})
    response = await async_client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {basic_user_token}"}
    )
    assert response.status_code == 403
    
    # Test admin access permissions
    admin_token = create_access_token({"sub": create_admin_user["id"], "role": "admin"})
    response = await async_client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
@pytest.mark.users
async def test_user_data_encryption(async_client, create_test_user):
    """Test encryption of sensitive user data."""
    user_id = create_test_user["id"]
    
    # Verify email is encrypted in database
    response = await async_client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"].startswith("v1:")  # Encryption version prefix
    
    # Test secure data update
    update_data = {"email": "updated@example.com"}
    response = await async_client.patch(
        f"/api/v1/users/{user_id}",
        json=update_data
    )
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["email"].startswith("v1:")

@pytest.mark.asyncio
@pytest.mark.users
async def test_user_deletion_security(async_client, create_admin_user, create_test_user):
    """Test secure user deletion process."""
    admin_token = create_access_token({"sub": create_admin_user["id"], "role": "admin"})
    
    # Test deletion with audit trail
    response = await async_client.delete(
        f"/api/v1/users/{create_test_user['id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    
    # Verify audit log creation
    audit_response = await async_client.get(
        f"/api/v1/audit-logs/user/{create_test_user['id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert audit_response.status_code == 200
    audit_log = audit_response.json()
    assert audit_log["action"] == "user_deleted"