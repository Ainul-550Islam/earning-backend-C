"""
Google Cloud Storage Backup Service
Implements backup storage using Google Cloud Storage
"""

import os
import json
import logging
from datetime import datetime, timedelta
from google.cloud import storage
from google.oauth2 import service_account
from django.core.files.base import ContentFile
from django.conf import settings
from .BaseBackupService import BaseBackupService

logger = logging.getLogger(__name__)


class GCSBackupService(BaseBackupService):
    """
    Google Cloud Storage backup service implementation
    """
    
    def __init__(self, storage_location):
        """
        Initialize GCS backup service
        
        Args:
            storage_location: BackupStorageLocation instance with GCS configuration
        """
        super().__init__()
        self.storage_location = storage_location
        self.client = None
        self.bucket = None
        
        # Initialize GCS client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Cloud Storage client"""
        try:
            # Get credentials from storage location
            credentials_data = self.storage_location.config or {}
            
            # Check for service account credentials
            if 'credentials_file' in credentials_data:
                credentials_path = credentials_data['credentials_file']
                if os.path.exists(credentials_path):
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path
                    )
                else:
                    raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            # Check for JSON credentials
            elif 'credentials_json' in credentials_data:
                credentials_info = json.loads(credentials_data['credentials_json'])
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
            
            # Use default credentials
            else:
                credentials = None
            
            # Initialize client
            self.client = storage.Client(credentials=credentials)
            
            # Get bucket
            bucket_name = credentials_data.get('bucket_name')
            if not bucket_name:
                raise ValueError("GCS bucket name is required")
            
            self.bucket = self.client.bucket(bucket_name)
            
            # Test connection
            self.bucket.reload()
            
            logger.info(f"GCS client initialized for bucket: {bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
            raise
    
    def save_backup(self, backup_file, backup):
        """
        Save backup file to Google Cloud Storage
        
        Args:
            backup_file: Django File object or file-like object
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate filename
            filename = self._generate_filename(backup)
            
            # Reset file pointer if it's a Django File object
            if hasattr(backup_file, 'seek'):
                backup_file.seek(0)
            
            # Create blob object
            blob = self.bucket.blob(filename)
            
            # Set metadata
            metadata = self._create_metadata(backup)
            blob.metadata = metadata
            
            # Set storage class if specified
            storage_class = self.storage_location.config.get('storage_class', 'STANDARD')
            blob.storage_class = storage_class
            
            # Upload file
            blob.upload_from_file(
                backup_file,
                content_type='application/octet-stream',
                timeout=getattr(settings, 'GCS_UPLOAD_TIMEOUT', 3600)  # 1 hour
            )
            
            # Generate public URL if needed
            public_url = None
            if self.storage_location.config.get('public_access', False):
                blob.make_public()
                public_url = blob.public_url
            
            # Update backup model
            backup.file_path = f"gs://{self.bucket.name}/{filename}"
            backup.storage_location = f"gs://{self.bucket.name}"
            backup.file_size = backup_file.size if hasattr(backup_file, 'size') else 0
            
            if public_url:
                backup.public_url = public_url
            
            logger.info(f"Successfully saved backup to GCS: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save backup to GCS: {str(e)}")
            return False
    
    def delete_backup(self, backup):
        """
        Delete backup file from Google Cloud Storage
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract filename from file_path
            filename = self._extract_filename(backup.file_path)
            
            if not filename:
                logger.warning(f"Could not extract filename from: {backup.file_path}")
                return False
            
            # Delete blob
            blob = self.bucket.blob(filename)
            blob.delete()
            
            logger.info(f"Successfully deleted backup from GCS: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup from GCS: {str(e)}")
            return False
    
    def list_backups(self, prefix=None):
        """
        List backup files from Google Cloud Storage
        
        Args:
            prefix: Optional prefix to filter results
            
        Returns:
            list: List of backup file information
        """
        try:
            # List blobs
            blobs = self.client.list_blobs(
                self.bucket,
                prefix=prefix,
                versions=False  # Only list latest versions
            )
            
            backup_files = []
            for blob in blobs:
                backup_info = {
                    'name': blob.name,
                    'size': blob.size,
                    'created': blob.time_created,
                    'updated': blob.updated,
                    'content_type': blob.content_type,
                    'md5_hash': blob.md5_hash,
                    'crc32c': blob.crc32c,
                    'generation': blob.generation,
                    'metadata': blob.metadata or {}
                }
                backup_files.append(backup_info)
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x['created'], reverse=True)
            
            return backup_files
            
        except Exception as e:
            logger.error(f"Failed to list backups from GCS: {str(e)}")
            return []
    
    def download_backup(self, filename):
        """
        Download backup file from Google Cloud Storage
        
        Args:
            filename: Name of the file to download
            
        Returns:
            bytes: File content, None if failed
        """
        try:
            blob = self.bucket.blob(filename)
            
            # Check if file exists
            if not blob.exists():
                logger.warning(f"Backup file not found in GCS: {filename}")
                return None
            
            # Download file
            content = blob.download_as_bytes()
            
            logger.info(f"Successfully downloaded backup from GCS: {filename}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to download backup from GCS: {str(e)}")
            return None
    
    def backup_exists(self, filename):
        """
        Check if backup file exists in Google Cloud Storage
        
        Args:
            filename: Name of the file to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            blob = self.bucket.blob(filename)
            return blob.exists()
            
        except Exception as e:
            logger.error(f"Failed to check backup existence in GCS: {str(e)}")
            return False
    
    def get_backup_info(self, filename):
        """
        Get backup file information from Google Cloud Storage
        
        Args:
            filename: Name of the file
            
        Returns:
            dict: File information, None if failed
        """
        try:
            blob = self.bucket.blob(filename)
            
            # Check if file exists
            if not blob.exists():
                return None
            
            # Reload to get latest metadata
            blob.reload()
            
            return {
                'name': blob.name,
                'size': blob.size,
                'created': blob.time_created,
                'updated': blob.updated,
                'content_type': blob.content_type,
                'md5_hash': blob.md5_hash,
                'crc32c': blob.crc32c,
                'generation': blob.generation,
                'metadata': blob.metadata or {},
                'storage_class': blob.storage_class,
                'etag': blob.etag
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup info from GCS: {str(e)}")
            return None
    
    def get_presigned_url(self, filename, expiration=3600):
        """
        Generate presigned URL for backup file
        
        Args:
            filename: Name of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL, None if failed
        """
        try:
            blob = self.bucket.blob(filename)
            
            # Check if file exists
            if not blob.exists():
                return None
            
            # Generate presigned URL
            url = blob.generate_signed_url(
                version='v4',
                expiration=timedelta(seconds=expiration),
                method='GET',
                content_type='application/octet-stream'
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for GCS: {str(e)}")
            return None
    
    def cleanup_old_backups(self, retention_days=30, prefix=None):
        """
        Clean up old backup files based on retention policy
        
        Args:
            retention_days: Number of days to retain backups
            prefix: Optional prefix to filter files
            
        Returns:
            dict: Cleanup results
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # List all blobs
            blobs = self.client.list_blobs(
                self.bucket,
                prefix=prefix,
                versions=False
            )
            
            deleted_count = 0
            deleted_size = 0
            errors = []
            
            for blob in blobs:
                # Skip if blob is too new
                if blob.time_created and blob.time_created > cutoff_date:
                    continue
                
                try:
                    # Get size before deletion
                    size = blob.size or 0
                    
                    # Delete blob
                    blob.delete()
                    
                    deleted_count += 1
                    deleted_size += size
                    
                    logger.info(f"Deleted old backup from GCS: {blob.name}")
                    
                except Exception as e:
                    error_msg = f"Failed to delete {blob.name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                'deleted_count': deleted_count,
                'deleted_size': deleted_size,
                'errors': errors,
                'success': len(errors) == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups in GCS: {str(e)}")
            return {
                'deleted_count': 0,
                'deleted_size': 0,
                'errors': [str(e)],
                'success': False
            }
    
    def _generate_filename(self, backup):
        """
        Generate filename for backup
        
        Args:
            backup: Backup model instance
            
        Returns:
            str: Generated filename
        """
        timestamp = backup.created_at.strftime('%Y%m%d_%H%M%S')
        name = backup.name.replace(' ', '_').lower()
        
        # Add extension based on compression
        extension = '.sql'
        if backup.compression_enabled:
            if backup.compression_method == 'gzip':
                extension = '.sql.gz'
            elif backup.compression_method == 'bzip2':
                extension = '.sql.bz2'
            elif backup.compression_method == 'lzma':
                extension = '.sql.xz'
            elif backup.compression_method == 'zstd':
                extension = '.sql.zst'
            elif backup.compression_method == 'zip':
                extension = '.zip'
        
        # Add encryption extension
        if backup.encryption_enabled:
            extension += '.enc'
        
        # Generate full path with date structure
        date_path = backup.created_at.strftime('%Y/%m/%d')
        filename = f"{date_path}/{name}_{timestamp}{extension}"
        
        return filename
    
    def _extract_filename(self, file_path):
        """
        Extract filename from GCS file path
        
        Args:
            file_path: GCS file path (gs://bucket-name/path/to/file)
            
        Returns:
            str: Filename, None if invalid
        """
        if not file_path:
            return None
        
        # Remove gs://bucket-name/ prefix
        if file_path.startswith('gs://'):
            parts = file_path.split('/', 2)
            if len(parts) > 1:
                return parts[1]
        
        return file_path
    
    def _create_metadata(self, backup):
        """
        Create metadata dictionary for backup file
        
        Args:
            backup: Backup model instance
            
        Returns:
            dict: Metadata dictionary
        """
        metadata = {
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'database_name': backup.database_name,
            'created_at': backup.created_at.isoformat(),
            'created_by': str(backup.created_by) if backup.created_by else None,
            'file_hash': backup.file_hash,
            'file_size': str(backup.file_size) if backup.file_size else None,
            'encryption_enabled': str(backup.encryption_enabled),
            'encryption_method': backup.encryption_method,
            'compression_enabled': str(backup.compression_enabled),
            'compression_method': backup.compression_method,
            'storage_service': 'gcs',
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Add any custom metadata from config
        custom_metadata = self.storage_location.config.get('custom_metadata', {})
        metadata.update(custom_metadata)
        
        return metadata
    
    def get_storage_usage(self):
        """
        Get storage usage statistics
        
        Returns:
            dict: Storage usage information
        """
        try:
            # Get bucket info
            self.bucket.reload()
            
            # List all objects to calculate usage
            blobs = list(self.client.list_blobs(self.bucket))
            
            total_size = sum(blob.size for blob in blobs)
            total_count = len(blobs)
            
            return {
                'total_size': total_size,
                'total_count': total_count,
                'bucket_name': self.bucket.name,
                'storage_class': getattr(self.bucket, 'storage_class', 'STANDARD'),
                'location': getattr(self.bucket, 'location', None)
            }
            
        except Exception as e:
            logger.error(f"Failed to get GCS storage usage: {str(e)}")
            return {
                'total_size': 0,
                'total_count': 0,
                'error': str(e)
            }
    
    def test_connection(self):
        """
        Test connection to Google Cloud Storage
        
        Returns:
            dict: Connection test results
        """
        try:
            # Test bucket access
            self.bucket.reload()
            
            # Test list operation
            list(self.client.list_blobs(self.bucket, max_results=1))
            
            return {
                'success': True,
                'message': 'GCS connection successful',
                'bucket_name': self.bucket.name,
                'location': getattr(self.bucket, 'location', None)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'GCS connection failed: {str(e)}',
                'error': str(e)
            }
