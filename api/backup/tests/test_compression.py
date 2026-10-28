"""
Test Compression Functionality
Comprehensive tests for backup compression and decompression
"""

import os
import tempfile
import zipfile
import gzip
import bz2
import lzma
import zstandard as zstd
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.services.BaseBackupService import BaseBackupService
from api.backup.models import Backup, BackupAlert
from api.backup.services.factory import BackupServiceFactory
from api.backup.models import BackupStorageLocation

User = get_user_model()


class CompressionTest(TestCase):
    """Test backup compression functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.base_service = BaseBackupService()
        self.test_content = b'Test backup content for compression ' * 1000  # 43KB
        self.test_file_path = None
    
    def tearDown(self):
        """Clean up test files"""
        if self.test_file_path and os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
    
    def test_compress_data_with_zip(self):
        """Test data compression with ZIP"""
        compressed_path = self.base_service._compress_data(
            self.test_content, 'zip', compression_level=6
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(os.path.exists(compressed_path))
        self.assertTrue(compressed_path.endswith('.zip'))
        
        # Verify compressed file is smaller
        compressed_size = os.path.getsize(compressed_path)
        self.assertLess(compressed_size, len(self.test_content))
        
        # Verify ZIP file can be opened
        with zipfile.ZipFile(compressed_path, 'r') as zipf:
            file_list = zipf.namelist()
            self.assertEqual(len(file_list), 1)
            
            # Extract and verify content
            with zipf.open(file_list[0]) as f:
                extracted_content = f.read()
                self.assertEqual(extracted_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_compress_data_with_gzip(self):
        """Test data compression with gzip"""
        compressed_path = self.base_service._compress_data(
            self.test_content, 'gzip', compression_level=6
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(os.path.exists(compressed_path))
        self.assertTrue(compressed_path.endswith('.gz'))
        
        # Verify compressed file is smaller
        compressed_size = os.path.getsize(compressed_path)
        self.assertLess(compressed_size, len(self.test_content))
        
        # Verify gzip file can be decompressed
        with gzip.open(compressed_path, 'rb') as gzf:
            decompressed_content = gzf.read()
            self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_compress_data_with_bzip2(self):
        """Test data compression with bzip2"""
        compressed_path = self.base_service._compress_data(
            self.test_content, 'bzip2', compression_level=6
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(os.path.exists(compressed_path))
        self.assertTrue(compressed_path.endswith('.bz2'))
        
        # Verify compressed file is smaller
        compressed_size = os.path.getsize(compressed_path)
        self.assertLess(compressed_size, len(self.test_content))
        
        # Verify bzip2 file can be decompressed
        with bz2.open(compressed_path, 'rb') as bzf:
            decompressed_content = bzf.read()
            self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_compress_data_with_lzma(self):
        """Test data compression with LZMA"""
        compressed_path = self.base_service._compress_data(
            self.test_content, 'lzma', compression_level=6
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(os.path.exists(compressed_path))
        self.assertTrue(compressed_path.endswith('.xz'))
        
        # Verify compressed file is smaller
        compressed_size = os.path.getsize(compressed_path)
        self.assertLess(compressed_size, len(self.test_content))
        
        # Verify LZMA file can be decompressed
        with lzma.open(compressed_path, 'rb') as xzf:
            decompressed_content = xzf.read()
            self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_compress_data_with_zstd(self):
        """Test data compression with Zstandard"""
        compressed_path = self.base_service._compress_data(
            self.test_content, 'zstd', compression_level=6
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(os.path.exists(compressed_path))
        self.assertTrue(compressed_path.endswith('.zst'))
        
        # Verify compressed file is smaller
        compressed_size = os.path.getsize(compressed_path)
        self.assertLess(compressed_size, len(self.test_content))
        
        # Verify Zstandard file can be decompressed
        with open(compressed_path, 'rb') as f:
            compressed_data = f.read()
            
        # Create Zstandard decompressor
        dctx = zstd.ZstdDecompressor()
        decompressed_content = dctx.decompress(compressed_data)
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_compress_data_invalid_format(self):
        """Test compression with invalid format"""
        with self.assertRaises(ValueError):
            self.base_service._compress_data(
                self.test_content, 'invalid_format'
            )
    
    def test_compress_data_empty_content(self):
        """Test compression of empty content"""
        empty_content = b''
        
        # Test with each compression format
        formats = ['zip', 'gzip', 'bzip2', 'lzma', 'zstd']
        
        for format_type in formats:
            with self.subTest(format_type=format_type):
                compressed_path = self.base_service._compress_data(
                    empty_content, format_type
                )
                
                self.assertIsNotNone(compressed_path)
                self.assertTrue(os.path.exists(compressed_path))
                
                # Clean up
                os.remove(compressed_path)
    
    def test_compress_data_large_content(self):
        """Test compression of large content"""
        large_content = b'A' * (1024 * 1024)  # 1MB
        
        # Test with each compression format
        formats = ['zip', 'gzip', 'bzip2', 'lzma', 'zstd']
        
        for format_type in formats:
            with self.subTest(format_type=format_type):
                compressed_path = self.base_service._compress_data(
                    large_content, format_type
                )
                
                self.assertIsNotNone(compressed_path)
                self.assertTrue(os.path.exists(compressed_path))
                
                # Verify compression ratio
                original_size = len(large_content)
                compressed_size = os.path.getsize(compressed_path)
                compression_ratio = compressed_size / original_size
                
                # Should achieve some compression (ratio < 1 for repetitive data)
                self.assertLessEqual(compression_ratio, 1.0)
                
                # Clean up
                os.remove(compressed_path)
    
    def test_compress_data_with_different_levels(self):
        """Test compression with different compression levels"""
        compression_levels = [1, 6, 9]  # Fast, default, best
        
        for level in compression_levels:
            with self.subTest(compression_level=level):
                compressed_path = self.base_service._compress_data(
                    self.test_content, 'zip', compression_level=level
                )
                
                self.assertIsNotNone(compressed_path)
                self.assertTrue(os.path.exists(compressed_path))
                
                # Clean up
                os.remove(compressed_path)
    
    def test_decompress_data_from_zip(self):
        """Test data decompression from ZIP"""
        # Create compressed file first
        compressed_path = self.base_service._compress_data(
            self.test_content, 'zip'
        )
        
        # Test decompression
        decompressed_content = self.base_service._decompress_data(
            compressed_path, 'zip'
        )
        
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_decompress_data_from_gzip(self):
        """Test data decompression from gzip"""
        # Create compressed file first
        compressed_path = self.base_service._compress_data(
            self.test_content, 'gzip'
        )
        
        # Test decompression
        decompressed_content = self.base_service._decompress_data(
            compressed_path, 'gzip'
        )
        
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_decompress_data_from_bzip2(self):
        """Test data decompression from bzip2"""
        # Create compressed file first
        compressed_path = self.base_service._compress_data(
            self.test_content, 'bzip2'
        )
        
        # Test decompression
        decompressed_content = self.base_service._decompress_data(
            compressed_path, 'bzip2'
        )
        
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_decompress_data_from_lzma(self):
        """Test data decompression from LZMA"""
        # Create compressed file first
        compressed_path = self.base_service._compress_data(
            self.test_content, 'lzma'
        )
        
        # Test decompression
        decompressed_content = self.base_service._decompress_data(
            compressed_path, 'lzma'
        )
        
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_decompress_data_from_zstd(self):
        """Test data decompression from Zstandard"""
        # Create compressed file first
        compressed_path = self.base_service._compress_data(
            self.test_content, 'zstd'
        )
        
        # Test decompression
        decompressed_content = self.base_service._decompress_data(
            compressed_path, 'zstd'
        )
        
        self.assertEqual(decompressed_content, self.test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_decompress_data_invalid_format(self):
        """Test decompression with invalid format"""
        # Create test file
        test_file = tempfile.NamedTemporaryFile(delete=False)
        test_file.write(b'test content')
        test_file.close()
        
        with self.assertRaises(ValueError):
            self.base_service._decompress_data(
                test_file.name, 'invalid_format'
            )
        
        # Clean up
        os.remove(test_file.name)
    
    def test_decompress_corrupted_file(self):
        """Test decompression of corrupted file"""
        # Create corrupted compressed file
        corrupted_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        corrupted_file.write(b'corrupted zip data')
        corrupted_file.close()
        
        # Should raise exception for corrupted file
        with self.assertRaises(Exception):
            self.base_service._decompress_data(
                corrupted_file.name, 'zip'
            )
        
        # Clean up
        os.remove(corrupted_file.name)
    
    def test_compress_decompress_roundtrip(self):
        """Test full compress-decompress roundtrip"""
        formats = ['zip', 'gzip', 'bzip2', 'lzma', 'zstd']
        
        for format_type in formats:
            with self.subTest(format_type=format_type):
                # Compress data
                compressed_path = self.base_service._compress_data(
                    self.test_content, format_type
                )
                
                # Decompress data
                decompressed_content = self.base_service._decompress_data(
                    compressed_path, format_type
                )
                
                # Should get original data back
                self.assertEqual(decompressed_content, self.test_content)
                
                # Clean up
                os.remove(compressed_path)
    
    def test_compression_ratio_comparison(self):
        """Test compression ratio comparison between formats"""
        original_size = len(self.test_content)
        compression_ratios = {}
        
        formats = ['zip', 'gzip', 'bzip2', 'lzma', 'zstd']
        
        for format_type in formats:
            with self.subTest(format_type=format_type):
                compressed_path = self.base_service._compress_data(
                    self.test_content, format_type
                )
                
                compressed_size = os.path.getsize(compressed_path)
                ratio = compressed_size / original_size
                compression_ratios[format_type] = ratio
                
                # Clean up
                os.remove(compressed_path)
        
        # All formats should achieve some compression
        for format_type, ratio in compression_ratios.items():
            self.assertLessEqual(ratio, 1.0, 
                f"{format_type} should compress data")
        
        # Zstandard should typically be the most efficient
        if 'zstd' in compression_ratios:
            self.assertLessEqual(
                compression_ratios['zstd'], 
                compression_ratios['zip'],
                "Zstandard should be more efficient than ZIP"
            )


class CompressionIntegrationTest(TestCase):
    """Test compression integration with backup workflow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            endpoint=tempfile.mkdtemp(),
            is_active=True
        )
    
    @patch('backup.services.factory.BackupServiceFactory')
    def test_backup_with_compression_workflow(self, mock_factory):
        """Test backup creation with compression"""
        # Mock storage service
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        # Create backup with compression
        backup = Backup.objects.create(
            name='Test Compressed Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=True,
            compression_method='gzip',
            created_by=self.user
        )
        
        # Create test file
        test_content = b'Test backup content for compression'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test compression during backup
        from api.backup.services.BaseBackupService import BaseBackupService
        base_service = BaseBackupService()
        
        # Compress the file
        compressed_path = base_service._compress_data(
            test_content, 'gzip'
        )
        
        self.assertIsNotNone(compressed_path)
        self.assertTrue(compressed_path.endswith('.gz'))
        
        # Verify compression
        with gzip.open(compressed_path, 'rb') as gzf:
            decompressed_content = gzf.read()
            self.assertEqual(decompressed_content, test_content)
        
        # Clean up
        os.remove(compressed_path)
    
    def test_backup_compression_metadata(self):
        """Test backup compression metadata storage"""
        # Create backup with compression
        backup = Backup.objects.create(
            name='Test Compression Metadata',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=True,
            compression_method='zip',
            compression_level=6
        )
        
        # Verify compression metadata
        self.assertTrue(backup.compression_enabled)
        self.assertEqual(backup.compression_method, 'zip')
        self.assertEqual(backup.compression_level, 6)
    
    def test_backup_compression_alert_creation(self):
        """Test alert creation for compression failures"""
        # Create backup
        backup = Backup.objects.create(
            name='Test Compression Alert',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=False  # Should be compressed but isn't
        )
        
        # Create alert for compression failure
        alert = BackupAlert.objects.create(
            alert_type='security',
            message=f"Backup {backup.name} should be compressed but isn't",
            backup=backup,
            severity='low',
            metadata={
                'expected_compression': True,
                'actual_compression': False,
                'compression_method': 'gzip'
            }
        )
        
        # Verify alert
        self.assertEqual(alert.alert_type, 'security')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'low')
        self.assertIn('expected_compression', alert.metadata)
    
    def test_compression_performance_tracking(self):
        """Test compression performance tracking"""
        import time
        
        from api.backup.services.BaseBackupService import BaseBackupService
        base_service = BaseBackupService()
        
        # Measure compression time for each format
        formats = ['zip', 'gzip', 'bzip2', 'lzma', 'zstd']
        compression_times = {}
        
        for format_type in formats:
            with self.subTest(format_type=format_type):
                start_time = time.time()
                
                compressed_path = base_service._compress_data(
                    self.test_content, format_type
                )
                
                end_time = time.time()
                compression_time = end_time - start_time
                compression_times[format_type] = compression_time
                
                # Clean up
                os.remove(compressed_path)
        
        # All formats should complete within reasonable time
        for format_type, comp_time in compression_times.items():
            self.assertLess(comp_time, 5.0, 
                f"{format_type} compression should complete within 5 seconds")
    
    def test_compression_memory_usage(self):
        """Test compression memory usage"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Compress large data
        large_content = b'A' * (1024 * 1024 * 5)  # 5MB
        
        from api.backup.services.BaseBackupService import BaseBackupService
        base_service = BaseBackupService()
        
        compressed_path = base_service._compress_data(
            large_content, 'gzip'
        )
        
        # Get memory usage after compression
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Should not use excessive memory (less than 20MB for 5MB data)
        self.assertLess(memory_increase, 20 * 1024 * 1024)
        
        # Clean up
        os.remove(compressed_path)


class CompressionErrorHandlingTest(TestCase):
    """Test compression error handling"""
    
    def setUp(self):
        """Set up test data"""
        self.base_service = BaseBackupService()
        self.test_content = b'Test backup content'
    
    def test_compress_with_insufficient_disk_space(self):
        """Test compression with insufficient disk space"""
        # Mock disk space check to return insufficient space
        with patch('os.statvfs') as mock_statvfs:
            mock_statvfs.return_value = Mock(
                f_bavail=1000,  # Very little space available
                f_frsize=4096
            )
            
            # Should raise exception for insufficient space
            with self.assertRaises(OSError):
                self.base_service._compress_data(
                    self.test_content, 'gzip'
                )
    
    def test_compress_with_permission_error(self):
        """Test compression with permission error"""
        # Mock file creation to raise permission error
        with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
            mock_tempfile.side_effect = PermissionError("Permission denied")
            
            with self.assertRaises(PermissionError):
                self.base_service._compress_data(
                    self.test_content, 'gzip'
                )
    
    def test_decompress_corrupted_file(self):
        """Test decompression of corrupted file"""
        # Create corrupted compressed file
        corrupted_file = tempfile.NamedTemporaryFile(delete=False, suffix='.gz')
        corrupted_file.write(b'corrupted gzip data')
        corrupted_file.close()
        
        # Should raise exception for corrupted file
        with self.assertRaises(Exception):
            self.base_service._decompress_data(
                corrupted_file.name, 'gzip'
            )
        
        # Clean up
        os.remove(corrupted_file.name)
    
    def test_decompress_nonexistent_file(self):
        """Test decompression of non-existent file"""
        nonexistent_file = '/tmp/nonexistent_file.gz'
        
        # Should raise exception for non-existent file
        with self.assertRaises(FileNotFoundError):
            self.base_service._decompress_data(
                nonexistent_file, 'gzip'
            )
    
    def test_compression_format_fallback(self):
        """Test compression format fallback"""
        # Test with unsupported format
        with self.assertRaises(ValueError):
            self.base_service._compress_data(
                self.test_content, 'unsupported_format'
            )
    
    def test_compression_level_validation(self):
        """Test compression level validation"""
        # Test with invalid compression level
        with self.assertRaises(ValueError):
            self.base_service._compress_data(
                self.test_content, 'gzip', compression_level=20  # Invalid level
            )
    
    def test_compression_thread_safety(self):
        """Test compression thread safety"""
        import threading
        import time
        
        results = []
        errors = []
        
        def compress_data(index):
            try:
                test_content = f'Test content {index}'.encode()
                compressed_path = self.base_service._compress_data(
                    test_content, 'gzip'
                )
                results.append(compressed_path)
                
                # Clean up
                if compressed_path and os.path.exists(compressed_path):
                    os.remove(compressed_path)
                    
            except Exception as e:
                errors.append(e)
        
        # Create multiple compression threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=compress_data, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)
        
        for result in results:
            self.assertIsNotNone(result)
