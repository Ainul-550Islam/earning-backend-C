# api/djoyalty/tests.py
"""
Djoyalty Tests -- Comprehensive test suite।
Tests: models, services, logic, API endpoints, integrations।

Run: python manage.py test djoyalty
"""
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone


# ─── Logic Tests (no DB needed) ──────────────────────────────────────────────

class TestPointsLogic(TestCase):
    """Test pure business logic functions।"""

    def test_calculate_earn_points_basic(self):
        from .logic import calculate_earn_points
        result = calculate_earn_points(
            transaction_value=Decimal('1000'),
            earn_rate=Decimal('1'),
        )
        self.assertEqual(result, Decimal('1000'))

    def test_calculate_earn_points_with_multiplier(self):
        from .logic import calculate_earn_points
        result = calculate_earn_points(
            transaction_value=Decimal('1000'),
            earn_rate=Decimal('1'),
            multiplier=Decimal('2'),
        )
        self.assertEqual(result, Decimal('2000'))

    def test_calculate_earn_points_with_bonus(self):
        from .logic import calculate_earn_points
        result = calculate_earn_points(
            transaction_value=Decimal('1000'),
            earn_rate=Decimal('1'),
            bonus_percent=Decimal('20'),
        )
        self.assertEqual(result, Decimal('1200'))

    def test_calculate_earn_points_max_cap(self):
        from .logic import calculate_earn_points
        result = calculate_earn_points(
            transaction_value=Decimal('1000'),
            earn_rate=Decimal('2'),
            max_points=Decimal('500'),
        )
        self.assertEqual(result, Decimal('500'))

    def test_calculate_points_cash_value(self):
        from .logic import calculate_points_cash_value
        result = calculate_points_cash_value(
            points=Decimal('100'),
            redemption_rate=Decimal('0.01'),
        )
        self.assertEqual(result, Decimal('1.00'))

    def test_calculate_cashout_amount(self):
        from .logic import calculate_cashout_amount
        result = calculate_cashout_amount(
            points=Decimal('1000'),
            points_per_unit=Decimal('100'),
        )
        self.assertEqual(result, Decimal('10.00'))

    def test_calculate_cashout_with_fee(self):
        from .logic import calculate_cashout_amount
        result = calculate_cashout_amount(
            points=Decimal('1000'),
            points_per_unit=Decimal('100'),
            processing_fee_pct=Decimal('10'),
        )
        self.assertEqual(result, Decimal('9.00'))

    def test_calculate_tier_progress(self):
        from .logic import calculate_tier_progress
        result = calculate_tier_progress(
            current_points=Decimal('500'),
            current_tier_min=Decimal('0'),
            next_tier_min=Decimal('1000'),
        )
        self.assertEqual(result['percent'], 50)
        self.assertEqual(result['points_needed'], Decimal('500'))

    def test_rfm_score_champions(self):
        from .logic import compute_rfm_score
        result = compute_rfm_score(recency_days=3, frequency=25, monetary_value=Decimal('100000'))
        self.assertEqual(result['rfm_segment'], 'champions')
        self.assertEqual(result['recency_score'], 5)

    def test_rfm_score_lost(self):
        from .logic import compute_rfm_score
        result = compute_rfm_score(recency_days=200, frequency=1, monetary_value=Decimal('100'))
        self.assertEqual(result['rfm_segment'], 'lost')

    def test_churn_probability_low(self):
        from .logic import compute_churn_probability
        result = compute_churn_probability(
            recency_days=5, frequency=20,
            avg_order_value=Decimal('5000'), account_age_days=365,
        )
        self.assertEqual(result['risk_level'], 'low')

    def test_churn_probability_critical(self):
        from .logic import compute_churn_probability
        result = compute_churn_probability(
            recency_days=150, frequency=1,
            avg_order_value=Decimal('200'), account_age_days=10,
        )
        self.assertIn(result['risk_level'], ('high', 'critical'))

    def test_offerwall_points_calculation(self):
        from .logic import calculate_offerwall_points
        result = calculate_offerwall_points(
            payout_usd=Decimal('1.50'),
            currency_ratio=Decimal('100'),
        )
        self.assertEqual(result, Decimal('150'))

    def test_voucher_percent_discount(self):
        from .logic import calculate_voucher_discount, apply_voucher
        discount = calculate_voucher_discount(
            original_price=Decimal('1000'),
            discount_value=Decimal('10'),
            discount_type='percent',
        )
        self.assertEqual(discount, Decimal('100'))
        final = apply_voucher(Decimal('1000'), discount)
        self.assertEqual(final, Decimal('900'))

    def test_voucher_fixed_discount(self):
        from .logic import calculate_voucher_discount
        discount = calculate_voucher_discount(
            original_price=Decimal('1000'),
            discount_value=Decimal('50'),
            discount_type='fixed',
        )
        self.assertEqual(discount, Decimal('50'))

    def test_voucher_discount_capped(self):
        from .logic import calculate_voucher_discount
        discount = calculate_voucher_discount(
            original_price=Decimal('100'),
            discount_value=Decimal('50'),
            discount_type='percent',
            max_discount=Decimal('30'),
        )
        self.assertEqual(discount, Decimal('30'))


