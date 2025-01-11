"""
Authentication middleware for JWT verification and user injection.

Version: 1.0
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from typing import Optional
import logging
from datetime import datetime

from app.core.constants import DEFAULT_ALGORITHM
from app.core.config import get_settings
from app.core.exceptions import CREDENTIALS_EXCEPTION
from app.db.mongodb import get_database
from app.models.user import User
from app.core.logging import AuditLogger
from app.schemas.user import UserInDB

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a stream handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

security = HTTPBearer()
audit_logger = AuditLogger()

# List of paths that don't require authentication
PUBLIC_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health"
]

def verify_token(token: str) -> dict:
    """Verify JWT token and return payload."""
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[DEFAULT_ALGORITHM]
        )
        # logger.debug(f"Token payload: {payload}")
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise CREDENTIALS_EXCEPTION

async def get_current_user_from_token(token: str) -> Optional[UserInDB]:
    """Get current user from token."""
    try:
        # Verify token synchronously
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            logger.error("No user_id in token payload")
            raise CREDENTIALS_EXCEPTION

        db = await get_database()
        user = await User.get_by_id(user_id, db)
        if not user:
            logger.error(f"No user found for ID: {user_id}")
            raise CREDENTIALS_EXCEPTION

        if not user.is_active:
            logger.error(f"User {user_id} is inactive")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )

        # Convert User model to UserInDB schema
        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role or "ADMIN",
            "is_active": user.is_active,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "hashed_password": user.hashed_password,
            "created_at": user.created_at or datetime.utcnow(),
            "updated_at": user.updated_at or datetime.utcnow()
        }
        
        return UserInDB(**user_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user_from_token: {str(e)}")
        raise CREDENTIALS_EXCEPTION

async def auth_middleware(request: Request, call_next):
    """
    Middleware to handle authentication and authorization.
    """
    try:
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public endpoints
        if any(request.url.path.startswith(path) for path in PUBLIC_PATHS):
            return await call_next(request)

        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("No Authorization header found")
            raise CREDENTIALS_EXCEPTION

        token = auth_header.split(" ")[1] if len(auth_header.split(" ")) > 1 else None
        if not token:
            logger.warning("No token found in Authorization header")
            raise CREDENTIALS_EXCEPTION

        # Get user from token (this includes token verification)
        user = await get_current_user_from_token(token)
        
        # Set user in request state
        request.state.user = user
        
        # Proceed with request
        try:
            response = await call_next(request)
            return response
        except ExceptionGroup as eg:
            # Only handle S3-specific errors in TaskGroup
            for exc in eg.exceptions:
                if isinstance(exc, ValueError) and "S3" in str(exc):
                    logger.warning(f"S3 service unavailable: {str(exc)}")
                    return JSONResponse(
                        status_code=503,
                        content={"detail": "Storage service temporarily unavailable"}
                    )
            # If it's not an S3 error, let it propagate
            raise
        except Exception as service_error:
            logger.error(f"Service error: {str(service_error)}")
            raise

    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise CREDENTIALS_EXCEPTION
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in auth middleware: {str(e)}")
        if isinstance(e, ExceptionGroup):
            raise  # Let TaskGroup exceptions propagate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) 