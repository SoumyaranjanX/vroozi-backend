"""
FastAPI v1 API router configuration module.

Version: 1.0
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.contracts import router as contracts_router
from app.api.v1.endpoints.purchase_orders import router as po_router
from app.api.v1.endpoints.ocr import router as ocr_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.activities import router as activities_router

# Initialize main API router
api_router = APIRouter()

# Include routers for different endpoints
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    contracts_router,
    prefix="/contracts",
    tags=["Contracts"]
)

api_router.include_router(
    po_router,
    prefix="/purchase-orders",
    tags=["Purchase Orders"]
)

api_router.include_router(
    ocr_router,
    prefix="/ocr",
    tags=["OCR Processing"]
)

api_router.include_router(
    users_router,
    prefix="/users",
    tags=["Users"]
)

api_router.include_router(
    activities_router,
    prefix="/activities",
    tags=["Activities"]
)

# Export router
__all__ = ["api_router"]
