"""
Tasks package initialization module for the Contract Processing System.
Exports Celery tasks for contract processing, OCR operations, and email notifications
with comprehensive monitoring and error handling capabilities.

Version: 1.0
"""

# Import Celery application instance
from app.tasks.celery_app import celery_app

# Import OCR processing tasks
from app.tasks.ocr_tasks import (
    process_contract_ocr,
    bulk_process_contracts
)

# Import contract processing tasks
from app.tasks.contract_tasks import (
    process_contract_task,
    validate_contract_task
)

# Import email notification tasks
from app.tasks.email_tasks import (
    send_contract_processed_email,
    send_po_generated_email
)

# Export all task interfaces
__all__ = [
    'celery_app',
    'process_contract_ocr',
    'bulk_process_contracts',
    'process_contract_task',
    'validate_contract_task',
    'send_contract_processed_email',
    'send_po_generated_email'
]

# Initialize Celery application configuration
celery_app.conf.update(
    # Task routing configuration
    task_routes={
        'app.tasks.ocr_tasks.*': {'queue': 'ocr_tasks'},
        'app.tasks.contract_tasks.*': {'queue': 'contract_tasks'},
        'app.tasks.email_tasks.*': {'queue': 'email_tasks'}
    },

    # Task execution settings
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_compression='gzip',
    result_compression='gzip',
    task_track_started=True,
    task_track_received=True,
    task_send_sent_event=True,
    worker_send_task_events=True,

    # Worker configuration
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=400000,  # 400MB
    worker_concurrency=8,
    worker_pool='prefork',

    # Task time limits
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queue_max_priority=10,

    # Monitoring and events
    enable_utc=True,
    timezone='UTC'
)

# Register task modules for auto-discovery
celery_app.autodiscover_tasks([
    'app.tasks.ocr_tasks',
    'app.tasks.contract_tasks',
    'app.tasks.email_tasks'
])