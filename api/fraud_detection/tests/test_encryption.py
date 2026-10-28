"""
Comprehensive encryption service testing for fraud_detection module.

This test file covers all encryption functionality and data protection
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import base64
import hashlib
import secrets

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.encryption import (
    FraudEncryptionService, DataEncryption, KeyManagement,
    SecureHashing, TokenGeneration, SecureStorage
)
from api.users.models import User

User = get_user_model()


class BaseEncryptionTest(TestCase):
    """Base test class for encryption testing"""
    
    def setUp(self):
        """Set up common test data"""
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
        
        # Test encryption keys
        self.test_key = Fernet.generate_key()
        self.test_password = 'test_encryption_password_123'
        self.test_salt = os.urandom(16)
        
        # Test data
        self.test_data = {
            'user_id': self.regular_user.pk,
            'fraud_score': 85,
            'risk_level': 'high',
            'evidence': {
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0 (Test Browser)',
                'timestamp': timezone.now().isoformat()
            }
        }
        
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class FraudEncryptionServiceTest(BaseEncryptionTest):
    """Test cases for FraudEncryptionService"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.encryption_service = FraudEncryptionService()
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test complete encrypt-decrypt roundtrip"""
        # Encrypt data
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key=self.test_key
        )
        
        self.assertIsInstance(encrypted_data, str)
        self.assertNotEqual(encrypted_data, json.dumps(self.test_data))
        
        # Decrypt data
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key=self.test_key
        )
        
        self.assertEqual(decrypted_data, self.test_data)
    
    def test_encrypt_with_generated_key(self):
        """Test encryption with auto-generated key"""
        encrypted_data, key = self.encryption_service.encrypt_with_generated_key(
            self.test_data
        )
        
        self.assertIsInstance(encrypted_data, str)
        self.assertIsInstance(key, bytes)
        
        # Decrypt with generated key
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key=key
        )
        
        self.assertEqual(decrypted_data, self.test_data)
    
    def test_encrypt_with_password(self):
        """Test encryption with password-based key derivation"""
        encrypted_data, salt = self.encryption_service.encrypt_with_password(
            self.test_data,
            password=self.test_password
        )
        
        self.assertIsInstance(encrypted_data, str)
        self.assertIsInstance(salt, bytes)
        
        # Decrypt with password
        decrypted_data = self.encryption_service.decrypt_with_password(
            encrypted_data,
            password=self.test_password,
            salt=salt
        )
        
        self.assertEqual(decrypted_data, self.test_data)
    
    def test_encrypt_fraud_attempt_data(self):
        """Test encrypting fraud attempt specific data"""
        fraud_attempt = FraudAttempt.objects.create(
            user=self.regular_user,
            attempt_type='multi_account',
            description='Test fraud attempt',
            detected_by='TestDetector',
            fraud_score=85,
            evidence_data={'ip_address': '192.168.1.1'},
            metadata={'detector_version': '1.0'}
        )
        
        # Encrypt sensitive fields
        encrypted_evidence = self.encryption_service.encrypt_fraud_attempt_data(
            fraud_attempt,
            fields=['evidence_data', 'metadata']
        )
        
        self.assertIn('encrypted_evidence_data', encrypted_evidence)
        self.assertIn('encrypted_metadata', encrypted_evidence)
        self.assertIn('encryption_key_id', encrypted_evidence)
        
        # Decrypt the data
        decrypted_data = self.encryption_service.decrypt_fraud_attempt_data(
            encrypted_evidence
        )
        
        self.assertEqual(
            decrypted_data['evidence_data'],
            fraud_attempt.evidence_data
        )
        self.assertEqual(decrypted_data['metadata'], fraud_attempt.metadata)
    
    def test_encrypt_user_risk_profile(self):
        """Test encrypting user risk profile data"""
        risk_profile = UserRiskProfile.objects.create(
            user=self.regular_user,
            overall_risk_score=75,
            risk_factors={
                'multiple_accounts': True,
                'suspicious_ips': ['192.168.1.1', '192.168.1.2'],
                'unusual_devices': ['device_123', 'device_456']
            },
            restrictions={
                'payment_methods': ['credit_card'],
                'withdrawal_limits': {'daily': 1000}
            }
        )
        
        # Encrypt sensitive fields
        encrypted_profile = self.encryption_service.encrypt_user_risk_profile(
            risk_profile,
            fields=['risk_factors', 'restrictions']
        )
        
        self.assertIn('encrypted_risk_factors', encrypted_profile)
        self.assertIn('encrypted_restrictions', encrypted_profile)
        self.assertIn('encryption_key_id', encrypted_profile)
        
        # Decrypt the data
        decrypted_data = self.encryption_service.decrypt_user_risk_profile(
            encrypted_profile
        )
        
        self.assertEqual(decrypted_data['risk_factors'], risk_profile.risk_factors)
        self.assertEqual(decrypted_data['restrictions'], risk_profile.restrictions)
    
    def test_encrypt_device_fingerprint(self):
        """Test encrypting device fingerprint data"""
        device_fingerprint = DeviceFingerprint.objects.create(
            user=self.regular_user,
            device_id='test_device_123',
            device_hash='abc123def456',
            location_data={
                'country': 'US',
                'city': 'New York',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'accuracy': 10.5
            },
            user_agent='Mozilla/5.0 (Test Browser)',
            ip_address='192.168.1.1'
        )
        
        # Encrypt sensitive fields
        encrypted_fingerprint = self.encryption_service.encrypt_device_fingerprint(
            device_fingerprint,
            fields=['location_data', 'user_agent']
        )
        
        self.assertIn('encrypted_location_data', encrypted_fingerprint)
        self.assertIn('encrypted_user_agent', encrypted_fingerprint)
        
        # Decrypt the data
        decrypted_data = self.encryption_service.decrypt_device_fingerprint(
            encrypted_fingerprint
        )
        
        self.assertEqual(decrypted_data['location_data'], device_fingerprint.location_data)
        self.assertEqual(decrypted_data['user_agent'], device_fingerprint.user_agent)
    
    def test_batch_encryption(self):
        """Test batch encryption of multiple records"""
        # Create test data
        test_records = [
            {'id': 1, 'data': {'sensitive': 'info1'}},
            {'id': 2, 'data': {'sensitive': 'info2'}},
            {'id': 3, 'data': {'sensitive': 'info3'}}
        ]
        
        # Encrypt batch
        encrypted_batch = self.encryption_service.encrypt_batch(
            test_records,
            key=self.test_key
        )
        
        self.assertEqual(len(encrypted_batch), 3)
        for encrypted_record in encrypted_batch:
            self.assertIn('encrypted_data', encrypted_record)
            self.assertIn('id', encrypted_record)
        
        # Decrypt batch
        decrypted_batch = self.encryption_service.decrypt_batch(
            encrypted_batch,
            key=self.test_key
        )
        
        self.assertEqual(len(decrypted_batch), 3)
        for i, decrypted_record in enumerate(decrypted_batch):
            self.assertEqual(decrypted_record['data'], test_records[i]['data'])
    
    def test_encryption_performance(self):
        """Test encryption performance with large data"""
        large_data = {
            'user_id': self.regular_user.pk,
            'events': []
        }
        
        # Generate large dataset
        for i in range(1000):
            large_data['events'].append({
                'timestamp': timezone.now().isoformat(),
                'action': f'action_{i}',
                'details': {'value': i * 10, 'description': f'Description {i}'}
            })
        
        # Measure encryption time
        import time
        start_time = time.time()
        
        encrypted_data = self.encryption_service.encrypt_data(
            large_data,
            key=self.test_key
        )
        
        encryption_time = time.time() - start_time
        
        # Measure decryption time
        start_time = time.time()
        
        decrypted_data = self.encryption_service.decrypt_data(
            encrypted_data,
            key=self.test_key
        )
        
        decryption_time = time.time() - start_time
        
        # Verify data integrity
        self.assertEqual(decrypted_data, large_data)
        
        # Performance should be reasonable (less than 1 second for this dataset)
        self.assertLess(encryption_time, 1.0)
        self.assertLess(decryption_time, 1.0)
    
    def test_encryption_key_rotation(self):
        """Test encryption key rotation"""
        # Encrypt with original key
        original_key = Fernet.generate_key()
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key=original_key
        )
        
        # Generate new key
        new_key = Fernet.generate_key()
        
        # Re-encrypt with new key
        reencrypted_data = self.encryption_service.rotate_key(
            encrypted_data,
            old_key=original_key,
            new_key=new_key
        )
        
        # Decrypt with new key
        decrypted_data = self.encryption_service.decrypt_data(
            reencrypted_data,
            key=new_key
        )
        
        self.assertEqual(decrypted_data, self.test_data)
        
        # Should fail with old key
        with self.assertRaises(Exception):
            self.encryption_service.decrypt_data(
                reencrypted_data,
                key=original_key
            )
    
    def test_encryption_error_handling(self):
        """Test encryption error handling"""
        # Test invalid key
        invalid_key = b'invalid_key_that_is_too_short'
        
        with self.assertRaises(Exception):
            self.encryption_service.encrypt_data(
                self.test_data,
                key=invalid_key
            )
        
        # Test corrupted data
        corrupted_data = "corrupted_encrypted_data"
        
        with self.assertRaises(Exception):
            self.encryption_service.decrypt_data(
                corrupted_data,
                key=self.test_key
            )
        
        # Test wrong key
        wrong_key = Fernet.generate_key()
        encrypted_data = self.encryption_service.encrypt_data(
            self.test_data,
            key=self.test_key
        )
        
        with self.assertRaises(Exception):
            self.encryption_service.decrypt_data(
                encrypted_data,
                key=wrong_key
            )


class DataEncryptionTest(BaseEncryptionTest):
    """Test cases for DataEncryption class"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.data_encryption = DataEncryption()
    
    def test_aes_gcm_encryption(self):
        """Test AES-GCM encryption"""
        plaintext = json.dumps(self.test_data).encode('utf-8')
        key = os.urandom(32)  # 256-bit key
        iv = os.urandom(12)   # 96-bit IV for GCM
        
        # Encrypt
        ciphertext, tag = self.data_encryption.encrypt_aes_gcm(
            plaintext,
            key=key,
            iv=iv
        )
        
        self.assertIsInstance(ciphertext, bytes)
        self.assertIsInstance(tag, bytes)
        self.assertNotEqual(ciphertext, plaintext)
        
        # Decrypt
        decrypted_plaintext = self.data_encryption.decrypt_aes_gcm(
            ciphertext,
            key=key,
            iv=iv,
            tag=tag
        )
        
        self.assertEqual(decrypted_plaintext, plaintext)
    
    def test_chacha20_poly1305_encryption(self):
        """Test ChaCha20-Poly1305 encryption"""
        plaintext = json.dumps(self.test_data).encode('utf-8')
        key = os.urandom(32)  # 256-bit key
        nonce = os.urandom(12)  # 96-bit nonce
        
        # Encrypt
        ciphertext, tag = self.data_encryption.encrypt_chacha20_poly1305(
            plaintext,
            key=key,
            nonce=nonce
        )
        
        self.assertIsInstance(ciphertext, bytes)
        self.assertIsInstance(tag, bytes)
        
        # Decrypt
        decrypted_plaintext = self.data_encryption.decrypt_chacha20_poly1305(
            ciphertext,
            key=key,
            nonce=nonce,
            tag=tag
        )
        
        self.assertEqual(decrypted_plaintext, plaintext)
    
    def test_fernet_encryption(self):
        """Test Fernet encryption"""
        key = Fernet.generate_key()
        fernet = Fernet(key)
        
        plaintext = json.dumps(self.test_data).encode('utf-8')
        
        # Encrypt
        ciphertext = self.data_encryption.encrypt_fernet(
            plaintext,
            key=key
        )
        
        self.assertIsInstance(ciphertext, bytes)
        
        # Decrypt
        decrypted_plaintext = self.data_encryption.decrypt_fernet(
            ciphertext,
            key=key
        )
        
        self.assertEqual(decrypted_plaintext, plaintext)
    
    def test_encryption_algorithm_comparison(self):
        """Test comparison of different encryption algorithms"""
        plaintext = json.dumps(self.test_data).encode('utf-8')
        
        # Test Fernet
        fernet_key = Fernet.generate_key()
        fernet_ciphertext = self.data_encryption.encrypt_fernet(
            plaintext,
            key=fernet_key
        )
        
        # Test AES-GCM
        aes_key = os.urandom(32)
        aes_iv = os.urandom(12)
        aes_ciphertext, aes_tag = self.data_encryption.encrypt_aes_gcm(
            plaintext,
            key=aes_key,
            iv=aes_iv
        )
        
        # Test ChaCha20-Poly1305
        chacha_key = os.urandom(32)
        chacha_nonce = os.urandom(12)
        chacha_ciphertext, chacha_tag = self.data_encryption.encrypt_chacha20_poly1305(
            plaintext,
            key=chacha_key,
            nonce=chacha_nonce
        )
        
        # All should produce different ciphertexts
        self.assertNotEqual(fernet_ciphertext, aes_ciphertext)
        self.assertNotEqual(aes_ciphertext, chacha_ciphertext)
        
        # All should decrypt to the same plaintext
        fernet_decrypted = self.data_encryption.decrypt_fernet(
            fernet_ciphertext,
            key=fernet_key
        )
        
        aes_decrypted = self.data_encryption.decrypt_aes_gcm(
            aes_ciphertext,
            key=aes_key,
            iv=aes_iv,
            tag=aes_tag
        )
        
        chacha_decrypted = self.data_encryption.decrypt_chacha20_poly1305(
            chacha_ciphertext,
            key=chacha_key,
            nonce=chacha_nonce,
            tag=chacha_tag
        )
        
        self.assertEqual(fernet_decrypted, plaintext)
        self.assertEqual(aes_decrypted, plaintext)
        self.assertEqual(chacha_decrypted, plaintext)
    
    def test_encryption_with_associated_data(self):
        """Test encryption with associated data (AEAD)"""
        plaintext = json.dumps(self.test_data).encode('utf-8')
        associated_data = b'fraud_detection_metadata_v1'
        
        # Test AES-GCM with associated data
        key = os.urandom(32)
        iv = os.urandom(12)
        ciphertext, tag = self.data_encryption.encrypt_aes_gcm(
            plaintext,
            key=key,
            iv=iv,
            associated_data=associated_data
        )
        
        # Decrypt with correct associated data
        decrypted = self.data_encryption.decrypt_aes_gcm(
            ciphertext,
            key=key,
            iv=iv,
            tag=tag,
            associated_data=associated_data
        )
        self.assertEqual(decrypted, plaintext)
        
        # Decrypt with incorrect associated data should fail
        with self.assertRaises(Exception):
            self.data_encryption.decrypt_aes_gcm(
                ciphertext,
                key=key,
                iv=iv,
                tag=tag,
                associated_data=b'incorrect_metadata'
            )


