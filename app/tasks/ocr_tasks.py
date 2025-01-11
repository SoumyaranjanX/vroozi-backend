"""
Enhanced Celery task module for OCR processing operations using Google Cloud Vision API.
Implements distributed task queue functionality with comprehensive monitoring, error handling,
and performance optimization.

Version: 1.0
"""

# External imports with version specifications
from celery import Task  # celery v5.2.7
import logging  # built-in
from prometheus_client import Counter, Histogram  # prometheus_client v0.15+
from typing import Dict, Any, Optional, List
import time
from datetime import datetime
import json

# Internal imports
from app.tasks.celery_app import celery_app
from app.services.ocr_service import OCRService
from app.schemas.ocr import (
    OCRRequest,
    OCRResponse,
    OCRValidationRequest,
    OCRValidationResponse,
    MIN_CONFIDENCE_SCORE
)

# Configure logging with structured format
logger = logging.getLogger(__name__)

# Prometheus metrics
OCR_PROCESSING_TIME = Histogram(
    'ocr_processing_seconds',
    'Time spent processing OCR requests',
    ['status']
)
OCR_REQUESTS_TOTAL = Counter(
    'ocr_requests_total',
    'Total number of OCR requests',
    ['status']
)
OCR_CONFIDENCE_SCORE = Histogram(
    'ocr_confidence_score',
    'OCR confidence scores distribution',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)

def log_task_event(event_type: str, task_id: str, details: Dict[str, Any]) -> None:
    """Helper function for structured logging of task events"""
    log_data = {
        "event": event_type,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        **details
    }
    logger.info(json.dumps(log_data))

class OCRTask(Task):
    """Enhanced base task class for OCR operations with automatic resource management."""
    
    _ocr_service: Optional[OCRService] = None
    
    @property
    def ocr_service(self) -> OCRService:
        """Lazy initialization of OCR service."""
        if self._ocr_service is None:
            self._ocr_service = OCRService()
        return self._ocr_service

