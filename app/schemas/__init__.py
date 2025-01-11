"""
Main entry point for Pydantic schema models that define data validation and serialization rules
for the contract processing system. Provides centralized schema registry with version tracking,
validation utilities, and comprehensive type hints for enhanced IDE support.

Version: 1.0.0
"""

# External imports with versions
from typing import Dict, Optional  # python 3.9+
from pydantic import BaseModel  # pydantic v1.10.0

# Internal imports for authentication schemas
from .auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    PasswordChangeRequest
)

# Internal imports for user management schemas
from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserInDB
)

# Internal imports for contract processing schemas
from .contract import (
    ContractBase,
    ContractCreate,
    ContractUpdate,
    ContractResponse,
    ContractValidationRequest,
    ContractValidationResponse,
    BatchUploadResponse
)

# Internal imports for purchase order schemas
from .purchase_order import (
    PurchaseOrderBase,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseOrderValidationRequest,
    PurchaseOrderValidationResponse
)

# Internal imports for OCR processing schemas
from .ocr import (
    OCRRequest,
    OCRResponse,
    OCRStatus
)

# Export all schemas
__all__ = [
    # Authentication schemas
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    
    # User management schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    
    # Contract processing schemas
    "ContractBase",
    "ContractCreate",
    "ContractUpdate",
    "ContractResponse",
    "ContractValidationRequest",
    "ContractValidationResponse",
    "BatchUploadResponse",
    
    # Purchase order schemas
    "PurchaseOrderBase",
    "PurchaseOrderCreate",
    "PurchaseOrderUpdate",
    "PurchaseOrderResponse",
    "PurchaseOrderValidationRequest",
    "PurchaseOrderValidationResponse",
    
    # OCR processing schemas
    "OCRRequest",
    "OCRResponse",
    "OCRStatus"
]