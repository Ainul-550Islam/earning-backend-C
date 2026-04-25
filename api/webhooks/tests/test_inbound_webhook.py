"""Test Inbound Webhook for Webhooks System

This module contains tests for the inbound webhook receiver
including signature verification, payload parsing, and event routing.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..services.inbound import InboundWebhookService, SignatureVerifier, PayloadParser, InboundEventRouter
from ..models import (
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
)
from ..constants import InboundSource, ErrorType

User = get_user_model()


class InboundWebhookServiceTest(TestCase):
    """Test cases for InboundWebhookService."""
    
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
        self.inbound_service = InboundWebhookService()
    
    def test_process_inbound_webhook_success(self):
        """Test successful inbound webhook processing."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'payment_id': 'pay_123456789',
                    'amount': 100.00,
                    'currency': 'USD'
                }
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret),
            'X-Stripe-Idempotency-Key': 'test-key-12345'
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result['success'])
            self.assertEqual(result['event_type'], 'payment_intent.succeeded')
            mock_route.assert_called_once()
    
    def test_process_inbound_webhook_invalid_signature(self):
        """Test inbound webhook processing with invalid signature."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': 'invalid-signature'
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Invalid signature')
    
    def test_process_inbound_webhook_no_signature(self):
        """Test inbound webhook processing with no signature."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Missing signature')
    
    def test_process_inbound_webhook_inactive_webhook(self):
        """Test inbound webhook processing with inactive webhook."""
        inactive_webhook = InboundWebhook.objects.create(
            source=InboundSource.STRIPE,
            url_token='stripe-webhook-67890',
            secret='stripe-secret-key',
            is_active=False,
            created_by=self.user,
        )
        
        payload = {'event': {'type': 'payment_intent.succeeded'}}
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, inactive_webhook.secret)
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=inactive_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Webhook is inactive')
    
    def test_process_inbound_webhook_invalid_json(self):
        """Test inbound webhook processing with invalid JSON."""
        payload = 'invalid json'
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature({'test': 'data'}, self.inbound_webhook.secret)
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Invalid JSON payload')
    
    def test_process_inbound_webhook_no_event_type(self):
        """Test inbound webhook processing with no event type."""
        payload = {'data': {'payment_id': 'pay_123456789'}}
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Missing event type')
    
    def test_process_inbound_webhook_creates_log(self):
        """Test that inbound webhook processing creates log."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            # Check that log was created
            log = InboundWebhookLog.objects.get(inbound=self.inbound_webhook)
            self.assertEqual(log.raw_payload, payload)
            self.assertEqual(log.headers, headers)
            self.assertEqual(log.ip_address, '192.168.1.1')
            self.assertTrue(log.signature_valid)
            self.assertTrue(log.processed)
    
    def test_process_inbound_webhook_creates_error_log(self):
        """Test that inbound webhook processing creates error log on failure."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': 'invalid-signature'
        }
        
        self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        # Check that log and error were created
        log = InboundWebhookLog.objects.get(inbound=self.inbound_webhook)
        self.assertFalse(log.signature_valid)
        self.assertFalse(log.processed)
        
        error = InboundWebhookError.objects.get(log=log)
        self.assertEqual(error.error_type, ErrorType.AUTHENTICATION_ERROR)
        self.assertIn('Invalid signature', error.error_message)
    
    def test_process_inbound_webhook_with_routing(self):
        """Test inbound webhook processing with event routing."""
        # Create route
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment_intent.*',
            handler_function='handle_payment_intent',
            is_active=True
        )
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result['success'])
            mock_route.assert_called_once()
    
    def test_process_inbound_webhook_no_matching_route(self):
        """Test inbound webhook processing with no matching route."""
        payload = {
            'event': {
                'type': 'unknown.event',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No matching route found')
    
    def test_process_inbound_webhook_with_timestamp_validation(self):
        """Test inbound webhook processing with timestamp validation."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret),
            'X-Stripe-Timestamp': '2024-01-01T00:00:00Z'
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1',
                max_age_seconds=300
            )
            
            self.assertTrue(result['success'])
    
    def test_process_inbound_webhook_with_old_timestamp(self):
        """Test inbound webhook processing with old timestamp."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret),
            'X-Stripe-Timestamp': '2023-01-01T00:00:00Z'  # Old timestamp
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=self.inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.1',
            max_age_seconds=300
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Timestamp too old')
    
    def test_process_inbound_webhook_with_ip_whitelist_allowed(self):
        """Test inbound webhook processing with allowed IP."""
        inbound_webhook = InboundWebhook.objects.create(
            source=InboundSource.STRIPE,
            url_token='stripe-webhook-whitelist',
            secret='stripe-secret-key',
            is_active=True,
            created_by=self.user,
        )
        
        # Add IP whitelist (this would be stored elsewhere in a real implementation)
        allowed_ips = ['192.168.1.1', '10.0.0.1']
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1',
                allowed_ips=allowed_ips
            )
            
            self.assertTrue(result['success'])
    
    def test_process_inbound_webhook_with_ip_whitelist_blocked(self):
        """Test inbound webhook processing with blocked IP."""
        inbound_webhook = InboundWebhook.objects.create(
            source=InboundSource.STRIPE,
            url_token='stripe-webhook-blocked',
            secret='stripe-secret-key',
            is_active=True,
            created_by=self.user,
        )
        
        # Add IP whitelist (this would be stored elsewhere in a real implementation)
        allowed_ips = ['192.168.1.1', '10.0.0.1']
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, inbound_webhook.secret)
        }
        
        result = self.inbound_service.process_inbound_webhook(
            inbound=inbound_webhook,
            payload=payload,
            headers=headers,
            ip_address='192.168.1.2',  # Not in whitelist
            allowed_ips=allowed_ips
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'IP address not allowed')
    
    def test_process_inbound_webhook_with_duplicate_event(self):
        """Test inbound webhook processing with duplicate event."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret),
            'X-Stripe-Idempotency-Key': 'duplicate-key-12345'
        }
        
        # First processing
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result1 = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result1['success'])
        
        # Second processing (should be detected as duplicate)
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            result2 = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertFalse(result2['success'])
            self.assertEqual(result2['error'], 'Duplicate event')
    
    def test_process_inbound_webhook_with_large_payload(self):
        """Test inbound webhook processing with large payload."""
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
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(large_payload, self.inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=large_payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result['success'])
    
    def test_process_inbound_webhook_with_unicode_payload(self):
        """Test inbound webhook processing with unicode payload."""
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
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            result = self.inbound_service.process_inbound_webhook(
                inbound=self.inbound_webhook,
                payload=payload,
                headers=headers,
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result['success'])
    
    def test_process_inbound_webhook_performance(self):
        """Test inbound webhook processing performance."""
        import time
        
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Stripe-Signature': self._generate_signature(payload, self.inbound_webhook.secret)
        }
        
        with patch('api.webhooks.services.inbound.InboundEventRouter.route_event') as mock_route:
            mock_route.return_value = True
            
            start_time = time.time()
            
            # Process 100 webhooks
            for i in range(100):
                result = self.inbound_service.process_inbound_webhook(
                    inbound=self.inbound_webhook,
                    payload=payload,
                    headers=headers,
                    ip_address='192.168.1.1'
                )
                self.assertTrue(result['success'])
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 5 seconds)
            self.assertLess(end_time - start_time, 5.0)
    
    def _generate_signature(self, payload, secret):
        """Generate HMAC signature for testing."""
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f'sha256={signature}'


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
    
    def test_verify_signature_stripe(self):
        """Test Stripe signature verification."""
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
        
        is_valid = self.signature_verifier.verify_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source=InboundSource.STRIPE
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_paypal(self):
        """Test PayPal signature verification."""
        payload = {
            'event': {
                'type': 'PAYMENT.SALE.COMPLETED',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        # Generate PayPal signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'PAYPAL-AUTH-SHA256': signature}
        
        is_valid = self.signature_verifier.verify_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source=InboundSource.PAYPAL
        )
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_invalid(self):
        """Test invalid signature verification."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {'X-Stripe-Signature': 'invalid-signature'}
        
        is_valid = self.signature_verifier.verify_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source=InboundSource.STRIPE
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_missing_header(self):
        """Test signature verification with missing header."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {}
        
        is_valid = self.signature_verifier.verify_signature(
            payload=payload,
            headers=headers,
            secret=self.inbound_webhook.secret,
            source=InboundSource.STRIPE
        )
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_unknown_source(self):
        """Test signature verification with unknown source."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        headers = {'X-Signature': 'some-signature'}
        
        is_valid = self.signature_verifier.verify_signature(
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
        
        # Generate valid signature
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.inbound_webhook.secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Stripe-Signature': f'sha256={signature}'}
        
        with patch('hmac.compare_digest') as mock_compare:
            mock_compare.return_value = True
            
            is_valid = self.signature_verifier.verify_signature(
                payload=payload,
                headers=headers,
                secret=self.inbound_webhook.secret,
                source=InboundSource.STRIPE
            )
            
            self.assertTrue(is_valid)
            mock_compare.assert_called_once()


class PayloadParserTest(TestCase):
    """Test cases for PayloadParser."""
    
    def setUp(self):
        """Set up test data."""
        self.payload_parser = PayloadParser()
    
    def test_parse_payload_valid_json(self):
        """Test parsing valid JSON payload."""
        payload_str = '{"event": {"type": "payment_intent.succeeded"}}'
        
        parsed = self.payload_parser.parse_payload(payload_str)
        
        self.assertEqual(parsed['event']['type'], 'payment_intent.succeeded')
    
    def test_parse_payload_invalid_json(self):
        """Test parsing invalid JSON payload."""
        payload_str = 'invalid json'
        
        with self.assertRaises(ValueError):
            self.payload_parser.parse_payload(payload_str)
    
    def test_parse_payload_empty_string(self):
        """Test parsing empty string payload."""
        payload_str = ''
        
        with self.assertRaises(ValueError):
            self.payload_parser.parse_payload(payload_str)
    
    def test_parse_payload_none(self):
        """Test parsing None payload."""
        with self.assertRaises(ValueError):
            self.payload_parser.parse_payload(None)
    
    def test_extract_event_type_stripe(self):
        """Test extracting event type from Stripe payload."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        event_type = self.payload_parser.extract_event_type(payload, InboundSource.STRIPE)
        
        self.assertEqual(event_type, 'payment_intent.succeeded')
    
    def test_extract_event_type_paypal(self):
        """Test extracting event type from PayPal payload."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        event_type = self.payload_parser.extract_event_type(payload, InboundSource.PAYPAL)
        
        self.assertEqual(event_type, 'PAYMENT.SALE.COMPLETED')
    
    def test_extract_event_type_missing(self):
        """Test extracting event type with missing field."""
        payload = {'data': {'payment_id': 'pay_123456789'}}
        
        with self.assertRaises(ValueError):
            self.payload_parser.extract_event_type(payload, InboundSource.STRIPE)
    
    def test_extract_event_type_unknown_source(self):
        """Test extracting event type from unknown source."""
        payload = {'event': {'type': 'payment_intent.succeeded'}}
        
        with self.assertRaises(ValueError):
            self.payload_parser.extract_event_type(payload, 'unknown')
    
    def test_validate_payload_structure_stripe(self):
        """Test validating Stripe payload structure."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        is_valid = self.payload_parser.validate_payload_structure(payload, InboundSource.STRIPE)
        
        self.assertTrue(is_valid)
    
    def test_validate_payload_structure_invalid_stripe(self):
        """Test validating invalid Stripe payload structure."""
        payload = {'data': {'payment_id': 'pay_123456789'}}
        
        is_valid = self.payload_parser.validate_payload_structure(payload, InboundSource.STRIPE)
        
        self.assertFalse(is_valid)
    
    def test_validate_payload_structure_paypal(self):
        """Test validating PayPal payload structure."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        is_valid = self.payload_parser.validate_payload_structure(payload, InboundSource.PAYPAL)
        
        self.assertTrue(is_valid)
    
    def test_validate_payload_structure_invalid_paypal(self):
        """Test validating invalid PayPal payload structure."""
        payload = {'event_type': 'PAYMENT.SALE.COMPLETED'}
        
        is_valid = self.payload_parser.validate_payload_structure(payload, InboundSource.PAYPAL)
        
        self.assertFalse(is_valid)
    
    def test_normalize_payload_stripe(self):
        """Test normalizing Stripe payload."""
        payload = {
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {'payment_id': 'pay_123456789'}
            }
        }
        
        normalized = self.payload_parser.normalize_payload(payload, InboundSource.STRIPE)
        
        self.assertEqual(normalized['event_type'], 'payment_intent.succeeded')
        self.assertEqual(normalized['data'], {'payment_id': 'pay_123456789'})
    
    def test_normalize_payload_paypal(self):
        """Test normalizing PayPal payload."""
        payload = {
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'pay_123456789'}
        }
        
        normalized = self.payload_parser.normalize_payload(payload, InboundSource.PAYPAL)
        
        self.assertEqual(normalized['event_type'], 'PAYMENT.SALE.COMPLETED')
        self.assertEqual(normalized['data'], {'id': 'pay_123456789'})


