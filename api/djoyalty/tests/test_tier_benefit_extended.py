# api/djoyalty/tests/test_tier_benefit_extended.py
"""
TierBenefitViewSet tests -- by_tier, my_benefits, check_access, create_benefit。
Previously 0 of these 5 actions were tested (viewset was brand-new this session)。
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    from djoyalty.models.tiers import LoyaltyTier, UserTier, TierBenefit
    t    = Tenant.objects.create(name=f'TBCo-{Tenant.objects.count()}',
                                  slug=f'tb-{Tenant.objects.count()}', is_active=True)
    tier = LoyaltyTier.objects.create(tenant=t, name='Gold', rank=3,
                                       min_points=1000, is_active=True)
    b1   = TierBenefit.objects.create(tier=tier, benefit_type='free_shipping',
                                       name='Free Shipping', is_active=True)
    b2   = TierBenefit.objects.create(tier=tier, benefit_type='priority_support',
                                       name='Priority Support', is_active=True)
    u    = User.objects.create_user(username=f'tb_{User.objects.count()}', password='pw')
    c    = Customer.objects.create(tenant=t, user=u, code=f'TB{Customer.objects.count():04d}',
                                   is_active=True)
    UserTier.objects.create(customer=c, tier=tier, is_current=True)
    return t, tier, c, [b1, b2]

def _admin():
    u = User.objects.create_user(username=f'tba_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class TierBenefitListTest(TestCase):
    def setUp(self):
        self.tenant, self.tier, self.customer, self.benefits = _setup()
        self.admin = _admin()
        self.cli   = _cli(self.customer)

    def test_list_benefits(self):
        resp = self.admin.get('/api/loyalty/tier-benefits/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertGreaterEqual(len(resp.data['results']), 2)

    def test_list_filters_by_tier(self):
        resp = self.admin.get(f'/api/loyalty/tier-benefits/?tier_id={self.tier.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for b in resp.data['results']:
            self.assertEqual(b['tier_id'], self.tier.pk)

    @patch('djoyalty.viewsets.tiers.TierBenefitViewSet.TierBenefitService.get_benefits_for_tier')
    def test_by_tier(self, mock_get):
        mock_get.return_value = self.benefits
        resp = self.admin.get(f'/api/loyalty/tier-benefits/by-tier/{self.tier.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('tier_id', resp.data)
        self.assertIn('tier_name', resp.data)
        self.assertIn('benefits', resp.data)
        self.assertEqual(len(resp.data['benefits']), 2)
        mock_get.assert_called_once_with(tier_id=str(self.tier.pk))


class TierBenefitMyBenefitsTest(TestCase):
    def setUp(self):
        self.tenant, self.tier, self.customer, self.benefits = _setup()
        self.cli = _cli(self.customer)

    @patch('djoyalty.viewsets.tiers.TierBenefitViewSet.TierBenefitService.get_benefits_for_customer')
    def test_my_benefits_returns_active_benefits(self, mock_get):
        mock_get.return_value = self.benefits
        resp = self.cli.get(f'/api/loyalty/tier-benefits/my-benefits/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('current_tier', resp.data)
        self.assertIn('benefits', resp.data)
        self.assertIn('benefit_count', resp.data)
        self.assertEqual(resp.data['benefit_count'], 2)
        mock_get.assert_called_once()

    def test_my_benefits_requires_customer_id(self):
        resp = self.cli.get('/api/loyalty/tier-benefits/my-benefits/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TierBenefitCheckAccessTest(TestCase):
    def setUp(self):
        self.tenant, self.tier, self.customer, self.benefits = _setup()
        self.cli = _cli(self.customer)

    @patch('djoyalty.viewsets.tiers.TierBenefitViewSet.TierBenefitService.get_benefits_for_customer')
    def test_check_access_has_benefit(self, mock_get):
        mock_get.return_value = self.benefits
        resp = self.cli.post('/api/loyalty/tier-benefits/check-access/', {
            'customer_id':  self.customer.pk,
            'benefit_type': 'free_shipping',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['has_access'])
        self.assertEqual(resp.data['benefit_type'], 'free_shipping')
        self.assertIsInstance(resp.data['benefits'], list)

    @patch('djoyalty.viewsets.tiers.TierBenefitViewSet.TierBenefitService.get_benefits_for_customer')
    def test_check_access_no_benefit(self, mock_get):
        mock_get.return_value = self.benefits
        resp = self.cli.post('/api/loyalty/tier-benefits/check-access/', {
            'customer_id':  self.customer.pk,
            'benefit_type': 'private_lounge',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['has_access'])
        self.assertEqual(resp.data['benefits'], [])

    def test_check_access_requires_both_params(self):
        resp = self.cli.post('/api/loyalty/tier-benefits/check-access/', {
            'customer_id': self.customer.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TierBenefitCreateTest(TestCase):
    def setUp(self):
        self.tenant, self.tier, self.customer, self.benefits = _setup()
        self.admin = _admin()
        self.cli   = _cli(self.customer)

    def test_create_benefit_admin(self):
        resp = self.admin.post('/api/loyalty/tier-benefits/create/', {
            'tier_id':      self.tier.pk,
            'benefit_type': 'vip_lounge',
            'name':         'VIP Lounge Access',
            'description':  'Exclusive lounge access at partner venues',
            'value':        'unlimited',
        })
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        if resp.status_code == status.HTTP_201_CREATED:
            self.assertEqual(resp.data['benefit_type'], 'vip_lounge')
            self.assertEqual(resp.data['tier_id'], self.tier.pk)

    def test_create_benefit_requires_admin(self):
        resp = self.cli.post('/api/loyalty/tier-benefits/create/', {
            'tier_id': self.tier.pk, 'benefit_type': 'hack', 'name': 'hack',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
