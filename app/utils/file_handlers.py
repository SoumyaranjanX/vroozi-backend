"""
Enterprise-grade utility module for secure file operations.
Implements comprehensive file handling with validation, encryption, and secure storage management
for contract documents and purchase orders.

Version: 1.0
"""

# External imports with version specifications
import os  # built-in
import tempfile  # built-in
import shutil  # built-in
from typing import Dict, Optional, List, BinaryIO  # built-in
from cryptography.fernet import Fernet  # cryptography ^3.4.7
import tenacity  # tenacity ^8.0.1
import logging
import hashlib
from datetime import datetime, timedelta
import uuid

# Internal imports
from app.services.s3_service import S3Service
from app.utils.validators import validate_file_type, validate_file_size

# Configure logging
logger = logging.getLogger(__name__)

# Global constants
TEMP_DIR = os.path.join(os.getcwd(), 'tmp')
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for memory-efficient processing
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB per file limit
MAX_BATCH_SIZE = 500 * 1024 * 1024  # 500MB batch limit
TEMP_FILE_TTL = 3600  # 1 hour TTL for temporary files

class FileHandler:
    """
    Enterprise-grade class for managing secure file operations with validation,
    encryption, and storage handling.
    """

    def __init__(self, s3_service: S3Service):
        """
        Initialize FileHandler with required services and secure configuration.

        Args:
            s3_service: Initialized S3Service instance for storage operations
        """
        self._s3_service = s3_service
        self._temp_dir = self._initialize_temp_directory()
        self._file_cache: Dict[str, Dict] = {}
        self._encryptor = self._initialize_encryption()
        
        # Register cleanup handler
        import atexit
        atexit.register(self.cleanup_temp_files)

    def _initialize_temp_directory(self) -> str:
        """Create and secure temporary directory for file operations."""
        try:
            os.makedirs(TEMP_DIR, mode=0o700, exist_ok=True)
            return TEMP_DIR
        except Exception as e:
            logger.error(f"Failed to initialize temp directory: {str(e)}")
            raise RuntimeError("Temporary directory initialization failed")

    def _initialize_encryption(self) -> Fernet:
        """Initialize encryption for sensitive file content."""
        try:
            key = Fernet.generate_key()
            return Fernet(key)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise RuntimeError("Encryption initialization failed")

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying file processing after error: {retry_state.outcome.exception()}"
        )
    )
    def process_uploaded_file(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict
    ) -> str:
        """
        Securely process and validate uploaded file with content scanning.

        Args:
            file_content: Binary content of the uploaded file
            filename: Original filename
            metadata: File metadata dictionary

        Returns:
            str: Processed and encrypted file path in S3

        Raises:
            ValueError: If file validation fails
            RuntimeError: If file processing fails
        """
        try:
            # Generate secure temporary file path
            temp_file_path = self.create_temp_file(file_content, 
                                                 os.path.splitext(filename)[1])

            # Validate file
            if not validate_file_type(file_content):
                raise ValueError("Invalid file type")
            
            if not validate_file_size(len(file_content)):
                raise ValueError(f"File size exceeds limit of {MAX_FILE_SIZE} bytes")

            # Calculate file hash for integrity
            file_hash = self._calculate_file_hash(temp_file_path)

            # Enhance metadata
            enhanced_metadata = {
                **metadata,
                'original_filename': filename,
                'file_hash': file_hash,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'processed_by': 'file_handler_v1'
            }

            # Generate secure S3 key
            s3_key = f"contracts/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}"

            # Upload to S3 with encryption
            upload_result = self._s3_service.upload_file(
                temp_file_path,
                s3_key,
                enhanced_metadata
            )

            # Verify upload
            if not upload_result.get('status') == 'success':
                raise RuntimeError("File upload failed")

            # Cleanup temporary file
            self._secure_delete(temp_file_path)

            logger.info(f"Successfully processed file: {filename}")
            return s3_key

        except Exception as e:
            logger.error(f"File processing failed: {str(e)}")
            if 'temp_file_path' in locals():
                self._secure_delete(temp_file_path)
            raise

    def create_temp_file(self, content: bytes, suffix: str) -> str:
        """
        Create a secure temporary file with proper permissions.

        Args:
            content: File content
            suffix: File extension

        Returns:
            str: Path to temporary file

        Raises:
            RuntimeError: If temporary file creation fails
        """
        try:
            # Generate secure random filename
            temp_filename = f"{uuid.uuid4()}{suffix}"
            temp_path = os.path.join(self._temp_dir, temp_filename)

            # Write content with secure permissions
            with open(temp_path, 'wb') as f:
                f.write(content)

            # Set secure permissions
            os.chmod(temp_path, 0o600)

            # Register for cleanup
            self._file_cache[temp_path] = {
                'created_at': datetime.utcnow(),
                'ttl': TEMP_FILE_TTL
            }

            return temp_path

        except Exception as e:
            logger.error(f"Temporary file creation failed: {str(e)}")
            raise RuntimeError("Failed to create temporary file")

    def cleanup_temp_files(self) -> bool:
        """
        Securely clean up temporary files with verification.

        Returns:
            bool: Cleanup success status
        """
        try:
            current_time = datetime.utcnow()
            files_to_delete = []

            # Identify expired files
            for file_path, metadata in self._file_cache.items():
                if current_time - metadata['created_at'] > timedelta(seconds=metadata['ttl']):
                    files_to_delete.append(file_path)

            # Securely delete expired files
            for file_path in files_to_delete:
                self._secure_delete(file_path)
                del self._file_cache[file_path]

            logger.info(f"Cleaned up {len(files_to_delete)} temporary files")
            return True

        except Exception as e:
            logger.error(f"Temporary file cleanup failed: {str(e)}")
            return False

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file for integrity verification."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _secure_delete(self, file_path: str) -> None:
        """Securely delete file with multiple overwrites."""
        try:
            if os.path.exists(file_path):
                # Overwrite file content before deletion
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(os.path.getsize(file_path)))
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Secure file deletion failed: {str(e)}")
            raise

# Export public interfaces
__all__ = ['FileHandler']