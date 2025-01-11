"""
Dependency injection module for FastAPI application.

Version: 1.0
"""

from fastapi import Depends, HTTPException, status
from typing import Optional
from pathlib import Path

from app.services.contract_service import ContractService
from app.services.ocr_service import OCRService
from app.services.s3_service import S3Service
from app.services.purchase_order_service import PurchaseOrderService
from app.services.email_service import EmailService
from app.core.config import get_settings
import logging
from app.db.mongodb import get_database

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Service instances
_ocr_service: Optional[OCRService] = None
_s3_service: Optional[S3Service] = None
_po_service: Optional[PurchaseOrderService] = None
_contract_service: Optional[ContractService] = None
_email_service: Optional[EmailService] = None

def get_email_service() -> EmailService:
    """Get or create Email service instance."""
    global _email_service
    if _email_service is None:
        try:
            settings = get_settings()
            _email_service = EmailService()
        except Exception as e:
            logger.error(f"Failed to initialize Email service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service unavailable"
            )
    return _email_service

def get_ocr_service() -> OCRService:
    """Get or create OCR service instance."""
    global _ocr_service
    if _ocr_service is None:
        try:
            _ocr_service = OCRService()
        except Exception as e:
            logger.error(f"Failed to initialize OCR service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OCR service unavailable"
            )
    return _ocr_service

def get_s3_service() -> S3Service:
    """Get or create S3 service instance."""
    global _s3_service
    if _s3_service is None:
        try:
            settings = get_settings()
            _s3_service = S3Service()
        except Exception as e:
            logger.error(f"Failed to initialize S3 service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service unavailable"
            )
    return _s3_service

async def get_po_service(
    s3_service: S3Service = Depends(),
    email_service: EmailService = Depends(),
    settings = Depends(get_settings),
    db = Depends(get_database)
) -> PurchaseOrderService:
    """
    Get configured purchase order service instance.
    
    Args:
        s3_service: S3 service instance
        email_service: Email service instance
        settings: Application settings
        db: Database instance
        
    Returns:
        PurchaseOrderService: Configured service instance
    """
    return PurchaseOrderService(
        s3_service=s3_service,
        email_service=email_service,
        config=settings.dict(),
        db=db
    )

def get_contract_service(
    s3_service: S3Service = Depends(get_s3_service),
    po_service: PurchaseOrderService = Depends(get_po_service),
    ocr_service: Optional[OCRService] = Depends(get_ocr_service)
) -> ContractService:
    """Get or create Contract service instance."""
    global _contract_service
    if _contract_service is None:
        try:
            _contract_service = ContractService(
                ocr_service=ocr_service,
                s3_service=s3_service,
                po_service=po_service
            )
        except Exception as e:
            logger.error(f"Failed to initialize Contract service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Contract service unavailable"
            )
    return _contract_service 