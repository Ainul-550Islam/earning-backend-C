"""
Test S3 Backup Service
Comprehensive tests for S3BackupService functionality
"""

import os
import tempfile
import boto3
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.services.S3BackupService import S3BackupService
from api.backup.models import Backup, BackupStorageLocation

User = get_user_model()


class S3BackupServiceTest(TestCase):
    """Test S3BackupService functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test S3 Storage',
            storage_type='s3',
            endpoint='s3.amazonaws.com/test-bucket',
            access_key='test_access_key',
            secret_key='test_secret_key',
            region='us-east-1',
            is_active=True
        )
        
        self.s3_service = S3BackupService(self.storage_location)
    
    def test_service_initialization(self):
        """Test S3BackupService initialization"""
        service = S3BackupService(self.storage_location)
        
        # Should initialize without errors
        self.assertIsNotNone(service)
        self.assertEqual(service.storage_location, self.storage_location)
        self.assertIsNotNone(service.client)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_s3_client_creation(self, mock_boto_client):
        """Test S3 client creation with correct parameters"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        service = S3BackupService(self.storage_location)
        
        # Verify boto3 client was called with correct parameters
        mock_boto_client.assert_called_once_with(
            's3',
            aws_access_key_id=self.storage_location.access_key,
            aws_secret_access_key=self.storage_location.secret_key,
            region_name=self.storage_location.region
        )
        
        self.assertEqual(service.client, mock_client)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_s3_client_creation_with_session_token(self, mock_boto_client):
        """Test S3 client creation with session token"""
        # Add session token to storage location
        self.storage_location.session_token = 'test_session_token'
        self.storage_location.save()
        
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        service = S3BackupService(self.storage_location)
        
        # Verify boto3 client was called with session token
        mock_boto_client.assert_called_once_with(
            's3',
            aws_access_key_id=self.storage_location.access_key,
            aws_secret_access_key=self.storage_location.secret_key,
            aws_session_token=self.storage_location.session_token,
            region_name=self.storage_location.region
        )
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_save_backup_success(self, mock_boto_client):
        """Test successful backup save to S3"""
        # Mock S3 client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful upload
        mock_client.upload_fileobj.return_value = {
            'ETag': '"test-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/backup.sql'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test S3 Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Verify upload was called
        mock_client.upload_fileobj.assert_called_once()
        
        # Verify bucket and key
        call_args = mock_client.upload_fileobj.call_args
        self.assertEqual(call_args[1]['Bucket'], self.storage_location.bucket_name)
        self.assertIn('test_backup.sql', call_args[1]['Key'])
        
        # Should return True on success
        self.assertTrue(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_save_backup_with_metadata(self, mock_boto_client):
        """Test backup save with metadata"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful upload
        mock_client.upload_fileobj.return_value = {
            'ETag': '"test-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/backup.sql'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup with metadata
        backup = Backup.objects.create(
            name='Test Metadata Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db',
            file_size=1024000,
            file_hash='sha256hash123',
            compression_enabled=True,
            encryption_enabled=True
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Verify metadata was included
        call_args = mock_client.upload_fileobj.call_args[1]
        metadata = call_args.get('Metadata', {})
        
        self.assertIn('file-size', metadata)
        self.assertIn('file-hash', metadata)
        self.assertIn('compression', metadata)
        self.assertIn('encryption', metadata)
        self.assertIn('backup-type', metadata)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_save_backup_with_storage_class(self, mock_boto_client):
        """Test backup save with storage class"""
        # Add storage class to storage location
        self.storage_location.storage_class = 'STANDARD_IA'
        self.storage_location.save()
        
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful upload
        mock_client.upload_fileobj.return_value = {
            'ETag': '"test-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/backup.sql'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Storage Class Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Verify storage class was included
        call_args = mock_client.upload_fileobj.call_args[1]
        self.assertEqual(call_args.get('StorageClass'), 'STANDARD_IA')
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_save_backup_multipart_upload(self, mock_boto_client):
        """Test backup save with multipart upload for large files"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock multipart upload
        mock_client.create_multipart_upload.return_value = {
            'UploadId': 'test-upload-id'
        }
        mock_client.upload_part.return_value = {
            'ETag': '"part-etag"'
        }
        mock_client.complete_multipart_upload.return_value = {
            'ETag': '"complete-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/large_backup.sql'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup with large file
        backup = Backup.objects.create(
            name='Test Large Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create large test file (> 100MB to trigger multipart)
        large_content = b'A' * (100 * 1024 * 1024)  # 100MB
        backup_file = ContentFile(large_content)
        backup_file.name = 'large_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Verify multipart upload was used
        mock_client.create_multipart_upload.assert_called_once()
        mock_client.upload_part.assert_called()
        mock_client.complete_multipart_upload.assert_called_once()
        
        self.assertTrue(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_save_backup_failure(self, mock_boto_client):
        """Test backup save failure"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock S3 upload failure
        from botocore.exceptions import ClientError
        mock_client.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'PutObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Failed Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Should return False on failure
        self.assertFalse(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_delete_backup_success(self, mock_boto_client):
        """Test successful backup deletion from S3"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful deletion
        mock_client.delete_object.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 204}
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Delete Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db',
            storage_location='test-bucket/test_backup.sql'
        )
        
        # Test delete backup
        result = service.delete_backup(backup)
        
        # Verify delete was called
        mock_client.delete_object.assert_called_once_with(
            Bucket=self.storage_location.bucket_name,
            Key='test_backup.sql'
        )
        
        self.assertTrue(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_delete_backup_not_found(self, mock_boto_client):
        """Test backup deletion when file not found"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock file not found error
        from botocore.exceptions import ClientError
        mock_client.delete_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist'}},
            'DeleteObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Not Found Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db',
            storage_location='test-bucket/nonexistent.sql'
        )
        
        # Test delete backup
        result = service.delete_backup(backup)
        
        # Should handle not found gracefully
        self.assertTrue(result)  # File not found is not an error for deletion
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_delete_backup_failure(self, mock_boto_client):
        """Test backup deletion failure"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock deletion failure
        from botocore.exceptions import ClientError
        mock_client.delete_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'DeleteObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Delete Failed Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db',
            storage_location='test-bucket/test_backup.sql'
        )
        
        # Test delete backup
        result = service.delete_backup(backup)
        
        # Should return False on failure
        self.assertFalse(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_list_backups_success(self, mock_boto_client):
        """Test successful backup listing from S3"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful list
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'backup1.sql',
                    'LastModified': datetime.now(),
                    'ETag': '"backup1-etag"',
                    'Size': 1024000,
                    'StorageClass': 'STANDARD'
                },
                {
                    'Key': 'backup2.sql',
                    'LastModified': datetime.now() - timedelta(days=1),
                    'ETag': '"backup2-etag"',
                    'Size': 2048000,
                    'StorageClass': 'STANDARD_IA'
                }
            ]
        }
        
        service = S3BackupService(self.storage_location)
        
        # Test list backups
        result = service.list_backups()
        
        # Verify list was called
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket=self.storage_location.bucket_name
        )
        
        # Should return list of backup files
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['Key'], 'backup1.sql')
        self.assertEqual(result[1]['Key'], 'backup2.sql')
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_list_backups_empty(self, mock_boto_client):
        """Test backup listing when bucket is empty"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock empty bucket
        mock_client.list_objects_v2.return_value = {
            'Contents': []
        }
        
        service = S3BackupService(self.storage_location)
        
        # Test list backups
        result = service.list_backups()
        
        # Should return empty list
        self.assertEqual(result, [])
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_list_backups_with_prefix(self, mock_boto_client):
        """Test backup listing with prefix"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock list with prefix
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'backups/daily/backup1.sql',
                    'LastModified': datetime.now(),
                    'ETag': '"backup1-etag"',
                    'Size': 1024000
                }
            ]
        }
        
        service = S3BackupService(self.storage_location)
        
        # Test list backups with prefix
        result = service.list_backups(prefix='backups/daily/')
        
        # Verify list was called with prefix
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket=self.storage_location.bucket_name,
            Prefix='backups/daily/'
        )
        
        # Should return filtered list
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['Key'], 'backups/daily/backup1.sql')
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_download_backup_success(self, mock_boto_client):
        """Test successful backup download from S3"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful download
        mock_response = {
            'Body': Mock(read=Mock(return_value=b'Test backup content')),
            'ContentLength': 1024,
            'ETag': '"test-etag"'
        }
        mock_client.get_object.return_value = mock_response
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Download Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db',
            storage_location='test-bucket/test_backup.sql'
        )
        
        # Test download backup
        result = service.download_backup('test_backup.sql')
        
        # Verify download was called
        mock_client.get_object.assert_called_once_with(
            Bucket=self.storage_location.bucket_name,
            Key='test_backup.sql'
        )
        
        # Should return file content
        self.assertEqual(result, b'Test backup content')
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_download_backup_not_found(self, mock_boto_client):
        """Test backup download when file not found"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock file not found error
        from botocore.exceptions import ClientError
        mock_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist'}},
            'GetObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Test download backup
        result = service.download_backup('nonexistent.sql')
        
        # Should return None on not found
        self.assertIsNone(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_backup_exists_true(self, mock_boto_client):
        """Test backup exists check when file exists"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful head request
        mock_client.head_object.return_value = {
            'ContentLength': 1024,
            'ETag': '"test-etag"'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Test backup exists
        result = service.backup_exists('test_backup.sql')
        
        # Verify head was called
        mock_client.head_object.assert_called_once_with(
            Bucket=self.storage_location.bucket_name,
            Key='test_backup.sql'
        )
        
        self.assertTrue(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_backup_exists_false(self, mock_boto_client):
        """Test backup exists check when file doesn't exist"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock file not found error
        from botocore.exceptions import ClientError
        mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404', 'Message': 'Not Found'}},
            'HeadObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Test backup exists
        result = service.backup_exists('nonexistent.sql')
        
        # Should return False when not found
        self.assertFalse(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_get_backup_info_success(self, mock_boto_client):
        """Test successful backup info retrieval"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful head request
        mock_client.head_object.return_value = {
            'ContentLength': 1024000,
            'ETag': '"test-etag"',
            'LastModified': datetime.now(),
            'StorageClass': 'STANDARD',
            'Metadata': {
                'file-hash': 'sha256hash123',
                'compression': 'gzip'
            }
        }
        
        service = S3BackupService(self.storage_location)
        
        # Test get backup info
        result = service.get_backup_info('test_backup.sql')
        
        # Verify head was called
        mock_client.head_object.assert_called_once_with(
            Bucket=self.storage_location.bucket_name,
            Key='test_backup.sql'
        )
        
        # Should return backup info
        self.assertEqual(result['size'], 1024000)
        self.assertEqual(result['etag'], '"test-etag"')
        self.assertIn('last_modified', result)
        self.assertIn('storage_class', result)
        self.assertIn('metadata', result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_get_presigned_url(self, mock_boto_client):
        """Test presigned URL generation"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock presigned URL generation
        mock_client.generate_presigned_url.return_value = 'https://test-bucket.s3.amazonaws.com/test_backup.sql?signature=abc'
        
        service = S3BackupService(self.storage_location)
        
        # Test get presigned URL
        url = service.get_presigned_url('test_backup.sql', expiration=3600)
        
        # Verify presigned URL was generated
        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': self.storage_location.bucket_name, 'Key': 'test_backup.sql'},
            ExpiresIn=3600
        )
        
        self.assertEqual(url, 'https://test-bucket.s3.amazonaws.com/test_backup.sql?signature=abc')
    
    def test_get_presigned_url_default_expiration(self, mock_boto_client):
        """Test presigned URL with default expiration"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_client.generate_presigned_url.return_value = 'https://test-bucket.s3.amazonaws.com/test_backup.sql?signature=abc'
        
        service = S3BackupService(self.storage_location)
        
        # Test get presigned URL without expiration
        url = service.get_presigned_url('test_backup.sql')
        
        # Should use default expiration (1 hour)
        mock_client.generate_presigned_url.assert_called_once()
        call_args = mock_client.generate_presigned_url.call_args[1]
        expiration = call_args.get('ExpiresIn', 3600)
        
        # Default should be 3600 seconds (1 hour)
        self.assertEqual(expiration, 3600)


class S3BackupServiceErrorHandlingTest(TestCase):
    """Test S3BackupService error handling"""
    
    def setUp(self):
        """Set up test data"""
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test S3 Storage',
            storage_type='s3',
            endpoint='s3.amazonaws.com/test-bucket',
            access_key='test_access_key',
            secret_key='test_secret_key',
            region='us-east-1',
            is_active=True
        )
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_invalid_credentials_error(self, mock_boto_client):
        """Test handling of invalid credentials"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock authentication error
        from botocore.exceptions import ClientError
        mock_client.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'InvalidAccessKeyId', 'Message': 'The AWS Access Key Id you provided does not exist in our records'}},
            'PutObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Invalid Credentials',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Should handle authentication error gracefully
        self.assertFalse(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_network_timeout_error(self, mock_boto_client):
        """Test handling of network timeout"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock network timeout
        from botocore.exceptions import ReadTimeoutError
        mock_client.upload_fileobj.side_effect = ReadTimeoutError(endpoint_url='https://s3.amazonaws.com/test-bucket')
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Timeout Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Should handle timeout gracefully
        self.assertFalse(result)
    
    def test_missing_storage_location_config(self):
        """Test service with missing storage location config"""
        # Create storage location with missing required fields
        incomplete_storage = BackupStorageLocation.objects.create(
            name='Incomplete Storage',
            storage_type='s3',
            # Missing access_key, secret_key, bucket_name
            is_active=True
        )
        
        # Should handle missing config gracefully
        with self.assertRaises(ValueError):
            S3BackupService(incomplete_storage)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_bucket_not_found_error(self, mock_boto_client):
        """Test handling of bucket not found error"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock bucket not found error
        from botocore.exceptions import ClientError
        mock_client.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}},
            'PutObject'
        )
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Bucket Not Found',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create test file
        test_content = b'Test backup content'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test save backup
        result = service.save_backup(backup_file, backup)
        
        # Should handle bucket not found gracefully
        self.assertFalse(result)


class S3BackupServicePerformanceTest(TestCase):
    """Test S3BackupService performance characteristics"""
    
    def setUp(self):
        """Set up test data"""
        self.storage_location = BackupStorageLocation.objects.create(
            name='Performance Test Storage',
            storage_type='s3',
            endpoint='s3.amazonaws.com/performance-test-bucket',
            access_key='test_access_key',
            secret_key='test_secret_key',
            region='us-east-1',
            is_active=True
        )
        
        self.s3_service = S3BackupService(self.storage_location)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_concurrent_uploads(self, mock_boto_client):
        """Test concurrent upload operations"""
        import threading
        import time
        
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock successful upload
        mock_client.upload_fileobj.return_value = {
            'ETag': '"concurrent-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/concurrent_backup.sql'
        }
        
        results = []
        errors = []
        
        def upload_backup(index):
            try:
                # Create test backup
                backup = Backup.objects.create(
                    name=f'Concurrent Backup {index}',
                    backup_type='full',
                    storage_type='s3',
                    database_name='test_db'
                )
                
                # Create test file
                test_content = f'Concurrent backup content {index}'.encode()
                backup_file = ContentFile(test_content)
                backup_file.name = f'concurrent_backup_{index}.sql'
                
                # Test upload
                service = S3BackupService(self.storage_location)
                result = service.save_backup(backup_file, backup)
                results.append(result)
                
            except Exception as e:
                errors.append(e)
        
        # Create multiple upload threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=upload_backup, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all uploads completed
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)
        for result in results:
            self.assertTrue(result)
    
    @patch('backup.services.S3BackupService.boto3.client')
    def test_large_file_upload_performance(self, mock_boto_client):
        """Test large file upload performance"""
        import time
        
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock multipart upload for large file
        mock_client.create_multipart_upload.return_value = {
            'UploadId': 'large-file-upload-id'
        }
        mock_client.upload_part.return_value = {
            'ETag': '"large-part-etag"'
        }
        mock_client.complete_multipart_upload.return_value = {
            'ETag': '"large-complete-etag"',
            'Location': 'https://s3.amazonaws.com/test-bucket/large_backup.sql'
        }
        
        service = S3BackupService(self.storage_location)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Large Performance Backup',
            backup_type='full',
            storage_type='s3',
            database_name='test_db'
        )
        
        # Create large test file (50MB)
        large_content = b'A' * (50 * 1024 * 1024)
        backup_file = ContentFile(large_content)
        backup_file.name = 'large_backup.sql'
        
        # Measure upload time
        start_time = time.time()
        result = service.save_backup(backup_file, backup)
        end_time = time.time()
        
        # Verify multipart upload was used
        mock_client.create_multipart_upload.assert_called_once()
        self.assertTrue(result)
        
        # Should complete within reasonable time (less than 30 seconds)
        upload_time = end_time - start_time
        self.assertLess(upload_time, 30.0)
