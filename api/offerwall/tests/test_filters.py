"""
tests/test_filters.py

Tests for offerwall filter backends:
  - OfferFilterBackend
  - ProviderFilterBackend
  - ConversionFilterBackend
  - OfferClickFilterBackend
  - DateRangeFilterBackend

Run: python manage.py test api.offerwall.tests.test_filters
"""
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


def make_user(username='filteruser'):
    return User.objects.create_user(username, password='pass')


def make_provider(ptype='tapjoy', name='FilterProv'):
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=name, provider_type=ptype, status='active',
        api_key='k', revenue_share=Decimal('70'))


def make_category(slug='games'):
    from api.offerwall.models import OfferCategory
    return OfferCategory.objects.create(name=slug.title(), slug=slug, is_active=True)


def make_offer(provider, ext_id, **kwargs):
    from api.offerwall.models import Offer
    defaults = dict(
        title=f'Offer {ext_id}', payout=Decimal('1.00'),
        reward_amount=Decimal('0.70'), status='active',
    )
    defaults.update(kwargs)
    return Offer.objects.create(provider=provider, external_offer_id=ext_id, **defaults)


# ─────────────────────────────────────────────────────────────────────────────
# OfferFilterBackend
# ─────────────────────────────────────────────────────────────────────────────

class OfferFilterBackendTest(TestCase):
    def setUp(self):
        self.user     = make_user('offerfilter')
        self.prov     = make_provider()
        self.cat      = make_category('games')
        self.client   = APIClient()
        self.client.force_authenticate(user=self.user)

        self.offer_android = make_offer(self.prov, 'F001',
            offer_type='app_install', platform='android',
            payout=Decimal('2.00'), category=self.cat, is_featured=True)
        self.offer_ios = make_offer(self.prov, 'F002',
            offer_type='survey', platform='ios',
            payout=Decimal('0.50'), is_featured=False)
        self.offer_web = make_offer(self.prov, 'F003',
            offer_type='signup', platform='web',
            payout=Decimal('1.00'))

    def test_filter_by_offer_type(self):
        resp = self.client.get('/api/offerwall/offers/?offer_type=survey')
        self.assertEqual(resp.status_code, 200)
        ids = [o['id'] for o in resp.data['results']]
        self.assertIn(str(self.offer_ios.id), ids)
        self.assertNotIn(str(self.offer_android.id), ids)

    def test_filter_by_platform(self):
        resp = self.client.get('/api/offerwall/offers/?platform=android')
        self.assertEqual(resp.status_code, 200)
        ids = [o['id'] for o in resp.data['results']]
        self.assertIn(str(self.offer_android.id), ids)
        self.assertNotIn(str(self.offer_ios.id), ids)

    def test_filter_by_min_payout(self):
        resp = self.client.get('/api/offerwall/offers/?min_payout=1.50')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 0)

    def test_filter_by_max_payout(self):
        resp = self.client.get('/api/offerwall/offers/?max_payout=0.75')
        self.assertEqual(resp.status_code, 200)
        ids = [o['id'] for o in resp.data['results']]
        self.assertNotIn(str(self.offer_android.id), ids)  # offer_android payout=2.00 excluded

    def test_filter_by_category(self):
        # Use category UUID (the OfferSearchSerializer validates by UUID/str)
        resp = self.client.get(f'/api/offerwall/offers/?category={self.cat.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_filter_featured_true(self):
        resp = self.client.get('/api/offerwall/offers/?featured=true')
        self.assertEqual(resp.status_code, 200)
        ids = [o['id'] for o in resp.data['results']]
        self.assertIn(str(self.offer_android.id), ids)
        self.assertNotIn(str(self.offer_ios.id), ids)

    def test_filter_by_provider(self):
        resp = self.client.get(f'/api/offerwall/offers/?provider={self.prov.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 0)

    def test_invalid_min_payout_ignored(self):
        resp = self.client.get('/api/offerwall/offers/?min_payout=not_a_number')
        self.assertEqual(resp.status_code, 200)  # Should not crash


# ─────────────────────────────────────────────────────────────────────────────
# ProviderFilterBackend
# ─────────────────────────────────────────────────────────────────────────────

class ProviderFilterBackendTest(TestCase):
    def setUp(self):
        self.user   = make_user('provfilter')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.prov_tapjoy  = make_provider('tapjoy',  'Tapjoy Provider')
        self.prov_adgem   = make_provider('adgem',   'AdGem Provider')
        self.prov_inactive = make_provider('adgate', 'Inactive Prov')
        self.prov_inactive.status = 'inactive'
        self.prov_inactive.save()

    def test_filter_by_provider_type(self):
        resp = self.client.get('/api/offerwall/providers/?provider_type=tapjoy')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data['results']]
        self.assertIn(str(self.prov_tapjoy.id), ids)
        self.assertNotIn(str(self.prov_adgem.id), ids)

    def test_filter_by_status_active(self):
        resp = self.client.get('/api/offerwall/providers/?status=active')
        self.assertEqual(resp.status_code, 200)
        for p in resp.data['results']:
            self.assertEqual(p['status'], 'active')

    def test_filter_by_name(self):
        resp = self.client.get('/api/offerwall/providers/?name=AdGem')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data['results']]
        self.assertIn(str(self.prov_adgem.id), ids)


