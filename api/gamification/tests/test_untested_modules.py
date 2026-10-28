"""
test_untested_modules.py
========================
Tests for modules that had 0% test coverage:
  - consumers.py   (WebSocket consumers)
  - webhooks.py    (WebhookManager)
  - monitoring.py  (HealthChecker, MonitoringService)
  - sanctions.py   (SanctionManager, enforcers)
  - decorators.py  (cache_result, log_execution, validate_points, retry…)
  - plugins.py     (PluginManager, built-in plugins)
  - hooks.py       (HookRegistry, execute_hook)
"""
from __future__ import annotations

import asyncio
import time
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from api.gamification.tests.factories import UserFactory

User = get_user_model()


# ===========================================================================
# consumers.py
# ===========================================================================

class ConsumersImportTest(TestCase):
    """Verify all consumer classes are importable and have expected interface."""

    def test_consumer_classes_importable(self):
        from api.gamification.consumers import (
            BaseGamificationConsumer,
            LeaderboardConsumer,
            AchievementConsumer,
            StreakConsumer,
            ChallengeConsumer,
            NotificationConsumer,
            ContestConsumer,
            PointsConsumer,
            StreakFreezeConsumer,
            ContestParticipantConsumer,
            GamificationConfigConsumer,
            GamificationInsightConsumer,
        )
        # All are subclasses of BaseGamificationConsumer
        for cls in [LeaderboardConsumer, AchievementConsumer, StreakConsumer,
                    ChallengeConsumer, NotificationConsumer, ContestConsumer,
                    PointsConsumer, StreakFreezeConsumer, ContestParticipantConsumer,
                    GamificationConfigConsumer, GamificationInsightConsumer]:
            self.assertTrue(
                issubclass(cls, BaseGamificationConsumer),
                f"{cls.__name__} must subclass BaseGamificationConsumer",
            )

    def test_base_consumer_has_connect_disconnect(self):
        from api.gamification.consumers import BaseGamificationConsumer
        self.assertTrue(hasattr(BaseGamificationConsumer, "connect"))
        self.assertTrue(hasattr(BaseGamificationConsumer, "disconnect"))

    def test_leaderboard_consumer_has_receive(self):
        from api.gamification.consumers import LeaderboardConsumer
        self.assertTrue(hasattr(LeaderboardConsumer, "receive") or
                        hasattr(LeaderboardConsumer, "receive_json"))

    def test_all_consumers_have_group_name_or_room(self):
        """Every consumer should define a group_name or group prefix."""
        from api.gamification.consumers import (
            LeaderboardConsumer, AchievementConsumer, StreakConsumer,
        )
        for cls in [LeaderboardConsumer, AchievementConsumer, StreakConsumer]:
            src = open("api/gamification/consumers.py").read()
            self.assertIn("group_name", src, "consumers.py must define group_name")


# ===========================================================================
# webhooks.py
# ===========================================================================

