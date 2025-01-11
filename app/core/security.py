"""
Security utilities for token management.

Version: 1.0
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Union, Pattern
from jose import jwt
from fastapi import Depends, HTTPException, status
import re
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.auth_dependencies import redis_client, security_logger
from app.core.user_utils import get_current_user
from app.core.constants import (
    DEFAULT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)

class RequiresRole:
    """Dependency class for role-based access control."""
    
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: Dict = Depends(get_current_user)) -> Dict:
        """
        Check if the current user has one of the allowed roles.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            Dict: Current user if authorized
            
        Raises:
            HTTPException: If user's role is not in allowed roles
        """
        if current_user.get("role") not in self.allowed_roles:
            security_logger.log_security_event(
                "unauthorized_access_attempt",
                {
                    "user_id": current_user.get("id"),
                    "required_roles": self.allowed_roles,
                    "user_role": current_user.get("role")
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have the required role to perform this action"
            )
        return current_user

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Token payload data
        expires_delta: Optional custom expiration time
        
    Returns:
        str: Encoded JWT token
    """
    settings = get_settings()
    
    # Set token expiry
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Prepare token data
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    })
    
    # Create signed token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=DEFAULT_ALGORITHM
    )
    
    # Log token creation
    security_logger.log_security_event(
        "access_token_created",
        {"user_id": data.get("sub"), "expires": expire.isoformat()}
    )
    
    return encoded_jwt

def create_refresh_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT refresh token.
    
    Args:
        data: Token payload data
        expires_delta: Optional custom expiration time
        
    Returns:
        str: Encoded JWT token
    """
    settings = get_settings()
    
    # Set token expiry
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Prepare token data
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    })
    
    # Create signed token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=getattr(settings, "ALGORITHM", DEFAULT_ALGORITHM)
    )
    
    # Store refresh token in Redis
    user_id = data.get("sub")
    if user_id and settings.USE_REDIS:
        redis_client.setex(
            f"refresh_token:{encoded_jwt}",
            REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # Convert days to seconds
            user_id
        )
    
    # Log token creation
    security_logger.log_security_event(
        "refresh_token_created",
        {"user_id": user_id, "expires": expire.isoformat()}
    )
    
    return encoded_jwt

async def revoke_token(token: str, token_type: str = "access") -> bool:
    """
    Revoke a token by adding it to the blacklist.
    
    Args:
        token: Token to revoke
        token_type: Type of token ("access" or "refresh")
        
    Returns:
        bool: True if token was revoked successfully
    """
    try:
        # Decode token without verification to get expiration
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[getattr(settings, "ALGORITHM", DEFAULT_ALGORITHM)],
            options={"verify_signature": False}
        )
        
        # Calculate remaining time until expiration
        exp = datetime.fromtimestamp(payload["exp"])
        remaining = (exp - datetime.utcnow()).total_seconds()
        
        if remaining > 0:
            # Add to blacklist with remaining time
            redis_client.setex(
                f"blacklisted_token:{token}",
                int(remaining),
                "1"
            )
            
            # If refresh token, remove from valid refresh tokens
            if token_type == "refresh":
                redis_client.delete(f"refresh_token:{token}")
            
            security_logger.log_security_event(
                "token_revoked",
                {
                    "token_type": token_type,
                    "user_id": payload.get("sub"),
                    "expires": exp.isoformat()
                }
            )
            return True
            
        return False
        
    except Exception as e:
        security_logger.log_security_event(
            "token_revocation_error",
            {"error": str(e)}
        )
        return False

class PIIMasker:
    """Utility class for masking PII (Personally Identifiable Information) in logs."""
    
    # Common PII patterns
    PII_PATTERNS = {
        'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    }
    
    @staticmethod
    def mask_pii(data: Union[str, Dict[str, Any], List[Any]]) -> Union[str, Dict[str, Any], List[Any]]:
        """
        Mask PII in the provided data.
        
        Args:
            data: String, dictionary, or list containing potential PII
            
        Returns:
            Data with PII masked
        """
        if isinstance(data, str):
            return PIIMasker._mask_string(data)
        elif isinstance(data, dict):
            return {k: PIIMasker.mask_pii(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [PIIMasker.mask_pii(item) for item in data]
        return data
    
    @staticmethod
    def _mask_string(text: str) -> str:
        """Mask PII in a string."""
        for pattern_name, pattern in PIIMasker.PII_PATTERNS.items():
            text = re.sub(
                pattern,
                f'[MASKED_{pattern_name.upper()}]',
                text
            )
        return text

async def verify_token(token: str) -> Dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or blacklisted
    """
    settings = get_settings()
    
    try:
        # Check if token is blacklisted
        if await redis_client.get(f"blacklisted_token:{token}"):
            security_logger.log_security_event(
                "blacklisted_token_used",
                {"token": token[:10] + "..."}  # Log only first 10 chars for security
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[getattr(settings, "ALGORITHM", DEFAULT_ALGORITHM)]
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        security_logger.log_security_event("expired_token_used", {})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        security_logger.log_security_event("invalid_token_used", {})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

def get_token_from_header(authorization: str) -> str:
    """
    Extract token from authorization header.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        str: Extracted token
        
    Raises:
        HTTPException: If token format is invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    return authorization.replace("Bearer ", "")