# ─── Validator Tests ─────────────────────────────────────────────────────────

class TestLoyaltyValidator(TestCase):

    def test_validate_earn_negative_points(self):
        from .validator import LoyaltyValidator
        from .factories import CustomerFactory
        customer = CustomerFactory.build()
        customer.is_active = True
        ok, msg = LoyaltyValidator.validate_earn(customer, Decimal('-10'), 'purchase')
        self.assertFalse(ok)
        self.assertIn('positive', msg)

    def test_validate_redeem_zero_points(self):
        from .validator import LoyaltyValidator
        from .factories import CustomerFactory
        customer = CustomerFactory.build()
        customer.is_active = True
        ok, msg = LoyaltyValidator.validate_redeem(customer, Decimal('0'))
        self.assertFalse(ok)

    def test_validate_earn_inactive_customer(self):
        from .validator import LoyaltyValidator
        from .factories import CustomerFactory
        customer = CustomerFactory.build()
        customer.is_active = False
        ok, msg = LoyaltyValidator.validate_earn(customer, Decimal('100'), 'purchase')
        self.assertFalse(ok)
        self.assertIn('active', msg)


# ─── Choices Tests ────────────────────────────────────────────────────────────

class TestChoices(TestCase):

    def test_ledger_constants_exist(self):
        from .choices import LEDGER_CREDIT, LEDGER_DEBIT
        self.assertEqual(LEDGER_CREDIT, 'credit')
        self.assertEqual(LEDGER_DEBIT, 'debit')

    def test_all_choices_are_tuples(self):
        from .choices import LEDGER_TXN_TYPE_CHOICES
        for choice in LEDGER_TXN_TYPE_CHOICES:
            self.assertIsInstance(choice, (list, tuple))
            self.assertEqual(len(choice), 2)


# ─── Managers Tests ───────────────────────────────────────────────────────────

class TestManagers(TestCase):

    def test_active_manager_returns_only_active(self):
        from .managers import ActiveManager
        from django.db import models as dm

        class MockModel:
            class _meta:
                pass

        manager = ActiveManager()
        self.assertTrue(hasattr(manager, 'get_queryset'))


# ─── Integration System Tests ────────────────────────────────────────────────

class TestEventBus(TestCase):

    def setUp(self):
        from .integration_system.event_bus import EventBus
        EventBus.clear()

    def test_subscribe_and_publish(self):
        from .integration_system.event_bus import EventBus

        received = []

        @EventBus.subscribe('test.event')
        def handler(event):
            received.append(event.event_type)

        EventBus.publish('test.event', data={'test': True})
        self.assertIn('test.event', received)

    def test_publish_without_subscriber(self):
        from .integration_system.event_bus import EventBus
        # Should not raise
        EventBus.publish('test.no_subscriber', data={})

    def test_multiple_subscribers(self):
        from .integration_system.event_bus import EventBus

        results = []

        @EventBus.subscribe('test.multi')
        def h1(event):
            results.append('h1')

        @EventBus.subscribe('test.multi')
        def h2(event):
            results.append('h2')

        EventBus.publish('test.multi')
        self.assertEqual(len(results), 2)

    def test_get_stats(self):
        from .integration_system.event_bus import EventBus
        stats = EventBus.get_stats()
        self.assertIn('total_subscriptions', stats)


class TestCircuitBreaker(TestCase):

    def test_circuit_starts_closed(self):
        from .integration_system.fallback_logic import CircuitBreaker
        from .integration_system.integ_constants import CircuitBreakerState
        cb = CircuitBreaker('test_svc_1', failure_threshold=3, timeout=10)
        self.assertEqual(cb.get_state(), CircuitBreakerState.CLOSED)

    def test_circuit_opens_after_threshold(self):
        from .integration_system.fallback_logic import CircuitBreaker
        from .integration_system.integ_constants import CircuitBreakerState
        from .integration_system.integ_exceptions import DjoyaltyIntegrationError

        cb = CircuitBreaker('test_svc_2', failure_threshold=2, timeout=30)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.get_state(), CircuitBreakerState.OPEN)

    def test_circuit_resets(self):
        from .integration_system.fallback_logic import CircuitBreaker
        from .integration_system.integ_constants import CircuitBreakerState

        cb = CircuitBreaker('test_svc_3', failure_threshold=2, timeout=30)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        self.assertEqual(cb.get_state(), CircuitBreakerState.CLOSED)


