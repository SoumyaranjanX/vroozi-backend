"""
Application initialization module for the Contract Processing System.
Configures and exports a production-ready FastAPI application instance with
comprehensive middleware, security, monitoring, and API routing capabilities.

Version: 1.0
"""

# External imports - versions specified for production stability
from fastapi import FastAPI, HTTPException, Request  # v0.95+
# TODO: Re-enable after fixing dependency issues
# from prometheus_fastapi_instrumentator import Instrumentator  # v5.9+
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

# Internal imports
from app.config.settings import (
    PROJECT_NAME,
    DEBUG,
    API_V1_PREFIX,
    MONGODB_URL
)
from app.api.v1.router import api_router
from app.middleware.cors_middleware import setup_cors_middleware
from app.db.mongodb import init_mongodb
from app.core.logging import setup_logging
from app.core.exceptions import handle_api_exception

# Initialize logging
logger = logging.getLogger(__name__)

# Export public interfaces
__all__ = []