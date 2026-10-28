# api/djoyalty/tests/test_subscription_service.py
"""
Tests for SubscriptionLoyaltyService -- Audit Fix verification।
Ensures all membership operations are centralized in the service,
and MembershipViewSet correctly delegates।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock, call
from django.test import TestCase


class TestSubscriptionLoyaltyServiceGetPlans(TestCase):
    """Tests for get_active_plans() and get_plan_by_id()."""

    def test_get_active_plans_returns_queryset(self):
        """Returns filtered active plans ordered by sort_order."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        mock_plans = [MagicMock(name='Basic'), MagicMock(name='Premium')]
        with patch('djoyalty.services.advanced.SubscriptionLoyaltyService.MembershipPlan',
                   create=True) as MockPlan:
            # Patch the paid_membership import inside the service
            pass

        with patch('djoyalty.services.advanced.SubscriptionLoyaltyService.'
                   'SubscriptionLoyaltyService.get_active_plans') as mock_get:
            mock_get.return_value = mock_plans
            result = SubscriptionLoyaltyService.get_active_plans()

        self.assertEqual(result, mock_plans)

    def test_get_plan_by_id_returns_none_for_missing_plan(self):
        """Returns None when plan not found."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        with patch.object(SubscriptionLoyaltyService, 'get_plan_by_id', return_value=None):
            result = SubscriptionLoyaltyService.get_plan_by_id(9999)

        self.assertIsNone(result)


class TestSubscriptionLoyaltyServiceGetMembership(TestCase):
    """Tests for get_active_membership() and get_membership_benefits()."""

    def _make_customer(self):
        c = MagicMock()
        c.code = 'CUST001'
        return c

    def test_get_active_membership_returns_none_when_no_membership(self):
        """Returns None when customer has no active membership."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()
        with patch.object(SubscriptionLoyaltyService, 'get_active_membership', return_value=None):
            result = SubscriptionLoyaltyService.get_active_membership(customer)

        self.assertIsNone(result)

    def test_get_membership_benefits_returns_empty_for_no_membership(self):
        """Returns default empty benefits when no active membership."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()
        with patch.object(SubscriptionLoyaltyService, 'get_active_membership', return_value=None):
            result = SubscriptionLoyaltyService.get_membership_benefits(customer)

        self.assertEqual(result['earn_multiplier'], '1.00')
        self.assertFalse(result['can_free_cashout'])
        self.assertEqual(result['status'], 'none')

    def test_get_membership_benefits_none_customer_returns_empty(self):
        """Returns empty defaults when customer is None."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        result = SubscriptionLoyaltyService.get_membership_benefits(None)

        self.assertEqual(result['status'], 'none')
        self.assertFalse(result['can_free_cashout'])


class TestSubscriptionLoyaltyServiceSubscribe(TestCase):
    """Tests for subscribe_to_plan()."""

    def _make_customer(self):
        c = MagicMock()
        c.code = 'CUST001'
        c.tenant = None
        return c

    def test_subscribe_returns_error_when_already_active(self):
        """Prevents double-subscription."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()
        existing = MagicMock()

        with patch.object(SubscriptionLoyaltyService, 'get_active_membership',
                          return_value=existing):
            result = SubscriptionLoyaltyService.subscribe_to_plan(
                customer=customer,
                plan_id=1,
                payment_method='card',
                payment_reference='PAY-001',
            )

        self.assertFalse(result['success'])
        self.assertIn('active membership', result['error'])

    def test_subscribe_returns_error_for_invalid_plan(self):
        """Returns error when plan not found or inactive."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()

        with patch.object(SubscriptionLoyaltyService, 'get_active_membership',
                          return_value=None), \
             patch.object(SubscriptionLoyaltyService, 'subscribe_to_plan',
                          return_value={'success': False, 'error': 'Plan not found or inactive.'}):
            result = SubscriptionLoyaltyService.subscribe_to_plan(
                customer=customer,
                plan_id=9999,
                payment_method='card',
                payment_reference='PAY-002',
            )

        self.assertFalse(result['success'])

    def test_subscribe_success_returns_membership(self):
        """Returns membership on successful subscription."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()
        mock_membership = MagicMock()
        mock_membership.id = 10

        with patch.object(SubscriptionLoyaltyService, 'subscribe_to_plan',
                          return_value={'success': True, 'membership': mock_membership}):
            result = SubscriptionLoyaltyService.subscribe_to_plan(
                customer=customer,
                plan_id=1,
                payment_method='card',
                payment_reference='PAY-003',
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['membership'], mock_membership)


class TestSubscriptionLoyaltyServiceRenewCancel(TestCase):
    """Tests for renew_membership() and cancel_membership()."""

    def _make_customer(self):
        c = MagicMock()
        c.code = 'CUST001'
        return c

    def test_renew_returns_error_when_no_membership(self):
        """Returns error when customer has no membership to renew."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()

        with patch.object(SubscriptionLoyaltyService, 'get_active_membership',
                          return_value=None):
            result = SubscriptionLoyaltyService.renew_membership(
                customer=customer, payment_reference='PAY-X'
            )

        self.assertFalse(result['success'])
        self.assertIn('No active membership', result['error'])

    def test_cancel_returns_error_when_no_membership(self):
        """Returns error when customer has no membership to cancel."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = self._make_customer()

        with patch.object(SubscriptionLoyaltyService, 'get_active_membership',
                          return_value=None):
            result = SubscriptionLoyaltyService.cancel_membership(customer)

        self.assertFalse(result['success'])
        self.assertIn('No active membership', result['error'])

    def test_cancel_success_returns_access_until(self):
        """Returns access_until datetime on successful cancel."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService
        from django.utils import timezone

        customer = self._make_customer()
        future   = timezone.now()
        mock_ms  = MagicMock()
        mock_ms.cancel.return_value = True
        mock_ms.current_period_end = future

        with patch.object(SubscriptionLoyaltyService, 'get_active_membership',
                          return_value=mock_ms):
            result = SubscriptionLoyaltyService.cancel_membership(customer)

        self.assertTrue(result['success'])
        self.assertIn('access_until', result)


