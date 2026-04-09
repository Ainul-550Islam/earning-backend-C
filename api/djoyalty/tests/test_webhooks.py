# api/djoyalty/tests/test_webhooks.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer


class WebhookSecurityTest(TestCase):

    def test_sign_payload(self):
        from djoyalty.webhooks.webhook_security import sign_payload
        signature = sign_payload(b'test payload', 'mysecret')
        self.assertTrue(signature.startswith('sha256='))

    def test_verify_signature_valid(self):
        from djoyalty.webhooks.webhook_security import sign_payload, verify_signature
        payload = b'test data'
        secret = 'mysecret'
        signature = sign_payload(payload, secret)
        self.assertTrue(verify_signature(payload, signature, secret))

    def test_verify_signature_invalid(self):
        from djoyalty.webhooks.webhook_security import verify_signature
        self.assertFalse(verify_signature(b'test', 'sha256=invalid', 'secret'))

    def test_verify_signature_wrong_secret(self):
        from djoyalty.webhooks.webhook_security import sign_payload, verify_signature
        payload = b'hello'
        sig = sign_payload(payload, 'correct_secret')
        self.assertFalse(verify_signature(payload, sig, 'wrong_secret'))

    def test_generate_secret(self):
        from djoyalty.webhooks.webhook_security import generate_secret
        s1 = generate_secret()
        s2 = generate_secret()
        self.assertNotEqual(s1, s2)
        self.assertEqual(len(s1), 32)


class WebhookRegistryTest(TestCase):

    def setUp(self):
        from djoyalty.webhooks.webhook_registry import WebhookRegistry
        WebhookRegistry.clear() if hasattr(WebhookRegistry, '_endpoints') else None

    def test_register_endpoint(self):
        from djoyalty.webhooks.webhook_registry import WebhookRegistry
        WebhookRegistry._endpoints = []
        WebhookRegistry.register('https://example.com/hook', ['points.earned'], 'secret')
        self.assertEqual(len(WebhookRegistry._endpoints), 1)

    def test_get_endpoints_for_event(self):
        from djoyalty.webhooks.webhook_registry import WebhookRegistry
        WebhookRegistry._endpoints = []
        WebhookRegistry.register('https://example.com/hook', ['points.earned', 'tier.changed'])
        endpoints = WebhookRegistry.get_endpoints_for_event('points.earned')
        self.assertEqual(len(endpoints), 1)

    def test_get_endpoints_for_unregistered_event(self):
        from djoyalty.webhooks.webhook_registry import WebhookRegistry
        WebhookRegistry._endpoints = []
        endpoints = WebhookRegistry.get_endpoints_for_event('unknown.event')
        self.assertEqual(len(endpoints), 0)


class WebhookPayloadTest(TestCase):

    def test_build_payload_has_required_keys(self):
        from djoyalty.webhooks.webhook_payloads import build_payload
        from djoyalty.events.loyalty_events import LoyaltyEvent
        event = LoyaltyEvent(event_type='points.earned', data={'points': '100'})
        payload = build_payload(event)
        self.assertIn('event', payload)
        self.assertIn('timestamp', payload)
        self.assertIn('data', payload)
        self.assertEqual(payload['event'], 'points.earned')
