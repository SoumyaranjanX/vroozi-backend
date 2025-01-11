"""
Enhanced MongoDB model implementation for contract documents with advanced security features,
OCR processing capabilities, and comprehensive validation workflows.

Version: 1.0
"""

# External imports with versions
from datetime import datetime  # built-in
from typing import Dict, List, Optional, Any, Union  # built-in
from bson import ObjectId, Binary  # bson v1.23.0
import uuid  # built-in
import pymongo  # pymongo v4.3.0
from cryptography.fernet import Fernet  # cryptography v37.0.0

# Internal imports
from app.db.mongodb import get_database
from app.models.audit_log import create_audit_log

# Global constants for contract management
CONTRACT_COLLECTION = "contracts"
CONTRACT_STATUS_CHOICES = [
    "PENDING",
    "PROCESSING",
    "VALIDATION_REQUIRED",
    "VALIDATED",
    "FAILED",
    "COMPLETED"
]
FILE_TYPES_ALLOWED = ["pdf", "docx", "png", "jpg", "jpeg"]
MAX_FILE_SIZE_MB = 25
SENSITIVE_FIELDS = ["metadata.financial_data", "metadata.personal_info"]

class Contract:
    """
    Enhanced MongoDB model for contract documents with comprehensive security features,
    validation workflows, and audit logging capabilities.
    """
    
    def __init__(self, contract_data: Dict, security_context: Optional[Dict] = None):
        """
        Initializes contract document with enhanced validation and security features.
        
        Args:
            contract_data: Dictionary containing contract information
            security_context: Optional security context for enhanced access control
            
        Raises:
            ValueError: If validation fails or security requirements not met
        """
        # Validate required fields
        required_fields = {'file_path', 'created_by'}
        if missing := required_fields - set(contract_data.keys()):
            raise ValueError(f"Missing required fields: {missing}")

        # Initialize core properties with validation
        # Handle both id and _id for input, but store as _id internally
        id_value = contract_data.get('_id') or contract_data.get('id')
        self._id = ObjectId(id_value) if id_value else ObjectId()
        
        self.file_path = contract_data['file_path']
        self.status = contract_data.get('status', 'UPLOADED')
        self.metadata = contract_data.get('metadata', {})
        self.created_by = contract_data['created_by']
        self.created_at = contract_data.get('created_at', datetime.utcnow())
        self.updated_at = contract_data.get('updated_at', datetime.utcnow())
        self.extracted_data = contract_data.get('extracted_data')
        self.validation_notes = contract_data.get('validation_notes', {})
        self.error_details = contract_data.get('error_details', {})
        self.po_numbers = contract_data.get('po_numbers', [])
        self.file_size = contract_data.get('file_size', 0)
        
        # Initialize security metadata with safe defaults if security_context is None
        if 'security_metadata' in contract_data:
            self.security_metadata = contract_data['security_metadata']
        else:
            self.security_metadata = {
                'encryption_key_id': str(uuid.uuid4()),
                'access_control': [],
                'data_classification': 'confidential'
            }
            if security_context:
                self.security_metadata.update({
                    'access_control': security_context.get('access_control', []),
                    'data_classification': security_context.get('classification', 'confidential')
                })
        
        self.version_history = contract_data.get('version_history', [])

        # Validate contract status
        if self.status not in CONTRACT_STATUS_CHOICES:
            raise ValueError(f"Invalid status: {self.status}")

        # Validate file size
        if self.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB}MB")

        # Validate file type
        file_extension = self.file_path.split('.')[-1].lower()
        if file_extension not in FILE_TYPES_ALLOWED:
            raise ValueError(f"Invalid file type: {file_extension}")

    @property
    def id(self) -> str:
        """Get contract ID as string for API responses."""
        return str(self._id)

    async def save(self, security_context: Optional[Dict] = None) -> Dict:
        """
        Persists contract with encryption and audit logging.
        
        Args:
            security_context: Optional security context for access control
            
        Returns:
            Dict: Saved contract data with audit information
            
        Raises:
            RuntimeError: If database operation fails
        """
        try:
            db = await get_database()
            
            # Prepare contract data
            contract_data = self.to_dict()
            contract_data['updated_at'] = datetime.utcnow()
            
            # Update version history
            version_entry = {
                'timestamp': datetime.utcnow(),
                'user_id': security_context.get('user_id') if security_context else None,
                'changes': {'status': self.status}
            }
            contract_data['version_history'].append(version_entry)
            
            # Encrypt sensitive fields
            for field in SENSITIVE_FIELDS:
                if field in contract_data['metadata']:
                    contract_data['metadata'][field] = self._encrypt_field(
                        contract_data['metadata'][field],
                        self.security_metadata['encryption_key_id']
                    )

            # Perform upsert operation
            result = await db[CONTRACT_COLLECTION].update_one(
                {'_id': self._id},
                {'$set': contract_data},
                upsert=True
            )
            
            # Create audit log entry
            await create_audit_log(
                entity_type="contract",
                entity_id=str(self._id),
                action="save",
                user_id=security_context.get('user_id') if security_context else None,
                changes=version_entry['changes']
            )
            
            return {
                'status': 'success',
                'contract_id': str(self._id),
                'message': 'Contract saved successfully'
            }
                
        except Exception as e:
            raise RuntimeError(f"Failed to save contract: {str(e)}")

    async def update(self, update_data: Dict, user_id: str, security_context: Optional[Dict] = None) -> Dict:
        """
        Updates contract with enhanced security and validation.
        
        Args:
            update_data: Dictionary of fields to update
            user_id: ID of user performing the update
            security_context: Optional security context for access control
            
        Returns:
            Dict: Updated contract data
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If update operation fails
        """
        try:
            # Validate update permissions
            if security_context and not self._validate_access(security_context):
                raise ValueError("Insufficient permissions for update")

            # Validate status transition if included
            if 'status' in update_data:
                if update_data['status'] not in CONTRACT_STATUS_CHOICES:
                    raise ValueError(f"Invalid status: {update_data['status']}")

            # Update fields
            for field, value in update_data.items():
                if field == 'validation_notes' and hasattr(self, 'validation_notes'):
                    # Merge validation notes instead of replacing
                    self.validation_notes.update(value)
                elif field == 'metadata' and hasattr(self, 'metadata'):
                    # Merge metadata instead of replacing
                    self.metadata.update(value)
                elif field == 'error_details' and hasattr(self, 'error_details'):
                    # Merge error details instead of replacing
                    self.error_details.update(value)
                elif hasattr(self, field):
                    # Direct field update
                    setattr(self, field, value)

            self.updated_at = datetime.utcnow()

            # Save updates
            result = await self.save(security_context={'user_id': user_id})
            
            return {
                'status': 'success',
                'contract_id': str(self._id),
                'message': 'Contract updated successfully'
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to update contract: {str(e)}")

    def to_dict(self) -> Dict:
        """
        Converts contract to dictionary format with proper type handling.
        
        Returns:
            Dict: Contract data dictionary
        """
        return {
            '_id': self._id,  # Keep _id for MongoDB operations
            'id': self.id,    # Include id for API responses
            'file_path': self.file_path,
            'status': self.status,
            'metadata': self.metadata,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'extracted_data': self.extracted_data,
            'validation_notes': self.validation_notes,
            'error_details': self.error_details,
            'po_numbers': self.po_numbers,
            'file_size': self.file_size,
            'security_metadata': self.security_metadata,
            'version_history': self.version_history
        }

    def _encrypt_field(self, value: Any, key_id: str) -> str:
        """
        Encrypts sensitive field values using Fernet encryption.
        
        Args:
            value: Value to encrypt
            key_id: Encryption key identifier
            
        Returns:
            str: Encrypted value
        """
        try:
            # In production, key should be retrieved from secure key management service
            fernet = Fernet(Fernet.generate_key())
            return fernet.encrypt(str(value).encode()).decode()
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {str(e)}")

    def _validate_access(self, security_context: Dict) -> bool:
        """
        Validates access permissions based on security context.
        
        Args:
            security_context: Security context containing access control information
            
        Returns:
            bool: True if access is allowed
        """
        if not security_context:
            return False
            
        required_access = self.security_metadata.get('access_control', [])
        user_access = security_context.get('access_control', [])
        
        return bool(set(required_access) & set(user_access))

    @staticmethod
    async def get_by_id(contract_id: str) -> Optional['Contract']:
        """
        Get a contract by its ID.

        Args:
            contract_id: ID of the contract to retrieve

        Returns:
            Optional[Contract]: Contract if found, None otherwise
        """
        try:
            db = await get_database()
            doc = await db[CONTRACT_COLLECTION].find_one({'_id': ObjectId(contract_id)})
            return Contract(doc) if doc else None
            
        except Exception as e:
            raise RuntimeError(f"Failed to get contract by ID: {str(e)}")

    @staticmethod
    async def get_contracts(
        query: Dict = None,
        skip: int = 0,
        limit: int = 100,
        user_id: str = None
    ) -> List['Contract']:
        """
        Get list of contracts with pagination and filtering support.

        Args:
            query: Optional query filters
            skip: Number of records to skip
            limit: Maximum number of records to return
            user_id: ID of user requesting contracts

        Returns:
            List[Contract]: List of contract documents
        """
        try:
            db = await get_database()
            
            # Build base query
            base_query = {}
            
            # Add any additional query filters
            if query:
                base_query.update(query)
            
            # Add user filter if not admin
            # TODO: Add proper role check
            if user_id:
                base_query['created_by'] = user_id
            
            # Execute query with pagination
            cursor = db[CONTRACT_COLLECTION].find(base_query)
            cursor = cursor.skip(skip).limit(limit)
            cursor = cursor.sort('created_at', pymongo.DESCENDING)
            
            # Convert results to Contract objects
            contracts = []
            async for doc in cursor:
                contracts.append(Contract(doc))
            
            return contracts
            
        except Exception as e:
            raise RuntimeError(f"Failed to get contracts: {str(e)}")

async def create_contract(contract_data: Dict, security_context: Optional[Dict] = None) -> Contract:
    """
    Creates contract with enhanced security and validation.
    
    Args:
        contract_data: Dictionary containing contract information
        security_context: Optional security context for access control
        
    Returns:
        Contract: Created contract instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Create contract instance
        contract = Contract(contract_data, security_context)
        
        # Save contract with audit logging
        await contract.save(security_context)
        
        return contract
        
    except Exception as e:
        raise ValueError(f"Failed to create contract: {str(e)}")

# Export public interfaces
__all__ = ['Contract', 'create_contract']