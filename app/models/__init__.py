"""
Models package initializer that exports all MongoDB document models for the contract processing system.
Provides a centralized point for importing models throughout the application while maintaining 
security boundaries and efficient data access patterns.

Version: 1.0
"""

# Define public exports for the models package
# This controls which models are available when importing from app.models
__all__ = [
    "User",           # User model for authentication and RBAC
    "Contract",       # Contract processing and validation model
    "PurchaseOrder",  # Purchase order generation model
    "AuditLog"        # Audit logging model
]