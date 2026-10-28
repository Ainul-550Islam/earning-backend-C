from django.test import TestCase
# api/referral/tests/test_logic_advanced.py
# Advanced logic tests for world-class features
# Run: python manage.py test api.referral.tests.test_logic_advanced
# ============================================================

from decimal import Decimal
from django.test import SimpleTestCase


class TestChoices(SimpleTestCase):

    def test_all_commission_statuses_defined(self):
        from api.referral.choices import CommissionStatus
        self.assertIn('pending',    CommissionStatus.values)
        self.assertIn('held',       CommissionStatus.values)
        self.assertIn('released',   CommissionStatus.values)
        self.assertIn('clawed_back',CommissionStatus.values)

    def test_all_social_platforms_defined(self):
        from api.referral.choices import SocialPlatform
        expected = ['whatsapp', 'telegram', 'facebook', 'twitter', 'qr_code']
        for p in expected:
            self.assertIn(p, SocialPlatform.values, f'{p} missing from SocialPlatform')

    def test_tier_levels_ordered(self):
        from api.referral.choices import TierLevel
        self.assertIn('bronze',   TierLevel.values)
        self.assertIn('gold',     TierLevel.values)
        self.assertIn('platinum', TierLevel.values)


class TestExceptions(SimpleTestCase):

    def test_self_referral_error_is_drf_exception(self):
        from rest_framework.exceptions import APIException
        from api.referral.exceptions import SelfReferralError
        e = SelfReferralError()
        self.assertIsInstance(e, APIException)
        self.assertEqual(e.status_code, 400)

    def test_fraud_detected_returns_403(self):
        from api.referral.exceptions import FraudDetectedError
        e = FraudDetectedError()
        self.assertEqual(e.status_code, 403)

    def test_rate_limit_returns_429(self):
        from api.referral.exceptions import ReferralRateLimitError
        e = ReferralRateLimitError()
        self.assertEqual(e.status_code, 429)

    def test_program_inactive_returns_503(self):
        from api.referral.exceptions import ReferralProgramInactiveError
        e = ReferralProgramInactiveError()
        self.assertEqual(e.status_code, 503)


class TestValidators(SimpleTestCase):

    def test_valid_referral_code(self):
        from api.referral.validator import validate_referral_code
        code = validate_referral_code('EARN1234')
        self.assertEqual(code, 'EARN1234')

    def test_code_too_short(self):
        from api.referral.validator import validate_referral_code
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_referral_code('AB')

    def test_code_with_special_chars_rejected(self):
        from api.referral.validator import validate_referral_code
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_referral_code('EARN@#$%')

    def test_valid_commission_amount(self):
        from api.referral.validator import validate_commission_amount
        amount = validate_commission_amount('10.50')
        self.assertEqual(amount, Decimal('10.50'))

    def test_negative_amount_rejected(self):
        from api.referral.validator import validate_commission_amount
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_commission_amount('-5')

    def test_valid_commission_rate(self):
        from api.referral.validator import validate_commission_rate
        rate = validate_commission_rate(10)
        self.assertEqual(rate, Decimal('10'))

    def test_rate_over_100_rejected(self):
        from api.referral.validator import validate_commission_rate
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_commission_rate(101)

    def test_level_validation(self):
        from api.referral.validator import validate_referral_level
        for level in [1, 2, 3]:
            self.assertEqual(validate_referral_level(level), level)

    def test_invalid_level_rejected(self):
        from api.referral.validator import validate_referral_level
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_referral_level(4)

    def test_fraud_score_0_100(self):
        from api.referral.validator import validate_fraud_score
        self.assertEqual(validate_fraud_score(0), 0)
        self.assertEqual(validate_fraud_score(100), 100)

    def test_fraud_score_out_of_range(self):
        from api.referral.validator import validate_fraud_score
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_fraud_score(101)


class TestPagination(SimpleTestCase):

    def test_referral_pagination_defaults(self):
        from api.referral.pagination import ReferralPagination
        p = ReferralPagination()
        self.assertEqual(p.page_size, 20)
        self.assertEqual(p.max_page_size, 100)

    def test_leaderboard_pagination_fixed_size(self):
        from api.referral.pagination import LeaderboardPagination
        p = LeaderboardPagination()
        self.assertEqual(p.page_size, 50)
        self.assertEqual(p.max_page_size, 50)

    def test_cursor_pagination_ordering(self):
        from api.referral.pagination import CursorReferralPagination
        p = CursorReferralPagination()
        self.assertEqual(p.ordering, '-created_at')

    def test_admin_pagination_large(self):
        from api.referral.pagination import AdminReferralPagination
        p = AdminReferralPagination()
        self.assertEqual(p.page_size, 100)
        self.assertEqual(p.max_page_size, 1000)


