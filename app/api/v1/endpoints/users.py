# External imports with versions for production stability
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status  # v0.95.0
from fastapi.security import OAuth2PasswordBearer  # v0.95.0
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import hashlib
from ipaddress import ip_address
import time
from bson import ObjectId

# Internal imports
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserInDB
from app.core.security import get_password_hash
from app.core.logging import AuditLogger
from app.core.constants import ADMIN_ROLES, MANAGER_ROLES, VIEWER_ROLES
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.mongodb import get_database

# Initialize router with prefix and tags
router = APIRouter(tags=["users"])

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiting settings
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds

# Initialize rate limiter and audit logger
rate_limiter = Limiter(key_func=get_remote_address)
audit_logger = AuditLogger()

async def verify_admin_access(request: Request) -> bool:
    """
    Verifies if the current user has admin privileges
    """
    current_user = request.state.user
    if current_user.role not in ADMIN_ROLES:
        await audit_logger.log_operation(
            entity_type="users",
            action="admin_access_attempt",
            user_id=str(current_user.id),
            details={"role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required"
        )
    return True

@router.get("/", response_model=List[UserInDB])
async def get_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
) -> List[UserInDB]:
    """
    Retrieve paginated list of users with security logging and data masking
    """
    current_user = request.state.user
    
    # Verify manager access
    if current_user.role not in MANAGER_ROLES:
        await audit_logger.log_operation(
            entity_type="users",
            action="list_users_attempt",
            user_id=str(current_user.id),
            details={"role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    db = await get_database()
    users = await db["users"].find().skip(skip).limit(limit).to_list(length=limit)
    
    # Mask sensitive data for non-admin users
    if current_user.role not in ADMIN_ROLES:
        for user in users:
            user.email = f"{user.email[:3]}...@{user.email.split('@')[1]}"
            user.last_failed_ip = None
    
    await audit_logger.log_operation(
        entity_type="users",
        action="list_users",
        user_id=str(current_user.id),
        details={"skip": skip, "limit": limit}
    )
    
    return users

@router.post("/", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user: UserCreate
) -> UserInDB:
    """
    Create new user with security checks and audit logging
    """
    current_user = request.state.user
    await verify_admin_access(request)
    
    db = await get_database()
    
    # Check if email already exists
    if await db["users"].find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with security tracking fields
    user_data = UserInDB(
        **user.dict(),
        hashed_password=get_password_hash(user.password),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        password_changed_at=datetime.utcnow()
    )
    
    result = await db["users"].insert_one(user_data.dict())
    
    await audit_logger.log_operation(
        entity_type="users",
        action="create_user",
        user_id=str(current_user.id),
        details={
            "new_user_id": str(result.inserted_id),
            "user_role": user.role
        }
    )
    
    return user_data

@router.put("/", response_model=Dict[str, str])
async def update_user(
    request: Request,
    user_update: UserUpdate
) -> Dict[str, str]:
    """
    Update user with security validation and audit logging
    """
    try:
        current_user = request.state.user
        logger.debug(f"Update data received: {user_update.dict()}")
        
        db = await get_database()

        user_id=str(current_user.id)
        
        # Verify permissions
        if current_user.role not in ADMIN_ROLES:
            await audit_logger.log_operation(
                entity_type="users",
                action="update_user_attempt",
                user_id=str(current_user.id),
                details={
                    "target_user_id": user_id,
                    "role": current_user.role
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        existing_user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.debug(f"Existing user data: {existing_user}")
        
        # Only include fields that were actually provided in the update
        update_data = {k: v for k, v in user_update.dict(exclude_unset=True).items() if v is not None}
        logger.debug(f"Update data after filtering: {update_data}")
        
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
            update_data["password_changed_at"] = datetime.utcnow()
        
        # Only convert role to uppercase if it's provided
        if "role" in update_data:
            update_data["role"] = update_data["role"].upper()
            logger.debug(f"Role after conversion: {update_data['role']}")
        
        update_data["updated_at"] = datetime.utcnow()
        
        logger.debug(f"Final update data: {update_data}")
        
        # Use findOneAndUpdate to get the updated document in a single operation
        updated_user = await db["users"].find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True  # Return the updated document
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found after update"
            )
        
        logger.debug(f"Updated user from DB: {updated_user}")
        
        # Convert _id to id and return only necessary fields
        user_dict = {
            "email": updated_user["email"],
            "first_name": updated_user["first_name"],
            "last_name": updated_user["last_name"]
        }
        
        # Log the successful update
        await audit_logger.log_operation(
            entity_type="users",
            action="update_user",
            user_id=str(current_user.id),
            details={
                "updated_user_id": user_id,
                "changes": {k: "..." if k == "password" else v for k, v in update_data.items()}
            }
        )
        
        return user_dict
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: str
) -> None:
    """
    Delete user with security checks and audit logging
    """
    current_user = request.state.user
    await verify_admin_access(request)
    
    db = await get_database()
    result = await db["users"].delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await audit_logger.log_operation(
        entity_type="users",
        action="delete_user",
        user_id=str(current_user.id),
        details={"deleted_user_id": user_id}
    )

@router.get("/me", response_model=UserInDB)
async def get_current_user_profile(request: Request) -> UserInDB:
    """
    Get current user's profile with security logging
    """
    current_user = request.state.user
    await audit_logger.log_operation(
        entity_type="users",
        action="view_profile",
        user_id=str(current_user.id)
    )
    return current_user