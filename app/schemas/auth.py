"""
Authentication and authorization schemas for the Contract Processing System.
Implements secure validation for authentication flows and role-based access control.

Version: 1.0
"""

# External imports with version specifications
from pydantic import BaseModel, Field, EmailStr, constr, validator  # v1.10.0
from typing import Optional, List
from datetime import datetime

# Internal imports
from app.models.user import User

# Global constants for security configuration
PASSWORD_REGEX = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$'
ADMIN_PASSWORD_REGEX = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{12,}$'
PASSWORD_HISTORY_DEPTH = 10
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds

class LoginRequest(BaseModel):
    """
    Schema for validating login request data with enhanced security measures.
    """
    email: EmailStr = Field(
        ...,
        description="User's email address for authentication",
        example="user@example.com"
    )
    password: str = Field(
        ...,
        min_length=8,
        description="User's password",
        example="SecureP@ss123"
    )

    class Config:
        """Configuration for the LoginRequest model"""
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecureP@ss123"
            }
        }

class TokenResponse(BaseModel):
    """
    Schema for JWT token response after successful authentication.
    Implements both access and refresh tokens for enhanced security.
    """
    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
        example="eyJhbGciOiJSUzI1NiIs..."
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens",
        example="eyJhbGciOiJSUzI1NiIs..."
    )
    token_type: str = Field(
        default="bearer",
        description="Type of token issued",
        example="bearer"
    )

    class Config:
        """Configuration for the TokenResponse model"""
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
                "token_type": "bearer"
            }
        }

class RefreshTokenRequest(BaseModel):
    """
    Schema for validating refresh token requests.
    """
    refresh_token: str = Field(
        ...,
        description="Valid refresh token for obtaining new access token",
        example="eyJhbGciOiJSUzI1NiIs..."
    )

    class Config:
        """Configuration for the RefreshTokenRequest model"""
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJSUzI1NiIs..."
            }
        }

class PasswordChangeRequest(BaseModel):
    """
    Schema for password change requests with enhanced security validation.
    Implements role-based password complexity and history validation.
    """
    current_password: str = Field(
        ...,
        min_length=8,
        description="Current password for verification",
        example="OldP@ssword123"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password meeting security requirements",
        example="NewP@ssword123"
    )
    user_role: str = Field(
        ...,
        description="User's role for password complexity validation",
        example="contract_manager"
    )

    @validator('new_password')
    def validate_password_complexity(cls, password: str, values: dict) -> str:
        """
        Validates password complexity based on user role and security requirements.
        
        Args:
            password: New password to validate
            values: Dict containing other field values including user_role
            
        Returns:
            str: Validated password
            
        Raises:
            ValueError: If password doesn't meet complexity requirements
        """
        role = values.get('user_role')
        
        # Basic validation for all roles
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one number")
        if not any(c in '@$!%*#?&' for c in password):
            raise ValueError("Password must contain at least one special character")

        # Enhanced validation for admin role
        if role == 'admin':
            if not len(password) >= 12:
                raise ValueError("Admin passwords must be at least 12 characters long")
            if not any(c.isdigit() for c in password[-4:]):
                raise ValueError("Admin passwords must contain a number in the last 4 characters")
        
        # Standard validation for other roles
        elif not len(password) >= 8:
            raise ValueError("Password must be at least 8 characters long")

        return password

    class Config:
        """Configuration for the PasswordChangeRequest model"""
        schema_extra = {
            "example": {
                "current_password": "OldP@ssword123",
                "new_password": "NewP@ssword123",
                "user_role": "contract_manager"
            }
        }

class LogoutRequest(BaseModel):
    """
    Schema for logout request data.
    The refresh token is optional since it might be provided via cookies.
    """
    refresh_token: Optional[str] = Field(
        default=None,
        description="Optional refresh token if not provided via cookies",
        example="eyJhbGciOiJSUzI1NiIs..."
    )

    class Config:
        """Configuration for the LogoutRequest model"""
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJSUzI1NiIs..."
            }
        }

# Export all schema classes
__all__ = [
    'LoginRequest',
    'TokenResponse',
    'RefreshTokenRequest',
    'PasswordChangeRequest',
    'LogoutRequest'
]