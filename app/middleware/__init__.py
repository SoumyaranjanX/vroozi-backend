"""
Middleware initialization module for the Contract Processing System.
Implements a secure, monitored, and performant middleware stack with comprehensive
error handling, logging, and authentication capabilities.

Version: 1.0
"""

# External imports with version specifications
from fastapi import FastAPI  # version 0.95+
from prometheus_client import Counter, Histogram  # version 0.16+
import structlog  # version 23.1+
from typing import Dict, Any
import time
import logging

# Internal imports
from app.middleware.cors_middleware import setup_cors_middleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging_middleware import logging_middleware
from app.middleware.auth_middleware import AuthMiddleware
from app.core.logging import get_request_logger
from app.core.config import get_settings
from app.db.mongodb import get_database

# Configure structured logging
logger = structlog.get_logger("middleware")

# Initialize metrics collectors
MIDDLEWARE_METRICS = {
    "operations_total": Counter(
        "middleware_operations_total",
        "Total count of middleware operations",
        ["middleware_type", "status"]
    ),
    "operation_duration": Histogram(
        "middleware_operation_duration_seconds",
        "Duration of middleware operations",
        ["middleware_type"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
    )
}

async def setup_middleware(app: FastAPI, config: Dict[str, Any]) -> None:
    """
    Configures and adds all middleware components to the FastAPI application
    with comprehensive security, monitoring, and error handling capabilities.

    Args:
        app: FastAPI application instance
        config: Application configuration dictionary

    Returns:
        None: Modifies FastAPI application in place
    """
    try:
        # Get application settings
        settings = get_settings()
        environment = settings.ENVIRONMENT

        # Initialize request logger
        request_logger = get_request_logger(
            trace_id="middleware_setup",
            context={"environment": environment}
        )

        # Start timing middleware setup
        start_time = time.time()

        # 1. Set up CORS middleware with security policies
        logger.info("Configuring CORS middleware...")
        setup_cors_middleware(app)
        MIDDLEWARE_METRICS["operations_total"].labels(
            middleware_type="cors",
            status="success"
        ).inc()

        # 2. Configure error handling middleware
        logger.info("Configuring error handling middleware...")
        app.add_middleware(ErrorHandlerMiddleware)
        MIDDLEWARE_METRICS["operations_total"].labels(
            middleware_type="error_handler",
            status="success"
        ).inc()

        # 3. Set up authentication middleware with Redis client
        logger.info("Configuring authentication middleware...")
        redis_client = config.get("redis_client")
        if not redis_client:
            raise ValueError("Redis client not configured for auth middleware")

        app.add_middleware(
            AuthMiddleware,
            redis_client=redis_client,
            security_logger=request_logger,
            rate_limiter=config.get("rate_limiter")
        )
        MIDDLEWARE_METRICS["operations_total"].labels(
            middleware_type="auth",
            status="success"
        ).inc()

        # 4. Add logging middleware with ELK stack integration
        logger.info("Configuring logging middleware...")
        app.middleware("http")(logging_middleware)
        MIDDLEWARE_METRICS["operations_total"].labels(
            middleware_type="logging",
            status="success"
        ).inc()

        # 5. Add performance monitoring middleware
        @app.middleware("http")
        async def performance_middleware(request, call_next):
            start_time = time.time()
            response = await call_next(request)
            duration = time.time() - start_time
            
            MIDDLEWARE_METRICS["operation_duration"].labels(
                middleware_type="request"
            ).observe(duration)
            
            return response

        # 6. Add health check endpoints for middleware components
        @app.get("/health/middleware", tags=["Health"])
        async def middleware_health():
            health_status = {
                "cors": True,
                "auth": await _check_auth_health(redis_client),
                "logging": await _check_logging_health(),
                "database": await _check_database_health()
            }
            return {"status": "healthy" if all(health_status.values()) else "unhealthy",
                    "components": health_status}

        # Calculate and log setup duration
        setup_duration = time.time() - start_time
        MIDDLEWARE_METRICS["operation_duration"].labels(
            middleware_type="setup"
        ).observe(setup_duration)

        logger.info(
            "Middleware stack configured successfully",
            duration=setup_duration,
            environment=environment
        )

    except Exception as e:
        logger.error(
            "Failed to configure middleware stack",
            error=str(e),
            environment=environment
        )
        MIDDLEWARE_METRICS["operations_total"].labels(
            middleware_type="setup",
            status="error"
        ).inc()
        raise

async def _check_auth_health(redis_client) -> bool:
    """Checks health of authentication components."""
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Auth health check failed: {str(e)}")
        return False

async def _check_logging_health() -> bool:
    """Checks health of logging components."""
    try:
        # Verify logger configuration
        return logging.getLogger().handlers != []
    except Exception as e:
        logger.error(f"Logging health check failed: {str(e)}")
        return False

async def _check_database_health() -> bool:
    """Checks health of database connection."""
    try:
        db = await get_database()
        await db.command('ping')
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

# Export public interfaces
__all__ = ['setup_middleware']