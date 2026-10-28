"""
tests/test_phase2_services.py

Unit tests for Phase-2 offerwall provider services:
  - MonlixService
  - OGAdsService
  - FyberService
  - LiftoffService
  - AppLiftService

Run: python manage.py test api.offerwall.tests.test_phase2_services
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase
from api.offerwall.models import OfferProvider


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def mk_provider(ptype, **kwargs):
    defaults = dict(
        name=f'{ptype.title()} Test',
        provider_type=ptype,
        status='active',
        api_key='test_key_123',
        api_secret='test_secret_456',
        app_id='test_app_001',
        publisher_id='pub_001',
        secret_key='webhook_secret_xyz',
        revenue_share=Decimal('70.00'),
    )
    defaults.update(kwargs)
    return OfferProvider(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# MONLIX SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class MonlixServiceInitTest(TestCase):
    def setUp(self):
        self.provider = mk_provider('monlix')

    def test_init_sets_api_base(self):
        from api.offerwall.services.MonlixService import MonlixService
        svc = MonlixService(self.provider)
        self.assertIn('monlix', svc.api_base)

    def test_init_sets_publisher_id(self):
        from api.offerwall.services.MonlixService import MonlixService
        svc = MonlixService(self.provider)
        self.assertEqual(svc.publisher_id, 'pub_001')

    def test_init_sets_api_key(self):
        from api.offerwall.services.MonlixService import MonlixService
        svc = MonlixService(self.provider)
        self.assertEqual(svc.api_key, 'test_key_123')

    def test_init_sets_secret_key(self):
        from api.offerwall.services.MonlixService import MonlixService
        svc = MonlixService(self.provider)
        self.assertEqual(svc.secret_key, 'webhook_secret_xyz')


class MonlixServiceNormalizeTest(TestCase):
    def setUp(self):
        from api.offerwall.services.MonlixService import MonlixService
        self.svc = MonlixService(mk_provider('monlix'))

    def test_normalize_offer_maps_fields(self):
        raw = {
            'id': 'MX001', 'name': 'Play Game', 'description': 'Desc',
            'type': 'app', 'device': 'android', 'countries': ['US', 'GB'],
            'link': 'https://example.com/go', 'payout': '1.50',
            'reward': '1.05', 'status': 'active', 'daily_cap': 100,
        }
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['external_offer_id'], 'MX001')
        self.assertEqual(result['title'], 'Play Game')
        self.assertEqual(result['offer_type'], 'app_install')
        self.assertEqual(result['platform'], 'android')
        self.assertEqual(result['payout'], Decimal('1.50'))
        self.assertEqual(result['reward_amount'], Decimal('1.05'))
        self.assertEqual(result['status'], 'active')
        self.assertEqual(result['daily_cap'], 100)

    def test_normalize_survey_type(self):
        raw = {'id': 'MX002', 'name': 'Survey', 'type': 'survey',
               'payout': '0.75', 'status': 'active'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['offer_type'], 'survey')

    def test_normalize_unknown_type_defaults_to_other(self):
        raw = {'id': 'MX003', 'name': 'Unknown', 'type': 'xyz', 'payout': '0.10'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['offer_type'], 'other')

    def test_normalize_payout_as_decimal(self):
        raw = {'id': 'MX004', 'name': 'T', 'payout': '2.999'}
        result = self.svc._normalize_offer(raw)
        self.assertIsInstance(result['payout'], Decimal)


class MonlixWebhookParseTest(TestCase):
    def setUp(self):
        from api.offerwall.services.MonlixService import MonlixService
        self.svc = MonlixService(mk_provider('monlix'))

    def test_parse_webhook_extracts_fields(self):
        data = {
            'user_id': '42', 'offer_id': 'MX001',
            'transaction_id': 'TXN_ABC', 'payout': '1.50',
            'reward': '1.05', 'status': 'approved',
        }
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['user_id'], '42')
        self.assertEqual(result['offer_id'], 'MX001')
        self.assertEqual(result['conversion_id'], 'TXN_ABC')
        self.assertEqual(result['payout_amount'], Decimal('1.50'))
        self.assertEqual(result['reward_amount'], Decimal('1.05'))
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['provider_type'], 'monlix')

    def test_parse_webhook_signature_verified(self):
        import hmac, hashlib
        data = {'user_id': '1', 'offer_id': '2', 'payout': '1.00',
                'transaction_id': 'TXN123'}
        msg  = "1:2:1.00"
        sig  = hmac.new(b'webhook_secret_xyz', msg.encode(), hashlib.sha256).hexdigest()
        data['signature'] = sig
        # Should not raise
        result = self.svc.parse_webhook(data)
        self.assertIsNotNone(result)

    def test_invalid_signature_raises(self):
        from api.offerwall.exceptions import InvalidWebhookSignatureException
        data = {'user_id': '1', 'offer_id': '2', 'payout': '1.00',
                'transaction_id': 'TXN999', 'signature': 'BADSIG'}
        with self.assertRaises(InvalidWebhookSignatureException):
            self.svc.parse_webhook(data)


# ─────────────────────────────────────────────────────────────────────────────
# OGADS SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class OGAdsServiceNormalizeTest(TestCase):
    def setUp(self):
        from api.offerwall.services.OGAdsService import OGAdsService
        self.svc = OGAdsService(mk_provider('ogads'))

    def test_normalize_cpi_maps_app_install(self):
        raw = {'id': 'OG001', 'name': 'App Install', 'type': 'cpi',
               'os': 'android', 'payout': '2.00', 'country': 'US',
               'link': 'https://og.com/click', 'points': '1.40'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['offer_type'], 'app_install')
        self.assertEqual(result['payout'], Decimal('2.00'))
        self.assertEqual(result['reward_amount'], Decimal('1.40'))

    def test_normalize_survey_type(self):
        raw = {'id': 'OG002', 'name': 'Survey', 'type': 'survey', 'payout': '0.50'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['offer_type'], 'survey')

    def test_normalize_unknown_type_other(self):
        raw = {'id': 'OG003', 'name': 'X', 'type': 'promo', 'payout': '0.10'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['offer_type'], 'other')


class OGAdsWebhookParseTest(TestCase):
    def setUp(self):
        from api.offerwall.services.OGAdsService import OGAdsService
        self.svc = OGAdsService(mk_provider('ogads'))

    def test_parse_webhook_uses_sub1_as_user(self):
        data = {'sub1': '99', 'aff_sub': 'OG001',
                'transaction_id': 'TX001', 'payout': '2.00', 'status': 'approved'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['user_id'], '99')
        self.assertEqual(result['offer_id'], 'OG001')
        self.assertEqual(result['conversion_id'], 'TX001')
        self.assertEqual(result['provider_type'], 'ogads')

    def test_parse_webhook_fallback_user_id(self):
        data = {'user_id': '55', 'offer_id': 'OG002',
                'tid': 'TX002', 'payout': '1.00'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['user_id'], '55')


# ─────────────────────────────────────────────────────────────────────────────
# FYBER SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class FyberServiceHashkeyTest(TestCase):
    def setUp(self):
        from api.offerwall.services.FyberService import FyberService
        self.svc = FyberService(mk_provider('fyber'))
        self.svc.app_id = 'APP123'
        self.svc.security_token = 'TOKEN456'

    def test_hashkey_is_sha1(self):
        import hashlib
        uid    = 'user1'
        ip     = '1.2.3.4'
        locale = 'en'
        raw    = f"APP123{ip}{locale}{uid}TOKEN456"
        expected = hashlib.sha1(raw.encode()).hexdigest()
        self.assertEqual(self.svc._build_hashkey(uid, ip, locale), expected)

    def test_hashkey_is_40_chars(self):
        result = self.svc._build_hashkey('u', '0.0.0.0', 'en')
        self.assertEqual(len(result), 40)


class FyberServiceNormalizeTest(TestCase):
    def setUp(self):
        from api.offerwall.services.FyberService import FyberService
        self.svc = FyberService(mk_provider('fyber'))

    def test_normalize_offer_maps_fields(self):
        raw = {
            'offerId': 'FY001',
            'title': 'Fyber Offer',
            'teaser': 'Short teaser',
            'os': 'ios',
            'link': 'https://fyber.com/click',
            'thumbnail': {'lowres': 'https://img.com/img.jpg'},
            'payout': {'gross': '3.00', 'net': '2.10'},
        }
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['external_offer_id'], 'FY001')
        self.assertEqual(result['title'], 'Fyber Offer')
        self.assertEqual(result['payout'], Decimal('3.00'))
        self.assertEqual(result['reward_amount'], Decimal('2.10'))


class FyberWebhookParseTest(TestCase):
    def setUp(self):
        from api.offerwall.services.FyberService import FyberService
        self.svc = FyberService(mk_provider('fyber'))

    def test_parse_returns_approved_status(self):
        data = {'uid': '7', 'orderId': 'ORD001', 'pub0': 'FY001',
                'grossAmount': '3.00', 'virtualCurrency': '2.10'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['user_id'], '7')
        self.assertEqual(result['payout_amount'], Decimal('3.00'))
        self.assertEqual(result['provider_type'], 'fyber')


# ─────────────────────────────────────────────────────────────────────────────
# LIFTOFF SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class LiftoffServiceNormalizeTest(TestCase):
    def setUp(self):
        from api.offerwall.services.LiftoffService import LiftoffService
        self.svc = LiftoffService(mk_provider('liftoff'))

    def test_normalize_install_campaign(self):
        raw = {
            'campaign_id': 'LF001', 'app_name': 'Mobile Game',
            'description': 'Play game', 'platform': 'android',
            'target_countries': ['US', 'CA'],
            'click_url': 'https://liftoff.io/click',
            'icon_url': 'https://img.com/icon.png',
            'payout': '1.80', 'status': 'active',
            'campaign_type': 'install',
        }
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['external_offer_id'], 'LF001')
        self.assertEqual(result['offer_type'], 'app_install')
        self.assertEqual(result['status'], 'active')
        self.assertEqual(result['payout'], Decimal('1.80'))

    def test_normalize_paused_status(self):
        raw = {'campaign_id': 'LF002', 'app_name': 'X', 'payout': '1.00',
               'status': 'paused', 'campaign_type': 'install'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['status'], 'paused')


class LiftoffWebhookParseTest(TestCase):
    def setUp(self):
        from api.offerwall.services.LiftoffService import LiftoffService
        self.svc = LiftoffService(mk_provider('liftoff'))

    def test_parse_webhook_fields(self):
        data = {'ext_user_id': '5', 'ext_campaign_id': 'LF001',
                'transaction_id': 'TXLF001', 'payout': '1.80'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['user_id'], '5')
        self.assertEqual(result['offer_id'], 'LF001')
        self.assertEqual(result['payout_amount'], Decimal('1.80'))
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['provider_type'], 'liftoff')


# ─────────────────────────────────────────────────────────────────────────────
# APPLIFT SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class AppLiftServiceNormalizeTest(TestCase):
    def setUp(self):
        from api.offerwall.services.AppLiftService import AppLiftService
        self.svc = AppLiftService(mk_provider('applift'))

    def test_normalize_has_offers_format(self):
        raw = {
            'id': 'AL001',
            'name': 'AppLift Offer',
            'description': 'desc',
            'vertical': 'install',
            'platforms': ['android'],
            'countries': ['US'],
            'payout': {'amount': '1.20'},
            'status': 'active',
            'thumbnail_url': 'https://img.com/t.png',
        }
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['external_offer_id'], 'AL001')
        self.assertEqual(result['offer_type'], 'app_install')
        self.assertEqual(result['payout'], Decimal('1.20'))
        self.assertEqual(result['status'], 'active')

    def test_normalize_payout_as_flat_string(self):
        raw = {'id': 'AL002', 'name': 'X', 'vertical': 'cpi',
               'platforms': ['ios'], 'payout': '2.00', 'status': 'active'}
        result = self.svc._normalize_offer(raw)
        self.assertEqual(result['payout'], Decimal('2.00'))


class AppLiftWebhookParseTest(TestCase):
    def setUp(self):
        from api.offerwall.services.AppLiftService import AppLiftService
        self.svc = AppLiftService(mk_provider('applift'))

    def test_parse_uses_aff_sub_as_user(self):
        data = {'aff_sub': '11', 'aff_sub2': 'AL001',
                'transaction_id': 'TXAL001', 'payout': '1.20',
                'status': 'approved'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['user_id'], '11')
        self.assertEqual(result['offer_id'], 'AL001')
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['provider_type'], 'applift')

    def test_parse_maps_rejected_status(self):
        data = {'aff_sub': '11', 'aff_sub2': 'AL002',
                'transaction_id': 'TXAL002', 'payout': '0.00',
                'status': 'rejected'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['status'], 'rejected')

    def test_parse_maps_reversed_to_chargeback(self):
        data = {'aff_sub': '11', 'aff_sub2': 'AL003',
                'transaction_id': 'TXAL003', 'payout': '0.00',
                'status': 'reversed'}
        result = self.svc.parse_webhook(data)
        self.assertEqual(result['status'], 'chargeback')


# ─────────────────────────────────────────────────────────────────────────────
# OFFER FACTORY — Phase-2 registration
# ─────────────────────────────────────────────────────────────────────────────

class OfferFactoryPhase2RegistrationTest(TestCase):
    def test_monlix_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        types = list(OfferFactory._processors.keys())
        self.assertIn('monlix', types)

    def test_ogads_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        self.assertIn('ogads', list(OfferFactory._processors.keys()))

    def test_fyber_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        self.assertIn('fyber', list(OfferFactory._processors.keys()))

    def test_liftoff_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        self.assertIn('liftoff', list(OfferFactory._processors.keys()))

    def test_applift_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        self.assertIn('applift', list(OfferFactory._processors.keys()))

    def test_original_providers_still_registered(self):
        from api.offerwall.services.OfferFactory import OfferFactory, auto_register_processors
        OfferFactory.reset_registry()
        auto_register_processors()
        types = list(OfferFactory._processors.keys())
        for ptype in ('tapjoy', 'adgem', 'adgate', 'offerwall', 'persona'):
            self.assertIn(ptype, types, f'{ptype} should still be registered')
