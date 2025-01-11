"""
FastAPI router endpoints for contract management implementing secure, high-performance
contract processing with comprehensive error handling, audit logging, and performance monitoring.

Version: 1.0
"""

# External imports - versions specified for production stability
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status  # v0.95.0
from typing import List, Dict, Optional
import asyncio
from datetime import datetime
import logging
import uuid

# Internal imports
from app.services.contract_service import ContractService
from app.core.logging import AuditLogger
from app.core.security import RequiresRole
from app.models.contract import Contract
from app.schemas.contract import (
    ContractResponse,
    BatchUploadResponse,
    ContractValidationRequest,
    ContractValidationResponse,
    ContractUpdateRequest
)
from app.core.exceptions import OCRProcessingException, ValidationException
from app.core.dependencies import get_contract_service

# Initialize router with prefix and tags
router = APIRouter(tags=['contracts'])

# Initialize audit logger
audit_logger = AuditLogger()

# Configure logging
logger = logging.getLogger(__name__)

# Handler for both paths (with and without trailing slash)
@router.get("")  # No trailing slash
@router.get("/")  # With trailing slash
async def get_contracts(
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    contract_service: ContractService = Depends(get_contract_service)
) -> List[ContractResponse]:
    """Get all contracts with enhanced filtering and pagination."""
    contracts = await contract_service.get_contracts(current_user['id'])
    return contracts

@router.post("")  # No trailing slash
@router.post("/")  # With trailing slash
async def upload_contract(
    file: UploadFile = File(...),
    metadata: Optional[Dict] = None,
    background_tasks: BackgroundTasks = None,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    contract_service: ContractService = Depends(get_contract_service)
) -> ContractResponse:
    """
    Enhanced endpoint for uploading and processing a single contract document.
    Implements comprehensive validation, security checks, and performance monitoring.

    Args:
        file: Contract document file
        metadata: Optional contract metadata
        background_tasks: FastAPI background tasks handler
        current_user: Current authenticated user with role validation
        contract_service: Contract service instance

    Returns:
        ContractResponse: Processed contract details with status

    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        # Start performance monitoring
        start_time = datetime.utcnow()

        # Validate file size and type
        if file.size > 25 * 1024 * 1024:  # 25MB limit
            raise ValidationException("File size exceeds maximum limit of 25MB")

        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ['pdf', 'docx', 'png', 'jpg', 'jpeg']:
            raise ValidationException(f"Unsupported file type: {file_extension}")

        # Generate tracking ID
        tracking_id = str(uuid.uuid4())

        # Log upload initiation
        await audit_logger.log_operation(
            entity_type="contract",
            action="upload_initiated",
            user_id=current_user['id'],
            details={
                'tracking_id': tracking_id,
                'filename': file.filename,
                'file_size': file.size
            }
        )

        # Process contract
        file_contents = await file.read()  # Read the file contents
        await file.seek(0)  # Reset the file pointer for potential future reads
        
        contract = await contract_service.upload_contract(
            file_data=file_contents,  # Pass the actual file contents
            filename=file.filename,    # Pass the original filename
            metadata=metadata or {},
            user_id=current_user['id'],
            security_context={
                'user_id': current_user['id'],
                'role': current_user['role'],
                'tracking_id': tracking_id
            }
        )

        # Schedule background OCR processing
        if background_tasks and contract_service._ocr_service:
            background_tasks.add_task(
                contract_service.process_contract,
                contract_id=str(contract._id),
                user_id=current_user['id']
            )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Log successful upload
        await audit_logger.log_operation(
            entity_type="contract",
            action="upload_completed",
            user_id=current_user['id'],
            details={
                'tracking_id': tracking_id,
                'contract_id': str(contract._id),
                'processing_time': processing_time,
                'ocr_scheduled': bool(background_tasks and contract_service._ocr_service)
            }
        )

        return ContractResponse(
            id=str(contract._id),
            file_path=contract.file_path,
            status=contract.status,
            metadata=contract.metadata,
            created_by=contract.created_by,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
            extracted_data=contract.extracted_data,
            validation_notes=contract.validation_notes,
            error_details=contract.error_details,
            po_numbers=contract.po_numbers,
            tracking_id=tracking_id,
            processing_time=processing_time
        )

    except ValidationException as e:
        logger.warning(f"Contract validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except OCRProcessingException as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Contract upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during contract processing"
        )

@router.post(
    '/batch',
    response_model=BatchUploadResponse,
    description="Upload and process multiple contracts with parallel processing and progress tracking"
)
async def batch_upload_contracts(
    files: List[UploadFile] = File(...),
    metadata_list: Optional[List[Dict]] = None,
    background_tasks: BackgroundTasks = None,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    contract_service: ContractService = Depends(get_contract_service)
) -> BatchUploadResponse:
    """
    Enhanced endpoint for batch contract upload and processing.
    Implements parallel processing, progress tracking, and partial failure handling.

    Args:
        files: List of contract document files
        metadata_list: Optional list of metadata for each contract
        background_tasks: FastAPI background tasks handler
        current_user: Current authenticated user with role validation
        contract_service: Contract service instance

    Returns:
        BatchUploadResponse: Batch processing results with individual statuses

    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        # Validate batch size
        if len(files) > 50:  # Maximum 50 files per batch
            raise ValidationException("Batch size exceeds maximum limit of 50 files")

        # Generate batch tracking ID
        batch_id = str(uuid.uuid4())

        # Log batch processing initiation
        await audit_logger.log_operation(
            entity_type="contract_batch",
            action="batch_upload_initiated",
            user_id=current_user['id'],
            details={
                'batch_id': batch_id,
                'file_count': len(files)
            }
        )

        # Process contracts in parallel
        tasks = []
        for idx, file in enumerate(files):
            metadata = metadata_list[idx] if metadata_list and idx < len(metadata_list) else {}
            task = asyncio.create_task(
                contract_service.upload_contract(
                    file_path=file.file,
                    metadata=metadata,
                    user_id=current_user['id'],
                    security_context={
                        'user_id': current_user['id'],
                        'role': current_user['role'],
                        'batch_id': batch_id
                    }
                )
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = []
        for completed in asyncio.as_completed(tasks):
            try:
                contract = await completed
                results.append({
                    'status': 'success',
                    'contract_id': str(contract._id),
                    'file_path': contract.file_path
                })
            except Exception as e:
                results.append({
                    'status': 'error',
                    'error': str(e)
                })

        # Schedule background processing for successful uploads
        if background_tasks:
            for result in results:
                if result['status'] == 'success':
                    background_tasks.add_task(
                        contract_service.process_contract,
                        contract_id=result['contract_id'],
                        user_id=current_user['id']
                    )

        # Log batch completion
        await audit_logger.log_operation(
            entity_type="contract_batch",
            action="batch_upload_completed",
            user_id=current_user['id'],
            details={
                'batch_id': batch_id,
                'total_files': len(files),
                'successful': len([r for r in results if r['status'] == 'success']),
                'failed': len([r for r in results if r['status'] == 'error'])
            }
        )

        return BatchUploadResponse(
            successful_uploads=[r for r in results if r['status'] == 'success'],
            failed_uploads=[r for r in results if r['status'] == 'error'],
            total_count=len(files),
            success_count=len([r for r in results if r['status'] == 'success']),
            batch_id=batch_id,
            processing_time=(datetime.utcnow() - start_time).total_seconds()
        )

    except ValidationException as e:
        logger.warning(f"Batch validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during batch processing"
        )

@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    contract_service: ContractService = Depends(get_contract_service)
) -> ContractResponse:
    """Get a specific contract by ID."""
    try:
        contract = await contract_service.get_contract(contract_id, current_user['id'])
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract with ID {contract_id} not found"
            )
        return contract
    except Exception as e:
        logger.error(f"Error retrieving contract {contract_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving contract"
        )

