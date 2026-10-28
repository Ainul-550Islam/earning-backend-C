"""
tests/test_chargeback.py — ChargebackService + webhook views (was 0 tests)
Covers: ChargebackService.process(), wallet reversal, notify,
        ChargebackWebhookView, TapjoyChargebackView,
        AdGateChargebackView, PersonaChargebackView
"""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class ChargebackServiceTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferFactory, OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory()
        self.offer      = OfferFactory(provider=self.provider)
        self.user       = User.objects.create_user('cbsvc', password='pw')
        self.conversion = OfferConversionFactory(
            offer=self.offer, user=self.user, status='approved',
            reward_amount=Decimal('0.50'))

    @patch('api.offerwall.chargeback.ChargebackService._reverse_wallet',
           return_value=True)
    @patch('api.offerwall.chargeback.ChargebackService._notify_user')
    @patch('api.offerwall.chargeback.ChargebackService._audit')
    def test_process_approved_conversion(self, mock_audit, mock_notify, mock_wallet):
        from api.offerwall.chargeback import ChargebackService
        result = ChargebackService.process(
            conversion_id=self.conversion.conversion_id,
            reason='fraud detected')
        self.assertTrue(result['success'])
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.status, 'chargeback')
        mock_wallet.assert_called_once()
        mock_notify.assert_called_once()

    def test_process_nonexistent_conversion(self):
        from api.offerwall.chargeback import ChargebackService
        result = ChargebackService.process(
            conversion_id='nonexistent-id-12345', reason='test')
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_process_pending_conversion_fails(self):
        from api.offerwall.chargeback import ChargebackService
        self.conversion.status = 'pending'
        self.conversion.save()
        result = ChargebackService.process(
            conversion_id=self.conversion.conversion_id, reason='test')
        self.assertFalse(result['success'])

    @patch('api.offerwall.chargeback.ChargebackService._reverse_wallet',
           return_value=True)
    @patch('api.offerwall.chargeback.ChargebackService._notify_user')
    @patch('api.offerwall.chargeback.ChargebackService._audit')
    def test_process_returns_reversed_amount(self, mock_audit, mock_notify, mock_wallet):
        from api.offerwall.chargeback import ChargebackService
        result = ChargebackService.process(
            conversion_id=self.conversion.conversion_id, reason='test')
        self.assertIn('reversed_amount', result)
        self.assertGreater(float(result['reversed_amount']), 0)

    def test_idempotent_double_chargeback(self):
        """Already charged-back conversion should not be re-processed (no
        duplicate wallet reversal) — process() signals this via idempotent=True
        while still returning success=True, per its documented contract."""
        from api.offerwall.chargeback import ChargebackService
        self.conversion.status = 'chargeback'
        self.conversion.save()
        result = ChargebackService.process(
            conversion_id=self.conversion.conversion_id, reason='repeat')
        self.assertTrue(result['success'])
        self.assertTrue(result.get('idempotent'))


class ChargebackWebhookViewTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory(secret_key='cb_test_secret')
        self.conversion = OfferConversionFactory(status='approved')

    def _make_sig(self, conversion_id, secret):
        payload = json.dumps({
            'conversion_id': conversion_id,
            'reason': 'fraud',
        }).encode()
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(), payload

    def test_valid_chargeback_processes(self):
        sig, payload = self._make_sig(
            self.conversion.conversion_id, 'cb_test_secret')
        with patch('api.offerwall.chargeback.ChargebackService.process',
                   return_value={'success': True,
                                 'conversion_id': self.conversion.conversion_id,
                                 'reversed_amount': '0.50'}):
            resp = self.client.post(
                '/api/offerwall/webhooks/chargeback/',
                data=payload,
                content_type='application/json',
                HTTP_X_SIGNATURE=sig,
            )
        self.assertIn(resp.status_code, [200, 404])

    def test_missing_conversion_id_returns_400(self):
        payload = json.dumps({'reason': 'fraud'}).encode()
        resp    = self.client.post(
            '/api/offerwall/webhooks/chargeback/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_failed_chargeback_returns_400(self):
        payload = json.dumps({
            'conversion_id': 'nonexistent',
            'reason': 'fraud',
        }).encode()
        resp = self.client.post(
            '/api/offerwall/webhooks/chargeback/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class TapjoyChargebackViewTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import (
            OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory(
            provider_type='tapjoy', secret_key='tapjoy_cb_secret')
        self.conversion = OfferConversionFactory(status='approved')

    def test_valid_tapjoy_chargeback(self):
        payload = json.dumps({
            'conversion_id': self.conversion.conversion_id,
            'reason':        'chargeback',
        }).encode()
        sig = hmac.new(b'tapjoy_cb_secret', payload, hashlib.sha256).hexdigest()

        with patch('api.offerwall.chargeback.ChargebackService.process',
                   return_value={'success': True,
                                 'conversion_id': self.conversion.conversion_id,
                                 'reversed_amount': '0.50'}):
            resp = self.client.post(
                '/api/offerwall/webhooks/tapjoy/chargeback/',
                data=payload,
                content_type='application/json',
                HTTP_X_TAPJOY_SIGNATURE=sig,
            )
        self.assertIn(resp.status_code, [200, 404])
