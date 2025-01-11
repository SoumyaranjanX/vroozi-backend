"""
Templates Package Initialization Module
Version: 1.0
Purpose: Provides centralized access to email and purchase order templates with caching and security.

This module manages template loading, caching, and rendering with comprehensive error handling
and type safety for the notification and document generation services.
"""

# External imports with version specifications
from pathlib import Path  # python 3.9+
from jinja2 import (  # jinja2 v3.1.2
    Environment,
    FileSystemLoader,
    Template,
    TemplateNotFound,
    sandbox
)
from typing import Dict, Optional
import logging
from threading import Lock

# Internal imports
from app.config.settings import TEMPLATES_DIR

# Configure logging
logger = logging.getLogger(__name__)

# Template path constants
TEMPLATE_PATHS = {
    'EMAIL_BASE': 'email/base.html',
    'CONTRACT_PROCESSED': 'email/contract_processed.html',
    'PO_GENERATED': 'email/po_generated.html',
    'PO_STANDARD': 'po/standard_template.html'
}

# Initialize Jinja2 environment with security settings and caching
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    auto_reload=False,  # Disable auto-reload in production
    enable_async=True,  # Enable async rendering
    cache_size=100,  # Limit cache size
    autoescape=True,  # Enable autoescaping for security
    trim_blocks=True,  # Remove first newline after block
    lstrip_blocks=True  # Strip tabs and spaces from start of line
)

# Template cache with thread-safe access
_template_cache: Dict[str, Template] = {}
_cache_lock = Lock()

def validate_template_path(template_path: str) -> bool:
    """
    Validates template path existence and accessibility.
    
    Args:
        template_path: Path to the template relative to TEMPLATES_DIR
        
    Returns:
        bool: True if template exists and is accessible
        
    Raises:
        ValueError: If template path is invalid or inaccessible
    """
    try:
        if template_path not in TEMPLATE_PATHS.values():
            raise ValueError(f"Invalid template path: {template_path}")
            
        full_path = Path(TEMPLATES_DIR) / template_path
        if not full_path.is_file():
            raise ValueError(f"Template file not found: {template_path}")
            
        if not os.access(full_path, os.R_OK):
            raise ValueError(f"Template file not readable: {template_path}")
            
        return True
    except Exception as e:
        logger.error(f"Template validation failed: {str(e)}")
        return False

def get_template(template_path: str) -> Template:
    """
    Retrieves a Jinja2 template with caching and error handling.
    
    Args:
        template_path: Path to the template relative to TEMPLATES_DIR
        
    Returns:
        Template: Jinja2 Template object for rendering
        
    Raises:
        TemplateNotFound: If template cannot be found
        ValueError: If template path is invalid
    """
    try:
        # Check cache first
        with _cache_lock:
            cached_template = _template_cache.get(template_path)
            if cached_template:
                return cached_template
        
        # Validate template path
        if not validate_template_path(template_path):
            raise ValueError(f"Invalid template path: {template_path}")
        
        # Load and cache template
        template = jinja_env.get_template(template_path)
        
        with _cache_lock:
            _template_cache[template_path] = template
        
        return template
    
    except TemplateNotFound as e:
        logger.error(f"Template not found: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading template: {str(e)}")
        raise

def render_template(template_path: str, context: dict) -> str:
    """
    Renders a template with provided context data and error handling.
    
    Args:
        template_path: Path to the template relative to TEMPLATES_DIR
        context: Dictionary containing template variables
        
    Returns:
        str: Rendered template string
        
    Raises:
        ValueError: If context data is invalid
        TemplateNotFound: If template cannot be found
    """
    try:
        # Validate context
        if not isinstance(context, dict):
            raise ValueError("Context must be a dictionary")
        
        # Get template
        template = get_template(template_path)
        
        # Create sandbox environment for secure rendering
        sandbox_env = sandbox.ImmutableSandboxedEnvironment()
        
        # Render template with sandbox
        rendered = sandbox_env.from_string(template.source).render(**context)
        
        # Basic validation of rendered output
        if not rendered or len(rendered.strip()) == 0:
            raise ValueError("Template rendered empty output")
        
        return rendered
    
    except Exception as e:
        logger.error(f"Template rendering failed: {str(e)}")
        raise

def clear_template_cache() -> None:
    """
    Clears the template cache to free memory.
    Thread-safe operation for cache management.
    """
    try:
        with _cache_lock:
            _template_cache.clear()
        logger.info("Template cache cleared successfully")
    except Exception as e:
        logger.error(f"Error clearing template cache: {str(e)}")
        raise

# Initialize template validation on module load
for template_name, template_path in TEMPLATE_PATHS.items():
    try:
        validate_template_path(template_path)
        logger.info(f"Validated template: {template_name}")
    except Exception as e:
        logger.error(f"Template validation failed for {template_name}: {str(e)}")

__all__ = [
    'TEMPLATE_PATHS',
    'get_template',
    'render_template',
    'clear_template_cache'
]