"""
Authentication service implementation.

Version: 1.0
"""

from datetime import datetime
from typing import Optional, Dict
import logging
from fastapi import HTTPException

from app.models.user import User
from app.core.security import create_access_token, create_refresh_token
from app.core.auth_utils import verify_password, get_password_hash
from app.core.auth_dependencies import (
    INVALID_CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION,
    redis_client,
    security_logger
)
from app.config.settings import get_settings

# Configure module logger
logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling authentication operations."""

    def __init__(self, db):
        self.db = db
        self.settings = get_settings()

    async def authenticate_user(self, email: str, password: str) -> Dict:
        """
        Authenticate user and generate access tokens.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            dict: Access and refresh tokens
            
        Raises:
            HTTPException: For authentication failures
        """
        try:
            # Get user by email
            logger.info(f"Attempting to authenticate user: {email}")
            user = await User.get_by_email(email, self.db)
            
            if not user:
                logger.error(f"User not found: {email}")
                security_logger.log_security_event(
                    "failed_login_attempt",
                    {"email": email, "reason": "user_not_found"}
                )
                raise INVALID_CREDENTIALS_EXCEPTION

            logger.info(f"User found: {email}, checking password")
            # Check if user is active
            if not user.is_active:
                logger.error(f"User inactive: {email}")
                security_logger.log_security_event(
                    "failed_login_attempt",
                    {"email": email, "reason": "inactive_account"}
                )
                raise INACTIVE_USER_EXCEPTION

            # Verify password
            logger.info(f"Verifying password for user: {email}")
            if not verify_password(password, user.hashed_password):
                logger.error(f"Invalid password for user: {email}")
                security_logger.log_security_event(
                    "failed_login_attempt",
                    {"email": email, "reason": "invalid_password"}
                )
                raise INVALID_CREDENTIALS_EXCEPTION
            
            # Prepare response data
            response_data = {
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "role": user.role
                }
            }
            
            # Generate tokens
            response_data["accessToken"] = create_access_token(
                data={
                    "sub": str(user.id),
                    "email": user.email,
                    "role": user.role
                }
            )
            response_data["refreshToken"] = create_refresh_token(
                data={
                    "sub": str(user.id),
                    "email": user.email
                }
            )

            # Handle Redis token storage
            if self.settings.USE_REDIS:
                if redis_client is not None:
                    try:
                        redis_client.setex(
                            f"refresh_token:{response_data['refreshToken']}",
                            60 * 60 * 24 * 7,  # 7 days
                            str(user.id)
                        )
                        logger.info("Token stored in Redis successfully")
                    except Exception as e:
                        logger.warning(f"Redis error, continuing without token storage: {str(e)}")
                else:
                    logger.warning("Redis client is not available, skipping token storage")
            else:
                logger.info("Redis is disabled, skipping token storage")

            # Log successful login
            security_logger.log_security_event(
                "login_success",
                {"email": email}
            )

            return response_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise INVALID_CREDENTIALS_EXCEPTION

    async def create_user(self, user_data: dict) -> User:
        """
        Create a new user.
        
        Args:
            user_data: User registration data
            
        Returns:
            User: Created user object
            
        Raises:
            HTTPException: For validation or database errors
        """
        try:
            # Check if user exists
            existing_user = await User.get_by_email(user_data["email"], self.db)
            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="User with this email already exists"
                )

            # Hash password
            user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
            
            # Create user
            user = await User.create(user_data, self.db)

            security_logger.log_security_event(
                "user_created",
                {"email": user.email}
            )

            return user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error creating user"
            )

    async def logout(self, token: str) -> None:
        """
        Logout user by blacklisting their token.
        """
        try:
            # Handle Redis token blacklisting
            if self.settings.USE_REDIS:
                if redis_client is not None:
                    try:
                        redis_client.setex(
                            f"blacklisted_token:{token}",
                            60 * 15,  # 15 minutes (token TTL)
                            "true"
                        )
                        logger.info("Token blacklisted in Redis successfully")
                    except Exception as e:
                        logger.warning(f"Redis error during logout, continuing: {str(e)}")
                else:
                    logger.warning("Redis client is not available, skipping token blacklisting")
            else:
                logger.info("Redis is disabled, skipping token blacklisting")

            # Log logout event
            security_logger.log_security_event(
                "user_logout",
                {"token": token[:10] + "..."}
            )

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            raise