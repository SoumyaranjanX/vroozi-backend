"""
User-related utilities and dependencies.

Version: 1.0
"""

from typing import Dict, Optional
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.core.config import get_settings
from app.core.exceptions import (
    CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION,
    TOKEN_BLACKLISTED_EXCEPTION
)
from app.core.constants import DEFAULT_ALGORITHM
from app.db.mongodb import get_database

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> Dict:
    """
    Get current user from JWT token.
    
    Args:
        token: JWT token from request
        
    Returns:
        Dict: Current user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        settings = get_settings()
        # Check if token is blacklisted
        from app.core.auth_dependencies import redis_client, security_logger
        if settings.USE_REDIS:
            if redis_client.exists(f"blacklisted_token:{token}"):
                security_logger.log_security_event(
                    "blacklisted_token_used",
                    {"token": token}
                )
                raise TOKEN_BLACKLISTED_EXCEPTION
        
        # Decode token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[DEFAULT_ALGORITHM]
        )
        
        # Extract user ID
        user_id: str = payload.get("sub")
        if user_id is None:
            raise CREDENTIALS_EXCEPTION

        # Get database connection
        db = await get_database()
        
        # Get user from database
        from app.models.user import User
        try:
            user = await User.get_by_id(user_id, db)
            if user is None:
                raise CREDENTIALS_EXCEPTION
                
            if not user.is_active:
                raise INACTIVE_USER_EXCEPTION
            
            return {
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            }
        except Exception as e:
            print("Error getting user: ", str(e))
            raise CREDENTIALS_EXCEPTION
        
    except JWTError:
        from app.core.auth_dependencies import security_logger
        security_logger.log_security_event(
            "invalid_token_used",
            {"token": token[:10] + "..."} if token else {"token": None}
        )
        raise CREDENTIALS_EXCEPTION 