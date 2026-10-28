"""
Storage Adapter Tests - Adapter Pattern
Tests for storage adapters using the new adapter pattern.
"""

import unittest
import tempfile
import shutil
import os
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from api.backup.services.storage.base import (
    StorageAdapterInterface,
    StorageAdapterFactory,
    StorageError,
    StorageConnectionError,
    StorageValidationError
)
from api.backup.services.storage.local_adapter import LocalStorageAdapter
from api.backup.services.storage.s3_adapter import S3StorageAdapter
from api.backup.services.storage.factory import BackupStorageFactory, create_storage_adapter

User = get_user_model()


class StorageAdapterFactoryTests(TestCase):
    """Tests for storage adapter factory."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = BackupStorageFactory()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test data."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_get_local_adapter(self):
        """Test getting local storage adapter."""
        config = {'base_path': self.temp_dir}
        adapter = self.factory.get_adapter('local', config)
        
        self.assertIsInstance(adapter, LocalStorageAdapter)
        self.assertEqual(adapter.base_path, self.temp_dir)
    
    def test_get_s3_adapter(self):
        """Test getting S3 storage adapter."""
        config = {
            'access_key': 'test_key',
            'secret_key': 'test_secret',
            'bucket_name': 'test-bucket',
            'region': 'us-east-1'
        }
        
        with patch('backup.services.storage.s3_adapter.boto3.client') as mock_boto:
            mock_client = Mock()
            mock_boto.return_value = mock_client
            mock_client.head_bucket.return_value = {}
            
            adapter = self.factory.get_adapter('s3', config)
            
            self.assertIsInstance(adapter, S3StorageAdapter)
            self.assertEqual(adapter.bucket_name, 'test-bucket')
            self.assertEqual(adapter.region, 'us-east-1')
    
    def test_unsupported_adapter_type(self):
        """Test getting unsupported adapter type."""
        with self.assertRaises(ValueError) as context:
            self.factory.get_adapter('unsupported', {})
        
        self.assertIn('Unsupported storage type', str(context.exception))
    
    def test_get_available_types(self):
        """Test getting available adapter types."""
        types = self.factory.get_available_types()
        
        self.assertIn('local', types)
        self.assertIn('s3', types)
        self.assertIsInstance(types, list)
    
    def test_validate_local_config(self):
        """Test validating local storage config."""
        valid_config = {'base_path': self.temp_dir}
        invalid_config = {'base_path': None}
        
        self.assertTrue(self.factory.validate_config('local', valid_config))
        self.assertFalse(self.factory.validate_config('local', invalid_config))
    
    def test_validate_s3_config(self):
        """Test validating S3 storage config."""
        valid_config = {
            'access_key': 'test_key',
            'secret_key': 'test_secret',
            'bucket_name': 'test-bucket'
        }
        
        with patch('backup.services.storage.s3_adapter.boto3.client'):
            self.assertTrue(self.factory.validate_config('s3', valid_config))
        
        invalid_config = {'access_key': 'test_key'}  # Missing required fields
        self.assertFalse(self.factory.validate_config('s3', invalid_config))


class LocalStorageAdapterTests(TestCase):
    """Tests for local storage adapter."""
    
    def setUp(self):
        """Set up test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'base_path': self.temp_dir,
            'create_dirs': True,
            'backup_subdir': 'test_backups'
        }
        self.adapter = LocalStorageAdapter(self.config)
        
        # Create test backup mock
        self.backup = Mock()
        self.backup.backup_id = 'test-backup-id'
        self.backup.name = 'Test Backup'
        self.backup.created_at = Mock()
        self.backup.created_at.strftime = Mock(return_value='2024/01/01')
        self.backup.compression_enabled = False
        self.backup.file_path = None
    
    def tearDown(self):
        """Clean up test data."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_save_backup(self):
        """Test saving backup to local storage."""
        test_content = b'Test backup content'
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            result = self.adapter.save_backup(test_file, self.backup)
            
            self.assertTrue(result)
            self.assertIsNotNone(self.backup.file_path)
    
    def test_save_backup_creates_directories(self):
        """Test that save_backup creates necessary directories."""
        test_content = b'Test backup content'
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            self.adapter.save_backup(test_file, self.backup)
            
            # Check that directory was created
            expected_dir = os.path.join(self.temp_dir, 'test_backups', '2024', '01', '01')
            self.assertTrue(os.path.exists(expected_dir))
    
    def test_backup_exists(self):
        """Test checking if backup exists."""
        # First save a backup
        test_content = b'Test backup content'
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            self.adapter.save_backup(test_file, self.backup)
            
            # Now check if it exists
            exists = self.adapter.backup_exists(self.backup)
            self.assertTrue(exists)
    
    def test_backup_not_exists(self):
        """Test checking if non-existent backup exists."""
        self.backup.file_path = 'non/existent/path.sql'
        
        exists = self.adapter.backup_exists(self.backup)
        self.assertFalse(exists)
    
    def test_get_backup_size(self):
        """Test getting backup file size."""
        # Create a test file
        test_content = b'Test backup content' * 100  # Make it larger
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            self.adapter.save_backup(test_file, self.backup)
            
            # Get size
            size = self.adapter.get_backup_size(self.backup)
            self.assertEqual(size, len(test_content))
    
    def test_delete_backup(self):
        """Test deleting backup file."""
        # First save a backup
        test_content = b'Test backup content'
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            self.adapter.save_backup(test_file, self.backup)
            
            # Now delete it
            result = self.adapter.delete_backup(self.backup)
            self.assertTrue(result)
            
            # Check that file no longer exists
            exists = self.adapter.backup_exists(self.backup)
            self.assertFalse(exists)
    
    def test_list_backups(self):
        """Test listing backups."""
        # Create multiple test files
        for i in range(3):
            backup = Mock()
            backup.backup_id = f'test-backup-{i}'
            backup.name = f'Test Backup {i}'
            backup.created_at = Mock()
            backup.created_at.strftime = Mock(return_value='2024/01/01')
            backup.compression_enabled = False
            
            test_content = f'Test backup content {i}'.encode()
            test_file = Mock()
            test_file.seek = Mock()
            test_file.seek.return_value = None
            
            with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
                self.adapter.save_backup(test_file, backup)
        
        # List backups
        backups = self.adapter.list_backups()
        
        self.assertEqual(len(backups), 3)
        self.assertIsInstance(backups, list)
    
    def test_get_storage_stats(self):
        """Test getting storage statistics."""
        # Create a test backup
        test_content = b'Test backup content'
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            self.adapter.save_backup(test_file, self.backup)
            
            # Get stats
            stats = self.adapter.get_storage_stats()
            
            self.assertIn('total_objects', stats)
            self.assertIn('total_size_bytes', stats)
            self.assertIn('total_size_mb', stats)
            self.assertIn('adapter', stats)
            self.assertEqual(stats['adapter'], 'Local')
            self.assertEqual(stats['total_objects'], 1)
    
    def test_test_connection(self):
        """Test connection to local storage."""
        result = self.adapter.test_connection()
        self.assertTrue(result)
    
    def test_validate_config(self):
        """Test configuration validation."""
        valid_config = {'base_path': self.temp_dir}
        invalid_config = {'base_path': None}
        
        self.assertTrue(self.adapter.validate_config(valid_config))
        self.assertFalse(self.adapter.validate_config(invalid_config))
    
    def test_get_adapter_info(self):
        """Test getting adapter information."""
        info = self.adapter.get_adapter_info()
        
        self.assertIn('name', info)
        self.assertIn('type', info)
        self.assertIn('version', info)
        self.assertIn('capabilities', info)
        self.assertEqual(info['name'], 'LocalStorageAdapter')
        self.assertEqual(info['type'], 'storage_adapter')


class S3StorageAdapterTests(TestCase):
    """Tests for S3 storage adapter."""
    
    def setUp(self):
        """Set up test data."""
        self.config = {
            'access_key': 'test_access_key',
            'secret_key': 'test_secret_key',
            'bucket_name': 'test-bucket',
            'region': 'us-east-1'
        }
        
        # Mock S3 client
        self.mock_client = Mock()
        self.mock_client.head_bucket.return_value = {}
        self.mock_client.upload_fileobj.return_value = {}
        self.mock_client.get_object.return_value = {'Body': Mock()}
        self.mock_client.delete_object.return_value = {}
        self.mock_client.head_object.return_value = {'ContentLength': 1000}
        self.mock_client.generate_presigned_url.return_value = 'https://test-bucket.s3.amazonaws.com/test-file'
        self.mock_client.list_objects_v2.return_value = {'Contents': []}
        
    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            
            self.assertEqual(adapter.bucket_name, 'test-bucket')
            self.assertEqual(adapter.region, 'us-east-1')
    
    def test_init_with_invalid_config(self):
        """Test initialization with invalid configuration."""
        invalid_config = {'access_key': 'test_key'}  # Missing required fields
        
        with self.assertRaises(StorageValidationError):
            S3StorageAdapter(invalid_config)
    
    def test_save_backup(self):
        """Test saving backup to S3."""
        backup = Mock()
        backup.backup_id = 'test-backup-id'
        backup.name = 'Test Backup'
        backup.created_at = Mock()
        backup.created_at.strftime = Mock(return_value='2024/01/01')
        backup.compression_enabled = False
        
        test_file = Mock()
        test_file.seek = Mock()
        test_file.seek.return_value = None
        
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            result = adapter.save_backup(test_file, backup)
            
            self.assertTrue(result)
            self.mock_client.upload_fileobj.assert_called_once()
    
    def test_retrieve_backup(self):
        """Test retrieving backup from S3."""
        backup = Mock()
        backup.file_path = 'test-backup.sql'
        
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            result = adapter.retrieve_backup(backup)
            
            self.assertIsNotNone(result)
            self.mock_client.get_object.assert_called_once()
    
    def test_backup_exists(self):
        """Test checking if backup exists in S3."""
        backup = Mock()
        backup.file_path = 'test-backup.sql'
        
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            result = adapter.backup_exists(backup)
            
            self.assertTrue(result)
            self.mock_client.head_object.assert_called_once()
    
    def test_backup_not_exists(self):
        """Test checking if non-existent backup exists in S3."""
        backup = Mock()
        backup.file_path = 'non-existent.sql'
        
        # Mock 404 error
        self.mock_client.head_object.side_effect = Exception("404 Not Found")
        
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            result = adapter.backup_exists(backup)
            
            self.assertFalse(result)
    
    def test_get_backup_url(self):
        """Test generating presigned URL."""
        backup = Mock()
        backup.file_path = 'test-backup.sql'
        
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            url = adapter.get_backup_url(backup, expires_in=3600)
            
            self.assertEqual(url, 'https://test-bucket.s3.amazonaws.com/test-file')
            self.mock_client.generate_presigned_url.assert_called_once()
    
    def test_get_storage_stats(self):
        """Test getting S3 storage statistics."""
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            stats = adapter.get_storage_stats()
            
            self.assertIn('bucket_name', stats)
            self.assertIn('region', stats)
            self.assertIn('total_objects', stats)
            self.assertIn('adapter', stats)
            self.assertEqual(stats['bucket_name'], 'test-bucket')
            self.assertEqual(stats['adapter'], 'S3')
    
    def test_test_connection(self):
        """Test connection to S3."""
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            result = adapter.test_connection()
            
            self.assertTrue(result)
            self.mock_client.head_bucket.assert_called_once()
    
    def test_validate_config(self):
        """Test S3 configuration validation."""
        valid_config = {
            'access_key': 'test_key',
            'secret_key': 'test_secret',
            'bucket_name': 'test-bucket'
        }
        invalid_config = {'access_key': 'test_key'}  # Missing required fields
        
        self.assertTrue(S3StorageAdapter.validate_config(valid_config))
        self.assertFalse(S3StorageAdapter.validate_config(invalid_config))
    
    def test_get_adapter_info(self):
        """Test getting S3 adapter information."""
        with patch('backup.services.storage.s3_adapter.boto3.client', return_value=self.mock_client):
            adapter = S3StorageAdapter(self.config)
            info = adapter.get_adapter_info()
            
            self.assertIn('name', info)
            self.assertIn('type', info)
            self.assertIn('version', info)
            self.assertIn('capabilities', info)
            self.assertIn('supported_regions', info)
            self.assertEqual(info['name'], 'S3StorageAdapter')
            self.assertEqual(info['type'], 'storage_adapter')
            self.assertIn('presigned_urls', info['capabilities'])


class StorageAdapterIntegrationTests(TestCase):
    """Integration tests for storage adapters."""
    
    def setUp(self):
        """Set up test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.local_config = {'base_path': self.temp_dir}
        self.s3_config = {
            'access_key': 'test_key',
            'secret_key': 'test_secret',
            'bucket_name': 'test-bucket'
        }
    
    def tearDown(self):
        """Clean up test data."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_switch_between_adapters(self):
        """Test switching between different storage adapters."""
        # Test local adapter
        local_adapter = create_storage_adapter('local', self.local_config)
        self.assertIsInstance(local_adapter, LocalStorageAdapter)
        
        # Test S3 adapter
        with patch('backup.services.storage.s3_adapter.boto3.client'):
            s3_adapter = create_storage_adapter('s3', self.s3_config)
            self.assertIsInstance(s3_adapter, S3StorageAdapter)
    
    def test_adapter_factory_methods(self):
        """Test factory convenience methods."""
        from api.backup.services.storage import get_available_storage_types
        
        types = get_available_storage_types()
        self.assertIn('local', types)
        self.assertIn('s3', types)
    
    def test_adapter_error_handling(self):
        """Test adapter error handling."""
        adapter = LocalStorageAdapter(self.local_config)
        
        # Test error handling
        error = Exception("Test error")
        error_info = adapter.handle_error(error, 'test_operation')
        
        self.assertIn('error', error_info)
        self.assertIn('operation', error_info)
        self.assertIn('timestamp', error_info)
        self.assertIn('adapter', error_info)
        self.assertEqual(error_info['operation'], 'test_operation')
        self.assertEqual(error_info['adapter'], 'LocalStorageAdapter')


if __name__ == '__main__':
    unittest.main()
