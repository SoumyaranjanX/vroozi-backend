"""
Enhanced audit log model implementation for comprehensive system activity tracking,
security monitoring, and compliance reporting with SOC 2 support.

Version: 1.0
"""

# External imports with versions
from datetime import datetime  # built-in
from typing import Dict, Optional, Any, List, Union  # built-in
from bson import ObjectId  # bson v1.23.0
import json  # built-in

# Internal imports
from app.db.mongodb import get_database
from app.models.user import User

# Global constants for audit configuration
AUDIT_LOG_COLLECTION = "audit_logs"
RETENTION_DAYS = 30
BATCH_SIZE = 1000
MAX_CHANGES_SIZE = 1048576  # 1MB limit for changes data

class AuditLog:
    """
    Enhanced audit log model for tracking system events and changes with 
    improved security and compliance features.
    """
    
    def __init__(self, log_data: Dict[str, Any]):
        """
        Initializes audit log entry with enhanced validation and security context.
        
        Args:
            log_data: Dictionary containing audit log information
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        required_fields = {'entity_type', 'entity_id', 'action', 'user_id'}
        if missing := required_fields - set(log_data.keys()):
            raise ValueError(f"Missing required fields: {missing}")

        # Initialize core properties
        self._id = ObjectId(log_data.get('_id')) if '_id' in log_data else ObjectId()
        self.entity_type = log_data['entity_type']
        self.entity_id = log_data['entity_id']
        self.action = log_data['action']
        self.user_id = log_data['user_id']
        self.user_email = log_data.get('user_email')
        self.changes = log_data.get('changes', {})
        self.timestamp = log_data.get('timestamp', datetime.utcnow())
        
        # Security context
        self.ip_address = log_data.get('ip_address')
        self.user_agent = log_data.get('user_agent')
        self.security_context = log_data.get('security_context', {})
        self.correlation_id = log_data.get('correlation_id')
        self.is_sensitive = log_data.get('is_sensitive', False)

        # Validate changes data size
        if len(json.dumps(self.changes)) > MAX_CHANGES_SIZE:
            raise ValueError(f"Changes data exceeds maximum size of {MAX_CHANGES_SIZE} bytes")

    async def save(self) -> Dict:
        """
        Persists audit log entry with enhanced error handling and validation.
        
        Returns:
            Dict: Saved audit log data with confirmation
            
        Raises:
            RuntimeError: If database operation fails
        """
        try:
            db = await get_database()
            
            # Prepare audit data
            audit_data = self.to_dict()
            
            # Insert audit log
            result = await db[AUDIT_LOG_COLLECTION].insert_one(audit_data)
            
            if not result.inserted_id:
                raise RuntimeError("Failed to save audit log")
                
            audit_data['_id'] = str(result.inserted_id)
            return {
                'status': 'success',
                'audit_log': audit_data,
                'message': 'Audit log created successfully'
            }
            
        except Exception as e:
            raise RuntimeError(f"Error saving audit log: {str(e)}")

    def to_dict(self) -> Dict:
        """
        Converts audit log to dictionary with enhanced formatting and security.
        
        Returns:
            Dict: Sanitized audit log data dictionary
        """
        return {
            '_id': str(self._id),
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'changes': self.changes,
            'timestamp': self.timestamp,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'security_context': self.security_context,
            'correlation_id': self.correlation_id,
            'is_sensitive': self.is_sensitive
        }

async def create_audit_log(
    entity_type: str,
    entity_id: str,
    action: str,
    user_id: str,
    changes: Dict[str, Any],
    ip_address: Optional[str] = None,
    is_sensitive: Optional[bool] = False
) -> AuditLog:
    """
    Creates new audit log entry with enhanced security and validation.
    
    Args:
        entity_type: Type of entity being audited
        entity_id: Identifier of the audited entity
        action: Action performed
        user_id: ID of user performing the action
        changes: Dictionary of changes made
        ip_address: Optional IP address of the request
        is_sensitive: Flag for sensitive data handling
        
    Returns:
        AuditLog: Created and validated audit log instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Create audit log data
        log_data = {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'action': action,
            'user_id': user_id,
            'changes': changes,
            'ip_address': ip_address,
            'is_sensitive': is_sensitive,
            'timestamp': datetime.utcnow()
        }
        
        # Create and save audit log
        audit_log = AuditLog(log_data)
        await audit_log.save()
        
        return audit_log
        
    except Exception as e:
        raise ValueError(f"Failed to create audit log: {str(e)}")

async def get_audit_logs(
    filters: Dict[str, Any],
    skip: int = 0,
    limit: int = 100,
    sort: Optional[Dict] = None,
    include_sensitive: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Retrieves audit logs with enhanced filtering and pagination.
    
    Args:
        filters: Query filters to apply
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort: Sort criteria
        include_sensitive: Whether to include sensitive logs
        
    Returns:
        Dict[str, Any]: Paginated audit logs with metadata
    """
    try:
        db = await get_database()
        
        # Build query
        query = filters.copy()
        if not include_sensitive:
            query['is_sensitive'] = False
            
        # Set default sort if not provided
        if not sort:
            sort = {'timestamp': -1}
            
        # Execute query with pagination
        cursor = db[AUDIT_LOG_COLLECTION].find(query)
        total = await db[AUDIT_LOG_COLLECTION].count_documents(query)
        
        # Apply pagination and sort
        cursor = cursor.skip(skip).limit(limit).sort(list(sort.items()))
        
        # Convert cursor to list
        audit_logs = await cursor.to_list(length=limit)
        
        return {
            'audit_logs': [AuditLog(log).to_dict() for log in audit_logs],
            'total': total,
            'skip': skip,
            'limit': limit,
            'has_more': total > (skip + limit)
        }
        
    except Exception as e:
        raise RuntimeError(f"Error retrieving audit logs: {str(e)}")

async def cleanup_old_logs(
    batch_size: Optional[int] = BATCH_SIZE,
    dry_run: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Removes audit logs with enhanced batch processing and verification.
    
    Args:
        batch_size: Size of deletion batches
        dry_run: If True, only simulate deletion
        
    Returns:
        Dict[str, Any]: Cleanup operation results and statistics
    """
    try:
        db = await get_database()
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        
        # Build query for old logs
        query = {
            'timestamp': {'$lt': cutoff_date},
            'is_sensitive': False  # Never auto-delete sensitive logs
        }
        
        # Count logs to be deleted
        total_logs = await db[AUDIT_LOG_COLLECTION].count_documents(query)
        
        if dry_run:
            return {
                'status': 'simulated',
                'logs_to_delete': total_logs,
                'message': f"Would delete {total_logs} logs"
            }
            
        # Process deletion in batches
        deleted_count = 0
        while deleted_count < total_logs:
            result = await db[AUDIT_LOG_COLLECTION].delete_many(
                query,
                limit=batch_size
            )
            deleted_count += result.deleted_count
            
        return {
            'status': 'success',
            'total_deleted': deleted_count,
            'cutoff_date': cutoff_date,
            'message': f"Successfully deleted {deleted_count} logs"
        }
        
    except Exception as e:
        raise RuntimeError(f"Error during log cleanup: {str(e)}")

# Export public interfaces
__all__ = [
    'AuditLog',
    'create_audit_log',
    'get_audit_logs',
    'cleanup_old_logs'
]