class TestThrottling(SimpleTestCase):

    def test_all_throttle_classes_defined(self):
        from api.referral.throttling import (
            ReferralUserThrottle, ReferralSignupThrottle,
            ReferralInviteThrottle, ReferralAnonThrottle,
            ReferralRedirectThrottle, AdminReferralThrottle,
            FraudCheckThrottle, WebhookThrottle,
        )
        throttles = [
            ReferralUserThrottle, ReferralSignupThrottle,
            ReferralInviteThrottle, ReferralAnonThrottle,
        ]
        for t in throttles:
            self.assertIsNotNone(t.scope)


class TestEndpointReference(SimpleTestCase):

    def test_endpoint_table_not_empty(self):
        from api.referral.endpoint import ENDPOINTS, get_endpoint_docs
        self.assertGreater(len(ENDPOINTS), 30)
        docs = get_endpoint_docs()
        self.assertGreater(len(docs), 30)
        for entry in docs:
            self.assertIn('method', entry)
            self.assertIn('path', entry)
            self.assertIn('description', entry)

    def test_health_endpoint_in_table(self):
        from api.referral.endpoint import ENDPOINTS
        paths = [k for k in ENDPOINTS.keys()]
        health_paths = [p for p in paths if 'health' in p.lower()]
        self.assertGreater(len(health_paths), 0)


class TestAbstracts(SimpleTestCase):

    def test_timestamped_model_is_abstract(self):
        from api.referral.abstracts import TimeStampedModel
        self.assertTrue(TimeStampedModel._meta.abstract)

    def test_tenant_scoped_is_abstract(self):
        from api.referral.abstracts import TenantScopedModel
        self.assertTrue(TenantScopedModel._meta.abstract)

    def test_status_model_is_abstract(self):
        from api.referral.abstracts import StatusModel
        self.assertTrue(StatusModel._meta.abstract)

    def test_date_range_model_properties(self):
        from api.referral.abstracts import DateRangeModel
        from django.utils import timezone
        from datetime import timedelta

        # Create minimal concrete class for testing
        class TestDateRange(DateRangeModel):
            class Meta(DateRangeModel.Meta):
                app_label = 'referral'

        obj = TestDateRange.__new__(TestDateRange)
        now = timezone.now()
        obj.start_date = now - timedelta(hours=1)
        obj.end_date   = now + timedelta(hours=1)
        self.assertTrue(obj.is_currently_active)
        self.assertFalse(obj.has_ended)
        self.assertTrue(obj.has_started)


class TestHooks(SimpleTestCase):

    def test_register_and_fire(self):
        from api.referral.hooks import ReferralHooks

        received = []

        def handler(**kwargs):
            received.append(kwargs)

        ReferralHooks.register('test_event_xyz', handler)
        ReferralHooks.fire('test_event_xyz', foo='bar')
        ReferralHooks.unregister('test_event_xyz', handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['foo'], 'bar')

    def test_unregister_stops_firing(self):
        from api.referral.hooks import ReferralHooks

        count = [0]

        def handler(**kwargs):
            count[0] += 1

        ReferralHooks.register('test_unsub_xyz', handler)
        ReferralHooks.fire('test_unsub_xyz')
        ReferralHooks.unregister('test_unsub_xyz', handler)
        ReferralHooks.fire('test_unsub_xyz')

        self.assertEqual(count[0], 1)


class TestPlugins(SimpleTestCase):

    def test_plugin_registration(self):
        from api.referral.plugins import PluginRegistry, ReferralPlugin

        class TestPlugin(ReferralPlugin):
            name = 'test_plugin_xyz'

        PluginRegistry.register(TestPlugin())
        plugins = PluginRegistry.list_plugins()
        names = [p['name'] for p in plugins]
        self.assertIn('test_plugin_xyz', names)
        PluginRegistry.unregister('test_plugin_xyz')

    def test_fire_plugin_event(self):
        from api.referral.plugins import PluginRegistry, ReferralPlugin

        fired = []

        class FirePlugin(ReferralPlugin):
            name = 'fire_plugin_xyz'
            def on_referral_created(self, **kwargs):
                fired.append(True)

        PluginRegistry.register(FirePlugin())
        PluginRegistry.fire('on_referral_created', referrer=None, referred_user=None, referral=None)
        PluginRegistry.unregister('fire_plugin_xyz')

        self.assertEqual(len(fired), 1)


class TestRegistry(TestCase):

    def test_get_model_by_name(self):
        from api.referral.registry import registry
        model = registry.get_model('Referral')
        self.assertIsNotNone(model)

    def test_get_nonexistent_model(self):
        from api.referral.registry import registry
        model = registry.get_model('NonExistentModel999')
        self.assertIsNone(model)

    def test_registry_status(self):
        from api.referral.registry import registry, _populate_registry
        _populate_registry(registry)
        status = registry.get_status()
        self.assertGreater(status['total_models'], 0)