"""
Test suite for validation utility functions in the Contract Processing System.
Tests file type validation, data format validation, business rules, and security aspects.

Version: 1.0
"""

# External imports with versions
import pytest  # pytest v7.3+
import magic  # python-magic v0.4.27
from datetime import datetime, timedelta
import json

# Internal imports
from app.utils.validators import (
    validate_file_type,
    validate_file_size,
    validate_po_number,
    validate_contract_number,
    validate_extracted_data,
    validate_po_data
)
from app.core.exceptions import ValidationException
from app.core.security import SecurityContext

# Test constants
VALID_FILE_CONTENTS = {
    'pdf': b'%PDF-1.4\n',
    'docx': b'PK\x03\x04',
    'jpeg': b'\xFF\xD8\xFF',
    'png': b'\x89PNG\r\n\x1a\n',
    'tiff': b'II*\x00'
}

INVALID_FILE_CONTENTS = {
    'exe': b'MZ\x90\x00',
    'zip': b'PK\x03\x04\x14\x00',
    'html': b'<!DOCTYPE html>'
}

VALID_EXTRACTED_DATA = {
    "contract_number": "CTR-123456-ABCD",
    "parties": [
        {"name": "Company A", "role": "Vendor"},
        {"name": "Company B", "role": "Client"}
    ],
    "effective_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
    "expiration_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
    "total_value": 10000.00,
    "payment_terms": "Net 30"
}

@pytest.fixture
def security_context():
    """Fixture for security context with valid credentials."""
    return SecurityContext(
        user_id="test_user",
        client_ip="127.0.0.1",
        request_path="/api/v1/contracts",
        request_method="POST"
    )

class TestFileValidation:
    """Test suite for file validation functions."""

    @pytest.mark.parametrize("file_content,mime_type", [
        (VALID_FILE_CONTENTS['pdf'], 'application/pdf'),
        (VALID_FILE_CONTENTS['docx'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        (VALID_FILE_CONTENTS['jpeg'], 'image/jpeg'),
        (VALID_FILE_CONTENTS['png'], 'image/png'),
        (VALID_FILE_CONTENTS['tiff'], 'image/tiff')
    ])
    def test_validate_file_type_valid(self, file_content, mime_type, security_context):
        """Test file type validation with valid file types."""
        assert validate_file_type(file_content) is True

    @pytest.mark.parametrize("file_content,mime_type", [
        (INVALID_FILE_CONTENTS['exe'], 'application/x-msdownload'),
        (INVALID_FILE_CONTENTS['zip'], 'application/zip'),
        (INVALID_FILE_CONTENTS['html'], 'text/html')
    ])
    def test_validate_file_type_invalid(self, file_content, mime_type, security_context):
        """Test file type validation with invalid file types."""
        with pytest.raises(ValidationException) as exc_info:
            validate_file_type(file_content)
        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value)

    def test_validate_file_size_exceeded(self, security_context):
        """Test file size validation with oversized file."""
        large_file = b'0' * (26 * 1024 * 1024)  # 26MB
        with pytest.raises(ValidationException) as exc_info:
            validate_file_size(large_file)
        assert exc_info.value.status_code == 400
        assert "File size exceeds maximum limit" in str(exc_info.value)

class TestDataValidation:
    """Test suite for data validation functions."""

    def test_validate_extracted_data_valid(self, security_context):
        """Test validation of valid extracted contract data."""
        assert validate_extracted_data(VALID_EXTRACTED_DATA) is True

    @pytest.mark.parametrize("field,invalid_value", [
        ("contract_number", "INVALID-123"),
        ("parties", [{"name": "Company A"}]),  # Missing role
        ("effective_date", "2023-13-45"),  # Invalid date
        ("total_value", -1000),  # Negative value
        ("payment_terms", "<script>alert('xss')</script>")  # XSS attempt
    ])
    def test_validate_extracted_data_invalid(self, field, invalid_value, security_context):
        """Test validation with invalid extracted data fields."""
        invalid_data = VALID_EXTRACTED_DATA.copy()
        invalid_data[field] = invalid_value
        
        with pytest.raises(ValidationException) as exc_info:
            validate_extracted_data(invalid_data)
        assert exc_info.value.status_code == 400

    @pytest.mark.parametrize("po_number", [
        "PO-123456-ABCD",
        "PO-999999-XYZ9"
    ])
    def test_validate_po_number_valid(self, po_number, security_context):
        """Test validation of valid PO numbers."""
        assert validate_po_number(po_number) is True

    @pytest.mark.parametrize("invalid_po", [
        "PO123456ABCD",  # Missing hyphens
        "PO-12345-ABCD",  # Wrong number format
        "XX-123456-ABCD",  # Wrong prefix
        "PO-123456-abcd"  # Lowercase letters
    ])
    def test_validate_po_number_invalid(self, invalid_po, security_context):
        """Test validation of invalid PO numbers."""
        with pytest.raises(ValidationException) as exc_info:
            validate_po_number(invalid_po)
        assert exc_info.value.status_code == 400
        assert "Invalid PO number format" in str(exc_info.value)

class TestSecurityValidation:
    """Test suite for security-related validations."""

    def test_validate_with_invalid_security_context(self):
        """Test validation with invalid security context."""
        invalid_context = SecurityContext(
            user_id="",
            client_ip="invalid_ip",
            request_path="",
            request_method=""
        )
        
        with pytest.raises(ValidationException) as exc_info:
            validate_file_type(VALID_FILE_CONTENTS['pdf'], security_context=invalid_context)
        assert exc_info.value.status_code == 401

    def test_validate_with_rate_limit_exceeded(self, security_context):
        """Test validation when rate limit is exceeded."""
        # Simulate rate limit exceeded
        for _ in range(101):  # Exceed 100 requests/minute limit
            validate_file_type(VALID_FILE_CONTENTS['pdf'])
            
        with pytest.raises(ValidationException) as exc_info:
            validate_file_type(VALID_FILE_CONTENTS['pdf'])
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_validate_with_xss_attempt(self, security_context):
        """Test validation with XSS injection attempt."""
        malicious_data = VALID_EXTRACTED_DATA.copy()
        malicious_data["payment_terms"] = "<script>alert('xss')</script>"
        
        result = validate_extracted_data(malicious_data)
        assert result is True
        assert "<script>" not in malicious_data["payment_terms"]

if __name__ == "__main__":
    pytest.main(["-v"])