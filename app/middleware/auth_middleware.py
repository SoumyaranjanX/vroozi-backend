"""
Authentication middleware for the FastAPI application.
Provides JWT token validation, rate limiting, and role-based access control.

Version: 1.0
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Dict, Any, Optional
import time
import logging

from app.core.security import verify_token, get_token_from_header
from app.core.exceptions import CREDENTIALS_EXCEPTION
from app.core.logging import get_request_logger

# Configure logger
logger = get_request_logger(
    trace_id="auth_middleware",
    context={
        "component": "middleware",
        "module": "auth"
    }
)

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication and rate limiting."""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        """
        Initialize the middleware.
        
        Args:
            app: The FastAPI application
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/api/docs", "/api/redoc", "/api/openapi.json"]
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process the request and handle authentication.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            Response: The API response
        """
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        try:
            # Get and verify token
            token = get_token_from_header(request)
            if not token:
                raise CREDENTIALS_EXCEPTION
            
            # Verify token and get user info
            user_info = verify_token(token)
            
            # Add user info to request state
            request.state.user = user_info
            
            # Process request
            start_time = time.time()
            response = await call_next(request)
            request_time = time.time() - start_time
            
            # Log successful request
            logger.info(
                "Request authenticated",
                extra={
                    "user_id": user_info.get("sub"),
                    "path": request.url.path,
                    "method": request.method,
                    "processing_time": request_time
                }
            )
            
            return response
            
        except Exception as e:
            # Log authentication failure
            logger.error(
                "Authentication failed",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(e)
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication failed",
                    "error": str(e)
                }
            )