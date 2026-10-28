"""
Azure Blob Storage Backup Service
Implements backup storage using Microsoft Azure Blob Storage
"""

import os
import json
import logging
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError, AzureError
from django.core.files.base import ContentFile
from django.conf import settings
from .BaseBackupService import BaseBackupService

logger = logging.getLogger(__name__)


class AzureBackupService(BaseBackupService):
    """
    Azure Blob Storage backup service implementation
    """
    
    def __init__(self, storage_location):
        """
        Initialize Azure backup service
        
        Args:
            storage_location: BackupStorageLocation instance with Azure configuration
        """
        super().__init__()
        self.storage_location = storage_location
        self.blob_service_client = None
        self.container_client = None
        
        # Initialize Azure client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure Blob Storage client"""
        try:
            # Get credentials from storage location
            credentials = self.storage_location.config or {}
            
            account_name = credentials.get('account_name')
            account_key = credentials.get('account_key')
            connection_string = credentials.get('connection_string')
            container_name = credentials.get('container_name')
            
            if not container_name:
                raise ValueError("Azure container name is required")
            
            # Create client using connection string if provided
            if connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
            else:
                # Create client using account name and key
                if not account_name or not account_key:
                    raise ValueError("Azure account name and key are required")
                
                self.blob_service_client = BlobServiceClient(
                    account_url=f"https://{account_name}.blob.core.windows.net",
                    credential=account_key
                )
            
            # Get container client
            self.container_client = self.blob_service_client.get_container_client(container_name)
            
            # Test connection
            self.container_client.get_container_properties()
            
            logger.info(f"Azure client initialized for container: {container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure client: {str(e)}")
            raise
    
    def save_backup(self, backup_file, backup):
        """
        Save backup file to Azure Blob Storage
        
        Args:
            backup_file: Django File object or file-like object
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate blob name
            blob_name = self._generate_blob_name(backup)
            
            # Reset file pointer if it's a Django File object
            if hasattr(backup_file, 'seek'):
                backup_file.seek(0)
            
            # Create blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Set metadata
            metadata = self._create_metadata(backup)
            
            # Set blob properties
            blob_properties = {
                'content_type': 'application/octet-stream',
                'metadata': metadata
            }
            
            # Add standard tier if specified
            standard_tier = self.storage_location.config.get('standard_tier', 'Hot')
            if standard_tier in ['Hot', 'Cool', 'Archive']:
                blob_properties['standard_blob_tier'] = standard_tier
            
            # Upload file
            blob_client.upload_blob(
                backup_file,
                overwrite=True,
                blob_properties=blob_properties,
                timeout=getattr(settings, 'AZURE_UPLOAD_TIMEOUT', 3600)  # 1 hour
            )
            
            # Update backup model
            backup.file_path = f"azure://{self.container_client.container_name}/{blob_name}"
            backup.storage_location = f"azure://{self.container_client.container_name}"
            
            if hasattr(backup_file, 'size'):
                backup.file_size = backup_file.size
            
            # Generate SAS URL if needed
            if self.storage_location.config.get('generate_sas_url', False):
                backup.public_url = self._generate_sas_url(blob_name)
            
            logger.info(f"Successfully saved backup to Azure: {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save backup to Azure: {str(e)}")
            return False
    
    def delete_backup(self, backup):
        """
        Delete backup file from Azure Blob Storage
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract blob name from file path
            blob_name = self._extract_blob_name(backup.file_path)
            
            if not blob_name:
                logger.warning(f"Could not extract blob name from: {backup.file_path}")
                return False
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Delete blob
            blob_client.delete_blob()
            
            logger.info(f"Successfully deleted backup from Azure: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Backup blob not found in Azure: {blob_name}")
            return True  # Not found is considered success for deletion
        except Exception as e:
            logger.error(f"Failed to delete backup from Azure: {str(e)}")
            return False
    
    def list_backups(self, prefix=None):
        """
        List backup files from Azure Blob Storage
        
        Args:
            prefix: Optional prefix to filter results
            
        Returns:
            list: List of backup file information
        """
        try:
            # List blobs
            blobs = self.container_client.list_blobs(
                name_starts_with=prefix,
                include=['metadata']
            )
            
            backup_files = []
            for blob in blobs:
                backup_info = {
                    'name': blob.name,
                    'size': blob.size,
                    'created': blob.creation_time,
                    'modified': blob.last_modified,
                    'content_type': blob.content_settings.content_type if blob.content_settings else 'application/octet-stream',
                    'etag': blob.etag,
                    'metadata': blob.metadata or {},
                    'access_tier': blob.blob_tier if hasattr(blob, 'blob_tier') else None
                }
                backup_files.append(backup_info)
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x['created'], reverse=True)
            
            return backup_files
            
        except Exception as e:
            logger.error(f"Failed to list backups from Azure: {str(e)}")
            return []
    
    def download_backup(self, blob_name):
        """
        Download backup file from Azure Blob Storage
        
        Args:
            blob_name: Name of the blob to download
            
        Returns:
            bytes: File content, None if failed
        """
        try:
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Download blob
            blob_data = blob_client.download_blob()
            
            logger.info(f"Successfully downloaded backup from Azure: {blob_name}")
            return blob_data.readall()
            
        except ResourceNotFoundError:
            logger.warning(f"Backup blob not found in Azure: {blob_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to download backup from Azure: {str(e)}")
            return None
    
    def backup_exists(self, blob_name):
        """
        Check if backup file exists in Azure Blob Storage
        
        Args:
            blob_name: Name of the blob to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Failed to check backup existence in Azure: {str(e)}")
            return False
    
    def get_backup_info(self, blob_name):
        """
        Get backup file information from Azure Blob Storage
        
        Args:
            blob_name: Name of the blob to check
            
        Returns:
            dict: File information, None if failed
        """
        try:
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            if not blob_client.exists():
                return None
            
            # Get blob properties
            blob_properties = blob_client.get_blob_properties()
            
            return {
                'name': blob_name,
                'size': blob_properties.size,
                'created': blob_properties.creation_time,
                'modified': blob_properties.last_modified,
                'content_type': blob_properties.content_settings.content_type if blob_properties.content_settings else 'application/octet-stream',
                'etag': blob_properties.etag,
                'metadata': blob_properties.metadata or {},
                'access_tier': blob_properties.blob_tier if hasattr(blob_properties, 'blob_tier') else None,
                'lease_status': blob_properties.lease.status if hasattr(blob_properties, 'lease') else None,
                'server_encrypted': blob_properties.server_encrypted if hasattr(blob_properties, 'server_encrypted') else None
            }
            
        except ResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get backup info from Azure: {str(e)}")
            return None
    
    def get_presigned_url(self, blob_name, expiration=3600):
        """
        Generate SAS URL for backup file
        
        Args:
            blob_name: Name of the blob
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: SAS URL, None if failed
        """
        try:
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            if not blob_client.exists():
                return None
            
            # Generate SAS token
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            # Create SAS token
            sas_token = generate_blob_sas(
                account_name=self.storage_location.config.get('account_name'),
                container_name=self.container_client.container_name,
                blob_name=blob_name,
                account_key=self.storage_location.config.get('account_key'),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(seconds=expiration)
            )
            
            # Build SAS URL
            sas_url = f"https://{self.storage_location.config.get('account_name')}.blob.core.windows.net/{self.container_client.container_name}/{blob_name}?{sas_token}"
            
            return sas_url
            
        except Exception as e:
            logger.error(f"Failed to generate SAS URL for Azure: {str(e)}")
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
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # List all blobs
            blobs = self.container_client.list_blobs(
                name_starts_with=prefix,
                include=['metadata']
            )
            
            deleted_count = 0
            deleted_size = 0
            errors = []
            
            for blob in blobs:
                # Skip if blob is too new
                if blob.creation_time and blob.creation_time > cutoff_date:
                    continue
                
                try:
                    # Get size before deletion
                    size = blob.size or 0
                    
                    # Get blob client and delete
                    blob_client = self.container_client.get_blob_client(blob.name)
                    blob_client.delete_blob()
                    
                    deleted_count += 1
                    deleted_size += size
                    
                    logger.info(f"Deleted old backup from Azure: {blob.name}")
                    
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
            logger.error(f"Failed to cleanup old backups in Azure: {str(e)}")
            return {
                'deleted_count': 0,
                'deleted_size': 0,
                'errors': [str(e)],
                'success': False
            }
    
    def _generate_blob_name(self, backup):
        """
        Generate blob name for backup
        
        Args:
            backup: Backup model instance
            
        Returns:
            str: Generated blob name
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
        blob_name = f"{date_path}/{name}_{timestamp}{extension}"
        
        return blob_name
    
    def _extract_blob_name(self, file_path):
        """
        Extract blob name from Azure file path
        
        Args:
            file_path: Azure file path (azure://container-name/path/to/file)
            
        Returns:
            str: Blob name, None if invalid
        """
        if not file_path:
            return None
        
        # Remove azure://container-name/ prefix
        if file_path.startswith('azure://'):
            parts = file_path.split('/', 2)
            if len(parts) > 1:
                return parts[1]
        
        return file_path
    
    def _create_metadata(self, backup):
        """
        Create metadata dictionary for backup blob
        
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
            'storage_service': 'azure',
            'uploaded_at': datetime.utcnow().isoformat()
        }
        
        # Add any custom metadata from config
        custom_metadata = self.storage_location.config.get('custom_metadata', {})
        metadata.update(custom_metadata)
        
        return metadata
    
    def _generate_sas_url(self, blob_name, expiration=3600):
        """
        Generate SAS URL for blob
        
        Args:
            blob_name: Name of the blob
            expiration: URL expiration time in seconds
            
        Returns:
            str: SAS URL
        """
        return self.get_presigned_url(blob_name, expiration)
    
    def get_storage_usage(self):
        """
        Get storage usage statistics
        
        Returns:
            dict: Storage usage information
        """
        try:
            # Get container properties
            container_properties = self.container_client.get_container_properties()
            
            # List all blobs to calculate usage
            blobs = list(self.container_client.list_blobs())
            
            total_size = sum(blob.size for blob in blobs)
            total_count = len(blobs)
            
            return {
                'total_size': total_size,
                'total_count': total_count,
                'container_name': self.container_client.container_name,
                'last_modified': container_properties.last_modified,
                'etag': container_properties.etag
            }
            
        except Exception as e:
            logger.error(f"Failed to get Azure storage usage: {str(e)}")
            return {
                'total_size': 0,
                'total_count': 0,
                'error': str(e)
            }
    
    def test_connection(self):
        """
        Test connection to Azure Blob Storage
        
        Returns:
            dict: Connection test results
        """
        try:
            # Test container access
            self.container_client.get_container_properties()
            
            # Test list operation
            list(self.container_client.list_blobs(max_results=1))
            
            return {
                'success': True,
                'message': 'Azure connection successful',
                'container_name': self.container_client.container_name,
                'account_name': self.storage_location.config.get('account_name')
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Azure connection failed: {str(e)}',
                'error': str(e)
            }
