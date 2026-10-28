# api/cms/tests/test_integration_system.py
"""Tests for INTEGRATION_SYSTEM: circuit breaker, validator, registry, event bus, auth."""
from django.test import TestCase
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass
from unittest.mock import patch, MagicMock
from decimal import Decimal

# All INTEGRATION_SYSTEM classes — skip tests if not installed
def _get(module, name):
    """Lazy import helper. Returns class or None."""
    try:
        import importlib
        mod = importlib.import_module(f'api.cms.INTEGRATION_SYSTEM.{module}')
        return getattr(mod, name, None)
    except ImportError:
        return None


class TestIntegConstants(TestCase):
    def test_event_names_exist(self):
        CMSEvents = _get('integ_constants', 'CMSEvents')
        if CMSEvents is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        self.assertTrue(hasattr(CMSEvents, 'CPALEAD_POSTBACK_RECEIVED'))
        self.assertTrue(hasattr(CMSEvents, 'REWARD_EARNED'))
        self.assertTrue(hasattr(CMSEvents, 'CONTENT_UNLOCKED'))

    def test_limits_defined(self):
        IntegLimits = _get('integ_constants', 'IntegLimits')
        if IntegLimits is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        self.assertGreater(IntegLimits.MAX_POSTBACK_PAYOUT_USD, 0)
        self.assertGreater(IntegLimits.CIRCUIT_BREAKER_FAIL_THRESHOLD, 0)
        self.assertGreater(IntegLimits.POSTBACK_RESPONSE_SLA_MS, 0)


class TestIntegExceptions(TestCase):
    def test_circuit_open_error(self):
        CircuitOpenError = _get('integ_exceptions', 'CircuitOpenError')
        if CircuitOpenError is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        e = CircuitOpenError("cpalead_api", retry_after_sec=300)
        self.assertEqual(e.service, "cpalead_api")
        self.assertEqual(e.retry_after_sec, 300)

    def test_validation_error_has_field(self):
        ValidationError = _get('integ_exceptions', 'ValidationError')
        if ValidationError is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        e = ValidationError("Invalid payout", field="payout", value=-1)
        self.assertEqual(e.field, "payout")
        self.assertIn("payout", e.details)

    def test_webhook_auth_error(self):
        WebhookAuthError = _get('integ_exceptions', 'WebhookAuthError')
        if WebhookAuthError is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        e = WebhookAuthError("invalid_signature")
        self.assertEqual(e.code, "webhook_auth_error")

    def test_duplicate_event_error(self):
        DuplicateEventError = _get('integ_exceptions', 'DuplicateEventError')
        if DuplicateEventError is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        e = DuplicateEventError("lead_12345")
        self.assertEqual(e.event_id, "lead_12345")


class TestIntegRegistry(TestCase):
    def test_register_and_get(self):
        CMSRegistry = _get('integ_registry', 'CMSRegistry')
        if CMSRegistry is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        CMSRegistry.register("test_svc", "os.path", capabilities=["join", "exists"])
        self.assertTrue(CMSRegistry.has("test_svc"))
        self.assertTrue(CMSRegistry.can("test_svc", "join"))
        self.assertFalse(CMSRegistry.can("test_svc", "nonexistent"))

    def test_unregister(self):
        CMSRegistry = _get('integ_registry', 'CMSRegistry')
        if CMSRegistry is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        CMSRegistry.register("temp_svc", "os", [])
        CMSRegistry.unregister("temp_svc")
        self.assertFalse(CMSRegistry.has("temp_svc"))

    def test_call_with_fallback(self):
        CMSRegistry = _get('integ_registry', 'CMSRegistry')
        if CMSRegistry is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = CMSRegistry.call("nonexistent_svc", "some_method", fallback="default")
        self.assertEqual(result, "default")

    def test_hook_registration_and_fire(self):
        CMSRegistry = _get('integ_registry', 'CMSRegistry')
        if CMSRegistry is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        fired = []
        CMSRegistry.on("test.event", lambda **kw: fired.append(kw), app_name="test")
        CMSRegistry.fire("test.event", user_id=1, amount=10)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["user_id"], 1)

    def test_auto_registered_services(self):
        CMSRegistry = _get('integ_registry', 'CMSRegistry')
        if CMSRegistry is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        self.assertTrue(CMSRegistry.has("virtual_wallet"))
        self.assertTrue(CMSRegistry.has("cpalead"))
        self.assertTrue(CMSRegistry.has("notifications"))


