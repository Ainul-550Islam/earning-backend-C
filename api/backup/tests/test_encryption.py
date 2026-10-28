"""
Test Encryption Functionality
Comprehensive tests for backup encryption and decryption
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
from api.backup.models import Backup, BackupEncryption, BackupAlert
from api.backup.services.factory import BackupServiceFactory
from api.backup.models import BackupStorageLocation

User = get_user_model()


class EncryptionTest(TestCase):
    """Test backup encryption functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.base_service = BaseBackupService()
        self.test_content = b'Test backup content for encryption'
        self.test_key = b'test_encryption_key_32_bytes_long'
    
    def test_generate_encryption_key(self):
        """Test encryption key generation"""
        key = self.base_service._generate_encryption_key()
        
        # Should generate 32-byte key
        self.assertEqual(len(key), 32)
        
        # Should be bytes
        self.assertIsInstance(key, bytes)
        
        # Should be different each time
        key2 = self.base_service._generate_encryption_key()
        self.assertNotEqual(key, key2)
    
    def test_generate_encryption_key_with_password(self):
        """Test encryption key generation with password"""
        password = b'test_password'
        key = self.base_service._generate_encryption_key(password)
        
        # Should generate 32-byte key
        self.assertEqual(len(key), 32)
        
        # Should be deterministic with same password
        key2 = self.base_service._generate_encryption_key(password)
        self.assertEqual(key, key2)
    
    def test_encrypt_data_with_fernet(self):
        """Test data encryption with Fernet"""
        from cryptography.fernet import Fernet
        
        # Mock Fernet
        with patch('backup.services.BaseBackupService.Fernet') as mock_fernet:
            mock_cipher = Mock()
            mock_fernet.return_value = mock_cipher
            mock_cipher.encrypt.return_value = b'encrypted_data'
            
            # Test encryption
            result = self.base_service._encrypt_data(self.test_content, 'Fernet')
            
            # Verify Fernet was used
            mock_fernet.assert_called_once()
            mock_cipher.encrypt.assert_called_once_with(self.test_content)
            
            self.assertEqual(result, b'encrypted_data')
    
    def test_encrypt_data_with_aes_gcm(self):
        """Test data encryption with AES-256-GCM"""
        # Mock AES-GCM encryption
        with patch('backup.services.BaseBackupService.AESGCM') as mock_aes:
            mock_cipher = Mock()
            mock_aes.return_value = mock_cipher
            mock_cipher.encrypt.return_value = (b'encrypted_data', b'auth_tag')
            
            # Test encryption
            result = self.base_service._encrypt_data(self.test_content, 'AES-256-GCM')
            
            # Verify AES-GCM was used
            mock_aes.assert_called_once()
            mock_cipher.encrypt.assert_called_once_with(self.test_content)
            
            # Should return encrypted data and auth tag
            self.assertEqual(result, (b'encrypted_data', b'auth_tag'))
    
    def test_encrypt_data_with_chacha20(self):
        """Test data encryption with ChaCha20-Poly1305"""
        # Mock ChaCha20-Poly1305 encryption
        with patch('backup.services.BaseBackupService.ChaCha20Poly1305') as mock_chacha:
            mock_cipher = Mock()
            mock_chacha.return_value = mock_cipher
            mock_cipher.encrypt.return_value = b'encrypted_data'
            
            # Test encryption
            result = self.base_service._encrypt_data(self.test_content, 'ChaCha20-Poly1305')
            
            # Verify ChaCha20 was used
            mock_chacha.assert_called_once()
            mock_cipher.encrypt.assert_called_once_with(self.test_content)
            
            self.assertEqual(result, b'encrypted_data')
    
    def test_encrypt_data_invalid_algorithm(self):
        """Test encryption with invalid algorithm"""
        with self.assertRaises(ValueError):
            self.base_service._encrypt_data(self.test_content, 'INVALID_ALGORITHM')
    
    def test_decrypt_data_with_fernet(self):
        """Test data decryption with Fernet"""
        from cryptography.fernet import Fernet
        
        # Mock Fernet
        with patch('backup.services.BaseBackupService.Fernet') as mock_fernet:
            mock_cipher = Mock()
            mock_fernet.return_value = mock_cipher
            mock_cipher.decrypt.return_value = self.test_content
            
            # Test decryption
            result = self.base_service._decrypt_data(b'encrypted_data', 'Fernet')
            
            # Verify Fernet was used
            mock_fernet.assert_called_once()
            mock_cipher.decrypt.assert_called_once_with(b'encrypted_data')
            
            self.assertEqual(result, self.test_content)
    
    def test_decrypt_data_with_aes_gcm(self):
        """Test data decryption with AES-256-GCM"""
        # Mock AES-GCM decryption
        with patch('backup.services.BaseBackupService.AESGCM') as mock_aes:
            mock_cipher = Mock()
            mock_aes.return_value = mock_cipher
            mock_cipher.decrypt.return_value = self.test_content
            
            # Test decryption
            result = self.base_service._decrypt_data((b'encrypted_data', b'auth_tag'), 'AES-256-GCM')
            
            # Verify AES-GCM was used
            mock_aes.assert_called_once()
            mock_cipher.decrypt.assert_called_once_with(b'encrypted_data', b'auth_tag')
            
            self.assertEqual(result, self.test_content)
    
    def test_decrypt_data_with_chacha20(self):
        """Test data decryption with ChaCha20-Poly1305"""
        # Mock ChaCha20-Poly1305 decryption
        with patch('backup.services.BaseBackupService.ChaCha20Poly1305') as mock_chacha:
            mock_cipher = Mock()
            mock_chacha.return_value = mock_cipher
            mock_cipher.decrypt.return_value = self.test_content
            
            # Test decryption
            result = self.base_service._decrypt_data(b'encrypted_data', 'ChaCha20-Poly1305')
            
            # Verify ChaCha20 was used
            mock_chacha.assert_called_once()
            mock_chacha.decrypt.assert_called_once_with(b'encrypted_data')
            
            self.assertEqual(result, self.test_content)
    
    def test_decrypt_data_invalid_algorithm(self):
        """Test decryption with invalid algorithm"""
        with self.assertRaises(ValueError):
            self.base_service._decrypt_data(b'encrypted_data', 'INVALID_ALGORITHM')
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test full encrypt-decrypt roundtrip"""
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                # Encrypt data
                encrypted = self.base_service._encrypt_data(self.test_content, algorithm)
                
                # Decrypt data
                if algorithm == 'AES-256-GCM':
                    decrypted = self.base_service._decrypt_data(encrypted, algorithm)
                else:
                    decrypted = self.base_service._decrypt_data(encrypted, algorithm)
                
                # Should get original data back
                self.assertEqual(decrypted, self.test_content)
    
    def test_encrypt_large_data(self):
        """Test encryption of large data"""
        large_content = b'A' * (1024 * 1024)  # 1MB of data
        
        # Test encryption with each algorithm
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                encrypted = self.base_service._encrypt_data(large_content, algorithm)
                
                # Should handle large data
                self.assertIsNotNone(encrypted)
                self.assertGreater(len(encrypted), 0)
    
    def test_encrypt_empty_data(self):
        """Test encryption of empty data"""
        empty_content = b''
        
        # Test encryption with each algorithm
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                encrypted = self.base_service._encrypt_data(empty_content, algorithm)
                
                # Should handle empty data
                self.assertIsNotNone(encrypted)
    
    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data"""
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                with self.assertRaises(Exception):
                    self.base_service._decrypt_data(b'invalid_encrypted_data', algorithm)


