# api/referral/tests/test_integration_system.py
# Tests for INTEGRATION_SYSTEM — bridge, adapters, event bus
# Run: python manage.py test api.referral.tests.test_integration_system
# ============================================================

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TestEventBus(TestCase):

    def test_subscribe_and_publish(self):
        from api.referral.INTEGRATION_SYSTEM.event_bus import ReferralEventBus

        bus = ReferralEventBus()
        received = []

        def handler(event, **kwargs):
            received.append({'event': event, **kwargs})

        bus.subscribe('test.event', handler)
        bus.publish('test.event', async_mode=False, data='hello')
        bus.unsubscribe('test.event', handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['event'], 'test.event')
        self.assertEqual(received[0]['data'], 'hello')

    def test_unsubscribe_stops_delivery(self):
        from api.referral.INTEGRATION_SYSTEM.event_bus import ReferralEventBus

        bus = ReferralEventBus()
        count = [0]

        def handler(event, **kwargs):
            count[0] += 1

        bus.subscribe('unsub.test', handler)
        bus.publish('unsub.test', async_mode=False)
        bus.unsubscribe('unsub.test', handler)
        bus.publish('unsub.test', async_mode=False)

        self.assertEqual(count[0], 1)

    def test_dead_letter_on_handler_error(self):
        from api.referral.INTEGRATION_SYSTEM.event_bus import ReferralEventBus

        bus = ReferralEventBus()

        def bad_handler(event, **kwargs):
            raise ValueError('Test error')

        bus.subscribe('error.event', bad_handler)
        bus.publish('error.event', async_mode=False)
        bus.unsubscribe('error.event', bad_handler)

        self.assertGreater(len(bus.get_dead_letters()), 0)

    def test_bus_stats(self):
        from api.referral.INTEGRATION_SYSTEM.event_bus import ReferralEventBus
        bus = ReferralEventBus()
        stats = bus.get_stats()
        self.assertIn('published_count', stats)
        self.assertIn('failed_count', stats)


class TestIntegrationRegistry(TestCase):

    def test_auto_discover(self):
        from api.referral.INTEGRATION_SYSTEM.integ_registry import get_registry
        registry = get_registry()
        results = registry.auto_discover_modules()
        self.assertIsInstance(results, dict)
        # wallet should be available in test env
        self.assertIn('wallet', results)

    def test_register_handler(self):
        from api.referral.INTEGRATION_SYSTEM.integ_registry import IntegrationRegistry

        registry = IntegrationRegistry.__new__(IntegrationRegistry)
        registry._handlers = {}
        registry._adapters = {}
        registry._module_status = {}

        def my_handler(**kwargs): pass

        registry.register_handler('test.event', my_handler, 'test')
        handlers = registry.get_handlers('test.event')
        self.assertIn(my_handler, handlers)

    def test_registry_status(self):
        from api.referral.INTEGRATION_SYSTEM.integ_registry import get_registry
        registry = get_registry()
        status = registry.get_status()
        self.assertIn('handlers', status)
        self.assertIn('adapters', status)
        self.assertIn('modules', status)


class TestDataBridge(TestCase):

    def test_to_decimal_string(self):
        from api.referral.INTEGRATION_SYSTEM.data_bridge import DataBridge
        result = DataBridge.to_decimal('10.50')
        self.assertEqual(result, Decimal('10.5000'))

    def test_to_decimal_none_returns_zero(self):
        from api.referral.INTEGRATION_SYSTEM.data_bridge import DataBridge
        result = DataBridge.to_decimal(None)
        self.assertEqual(result, Decimal('0'))

    def test_to_decimal_invalid_returns_zero(self):
        from api.referral.INTEGRATION_SYSTEM.data_bridge import DataBridge
        result = DataBridge.to_decimal('not_a_number')
        self.assertEqual(result, Decimal('0'))

    def test_safe_amount_zero_returns_zero(self):
        from api.referral.INTEGRATION_SYSTEM.data_bridge import DataBridge
        result = DataBridge.safe_amount('0')
        self.assertEqual(result, Decimal('0'))

    def test_settings_to_dict(self):
        from api.referral.models import ReferralSettings
        from api.referral.INTEGRATION_SYSTEM.data_bridge import DataBridge
        settings = ReferralSettings.objects.create(
            level1_commission_rate=Decimal('10'),
            level2_commission_rate=Decimal('5'),
        )
        d = DataBridge.settings_to_dict(settings)
        self.assertEqual(d['level1_rate'], 10.0)
        self.assertEqual(d['level2_rate'], 5.0)


