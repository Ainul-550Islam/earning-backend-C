"""
Comprehensive encryption tests for rate_limit module.

This test file covers all encryption services, key management,
data protection, and encryption performance.
"""

import json
import hashlib
import secrets
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta
import base64

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.encryption import RateLimitEncryptionService

User = get_user_model()


class RateLimitEncryptionServiceTest(TestCase):
    """Test cases for RateLimitEncryptionService"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.encryption_service = RateLimitEncryptionService()
        
        # Create test data
        self.test_data = {
            'user_id': self.regular_user.id,
            'endpoint': '/api/test/',
            'method': 'GET',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'timestamp': timezone.now().isoformat()
        }
        
    def test_generate_encryption_key(self):
        """Test encryption key generation"""
        key = self.encryption_service.generate_key()
        
        # Verify key is valid Fernet key
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 44)  # Fernet key length
        
        # Verify key can be used for encryption
        fernet = Fernet(key)
        test_data = b'test message'
        encrypted = fernet.encrypt(test_data)
        decrypted = fernet.decrypt(encrypted)
        self.assertEqual(decrypted, test_data)
        
    def test_generate_aes_key(self):
        """Test AES key generation"""
        key = self.encryption_service.generate_aes_key()
        
        # Verify key is valid AES key
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)  # AES-256 key length
        
    def test_encrypt_decrypt_data(self):
        """Test data encryption and decryption"""
        # Encrypt data
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key_type='fernet'
        )
        
        # Verify encrypted data is different from original
        self.assertNotEqual(encrypted_data, self.test_data)
        self.assertIsInstance(encrypted_data, str)
        
        # Decrypt data
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key_type='fernet'
        )
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted_data, self.test_data)
        
    def test_encrypt_decrypt_aes_gcm(self):
        """Test AES-GCM encryption and decryption"""
        # Encrypt data with AES-GCM
        encrypted_result = self.encryption_service.encrypt_data_aes_gcm(
            self.test_data
        )
        
        # Verify encrypted result structure
        self.assertIn('encrypted_data', encrypted_result)
        self.assertIn('nonce', encrypted_result)
        self.assertIn('tag', encrypted_result)
        
        # Decrypt data
        decrypted_data = self.encryption_service.decrypt_data_aes_gcm(
            encrypted_result['encrypted_data'],
            encrypted_result['nonce'],
            encrypted_result['tag']
        )
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted_data, self.test_data)
        
    def test_encrypt_decrypt_chacha20(self):
        """Test ChaCha20-Poly1305 encryption and decryption"""
        # Encrypt data with ChaCha20
        encrypted_result = self.encryption_service.encrypt_data_chacha20(
            self.test_data
        )
        
        # Verify encrypted result structure
        self.assertIn('encrypted_data', encrypted_result)
        self.assertIn('nonce', encrypted_result)
        self.assertIn('tag', encrypted_result)
        
        # Decrypt data
        decrypted_data = self.encryption_service.decrypt_data_chacha20(
            encrypted_result['encrypted_data'],
            encrypted_result['nonce'],
            encrypted_result['tag']
        )
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted_data, self.test_data)
        
    def test_hash_password(self):
        """Test password hashing"""
        password = 'test_password_123'
        
        # Hash password
        hashed_password = self.encryption_service.hash_password(password)
        
        # Verify hash is different from password
        self.assertNotEqual(hashed_password, password)
        self.assertIsInstance(hashed_password, str)
        
        # Verify password can be verified
        is_valid = self.encryption_service.verify_password(password, hashed_password)
        self.assertTrue(is_valid)
        
        # Verify wrong password is rejected
        is_invalid = self.encryption_service.verify_password('wrong_password', hashed_password)
        self.assertFalse(is_invalid)
        
    def test_generate_secure_token(self):
        """Test secure token generation"""
        token = self.encryption_service.generate_secure_token()
        
        # Verify token properties
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 64)  # 32 bytes * 2 (hex encoding)
        
        # Verify tokens are unique
        token2 = self.encryption_service.generate_secure_token()
        self.assertNotEqual(token, token2)
        
    def test_encrypt_sensitive_fields(self):
        """Test encryption of sensitive model fields"""
        # Create rate limit log with sensitive data
        log_data = {
            'user': self.regular_user,
            'endpoint': '/api/sensitive/',
            'method': 'POST',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'request_data': {
                'credit_card': '4111111111111111',
                'ssn': '123-45-6789',
                'api_key': 'sk_test_1234567890'
            }
        }
        
        # Encrypt sensitive fields
        encrypted_log_data = self.encryption_service.encrypt_sensitive_fields(
            log_data,
            sensitive_fields=['request_data']
        )
        
        # Verify sensitive data is encrypted
        self.assertNotEqual(
            encrypted_log_data['request_data'],
            log_data['request_data']
        )
        
        # Decrypt sensitive fields
        decrypted_log_data = self.encryption_service.decrypt_sensitive_fields(
            encrypted_log_data,
            sensitive_fields=['request_data']
        )
        
        # Verify decrypted data matches original
        self.assertEqual(
            decrypted_log_data['request_data'],
            log_data['request_data']
        )
        
    def test_key_rotation(self):
        """Test encryption key rotation"""
        # Generate initial key
        initial_key = self.encryption_service.generate_key()
        
        # Encrypt data with initial key
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key=initial_key
        )
        
        # Generate new key
        new_key = self.encryption_service.generate_key()
        
        # Rotate encryption
        rotated_data = self.encryption_service.rotate_encryption(
            encrypted_data,
            old_key=initial_key,
            new_key=new_key
        )
        
        # Verify rotated data is different
        self.assertNotEqual(rotated_data, encrypted_data)
        
        # Decrypt with new key
        decrypted_data = self.encryption_service.decrypt_data(
            rotated_data,
            key=new_key
        )
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted_data, self.test_data)
        
    def test_encryption_performance(self):
        """Test encryption performance with large data"""
        import time
        
        # Generate large dataset
        large_data = {
            'users': [
                {
                    'id': i,
                    'name': f'user_{i}',
                    'email': f'user_{i}@example.com',
                    'data': 'x' * 1000  # 1KB per user
                }
                for i in range(1000)
            ]
        }
        
        # Test encryption performance
        start_time = time.time()
        encrypted_data = self.encryption_service.encrypt_data(
            large_data,
            key_type='fernet'
        )
        encryption_time = time.time() - start_time
        
        # Test decryption performance
        start_time = time.time()
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key_type='fernet'
        )
        decryption_time = time.time() - start_time
        
        # Verify performance is reasonable (< 1 second for 1MB data)
        self.assertLess(encryption_time, 1.0)
        self.assertLess(decryption_time, 1.0)
        
        # Verify data integrity
        self.assertEqual(decrypted_data, large_data)
        
    def test_encryption_with_invalid_key(self):
        """Test encryption with invalid key"""
        invalid_key = b'invalid_key_that_is_too_short'
        
        with self.assertRaises(Exception):
            self.encryption_service.encrypt_data(
                self.test_data,
                key=invalid_key
            )
            
    def test_decryption_with_wrong_key(self):
        """Test decryption with wrong key"""
        # Encrypt with valid key
        key1 = self.encryption_service.generate_key()
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key=key1
        )
        
        # Try to decrypt with wrong key
        key2 = self.encryption_service.generate_key()
        
        with self.assertRaises(Exception):
            self.encryption_service.decrypt_data(
                encrypted_data,
                key=key2
            )
            
    def test_encryption_corrupted_data(self):
        """Test decryption of corrupted data"""
        # Encrypt data
        encrypted_data = self.encryption_service.encrypt_data(self.test_data)
        
        # Corrupt encrypted data
        corrupted_data = encrypted_data[:-10] + 'corrupted'
        
        with self.assertRaises(Exception):
            self.encryption_service.decrypt_data(corrupted_data)
            
    def test_encrypt_decrypt_binary_data(self):
        """Test encryption and decryption of binary data"""
        binary_data = b'\x00\x01\x02\x03\x04\x05' * 100  # 600 bytes
        
        # Encrypt binary data
        encrypted_data = self.encryption_service.encrypt_data(
            binary_data,
            key_type='fernet'
        )
        
        # Decrypt binary data
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key_type='fernet'
        )
        
        # Verify data integrity
        self.assertEqual(decrypted_data, binary_data)
        
    def test_encrypt_decrypt_unicode_data(self):
        """Test encryption and decryption of unicode data"""
        unicode_data = {
            'message': 'Hello world! ¡Hola mundo! Bonjour le monde!  Hallo Welt!',
            'emoji': 'ððððð',
            'symbols': 'â â â â â',
            'chinese': 'ä½ å¥½ä¸çå¢ ï¼',
            'arabic': 'Ù ÙØ±ØØ¨Ø§ ÙØ§ÙÙÙÙ '
        }
        
        # Encrypt unicode data
        encrypted_data = self.encryption_service.encrypt_data(unicode_data)
        
        # Decrypt unicode data
        decrypted_data = self.encryption_service.decrypt_data(encrypted_data)
        
        # Verify data integrity
        self.assertEqual(decrypted_data, unicode_data)
        
    def test_key_derivation(self):
        """Test key derivation from password"""
        password = 'test_password_123'
        salt = secrets.token_bytes(16)
        
        # Derive key from password
        derived_key = self.encryption_service.derive_key_from_password(
            password,
            salt
        )
        
        # Verify derived key properties
        self.assertIsInstance(derived_key, bytes)
        self.assertEqual(len(derived_key), 32)  # 256-bit key
        
        # Verify same password and salt produces same key
        derived_key2 = self.encryption_service.derive_key_from_password(
            password,
            salt
        )
        self.assertEqual(derived_key, derived_key2)
        
        # Verify different salt produces different key
        salt2 = secrets.token_bytes(16)
        derived_key3 = self.encryption_service.derive_key_from_password(
            password,
            salt2
        )
        self.assertNotEqual(derived_key, derived_key3)
        
    def test_encryption_metadata(self):
        """Test encryption metadata tracking"""
        # Encrypt data with metadata
        encryption_result = self.encryption_service.encrypt_data_with_metadata(
            self.test_data,
            algorithm='fernet',
            key_id='test_key_1',
            version='1.0'
        )
        
        # Verify metadata structure
        self.assertIn('encrypted_data', encryption_result)
        self.assertIn('metadata', encryption_result)
        
        metadata = encryption_result['metadata']
        self.assertEqual(metadata['algorithm'], 'fernet')
        self.assertEqual(metadata['key_id'], 'test_key_1')
        self.assertEqual(metadata['version'], '1.0')
        self.assertIn('timestamp', metadata)
        self.assertIn('data_hash', metadata)
        
        # Verify data hash
        original_hash = hashlib.sha256(
            json.dumps(self.test_data, sort_keys=True).encode()
        ).hexdigest()
        self.assertEqual(metadata['data_hash'], original_hash)
        
    def test_batch_encryption(self):
        """Test batch encryption of multiple items"""
        batch_data = [
            {'id': 1, 'data': 'test_data_1'},
            {'id': 2, 'data': 'test_data_2'},
            {'id': 3, 'data': 'test_data_3'}
        ]
        
        # Encrypt batch
        encrypted_batch = self.encryption_service.encrypt_batch(batch_data)
        
        # Verify all items are encrypted
        self.assertEqual(len(encrypted_batch), len(batch_data))
        for encrypted_item in encrypted_batch:
            self.assertIn('encrypted_data', encrypted_item)
            self.assertIn('metadata', encrypted_item)
            
        # Decrypt batch
        decrypted_batch = self.encryption_service.decrypt_batch(encrypted_batch)
        
        # Verify decrypted data matches original
        self.assertEqual(decrypted_batch, batch_data)
        
    def test_secure_random_generation(self):
        """Test secure random number generation"""
        # Generate random bytes
        random_bytes = self.encryption_service.generate_secure_random_bytes(32)
        
        # Verify properties
        self.assertIsInstance(random_bytes, bytes)
        self.assertEqual(len(random_bytes), 32)
        
        # Verify randomness
        random_bytes2 = self.encryption_service.generate_secure_random_bytes(32)
        self.assertNotEqual(random_bytes, random_bytes2)
        
        # Generate random integer
        random_int = self.encryption_service.generate_secure_random_int(1, 1000000)
        
        # Verify properties
        self.assertIsInstance(random_int, int)
        self.assertGreaterEqual(random_int, 1)
        self.assertLessEqual(random_int, 1000000)
        
    def test_encryption_key_storage(self):
        """Test encryption key storage and retrieval"""
        # Store encryption key
        key_id = 'test_key_storage'
        key = self.encryption_service.generate_key()
        
        self.encryption_service.store_encryption_key(key_id, key)
        
        # Retrieve encryption key
        retrieved_key = self.encryption_service.get_encryption_key(key_id)
        
        # Verify key matches
        self.assertEqual(retrieved_key, key)
        
        # Delete encryption key
        self.encryption_service.delete_encryption_key(key_id)
        
        # Verify key is deleted
        with self.assertRaises(KeyError):
            self.encryption_service.get_encryption_key(key_id)
            
    def test_encryption_audit_log(self):
        """Test encryption audit logging"""
        # Perform encryption operation
        encrypted_data = self.encryption_service.encrypt_data(self.test_data)
        
        # Check audit log
        audit_logs = self.encryption_service.get_encryption_audit_logs()
        
        # Verify audit log entry
        self.assertEqual(len(audit_logs), 1)
        log_entry = audit_logs[0]
        
        self.assertEqual(log_entry['operation'], 'encrypt')
        self.assertIn('timestamp', log_entry)
        self.assertIn('data_size', log_entry)
        self.assertIn('algorithm', log_entry)
        
        # Perform decryption operation
        self.encryption_service.decrypt_data(encrypted_data)
        
        # Check audit log again
        audit_logs = self.encryption_service.get_encryption_audit_logs()
        
        # Verify both operations are logged
        self.assertEqual(len(audit_logs), 2)
        self.assertEqual(audit_logs[1]['operation'], 'decrypt')


class RateLimitEncryptionIntegrationTest(TransactionTestCase):
    """Integration tests for rate limit encryption"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.encryption_service = RateLimitEncryptionService()
        
    def test_end_to_end_encryption_workflow(self):
        """Test complete encryption workflow"""
        # Create sensitive rate limit data
        rate_limit_data = {
            'user_id': self.regular_user.id,
            'endpoint': '/api/payment/',
            'method': 'POST',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'request_data': {
                'credit_card': '4111111111111111',
                'cvv': '123',
                'expiry': '12/25',
                'amount': '99.99'
            },
            'response_data': {
                'transaction_id': 'txn_1234567890',
                'status': 'approved',
                'auth_code': '123456'
            }
        }
        
        # Encrypt sensitive fields
        encrypted_data = self.encryption_service.encrypt_sensitive_fields(
            rate_limit_data,
            sensitive_fields=['request_data', 'response_data']
        )
        
        # Store encrypted data in rate limit log
        rate_limit_log = RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint=encrypted_data['endpoint'],
            method=encrypted_data['method'],
            ip_address=encrypted_data['ip_address'],
            user_agent=encrypted_data['user_agent'],
            status_code=200,
            is_allowed=True,
            encrypted_request_data=encrypted_data['request_data'],
            encrypted_response_data=encrypted_data['response_data']
        )
        
        # Retrieve and decrypt data
        decrypted_data = self.encryption_service.decrypt_sensitive_fields(
            {
                'request_data': rate_limit_log.encrypted_request_data,
                'response_data': rate_limit_log.encrypted_response_data
            },
            sensitive_fields=['request_data', 'response_data']
        )
        
        # Verify decrypted data matches original
        self.assertEqual(
            decrypted_data['request_data'],
            rate_limit_data['request_data']
        )
        self.assertEqual(
            decrypted_data['response_data'],
            rate_limit_data['response_data']
        )
        
    def test_encryption_key_rotation_workflow(self):
        """Test encryption key rotation workflow"""
        # Create initial encryption key
        initial_key_id = 'initial_key'
        initial_key = self.encryption_service.generate_key()
        self.encryption_service.store_encryption_key(initial_key_id, initial_key)
        
        # Encrypt data with initial key
        sensitive_data = {
            'api_key': 'sk_test_1234567890',
            'webhook_secret': 'whsec_1234567890',
            'database_password': 'db_pass_123'
        }
        
        encrypted_data = self.encryption_service.encrypt_data(
            sensitive_data,
            key=initial_key
        )
        
        # Create new encryption key
        new_key_id = 'new_key'
        new_key = self.encryption_service.generate_key()
        self.encryption_service.store_encryption_key(new_key_id, new_key)
        
        # Rotate encryption
        rotated_data = self.encryption_service.rotate_encryption(
            encrypted_data,
            old_key_id=initial_key_id,
            new_key_id=new_key_id
        )
        
        # Delete old key
        self.encryption_service.delete_encryption_key(initial_key_id)
        
        # Verify old key is gone
        with self.assertRaises(KeyError):
            self.encryption_service.get_encryption_key(initial_key_id)
        
        # Verify data can still be decrypted with new key
        decrypted_data = self.encryption_service.decrypt_data(
            rotated_data,
            key_id=new_key_id
        )
        
        self.assertEqual(decrypted_data, sensitive_data)
        
    def test_encryption_performance_under_load(self):
        """Test encryption performance under load"""
        import time
        import threading
        
        # Generate test data
        test_data_sets = [
            {
                'user_id': i,
                'data': 'x' * 1000  # 1KB per record
            }
            for i in range(100)
        ]
        
        # Test concurrent encryption
        results = []
        errors = []
        
        def encrypt_data(data_set):
            try:
                start_time = time.time()
                encrypted = self.encryption_service.encrypt_data(data_set)
                end_time = time.time()
                results.append({
                    'data_set': data_set,
                    'encrypted_data': encrypted,
                    'time': end_time - start_time
                })
            except Exception as e:
                errors.append(str(e))
        
        # Start concurrent threads
        threads = []
        for data_set in test_data_sets:
            thread = threading.Thread(target=encrypt_data, args=(data_set,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(results), len(test_data_sets))
        self.assertEqual(len(errors), 0)
        
        # Verify performance (all operations should complete within 5 seconds)
        total_time = sum(result['time'] for result in results)
        self.assertLess(total_time, 5.0)
        
        # Verify data integrity
        for result in results:
            decrypted = self.encryption_service.decrypt_data(result['encrypted_data'])
            self.assertEqual(decrypted, result['data_set'])
