"""
Logging configuration module.

Version: 1.0
"""

import logging
import logging.config
import os
from typing import Dict, Any, Optional
import json
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import socket
import uuid
from datetime import datetime

from app.config.settings import ENVIRONMENT, DEBUG

# Global Constants
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

# Environment-specific log formats
LOG_FORMAT = {
    'development': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'production': {
        'timestamp': '%(asctime)s',
        'level': '%(levelname)s',
        'service': 'contract-processor',
        'name': '%(name)s',
        'message': '%(message)s',
        'trace_id': '%(trace_id)s',
        'environment': '%(environment)s',
        'host': '%(hostname)s',
        'thread': '%(threadName)s'
    }
}

LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE_PATH = '/app/logs'
AUDIT_LOG_FILE = 'security_audit.log'

class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for ELK Stack integration"""
    
    def __init__(self):
        super().__init__()
        self.hostname = socket.gethostname()

    def format(self, record):
        """Format log record as JSON with additional context"""
        # Add default trace ID if not present
        if not hasattr(record, 'trace_id'):
            record.trace_id = str(uuid.uuid4())

        # Add hostname if not present
        if not hasattr(record, 'hostname'):
            record.hostname = self.hostname

        # Add environment if not present
        if not hasattr(record, 'environment'):
            record.environment = ENVIRONMENT

        # Create log entry dictionary
        log_entry = {
            'timestamp': datetime.utcfromtimestamp(record.created).strftime(LOG_DATE_FORMAT),
            'level': record.levelname,
            'service': 'contract-processor',
            'name': record.name,
            'message': record.getMessage(),
            'trace_id': record.trace_id,
            'environment': record.environment,
            'host': record.hostname,
            'thread': record.threadName
        }

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add custom fields if present
        if hasattr(record, 'data'):
            log_entry['data'] = record.data

        return json.dumps(log_entry)

class SecurityAuditFormatter(logging.Formatter):
    """Specialized formatter for security audit logs"""
    
    def format(self, record):
        """Format security audit log with additional context"""
        record.timestamp = datetime.utcfromtimestamp(record.created).strftime(LOG_DATE_FORMAT)
        return (f"[{record.timestamp}] [{record.levelname}] "
                f"[TraceID: {getattr(record, 'trace_id', 'N/A')}] "
                f"[User: {getattr(record, 'user', 'N/A')}] "
                f"[IP: {getattr(record, 'ip', 'N/A')}] "
                f"[Action: {getattr(record, 'action', 'N/A')}] "
                f"{record.getMessage()}")

class SecurityLogger:
    """Security event logging utility."""
    
    def __init__(self):
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        # Add file handler if not already present
        if not self.logger.handlers:
            # Ensure logs directory exists
            os.makedirs(LOG_FILE_PATH, exist_ok=True)
            
            fh = logging.FileHandler(os.path.join(LOG_FILE_PATH, AUDIT_LOG_FILE))
            fh.setLevel(logging.INFO)
            formatter = SecurityAuditFormatter()
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
    
    def log_security_event(self, event_type: str, details: dict = None):
        """Log security event with details."""
        self.logger.info(
            f"Security event: {event_type}",
            extra={"details": details or {}}
        )

class AuditLogger:
    """Audit logging utility for tracking operations and changes."""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # Add file handler if not already present
        if not self.logger.handlers:
            # Ensure logs directory exists
            os.makedirs(LOG_FILE_PATH, exist_ok=True)
            
            fh = TimedRotatingFileHandler(
                os.path.join(LOG_FILE_PATH, 'audit.log'),
                when='midnight',
                interval=1,
                backupCount=30
            )
            fh.setLevel(logging.INFO)
            formatter = JsonFormatter()
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
    
    async def log_operation(self, entity_type: str, action: str, user_id: str, details: Dict[str, Any] = None):
        """Log an operation with its details."""
        log_data = {
            'entity_type': entity_type,
            'action': action,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'trace_id': str(uuid.uuid4()),
            'details': details or {}
        }
        
        self.logger.info(
            f"{action} performed on {entity_type}",
            extra={
                'data': log_data,
                'trace_id': log_data['trace_id']
            }
        )

def get_file_handler_config(filename: str, formatter: str, additional_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Generate configuration for file-based logging handlers"""
    
    # Ensure logs directory exists
    os.makedirs(LOG_FILE_PATH, exist_ok=True)
    
    file_path = os.path.join(LOG_FILE_PATH, filename)
    
    handler_config = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': file_path,
        'maxBytes': 10485760,  # 10MB
        'backupCount': 10,
        'encoding': 'utf-8',
        'formatter': formatter,
        'mode': 'a',
    }
    
    # Update with additional settings
    handler_config.update(additional_settings)
    
    return handler_config

