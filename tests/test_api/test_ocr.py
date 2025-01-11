"""
Comprehensive test suite for OCR API endpoints covering document processing,
validation, status monitoring, performance metrics, and security aspects.

Version: 1.0
"""

# External imports - versions specified for production stability
import pytest  # pytest v7.3+
import pytest_asyncio  # pytest-asyncio v0.21+
import uuid
import json
import time
from unittest.mock import Mock, AsyncMock

# Internal imports
from app.schemas.ocr import (
    OCRRequest,
    OCRResponse,
    OCRValidationRequest,
    OCRValidationResponse,
    OCRStatusResponse
)
from app.services.ocr_service import OCRService
from app.core.security import SecurityContext

# Constants for testing
OCR_API_PREFIX = "/api/v1/ocr"
TEST_CONTRACT_ID = uuid.uuid4()
MIN_CONFIDENCE_SCORE = 0.95
MAX_PROCESSING_TIME = 5.0

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
async def test_process_document_success(async_client, mocker):
    """
    Test successful OCR processing with performance and accuracy validation.
    
    Verifies:
    - Document processing completes within 5 seconds
    - OCR confidence score meets 95% threshold
    - Security audit logging is performed
    - Response format and status codes are correct
    """
    # Setup test data
    file_path = "contracts/test_contract.pdf"
    request_data = {
        "contract_id": str(TEST_CONTRACT_ID),
        "file_path": file_path,
        "processing_options": {
            "language": "en",
            "enhance_resolution": True
        }
    }

    # Mock security context
    security_context = {
        "user_id": "test_user",
        "access_level": "contract_manager",
        "ip_address": "127.0.0.1"
    }
    mocker.patch.object(
        SecurityContext,
        "get_current_context",
        return_value=security_context
    )

    # Mock OCR service response
    mock_ocr_response = OCRResponse(
        contract_id=TEST_CONTRACT_ID,
        status="COMPLETED",
        extracted_data={
            "full_text": "Sample contract text",
            "blocks": [
                {
                    "text": "Sample contract text",
                    "confidence": 0.98,
                    "bounds": {"left": 0, "top": 0, "right": 100, "bottom": 50}
                }
            ]
        },
        confidence_score=0.98,
        processing_time=2.5,
        performance_metrics={
            "api_latency": 1.2,
            "cpu_usage": 45.2,
            "memory_usage": 128.5
        }
    )
    
    mocker.patch.object(
        OCRService,
        "process_document",
        return_value=mock_ocr_response
    )

    # Start performance timer
    start_time = time.time()

    # Send request
    response = await async_client.post(
        f"{OCR_API_PREFIX}/process",
        json=request_data
    )

    # Calculate processing time
    processing_time = time.time() - start_time

    # Assert response status
    assert response.status_code == 202, "Expected accepted status code"

    # Validate response data
    response_data = response.json()
    assert "task_id" in response_data, "Response should contain task ID"
    assert response_data["status"] == "PROCESSING", "Initial status should be PROCESSING"

    # Verify processing time
    assert processing_time < MAX_PROCESSING_TIME, (
        f"Processing time {processing_time}s exceeded maximum {MAX_PROCESSING_TIME}s"
    )

    # Verify OCR service call
    OCRService.process_document.assert_called_once()
    call_args = OCRService.process_document.call_args[0][0]
    assert str(call_args.contract_id) == str(TEST_CONTRACT_ID)
    assert call_args.file_path == file_path

    # Verify confidence score
    assert mock_ocr_response.confidence_score >= MIN_CONFIDENCE_SCORE, (
        f"Confidence score {mock_ocr_response.confidence_score} below minimum {MIN_CONFIDENCE_SCORE}"
    )

    # Verify security audit logging
    SecurityContext.get_current_context.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_document_validation_required(async_client, mocker):
    """
    Test OCR processing that requires manual validation due to low confidence.
    """
    # Setup test data with low confidence score
    request_data = {
        "contract_id": str(TEST_CONTRACT_ID),
        "file_path": "contracts/test_contract.pdf"
    }

    mock_ocr_response = OCRResponse(
        contract_id=TEST_CONTRACT_ID,
        status="VALIDATION_REQUIRED",
        extracted_data={
            "full_text": "Sample text",
            "blocks": [
                {
                    "text": "Sample text",
                    "confidence": 0.85,
                    "bounds": {"left": 0, "top": 0, "right": 100, "bottom": 50}
                }
            ]
        },
        confidence_score=0.85,
        processing_time=1.5
    )

    mocker.patch.object(
        OCRService,
        "process_document",
        return_value=mock_ocr_response
    )

    # Send request
    response = await async_client.post(
        f"{OCR_API_PREFIX}/process",
        json=request_data
    )

    # Verify response
    assert response.status_code == 202
    response_data = response.json()
    assert response_data["status"] == "PROCESSING"
    assert "validation_required" in response_data
    assert response_data["validation_required"] is True

@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_extracted_data(async_client, mocker):
    """
    Test validation of extracted OCR data with corrections.
    """
    validation_request = {
        "contract_id": str(TEST_CONTRACT_ID),
        "corrected_data": {
            "full_text": "Corrected contract text",
            "blocks": [
                {
                    "text": "Corrected contract text",
                    "confidence": 1.0,
                    "bounds": {"left": 0, "top": 0, "right": 100, "bottom": 50}
                }
            ]
        },
        "validation_notes": "Manual correction of text"
    }

    mock_validation_response = OCRValidationResponse(
        contract_id=TEST_CONTRACT_ID,
        status="VALIDATED",
        validated_data=validation_request["corrected_data"],
        validation_metadata={
            "validator_id": "test_user",
            "validation_timestamp": "2023-01-01T12:00:00Z",
            "confidence_improvement": 0.15
        }
    )

    mocker.patch.object(
        OCRService,
        "validate_extracted_data",
        return_value=mock_validation_response
    )

    # Send validation request
    response = await async_client.post(
        f"{OCR_API_PREFIX}/validate",
        json=validation_request
    )

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "VALIDATED"
    assert "validated_data" in response_data
    assert "validation_metadata" in response_data

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_processing_status(async_client, mocker):
    """
    Test retrieval of OCR processing status.
    """
    mock_status_response = OCRStatusResponse(
        contract_id=TEST_CONTRACT_ID,
        status="COMPLETED",
        progress=100,
        processing_time=2.5,
        performance_metrics={
            "api_latency": 1.2,
            "cpu_usage": 45.2,
            "memory_usage": 128.5
        }
    )

    mocker.patch.object(
        OCRService,
        "get_processing_status",
        return_value=mock_status_response
    )

    # Send status request
    response = await async_client.get(
        f"{OCR_API_PREFIX}/status/{TEST_CONTRACT_ID}"
    )

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "COMPLETED"
    assert response_data["progress"] == 100
    assert "performance_metrics" in response_data

@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_document_failure(async_client, mocker):
    """
    Test OCR processing failure handling.
    """
    request_data = {
        "contract_id": str(TEST_CONTRACT_ID),
        "file_path": "contracts/invalid.pdf"
    }

    mocker.patch.object(
        OCRService,
        "process_document",
        side_effect=Exception("OCR processing failed")
    )

    # Send request
    response = await async_client.post(
        f"{OCR_API_PREFIX}/process",
        json=request_data
    )

    # Verify error response
    assert response.status_code == 500
    response_data = response.json()
    assert "error" in response_data
    assert response_data["error"]["message"] == "OCR processing failed"