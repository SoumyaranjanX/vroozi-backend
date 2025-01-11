"""
Core authentication module implementing OAuth 2.0 with JWT token-based authentication,
enhanced security monitoring, rate limiting, and role-based access control.

Version: 1.0
"""

from fastapi import HTTPException, Depends
from jose import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from app.core.security import create_access_token, create_refresh_token
from app.core.auth_dependencies import (
    CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION,
    INVALID_CREDENTIALS_EXCEPTION,
    RATE_LIMIT_EXCEPTION,
    TOKEN_BLACKLISTED_EXCEPTION,
    redis_client,
    security_logger,
    SecurityLogger
)
from app.core.config import get_settings

# Configure module logger
logger = logging.getLogger(__name__)

async def validate_token(token: str) -> Dict:
    """
    Validates JWT token and returns payload.
    
    Args:
        token: JWT token
        
    Returns:
        Dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Check token blacklist
        if redis_client.exists(f"blacklisted_token:{token}"):
            raise TOKEN_BLACKLISTED_EXCEPTION
        
        # Decode and validate token
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM]
        )
        
        # Extract and validate user ID
        user_id = payload.get("sub")
        if not user_id:
            raise CREDENTIALS_EXCEPTION
            
        # Log successful validation
        security_logger.log_security_event(
            "token_validated",
            {"user_id": user_id}
        )
        
        return payload
        
    except jwt.JWTError:
        security_logger.log_security_event(
            "invalid_token",
            {"token": token[:10] + "..."}
        )
        raise CREDENTIALS_EXCEPTION
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise CREDENTIALS_EXCEPTION

class PermissionDependency:
    """Enhanced dependency class for role-based access control with logging."""
    
    def __init__(self, allowed_roles: List[str]):
        """Initialize with allowed roles."""
        self.allowed_roles = allowed_roles
        self.security_logger = SecurityLogger()

    async def __call__(self, token_data: Dict = Depends(validate_token)) -> Dict:
        """
        Validates user role against allowed roles with security logging.
        
        Args:
            token_data: Validated token data
            
        Returns:
            Dict: Token data if authorized
            
        Raises:
            HTTPException: If user is not authorized
        """
        user_role = token_data.get("role")
        
        if user_role not in self.allowed_roles:
            self.security_logger.log_security_event(
                "unauthorized_access",
                {
                    "user_id": token_data.get("sub"),
                    "role": user_role,
                    "required_roles": self.allowed_roles
                }
            )
            raise HTTPException(
                status_code=403,
                detail="Not authorized to perform this action"
            )
        return token_data