@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    contract_data: ContractUpdateRequest,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    contract_service: ContractService = Depends(get_contract_service)
) -> ContractResponse:
    """
    Update a contract's data.
    
    Args:
        contract_id: ID of the contract to update
        contract_data: Contract update data
        current_user: Current authenticated user with role validation
        contract_service: Contract service instance
        
    Returns:
        ContractResponse: Updated contract details
        
    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        print(contract_data)
        # Update contract with validation data
        await contract_service.update_contract_validation(
            contract_id=contract_id,
            validation_data=contract_data.dict(),
            user_id=current_user['id']
        )
        
        # Get the updated contract with full data
        updated_contract = await contract_service.get_contract(contract_id, current_user['id'])
        
        if not updated_contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )
            
        # Convert contract data to response model
        return ContractResponse(
            id=contract_id,
            file_path=updated_contract.file_path,
            status=updated_contract.status,
            metadata=updated_contract.metadata,
            created_by=updated_contract.created_by,
            created_at=updated_contract.created_at,
            updated_at=updated_contract.updated_at,
            extracted_data=updated_contract.extracted_data,
            validation_notes=updated_contract.validation_notes,
            error_details=updated_contract.error_details,
            po_numbers=updated_contract.po_numbers
        )
        
    except ValidationException as e:
        logger.warning(f"Contract update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Contract update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during contract update"
        )

# Export router
__all__ = ['router']