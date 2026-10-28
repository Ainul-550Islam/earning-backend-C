"""
tests/test_phase2_webhooks.py

Tests for Phase-2 webhook handlers.
Strategy: patch OfferwallIntegrationService.process_conversion at the
module level where the webhook imports it lazily.
"""
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()

# Patch at the lazy import site used by every webhook handler
_SVC = 'api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.process_conversion'


# ── helpers ──────────────────────────────────────────────────────────────────

def _user(username):
    return User.objects.create_user(username, password='p')


def _provider(ptype):
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=f'{ptype.title()} Prov', provider_type=ptype, status='active',
        api_key='k', app_id='app', publisher_id='pub', secret_key='',
        revenue_share=Decimal('70'), config={'auto_approve': True},
    )


def _offer(provider, ext_id='EXT001'):
    from api.offerwall.models import Offer
    return Offer.objects.create(
        provider=provider, external_offer_id=ext_id, title='T',
        payout=Decimal('1.50'), reward_amount=Decimal('1.05'), status='active',
    )


def _mock_result(conv_id='TXN_TEST'):
    conv = MagicMock()
    conv.conversion_id = conv_id
    return {'conversion': conv, 'created': True}


# ── MONLIX ───────────────────────────────────────────────────────────────────

class MonlixWebhookViewTest(TestCase):
    def setUp(self):
        self.rf       = RequestFactory()
        self.user     = _user('monlix_usr')
        self.provider = _provider('monlix')
        self.offer    = _offer(self.provider, 'MX001')

    @patch(_SVC)
    def test_get_valid_payload_returns_200(self, mock_proc):
        from api.offerwall.webhooks.MonlixWebhook import MonlixWebhookView
        mock_proc.return_value = _mock_result('MX_T1')
        req = self.rf.get('/', {
            'user_id': str(self.user.pk), 'offer_id': 'MX001',
            'transaction_id': 'MX_T1', 'payout': '1.50', 'status': 'approved',
        })
        self.assertEqual(MonlixWebhookView.as_view()(req).status_code, 200)

    def test_missing_user_id_returns_400(self):
        from api.offerwall.webhooks.MonlixWebhook import MonlixWebhookView
        req = self.rf.get('/', {'offer_id': 'MX001', 'transaction_id': 'MX_T2', 'payout': '1.50'})
        self.assertEqual(MonlixWebhookView.as_view()(req).status_code, 400)

    def test_unknown_user_returns_400(self):
        from api.offerwall.webhooks.MonlixWebhook import MonlixWebhookView
        req = self.rf.get('/', {
            'user_id': '99999', 'offer_id': 'MX001',
            'transaction_id': 'MX_T3', 'payout': '1.50',
        })
        self.assertEqual(MonlixWebhookView.as_view()(req).status_code, 400)

    @patch(_SVC)
    def test_post_request_also_accepted(self, mock_proc):
        from api.offerwall.webhooks.MonlixWebhook import MonlixWebhookView
        mock_proc.return_value = _mock_result('MX_T4')
        req = self.rf.post('/', {
            'user_id': str(self.user.pk), 'offer_id': 'MX001',
            'transaction_id': 'MX_T4', 'payout': '1.50',
        })
        self.assertEqual(MonlixWebhookView.as_view()(req).status_code, 200)


# ── OGADS ────────────────────────────────────────────────────────────────────

class OGAdsWebhookViewTest(TestCase):
    def setUp(self):
        self.rf       = RequestFactory()
        self.user     = _user('ogads_usr')
        self.provider = _provider('ogads')
        self.offer    = _offer(self.provider, 'OG001')

    @patch(_SVC)
    def test_get_valid_payload_returns_200(self, mock_proc):
        from api.offerwall.webhooks.OGAdsWebhook import OGAdsWebhookView
        mock_proc.return_value = _mock_result('OG_T1')
        req = self.rf.get('/', {
            'sub1': str(self.user.pk), 'aff_sub': 'OG001',
            'transaction_id': 'OG_T1', 'payout': '2.00', 'status': 'approved',
        })
        self.assertEqual(OGAdsWebhookView.as_view()(req).status_code, 200)

    def test_missing_sub1_returns_400(self):
        from api.offerwall.webhooks.OGAdsWebhook import OGAdsWebhookView
        req = self.rf.get('/', {'aff_sub': 'OG001', 'transaction_id': 'OG_T2', 'payout': '2.00'})
        self.assertEqual(OGAdsWebhookView.as_view()(req).status_code, 400)

    def test_invalid_user_returns_400(self):
        from api.offerwall.webhooks.OGAdsWebhook import OGAdsWebhookView
        req = self.rf.get('/', {
            'sub1': '88888', 'aff_sub': 'OG001',
            'transaction_id': 'OG_T3', 'payout': '2.00',
        })
        self.assertEqual(OGAdsWebhookView.as_view()(req).status_code, 400)


# ── FYBER ────────────────────────────────────────────────────────────────────

