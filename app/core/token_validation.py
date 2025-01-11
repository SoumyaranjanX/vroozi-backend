"""
Token validation utilities.

Version: 1.0
"""

from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt, JWTError
from typing import Optional, Dict, List
from datetime import datetime

from app.core.config import get_settings
from app.core.auth_dependencies import (
    CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION,
    redis_client,
    security_logger
)
from app.core.security import DEFAULT_ALGORITHM

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    scopes={
        "admin": "Full access to all resources",
        "user": "Standard user access",
    }
)

class InvalidTokenError(HTTPException):
    """Custom exception for invalid tokens."""
    def __init__(self, detail: str):
        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

async def validate_token(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme)
) -> Dict:
    """
    Validate JWT token and return payload.
    
    Args:
        security_scopes: Required security scopes
        token: JWT token from Authorization header
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or insufficient permissions
    """
    try:
        # Check token blacklist
        if redis_client.exists(f"blacklisted_token:{token}"):
            raise InvalidTokenError("Token has been invalidated")
        
        # Decode and validate token
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[getattr(settings, "ALGORITHM", DEFAULT_ALGORITHM)]
        )
        
        # Validate token type
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        
        # Validate token expiration
        exp = datetime.fromtimestamp(payload.get("exp", 0))
        if datetime.utcnow() > exp:
            raise InvalidTokenError("Token has expired")
        
        # Extract and validate user ID and roles
        user_id = payload.get("sub")
        user_roles = payload.get("roles", [])
        
        if not user_id:
            raise CREDENTIALS_EXCEPTION
            
        # Validate scopes/roles
        if security_scopes.scopes:
            for required_scope in security_scopes.scopes:
                if required_scope not in user_roles:
                    raise HTTPException(
                        status_code=403,
                        detail="Insufficient permissions",
                        headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'}
                    )
        
        # Log successful validation
        security_logger.log_security_event(
            "token_validated",
            {
                "user_id": user_id,
                "roles": user_roles,
                "required_scopes": security_scopes.scopes,
                "expires": exp.isoformat()
            }
        )
        
        return payload
        
    except JWTError as e:
        security_logger.log_security_event(
            "invalid_token",
            {
                "token": token[:10] + "...",
                "error": str(e)
            }
        )
        raise CREDENTIALS_EXCEPTION
    except InvalidTokenError:
        raise
    except Exception as e:
        security_logger.log_security_event(
            "token_validation_error",
            {"error": str(e)}
        )
        raise CREDENTIALS_EXCEPTION

async def validate_refresh_token(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    Validate JWT refresh token and return payload.
    
    Args:
        token: JWT refresh token
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Check if refresh token exists in Redis
        if not redis_client.exists(f"refresh_token:{token}"):
            raise InvalidTokenError("Refresh token not found or expired")
        
        # Decode and validate token
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[getattr(settings, "ALGORITHM", DEFAULT_ALGORITHM)]
        )
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")
        
        # Validate token expiration
        exp = datetime.fromtimestamp(payload.get("exp", 0))
        if datetime.utcnow() > exp:
            raise InvalidTokenError("Token has expired")
            
        # Extract and validate user ID
        user_id = payload.get("sub")
        if not user_id:
            raise CREDENTIALS_EXCEPTION
            
        # Verify user ID matches stored token
        stored_user_id = redis_client.get(f"refresh_token:{token}")
        if stored_user_id != user_id:
            raise InvalidTokenError("Invalid refresh token")
            
        # Log successful validation
        security_logger.log_security_event(
            "refresh_token_validated",
            {
                "user_id": user_id,
                "expires": exp.isoformat()
            }
        )
        
        return payload
        
    except JWTError as e:
        security_logger.log_security_event(
            "invalid_refresh_token",
            {
                "token": token[:10] + "...",
                "error": str(e)
            }
        )
        raise CREDENTIALS_EXCEPTION
    except InvalidTokenError:
        raise
    except Exception as e:
        security_logger.log_security_event(
            "refresh_token_validation_error",
            {"error": str(e)}
        )
        raise CREDENTIALS_EXCEPTION

def require_roles(required_roles: List[str]):
    """
    Dependency for role-based access control.
    
    Args:
        required_roles: List of required roles
        
    Returns:
        Callable: Dependency function
    """
    async def role_checker(
        payload: Dict = Security(validate_token, scopes=required_roles)
    ) -> Dict:
        return payload
    return role_checker 