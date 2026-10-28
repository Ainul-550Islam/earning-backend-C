# api/djoyalty/tests/test_membership_extended.py
"""
Extended MembershipViewSet tests -- subscribe, renew, cancel, my_benefits,
admin_active, credit_bonus। Previously 0 of 9 actions tested。
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


def _tenant():
    from djoyalty.models.core import Tenant
    return Tenant.objects.create(name='MemCo', slug=f'mem-co-{Tenant.objects.count()}', is_active=True)

def _customer(tenant):
    from djoyalty.models.core import Customer
    u = User.objects.create_user(username=f'mem_{Customer.objects.count()}', password='pw')
    return Customer.objects.create(tenant=tenant, user=u,
                                   code=f'M{Customer.objects.count():04d}', is_active=True)

def _plan(tenant, price=Decimal('299.00')):
    from djoyalty.paid_membership import MembershipPlan
    return MembershipPlan.objects.create(
        tenant=tenant, name='Gold Plan', plan_code=f'GOLD-{MembershipPlan.objects.count()}',
        billing_cycle='monthly', price=price, currency='BDT',
        welcome_points=Decimal('500'), monthly_bonus_points=Decimal('100'),
        earn_multiplier=Decimal('2.00'), free_cashout_per_month=2,
        priority_support=True, exclusive_offers=True, early_access=True,
        is_active=True, sort_order=1,
    )

def _admin():
    u = User.objects.create_user(username=f'madmin_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class MembershipPlansTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.plan     = _plan(self.tenant)
        self.cli      = _cli(self.customer)

    def test_list_plans(self):
        resp = self.cli.get('/api/loyalty/memberships/plans/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('plans', resp.data)
        self.assertGreaterEqual(len(resp.data['plans']), 1)

    def test_plan_has_required_fields(self):
        resp = self.cli.get('/api/loyalty/memberships/plans/')
        plan = resp.data['plans'][0]
        for field in ('id', 'name', 'price', 'billing_cycle', 'earn_multiplier',
                      'welcome_points', 'monthly_bonus_points', 'is_active'):
            self.assertIn(field, plan, f"Field {field} missing from plan response")


class MembershipSubscribeTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.plan     = _plan(self.tenant)
        self.cli      = _cli(self.customer)
        self.admin    = _admin()

    @patch('djoyalty.viewsets.advanced.MembershipViewSet.PointsEngine.credit')
    def test_subscribe_creates_membership(self, mock_credit):
        resp = self.cli.post('/api/loyalty/memberships/subscribe/', {
            'plan_id':          self.plan.pk,
            'payment_method':   'bkash',
            'payment_reference': 'BKS-001',
            'auto_renew':       True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'subscribed')
        self.assertIn('membership', resp.data)
        m = resp.data['membership']
        self.assertEqual(m['status'], 'active')

    def test_subscribe_prevents_duplicate(self):
        from djoyalty.paid_membership import CustomerMembership
        CustomerMembership.objects.create(
            customer=self.customer, tenant=self.tenant, plan=self.plan,
            status='active', current_period_end=timezone.now() + timedelta(days=30),
        )
        resp = self.cli.post('/api/loyalty/memberships/subscribe/', {
            'plan_id': self.plan.pk, 'payment_method': 'bkash',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already have', resp.data.get('error', '').lower())

    def test_subscribe_invalid_plan(self):
        resp = self.cli.post('/api/loyalty/memberships/subscribe/', {
            'plan_id': 99999, 'payment_method': 'bkash',
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_subscribe_validates_input(self):
        resp = self.cli.post('/api/loyalty/memberships/subscribe/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class MembershipMyMembershipTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.plan     = _plan(self.tenant)
        self.cli      = _cli(self.customer)

    def test_my_membership_none(self):
        resp = self.cli.get('/api/loyalty/memberships/my/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data.get('membership'))

    def test_my_membership_active(self):
        from djoyalty.paid_membership import CustomerMembership
        m = CustomerMembership.objects.create(
            customer=self.customer, tenant=self.tenant, plan=self.plan,
            status='active', current_period_end=timezone.now() + timedelta(days=30),
        )
        resp = self.cli.get('/api/loyalty/memberships/my/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data.get('membership'))
        self.assertEqual(resp.data['membership']['status'], 'active')

    def test_my_benefits(self):
        from djoyalty.paid_membership import CustomerMembership
        CustomerMembership.objects.create(
            customer=self.customer, tenant=self.tenant, plan=self.plan,
            status='active', current_period_end=timezone.now() + timedelta(days=30),
        )
        resp = self.cli.get('/api/loyalty/memberships/my/benefits/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('earn_multiplier', 'can_free_cashout', 'has_priority_support',
                      'has_exclusive_offers', 'monthly_bonus_points'):
            self.assertIn(field, resp.data)


class MembershipCancelRenewTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.plan     = _plan(self.tenant)
        self.cli      = _cli(self.customer)
        from djoyalty.paid_membership import CustomerMembership
        self.membership = CustomerMembership.objects.create(
            customer=self.customer, tenant=self.tenant, plan=self.plan,
            status='active', current_period_end=timezone.now() + timedelta(days=30),
        )

    @patch('djoyalty.paid_membership.CustomerMembership.cancel')
    def test_cancel_membership(self, mock_cancel):
        mock_cancel.return_value = True
        resp = self.cli.post('/api/loyalty/memberships/my/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'cancelled')
        self.assertIn('access_until', resp.data)
        mock_cancel.assert_called_once()

    @patch('djoyalty.paid_membership.CustomerMembership.renew')
    def test_renew_membership(self, mock_renew):
        mock_renew.return_value = True
        resp = self.cli.post('/api/loyalty/memberships/my/renew/', {
            'payment_reference': 'BKS-RENEW-001',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'renewed')
        mock_renew.assert_called_once()


class MembershipAdminTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.plan     = _plan(self.tenant)
        self.admin    = _admin()
        from djoyalty.paid_membership import CustomerMembership
        self.membership = CustomerMembership.objects.create(
            customer=self.customer, tenant=self.tenant, plan=self.plan,
            status='active', current_period_end=timezone.now() + timedelta(days=30),
        )

    def test_admin_active_list(self):
        resp = self.admin.get('/api/loyalty/memberships/admin/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('memberships', resp.data)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_admin_active_requires_admin(self):
        cli = _cli(self.customer)
        resp = cli.get('/api/loyalty/memberships/admin/active/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.advanced.MembershipViewSet.MembershipBenefitsManager.credit_monthly_bonus')
    def test_credit_bonus(self, mock_credit):
        mock_credit.return_value = True
        resp = self.admin.post(
            f'/api/loyalty/memberships/{self.membership.pk}/credit-bonus/',
            {'force': True, 'note': 'Manual credit'}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'credited')
        mock_credit.assert_called_once()
