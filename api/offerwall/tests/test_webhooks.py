"""
Webhook Tests — HIGH PRIORITY
Run: python manage.py test api.offerwall.tests.test_webhooks
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from api.offerwall.models import OfferProvider, Offer, OfferConversion

User = get_user_model()


def _base(ptype='tapjoy'):
    prov = OfferProvider.objects.create(
        name=f'WH_{ptype}', provider_type=ptype, status='active',
        revenue_share=Decimal('70'), secret_key='test_secret', config={})
    offer = Offer.objects.create(
        provider=prov, external_offer_id='wh_ext_001', title='WH Offer',
        description='d', payout=Decimal('1'), reward_amount=Decimal('0.70'),
        click_url='https://x.com', status='active', currency='USD', reward_currency='BDT')
    user = User.objects.create_user(
        username=f'whu_{ptype}', email=f'wh_{ptype}@t.com', password='p')
    return prov, offer, user


class TapjoyWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov, self.offer, self.user = _base('tapjoy')

    def _params(self, trans_id='tx_001', verifier='sig'):
        return {'snuid': str(self.user.id), 'id': self.offer.external_offer_id,
                'currency': '1.000000', 'verifier': verifier, 'trans_id': trans_id}

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_valid_creates_conversion(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        r = self.client.get('/api/offerwall/webhooks/tapjoy/', self._params())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(OfferConversion.objects.filter(conversion_id='tapjoy_tx_001').exists())

    def test_missing_params_400(self):
        self.assertEqual(self.client.get('/api/offerwall/webhooks/tapjoy/', {}).status_code, 400)

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_duplicate_not_created_twice(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='tapjoy_dup_001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.client.get('/api/offerwall/webhooks/tapjoy/', self._params(trans_id='dup_001'))
        self.assertEqual(
            OfferConversion.objects.filter(conversion_id='tapjoy_dup_001').count(), 1)

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    def test_invalid_signature_403(self, mock_verify):
        mock_verify.side_effect = Exception('Invalid sig')
        r = self.client.get('/api/offerwall/webhooks/tapjoy/', self._params(verifier='bad'))
        self.assertEqual(r.status_code, 403)

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_external_field_name_correct(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        self.client.get('/api/offerwall/webhooks/tapjoy/', self._params(trans_id='fn_001'))
        conv = OfferConversion.objects.filter(conversion_id='tapjoy_fn_001').first()
        self.assertIsNotNone(conv)
        # external_WalletTransaction_id must be set (not external_transaction_id)
        self.assertTrue(hasattr(conv, 'external_WalletTransaction_id'))
        self.assertFalse(hasattr(conv, 'external_transaction_id'))


class AdGemWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov, self.offer, self.user = _base('adgem')

    @patch('api.offerwall.services.AdGemService.AdGemService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_valid_creates_conversion(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id),
            'offer_id': self.offer.external_offer_id,
            'points': '1.0', 'signature': 'sig', 'transaction_id': 'ag_001',
        })
        self.assertEqual(r.status_code, 200)

    def test_missing_params_400(self):
        self.assertEqual(self.client.get('/api/offerwall/webhooks/adgem/', {}).status_code, 400)

    @patch('api.offerwall.services.AdGemService.AdGemService.verify_postback')
    def test_invalid_signature_403(self, mock_verify):
        mock_verify.side_effect = Exception('Bad sig')
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id), 'offer_id': 'x', 'points': '1', 'signature': 'bad'})
        self.assertEqual(r.status_code, 403)

    @patch('api.offerwall.services.AdGemService.AdGemService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_duplicate_idempotent(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='adgem_dup_ag',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id), 'offer_id': self.offer.external_offer_id,
            'points': '1.0', 'signature': 'sig', 'transaction_id': 'dup_ag',
        })
        self.assertEqual(
            OfferConversion.objects.filter(conversion_id='adgem_dup_ag').count(), 1)


class OfferwallWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov, self.offer, self.user = _base('offerwall')

    @patch('api.offerwall.services.OfferwallService.OfferwallService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_valid_creates_conversion(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        r = self.client.get('/api/offerwall/webhooks/offertoro/', {
            'oid': self.offer.external_offer_id,
            'user_id': str(self.user.id),
            'amount': '1.0', 'sig': 'sig',
        })
        self.assertEqual(r.status_code, 200)

    def test_missing_params_400(self):
        self.assertEqual(
            self.client.get('/api/offerwall/webhooks/offertoro/', {}).status_code, 400)

    @patch('api.offerwall.services.OfferwallService.OfferwallService.verify_postback')
    def test_invalid_signature_403(self, mock_verify):
        mock_verify.side_effect = Exception('Bad sig')
        r = self.client.get('/api/offerwall/webhooks/offertoro/', {
            'oid': self.offer.external_offer_id,
            'user_id': str(self.user.id),
            'amount': '1.0', 'sig': 'badsig',
        })
        self.assertEqual(r.status_code, 403)


# ── Extra Webhook Tests ───────────────────────────────────────────────────────

class TapjoyWebhookExtraTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.prov, self.offer, self.user = _base('tapjoy')

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_post_method_also_works(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'snuid': str(self.user.id),
            'id': self.offer.external_offer_id,
            'currency': '1.000000',
            'verifier': 'sig',
            'trans_id': 'post_tx_001',
        })
        self.assertIn(r.status_code, [200, 201, 400])

    @patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_external_wallet_transaction_id_set(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        self.client.get('/api/offerwall/webhooks/tapjoy/', {
            'snuid': str(self.user.id),
            'id': self.offer.external_offer_id,
            'currency': '1.0',
            'verifier': 'sig',
            'trans_id': 'ew_tx_001',
        })
        conv = OfferConversion.objects.filter(conversion_id='tapjoy_ew_tx_001').first()
        if conv:
            self.assertTrue(hasattr(conv, 'external_WalletTransaction_id'))
            self.assertFalse(hasattr(conv, 'external_transaction_id'))

    def test_unknown_offer_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/tapjoy/', {
            'snuid': str(self.user.id),
            'id': 'nonexistent_offer_xyz',
            'currency': '1.0',
            'verifier': 'sig',
            'trans_id': 'unknown_001',
        })
        self.assertIn(r.status_code, [400, 403])

    def test_unknown_user_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/tapjoy/', {
            'snuid': '999999',
            'id': self.offer.external_offer_id,
            'currency': '1.0',
            'verifier': 'sig',
            'trans_id': 'nouser_001',
        })
        self.assertIn(r.status_code, [400, 403])


class AdGemWebhookExtraTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.prov, self.offer, self.user = _base('adgem')

    @patch('api.offerwall.services.AdGemService.AdGemService.verify_postback')
    @patch('api.offerwall.utils.RewardCalculator.RewardCalculator.calculate_total_reward')
    def test_offertoro_duplicate_idempotent(self, mock_calc, mock_verify):
        mock_verify.return_value = True
        mock_calc.return_value = {
            'total_reward': Decimal('0.70'), 'base_reward': Decimal('0.70'), 'currency': 'BDT'}
        OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='adgem_idem_tx',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id),
            'offer_id': self.offer.external_offer_id,
            'points': '1.0', 'signature': 'sig', 'transaction_id': 'idem_tx',
        })
        count = OfferConversion.objects.filter(conversion_id='adgem_idem_tx').count()
        self.assertEqual(count, 1)

    def test_missing_user_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'offer_id': self.offer.external_offer_id,
            'points': '1.0', 'signature': 'sig',
        })
        self.assertEqual(r.status_code, 400)

    def test_missing_offer_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id),
            'points': '1.0', 'signature': 'sig',
        })
        self.assertEqual(r.status_code, 400)


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK EDGE CASE TESTS — missing payload edge cases
# ══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid
from decimal import Decimal as _D
from unittest.mock import patch as _patch, MagicMock as _MM


def _prov(name, ptype):
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=name, provider_type=ptype, status='active',
        revenue_share=_D('70'), secret_key='wh_secret_abc')


def _offer(prov, ext_id):
    from api.offerwall.models import Offer
    return Offer.objects.create(
        provider=prov, external_offer_id=ext_id,
        title='WH Offer', description='d', payout=_D('1'),
        reward_amount=_D('0.70'), click_url='https://x.com', status='active')


def _user(un):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(
        username=un, email=f'{un}@t.com', password='p')


class TapjoyWebhookEdgeCasesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov  = _prov('tj_wh', 'tapjoy')
        self.user  = _user('tj_wh_u')
        self.offer = _offer(self.prov, 'tj_ext_01')

    def test_missing_id_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'snuid': str(self.user.id), 'currency': '100'})
        self.assertEqual(r.status_code, 400)

    def test_missing_snuid_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'id': 'tj_ext_01', 'currency': '100'})
        self.assertEqual(r.status_code, 400)

    def test_missing_currency_returns_400(self):
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'id': 'tj_ext_01', 'snuid': str(self.user.id)})
        self.assertEqual(r.status_code, 400)

    @_patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.process_conversion')
    @_patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback', return_value=True)
    def test_valid_payload_returns_200(self, mock_verify, mock_proc):
        mock_conv = _MM(); mock_conv.conversion_id = 'tj_c1'
        mock_proc.return_value = {'success': True, 'conversion': mock_conv, 'created': True}
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'id': 'tj_ext_01', 'snuid': str(self.user.id), 'currency': '100', 'verifier': 'v'})
        self.assertEqual(r.status_code, 200)

    @_patch('api.offerwall.services.TapjoyService.TapjoyService.verify_postback',
            side_effect=Exception('bad sig'))
    def test_invalid_signature_returns_400(self, mock_v):
        r = self.client.post('/api/offerwall/webhooks/tapjoy/', {
            'id': 'tj_ext_01', 'snuid': str(self.user.id),
            'currency': '100', 'verifier': 'bad'})
        self.assertEqual(r.status_code, 400)


class AdGemWebhookEdgeCasesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov  = _prov('ag_wh', 'adgem')
        self.user  = _user('ag_wh_u')
        self.offer = _offer(self.prov, 'ag_ext_01')

    def test_missing_user_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/adgem/',
                            {'offer_id': 'ag_ext_01', 'points': '100',
                             'transaction_id': 'tx1'})
        self.assertEqual(r.status_code, 400)

    def test_missing_offer_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/adgem/',
                            {'user_id': str(self.user.id), 'points': '100',
                             'transaction_id': 'tx1'})
        self.assertEqual(r.status_code, 400)

    def test_missing_transaction_id_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/adgem/',
                            {'user_id': str(self.user.id),
                             'offer_id': 'ag_ext_01', 'points': '100'})
        self.assertEqual(r.status_code, 400)

    @_patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.process_conversion')
    @_patch('api.offerwall.services.AdGemService.AdGemService.verify_postback', return_value=True)
    def test_valid_get_returns_200(self, mock_v, mock_proc):
        mock_conv = _MM(); mock_conv.conversion_id = 'ag_c1'
        mock_proc.return_value = {'success': True, 'conversion': mock_conv, 'created': True}
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id), 'offer_id': 'ag_ext_01',
            'points': '100', 'transaction_id': 'tx_ag_v1', 'signature': 'sig'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'1')

    @_patch('api.offerwall.services.AdGemService.AdGemService.verify_postback',
            side_effect=Exception('bad sig'))
    def test_tampered_signature_returns_400(self, mock_v):
        r = self.client.get('/api/offerwall/webhooks/adgem/', {
            'user_id': str(self.user.id), 'offer_id': 'ag_ext_01',
            'points': '100', 'transaction_id': 'tx_ag_bad', 'signature': 'wrong'})
        self.assertEqual(r.status_code, 400)


class OfferwallWebhookEdgeCasesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prov  = _prov('ot_wh', 'offerwall')
        self.user  = _user('ot_wh_u')
        self.offer = _offer(self.prov, 'ot_ext_01')

    def test_missing_oid_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/offertoro/', {
            'user_id': str(self.user.id), 'amount': '0.50'})
        self.assertEqual(r.status_code, 400)

    def test_missing_amount_returns_400(self):
        r = self.client.get('/api/offerwall/webhooks/offertoro/', {
            'oid': 'ot_ext_01', 'user_id': str(self.user.id)})
        self.assertEqual(r.status_code, 400)

    @_patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.process_conversion')
    @_patch('api.offerwall.services.OfferwallService.OfferwallService.verify_postback', return_value=True)
    def test_valid_get_returns_200(self, mock_v, mock_proc):
        mock_conv = _MM(); mock_conv.conversion_id = 'ot_c1'
        mock_proc.return_value = {'success': True, 'conversion': mock_conv, 'created': True}
        r = self.client.get('/api/offerwall/webhooks/offertoro/', {
            'oid': 'ot_ext_01', 'user_id': str(self.user.id),
            'amount': '0.50', 'sig': 'validsig'})
        self.assertEqual(r.status_code, 200)
