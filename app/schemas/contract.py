"""
Contract schema models for data validation and serialization.
Implements comprehensive validation rules, security checks, and data transformation logic
for the contract processing system.

Version: 1.0.0
"""

# External imports with versions
from pydantic import BaseModel, Field, constr  # v1.10.0
from pydantic import UUID4, Json  # v1.10.0
from datetime import datetime
from typing import Optional, List, Dict, Any

# Internal imports
from app.models.contract import CONTRACT_STATUS_CHOICES, FILE_TYPES_ALLOWED

class ContractBase(BaseModel):
    """
    Base Pydantic model for contract data validation with comprehensive validation rules
    and security checks.
    """
    id: str = Field(
        ...,
        description="Unique identifier for the contract",
        example="507f1f77bcf86cd799439011"
    )
    
    file_path: str = Field(
        ...,
        description="File path for contract document",
        example="contracts/2023/contract-123.pdf"
    )
    
    status: str = Field(
        ...,
        description="Current status of the contract",
        example="UPLOADED"
    )
    
    metadata: dict = Field(
        default={},
        description="Contract metadata and additional information",
        example={
            "contract_type": "purchase",
            "department": "procurement",
            "priority": "high"
        }
    )
    
    created_by: str = Field(
        ...,
        description="ID of user who created the contract",
        example="507f1f77bcf86cd799439011"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of contract creation"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of last update"
    )
    
    extracted_data: Optional[dict] = Field(
        None,
        description="Data extracted from contract via OCR",
        example={
            "vendor_name": "Acme Corp",
            "total_amount": 15000.00,
            "delivery_date": "2023-12-31"
        }
    )
    
    validation_notes: Optional[dict] = Field(
        None,
        description="Notes from manual validation process",
        example={
            "reviewed_by": "John Doe",
            "review_date": "2023-06-15",
            "comments": "All terms verified"
        }
    )
    
    error_details: Optional[dict] = Field(
        None,
        description="Error details if processing failed",
        example={
            "error_type": "OCR_FAILED",
            "message": "OCR processing failed: poor image quality",
            "timestamp": "2023-06-15T10:00:00Z"
        }
    )
    
    po_numbers: List[str] = Field(
        default=[],
        description="List of generated PO numbers",
        example=["PO-2023-001", "PO-2023-002"]
    )

    class Config:
        """Pydantic model configuration"""
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "file_path": "contracts/2023/contract-123.pdf",
                "status": "UPLOADED",
                "metadata": {
                    "contract_type": "purchase",
                    "department": "procurement",
                    "priority": "high"
                },
                "created_by": "507f1f77bcf86cd799439011",
                "created_at": "2023-06-15T10:00:00Z",
                "updated_at": "2023-06-15T10:00:00Z"
            }
        }

    @classmethod
    def validate_status(cls, status: str, previous_status: Optional[str] = None) -> bool:
        """
        Validates contract status against allowed values with transition rules.
        
        Args:
            status: New status to validate
            previous_status: Optional previous status for transition validation
            
        Returns:
            bool: True if status transition is valid
        """
        if status not in CONTRACT_STATUS_CHOICES:
            return False
            
        # Define valid status transitions
        valid_transitions = {
            "UPLOADED": ["PROCESSING"],
            "PROCESSING": ["VALIDATION_REQUIRED", "FAILED"],
            "VALIDATION_REQUIRED": ["VALIDATED", "FAILED"],
            "VALIDATED": ["COMPLETED"],
            "FAILED": ["PROCESSING"],
            "COMPLETED": []
        }
        
        if previous_status and status not in valid_transitions[previous_status]:
            return False
            
        return True

    @classmethod
    def validate_file_type(cls, file_path: str) -> bool:
        """
        Validates file type against allowed formats with security checks.
        
        Args:
            file_path: File path to validate
            
        Returns:
            bool: True if file type is allowed
        """
        try:
            extension = file_path.split('.')[-1].lower()
            return extension in FILE_TYPES_ALLOWED
        except Exception:
            return False

class ContractCreate(BaseModel):
    """
    Schema for contract creation request with enhanced validation.
    """
    file_path: constr(regex='^[a-zA-Z0-9/_-]+$', min_length=1, max_length=255) = Field(
        ...,
        description="Secure file path for contract document"
    )
    
    metadata: dict = Field(
        default={},
        description="Contract metadata and additional information"
    )
    
    created_by: UUID4 = Field(
        ...,
        description="ID of user creating the contract"
    )

    @classmethod
    def validate_metadata(cls, metadata: dict) -> bool:
        """
        Validates metadata structure and content.
        
        Args:
            metadata: Metadata dictionary to validate
            
        Returns:
            bool: True if metadata is valid
        """
        required_fields = {'contract_type', 'department'}
        if not all(field in metadata for field in required_fields):
            return False
            
        # Validate metadata field types
        if not isinstance(metadata.get('contract_type'), str):
            return False
        if not isinstance(metadata.get('department'), str):
            return False
            
        # Validate metadata size
        if len(str(metadata)) > 10000:  # 10KB limit
            return False
            
        return True

class ContractUpdate(BaseModel):
    """
    Schema for contract update request with partial update support.
    """
    status: Optional[str] = Field(
        None,
        description="Updated contract status"
    )
    
    metadata: Optional[dict] = Field(
        None,
        description="Updated contract metadata"
    )
    
    extracted_data: Optional[dict] = Field(
        None,
        description="Updated extracted data"
    )
    
    validation_notes: Optional[dict] = Field(
        None,
        description="Updated validation notes"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if processing failed"
    )

    @classmethod
    def validate_update(cls, update_data: dict, existing_contract: 'ContractBase') -> bool:
        """Validate contract update data against business rules."""
        if 'status' in update_data:
            if not ContractBase.validate_status(
                update_data['status'],
                existing_contract.status
            ):
                return False
        return True

