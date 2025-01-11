"""
Enhanced FastAPI router for OCR (Optical Character Recognition) operations.
Implements high-accuracy document processing with comprehensive monitoring,
validation workflows, and error handling.

Version: 1.0
"""

# External imports with versions
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks  # fastapi v0.95+
from prometheus_client import Counter, Histogram, CollectorRegistry  # prometheus_client v0.16+
import structlog  # structlog v23.1.0
import logging  # built-in
from typing import Dict, Any
from datetime import datetime
import uuid

# Internal imports
from app.schemas.ocr import (
    OCRRequest,
    OCRResponse,
    OCRValidationRequest,
    OCRValidationResponse
)
from app.tasks.ocr_tasks import process_contract_ocr, validate_ocr_data
from app.services.ocr_service import OCRService

# Initialize router with prefix and tags
router = APIRouter(prefix='/ocr', tags=['OCR'])

# Configure structured logging
logger = structlog.get_logger(__name__)

# Constants for rate limiting and validation
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 3600  # 1 hour
OCR_CONFIDENCE_THRESHOLD = 0.95

# Create custom registry for OCR metrics
ocr_registry = CollectorRegistry()

# Prometheus metrics
OCR_REQUESTS = Counter(
    'ocr_requests_total',
    'Total number of OCR requests',
    ['endpoint', 'status'],
    registry=ocr_registry
)

OCR_PROCESSING_TIME = Histogram(
    'ocr_processing_duration_seconds',
    'Time spent processing OCR requests',
    ['endpoint'],
    registry=ocr_registry
)

OCR_CONFIDENCE_SCORES = Histogram(
    'ocr_confidence_scores',
    'Distribution of OCR confidence scores',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)

@router.post(
    '/process',
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    description="Process document using OCR with high accuracy requirements"
)
async def process_document(
    request: OCRRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Enhanced endpoint for initiating OCR processing with comprehensive monitoring
    and validation workflows.
    
    Args:
        request: OCR processing request
        background_tasks: FastAPI background tasks handler
        
    Returns:
        Dict containing task ID and processing status
        
    Raises:
        HTTPException: If request validation fails or rate limit exceeded
    """
    try:
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Received OCR processing request",
            correlation_id=correlation_id,
            contract_id=str(request.contract_id)
        )

        # Record request metric
        OCR_REQUESTS.labels(endpoint='process', status='received').inc()

        # Validate file path and format
        if not request.file_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File path is required"
            )

        # Prepare task data with enhanced context
        task_data = {
            "contract_id": str(request.contract_id),
            "file_path": request.file_path,
            "correlation_id": correlation_id,
            "confidence_threshold": OCR_CONFIDENCE_THRESHOLD,
            "enqueued_at": datetime.utcnow().isoformat(),
            "processing_options": request.processing_options
        }

        # Add OCR processing task to background tasks
        background_tasks.add_task(
            process_contract_ocr.delay,
            task_data
        )

        logger.info(
            "OCR processing task created",
            correlation_id=correlation_id,
            contract_id=str(request.contract_id)
        )

        return {
            "status": "accepted",
            "task_id": correlation_id,
            "message": "OCR processing initiated",
            "estimated_time": "5 seconds"
        }

    except HTTPException as he:
        OCR_REQUESTS.labels(endpoint='process', status='error').inc()
        logger.error(
            "OCR processing request failed",
            correlation_id=correlation_id,
            error=str(he),
            status_code=he.status_code
        )
        raise

    except Exception as e:
        OCR_REQUESTS.labels(endpoint='process', status='error').inc()
        logger.error(
            "Unexpected error during OCR processing",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during OCR processing"
        )

@router.post(
    '/validate',
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    description="Validate OCR extracted data with confidence scoring"
)
async def validate_extracted_data(
    request: OCRValidationRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Enhanced endpoint for validating OCR data with comprehensive confidence scoring
    and quality assurance.
    
    Args:
        request: Validation request
        background_tasks: FastAPI background tasks handler
        
    Returns:
        Dict containing validation task ID and status
        
    Raises:
        HTTPException: If validation request is invalid
    """
    try:
        # Generate correlation ID for validation tracking
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Received OCR validation request",
            correlation_id=correlation_id,
            contract_id=str(request.contract_id)
        )

        # Record validation request metric
        OCR_REQUESTS.labels(endpoint='validate', status='received').inc()

        # Prepare validation task data
        validation_data = {
            "contract_id": str(request.contract_id),
            "corrected_data": request.corrected_data,
            "correlation_id": correlation_id,
            "validation_notes": request.validation_notes,
            "enqueued_at": datetime.utcnow().isoformat()
        }

        # Add validation task to background tasks
        background_tasks.add_task(
            validate_ocr_data.delay,
            validation_data
        )

        logger.info(
            "OCR validation task created",
            correlation_id=correlation_id,
            contract_id=str(request.contract_id)
        )

        return {
            "status": "accepted",
            "task_id": correlation_id,
            "message": "Validation process initiated"
        }

    except HTTPException as he:
        OCR_REQUESTS.labels(endpoint='validate', status='error').inc()
        logger.error(
            "OCR validation request failed",
            correlation_id=correlation_id,
            error=str(he),
            status_code=he.status_code
        )
        raise

    except Exception as e:
        OCR_REQUESTS.labels(endpoint='validate', status='error').inc()
        logger.error(
            "Unexpected error during OCR validation",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during validation"
        )

@router.get(
    '/status/{task_id}',
    response_model=Dict[str, Any],
    description="Get detailed OCR processing status with metrics"
)
async def get_processing_status(
    task_id: str,
    correlation_id: str
) -> Dict[str, Any]:
    """
    Enhanced status checking endpoint with detailed progress tracking and
    performance metrics.
    
    Args:
        task_id: Task identifier
        correlation_id: Request correlation ID
        
    Returns:
        Dict containing detailed task status and metrics
        
    Raises:
        HTTPException: If task is not found or status check fails
    """
    try:
        logger.info(
            "Checking OCR task status",
            task_id=task_id,
            correlation_id=correlation_id
        )

        # Record status check metric
        OCR_REQUESTS.labels(endpoint='status', status='received').inc()

        # Get task result from Celery
        task = process_contract_ocr.AsyncResult(task_id)
        
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Prepare status response with metrics
        response = {
            "task_id": task_id,
            "status": task.status,
            "progress": task.info.get('progress', 0) if task.info else 0,
            "result": task.result if task.ready() else None,
            "error": str(task.result) if task.failed() else None,
            "metrics": {
                "processing_time": task.info.get('processing_time') if task.info else None,
                "confidence_score": task.info.get('confidence_score') if task.info else None,
                "queue_time": task.info.get('queue_time') if task.info else None
            }
        }

        logger.info(
            "OCR task status retrieved",
            task_id=task_id,
            correlation_id=correlation_id,
            status=response['status']
        )

        return response

    except HTTPException as he:
        OCR_REQUESTS.labels(endpoint='status', status='error').inc()
        logger.error(
            "Failed to retrieve task status",
            task_id=task_id,
            correlation_id=correlation_id,
            error=str(he),
            status_code=he.status_code
        )
        raise

    except Exception as e:
        OCR_REQUESTS.labels(endpoint='status', status='error').inc()
        logger.error(
            "Unexpected error checking task status",
            task_id=task_id,
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error checking task status"
        )