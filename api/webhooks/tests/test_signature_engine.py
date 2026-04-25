"""Test Signature Engine for Webhooks System

This module contains tests for the webhook signature engine
including HMAC signature generation and verification.
"""

import pytest
import hmac
import hashlib
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone

from ..services.core import SignatureEngine
from ..models import WebhookEndpoint


class SignatureEngineTest(TestCase):
    """Test cases for SignatureEngine."""
    
    def setUp(self):
        """Set up test data."""
        self.signature_engine = SignatureEngine()
        self.secret = 'test-secret-key-12345'
        self.payload = {
            'user_id': 12345,
            'email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z'
        }
    
    def test_sign_payload_basic(self):
        """Test basic payload signing."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 hex length
        self.assertTrue(all(c in '0123456789abcdef' for c in signature.lower()))
    
    def test_sign_payload_consistency(self):
        """Test that signing the same payload produces the same signature."""
        signature1 = self.signature_engine.sign(self.payload, self.secret)
        signature2 = self.signature_engine.sign(self.payload, self.secret)
        
        self.assertEqual(signature1, signature2)
    
    def test_sign_payload_different_secrets(self):
        """Test that different secrets produce different signatures."""
        signature1 = self.signature_engine.sign(self.payload, self.secret)
        signature2 = self.signature_engine.sign(self.payload, 'different-secret')
        
        self.assertNotEqual(signature1, signature2)
    
    def test_sign_payload_different_payloads(self):
        """Test that different payloads produce different signatures."""
        signature1 = self.signature_engine.sign(self.payload, self.secret)
        signature2 = self.signature_engine.sign({'user_id': 54321}, self.secret)
        
        self.assertNotEqual(signature1, signature2)
    
    def test_sign_payload_empty_dict(self):
        """Test signing an empty payload."""
        signature = self.signature_engine.sign({}, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_nested_dict(self):
        """Test signing a nested payload."""
        nested_payload = {
            'user': {
                'id': 12345,
                'profile': {
                    'name': 'Test User',
                    'settings': {
                        'notifications': True
                    }
                }
            }
        }
        
        signature = self.signature_engine.sign(nested_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_with_special_characters(self):
        """Test signing payload with special characters."""
        special_payload = {
            'message': 'Hello World! @#$%^&*()_+-=[]{}|;:,.<>?',
            'unicode': 'Hello World! ñáéíóú',
            'emoji': 'Hello World! emoji test'
        }
        
        signature = self.signature_engine.sign(special_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        is_valid = self.signature_engine.verify(self.payload, signature, self.secret)
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        invalid_signature = signature[:-1] + '0'  # Change last character
        
        is_valid = self.signature_engine.verify(self.payload, invalid_signature, self.secret)
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_wrong_secret(self):
        """Test signature verification with wrong secret."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        wrong_secret = 'wrong-secret-key'
        
        is_valid = self.signature_engine.verify(self.payload, signature, wrong_secret)
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_wrong_payload(self):
        """Test signature verification with wrong payload."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        wrong_payload = {'user_id': 54321}
        
        is_valid = self.signature_engine.verify(wrong_payload, signature, self.secret)
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_empty_payload(self):
        """Test signature verification with empty payload."""
        signature = self.signature_engine.sign({}, self.secret)
        
        is_valid = self.signature_engine.verify({}, signature, self.secret)
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_timing_attack_protection(self):
        """Test that signature verification uses constant-time comparison."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        # This test ensures we're using hmac.compare_digest for timing attack protection
        with patch('hmac.compare_digest') as mock_compare:
            mock_compare.return_value = True
            
            self.signature_engine.verify(self.payload, signature, self.secret)
            
            mock_compare.assert_called_once()
    
    def test_generate_webhook_headers(self):
        """Test webhook header generation."""
        headers = self.signature_engine.generate_headers(self.payload, self.secret)
        
        self.assertIn('X-Webhook-Signature', headers)
        self.assertIn('X-Webhook-Timestamp', headers)
        self.assertIn('Content-Type', headers)
        self.assertIn('User-Agent', headers)
        
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['User-Agent'], 'Webhooks-Client/1.0')
        self.assertIsInstance(headers['X-Webhook-Timestamp'], str)
        self.assertIsInstance(headers['X-Webhook-Signature'], str)
    
    def test_verify_webhook_headers_valid(self):
        """Test webhook header verification with valid headers."""
        headers = self.signature_engine.generate_headers(self.payload, self.secret)
        
        is_valid = self.signature_engine.verify_webhook_headers(
            self.payload,
            headers,
            self.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_webhook_headers_invalid_signature(self):
        """Test webhook header verification with invalid signature."""
        headers = self.signature_engine.generate_headers(self.payload, self.secret)
        headers['X-Webhook-Signature'] = 'invalid-signature'
        
        is_valid = self.signature_engine.verify_webhook_headers(
            self.payload,
            headers,
            self.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_webhook_headers_missing_signature(self):
        """Test webhook header verification with missing signature."""
        headers = {
            'X-Webhook-Timestamp': '2024-01-01T00:00:00Z',
            'Content-Type': 'application/json'
        }
        
        is_valid = self.signature_engine.verify_webhook_headers(
            self.payload,
            headers,
            self.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_webhook_headers_missing_timestamp(self):
        """Test webhook header verification with missing timestamp."""
        headers = {
            'X-Webhook-Signature': 'some-signature',
            'Content-Type': 'application/json'
        }
        
        is_valid = self.signature_engine.verify_webhook_headers(
            self.payload,
            headers,
            self.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_webhook_headers_old_timestamp(self):
        """Test webhook header verification with old timestamp."""
        headers = self.signature_engine.generate_headers(self.payload, self.secret)
        # Set timestamp to 10 minutes ago
        headers['X-Webhook-Timestamp'] = '2023-12-31T23:50:00Z'
        
        is_valid = self.signature_engine.verify_webhook_headers(
            self.payload,
            headers,
            self.secret,
            max_age_seconds=300  # 5 minutes
        )
        
        self.assertFalse(is_valid)
    
    def test_get_signature_algorithm(self):
        """Test getting signature algorithm."""
        algorithm = self.signature_engine.get_algorithm()
        
        self.assertEqual(algorithm, 'sha256')
    
    def test_sign_with_different_algorithm(self):
        """Test signing with different algorithm."""
        # Create signature engine with SHA1
        sha1_engine = SignatureEngine(algorithm='sha1')
        
        signature = sha1_engine.sign(self.payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 40)  # SHA1 hex length
    
    def test_sign_with_sha256_algorithm(self):
        """Test signing with SHA256 algorithm."""
        sha256_engine = SignatureEngine(algorithm='sha256')
        
        signature = sha256_engine.sign(self.payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 hex length
    
    def test_sign_with_invalid_algorithm(self):
        """Test signing with invalid algorithm."""
        with self.assertRaises(ValueError):
            SignatureEngine(algorithm='invalid_algorithm')
    
    def test_sign_payload_with_bytes(self):
        """Test signing with bytes payload."""
        import json
        payload_bytes = json.dumps(self.payload).encode('utf-8')
        
        signature = self.signature_engine.sign(payload_bytes, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_with_string(self):
        """Test signing with string payload."""
        import json
        payload_string = json.dumps(self.payload)
        
        signature = self.signature_engine.sign(payload_string, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_unicode_handling(self):
        """Test unicode handling in payload signing."""
        unicode_payload = {
            'message': 'Hello World! ñáéíóú',
            'emoji': 'Hello World! emoji test'
        }
        
        signature = self.signature_engine.sign(unicode_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_large_payload(self):
        """Test signing with large payload."""
        large_payload = {
            'data': ['item'] * 1000,  # Large list
            'nested': {
                'level1': {
                    'level2': {
                        'level3': 'deeply nested data'
                    }
                }
            }
        }
        
        signature = self.signature_engine.sign(large_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_none_values(self):
        """Test signing payload with None values."""
        payload_with_none = {
            'user_id': 12345,
            'email': None,
            'profile': None
        }
        
        signature = self.signature_engine.sign(payload_with_none, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_numeric_values(self):
        """Test signing payload with different numeric types."""
        numeric_payload = {
            'integer': 12345,
            'float': 123.45,
            'boolean': True,
            'zero': 0,
            'negative': -123
        }
        
        signature = self.signature_engine.sign(numeric_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_list_values(self):
        """Test signing payload with list values."""
        list_payload = {
            'tags': ['tag1', 'tag2', 'tag3'],
            'numbers': [1, 2, 3, 4, 5],
            'mixed': ['string', 123, True, None]
        }
        
        signature = self.signature_engine.sign(list_payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_order_independence(self):
        """Test that payload order doesn't affect signature."""
        payload1 = {'a': 1, 'b': 2, 'c': 3}
        payload2 = {'c': 3, 'b': 2, 'a': 1}
        
        signature1 = self.signature_engine.sign(payload1, self.secret)
        signature2 = self.signature_engine.sign(payload2, self.secret)
        
        self.assertEqual(signature1, signature2)
    
    def test_sign_payload_with_endpoint(self):
        """Test signing with webhook endpoint."""
        endpoint = WebhookEndpoint(
            url='https://example.com/webhook',
            secret=self.secret
        )
        
        signature = self.signature_engine.sign_with_endpoint(self.payload, endpoint)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_verify_signature_with_endpoint(self):
        """Test signature verification with webhook endpoint."""
        endpoint = WebhookEndpoint(
            url='https://example.com/webhook',
            secret=self.secret
        )
        
        signature = self.signature_engine.sign_with_endpoint(self.payload, endpoint)
        
        is_valid = self.signature_engine.verify_with_endpoint(
            self.payload,
            signature,
            endpoint
        )
        
        self.assertTrue(is_valid)
    
    def test_sign_payload_with_endpoint_no_secret(self):
        """Test signing with endpoint that has no secret."""
        endpoint = WebhookEndpoint(
            url='https://example.com/webhook'
        )
        
        with self.assertRaises(ValueError):
            self.signature_engine.sign_with_endpoint(self.payload, endpoint)
    
    def test_verify_signature_with_endpoint_no_secret(self):
        """Test signature verification with endpoint that has no secret."""
        endpoint = WebhookEndpoint(
            url='https://example.com/webhook'
        )
        
        with self.assertRaises(ValueError):
            self.signature_engine.verify_with_endpoint(
                self.payload,
                'some-signature',
                endpoint
            )
    
    def test_sign_payload_with_custom_hashlib(self):
        """Test signing with custom hashlib function."""
        custom_engine = SignatureEngine(hashlib_func=hashlib.sha256)
        
        signature = custom_engine.sign(self.payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_sign_payload_performance(self):
        """Test signing performance with large payload."""
        import time
        
        large_payload = {
            'data': ['item'] * 10000
        }
        
        start_time = time.time()
        signature = self.signature_engine.sign(large_payload, self.secret)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
    
    def test_verify_signature_performance(self):
        """Test verification performance."""
        import time
        
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        start_time = time.time()
        is_valid = self.signature_engine.verify(self.payload, signature, self.secret)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 0.1 seconds)
        self.assertLess(end_time - start_time, 0.1)
        self.assertTrue(is_valid)
    
    def test_sign_payload_concurrent_safety(self):
        """Test that signing is thread-safe."""
        import threading
        
        results = []
        
        def sign_payload():
            signature = self.signature_engine.sign(self.payload, self.secret)
            results.append(signature)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=sign_payload)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All signatures should be identical
        self.assertEqual(len(results), 10)
        self.assertTrue(all(sig == results[0] for sig in results))
    
    def test_verify_signature_concurrent_safety(self):
        """Test that verification is thread-safe."""
        import threading
        
        signature = self.signature_engine.sign(self.payload, self.secret)
        results = []
        
        def verify_signature():
            is_valid = self.signature_engine.verify(self.payload, signature, self.secret)
            results.append(is_valid)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=verify_signature)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All verifications should be True
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result for result in results))
    
    def test_sign_payload_memory_efficiency(self):
        """Test memory efficiency with large payloads."""
        import sys
        
        # Create a large payload
        large_payload = {
            'data': ['x' * 1000] * 1000  # ~1MB of data
        }
        
        # Get memory usage before signing
        initial_memory = sys.getsizeof(large_payload)
        
        # Sign the payload
        signature = self.signature_engine.sign(large_payload, self.secret)
        
        # Get memory usage after signing
        final_memory = sys.getsizeof(large_payload) + sys.getsizeof(signature)
        
        # Memory usage should be reasonable
        self.assertLess(final_memory, initial_memory * 2)
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)
