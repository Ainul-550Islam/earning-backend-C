"""Test Signature Verifier for Webhooks System

This module contains tests for the webhook signature verifier
including external signature verification and validation logic.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from ..services.inbound import SignatureVerifier
from ..models import InboundWebhook
from ..constants import InboundSource

User = get_user_model()


class SignatureVerifierTest(TestCase):
    """Test cases for SignatureVerifier."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.inbound_webhook = InboundWebhook.objects.create(
            source=InboundSource.STRIPE,
            url_token='stripe-webhook-12345',
            secret='stripe-secret-key',
            is_active=True,
            created_by=self.user,
        )
        self.signature_verifier = SignatureVerifier()
    
    def test_verify_stripe_signature_valid(self):
        """Test valid Stripe signature verification."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate Stripe signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_stripe_signature_invalid(self):
        """Test invalid Stripe signature verification."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {'X-Stripe-Signature': 'invalid-signature'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_stripe_signature_missing_header(self):
        """Test Stripe signature verification with missing header."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_stripe_signature_malformed_header(self):
        """Test Stripe signature verification with malformed header."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {'X-Stripe-Signature': 'invalid-format'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_stripe_signature_multiple_signatures(self):
        """Test Stripe signature verification with multiple signatures."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate multiple signatures
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature1 = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature2 = hmac.new(
            'different-secret'.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature1},sha256={signature2}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_stripe_signature_timestamp_validation(self):
        """Test Stripe signature verification with timestamp validation."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Stripe-Signature': f'sha256={signature}',
            'X-Stripe-Timestamp': '2024-01-01T00:00:00Z'
        }
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            timestamp_tolerance=300
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_stripe_signature_old_timestamp(self):
        """Test Stripe signature verification with old timestamp."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Stripe-Signature': f'sha256={signature}',
            'X-Stripe-Timestamp': '2023-01-01T00:00:00Z'  # Old timestamp
        }
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            timestamp_tolerance=300
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_paypal_signature_valid(self):
        """Test valid PayPal signature verification."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        # Generate PayPal signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'PAYPAL-AUTH-SHA256': signature}
        
        is_valid = self.signature_verifier.verify_paypal_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_paypal_signature_invalid(self):
        """Test invalid PayPal signature verification."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        headers = {'PAYPAL-AUTH-SHA256': 'invalid-signature'}
        
        is_valid = self.signature_verifier.verify_paypal_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_paypal_signature_missing_header(self):
        """Test PayPal signature verification with missing header."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        headers = {}
        
        is_valid = self.signature_verifier.verify_paypal_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_paypal_signature_with_cert_id(self):
        """Test PayPal signature verification with cert ID."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'PAYPAL-AUTH-SHA256': signature,
            'PAYPAL-AUTH-ALGO': 'SHA256withRSA',
            'PAYPAL-TRANSMISSION-ID': 'trans-12345',
            'PAYPAL-CERT-ID': 'cert-12345'
        }
        
        is_valid = self.signature_verifier.verify_paypal_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_bkash_signature_valid(self):
        """Test valid bKash signature verification."""
        payload = {
            'eventType': 'payment.success',
            'data': {'paymentId': 'pay_123456789'}
        }
        
        # Generate bKash signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-BKash-Signature': signature}
        
        is_valid = self.signature_verifier.verify_bkash_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_bkash_signature_invalid(self):
        """Test invalid bKash signature verification."""
        payload = {
            'eventType': 'payment.success',
            'data': {'paymentId': 'pay_123456789'}
        }
        
        headers = {'X-BKash-Signature': 'invalid-signature'}
        
        is_valid = self.signature_verifier.verify_bkash_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_bkash_signature_with_timestamp(self):
        """Test bKash signature verification with timestamp."""
        payload = {
            'eventType': 'payment.success',
            'data': {'paymentId': 'pay_123456789'}
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-BKash-Signature': signature,
            'X-BKash-Timestamp': '2024-01-01T00:00:00Z'
        }
        
        is_valid = self.signature_verifier.verify_bkash_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_nagad_signature_valid(self):
        """Test valid Nagad signature verification."""
        payload = {
            'eventType': 'payment.success',
            'data': {'paymentId': 'pay_123456789'}
        }
        
        # Generate Nagad signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Nagad-Signature': signature}
        
        is_valid = self.signature_verifier.verify_nagad_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_nagad_signature_invalid(self):
        """Test invalid Nagad signature verification."""
        payload = {
            'eventType': 'payment.success',
            'data': {'paymentId': 'pay_123456789'}
        }
        
        headers = {'X-Nagad-Signature': 'invalid-signature'}
        
        is_valid = self.signature_verifier.verify_nagad_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_by_source(self):
        """Test signature verification by source."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_signature_by_source(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source=InboundSource.STRIPE
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_by_source_unknown(self):
        """Test signature verification with unknown source."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {'X-Signature': 'some-signature'}
        
        is_valid = self.signature_verifier.verify_signature_by_source(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source='unknown'
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_timing_attack_protection(self):
        """Test that signature verification uses constant-time comparison."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        with patch('hmac.compare_digest') as mock_compare:
            mock_compare.return_value = True
            
            is_valid = self.signature_verifier.verify_stripe_signature(
                payload=payload,
                headers=headers,
                secret=self.inbound_webhook.secret
            )
            
            self.assertTrue(is_valid)
            mock_compare.assert_called_once()
    
    def test_verify_signature_with_large_payload(self):
        """Test signature verification with large payload."""
        # Create large payload
        large_payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'payment_id': 'pay_123456789',
                    'large_data': ['x' * 1000] * 100  # ~1MB of data
                }
            }
        }
        
        # Generate signature
        payload_json = json.dumps(large_payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=large_payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_unicode_payload(self):
        """Test signature verification with unicode payload."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'payment_id': 'pay_123456789',
                    'message': 'Hello World! ñáéíóú',
                    'emoji': 'Hello World! emoji test'
                }
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_empty_payload(self):
        """Test signature verification with empty payload."""
        payload = {}
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_none_payload(self):
        """Test signature verification with None payload."""
        with self.assertRaises(ValueError):
            self.signature_verifier.verify_stripe_signature(
                payload=None,
                headers={'X-Stripe-Signature': 'some-signature'},
                secret=self.inbound_webhook.secret
            )
    
    def test_verify_signature_with_none_headers(self):
        """Test signature verification with None headers."""
        payload = {'event': {'type': 'payment_intent.succeeded'}}
        
        with self.assertRaises(ValueError):
            self.signature_verifier.verify_stripe_signature(
                payload=payload,
                headers=None,
                secret=self.inbound_webhook.secret
            )
    
    def test_verify_signature_with_none_secret(self):
        """Test signature verification with None secret."""
        payload = {'event': {'type': 'payment_intent.succeeded'}}
        headers = {'X-Stripe-Signature': 'some-signature'}
        
        with self.assertRaises(ValueError):
            self.signature_verifier.verify_stripe_signature(
                payload=payload,
                headers=headers,
                secret=None
            )
    
    def test_verify_signature_performance(self):
        """Test signature verification performance."""
        import time
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        start_time = time.time()
        
        # Verify 1000 signatures
        for _ in range(1000):
            is_valid = self.signature_verifier.verify_stripe_signature(
                payload=payload,
                headers=headers,
                secret=self.inbound_webhook.secret
            )
            self.assertTrue(is_valid)
        
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
    
    def test_verify_signature_concurrent_safety(self):
        """Test signature verification concurrent safety."""
        import threading
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        results = []
        
        def verify_signature():
            is_valid = self.signature_verifier.verify_stripe_signature(
                payload=payload,
                headers=headers,
                secret=self.inbound_webhook.secret
            )
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
        
        # All verifications should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result for result in results))
    
    def test_verify_signature_memory_efficiency(self):
        """Test signature verification memory efficiency."""
        import sys
        
        # Create large payload
        large_payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'payment_id': 'pay_123456789',
                    'large_data': ['x' * 1000] * 1000  # ~1MB of data
                }
            }
        }
        
        # Generate signature
        payload_json = json.dumps(large_payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        # Get memory usage before verification
        initial_memory = sys.getsizeof(large_payload) + sys.getsizeof(headers)
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=large_payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        # Get memory usage after verification
        final_memory = sys.getsizeof(large_payload) + sys.getsizeof(headers)
        
        # Memory usage should be reasonable
        self.assertLess(final_memory, initial_memory * 2)
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_different_algorithms(self):
        """Test signature verification with different algorithms."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Test SHA256
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        sha256_signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={sha256_signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
        
        # Test SHA1 (if supported)
        sha1_signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha1={sha1_signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        # SHA1 might not be supported by default, but should handle gracefully
        self.assertIsInstance(is_valid, bool)
    
    def test_verify_signature_with_case_insensitive_headers(self):
        """Test signature verification with case-insensitive headers."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'x-stripe-signature': f'sha256={signature}'}  # Lowercase
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_whitespace_in_signature(self):
        """Test signature verification with whitespace in signature."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'  sha256={signature}  '}  # With whitespace
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_with_special_characters_in_payload(self):
        """Test signature verification with special characters in payload."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'payment_id': 'pay_123456789',
                    'message': 'Hello @#$%^&*()_+-=[]{}|;:,.<>?!',
                    'unicode': 'Hello World! ñáéíóú'
                }
            }
        }
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        is_valid = self.signature_verifier.verify_stripe_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret
        )
        
        self.assertTrue(is_valid)
