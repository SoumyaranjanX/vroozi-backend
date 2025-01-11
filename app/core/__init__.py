"""
Core module initializer for the Contract Processing System.
Provides centralized access to core application services with thread-safe initialization
and proper resource management.

Version: 1.0
"""

# External imports with version specifications
import threading  # built-in

# Internal imports
from app.core.config import Settings, get_settings
from app.core.auth import (
    validate_token,
    PermissionDependency
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    revoke_token
)
from app.core.auth_utils import (
    get_password_hash,
    verify_password
)
from app.core.logging import configure_logging

# Global version
__version__ = "1.0.0"

# Thread synchronization primitives
_init_lock = threading.Lock()
_initialized = False

def initialize_core() -> None:
    """
    Thread-safe initialization of core module components.
    Sets up logging, configuration, and security services.
    
    Raises:
        RuntimeError: If initialization fails
    """
    global _initialized
    
    with _init_lock:
        try:
            # Check if already initialized
            if _initialized:
                return
                
            # Set up logging first for proper error tracking
            configure_logging()
            
            # Mark as initialized
            _initialized = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize core module: {str(e)}")

# Export public interfaces
__all__ = [
    "Settings",
    "get_settings",
    "validate_token",
    "PermissionDependency",
    "create_access_token",
    "create_refresh_token",
    "revoke_token",
    "get_password_hash",
    "verify_password",
    "configure_logging",
    "initialize_core"
]