class KeyManagementTest(BaseEncryptionTest):
    """Test cases for KeyManagement class"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.key_manager = KeyManagement()
    
    def test_generate_key(self):
        """Test key generation"""
        key = self.key_manager.generate_key('fernet')
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 44)  # Fernet keys are base64-encoded 32-byte keys
        
        key = self.key_manager.generate_key('aes')
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)  # AES-256 keys are 32 bytes
        
        key = self.key_manager.generate_key('chacha20')
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)  # ChaCha20 keys are 32 bytes
    
    def test_derive_key_from_password(self):
        """Test key derivation from password"""
        password = self.test_password.encode('utf-8')
        salt = self.test_salt
        
        key = self.key_manager.derive_key_from_password(
            password,
            salt,
            algorithm='pbkdf2',
            iterations=100000
        )
        
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)  # 256-bit key
        
        # Same password and salt should produce same key
        key2 = self.key_manager.derive_key_from_password(
            password,
            salt,
            algorithm='pbkdf2',
            iterations=100000
        )
        self.assertEqual(key, key2)
        
        # Different salt should produce different key
        different_salt = os.urandom(16)
        key3 = self.key_manager.derive_key_from_password(
            password,
            different_salt,
            algorithm='pbkdf2',
            iterations=100000
        )
        self.assertNotEqual(key, key3)
    
    def test_store_and_retrieve_key(self):
        """Test storing and retrieving keys"""
        key_id = 'test_key_123'
        key = self.key_manager.generate_key('fernet')
        
        # Store key
        self.key_manager.store_key(key_id, key, metadata={'purpose': 'test'})
        
        # Retrieve key
        retrieved_key, metadata = self.key_manager.retrieve_key(key_id)
        
        self.assertEqual(retrieved_key, key)
        self.assertEqual(metadata['purpose'], 'test')
    
    def test_key_rotation(self):
        """Test key rotation"""
        key_id = 'rotating_key_456'
        original_key = self.key_manager.generate_key('fernet')
        
        # Store original key
        self.key_manager.store_key(key_id, original_key, version=1)
        
        # Rotate key
        new_key = self.key_manager.rotate_key(key_id)
        
        self.assertNotEqual(new_key, original_key)
        
        # Retrieve new key
        retrieved_key, metadata = self.key_manager.retrieve_key(key_id)
        self.assertEqual(retrieved_key, new_key)
        self.assertEqual(metadata['version'], 2)
        
        # Old key should still be accessible for decryption
        old_key, old_metadata = self.key_manager.retrieve_key(key_id, version=1)
        self.assertEqual(old_key, original_key)
        self.assertEqual(old_metadata['version'], 1)
    
    def test_key_destruction(self):
        """Test secure key destruction"""
        key_id = 'destructible_key_789'
        key = self.key_manager.generate_key('fernet')
        
        # Store key
        self.key_manager.store_key(key_id, key)
        
        # Verify key exists
        retrieved_key, _ = self.key_manager.retrieve_key(key_id)
        self.assertEqual(retrieved_key, key)
        
        # Destroy key
        self.key_manager.destroy_key(key_id)
        
        # Key should no longer be accessible
        with self.assertRaises(Exception):
            self.key_manager.retrieve_key(key_id)
    
    def test_key_export_import(self):
        """Test key export and import"""
        key_id = 'exportable_key_999'
        key = self.key_manager.generate_key('fernet')
        
        # Store key
        self.key_manager.store_key(key_id, key)
        
        # Export key
        exported_data = self.key_manager.export_key(key_id, include_metadata=True)
        
        self.assertIn('key_data', exported_data)
        self.assertIn('metadata', exported_data)
        self.assertIn('export_timestamp', exported_data)
        
        # Import key to new key ID
        new_key_id = 'imported_key_888'
        self.key_manager.import_key(new_key_id, exported_data)
        
        # Verify imported key
        imported_key, imported_metadata = self.key_manager.retrieve_key(new_key_id)
        self.assertEqual(imported_key, key)
        self.assertEqual(imported_metadata['purpose'], exported_data['metadata']['purpose'])


class SecureHashingTest(BaseEncryptionTest):
    """Test cases for SecureHashing class"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.secure_hashing = SecureHashing()
    
    def test_sha256_hashing(self):
        """Test SHA-256 hashing"""
        data = json.dumps(self.test_data).encode('utf-8')
        
        hash_value = self.secure_hashing.hash_sha256(data)
        
        self.assertIsInstance(hash_value, str)
        self.assertEqual(len(hash_value), 64)  # SHA-256 produces 64-character hex string
        
        # Same data should produce same hash
        hash_value2 = self.secure_hashing.hash_sha256(data)
        self.assertEqual(hash_value, hash_value2)
        
        # Different data should produce different hash
        different_data = b'different data'
        hash_value3 = self.secure_hashing.hash_sha256(different_data)
        self.assertNotEqual(hash_value, hash_value3)
    
    def test_hash_with_salt(self):
        """Test hashing with salt"""
        data = json.dumps(self.test_data).encode('utf-8')
        salt = self.test_salt
        
        salted_hash = self.secure_hashing.hash_with_salt(data, salt)
        
        self.assertIsInstance(salted_hash, str)
        
        # Same data and salt should produce same hash
        salted_hash2 = self.secure_hashing.hash_with_salt(data, salt)
        self.assertEqual(salted_hash, salted_hash2)
        
        # Same data with different salt should produce different hash
        different_salt = os.urandom(16)
        salted_hash3 = self.secure_hashing.hash_with_salt(data, different_salt)
        self.assertNotEqual(salted_hash, salted_hash3)
    
    def test_hash_verification(self):
        """Test hash verification"""
        data = json.dumps(self.test_data).encode('utf-8')
        
        # Generate hash
        hash_value = self.secure_hashing.hash_sha256(data)
        
        # Verify correct data
        is_valid = self.secure_hashing.verify_hash(data, hash_value)
        self.assertTrue(is_valid)
        
        # Verify incorrect data
        incorrect_data = b'incorrect data'
        is_invalid = self.secure_hashing.verify_hash(incorrect_data, hash_value)
        self.assertFalse(is_invalid)
    
    def test_hmac_generation(self):
        """Test HMAC generation"""
        data = json.dumps(self.test_data).encode('utf-8')
        secret_key = b'hmac_secret_key_123'
        
        hmac_value = self.secure_hashing.generate_hmac(data, secret_key)
        
        self.assertIsInstance(hmac_value, str)
        
        # Same data and key should produce same HMAC
        hmac_value2 = self.secure_hashing.generate_hmac(data, secret_key)
        self.assertEqual(hmac_value, hmac_value2)
        
        # Different key should produce different HMAC
        different_key = b'different_secret_key'
        hmac_value3 = self.secure_hashing.generate_hmac(data, different_key)
        self.assertNotEqual(hmac_value, hmac_value3)
    
    def test_hmac_verification(self):
        """Test HMAC verification"""
        data = json.dumps(self.test_data).encode('utf-8')
        secret_key = b'hmac_secret_key_123'
        
        # Generate HMAC
        hmac_value = self.secure_hashing.generate_hmac(data, secret_key)
        
        # Verify with correct key
        is_valid = self.secure_hashing.verify_hmac(data, hmac_value, secret_key)
        self.assertTrue(is_valid)
        
        # Verify with incorrect key
        incorrect_key = b'incorrect_secret_key'
        is_invalid = self.secure_hashing.verify_hmac(data, hmac_value, incorrect_key)
        self.assertFalse(is_invalid)
    
    def test_password_hashing(self):
        """Test secure password hashing"""
        password = self.test_password
        
        # Hash password
        hashed_password = self.secure_hashing.hash_password(password)
        
        self.assertIsInstance(hashed_password, str)
        self.assertNotEqual(hashed_password, password)
        
        # Verify correct password
        is_valid = self.secure_hashing.verify_password(password, hashed_password)
        self.assertTrue(is_valid)
        
        # Verify incorrect password
        is_invalid = self.secure_hashing.verify_password('wrong_password', hashed_password)
        self.assertFalse(is_invalid)
    
    def test_hash_collision_resistance(self):
        """Test hash collision resistance"""
        # Generate two different but similar data sets
        data1 = {'user_id': 1, 'score': 85}
        data2 = {'user_id': 1, 'score': 86}  # Only score differs
        
        hash1 = self.secure_hashing.hash_sha256(json.dumps(data1).encode('utf-8'))
        hash2 = self.secure_hashing.hash_sha256(json.dumps(data2).encode('utf-8'))
        
        # Hashes should be different
        self.assertNotEqual(hash1, hash2)
        
        # Even small changes should produce completely different hashes
        self.assertNotEqual(hash1[:10], hash2[:10])  # First 10 characters should differ


