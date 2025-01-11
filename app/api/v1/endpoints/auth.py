"""
Authentication endpoints for the Contract Processing System.
Implements secure OAuth 2.0 with JWT tokens, rate limiting, and comprehensive security logging.

Version: 1.0
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime
import logging
from typing import Dict, Optional

from app.services.auth_service import AuthService
from app.core.logging import SecurityLogger
from app.schemas.user import UserCreate, UserInDB
from app.core.security import (
    create_access_token,
    create_refresh_token,
    revoke_token,
    get_password_hash
)
from app.core.token_validation import validate_token, validate_refresh_token
from app.db.mongodb import get_database
from app.schemas.auth import LoginRequest, LogoutRequest

# Configure module logger
logger = logging.getLogger(__name__)

# Initialize router with prefix and tags
router = APIRouter(
    tags=["Authentication"]
)

# Initialize services
security_logger = SecurityLogger()

# Rate limiting configuration
rate_limiter = Limiter(key_func=get_remote_address)

@router.post("/register", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
@rate_limiter.limit("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db=Depends(get_database)
) -> Dict[str, str]:
    """
    Register a new user with secure password hashing and validation.
    
    Args:
        request: FastAPI request object
        user_data: User registration data
        db: MongoDB database instance
        
    Returns:
        Dict containing success message
        
    Raises:
        HTTPException: For registration failures
    """
    try:
        print(f"Received user data: {user_data}")
        # Check if email already exists
        existing_user = await db["users"].find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user document
        user_dict = {
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "hashed_password": get_password_hash(user_data.password),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "role": user_data.role if hasattr(user_data, "role") else "ADMIN"
        }
        
        # Insert into database
        result = await db["users"].insert_one(user_dict)
        
        # Log successful registration
        security_logger.log_security_event(
            "user_registration",
            {
                "user_id": str(result.inserted_id),
                "email": user_data.email,
                "ip_address": request.client.host
            }
        )
        
        return {"message": "User registered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.post("/login")
@rate_limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    response: Response,
    db=Depends(get_database)
) -> Dict:
    """
    Secure endpoint for user authentication with rate limiting and security logging.
    
    Args:
        request: FastAPI request object
        credentials: User login credentials
        response: FastAPI response object
        db: MongoDB database instance
        
    Returns:
        Dict containing access token, refresh token and user data
        
    Raises:
        HTTPException: For various authentication failures
    """
    try:
        # Get client IP for security tracking
        client_ip = request.client.host
        
        # Initialize auth service
        auth_service = AuthService(db)
        
        # Authenticate user
        auth_result = await auth_service.authenticate_user(
            email=credentials.email,
            password=credentials.password
        )
        
        # Set secure cookie headers
        response.set_cookie(
            key="refresh_token",
            value=auth_result["refreshToken"],
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=604800  # 7 days
        )
        
        # Set security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return {
            "accessToken": auth_result["accessToken"],
            # "tokenExpires": auth_result["tokenExpires"],
            # "token_type": "bearer",
            "user": auth_result["user"]
        }
        
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )

@router.post("/refresh")
@rate_limiter.limit("10/minute")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db=Depends(get_database)
) -> Dict:
    """
    Secure endpoint for token refresh with enhanced validation.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        db: MongoDB database instance
        
    Returns:
        Dict containing new access token
        
    Raises:
        HTTPException: For invalid or expired refresh tokens
    """
    try:
        # Get refresh token from secure cookie
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Refresh token missing"
            )
        
        # Validate refresh token
        payload = await validate_refresh_token(refresh_token)
        
        # Initialize auth service
        auth_service = AuthService(db)
        
        # Generate new tokens
        auth_result = await auth_service.authenticate_user(
            email=payload["email"],
            password=None,
            refresh=True
        )
        
        # Set new refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=auth_result["refresh_token"],
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=604800  # 7 days
        )
        
        # Set security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return {
            "access_token": auth_result["access_token"],
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during token refresh"
        )

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    logout_data: Optional[LogoutRequest] = None,
    current_user: Optional[UserInDB] = None,
) -> Dict:
    """
    Secure endpoint for user logout with token invalidation.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        logout_data: Optional logout request data containing refresh token
        current_user: Currently authenticated user (optional)
        
    Returns:
        Dict containing logout confirmation
        
    Raises:
        HTTPException: For logout failures
    """
    try:
        # Get tokens for invalidation
        access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        refresh_token = request.cookies.get("refresh_token")
        
        # Get refresh token from request body if provided
        if logout_data and logout_data.refresh_token:
            refresh_token = logout_data.refresh_token
        
        # Revoke tokens if they exist
        if access_token:
            try:
                await revoke_token(access_token, "access")
            except Exception as e:
                logger.warning(f"Error revoking access token: {str(e)}")
        
        if refresh_token:
            try:
                await revoke_token(refresh_token, "refresh")
            except Exception as e:
                logger.warning(f"Error revoking refresh token: {str(e)}")
        
        # Clear secure cookie
        response.delete_cookie(
            key="refresh_token",
            httponly=True,
            secure=True,
            samesite="strict"
        )
        
        # Set security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during logout"
        )

@router.get("/debug/check-user/{email}")
async def check_user(
    email: str,
    db=Depends(get_database)
) -> Dict:
    """Debug endpoint to check user existence and data."""
    try:
        user_dict = await db["users"].find_one({"email": email})
        if user_dict:
            # Convert ObjectId to string for JSON serialization
            user_dict["_id"] = str(user_dict["_id"])
            return {"exists": True, "user_data": user_dict}
        return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error checking user: {str(e)}"
        )

@router.post("/debug/fix-user-fields/{email}")
async def fix_user_fields(
    email: str,
    db=Depends(get_database)
) -> Dict:
    """Debug endpoint to fix user field names."""
    try:
        # Update the user document
        result = await db["users"].update_one(
            {"email": email},
            {
                "$rename": {
                    "firstName": "first_name",
                    "lastName": "last_name"
                }
            }
        )
        
        # Check if user was updated
        if result.modified_count > 0:
            # Get updated user data
            user_dict = await db["users"].find_one({"email": email})
            if user_dict:
                user_dict["_id"] = str(user_dict["_id"])
                return {"message": "User fields updated successfully", "user_data": user_dict}
        
        return {"message": "No user was updated"}
        
    except Exception as e:
        logger.error(f"Error updating user fields: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating user fields: {str(e)}"
        )

# Export router
__all__ = ["router"]