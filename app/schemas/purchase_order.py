"""
Pydantic schemas for purchase order data validation with enhanced security features.

Version: 1.0
"""

# External imports with versions
from pydantic import BaseModel, Field, validator, root_validator  # pydantic v1.10+
from typing import Optional, List, Dict, Any, Union  # python 3.9+
from datetime import datetime  # python 3.9+

# Internal imports
from app.models.purchase_order import (
    PO_STATUS_CHOICES,
    PO_FORMAT_CHOICES,
    PO_TEMPLATE_CHOICES
)

class PurchaseOrderBase(BaseModel):
    """
    Base Pydantic model for purchase order data validation with enhanced security features.
    """
    template_type: str = Field(
        ...,
        description="Template style for PO generation",
        example="standard"
    )
    output_format: str = Field(
        ...,
        description="Output format for generated PO",
        example="pdf"
    )
    po_data: Dict[str, Any] = Field(
        ...,
        description="Structured PO content data"
    )
    include_logo: Optional[bool] = Field(
        False,
        description="Flag to include company logo"
    )
    digital_signature: Optional[bool] = Field(
        False,
        description="Flag to include digital signature"
    )
    send_notification: Optional[bool] = Field(
        False,
        description="Flag to send email notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for PO"
    )

    @validator('template_type')
    def validate_template_type(cls, value: str) -> str:
        """Validates template type against allowed choices with security checks."""
        # Sanitize input
        value = value.strip().lower()
        
        if value not in PO_TEMPLATE_CHOICES:
            raise ValueError(f"Invalid template type. Must be one of: {PO_TEMPLATE_CHOICES}")
        
        return value

    @validator('output_format')
    def validate_output_format(cls, value: str) -> str:
        """Validates output format against allowed choices with format-specific checks."""
        # Sanitize input
        value = value.strip().lower()
        
        if value not in PO_FORMAT_CHOICES:
            raise ValueError(f"Invalid output format. Must be one of: {PO_FORMAT_CHOICES}")
        
        return value

    @root_validator
    def validate_po_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validates PO data structure and content with enhanced security."""
        po_data = values.get('po_data', {})
        template_type = values.get('template_type')
        
        # Basic required fields for all templates
        basic_required = ['vendor_name', 'total_amount']
        missing_basic = [field for field in basic_required if field not in po_data]
        if missing_basic:
            raise ValueError(f"Missing basic required fields: {missing_basic}")

        # Set default values for optional fields
        if template_type == 'standard':
            po_data.setdefault('vendor_address', 'N/A')
            po_data.setdefault('buyer_name', 'N/A')
            po_data.setdefault('buyer_address', 'N/A')
            po_data.setdefault('payment_terms', 'Standard payment terms apply')

        # Validate line items if present
        if 'line_items' in po_data:
            if not isinstance(po_data['line_items'], list):
                raise ValueError("line_items must be a list")
            for item in po_data['line_items']:
                if not all(k in item for k in ['description', 'quantity', 'unit_price']):
                    raise ValueError("Each line item must contain description, quantity, and unit_price")
                
                # Validate numerical values
                if not isinstance(item['quantity'], (int, float)) or item['quantity'] <= 0:
                    raise ValueError("Quantity must be a positive number")
                if not isinstance(item['unit_price'], (int, float)) or item['unit_price'] <= 0:
                    raise ValueError("Unit price must be a positive number")

        # Validate total amount
        if 'total_amount' in po_data:
            if not isinstance(po_data['total_amount'], (int, float)) or po_data['total_amount'] <= 0:
                raise ValueError("Total amount must be a positive number")

        # Update the values with potentially modified po_data
        values['po_data'] = po_data
        return values

class PurchaseOrderCreate(PurchaseOrderBase):
    """Schema for creating a new purchase order with enhanced validation."""
    contract_id: str = Field(
        ...,
        description="Associated contract ID",
        regex=r'^[0-9a-fA-F]{24}$'  # MongoDB ObjectId format
    )
    attachments: Optional[List[str]] = Field(
        None,
        description="List of attachment file paths",
        max_items=10
    )
    preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional processing preferences"
    )

class PurchaseOrderUpdate(PurchaseOrderBase):
    """Schema for updating an existing purchase order with change tracking."""
    status: Optional[str] = Field(
        None,
        description="Updated PO status"
    )
    change_log: Optional[Dict[str, Any]] = Field(
        None,
        description="Track changes made to PO"
    )

    @validator('status')
    def validate_status(cls, value: str) -> str:
        """Validates status against allowed choices with transition rules."""
        if value not in PO_STATUS_CHOICES:
            raise ValueError(f"Invalid status. Must be one of: {PO_STATUS_CHOICES}")
            
        return value

class PurchaseOrderResponse(BaseModel):
    """Schema for purchase order API responses with comprehensive details."""
    id: str = Field(..., description="PO document ID")
    po_number: str = Field(..., description="Unique PO number")
    status: str = Field(..., description="Current PO status")
    contract_id: str = Field(..., description="Associated contract ID")
    generated_by: str = Field(..., description="User ID of PO generator")
    template_type: str = Field(..., description="Selected template type")
    output_format: str = Field(..., description="Output format")
    file_path: Optional[str] = Field(None, description="Generated file path")
    po_data: Dict[str, Any] = Field(..., description="PO content data")
    amount: float = Field(..., description="Total amount of the purchase order")
    include_logo: bool = Field(..., description="Logo inclusion flag")
    digital_signature: bool = Field(..., description="Digital signature flag")
    send_notification: bool = Field(..., description="Notification flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    sent_at: Optional[datetime] = Field(None, description="Sent timestamp")
    error_message: Optional[str] = Field(None, description="Error details")
    audit_trail: Optional[Dict[str, Any]] = Field(None, description="Audit information")

    @validator('amount')
    def validate_amount(cls, v: float) -> float:
        """Validates that amount is a positive number."""
        if v < 0:
            raise ValueError("Amount must be a positive number")
        return round(v, 2)  # Round to 2 decimal places

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

class PurchaseOrderValidationRequest(BaseModel):
    """Schema for purchase order validation request."""
    po_id: str = Field(
        ...,
        description="ID of the purchase order to validate",
        regex=r'^[0-9a-fA-F]{24}$'  # MongoDB ObjectId format
    )
    corrected_data: Dict[str, Any] = Field(
        ...,
        description="Corrected purchase order data"
    )
    validation_notes: Optional[Dict[str, Any]] = Field(
        None,
        description="Notes from the validation process"
    )

class PurchaseOrderValidationResponse(BaseModel):
    """Schema for purchase order validation response."""
    po_id: str = Field(
        ...,
        description="ID of the validated purchase order"
    )
    status: str = Field(
        ...,
        description="Validation status"
    )
    validated_data: Dict[str, Any] = Field(
        ...,
        description="Final validated purchase order data"
    )
    validation_metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata about the validation process"
    )