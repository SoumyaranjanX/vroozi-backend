# External imports - versions specified for production stability
from pydantic import BaseModel, Field, EmailStr, constr  # v1.10.0
from datetime import datetime
from typing import Optional
from pydantic import validator

# Global constants for user validation and security
ROLE_CHOICES = ['ADMIN']

# Enhanced password regex pattern requiring minimum 8 characters, at least one letter, 
# one number and one special character
PASSWORD_REGEX = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$'

# Security threshold for login attempts before account lockout
MAX_LOGIN_ATTEMPTS = 5

class UserBase(BaseModel):
    """
    Base Pydantic model for user data validation with enhanced security measures.
    Implements core user profile fields with strict validation rules.
    """
    email: EmailStr = Field(
        ...,
        description="User's email address for authentication and communication",
        example="user@example.com"
    )
    first_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        regex="^[a-zA-Z\s-]+$",
        description="User's first name",
        example="John",
    )
    last_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        regex="^[a-zA-Z\s-]+$",
        description="User's last name",
        example="Doe",
    )
    role: str = Field(
        default="ADMIN",  # Set default role to ADMIN
        description="User's role for access control",
        example="ADMIN"
    )

    class Config:
        """Configuration for the UserBase model"""
        min_anystr_length = 1
        max_anystr_length = 100
        anystr_strip_whitespace = True
        allow_population_by_field_name = True  # Allow both alias and original field names

    @classmethod
    def validate_role(cls, v):
        """Validate that the role is one of the allowed choices"""
        if v not in ROLE_CHOICES:
            raise ValueError(f"Role must be one of: {', '.join(ROLE_CHOICES)}")
        return v

class UserCreate(UserBase):
    """
    Schema for user registration with enhanced password validation and security measures.
    Extends UserBase with additional password requirements.
    """
    password: constr(regex=PASSWORD_REGEX) = Field(
        ...,
        description="User's password meeting security requirements",
        example="SecureP@ss123"
    )

    class Config:
        """Configuration for the UserCreate model"""
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "contract_manager",
                "password": "SecureP@ss123"
            }
        }

class UserUpdate(BaseModel):
    """
    Schema for user profile updates with optional fields and validation.
    Allows partial updates while maintaining security requirements.
    """
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=50,
        regex="^[a-zA-Z\s-]+$"
    )
    last_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=50,
        regex="^[a-zA-Z\s-]+$"
    )
    role: Optional[str] = None
    password: Optional[constr(regex=PASSWORD_REGEX)] = None

    class Config:
        """Configuration for the UserUpdate model"""
        extra = "forbid"  # Prevent additional fields from being included

    @validator('role')
    def validate_role(cls, v):
        """Validate role if provided"""
        if v is not None:
            v = v.upper()  # Convert to uppercase for comparison
            if v not in ROLE_CHOICES:
                raise ValueError(f"Role must be one of: {', '.join(ROLE_CHOICES)}")
        return v

class UserInDB(UserBase):
    """
    Enhanced schema for user data storage with comprehensive security tracking.
    Includes additional fields for monitoring user activity and security status.
    """
    id: str = Field(
        ...,
        description="Unique identifier for the user"
    )
    hashed_password: str = Field(
        ...,
        description="Hashed password for the user"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of user creation"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of last update"
    )
    is_active: bool = Field(
        default=True,
        description="User account status"
    )
    login_attempts: Optional[int] = Field(
        default=0,
        ge=0,
        le=MAX_LOGIN_ATTEMPTS,
        description="Number of failed login attempts"
    )
    last_login: Optional[datetime] = Field(
        None,
        description="Timestamp of last successful login"
    )
    password_changed_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last password change"
    )
    last_failed_login: Optional[datetime] = Field(
        None,
        description="Timestamp of last failed login attempt"
    )
    last_failed_ip: Optional[str] = Field(
        None,
        description="IP address of last failed login attempt"
    )

    class Config:
        """Configuration for the UserInDB model"""
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "user123",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "contract_manager",
                "hashed_password": "hashed_password_string",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "is_active": True,
                "login_attempts": 0,
                "last_login": "2023-01-01T00:00:00",
                "password_changed_at": "2023-01-01T00:00:00"
            }
        }
        
    @validator('role')
    def validate_role(cls, v):
        """Validate that the role is one of the allowed choices"""
        if v:
            v = v.upper()  # Convert to uppercase for comparison
            if v not in ROLE_CHOICES:
                raise ValueError(f"Role must be one of: {', '.join(ROLE_CHOICES)}")
        return v