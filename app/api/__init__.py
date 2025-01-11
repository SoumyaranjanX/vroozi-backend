"""
API package initialization module for the Contract Processing System.
Configures and exports the main FastAPI router with versioned endpoints,
security features, and monitoring integration.

Version: 1.0
"""

# External imports with version specifications
from fastapi import APIRouter  # fastapi v0.95.0
from typing import Dict, Any

# Internal imports
from app.api.v1.router import api_router as v1_router
from app.core.logging import get_request_logger
from app.core.exceptions import handle_api_exception

# Configure module logger
logger = get_request_logger(
    trace_id="api_init",
    context={
        "component": "api",
        "api_version": "1.0"
    }
)

# Global constants for API configuration
API_VERSION = "v1"
API_PREFIX = "/api"
DEPRECATED_VERSIONS: Dict[str, Any] = {}  # Track deprecated API versions

def get_api_router() -> APIRouter:
    """
    Returns configured API router with versioning and security features.
    
    Returns:
        APIRouter: Configured FastAPI router instance
    """
    try:
        # Create main API router
        main_router = APIRouter()
        
        # Include v1 router with prefix
        main_router.include_router(
            v1_router,
            prefix=f"{API_PREFIX}/{API_VERSION}"
        )
        
        logger.info(
            "API router initialized successfully",
            extra={
                "current_version": API_VERSION,
                "deprecated_versions": list(DEPRECATED_VERSIONS.keys())
            }
        )
        
        return main_router
        
    except Exception as e:
        logger.error(f"Failed to initialize API router: {str(e)}")
        raise

# Export configured router for application use
api_router = get_api_router()

# Export version information
__version__ = "1.0"
__api_version__ = API_VERSION

# Export public interfaces
__all__ = [
    "api_router",
    "__version__",
    "__api_version__"
]