class InboundEventRouterTest(TestCase):
    """Test cases for InboundEventRouter."""
    
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
        self.event_router = InboundEventRouter()
    
    def test_route_event_success(self):
        """Test successful event routing."""
        # Create route
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment_intent.*',
            handler_function='handle_payment_intent',
            is_active=True
        )
        
        event_data = {
            'event_type': 'payment_intent.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        with patch('api.webhooks.handlers.handle_payment_intent') as mock_handler:
            mock_handler.return_value = True
            
            result = self.event_router.route_event(event_data)
            
            self.assertTrue(result)
            mock_handler.assert_called_once_with(event_data)
    
    def test_route_event_no_matching_route(self):
        """Test event routing with no matching route."""
        event_data = {
            'event_type': 'unknown.event',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        result = self.event_router.route_event(event_data)
        
        self.assertFalse(result)
    
    def test_route_event_inactive_route(self):
        """Test event routing with inactive route."""
        # Create inactive route
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment_intent.*',
            handler_function='handle_payment_intent',
            is_active=False
        )
        
        event_data = {
            'event_type': 'payment_intent.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        result = self.event_router.route_event(event_data)
        
        self.assertFalse(result)
    
    def test_route_event_handler_exception(self):
        """Test event routing with handler exception."""
        # Create route
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment_intent.*',
            handler_function='handle_payment_intent',
            is_active=True
        )
        
        event_data = {
            'event_type': 'payment_intent.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        with patch('api.webhooks.handlers.handle_payment_intent') as mock_handler:
            mock_handler.side_effect = Exception('Handler error')
            
            result = self.event_router.route_event(event_data)
            
            self.assertFalse(result)
    
    def test_route_event_multiple_matching_routes(self):
        """Test event routing with multiple matching routes."""
        # Create multiple routes
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment_intent.*',
            handler_function='handle_payment_intent',
            is_active=True
        )
        
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern='payment.*',
            handler_function='handle_payment',
            is_active=True
        )
        
        event_data = {
            'event_type': 'payment_intent.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        with patch('api.webhooks.handlers.handle_payment_intent') as mock_handler1, \
             patch('api.webhooks.handlers.handle_payment') as mock_handler2:
            
            mock_handler1.return_value = True
            mock_handler2.return_value = True
            
            result = self.event_router.route_event(event_data)
            
            self.assertTrue(result)
            # Should call the most specific route
            mock_handler1.assert_called_once()
            mock_handler2.assert_not_called()
    
    def test_route_event_with_regex_pattern(self):
        """Test event routing with regex pattern."""
        # Create route with regex pattern
        InboundWebhookRoute.objects.create(
            inbound=self.inbound_webhook,
            event_pattern=r'^payment_intent\.(succeeded|failed)$',
            handler_function='handle_payment_intent',
            is_active=True
        )
        
        # Test matching pattern
        event_data = {
            'event_type': 'payment_intent.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        with patch('api.webhooks.handlers.handle_payment_intent') as mock_handler:
            mock_handler.return_value = True
            
            result = self.event_router.route_event(event_data)
            
            self.assertTrue(result)
            mock_handler.assert_called_once()
        
        # Test non-matching pattern
        event_data = {
            'event_type': 'payment_intent.pending',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        result = self.event_router.route_event(event_data)
        
        self.assertFalse(result)
    
    def test_route_event_performance(self):
        """Test event routing performance."""
        import time
        
        # Create multiple routes
        for i in range(10):
            InboundWebhookRoute.objects.create(
                inbound=self.inbound_webhook,
                event_pattern=f'event_{i}.*',
                handler_function=f'handle_event_{i}',
                is_active=True
            )
        
        event_data = {
            'event_type': 'event_5.succeeded',
            'data': {'payment_id': 'pay_123456789'}
        }
        
        with patch('api.webhooks.handlers.handle_event_5') as mock_handler:
            mock_handler.return_value = True
            
            start_time = time.time()
            
            # Route 100 events
            for _ in range(100):
                result = self.event_router.route_event(event_data)
                self.assertTrue(result)
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 1 second)
            self.assertLess(end_time - start_time, 1.0)
            self.assertEqual(mock_handler.call_count, 100)