class ContractUpdateRequest(BaseModel):
    """
    Schema for contract update request from frontend.
    """
    extracted_data: Optional[Dict[str, Any]] = Field(
        default={},
        description="Updated extracted data from the contract",
        example={
            "vendor_name": "Acme Corporation",
            "total_amount": 15000.00,
            "delivery_date": "2023-12-31"
        }
    )
    
    validation_notes: Optional[Dict[str, Any]] = Field(
        default={},
        description="Notes from the validation process",
        example={
            "comments": "All terms verified",
            "confidence_level": 0.95
        }
    )

    status: Optional[str] = Field(
        None,
        description="Updated contract status"
    )

    class Config:
        """Request model configuration"""
        schema_extra = {
            "example": {
                "extracted_data": {
                    "vendor_name": "Acme Corporation",
                    "total_amount": 15000.00,
                    "delivery_date": "2023-12-31"
                },
                "validation_notes": {
                    "comments": "All terms verified",
                    "confidence_level": 0.95
                },
                "is_validated": False
            }
        }

class ContractResponse(ContractBase):
    """
    Schema for contract response data with secure serialization.
    """
    
    @classmethod
    def from_orm(cls, db_contract: 'Contract') -> 'ContractResponse':
        """
        Creates response model from ORM model with secure data handling.
        
        Args:
            db_contract: Database contract model
            
        Returns:
            ContractResponse: Secure API response model
        """
        # Convert ORM model to dictionary
        contract_dict = {
            'id': str(db_contract._id),
            'file_path': db_contract.file_path,
            'status': db_contract.status,
            'metadata': db_contract.metadata,
            'created_by': db_contract.created_by,
            'created_at': db_contract.created_at,
            'updated_at': db_contract.updated_at,
            'extracted_data': db_contract.extracted_data,
            'validation_notes': db_contract.validation_notes,
            'error_details': db_contract.error_details,
            'po_numbers': db_contract.po_numbers
        }
        
        # Create and return response model
        return cls(**contract_dict)

    class Config:
        """Response model configuration"""
        orm_mode = True

class BatchUploadResponse(BaseModel):
    """Schema for batch contract upload response."""
    
    successful_uploads: List[ContractResponse] = Field(
        default=[],
        description="List of successfully uploaded contracts"
    )
    
    failed_uploads: List[Dict[str, Any]] = Field(
        default=[],
        description="List of failed uploads with error details",
        example=[
            {
                "file_name": "contract1.pdf",
                "error": "Invalid file format"
            }
        ]
    )
    
    total_count: int = Field(
        ...,
        description="Total number of files in batch",
        example=5
    )
    
    success_count: int = Field(
        ...,
        description="Number of successful uploads",
        example=3
    )
    
    batch_id: UUID4 = Field(
        ...,
        description="Unique identifier for the batch upload",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    
    processing_time: float = Field(
        ...,
        description="Total processing time in seconds",
        example=2.5
    )
    
    class Config:
        """Response model configuration"""
        schema_extra = {
            "example": {
                "successful_uploads": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "file_path": "contracts/2023/contract-123.pdf",
                        "status": "UPLOADED",
                        "metadata": {
                            "contract_type": "purchase",
                            "department": "procurement"
                        }
                    }
                ],
                "failed_uploads": [
                    {
                        "file_name": "contract1.pdf",
                        "error": "Invalid file format"
                    }
                ],
                "total_count": 5,
                "success_count": 3,
                "batch_id": "123e4567-e89b-12d3-a456-426614174000",
                "processing_time": 2.5
            }
        }

class ContractValidationRequest(BaseModel):
    """Schema for contract validation request."""
    
    corrected_data: Dict[str, Any] = Field(
        ...,
        description="Corrected contract data",
        example={
            "vendor_name": "Acme Corporation",
            "total_amount": 15000.00,
            "delivery_date": "2023-12-31"
        }
    )
    
    validation_notes: Optional[Dict[str, Any]] = Field(
        None,
        description="Notes from the validation process",
        example={
            "reviewer": "John Doe",
            "comments": "Vendor name corrected"
        }
    )

class ContractValidationResponse(BaseModel):
    """Schema for contract validation response."""
    
    contract_id: UUID4 = Field(
        ...,
        description="ID of the validated contract",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    
    status: str = Field(
        ...,
        description="Validation status",
        example="VALIDATED"
    )
    
    validated_data: Dict[str, Any] = Field(
        ...,
        description="Final validated contract data",
        example={
            "vendor_name": "Acme Corporation",
            "total_amount": 15000.00,
            "delivery_date": "2023-12-31"
        }
    )
    
    validation_metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata about the validation process",
        example={
            "validation_timestamp": "2023-06-15T10:00:00Z",
            "validation_confidence": 0.95,
            "changes_made": ["vendor_name"]
        }
    )
    
    class Config:
        """Response model configuration"""
        schema_extra = {
            "example": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "VALIDATED",
                "validated_data": {
                    "vendor_name": "Acme Corporation",
                    "total_amount": 15000.00,
                    "delivery_date": "2023-12-31"
                },
                "validation_metadata": {
                    "validation_timestamp": "2023-06-15T10:00:00Z",
                    "validation_confidence": 0.95,
                    "changes_made": ["vendor_name"]
                }
            }
        }