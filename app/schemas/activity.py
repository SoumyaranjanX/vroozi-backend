from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class ActivityMetadata(BaseModel):
    entityId: Optional[str] = Field(None, description="Unique identifier of the related entity")
    entityType: Optional[str] = Field(None, description="Type of the related entity (e.g., contract, purchase_order)")
    status: Optional[str] = Field(None, description="Current status of the entity")
    icon: Optional[str] = Field(None, description="Icon name for the activity type")
    color: Optional[str] = Field(None, description="Color scheme for the activity status")
    contractId: Optional[str] = Field(None, description="Contract ID if this activity is related to a contract")
    purchaseOrderId: Optional[str] = Field(None, description="Purchase Order ID if this activity is related to a PO")
    displayId: Optional[str] = Field(None, description="Display-friendly ID for the entity")

class Activity(BaseModel):
    id: str = Field(..., description="Unique identifier of the activity")
    type: str = Field(..., description="Type of activity: contract, purchase_order, or system")
    action: str = Field(..., description="The action performed (e.g., save, process_contract, validation_update)")
    description: str = Field(
        default="No description",
        description="Human-readable description of the activity"
    )
    timestamp: datetime = Field(..., description="When the activity occurred")
    userId: str = Field(..., description="ID of the user who performed the action")
    userName: str = Field(
        default="System",
        description="Name or email of the user who performed the action"
    )
    metadata: Optional[ActivityMetadata] = Field(
        default_factory=ActivityMetadata,
        description="Additional information about the activity"
    )

    def get_display_action(self) -> str:
        """Returns a user-friendly display version of the action"""
        action_map = {
            "save": "Saved",
            "process_contract": "Started Contract Processing",
            "validation_update": "Updated Validation Status",
            "create": "Created",
            "upload": "Uploaded",
            "delete": "Deleted",
            "update": "Updated"
        }
        return action_map.get(self.action, self.action.replace("_", " ").title())

    def get_display_status(self) -> str:
        """Returns a user-friendly display version of the status"""
        if not self.metadata or not self.metadata.status:
            return ""
            
        status_map = {
            "PENDING": "Pending",
            "PROCESSING": "Processing",
            "VALIDATION_REQUIRED": "Validation Required",
            "VALIDATED": "Validated",
            "REJECTED": "Rejected",
            "ERROR": "Error",
            "draft": "Draft",
            "final": "Final"
        }
        return status_map.get(self.metadata.status, self.metadata.status)

    def get_ui_metadata(self) -> Dict:
        """Returns UI-specific metadata for rendering"""
        # Icon mapping based on type and action
        icon_map = {
            "contract": {
                "default": "description",
                "process_contract": "sync",
                "validation_update": "check_circle",
                "upload": "upload_file"
            },
            "purchase_order": {
                "default": "shopping_cart",
                "create": "add_shopping_cart",
                "update": "edit"
            },
            "system": {
                "default": "settings",
                "error": "error"
            }
        }

        # Color mapping based on status
        color_map = {
            "PENDING": "warning",
            "PROCESSING": "info",
            "VALIDATION_REQUIRED": "warning",
            "VALIDATED": "success",
            "REJECTED": "error",
            "ERROR": "error",
            "draft": "default",
            "final": "success"
        }

        # Get icon based on type and action
        type_icons = icon_map.get(self.type, icon_map["system"])
        icon = type_icons.get(self.action, type_icons["default"])

        # Get color based on status
        status = self.metadata.status if self.metadata else None
        color = color_map.get(status, "default") if status else "default"

        # Get entity-specific IDs
        entity_id = None
        if self.metadata:
            if self.type == "contract":
                entity_id = self.metadata.contractId or self.metadata.entityId
            elif self.type == "purchase_order":
                entity_id = self.metadata.purchaseOrderId or self.metadata.entityId

        return {
            "icon": icon,
            "color": color,
            "displayAction": self.get_display_action(),
            "displayStatus": self.get_display_status(),
            "displayTime": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "isSystem": self.userName == "System",
            "entityType": self.metadata.entityType.replace("_", " ").title() if self.metadata and self.metadata.entityType else None,
            "entityId": entity_id,
            "displayId": self.metadata.displayId if self.metadata else None
        } 