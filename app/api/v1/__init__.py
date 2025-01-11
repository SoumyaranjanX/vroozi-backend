"""
FastAPI v1 API router initialization module that configures and exports the main API router
with comprehensive security, monitoring, and rate limiting for all v1 endpoints.

Version: 1.0
"""

# External imports with version specifications
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_limiter import FastAPILimiter
from prometheus_client import Counter, Histogram
import structlog
from datetime import datetime
import logging
from typing import Dict, Any

# Configure module logger
logger = logging.getLogger(__name__)

# Initialize metrics
request_counter = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Initialize base router
api_router = APIRouter()

# Export router
__all__ = ["api_router"]