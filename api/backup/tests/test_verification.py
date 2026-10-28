"""
Test Verification Functionality
Comprehensive tests for backup verification and integrity checking
"""

import os
import tempfile
import hashlib
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.services.BaseBackupService import BaseBackupService
from api.backup.services.BackupValidator import BackupValidator
from api.backup.models import Backup, BackupVerification, BackupAlert
from api.backup.services.factory import BackupServiceFactory
from api.backup.models import BackupStorageLocation

User = get_user_model()


class VerificationTest(TestCase):
    """Test backup verification functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.base_service = BaseBackupService()
        self.validator = BackupValidator()
        self.test_content = b'Test backup content for verification'
        self.test_hash = hashlib.sha256(self.test_content).hexdigest()
    
    def test_calculate_file_hash(self):
        """Test file hash calculation"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Calculate hash
            calculated_hash = self.base_service._calculate_file_hash(f.name)
            
            # Should match expected hash
            self.assertEqual(calculated_hash, self.test_hash)
            
            # Clean up
            os.remove(f.name)
    
    def test_calculate_file_hash_different_algorithms(self):
        """Test file hash calculation with different algorithms"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Test MD5
            md5_hash = self.base_service._calculate_file_hash(
                f.name, algorithm='md5'
            )
            self.assertEqual(len(md5_hash), 32)  # MD5 hex length
            
            # Test SHA-1
            sha1_hash = self.base_service._calculate_file_hash(
                f.name, algorithm='sha1'
            )
            self.assertEqual(len(sha1_hash), 40)  # SHA-1 hex length
            
            # Test SHA-256 (default)
            sha256_hash = self.base_service._calculate_file_hash(
                f.name, algorithm='sha256'
            )
            self.assertEqual(len(sha256_hash), 64)  # SHA-256 hex length
            self.assertEqual(sha256_hash, self.test_hash)
            
            # Clean up
            os.remove(f.name)
    
    def test_calculate_file_hash_invalid_algorithm(self):
        """Test file hash calculation with invalid algorithm"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Should raise ValueError for invalid algorithm
            with self.assertRaises(ValueError):
                self.base_service._calculate_file_hash(
                    f.name, algorithm='invalid_algorithm'
                )
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_file_integrity_success(self):
        """Test successful file integrity verification"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Verify integrity
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=self.test_hash
            )
            
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_file_integrity_failure(self):
        """Test file integrity verification failure"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'Different content')
            f.close()
            
            # Verify integrity with wrong hash
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=self.test_hash
            )
            
            self.assertFalse(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_file_size_success(self):
        """Test successful file size verification"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            file_size = len(self.test_content)
            
            # Verify size
            result = self.validator.verify_file_size(
                f.name, expected_size=file_size
            )
            
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_file_size_failure(self):
        """Test file size verification failure"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Verify size with wrong expected size
            result = self.validator.verify_file_size(
                f.name, expected_size=999999
            )
            
            self.assertFalse(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_file_nonexistent(self):
        """Test verification of non-existent file"""
        nonexistent_file = '/tmp/nonexistent_file.sql'
        
        # Should handle non-existent file gracefully
        with self.assertRaises(FileNotFoundError):
            self.validator.verify_file_integrity(
                nonexistent_file, expected_hash=self.test_hash
            )
        
        with self.assertRaises(FileNotFoundError):
            self.validator.verify_file_size(
                nonexistent_file, expected_size=1000
            )
    
    def test_verify_file_corrupted(self):
        """Test verification of corrupted file"""
        # Create corrupted file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'Corrupted content that will fail verification')
            f.close()
            
            # Should detect corruption through hash mismatch
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=self.test_hash
            )
            
            self.assertFalse(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_large_file(self):
        """Test verification of large file"""
        # Create large test file (1MB)
        large_content = b'A' * (1024 * 1024)
        large_hash = hashlib.sha256(large_content).hexdigest()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(large_content)
            f.close()
            
            # Verify large file
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=large_hash
            )
            
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verify_empty_file(self):
        """Test verification of empty file"""
        # Create empty file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'')
            f.close()
            
            empty_hash = hashlib.sha256(b'').hexdigest()
            
            # Verify empty file
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=empty_hash
            )
            
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)


