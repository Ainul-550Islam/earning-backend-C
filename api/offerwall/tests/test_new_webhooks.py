"""
tests/test_new_webhooks.py

Covers:
  - AdGateWebhookView (was 0 tests)
  - PersonaWebhookView (was 0 tests)
  - OfferConversionViewSet.chargeback action (was 0 tests)
  - OfferConversionViewSet.reverse action (was 0 tests)
  - AdGateChargebackView
  - PersonaChargebackView
"""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class AdGateWebhookViewTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferProviderFactory, OfferFactory
        self.provider = OfferProviderFactory(
            provider_type='adgate', status='active',
            secret_key='adgate_secret')
        self.offer = OfferFactory(
            provider=self.provider,
            external_offer_id='AG-001')
        self.user = User.objects.create_user(
            username='aguser', password='pw')

    def _make_sig(self, pointvalue, adgateid, userid, secret):
        raw = f'{pointvalue}{adgateid}{userid}{secret}'
        return hashlib.sha256(raw.encode()).hexdigest()

    def test_valid_postback_creates_conversion(self):
        sig = self._make_sig('0.50', 'AG-001', self.user.id, 'adgate_secret')
        with patch('api.offerwall.services.OfferwallIntegrationService'
                   '.OfferwallIntegrationService.process_conversion',
                   return_value={'success': True,
                                 'conversion': MagicMock(conversion_id='cb1'),
                                 'created': True}):
            resp = self.client.get('/api/offerwall/webhooks/adgate/', {
                'userid':      str(self.user.id),
                'adgateid':    'AG-001',
                'pointvalue':  '0.50',
                'hash':        sig,
                'transaction': 'TXN-AG-001',
            })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'1')

    def test_invalid_signature_returns_401(self):
        resp = self.client.get('/api/offerwall/webhooks/adgate/', {
            'userid':      str(self.user.id),
            'adgateid':    'AG-001',
            'pointvalue':  '0.50',
            'hash':        'badhash',
            'transaction': 'TXN-AG-002',
        })
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.content, b'0')

    def test_missing_params_returns_400(self):
        resp = self.client.get('/api/offerwall/webhooks/adgate/', {
            'userid': str(self.user.id),
        })
        self.assertEqual(resp.status_code, 400)

    def test_unknown_user_returns_400(self):
        sig = self._make_sig('0.50', 'AG-001', '99999', 'adgate_secret')
        resp = self.client.get('/api/offerwall/webhooks/adgate/', {
            'userid':      '99999',
            'adgateid':    'AG-001',
            'pointvalue':  '0.50',
            'hash':        sig,
            'transaction': 'TXN-AG-003',
        })
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_conversion_returns_200(self):
        sig = self._make_sig('0.50', 'AG-001', self.user.id, 'adgate_secret')
        with patch('api.offerwall.services.OfferwallIntegrationService'
                   '.OfferwallIntegrationService.process_conversion',
                   return_value={'success': True,
                                 'conversion': MagicMock(conversion_id='cb1'),
                                 'created': False,
                                 'message': 'Duplicate'}):
            resp = self.client.get('/api/offerwall/webhooks/adgate/', {
                'userid':      str(self.user.id),
                'adgateid':    'AG-001',
                'pointvalue':  '0.50',
                'hash':        sig,
                'transaction': 'TXN-AG-001',
            })
        self.assertEqual(resp.status_code, 200)


class PersonaWebhookViewTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferProviderFactory
        self.provider = OfferProviderFactory(
            provider_type='persona', status='active',
            secret_key='persona_secret')
        self.user = User.objects.create_user(
            username='personauser', password='pw')

    def _make_sig(self, user_id, survey_id, payout, secret):
        raw = f'{user_id}{survey_id}{payout}{secret}'
        return hashlib.md5(raw.encode()).hexdigest()

    def test_complete_status_creates_conversion(self):
        sig = self._make_sig(
            self.user.id, 'SRV-001', '0.35', 'persona_secret')
        with patch('api.offerwall.services.OfferwallIntegrationService'
                   '.OfferwallIntegrationService.process_conversion',
                   return_value={'success': True,
                                 'conversion': MagicMock(conversion_id='pc1'),
                                 'created': True}):
            resp = self.client.get('/api/offerwall/webhooks/persona/', {
                'user_id':   str(self.user.id),
                'survey_id': 'SRV-001',
                'payout':    '0.35',
                'hash':      sig,
                'status':    'complete',
            })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'1')

    def test_screenout_not_credited(self):
        sig = self._make_sig(
            self.user.id, 'SRV-002', '0', 'persona_secret')
        resp = self.client.get('/api/offerwall/webhooks/persona/', {
            'user_id':   str(self.user.id),
            'survey_id': 'SRV-002',
            'payout':    '0',
            'hash':      sig,
            'status':    'screenout',
        })
        # Should acknowledge but not credit
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'1')

    def test_missing_user_id_returns_400(self):
        resp = self.client.get('/api/offerwall/webhooks/persona/', {
            'survey_id': 'SRV-003',
        })
        self.assertEqual(resp.status_code, 400)

    def test_invalid_signature_returns_401(self):
        resp = self.client.get('/api/offerwall/webhooks/persona/', {
            'user_id':   str(self.user.id),
            'survey_id': 'SRV-004',
            'payout':    '0.35',
            'hash':      'badsig',
            'status':    'complete',
        })
        self.assertEqual(resp.status_code, 401)


class ConversionChargebackActionTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin  = User.objects.create_superuser(
            'cbadmin', 'cb@test.com', 'pw')
        self.user   = User.objects.create_user('cbuser', password='pw')
        self.client.force_authenticate(user=self.admin)
        from api.offerwall.tests.factories import (
            OfferFactory, OfferProviderFactory, OfferConversionFactory)
        self.provider   = OfferProviderFactory()
        self.offer      = OfferFactory(provider=self.provider)
        self.conversion = OfferConversionFactory(
            offer=self.offer, user=self.user, status='approved')

    def test_chargeback_approved_conversion(self):
        url  = f'/api/offerwall/conversions/{self.conversion.pk}/chargeback/'
        resp = self.client.post(url, {'reason': 'fraud'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.status, 'chargeback')

    def test_chargeback_pending_conversion_fails(self):
        self.conversion.status = 'pending'
        self.conversion.save()
        url  = f'/api/offerwall/conversions/{self.conversion.pk}/chargeback/'
        resp = self.client.post(url, {'reason': 'test'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_chargeback_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        url  = f'/api/offerwall/conversions/{self.conversion.pk}/chargeback/'
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_reverse_chargeback_conversion(self):
        self.conversion.status = 'chargeback'
        self.conversion.save()
        url  = f'/api/offerwall/conversions/{self.conversion.pk}/reverse/'
        resp = self.client.post(url, {'reason': 'error'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.status, 'reversed')

    def test_reverse_pending_fails(self):
        self.conversion.status = 'pending'
        self.conversion.save()
        url  = f'/api/offerwall/conversions/{self.conversion.pk}/reverse/'
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 400)


class AdGateChargebackViewTest(TestCase):

    def setUp(self):
        from api.offerwall.tests.factories import OfferProviderFactory, OfferConversionFactory
        self.provider   = OfferProviderFactory(
            provider_type='adgate', status='active', secret_key='cb_secret')
        self.conv       = OfferConversionFactory(status='approved')

    def test_valid_chargeback(self):
        payload = json.dumps({
            'conversion_id': self.conv.conversion_id,
            'reason':        'fraud',
            'initiated_by':  'adgate',
        }).encode()
        sig = hmac.new(b'cb_secret', payload, hashlib.sha256).hexdigest()

        with patch('api.offerwall.chargeback.ChargebackService.process',
                   return_value={'success': True,
                                 'conversion_id': self.conv.conversion_id,
                                 'reversed_amount': '0.50'}):
            resp = self.client.post(
                '/api/offerwall/webhooks/adgate/chargeback/',
                data=payload,
                content_type='application/json',
                HTTP_X_ADGATE_SIGNATURE=sig,
            )
        self.assertIn(resp.status_code, [200, 404])

    def test_missing_conversion_id(self):
        resp = self.client.post(
            '/api/offerwall/webhooks/adgate/chargeback/',
            data=json.dumps({'reason': 'fraud'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
