"""
Celery application configuration module for the Contract Processing System.
Implements distributed task queue system with Redis Sentinel support, optimized worker
configurations, and comprehensive task routing for high availability and performance.

Version: 1.0
"""

# External imports with version specifications
from celery import Celery  # celery v5.2.7
from kombu import Queue, Exchange  # kombu v5.2.4
from celery.backends.redis import RedisBackend  # celery v5.2.7
import logging
from typing import Dict, Any
import os

# Internal imports
from app.core.config import get_settings
from app.db.redis_client import get_redis_client

# Configure logging
logger = logging.getLogger(__name__)

def ensure_directories(base_dir: str) -> None:
    """Create all required directories for Celery filesystem broker."""
    os.makedirs(os.path.join(base_dir, 'in'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'out'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'processed'), exist_ok=True)

def configure_celery() -> Celery:
    """
    Configures Celery application with enhanced Redis Sentinel support,
    optimized worker settings, and comprehensive task routing.
    
    Returns:
        Celery: Configured Celery application instance with HA support
    """
    try:
        settings = get_settings()
        redis_config = settings.get_redis_settings()
        use_redis = settings.USE_REDIS

        if use_redis and redis_config:
            # Configure broker and backend URLs with sentinel support
            broker_url = (
                f"sentinel://{redis_config['host']}:{redis_config['port']}/0"
                f"?master_name=mymaster"
            )
            if redis_config.get('password'):
                broker_url += f"&sentinel_kwargs={{'password': '{redis_config['password']}'}}"
            
            backend_url = (
                f"sentinel://{redis_config['host']}:{redis_config['port']}/1"
                f"?master_name=mymaster"
            )
            if redis_config.get('password'):
                backend_url += f"&sentinel_kwargs={{'password': '{redis_config['password']}'}}"
        else:
            # Use filesystem backend when Redis is disabled (development mode)
            data_dir = '/app/celery_data'
            ensure_directories(data_dir)
            broker_url = "filesystem://"
            backend_url = f"file://{data_dir}"

        # Initialize Celery application
        app = Celery(
            'contract_processor',
            broker=broker_url,
            backend=backend_url,
            include=['app.tasks.ocr_tasks']
        )

        # Configure Celery settings
        app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=3600,  # 1 hour
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=100,
        )

        # Additional configuration for filesystem broker
        if not use_redis:
            data_dir = '/app/celery_data'
            app.conf.update(
                broker_transport_options={
                    'data_folder_in': os.path.join(data_dir, 'in'),
                    'data_folder_out': os.path.join(data_dir, 'out'),
                    'processed_folder': os.path.join(data_dir, 'processed'),
                    'store_processed': True,
                }
            )

        return app

    except Exception as e:
        logger.error(f"Failed to configure Celery: {str(e)}")
        # Use filesystem as fallback
        data_dir = '/app/celery_data'
        ensure_directories(data_dir)
        app = Celery(
            'contract_processor',
            broker="filesystem://",
            backend=f"file://{data_dir}",
            include=['app.tasks.ocr_tasks']
        )
        app.conf.update(
            broker_transport_options={
                'data_folder_in': os.path.join(data_dir, 'in'),
                'data_folder_out': os.path.join(data_dir, 'out'),
                'processed_folder': os.path.join(data_dir, 'processed'),
                'store_processed': True,
            }
        )
        return app

def init_celery() -> None:
    """
    Initializes Celery application with comprehensive configuration
    including monitoring and HA support.
    """
    try:
        # Configure and get Celery app instance
        app = configure_celery()
        
        # Register task modules
        app.autodiscover_tasks([
            'app.tasks.ocr_tasks',
            'app.tasks.email_tasks',
            'app.tasks.contract_tasks'
        ])

        # Configure Flower monitoring
        app.conf.update(
            flower_basic_auth=['admin:admin'],
            flower_port=5555,
            flower_address='0.0.0.0'
        )

        # Set up logging integration
        app.log.setup_logging_subsystem()

        logger.info("Celery application initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize Celery: {str(e)}")
        raise

# Create and configure Celery application instance
celery_app = configure_celery()

# Export Celery application instance
__all__ = ['celery_app']