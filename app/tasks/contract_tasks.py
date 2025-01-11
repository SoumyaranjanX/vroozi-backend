"""
Celery task module for handling asynchronous contract processing operations.
Implements distributed task processing with retry mechanisms, comprehensive error handling,
performance monitoring, and secure task execution.

Version: 1.0
"""

# External imports with versions
import celery  # v5.2+
import logging  # built-in
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

# Internal imports
from app.tasks.celery_app import celery_app
from app.services.contract_service import ContractService
from app.services.ocr_service import OCRService
from app.services.s3_service import S3Service
from app.services.purchase_order_service import PurchaseOrderService
from app.core.logging import get_request_logger

# Configure logging
logger = get_request_logger(
    trace_id="contract_tasks",
    context={
        "component": "tasks",
        "module": "contract_tasks"
    }
)

# Initialize services lazily
_contract_service = None

def get_contract_service() -> ContractService:
    """Get or create the contract service instance"""
    global _contract_service
    if _contract_service is None:
        ocr_service = OCRService()
        s3_service = S3Service()
        po_service = PurchaseOrderService()
        _contract_service = ContractService(
            ocr_service=ocr_service,
            s3_service=s3_service,
            po_service=po_service
        )
    return _contract_service

@celery_app.task(
    name='contract_tasks.process_contract',
    queue='contract_tasks',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='100/m',
    priority=9
)
def process_contract_task(
    self,
    contract_id: str,
    processing_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Celery task for processing contract through OCR extraction with comprehensive
    error handling and monitoring.

    Args:
        contract_id: Unique identifier for the contract
        processing_options: Dictionary of processing configuration options
        
    Returns:
        Dict[str, Any]: Processing results with status and extracted data
        
    Raises:
        celery.exceptions.Retry: When task needs to be retried
    """
    task_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            "Contract processing started",
            extra={
                "task_id": task_id,
                "contract_id": contract_id,
                "options": processing_options
            }
        )
        
        # Get contract service instance
        contract_service = get_contract_service()
        
        # Process contract
        result = contract_service.process_contract(
            contract_id=contract_id,
            options=processing_options
        )
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "Contract processing completed",
            extra={
                "task_id": task_id,
                "contract_id": contract_id,
                "processing_time": processing_time
            }
        )
        
        return {
            "status": "success",
            "contract_id": contract_id,
            "processing_time": processing_time,
            "result": result
        }
        
    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        logger.error(
            "Contract processing failed",
            extra={
                "task_id": task_id,
                "contract_id": contract_id,
                "error": str(e),
                "processing_time": processing_time
            }
        )
        
        # Retry task if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
            
        return {
            "status": "error",
            "contract_id": contract_id,
            "error": str(e),
            "processing_time": processing_time
        }

@celery_app.task(
    name='contract_tasks.validate_contract',
    queue='contract_tasks',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    rate_limit='150/m',
    priority=8
)
def validate_contract_task(
    self,
    contract_id: str,
    validation_data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    Celery task for validating extracted contract data with enhanced validation logic.

    Args:
        contract_id: Contract identifier
        validation_data: Data for validation
        user_id: ID of user performing validation

    Returns:
        Dict containing validation results and metrics
    """
    start_time = datetime.utcnow()
    trace_id = str(uuid.uuid4())

    try:
        # Initialize validation context
        validation_context = {
            'trace_id': trace_id,
            'contract_id': contract_id,
            'user_id': user_id,
            'task_id': self.request.id
        }

        logger.info(
            "Contract validation started",
            extra=validation_context
        )

        # Get contract service instance
        contract_service = get_contract_service()

        # Perform contract validation
        validation_result = contract_service.validate_contract(
            contract_id=contract_id,
            validation_data=validation_data,
            user_id=user_id
        )

        # Calculate validation metrics
        validation_time = (datetime.utcnow() - start_time).total_seconds()

        # Prepare success response
        response = {
            'status': 'success',
            'contract_id': contract_id,
            'validation_time': validation_time,
            'validation_result': validation_result,
            'trace_id': trace_id
        }

        logger.info(
            "Contract validation completed",
            extra={
                **validation_context,
                "validation_time": validation_time
            }
        )

        return response

    except Exception as e:
        logger.error(
            "Contract validation failed",
            extra={
                "error": str(e),
                **validation_context
            }
        )

        if self.request.retries < self.max_retries:
            self.retry(exc=e)

        return {
            'status': 'error',
            'contract_id': contract_id,
            'error': str(e),
            'trace_id': trace_id
        }

@celery_app.task(
    name='contract_tasks.generate_pos',
    queue='contract_tasks',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='50/m',
    priority=7
)
def generate_purchase_orders_task(
    self,
    contract_id: str,
    user_id: str,
    generation_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Celery task for generating purchase orders from validated contract.

    Args:
        contract_id: Contract identifier
        user_id: ID of user requesting PO generation
        generation_options: PO generation configuration options

    Returns:
        Dict containing generated PO details and metrics
    """
    start_time = datetime.utcnow()
    trace_id = str(uuid.uuid4())

    try:
        # Initialize generation context
        generation_context = {
            'trace_id': trace_id,
            'contract_id': contract_id,
            'user_id': user_id,
            'task_id': self.request.id
        }

        logger.info(
            "Purchase order generation started",
            extra={
                "trace_id": trace_id,
                "contract_id": contract_id,
                "user_id": user_id,
                "task_id": self.request.id
            }
        )

        # Get contract service instance
        contract_service = get_contract_service()

        # Generate purchase orders
        po_result = contract_service.generate_purchase_orders(
            contract_id=contract_id,
            user_id=user_id,
            generation_options=generation_options
        )

        # Calculate generation metrics
        generation_time = (datetime.utcnow() - start_time).total_seconds()

        # Prepare success response
        response = {
            'status': 'success',
            'contract_id': contract_id,
            'generation_time': generation_time,
            'po_numbers': po_result.get('po_numbers', []),
            'trace_id': trace_id
        }

        logger.info(
            "Purchase order generation completed",
            extra={
                "trace_id": trace_id,
                "contract_id": contract_id,
                "user_id": user_id,
                "task_id": self.request.id,
                "generation_time": generation_time
            }
        )

        return response

    except Exception as e:
        logger.error(
            "po_generation_failed",
            error=str(e),
            **generation_context
        )

        sentry_sdk.capture_exception(e)

        if self.request.retries < self.max_retries:
            self.retry(exc=e)

        return {
            'status': 'error',
            'contract_id': contract_id,
            'error': str(e),
            'trace_id': trace_id
        }