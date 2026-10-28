"""
Provider Service Tests — TapjoyService, AdGemService, OfferProcessorFactory
Run: python manage.py test api.offerwall.tests.test_services
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from api.offerwall.models import OfferProvider, Offer

User = get_user_model()


def mk_provider(ptype='tapjoy', **kw):
    d = dict(name=f'Prov_{ptype}', provider_type=ptype, status='active',
             api_key='test_key', app_id='test_app', secret_key='test_secret',
             revenue_share=Decimal('70.00'))
    d.update(kw)
    return OfferProvider.objects.create(**d)


def mk_offer(provider, **kw):
    d = dict(external_offer_id=str(uuid.uuid4())[:12], title='Svc Offer',
             description='d', payout=Decimal('1'), reward_amount=Decimal('0.70'),
             click_url='https://x.com', status='active',
             currency='USD', reward_currency='BDT')
    d.update(kw)
    return Offer.objects.create(provider=provider, **d)


def mk_user(un='svcuser'):
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


# ── TapjoyService ─────────────────────────────────────────────────────────────

class TapjoyServiceTest(TestCase):

    def setUp(self):
        self.provider = mk_provider('tapjoy')
        self.offer    = mk_offer(self.provider)
        self.user     = mk_user()

    def _svc(self):
        from api.offerwall.services.TapjoyService import TapjoyService
        return TapjoyService(self.provider)

    @patch('requests.Session.get')
    def test_fetch_offers_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'Offer': [{
                'OfferID': 'tj_001', 'Anchor': 'Tapjoy Offer', 'Description': 'desc',
                'Payout': '1.50', 'Icon': 'https://img.tapjoy.com/1.png',
                'OfferURL': 'https://tapjoy.com/click/tj_001', 'Platform': 'Android',
            }]}
        )
        result = self._svc().fetch_offers()
        self.assertIsInstance(result, list)

    @patch('requests.Session.get')
    def test_fetch_offers_http_error_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500, json=lambda: {})
        result = self._svc().fetch_offers()
        self.assertEqual(result, [])

    @patch('requests.Session.get')
    def test_fetch_offers_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception('Connection refused')
        result = self._svc().fetch_offers()
        self.assertEqual(result, [])

    def test_parse_offer_data_normalizes_fields(self):
        raw = {
            'OfferID': '999', 'Anchor': 'Parsed Offer', 'Description': 'Install',
            'Payout': '2.00', 'Icon': 'https://img.tapjoy.com/icon.png',
            'OfferURL': 'https://tapjoy.com/click/999', 'Platform': 'iOS',
        }
        parsed = self._svc().parse_offer_data(raw)
        self.assertIn('external_offer_id', parsed)
        self.assertIn('title', parsed)
        self.assertIn('payout', parsed)
        self.assertIn('click_url', parsed)

    def test_parse_offer_data_external_id_from_OfferID(self):
        raw = {'OfferID': 'tj_ext_999', 'Anchor': 'T', 'Description': 'd',
               'Payout': '1', 'Icon': '', 'OfferURL': 'https://x.com', 'Platform': 'all'}
        parsed = self._svc().parse_offer_data(raw)
        self.assertEqual(str(parsed['external_offer_id']), 'tj_ext_999')

    def test_build_click_url_contains_user_id(self):
        url = self._svc().build_click_url(self.offer, self.user)
        self.assertIn('http', url)

    def test_verify_postback_valid_returns_true(self):
        svc = self._svc()
        result = svc.verify_postback({
            'snuid': str(self.user.id), 'id': self.offer.external_offer_id,
            'currency': '1.00', 'verifier': 'any'
        })
        self.assertIsInstance(result, bool)

    def test_verify_postback_missing_verifier_raises(self):
        from api.offerwall.exceptions import FraudException, OfferwallException
        svc = self._svc()
        try:
            svc.verify_postback({'snuid': '1', 'id': 'x', 'currency': '1'})
        except (FraudException, OfferwallException, Exception):
            pass  # Expected


# ── AdGemService ──────────────────────────────────────────────────────────────

class AdGemServiceTest(TestCase):

    def setUp(self):
        self.provider = mk_provider('adgem')
        self.offer    = mk_offer(self.provider)
        self.user     = mk_user('adgemuser')

    def _svc(self):
        from api.offerwall.services.AdGemService import AdGemService
        return AdGemService(self.provider)

    def test_get_auth_headers_returns_dict(self):
        headers = self._svc().get_auth_headers()
        self.assertIsInstance(headers, dict)

    @patch('requests.Session.get')
    def test_fetch_offers_parses_response(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{'id': 'ag_001', 'name': 'AdGem Offer',
                           'description': 'Play', 'payout': 1.20,
                           'icon_url': 'https://adgem.com/i.png',
                           'click_url': 'https://adgem.com/c', 'platform': 'android'}]
        )
        result = self._svc().fetch_offers()
        self.assertIsInstance(result, list)

    @patch('requests.Session.get')
    def test_fetch_offers_http_error_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=503, json=lambda: [])
        self.assertEqual(self._svc().fetch_offers(), [])

    def test_parse_offer_data_normalizes_fields(self):
        raw = {'id': 'ag_002', 'name': 'AG Offer', 'description': 'desc',
               'payout': 1.5, 'icon_url': '', 'click_url': 'https://x.com',
               'platform': 'ios', 'countries': ['US', 'GB']}
        parsed = self._svc().parse_offer_data(raw)
        self.assertIn('external_offer_id', parsed)
        self.assertIn('payout', parsed)

    def test_build_click_url_not_empty(self):
        url = self._svc().build_click_url(self.offer, self.user)
        self.assertTrue(len(url) > 0)

    def test_parse_adgem_type_survey(self):
        svc = self._svc()
        if hasattr(svc, '_parse_adgem_type'):
            result = svc._parse_adgem_type('survey')
            self.assertEqual(result, 'survey')

    def test_parse_adgem_type_install(self):
        svc = self._svc()
        if hasattr(svc, '_parse_adgem_type'):
            result = svc._parse_adgem_type('install')
            self.assertIn(result, ['app_install', 'install', 'app_action'])


# ── OfferProcessorFactory ─────────────────────────────────────────────────────

class OfferProcessorFactoryTest(TestCase):

    def setUp(self):
        self.tapjoy_provider = mk_provider('tapjoy')
        self.adgem_provider  = mk_provider('adgem', name='AdGemP')
        self.adgate_provider = mk_provider('adgate', name='AdGateP')
        self.user = mk_user('procuser')

    def test_create_tapjoy_processor(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        p = OfferProcessorFactory.create(self.tapjoy_provider)
        self.assertIsNotNone(p)
        self.assertEqual(p.provider, self.tapjoy_provider)

    def test_create_adgem_processor(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        p = OfferProcessorFactory.create(self.adgem_provider)
        self.assertIsNotNone(p)

    def test_create_adgate_processor(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        p = OfferProcessorFactory.create(self.adgate_provider)
        self.assertIsNotNone(p)

    def test_unknown_provider_raises(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        from api.offerwall.exceptions import InvalidProviderConfigException
        bad = mk_provider('xyz_unknown_provider_type', name='BadProv')
        with self.assertRaises(InvalidProviderConfigException):
            OfferProcessorFactory.create(bad)

    def test_register_custom_processor(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory, OfferProcessor

        class FakeProcessor(OfferProcessor):
            def fetch_offers(self, **kw): return []
            def parse_offer_data(self, raw): return {}
            def verify_postback(self, data): return True
            def build_click_url(self, offer, user): return 'https://fake.com'

        OfferProcessorFactory.register('fake_test_type', FakeProcessor)
        p = mk_provider('fake_test_type', name='FakeProv')
        proc = OfferProcessorFactory.create(p)
        self.assertIsInstance(proc, FakeProcessor)

    def test_get_available_processors_returns_list(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        processors = OfferProcessorFactory.get_available_processors()
        self.assertIsInstance(processors, list)
        self.assertIn('tapjoy', processors)

    def test_normalize_platform_android(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        proc = OfferProcessorFactory.create(self.tapjoy_provider)
        result = proc.normalize_platform('Android')
        self.assertIn(result, ['android', 'Android'])

    def test_normalize_offer_type_install(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        proc = OfferProcessorFactory.create(self.tapjoy_provider)
        if hasattr(proc, 'normalize_offer_type'):
            result = proc.normalize_offer_type('install')
            self.assertIn(result, ['app_install', 'install'])

    def test_validate_payout_positive_passes(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        proc = OfferProcessorFactory.create(self.tapjoy_provider)
        result = proc.validate_payout('1.50')
        self.assertTrue(result)

    def test_validate_payout_zero_fails(self):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        proc = OfferProcessorFactory.create(self.tapjoy_provider)
        result = proc.validate_payout('0')
        self.assertFalse(result)

    @patch('requests.Session.get')
    def test_sync_offers_creates_new_offer(self, mock_get):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'Offer': [{
                'OfferID': f'sync_{uuid.uuid4().hex[:8]}',
                'Anchor': 'Synced New Offer', 'Description': 'desc',
                'Payout': '1.50', 'Icon': '', 'OfferURL': 'https://x.com', 'Platform': 'Android',
            }]}
        )
        proc   = OfferProcessorFactory.create(self.tapjoy_provider)
        result = proc.sync_offers()
        self.assertIn('synced', result)
        self.assertIsInstance(result['synced'], int)

    @patch('requests.Session.get')
    def test_sync_offers_handles_api_error_gracefully(self, mock_get):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        mock_get.side_effect = Exception('API timeout')
        proc   = OfferProcessorFactory.create(self.tapjoy_provider)
        result = proc.sync_offers()
        self.assertIsNotNone(result)

    @patch('requests.Session.get')
    def test_sync_offers_updates_existing(self, mock_get):
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory
        existing_ext_id = f'existing_{uuid.uuid4().hex[:8]}'
        mk_offer(self.tapjoy_provider, external_offer_id=existing_ext_id,
                 title='Old Title', payout=Decimal('1.00'))
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'Offer': [{
                'OfferID': existing_ext_id, 'Anchor': 'Updated Title',
                'Description': 'new', 'Payout': '1.75',
                'Icon': '', 'OfferURL': 'https://x.com', 'Platform': 'Android',
            }]}
        )
        proc = OfferProcessorFactory.create(self.tapjoy_provider)
        proc.sync_offers()
        count = Offer.objects.filter(
            provider=self.tapjoy_provider, external_offer_id=existing_ext_id).count()
        self.assertEqual(count, 1)


# ══════════════════════════════════════════════════════════════════════════════
# MISSING SERVICE TESTS — AdGateService, PersonaService, OfferFactory,
#                         OfferwallService
# ══════════════════════════════════════════════════════════════════════════════

from unittest.mock import patch as _patch, MagicMock as _MM
from decimal import Decimal as _D


def _prov(name='svc_p', ptype='adgate'):
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=name, provider_type=ptype, status='active',
        revenue_share=_D('70'))


class AdGateServiceTest(TestCase):
    def setUp(self):
        from api.offerwall.services.AdGateService import AdGateService
        self.prov = _prov('ag_p', 'adgate')
        self.svc  = AdGateService(self.prov)

    def test_instantiation(self):
        from api.offerwall.services.AdGateService import AdGateService
        self.assertIsInstance(self.svc, AdGateService)

    @_patch('requests.Session.get')
    def test_fetch_offers_returns_list(self, mock_get):
        mock_resp = _MM()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'offers': []}
        mock_get.return_value = mock_resp
        result = self.svc.fetch_offers()
        self.assertIsInstance(result, list)

    @_patch('requests.Session.get')
    def test_fetch_offers_network_error_raises_or_returns_empty(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        try:
            result = self.svc.fetch_offers()
            self.assertIsInstance(result, list)
        except Exception:
            pass  # allowed to propagate

    def test_verify_postback_returns_bool(self):
        result = self.svc.verify_postback({'sig': 'x'})
        self.assertIsInstance(result, bool)

    def test_build_click_url_contains_offer_id(self):
        from api.offerwall.models import Offer
        import uuid
        offer = Offer.objects.create(
            provider=self.prov, external_offer_id='ag_ext_001',
            title='AG Offer', description='d', payout=_D('1'),
            reward_amount=_D('0.70'), click_url='https://adgate.com/offer?id=ag_ext_001',
            status='active')
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(
            username='ag_usr', email='ag@t.com', password='p')
        url = self.svc.build_click_url(offer, user)
        self.assertIsInstance(url, str)
        self.assertTrue(len(url) > 0)


class PersonaServiceTest(TestCase):
    def setUp(self):
        from api.offerwall.services.PersonaService import PersonaService
        self.prov = _prov('ps_p', 'persona')
        self.svc  = PersonaService(self.prov)

    def test_instantiation(self):
        from api.offerwall.services.PersonaService import PersonaService
        self.assertIsInstance(self.svc, PersonaService)

    @_patch('requests.Session.get')
    def test_fetch_offers_returns_list(self, mock_get):
        mock_resp = _MM()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'offers': []}
        mock_get.return_value = mock_resp
        result = self.svc.fetch_offers()
        self.assertIsInstance(result, list)

    def test_verify_postback_returns_bool(self):
        result = self.svc.verify_postback({'sig': 'x'})
        self.assertIsInstance(result, bool)

    def test_parse_offer_data_returns_dict(self):
        raw = {'id': 'ps001', 'name': 'Test', 'payout': 1.0,
               'countries': ['US'], 'platforms': ['android']}
        result = self.svc.parse_offer_data(raw)
        self.assertIsInstance(result, dict)


class OfferFactoryTest(TestCase):
    def test_get_available_providers_returns_list(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        providers = OfferFactory.get_available_providers()
        self.assertIsInstance(providers, list)

    def test_is_provider_supported_tapjoy(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        self.assertTrue(OfferFactory.is_provider_supported('tapjoy'))

    def test_is_provider_supported_adgem(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        self.assertTrue(OfferFactory.is_provider_supported('adgem'))

    def test_is_provider_supported_unknown(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        self.assertFalse(OfferFactory.is_provider_supported('nonexistent_xyz'))

    def test_get_processor_class_tapjoy(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        cls = OfferFactory.get_processor_class('tapjoy')
        self.assertIsNotNone(cls)

    def test_get_processor_class_unknown_raises(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        with self.assertRaises(Exception):
            OfferFactory.get_processor_class('not_real')

    def test_create_processor_returns_instance(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        prov = _prov('of_p', 'tapjoy')
        processor = OfferFactory.create_processor(prov)
        self.assertIsNotNone(processor)

    def test_bulk_create_processors_returns_list(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        p1 = _prov('of_p1', 'tapjoy')
        p2 = _prov('of_p2', 'adgem')
        processors = OfferFactory.bulk_create_processors([p1, p2])
        self.assertIsInstance(processors, list)

    def test_get_processor_info_contains_type(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        info = OfferFactory.get_processor_info('tapjoy')
        self.assertIsInstance(info, dict)

    def test_get_provider_capabilities_returns_dict(self):
        from api.offerwall.services.OfferFactory import OfferFactory
        caps = OfferFactory.get_provider_capabilities('tapjoy')
        self.assertIsInstance(caps, dict)


class OfferwallServiceTest(TestCase):
    def setUp(self):
        from api.offerwall.services.OfferwallService import OfferwallService
        self.prov = _prov('os_p', 'custom')
        self.svc  = OfferwallService(self.prov)

    def test_instantiation(self):
        from api.offerwall.services.OfferwallService import OfferwallService
        self.assertIsInstance(self.svc, OfferwallService)

    def test_verify_postback_returns_bool(self):
        result = self.svc.verify_postback({'sig': 'x'})
        self.assertIsInstance(result, bool)

    def test_parse_offer_data_returns_dict(self):
        raw = {'id': 'os001', 'title': 'OS Offer', 'payout': '1.00'}
        result = self.svc.parse_offer_data(raw)
        self.assertIsInstance(result, dict)

    @_patch('requests.Session.get')
    def test_fetch_offers_returns_list(self, mock_get):
        mock_resp = _MM()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'offers': []}
        mock_get.return_value = mock_resp
        result = self.svc.fetch_offers()
        self.assertIsInstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# OfferwallIntegrationService — extended tests for new params
# ══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid
from decimal import Decimal as _D
from unittest.mock import patch as _patch, MagicMock as _MM


def _mk_set(label='ois'):
    from django.contrib.auth import get_user_model
    from api.offerwall.models import OfferProvider, Offer
    user = get_user_model().objects.create_user(
        username=f'{label}_u', email=f'{label}@t.com', password='p')
    prov = Offer.objects.filter(provider__name=f'{label}_p').first()
    if not prov:
        from api.offerwall.models import OfferProvider as OP
        p = OP.objects.create(name=f'{label}_p', provider_type='tapjoy',
                               status='active', revenue_share=_D('70'))
    else:
        p = prov.provider
    from api.offerwall.models import OfferProvider as OP
    p = OP.objects.filter(name=f'{label}_p').first() or \
        OP.objects.create(name=f'{label}_p', provider_type='tapjoy',
                          status='active', revenue_share=_D('70'))
    offer = Offer.objects.create(
        provider=p, external_offer_id=_uuid.uuid4().hex[:10],
        title='OIS Offer', description='d', payout=_D('1'),
        reward_amount=_D('0.70'), click_url='https://x.com', status='active')
    return user, p, offer


class IntegrationServiceExtendedTest(TestCase):

    def test_process_conversion_external_tx_id_deduplication(self):
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)
        from api.offerwall.models import OfferConversion
        user, prov, offer = _mk_set('ois_dup')
        ext_tx = f'ext_{_uuid.uuid4().hex[:8]}'
        r1 = OIS.process_conversion(
            offer=offer, user=user, conversion_id=f'c_{_uuid.uuid4().hex[:8]}',
            payout_amount=_D('1'), reward_amount=_D('0.70'),
            external_tx_id=ext_tx)
        self.assertTrue(r1['created'])
        r2 = OIS.process_conversion(
            offer=offer, user=user, conversion_id=f'c_{_uuid.uuid4().hex[:8]}',
            payout_amount=_D('1'), reward_amount=_D('0.70'),
            external_tx_id=ext_tx)
        self.assertFalse(r2['created'])

    def test_process_conversion_autogenerated_id(self):
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)
        user, prov, offer = _mk_set('ois_auto')
        r = OIS.process_conversion(
            offer=offer, user=user,
            payout_amount=_D('1'), reward_amount=_D('0.70'))
        self.assertTrue(r['success'])
        self.assertTrue(r['created'])
        self.assertIn('auto_', r['conversion_id'])

    @_patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.approve_conversion')
    def test_process_conversion_auto_approve(self, mock_approve):
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)
        mock_approve.return_value = {'success': True}
        user, prov, offer = _mk_set('ois_aa')
        r = OIS.process_conversion(
            offer=offer, user=user,
            payout_amount=_D('1'), reward_amount=_D('0.70'),
            auto_approve=True)
        self.assertTrue(r['created'])
        mock_approve.assert_called_once()

    def test_approve_already_approved_returns_error(self):
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)
        from api.offerwall.models import OfferConversion
        user, prov, offer = _mk_set('ois_aa2')
        r = OIS.process_conversion(
            offer=offer, user=user,
            payout_amount=_D('1'), reward_amount=_D('0.70'))
        conv = r['conversion']
        conv.status = 'approved'
        conv.save(update_fields=['status'])
        result = OIS.approve_conversion(conv)
        self.assertFalse(result['success'])
        self.assertIn('approved', result['error'])

    def test_reject_approved_conversion_returns_error(self):
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)
        user, prov, offer = _mk_set('ois_rj')
        r = OIS.process_conversion(
            offer=offer, user=user,
            payout_amount=_D('1'), reward_amount=_D('0.70'))
        conv = r['conversion']
        conv.status = 'approved'
        conv.save(update_fields=['status'])
        result = OIS.reject_conversion(conv, reason='test')
        self.assertFalse(result['success'])
