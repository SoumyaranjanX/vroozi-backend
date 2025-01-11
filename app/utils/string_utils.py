"""
String utility module providing enhanced text manipulation and validation functions
for contract processing and OCR data extraction with international text support.

Version: 1.0
"""

# External imports with version specifications
import re  # built-in
import unicodedata  # built-in
from typing import List, Dict, Optional  # built-in

# Internal imports
from app.core.exceptions import ValidationException
from app.core.logging import get_logger

# Configure logger
logger = get_logger(__name__)

# Regular expression patterns for validation
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
PHONE_REGEX = r'^\+?[1-9][0-9]{7,14}$'
CURRENCY_REGEX = r'^\$?\d+(\.\d{2})?$'

# OCR error correction patterns
OCR_ERROR_PATTERNS = {
    '0': ['O', 'Q', 'D'],
    '1': ['I', 'l'],
    '2': ['Z'],
    '5': ['S'],
    '8': ['B']
}

# International currency symbols mapping
INTERNATIONAL_CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥'
}

def normalize_text(
    text: str,
    lowercase: bool = True,
    handle_ocr_errors: bool = True,
    lang_code: str = 'en'
) -> str:
    """
    Enhanced text normalization with OCR-specific processing and international text support.

    Args:
        text: Input text to normalize
        lowercase: Whether to convert text to lowercase
        handle_ocr_errors: Whether to apply OCR error correction
        lang_code: Language code for specific normalization rules

    Returns:
        str: Normalized text string

    Raises:
        ValidationException: If text normalization fails
    """
    try:
        if not isinstance(text, str):
            raise ValidationException("Input must be a string", "INVALID_INPUT_TYPE")

        # Remove leading/trailing whitespace and normalize spaces
        normalized = ' '.join(text.split())

        # Apply OCR error correction if enabled
        if handle_ocr_errors:
            for digit, replacements in OCR_ERROR_PATTERNS.items():
                for replacement in replacements:
                    normalized = re.sub(
                        f'(?<![a-zA-Z]){replacement}(?![a-zA-Z])',
                        digit,
                        normalized
                    )

        # Apply unicode normalization (NFKC for compatibility decomposition)
        normalized = unicodedata.normalize('NFKC', normalized)

        # Apply language-specific normalization
        if lang_code == 'de':
            # Handle German special characters
            normalized = normalized.replace('ß', 'ss')
        elif lang_code == 'fr':
            # Handle French accents in OCR
            normalized = ''.join(c for c in unicodedata.normalize('NFD', normalized)
                               if unicodedata.category(c) != 'Mn')

        # Convert to lowercase if specified
        if lowercase:
            normalized = normalized.lower()

        # Remove any remaining control characters
        normalized = ''.join(char for char in normalized 
                           if unicodedata.category(char)[0] != 'C')

        return normalized

    except ValidationException as ve:
        logger.error(f"Validation error during text normalization: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error during text normalization: {str(e)}")
        raise ValidationException(
            f"Text normalization failed: {str(e)}",
            "NORMALIZATION_ERROR"
        )

def extract_numbers(
    text: str,
    handle_ocr_errors: bool = True,
    number_format: str = 'any'
) -> List[str]:
    """
    Enhanced number extraction with OCR support and international format handling.

    Args:
        text: Input text to extract numbers from
        handle_ocr_errors: Whether to apply OCR error correction
        number_format: Format specification ('any', 'integer', 'decimal', 'currency')

    Returns:
        List[str]: List of extracted numbers

    Raises:
        ValidationException: If number extraction fails
    """
    try:
        if not isinstance(text, str):
            raise ValidationException("Input must be a string", "INVALID_INPUT_TYPE")

        # Normalize text with OCR correction if enabled
        normalized = normalize_text(text, lowercase=False, handle_ocr_errors=handle_ocr_errors)

        # Define number patterns based on format
        patterns = {
            'any': r'-?\d+(?:\.\d+)?',
            'integer': r'-?\d+',
            'decimal': r'-?\d+\.\d+',
            'currency': r'(?:[$€£¥]\s*)?-?\d+(?:,\d{3})*(?:\.\d{2})?'
        }

        if number_format not in patterns:
            raise ValidationException(
                f"Invalid number format: {number_format}",
                "INVALID_FORMAT"
            )

        # Extract numbers using the specified pattern
        numbers = re.findall(patterns[number_format], normalized)

        # Clean up currency numbers
        if number_format == 'currency':
            numbers = [re.sub(r'[,$€£¥\s]', '', num) for num in numbers]

        # Validate extracted numbers
        validated_numbers = []
        for num in numbers:
            try:
                float(num)  # Validate number format
                validated_numbers.append(num)
            except ValueError:
                continue

        return validated_numbers

    except ValidationException as ve:
        logger.error(f"Validation error during number extraction: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error during number extraction: {str(e)}")
        raise ValidationException(
            f"Number extraction failed: {str(e)}",
            "EXTRACTION_ERROR"
        )

def format_currency(
    amount: float,
    currency_code: str = 'USD',
    locale: str = 'en_US'
) -> str:
    """
    Enhanced currency formatting with international support.

    Args:
        amount: Amount to format
        currency_code: ISO currency code
        locale: Locale code for formatting rules

    Returns:
        str: Formatted currency string

    Raises:
        ValidationException: If currency formatting fails
    """
    try:
        if not isinstance(amount, (int, float)):
            raise ValidationException(
                "Amount must be a number",
                "INVALID_AMOUNT_TYPE"
            )

        if currency_code not in INTERNATIONAL_CURRENCY_SYMBOLS:
            raise ValidationException(
                f"Unsupported currency code: {currency_code}",
                "INVALID_CURRENCY_CODE"
            )

        # Get currency symbol
        symbol = INTERNATIONAL_CURRENCY_SYMBOLS[currency_code]

        # Format number with proper precision
        formatted_amount = f"{abs(amount):,.2f}"

        # Apply locale-specific formatting
        if locale.startswith('de'):
            # German format: 1.234,56 €
            formatted_amount = formatted_amount.replace(',', 'X').replace('.', ',').replace('X', '.')
            formatted = f"{formatted_amount} {symbol}"
        elif locale.startswith('fr'):
            # French format: 1 234,56 €
            formatted_amount = formatted_amount.replace(',', 'X').replace('.', ',').replace('X', ' ')
            formatted = f"{formatted_amount} {symbol}"
        else:
            # Default format: $1,234.56
            formatted = f"{symbol}{formatted_amount}"

        # Handle negative amounts
        if amount < 0:
            formatted = f"-{formatted}"

        return formatted

    except ValidationException as ve:
        logger.error(f"Validation error during currency formatting: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error during currency formatting: {str(e)}")
        raise ValidationException(
            f"Currency formatting failed: {str(e)}",
            "FORMATTING_ERROR"
        )

# Export public interfaces
__all__ = [
    'normalize_text',
    'extract_numbers',
    'format_currency'
]