class TestIntegrationValidator(TestCase):

    def test_valid_user(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        user = User.objects.create_user(username='iv_user', password='pass')
        v = IntegrationValidator()
        result = v.validate_user(user)
        self.assertTrue(result)
        self.assertTrue(v.is_valid())

    def test_none_user_invalid(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        result = v.validate_user(None)
        self.assertFalse(result)
        self.assertFalse(v.is_valid())

    def test_valid_amount(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        self.assertTrue(v.validate_amount(100))
        self.assertTrue(v.is_valid())

    def test_zero_amount_invalid(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        self.assertFalse(v.validate_amount(0))

    def test_valid_level(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        for level in [1, 2, 3]:
            v = IntegrationValidator()
            self.assertTrue(v.validate_level(level))

    def test_invalid_level(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        self.assertFalse(v.validate_level(0))
        self.assertFalse(v.validate_level(4))

    def test_valid_referral_code(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        self.assertTrue(v.validate_referral_code('EARN1234'))

    def test_invalid_referral_code(self):
        from api.referral.INTEGRATION_SYSTEM.data_validator import IntegrationValidator
        v = IntegrationValidator()
        self.assertFalse(v.validate_referral_code(''))
        self.assertFalse(v.validate_referral_code('AB'))


class TestIntegrationExceptions(TestCase):

    def test_module_unavailable_error(self):
        from api.referral.INTEGRATION_SYSTEM.integ_exceptions import ModuleUnavailableError
        e = ModuleUnavailableError('wallet')
        self.assertIn('wallet', str(e))
        self.assertEqual(e.module, 'wallet')

    def test_sync_conflict_error(self):
        from api.referral.INTEGRATION_SYSTEM.integ_exceptions import SyncConflictError
        e = SyncConflictError('conflict', conflicting_ids=[1, 2, 3])
        self.assertEqual(e.conflicting_ids, [1, 2, 3])

    def test_circuit_breaker_error(self):
        from api.referral.INTEGRATION_SYSTEM.integ_exceptions import CircuitBreakerOpenError
        e = CircuitBreakerOpenError('test_service')
        self.assertIn('test_service', str(e))


class TestFallbackLogic(TestCase):

    def test_circuit_breaker_success(self):
        from api.referral.INTEGRATION_SYSTEM.fallback_logic import CircuitBreaker

        cb = CircuitBreaker('test_cb')

        def good_func():
            return 'ok'

        result = cb.call(good_func, fallback='fallback_val')
        self.assertEqual(result, 'ok')
        self.assertEqual(cb._state, 'CLOSED')

    def test_circuit_breaker_opens_on_failures(self):
        from api.referral.INTEGRATION_SYSTEM.fallback_logic import CircuitBreaker

        cb = CircuitBreaker('test_cb2')
        cb.FAILURE_THRESHOLD = 2

        def bad_func():
            raise Exception('fail')

        for _ in range(2):
            try:
                cb.call(bad_func, fallback='fb')
            except Exception:
                pass

        self.assertEqual(cb._state, 'OPEN')

    def test_with_fallback_decorator(self):
        from api.referral.INTEGRATION_SYSTEM.fallback_logic import with_fallback

        @with_fallback(fallback_value='default')
        def risky():
            raise RuntimeError('oops')

        result = risky()
        self.assertEqual(result, 'default')

    def test_with_retry_succeeds_eventually(self):
        from api.referral.INTEGRATION_SYSTEM.fallback_logic import with_retry

        call_count = [0]

        @with_retry(max_retries=3, delay=0)
        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception('not yet')
            return 'success'

        result = flaky()
        self.assertEqual(result, 'success')
        self.assertEqual(call_count[0], 3)


class TestAuthBridge(TestCase):

    def setUp(self):
        self.regular = User.objects.create_user(username='ab_reg', password='pass')
        self.staff    = User.objects.create_user(username='ab_staff', password='pass', is_staff=True)
        self.superuser = User.objects.create_user(username='ab_super', password='pass', is_superuser=True)

    def test_superuser_can_view(self):
        from api.referral.INTEGRATION_SYSTEM.auth_bridge import ReferralAuthBridge
        self.assertTrue(ReferralAuthBridge.can_view_referrals(self.superuser))

    def test_staff_can_manage_fraud(self):
        from api.referral.INTEGRATION_SYSTEM.auth_bridge import ReferralAuthBridge
        self.assertTrue(ReferralAuthBridge.can_manage_fraud(self.staff))

    def test_regular_user_cannot_manage_fraud(self):
        from api.referral.INTEGRATION_SYSTEM.auth_bridge import ReferralAuthBridge
        self.assertFalse(ReferralAuthBridge.can_manage_fraud(self.regular))

    def test_none_user_cannot_view(self):
        from api.referral.INTEGRATION_SYSTEM.auth_bridge import ReferralAuthBridge
        self.assertFalse(ReferralAuthBridge.can_view_referrals(None))

    def test_get_permissions_dict(self):
        from api.referral.INTEGRATION_SYSTEM.auth_bridge import ReferralAuthBridge
        perms = ReferralAuthBridge.get_referral_permissions_for_user(self.superuser)
        self.assertIn('can_view', perms)
        self.assertIn('can_manage_campaigns', perms)
        self.assertTrue(perms['can_view'])


class TestPerformanceMonitor(TestCase):

    def test_track_context_manager(self):
        from api.referral.INTEGRATION_SYSTEM.performance_monitor import get_monitor

        monitor = get_monitor()
        with monitor.track('test_operation'):
            pass  # Simulate work

        stats = monitor.get_stats('test_operation')
        self.assertIn('calls', stats)
        self.assertGreater(stats['calls'], 0)

    def test_error_tracked_on_exception(self):
        from api.referral.INTEGRATION_SYSTEM.performance_monitor import get_monitor

        monitor = get_monitor()
        try:
            with monitor.track('error_operation'):
                raise ValueError('test error')
        except ValueError:
            pass

        stats = monitor.get_stats('error_operation')
        self.assertGreater(stats.get('errors', 0), 0)

    def test_summary_returns_counts(self):
        from api.referral.INTEGRATION_SYSTEM.performance_monitor import get_monitor
        summary = get_monitor().get_summary()
        self.assertIn('total_operations', summary)
        self.assertIn('operations', summary)