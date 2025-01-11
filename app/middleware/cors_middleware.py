"""
CORS Middleware module for secure cross-origin resource sharing configuration.
Provides comprehensive security controls with environment-aware settings.

Version: 1.0
"""

# External imports with version specifications
from fastapi.middleware.cors import CORSMiddleware  # fastapi v0.95+
from fastapi import FastAPI  # fastapi v0.95+
from typing import List, Dict
import logging
import re

# Internal imports
from app.core.config import get_settings

# Configure logger
logger = logging.getLogger(__name__)

def validate_origin(origin: str, allowed_origins: List[str], environment: str) -> bool:
    """
    Validates origin against allowed patterns with environment-specific rules.
    
    Args:
        origin: Origin to validate
        allowed_origins: List of allowed origin patterns
        environment: Current environment (development, staging, production)
        
    Returns:
        bool: Whether the origin is valid
    """
    try:
        # Production requires HTTPS
        if environment == "production" and not origin.startswith("https://"):
            logger.warning(f"Rejected non-HTTPS origin in production: {origin}")
            return False
            
        # Check against allowed patterns
        for pattern in allowed_origins:
            if pattern == "*":
                return environment != "production"  # Wildcard only allowed in non-production
            if re.match(pattern.replace("*", ".*"), origin):
                return True
                
        logger.warning(f"Origin not in allowed list: {origin}")
        return False
        
    except Exception as e:
        logger.error(f"Origin validation error: {str(e)}")
        return False

def setup_cors_middleware(app: FastAPI) -> None:
    """
    Configures enhanced CORS middleware with comprehensive security controls.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        None: Modifies FastAPI application in place
    """
    settings = get_settings()
    environment = settings.ENVIRONMENT
    
    # Security headers based on environment
    security_headers: Dict[str, str] = settings.SECURITY_HEADERS.copy()
    
    # Environment-specific CORS configuration
    cors_config = {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
        ],
        "expose_headers": [
            "Content-Length",
            "Content-Range",
            "X-Content-Range",
        ],
        "max_age": 600,  # 10 minutes cache for preflight requests
    }
    
    # Production-specific security enhancements
    if environment == "production":
        # Strict HTTPS enforcement
        security_headers.update({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "frame-ancestors 'none'"
            ),
        })
        
        # Stricter CORS settings for production
        cors_config.update({
            "allow_credentials": True,
            "max_age": 3600,  # 1 hour cache for preflight in production
        })
    
    # Custom CORS middleware with enhanced security
    class SecureCORSMiddleware(CORSMiddleware):
        async def validate_origin_security(self, origin: str) -> bool:
            """Enhanced origin validation with security logging."""
            is_valid = validate_origin(origin, self.allow_origins, environment)
            
            if not is_valid:
                logger.warning(
                    f"CORS violation attempt - Origin: {origin}, "
                    f"Environment: {environment}"
                )
            
            return is_valid
    
    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        for header, value in security_headers.items():
            response.headers[header] = value
        return response
    
    # Add CORS middleware with security enhancements
    app.add_middleware(
        SecureCORSMiddleware,
        **cors_config,
    )
    
    # Add CORS violation monitoring
    @app.middleware("http")
    async def monitor_cors_violations(request, call_next):
        try:
            origin = request.headers.get("origin")
            if origin and not validate_origin(origin, settings.CORS_ORIGINS, environment):
                logger.warning(
                    f"CORS violation detected - Origin: {origin}, "
                    f"Path: {request.url.path}, "
                    f"Method: {request.method}, "
                    f"Environment: {environment}"
                )
        except Exception as e:
            logger.error(f"CORS monitoring error: {str(e)}")
            
        return await call_next(request)

    logger.info(
        f"CORS middleware configured for environment: {environment} "
        f"with {len(settings.CORS_ORIGINS)} allowed origins"
    )

# Export public interfaces
__all__ = ['setup_cors_middleware']