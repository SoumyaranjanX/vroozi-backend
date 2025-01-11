"""
User model and authentication methods.

Version: 1.0
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
import logging

from app.core.exceptions import (
    INVALID_CREDENTIALS_EXCEPTION,
    INACTIVE_USER_EXCEPTION
)

# Configure module logger
logger = logging.getLogger(__name__)

class User(BaseModel):
    """User model with authentication methods."""
    
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    hashed_password: str
    first_name: str = Field()
    last_name: str = Field()
    role: str = "ADMIN"
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        alias_generator = None  # Disable automatic alias generation

    @classmethod
    async def get_by_email(cls, email: str, db) -> Optional["User"]:
        """Get user by email."""
        try:
            logger.info(f"Looking up user by email: {email}")
            user_dict = await db["users"].find_one({"email": email})
            if user_dict:
                logger.info(f"Found user: {user_dict}")
                # Convert ObjectId to string
                if isinstance(user_dict.get("_id"), ObjectId):
                    user_dict["_id"] = str(user_dict["_id"])
                return cls(**user_dict)
            logger.error(f"No user found with email: {email}")
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            return None

    @classmethod
    async def get_by_id(cls, user_id: str, db) -> Optional["User"]:
        """Get user by ID."""
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(user_id)
            user_dict = await db["users"].find_one({"_id": object_id})
            if user_dict:
                # Convert ObjectId to string for serialization
                if isinstance(user_dict.get("_id"), ObjectId):
                    user_dict["_id"] = str(user_dict["_id"])
                return cls(**user_dict)
            logger.error(f"No user found with ID: {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None

    @classmethod
    async def create(cls, user_data: dict, db) -> "User":
        """Create new user."""
        try:
            # Set timestamps
            user_data["created_at"] = datetime.utcnow()
            user_data["updated_at"] = datetime.utcnow()
            
            # Insert into database
            result = await db["users"].insert_one(user_data)
            user_data["_id"] = result.inserted_id
            
            return cls(**user_data)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise