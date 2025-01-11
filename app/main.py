"""
Main FastAPI application entry point for the Contract Processing System.
Implements comprehensive security, monitoring, and high availability features.

Version: 1.0
"""

# External imports with version specifications
from fastapi import FastAPI, Request, Response  # fastapi v0.95.0
from fastapi.middleware.trustedhost import TrustedHostMiddleware  # fastapi v0.95.0
from fastapi.middleware.gzip import GZipMiddleware  # fastapi v0.95.0
from redis import Redis  # redis v4.5.0
from pymongo import MongoClient  # pymongo v4.3.0
import structlog  # structlog v23.1.0
from prometheus_client import Counter, Histogram, CollectorRegistry  # prometheus_client v0.16.0
import time
from typing import Dict, Optional, Tuple
import uuid
import atexit
import signal
import asyncio
from fastapi.middleware.cors import CORSMiddleware

# Internal imports
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.middleware.cors_middleware import setup_cors_middleware
from app.core.logging import setup_logging
from app.db.mongodb import init_mongodb
from app.core.exceptions import handle_api_exception
from app.middleware.auth import auth_middleware

# Configure structured logging
logger = structlog.get_logger(__name__)

# Initialize metrics registry
metrics_registry = CollectorRegistry()

def setup_metrics() -> Tuple[Counter, Histogram]:
    """Initialize and return Prometheus metrics."""
    request_counter = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status'],
        registry=metrics_registry
    )

    request_duration = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        registry=metrics_registry
    )
    
    return request_counter, request_duration

# Initialize metrics
request_counter, request_duration = setup_metrics()

def create_application() -> FastAPI:
    """
    Creates and configures the FastAPI application with comprehensive security,
    monitoring, and high availability features.
    """
    settings = get_settings()
    
    # Create FastAPI application
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Contract Processing System API with comprehensive monitoring and security",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        redirect_slashes=False
    )
    
    # Add middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    setup_cors_middleware(app)
    
    # Add monitoring middleware
    @app.middleware("http")
    async def monitor_requests(request: Request, call_next):
        """Middleware for monitoring API requests with metrics collection."""
        start_time = time.time()
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        request_counter.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on application startup."""
        try:
            # Initialize MongoDB
            if not await init_mongodb():
                logger.error("Failed to initialize MongoDB")
                raise RuntimeError("Database initialization failed")
            logger.info("MongoDB initialized successfully")

            # Initialize Redis if enabled
            if settings.USE_REDIS:
                await initialize_redis(app)
                logger.info("Redis initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            raise
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup services on application shutdown."""
        from app.db.mongodb import close_mongodb_connection
        await close_mongodb_connection()
        logger.info("Cleaned up database connections")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add authentication middleware
    app.middleware("http")(auth_middleware)

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    return app

# Create FastAPI application instance
app = create_application()

async def initialize_redis(app: FastAPI) -> None:
    """
    Initialize Redis connection with failover support.

    Args:
        app: FastAPI application instance
    """
    settings = get_settings()
    redis_config = settings.get_redis_settings()

    try:
        app.state.redis = Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config['password'],
            ssl=redis_config['ssl'],
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True
        )
        await app.state.redis.ping()
        logger.info("Redis connection established successfully")

    except Exception as e:
        logger.error(f"Redis initialization failed: {str(e)}")
        raise

async def check_database_health() -> bool:
    """Check MongoDB connection health."""
    try:
        settings = get_settings()
        client = MongoClient(settings.MONGODB_URL.get_secret_value())
        client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

async def check_redis_health() -> bool:
    """Check Redis connection health."""
    try:
        settings = get_settings()
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD.get_secret_value()
        )
        return redis_client.ping()
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return False

# Handle system signals for graceful shutdown
def handle_sigterm(*args):
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info("Received SIGTERM signal")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=4,
        log_level="info"
    )