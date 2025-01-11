"""
Migration script to create users collection with indexes and validation.

Version: 1.0
"""

from typing import Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, TEXT
from pymongo.errors import CollectionInvalid
import logging

logger = logging.getLogger(__name__)

async def upgrade(db: AsyncIOMotorDatabase) -> bool:
    """
    Upgrade database: Create users collection with indexes and validation.
    
    Args:
        db: AsyncIOMotorDatabase instance
        
    Returns:
        bool: True if migration successful, False otherwise
    """
    try:
        # Try to create collection with validation
        try:
            await db.create_collection(
                "users",
                validator={
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": ["email", "hashed_password", "first_name", "last_name", "role", "is_active", "created_at", "updated_at"],
                        "properties": {
                            "email": {
                                "bsonType": "string",
                                "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                            },
                            "hashed_password": {"bsonType": "string"},
                            "first_name": {"bsonType": "string"},
                            "last_name": {"bsonType": "string"},
                            "role": {
                                "bsonType": "string",
                                "enum": ["admin", "contract_manager", "reviewer", "basic_user"]
                            },
                            "is_active": {"bsonType": "bool"},
                            "created_at": {"bsonType": "date"},
                            "updated_at": {"bsonType": "date"}
                        }
                    }
                }
            )
            logger.info("Created users collection")
        except CollectionInvalid:
            logger.info("Users collection already exists")
        
        # Drop existing indexes (if any)
        await db.users.drop_indexes()
        
        # Create indexes
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("first_name", ASCENDING), ("last_name", ASCENDING)]),
            IndexModel([("created_at", ASCENDING)]),
            IndexModel([("updated_at", ASCENDING)])
        ]
        
        await db.users.create_indexes(indexes)
        
        logger.info("Successfully created/updated users collection with indexes")
        return True
        
    except Exception as e:
        logger.error(f"Error in users collection migration: {str(e)}")
        return False

async def downgrade(db: AsyncIOMotorDatabase) -> bool:
    """
    Downgrade database: Remove users collection.
    
    Args:
        db: AsyncIOMotorDatabase instance
        
    Returns:
        bool: True if downgrade successful, False otherwise
    """
    try:
        await db.users.drop()
        logger.info("Successfully dropped users collection")
        return True
        
    except Exception as e:
        logger.error(f"Error in users collection downgrade: {str(e)}")
        return False 