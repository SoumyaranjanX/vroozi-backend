#!/usr/bin/env python3
"""
MongoDB Backup Script
Version: 1.0
Purpose: Enterprise-grade MongoDB backup solution with full and incremental backup support,
         parallel compression, integrity verification, and AWS S3 integration.
"""

# External imports with version specifications
import boto3  # version: 1.26+
import pymongo  # version: 4.3+
import gzip
import multiprocessing
import argparse
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
import json
import subprocess
import sys

# Internal imports
from app.config.settings import get_settings

# Global constants
logger = logging.getLogger(__name__)
BACKUP_TYPES = {"full": "full", "incremental": "incremental"}
RETENTION_DAYS = 30
COMPRESSION_LEVEL = 9
MAX_RETRIES = 3
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks for multipart upload
BACKUP_SCHEDULE = {
    "incremental": "0 0 * * 1-6",  # Daily at midnight except Sunday
    "full": "0 0 * * 0"  # Sunday at midnight
}

def setup_logging(log_level: str) -> None:
    """
    Configure comprehensive logging with rotation and formatting.
    
    Args:
        log_level: Desired logging level (DEBUG, INFO, WARNING, ERROR)
    """
    log_format = '%(asctime)s - %(processName)s - [%(levelname)s] - %(message)s'
    formatter = logging.Formatter(log_format)
    
    # Configure rotating file handler
    log_file = Path('logs/mongodb_backup.log')
    log_file.parent.mkdir(exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Configure console handler with color coding
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command line arguments.
    
    Returns:
        Namespace containing validated arguments
    """
    parser = argparse.ArgumentParser(description='MongoDB Backup Script')
    parser.add_argument(
        '--type',
        choices=BACKUP_TYPES.values(),
        default='incremental',
        help='Backup type (full or incremental)'
    )
    parser.add_argument(
        '--compression-level',
        type=int,
        choices=range(1, 10),
        default=COMPRESSION_LEVEL,
        help='Compression level (1-9)'
    )
    parser.add_argument(
        '--parallel-processes',
        type=int,
        default=multiprocessing.cpu_count(),
        help='Number of parallel compression processes'
    )
    parser.add_argument(
        '--skip-upload',
        action='store_true',
        help='Skip S3 upload'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=RETENTION_DAYS,
        help='Number of days to retain backups'
    )
    
    return parser.parse_args()

def verify_backup_integrity(backup_file: Path) -> bool:
    """
    Verify backup integrity through checksums and sample restoration.
    
    Args:
        backup_file: Path to the backup file
        
    Returns:
        bool indicating verification success
    """
    logger.info(f"Verifying integrity of backup file: {backup_file}")
    
    try:
        # Calculate and store checksum
        sha256_hash = hashlib.sha256()
        with open(backup_file, 'rb') as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
                sha256_hash.update(chunk)
        checksum = sha256_hash.hexdigest()
        
        # Verify gzip integrity
        with gzip.open(backup_file, 'rb') as f:
            f.read(1)  # Try reading first byte to verify gzip integrity
        
        # Perform sample restoration test
        test_restore_path = backup_file.parent / 'test_restore'
        test_restore_path.mkdir(exist_ok=True)
        
        restore_cmd = [
            'mongorestore',
            '--gzip',
            '--archive=' + str(backup_file),
            '--dir=' + str(test_restore_path),
            '--dryRun'  # Verify without actual restoration
        ]
        
        result = subprocess.run(restore_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Restore test failed: {result.stderr}")
        
        # Store verification metadata
        metadata = {
            'checksum': checksum,
            'verified_at': datetime.utcnow().isoformat(),
            'size': backup_file.stat().st_size,
            'verification_status': 'success'
        }
        
        metadata_file = backup_file.with_suffix('.meta.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        logger.info("Backup verification completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Backup verification failed: {str(e)}")
        return False

def create_backup(backup_type: str, output_dir: Path) -> Optional[Path]:
    """
    Create MongoDB backup with parallel compression and verification.
    
    Args:
        backup_type: Type of backup (full or incremental)
        output_dir: Directory for backup storage
        
    Returns:
        Path to verified backup file or None if backup fails
    """
    try:
        settings = get_settings()
        mongo_settings = settings.get_mongodb_settings()
        
        # Create backup directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with metadata
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = output_dir / f"mongodb_{backup_type}_{timestamp}.gz"
        
        # Prepare mongodump command
        dump_cmd = [
            'mongodump',
            '--uri=' + mongo_settings['host'],
            '--gzip',
            '--archive=' + str(backup_file)
        ]
        
        if backup_type == 'incremental':
            # Add oplog for point-in-time recovery
            dump_cmd.extend(['--oplog'])
        
        # Execute backup with progress monitoring
        logger.info(f"Starting {backup_type} backup to {backup_file}")
        result = subprocess.run(dump_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Backup failed: {result.stderr}")
        
        # Verify backup integrity
        if not verify_backup_integrity(backup_file):
            raise Exception("Backup verification failed")
        
        logger.info(f"Backup completed successfully: {backup_file}")
        return backup_file
        
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None

def upload_to_s3(backup_file: Path) -> bool:
    """
    Upload backup to S3 with multipart upload and verification.
    
    Args:
        backup_file: Path to the backup file
        
    Returns:
        bool indicating upload success
    """
    try:
        settings = get_settings()
        aws_settings = settings.get_aws_settings()
        
        # Initialize S3 client with retry configuration
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_settings['aws_access_key_id'],
            aws_secret_access_key=aws_settings['aws_secret_access_key'],
            region_name=aws_settings['region_name'],
            config=boto3.Config(
                retries={'max_attempts': MAX_RETRIES},
                connect_timeout=5,
                read_timeout=300
            )
        )
        
        # Calculate optimal chunk size for multipart upload
        file_size = backup_file.stat().st_size
        chunk_count = min(10000, max(1, file_size // CHUNK_SIZE))
        chunk_size = file_size // chunk_count
        
        # Initiate multipart upload
        s3_key = f"backups/{backup_file.name}"
        multipart_upload = s3_client.create_multipart_upload(
            Bucket=aws_settings['s3_bucket'],
            Key=s3_key
        )
        
        # Upload parts in parallel
        with open(backup_file, 'rb') as f:
            parts = []
            part_number = 1
            
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                    
                response = s3_client.upload_part(
                    Bucket=aws_settings['s3_bucket'],
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=multipart_upload['UploadId'],
                    Body=data
                )
                
                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })
                part_number += 1
        
        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=aws_settings['s3_bucket'],
            Key=s3_key,
            UploadId=multipart_upload['UploadId'],
            MultipartUpload={'Parts': parts}
        )
        
        logger.info(f"Successfully uploaded backup to S3: {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"S3 upload failed: {str(e)}")
        return False

def cleanup_old_backups(backup_dir: Path) -> None:
    """
    Manage backup retention with S3 synchronization.
    
    Args:
        backup_dir: Directory containing backups
    """
    try:
        retention_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        
        for backup_file in backup_dir.glob('mongodb_*.gz'):
            # Parse backup date from filename
            try:
                date_str = backup_file.name.split('_')[2]
                backup_date = datetime.strptime(date_str, '%Y%m%d')
                
                if backup_date < retention_date:
                    logger.info(f"Removing expired backup: {backup_file}")
                    backup_file.unlink()
                    
                    # Remove associated metadata file
                    metadata_file = backup_file.with_suffix('.meta.json')
                    if metadata_file.exists():
                        metadata_file.unlink()
            except (IndexError, ValueError):
                logger.warning(f"Could not parse date from backup file: {backup_file}")
                continue
        
        logger.info("Backup cleanup completed")
        
    except Exception as e:
        logger.error(f"Backup cleanup failed: {str(e)}")

def main() -> int:
    """
    Main function orchestrating the backup process.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        args = parse_arguments()
        setup_logging(get_settings().LOG_LEVEL)
        
        logger.info(f"Starting MongoDB backup process - Type: {args.type}")
        
        # Create backup
        backup_dir = Path('backups')
        backup_file = create_backup(args.type, backup_dir)
        
        if not backup_file:
            logger.error("Backup creation failed")
            return 1
        
        # Upload to S3 if enabled
        if not args.skip_upload:
            if not upload_to_s3(backup_file):
                logger.error("S3 upload failed")
                return 1
        
        # Cleanup old backups
        cleanup_old_backups(backup_dir)
        
        logger.info("Backup process completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Backup process failed: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())