# Version: 1.0
# Purpose: Comprehensive logging configuration with ELK Stack integration and security audit logging

import logging
import logging.config
import os
from typing import Dict, Any
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
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
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
    """Configure application-wide logging with appropriate handlers and formatters."""
    config = get_log_config()
    logging.config.dictConfig(config)
    
    # Create logs directory if it doesn't exist
    os.makedirs(LOG_FILE_PATH, exist_ok=True)
    
    # Set up security audit logging
    audit_logger = logging.getLogger('security_audit')
    audit_handler = TimedRotatingFileHandler(
        os.path.join(LOG_FILE_PATH, AUDIT_LOG_FILE),
        when='midnight',
        interval=1,
        backupCount=30
    )
    audit_handler.setFormatter(SecurityAuditFormatter())
    audit_logger.addHandler(audit_handler)
    
    logging.info("Logging configuration completed successfully")

# Export constants and functions
__all__ = ['LOG_LEVEL', 'LOG_FORMAT', 'LOG_DATE_FORMAT', 'get_log_config', 'configure_logging']