"""
Shared constants for the core module.

Version: 1.0
"""

# Token configuration
DEFAULT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Role-based access control constants
ADMIN_ROLES = ["ADMIN"]
MANAGER_ROLES = ["ADMIN", "CONTRACT_MANAGER"]
VIEWER_ROLES = ["ADMIN", "CONTRACT_MANAGER", "REVIEWER"] 