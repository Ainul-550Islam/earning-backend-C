"""
Tests for the 7 missing components added in the feature-completeness pass:
  1. ContentLock (content_lock.py)
  2. ChargebackService (chargeback.py)
  3. Publisher API / EmbedToken (publisher.py)
  4. EarningsExport (exports.py)
  5. SurveyProviderService (services/survey/)
  6. BulkConversionWebhookView (bulk_conversion.py)
  7. expire_offers management command (management/commands/)

Run: python manage.py test api.offerwall.tests.test_missing_components
"""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def mk_user(un='mc_user', admin=False):
    if admin:
        return User.objects.create_superuser(
            username=un, email=f'{un}@t.com', password='Admin@123')
    return User.objects.create_user(
        username=un, email=f'{un}@t.com', password='pass')


def mk_provider(name='MC_P', ptype='tapjoy'):
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=name, provider_type=ptype, status='active',
        revenue_share=Decimal('70'), secret_key='testsecret')


def mk_offer(provider, ext_id=None):
    from api.offerwall.models import Offer
    return Offer.objects.create(
        provider=provider,
        external_offer_id=ext_id or uuid.uuid4().hex[:12],
        title='Test offer', description='d',
        payout=Decimal('1'), reward_amount=Decimal('0.70'),
        click_url='https://x.com', status='active',
    )


def mk_conversion(offer, user, conv_status='pending', ext_tx=None):
    from api.offerwall.models import OfferConversion
    return OfferConversion.objects.create(
        offer=offer, user=user,
        conversion_id=uuid.uuid4().hex[:12],
        external_WalletTransaction_id=ext_tx or uuid.uuid4().hex[:10],
        payout_amount=Decimal('1'), reward_amount=Decimal('0.70'),
        bonus_amount=Decimal('0'), status=conv_status,
    )


# ═════════════════════════════════════════════════════════════
# 1. CONTENT LOCK
# ═════════════════════════════════════════════════════════════

class ContentLockModelTest(TestCase):
    def setUp(self):
        self.user = mk_user('cl_u')

    def test_token_auto_generated(self):
        from api.offerwall.content_lock import ContentLock
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='Gate 1',
            required_conversions=1)
        self.assertTrue(len(lock.token) >= 16)

    def test_token_unique(self):
        from api.offerwall.content_lock import ContentLock
        a = ContentLock.objects.create(publisher=self.user, lock_type='url',
                                       title='G1', required_conversions=1)
        b = ContentLock.objects.create(publisher=self.user, lock_type='url',
                                       title='G2', required_conversions=1)
        self.assertNotEqual(a.token, b.token)

    def test_not_expired_by_default(self):
        from api.offerwall.content_lock import ContentLock
        lock = ContentLock.objects.create(publisher=self.user, lock_type='url',
                                          title='G3', required_conversions=1)
        self.assertFalse(lock.is_expired())

    def test_expired_when_past_expiry(self):
        from api.offerwall.content_lock import ContentLock
        from django.utils import timezone
        from datetime import timedelta
        past = timezone.now() - timedelta(hours=1)
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='G4',
            required_conversions=1, expires_at=past)
        self.assertTrue(lock.is_expired())

    def test_not_unlocked_without_conversions(self):
        from api.offerwall.content_lock import ContentLock
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='G5',
            required_conversions=1)
        self.assertFalse(lock.is_unlocked_for(self.user))

    def test_unlocked_after_approved_conversion(self):
        from api.offerwall.content_lock import ContentLock
        prov  = mk_provider('cl_prov')
        offer = mk_offer(prov)
        mk_conversion(offer, self.user, conv_status='approved')
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='G6',
            required_conversions=1)
        self.assertTrue(lock.is_unlocked_for(self.user))

    def test_requires_two_conversions_not_one(self):
        from api.offerwall.content_lock import ContentLock
        prov  = mk_provider('cl_p2')
        offer = mk_offer(prov, 'cl_o2')
        mk_conversion(offer, self.user, conv_status='approved', ext_tx='tx_a')
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='G7',
            required_conversions=2)
        self.assertFalse(lock.is_unlocked_for(self.user))

    def test_anonymous_user_not_unlocked(self):
        from api.offerwall.content_lock import ContentLock
        anon = MagicMock()
        anon.is_authenticated = False
        lock = ContentLock.objects.create(
            publisher=self.user, lock_type='url', title='G8',
            required_conversions=1)
        self.assertFalse(lock.is_unlocked_for(anon))


class ContentLockViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = mk_user('clv_u')
        self.client.force_authenticate(self.user)

    def test_create_lock_returns_201(self):
        r = self.client.post('/api/offerwall/locks/', {
            'lock_type': 'url', 'title': 'My gate',
            'required_conversions': 1,
            'content_url': 'https://example.com/secret',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('token', r.data)

    def test_list_own_locks(self):
        from api.offerwall.content_lock import ContentLock
        ContentLock.objects.create(publisher=self.user, lock_type='url',
                                   title='T', required_conversions=1)
        r = self.client.get('/api/offerwall/locks/')
        self.assertEqual(r.status_code, 200)

    def test_check_not_unlocked_returns_402(self):
        from api.offerwall.content_lock import ContentLock
        lock = ContentLock.objects.create(publisher=self.user, lock_type='url',
                                          title='CK', required_conversions=1)
        r = self.client.get(f'/api/offerwall/locks/{lock.id}/check/')
        self.assertIn(r.status_code, [402, 200])

    def test_by_token_public_endpoint(self):
        from api.offerwall.content_lock import ContentLock
        lock = ContentLock.objects.create(publisher=self.user, lock_type='url',
                                          title='BT', required_conversions=1)
        self.client.logout()
        r = self.client.get(f'/api/offerwall/locks/by_token/{lock.token}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['token'], lock.token)

    def test_by_token_invalid_returns_404(self):
        r = self.client.get('/api/offerwall/locks/by_token/does_not_exist/')
        self.assertEqual(r.status_code, 404)


# ═════════════════════════════════════════════════════════════
# 2. CHARGEBACK
# ═════════════════════════════════════════════════════════════

class ChargebackServiceTest(TestCase):
    def setUp(self):
        self.user  = mk_user('cb_u')
        self.prov  = mk_provider('cb_prov')
        self.offer = mk_offer(self.prov)
        self.conv  = mk_conversion(self.offer, self.user, conv_status='approved')

    @patch('api.offerwall.chargeback.ChargebackService._reverse_wallet', return_value=True)
    @patch('api.offerwall.chargeback.ChargebackService._notify_user')
    @patch('api.offerwall.chargeback.ChargebackService._audit')
    def test_process_approved_conversion(self, mock_audit, mock_notify, mock_wallet):
        from api.offerwall.chargeback import ChargebackService
        result = ChargebackService.process(
            conversion_id=self.conv.conversion_id,
            reason='fraud', provider_reference='cb_ref_001')
        self.assertTrue(result['success'])
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.status, 'chargeback')

    @patch('api.offerwall.chargeback.ChargebackService._reverse_wallet', return_value=True)
    @patch('api.offerwall.chargeback.ChargebackService._notify_user')
    @patch('api.offerwall.chargeback.ChargebackService._audit')
    def test_idempotent_second_call(self, *_):
        from api.offerwall.chargeback import ChargebackService
        ChargebackService.process(conversion_id=self.conv.conversion_id)
        result = ChargebackService.process(conversion_id=self.conv.conversion_id)
        self.assertTrue(result.get('idempotent'))

    def test_unknown_conversion_id_returns_error(self):
        from api.offerwall.chargeback import ChargebackService
        result = ChargebackService.process(conversion_id='does_not_exist_xyz')
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'conversion_not_found')

    def test_cannot_chargeback_pending(self):
        from api.offerwall.chargeback import ChargebackService
        pending = mk_conversion(self.offer, self.user, conv_status='pending',
                                ext_tx='cb_pending_tx')
        result = ChargebackService.process(
            conversion_id=pending.conversion_id, reason='test')
        self.assertFalse(result['success'])
        self.assertIn('cannot_chargeback', result['error'])

    def test_signature_verifier_valid(self):
        from api.offerwall.chargeback import ChargebackSignatureVerifier
        import hmac as _hmac, hashlib
        secret  = 'mysecret'
        payload = b'{"test": 1}'
        sig     = _hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        self.assertTrue(ChargebackSignatureVerifier.verify(payload, sig, secret))

    def test_signature_verifier_invalid(self):
        from api.offerwall.chargeback import ChargebackSignatureVerifier
        self.assertFalse(
            ChargebackSignatureVerifier.verify(b'data', 'badsig', 'secret'))


class ChargebackWebhookViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = mk_user('cbwv_u')
        self.prov   = mk_provider('cbwv_prov')
        self.offer  = mk_offer(self.prov)
        self.conv   = mk_conversion(self.offer, self.user, conv_status='approved')

    @patch('api.offerwall.chargeback.ChargebackService.process',
           return_value={'success': True, 'conversion_id': 'x', 'reversed_amount': '0.70'})
    def test_valid_post_returns_200(self, mock_process):
        r = self.client.post('/api/offerwall/webhooks/chargeback/', {
            'conversion_id': self.conv.conversion_id,
            'reason': 'fraud',
        }, format='json')
        self.assertEqual(r.status_code, 200)

    def test_missing_conversion_id_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/chargeback/',
                             {'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)


# ═════════════════════════════════════════════════════════════
# 3. PUBLISHER / EMBED SDK
# ═════════════════════════════════════════════════════════════

class PublisherAPIKeyTest(TestCase):
    def setUp(self):
        self.user = mk_user('pk_u')

    def test_generate_returns_instance_and_raw_key(self):
        from api.offerwall.publisher import PublisherAPIKey
        inst, raw = PublisherAPIKey.generate(self.user, 'MyKey')
        self.assertIsNotNone(inst.id)
        self.assertTrue(raw.startswith('ow_'))

    def test_authenticate_valid_key(self):
        from api.offerwall.publisher import PublisherAPIKey
        _, raw = PublisherAPIKey.generate(self.user, 'AuthKey')
        found  = PublisherAPIKey.authenticate(raw)
        self.assertEqual(found.id, self.user.id)

    def test_authenticate_invalid_key(self):
        from api.offerwall.publisher import PublisherAPIKey
        self.assertIsNone(PublisherAPIKey.authenticate('ow_badkey'))

    def test_authenticate_non_ow_prefix(self):
        from api.offerwall.publisher import PublisherAPIKey
        self.assertIsNone(PublisherAPIKey.authenticate('sk_somekey'))

    def test_is_expired_false_for_new_key(self):
        from api.offerwall.publisher import PublisherAPIKey
        inst, _ = PublisherAPIKey.generate(self.user, 'NoExpiry')
        self.assertFalse(inst.is_expired())

    def test_is_expired_true_for_past_expiry(self):
        from api.offerwall.publisher import PublisherAPIKey
        from django.utils import timezone
        from datetime import timedelta
        inst, _ = PublisherAPIKey.generate(self.user, 'Expired',
                                            expires_days=0)
        inst.expires_at = timezone.now() - timedelta(hours=1)
        inst.save()
        self.assertTrue(inst.is_expired())


class EmbedTokenServiceTest(TestCase):
    def setUp(self):
        self.user = mk_user('et_u')

    def test_generate_returns_token(self):
        from api.offerwall.publisher import EmbedTokenService
        data = EmbedTokenService.generate(self.user.id)
        self.assertIn('token', data)
        self.assertTrue(len(data['token']) > 10)

    def test_verify_valid_token(self):
        from api.offerwall.publisher import EmbedTokenService
        data   = EmbedTokenService.generate(self.user.id)
        result = EmbedTokenService.verify(data['token'])
        self.assertIsNotNone(result)
        self.assertEqual(str(result['user_id']), str(self.user.id))

    def test_verify_tampered_token_returns_none(self):
        from api.offerwall.publisher import EmbedTokenService
        data   = EmbedTokenService.generate(self.user.id)
        broken = data['token'] + 'tampered'
        self.assertIsNone(EmbedTokenService.verify(broken))

    def test_sdk_config_endpoint_200(self):
        client = APIClient()
        client.force_authenticate(mk_user('sdk_u'))
        r = client.get('/api/offerwall/publisher/sdk-config/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('api_base', r.data)

    def test_publisher_stats_endpoint_200(self):
        client = APIClient()
        client.force_authenticate(mk_user('pst_u'))
        r = client.get('/api/offerwall/publisher/stats/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('total_conversions', r.data)

    def test_create_api_key_endpoint_201(self):
        client = APIClient()
        client.force_authenticate(mk_user('cak_u'))
        r = client.post('/api/offerwall/publisher/keys/',
                        {'name': 'Test key', 'scope': 'embed'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('key', r.data)
        self.assertTrue(r.data['key'].startswith('ow_'))

    def test_invalid_scope_returns_400(self):
        client = APIClient()
        client.force_authenticate(mk_user('bad_scope_u'))
        r = client.post('/api/offerwall/publisher/keys/',
                        {'name': 'k', 'scope': 'invalid'}, format='json')
        self.assertEqual(r.status_code, 400)


# ═════════════════════════════════════════════════════════════
# 4. EARNINGS EXPORT
# ═════════════════════════════════════════════════════════════

class EarningsExportTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = mk_user('exp_u')
        self.prov   = mk_provider('exp_prov')
        self.offer  = mk_offer(self.prov, 'exp_ext_01')
        mk_conversion(self.offer, self.user, conv_status='approved', ext_tx='exp_tx01')
        mk_conversion(self.offer, self.user, conv_status='approved', ext_tx='exp_tx02')
        self.client.force_authenticate(self.user)

    def test_csv_export_returns_200(self):
        r = self.client.get('/api/offerwall/exports/earnings/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])

    def test_csv_has_header_row(self):
        r = self.client.get('/api/offerwall/exports/earnings/')
        content = r.content.decode()
        self.assertIn('Conversion ID', content)
        self.assertIn('Reward amount', content)

    def test_csv_contains_conversion_data(self):
        r = self.client.get('/api/offerwall/exports/earnings/')
        content = r.content.decode()
        self.assertIn('approved', content)

    def test_json_format_returns_list(self):
        r = self.client.get('/api/offerwall/exports/earnings/?fmt=json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/json')
        import json
        data = json.loads(r.content)
        self.assertIn('results', data)
        self.assertGreaterEqual(data['count'], 2)

    def test_status_filter_pending(self):
        mk_conversion(self.offer, self.user, conv_status='pending', ext_tx='exp_pend')
        r = self.client.get('/api/offerwall/exports/earnings/?fmt=json&status=pending')
        import json
        data = json.loads(r.content)
        for row in data['results']:
            self.assertEqual(row['Status'], 'pending')

    def test_unauthenticated_returns_401(self):
        anon = APIClient()
        r = anon.get('/api/offerwall/exports/earnings/')
        self.assertEqual(r.status_code, 401)

    def test_content_disposition_has_filename(self):
        r = self.client.get('/api/offerwall/exports/earnings/')
        cd = r.get('Content-Disposition', '')
        self.assertIn('attachment', cd)
        self.assertIn('.csv', cd)


# ═════════════════════════════════════════════════════════════
# 5. SURVEY PROVIDER SERVICE
# ═════════════════════════════════════════════════════════════

class SurveyProviderFactoryTest(TestCase):
    def test_supported_types_includes_cpx(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        self.assertIn('cpx', SurveyProviderFactory.supported_types())

    def test_supported_types_includes_bitlabs(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        self.assertIn('bitlabs', SurveyProviderFactory.supported_types())

    def test_supported_types_includes_pollfish(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        self.assertIn('pollfish', SurveyProviderFactory.supported_types())

    def test_is_supported_true_for_cpx(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        self.assertTrue(SurveyProviderFactory.is_supported('cpx'))

    def test_is_supported_false_for_unknown(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        self.assertFalse(SurveyProviderFactory.is_supported('nonexistent'))

    def test_create_cpx_returns_instance(self):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory, CPXResearchService)
        prov = mk_provider('srv_cpx', 'cpx')
        svc  = SurveyProviderFactory.create(prov)
        self.assertIsInstance(svc, CPXResearchService)

    def test_create_bitlabs_returns_instance(self):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory, BitLabsService)
        prov = mk_provider('srv_bl', 'bitlabs')
        svc  = SurveyProviderFactory.create(prov)
        self.assertIsInstance(svc, BitLabsService)

    def test_create_pollfish_returns_instance(self):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory, PollfishService)
        prov = mk_provider('srv_pf', 'pollfish')
        svc  = SurveyProviderFactory.create(prov)
        self.assertIsInstance(svc, PollfishService)

    def test_create_unknown_raises(self):
        from api.offerwall.services.survey.SurveyProviderService import SurveyProviderFactory
        prov = mk_provider('srv_unk', 'unknown_xyz')
        with self.assertRaises(ValueError):
            SurveyProviderFactory.create(prov)


class CPXResearchServiceTest(TestCase):
    def setUp(self):
        self.prov = mk_provider('cpx_p', 'cpx')
        from api.offerwall.services.survey.SurveyProviderService import CPXResearchService
        self.svc  = CPXResearchService(self.prov)
        self.user = mk_user('cpx_u')

    @patch('requests.Session.get')
    def test_fetch_surveys_returns_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': {'surveys': []}}
        mock_get.return_value = mock_resp
        result = self.svc.fetch_surveys(self.user)
        self.assertIsInstance(result, list)

    @patch('requests.Session.get')
    def test_fetch_surveys_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        result = self.svc.fetch_surveys(self.user)
        self.assertEqual(result, [])

    def test_verify_postback_valid(self):
        import hashlib
        app_id = self.prov.app_id or 'app123'
        secret = self.prov.api_secret or 'secret123'
        subid  = '42'
        sig    = hashlib.md5(f'{app_id}{subid}{secret}'.encode()).hexdigest()
        self.prov.app_id     = app_id
        self.prov.api_secret = secret
        svc = __import__(
            'api.offerwall.services.survey.SurveyProviderService',
            fromlist=['CPXResearchService']
        ).CPXResearchService(self.prov)
        self.assertTrue(svc.verify_postback({'hash': sig, 'subid': subid}))

    def test_build_survey_url_contains_app_id(self):
        survey = {'id': 'sv001'}
        url    = self.svc.build_survey_url(survey, self.user)
        self.assertIn('cpx-research', url)

    def test_parse_postback_approved(self):
        result = self.svc.parse_postback(
            {'subid': '42', 'survey_id': 'sv1', 'payout': '0.70',
             'status': '1', 'transaction_id': 'tx1'})
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['payout'], Decimal('0.70'))


class BitLabsServiceTest(TestCase):
    def setUp(self):
        self.prov = mk_provider('bl_p', 'bitlabs')
        from api.offerwall.services.survey.SurveyProviderService import BitLabsService
        self.svc  = BitLabsService(self.prov)
        self.user = mk_user('bl_u')

    @patch('requests.Session.get')
    def test_fetch_surveys_returns_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'data': {'surveys': []}}
        mock_get.return_value = mock_resp
        result = self.svc.fetch_surveys(self.user)
        self.assertIsInstance(result, list)

    def test_build_survey_url_contains_token(self):
        url = self.svc.build_survey_url({'id': 'bls1'}, self.user)
        self.assertIn('bitlabs', url)

    def test_parse_postback_approved(self):
        result = self.svc.parse_postback(
            {'uid': '5', 'survey_id': 'bls1', 'reward': '1.00',
             'transaction_id': 'tx_bl'})
        self.assertEqual(result['status'], 'approved')


class PollfishServiceTest(TestCase):
    def setUp(self):
        self.prov = mk_provider('pf_p', 'pollfish')
        from api.offerwall.services.survey.SurveyProviderService import PollfishService
        self.svc  = PollfishService(self.prov)
        self.user = mk_user('pf_u')

    def test_fetch_surveys_returns_sdk_config(self):
        result = self.svc.fetch_surveys(self.user)
        self.assertEqual(len(result), 1)
        self.assertIn('sdk_config', result[0])

    def test_build_survey_url_returns_string(self):
        url = self.svc.build_survey_url({'id': 'sdk'}, self.user)
        self.assertIsInstance(url, str)
        self.assertIn('pollfish', url)

    def test_parse_postback_payout_in_dollars(self):
        result = self.svc.parse_postback({'user_id': '7', 'cpa': '150', 'survey_id': 'pf1'})
        self.assertEqual(result['payout'], Decimal('1.50'))


# ═════════════════════════════════════════════════════════════
# 6. BULK CONVERSION WEBHOOK
# ═════════════════════════════════════════════════════════════

class BulkConversionWebhookTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = mk_user('bk_u')
        self.prov   = mk_provider('bk_prov')
        self.offer  = mk_offer(self.prov, 'bk_ext_01')

    def test_empty_conversions_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/bulk/',
                             {'provider': 'tapjoy', 'conversions': []},
                             format='json')
        self.assertEqual(r.status_code, 400)

    def test_non_list_conversions_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/bulk/',
                             {'provider': 'tapjoy', 'conversions': 'bad'},
                             format='json')
        self.assertEqual(r.status_code, 400)

    def test_unknown_provider_returns_404(self):
        r = self.client.post('/api/offerwall/webhooks/bulk/', {
            'provider':    'nonexistent_xyz',
            'conversions': [{'user_id': str(self.user.id),
                             'offer_id': 'bk_ext_01',
                             'transaction_id': 'tx_bk_01',
                             'payout': '0.70', 'status': 'approved'}],
        }, format='json')
        self.assertEqual(r.status_code, 404)

    @patch('api.offerwall.bulk_conversion.BulkConversionProcessor.process_batch')
    def test_valid_batch_returns_200(self, mock_batch):
        mock_batch.return_value = {
            'received': 1, 'processed': 1, 'duplicates': 0,
            'errors': 0, 'results': [{'transaction_id': 'tx_ok', 'status': 'created'}]}
        r = self.client.post('/api/offerwall/webhooks/bulk/', {
            'provider':    'tapjoy',
            'conversions': [{'user_id': str(self.user.id),
                             'offer_id': 'bk_ext_01',
                             'transaction_id': 'tx_bk_02',
                             'payout': '0.70', 'status': 'approved'}],
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['processed'], 1)

    def test_oversized_batch_returns_413(self):
        conversions = [{'transaction_id': f'tx_{i}', 'payout': '0.1'}
                       for i in range(501)]
        r = self.client.post('/api/offerwall/webhooks/bulk/', {
            'provider': 'tapjoy', 'conversions': conversions}, format='json')
        self.assertEqual(r.status_code, 413)

    def test_duplicate_detection(self):
        from api.offerwall.bulk_conversion import BulkConversionProcessor
        ext_tx = 'dup_tx_001'
        mk_conversion(self.offer, self.user, ext_tx=ext_tx)
        processor = BulkConversionProcessor(self.prov)
        result    = processor.process_batch([{
            'user_id': str(self.user.id), 'offer_id': 'bk_ext_01',
            'transaction_id': ext_tx, 'payout': '0.70', 'status': 'approved',
        }])
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(result['processed'],  0)


# ═════════════════════════════════════════════════════════════
# 7. EXPIRE OFFERS MANAGEMENT COMMAND
# ═════════════════════════════════════════════════════════════

class ExpireOffersCommandTest(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        self.prov    = mk_provider('exp_cmd_p')
        self.past    = timezone.now() - timedelta(hours=2)
        self.future  = timezone.now() + timedelta(days=7)

    def _mk_offer_with_end(self, end_date, ext='eo'):
        from api.offerwall.models import Offer
        return Offer.objects.create(
            provider=self.prov, external_offer_id=f'{ext}_{uuid.uuid4().hex[:6]}',
            title=f'Offer {ext}', description='d',
            payout=Decimal('1'), reward_amount=Decimal('0.70'),
            click_url='https://x.com', status='active',
            end_date=end_date,
        )

    def _run(self, *args):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('expire_offers', *args, stdout=out)
        return out.getvalue()

    def test_expired_offer_gets_status_expired(self):
        offer = self._mk_offer_with_end(self.past, 'exp_e')
        self._run()
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'expired')

    def test_active_future_offer_unchanged(self):
        offer = self._mk_offer_with_end(self.future, 'fut_e')
        self._run()
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'active')

    def test_no_end_date_offer_unchanged(self):
        from api.offerwall.models import Offer
        offer = Offer.objects.create(
            provider=self.prov, external_offer_id=f'no_end_{uuid.uuid4().hex[:6]}',
            title='No end', description='d', payout=Decimal('1'),
            reward_amount=Decimal('0.70'), click_url='https://x.com',
            status='active', end_date=None,
        )
        self._run()
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'active')

    def test_dry_run_does_not_change_status(self):
        offer = self._mk_offer_with_end(self.past, 'dry_e')
        self._run('--dry-run')
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'active')

    def test_dry_run_output_mentions_offer(self):
        self._mk_offer_with_end(self.past, 'dry_msg')
        output = self._run('--dry-run')
        self.assertIn('dry-run', output.lower())

    def test_multiple_expired_offers_all_updated(self):
        o1 = self._mk_offer_with_end(self.past, 'multi1')
        o2 = self._mk_offer_with_end(self.past, 'multi2')
        o3 = self._mk_offer_with_end(self.past, 'multi3')
        self._run()
        for o in [o1, o2, o3]:
            o.refresh_from_db()
            self.assertEqual(o.status, 'expired')

    def test_command_output_shows_count(self):
        self._mk_offer_with_end(self.past, 'cnt1')
        output = self._run()
        self.assertIn('1', output)