class TokenGenerationTest(BaseEncryptionTest):
    """Test cases for TokenGeneration class"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.token_generator = TokenGeneration()
    
    def test_generate_secure_token(self):
        """Test secure token generation"""
        token = self.token_generator.generate_secure_token(length=32)
        
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 32)
        
        # Tokens should be different each time
        token2 = self.token_generator.generate_secure_token(length=32)
        self.assertNotEqual(token, token2)
    
    def test_generate_api_key(self):
        """Test API key generation"""
        api_key = self.token_generator.generate_api_key()
        
        self.assertIsInstance(api_key, str)
        self.assertTrue(api_key.startswith('fd_'))  # Fraud detection prefix
        self.assertEqual(len(api_key), 32)  # prefix + 28 character token
        
        # API keys should be different each time
        api_key2 = self.token_generator.generate_api_key()
        self.assertNotEqual(api_key, api_key2)
    
    def test_generate_session_token(self):
        """Test session token generation"""
        session_token = self.token_generator.generate_session_token(
            user_id=self.regular_user.pk
        )
        
        self.assertIsInstance(session_token, str)
        self.assertIn(str(self.regular_user.pk), session_token)
        
        # Session tokens should include timestamp
        self.assertIn('timestamp', session_token)
        
        # Different users should get different tokens
        admin_token = self.token_generator.generate_session_token(
            user_id=self.admin_user.pk
        )
        self.assertNotEqual(session_token, admin_token)
    
    def test_generate_webhook_signature_token(self):
        """Test webhook signature token generation"""
        payload = json.dumps(self.test_data)
        secret = b'webhook_secret_123'
        
        signature_token = self.token_generator.generate_webhook_signature(
            payload,
            secret
        )
        
        self.assertIsInstance(signature_token, str)
        
        # Same payload and secret should produce same signature
        signature_token2 = self.token_generator.generate_webhook_signature(
            payload,
            secret
        )
        self.assertEqual(signature_token, signature_token2)
        
        # Different secret should produce different signature
        different_secret = b'different_secret'
        signature_token3 = self.token_generator.generate_webhook_signature(
            payload,
            different_secret
        )
        self.assertNotEqual(signature_token, signature_token3)
    
    def test_validate_token_format(self):
        """Test token format validation"""
        # Valid API key
        valid_api_key = self.token_generator.generate_api_key()
        is_valid = self.token_generator.validate_token_format(valid_api_key, 'api_key')
        self.assertTrue(is_valid)
        
        # Invalid API key
        invalid_api_key = 'invalid_key_format'
        is_invalid = self.token_generator.validate_token_format(invalid_api_key, 'api_key')
        self.assertFalse(is_invalid)
        
        # Valid session token
        valid_session_token = self.token_generator.generate_session_token(
            user_id=self.regular_user.pk
        )
        is_valid = self.token_generator.validate_token_format(valid_session_token, 'session_token')
        self.assertTrue(is_valid)
    
    def test_token_expiration(self):
        """Test token expiration handling"""
        # Generate token with short expiration
        short_lived_token = self.token_generator.generate_secure_token(
            length=32,
            expires_in=1  # 1 second
        )
        
        # Token should be valid immediately
        is_valid = self.token_generator.is_token_valid(short_lived_token)
        self.assertTrue(is_valid)
        
        # Wait for expiration (in real implementation, this would use time mocking)
        # For testing purposes, we'll simulate expiration
        import time
        time.sleep(2)
        
        # Token should be expired
        is_expired = self.token_generator.is_token_valid(short_lived_token)
        self.assertFalse(is_expired)


class SecureStorageTest(BaseEncryptionTest):
    """Test cases for SecureStorage class"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.secure_storage = SecureStorage()
    
    def test_store_encrypted_data(self):
        """Test storing encrypted data"""
        data_id = 'secure_data_123'
        
        # Store encrypted data
        storage_id = self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            encryption_algorithm='fernet'
        )
        
        self.assertIsInstance(storage_id, str)
        self.assertEqual(storage_id, data_id)
    
    def test_retrieve_encrypted_data(self):
        """Test retrieving encrypted data"""
        data_id = 'secure_data_456'
        
        # Store encrypted data
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            encryption_algorithm='fernet'
        )
        
        # Retrieve encrypted data
        retrieved_data = self.secure_storage.retrieve_encrypted_data(data_id)
        
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_secure_delete(self):
        """Test secure deletion of data"""
        data_id = 'secure_data_789'
        
        # Store encrypted data
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            encryption_algorithm='fernet'
        )
        
        # Verify data exists
        retrieved_data = self.secure_storage.retrieve_encrypted_data(data_id)
        self.assertEqual(retrieved_data, self.test_data)
        
        # Secure delete
        self.secure_storage.secure_delete(data_id)
        
        # Data should no longer be accessible
        with self.assertRaises(Exception):
            self.secure_storage.retrieve_encrypted_data(data_id)
    
    def test_data_integrity_verification(self):
        """Test data integrity verification"""
        data_id = 'integrity_test_123'
        
        # Store encrypted data with integrity hash
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            encryption_algorithm='fernet',
            include_integrity_hash=True
        )
        
        # Verify integrity
        is_integrity_valid = self.secure_storage.verify_data_integrity(data_id)
        self.assertTrue(is_integrity_valid)
        
        # Retrieve data (should pass integrity check)
        retrieved_data = self.secure_storage.retrieve_encrypted_data(data_id)
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_encryption_at_rest(self):
        """Test encryption at rest"""
        data_id = 'encryption_at_rest_123'
        
        # Store data with encryption at rest
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            encryption_algorithm='aes_gcm',
            encryption_at_rest=True
        )
        
        # Retrieve data
        retrieved_data = self.secure_storage.retrieve_encrypted_data(data_id)
        
        self.assertEqual(retrieved_data, self.test_data)
        
        # Verify data is encrypted in storage (implementation-specific check)
        storage_info = self.secure_storage.get_storage_info(data_id)
        self.assertTrue(storage_info['is_encrypted'])
        self.assertEqual(storage_info['encryption_algorithm'], 'aes_gcm')
    
    def test_access_control(self):
        """Test access control for stored data"""
        data_id = 'access_control_123'
        
        # Store data with access restrictions
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            allowed_users=[self.admin_user.pk],
            access_level='admin'
        )
        
        # Admin user should have access
        admin_data = self.secure_storage.retrieve_encrypted_data(
            data_id,
            user_id=self.admin_user.pk
        )
        self.assertEqual(admin_data, self.test_data)
        
        # Regular user should be denied access
        with self.assertRaises(PermissionError):
            self.secure_storage.retrieve_encrypted_data(
                data_id,
                user_id=self.regular_user.pk
            )
    
    def test_audit_logging(self):
        """Test audit logging for storage operations"""
        data_id = 'audit_test_123'
        
        # Store data
        self.secure_storage.store_encrypted_data(
            data_id,
            self.test_data,
            audit_log=True
        )
        
        # Retrieve data
        self.secure_storage.retrieve_encrypted_data(
            data_id,
            audit_log=True
        )
        
        # Check audit logs
        audit_logs = self.secure_storage.get_audit_logs(data_id)
        
        self.assertEqual(len(audit_logs), 2)  # Store and retrieve operations
        self.assertEqual(audit_logs[0]['operation'], 'store')
        self.assertEqual(audit_logs[1]['operation'], 'retrieve')
        
        # Verify timestamps are present
        for log in audit_logs:
            self.assertIn('timestamp', log)
            self.assertIn('user_id', log)


