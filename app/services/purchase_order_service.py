"""
Enterprise-grade service module for managing purchase order generation, processing, and lifecycle management.
Implements template-based PO generation with multiple output formats, batch processing capabilities,
notification integration, and comprehensive monitoring.

Version: 1.0
"""

# External imports with versions
import asyncio  # python 3.9+
import structlog  # v22.1+
from jinja2 import Environment, FileSystemLoader, select_autoescape  # v3.1.2
from weasyprint import HTML  # v57.1
from docx import Document  # v0.8.11
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
import hashlib
from pathlib import Path
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase  # Add this import
from bson import ObjectId

# Internal imports
from app.models.purchase_order import (
    PurchaseOrder,
    PO_STATUS_CHOICES,
    PO_FORMAT_CHOICES,
    PO_TEMPLATE_CHOICES,
    create_purchase_order
)
from app.services.s3_service import S3Service
from app.services.email_service import EmailService

# Configure structured logging
logger = structlog.get_logger(__name__)

# Global constants
MAX_BATCH_SIZE = 50  # Maximum POs to process in a batch
TEMPLATE_SANDBOX_CONFIG = {
    'trim_blocks': True,
    'lstrip_blocks': True
}

class PurchaseOrderService:
    """
    Service class for managing purchase order generation and processing with
    comprehensive security, monitoring, and scalability features.
    """

    def __init__(
        self, 
        s3_service: S3Service, 
        email_service: EmailService, 
        config: Dict,
        db: AsyncIOMotorDatabase
    ):
        """
        Initialize purchase order service with required dependencies and configuration.

        Args:
            s3_service: S3 service instance for file storage
            email_service: Email service for notifications
            config: Service configuration dictionary
            db: Database instance for data persistence
        """
        self._s3_service = s3_service
        self._email_service = email_service
        self._config = config
        self._db = db
        
        # Initialize Jinja2 environment with security measures
        template_path = config.get('template_dir', Path(__file__).parent.parent / "templates" / "purchase_orders")
        logger.info(f"Initializing Jinja2 environment with template path: {template_path}")
        
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(template_path)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Initialize template cache for performance
        self._template_cache = {}
        
        # Initialize metrics tracking
        self._metrics = {
            'total_generated': 0,
            'generation_times': [],
            'errors': 0
        }

    async def create_purchase_order(
        self,
        contract_id: str,
        po_data: Dict,
        user_id: str,
        send_notification: bool = True
    ) -> PurchaseOrder:
        """
        Creates a new purchase order from contract data with comprehensive validation and monitoring.

        Args:
            contract_id: Associated contract ID
            po_data: Purchase order data dictionary
            user_id: ID of user generating the PO
            send_notification: Flag to trigger email notification

        Returns:
            PurchaseOrder: Generated purchase order document with status and metrics

        Raises:
            ValidationException: If validation fails
            Exception: For other processing errors
        """
        try:
            # Start performance monitoring
            start_time = datetime.utcnow()

            # Generate unique PO number
            po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

            # Validate and process line items
            line_items = po_data.get("po_data", {}).get("line_items", [])
            total_amount = po_data.get("po_data", {}).get("total_amount", 0)

            processed_line_items = []
            for item in line_items:
                # Ensure required fields with defaults
                processed_item = {
                    "name": item.get("name", "Contract Item"),
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 1),  # Default to 1 if not provided
                    "unit_price": item.get("unit_price", total_amount),  # Default to total amount if not provided
                    "total": item.get("total", (item.get("quantity", 1) * item.get("unit_price", total_amount)))
                }
                processed_line_items.append(processed_item)

            # Calculate totals
            subtotal = sum(item["total"] for item in processed_line_items)
            tax = po_data.get("po_data", {}).get("tax", 0)
            total = subtotal + tax

            # Update po_data with processed values
            processed_po_data = {
                **po_data.get("po_data", {}),
                "line_items": processed_line_items,
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "total_amount": total  # Ensure total_amount matches the calculated total
            }

            # Prepare purchase order data
            po_dict = {
                "po_number": po_number,
                "status": "draft",
                "contract_id": contract_id,
                "generated_by": user_id,
                "template_type": po_data.get("template_type", "standard"),
                "output_format": po_data.get("output_format", "pdf"),
                "po_data": processed_po_data,
                "include_logo": po_data.get("include_logo", False),
                "digital_signature": po_data.get("digital_signature", False),
                "send_notification": send_notification,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Create purchase order with security context
            security_context = {"user_id": user_id}
            po = await create_purchase_order(po_dict, security_context)

            # Update metrics
            self._metrics['total_generated'] += 1
            self._metrics['generation_times'].append(
                (datetime.utcnow() - start_time).total_seconds()
            )

            # Send notification if requested
            if send_notification and self._email_service:
                recipient_email = processed_po_data.get("buyer_email") or processed_po_data.get("vendor_email")
                if recipient_email:
                    await self._email_service.send_po_generated_notification(
                        recipient_email=recipient_email,
                        po_number=po.po_number,
                        po_data=processed_po_data
                    )

            return po

        except Exception as e:
            # Log error and update metrics
            logger.error(f"purchase_order_generation_failed contract_id={contract_id} error={str(e)}")
            self._metrics['errors'] += 1
            raise

    async def _generate_po_file(self, po: PurchaseOrder) -> bytes:
        """
        Generate PO file content using template with proper format handling.

        Args:
            po: Purchase order document instance

        Returns:
            bytes: Generated file content

        Raises:
            ValueError: If template or format is invalid
        """
        # Get template from cache or load it
        template_key = f"{po.template_type}_{po.output_format}"
        if template_key not in self._template_cache:
            template = self._jinja_env.get_template(
                f"{po.template_type}.html"
            )
            self._template_cache[template_key] = template
        else:
            template = self._template_cache[template_key]

        # Render HTML content
        html_content = template.render(
            po_number=po.po_number,
            po_data=po.po_data,
            generated_at=datetime.utcnow().isoformat(),
            include_logo=po.include_logo,
            digital_signature=po.digital_signature
        )

        # Convert to requested format
        if po.output_format == 'pdf':
            return await self._generate_pdf(html_content)
        elif po.output_format == 'docx':
            return await self._generate_docx(html_content)
        else:
            raise ValueError(f"Unsupported output format: {po.output_format}")

    async def _generate_pdf(self, html_content: str) -> bytes:
        """
        Generate PDF from HTML content using WeasyPrint.

        Args:
            html_content: Rendered HTML content

        Returns:
            bytes: PDF file content
        """
        return HTML(string=html_content).write_pdf()

    async def _generate_docx(self, html_content: str) -> bytes:
        """
        Generate DOCX from HTML content using python-docx.

        Args:
            html_content: Rendered HTML content

        Returns:
            bytes: DOCX file content
        """
        doc = Document()
        doc.add_paragraph(html_content)  # Basic conversion, enhance as needed
        return doc.save()

    async def _upload_po_file(
        self,
        file_content: bytes,
        s3_key: str,
        metadata: Dict,
        file_format: str
    ) -> Dict:
        """
        Upload generated PO file to S3 with metadata.

        Args:
            file_content: File content bytes
            s3_key: S3 storage key
            metadata: File metadata dictionary
            file_format: File format (pdf/docx)

        Returns:
            Dict: Upload result including file URL
        """
        content_types = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }

        return await self._s3_service.upload_file(
            file_content,
            s3_key,
            metadata,
            content_type=content_types.get(file_format, 'application/octet-stream')
        )

    async def _send_notification(self, po: PurchaseOrder) -> None:
        """
        Send email notification for generated PO.

        Args:
            po: Generated purchase order document
        """
        try:
            await self._email_service.send_po_generated_notification(
                recipient_email=po.po_data.get('recipient_email'),
                po_number=po.po_number,
                po_data={
                    'status': po.status,
                    'generated_at': po.created_at.isoformat(),
                    'download_url': await self.get_po_download_url(po.po_number)
                }
            )
        except Exception as e:
            logger.error(
                "po_notification_failed",
                error=str(e),
                po_number=po.po_number
            )

    def _generate_po_number(self) -> str:
        """
        Generate unique PO number with proper formatting.

        Returns:
            str: Formatted PO number
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"PO-{timestamp}-{os.urandom(4).hex()}"

    def _update_metrics(self, generation_time: float) -> None:
        """
        Update service metrics with new generation data.

        Args:
            generation_time: Time taken to generate PO in seconds
        """
        self._metrics['total_generated'] += 1
        self._metrics['generation_times'].append(generation_time)
        
        # Keep only last 1000 generation times
        if len(self._metrics['generation_times']) > 1000:
            self._metrics['generation_times'] = self._metrics['generation_times'][-1000:]

    async def get_po_download_url(self, po_number: str) -> str:
        """
        Get secure download URL for generated PO.

        Args:
            po_number: PO number to get URL for

        Returns:
            str: Signed download URL

        Raises:
            ValueError: If PO not found
        """
        po = await PurchaseOrder.objects.get(po_number=po_number)
        if not po or not po.file_path:
            raise ValueError(f"PO not found or file not generated: {po_number}")

        return await self._s3_service.get_file_url(
            po.file_path.replace('s3://', ''),
            expiry=3600  # URL valid for 1 hour
        )

    async def get_purchase_orders(
        self,
        user_id: str,
        filters: dict = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Get list of purchase orders with optional filtering.

        Args:
            user_id: ID of the requesting user
            filters: Optional dictionary of filters to apply
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return (pagination)

        Returns:
            List[PurchaseOrder]: List of purchase orders matching criteria
        """
        try:
            # Start with base query
            query = {}

            # Add filters if provided
            if filters:
                query.update(filters)

            # Get purchase orders from database
            cursor = self._db.purchase_orders.find(
                query,
                skip=skip,
                limit=limit
            )
            
            # Convert cursor to list of PurchaseOrder objects
            purchase_orders = []
            async for doc in cursor:
                # Convert MongoDB _id to string id
                doc_id = str(doc.pop('_id'))
                
                # Get po_data and extract amount
                po_data = doc.get('po_data', {})
                amount = po_data.get('total_amount', 0)
                
                # Create PurchaseOrder object with properly formatted data
                purchase_order_data = {
                    'id': doc_id,
                    'po_number': doc.get('po_number'),
                    'status': doc.get('status', 'draft'),
                    'contract_id': doc.get('contract_id'),
                    'generated_by': doc.get('generated_by'),
                    'template_type': doc.get('template_type', 'standard'),
                    'output_format': doc.get('output_format', 'pdf'),
                    'file_path': doc.get('file_path'),
                    'po_data': {
                        **po_data,
                        'amount': amount  # Add amount to po_data
                    },
                    'include_logo': doc.get('include_logo', False),
                    'digital_signature': doc.get('digital_signature', False),
                    'send_notification': doc.get('send_notification', False),
                    'created_at': doc.get('created_at', datetime.utcnow()),
                    'updated_at': doc.get('updated_at', datetime.utcnow()),
                    'sent_at': doc.get('sent_at'),
                    'error_message': doc.get('error_message')
                }
                purchase_orders.append(PurchaseOrder(purchase_order_data))

            return purchase_orders

        except Exception as e:
            logger.error(f"Error retrieving purchase orders: {str(e)}")
            raise e

    async def send_purchase_order(self, po_id: str, user_id: str) -> PurchaseOrder:
        """
        Send a purchase order to the recipient.

        Args:
            po_id: ID of the purchase order to send
            user_id: ID of the user sending the purchase order

        Returns:
            PurchaseOrder: Updated purchase order instance

        Raises:
            ValueError: If purchase order not found
        """
        try:
            # Get purchase order from database
            collection = self._db.purchase_orders
            po_doc = await collection.find_one({"_id": ObjectId(po_id)})
            
            if not po_doc:
                raise ValueError(f"Purchase order not found: {po_id}")

            # Create PurchaseOrder instance
            po = PurchaseOrder(po_doc)

            # Send email notification
            if self._email_service:
                recipient_email = po.po_data.get("recipient_email")
                if recipient_email:
                    await self._email_service.send_po_notification(
                        recipient_email=recipient_email,
                        po_number=po.po_number,
                        po_data=po.po_data
                    )

            # Update purchase order status and sent timestamp
            update_data = {
                "status": "sent",
                "sent_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Update in database
            await collection.update_one(
                {"_id": ObjectId(po_id)},
                {"$set": update_data}
            )

            # Update PurchaseOrder instance
            po.status = update_data["status"]
            po.sent_at = update_data["sent_at"]
            po.updated_at = update_data["updated_at"]

            # Create audit log
            await create_audit_log(
                entity_type="purchase_order",
                entity_id=str(po.id),
                action="send",
                user_id=user_id,
                changes=update_data
            )

            return po

        except Exception as e:
            logger.error(f"Failed to send purchase order {po_id}: {str(e)}")
            raise