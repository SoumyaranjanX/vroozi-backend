"""
Initialization module for the API v1 endpoints package that exports all endpoint routers
for the Contract Processing System. Provides centralized access to authentication,
contract management, purchase order, OCR, and user management endpoints with comprehensive
security, monitoring, and error handling capabilities.

Version: 1.0
"""

# External imports with version specifications
from fastapi import APIRouter  # fastapi v0.95.0
from prometheus_client import Counter, Histogram  # prometheus_client v0.16.0
from circuitbreaker import CircuitBreaker  # circuitbreaker v1.4.0
import structlog  # structlog v22.1.0
from typing import Dict, List

# Internal imports
from .auth import router as auth_router
from .contracts import router as contracts_router
from .purchase_orders import router as purchase_orders_router
from .ocr import router as ocr_router

# Configure structured logging
logger = structlog.get_logger(__name__)

# Global constants
API_VERSION = "v1"
RATE_LIMIT_DEFAULT = "100/minute"

# Prometheus metrics
ENDPOINT_REQUESTS = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status']
)

ENDPOINT_LATENCY = Histogram(
    'api_request_duration_seconds',
    'API endpoint latency in seconds',
    ['endpoint', 'method']
)

@CircuitBreaker(failure_threshold=5, recovery_timeout=60)
def initialize_routers() -> Dict[str, APIRouter]:
    """
    Initializes and validates all API endpoint routers with security and monitoring.
    Implements circuit breaker pattern for external service dependencies.

    Returns:
        Dict[str, APIRouter]: Dictionary of initialized and validated routers

    Raises:
        RuntimeError: If router initialization fails
    """
    try:
        # Initialize router collection
        routers = {
            'auth': auth_router,
            'contracts': contracts_router,
            'purchase_orders': purchase_orders_router,
            'ocr': ocr_router
        }

        # Validate router configurations
        for name, router in routers.items():
            logger.info(
                "Initializing router",
                router_name=name,
                endpoint_count=len(router.routes)
            )

            # Validate route handlers
            for route in router.routes:
                if not route.endpoint:
                    raise ValueError(f"Invalid route handler in {name} router")

        logger.info(
            "API routers initialized successfully",
            router_count=len(routers),
            api_version=API_VERSION
        )

        return routers

    except Exception as e:
        logger.error(
            "Failed to initialize API routers",
            error=str(e)
        )
        raise RuntimeError(f"Router initialization failed: {str(e)}")

async def monitor_requests(request, call_next):
    """
    Middleware for monitoring API requests with metrics collection.

    Args:
        request: FastAPI request object
        call_next: Next middleware in chain

    Returns:
        Response from next middleware
    """
    import time
    start_time = time.time()

    try:
        # Process request
        response = await call_next(request)

        # Record metrics
        endpoint = request.url.path
        method = request.method
        status = response.status_code

        ENDPOINT_REQUESTS.labels(
            endpoint=endpoint,
            method=method,
            status=status
        ).inc()

        ENDPOINT_LATENCY.labels(
            endpoint=endpoint,
            method=method
        ).observe(time.time() - start_time)

        return response

    except Exception as e:
        logger.error(
            "Request processing failed",
            endpoint=request.url.path,
            method=request.method,
            error=str(e)
        )
        raise

# Initialize routers with monitoring
initialized_routers = initialize_routers()

# Export routers and version
__all__ = [
    'auth_router',
    'contracts_router', 
    'purchase_orders_router',
    'ocr_router',
    'API_VERSION'
]