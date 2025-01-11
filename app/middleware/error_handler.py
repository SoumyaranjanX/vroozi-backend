"""
Error handling middleware for the FastAPI application.
Provides centralized error handling and logging with PII masking.

Version: 1.0
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Dict, Any, Optional
import traceback
import logging

from app.core.exceptions import BaseAPIException, handle_api_exception
from app.core.security import PIIMasker
from app.core.logging import get_request_logger

# Configure logger
logger = get_request_logger(
    trace_id="error_handler",
    context={
        "component": "middleware",
        "module": "error_handler"
    }
)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling and logging API errors with PII masking."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process the request and handle any errors.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            Response: The API response
        """
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Mask any PII in the error details
            error_details = handle_api_exception(e)
            masked_details = PIIMasker.mask_pii(error_details)
            
            # Log the error with masked details
            logger.error(
                "Request processing failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_details": masked_details,
                    "path": request.url.path,
                    "method": request.method,
                    "traceback": traceback.format_exc()
                }
            )
            
            # Return error response
            if isinstance(e, BaseAPIException):
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "detail": e.message,
                        "error_details": masked_details
                    }
                )
            
            # Handle unexpected errors
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_details": masked_details
                }
            )