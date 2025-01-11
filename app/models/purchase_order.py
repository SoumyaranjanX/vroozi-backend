# Version: 1.0
# Purpose: MongoDB document model for purchase orders with enhanced tracking and notification capabilities

# External imports with versions
from datetime import datetime  # python 3.9+
from typing import Dict, List, Optional, Any, Union  # built-in
from bson import ObjectId  # bson v1.23.0
import uuid  # built-in

# Internal imports
from app.db.mongodb import get_database
from app.models.audit_log import create_audit_log, get_audit_logs

# Global constants for purchase order configuration
PO_COLLECTION = "purchase_orders"
PO_STATUS_CHOICES = ["draft", "generated", "sent", "error"]
PO_FORMAT_CHOICES = ["pdf", "docx"]
PO_TEMPLATE_CHOICES = ["standard", "detailed", "simple"]

def serialize_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

def serialize_dict(data: Dict) -> Dict:
    """Recursively serialize dictionary values."""
    return {k: serialize_datetime(v) for k, v in data.items()}

class PurchaseOrder:
    """
    Enhanced MongoDB model for purchase orders with comprehensive
    template-based generation support and advanced customization options.
    """
    
    def __init__(self, po_data: Dict, security_context: Optional[Dict] = None):
        """
        Initializes a new purchase order document with enhanced customization options.
        Sets default values and timestamps.
        
        Args:
            po_data: Dictionary containing purchase order information
            security_context: Optional security context for access control
            
        Raises:
            ValueError: If validation fails
        """
        # Initialize core properties with validation
        id_value = po_data.get('_id') or po_data.get('id')
        self._id = ObjectId(id_value) if id_value else ObjectId()
        
        self.po_number = po_data.get('po_number')
        self.status = po_data.get('status', 'draft')
        self.contract_id = po_data.get('contract_id')
        self.generated_by = po_data.get('generated_by')
        self.template_type = po_data.get('template_type', 'standard')
        self.output_format = po_data.get('output_format', 'pdf')
        self.file_path = po_data.get('file_path')
        self.po_data = po_data.get('po_data', {})
        self.include_logo = po_data.get('include_logo', False)
        self.digital_signature = po_data.get('digital_signature', False)
        self.send_notification = po_data.get('send_notification', False)
        self.created_at = po_data.get('created_at', datetime.utcnow())
        self.updated_at = po_data.get('updated_at', datetime.utcnow())
        self.sent_at = po_data.get('sent_at')
        self.error_message = po_data.get('error_message')
        self._audit_trail = None

        # Validate status
        if self.status not in PO_STATUS_CHOICES:
            raise ValueError(f"Invalid status: {self.status}")
        
        # Validate template type
        if self.template_type not in PO_TEMPLATE_CHOICES:
            raise ValueError(f"Invalid template type: {self.template_type}")
        
        # Validate output format
        if self.output_format not in PO_FORMAT_CHOICES:
            raise ValueError(f"Invalid output format: {self.output_format}")

    @property
    def id(self) -> str:
        """Returns string representation of document ID."""
        return str(self._id)

    @property
    async def audit_trail(self) -> Dict[str, Any]:
        """Get audit trail for this purchase order."""
        if self._audit_trail is None:
            filters = {
                'entity_type': 'purchase_order',
                'entity_id': self.id
            }
            self._audit_trail = await get_audit_logs(filters=filters)
        return self._audit_trail

    async def save(self, security_context: Optional[Dict] = None) -> Dict:
        """
        Saves purchase order document to MongoDB with validation.
        
        Args:
            security_context: Optional security context for access control
            
        Returns:
            Dict: Saved document data
            
        Raises:
            Exception: If save operation fails
        """
        db = await get_database()
        collection = db[PO_COLLECTION]

        # Update timestamp
        self.updated_at = datetime.utcnow()

        # Convert to dict for storage
        po_dict = self.to_dict()
        
        # Remove _id from update data
        update_data = {k: v for k, v in po_dict.items() if k != '_id'}

        # Save to database
        await collection.update_one(
            {'_id': self._id},
            {'$set': update_data},
            upsert=True
        )

        # Create audit log with serialized data
        changes = serialize_dict({"status": self.status})
        await create_audit_log(
            entity_type="purchase_order",
            entity_id=self.id,
            action="save",
            user_id=security_context.get('user_id') if security_context else None,
            changes=changes
        )

        return po_dict

    def to_dict(self) -> Dict:
        """
        Converts purchase order to dictionary format.
        
        Returns:
            Dict: Document data dictionary
        """
        return {
            '_id': str(self._id),
            'po_number': self.po_number,
            'status': self.status,
            'contract_id': self.contract_id,
            'generated_by': self.generated_by,
            'template_type': self.template_type,
            'output_format': self.output_format,
            'file_path': self.file_path,
            'po_data': self.po_data,
            'include_logo': self.include_logo,
            'digital_signature': self.digital_signature,
            'send_notification': self.send_notification,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'sent_at': self.sent_at,
            'error_message': self.error_message
        }

async def create_purchase_order(po_data: Dict, security_context: Optional[Dict] = None) -> PurchaseOrder:
    """
    Creates a new purchase order with validation and audit logging.
    
    Args:
        po_data: Purchase order data dictionary
        security_context: Optional security context for access control
        
    Returns:
        PurchaseOrder: Created purchase order instance
        
    Raises:
        ValueError: If validation fails
    """
    # Create purchase order instance
    po = PurchaseOrder(po_data, security_context)
    
    # Save to database
    await po.save(security_context)
    
    # Create audit log with serialized data
    changes = serialize_dict(po_data)
    await create_audit_log(
        entity_type="purchase_order",
        entity_id=po.id,
        action="create",
        user_id=security_context.get('user_id') if security_context else None,
        changes=changes
    )
    
    return po