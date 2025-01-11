"""
Comprehensive test suite for security utility functions.
Tests token generation, data encryption/decryption, authentication token creation,
password validation, and security boundary testing with performance benchmarks.

Version: 1.0
"""

# External imports with version specifications
import pytest  # pytest v7.3+
import base64  # built-in
import re  # built-in
import secrets  # built-in
import time
from typing import Dict, Any
import statistics

# Internal imports
from app.utils.security import (
    generate_secure_token,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    create_auth_tokens,
    validate_password_strength
)

@pytest.fixture
def test_encryption_key() -> bytes:
    """Fixture providing secure test encryption key."""
    return secrets.token_bytes(32)

@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Fixture providing valid test user data."""
    return {
        "id": "test123",
        "email": "test@example.com",
        "roles": ["user"],
        "organization": "test_org"
    }

class TestSecurityUtils:
    """Test class for security utility functions with comprehensive security validation."""

    def setup_method(self):
        """Setup method with security context."""
        self.test_data = {
            "small": "test123",
            "medium": "A" * 1024,
            "large": "B" * 4096,
            "special": "特殊字符@#$%",
            "sensitive": "password123!@#"
        }
        self.encryption_key = secrets.token_bytes(32)

    def teardown_method(self):
        """Secure cleanup after tests."""
        # Clean sensitive test data
        for key in self.test_data:
            self.test_data[key] = None
        self.encryption_key = None

    @pytest.mark.security
    @pytest.mark.parametrize("length", [16, 32, 64, 128])
    def test_generate_secure_token_length(self, length: int):
        """Test secure token generation with various lengths."""
        token = generate_secure_token(length)
        
        # Verify token length
        assert len(token) == length
        
        # Verify token is URL-safe base64 encoded
        assert all(c in '-_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' 
                  for c in token)
        
        # Verify token entropy
        unique_chars = len(set(token))
        assert unique_chars >= min(length // 2, 32)

    @pytest.mark.security
    def test_generate_secure_token_uniqueness(self):
        """Test token uniqueness and randomness."""
        tokens = [generate_secure_token(32) for _ in range(1000)]
        unique_tokens = set(tokens)
        
        # Verify all tokens are unique
        assert len(tokens) == len(unique_tokens)
        
        # Statistical distribution test
        char_counts = {}
        for token in tokens:
            for char in token:
                char_counts[char] = char_counts.get(char, 0) + 1
                
        # Check character distribution
        mean = statistics.mean(char_counts.values())
        stdev = statistics.stdev(char_counts.values())
        assert stdev / mean < 0.3  # Ensure relatively even distribution

    @pytest.mark.security
    @pytest.mark.slow
    def test_generate_secure_token_timing(self):
        """Test token generation for timing attack vulnerability."""
        timings = []
        
        for _ in range(100):
            start = time.perf_counter()
            generate_secure_token(32)
            end = time.perf_counter()
            timings.append(end - start)
            
        # Analyze timing consistency
        mean = statistics.mean(timings)
        stdev = statistics.stdev(timings)
        
        # Verify timing variation is minimal (within 10% of mean)
        assert stdev / mean < 0.1

    @pytest.mark.security
    @pytest.mark.parametrize("test_data", [
        "test123",
        "sensitive info",
        "特殊字符",
        "A" * 1024
    ])
    def test_encrypt_decrypt_sensitive_data(self, test_data: str):
        """Test encryption and decryption with memory cleanup."""
        # Encrypt data
        encrypted = encrypt_sensitive_data(test_data)
        
        # Verify encryption format
        assert encrypted.startswith("v1:")
        assert len(encrypted) > len(test_data)
        
        # Verify encrypted data is different from input
        assert encrypted[3:] != base64.b64encode(test_data.encode()).decode()
        
        # Decrypt data
        decrypted = decrypt_sensitive_data(encrypted)
        
        # Verify decryption
        assert decrypted == test_data
        
        # Memory cleanup verification
        del encrypted
        del decrypted

    @pytest.mark.security
    def test_create_auth_tokens_validation(self, test_user_data: Dict[str, Any]):
        """Test authentication token creation and validation."""
        tokens = create_auth_tokens(test_user_data)
        
        # Verify token structure
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
        
        # Verify token formats
        assert len(tokens["access_token"]) > 32
        assert len(tokens["refresh_token"]) > 32
        
        # Verify tokens are different
        assert tokens["access_token"] != tokens["refresh_token"]

    @pytest.mark.security
    @pytest.mark.parametrize("password,expected", [
        ("short", False),
        ("no_numbers", False),
        ("12345678", False),
        ("Password123", False),
        ("Password123!", True),
        ("SuperSecure123!@#", True),
        ("abcd1234", False),
        ("A" * 129, False)
    ])
    def test_password_strength_validation(self, password: str, expected: bool):
        """Test password strength validation rules."""
        result = validate_password_strength(password)
        assert result == expected

    @pytest.mark.security
    def test_encryption_error_handling(self):
        """Test encryption error handling and security boundaries."""
        with pytest.raises(ValueError):
            encrypt_sensitive_data("")
            
        with pytest.raises(ValueError):
            encrypt_sensitive_data(None)
            
        with pytest.raises(ValueError):
            decrypt_sensitive_data("invalid_format")
            
        with pytest.raises(ValueError):
            decrypt_sensitive_data("v1:invalid_base64")

    @pytest.mark.security
    def test_token_creation_error_handling(self, test_user_data: Dict[str, Any]):
        """Test token creation error handling."""
        invalid_data = test_user_data.copy()
        
        # Test missing required fields
        del invalid_data["id"]
        with pytest.raises(ValueError):
            create_auth_tokens(invalid_data)
            
        # Test invalid field types
        invalid_data = test_user_data.copy()
        invalid_data["roles"] = "not_a_list"
        with pytest.raises(ValueError):
            create_auth_tokens(invalid_data)

if __name__ == "__main__":
    pytest.main(["-v", __file__])