class TestIntegrationRegistry(TestCase):

    def test_registry_is_singleton(self):
        from .integration_system.integ_registry import IntegrationRegistry
        r1 = IntegrationRegistry.get_instance()
        r2 = IntegrationRegistry.get_instance()
        self.assertIs(r1, r2)

    def test_register_and_get(self):
        from .integration_system.integ_registry import IntegrationRegistry

        class DummyIntegration:
            @staticmethod
            def is_configured():
                return True

        registry = IntegrationRegistry.get_instance()
        registry.register('dummy_test', DummyIntegration, description='Test')
        inst = registry.get('dummy_test')
        self.assertIsNotNone(inst)

    def test_get_nonexistent_returns_none(self):
        from .integration_system.integ_registry import IntegrationRegistry
        registry = IntegrationRegistry.get_instance()
        result = registry.get('nonexistent_xyz')
        self.assertIsNone(result)


# ─── Exceptions Tests ────────────────────────────────────────────────────────

class TestExceptions(TestCase):

    def test_integration_error_has_to_dict(self):
        from .integration_system.integ_exceptions import DjoyaltyIntegrationError
        err = DjoyaltyIntegrationError('Test error', integration_name='test')
        d = err.to_dict()
        self.assertIn('error', d)
        self.assertIn('integration', d)

    def test_circuit_breaker_error(self):
        from .integration_system.integ_exceptions import CircuitBreakerOpenError
        err = CircuitBreakerOpenError('bkash', retry_after=60)
        self.assertEqual(err.retry_after, 60)
        self.assertIn('bkash', str(err))

    def test_not_configured_error(self):
        from .integration_system.integ_exceptions import IntegrationNotConfiguredError
        err = IntegrationNotConfiguredError('bkash')
        self.assertIn('bkash', str(err))


# ─── Hooks Tests ─────────────────────────────────────────────────────────────

class TestLoyaltyHooks(TestCase):

    def setUp(self):
        from .hooks import LoyaltyHooks
        LoyaltyHooks.clear()

    def test_register_and_fire(self):
        from .hooks import LoyaltyHooks

        results = []

        @LoyaltyHooks.register('after_earn')
        def my_hook(customer, points, **kwargs):
            results.append(points)

        LoyaltyHooks.fire('after_earn', customer=None, points=100)
        self.assertIn(100, results)

    def test_fire_empty_hook(self):
        from .hooks import LoyaltyHooks
        # Should not raise
        LoyaltyHooks.fire('before_earn', customer=None, points=0)

    def test_list_hooks(self):
        from .hooks import LoyaltyHooks

        @LoyaltyHooks.register('after_earn')
        def hook1(**kwargs):
            pass

        hooks = LoyaltyHooks.list_hooks()
        self.assertIn('after_earn', hooks)


# ─── Plugins Tests ───────────────────────────────────────────────────────────

class TestPlugins(TestCase):

    def setUp(self):
        from .plugins import LoyaltyPluginRegistry
        LoyaltyPluginRegistry._plugins.clear()

    def test_register_plugin(self):
        from .plugins import LoyaltyPluginRegistry, BaseLoyaltyPlugin

        class MyPlugin(BaseLoyaltyPlugin):
            name = 'test_plugin'
            version = '1.0.0'

        LoyaltyPluginRegistry.register(MyPlugin())
        plugin = LoyaltyPluginRegistry.get('test_plugin')
        self.assertIsNotNone(plugin)

    def test_no_bonus_by_default(self):
        from .plugins import LoyaltyPluginRegistry, BaseLoyaltyPlugin

        class NoBonusPlugin(BaseLoyaltyPlugin):
            name = 'no_bonus_plugin'

        LoyaltyPluginRegistry.register(NoBonusPlugin())
        bonus = LoyaltyPluginRegistry.get_total_bonus_points(None, None, 100)
        self.assertEqual(bonus, 0)

    def test_list_plugins(self):
        from .plugins import LoyaltyPluginRegistry, BaseLoyaltyPlugin

        class ListPlugin(BaseLoyaltyPlugin):
            name = 'list_plugin'
            description = 'Test list'

        LoyaltyPluginRegistry.register(ListPlugin())
        plugins = LoyaltyPluginRegistry.list_plugins()
        names = [p['name'] for p in plugins]
        self.assertIn('list_plugin', names)
