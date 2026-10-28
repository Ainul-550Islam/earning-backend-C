# api/djoyalty/tests/test_points_extended.py
"""
Extended PointsViewSet tests -- covers reserve, release, earn, adjust, balance, summary।
Previously: 0 of these 8 actions were tested।
After this file: all 8 covered।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def make_tenant():
    from djoyalty.models.core import Tenant
    return Tenant.objects.create(name='Test Co', slug='test-co', is_active=True)


def make_customer(tenant, user=None):
    from djoyalty.models.core import Customer
    if user is None:
        user = User.objects.create_user(
            username=f'u_{Customer.objects.count()}',
            password='pw123',
        )
    return Customer.objects.create(
        tenant=tenant, user=user,
        code=f'C{Customer.objects.count():04d}',
        is_active=True,
    )


def make_loyalty_points(customer, balance=Decimal('500.00')):
    from djoyalty.models.points import LoyaltyPoints
    lp, _ = LoyaltyPoints.objects.get_or_create(customer=customer)
    lp.balance            = balance
    lp.available_balance  = balance
    lp.frozen_balance     = Decimal('0')
    lp.lifetime_earned    = balance
    lp.lifetime_redeemed  = Decimal('0')
    lp.lifetime_expired   = Decimal('0')
    lp.save()
    return lp


def admin_client(tenant):
    user = User.objects.create_user(username='admin_pts', password='pw', is_staff=True)
    c = APIClient()
    c.force_authenticate(user=user)
    c.user = user
    return c


def customer_client(customer):
    c = APIClient()
    c.force_authenticate(user=customer.user)
    return c


class PointsEarnTest(TestCase):
    def setUp(self):
        self.tenant   = make_tenant()
        self.customer = make_customer(self.tenant)
        self.lp       = make_loyalty_points(self.customer)
        self.admin    = admin_client(self.tenant)

    @patch('djoyalty.viewsets.points.PointsViewSet.PointsEngine.process_earn')
    def test_earn_awards_points(self, mock_earn):
        mock_earn.return_value = Decimal('50.00')
        resp = self.admin.post('/api/loyalty/points/earn/', {
            'customer_id':  self.customer.pk,
            'spend_amount': '500',
            'reference_id': 'txn-001',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('points_earned', resp.data)
        mock_earn.assert_called_once()

    def test_earn_requires_reference_id(self):
        resp = self.admin.post('/api/loyalty/points/earn/', {
            'customer_id':  self.customer.pk,
            'spend_amount': '500',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reference_id', resp.data.get('error', '').lower()
                      if 'error' in resp.data else str(resp.data))

    def test_earn_requires_admin_permission(self):
        cli = customer_client(self.customer)
        resp = cli.post('/api/loyalty/points/earn/', {
            'customer_id': self.customer.pk, 'spend_amount': '100', 'reference_id': 'x',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.points.PointsViewSet.IdempotencyGuard')
    @patch('djoyalty.viewsets.points.PointsViewSet.PointsEngine.process_earn')
    def test_earn_idempotency_returns_cached(self, mock_earn, mock_guard_cls):
        guard = MagicMock()
        guard.already_processed.return_value = True
        guard.get_cached_result.return_value = {'points_earned': '50', 'message': 'Earned 50 points'}
        mock_guard_cls.return_value = guard
        resp = self.admin.post('/api/loyalty/points/earn/', {
            'customer_id': self.customer.pk, 'spend_amount': '500', 'reference_id': 'txn-001',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('idempotent', False))
        mock_earn.assert_not_called()


class PointsBalanceSummaryTest(TestCase):
    def setUp(self):
        self.tenant   = make_tenant()
        self.customer = make_customer(self.tenant)
        self.lp       = make_loyalty_points(self.customer, Decimal('750.00'))
        self.cli      = customer_client(self.customer)
        self.admin    = admin_client(self.tenant)

    def test_balance_own_customer(self):
        resp = self.cli.get(f'/api/loyalty/points/balance/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['balance'], '750.00')
        self.assertIn('available_balance', resp.data)
        self.assertIn('frozen_balance', resp.data)
        self.assertIn('lifetime_earned', resp.data)

    def test_balance_other_customer_forbidden(self):
        other     = make_customer(self.tenant)
        other_cli = customer_client(other)
        resp = other_cli.get(f'/api/loyalty/points/balance/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_balance_admin_can_query_any(self):
        resp = self.admin.get(f'/api/loyalty/points/balance/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['balance'], '750.00')

    def test_summary_includes_expiry_and_tier(self):
        resp = self.cli.get(f'/api/loyalty/points/summary/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('balance', 'available_balance', 'frozen_balance',
                      'lifetime_earned', 'lifetime_redeemed', 'tier', 'expiring_soon'):
            self.assertIn(field, resp.data)

    def test_balance_requires_customer_id(self):
        resp = self.cli.get('/api/loyalty/points/balance/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PointsAdjustTest(TestCase):
    def setUp(self):
        self.tenant   = make_tenant()
        self.customer = make_customer(self.tenant)
        self.lp       = make_loyalty_points(self.customer, Decimal('200.00'))
        self.admin    = admin_client(self.tenant)

    @patch('djoyalty.viewsets.points.PointsViewSet.PointsAdjustmentService.adjust')
    def test_adjust_credits_points(self, mock_adjust):
        from djoyalty.models.points import LoyaltyPoints
        lp = self.lp
        lp.balance = Decimal('300.00')
        mock_adjust.return_value = lp
        resp = self.admin.post('/api/loyalty/points/adjust/', {
            'customer_id': self.customer.pk,
            'points':      '100',
            'reason':      'Customer service credit',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('balance', resp.data)
        mock_adjust.assert_called_once()

    def test_adjust_requires_reason(self):
        resp = self.admin.post('/api/loyalty/points/adjust/', {
            'customer_id': self.customer.pk, 'points': '100', 'reason': '',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adjust_requires_admin(self):
        cli = customer_client(self.customer)
        resp = cli.post('/api/loyalty/points/adjust/', {
            'customer_id': self.customer.pk, 'points': '100', 'reason': 'hack',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class PointsReserveReleaseTest(TestCase):
    def setUp(self):
        self.tenant   = make_tenant()
        self.customer = make_customer(self.tenant)
        self.lp       = make_loyalty_points(self.customer, Decimal('500.00'))
        self.admin    = admin_client(self.tenant)

    @patch('djoyalty.viewsets.points.PointsViewSet.PointsReservationService.reserve')
    def test_reserve_holds_points(self, mock_reserve):
        from django.utils import timezone
        from datetime import timedelta
        mock_res = MagicMock()
        mock_res.id         = 1
        mock_res.points     = Decimal('200.00')
        mock_res.reference  = 'order-789'
        mock_res.expires_at = timezone.now() + timedelta(minutes=30)
        mock_reserve.return_value = mock_res
        resp = self.admin.post('/api/loyalty/points/reserve/', {
            'customer_id': self.customer.pk,
            'points':      '200',
            'reference':   'order-789',
            'hold_minutes': 30,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'reserved')
        self.assertIn('reservation_id', resp.data)
        self.assertIn('expires_at', resp.data)
        mock_reserve.assert_called_once()

    def test_reserve_requires_reference(self):
        resp = self.admin.post('/api/loyalty/points/reserve/', {
            'customer_id': self.customer.pk, 'points': '200',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('djoyalty.viewsets.points.PointsViewSet.PointsReservationService.release')
    def test_release_returns_points(self, mock_release):
        mock_release.return_value = True
        resp = self.admin.post('/api/loyalty/points/release/', {'reference': 'order-789'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'released')
        mock_release.assert_called_once_with(reference='order-789')

    @patch('djoyalty.viewsets.points.PointsViewSet.PointsReservationService.release')
    def test_release_not_found(self, mock_release):
        mock_release.return_value = False
        resp = self.admin.post('/api/loyalty/points/release/', {'reference': 'bad-ref'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_release_requires_reference(self):
        resp = self.admin.post('/api/loyalty/points/release/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reservations_list_admin_only(self):
        resp = self.admin.get('/api/loyalty/points/reservations/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        cli = customer_client(self.customer)
        resp2 = cli.get('/api/loyalty/points/reservations/')
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)