# ─────────────────────────────────────────────────────────────────────────────
# ConversionFilterBackend
# ─────────────────────────────────────────────────────────────────────────────

class ConversionFilterBackendTest(TestCase):
    def setUp(self):
        import uuid
        from api.offerwall.models import OfferConversion
        self.user   = make_user('convfilter')
        self.user2  = make_user('convfilter2')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        prov  = make_provider()
        offer = make_offer(prov, 'CF001')

        self.conv_approved = OfferConversion.objects.create(
            offer=offer, user=self.user,
            conversion_id=uuid.uuid4().hex,
            payout_amount=Decimal('1.00'), reward_amount=Decimal('0.70'),
            status='approved')
        self.conv_pending = OfferConversion.objects.create(
            offer=offer, user=self.user,
            conversion_id=uuid.uuid4().hex,
            payout_amount=Decimal('1.00'), reward_amount=Decimal('0.70'),
            status='pending')

    def test_filter_by_status_approved(self):
        resp = self.client.get('/api/offerwall/conversions/?status=approved')
        self.assertEqual(resp.status_code, 200)
        ids = [c['id'] for c in resp.data['results']]
        self.assertIn(str(self.conv_approved.id), ids)
        self.assertNotIn(str(self.conv_pending.id), ids)

    def test_filter_by_status_pending(self):
        resp = self.client.get('/api/offerwall/conversions/?status=pending')
        self.assertEqual(resp.status_code, 200)
        for c in resp.data['results']:
            self.assertEqual(c['status'], 'pending')

    def test_filter_date_from(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = self.client.get(f'/api/offerwall/conversions/?date_from={yesterday}')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 0)

    def test_filter_date_to_before_today(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        resp = self.client.get(f'/api/offerwall/conversions/?date_to={future}')
        self.assertEqual(resp.status_code, 200)

    def test_invalid_date_ignored(self):
        resp = self.client.get('/api/offerwall/conversions/?date_from=not-a-date')
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# DateRangeFilterBackend
# ─────────────────────────────────────────────────────────────────────────────

class DateRangeFilterBackendTest(TestCase):
    def setUp(self):
        from api.offerwall.filters import DateRangeFilterBackend
        self.backend = DateRangeFilterBackend()

    def test_filter_with_valid_date_from(self):
        from api.offerwall.models import OfferProvider
        from unittest.mock import MagicMock
        qs      = OfferProvider.objects.all()
        request = MagicMock()
        request.query_params = {'date_from': '2026-01-01'}
        result  = self.backend.filter_queryset(request, qs, None)
        self.assertIsNotNone(result)

    def test_filter_with_invalid_date_skipped(self):
        from api.offerwall.models import OfferProvider
        from unittest.mock import MagicMock
        qs      = OfferProvider.objects.all()
        request = MagicMock()
        request.query_params = {'date_from': 'INVALID'}
        # Should not raise
        result  = self.backend.filter_queryset(request, qs, None)
        self.assertIsNotNone(result)

    def test_filter_custom_date_field(self):
        from api.offerwall.models import OfferProvider
        from unittest.mock import MagicMock
        qs      = OfferProvider.objects.all()
        request = MagicMock()
        request.query_params = {
            'date_field': 'updated_at', 'date_from': '2026-01-01'}
        result = self.backend.filter_queryset(request, qs, None)
        self.assertIsNotNone(result)
