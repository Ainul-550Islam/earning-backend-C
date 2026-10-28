"""
View / API Tests — MEDIUM PRIORITY (data input views)
Run: python manage.py test api.offerwall.tests.test_views
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from api.offerwall.models import OfferProvider, OfferCategory, Offer, OfferConversion

User = get_user_model()


def _make(label=''):
    prov = OfferProvider.objects.create(
        name=f'VP{label}', provider_type='tapjoy', status='active',
        revenue_share=Decimal('70'))
    cat = OfferCategory.objects.create(
        name=f'Cat{label}', slug=f'cat-{label}-{uuid.uuid4().hex[:4]}', is_active=True)
    offer = Offer.objects.create(
        provider=prov, external_offer_id=str(uuid.uuid4())[:12],
        title='View Offer', description='d', payout=Decimal('1'),
        reward_amount=Decimal('0.70'), click_url='https://x.com',
        status='active', category=cat)
    admin = User.objects.create_superuser(
        username=f'adm{label}', email=f'adm{label}@t.com', password='Admin@123')
    user = User.objects.create_user(
        username=f'usr{label}', email=f'usr{label}@t.com', password='User@123')
    return prov, cat, offer, admin, user


# ── Public list ───────────────────────────────────────────────────────────────

class PublicOfferListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        prov = OfferProvider.objects.create(
            name='PP', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
        Offer.objects.create(provider=prov, external_offer_id='pub_a', title='Active Offer',
            description='d', payout=Decimal('1'), reward_amount=Decimal('0.70'),
            click_url='https://x.com', status='active')
        Offer.objects.create(provider=prov, external_offer_id='pub_p', title='Paused Offer',
            description='d', payout=Decimal('1'), reward_amount=Decimal('0.70'),
            click_url='https://x.com', status='paused')

    def test_no_auth_required(self):
        self.assertEqual(self.client.get('/api/offerwall/public/').status_code, 200)

    def test_returns_only_active(self):
        r = self.client.get('/api/offerwall/public/')
        titles = [o['title'] for o in r.data.get('results', [])]
        self.assertIn('Active Offer', titles)
        self.assertNotIn('Paused Offer', titles)

    def test_has_count(self):
        r = self.client.get('/api/offerwall/public/')
        self.assertIn('count', r.data)

    def test_required_fields(self):
        r = self.client.get('/api/offerwall/public/')
        if r.data.get('results'):
            for f in ['id', 'title', 'payout', 'reward_amount', 'click_url']:
                self.assertIn(f, r.data['results'][0])


# ── Offer list & detail ───────────────────────────────────────────────────────

class OfferListViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('lv')

    def test_unauth_returns_401(self):
        self.assertEqual(self.client.get('/api/offerwall/offers/').status_code, 401)

    def test_auth_returns_200(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/').status_code, 200)

    def test_filter_by_category(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/offers/?category={self.cat.id}')
        self.assertEqual(r.status_code, 200)

    def test_search_by_title(self):
        Offer.objects.create(provider=self.prov, external_offer_id='srch1',
            title='UniqueSearchXYZ123', description='d', payout=Decimal('1'),
            reward_amount=Decimal('0.7'), click_url='https://x.com', status='active')
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?q=UniqueSearchXYZ123')
        titles = [o['title'] for o in r.data.get('results', r.data)]
        self.assertIn('UniqueSearchXYZ123', titles)

    def test_paused_not_in_list(self):
        Offer.objects.create(provider=self.prov, external_offer_id='psd1',
            title='PausedXYZ', description='d', payout=Decimal('1'),
            reward_amount=Decimal('0.7'), click_url='https://x.com', status='paused')
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/')
        titles = [o['title'] for o in r.data.get('results', r.data)]
        self.assertNotIn('PausedXYZ', titles)

    def test_sort_by_payout(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/?sort_by=payout').status_code, 200)

    def test_sort_by_quality_score(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/?sort_by=quality_score').status_code, 200)


class OfferDetailViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('dv')

    def test_retrieve_200(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/offers/{self.offer.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(str(r.data['id']), str(self.offer.id))

    def test_nonexistent_404(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/offers/{uuid.uuid4()}/')
        self.assertEqual(r.status_code, 404)


# ── Offer click action ────────────────────────────────────────────────────────

class OfferClickTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('ck')

    @patch('api.offerwall.utils.FraudDetector.FraudDetector.comprehensive_fraud_check')
    @patch('api.offerwall.utils.AnalyticsTracker.AnalyticsTracker.track_offer_click')
    @patch('api.offerwall.services.OfferProcessor.OfferProcessorFactory.create')
    def test_click_returns_200(self, mock_proc, mock_track, mock_fraud):
        mock_fraud.return_value = {'should_block': False, 'fraud_score': 0}
        mock_click = MagicMock(); mock_click.click_id = 'ck_001'
        mock_track.return_value = mock_click
        mock_proc.return_value.build_click_url.return_value = 'https://click.example.com'
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/click/')
        self.assertIn(r.status_code, [200, 201])

    @patch('api.offerwall.utils.FraudDetector.FraudDetector.comprehensive_fraud_check')
    def test_click_blocked_by_fraud(self, mock_fraud):
        mock_fraud.return_value = {'should_block': True, 'fraud_score': 90}
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/click/')
        self.assertIn(r.status_code, [400, 403, 429])

    def test_click_unauth_401(self):
        self.assertEqual(
            self.client.post(f'/api/offerwall/offers/{self.offer.id}/click/').status_code, 401)

    def test_click_invalid_offer_id_404(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{uuid.uuid4()}/click/')
        self.assertIn(r.status_code, [400, 404])


# ── Special endpoints ─────────────────────────────────────────────────────────

class SpecialEndpointsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('sp')

    def test_stats_endpoint(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/stats/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('total_offers', r.data)
        self.assertIn('active_offers', r.data)

    def test_featured_endpoint(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/featured/').status_code, 200)

    def test_recommended_endpoint(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/recommended/').status_code, 200)

    @patch('api.offerwall.utils.AnalyticsTracker.AnalyticsTracker.get_trending_offers')
    def test_trending_endpoint(self, mock_trending):
        mock_trending.return_value = []
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/offers/trending/').status_code, 200)


# ── Provider views ────────────────────────────────────────────────────────────

class ProviderViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('pv')

    def test_list_auth(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/providers/').status_code, 200)

    def test_admin_create_provider(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/offerwall/providers/', {
            'name': 'New Prov', 'provider_type': 'adgem',
            'status': 'testing', 'revenue_share': '65.00'})
        self.assertIn(r.status_code, [200, 201])

    def test_user_cannot_create(self):
        self.client.force_authenticate(self.user)
        r = self.client.post('/api/offerwall/providers/', {
            'name': 'Unauth', 'provider_type': 'tapjoy', 'revenue_share': '70'})
        self.assertEqual(r.status_code, 403)

    @patch('api.offerwall.services.OfferProcessor.OfferProcessorFactory.create')
    def test_admin_sync_provider(self, mock_proc):
        mock_proc.return_value.sync_offers.return_value = {
            'synced': 5, 'created': 3, 'updated': 2, 'errors': 0}
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/providers/{self.prov.id}/sync/')
        self.assertIn(r.status_code, [200, 201])

    def test_provider_stats(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/providers/{self.prov.id}/stats/')
        self.assertEqual(r.status_code, 200)


# ── Category views ────────────────────────────────────────────────────────────

class CategoryViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('cv')

    def test_list_categories(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/categories/').status_code, 200)

    def test_admin_create(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/offerwall/categories/',
                             {'name': 'New Cat', 'slug': f'nc-{uuid.uuid4().hex[:4]}'})
        self.assertIn(r.status_code, [200, 201])

    def test_user_cannot_create(self):
        self.client.force_authenticate(self.user)
        r = self.client.post('/api/offerwall/categories/',
                             {'name': 'Unauth', 'slug': 'unauth-cat'})
        self.assertEqual(r.status_code, 403)

    def test_category_offers(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/categories/{self.cat.id}/offers/')
        self.assertEqual(r.status_code, 200)


# ── Conversion views ──────────────────────────────────────────────────────────

class ConversionViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('cnv')
        self.conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='cv001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='pending')

    def test_list_conversions(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/conversions/').status_code, 200)

    def test_user_sees_only_own(self):
        other = User.objects.create_user(username='other_cnv', email='oc@t.com', password='p')
        OfferConversion.objects.create(offer=self.offer, user=other, conversion_id='oc001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='pending')
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/conversions/')
        ids = [c['conversion_id'] for c in r.data.get('results', r.data)]
        self.assertNotIn('oc001', ids)
        self.assertIn('cv001', ids)

    def test_conversion_stats(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/conversions/stats/').status_code, 200)


# ── Click views ───────────────────────────────────────────────────────────────

class ClickViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('clv')

    def test_list_clicks(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/clicks/').status_code, 200)

    def test_click_stats(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/clicks/stats/').status_code, 200)


# ── Extra filter tests ────────────────────────────────────────────────────────

class OfferFilterExtraTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.prov, self.cat, self.offer, self.admin, self.user = _make('fx')

    def test_filter_by_platform(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?platform=android')
        self.assertEqual(r.status_code, 200)

    def test_filter_by_min_payout(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?min_payout=0.50')
        self.assertEqual(r.status_code, 200)
        for o in r.data.get('results', r.data):
            self.assertGreaterEqual(float(o['payout']), 0.50)

    def test_filter_by_max_payout(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?max_payout=5.00')
        self.assertEqual(r.status_code, 200)

    def test_filter_by_offer_type(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?offer_type=app_install')
        self.assertEqual(r.status_code, 200)

    def test_filter_featured_true(self):
        import uuid as _uuid
        Offer.objects.create(
            provider=self.prov, external_offer_id=str(_uuid.uuid4())[:12],
            title='Featured Offer', description='d', payout=Decimal('1'),
            reward_amount=Decimal('0.70'), click_url='https://x.com',
            status='active', is_featured=True)
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?featured=true')
        self.assertEqual(r.status_code, 200)

    def test_offer_list_pagination(self):
        self.client.force_authenticate(self.user)
        r = self.client.get('/api/offerwall/offers/?page=1&page_size=5')
        self.assertEqual(r.status_code, 200)

    def test_click_stats_endpoint(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/clicks/stats/').status_code, 200)

    def test_offerwall_list_endpoint(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/offerwall/walls/').status_code, 200)

    def test_conversion_detail(self):
        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='det_cv001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='pending')
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/conversions/{conv.id}/')
        self.assertEqual(r.status_code, 200)

    def test_unauth_conversion_list_401(self):
        self.assertEqual(self.client.get('/api/offerwall/conversions/').status_code, 401)


# ══════════════════════════════════════════════════════════════════════════════
# MISSING VIEW ACTION TESTS — approve, reject, toggle_*, calculate_quality,
#   OfferWallViewSet.get_offers, ProviderViewSet.stats
# ══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid
from decimal import Decimal as _D


def _make_full(label='x'):
    """Return provider, offer, offerwall, admin, user."""
    prov = OfferProvider.objects.create(
        name=f'FP{label}', provider_type='tapjoy', status='active',
        revenue_share=_D('70'))
    cat = OfferCategory.objects.create(
        name=f'FC{label}', slug=f'fc-{label}-{_uuid.uuid4().hex[:4]}', is_active=True)
    offer = Offer.objects.create(
        provider=prov, external_offer_id=_uuid.uuid4().hex[:12],
        title=f'FO{label}', description='d', payout=_D('1'),
        reward_amount=_D('0.70'), click_url='https://x.com',
        status='active', category=cat)
    from api.offerwall.models import OfferWall
    wall = OfferWall.objects.create(
        name=f'WL{label}', slug=f'wl-{label}', provider=prov, is_active=True)
    admin = User.objects.create_superuser(
        username=f'fa{label}', email=f'fa{label}@t.com', password='A@123')
    user = User.objects.create_user(
        username=f'fu{label}', email=f'fu{label}@t.com', password='p')
    return prov, offer, wall, admin, user


def _conv(offer, user, label='c'):
    return OfferConversion.objects.create(
        offer=offer, user=user, conversion_id=_uuid.uuid4().hex[:10],
        payout_amount=_D('1'), reward_amount=_D('0.70'),
        bonus_amount=_D('0'), status='pending')


class ConversionApproveViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('ap')
        self.conv = _conv(self.offer, self.user, 'ap')

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.approve_conversion')
    def test_admin_approve_returns_200(self, mock_approve):
        mock_approve.return_value = {'success': True}
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/approve/')
        self.assertEqual(r.status_code, 200)

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.approve_conversion')
    def test_user_approve_returns_403(self, mock_approve):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/approve/')
        self.assertEqual(r.status_code, 403)
        mock_approve.assert_not_called()

    def test_unauthenticated_approve_returns_401(self):
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/approve/')
        self.assertEqual(r.status_code, 401)

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.approve_conversion')
    def test_approve_service_error_returns_error(self, mock_approve):
        mock_approve.return_value = {'success': False, 'error': 'already approved'}
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/approve/')
        self.assertNotEqual(r.status_code, 200)


class ConversionRejectViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('rj')
        self.conv = _conv(self.offer, self.user, 'rj')

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.reject_conversion')
    def test_admin_reject_returns_200(self, mock_reject):
        mock_reject.return_value = {'success': True}
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/reject/',
                             {'reason': 'fraud'}, format='json')
        self.assertEqual(r.status_code, 200)

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.reject_conversion')
    def test_reason_passed_to_service(self, mock_reject):
        mock_reject.return_value = {'success': True}
        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/offerwall/conversions/{self.conv.id}/reject/',
                         {'reason': 'duplicate'}, format='json')
        call_kwargs = mock_reject.call_args.kwargs
        self.assertEqual(call_kwargs.get('reason'), 'duplicate')

    @patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.reject_conversion')
    def test_user_reject_returns_403(self, mock_reject):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/reject/',
                             {'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_reject_returns_401(self):
        r = self.client.post(f'/api/offerwall/conversions/{self.conv.id}/reject/')
        self.assertEqual(r.status_code, 401)


class ToggleFeaturedViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('tf')

    def test_admin_toggle_featured_200(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_featured/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('is_featured', r.data.get('data', r.data))

    def test_toggle_changes_state(self):
        self.client.force_authenticate(self.admin)
        initial = self.offer.is_featured
        self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_featured/')
        self.offer.refresh_from_db()
        self.assertNotEqual(self.offer.is_featured, initial)

    def test_user_toggle_featured_403(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_featured/')
        self.assertIn(r.status_code, [403, 404])


class ToggleTrendingViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('tt')

    def test_admin_toggle_trending_200(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_trending/')
        self.assertEqual(r.status_code, 200)

    def test_toggle_trending_changes_state(self):
        self.client.force_authenticate(self.admin)
        initial = self.offer.is_trending
        self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_trending/')
        self.offer.refresh_from_db()
        self.assertNotEqual(self.offer.is_trending, initial)

    def test_user_toggle_trending_403(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/toggle_trending/')
        self.assertIn(r.status_code, [403, 404])


class CalculateQualityViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('cq')

    def test_admin_calculate_quality_200(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/calculate_quality/')
        self.assertEqual(r.status_code, 200)
        body = r.data.get('data', r.data)
        self.assertIn('quality_score', body)

    def test_quality_score_is_numeric(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/calculate_quality/')
        body = r.data.get('data', r.data)
        score = body.get('quality_score')
        self.assertIsNotNone(score)
        self.assertIsInstance(float(score), float)

    def test_user_calculate_quality_403(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'/api/offerwall/offers/{self.offer.id}/calculate_quality/')
        self.assertIn(r.status_code, [403, 404])


class OfferWallGetOffersViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('wg')

    def test_get_offers_returns_200(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/walls/{self.wall.id}/offers/')
        self.assertEqual(r.status_code, 200)

    def test_get_offers_returns_list(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/walls/{self.wall.id}/offers/')
        self.assertIn('results', r.data)

    def test_get_offers_unauthenticated_401(self):
        r = self.client.get(f'/api/offerwall/walls/{self.wall.id}/offers/')
        self.assertEqual(r.status_code, 401)

    def test_get_offers_nonexistent_wall_404(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f'/api/offerwall/walls/9999999/offers/')
        self.assertEqual(r.status_code, 404)


class ProviderStatsViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov, self.offer, self.wall, self.admin, self.user = _make_full('ps')

    def test_provider_stats_200(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'/api/offerwall/providers/{self.prov.id}/stats/')
        self.assertEqual(r.status_code, 200)

    def test_provider_stats_has_required_keys(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'/api/offerwall/providers/{self.prov.id}/stats/')
        for key in ['total_offers', 'total_conversions', 'total_revenue', 'status']:
            self.assertIn(key, r.data)

    def test_provider_stats_unauthenticated_401(self):
        r = self.client.get(f'/api/offerwall/providers/{self.prov.id}/stats/')
        self.assertEqual(r.status_code, 401)
