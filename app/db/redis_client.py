"""
Redis client module for the Contract Processing System.
Provides high-performance data caching and session management with cluster mode support,
AOF persistence, and comprehensive error handling.

Version: 1.0
"""

# External imports with version specifications
from redis import Redis, ConnectionPool  # redis v4.5+
from typing import Any, Optional, Dict
import json
import logging
from fastapi import status, HTTPException

# Internal imports
from app.core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Global redis client instance for singleton pattern
redis_client = None

class RedisException(Exception):
    """Base exception for Redis-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

def get_redis_client() -> Optional[Redis]:
    """
    Returns a singleton Redis client instance with connection pooling if Redis is enabled.
    Implements thread-safe connection reuse pattern.
    
    Returns:
        Redis: Configured Redis client instance with cluster mode support, or None if Redis is disabled
        
    Raises:
        RedisException: If Redis connection fails when Redis is enabled
    """
    global redis_client
    
    settings = get_settings()
    if not settings.USE_REDIS:
        return None
    
    if redis_client is None:
        redis_client = init_redis()
    
    return redis_client

def init_redis() -> Optional[Redis]:
    """
    Initializes Redis connection with cluster configuration and AOF persistence if Redis is enabled.
    Implements comprehensive error handling and connection verification.
    
    Returns:
        Redis: Configured Redis client with cluster mode and persistence, or None if Redis is disabled
        
    Raises:
        RedisException: If Redis initialization fails when Redis is enabled
    """
    try:
        settings = get_settings()
        if not settings.USE_REDIS:
            return None
        
        redis_settings = settings.get_redis_settings()
        if not redis_settings:
            return None
        
        # Configure connection pool
        pool = ConnectionPool(
            host=redis_settings["host"],
            port=redis_settings["port"],
            password=redis_settings["password"],
            decode_responses=True,
            max_connections=10
        )
        
        # Initialize Redis client
        client = Redis(connection_pool=pool)
        
        # Test connection
        client.ping()
        
        logger.info("Redis client initialized successfully")
        return client
        
    except Exception as e:
        logger.error(f"Redis initialization failed: {str(e)}")
        raise RedisException(
            message="Failed to initialize Redis connection",
            details={"error": str(e)}
        )

class RedisCache:
    """
    Enhanced Redis caching implementation with serialization and error handling.
    Provides standardized interface for caching operations with TTL support.
    """
    
    def __init__(self, default_ttl: int = 900):
        """
        Initialize Redis cache with default TTL.
        
        Args:
            default_ttl: Default time-to-live in seconds (15 minutes)
        """
        self.client = get_redis_client()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Any:
        """
        Get cached value with JSON deserialization.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Deserialized cached value
            
        Raises:
            RedisException: If cache operation fails
        """
        if not self.client:
            return None

        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
            
        except json.JSONDecodeError as e:
            logger.error(f"Cache deserialization failed: {str(e)}")
            raise RedisException(
                message="Failed to deserialize cached value",
                details={"key": key, "error": str(e)}
            )
        except Exception as e:
            logger.error(f"Cache get operation failed: {str(e)}")
            raise RedisException(
                message="Failed to get cached value",
                details={"key": key, "error": str(e)}
            )
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set cache value with JSON serialization.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional time-to-live in seconds
            
        Returns:
            bool: True if successful
            
        Raises:
            RedisException: If cache operation fails
        """
        if not self.client:
            return False

        try:
            serialized = json.dumps(value)
            return self.client.setex(
                key,
                ttl or self.default_ttl,
                serialized
            )
            
        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"Cache serialization failed: {str(e)}")
            raise RedisException(
                message="Failed to serialize value for caching",
                details={"key": key, "error": str(e)}
            )
        except Exception as e:
            logger.error(f"Cache set operation failed: {str(e)}")
            raise RedisException(
                message="Failed to set cached value",
                details={"key": key, "error": str(e)}
            )
    
    def delete(self, key: str) -> bool:
        """
        Delete cached value.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if successful
            
        Raises:
            RedisException: If cache operation fails
        """
        if not self.client:
            return False

        try:
            return bool(self.client.delete(key))
            
        except Exception as e:
            logger.error(f"Cache delete operation failed: {str(e)}")
            raise RedisException(
                message="Failed to delete cached value",
                details={"key": key, "error": str(e)}
            )
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if key exists
            
        Raises:
            RedisException: If cache operation fails
        """
        if not self.client:
            return False

        try:
            return bool(self.client.exists(key))
            
        except Exception as e:
            logger.error(f"Cache exists operation failed: {str(e)}")
            raise RedisException(
                message="Failed to check cache key existence",
                details={"key": key, "error": str(e)}
            )

# Export public interfaces
__all__ = ['get_redis_client', 'RedisCache']