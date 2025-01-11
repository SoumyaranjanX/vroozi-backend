# Version: 1.0
# Purpose: Enhanced FastAPI middleware for comprehensive request/response logging,
# performance monitoring, and security tracking with ELK Stack integration

import time
import uuid
import psutil  # version 5.9.0
from typing import Callable, Dict, Any
import contextlib
from fastapi import Request, Response  # version 0.95.0
import re
import json
from datetime import datetime

from app.core.logging import log_request, log_response
from app.config.settings import DEBUG, ENVIRONMENT

# Global Constants
EXCLUDED_PATHS = [
    '/health', '/metrics', '/docs', '/redoc', '/openapi.json',
    '/favicon.ico', '/_next/*', '/static/*', '/api/v1/auth/*'
]

SENSITIVE_PATTERNS = [
    r'password', r'token', r'secret', r'key', r'auth',
    r'credit_card', r'ssn'
]

def generate_trace_id() -> str:
    """
    Generate a unique trace ID with enhanced security features.
    
    Returns:
        str: Environment-prefixed UUID string with timestamp
    """
    timestamp = int(time.time() * 1_000_000)  # Microsecond precision
    unique_id = str(uuid.uuid4())
    env_prefix = ENVIRONMENT[:4].upper()
    return f"{env_prefix}-{timestamp}-{unique_id}"

def should_log_path(path: str) -> bool:
    """
    Determine if the request path should be logged using pattern matching.
    
    Args:
        path: Request path to evaluate
        
    Returns:
        bool: True if path should be logged, False if excluded
    """
    # Check exact matches
    if path in EXCLUDED_PATHS:
        return False
    
    # Check wildcard patterns
    for excluded in EXCLUDED_PATHS:
        if excluded.endswith('/*'):
            prefix = excluded[:-2]
            if path.startswith(prefix):
                return False
    
    return True

def get_memory_usage() -> Dict[str, float]:
    """
    Capture current process memory usage statistics.
    
    Returns:
        dict: Memory usage metrics including RSS and virtual memory
    """
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'rss_bytes': memory_info.rss,
        'vms_bytes': memory_info.vms,
        'memory_percent': process.memory_percent(),
        'cpu_percent': process.cpu_percent(interval=None)
    }

@contextlib.contextmanager
async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Enhanced FastAPI middleware for comprehensive logging and monitoring.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware or route handler
        
    Returns:
        Response: Response from next middleware or route handler
    """
    # Generate trace ID and initial timestamp
    trace_id = generate_trace_id()
    start_time = time.perf_counter()
    initial_memory = get_memory_usage()
    
    # Prepare request context
    request_context = {
        'trace_id': trace_id,
        'method': request.method,
        'path': request.url.path,
        'query_params': str(request.query_params),
        'client_host': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
        'environment': ENVIRONMENT,
        'timestamp': datetime.utcnow().isoformat()
    }

    # Add request ID header
    request.state.trace_id = trace_id

    try:
        # Log request if path should be logged
        if should_log_path(request.url.path):
            # Mask sensitive data in headers and query params
            safe_headers = request.headers.copy()
            for pattern in SENSITIVE_PATTERNS:
                for key in safe_headers:
                    if re.search(pattern, key, re.IGNORECASE):
                        safe_headers[key] = '[REDACTED]'
            
            request_context['headers'] = dict(safe_headers)
            await log_request(request_context)

        # Process request
        response = await call_next(request)
        
        # Calculate performance metrics
        duration = time.perf_counter() - start_time
        final_memory = get_memory_usage()
        memory_delta = {
            'rss_delta': final_memory['rss_bytes'] - initial_memory['rss_bytes'],
            'vms_delta': final_memory['vms_bytes'] - initial_memory['vms_bytes'],
            'memory_percent_delta': final_memory['memory_percent'] - initial_memory['memory_percent']
        }

        # Prepare response context
        response_context = {
            **request_context,
            'status_code': response.status_code,
            'duration_seconds': duration,
            'memory_metrics': memory_delta,
            'response_time_ms': duration * 1000,
            'content_length': len(response.body) if hasattr(response, 'body') else 0
        }

        # Add performance headers in debug mode
        if DEBUG:
            response.headers['X-Process-Time'] = str(duration)
            response.headers['X-Memory-Delta'] = json.dumps(memory_delta)

        # Add trace ID to response headers
        response.headers['X-Trace-ID'] = trace_id

        # Log response if path was logged
        if should_log_path(request.url.path):
            await log_response(response_context)

        return response

    except Exception as e:
        # Log error with full context
        error_context = {
            **request_context,
            'error': str(e),
            'error_type': e.__class__.__name__,
            'duration_seconds': time.perf_counter() - start_time
        }
        
        # Include stack trace in development
        if DEBUG:
            import traceback
            error_context['stack_trace'] = traceback.format_exc()
            
        await log_request({**error_context, 'event': 'request_error'})
        raise

# Export middleware function
__all__ = ['logging_middleware']