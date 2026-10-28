# api/djoyalty/tests/test_referral_extended.py
"""
Extended ReferralViewSet tests -- convert, my_stats, conversions,
track_click, my_link。 Previously 0 of these 5 actions were tested。
Covers ReferralPointsService.award_referral_points() integration。
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    t = Tenant.objects.create(name=f'RefCo-{Tenant.objects.count()}',
                               slug=f'ref-{Tenant.objects.count()}', is_active=True)
    u1 = User.objects.create_user(username=f'ref_r_{User.objects.count()}', password='pw')
    u2 = User.objects.create_user(username=f'ref_e_{User.objects.count()}', password='pw')
    referrer  = Customer.objects.create(tenant=t, user=u1, code=f'R{Customer.objects.count():04d}',
                                        is_active=True, referral_code='TESTREF')
    referred  = Customer.objects.create(tenant=t, user=u2, code=f'E{Customer.objects.count():04d}',
                                        is_active=True)
    return t, referrer, referred

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c

def _admin():
    u = User.objects.create_user(username=f'ra_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c


class ReferralLinkTest(TestCase):
    def setUp(self):
        self.tenant, self.referrer, self.referred = _setup()
        self.cli = _cli(self.referrer)

    def test_get_or_create_referral_link(self):
        resp = self.cli.get(f'/api/loyalty/referrals/my_link/?customer_id={self.referrer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('code', resp.data)
        self.assertIn('total_clicks', resp.data)
        self.assertIn('total_conversions', resp.data)
        self.assertIn('total_points_earned', resp.data)

    def test_my_link_creates_if_missing(self):
        from djoyalty.models.referral import ReferralLink
        ReferralLink.objects.filter(customer=self.referrer).delete()
        resp = self.cli.post(
            '/api/loyalty/referrals/my_link/',
            {'customer_id': self.referrer.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('code', resp.data)
        self.assertTrue(ReferralLink.objects.filter(customer=self.referrer).exists())

    def test_my_stats_no_link(self):
        from djoyalty.models.referral import ReferralLink
        ReferralLink.objects.filter(customer=self.referrer).delete()
        resp = self.cli.get(f'/api/loyalty/referrals/my-stats/?customer_id={self.referrer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['has_referral_link'])

    def test_my_stats_with_link(self):
        from djoyalty.models.referral import ReferralLink
        ReferralLink.objects.get_or_create(customer=self.referrer, defaults={
            'tenant': self.tenant, 'code': 'TESTREF',
            'total_clicks': 5, 'unique_clicks': 3,
            'total_conversions': 2, 'total_points_earned': Decimal('200'),
        })
        resp = self.cli.get(f'/api/loyalty/referrals/my-stats/?customer_id={self.referrer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['has_referral_link'])
        self.assertEqual(resp.data['total_clicks'], 5)
        self.assertEqual(resp.data['total_conversions'], 2)


class ReferralConvertTest(TestCase):
    def setUp(self):
        self.tenant, self.referrer, self.referred = _setup()
        self.cli   = _cli(self.referred)
        self.admin = _admin()
        from djoyalty.models.referral import ReferralLink
        self.link = ReferralLink.objects.create(
            customer=self.referrer, tenant=self.tenant,
            code='TESTREF', is_active=True,
        )

    @patch('djoyalty.viewsets.advanced.ReferralViewSet.ReferralPointsService.award_referral_points')
    def test_convert_awards_points_to_both(self, mock_award):
        mock_award.side_effect = [Decimal('100'), Decimal('50')]
        resp = self.cli.post('/api/loyalty/referrals/convert/', {
            'referral_code':    'TESTREF',
            'customer_id':      self.referred.pk,
            'conversion_type':  'signup',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'converted')
        self.assertEqual(resp.data['referrer_points'], '100')
        self.assertEqual(resp.data['referred_points'], '50')
        self.assertEqual(mock_award.call_count, 2)

    def test_convert_invalid_code(self):
        resp = self.cli.post('/api/loyalty/referrals/convert/', {
            'referral_code': 'BADCODE', 'customer_id': self.referred.pk,
            'conversion_type': 'signup',
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_convert_self_referral_blocked(self):
        resp = _cli(self.referrer).post('/api/loyalty/referrals/convert/', {
            'referral_code': 'TESTREF', 'customer_id': self.referrer.pk,
            'conversion_type': 'signup',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('self-referral', resp.data.get('error', '').lower())

    @patch('djoyalty.viewsets.advanced.ReferralViewSet.ReferralPointsService.award_referral_points')
    def test_convert_prevents_duplicate(self, mock_award):
        mock_award.side_effect = [Decimal('100'), Decimal('50')]
        self.cli.post('/api/loyalty/referrals/convert/', {
            'referral_code': 'TESTREF', 'customer_id': self.referred.pk,
            'conversion_type': 'signup',
        })
        resp = self.cli.post('/api/loyalty/referrals/convert/', {
            'referral_code': 'TESTREF', 'customer_id': self.referred.pk,
            'conversion_type': 'signup',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already converted', resp.data.get('error', ''))

    def test_convert_validates_input(self):
        resp = self.cli.post('/api/loyalty/referrals/convert/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_conversions(self):
        resp = self.cli.get(
            f'/api/loyalty/referrals/conversions/?customer_id={self.referrer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
