"""
FastAPI router endpoints for purchase order management with comprehensive validation,
error handling, and audit logging.

Version: 1.0
"""

# External imports - versions specified for production stability
from fastapi import APIRouter, Depends, HTTPException, status  # v0.95.0
from typing import List, Dict, Optional
from datetime import datetime
import logging
from uuid import UUID

# Internal imports
from app.services.purchase_order_service import PurchaseOrderService
from app.core.logging import AuditLogger
from app.core.security import RequiresRole
from app.core.user_utils import get_current_user
from app.core.dependencies import get_po_service
from app.models.purchase_order import PurchaseOrder
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    PurchaseOrderValidationRequest,
    PurchaseOrderValidationResponse
)
from app.core.exceptions import ValidationException
from app.models.user import User

# Define allowed roles for endpoints
ALLOWED_ROLES = ['ADMIN', 'PO_MANAGER']

# Initialize router with prefix and tags
router = APIRouter(tags=['purchase-orders'])

# Initialize audit logger
audit_logger = AuditLogger()

# Configure logging
logger = logging.getLogger(__name__)

@router.post(
    '/',
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new purchase order with comprehensive validation"
)
async def create_purchase_order(
    po_data: PurchaseOrderCreate,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'PO_MANAGER'])),
    po_service: PurchaseOrderService = Depends(get_po_service)
) -> PurchaseOrderResponse:
    """
    Create a new purchase order with comprehensive validation and security checks.
    
    Args:
        po_data: Purchase order creation data
        current_user: Current authenticated user
        po_service: Purchase order service instance
        
    Returns:
        PurchaseOrderResponse: Created purchase order details
        
    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        # Start performance monitoring
        start_time = datetime.utcnow()

        # Log operation initiation
        await audit_logger.log_operation(
            entity_type="purchase_order",
            action="create_initiated",
            user_id=current_user['id'],
            details={
                'contract_id': po_data.contract_id,
                'template_type': po_data.template_type
            }
        )

        # Create purchase order
        po = await po_service.create_purchase_order(
            contract_id=po_data.contract_id,
            po_data=po_data.dict(),
            user_id=current_user['id'],
            send_notification=po_data.send_notification if hasattr(po_data, 'send_notification') else True
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Log successful creation
        await audit_logger.log_operation(
            entity_type="purchase_order",
            action="create_completed",
            user_id=current_user['id'],
            details={
                'po_id': str(po.id),
                'processing_time': processing_time
            }
        )

        # Get audit trail
        audit_trail = await po.audit_trail

        return PurchaseOrderResponse(
            id=str(po.id),
            po_number=po.po_number,
            status=po.status,
            contract_id=po.contract_id,
            generated_by=po.generated_by,
            template_type=po.template_type,
            output_format=po.output_format,
            file_path=po.file_path,
            po_data=po.po_data,
            amount=po.po_data.get('total_amount', 0),
            include_logo=po.include_logo,
            digital_signature=po.digital_signature,
            send_notification=po.send_notification,
            created_at=po.created_at,
            updated_at=po.updated_at,
            sent_at=po.sent_at,
            error_message=po.error_message,
            audit_trail=audit_trail
        )

    except ValidationException as e:
        logger.warning(f"Purchase order validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Purchase order creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during purchase order creation"
        )

@router.post(
    '/batch',
    response_model=List[PurchaseOrderResponse],
    status_code=status.HTTP_201_CREATED,
    description="Create multiple purchase orders in batch with optimized processing"
)
async def batch_create_purchase_orders(
    po_batch_data: List[PurchaseOrderCreate],
    current_user: Dict = Depends(RequiresRole(['admin', 'po_manager'])),
    po_service: PurchaseOrderService = Depends(get_po_service)
) -> List[PurchaseOrderResponse]:
    """
    Create multiple purchase orders in batch with optimized processing.
    
    Args:
        po_batch_data: List of purchase order creation data
        current_user: Current authenticated user
        po_service: Purchase order service instance
        
    Returns:
        List[PurchaseOrderResponse]: List of created purchase orders
        
    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        # Start performance monitoring
        start_time = datetime.utcnow()

        # Generate batch ID
        batch_id = str(UUID.uuid4())

        # Log batch operation initiation
        await audit_logger.log_operation(
            entity_type="purchase_order_batch",
            action="batch_create_initiated",
            user_id=current_user['id'],
            details={
                'batch_id': batch_id,
                'batch_size': len(po_batch_data)
            }
        )

        # Process batch
        results = await po_service.process_batch(
            po_data_list=[po.dict() for po in po_batch_data],
            user_id=current_user['id'],
            security_context={
                'user_id': current_user['id'],
                'role': current_user['role'],
                'batch_id': batch_id
            }
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Log batch completion
        await audit_logger.log_operation(
            entity_type="purchase_order_batch",
            action="batch_create_completed",
            user_id=current_user['id'],
            details={
                'batch_id': batch_id,
                'successful': len([r for r in results if not r.get('error')]),
                'failed': len([r for r in results if r.get('error')]),
                'processing_time': processing_time
            }
        )

        # Convert to response format
        return [
            PurchaseOrderResponse(
                id=str(po.id),
                po_number=po.po_number,
                status=po.status,
                contract_id=po.contract_id,
                generated_by=po.generated_by,
                template_type=po.template_type,
                output_format=po.output_format,
                file_path=po.file_path,
                po_data=po.po_data,
                include_logo=po.include_logo,
                digital_signature=po.digital_signature,
                send_notification=po.send_notification,
                created_at=po.created_at,
                updated_at=po.updated_at,
                sent_at=po.sent_at,
                error_message=po.error_message,
                audit_trail=po.audit_trail
            )
            for po in results if not po.get('error')
        ]

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

@router.get("/{po_number}/download",
    summary="Get PO download URL",
    description="Generate secure download URL for purchase order document"
)
async def get_po_download_link(
    po_number: str,
    current_user: User = Depends(RequiresRole(ALLOWED_ROLES)),
    po_service: PurchaseOrderService = Depends(get_po_service)
) -> Dict[str, str]:
    """
    Generates secure download URL for purchase order document.

    Args:
        po_number: Purchase order number
        current_user: Authenticated user with required role
        po_service: Purchase order service instance

    Returns:
        Dict containing download URL

    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        download_url = await po_service.get_po_download_url(po_number)
        
        logger.info(
            "po_download_url_generated",
            po_number=po_number,
            user_id=str(current_user.id)
        )
        
        return {"download_url": download_url}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "po_download_url_generation_failed",
            po_number=po_number,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )

@router.get(
    '/',
    response_model=List[PurchaseOrderResponse],
    status_code=status.HTTP_200_OK,
    description="Get list of purchase orders with optional filtering"
)
async def get_purchase_orders(
    current_user: Dict = Depends(RequiresRole(ALLOWED_ROLES)),
    po_service: PurchaseOrderService = Depends(get_po_service),
    skip: int = 0,
    limit: int = 100,
    contract_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[PurchaseOrderResponse]:
    """
    Get list of purchase orders with optional filtering.
    
    Args:
        current_user: Current authenticated user
        po_service: Purchase order service instance
        skip: Number of records to skip
        limit: Maximum number of records to return
        contract_id: Optional contract ID filter
        status_filter: Optional status filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        List[PurchaseOrderResponse]: List of purchase orders
        
    Raises:
        HTTPException: For validation or processing errors
    """
    try:
        # Build filter criteria
        filters = {}
        if contract_id:
            filters['contract_id'] = contract_id
        if status_filter:
            filters['status'] = status_filter
        if start_date:
            filters['created_at'] = {'$gte': start_date}
        if end_date:
            if 'created_at' in filters:
                filters['created_at']['$lte'] = end_date
            else:
                filters['created_at'] = {'$lte': end_date}

        # Get purchase orders
        purchase_orders = await po_service.get_purchase_orders(
            user_id=current_user['id'],
            filters=filters,
            skip=skip,
            limit=limit
        )

        return [
            PurchaseOrderResponse(
                id=str(po.id),
                po_number=po.po_number,
                status=po.status,
                contract_id=po.contract_id,
                generated_by=po.generated_by,
                template_type=po.template_type,
                output_format=po.output_format,
                file_path=po.file_path,
                po_data=po.po_data,
                amount=po.po_data.get('total_amount', 0),
                include_logo=po.include_logo,
                digital_signature=po.digital_signature,
                send_notification=po.send_notification,
                created_at=po.created_at,
                updated_at=po.updated_at,
                sent_at=po.sent_at,
                error_message=po.error_message,
                audit_trail=await po.audit_trail
            )
            for po in purchase_orders
        ]

    except Exception as e:
        logger.error(f"Error retrieving purchase orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving purchase orders"
        )

@router.post(
    '/{po_id}/send',
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    description="Send a purchase order to the recipient"
)
async def send_purchase_order(
    po_id: str,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'PO_MANAGER'])),
    po_service: PurchaseOrderService = Depends(get_po_service)
) -> PurchaseOrderResponse:
    """
    Send a purchase order to the recipient.
    
    Args:
        po_id: ID of the purchase order to send
        current_user: Current authenticated user
        po_service: Purchase order service instance
    
    Returns:
        PurchaseOrderResponse: Updated purchase order details
    
    Raises:
        HTTPException: If purchase order not found or sending fails
    """
    try:
        start_time = datetime.utcnow()

        # Send purchase order
        po = await po_service.send_purchase_order(
            po_id=po_id,
            user_id=current_user['id']
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Log successful sending
        await audit_logger.log_operation(
            entity_type="purchase_order",
            action="send_completed",
            user_id=current_user['id'],
            details={
                'po_id': po_id,
                'processing_time': processing_time
            }
        )

        # Get audit trail
        audit_trail = await po.audit_trail

        return PurchaseOrderResponse(
            id=str(po.id),
            po_number=po.po_number,
            status=po.status,
            contract_id=po.contract_id,
            generated_by=po.generated_by,
            template_type=po.template_type,
            output_format=po.output_format,
            file_path=po.file_path,
            po_data=po.po_data,
            include_logo=po.include_logo,
            digital_signature=po.digital_signature,
            send_notification=po.send_notification,
            created_at=po.created_at,
            updated_at=po.updated_at,
            sent_at=po.sent_at,
            error_message=po.error_message,
            audit_trail=audit_trail
        )

    except ValueError as e:
        logger.warning(f"Purchase order not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to send purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while sending purchase order"
        )

# Export router
__all__ = ['router']

# Export router
__all__ = ['router']