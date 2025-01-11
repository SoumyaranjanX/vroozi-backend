"""
Validators module for Contract Processing System.
Implements comprehensive validation functions for contract processing and purchase order generation.

Version: 1.0
"""

# External imports with versions
import re  # built-in
import magic  # python-magic v0.4.27
from datetime import datetime  # built-in
import bleach  # v5.0.1

# Internal imports
from app.core.exceptions import ValidationException
from app.core.security import SecurityContext

# Global constants for validation rules
ALLOWED_FILE_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
    'image/tiff'
]

# Maximum file size (25MB)
MAX_FILE_SIZE = 25 * 1024 * 1024

# Validation patterns
PO_NUMBER_PATTERN = r'^PO-\d{6}-[A-Z0-9]{4}$'
CONTRACT_NUMBER_PATTERN = r'^CTR-\d{6}-[A-Z0-9]{4}$'

# Rate limiting settings
VALIDATION_RATE_LIMIT = 100
VALIDATION_WINDOW = 3600  # 1 hour

@SecurityContext.validate_request
def validate_file_type(file_content: bytes) -> bool:
    """
    Validates if uploaded file type is supported using secure MIME type detection.
    
    Args:
        file_content: Binary content of the uploaded file
        
    Returns:
        bool: True if file type is supported
        
    Raises:
        ValidationException: If file type validation fails
    """
    try:
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise ValidationException(
                message="File size exceeds maximum limit",
                error_code="VAL_001",
                details={"max_size": MAX_FILE_SIZE},
                status_code=400
            )

        # Detect MIME type using python-magic
        mime = magic.Magic(mime=True)
        detected_type = mime.from_buffer(file_content)

        # Verify file type signature
        if detected_type not in ALLOWED_FILE_TYPES:
            raise ValidationException(
                message="Unsupported file type",
                error_code="VAL_002",
                details={
                    "detected_type": detected_type,
                    "allowed_types": ALLOWED_FILE_TYPES
                },
                status_code=400
            )

        return True

    except ValidationException:
        raise
    except Exception as e:
        raise ValidationException(
            message="File validation failed",
            error_code="VAL_003",
            details={"error": str(e)},
            status_code=500
        )

@SecurityContext.validate_request
def validate_extracted_data(extracted_data: dict) -> bool:
    """
    Validates structure and content of OCR extracted data with enhanced security.
    
    Args:
        extracted_data: Dictionary containing extracted contract data
        
    Returns:
        bool: True if data structure is valid
        
    Raises:
        ValidationException: If data validation fails
    """
    try:
        # Required fields for contract data
        required_fields = {
            "contract_number": str,
            "parties": list,
            "effective_date": str,
            "expiration_date": str,
            "total_value": float,
            "payment_terms": str
        }

        # Validate required fields and their types
        for field, field_type in required_fields.items():
            if field not in extracted_data:
                raise ValidationException(
                    message=f"Missing required field: {field}",
                    error_code="VAL_004",
                    details={"field": field},
                    status_code=400
                )
            
            if not isinstance(extracted_data[field], field_type):
                raise ValidationException(
                    message=f"Invalid type for field: {field}",
                    error_code="VAL_005",
                    details={
                        "field": field,
                        "expected_type": str(field_type),
                        "received_type": str(type(extracted_data[field]))
                    },
                    status_code=400
                )

        # Sanitize text fields
        for field in ["contract_number", "payment_terms"]:
            extracted_data[field] = bleach.clean(
                extracted_data[field],
                tags=[],
                strip=True
            )

        # Validate contract number format
        if not re.match(CONTRACT_NUMBER_PATTERN, extracted_data["contract_number"]):
            raise ValidationException(
                message="Invalid contract number format",
                error_code="VAL_006",
                details={"pattern": CONTRACT_NUMBER_PATTERN},
                status_code=400
            )

        # Validate dates
        for date_field in ["effective_date", "expiration_date"]:
            try:
                date_value = datetime.strptime(extracted_data[date_field], "%Y-%m-%d")
                
                # Ensure effective date is not in the past
                if date_field == "effective_date" and date_value.date() < datetime.now().date():
                    raise ValidationException(
                        message="Effective date cannot be in the past",
                        error_code="VAL_007",
                        details={"field": date_field},
                        status_code=400
                    )
                
                # Ensure expiration date is after effective date
                if (date_field == "expiration_date" and 
                    date_value.date() <= datetime.strptime(extracted_data["effective_date"], "%Y-%m-%d").date()):
                    raise ValidationException(
                        message="Expiration date must be after effective date",
                        error_code="VAL_008",
                        details={"field": date_field},
                        status_code=400
                    )
            except ValueError:
                raise ValidationException(
                    message=f"Invalid date format for {date_field}",
                    error_code="VAL_009",
                    details={
                        "field": date_field,
                        "expected_format": "YYYY-MM-DD"
                    },
                    status_code=400
                )

        # Validate total value
        if extracted_data["total_value"] <= 0:
            raise ValidationException(
                message="Total value must be greater than zero",
                error_code="VAL_010",
                details={"field": "total_value"},
                status_code=400
            )

        # Validate parties list
        if len(extracted_data["parties"]) < 2:
            raise ValidationException(
                message="Contract must have at least two parties",
                error_code="VAL_011",
                details={"field": "parties"},
                status_code=400
            )

        # Validate party information
        for party in extracted_data["parties"]:
            if not isinstance(party, dict) or "name" not in party or "role" not in party:
                raise ValidationException(
                    message="Invalid party information",
                    error_code="VAL_012",
                    details={"required_fields": ["name", "role"]},
                    status_code=400
                )
            
            # Sanitize party information
            party["name"] = bleach.clean(party["name"], tags=[], strip=True)
            party["role"] = bleach.clean(party["role"], tags=[], strip=True)

        return True

    except ValidationException:
        raise
    except Exception as e:
        raise ValidationException(
            message="Data validation failed",
            error_code="VAL_013",
            details={"error": str(e)},
            status_code=500
        )