@celery_app.task(
    name='ocr_tasks.process_contract_ocr',
    queue='ocr_tasks',
    bind=True,
    base=OCRTask,
    max_retries=3,
    soft_time_limit=300,
    acks_late=True
)
async def process_contract_ocr(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task for asynchronous OCR processing of contract documents with enhanced
    monitoring and error handling.
    
    Args:
        request: OCR processing request dictionary
        
    Returns:
        Dict[str, Any]: OCR processing results with extracted text and metrics
        
    Raises:
        OCRProcessingException: If processing fails after retries
    """
    start_time = time.time()
    processing_status = "success"
    
    try:
        # Validate and prepare request
        ocr_request = OCRRequest(**request)
        
        log_task_event("ocr_processing_started", self.request.id, {
            "contract_id": str(ocr_request.contract_id)
        })
        
        # Process document with OCR service
        response = await self.ocr_service.process_document(ocr_request)
        
        # Record metrics
        processing_time = time.time() - start_time
        OCR_PROCESSING_TIME.labels(status="success").observe(processing_time)
        OCR_REQUESTS_TOTAL.labels(status="success").inc()
        OCR_CONFIDENCE_SCORE.observe(response.confidence_score)
        
        # Add performance metrics
        response_dict = response.dict()
        response_dict["performance_metrics"].update({
            "processing_time": processing_time,
            "queue_time": start_time - request.get("enqueued_at", start_time),
            "total_time": time.time() - request.get("enqueued_at", start_time)
        })
        
        log_task_event("ocr_processing_completed", self.request.id, {
            "contract_id": str(ocr_request.contract_id),
            "confidence_score": response.confidence_score,
            "processing_time": processing_time
        })
        
        return response_dict
        
    except Exception as e:
        processing_status = "error"
        log_task_event("ocr_processing_failed", self.request.id, {
            "contract_id": request.get("contract_id"),
            "error": str(e)
        })
        
        # Record error metrics
        OCR_PROCESSING_TIME.labels(status="error").observe(time.time() - start_time)
        OCR_REQUESTS_TOTAL.labels(status="error").inc()
        
        # Implement exponential backoff retry
        retry_count = self.request.retries
        max_retries = self.max_retries
        
        if retry_count < max_retries:
            # Calculate backoff delay: 2^retry_count seconds
            backoff_delay = 2 ** retry_count
            logger.info(
                f"Retrying OCR processing in {backoff_delay} seconds "
                f"(attempt {retry_count + 1}/{max_retries + 1})"
            )
            raise self.retry(exc=e, countdown=backoff_delay)
        
        # If all retries exhausted, return error response
        return {
            "status": "FAILED",
            "contract_id": request.get("contract_id"),
            "error_details": {
                "message": str(e),
                "type": e.__class__.__name__
            },
            "processing_time": time.time() - start_time
        }

@celery_app.task(
    name='ocr_tasks.validate_ocr_data',
    queue='ocr_tasks',
    bind=True,
    base=OCRTask,
    max_retries=2,
    soft_time_limit=180,
    acks_late=True
)
async def validate_ocr_data(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task for validating and processing corrected OCR data with quality assurance.
    
    Args:
        request: Validation request dictionary
        
    Returns:
        Dict[str, Any]: Validation results with quality metrics
        
    Raises:
        ValidationException: If validation fails after retries
    """
    start_time = time.time()
    validation_status = "success"
    
    try:
        # Validate and prepare request
        validation_request = OCRValidationRequest(**request)
        
        log_task_event("ocr_validation_started", self.request.id, {
            "contract_id": str(validation_request.contract_id)
        })
        
        # Validate extracted data
        response = await self.ocr_service.validate_extracted_data(validation_request)
        
        # Record validation metrics
        validation_time = time.time() - start_time
        OCR_PROCESSING_TIME.labels(status="validation").observe(validation_time)
        OCR_REQUESTS_TOTAL.labels(status="validation").inc()
        
        # Add validation metrics
        response_dict = response.dict()
        response_dict["validation_metadata"].update({
            "validation_time": validation_time,
            "validation_timestamp": datetime.utcnow().isoformat()
        })
        
        log_task_event("ocr_validation_completed", self.request.id, {
            "contract_id": str(validation_request.contract_id),
            "validation_time": validation_time
        })
        
        return response_dict
        
    except Exception as e:
        validation_status = "error"
        log_task_event("ocr_validation_failed", self.request.id, {
            "contract_id": request.get("contract_id"),
            "error": str(e)
        })
        
        # Record error metrics
        OCR_PROCESSING_TIME.labels(status="validation_error").observe(time.time() - start_time)
        OCR_REQUESTS_TOTAL.labels(status="validation_error").inc()
        
        # Implement retry logic
        if self.request.retries < self.max_retries:
            backoff_delay = 2 ** self.request.retries
            raise self.retry(exc=e, countdown=backoff_delay)
        
        # Return error response if retries exhausted
        return {
            "status": "VALIDATION_FAILED",
            "contract_id": request.get("contract_id"),
            "error_details": {
                "message": str(e),
                "type": e.__class__.__name__
            },
            "validation_time": time.time() - start_time
        }

@celery_app.task(
    name='ocr_tasks.bulk_process_contracts',
    queue='ocr_tasks',
    bind=True,
    base=OCRTask,
    max_retries=3,
    soft_time_limit=600,  # 10 minutes
    acks_late=True
)
async def bulk_process_contracts(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process multiple contracts in bulk using OCR.
    
    Args:
        requests: List of OCR processing requests
        
    Returns:
        List[Dict[str, Any]]: List of OCR processing results
    """
    start_time = time.time()
    results = []
    
    try:
        log_task_event("bulk_process_started", self.request.id, {
            "batch_size": len(requests)
        })
        
        for request in requests:
            try:
                result = await process_contract_ocr.delay(request)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process contract: {str(e)}")
                results.append({
                    "error": str(e),
                    "status": "failed",
                    "request": request
                })
        
        processing_time = time.time() - start_time
        OCR_PROCESSING_TIME.labels(status="success").observe(processing_time)
        
        log_task_event("bulk_process_completed", self.request.id, {
            "processing_time": processing_time,
            "successful": len([r for r in results if not r.get("error")]),
            "failed": len([r for r in results if r.get("error")])
        })
        
        return results
        
    except Exception as e:
        processing_time = time.time() - start_time
        OCR_PROCESSING_TIME.labels(status="error").observe(processing_time)
        
        log_task_event("bulk_process_failed", self.request.id, {
            "error": str(e),
            "processing_time": processing_time
        })
        
        raise