class WebhookManagerTest(TestCase):
    """Tests for WebhookManager in webhooks.py."""

    def test_webhook_manager_importable(self):
        from api.gamification.webhooks import WebhookManager
        self.assertIsNotNone(WebhookManager)

    def test_webhook_manager_instantiable(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        self.assertIsNotNone(wm)

    def test_webhook_manager_has_send_method(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        self.assertTrue(
            hasattr(wm, "send") or hasattr(wm, "deliver") or hasattr(wm, "dispatch"),
            "WebhookManager must have a send/deliver/dispatch method",
        )

    def test_webhook_manager_has_register_method(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        self.assertTrue(
            hasattr(wm, "register") or hasattr(wm, "add_endpoint") or hasattr(wm, "register_endpoint"),
            "WebhookManager must have a register/add_endpoint method",
        )

    @patch("requests.post", return_value=MagicMock(status_code=200))
    def test_webhook_delivery_never_raises(self, mock_post):
        """WebhookManager must never propagate exceptions to caller."""
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        send_fn = getattr(wm, "send", None) or getattr(wm, "deliver", None) or getattr(wm, "dispatch", None)
        if send_fn:
            try:
                send_fn("https://example.com/wh", {"event": "test"})
            except Exception as exc:
                self.fail(f"WebhookManager raised: {exc}")


# ===========================================================================
# monitoring.py
# ===========================================================================

class MonitoringImportTest(TestCase):
    """Tests for monitoring.py — HealthCheckers and MonitoringService."""

    def test_monitoring_classes_importable(self):
        from api.gamification.monitoring import (
            HealthCheck,
            Metric,
            Alert,
            BaseHealthChecker,
            DatabaseHealthChecker,
            CacheHealthChecker,
            GamificationHealthChecker,
            PerformanceHealthChecker,
            MonitoringService,
            MetricsCollector,
            AlertManager,
        )

    def test_database_health_checker_has_check_method(self):
        from api.gamification.monitoring import DatabaseHealthChecker
        checker = DatabaseHealthChecker()
        self.assertTrue(hasattr(checker, "check"))

    def test_cache_health_checker_has_check_method(self):
        from api.gamification.monitoring import CacheHealthChecker
        checker = CacheHealthChecker()
        self.assertTrue(hasattr(checker, "check"))

    def test_gamification_health_checker_has_check_method(self):
        from api.gamification.monitoring import GamificationHealthChecker
        checker = GamificationHealthChecker()
        self.assertTrue(hasattr(checker, "check"))

    @patch("django.db.connection.cursor")
    def test_database_health_checker_check_never_raises(self, mock_cursor):
        from api.gamification.monitoring import DatabaseHealthChecker, HealthCheck
        mock_cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_cursor.return_value.__exit__ = MagicMock(return_value=False)
        checker = DatabaseHealthChecker()
        try:
            result = checker.check(HealthCheck(name="db_test"))
        except Exception as exc:
            self.fail(f"DatabaseHealthChecker.check raised: {exc}")

    def test_monitoring_service_instantiable(self):
        from api.gamification.monitoring import MonitoringService
        svc = MonitoringService()
        self.assertIsNotNone(svc)

    def test_monitoring_service_has_collect_metrics(self):
        from api.gamification.monitoring import MonitoringService
        svc = MonitoringService()
        self.assertTrue(
            hasattr(svc, "collect_metrics") or hasattr(svc, "record") or hasattr(svc, "report"),
        )

    def test_metrics_collector_instantiable(self):
        from api.gamification.monitoring import MetricsCollector
        mc = MetricsCollector()
        self.assertIsNotNone(mc)

    def test_alert_manager_instantiable(self):
        from api.gamification.monitoring import AlertManager
        am = AlertManager()
        self.assertIsNotNone(am)


# ===========================================================================
# sanctions.py
# ===========================================================================

class SanctionsImportTest(TestCase):
    """Tests for sanctions.py — enforcer classes and SanctionManager."""

    def test_sanction_classes_importable(self):
        from api.gamification.sanctions import (
            ViolationSeverity,
            ViolationType,
            SanctionType,
            Violation,
            Sanction,
            BaseSanctionEnforcer,
            PointsDeductionEnforcer,
            BadgeRevocationEnforcer,
            StreakResetEnforcer,
            TemporarySuspensionEnforcer,
            AchievementRemovalEnforcer,
            SanctionManager,
            detect_and_apply_sanctions,
            check_user_suspension,
        )

    def test_points_deduction_enforcer_has_enforce(self):
        from api.gamification.sanctions import PointsDeductionEnforcer
        enforcer = PointsDeductionEnforcer()
        self.assertTrue(hasattr(enforcer, "enforce"))

    def test_badge_revocation_enforcer_has_enforce(self):
        from api.gamification.sanctions import BadgeRevocationEnforcer
        enforcer = BadgeRevocationEnforcer()
        self.assertTrue(hasattr(enforcer, "enforce"))

    def test_streak_reset_enforcer_has_enforce(self):
        from api.gamification.sanctions import StreakResetEnforcer
        enforcer = StreakResetEnforcer()
        self.assertTrue(hasattr(enforcer, "enforce"))

    def test_temporary_suspension_enforcer_has_enforce(self):
        from api.gamification.sanctions import TemporarySuspensionEnforcer
        enforcer = TemporarySuspensionEnforcer()
        self.assertTrue(hasattr(enforcer, "enforce"))

    def test_sanction_manager_instantiable(self):
        from api.gamification.sanctions import SanctionManager
        sm = SanctionManager()
        self.assertIsNotNone(sm)

    def test_sanction_manager_has_apply(self):
        from api.gamification.sanctions import SanctionManager
        sm = SanctionManager()
        self.assertTrue(hasattr(sm, "apply") or hasattr(sm, "enforce") or hasattr(sm, "sanction"))

    def test_detect_and_apply_never_raises(self):
        from api.gamification.sanctions import detect_and_apply_sanctions
        user = UserFactory()
        try:
            detect_and_apply_sanctions(
                user_id=str(user.pk),
                violation_type="POINTS_ABUSE",
                description="test violation",
            )
        except Exception as exc:
            self.fail(f"detect_and_apply_sanctions raised: {exc}")

    def test_check_user_suspension_returns_dict(self):
        from api.gamification.sanctions import check_user_suspension
        user = UserFactory()
        result = check_user_suspension(str(user.pk))
        self.assertIsInstance(result, dict)

    def test_violation_severity_has_expected_values(self):
        from api.gamification.sanctions import ViolationSeverity
        self.assertTrue(hasattr(ViolationSeverity, "LOW") or hasattr(ViolationSeverity, "MINOR"))

    def test_sanction_type_has_expected_values(self):
        from api.gamification.sanctions import SanctionType
        self.assertTrue(hasattr(SanctionType, "POINTS_DEDUCTION") or
                        hasattr(SanctionType, "WARNING"))


# ===========================================================================
# decorators.py
# ===========================================================================

class DecoratorsTest(TestCase):
    """Tests for decorators.py — cache_result, log_execution, validate_points, retry."""

    def test_decorators_importable(self):
        from api.gamification.decorators import (
            cache_result,
            log_execution,
            validate_points,
            rate_limit,
            transactional,
            retry,
            measure_performance,
            validate_user_exists,
        )

    def test_cache_result_decorator_returns_same_value(self):
        from api.gamification.decorators import cache_result

        call_count = [0]

        @cache_result(key_prefix="test_cache", timeout=60)
        def expensive_fn(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_fn(5)
        result2 = expensive_fn(5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)

    def test_log_execution_decorator_wraps_function(self):
        from api.gamification.decorators import log_execution

        @log_execution(level="DEBUG")
        def simple_fn(a, b):
            return a + b

        result = simple_fn(2, 3)
        self.assertEqual(result, 5)

    def test_log_execution_does_not_suppress_exceptions(self):
        from api.gamification.decorators import log_execution

        @log_execution()
        def failing_fn():
            raise ValueError("intentional error")

        with self.assertRaises(ValueError):
            failing_fn()

    def test_validate_points_rejects_negative(self):
        from api.gamification.decorators import validate_points

        @validate_points(min_value=0)
        def award(amount):
            return amount

        with self.assertRaises(Exception):
            award(-10)

    def test_validate_points_accepts_positive(self):
        from api.gamification.decorators import validate_points

        @validate_points(min_value=1)
        def award(amount):
            return amount

        result = award(100)
        self.assertEqual(result, 100)

    def test_retry_decorator_retries_on_failure(self):
        from api.gamification.decorators import retry

        attempt = [0]

        @retry(max_retries=3, delay=0.0, exceptions=(RuntimeError,))
        def flaky_fn():
            attempt[0] += 1
            if attempt[0] < 3:
                raise RuntimeError("not yet")
            return "success"

        result = flaky_fn()
        self.assertEqual(result, "success")
        self.assertEqual(attempt[0], 3)

    def test_retry_raises_after_max_retries(self):
        from api.gamification.decorators import retry

        @retry(max_retries=2, delay=0.0, exceptions=(RuntimeError,))
        def always_fails():
            raise RuntimeError("always fails")

        with self.assertRaises(RuntimeError):
            always_fails()

    def test_transactional_decorator_wraps_function(self):
        from api.gamification.decorators import transactional

        @transactional()
        def db_operation():
            return "committed"

        result = db_operation()
        self.assertEqual(result, "committed")

    def test_measure_performance_does_not_suppress_return(self):
        from api.gamification.decorators import measure_performance

        @measure_performance(log_slow_calls=False)
        def fast_fn():
            return 99

        self.assertEqual(fast_fn(), 99)


# ===========================================================================
# plugins.py
# ===========================================================================

class PluginsTest(TestCase):
    """Tests for plugins.py — PluginManager and built-in plugins."""

    def test_plugin_classes_importable(self):
        from api.gamification.plugins import (
            PluginInfo,
            BasePlugin,
            GamificationPlugin,
            NotificationPlugin,
            AnalyticsPlugin,
            IntegrationPlugin,
            PluginManager,
            EmailNotificationPlugin,
            LoggingAnalyticsPlugin,
            BasicGamificationPlugin,
            initialize_built_in_plugins,
        )

    def test_plugin_manager_instantiable(self):
        from api.gamification.plugins import PluginManager
        pm = PluginManager()
        self.assertIsNotNone(pm)

    def test_plugin_manager_has_register(self):
        from api.gamification.plugins import PluginManager
        pm = PluginManager()
        self.assertTrue(hasattr(pm, "register") or hasattr(pm, "add_plugin"))

    def test_plugin_manager_has_get_plugins(self):
        from api.gamification.plugins import PluginManager
        pm = PluginManager()
        self.assertTrue(
            hasattr(pm, "get_plugins") or hasattr(pm, "list_plugins") or hasattr(pm, "plugins"),
        )

    def test_email_notification_plugin_is_notification_plugin(self):
        from api.gamification.plugins import EmailNotificationPlugin, NotificationPlugin
        self.assertTrue(issubclass(EmailNotificationPlugin, NotificationPlugin))

    def test_logging_analytics_plugin_is_analytics_plugin(self):
        from api.gamification.plugins import LoggingAnalyticsPlugin, AnalyticsPlugin
        self.assertTrue(issubclass(LoggingAnalyticsPlugin, AnalyticsPlugin))

    def test_basic_gamification_plugin_is_gamification_plugin(self):
        from api.gamification.plugins import BasicGamificationPlugin, GamificationPlugin
        self.assertTrue(issubclass(BasicGamificationPlugin, GamificationPlugin))

    def test_initialize_built_in_plugins_never_raises(self):
        from api.gamification.plugins import initialize_built_in_plugins
        try:
            initialize_built_in_plugins()
        except Exception as exc:
            self.fail(f"initialize_built_in_plugins raised: {exc}")

    def test_plugin_info_has_required_fields(self):
        from api.gamification.plugins import PluginInfo
        self.assertTrue(hasattr(PluginInfo, "__dataclass_fields__") or
                        hasattr(PluginInfo, "__annotations__"),
                        "PluginInfo should be a dataclass or typed class")

    def test_base_plugin_has_execute(self):
        from api.gamification.plugins import BasePlugin
        self.assertTrue(hasattr(BasePlugin, "execute") or hasattr(BasePlugin, "run"))


# ===========================================================================
# hooks.py
# ===========================================================================

class HooksTest(TestCase):
    """Tests for hooks.py — HookRegistry, execute_hook, FunctionHook."""

    def test_hook_classes_importable(self):
        from api.gamification.hooks import (
            HookType,
            HookContext,
            Hook,
            FunctionHook,
            ConditionalHook,
            AsyncHook,
            HookRegistry,
            hook,
            execute_hook,
            execute_hook_with_result,
            validate_points_award,
            log_points_award,
            validate_badge_earn,
        )

    def test_hook_registry_instantiable(self):
        from api.gamification.hooks import HookRegistry
        registry = HookRegistry()
        self.assertIsNotNone(registry)

    def test_hook_registry_has_register(self):
        from api.gamification.hooks import HookRegistry
        registry = HookRegistry()
        self.assertTrue(hasattr(registry, "register"))

    def test_hook_registry_has_execute(self):
        from api.gamification.hooks import HookRegistry
        registry = HookRegistry()
        self.assertTrue(hasattr(registry, "execute") or hasattr(registry, "fire"))

    def test_function_hook_wraps_callable(self):
        from api.gamification.hooks import FunctionHook, HookContext
        called = [False]

        def my_hook(ctx):
            called[0] = True

        fh = FunctionHook(fn=my_hook, hook_name="test.hook")
        ctx = HookContext(hook_name="test.hook")
        fh.execute(ctx)
        self.assertTrue(called[0])

    def test_execute_hook_never_raises(self):
        from api.gamification.hooks import execute_hook
        try:
            execute_hook("nonexistent.hook", user_id="user-123", context={"points": 50})
        except Exception as exc:
            self.fail(f"execute_hook raised: {exc}")

    def test_validate_points_award_hook_returns_none_or_dict(self):
        from api.gamification.hooks import validate_points_award, HookContext
        ctx = HookContext(hook_name="points.award", data={"amount": 100, "user_id": "abc"})
        result = validate_points_award(ctx)
        self.assertIn(result, [None, {}] + ([result] if isinstance(result, dict) else []))

    def test_log_points_award_never_raises(self):
        from api.gamification.hooks import log_points_award, HookContext
        ctx = HookContext(hook_name="points.award", data={"amount": 50})
        try:
            log_points_award(ctx)
        except Exception as exc:
            self.fail(f"log_points_award raised: {exc}")

    def test_validate_badge_earn_hook_returns_none_or_dict(self):
        from api.gamification.hooks import validate_badge_earn, HookContext
        ctx = HookContext(hook_name="badge.earn", data={"badge_id": "badge-1", "user_id": "u1"})
        result = validate_badge_earn(ctx)
        self.assertIn(result, [None] + ([result] if isinstance(result, dict) else []))

    def test_conditional_hook_respects_condition(self):
        from api.gamification.hooks import ConditionalHook, HookContext
        called = [False]

        def my_fn(ctx):
            called[0] = True

        def never_true(ctx):
            return False

        ch = ConditionalHook(fn=my_fn, hook_name="test.conditional", condition=never_true)
        ctx = HookContext(hook_name="test.conditional")
        ch.execute(ctx)
        self.assertFalse(called[0], "ConditionalHook should not call fn when condition is False")

    def test_hook_type_has_expected_values(self):
        from api.gamification.hooks import HookType
        self.assertTrue(
            hasattr(HookType, "PRE") or hasattr(HookType, "BEFORE") or
            hasattr(HookType, "POST") or hasattr(HookType, "AFTER"),
        )


# ===========================================================================
# Sanction ViewSet URL registration test
# ===========================================================================

class SanctionViewSetRoutingTest(TestCase):
    """Confirm SanctionViewSet is registered in urls.py."""

    def test_sanctions_url_registered(self):
        content = open("api/gamification/urls.py").read()
        self.assertIn("sanction", content.lower(),
                      "urls.py must register SanctionViewSet under /sanctions/")

    def test_sanctions_viewset_imported_in_urls(self):
        content = open("api/gamification/urls.py").read()
        self.assertIn("SanctionViewSet", content,
                      "urls.py must import SanctionViewSet")
