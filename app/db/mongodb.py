"""
MongoDB database initialization and connection management.

Version: 1.0
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from typing import Optional

from app.core.config import get_settings

# Configure module logger
logger = logging.getLogger(__name__)

# Global database connection objects
_mongodb_client: Optional[AsyncIOMotorClient] = None
_mongodb_db = None

async def init_mongodb() -> bool:
    """
    Initialize MongoDB connection with retry logic and connection pooling.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    global _mongodb_client, _mongodb_db
    
    try:
        settings = get_settings()
        
        # Create client with connection pooling
        _mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL.get_secret_value(),
            maxPoolSize=10,
            minPoolSize=1
        )
        
        # Verify connection is alive
        await _mongodb_client.admin.command('ping')
        
        # Get database instance
        _mongodb_db = _mongodb_client[settings.MONGODB_DB_NAME]
        
        logger.info(f"Successfully connected to MongoDB at {settings.MONGODB_URL.get_secret_value()}")
        return True
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error initializing MongoDB: {str(e)}")
        return False

async def get_database():
    """
    Get MongoDB database instance with connection check.
    
    Returns:
        AsyncIOMotorDatabase: MongoDB database instance
    """
    global _mongodb_client, _mongodb_db
    
    if _mongodb_db is None:
        if not await init_mongodb():
            raise ConnectionFailure("Database connection not initialized")
    
    return _mongodb_db

async def close_mongodb_connection() -> None:
    """Close MongoDB connection gracefully."""
    global _mongodb_client
    
    if _mongodb_client is not None:
        _mongodb_client.close()
        _mongodb_client = None
        logger.info("MongoDB connection closed")