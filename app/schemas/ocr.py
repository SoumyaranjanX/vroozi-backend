"""
Enhanced Pydantic schema models for OCR data validation and serialization.
Implements comprehensive validation rules, performance tracking, and data structures
for the OCR processing workflow with support for manual corrections and error handling.

Version: 1.0
"""

# External imports with versions
from pydantic import BaseModel, Field, UUID4, Json  # pydantic v1.10.0
from typing import Optional, Dict, List
from enum import Enum

# Internal imports
from app.models.contract import CONTRACT_STATUS_CHOICES

# Constants for OCR validation
SUPPORTED_FILE_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
MIN_CONFIDENCE_SCORE = 0.95  # 95% minimum confidence requirement
MAX_PROCESSING_TIME = 5.0  # 5 seconds maximum processing time
MAX_BATCH_SIZE = 100  # Maximum number of documents in batch processing

class OCRStatus(str, Enum):
    """
    Enumeration of possible OCR processing statuses.
    """
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"

class OCRRequest(BaseModel):
    """
    Enhanced schema for OCR processing request validation with support for 
    processing options and security checks.
    """
    contract_id: UUID4 = Field(
        ...,
        description="Unique identifier for the contract document"
    )
    file_path: str = Field(
        ...,
        description="Path to the document file in storage",
        min_length=1,
        max_length=512
    )
    processing_options: Optional[Dict] = Field(
        default={},
        description="Optional OCR processing configuration parameters"
    )
    batch_processing: Optional[bool] = Field(
        default=False,
        description="Flag indicating if request is part of batch processing"
    )
    security_context: Optional[Dict] = Field(
        default={},
        description="Security context for access control and audit tracking"
    )

    class Config:
        """Configuration for the OCRRequest model"""
        schema_extra = {
            "example": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "contracts/2023/contract_123.pdf",
                "processing_options": {
                    "language": "en",
                    "enhance_resolution": True,
                    "detect_orientation": True
                },
                "batch_processing": False,
                "security_context": {
                    "user_id": "user123",
                    "access_level": "contract_manager"
                }
            }
        }

    def validate_file_path(self, file_path: str) -> bool:
        """
        Enhanced file path validation with security checks.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            bool: True if file type is supported and passes security checks
            
        Raises:
            ValueError: If file validation fails
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Extract and validate file extension
        file_extension = file_path.split('.')[-1].lower()
        if file_extension not in SUPPORTED_FILE_TYPES:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Basic path traversal prevention
        if '..' in file_path or '//' in file_path:
            raise ValueError("Invalid file path detected")

        return True

class BatchOCRRequest(BaseModel):
    """
    Enhanced schema for batch OCR processing requests.
    Supports processing multiple documents in a single request with shared configuration.
    """
    requests: List[OCRRequest] = Field(
        ...,
        description="List of OCR requests to process in batch",
        max_items=MAX_BATCH_SIZE
    )
    batch_id: UUID4 = Field(
        ...,
        description="Unique identifier for the batch request"
    )
    shared_processing_options: Optional[Dict] = Field(
        default={},
        description="Processing options applied to all requests in the batch"
    )
    priority: Optional[int] = Field(
        default=0,
        description="Processing priority for the batch (0-10)",
        ge=0,
        le=10
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="URL for batch completion callback notification"
    )
    error_handling: Optional[Dict] = Field(
        default={
            "continue_on_error": True,
            "max_retries": 3,
            "retry_delay": 5
        },
        description="Error handling configuration for the batch"
    )

    class Config:
        """Configuration for the BatchOCRRequest model"""
        schema_extra = {
            "example": {
                "batch_id": "123e4567-e89b-12d3-a456-426614174000",
                "requests": [
                    {
                        "contract_id": "123e4567-e89b-12d3-a456-426614174001",
                        "file_path": "contracts/2023/contract_123.pdf",
                        "processing_options": {"language": "en"}
                    },
                    {
                        "contract_id": "123e4567-e89b-12d3-a456-426614174002",
                        "file_path": "contracts/2023/contract_124.pdf",
                        "processing_options": {"language": "en"}
                    }
                ],
                "shared_processing_options": {
                    "enhance_resolution": True,
                    "detect_orientation": True
                },
                "priority": 5,
                "callback_url": "https://api.example.com/callbacks/ocr",
                "error_handling": {
                    "continue_on_error": True,
                    "max_retries": 3,
                    "retry_delay": 5
                }
            }
        }

    def validate_batch(self) -> bool:
        """
        Validates the entire batch request.
        
        Returns:
            bool: True if batch is valid
            
        Raises:
            ValueError: If batch validation fails
        """
        if not self.requests:
            raise ValueError("Batch must contain at least one request")
            
        if len(self.requests) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum limit of {MAX_BATCH_SIZE}")
            
        # Validate each request in the batch
        for request in self.requests:
            request.validate_file_path(request.file_path)
            
        return True

class OCRResponse(BaseModel):
    """
    Enhanced schema for OCR processing response with performance metrics 
    and error handling.
    """
    contract_id: UUID4 = Field(
        ...,
        description="Contract identifier matching the request"
    )
    status: str = Field(
        ...,
        description="Processing status of the OCR operation",
        choices=CONTRACT_STATUS_CHOICES
    )
    extracted_data: Json = Field(
        ...,
        description="Structured data extracted from the document"
    )
    confidence_score: float = Field(
        ...,
        description="Confidence score of the OCR extraction",
        ge=0.0,
        le=1.0
    )
    processing_time: float = Field(
        ...,
        description="Time taken for OCR processing in seconds",
        ge=0.0,
        le=MAX_PROCESSING_TIME
    )
    error_details: Optional[Dict] = Field(
        default=None,
        description="Details of any errors encountered during processing"
    )
    partial_results: Optional[Json] = Field(
        default=None,
        description="Partial extraction results in case of incomplete processing"
    )
    performance_metrics: Dict = Field(
        default_factory=dict,
        description="Detailed performance metrics of the OCR operation"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Non-critical warnings from the OCR process"
    )

    class Config:
        """Configuration for the OCRResponse model"""
        schema_extra = {
            "example": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "COMPLETED",
                "extracted_data": {
                    "parties": ["Company A", "Company B"],
                    "dates": {"start": "2023-01-01", "end": "2024-01-01"},
                    "values": {"total_amount": 50000.00}
                },
                "confidence_score": 0.98,
                "processing_time": 2.5,
                "performance_metrics": {
                    "cpu_usage": 45.2,
                    "memory_usage": 128.5,
                    "api_latency": 1.2
                }
            }
        }

class OCRValidationRequest(BaseModel):
    """
    Enhanced schema for OCR data validation request with change tracking.
    """
    contract_id: UUID4 = Field(
        ...,
        description="Contract identifier for validation"
    )
    corrected_data: Json = Field(
        ...,
        description="Manually corrected or validated data"
    )
    validation_notes: Optional[str] = Field(
        default=None,
        description="Notes regarding the validation process",
        max_length=1000
    )
    change_tracking: Optional[Dict] = Field(
        default_factory=dict,
        description="Tracking of changes made during validation"
    )
    validation_rules: Optional[List[str]] = Field(
        default=None,
        description="Custom validation rules to apply"
    )
    metadata: Optional[Dict] = Field(
        default_factory=dict,
        description="Additional metadata for validation context"
    )

    class Config:
        """Configuration for the OCRValidationRequest model"""
        schema_extra = {
            "example": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "corrected_data": {
                    "parties": ["Company A", "Company B"],
                    "total_amount": 50000.00
                },
                "validation_notes": "Corrected company names and amounts",
                "change_tracking": {
                    "modified_fields": ["parties", "total_amount"],
                    "timestamp": "2023-01-01T12:00:00Z"
                }
            }
        }

class OCRValidationResponse(BaseModel):
    """
    Enhanced schema for OCR validation response with detailed error reporting.
    """
    contract_id: UUID4 = Field(
        ...,
        description="Contract identifier matching the validation request"
    )
    status: str = Field(
        ...,
        description="Status of the validation process",
        choices=CONTRACT_STATUS_CHOICES
    )
    validated_data: Json = Field(
        ...,
        description="Final validated data after corrections"
    )
    validation_errors: Optional[List[Dict]] = Field(
        default=None,
        description="Details of validation errors if any"
    )
    change_history: Dict = Field(
        default_factory=dict,
        description="History of changes made during validation"
    )
    validation_metadata: Dict = Field(
        default_factory=dict,
        description="Metadata about the validation process"
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Recommendations for improving data quality"
    )

    class Config:
        """Configuration for the OCRValidationResponse model"""
        schema_extra = {
            "example": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "VALIDATED",
                "validated_data": {
                    "parties": ["Company A", "Company B"],
                    "total_amount": 50000.00
                },
                "validation_metadata": {
                    "validator_id": "user123",
                    "validation_timestamp": "2023-01-01T12:00:00Z",
                    "confidence_improvement": 0.15
                }
            }
        }

# Export public interfaces
__all__ = [
    'OCRStatus',
    'OCRRequest',
    'BatchOCRRequest',
    'OCRResponse',
    'OCRValidationRequest',
    'OCRValidationResponse',
    'SUPPORTED_FILE_TYPES',
    'MIN_CONFIDENCE_SCORE',
    'MAX_PROCESSING_TIME',
    'MAX_BATCH_SIZE'
]