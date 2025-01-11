"""
Common exceptions for authentication and authorization.

Version: 1.0
"""

from fastapi import HTTPException, status
from typing import Dict, Optional, Any

class BaseAPIException(Exception):
    """Base exception class for API errors."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

# Authentication exceptions
CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

INACTIVE_USER_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Inactive user",
    headers={"WWW-Authenticate": "Bearer"},
)

INVALID_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

RATE_LIMIT_EXCEPTION = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many requests",
    headers={"WWW-Authenticate": "Bearer"},
)

TOKEN_BLACKLISTED_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token has been invalidated",
    headers={"WWW-Authenticate": "Bearer"},
)

# Business logic exceptions
class InternalServerException(BaseAPIException):
    """Exception for internal server errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )

class OCRProcessingException(BaseAPIException):
    """Raised when OCR processing fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

class ValidationException(BaseAPIException):
    """Raised when validation fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

def handle_api_exception(exc: Exception) -> Dict[str, Any]:
    """
    Global exception handler for API endpoints.
    
    Args:
        exc: The exception to handle
        
    Returns:
        Dict containing error details
    """
    if isinstance(exc, HTTPException):
        return {
            "status_code": exc.status_code,
            "detail": exc.detail,
            "headers": exc.headers
        }
    elif isinstance(exc, BaseAPIException):
        return {
            "status_code": exc.status_code,
            "detail": exc.message,
            "error_details": exc.details
        }
    else:
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "Internal server error",
            "error_details": {"message": str(exc)}
        }