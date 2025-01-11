"""
Base model class for MongoDB documents.

Version: 1.0
"""

from datetime import datetime
from typing import Dict, Any
from bson import ObjectId

class BaseDocument:
    """Base document class providing common functionality for MongoDB models."""
    
    def __init__(self, data: Dict[str, Any]):
        self._id: ObjectId = data.get('_id', ObjectId())
        self.created_at: datetime = data.get('created_at', datetime.utcnow())
        self.updated_at: datetime = data.get('updated_at', datetime.utcnow())
        self._data: Dict[str, Any] = data
        self._validate_data()
    
    def _validate_data(self) -> None:
        """Validates document data structure and required fields."""
        required_fields = {'_id', 'created_at', 'updated_at'}
        missing_fields = required_fields - set(self._data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts document to dictionary format with proper type handling."""
        result = self._data.copy()
        if '_id' in result:
            result['_id'] = str(result['_id'])
        for field in ['created_at', 'updated_at']:
            if field in result and isinstance(result[field], datetime):
                result[field] = result[field].isoformat()
        return result 