"""
Date and Time Utility Module

This module provides standardized date and time handling functions for the application,
implementing robust timezone management, ISO format conversions, and comprehensive
validation for contracts and audit logs.

Version: 1.0.0
Author: Contract Processing System Team
"""

from datetime import datetime, timedelta, timezone
import pytz  # version: 2023.3
from typing import Union, Optional
import functools

# Global Constants
DEFAULT_TIMEZONE = pytz.UTC
ISO_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
ISO_DATE_FORMAT = '%Y-%m-%d'
TIMEZONE_CACHE_SIZE = 128

# Maximum allowed days for date calculations to prevent unreasonable values
MAX_DAYS_DIFFERENCE = 36500  # ~100 years
MAX_FUTURE_YEARS = 10

class DateValidationError(ValueError):
    """Custom exception for date validation errors."""
    pass

def get_current_timestamp() -> str:
    """
    Returns the current UTC timestamp in ISO format with microsecond precision.
    
    Returns:
        str: Current timestamp in ISO format (e.g., '2023-12-01T10:30:00.123456Z')
    
    Example:
        >>> get_current_timestamp()
        '2023-12-01T10:30:00.123456Z'
    """
    return datetime.now(DEFAULT_TIMEZONE).strftime(ISO_DATETIME_FORMAT)

@functools.lru_cache(maxsize=TIMEZONE_CACHE_SIZE)
def format_timestamp(timestamp: datetime, format_string: Optional[str] = None) -> str:
    """
    Formats a datetime object to ISO format string with timezone conversion.
    
    Args:
        timestamp (datetime): The datetime object to format
        format_string (Optional[str]): Custom format string (defaults to ISO_DATETIME_FORMAT)
    
    Returns:
        str: Formatted ISO timestamp string
    
    Raises:
        ValueError: If timestamp is None or invalid
    
    Example:
        >>> dt = datetime.now(timezone.utc)
        >>> format_timestamp(dt)
        '2023-12-01T10:30:00.123456Z'
    """
    if timestamp is None:
        raise ValueError("Timestamp cannot be None")
    
    # Ensure timestamp is timezone-aware and in UTC
    if timestamp.tzinfo is None:
        timestamp = DEFAULT_TIMEZONE.localize(timestamp)
    elif timestamp.tzinfo != DEFAULT_TIMEZONE:
        timestamp = timestamp.astimezone(DEFAULT_TIMEZONE)
    
    # Use specified format or default
    actual_format = format_string or ISO_DATETIME_FORMAT
    
    # Format with microsecond handling
    formatted = timestamp.strftime(actual_format)
    
    # Ensure Z suffix for UTC if using ISO format
    if actual_format == ISO_DATETIME_FORMAT and not formatted.endswith('Z'):
        formatted += 'Z'
    
    return formatted

def parse_iso_timestamp(timestamp_str: str, format_string: Optional[str] = None) -> datetime:
    """
    Parses an ISO format timestamp string to datetime object with validation.
    
    Args:
        timestamp_str (str): ISO format timestamp string
        format_string (Optional[str]): Custom format string (defaults to ISO_DATETIME_FORMAT)
    
    Returns:
        datetime: Parsed UTC datetime object
    
    Raises:
        ValueError: If timestamp string is invalid or parsing fails
    
    Example:
        >>> parse_iso_timestamp('2023-12-01T10:30:00.123456Z')
        datetime.datetime(2023, 12, 1, 10, 30, 0, 123456, tzinfo=timezone.utc)
    """
    if not timestamp_str:
        raise ValueError("Timestamp string cannot be empty")
    
    actual_format = format_string or ISO_DATETIME_FORMAT
    
    try:
        # Handle timezone suffix
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1]
            parsed_dt = datetime.strptime(timestamp_str, actual_format)
            return parsed_dt.replace(tzinfo=DEFAULT_TIMEZONE)
        else:
            # Try parsing with potential timezone info
            parsed_dt = datetime.strptime(timestamp_str, actual_format)
            if parsed_dt.tzinfo is None:
                return DEFAULT_TIMEZONE.localize(parsed_dt)
            return parsed_dt.astimezone(DEFAULT_TIMEZONE)
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}. Expected format: {actual_format}") from e

def is_valid_date_string(date_string: str, format: str = ISO_DATE_FORMAT) -> bool:
    """
    Validates if a string is a valid date in specified format with comprehensive error checking.
    
    Args:
        date_string (str): Date string to validate
        format (str): Expected date format (defaults to ISO_DATE_FORMAT)
    
    Returns:
        bool: True if valid date string, False otherwise
    
    Example:
        >>> is_valid_date_string('2023-12-01')
        True
        >>> is_valid_date_string('2023-13-01')
        False
    """
    if not date_string or not format:
        return False
    
    try:
        parsed_date = datetime.strptime(date_string, format)
        
        # Validate date is not in unreasonable future
        max_future_date = datetime.now() + timedelta(days=MAX_FUTURE_YEARS * 365)
        if parsed_date > max_future_date:
            return False
        
        # Additional validation for leap years
        if parsed_date.month == 2 and parsed_date.day == 29:
            # Verify it's actually a leap year
            year = parsed_date.year
            if not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
                return False
        
        return True
    except ValueError:
        return False

def calculate_date_difference(
    date1: Union[datetime, str],
    date2: Union[datetime, str]
) -> int:
    """
    Calculates difference between two dates in days with timezone handling.
    
    Args:
        date1 (Union[datetime, str]): First date
        date2 (Union[datetime, str]): Second date
    
    Returns:
        int: Absolute number of days between dates
    
    Raises:
        ValueError: If dates are invalid or difference exceeds maximum allowed
    
    Example:
        >>> calculate_date_difference('2023-12-01', '2023-12-31')
        30
    """
    # Convert string dates to datetime if needed
    if isinstance(date1, str):
        date1 = parse_iso_timestamp(date1)
    if isinstance(date2, str):
        date2 = parse_iso_timestamp(date2)
    
    # Ensure both dates are timezone-aware
    if date1.tzinfo is None:
        date1 = DEFAULT_TIMEZONE.localize(date1)
    if date2.tzinfo is None:
        date2 = DEFAULT_TIMEZONE.localize(date2)
    
    # Calculate difference
    difference = abs((date2 - date1).days)
    
    # Validate difference is within reasonable range
    if difference > MAX_DAYS_DIFFERENCE:
        raise ValueError(f"Date difference exceeds maximum allowed ({MAX_DAYS_DIFFERENCE} days)")
    
    return difference

def add_days_to_date(
    date: Union[datetime, str],
    days: int
) -> datetime:
    """
    Adds specified number of days to a date with timezone preservation.
    
    Args:
        date (Union[datetime, str]): Starting date
        days (int): Number of days to add (positive or negative)
    
    Returns:
        datetime: New date with added days
    
    Raises:
        ValueError: If days parameter is outside reasonable range
    
    Example:
        >>> add_days_to_date('2023-12-01', 30)
        datetime.datetime(2023, 12, 31, 0, 0, tzinfo=timezone.utc)
    """
    if abs(days) > MAX_DAYS_DIFFERENCE:
        raise ValueError(f"Days parameter ({days}) exceeds maximum allowed range")
    
    # Convert string date to datetime if needed
    if isinstance(date, str):
        date = parse_iso_timestamp(date)
    
    # Ensure date is timezone-aware
    if date.tzinfo is None:
        date = DEFAULT_TIMEZONE.localize(date)
    
    # Add days
    new_date = date + timedelta(days=days)
    
    # Preserve timezone
    return new_date.astimezone(date.tzinfo)