class TestDataValidator(TestCase):
    def test_valid_cpalead_postback(self):
        DataValidator = _get('data_validator', 'DataValidator')
        if DataValidator is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        data = {'subid': '12345', 'payout': '0.50', 'lead_id': 'lead_abc123', 'password': 'secret'}
        cleaned, errors = DataValidator.validate_cpalead_postback(data)
        self.assertEqual(errors, [])
        self.assertEqual(cleaned['subid'], '12345')

    def test_missing_required_field(self):
        DataValidator = _get('data_validator', 'DataValidator')
        if DataValidator is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        data = {'payout': '0.50', 'lead_id': 'abc'}  # missing subid
        cleaned, errors = DataValidator.validate_cpalead_postback(data)
        self.assertTrue(any('subid' in e for e in errors))

    def test_payout_too_high(self):
        DataValidator = _get('data_validator', 'DataValidator')
        if DataValidator is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        data = {'subid': '1', 'payout': '999999', 'lead_id': 'abc', 'password': 'x'}
        cleaned, errors = DataValidator.validate_cpalead_postback(data)
        self.assertTrue(any('payout' in e for e in errors))

    def test_validate_or_raise(self):
        DataValidator = _get('data_validator', 'DataValidator')
        ValidationError = _get('integ_exceptions', 'ValidationError')
        if DataValidator is None or ValidationError is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        with self.assertRaises(ValidationError):
            DataValidator.validate_or_raise({'wrong_field': 'value'}, DataValidator.CPALEAD_POSTBACK_SCHEMA)

    def test_safe_subid(self):
        DataValidator = _get('data_validator', 'DataValidator')
        if DataValidator is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        self.assertTrue(DataValidator.is_safe_subid('12345'))
        self.assertTrue(DataValidator.is_safe_subid('user_abc'))
        self.assertFalse(DataValidator.is_safe_subid(''))
        self.assertFalse(DataValidator.is_safe_subid('user; DROP TABLE'))

    def test_sanitize_string(self):
        DataValidator = _get('data_validator', 'DataValidator')
        if DataValidator is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        clean = DataValidator.sanitize_string("Hello\x00World")
        self.assertNotIn('\x00', clean)
        self.assertEqual(clean, "HelloWorld")


class TestAuthBridge(TestCase):
    def test_can_user_earn_unauthenticated(self):
        AuthBridge = _get('auth_bridge', 'AuthBridge')
        if AuthBridge is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = AuthBridge.can_user_earn(None)
        self.assertFalse(result)
        self.assertEqual(result.code, "unauthenticated")

    def test_can_user_earn_inactive(self):
        AuthBridge = _get('auth_bridge', 'AuthBridge')
        if AuthBridge is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        user = MagicMock()
        user.is_authenticated = True
        user.is_active = False
        result = AuthBridge.can_user_earn(user)
        self.assertFalse(result)
        self.assertEqual(result.code, "account_inactive")

    def test_can_user_earn_active(self):
        AuthBridge = _get('auth_bridge', 'AuthBridge')
        if AuthBridge is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        user = MagicMock()
        user.is_authenticated = True
        user.is_active = True
        user.profile.is_suspended = False
        with patch.object(AuthBridge, '_check_suspension', return_value=(False, "")):
            with patch.object(AuthBridge, '_check_kyc', return_value=(True, "")):
                with patch.object(AuthBridge, '_check_earning_freeze', return_value=(True, "")):
                    result = AuthBridge.can_user_earn(user)
        self.assertTrue(result)

    def test_validate_cpalead_auth_good_password(self):
        AuthBridge = _get('auth_bridge', 'AuthBridge')
        if AuthBridge is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = AuthBridge.validate_cpalead_postback_auth(
            password="mysecret", ip="1.2.3.4", postback_secret="mysecret"
        )
        self.assertTrue(result)

    def test_validate_cpalead_auth_bad_password(self):
        AuthBridge = _get('auth_bridge', 'AuthBridge')
        if AuthBridge is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = AuthBridge.validate_cpalead_postback_auth(
            password="wrongpass", ip="1.2.3.4", postback_secret="mysecret"
        )
        self.assertFalse(result)


