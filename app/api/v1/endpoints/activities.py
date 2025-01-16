"""
FastAPI router endpoints for activity tracking implementing secure activity logging
with comprehensive error handling and performance monitoring.

Version: 1.0
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.audit_log import get_audit_logs
from app.core.security import RequiresRole
from app.schemas.activity import Activity, ActivityMetadata
import logging

# Initialize router with prefix and tags
router = APIRouter(tags=['activities'])

# Configure logging
logger = logging.getLogger(__name__)

def get_activity_description(log: Dict, metadata: ActivityMetadata) -> str:
    """Generate a user-friendly description for the activity"""
    base_description = log.get("changes", {}).get("description")
    if base_description:
        return base_description

    action = log.get("action", "").lower()
    entity_type = metadata.entityType.replace("_", " ").title() if metadata.entityType else "Item"
    status = metadata.status
    entity_id = metadata.displayId or metadata.entityId

    if action == "process_contract":
        return f"Started processing {entity_type} #{entity_id}"
    elif action == "validation_update":
        return f"Updated {entity_type} #{entity_id} validation status to {status}"
    elif action == "save" and status:
        return f"{entity_type} #{entity_id} status changed to {status}"
    elif action == "create":
        return f"Created new {entity_type} #{entity_id}"
    elif action == "update":
        return f"Updated {entity_type} #{entity_id}"
    else:
        return f"{action.replace('_', ' ').title()} {entity_type} #{entity_id}"

def get_display_id(entity_id: str, entity_type: str) -> str:
    """Generate a display-friendly ID based on entity type"""
    if not entity_id:
        return None
        
    # Take the last 6 characters of the ID for display
    short_id = entity_id[-6:] if len(entity_id) > 6 else entity_id
    
    if entity_type == "contract":
        return f"CNT-{short_id}"
    elif entity_type == "purchase_order":
        return f"PO-{short_id}"
    return short_id

# Handler for both paths (with and without trailing slash)
@router.get("")  # No trailing slash
@router.get("/")  # With trailing slash
async def get_activities(
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER', 'USER']))
) -> List[Dict]:
    """
    Get recent activities for the current user.
    Activities are derived from audit logs and include:
    - Contract uploads and processing
    - Purchase order creation and updates
    - System events
    
    Returns a list of activities with UI metadata for professional rendering.
    """
    try:
        # Get audit logs and transform them into activities
        audit_result = await get_audit_logs(
            filters={},  # Get all logs
            limit=50,    # Limit to 50 most recent
            sort={"timestamp": -1}  # Sort by timestamp descending
        )
        
        activities = []
        for log in audit_result["audit_logs"]:
            # Determine activity type and entity ID
            activity_type = "system"
            entity_id = str(log.get("entity_id")) if log.get("entity_id") else None
            entity_type = log.get("entity_type", "").lower()
            
            if "contract" in entity_type:
                activity_type = "contract"
            elif "purchase_order" in entity_type:
                activity_type = "purchase_order"

            # Get user name from either user_email or user_name, fallback to "System"
            user_name = log.get("user_email") or log.get("user_name") or "System"
            
            # Create activity metadata with specific IDs
            metadata = ActivityMetadata(
                entityId=entity_id,
                entityType=entity_type,
                status=log.get("changes", {}).get("status"),
                contractId=entity_id if activity_type == "contract" else None,
                purchaseOrderId=entity_id if activity_type == "purchase_order" else None,
                displayId=get_display_id(entity_id, activity_type)
            )

            # Create activity with enhanced description
            activity = Activity(
                id=str(log.get("_id")),
                type=activity_type,
                action=log.get("action", "unknown"),
                description=get_activity_description(log, metadata),
                timestamp=log.get("timestamp"),
                userId=str(log.get("user_id")),
                userName=user_name,
                metadata=metadata
            )

            # Add activity with UI metadata
            activities.append({
                **activity.dict(),
                "ui": activity.get_ui_metadata()
            })
            
        return activities
        
    except Exception as e:
        logger.error(f"Failed to fetch activities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch activities: {str(e)}"
        ) 