class BackupVerificationModelTest(TestCase):
    """Test BackupVerification model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
    
    def test_backup_verification_creation(self):
        """Test BackupVerification model creation"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True,
            checksum_match=True,
            size_match=True,
            verified_by=self.user
        )
        
        self.assertEqual(str(verification), f"Verification of {self.backup.name} - Valid")
        self.assertEqual(verification.backup, self.backup)
        self.assertEqual(verification.verification_method, 'hash')
        self.assertTrue(verification.is_valid)
        self.assertTrue(verification.checksum_match)
        self.assertTrue(verification.size_match)
        self.assertEqual(verification.verified_by, self.user)
    
    def test_backup_verification_uuid_generation(self):
        """Test UUID generation for verification_id"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True
        )
        
        # Test UUID generation
        self.assertIsInstance(verification.verification_id, str)
        # Should be valid UUID string
        import uuid
        try:
            uuid.UUID(verification.verification_id)
            self.assertTrue(True)
        except ValueError:
            self.fail("verification_id should be a valid UUID")
    
    def test_backup_verification_methods(self):
        """Test different verification methods"""
        verification_methods = ['hash', 'size', 'test_restore', 'full']
        
        for method in verification_methods:
            with self.subTest(method=method):
                verification = BackupVerification.objects.create(
                    backup=self.backup,
                    verification_method=method,
                    is_valid=True
                )
                
                self.assertEqual(verification.verification_method, method)
    
    def test_backup_verification_details_storage(self):
        """Test verification details JSON storage"""
        details = {
            'hash_algorithm': 'sha256',
            'expected_hash': 'abc123',
            'actual_hash': 'abc123',
            'file_size': 1024000,
            'verification_time': 5.2
        }
        
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='full',
            is_valid=True,
            verification_details=details
        )
        
        self.assertEqual(verification.verification_details, details)
    
    def test_backup_verification_error_handling(self):
        """Test verification error handling"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=False,
            checksum_match=False,
            error_message='Hash mismatch detected'
        )
        
        self.assertFalse(verification.is_valid)
        self.assertFalse(verification.checksum_match)
        self.assertEqual(verification.error_message, 'Hash mismatch detected')
    
    def test_backup_verification_timestamps(self):
        """Test timestamp fields"""
        before_creation = timezone.now()
        
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True
        )
        
        after_creation = timezone.now()
        
        # Should set verified_at
        self.assertIsNotNone(verification.verified_at)
        self.assertLessEqual(verification.verified_at, after_creation)
        self.assertGreaterEqual(verification.verified_at, before_creation)
    
    def test_backup_verification_user_attribution(self):
        """Test user attribution for verification"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True,
            verified_by=self.user
        )
        
        self.assertEqual(verification.verified_by, self.user)
        self.assertIsNotNone(verification.verified_at)


class VerificationIntegrationTest(TestCase):
    """Test verification integration with backup workflow"""
    
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
    def test_backup_verification_workflow(self, mock_factory):
        """Test complete backup verification workflow"""
        # Mock storage service
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Verification Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='test_hash_123',
            file_size=1024000,
            created_by=self.user
        )
        
        # Create test file
        test_content = b'Test backup content for verification'
        backup_file = ContentFile(test_content)
        backup_file.name = 'test_backup.sql'
        
        # Test verification workflow
        from api.backup.services import BackupService
        backup_service = BackupService()
        
        verification = backup_service.verify_backup(
            str(backup.backup_id),
            verification_method='hash'
        )
        
        # Verify verification was created
        self.assertIsNotNone(verification)
        self.assertEqual(verification.backup, backup)
        self.assertEqual(verification.verification_method, 'hash')
        self.assertTrue(verification.is_valid)
    
    def test_verification_with_different_methods(self):
        """Test verification with different methods"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Multi-Method Verification',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='test_hash_123',
            file_size=1024000,
            created_by=self.user
        )
        
        # Test each verification method
        methods = ['hash', 'size', 'test_restore', 'full']
        
        for method in methods:
            with self.subTest(method=method):
                verification = BackupVerification.objects.create(
                    backup=backup,
                    verification_method=method,
                    is_valid=True
                )
                
                self.assertEqual(verification.verification_method, method)
    
    def test_verification_alert_creation(self):
        """Test alert creation for verification failures"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Verification Alert',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        # Create verification failure
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=False,
            checksum_match=False,
            error_message='Verification failed: hash mismatch'
        )
        
        # Create alert for verification failure
        alert = BackupAlert.objects.create(
            alert_type='verification_failed',
            message=f"Backup verification failed: {verification.error_message}",
            backup=backup,
            severity='medium',
            metadata={
                'verification_id': str(verification.verification_id),
                'verification_method': verification.verification_method,
                'error_message': verification.error_message
            }
        )
        
        # Verify alert
        self.assertEqual(alert.alert_type, 'verification_failed')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'medium')
        self.assertIn('verification_id', alert.metadata)
    
    def test_verification_performance_tracking(self):
        """Test verification performance tracking"""
        import time
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Performance Verification',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        # Measure verification time
        start_time = time.time()
        
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            verification_details={
                'verification_time': 2.5,
                'file_size': 1024000,
                'hash_calculation_time': 0.1
            }
        )
        
        end_time = time.time()
        verification_time = end_time - start_time
        
        # Should complete within reasonable time (less than 5 seconds for mock)
        self.assertLess(verification_time, 5.0)
        
        # Duration should be recorded
        self.assertIsNotNone(verification.verified_at)
    
    def test_concurrent_verifications(self):
        """Test concurrent verification operations"""
        import threading
        import time
        
        results = []
        
        def create_verification(index):
            # Create test backup
            backup = Backup.objects.create(
                name=f'Concurrent Verification {index}',
                backup_type='full',
                storage_type='local',
                database_name=f'test_db_{index}',
                created_by=self.user
            )
            
            # Create verification
            verification = BackupVerification.objects.create(
                backup=backup,
                verification_method='hash',
                is_valid=True
            )
            results.append(verification)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_verification, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all verifications completed
        self.assertEqual(len(results), 3)
        for verification in results:
            self.assertIsNotNone(verification)
    
    def test_verification_with_encrypted_backups(self):
        """Test verification of encrypted backups"""
        # Create encrypted backup
        backup = Backup.objects.create(
            name='Test Encrypted Verification',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM',
            created_by=self.user
        )
        
        # Create verification for encrypted backup
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            verification_details={
                'encryption_verified': True,
                'decryption_successful': True,
                'post_decryption_hash': 'decrypted_hash_123'
            }
        )
        
        # Verify encrypted backup verification
        self.assertEqual(verification.backup, backup)
        self.assertTrue(verification.is_valid)
        self.assertIn('encryption_verified', verification.verification_details)
    
    def test_verification_with_compressed_backups(self):
        """Test verification of compressed backups"""
        # Create compressed backup
        backup = Backup.objects.create(
            name='Test Compressed Verification',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=True,
            compression_method='gzip',
            created_by=self.user
        )
        
        # Create verification for compressed backup
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            verification_details={
                'compression_verified': True,
                'decompression_successful': True,
                'original_file_size': 2048000,
                'compressed_file_size': 1024000,
                'compression_ratio': 0.5
            }
        )
        
        # Verify compressed backup verification
        self.assertEqual(verification.backup, backup)
        self.assertTrue(verification.is_valid)
        self.assertIn('compression_verified', verification.verification_details)


class VerificationErrorHandlingTest(TestCase):
    """Test verification error handling"""
    
    def setUp(self):
        """Set up test data"""
        self.validator = BackupValidator()
        self.test_content = b'Test backup content'
        self.test_hash = hashlib.sha256(self.test_content).hexdigest()
    
    def test_verification_with_corrupted_file(self):
        """Test verification with corrupted file"""
        # Create corrupted file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'Corrupted content')
            f.close()
            
            # Should detect corruption
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=self.test_hash
            )
            
            self.assertFalse(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verification_with_missing_file(self):
        """Test verification with missing file"""
        missing_file = '/tmp/missing_file.sql'
        
        # Should handle missing file gracefully
        with self.assertRaises(FileNotFoundError):
            self.validator.verify_file_integrity(
                missing_file, expected_hash=self.test_hash
            )
    
    def test_verification_with_permission_error(self):
        """Test verification with permission error"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Mock permission error
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                with self.assertRaises(PermissionError):
                    self.validator.verify_file_integrity(
                        f.name, expected_hash=self.test_hash
                    )
            
            # Clean up
            os.remove(f.name)
    
    def test_verification_hash_consistency(self):
        """Test verification hash consistency"""
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.test_content)
            f.close()
            
            # Calculate hash multiple times
            hash1 = self.validator.calculate_file_hash(f.name)
            hash2 = self.validator.calculate_file_hash(f.name)
            hash3 = self.validator.calculate_file_hash(f.name)
            
            # Should be consistent
            self.assertEqual(hash1, hash2)
            self.assertEqual(hash2, hash3)
            self.assertEqual(hash1, self.test_hash)
            
            # Clean up
            os.remove(f.name)
    
    def test_verification_large_file_handling(self):
        """Test verification of large files"""
        # Create large test file (10MB)
        large_content = b'A' * (1024 * 1024 * 10)
        large_hash = hashlib.sha256(large_content).hexdigest()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(large_content)
            f.close()
            
            # Should handle large files
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=large_hash
            )
            
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verification_memory_usage(self):
        """Test verification memory usage"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Verify large file
        large_content = b'A' * (1024 * 1024 * 5)  # 5MB
        large_hash = hashlib.sha256(large_content).hexdigest()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(large_content)
            f.close()
            
            # Verify file
            result = self.validator.verify_file_integrity(
                f.name, expected_hash=large_hash
            )
            
            # Get memory usage after verification
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Should not use excessive memory (less than 20MB for 5MB file)
            self.assertLess(memory_increase, 20 * 1024 * 1024)
            self.assertTrue(result)
            
            # Clean up
            os.remove(f.name)
    
    def test_verification_timeout_handling(self):
        """Test verification timeout handling"""
        # Mock slow verification
        with patch('hashlib.sha256') as mock_sha256:
            # Create slow hash function
            def slow_hash(data):
                import time
                time.sleep(2)  # Simulate slow operation
                return hashlib.sha256(data)
            
            mock_sha256.side_effect = slow_hash
            
            # Create test file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(self.test_content)
                f.close()
                
                # Should handle slow verification
                import time
                start_time = time.time()
                
                result = self.validator.verify_file_integrity(
                    f.name, expected_hash=self.test_hash
                )
                
                end_time = time.time()
                verification_time = end_time - start_time
                
                # Should complete but take longer
                self.assertGreater(verification_time, 1.5)
                self.assertTrue(result)
                
                # Clean up
                os.remove(f.name)
