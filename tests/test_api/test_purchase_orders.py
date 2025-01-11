# Version: 1.0
# Purpose: Comprehensive test suite for purchase order API endpoints

# External imports with versions
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
import httpx  # httpx v0.24+
from datetime import datetime, timedelta  # standard library
import json  # standard library
from typing import Dict, List, Any  # standard library
import time  # standard library

# Internal imports
from app.schemas.purchase_order import POCreate, POUpdate, POResponse
from app.models.purchase_order import PO_STATUS_CHOICES, PO_FORMAT_CHOICES

# Test constants
TEST_CONTRACT_ID = "test_contract_123"
VALID_PO_DATA = {
    "template_type": "standard",
    "output_format": "pdf",
    "po_data": {
        "vendor_name": "Test Vendor",
        "total_amount": 1000.00,
        "line_items": [
            {
                "description": "Test Item",
                "quantity": 1,
                "unit_price": 1000.00
            }
        ]
    },
    "include_logo": True,
    "digital_signature": True,
    "send_notification": False
}
TEST_TEMPLATES = ["standard", "detailed", "simple"]
OUTPUT_FORMATS = ["pdf", "docx"]

# Test fixtures
@pytest.fixture
def valid_po_create_data() -> Dict[str, Any]:
    """Returns valid PO creation data."""
    return {
        **VALID_PO_DATA,
        "contract_id": TEST_CONTRACT_ID,
        "preferences": {
            "priority": "normal",
            "language": "en"
        }
    }

@pytest.fixture
def invalid_po_data() -> Dict[str, Any]:
    """Returns invalid PO data for negative testing."""
    return {
        "template_type": "invalid",
        "output_format": "invalid",
        "po_data": {},
        "contract_id": "invalid"
    }

# Test cases
@pytest.mark.asyncio
@pytest.mark.api
async def test_create_po_success(async_client: httpx.AsyncClient, admin_token: Dict[str, str]):
    """Tests successful creation of a purchase order with comprehensive validation."""
    # Arrange
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    data = valid_po_create_data()
    
    # Act
    start_time = time.time()
    response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=data,
        headers=headers
    )
    processing_time = time.time() - start_time
    
    # Assert - Status and timing
    assert response.status_code == 201
    assert processing_time < 5.0, "PO generation exceeded 5 second SLA"
    
    # Assert - Response structure
    po_data = response.json()
    assert isinstance(po_data, dict)
    assert all(key in po_data for key in [
        "id", "po_number", "status", "contract_id", "generated_by",
        "template_type", "output_format", "file_path", "created_at"
    ])
    
    # Assert - Data validation
    assert po_data["contract_id"] == TEST_CONTRACT_ID
    assert po_data["template_type"] == data["template_type"]
    assert po_data["output_format"] == data["output_format"]
    assert po_data["status"] in PO_STATUS_CHOICES
    assert po_data["include_logo"] == data["include_logo"]
    assert po_data["digital_signature"] == data["digital_signature"]

@pytest.mark.asyncio
@pytest.mark.api
async def test_create_po_invalid_data(async_client: httpx.AsyncClient, admin_token: Dict[str, str]):
    """Tests PO creation with invalid data to verify validation."""
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    data = invalid_po_data()
    
    response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=data,
        headers=headers
    )
    
    assert response.status_code == 422
    error_data = response.json()
    assert "detail" in error_data
    assert isinstance(error_data["detail"], list)

@pytest.mark.asyncio
@pytest.mark.api
async def test_create_po_unauthorized(async_client: httpx.AsyncClient):
    """Tests PO creation without authorization."""
    data = valid_po_create_data()
    
    response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=data
    )
    
    assert response.status_code == 401

@pytest.mark.asyncio
@pytest.mark.api
async def test_create_po_forbidden(async_client: httpx.AsyncClient, basic_user_token: Dict[str, str]):
    """Tests PO creation with insufficient permissions."""
    headers = {"Authorization": f"Bearer {basic_user_token['access_token']}"}
    data = valid_po_create_data()
    
    response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=data,
        headers=headers
    )
    
    assert response.status_code == 403

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.parametrize("template_type", TEST_TEMPLATES)
@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
async def test_po_template_formats(
    async_client: httpx.AsyncClient,
    admin_token: Dict[str, str],
    template_type: str,
    output_format: str
):
    """Tests PO generation with different template types and output formats."""
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    data = valid_po_create_data()
    data["template_type"] = template_type
    data["output_format"] = output_format
    
    response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=data,
        headers=headers
    )
    
    assert response.status_code == 201
    po_data = response.json()
    assert po_data["template_type"] == template_type
    assert po_data["output_format"] == output_format
    assert po_data["file_path"].endswith(f".{output_format}")

@pytest.mark.asyncio
@pytest.mark.api
async def test_batch_po_creation(async_client: httpx.AsyncClient, admin_token: Dict[str, str]):
    """Tests batch creation of purchase orders with performance monitoring."""
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    batch_size = 5
    batch_data = [valid_po_create_data() for _ in range(batch_size)]
    
    start_time = time.time()
    responses = await asyncio.gather(*[
        async_client.post(
            "/api/v1/purchase-orders/",
            json=data,
            headers=headers
        ) for data in batch_data
    ])
    total_time = time.time() - start_time
    
    # Assert timing
    assert total_time < 5.0 * batch_size, "Batch processing exceeded time limit"
    
    # Assert responses
    assert all(r.status_code == 201 for r in responses)
    po_numbers = [r.json()["po_number"] for r in responses]
    assert len(set(po_numbers)) == batch_size, "Duplicate PO numbers detected"

@pytest.mark.asyncio
@pytest.mark.api
async def test_po_status_update(async_client: httpx.AsyncClient, admin_token: Dict[str, str]):
    """Tests purchase order status updates."""
    # First create a PO
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    create_response = await async_client.post(
        "/api/v1/purchase-orders/",
        json=valid_po_create_data(),
        headers=headers
    )
    assert create_response.status_code == 201
    po_id = create_response.json()["id"]
    
    # Test status update
    update_data = {"status": "sent"}
    update_response = await async_client.patch(
        f"/api/v1/purchase-orders/{po_id}/status",
        json=update_data,
        headers=headers
    )
    
    assert update_response.status_code == 200
    updated_po = update_response.json()
    assert updated_po["status"] == "sent"
    assert "sent_at" in updated_po and updated_po["sent_at"] is not None

@pytest.mark.asyncio
@pytest.mark.api
async def test_po_retrieval(async_client: httpx.AsyncClient, admin_token: Dict[str, str]):
    """Tests purchase order retrieval with filtering and pagination."""
    headers = {"Authorization": f"Bearer {admin_token['access_token']}"}
    
    # Create test POs
    for _ in range(3):
        await async_client.post(
            "/api/v1/purchase-orders/",
            json=valid_po_create_data(),
            headers=headers
        )
    
    # Test retrieval with filters
    response = await async_client.get(
        "/api/v1/purchase-orders/",
        params={
            "status": "generated",
            "page": 1,
            "limit": 10
        },
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["items"], list)
    assert all(po["status"] == "generated" for po in data["items"])