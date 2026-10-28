# api/djoyalty/tests/test_campaign_extended.py
"""
Extended CampaignViewSet tests -- segments, participants, stats。
All 3 actions: previously 0 tested。
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    from djoyalty.models.campaigns import LoyaltyCampaign
    t = Tenant.objects.create(name=f'CampCo-{Tenant.objects.count()}',
                               slug=f'camp-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'cp_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u, code=f'CP{Customer.objects.count():04d}', is_active=True)
    camp = LoyaltyCampaign.objects.create(
        tenant=t, name='Summer Campaign', campaign_type='double_points',
        status='active', start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=30),
        earn_multiplier=Decimal('2.0'),
    )
    return t, c, camp

def _admin():
    u = User.objects.create_user(username=f'cpa_{User.objects.count()}', password='pw', is_staff=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return cli

def _cli(c):
    cli = APIClient(); cli.force_authenticate(user=c.user)
    return cli


class CampaignSegmentTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.campaign = _setup()
        self.admin = _admin()

    def test_list_segments_empty(self):
        resp = self.admin.get(f'/api/loyalty/campaigns/{self.campaign.pk}/segments/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    def test_create_segment(self):
        resp = self.admin.post(f'/api/loyalty/campaigns/{self.campaign.pk}/segments/', {
            'segment_type': 'tier_based',
            'criteria':     {'min_tier_rank': 2},
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['segment_type'], 'tier_based')

    def test_create_all_customers_segment(self):
        resp = self.admin.post(f'/api/loyalty/campaigns/{self.campaign.pk}/segments/', {
            'segment_type': 'all',
            'criteria':     {},
        })
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_segments_requires_admin(self):
        cli = _cli(self.customer)
        resp = cli.post(f'/api/loyalty/campaigns/{self.campaign.pk}/segments/',
                        {'segment_type': 'all'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_segments_404_for_invalid_campaign(self):
        resp = self.admin.get('/api/loyalty/campaigns/99999/segments/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class CampaignParticipantTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.campaign = _setup()
        self.admin = _admin()

    def test_participants_empty(self):
        resp = self.admin.get(f'/api/loyalty/campaigns/{self.campaign.pk}/participants/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('participants', resp.data)
        self.assertEqual(resp.data['count'], 0)

    def test_participants_with_data(self):
        from djoyalty.models.campaigns import CampaignParticipant
        CampaignParticipant.objects.create(
            campaign=self.campaign, customer=self.customer,
            status='in_progress', joined_at=timezone.now(),
        )
        resp = self.admin.get(f'/api/loyalty/campaigns/{self.campaign.pk}/participants/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        p = resp.data['participants'][0]
        for field in ('id', 'customer_code', 'status', 'joined_at'):
            self.assertIn(field, p)

    def test_participants_filter_by_status(self):
        from djoyalty.models.campaigns import CampaignParticipant
        CampaignParticipant.objects.create(campaign=self.campaign, customer=self.customer,
                                            status='completed', joined_at=timezone.now())
        resp = self.admin.get(
            f'/api/loyalty/campaigns/{self.campaign.pk}/participants/?status=completed'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for p in resp.data['participants']:
            self.assertEqual(p['status'], 'completed')

    def test_campaign_stats(self):
        resp = self.admin.get(f'/api/loyalty/campaigns/{self.campaign.pk}/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('campaign_id', 'campaign_name', 'total_participants'):
            self.assertIn(field, resp.data)
        self.assertEqual(resp.data['campaign_id'], self.campaign.pk)