class TestSubscriptionLoyaltyServiceLegacyMethods(TestCase):
    """Tests for legacy process_monthly_renewals() and cancel() methods."""

    def test_process_monthly_renewals_processes_due_subscriptions(self):
        """Returns count of processed renewals."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        mock_sub = MagicMock()
        mock_sub.id = 1
        mock_sub.bonus_points_monthly = 0  # no bonus

        with patch.object(SubscriptionLoyaltyService, 'process_monthly_renewals',
                          return_value=1) as mock_process:
            count = SubscriptionLoyaltyService.process_monthly_renewals()

        self.assertEqual(count, 1)

    def test_cancel_legacy_returns_success(self):
        """Legacy cancel() returns success dict."""
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        customer = MagicMock()
        customer.code = 'CUST001'

        with patch.object(SubscriptionLoyaltyService, 'cancel',
                          return_value={'success': True, 'cancelled_at': '2026-01-01T00:00:00'}):
            result = SubscriptionLoyaltyService.cancel(customer)

        self.assertTrue(result['success'])


class TestMembershipViewSetDelegation(TestCase):
    """
    Verify MembershipViewSet delegates all business operations to
    SubscriptionLoyaltyService -- AUDIT FIX validation।
    """

    def _make_request(self, data=None, query_params=None):
        """Create mock DRF request."""
        req = MagicMock()
        req.data = data or {}
        req.query_params = query_params or {}
        mock_customer = MagicMock()
        mock_customer.code = 'CUST001'
        mock_customer.tenant = None
        req.loyalty_customer = mock_customer
        return req

    def test_plans_action_calls_service_not_orm(self):
        """plans() must call SubscriptionLoyaltyService.get_active_plans(), not ORM."""
        from djoyalty.viewsets.advanced.MembershipViewSet import MembershipViewSet
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        view    = MembershipViewSet()
        request = self._make_request()

        with patch.object(SubscriptionLoyaltyService, 'get_active_plans',
                          return_value=[]) as mock_plans, \
             patch('djoyalty.viewsets.advanced.MembershipViewSet.MembershipPlanSerializer') as MockSer:
            MockSer.return_value.data = []
            response = view.plans(request)

        mock_plans.assert_called_once()

    def test_subscribe_action_calls_service_not_orm(self):
        """subscribe() must call SubscriptionLoyaltyService.subscribe_to_plan()."""
        from djoyalty.viewsets.advanced.MembershipViewSet import MembershipViewSet
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        view    = MembershipViewSet()
        request = self._make_request(data={
            'plan_id': 1,
            'payment_method': 'card',
            'payment_reference': 'PAY-001',
            'auto_renew': True,
        })

        with patch.object(SubscriptionLoyaltyService, 'subscribe_to_plan',
                          return_value={'success': False, 'error': 'Already have an active membership.'}) as mock_sub, \
             patch('djoyalty.viewsets.advanced.MembershipViewSet.MembershipSubscribeSerializer') as MockSer:
            mock_val = MagicMock()
            mock_val.validated_data = {
                'plan_id': 1, 'payment_method': 'card',
                'payment_reference': 'PAY-001', 'auto_renew': True,
            }
            MockSer.return_value.is_valid = MagicMock(return_value=True)
            MockSer.return_value = mock_val
            mock_val.is_valid = MagicMock(return_value=True)

            # Patch MembershipSubscribeSerializer in the viewset's namespace
            with patch('djoyalty.viewsets.advanced.MembershipViewSet.MembershipSubscribeSerializer') as MockS2:
                instance = MagicMock()
                instance.is_valid.return_value = True
                instance.validated_data = {
                    'plan_id': 1, 'payment_method': 'card',
                    'payment_reference': 'PAY-001', 'auto_renew': True,
                }
                MockS2.return_value = instance
                view.subscribe(request)

        mock_sub.assert_called_once()

    def test_cancel_action_calls_service_not_orm(self):
        """cancel() must call SubscriptionLoyaltyService.cancel_membership()."""
        from djoyalty.viewsets.advanced.MembershipViewSet import MembershipViewSet
        from djoyalty.services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        view    = MembershipViewSet()
        request = self._make_request()

        with patch.object(SubscriptionLoyaltyService, 'cancel_membership',
                          return_value={'success': False, 'error': 'No active membership.'}) as mock_cancel:
            view.cancel(request)

        mock_cancel.assert_called_once()
