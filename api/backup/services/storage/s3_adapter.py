"""
S3 Storage Adapter - Adapter Pattern Implementation
Implements the StorageAdapterInterface for Amazon S3 storage.
"""

import boto3
import os
import logging
from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from botocore.config import Config

from .base import (
    StorageAdapterInterface, 
    StorageError, 
    StorageConnectionError, 
    StorageValidationError,
    StorageNotFoundError,
    StoragePermissionError
)
from api.backup.models import Backup

logger = logging.getLogger(__name__)


class S3StorageAdapter(StorageAdapterInterface):
    """
    S3 storage adapter implementation.
    Handles all S3-specific storage operations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 adapter with configuration.
        
        Args:
            config: S3 configuration dictionary containing:
                - access_key: AWS access key
                - secret_key: AWS secret key
                - bucket_name: S3 bucket name
                - region: AWS region (default: us-east-1)
                - endpoint_url: Custom endpoint URL (optional)
                - use_ssl: Use SSL (default: True)
                - verify_ssl: Verify SSL certificates (default: True)
        """
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate S3 configuration."""
        required_fields = ['access_key', 'secret_key', 'bucket_name']
        
        for field in required_fields:
            if not self.config.get(field):
                raise StorageValidationError(f"S3 adapter requires '{field}' in configuration")
        
        # Validate bucket name format
        bucket_name = self.config['bucket_name']
        if not (3 <= len(bucket_name) <= 63):
            raise StorageValidationError("S3 bucket name must be 3-63 characters")
        
        if not bucket_name.replace('-', '').replace('.', '').isalnum():
            raise StorageValidationError("S3 bucket name must contain only alphanumeric, hyphens, and dots")
    
    def _initialize_client(self):
        """Initialize S3 client."""
        try:
            s3_config = Config(
                region_name=self.config.get('region', 'us-east-1'),
                use_ssl=self.config.get('use_ssl', True),
                verify_ssl=self.config.get('verify_ssl', True),
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
            
            self.client = boto3.client(
                's3',
                aws_access_key_id=self.config['access_key'],
                aws_secret_access_key=self.config['secret_key'],
                endpoint_url=self.config.get('endpoint_url'),
                config=s3_config
            )
            
            self.bucket_name = self.config['bucket_name']
            self.region = self.config.get('region', 'us-east-1')
            
            # Test connection
            if not self.test_connection():
                raise StorageConnectionError("Failed to connect to S3")
                
        except Exception as e:
            raise StorageConnectionError(f"Failed to initialize S3 client: {str(e)}")
    
    def save_backup(self, file_obj: BinaryIO, backup: 'Backup') -> bool:
        """
        Save backup file to S3.
        
        Args:
            file_obj: File-like object containing backup data
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate S3 key
            s3_key = self._generate_s3_key(backup)
            
            # Reset file pointer
            file_obj.seek(0)
            
            # Upload to S3
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/octet-stream',
                    'Metadata': {
                        'backup_id': str(backup.backup_id),
                        'backup_type': backup.backup_type,
                        'created_at': backup.created_at.isoformat(),
                        'database_name': backup.database_name
                    }
                }
            )
            
            # Update backup with S3 path
            backup.file_path = s3_key
            backup.save()
            
            logger.info(f"Successfully uploaded backup {backup.name} to S3: {s3_key}")
            return True
            
        except ClientError as e:
            error_info = self.handle_error(e, 'save_backup', backup)
            logger.error(f"S3 upload failed: {error_info}")
            return False
        except Exception as e:
            error_info = self.handle_error(e, 'save_backup', backup)
            logger.error(f"S3 upload failed: {error_info}")
            return False
    
    def retrieve_backup(self, backup: 'Backup') -> Optional[BinaryIO]:
        """
        Retrieve backup file from S3.
        
        Args:
            backup: Backup model instance
            
        Returns:
            BinaryIO: File-like object or None if not found
        """
        try:
            s3_key = backup.file_path or self._generate_s3_key(backup)
            
            # Download from S3
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Successfully retrieved backup {backup.name} from S3")
            return response['Body']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"Backup file not found in S3: {s3_key}")
                return None
            else:
                error_info = self.handle_error(e, 'retrieve_backup', backup)
                logger.error(f"S3 retrieval failed: {error_info}")
                return None
        except Exception as e:
            error_info = self.handle_error(e, 'retrieve_backup', backup)
            logger.error(f"S3 retrieval failed: {error_info}")
            return None
    
    def delete_backup(self, backup: 'Backup') -> bool:
        """
        Delete backup file from S3.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            s3_key = backup.file_path or self._generate_s3_key(backup)
            
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Successfully deleted backup {backup.name} from S3: {s3_key}")
            return True
            
        except ClientError as e:
            error_info = self.handle_error(e, 'delete_backup', backup)
            logger.error(f"S3 deletion failed: {error_info}")
            return False
        except Exception as e:
            error_info = self.handle_error(e, 'delete_backup', backup)
            logger.error(f"S3 deletion failed: {error_info}")
            return False
    
    def backup_exists(self, backup: 'Backup') -> bool:
        """
        Check if backup file exists in S3.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            s3_key = backup.file_path or self._generate_s3_key(backup)
            
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                error_info = self.handle_error(e, 'backup_exists', backup)
                logger.error(f"S3 existence check failed: {error_info}")
                return False
        except Exception as e:
            error_info = self.handle_error(e, 'backup_exists', backup)
            logger.error(f"S3 existence check failed: {error_info}")
            return False
    
    def get_backup_size(self, backup: 'Backup') -> Optional[int]:
        """
        Get backup file size from S3.
        
        Args:
            backup: Backup model instance
            
        Returns:
            int: File size in bytes or None if not found
        """
        try:
            s3_key = backup.file_path or self._generate_s3_key(backup)
            
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return response['ContentLength']
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            else:
                error_info = self.handle_error(e, 'get_backup_size', backup)
                logger.error(f"S3 size check failed: {error_info}")
                return None
        except Exception as e:
            error_info = self.handle_error(e, 'get_backup_size', backup)
            logger.error(f"S3 size check failed: {error_info}")
            return None
    
    def get_backup_url(self, backup: 'Backup', expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for backup download.
        
        Args:
            backup: Backup model instance
            expires_in: URL expiration time in seconds
            
        Returns:
            str: Presigned URL or None if not found
        """
        try:
            s3_key = backup.file_path or self._generate_s3_key(backup)
            
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )
            
            return url
            
        except ClientError as e:
            error_info = self.handle_error(e, 'get_backup_url', backup)
            logger.error(f"S3 URL generation failed: {error_info}")
            return None
        except Exception as e:
            error_info = self.handle_error(e, 'get_backup_url', backup)
            logger.error(f"S3 URL generation failed: {error_info}")
            return None
    
    def list_backups(self, prefix: str = '') -> list:
        """
        List all backup files in S3.
        
        Args:
            prefix: Path prefix to filter results
            
        Returns:
            list: List of backup file information
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            backups = []
            for obj in response.get('Contents', []):
                backups.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            return backups
            
        except ClientError as e:
            error_info = self.handle_error(e, 'list_backups')
            logger.error(f"S3 listing failed: {error_info}")
            return []
        except Exception as e:
            error_info = self.handle_error(e, 'list_backups')
            logger.error(f"S3 listing failed: {error_info}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get S3 storage usage statistics.
        
        Returns:
            Dict: Storage statistics
        """
        try:
            # Get bucket location
            location = self.client.get_bucket_location(Bucket=self.bucket_name)
            
            # List objects to calculate usage
            response = self.client.list_objects_v2(Bucket=self.bucket_name)
            
            total_objects = len(response.get('Contents', []))
            total_size = sum(obj['Size'] for obj in response.get('Contents', []))
            
            return {
                'bucket_name': self.bucket_name,
                'region': location['LocationConstraint'] or 'us-east-1',
                'total_objects': total_objects,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'adapter': 'S3'
            }
            
        except ClientError as e:
            error_info = self.handle_error(e, 'get_storage_stats')
            logger.error(f"S3 stats failed: {error_info}")
            return {}
        except Exception as e:
            error_info = self.handle_error(e, 'get_storage_stats')
            logger.error(f"S3 stats failed: {error_info}")
            return {}
    
    def test_connection(self) -> bool:
        """
        Test connection to S3.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to list bucket (requires read permissions)
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            logger.error(f"S3 connection test failed: {str(e)}")
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate S3 configuration.
        
        Args:
            config: S3 configuration dictionary
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            required_fields = ['access_key', 'secret_key', 'bucket_name']
            
            for field in required_fields:
                if not config.get(field):
                    return False
            
            bucket_name = config['bucket_name']
            if not (3 <= len(bucket_name) <= 63):
                return False
            
            if not bucket_name.replace('-', '').replace('.', '').isalnum():
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_adapter_info(self) -> Dict[str, str]:
        """
        Get S3 adapter information.
        
        Returns:
            Dict: Adapter information
        """
        return {
            'name': 'S3StorageAdapter',
            'type': 'storage_adapter',
            'version': '1.0.0',
            'capabilities': [
                'save_backup',
                'retrieve_backup',
                'delete_backup',
                'backup_exists',
                'get_backup_size',
                'get_backup_url',
                'list_backups',
                'get_storage_stats',
                'test_connection',
                'presigned_urls'
            ],
            'supported_regions': [
                'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                'eu-west-1', 'eu-west-2', 'eu-west-3',
                'ap-south-1', 'ap-southeast-1', 'ap-southeast-2',
                'ap-northeast-1', 'ap-northeast-2',
                'ca-central-1', 'sa-east-1'
            ]
        }
    
    def _generate_s3_key(self, backup: 'Backup') -> str:
        """
        Generate S3 key for backup.
        
        Args:
            backup: Backup model instance
            
        Returns:
            str: S3 key path
        """
        # Create path structure: backups/year/month/day/backup_id_filename.ext
        created_date = backup.created_at
        year = created_date.strftime('%Y')
        month = created_date.strftime('%m')
        day = created_date.strftime('%d')
        
        filename = f"{backup.backup_id}_{backup.name.replace(' ', '_')}.sql"
        if backup.compression_enabled:
            filename += '.gz'
        
        return f"backups/{year}/{month}/{day}/{filename}"
    
    def _cleanup_old_backups(self, days: int = 30) -> int:
        """
        Clean up old backups from S3.
        
        Args:
            days: Number of days to keep backups
            
        Returns:
            int: Number of deleted backups
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime('%Y/%m/%d')
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='backups/'
            )
            
            objects_to_delete = []
            for obj in response.get('Contents', []):
                if obj['Key'] < cutoff_str:
                    objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                # Delete in batches of 1000
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch}
                    )
            
            return len(objects_to_delete)
            
        except Exception as e:
            error_info = self.handle_error(e, 'cleanup_old_backups')
            logger.error(f"S3 cleanup failed: {error_info}")
            return 0