class BackupEncryptionModelTest(TestCase):
    """Test BackupEncryption model functionality"""
    
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
    
    def test_backup_encryption_creation(self):
        """Test BackupEncryption model creation"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            key_hash='sha256hash123',
            is_encrypted=True,
            encryption_key='encrypted_key_data'
        )
        
        self.assertEqual(str(encryption), f"Encryption of {self.backup.name} - AES-256-GCM")
        self.assertEqual(encryption.backup, self.backup)
        self.assertEqual(encryption.algorithm, 'AES-256-GCM')
        self.assertTrue(encryption.is_encrypted)
        self.assertEqual(encryption.key_hash, 'sha256hash123')
    
    def test_backup_encryption_one_to_one_relationship(self):
        """Test one-to-one relationship with backup"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='Fernet',
            is_encrypted=True
        )
        
        # Test reverse relationship
        self.assertEqual(self.backup.encryption_info, encryption)
        
        # Test uniqueness
        with self.assertRaises(Exception):
            BackupEncryption.objects.create(
                backup=self.backup,
                algorithm='AES-256-GCM',
                is_encrypted=True
            )
    
    def test_key_hash_generation_method(self):
        """Test key hash generation method"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            is_encrypted=True
        )
        
        test_key = 'test_encryption_key_123'
        generated_hash = encryption.generate_key_hash(test_key)
        
        # Should generate SHA256 hash
        self.assertEqual(len(generated_hash), 64)  # SHA256 hex length
        self.assertEqual(generated_hash, hashlib.sha256(test_key.encode()).hexdigest())
        
        # Should update model
        encryption.refresh_from_db()
        self.assertEqual(encryption.key_hash, generated_hash)
    
    def test_backup_encryption_metadata(self):
        """Test backup encryption metadata storage"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='ChaCha20-Poly1305',
            key_hash='sha256hash456',
            is_encrypted=True,
            salt='random_salt_123',
            iv='initialization_vector_456'
        )
        
        self.assertEqual(encryption.algorithm, 'ChaCha20-Poly1305')
        self.assertEqual(encryption.salt, 'random_salt_123')
        self.assertEqual(encryption.iv, 'initialization_vector_456')
        self.assertTrue(encryption.is_encrypted)
    
    def test_backup_encryption_timestamps(self):
        """Test timestamp fields"""
        before_creation = timezone.now()
        
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            is_encrypted=True
        )
        
        after_creation = timezone.now()
        
        # Should set created_at and updated_at
        self.assertIsNotNone(encryption.created_at)
        self.assertIsNotNone(encryption.updated_at)
        self.assertLessEqual(encryption.created_at, after_creation)
        self.assertLessEqual(encryption.updated_at, after_creation)
        self.assertGreaterEqual(encryption.created_at, before_creation)
    
    def test_backup_encryption_string_representation(self):
        """Test string representation"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='Fernet',
            is_encrypted=True
        )
        
        expected_str = f"Encryption of {self.backup.name} - Fernet"
        self.assertEqual(str(encryption), expected_str)


class EncryptionIntegrationTest(TestCase):
    """Test encryption integration with backup workflow"""
    
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
    def test_backup_with_encryption_workflow(self, mock_factory):
        """Test backup creation with encryption"""
        # Mock storage service
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        # Create backup with encryption
        backup = Backup.objects.create(
            name='Test Encrypted Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM',
            created_by=self.user
        )
        
        # Create encryption record
        encryption = BackupEncryption.objects.create(
            backup=backup,
            algorithm='AES-256-GCM',
            key_hash='test_hash',
            is_encrypted=True,
            encryption_key='test_key'
        )
        
        # Verify encryption record exists
        self.assertIsNotNone(encryption)
        self.assertEqual(encryption.backup, backup)
        self.assertEqual(encryption.algorithm, 'AES-256-GCM')
        self.assertTrue(encryption.is_encrypted)
    
    @patch('backup.services.factory.BackupServiceFactory')
    def test_backup_encryption_key_generation(self, mock_factory):
        """Test encryption key generation during backup"""
        # Mock storage service
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        # Create backup with encryption
        backup = Backup.objects.create(
            name='Test Key Generation Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM',
            created_by=self.user
        )
        
        # Test key generation
        from api.backup.services.BaseBackupService import BaseBackupService
        base_service = BaseBackupService()
        
        # Generate key
        key = base_service._generate_encryption_key()
        self.assertEqual(len(key), 32)
        
        # Create encryption record with generated key
        encryption = BackupEncryption.objects.create(
            backup=backup,
            algorithm='AES-256-GCM',
            key_hash=hashlib.sha256(key).hexdigest(),
            is_encrypted=True,
            encryption_key=key.hex()  # Store as hex
        )
        
        # Verify key hash
        self.assertEqual(encryption.key_hash, hashlib.sha256(key).hexdigest())
    
    def test_backup_encryption_metadata_storage(self):
        """Test encryption metadata storage during backup"""
        # Create backup with encryption
        backup = Backup.objects.create(
            name='Test Metadata Storage Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM',
            encryption_key='test_key',
            salt='test_salt',
            iv='test_iv'
        )
        
        # Create encryption record with metadata
        encryption = BackupEncryption.objects.create(
            backup=backup,
            algorithm='AES-256-GCM',
            key_hash='test_hash',
            is_encrypted=True,
            encryption_key='test_key',
            salt='test_salt',
            iv='test_iv'
        )
        
        # Verify metadata storage
        self.assertEqual(encryption.salt, 'test_salt')
        self.assertEqual(encryption.iv, 'test_iv')
        self.assertIsNotNone(encryption.created_at)
        self.assertIsNotNone(encryption.updated_at)
    
    def test_backup_encryption_alert_creation(self):
        """Test alert creation for encryption failures"""
        # Create backup
        backup = Backup.objects.create(
            name='Test Encryption Alert Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=False  # Should be encrypted but isn't
        )
        
        # Create security alert for encryption failure
        alert = BackupAlert.objects.create(
            alert_type='security',
            message=f"Backup {backup.name} should be encrypted but isn't",
            backup=backup,
            severity='medium',
            metadata={
                'expected_encryption': True,
                'actual_encryption': False,
                'encryption_method': 'AES-256-GCM'
            }
        )
        
        # Verify alert
        self.assertEqual(alert.alert_type, 'security')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'medium')
        self.assertIn('expected_encryption', alert.metadata)
    
    def test_backup_encryption_performance(self):
        """Test encryption performance"""
        import time
        
        # Create test data
        test_data = b'A' * (1024 * 100)  # 100KB of data
        
        from api.backup.services.BaseBackupService import BaseBackupService
        base_service = BaseBackupService()
        
        # Measure encryption time
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                start_time = time.time()
                
                # Encrypt data
                encrypted = base_service._encrypt_data(test_data, algorithm)
                
                end_time = time.time()
                encryption_time = end_time - start_time
                
                # Should encrypt within reasonable time (less than 1 second for 100KB)
                self.assertLess(encryption_time, 1.0)
                self.assertIsNotNone(encrypted)


class EncryptionErrorHandlingTest(TestCase):
    """Test encryption error handling"""
    
    def setUp(self):
        """Set up test data"""
        self.base_service = BaseBackupService()
        self.test_content = b'Test backup content'
    
    def test_encrypt_with_invalid_key(self):
        """Test encryption with invalid key"""
        # Mock Fernet with invalid key
        with patch('backup.services.BaseBackupService.Fernet') as mock_fernet:
            from cryptography.fernet import InvalidToken
            mock_fernet.side_effect = InvalidToken("Invalid key")
            
            with self.assertRaises(InvalidToken):
                self.base_service._encrypt_data(self.test_content, 'Fernet')
    
    def test_decrypt_with_invalid_key(self):
        """Test decryption with invalid key"""
        # Mock Fernet with invalid key
        with patch('backup.services.BaseBackupService.Fernet') as mock_fernet:
            from cryptography.fernet import InvalidToken
            mock_fernet.return_value = Mock()
            mock_fernet.return_value.decrypt.side_effect = InvalidToken("Invalid key")
            
            with self.assertRaises(InvalidToken):
                self.base_service._decrypt_data(b'encrypted_data', 'Fernet')
    
    def test_encrypt_with_corrupted_data(self):
        """Test encryption with corrupted data"""
        # Mock encryption to raise exception
        with patch('backup.services.BaseBackupService.AESGCM') as mock_aes:
            from cryptography.exceptions import InvalidTag
            mock_aes.return_value = Mock()
            mock_aes.return_value.encrypt.side_effect = InvalidTag("Invalid tag")
            
            with self.assertRaises(InvalidTag):
                self.base_service._encrypt_data(self.test_content, 'AES-256-GCM')
    
    def test_decrypt_with_corrupted_data(self):
        """Test decryption with corrupted data"""
        # Mock decryption to raise exception
        with patch('backup.services.BaseBackupService.AESGCM') as mock_aes:
            from cryptography.exceptions import InvalidTag
            mock_aes.return_value = Mock()
            mock_aes.return_value.decrypt.side_effect = InvalidTag("Invalid tag")
            
            with self.assertRaises(InvalidTag):
                self.base_service._decrypt_data((b'encrypted_data', b'invalid_tag'), 'AES-256-GCM')
    
    def test_key_hash_consistency(self):
        """Test key hash consistency"""
        test_key = b'test_encryption_key_123'
        
        # Generate hash multiple times
        hash1 = hashlib.sha256(test_key).hexdigest()
        hash2 = hashlib.sha256(test_key).hexdigest()
        hash3 = hashlib.sha256(test_key).hexdigest()
        
        # Should be consistent
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)
    
    def test_encryption_algorithm_selection(self):
        """Test encryption algorithm selection"""
        test_data = b'Test data'
        
        # Test each algorithm
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                # Should encrypt without error
                try:
                    encrypted = self.base_service._encrypt_data(test_data, algorithm)
                    self.assertIsNotNone(encrypted)
                except Exception as e:
                    self.fail(f"Algorithm {algorithm} should work: {str(e)}")
    
    def test_encryption_memory_usage(self):
        """Test encryption memory usage"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Encrypt large data
        large_data = b'A' * (1024 * 1024 * 10)  # 10MB
        
        algorithms = ['Fernet', 'AES-256-GCM', 'ChaCha20-Poly1305']
        
        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm):
                # Encrypt data
                encrypted = self.base_service._encrypt_data(large_data, algorithm)
                
                # Get memory usage after encryption
                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory
                
                # Should not use excessive memory (less than 50MB for 10MB data)
                self.assertLess(memory_increase, 50 * 1024 * 1024)
                self.assertIsNotNone(encrypted)
