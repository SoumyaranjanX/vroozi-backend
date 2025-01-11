"""
Enhanced service module for managing contract document lifecycle with comprehensive
error handling, security features, and monitoring capabilities.

Version: 1.0
"""

# External imports with versions
import asyncio  # built-in
import logging  # built-in
from typing import Dict, List, Optional, Any  # built-in
from circuitbreaker import circuit  # v1.4.0
from datetime import datetime
import hashlib
import os
import json
import uuid

# Internal imports
from app.models.contract import Contract, create_contract
from app.services.ocr_service import OCRService
from app.services.s3_service import S3Service
from app.services.purchase_order_service import PurchaseOrderService
from app.core.exceptions import OCRProcessingException, ValidationException
from app.models.audit_log import create_audit_log

# Configure logging
logger = logging.getLogger(__name__)

# Global constants
MAX_BATCH_SIZE = 50
MAX_RETRIES = 3
PROCESSING_TIMEOUT = 5
SUPPORTED_FILE_TYPES = ['pdf', 'docx', 'png', 'jpg', 'jpeg']

class ContractService:
    """
    Enhanced service class for managing contract document lifecycle with comprehensive
    error handling, security features, and monitoring capabilities.
    """

    def __init__(
        self,
        ocr_service: OCRService,
        s3_service: S3Service,
        po_service: PurchaseOrderService
    ):
        """
        Initialize contract service with required dependencies and monitoring.

        Args:
            ocr_service: Optional OCR processing service instance
            s3_service: S3 storage service instance
            po_service: Purchase order service instance
        """
        self._ocr_service = ocr_service
        self._s3_service = s3_service
        self._po_service = po_service
        
        # Initialize performance metrics
        self._metrics = {
            'total_processed': 0,
            'processing_times': [],
            'errors': 0
        }

    @circuit(failure_threshold=5, recovery_timeout=60)
    async def upload_contract(
        self,
        file_data: bytes,
        filename: str,
        metadata: Dict,
        user_id: str,
        security_context: Optional[Dict] = None
    ) -> Contract:
        """
        Upload and process new contract document with enhanced security and monitoring.

        Args:
            file_data: Binary content of the contract document
            filename: Original filename of the contract
            metadata: Contract metadata dictionary
            user_id: ID of user uploading contract
            security_context: Optional security context for access control

        Returns:
            Contract: Processed contract document

        Raises:
            ValueError: If validation fails
            OCRProcessingException: If processing fails
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate file type
            file_extension = filename.split('.')[-1].lower()
            if file_extension not in SUPPORTED_FILE_TYPES:
                raise ValidationException(f"Unsupported file type: {file_extension}")
            
            # Calculate file hash for integrity
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Prepare S3 path and enhanced metadata
            s3_key = f"contracts/{datetime.utcnow().strftime('%Y/%m')}/{file_hash}/{filename}"
            enhanced_metadata = {
                **metadata,
                'file_hash': file_hash,
                'uploaded_by': user_id,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'security_context': json.dumps(security_context or {})
            }

            # Convert all metadata values to strings for S3
            s3_metadata = {k: str(v) for k, v in enhanced_metadata.items()}

            # Upload to S3 with retry mechanism
            upload_result = self._s3_service.upload_file(
                file_data=file_data,
                s3_key=s3_key,
                metadata=s3_metadata
            )

            # Create contract record
            contract = await create_contract({
                'file_path': upload_result['s3_key'],
                'status': 'PENDING',
                'metadata': {
                    **enhanced_metadata,
                    'version_id': upload_result['version_id'],
                    'etag': upload_result['etag'],
                    's3_bucket': self._s3_service.bucket_name
                },
                'created_by': user_id,
                'file_size': upload_result['size']
            }, security_context)

            # Update metrics
            self._update_metrics(start_time)

            return contract

        except Exception as e:
            logger.error(f"Contract upload failed: {str(e)}")
            self._metrics['errors'] += 1
            raise

    async def process_batch(
        self,
        file_paths: List[str],
        metadata: Dict,
        user_id: str,
        security_context: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Process multiple contracts in batch with parallel execution.

        Args:
            file_paths: List of contract file paths
            metadata: Shared metadata for contracts
            user_id: ID of user processing contracts
            security_context: Optional security context

        Returns:
            List[Dict]: Batch processing results
        """
        if len(file_paths) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum limit of {MAX_BATCH_SIZE}")

        # Create processing tasks
        tasks = []
        for file_path in file_paths:
            task = asyncio.create_task(
                self.upload_contract(
                    file_path=file_path,
                    metadata=metadata,
                    user_id=user_id,
                    security_context=security_context
                )
            )
            tasks.append(task)

        # Process in parallel with result tracking
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

        return results

    async def generate_purchase_orders(
        self,
        contract_ids: List[str],
        po_template: str,
        user_id: str,
        security_context: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Generate purchase orders for processed contracts.

        Args:
            contract_ids: List of contract IDs
            po_template: Template type for PO generation
            user_id: ID of user generating POs
            security_context: Optional security context

        Returns:
            List[Dict]: PO generation results
        """
        results = []
        
        for contract_id in contract_ids:
            try:
                # Get contract
                contract = await Contract.get_by_id(contract_id)
                if not contract:
                    raise ValidationException(f"Contract not found: {contract_id}")
                
                if contract.status != 'VALIDATED':
                    raise ValidationException(
                        f"Contract {contract_id} not validated for PO generation"
                    )

                # Generate PO
                po = await self._po_service.create_purchase_order(
                    contract_id=contract_id,
                    po_data={
                        'template_type': po_template,
                        'contract_data': contract.extracted_data,
                        'metadata': contract.metadata
                    },
                    user_id=user_id
                )

                # Update contract with PO reference
                await contract.update({
                    'po_numbers': [*contract.po_numbers, po.po_number]
                }, user_id)

                results.append({
                    'status': 'success',
                    'contract_id': contract_id,
                    'po_number': po.po_number
                })

            except Exception as e:
                logger.error(f"PO generation failed for contract {contract_id}: {str(e)}")
                results.append({
                    'status': 'error',
                    'contract_id': contract_id,
                    'error': str(e)
                })

        return results

    async def _validate_file(self, file_path: str) -> None:
        """
        Validate file type and size with security checks.

        Args:
            file_path: Path to file for validation

        Raises:
            ValueError: If validation fails
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        # Validate file type
        file_extension = os.path.splitext(file_path)[1].lower().lstrip('.')
        if file_extension not in SUPPORTED_FILE_TYPES:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Validate file size
        file_size = os.path.getsize(file_path)
        if file_size > (25 * 1024 * 1024):  # 25MB limit
            raise ValueError("File size exceeds maximum limit of 25MB")

    async def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of file for integrity verification.

        Args:
            file_path: Path to file

        Returns:
            str: SHA256 hash of file
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _update_metrics(self, start_time: datetime) -> None:
        """
        Update service metrics with new processing data.

        Args:
            start_time: Processing start timestamp
        """
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        self._metrics['total_processed'] += 1
        self._metrics['processing_times'].append(processing_time)
        
        # Keep only last 1000 processing times
        if len(self._metrics['processing_times']) > 1000:
            self._metrics['processing_times'] = self._metrics['processing_times'][-1000:]

    async def get_contracts(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict] = None
    ) -> List[Contract]:
        """
        Get list of contracts with pagination and filtering support.

        Args:
            user_id: ID of user requesting contracts
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters to apply

        Returns:
            List[Contract]: List of contract documents
        """
        try:
            # Build query
            query = {}
            if filters:
                query.update(filters)

            # Get contracts from database
            contracts = await Contract.get_contracts(
                query=query,
                skip=skip,
                limit=limit,
                user_id=user_id
            )

            return contracts

        except Exception as e:
            logger.error(f"Failed to get contracts: {str(e)}")
            raise

    async def process_contract(self, contract_id: str, user_id: str) -> Contract:
        """
        Process a contract using OCR service.
        
        Args:
            contract_id: ID of the contract to process
            user_id: ID of the user initiating the processing
            
        Returns:
            Contract: Updated contract with processing results
            
        Raises:
            OCRProcessingException: If processing fails
        """
        try:
            # Get the contract
            contract = await Contract.get_by_id(contract_id)
            if not contract:
                raise ValidationException(f"Contract not found: {contract_id}")
            
            # Create OCR request
            from app.schemas.ocr import OCRRequest
            import os
            
            # Update contract status to PROCESSING
            await contract.update({
                'status': 'PROCESSING'
            }, user_id)
            
            # Generate a UUID for OCR processing
            ocr_uuid = str(uuid.uuid4())
            
            # Ensure tmp directory exists
            os.makedirs('/tmp', exist_ok=True)
            
            ocr_request = OCRRequest(
                contract_id=ocr_uuid,
                file_path=contract.file_path,
                processing_options=contract.metadata.get('processing_options', {})
            )
            
            try:
                # Process with OCR service
                ocr_result = await self._ocr_service.process_document(ocr_request)
                
                # Update contract with OCR results
                await contract.update({
                    'status': ocr_result.status,
                    'extracted_data': ocr_result.extracted_data,
                    'validation_notes': {
                        'confidence_score': ocr_result.confidence_score,
                        'processing_time': ocr_result.processing_time,
                        'ocr_request_id': ocr_uuid
                    }
                }, user_id)
            except Exception as e:
                # Update contract status to FAILED if OCR fails
                await contract.update({
                    'status': 'FAILED',
                    'error_details': {'message': str(e)}
                }, user_id)
                raise
            
            # Create audit log
            await create_audit_log(
                entity_type="contract",
                entity_id=str(contract._id),
                action="process_contract",
                user_id=user_id,
                changes={
                    'status': ocr_result.status,
                    'confidence_score': ocr_result.confidence_score,
                    'ocr_request_id': ocr_uuid
                }
            )
            
            return contract
            
        except Exception as e:
            logger.error(f"Contract processing failed: {str(e)}")
            raise OCRProcessingException(f"Contract processing failed: {str(e)}")

    async def get_contract(self, contract_id: str, user_id: str) -> Optional[Contract]:
        """
        Retrieve a single contract by ID.
        
        Args:
            contract_id: The ID of the contract to retrieve
            user_id: The ID of the user making the request
            
        Returns:
            Contract object if found, None otherwise
        """
        try:
            contract = await Contract.get_by_id(contract_id)
            if contract and (contract.created_by == user_id or await self._user_has_access(user_id, contract)):
                return contract
            return None
        except Exception as e:
            logger.error(f"Error retrieving contract {contract_id}: {str(e)}")
            return None

    async def _user_has_access(self, user_id: str, contract: Contract) -> bool:
        """Check if user has access to the contract based on roles and permissions."""
        # TODO: Implement proper access control based on your requirements
        return True

    async def update_contract_validation(
        self,
        contract_id: str,
        validation_data: Dict,
        user_id: str
    ) -> Optional[Contract]:
        """
        Update contract validation data and status.

        Args:
            contract_id: ID of the contract to update
            validation_data: Validation data including extracted fields and validation status
            user_id: ID of user performing validation

        Returns:
            Contract: Updated contract document or None if not found

        Raises:
            ValidationException: If validation fails
        """
        try:
            # Get contract
            contract = await Contract.get_by_id(contract_id)
            if not contract:
                return None

            # Prepare update data
            update_data = {
                'extracted_data': validation_data.get('extracted_data', {}),
                'validation_notes': {
                    'validated_by': user_id,
                    'validated_at': datetime.utcnow().isoformat(),
                    'confidence_level': validation_data.get('confidence_level', 0),
                    'comments': validation_data.get('comments', '')
                },
                'status': validation_data.get('status', 'VALIDATION_REQUIRED')
            }

            # Update status if contract is being validated
            if validation_data.get('is_validated', False):
                update_data['status'] = 'VALIDATED'
            
            # Update contract
            updated_contract = await contract.update(update_data, user_id)
            
            # Create audit log with correct argument passing
            await create_audit_log(
                entity_type='contract',
                entity_id=contract_id,
                action='validation_update',
                user_id=user_id,
                changes=update_data
            )

            return updated_contract

        except Exception as e:
            logger.error(f"Contract validation update failed: {str(e)}")
            raise ValidationException(f"Failed to update contract validation: {str(e)}")