class EncryptionIntegrationTest(BaseEncryptionTest):
    """Integration tests for encryption functionality"""
    
    def test_end_to_end_encryption_workflow(self):
        """Test complete encryption workflow"""
        # Step 1: Generate encryption key
        key_manager = KeyManagement()
        key_id = 'workflow_key_123'
        encryption_key = key_manager.generate_key('fernet')
        key_manager.store_key(key_id, encryption_key)
        
        # Step 2: Encrypt sensitive fraud data
        fraud_data = {
            'user_id': self.regular_user.pk,
            'fraud_score': 92,
            'evidence': {
                'ip_address': '192.168.1.100',
                'device_fingerprint': 'abc123def456',
                'sensitive_info': 'confidential_data_123'
            },
            'investigation_notes': 'Under investigation for account takeover'
        }
        
        encryption_service = FraudEncryptionService()
        encrypted_data = encryption_service.encrypt_data(fraud_data, key=encryption_key)
        
        # Step 3: Store encrypted data securely
        secure_storage = SecureStorage()
        storage_id = secure_storage.store_encrypted_data(
            'fraud_case_123',
            fraud_data,
            encryption_algorithm='fernet'
        )
        
        # Step 4: Retrieve and decrypt data
        retrieved_data = secure_storage.retrieve_encrypted_data(storage_id)
        decrypted_data = encryption_service.decrypt_data(encrypted_data, key=encryption_key)
        
        # Verify data integrity
        self.assertEqual(decrypted_data, fraud_data)
        self.assertEqual(retrieved_data, fraud_data)
        
        # Step 5: Clean up
        secure_storage.secure_delete(storage_id)
        key_manager.destroy_key(key_id)
    
    def test_multi_algorithm_encryption(self):
        """Test using multiple encryption algorithms"""
        data = self.test_data
        
        # Test with different algorithms
        algorithms = ['fernet', 'aes_gcm', 'chacha20_poly1305']
        encrypted_results = {}
        
        for algorithm in algorithms:
            encryption_service = FraudEncryptionService()
            
            if algorithm == 'fernet':
                key = Fernet.generate_key()
                encrypted_data = encryption_service.encrypt_data(data, key=key)
            elif algorithm == 'aes_gcm':
                key = os.urandom(32)
                iv = os.urandom(12)
                # For AES-GCM, we'd need to handle IV separately
                encrypted_data = encryption_service.encrypt_data(data, key=key)
            elif algorithm == 'chacha20_poly1305':
                key = os.urandom(32)
                encrypted_data = encryption_service.encrypt_data(data, key=key)
            
            encrypted_results[algorithm] = {
                'encrypted_data': encrypted_data,
                'key': key
            }
        
        # All should produce different encrypted results
        encrypted_values = [result['encrypted_data'] for result in encrypted_results.values()]
        self.assertEqual(len(set(encrypted_values)), len(encrypted_values))
        
        # All should decrypt to the same original data
        for algorithm, result in encrypted_results.items():
            encryption_service = FraudEncryptionService()
            decrypted_data = encryption_service.decrypt_data(
                result['encrypted_data'],
                key=result['key']
            )
            self.assertEqual(decrypted_data, data)
    
    def test_encryption_performance_with_large_dataset(self):
        """Test encryption performance with large dataset"""
        # Generate large fraud dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'case_id': f'case_{i}',
                'user_id': self.regular_user.pk,
                'fraud_score': 50 + (i % 50),
                'evidence': {
                    'ip_address': f'192.168.1.{i % 255}',
                    'device_id': f'device_{i}',
                    'timestamp': timezone.now().isoformat(),
                    'detailed_analysis': {
                        'risk_factors': [f'factor_{j}' for j in range(10)],
                        'behavioral_patterns': [f'pattern_{k}' for k in range(5)],
                        'network_analysis': {
                            'connections': [f'conn_{m}' for m in range(20)],
                            'anomalies': [f'anomaly_{n}' for n in range(3)]
                        }
                    }
                }
            })
        
        # Measure batch encryption performance
        import time
        start_time = time.time()
        
        encryption_service = FraudEncryptionService()
        key = Fernet.generate_key()
        
        # Encrypt in batches
        batch_size = 100
        encrypted_batches = []
        
        for i in range(0, len(large_dataset), batch_size):
            batch = large_dataset[i:i + batch_size]
            encrypted_batch = encryption_service.encrypt_batch(batch, key=key)
            encrypted_batches.append(encrypted_batch)
        
        encryption_time = time.time() - start_time
        
        # Measure batch decryption performance
        start_time = time.time()
        
        decrypted_dataset = []
        for encrypted_batch in encrypted_batches:
            decrypted_batch = encryption_service.decrypt_batch(encrypted_batch, key=key)
            decrypted_dataset.extend(decrypted_batch)
        
        decryption_time = time.time() - start_time
        
        # Verify data integrity
        self.assertEqual(len(decrypted_dataset), len(large_dataset))
        for original, decrypted in zip(large_dataset, decrypted_dataset):
            self.assertEqual(original, decrypted)
        
        # Performance should be reasonable
        self.assertLess(encryption_time, 5.0)  # Less than 5 seconds for 1000 records
        self.assertLess(decryption_time, 5.0)  # Less than 5 seconds for 1000 records