def get_log_config() -> Dict[str, Any]:
    """Generate comprehensive logging configuration"""
    
    # Create formatters based on environment
    formatters = {
        'standard': {
            'format': LOG_FORMAT['development'],
            'datefmt': LOG_DATE_FORMAT
        },
        'json': {
            '()': JsonFormatter
        },
        'security': {
            '()': SecurityAuditFormatter
        }
    }

    # Configure handlers
    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if ENVIRONMENT == 'production' else 'standard',
            'level': LOG_LEVEL
        },
        'file': get_file_handler_config(
            'app.log',
            'json' if ENVIRONMENT == 'production' else 'standard',
            {'maxBytes': 10485760, 'backupCount': 10}
        ),
        'security_audit': get_file_handler_config(
            AUDIT_LOG_FILE,
            'security',
            {
                'maxBytes': 52428800,  # 50MB
                'backupCount': 30,
                'mode': 'a',
            }
        )
    }

    # Configure loggers
    loggers = {
        '': {  # Root logger
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': True
        },
        'security_audit': {
            'handlers': ['security_audit', 'console'],
            'level': logging.INFO,
            'propagate': False
        },
        'contract_processor': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False
        }
    }

    # Complete logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'handlers': handlers,
        'loggers': loggers,
        'incremental': False
    }

    return config

def configure_logging():
    """Configure logging with environment-specific settings"""
    os.makedirs(LOG_FILE_PATH, exist_ok=True)
    logging.config.dictConfig(get_log_config())

def get_request_logger(
    trace_id: str = None,
    context: Dict[str, Any] = None
) -> logging.Logger:
    """
    Get a logger instance with request context.
    
    Args:
        trace_id: Optional trace ID for correlation
        context: Optional additional context information
        
    Returns:
        logging.Logger: Logger instance with request context
    """
    logger = logging.getLogger('request')
    
    extra = {}
    if trace_id:
        extra['trace_id'] = trace_id
    if context:
        extra.update(context)
    
    if extra:
        logger = logging.LoggerAdapter(logger, extra)
    
    return logger

def log_error(
    logger: logging.Logger,
    error: Exception,
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with context.
    
    Args:
        logger: The logger instance to use
        error: The exception that occurred
        message: A descriptive message about the error
        context: Additional context to include in the log
    """
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {})
    }
    
    logger.error(message, extra={"context": error_context})

def log_request(
    logger: logging.Logger,
    request: Any,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an incoming request with context.
    
    Args:
        logger: The logger instance to use
        request: The request object
        context: Additional context to include in the log
    """
    request_context = {
        "method": getattr(request, "method", "UNKNOWN"),
        "path": str(getattr(request, "url", "UNKNOWN")),
        "client_host": getattr(getattr(request, "client", None), "host", "UNKNOWN"),
        "headers": dict(getattr(request, "headers", {})),
        **(context or {})
    }
    
    logger.info("Request received", extra={"context": request_context})

def log_response(
    logger: logging.Logger,
    response: Any,
    request_time: float,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an outgoing response with timing and context.
    
    Args:
        logger: The logger instance to use
        response: The response object
        request_time: The time taken to process the request
        context: Additional context to include in the log
    """
    response_context = {
        "status_code": getattr(response, "status_code", 500),
        "processing_time": request_time,
        **(context or {})
    }
    
    logger.info("Response sent", extra={"context": response_context})

def setup_logging():
    """Initialize logging configuration for the application."""
    try:
        # Ensure logs directory exists
        os.makedirs(LOG_FILE_PATH, exist_ok=True)
        
        # Get logging configuration
        config = get_log_config()
        
        # Apply configuration
        logging.config.dictConfig(config)
        
        # Initialize security logger
        security_logger = SecurityLogger()
        
        # Initialize audit logger
        audit_logger = AuditLogger()
        
        # Log successful initialization
        logging.getLogger(__name__).info("Logging system initialized successfully")
        
        return security_logger, audit_logger
        
    except Exception as e:
        # Fallback to basic configuration if setup fails
        logging.basicConfig(
            level=LOG_LEVEL,
            format=LOG_FORMAT['development'],
            datefmt=LOG_DATE_FORMAT
        )
        logging.error(f"Failed to initialize logging configuration: {str(e)}")
        raise

# Export constants and functions
__all__ = [
    'LOG_LEVEL',
    'LOG_FORMAT',
    'LOG_DATE_FORMAT',
    'get_log_config',
    'configure_logging',
    'SecurityLogger',
    'AuditLogger',
    'get_request_logger',
    'log_error',
    'log_request',
    'log_response',
    'setup_logging'
]