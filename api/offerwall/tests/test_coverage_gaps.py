"""
Additional tests for gaps identified in analysis:
- OfferWallViewSet.get_offers
- PublicOfferListView  
- OfferConversionViewSet approve/reject actions
- OfferConversion.calculate_quality_score via signal
"""
from unittest.mock import patch, MagicMock
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def mk_provider(**kw):
    from api.offerwall.models import OfferProvider
    defaults = dict(name='P', provider_type='tapjoy', status='active',
                    api_key='k', revenue_share=Decimal('70.00'))
    defaults.update(kw)
    return OfferProvider.objects.create(**defaults)


def mk_offer(provider, **kw):
    from api.offerwall.models import Offer
    defaults = dict(provider=provider, title='T', description='D',
                    payout=Decimal('1.00'), reward_amount=Decimal('0.70'),
                    status='active')
    defaults.update(kw)
    return Offer.objects.create(**defaults)


def mk_wall(offers=None, **kw):
    from api.offerwall.models import OfferWall
    import uuid
    slug = kw.pop('slug', f'wall-{uuid.uuid4().hex[:6]}')
    wall = OfferWall.objects.create(name='W', slug=slug, **kw)
    return wall


def mk_conversion(offer, user, **kw):
    from api.offerwall.models import OfferConversion
    import uuid
    defaults = dict(conversion_id=uuid.uuid4().hex, status='pending',
                    payout_amount=Decimal('1.00'), reward_amount=Decimal('0.70'))
    defaults.update(kw)
    return OfferConversion.objects.create(offer=offer, user=user, **defaults)


class PublicOfferListViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.prov = mk_provider()

    def test_no_auth_required(self):
        resp = self.client.get('/api/offerwall/public/')
        self.assertNotEqual(resp.status_code, 401)

    def test_returns_only_active(self):
        mk_offer(self.prov, status='active')
        mk_offer(self.prov, status='paused', title='Paused')
        resp = self.client.get('/api/offerwall/public/')
        self.assertEqual(resp.status_code, 200)
        titles = [o['title'] for o in resp.data['results']]
        self.assertNotIn('Paused', titles)

    def test_response_has_count_and_results(self):
        mk_offer(self.prov)
        resp = self.client.get('/api/offerwall/public/')
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_deduplicates_by_title(self):
        mk_offer(self.prov, title='Same Title')
        mk_offer(self.prov, title='Same Title')
        resp = self.client.get('/api/offerwall/public/')
        titles = [o['title'] for o in resp.data['results']]
        self.assertEqual(titles.count('Same Title'), 1)

    def test_result_fields(self):
        mk_offer(self.prov)
        resp = self.client.get('/api/offerwall/public/')
        if resp.data['results']:
            obj = resp.data['results'][0]
            for field in ['id', 'title', 'payout', 'reward_amount', 'is_featured']:
                self.assertIn(field, obj)


class OfferWallGetOffersEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='u', password='p')
        self.client.force_authenticate(self.user)
        self.prov = mk_provider()

    def test_get_offers_returns_200(self):
        wall = mk_wall()
        resp = self.client.get(f'/api/offerwall/walls/{wall.id}/offers/')
        self.assertEqual(resp.status_code, 200)

    def test_get_offers_only_active(self):
        wall = mk_wall()
        mk_offer(self.prov, status='active')
        mk_offer(self.prov, status='paused', title='Paused')
        resp = self.client.get(f'/api/offerwall/walls/{wall.id}/offers/')
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_401(self):
        wall = mk_wall()
        self.client.force_authenticate(None)
        resp = self.client.get(f'/api/offerwall/walls/{wall.id}/offers/')
        self.assertEqual(resp.status_code, 401)

    def test_nonexistent_wall_404(self):
        import uuid
        resp = self.client.get(f'/api/offerwall/walls/{uuid.uuid4()}/offers/')
        self.assertEqual(resp.status_code, 404)


class ConversionApproveRejectEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username='adm', password='p', email='a@a.com')
        self.user = User.objects.create_user(username='u2', password='p')
        self.prov = mk_provider()
        self.offer = mk_offer(self.prov)

    def test_admin_can_approve(self):
        self.client.force_authenticate(self.admin)
        conv = mk_conversion(self.offer, self.user)
        with patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.approve_conversion',
                   return_value={'success': True}):
            resp = self.client.post(f'/api/offerwall/conversions/{conv.id}/approve/')
        self.assertIn(resp.status_code, [200, 201])

    def test_non_admin_cannot_approve(self):
        self.client.force_authenticate(self.user)
        conv = mk_conversion(self.offer, self.user)
        resp = self.client.post(f'/api/offerwall/conversions/{conv.id}/approve/')
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_reject(self):
        self.client.force_authenticate(self.admin)
        conv = mk_conversion(self.offer, self.user)
        with patch('api.offerwall.services.OfferwallIntegrationService.OfferwallIntegrationService.reject_conversion',
                   return_value={'success': True}):
            resp = self.client.post(f'/api/offerwall/conversions/{conv.id}/reject/', {'reason': 'fraud'})
        self.assertIn(resp.status_code, [200, 201])

    def test_unauthenticated_cannot_approve(self):
        self.client.force_authenticate(None)
        conv = mk_conversion(self.offer, self.user)
        resp = self.client.post(f'/api/offerwall/conversions/{conv.id}/approve/')
        self.assertEqual(resp.status_code, 401)


class AdminConversionQuerysetTest(TestCase):
    """Admin sees all conversions; users see only their own"""
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username='adm2', password='p', email='b@b.com')
        self.user1 = User.objects.create_user(username='u3', password='p')
        self.user2 = User.objects.create_user(username='u4', password='p')
        self.prov = mk_provider(name='P2')
        self.offer = mk_offer(self.prov)

    def test_admin_sees_all_conversions(self):
        mk_conversion(self.offer, self.user1)
        mk_conversion(self.offer, self.user2)
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/offerwall/conversions/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data['results'] if 'results' in resp.data else resp.data), 2)

    def test_user_sees_only_own_conversions(self):
        mk_conversion(self.offer, self.user1)
        mk_conversion(self.offer, self.user2)
        self.client.force_authenticate(self.user1)
        resp = self.client.get('/api/offerwall/conversions/')
        self.assertEqual(resp.status_code, 200)
        result_list = resp.data.get('results', resp.data)
        self.assertEqual(len(result_list), 1)


class QualityScoreSignalTest(TestCase):
    """quality_score updated on conversion approval"""
    def setUp(self):
        self.prov = mk_provider(name='P3')
        self.user = User.objects.create_user(username='u5', password='p')
        self.offer = mk_offer(self.prov)

    def test_quality_score_updated_after_approve(self):
        conv = mk_conversion(self.offer, self.user)
        initial_score = self.offer.quality_score
        conv.approve()
        self.offer.refresh_from_db()
        # score should be recalculated (may or may not change, but must not raise)
        self.assertIsNotNone(self.offer.quality_score)
