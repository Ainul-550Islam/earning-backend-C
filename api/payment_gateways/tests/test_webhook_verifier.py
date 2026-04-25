# tests/test_webhook_verifier.py
import pytest
import hmac, hashlib
from django.test import override_settings


class TestWebhookVerifierService:
    def test_verify_bkash_valid_signature(self):
        from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService
        secret  = 'test_bkash_secret'
        body    = b'{"paymentID":"PAY_001","status":"Authorized"}'
        sig     = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        with override_settings(BKASH_WEBHOOK_SECRET=secret):
            svc    = WebhookVerifierService()
            result = svc.verify('bkash', body, {'X-bKash-Signature': sig})
        assert result is True

    def test_verify_bkash_invalid_signature(self):
        from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService
        body   = b'{"paymentID":"PAY_001"}'
        with override_settings(BKASH_WEBHOOK_SECRET='correct_secret'):
            svc    = WebhookVerifierService()
            result = svc.verify('bkash', body, {'X-bKash-Signature': 'wrong_signature'})
        assert result is False

    def test_verify_stripe_signature(self):
        from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService
        import time
        secret = 'whsec_test'
        ts     = int(time.time())
        body   = b'{"type":"payment_intent.succeeded"}'
        sig    = hmac.new(secret.encode(), f'{ts}.'.encode() + body, hashlib.sha256).hexdigest()
        header = f't={ts},v1={sig}'
        with override_settings(STRIPE_WEBHOOK_SECRET=secret):
            svc    = WebhookVerifierService()
            result = svc.verify('stripe', body, {'Stripe-Signature': header})
        assert result is True

    def test_unknown_gateway_allowed(self):
        from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService
        svc    = WebhookVerifierService()
        result = svc.verify('unknown_gateway', b'body', {})
        assert result is True  # No config = allow