class FyberWebhookViewTest(TestCase):
    def setUp(self):
        self.rf       = RequestFactory()
        self.user     = _user('fyber_usr')
        self.provider = _provider('fyber')
        self.offer    = _offer(self.provider, 'FY001')

    @patch(_SVC)
    def test_get_valid_callback_returns_200(self, mock_proc):
        from api.offerwall.webhooks.FyberWebhook import FyberWebhookView
        mock_proc.return_value = _mock_result('FY_T1')
        req = self.rf.get('/', {
            'uid': str(self.user.pk), 'pub0': 'FY001',
            'orderId': 'FY_T1', 'grossAmount': '3.00', 'virtualCurrency': '2.10',
        })
        self.assertEqual(FyberWebhookView.as_view()(req).status_code, 200)

    def test_missing_uid_returns_400(self):
        from api.offerwall.webhooks.FyberWebhook import FyberWebhookView
        req = self.rf.get('/', {'orderId': 'FY_T2', 'grossAmount': '3.00'})
        self.assertEqual(FyberWebhookView.as_view()(req).status_code, 400)

    @patch(_SVC)
    def test_response_body_contains_ok(self, mock_proc):
        from api.offerwall.webhooks.FyberWebhook import FyberWebhookView
        mock_proc.return_value = _mock_result('FY_T3')
        req = self.rf.get('/', {
            'uid': str(self.user.pk), 'pub0': 'FY001',
            'orderId': 'FY_T3', 'grossAmount': '3.00',
        })
        resp = FyberWebhookView.as_view()(req)
        self.assertIn(b'OK', resp.content)


# ── LIFTOFF ──────────────────────────────────────────────────────────────────

class LiftoffWebhookViewTest(TestCase):
    def setUp(self):
        self.rf       = RequestFactory()
        self.user     = _user('liftoff_usr')
        self.provider = _provider('liftoff')
        self.offer    = _offer(self.provider, 'LF001')

    @patch(_SVC)
    def test_get_valid_payload_returns_200(self, mock_proc):
        from api.offerwall.webhooks.LiftoffWebhook import LiftoffWebhookView
        mock_proc.return_value = _mock_result('LF_T1')
        req = self.rf.get('/', {
            'ext_user_id': str(self.user.pk), 'ext_campaign_id': 'LF001',
            'transaction_id': 'LF_T1', 'payout': '1.80',
        })
        self.assertEqual(LiftoffWebhookView.as_view()(req).status_code, 200)

    def test_missing_user_returns_400(self):
        from api.offerwall.webhooks.LiftoffWebhook import LiftoffWebhookView
        req = self.rf.get('/', {'ext_campaign_id': 'LF001', 'transaction_id': 'LF_T2', 'payout': '1.80'})
        self.assertEqual(LiftoffWebhookView.as_view()(req).status_code, 400)

    @patch(_SVC)
    def test_post_json_payload_accepted(self, mock_proc):
        from api.offerwall.webhooks.LiftoffWebhook import LiftoffWebhookView
        mock_proc.return_value = _mock_result('LF_T3')
        body = json.dumps({
            'ext_user_id': str(self.user.pk), 'ext_campaign_id': 'LF001',
            'transaction_id': 'LF_T3', 'payout': '1.80',
        }).encode()
        req = self.rf.post('/', data=body, content_type='application/json')
        self.assertEqual(LiftoffWebhookView.as_view()(req).status_code, 200)


# ── APPLIFT ──────────────────────────────────────────────────────────────────

class AppLiftWebhookViewTest(TestCase):
    def setUp(self):
        self.rf       = RequestFactory()
        self.user     = _user('applift_usr')
        self.provider = _provider('applift')
        self.offer    = _offer(self.provider, 'AL001')

    @patch(_SVC)
    def test_get_valid_payload_returns_200(self, mock_proc):
        from api.offerwall.webhooks.AppLiftWebhook import AppLiftWebhookView
        mock_proc.return_value = _mock_result('AL_T1')
        req = self.rf.get('/', {
            'aff_sub': str(self.user.pk), 'aff_sub2': 'AL001',
            'transaction_id': 'AL_T1', 'payout': '1.20', 'status': 'approved',
        })
        self.assertEqual(AppLiftWebhookView.as_view()(req).status_code, 200)

    def test_missing_aff_sub_returns_400(self):
        from api.offerwall.webhooks.AppLiftWebhook import AppLiftWebhookView
        req = self.rf.get('/', {'aff_sub2': 'AL001', 'transaction_id': 'AL_T2', 'payout': '1.20'})
        self.assertEqual(AppLiftWebhookView.as_view()(req).status_code, 400)

    def test_invalid_user_returns_400(self):
        from api.offerwall.webhooks.AppLiftWebhook import AppLiftWebhookView
        req = self.rf.get('/', {
            'aff_sub': '77777', 'aff_sub2': 'AL001',
            'transaction_id': 'AL_T3', 'payout': '1.20',
        })
        self.assertEqual(AppLiftWebhookView.as_view()(req).status_code, 400)

    @patch(_SVC)
    def test_post_request_accepted(self, mock_proc):
        from api.offerwall.webhooks.AppLiftWebhook import AppLiftWebhookView
        mock_proc.return_value = _mock_result('AL_T4')
        req = self.rf.post('/', {
            'aff_sub': str(self.user.pk), 'aff_sub2': 'AL001',
            'transaction_id': 'AL_T4', 'payout': '1.20', 'status': 'approved',
        })
        self.assertEqual(AppLiftWebhookView.as_view()(req).status_code, 200)
