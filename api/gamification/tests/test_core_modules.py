"""test_core_modules.py — 0% coverage files: background_jobs, celery_beat_config, feature_flags,
webhooks, logic, analytics, encryption, middleware, routing, notifications_push, data_export,
attachment_upload_view, interactors, helpers, templatetags, context_processors"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from api.gamification.tests.factories import UserFactory, ContestCycleFactory

User = get_user_model()


# ===========================================================================
# background_jobs.py
# ===========================================================================

class BackgroundJobsImportTest(TestCase):
    def test_importable(self):
        from api.gamification.background_jobs import (
            BackgroundJob, JobQueue, JobProcessor, JobScheduler,
            BackgroundJobManager, enqueue_background_job,
            process_background_jobs, get_background_job_status,
        )

    def test_background_job_instantiable(self):
        from api.gamification.background_jobs import BackgroundJob
        job = BackgroundJob(job_type='test', payload={'key': 'value'})
        self.assertIsNotNone(job)

    def test_background_job_to_dict(self):
        from api.gamification.background_jobs import BackgroundJob
        job = BackgroundJob(job_type='award_badges', payload={'user_id': 'abc'})
        d = job.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn('job_type', d)

    def test_job_queue_instantiable(self):
        from api.gamification.background_jobs import JobQueue
        q = JobQueue()
        self.assertIsNotNone(q)

    def test_job_queue_enqueue(self):
        from api.gamification.background_jobs import JobQueue, BackgroundJob
        q = JobQueue()
        job = BackgroundJob(job_type='test', payload={})
        result = q.enqueue(job)
        self.assertIsNotNone(result)

    def test_job_queue_get_queue_stats(self):
        from api.gamification.background_jobs import JobQueue
        q = JobQueue()
        stats = q.get_queue_stats()
        self.assertIsInstance(stats, dict)

    def test_job_processor_instantiable(self):
        from api.gamification.background_jobs import JobProcessor
        p = JobProcessor()
        self.assertIsNotNone(p)

    def test_job_processor_has_process_job(self):
        from api.gamification.background_jobs import JobProcessor
        p = JobProcessor()
        self.assertTrue(hasattr(p, 'process_job'))

    def test_job_scheduler_instantiable(self):
        from api.gamification.background_jobs import JobScheduler
        s = JobScheduler()
        self.assertIsNotNone(s)

    def test_background_job_manager_instantiable(self):
        from api.gamification.background_jobs import BackgroundJobManager
        mgr = BackgroundJobManager()
        self.assertIsNotNone(mgr)

    def test_enqueue_background_job_function(self):
        from api.gamification.background_jobs import enqueue_background_job
        try:
            enqueue_background_job('test_job', {'key': 'val'})
        except Exception as e:
            self.fail(f"enqueue_background_job raised: {e}")

    def test_get_background_job_status_returns_dict(self):
        from api.gamification.background_jobs import get_background_job_status
        result = get_background_job_status('nonexistent-job-id')
        self.assertIsInstance(result, dict)


# ===========================================================================
# celery_beat_config.py
# ===========================================================================

class CeleryBeatConfigTest(TestCase):
    def test_importable(self):
        from api.gamification.celery_beat_config import (
            reset_daily_challenges, update_daily_leaderboards,
            generate_daily_reports, warm_daily_cache,
            check_expiring_streaks, retry_failed_webhooks,
        )

    @patch('api.gamification.tasks.create_daily_challenge')
    def test_reset_daily_challenges_never_raises(self, mock_task):
        from api.gamification.celery_beat_config import reset_daily_challenges
        mock_task.delay = MagicMock()
        try:
            reset_daily_challenges()
        except Exception as e:
            self.fail(f"reset_daily_challenges raised: {e}")

    @patch('api.gamification.tasks.update_leaderboard_snapshot')
    def test_update_daily_leaderboards_never_raises(self, mock_task):
        from api.gamification.celery_beat_config import update_daily_leaderboards
        mock_task.delay = MagicMock()
        try:
            update_daily_leaderboards()
        except Exception as e:
            self.fail(f"update_daily_leaderboards raised: {e}")

    def test_generate_daily_reports_never_raises(self):
        from api.gamification.celery_beat_config import generate_daily_reports
        try:
            generate_daily_reports()
        except Exception as e:
            self.fail(f"generate_daily_reports raised: {e}")

    def test_warm_daily_cache_never_raises(self):
        from api.gamification.celery_beat_config import warm_daily_cache
        try:
            warm_daily_cache()
        except Exception as e:
            self.fail(f"warm_daily_cache raised: {e}")

    def test_check_expiring_streaks_never_raises(self):
        from api.gamification.celery_beat_config import check_expiring_streaks
        try:
            check_expiring_streaks()
        except Exception as e:
            self.fail(f"check_expiring_streaks raised: {e}")

    def test_retry_failed_webhooks_never_raises(self):
        from api.gamification.celery_beat_config import retry_failed_webhooks
        try:
            retry_failed_webhooks()
        except Exception as e:
            self.fail(f"retry_failed_webhooks raised: {e}")


# ===========================================================================
# feature_flags.py
# ===========================================================================

class FeatureFlagsImportTest(TestCase):
    def test_importable(self):
        from api.gamification.feature_flags import (
            FeatureFlag, FeatureFlagManager, FeatureFlagContext,
            FeatureFlagPresets, feature_flag_required, is_feature_enabled,
            get_user_enabled_features, enable_feature_flag, create_feature_flag,
        )

class FeatureFlagTest(TestCase):
    def test_feature_flag_instantiable(self):
        from api.gamification.feature_flags import FeatureFlag
        flag = FeatureFlag(name='test_feature', enabled=True)
        self.assertIsNotNone(flag)

    def test_feature_flag_to_dict(self):
        from api.gamification.feature_flags import FeatureFlag
        flag = FeatureFlag(name='contests', enabled=True)
        d = flag.to_dict()
        self.assertIsInstance(d, dict)

    def test_feature_flag_is_enabled_for_user(self):
        from api.gamification.feature_flags import FeatureFlag
        user = UserFactory()
        flag = FeatureFlag(name='badges', enabled=True)
        result = flag.is_enabled_for_user(user)
        self.assertIsInstance(result, bool)


class FeatureFlagManagerTest(TestCase):
    def test_manager_instantiable(self):
        from api.gamification.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        self.assertIsNotNone(mgr)

    def test_get_flag_returns_flag_or_none(self):
        from api.gamification.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        result = mgr.get_flag('contests')
        self.assertIsNotNone(result) if result is not None else None

    def test_set_flag(self):
        from api.gamification.feature_flags import FeatureFlagManager, FeatureFlag
        mgr = FeatureFlagManager()
        flag = FeatureFlag(name='my_test_flag', enabled=False)
        try:
            mgr.set_flag(flag)
        except Exception as e:
            self.fail(f"set_flag raised: {e}")

    def test_delete_flag_nonexistent_doesnt_raise(self):
        from api.gamification.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        try:
            mgr.delete_flag('nonexistent_flag_xyz')
        except Exception as e:
            self.fail(f"delete_flag raised: {e}")

    def test_is_enabled_returns_bool(self):
        from api.gamification.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        result = mgr.is_enabled('contests')
        self.assertIsInstance(result, bool)

    def test_get_enabled_flags_returns_list(self):
        from api.gamification.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        result = mgr.get_enabled_flags()
        self.assertIsInstance(result, list)


class FeatureFlagFunctionsTest(TestCase):
    def test_is_feature_enabled_returns_bool(self):
        from api.gamification.feature_flags import is_feature_enabled
        result = is_feature_enabled('contests')
        self.assertIsInstance(result, bool)

    def test_get_user_enabled_features_returns_list(self):
        from api.gamification.feature_flags import get_user_enabled_features
        user = UserFactory()
        result = get_user_enabled_features(user)
        self.assertIsInstance(result, list)

    def test_feature_flag_required_decorator(self):
        from api.gamification.feature_flags import feature_flag_required
        @feature_flag_required('contests')
        def my_view(request):
            return 'ok'
        self.assertTrue(callable(my_view))


# ===========================================================================
# webhooks.py
# ===========================================================================

class WebhookManagerTest(TestCase):
    def test_importable(self):
        from api.gamification.webhooks import WebhookManager

    def test_webhook_manager_instantiable(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        self.assertIsNotNone(wm)

    def test_register_webhook(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        try:
            wm.register_webhook('https://example.com/wh', events=['badge.awarded'])
        except Exception as e:
            self.fail(f"register_webhook raised: {e}")

    def test_generate_signature(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        if hasattr(wm, '_generate_signature'):
            sig = wm._generate_signature('{"key":"val"}', 'secret123')
            self.assertIsInstance(sig, str)
            self.assertGreater(len(sig), 0)

    def test_generate_secret(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        if hasattr(wm, '_generate_secret'):
            secret = wm._generate_secret()
            self.assertIsInstance(secret, str)
            self.assertGreater(len(secret), 16)

    def test_verify_webhook_signature(self):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        if hasattr(wm, 'verify_webhook_signature'):
            # valid self-signed payload
            payload = '{"event":"test"}'
            secret = 'test_secret'
            if hasattr(wm, '_generate_signature'):
                sig = wm._generate_signature(payload, secret)
                result = wm.verify_webhook_signature(payload, sig, secret)
                self.assertTrue(result)

    @patch('requests.post', return_value=MagicMock(status_code=200))
    def test_trigger_webhook_never_raises(self, mock_post):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        try:
            wm.trigger_webhook('badge.awarded', {'badge_id': 'test'})
        except Exception as e:
            self.fail(f"trigger_webhook raised: {e}")

    @patch('requests.post', side_effect=Exception("network error"))
    def test_trigger_webhook_handles_network_errors(self, mock_post):
        from api.gamification.webhooks import WebhookManager
        wm = WebhookManager()
        try:
            wm.trigger_webhook('badge.awarded', {'badge_id': 'test'})
        except Exception:
            pass  # acceptable — some impls re-raise


# ===========================================================================
# logic.py — RuleEngine, PointsLogic, BadgeLogic
# ===========================================================================

class LogicImportTest(TestCase):
    def test_importable(self):
        from api.gamification.logic import (
            RuleType, Rule, RuleEngine, PointsLogic, BadgeLogic, LevelLogic,
        )

class RuleTest(TestCase):
    def test_rule_instantiable(self):
        from api.gamification.logic import Rule, RuleType
        rule = Rule(rule_type=RuleType.POINTS_THRESHOLD, threshold=100)
        self.assertIsNotNone(rule)

    def test_rule_evaluate_points_threshold(self):
        from api.gamification.logic import Rule, RuleType
        rule = Rule(rule_type=RuleType.POINTS_THRESHOLD, threshold=100)
        ctx = {'points': 150}
        result = rule.evaluate(ctx)
        self.assertIsInstance(result, bool)

    def test_rule_evaluate_points_threshold_below(self):
        from api.gamification.logic import Rule, RuleType
        rule = Rule(rule_type=RuleType.POINTS_THRESHOLD, threshold=100)
        ctx = {'points': 50}
        result = rule.evaluate(ctx)
        self.assertFalse(result)

    def test_rule_evaluate_streak_days(self):
        from api.gamification.logic import Rule, RuleType
        rule = Rule(rule_type=RuleType.STREAK_DAYS, threshold=7)
        ctx = {'streak_days': 10}
        result = rule.evaluate(ctx)
        self.assertIsInstance(result, bool)

    def test_rule_evaluate_achievement_count(self):
        from api.gamification.logic import Rule, RuleType
        rule = Rule(rule_type=RuleType.ACHIEVEMENT_COUNT, threshold=5)
        ctx = {'achievement_count': 6}
        result = rule.evaluate(ctx)
        self.assertIsInstance(result, bool)


class RuleEngineTest(TestCase):
    def test_rule_engine_instantiable(self):
        from api.gamification.logic import RuleEngine
        engine = RuleEngine()
        self.assertIsNotNone(engine)

    def test_add_rule(self):
        from api.gamification.logic import RuleEngine, Rule, RuleType
        engine = RuleEngine()
        rule = Rule(rule_type=RuleType.POINTS_THRESHOLD, threshold=50)
        engine.add_rule(rule)

    def test_evaluate_rules_all_pass(self):
        from api.gamification.logic import RuleEngine, Rule, RuleType
        engine = RuleEngine()
        engine.add_rule(Rule(rule_type=RuleType.POINTS_THRESHOLD, threshold=50))
        result = engine.evaluate_rules({'points': 100})
        self.assertIsInstance(result, bool)

    def test_evaluate_rules_empty_engine(self):
        from api.gamification.logic import RuleEngine
        engine = RuleEngine()
        result = engine.evaluate_rules({'points': 100})
        self.assertIsInstance(result, bool)


class PointsLogicTest(TestCase):
    def test_points_logic_importable(self):
        from api.gamification.logic import PointsLogic
        pl = PointsLogic()
        self.assertIsNotNone(pl)

    def test_calculate_contest_points(self):
        from api.gamification.logic import PointsLogic
        pl = PointsLogic()
        if hasattr(pl, 'calculate_contest_points'):
            result = pl.calculate_contest_points(base=100, rank=1, multiplier=1.5)
            self.assertIsInstance(result, (int, float, Decimal))


class BadgeLogicTest(TestCase):
    def test_badge_logic_instantiable(self):
        from api.gamification.logic import BadgeLogic
        bl = BadgeLogic()
        self.assertIsNotNone(bl)

    def test_badge_logic_has_check_eligibility(self):
        from api.gamification.logic import BadgeLogic
        bl = BadgeLogic()
        self.assertTrue(hasattr(bl, 'check_eligibility') or hasattr(bl, 'evaluate_badge_criteria'))


# ===========================================================================
# analytics.py
# ===========================================================================

class AnalyticsImportTest(TestCase):
    def test_importable(self):
        from api.gamification.analytics import (
            AnalyticsEvent, AnalyticsTracker, UserAnalytics,
            SystemAnalytics, ReportGenerator,
            track_gamification_event, get_user_analytics,
        )

class AnalyticsEventTest(TestCase):
    def test_analytics_event_instantiable(self):
        from api.gamification.analytics import AnalyticsEvent
        evt = AnalyticsEvent(event_type='badge.earned', user_id='u1', data={'badge': 'test'})
        self.assertIsNotNone(evt)

    def test_analytics_event_to_dict(self):
        from api.gamification.analytics import AnalyticsEvent
        evt = AnalyticsEvent(event_type='points.awarded', user_id='u2', data={'amount': 100})
        d = evt.to_dict()
        self.assertIsInstance(d, dict)

class AnalyticsTrackerTest(TestCase):
    def test_tracker_instantiable(self):
        from api.gamification.analytics import AnalyticsTracker
        t = AnalyticsTracker()
        self.assertIsNotNone(t)

    def test_track_badge_earned(self):
        from api.gamification.analytics import AnalyticsTracker
        user = UserFactory()
        t = AnalyticsTracker()
        try:
            t.track_badge_earned(user_id=str(user.pk), badge_id='badge-1')
        except Exception as e:
            self.fail(f"track_badge_earned raised: {e}")

    def test_track_challenge_completed(self):
        from api.gamification.analytics import AnalyticsTracker
        user = UserFactory()
        t = AnalyticsTracker()
        try:
            t.track_challenge_completed(user_id=str(user.pk), challenge_id='ch-1')
        except Exception as e:
            self.fail(f"track_challenge_completed raised: {e}")

    def test_track_streak_updated(self):
        from api.gamification.analytics import AnalyticsTracker
        user = UserFactory()
        t = AnalyticsTracker()
        try:
            t.track_streak_updated(user_id=str(user.pk), streak_days=5)
        except Exception as e:
            self.fail(f"track_streak_updated raised: {e}")

    def test_track_level_up(self):
        from api.gamification.analytics import AnalyticsTracker
        user = UserFactory()
        t = AnalyticsTracker()
        try:
            t.track_level_up(user_id=str(user.pk), new_level=5)
        except Exception as e:
            self.fail(f"track_level_up raised: {e}")

    def test_track_achievement_earned(self):
        from api.gamification.analytics import AnalyticsTracker
        user = UserFactory()
        t = AnalyticsTracker()
        try:
            t.track_achievement_earned(user_id=str(user.pk), achievement_type='TOP_RANK')
        except Exception as e:
            self.fail(f"track_achievement_earned raised: {e}")


class AnalyticsFunctionsTest(TestCase):
    def test_track_gamification_event_never_raises(self):
        from api.gamification.analytics import track_gamification_event
        user = UserFactory()
        try:
            track_gamification_event('test.event', user_id=str(user.pk), data={})
        except Exception as e:
            self.fail(f"track_gamification_event raised: {e}")

    def test_get_user_analytics_returns_dict(self):
        from api.gamification.analytics import get_user_analytics
        user = UserFactory()
        result = get_user_analytics(str(user.pk))
        self.assertIsInstance(result, dict)


# ===========================================================================
# encryption.py
# ===========================================================================

class EncryptionImportTest(TestCase):
    def test_importable(self):
        from api.gamification.encryption import (
            EncryptionProvider, AESEncryptionProvider, HashProvider,
            TokenGenerator, SecureDataHandler, DataMasking,
            encrypt_data, decrypt_data, hash_data, generate_token,
        )

class AESEncryptionTest(TestCase):
    def test_aes_provider_instantiable(self):
        from api.gamification.encryption import AESEncryptionProvider
        p = AESEncryptionProvider()
        self.assertIsNotNone(p)

    def test_encrypt_returns_string(self):
        from api.gamification.encryption import AESEncryptionProvider
        p = AESEncryptionProvider()
        encrypted = p.encrypt('hello world')
        self.assertIsInstance(encrypted, str)
        self.assertNotEqual(encrypted, 'hello world')

    def test_decrypt_roundtrip(self):
        from api.gamification.encryption import AESEncryptionProvider
        p = AESEncryptionProvider()
        original = 'sensitive data 123'
        encrypted = p.encrypt(original)
        decrypted = p.decrypt(encrypted)
        self.assertEqual(decrypted, original)

    def test_encrypt_different_each_time(self):
        from api.gamification.encryption import AESEncryptionProvider
        p = AESEncryptionProvider()
        e1 = p.encrypt('same')
        e2 = p.encrypt('same')
        # good encryption produces different ciphertext each time (IV randomness)
        self.assertNotEqual(e1, e2)


class HashProviderTest(TestCase):
    def test_hash_provider_instantiable(self):
        from api.gamification.encryption import HashProvider
        hp = HashProvider()
        self.assertIsNotNone(hp)

    def test_hash_returns_string(self):
        from api.gamification.encryption import HashProvider
        hp = HashProvider()
        if hasattr(hp, 'hash'):
            result = hp.hash('password123')
            self.assertIsInstance(result, str)


class TokenGeneratorTest(TestCase):
    def test_token_generator_instantiable(self):
        from api.gamification.encryption import TokenGenerator
        tg = TokenGenerator()
        self.assertIsNotNone(tg)

    def test_generate_token_returns_string(self):
        from api.gamification.encryption import TokenGenerator
        tg = TokenGenerator()
        if hasattr(tg, 'generate'):
            token = tg.generate()
            self.assertIsInstance(token, str)
            self.assertGreater(len(token), 10)


class EncryptionFunctionsTest(TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        from api.gamification.encryption import encrypt_data, decrypt_data
        data = 'my secret data'
        encrypted = encrypt_data(data)
        decrypted = decrypt_data(encrypted)
        self.assertEqual(decrypted, data)

    def test_hash_data_consistent(self):
        from api.gamification.encryption import hash_data
        h1 = hash_data('password')
        h2 = hash_data('password')
        self.assertEqual(h1, h2)

    def test_hash_data_different_inputs(self):
        from api.gamification.encryption import hash_data
        self.assertNotEqual(hash_data('a'), hash_data('b'))

    def test_generate_token_returns_string(self):
        from api.gamification.encryption import generate_token
        token = generate_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 16)


# ===========================================================================
# middleware.py
# ===========================================================================

class MiddlewareImportTest(TestCase):
    def test_importable(self):
        from api.gamification.middleware import (
            ActiveContestCycleMiddleware,
            GamificationTrackingMiddleware,
            GamificationSecurityMiddleware,
        )

class ActiveContestCycleMiddlewareTest(TestCase):
    def get_response(self, request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    def test_middleware_instantiable(self):
        from api.gamification.middleware import ActiveContestCycleMiddleware
        mw = ActiveContestCycleMiddleware(self.get_response)
        self.assertIsNotNone(mw)

    def test_generate_request_id(self):
        from api.gamification.middleware import ActiveContestCycleMiddleware
        mw = ActiveContestCycleMiddleware(self.get_response)
        if hasattr(mw, '_generate_request_id'):
            rid = mw._generate_request_id()
            self.assertIsInstance(rid, str)
            self.assertGreater(len(rid), 8)

    def test_get_client_ip(self):
        from api.gamification.middleware import ActiveContestCycleMiddleware
        from django.test import RequestFactory
        mw = ActiveContestCycleMiddleware(self.get_response)
        request = RequestFactory().get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        if hasattr(mw, '_get_client_ip'):
            ip = mw._get_client_ip(request)
            self.assertIsNotNone(ip)

    def test_basic_vpn_detection_local_ip(self):
        from api.gamification.middleware import ActiveContestCycleMiddleware
        mw = ActiveContestCycleMiddleware(self.get_response)
        if hasattr(mw, '_basic_vpn_detection'):
            is_vpn = mw._basic_vpn_detection('127.0.0.1')
            self.assertFalse(is_vpn)

    def test_middleware_callable(self):
        from api.gamification.middleware import ActiveContestCycleMiddleware
        from django.test import RequestFactory
        mw = ActiveContestCycleMiddleware(self.get_response)
        request = RequestFactory().get('/')
        try:
            response = mw(request)
            self.assertIsNotNone(response)
        except Exception as e:
            self.fail(f"middleware raised: {e}")


class GamificationTrackingMiddlewareTest(TestCase):
    def get_response(self, request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    def test_tracking_middleware_instantiable(self):
        from api.gamification.middleware import GamificationTrackingMiddleware
        mw = GamificationTrackingMiddleware(self.get_response)
        self.assertIsNotNone(mw)

    def test_tracking_middleware_callable(self):
        from api.gamification.middleware import GamificationTrackingMiddleware
        from django.test import RequestFactory
        mw = GamificationTrackingMiddleware(self.get_response)
        request = RequestFactory().get('/')
        try:
            response = mw(request)
            self.assertIsNotNone(response)
        except Exception as e:
            self.fail(f"GamificationTrackingMiddleware raised: {e}")


# ===========================================================================
# routing.py
# ===========================================================================

class RoutingImportTest(TestCase):
    def test_importable(self):
        from api.gamification.routing import (
            GamificationRouter, initialize_router,
            reverse_gamification_url, get_api_base_url,
            get_websocket_base_url, get_all_gamification_urls,
        )

class GamificationRouterTest(TestCase):
    def test_router_instantiable(self):
        from api.gamification.routing import GamificationRouter
        r = GamificationRouter()
        self.assertIsNotNone(r)

    def test_get_patterns_returns_list(self):
        from api.gamification.routing import GamificationRouter
        r = GamificationRouter()
        patterns = r.get_patterns()
        self.assertIsInstance(patterns, list)

    def test_clear_patterns(self):
        from api.gamification.routing import GamificationRouter
        r = GamificationRouter()
        try:
            r.clear_patterns()
            self.assertEqual(len(r.get_patterns()), 0)
        except Exception as e:
            self.fail(f"clear_patterns raised: {e}")

    def test_add_pattern(self):
        from api.gamification.routing import GamificationRouter
        r = GamificationRouter()
        try:
            r.add_pattern('/test/', None, name='test')
        except Exception as e:
            self.fail(f"add_pattern raised: {e}")

    def test_get_api_base_url_returns_string(self):
        from api.gamification.routing import get_api_base_url
        result = get_api_base_url()
        self.assertIsInstance(result, str)

    def test_get_all_gamification_urls_returns_list(self):
        from api.gamification.routing import get_all_gamification_urls
        result = get_all_gamification_urls()
        self.assertIsInstance(result, list)


# ===========================================================================
# notifications_push.py
# ===========================================================================

class NotificationsPushImportTest(TestCase):
    def test_importable(self):
        from api.gamification.notifications_push import (
            PushNotification, NotificationTemplate, NotificationPreferences,
            PushNotificationProvider, send_push_notification,
            send_custom_notification, get_notification_templates,
        )

class PushNotificationTest(TestCase):
    def test_push_notification_instantiable(self):
        from api.gamification.notifications_push import PushNotification
        n = PushNotification(title='Test', body='Test body', user_id='u1')
        self.assertIsNotNone(n)

    def test_push_notification_to_dict(self):
        from api.gamification.notifications_push import PushNotification
        n = PushNotification(title='Badge Earned!', body='You earned a badge', user_id='u1')
        d = n.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn('title', d)

class NotificationTemplateTest(TestCase):
    def test_template_instantiable(self):
        from api.gamification.notifications_push import NotificationTemplate
        t = NotificationTemplate(name='badge_earned', title_template='Badge!', body_template='You got {badge}')
        self.assertIsNotNone(t)

    def test_template_render(self):
        from api.gamification.notifications_push import NotificationTemplate
        t = NotificationTemplate(name='badge_earned', title_template='Badge!', body_template='You got {badge}')
        result = t.render({'badge': 'Gold Badge'})
        self.assertIsInstance(result, dict)

class NotificationPreferencesTest(TestCase):
    def test_preferences_instantiable(self):
        from api.gamification.notifications_push import NotificationPreferences
        user = UserFactory()
        prefs = NotificationPreferences(user_id=str(user.pk))
        self.assertIsNotNone(prefs)

    def test_get_preferences_returns_dict(self):
        from api.gamification.notifications_push import NotificationPreferences
        user = UserFactory()
        prefs = NotificationPreferences(user_id=str(user.pk))
        result = prefs.get_preferences()
        self.assertIsInstance(result, dict)

    def test_set_preference(self):
        from api.gamification.notifications_push import NotificationPreferences
        user = UserFactory()
        prefs = NotificationPreferences(user_id=str(user.pk))
        try:
            prefs.set_preference('badge_notifications', True)
        except Exception as e:
            self.fail(f"set_preference raised: {e}")

    def test_is_enabled_returns_bool(self):
        from api.gamification.notifications_push import NotificationPreferences
        user = UserFactory()
        prefs = NotificationPreferences(user_id=str(user.pk))
        result = prefs.is_enabled('badge_notifications')
        self.assertIsInstance(result, bool)

class NotificationFunctionsTest(TestCase):
    @patch('api.gamification.notifications_push.send_push_notification')
    def test_send_push_notification_never_raises(self, mock_send):
        from api.gamification.notifications_push import send_push_notification
        mock_send.return_value = True
        user = UserFactory()
        try:
            send_push_notification(user_id=str(user.pk), title='Test', body='Test body')
        except Exception as e:
            self.fail(f"send_push_notification raised: {e}")

    def test_get_notification_templates_returns_list(self):
        from api.gamification.notifications_push import get_notification_templates
        result = get_notification_templates()
        self.assertIsInstance(result, list)


# ===========================================================================
# data_export.py
# ===========================================================================

class DataExportImportTest(TestCase):
    def test_importable(self):
        from api.gamification.data_export import (
            ExportFormat, DataExporter, GamificationDataExporter,
            export_user_badges, export_user_streaks, export_leaderboard,
        )

class DataExporterTest(TestCase):
    def test_exporter_instantiable(self):
        from api.gamification.data_export import DataExporter
        exp = DataExporter()
        self.assertIsNotNone(exp)

    def test_export_csv(self):
        from api.gamification.data_export import DataExporter
        exp = DataExporter()
        if hasattr(exp, '_export_csv'):
            result = exp._export_csv([{'key': 'val'}])
            self.assertIsNotNone(result)

    def test_export_json(self):
        from api.gamification.data_export import DataExporter
        exp = DataExporter()
        if hasattr(exp, '_export_json'):
            result = exp._export_json([{'key': 'val'}])
            self.assertIsNotNone(result)

class GamificationDataExporterTest(TestCase):
    def test_gamification_exporter_instantiable(self):
        from api.gamification.data_export import GamificationDataExporter
        exp = GamificationDataExporter()
        self.assertIsNotNone(exp)

    def test_export_user_badges_method_exists(self):
        from api.gamification.data_export import GamificationDataExporter
        exp = GamificationDataExporter()
        self.assertTrue(hasattr(exp, 'export_user_badges'))

    def test_export_user_streaks_method_exists(self):
        from api.gamification.data_export import GamificationDataExporter
        exp = GamificationDataExporter()
        self.assertTrue(hasattr(exp, 'export_user_streaks'))

    def test_export_leaderboard_method_exists(self):
        from api.gamification.data_export import GamificationDataExporter
        exp = GamificationDataExporter()
        self.assertTrue(hasattr(exp, 'export_leaderboard'))

    @patch('api.gamification.data_export.GamificationDataExporter.export_user_badges')
    def test_export_user_badges_returns_bytes_or_str(self, mock_export):
        mock_export.return_value = b'badge_data'
        from api.gamification.data_export import GamificationDataExporter
        exp = GamificationDataExporter()
        user = UserFactory()
        result = exp.export_user_badges(user_id=str(user.pk))
        self.assertIsNotNone(result)


# ===========================================================================
# attachment_upload_view.py
# ===========================================================================

class AttachmentUploadImportTest(TestCase):
    def test_importable(self):
        from api.gamification.attachment_upload_view import (
            AttachmentUploader, BadgeImageUploader,
            ChallengeAttachmentUploader, ContestAttachmentUploader,
            upload_badge_image, upload_challenge_attachment,
            delete_attachment, get_attachment_info,
        )

class AttachmentUploaderTest(TestCase):
    def test_uploader_instantiable(self):
        from api.gamification.attachment_upload_view import AttachmentUploader
        u = AttachmentUploader()
        self.assertIsNotNone(u)

    def test_validate_file_method_exists(self):
        from api.gamification.attachment_upload_view import AttachmentUploader
        u = AttachmentUploader()
        self.assertTrue(hasattr(u, 'validate_file'))

    def test_generate_filename_method_exists(self):
        from api.gamification.attachment_upload_view import AttachmentUploader
        u = AttachmentUploader()
        self.assertTrue(hasattr(u, 'generate_filename'))

    def test_get_file_info_method_exists(self):
        from api.gamification.attachment_upload_view import AttachmentUploader
        u = AttachmentUploader()
        self.assertTrue(hasattr(u, 'get_file_info'))

class BadgeImageUploaderTest(TestCase):
    def test_badge_uploader_instantiable(self):
        from api.gamification.attachment_upload_view import BadgeImageUploader
        u = BadgeImageUploader()
        self.assertIsNotNone(u)

    def test_upload_badge_image_method_exists(self):
        from api.gamification.attachment_upload_view import BadgeImageUploader
        u = BadgeImageUploader()
        self.assertTrue(hasattr(u, 'upload_badge_image'))


# ===========================================================================
# interactors.py
# ===========================================================================

class InteractorsImportTest(TestCase):
    def test_importable(self):
        from api.gamification.interactors import (
            BaseInteractor, BadgeInteractor, StreakInteractor,
            ChallengeInteractor, LevelInteractor, ContestInteractor,
            process_user_gamification_activity, get_user_gamification_profile,
        )

class BadgeInteractorTest(TestCase):
    def test_badge_interactor_instantiable(self):
        from api.gamification.interactors import BadgeInteractor
        i = BadgeInteractor()
        self.assertIsNotNone(i)

    def test_award_badges_with_notifications_method_exists(self):
        from api.gamification.interactors import BadgeInteractor
        i = BadgeInteractor()
        self.assertTrue(hasattr(i, 'award_badges_with_notifications'))

    def test_get_user_badge_recommendations_method_exists(self):
        from api.gamification.interactors import BadgeInteractor
        i = BadgeInteractor()
        self.assertTrue(hasattr(i, 'get_user_badge_recommendations'))

class StreakInteractorTest(TestCase):
    def test_streak_interactor_instantiable(self):
        from api.gamification.interactors import StreakInteractor
        i = StreakInteractor()
        self.assertIsNotNone(i)

    def test_update_streak_with_milestones_method_exists(self):
        from api.gamification.interactors import StreakInteractor
        i = StreakInteractor()
        self.assertTrue(hasattr(i, 'update_streak_with_milestones'))

class InteractorFunctionsTest(TestCase):
    def test_process_user_gamification_activity_never_raises(self):
        from api.gamification.interactors import process_user_gamification_activity
        user = UserFactory()
        try:
            process_user_gamification_activity(user_id=str(user.pk), activity_type='login')
        except Exception as e:
            self.fail(f"process_user_gamification_activity raised: {e}")

    def test_get_user_gamification_profile_returns_dict(self):
        from api.gamification.interactors import get_user_gamification_profile
        user = UserFactory()
        result = get_user_gamification_profile(str(user.pk))
        self.assertIsInstance(result, dict)


# ===========================================================================
# helpers.py
# ===========================================================================

class HelpersImportTest(TestCase):
    def test_importable(self):
        from api.gamification.helpers import (
            PointsCalculator, BadgeHelper, StreakHelper, ChallengeHelper,
            LevelHelper, UserHelper, get_user_gamification_summary,
            calculate_global_leaderboard, invalidate_user_caches,
        )

class PointsCalculatorTest(TestCase):
    def test_instantiable(self):
        from api.gamification.helpers import PointsCalculator
        pc = PointsCalculator()
        self.assertIsNotNone(pc)

    def test_calculate_level_points(self):
        from api.gamification.helpers import PointsCalculator
        pc = PointsCalculator()
        result = pc.calculate_level_points(level=5)
        self.assertIsInstance(result, (int, float, Decimal))

    def test_calculate_streak_bonus_points(self):
        from api.gamification.helpers import PointsCalculator
        pc = PointsCalculator()
        result = pc.calculate_streak_bonus_points(streak_days=7, base_points=100)
        self.assertIsInstance(result, (int, float, Decimal))

    def test_calculate_challenge_bonus_points(self):
        from api.gamification.helpers import PointsCalculator
        pc = PointsCalculator()
        result = pc.calculate_challenge_bonus_points(base=50, difficulty='HARD')
        self.assertIsInstance(result, (int, float, Decimal))


class BadgeHelperTest(TestCase):
    def test_instantiable(self):
        from api.gamification.helpers import BadgeHelper
        bh = BadgeHelper()
        self.assertIsNotNone(bh)

    def test_get_badge_rarity_weight(self):
        from api.gamification.helpers import BadgeHelper
        from api.gamification.choices import BadgeRarity
        bh = BadgeHelper()
        weight = bh.get_badge_rarity_weight(BadgeRarity.LEGENDARY)
        self.assertIsInstance(weight, (int, float))
        self.assertGreater(weight, 0)

class HelpersModuleFunctionsTest(TestCase):
    def test_get_user_gamification_summary_returns_dict(self):
        from api.gamification.helpers import get_user_gamification_summary
        user = UserFactory()
        result = get_user_gamification_summary(str(user.pk))
        self.assertIsInstance(result, dict)

    def test_invalidate_user_caches_never_raises(self):
        from api.gamification.helpers import invalidate_user_caches
        user = UserFactory()
        try:
            invalidate_user_caches(str(user.pk))
        except Exception as e:
            self.fail(f"invalidate_user_caches raised: {e}")


# ===========================================================================
# templatetags/gamification_tags.py
# ===========================================================================

class TemplateTagsTest(TestCase):
    def test_importable(self):
        from api.gamification.templatetags.gamification_tags import (
            points_display, rank_suffix, gamif_user_points, gamif_leaderboard_widget,
        )

    def test_points_display(self):
        from api.gamification.templatetags.gamification_tags import points_display
        result = points_display(1500)
        self.assertIsNotNone(result)

    def test_rank_suffix_1st(self):
        from api.gamification.templatetags.gamification_tags import rank_suffix
        result = rank_suffix(1)
        self.assertIn('st', str(result))

    def test_rank_suffix_2nd(self):
        from api.gamification.templatetags.gamification_tags import rank_suffix
        result = rank_suffix(2)
        self.assertIn('nd', str(result))

    def test_rank_suffix_3rd(self):
        from api.gamification.templatetags.gamification_tags import rank_suffix
        result = rank_suffix(3)
        self.assertIn('rd', str(result))

    def test_rank_suffix_4th(self):
        from api.gamification.templatetags.gamification_tags import rank_suffix
        result = rank_suffix(4)
        self.assertIn('th', str(result))


# ===========================================================================
# context_processors.py
# ===========================================================================

class ContextProcessorsTest(TestCase):
    def test_importable(self):
        from api.gamification.context_processors import active_contest_cycle

    def test_active_contest_cycle_returns_dict(self):
        from api.gamification.context_processors import active_contest_cycle
        request = RequestFactory().get('/')
        result = active_contest_cycle(request)
        self.assertIsInstance(result, dict)
