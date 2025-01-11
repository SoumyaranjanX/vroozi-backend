"""
Enterprise-grade AWS S3 service module for secure document storage operations.
Implements comprehensive security, monitoring, and compliance features for contract documents
and purchase orders.

Version: 1.0
"""

# External imports with version specifications
import boto3  # boto3 v1.26+
from botocore.exceptions import ClientError, ParamValidationError  # botocore v1.29+
from typing import Dict, Any, Optional, List, Tuple
import logging
import hashlib
import os
from datetime import datetime
import json

# Internal imports
from app.core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunk size for multipart uploads
MAX_SINGLE_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024  # 5GB threshold for multipart upload

class S3Service:
    """
    Enterprise-grade service class for managing AWS S3 operations with enhanced
    security, monitoring, and compliance features.
    """

    def __init__(self):
        """
        Initialize S3Service with AWS credentials, configuration, and monitoring setup.
        """
        self.settings = get_settings()
        aws_config = self.settings.get_aws_settings()
        self.read_only = self.settings.READ_ONLY_MODE

        endpoint_url = aws_config.get('endpoint_url')
        logger.info(f"Initializing S3 service with endpoint: {endpoint_url}")

        if not endpoint_url:
            raise ValueError("AWS_ENDPOINT_URL is required but not set in environment")

        # Initialize S3 client with enhanced retry and timeout configuration
        self._s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_config['aws_access_key_id'],
            aws_secret_access_key=aws_config['aws_secret_access_key'],
            region_name=aws_config['region_name'],
            config=boto3.session.Config(
                signature_version='s3v4',
                retries={
                    'max_attempts': MAX_RETRIES,
                    'mode': 'adaptive'
                }
            )
        )
        self.bucket_name = aws_config['bucket_name']
        
        # Validate bucket configuration
        self._validate_bucket()

    def _validate_bucket(self) -> None:
        """Validate S3 bucket configuration and permissions."""
        try:
            # First try to list buckets to verify credentials
            try:
                response = self._s3_client.list_buckets()
                available_buckets = [bucket['Name'] for bucket in response['Buckets']]
                logger.info(f"Available S3 buckets: {available_buckets}")
                if self.bucket_name not in available_buckets:
                    logger.error(f"Bucket {self.bucket_name} not found in available buckets: {available_buckets}")
            except ClientError as e:
                logger.error(f"Failed to list buckets: {str(e)}")

            # Then try to access the specific bucket
            self._s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully validated access to bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_msg = e.response.get('Error', {}).get('Message', '')
            if error_code == '404':
                raise ValueError(f"Bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                raise ValueError(f"Access denied to bucket {self.bucket_name}. Error: {error_msg}")
            else:
                raise ValueError(f"Error accessing bucket {self.bucket_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error validating bucket: {str(e)}")
            raise ValueError(f"Failed to validate bucket access: {str(e)}")

    def upload_file(self, file_data: bytes, s3_key: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Upload file to S3 with enhanced error handling and validation.
        
        Args:
            file_data: Binary content to upload
            s3_key: S3 key for uploaded file (without bucket prefix)
            metadata: Optional metadata to attach to file
            
        Returns:
            Dict: Upload result with metadata
            
        Raises:
            S3ServiceException: If upload fails
        """
        try:
            # Clean up s3_key if it contains bucket prefix
            if s3_key.startswith('s3://'):
                s3_key = s3_key.split('/', 2)[2]  # Remove 's3://bucket_name/'
            
            # Upload file
            response = self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                Metadata=metadata or {}
            )
            
            logger.info(f"Successfully uploaded file to {s3_key}")
            
            return {
                's3_key': s3_key,
                'version_id': response.get('VersionId'),
                'etag': response.get('ETag', '').strip('"'),
                'size': len(file_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file to s3://{self.bucket_name}/{s3_key}: {str(e)}")
            raise S3ServiceException(f"Failed to upload file: {str(e)}")

    def download_file(self, s3_key: str, destination_path: str) -> Dict:
        """
        Download file from S3 with enhanced error handling and validation.
        
        Args:
            s3_key: S3 key of file to download (without bucket prefix)
            destination_path: Local path to save file
            
        Returns:
            Dict: Download result with metadata
            
        Raises:
            S3ServiceException: If download fails
        """
        try:
            # Clean up s3_key if it contains bucket prefix
            if s3_key.startswith('s3://'):
                s3_key = s3_key.split('/', 2)[2]  # Remove 's3://bucket_name/'
            
            # Download file
            self._s3_client.download_file(
                Bucket=self.bucket_name,
                Key=s3_key,
                Filename=destination_path
            )
            
            # Get object metadata
            head = self._s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                'destination': destination_path,
                'metadata': head.get('Metadata', {}),
                'content_type': head.get('ContentType'),
                'size': head.get('ContentLength', 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to download file s3://{self.bucket_name}/{s3_key}: {str(e)}")
            raise S3ServiceException(f"Failed to download file: {str(e)}")

    def _get_content_type(self, file_path: str) -> str:
        """Determine content type based on file extension."""
        extension = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        return content_types.get(extension, 'application/octet-stream')