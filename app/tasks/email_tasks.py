"""
Celery task module for handling asynchronous email notifications including contract processing
updates and purchase order generation notifications. Implements retry mechanisms, comprehensive
error handling, and performance monitoring.

Version: 1.0
"""

# External imports with version specifications
from celery import Task  # celery v5.2.7
import structlog  # structlog v22.1+
from typing import Dict, Any
import asyncio
from datetime import datetime

# Internal imports
from app.tasks.celery_app import celery_app
from app.services.email_service import EmailService

# Configure structured logging
logger = structlog.get_logger(__name__)

# Initialize email service
email_service = EmailService()

class EmailTask(Task):
    """Base task class for email notifications with enhanced error handling and monitoring."""
    
    _email_service = None
    
    @property
    def email_service(self) -> EmailService:
        """
        Singleton pattern for email service instance.
        
        Returns:
            EmailService: Configured email service instance
        """
        if self._email_service is None:
            self._email_service = email_service
        return self._email_service

@celery_app.task(
    base=EmailTask,
    queue='email_tasks',
    name='tasks.send_contract_processed_email',
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def send_contract_processed_email(
    recipient_email: str,
    contract_id: str,
    contract_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Celery task for sending contract processing completion notification emails
    with retry mechanism and status tracking.
    
    Args:
        recipient_email: Recipient's email address
        contract_id: ID of the processed contract
        contract_data: Contract processing results and metadata
        
    Returns:
        Dict containing delivery status and tracking information
        
    Raises:
        Exception: If email sending fails after all retries
    """
    task_id = celery_app.current_task.request.id
    logger.info(
        "contract_email_task_started",
        task_id=task_id,
        recipient=recipient_email,
        contract_id=contract_id
    )
    
    try:
        # Input validation
        if not all([recipient_email, contract_id, contract_data]):
            raise ValueError("Missing required parameters")
            
        # Initialize metrics
        start_time = datetime.utcnow()
        
        # Create event loop for async email sending
        loop = asyncio.get_event_loop()
        
        # Send email notification
        success = loop.run_until_complete(
            email_service.send_contract_processed_notification(
                recipient_email,
                contract_id,
                contract_data
            )
        )
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Prepare response with delivery status
        response = {
            "success": success,
            "task_id": task_id,
            "recipient": recipient_email,
            "contract_id": contract_id,
            "processing_time": processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "contract_email_sent_successfully" if success else "contract_email_send_failed",
            **response
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "contract_email_task_failed",
            task_id=task_id,
            recipient=recipient_email,
            contract_id=contract_id,
            error=str(e)
        )
        
        # Retry with exponential backoff
        raise celery_app.current_task.retry(exc=e)

@celery_app.task(
    base=EmailTask,
    queue='email_tasks',
    name='tasks.send_po_generated_email',
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def send_po_generated_email(
    recipient_email: str,
    po_number: str,
    po_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Celery task for sending purchase order generation notification emails
    with retry mechanism and status tracking.
    
    Args:
        recipient_email: Recipient's email address
        po_number: Generated purchase order number
        po_data: Purchase order details and metadata
        
    Returns:
        Dict containing delivery status and tracking information
        
    Raises:
        Exception: If email sending fails after all retries
    """
    task_id = celery_app.current_task.request.id
    logger.info(
        "po_email_task_started",
        task_id=task_id,
        recipient=recipient_email,
        po_number=po_number
    )
    
    try:
        # Input validation
        if not all([recipient_email, po_number, po_data]):
            raise ValueError("Missing required parameters")
            
        # Initialize metrics
        start_time = datetime.utcnow()
        
        # Create event loop for async email sending
        loop = asyncio.get_event_loop()
        
        # Send email notification
        success = loop.run_until_complete(
            email_service.send_po_generated_notification(
                recipient_email,
                po_number,
                po_data
            )
        )
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Prepare response with delivery status
        response = {
            "success": success,
            "task_id": task_id,
            "recipient": recipient_email,
            "po_number": po_number,
            "processing_time": processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "po_email_sent_successfully" if success else "po_email_send_failed",
            **response
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "po_email_task_failed",
            task_id=task_id,
            recipient=recipient_email,
            po_number=po_number,
            error=str(e)
        )
        
        # Retry with exponential backoff
        raise celery_app.current_task.retry(exc=e)