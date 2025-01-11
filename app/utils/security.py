"""
Enhanced security utility module for the Contract Processing System.
Provides high-level security operations with comprehensive validation and error handling.

Version: 1.0
"""

# External imports with version specifications
import secrets  # built-in
import base64  # built-in
import re  # built-in
import logging
from typing import Dict, Optional

# Internal imports
from app.core.security import (
    create_access_token,
    create_refresh_token,
    encrypt_data,
    decrypt_data
)

# Configure logging
logger = logging.getLogger(__name__)

# Constants for security configuration
MIN_TOKEN_LENGTH = 8
MAX_TOKEN_LENGTH = 128
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
PASSWORD_PATTERNS = {
    'uppercase': r'[A-Z]',
    'lowercase': r'[a-z]',
    'numbers': r'[0-9]',
    'special': r'[!@#$%^&*(),.?":{}|<>]'
}
COMMON_PASSWORD_PATTERNS = [
    r'12345',
    r'qwerty',
    r'password',
    r'admin',
    r'test'
]

def generate_secure_token(length: int = 32) -> str:
    """
    Generates a cryptographically secure random token with enhanced validation.
    
    Args:
        length: Desired length of the token (default: 32)
        
    Returns:
        str: URL-safe base64 encoded secure random token
        
    Raises:
        ValueError: If length is invalid or token generation fails
    """
    try:
        # Validate length parameter
        if not isinstance(length, int) or length < MIN_TOKEN_LENGTH or length > MAX_TOKEN_LENGTH:
            raise ValueError(f"Token length must be between {MIN_TOKEN_LENGTH} and {MAX_TOKEN_LENGTH}")
        
        # Generate secure random bytes with additional entropy
        random_bytes = secrets.token_bytes(length * 2)
        
        # Create URL-safe base64 encoded token
        token = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
        
        # Remove padding and trim to desired length
        token = token.rstrip('=')[:length]
        
        # Validate generated token
        if not token or len(token) != length:
            raise ValueError("Token generation failed validation")
            
        return token
    except Exception as e:
        logger.error(f"Token generation failed: {str(e)}")
        raise ValueError("Failed to generate secure token") from e

def encrypt_sensitive_data(data: str) -> str:
    """
    Encrypts sensitive data with comprehensive validation and error handling.
    
    Args:
        data: String data to encrypt
        
    Returns:
        str: Encrypted data string with format validation
        
    Raises:
        ValueError: If encryption fails or validation fails
    """
    try:
        # Validate input data
        if not data or not isinstance(data, str):
            raise ValueError("Invalid input data for encryption")
            
        # Validate data encoding
        data.encode('utf-8')
        
        # Encrypt data using core function
        encrypted = encrypt_data(data)
        
        # Validate encryption result format
        if not encrypted.startswith('v1:'):
            raise ValueError("Encryption result format validation failed")
            
        # Verify encrypted data is not empty and has minimum length
        if len(encrypted) < 32:
            raise ValueError("Encrypted data length validation failed")
            
        return encrypted
    except Exception as e:
        logger.error(f"Data encryption failed: {str(e)}")
        raise ValueError("Failed to encrypt sensitive data") from e
    finally:
        # Clean up sensitive data from memory
        del data

def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Decrypts sensitive data with comprehensive validation and error handling.
    
    Args:
        encrypted_data: Encrypted data string to decrypt
        
    Returns:
        str: Decrypted data string with format validation
        
    Raises:
        ValueError: If decryption fails or validation fails
    """
    try:
        # Validate input data
        if not encrypted_data or not isinstance(encrypted_data, str):
            raise ValueError("Invalid encrypted data format")
            
        # Validate encryption format
        if not encrypted_data.startswith('v1:'):
            raise ValueError("Invalid encryption version")
            
        # Decrypt data using core function
        decrypted = decrypt_data(encrypted_data)
        
        # Validate decrypted data encoding
        decrypted.encode('utf-8')
        
        return decrypted
    except Exception as e:
        logger.error(f"Data decryption failed: {str(e)}")
        raise ValueError("Failed to decrypt sensitive data") from e
    finally:
        # Clean up sensitive data from memory
        del encrypted_data

def create_auth_tokens(user_data: Dict) -> Dict:
    """
    Creates both access and refresh tokens with comprehensive validation.
    
    Args:
        user_data: Dictionary containing user information
        
    Returns:
        Dict: Dictionary containing validated access and refresh tokens
        
    Raises:
        ValueError: If token creation fails or validation fails
    """
    try:
        # Validate required user data fields
        required_fields = {'id', 'email', 'roles'}
        if not all(field in user_data for field in required_fields):
            raise ValueError("Missing required user data fields")
            
        # Validate field types
        if not isinstance(user_data['id'], str) or \
           not isinstance(user_data['email'], str) or \
           not isinstance(user_data['roles'], list):
            raise ValueError("Invalid user data field types")
            
        # Create access token
        access_token = create_access_token(user_data)
        
        # Validate access token format
        if not access_token or len(access_token) < 32:
            raise ValueError("Access token validation failed")
            
        # Create refresh token
        refresh_token = create_refresh_token(user_data)
        
        # Validate refresh token format
        if not refresh_token or len(refresh_token) < 32:
            raise ValueError("Refresh token validation failed")
            
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}")
        raise ValueError("Failed to create authentication tokens") from e

def validate_password_strength(password: str) -> bool:
    """
    Validates password meets comprehensive security requirements.
    
    Args:
        password: Password string to validate
        
    Returns:
        bool: True if password meets all requirements, False otherwise
    """
    try:
        # Check password length
        if not password or not isinstance(password, str):
            return False
            
        if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
            return False
            
        # Check password patterns
        for pattern_name, pattern in PASSWORD_PATTERNS.items():
            if not re.search(pattern, password):
                logger.debug(f"Password missing {pattern_name} requirement")
                return False
                
        # Check for common password patterns
        for common_pattern in COMMON_PASSWORD_PATTERNS:
            if re.search(common_pattern, password.lower()):
                logger.debug("Password contains common pattern")
                return False
                
        # Additional entropy check
        unique_chars = len(set(password))
        if unique_chars < 8:
            logger.debug("Password has insufficient unique characters")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Password validation failed: {str(e)}")
        return False
    finally:
        # Clean up sensitive data from memory
        del password

# Export public interfaces
__all__ = [
    'generate_secure_token',
    'encrypt_sensitive_data',
    'decrypt_sensitive_data',
    'create_auth_tokens',
    'validate_password_strength'
]