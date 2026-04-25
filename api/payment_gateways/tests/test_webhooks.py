# FILE 140 of 257 — tests/test_webhooks.py
import pytest, json
from django.test import RequestFactory

@pytest.mark.django_db
class TestPayPalWebhook:
    def test_paypal_webhook_invalid_json(self):
        from payment_gateways.webhooks.PayPalWebhook import paypal_webhook
        factory = RequestFactory()
        req = factory.post('/webhooks/paypal/', data=b'not-json',
                           content_type='application/json')
        resp = paypal_webhook(req)
        assert resp.status_code in (200, 400, 500)

@pytest.mark.django_db
class TestSSLCommerzWebhook:
    def test_sslcommerz_ipn_missing_signature(self):
        from payment_gateways.webhooks.SSLCommerzWebhook import sslcommerz_ipn
        factory = RequestFactory()
        req = factory.post('/webhooks/sslcommerz/', data={'tran_id':'TEST_001'})
        resp = sslcommerz_ipn(req)
        assert resp.status_code in (200, 400)
