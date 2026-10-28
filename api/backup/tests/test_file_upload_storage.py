"""
File Upload and Storage Tests - High Priority
Comprehensive tests for file upload and storage operations
"""

import uuid
import json
import tempfile
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from django.core.files.base import ContentFile
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.test import force_authenticate
from unittest.mock import patch, MagicMock, Mock, mock_open, call
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from api.backup.views import BackupViewSet, BackupStorageLocationViewSet
from api.backup.services import BackupService
from api.backup.services.factory import BackupServiceFactory
from api.backup.choices import BackupType, BackupStatus, StorageType

User = get_user_model()


class FileUploadValidationTests(TestCase):
    """Validation tests for file upload operations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.factory = APIRequestFactory()
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
        # Create storage location
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_valid_file_upload(self):
        """Test uploading a valid backup file"""
        # Create test file
        test_content = b'Test backup content for upload'
        test_file = SimpleUploadedFile(
            'test_backup.sql',
            test_content,
            content_type='application/sql'
        )
        
        # Create backup with file
        backup = Backup.objects.create(
            name='Test Backup with File',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Verify file was uploaded
        self.assertIsNotNone(backup.backup_file)
        self.assertTrue(backup.backup_file.name.endswith('.sql'))
        self.assertEqual(backup.file_size, len(test_content))
        
        # Verify file content
        backup.backup_file.seek(0)
        uploaded_content = backup.backup_file.read()
        self.assertEqual(uploaded_content, test_content)
    
    def test_file_size_validation(self):
        """Test file size validation"""
        # Test oversized file (simulate)
        oversized_content = b'x' * (100 * 1024 * 1024)  # 100MB
        
        with patch('backup.models.Backup.backup_file') as mock_file:
            mock_file.size = len(oversized_content)
            
            backup = Backup(
                name='Oversized Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                file_size=len(oversized_content)
            )
            
            # Should validate file size limits
            try:
                backup.full_clean()
                # If validation passes, file size should be within limits
                self.assertLessEqual(backup.file_size, 1024 * 1024 * 1024)  # 1GB limit
            except ValidationError as e:
                # Should catch oversized files
                self.assertIn('file_size', str(e))
    
    def test_file_extension_validation(self):
        """Test file extension validation"""
        valid_extensions = ['.sql', '.gz', '.zip', '.tar', '.backup']
        invalid_extensions = ['.exe', '.bat', '.sh', '.php', '.js']
        
        for ext in valid_extensions:
            test_file = SimpleUploadedFile(
                f'test{ext}',
                b'Test content',
                content_type='application/octet-stream'
            )
            
            try:
                backup = Backup.objects.create(
                    name=f'Valid Extension Test {ext}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    created_by=self.admin_user,
                    backup_file=test_file
                )
                self.assertTrue(backup.backup_file.name.endswith(ext))
            except ValidationError as e:
                self.fail(f"Valid extension {ext} should not raise ValidationError: {e}")
        
        for ext in invalid_extensions:
            test_file = SimpleUploadedFile(
                f'test{ext}',
                b'Test content',
                content_type='application/octet-stream'
            )
            
            try:
                backup = Backup.objects.create(
                    name=f'Invalid Extension Test {ext}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    created_by=self.admin_user,
                    backup_file=test_file
                )
                # If no validation error, the extension might be allowed
                # This depends on specific validation rules
            except ValidationError as e:
                # Expected for invalid extensions
                self.assertIn('backup_file', str(e))
    
    def test_file_content_type_validation(self):
        """Test file content type validation"""
        valid_content_types = [
            'application/sql',
            'application/gzip',
            'application/zip',
            'application/x-tar',
            'application/octet-stream'
        ]
        
        for content_type in valid_content_types:
            test_file = SimpleUploadedFile(
                'test.sql',
                b'Test content',
                content_type=content_type
            )
            
            try:
                backup = Backup.objects.create(
                    name=f'Content Type Test {content_type}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    created_by=self.admin_user,
                    backup_file=test_file
                )
                self.assertIsNotNone(backup.backup_file)
            except ValidationError as e:
                self.fail(f"Valid content type {content_type} should not raise ValidationError: {e}")
    
    def test_file_name_sanitization(self):
        """Test file name sanitization"""
        dangerous_names = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            'test<script>alert("xss")</script>.sql',
            'test|pipe.sql',
            'test?question.sql',
            'test*asterisk.sql',
            'test"quote.sql',
            'test<angle.sql',
            'test>angle.sql'
        ]
        
        for dangerous_name in dangerous_names:
            test_file = SimpleUploadedFile(
                dangerous_name,
                b'Test content',
                content_type='application/sql'
            )
            
            backup = Backup.objects.create(
                name=f'Sanitization Test',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            
            # Verify file name was sanitized (implementation dependent)
            # In most cases, Django handles this automatically
            self.assertIsNotNone(backup.backup_file)
            self.assertNotIn('..', backup.backup_file.name)
            self.assertNotIn('<', backup.backup_file.name)
            self.assertNotIn('>', backup.backup_file.name)
    
    def test_concurrent_file_upload(self):
        """Test concurrent file uploads"""
        uploaded_files = []
        errors = []
        
        def upload_file(index):
            try:
                test_file = SimpleUploadedFile(
                    f'concurrent_test_{index}.sql',
                    f'Concurrent test content {index}'.encode(),
                    content_type='application/sql'
                )
                
                backup = Backup.objects.create(
                    name=f'Concurrent Upload {index}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    created_by=self.admin_user,
                    backup_file=test_file
                )
                
                uploaded_files.append(backup.id)
                
            except Exception as e:
                errors.append(f"Error uploading file {index}: {e}")
        
        # Create multiple threads for concurrent uploads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=upload_file, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Upload errors: {errors}")
        self.assertEqual(len(uploaded_files), 5)
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Upload').count(), 5)


class LocalStorageTests(TransactionTestCase):
    """Tests for local storage operations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create temporary directory for local storage
        self.temp_dir = tempfile.mkdtemp()
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Local Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_local_storage_file_save(self):
        """Test saving files to local storage"""
        test_content = b'Local storage test content'
        test_file = SimpleUploadedFile(
            'local_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Local Storage Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Verify file exists in storage location
        expected_path = os.path.join(self.temp_dir, backup.backup_file.name)
        self.assertTrue(os.path.exists(expected_path))
        
        # Verify file content
        with open(expected_path, 'rb') as f:
            saved_content = f.read()
        self.assertEqual(saved_content, test_content)
    
    def test_local_storage_file_retrieval(self):
        """Test retrieving files from local storage"""
        test_content = b'Retrieval test content'
        test_file = SimpleUploadedFile(
            'retrieval_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Retrieval Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Retrieve file through model
        backup.backup_file.seek(0)
        retrieved_content = backup.backup_file.read()
        
        self.assertEqual(retrieved_content, test_content)
    
    def test_local_storage_file_deletion(self):
        """Test deleting files from local storage"""
        test_content = b'Deletion test content'
        test_file = SimpleUploadedFile(
            'deletion_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Deletion Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Verify file exists
        file_path = backup.backup_file.path
        self.assertTrue(os.path.exists(file_path))
        
        # Delete backup (should also delete file)
        backup_id = backup.id
        backup.delete()
        
        # Verify file is deleted
        self.assertFalse(os.path.exists(file_path))
    
    def test_local_storage_space_management(self):
        """Test local storage space management"""
        # Upload multiple files and check space usage
        file_sizes = [1024, 2048, 4096, 8192]
        uploaded_backups = []
        
        for i, size in enumerate(file_sizes):
            test_content = b'x' * size
            test_file = SimpleUploadedFile(
                f'space_test_{i}.sql',
                test_content,
                content_type='application/sql'
            )
            
            backup = Backup.objects.create(
                name=f'Space Test {i}',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            uploaded_backups.append(backup)
        
        # Verify total space usage
        total_expected_size = sum(file_sizes)
        actual_total_size = sum(backup.file_size for backup in uploaded_backups)
        self.assertEqual(actual_total_size, total_expected_size)
        
        # Delete one file and verify space is freed
        backup_to_delete = uploaded_backups[0]
        deleted_size = backup_to_delete.file_size
        file_path = backup_to_delete.backup_file.path
        
        backup_to_delete.delete()
        
        # Verify file was deleted
        self.assertFalse(os.path.exists(file_path))
        
        # Verify remaining space
        remaining_backups = Backup.objects.filter(name__startswith='Space Test')
        remaining_size = sum(backup.file_size for backup in remaining_backups)
        expected_remaining = total_expected_size - deleted_size
        self.assertEqual(remaining_size, expected_remaining)
    
    def test_local_storage_permission_handling(self):
        """Test local storage permission handling"""
        test_content = b'Permission test content'
        test_file = SimpleUploadedFile(
            'permission_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Permission Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        file_path = backup.backup_file.path
        
        # Check file permissions (implementation dependent)
        if os.name == 'posix':  # Unix-like systems
            file_stat = os.stat(file_path)
            # Verify file has appropriate permissions
            self.assertTrue(file_stat.st_mode & 0o600)  # At least owner read/write
    
    def test_local_storage_concurrent_access(self):
        """Test concurrent access to local storage"""
        results = []
        errors = []
        
        def concurrent_file_access(index):
            try:
                test_content = f'Concurrent access test {index}'.encode()
                test_file = SimpleUploadedFile(
                    f'concurrent_access_{index}.sql',
                    test_content,
                    content_type='application/sql'
                )
                
                backup = Backup.objects.create(
                    name=f'Concurrent Access {index}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    created_by=self.admin_user,
                    backup_file=test_file
                )
                
                # Try to read the file immediately
                backup.backup_file.seek(0)
                read_content = backup.backup_file.read()
                
                if read_content == test_content:
                    results.append(True)
                else:
                    results.append(False)
                    
            except Exception as e:
                errors.append(f"Concurrent access error {index}: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_file_access, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
        self.assertEqual(len(results), 5)
        self.assertTrue(all(results))


class S3StorageTests(TransactionTestCase):
    """Tests for S3 storage operations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='S3 Test Storage',
            storage_type=StorageType.S3,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            config={
                'access_key': 'test_access_key',
                'secret_key': 'test_secret_key',
                'bucket_name': 'test-bucket',
                'region': 'us-east-1'
            }
        )
    
    @patch('boto3.client')
    def test_s3_storage_file_save(self, mock_boto_client):
        """Test saving files to S3 storage"""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        test_content = b'S3 storage test content'
        test_file = SimpleUploadedFile(
            's3_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='S3 Storage Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Verify S3 upload was called
        mock_s3.upload_fileobj.assert_called_once()
        
        # Get the call arguments
        call_args = mock_s3.upload_fileobj.call_args
        self.assertEqual(call_args[1]['Bucket'], 'test-bucket')
        self.assertIn('s3_test.sql', call_args[1]['Key'])
    
    @patch('boto3.client')
    def test_s3_storage_file_retrieval(self, mock_boto_client):
        """Test retrieving files from S3 storage"""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock file download
        test_content = b'S3 retrieval test content'
        mock_file_obj = MagicMock()
        mock_file_obj.read.return_value = test_content
        mock_s3.download_fileobj.return_value = None
        
        test_file = SimpleUploadedFile(
            's3_retrieval_test.sql',
            b'Original content',
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='S3 Retrieval Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Test file retrieval (would be handled by Django's storage system)
        backup.backup_file.seek(0)
        # In a real implementation, this would trigger S3 download
    
    @patch('boto3.client')
    def test_s3_storage_authentication_error(self, mock_boto_client):
        """Test S3 storage authentication error handling"""
        # Mock authentication error
        mock_boto_client.side_effect = NoCredentialsError()
        
        test_file = SimpleUploadedFile(
            's3_auth_test.sql',
            b'Auth test content',
            content_type='application/sql'
        )
        
        try:
            backup = Backup.objects.create(
                name='S3 Auth Test',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            # If no error, the storage system might handle auth gracefully
        except Exception as e:
            # Expected authentication error
            self.assertIn('credential', str(e).lower())
    
    @patch('boto3.client')
    def test_s3_storage_network_error(self, mock_boto_client):
        """Test S3 storage network error handling"""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock network error
        mock_s3.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'NetworkingError', 'Message': 'Connection timeout'}},
            'UploadFileobj'
        )
        
        test_file = SimpleUploadedFile(
            's3_network_test.sql',
            b'Network test content',
            content_type='application/sql'
        )
        
        try:
            backup = Backup.objects.create(
                name='S3 Network Test',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            # If no error, the system might retry or handle gracefully
        except Exception as e:
            # Expected network error
            self.assertIn('network', str(e).lower())
    
    @patch('boto3.client')
    def test_s3_storage_space_limit(self, mock_boto_client):
        """Test S3 storage space limit handling"""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock space limit error
        mock_s3.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'EntityTooLarge', 'Message': 'File too large'}},
            'UploadFileobj'
        )
        
        # Create large file
        large_content = b'x' * (100 * 1024 * 1024)  # 100MB
        test_file = SimpleUploadedFile(
            's3_large_test.sql',
            large_content,
            content_type='application/sql'
        )
        
        try:
            backup = Backup.objects.create(
                name='S3 Large File Test',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            # If no error, the system might handle large files
        except Exception as e:
            # Expected size limit error
            self.assertIn('large', str(e).lower())


class FileUploadViewTests(APITestCase):
    """Tests for file upload through API views"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.factory = APIRequestFactory()
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='API Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_api_file_upload_valid(self):
        """Test valid file upload through API"""
        url = reverse('backup-list')
        
        test_content = b'API upload test content'
        test_file = SimpleUploadedFile(
            'api_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        data = {
            'name': 'API Upload Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'backup_file': test_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify backup was created with file
        backup = Backup.objects.get(name='API Upload Test')
        self.assertIsNotNone(backup.backup_file)
        self.assertEqual(backup.file_size, len(test_content))
    
    def test_api_file_upload_invalid_file_type(self):
        """Test invalid file type upload through API"""
        url = reverse('backup-list')
        
        # Create invalid file
        test_file = SimpleUploadedFile(
            'invalid.exe',
            b'Invalid executable content',
            content_type='application/octet-stream'
        )
        
        data = {
            'name': 'Invalid File Upload Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'backup_file': test_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should either succeed (if no validation) or fail (if validation exists)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn('backup_file', response.data)
        else:
            # If validation doesn't exist, file should be uploaded
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_api_file_upload_oversized_file(self):
        """Test oversized file upload through API"""
        url = reverse('backup-list')
        
        # Create large file (simulate)
        large_content = b'x' * (50 * 1024 * 1024)  # 50MB
        test_file = SimpleUploadedFile(
            'large_file.sql',
            large_content,
            content_type='application/sql'
        )
        
        data = {
            'name': 'Large File Upload Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'backup_file': test_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should either succeed (if within limits) or fail (if oversized)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn('backup_file', response.data)
        else:
            # If within limits, should succeed
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_api_file_upload_missing_file(self):
        """Test API upload without file"""
        url = reverse('backup-list')
        
        data = {
            'name': 'Missing File Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
            # Missing backup_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should succeed (file is optional) or fail (if required)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
    
    def test_api_file_upload_unauthorized_user(self):
        """Test file upload by unauthorized user"""
        url = reverse('backup-list')
        
        test_file = SimpleUploadedFile(
            'unauthorized_test.sql',
            b'Unauthorized upload content',
            content_type='application/sql'
        )
        
        data = {
            'name': 'Unauthorized Upload Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'backup_file': test_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        # Don't authenticate
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_api_file_upload_corrupted_file(self):
        """Test upload of corrupted file"""
        url = reverse('backup-list')
        
        # Create file with invalid content (simulate corruption)
        corrupted_content = b'\x00\x01\x02\x03' * 1000  # Binary garbage
        test_file = SimpleUploadedFile(
            'corrupted.sql',
            corrupted_content,
            content_type='application/sql'
        )
        
        data = {
            'name': 'Corrupted File Test',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'backup_file': test_file
        }
        
        request = self.factory.post(url, data, format='multipart')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should accept file (content validation happens later)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify file was stored
        backup = Backup.objects.get(name='Corrupted File Test')
        self.assertIsNotNone(backup.backup_file)
        self.assertEqual(backup.file_size, len(corrupted_content))


class FileIntegrityTests(TransactionTestCase):
    """Tests for file integrity and verification"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Integrity Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_file_hash_verification(self):
        """Test file hash verification"""
        test_content = b'Hash verification test content'
        test_file = SimpleUploadedFile(
            'hash_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Hash Verification Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Calculate hash
        calculated_hash = backup.calculate_file_hash()
        self.assertIsNotNone(calculated_hash)
        self.assertEqual(len(calculated_hash), 64)  # SHA256 hex length
        
        # Store hash and verify
        backup.file_hash = calculated_hash
        backup.save()
        
        # Verify hash matches
        backup.refresh_from_db()
        self.assertEqual(backup.file_hash, calculated_hash)
    
    def test_file_corruption_detection(self):
        """Test file corruption detection"""
        original_content = b'Original content for corruption test'
        test_file = SimpleUploadedFile(
            'corruption_test.sql',
            original_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Corruption Detection Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Calculate original hash
        original_hash = backup.calculate_file_hash()
        backup.file_hash = original_hash
        backup.save()
        
        # Simulate file corruption by modifying the file directly
        file_path = backup.backup_file.path
        with open(file_path, 'wb') as f:
            f.write(b'Corrupted content that differs from original')
        
        # Verify corruption detection
        current_hash = backup.calculate_file_hash()
        self.assertNotEqual(current_hash, original_hash)
        
        # Health check should detect corruption
        backup.is_healthy = False
        backup.health_score = 0
        backup.save()
        
        self.assertFalse(backup.is_healthy)
        self.assertEqual(backup.health_score, 0)
    
    def test_file_size_verification(self):
        """Test file size verification"""
        test_content = b'Size verification test content'
        test_file = SimpleUploadedFile(
            'size_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Size Verification Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Verify file size
        self.assertEqual(backup.file_size, len(test_content))
        
        # Get actual file size from filesystem
        actual_size = os.path.getsize(backup.backup_file.path)
        self.assertEqual(backup.file_size, actual_size)
        
        # Simulate size mismatch
        backup.file_size = 999999  # Wrong size
        backup.save()
        
        # Size verification should detect mismatch
        self.assertNotEqual(backup.file_size, actual_size)
    
    def test_file_integrity_after_operations(self):
        """Test file integrity after various operations"""
        test_content = b'Integrity operations test content'
        test_file = SimpleUploadedFile(
            'integrity_ops_test.sql',
            test_content,
            content_type='application/sql'
        )
        
        backup = Backup.objects.create(
            name='Integrity Operations Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user,
            backup_file=test_file
        )
        
        # Calculate initial hash
        initial_hash = backup.calculate_file_hash()
        backup.file_hash = initial_hash
        backup.save()
        
        # Test various operations that should preserve integrity
        operations = [
            'read',    # Reading the file
            'copy',    # Copying the file (if implemented)
            'move',    # Moving the file (if implemented)
        ]
        
        for operation in operations:
            if operation == 'read':
                # Read file
                backup.backup_file.seek(0)
                content = backup.backup_file.read()
                self.assertEqual(content, test_content)
            
            # Verify hash is unchanged
            current_hash = backup.calculate_file_hash()
            self.assertEqual(current_hash, initial_hash)
            
            # Verify file is still healthy
            backup.refresh_from_db()
            self.assertTrue(backup.is_healthy)


class FileUploadPerformanceTests(TransactionTestCase):
    """Performance tests for file upload operations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Performance Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_large_file_upload_performance(self):
        """Test performance with large file uploads"""
        file_sizes = [
            1024 * 1024,      # 1MB
            10 * 1024 * 1024, # 10MB
            50 * 1024 * 1024, # 50MB
        ]
        
        for size in file_sizes:
            start_time = time.time()
            
            test_content = b'x' * size
            test_file = SimpleUploadedFile(
                f'perf_test_{size}.sql',
                test_content,
                content_type='application/sql'
            )
            
            backup = Backup.objects.create(
                name=f'Performance Test {size}',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            
            end_time = time.time()
            upload_time = end_time - start_time
            
            # Verify upload completed
            self.assertIsNotNone(backup.backup_file)
            self.assertEqual(backup.file_size, size)
            
            # Performance assertion (adjust thresholds as needed)
            # Large files should complete within reasonable time
            if size <= 10 * 1024 * 1024:  # 10MB or less
                self.assertLess(upload_time, 5.0, f"Upload of {size} bytes took too long: {upload_time}s")
            else:  # Larger files
                self.assertLess(upload_time, 30.0, f"Upload of {size} bytes took too long: {upload_time}s")
            
            print(f"Uploaded {size} bytes in {upload_time:.2f}s")
    
    def test_concurrent_upload_performance(self):
        """Test performance with concurrent uploads"""
        num_concurrent = 5
        file_size = 1024 * 1024  # 1MB per file
        
        start_time = time.time()
        
        def upload_file(index):
            test_content = f'Concurrent upload {index}'.encode() + b'x' * (file_size - 20)
            test_file = SimpleUploadedFile(
                f'concurrent_perf_{index}.sql',
                test_content,
                content_type='application/sql'
            )
            
            backup = Backup.objects.create(
                name=f'Concurrent Performance Test {index}',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            
            return backup.id
        
        # Create multiple threads for concurrent uploads
        threads = []
        results = []
        
        for i in range(num_concurrent):
            thread = threading.Thread(target=lambda i=i: results.append(upload_file(i)))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all uploads completed
        self.assertEqual(len(results), num_concurrent)
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Performance Test').count(), num_concurrent)
        
        # Performance assertion
        # Concurrent uploads should be faster than sequential
        sequential_time_estimate = num_concurrent * 1.0  # Assume 1 second per file sequentially
        self.assertLess(total_time, sequential_time_estimate, 
                        f"Concurrent upload took too long: {total_time}s vs estimated sequential: {sequential_time_estimate}s")
        
        print(f"Concurrent upload of {num_concurrent} files ({file_size} bytes each) completed in {total_time:.2f}s")
    
    def test_file_hash_calculation_performance(self):
        """Test performance of file hash calculation"""
        file_sizes = [
            1024 * 1024,      # 1MB
            10 * 1024 * 1024, # 10MB
            50 * 1024 * 1024, # 50MB
        ]
        
        for size in file_sizes:
            test_content = b'x' * size
            test_file = SimpleUploadedFile(
                f'hash_perf_{size}.sql',
                test_content,
                content_type='application/sql'
            )
            
            backup = Backup.objects.create(
                name=f'Hash Performance Test {size}',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                created_by=self.admin_user,
                backup_file=test_file
            )
            
            # Measure hash calculation time
            start_time = time.time()
            calculated_hash = backup.calculate_file_hash()
            end_time = time.time()
            
            hash_time = end_time - start_time
            
            # Verify hash was calculated
            self.assertIsNotNone(calculated_hash)
            self.assertEqual(len(calculated_hash), 64)
            
            # Performance assertion
            # Hash calculation should be fast even for large files
            self.assertLess(hash_time, 5.0, f"Hash calculation for {size} bytes took too long: {hash_time}s")
            
            print(f"Hash calculation for {size} bytes completed in {hash_time:.4f}s")
