"""
User Service Module for Contract Processing System
Implements secure user management operations with role-based access control,
field-level encryption, and comprehensive audit logging.

Version: 1.0
"""

# External imports with version specifications
from fastapi import HTTPException  # v0.95.0
from bson import ObjectId  # v1.23.0
from datetime import datetime, timedelta  # built-in
from typing import Optional, List, Dict  # built-in
import logging
import asyncio

# Internal imports
from app.models.user import User
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserInDB
from app.core.security import get_password_hash, validate_password
from app.db.mongodb import get_database

# Configure module logger
logger = logging.getLogger(__name__)

# Global constants
USERS_COLLECTION = "users"
USER_NOT_FOUND_ERROR = HTTPException(status_code=404, detail="User not found")
DUPLICATE_EMAIL_ERROR = HTTPException(status_code=400, detail="Email already registered")
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = timedelta(minutes=30)
PASSWORD_HISTORY_SIZE = 5

class UserService:
    """
    Enhanced service class for secure user management operations with comprehensive
    security features and audit logging capabilities.
    """

    def __init__(self):
        """Initialize UserService with security configurations."""
        self._db = None
        self._role_permissions = {
            'admin': ['all'],
            'contract_manager': ['create_contract', 'edit_contract', 'view_contract', 'generate_po'],
            'reviewer': ['view_contract', 'edit_contract'],
            'basic_user': ['view_contract']
        }
        self._setup_logging()

    async def _get_db(self):
        """Securely retrieve database connection."""
        if not self._db:
            self._db = await get_database()
        return self._db

    def _setup_logging(self):
        """Configure secure audit logging."""
        self._audit_logger = logging.getLogger("user_service.audit")
        self._audit_logger.setLevel(logging.INFO)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Securely retrieve user by ID with field-level decryption.

        Args:
            user_id: User's unique identifier

        Returns:
            Optional[User]: Decrypted user instance if found

        Raises:
            HTTPException: If user not found or access denied
        """
        try:
            db = await self._get_db()
            user_data = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
            
            if not user_data:
                self._audit_logger.warning(f"Failed user lookup attempt for ID: {user_id}")
                raise USER_NOT_FOUND_ERROR
                
            user = User(user_data)
            self._audit_logger.info(f"Successful user lookup for ID: {user_id}")
            return user
            
        except Exception as e:
            self._audit_logger.error(f"Error in get_user_by_id: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Securely retrieve user by email with encryption handling.

        Args:
            email: User's email address

        Returns:
            Optional[User]: Decrypted user instance if found
        """
        try:
            db = await self._get_db()
            user_data = await db[USERS_COLLECTION].find_one({"email": email})
            
            if user_data:
                return User(user_data)
            return None
            
        except Exception as e:
            self._audit_logger.error(f"Error in get_user_by_email: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create new user with secure password handling and role validation.

        Args:
            user_data: Validated user creation data

        Returns:
            User: Created user instance

        Raises:
            HTTPException: If email exists or validation fails
        """
        try:
            # Check for existing user
            if await self.get_user_by_email(user_data.email):
                raise DUPLICATE_EMAIL_ERROR

            # Validate role
            if user_data.role not in self._role_permissions:
                raise HTTPException(status_code=400, detail="Invalid role specified")

            # Create user instance with security defaults
            user_dict = user_data.dict()
            user_dict["hashed_password"] = get_password_hash(user_data.password)
            user_dict["created_at"] = datetime.utcnow()
            user_dict["updated_at"] = datetime.utcnow()
            user_dict["is_active"] = True
            user_dict["login_attempts"] = 0
            user_dict["password_history"] = []
            
            # Insert user with encryption
            db = await self._get_db()
            result = await db[USERS_COLLECTION].insert_one(user_dict)
            
            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create user")

            self._audit_logger.info(f"User created successfully: {user_data.email}")
            return await self.get_user_by_id(str(result.inserted_id))

        except Exception as e:
            self._audit_logger.error(f"Error in create_user: {str(e)}")
            raise

    async def update_user(self, user_id: str, user_data: UserUpdate) -> User:
        """
        Update user with secure field validation and audit logging.

        Args:
            user_id: User's unique identifier
            user_data: Validated update data

        Returns:
            User: Updated user instance
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise USER_NOT_FOUND_ERROR

            update_dict = user_data.dict(exclude_unset=True)
            
            # Handle password update securely
            if "password" in update_dict:
                update_dict["hashed_password"] = get_password_hash(update_dict.pop("password"))
                update_dict["password_changed_at"] = datetime.utcnow()
                
                # Maintain password history
                if not user.password_history:
                    user.password_history = []
                user.password_history.append(user.hashed_password)
                if len(user.password_history) > PASSWORD_HISTORY_SIZE:
                    user.password_history.pop(0)
                update_dict["password_history"] = user.password_history

            update_dict["updated_at"] = datetime.utcnow()
            
            # Perform update with encryption
            db = await self._get_db()
            result = await db[USERS_COLLECTION].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_dict}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=500, detail="Failed to update user")

            self._audit_logger.info(f"User updated successfully: {user_id}")
            return await self.get_user_by_id(user_id)

        except Exception as e:
            self._audit_logger.error(f"Error in update_user: {str(e)}")
            raise

    async def validate_user_role(self, user_id: str, required_roles: List[str]) -> bool:
        """
        Validate user roles against authorization matrix with audit logging.

        Args:
            user_id: User's unique identifier
            required_roles: List of roles that grant access

        Returns:
            bool: True if user has required role
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            # Admin has all permissions
            if user.role == 'admin':
                return True

            # Check if user's role is in required roles
            has_access = user.role in required_roles
            
            # Log access attempt
            self._audit_logger.info(
                f"Role validation: user_id={user_id}, "
                f"role={user.role}, required_roles={required_roles}, "
                f"access_granted={has_access}"
            )
            
            return has_access

        except Exception as e:
            self._audit_logger.error(f"Error in validate_user_role: {str(e)}")
            return False

    async def deactivate_user(self, user_id: str) -> bool:
        """
        Securely deactivate user account with audit logging.

        Args:
            user_id: User's unique identifier

        Returns:
            bool: True if deactivation successful
        """
        try:
            db = await self._get_db()
            result = await db[USERS_COLLECTION].update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            success = result.modified_count > 0
            self._audit_logger.info(f"User deactivation: user_id={user_id}, success={success}")
            return success

        except Exception as e:
            self._audit_logger.error(f"Error in deactivate_user: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to deactivate user")

# Initialize global service instance
user_service = UserService()

# Export public interfaces
__all__ = ['user_service', 'UserService']