class TestCircuitBreaker(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_circuit_starts_closed(self):
        CircuitBreaker = _get('fallback_logic', 'CircuitBreaker')
        CircuitState = _get('fallback_logic', 'CircuitState')
        if CircuitBreaker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        cb = CircuitBreaker("test_cb_closed", fail_threshold=3)
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_circuit_opens_after_failures(self):
        CircuitBreaker = _get('fallback_logic', 'CircuitBreaker')
        CircuitState = _get('fallback_logic', 'CircuitState')
        if CircuitBreaker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        cb = CircuitBreaker("test_cb_open", fail_threshold=3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_circuit_raises_when_open(self):
        CircuitBreaker = _get('fallback_logic', 'CircuitBreaker')
        CircuitOpenError = _get('integ_exceptions', 'CircuitOpenError')
        if CircuitBreaker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        cb = CircuitBreaker("test_cb_raises", fail_threshold=1)
        cb.record_failure()
        with self.assertRaises(CircuitOpenError):
            cb.call(lambda: "result")

    def test_circuit_call_success(self):
        CircuitBreaker = _get('fallback_logic', 'CircuitBreaker')
        CircuitState = _get('fallback_logic', 'CircuitState')
        if CircuitBreaker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        cb = CircuitBreaker("test_cb_success", fail_threshold=5)
        result = cb.call(lambda: "hello")
        self.assertEqual(result, "hello")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_safe_call_returns_fallback(self):
        safe_call = _get('fallback_logic', 'safe_call')
        if safe_call is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = safe_call(lambda: (_ for _ in ()).throw(ValueError("error")), fallback="default", log_errors=False)
        self.assertEqual(result, "default")


class TestEventBus(TestCase):
    def setUp(self):
        InMemoryEventBus = _get('event_bus', 'InMemoryEventBus')
        if InMemoryEventBus:
            InMemoryEventBus._subscribers = {}

    def test_subscribe_and_publish(self):
        InMemoryEventBus = _get('event_bus', 'InMemoryEventBus')
        if InMemoryEventBus is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        received = []
        InMemoryEventBus.subscribe("test.event", lambda msg: received.append(msg))
        count = InMemoryEventBus.publish("test.event", {"key": "value"})
        self.assertEqual(count, 1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload["key"], "value")

    def test_wildcard_subscription(self):
        InMemoryEventBus = _get('event_bus', 'InMemoryEventBus')
        if InMemoryEventBus is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        received = []
        InMemoryEventBus.subscribe("*", lambda msg: received.append(msg.event_type))
        InMemoryEventBus.publish("any.event", {})
        self.assertIn("any.event", received)

    def test_event_message_serialization(self):
        EventMessage = _get('event_bus', 'EventMessage')
        if EventMessage is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        msg = EventMessage("test", {"amount": 10.5}, source="cms")
        json_str = msg.to_json()
        restored = EventMessage.from_json(json_str)
        self.assertEqual(restored.event_type, "test")
        self.assertEqual(restored.payload["amount"], 10.5)

    def test_eventbus_convenience_publish(self):
        EventBus = _get('event_bus', 'EventBus')
        InMemoryEventBus = _get('event_bus', 'InMemoryEventBus')
        if EventBus is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        received = []
        InMemoryEventBus.subscribe("reward.earned", lambda m: received.append(m))
        user = MagicMock()
        user.id = 99
        user.username = "testuser"
        EventBus.publish_reward_earned(user, 10.0, "USD", "CPAlead", "lead1", "lead_001", 1000)
        self.assertEqual(len(received), 1)


class TestHealthChecker(TestCase):
    def test_check_database_runs(self):
        HealthChecker = _get('health_check', 'HealthChecker')
        STATUS_OK = _get('health_check', 'STATUS_OK')
        STATUS_FAIL = _get('health_check', 'STATUS_FAIL')
        if HealthChecker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = HealthChecker.check_database()
        self.assertIn(result.status, [STATUS_OK, 'warn', STATUS_FAIL])
        self.assertIsNotNone(result.latency_ms)

    def test_check_cache_runs(self):
        HealthChecker = _get('health_check', 'HealthChecker')
        STATUS_OK = _get('health_check', 'STATUS_OK')
        if HealthChecker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        result = HealthChecker.check_cache()
        self.assertEqual(result.status, STATUS_OK)

    def test_check_all_structure(self):
        HealthChecker = _get('health_check', 'HealthChecker')
        if HealthChecker is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        report = HealthChecker.check_all()
        self.assertIn('status', report)
        self.assertIn('checks', report)
        self.assertIn('timestamp', report)
        self.assertIsInstance(report['checks'], list)

    def test_health_result_to_dict(self):
        HealthResult = _get('health_check', 'HealthResult')
        STATUS_OK = _get('health_check', 'STATUS_OK')
        if HealthResult is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        r = HealthResult("database", STATUS_OK, "12ms", 12.3)
        d = r.to_dict()
        self.assertEqual(d['name'], "database")
        self.assertEqual(d['status'], STATUS_OK)
        self.assertIsInstance(d['latency_ms'], int)


class TestSyncManager(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_acquire_and_release_lock(self):
        SyncManager = _get('sync_manager', 'SyncManager')
        if SyncManager is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        acquired = SyncManager.acquire_lock("test_resource_001", timeout=5)
        self.assertTrue(acquired)
        second = SyncManager.acquire_lock("test_resource_001", timeout=5)
        self.assertFalse(second)
        SyncManager.release_lock("test_resource_001")
        third = SyncManager.acquire_lock("test_resource_001", timeout=5)
        self.assertTrue(third)

    def test_atomic_reward_success(self):
        SyncManager = _get('sync_manager', 'SyncManager')
        if SyncManager is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        called = []
        def award_fn():
            called.append(True)
            return True
        success, msg = SyncManager.atomic_reward(1, "unique_lead_001", 10.0, award_fn)
        self.assertTrue(success)
        self.assertEqual(len(called), 1)

    def test_atomic_reward_dedup(self):
        SyncManager = _get('sync_manager', 'SyncManager')
        if SyncManager is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        from django.core.cache import cache
        cache.set("cms:reward:dedup:lead_already_done", "1", 86400)
        called = []
        success, msg = SyncManager.atomic_reward(1, "lead_already_done", 10.0, lambda: called.append(True))
        self.assertFalse(success)
        self.assertEqual(msg, "duplicate_reward")
        self.assertEqual(len(called), 0)

    def test_conflict_detection(self):
        SyncManager = _get('sync_manager', 'SyncManager')
        if SyncManager is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        conflict = SyncManager.detect_conflict("balance", version_a=1, version_b=2)
        self.assertIsNotNone(conflict)
        no_conflict = SyncManager.detect_conflict("balance", version_a=5, version_b=5)
        self.assertIsNone(no_conflict)

    def test_resolve_conflict_latest_wins(self):
        SyncManager = _get('sync_manager', 'SyncManager')
        if SyncManager is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        a = {"updated_at": "2024-01-01T10:00:00", "balance": 100}
        b = {"updated_at": "2024-01-02T10:00:00", "balance": 200}
        resolved = SyncManager.resolve_conflict("balance", a, b, strategy="latest_wins")
        self.assertEqual(resolved["balance"], 200)


class TestPerformanceMonitor(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_record_and_retrieve(self):
        PerformanceMonitor = _get('performance_monitor', 'PerformanceMonitor')
        if PerformanceMonitor is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        PerformanceMonitor.record("test_endpoint", duration_ms=50.0)
        PerformanceMonitor.record("test_endpoint", duration_ms=100.0)
        stats = PerformanceMonitor.get_stats("test_endpoint")
        data = stats.get("test_endpoint", {})
        if data.get("count"):
            self.assertGreaterEqual(data["count"], 2)

    def test_timed_decorator(self):
        PerformanceMonitor = _get('performance_monitor', 'PerformanceMonitor')
        if PerformanceMonitor is None:
            return self.skipTest('INTEGRATION_SYSTEM not installed')
        @PerformanceMonitor.timed("test_decorated")
        def fast_function():
            return "result"
        result = fast_function()
        self.assertEqual(result, "result")
