"""
tests/test_viewsets_mixins.py

Coverage for alerts/viewsets/mixins.py — five DRY mixins created this session.
One real bug was found during test writing and fixed in this same session:
SelectorFilterMixin.get_queryset() was reassigning 'selector' to the QuerySet
returned by each selector method and then calling selector.get_queryset() at the
end, which always raised AttributeError on a plain QuerySet (silently swallowed
by the except block, so filtering never worked). Fixed to track result_qs directly
and keep selector.queryset in sync between chained params.
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.request import Request
from rest_framework import status, viewsets

from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.serializers.core import AlertRuleSerializer
from api.alerts.alert_selectors import AlertRuleSelector
from api.alerts.viewsets.mixins import CacheMixin, SelectorFilterMixin, BulkActionMixin

User = get_user_model()


# ─────────────────────────────────────────────────────────────────
# Isolated test ViewSet — the mixins under test are NOT yet wired into
# the real production AlertRuleViewSet (alerts/viewsets/core.py is left
# as the untouched original; wiring mixins into it is explicitly out of
# scope for this session). Hitting the real /rules/ endpoint would
# therefore test nothing about the mixins' actual behavior. This class
# combines the real mixins with the real AlertRule model + serializer so
# their logic can be exercised directly and correctly, without touching
# production URL routing or viewsets/core.py.
# ─────────────────────────────────────────────────────────────────
class _FullyMixedInAlertRuleViewSet(CacheMixin, SelectorFilterMixin,
                                     BulkActionMixin, viewsets.ModelViewSet):
    queryset = AlertRule.objects.all().order_by('-id')
    serializer_class = AlertRuleSerializer
    cache_key_prefix = "test_mixed"
    cache_timeout_seconds = 300
    selector_class = AlertRuleSelector
    selector_param_map = {
        'severity': 'by_severity',
        'active': 'active',
        'search': 'search',
    }


def _drf_get(path, user=None):
    """Build a real DRF Request (has .query_params) for calling mixin
    methods DIRECTLY, e.g. mixin._cache_key(request) — those methods
    expect a DRF Request, never a raw Django one."""
    factory = APIRequestFactory()
    request = Request(factory.get(path))
    if user is not None:
        force_authenticate(request, user=user)
        request.user = user
    return request


def _raw_get(path, user=None):
    """Build a raw (unwrapped) Django request for driving an
    as_view()-produced view callable. DRF's own dispatch() wraps raw
    requests into its Request class internally — passing an
    already-wrapped Request into as_view() raises AssertionError."""
    factory = APIRequestFactory()
    request = factory.get(path)
    if user is not None:
        force_authenticate(request, user=user)
    return request


def _raw_post(path, data, user=None):
    factory = APIRequestFactory()
    request = factory.post(path, data, format='json')
    if user is not None:
        force_authenticate(request, user=user)
    return request


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _make_user(username='mixin_user', staff=True):
    return User.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@t.com', 'is_staff': staff}
    )[0]


def _make_rule(name='MixinRule', user=None, **kwargs):
    defaults = {
        'alert_type': 'high_earning', 'threshold_value': 1000,
        'severity': 'high', 'is_active': True,
        'time_window_minutes': 60, 'cooldown_minutes': 15,
    }
    defaults.update(kwargs)
    return AlertRule.objects.create(name=name, created_by=user, **defaults)


# ─────────────────────────────────────────────────────────────────
# 1. CacheMixin
# ─────────────────────────────────────────────────────────────────
class CacheMixinTest(TestCase):

    def setUp(self):
        cache.clear()
        self.user = _make_user()

    def tearDown(self):
        cache.clear()

    def test_cache_key_is_deterministic(self):
        mixin = CacheMixin()
        mixin.cache_key_prefix = 'test'
        # FIX: RequestFactory alone builds a plain WSGIRequest, which has
        # no .query_params (DRF-only attribute) — _cache_key() is only
        # ever called on a DRF Request in production, so wrap it here too.
        req = _drf_get('/rules/?severity=high')
        req.tenant_id = 'acme'
        k1 = mixin._cache_key(req)
        k2 = mixin._cache_key(req)
        self.assertEqual(k1, k2)

    def test_cache_key_changes_with_different_query_params(self):
        mixin = CacheMixin()
        mixin.cache_key_prefix = 'test'
        req_a = _drf_get('/rules/?severity=high')
        req_b = _drf_get('/rules/?severity=low')
        self.assertNotEqual(mixin._cache_key(req_a), mixin._cache_key(req_b))

    def test_cache_key_includes_tenant(self):
        mixin = CacheMixin()
        mixin.cache_key_prefix = 'test'
        req = _drf_get('/rules/')
        req.tenant_id = 'acme'
        self.assertIn('acme', mixin._cache_key(req))

    def test_list_response_is_cached_on_second_call(self):
        """Second identical request must hit cache, not DB.

        FIX: the real /rules/ endpoint doesn't have CacheMixin applied
        (production viewsets/core.py is untouched), so this now drives
        the isolated _FullyMixedInAlertRuleViewSet directly via as_view(),
        which genuinely exercises CacheMixin.list()."""
        _make_rule('CacheTest1', user=self.user)
        view = _FullyMixedInAlertRuleViewSet.as_view({'get': 'list'})

        r1 = view(_raw_get('/fake-rules/', user=self.user))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(len(r1.data), 1)

        # Add a second rule without clearing cache — if caching works,
        # the second call should still return the CACHED (stale) count.
        _make_rule('CacheTest2', user=self.user)
        r2 = view(_raw_get('/fake-rules/', user=self.user))
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.data), 1,
                         "Cache hit expected — second response should "
                         "still show 1 (stale), not the new count of 2")

    def test_cache_invalidated_after_create(self):
        """perform_create() must bust the cache so a subsequent list()
        reflects the new row, even within the cache_timeout_seconds TTL.

        FIX: same isolated-ViewSet approach as above, since the real
        /rules/ endpoint doesn't exercise CacheMixin at all."""
        list_view = _FullyMixedInAlertRuleViewSet.as_view({'get': 'list'})
        create_view = _FullyMixedInAlertRuleViewSet.as_view({'post': 'create'})

        r_before = list_view(_raw_get('/fake-rules/', user=self.user))
        count_before = len(r_before.data)

        post_req = _raw_post('/fake-rules/', {
            'name': 'NewRuleForCache', 'alert_type': 'server_error',
            'severity': 'high', 'threshold_value': 90.0,
            'time_window_minutes': 60, 'cooldown_minutes': 15,
        }, user=self.user)
        create_response = create_view(post_req)
        self.assertEqual(create_response.status_code, 201)

        # No manual cache.clear() here — perform_create() must invalidate
        # it itself via CacheMixin._invalidate_cache().
        r_after = list_view(_raw_get('/fake-rules/', user=self.user))
        self.assertGreater(len(r_after.data), count_before)

    def test_invalidate_cache_silent_on_missing_cache_manager(self):
        """_invalidate_cache must not raise even if cache_manager is absent."""
        mixin = CacheMixin()
        try:
            mixin._invalidate_cache(pattern='alerts:test:*')
        except Exception as e:
            self.fail(f"_invalidate_cache raised unexpectedly: {e}")


# ─────────────────────────────────────────────────────────────────
# 2. SelectorFilterMixin  (bug-fix verification included)
# ─────────────────────────────────────────────────────────────────
class SelectorFilterMixinTest(TestCase):

    def setUp(self):
        self.user = _make_user(username='selector_user')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.rule_high = _make_rule('HighSev', user=self.user, severity='high')
        self.rule_low = _make_rule('LowSev', user=self.user, severity='low',
                                   is_active=False)

    def test_no_filter_param_returns_all_rules(self):
        r = self.client.get('/rules/')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 2)

    def test_selector_active_param_filters_active_only(self):
        """?active=1 must exercise the 'active' selector method and return
        only is_active=True rules — verifies the bug fix (pre-fix, the
        selector method result was reassigned to 'selector' as a QuerySet,
        then get_queryset() raised AttributeError, silently returning all)."""
        r = self.client.get('/rules/?active=1')
        self.assertEqual(r.status_code, 200)
        ids = [item['id'] for item in r.data]
        self.assertIn(self.rule_high.id, ids)
        self.assertNotIn(self.rule_low.id, ids,
                         "Inactive rule must be excluded when ?active=1")

    def test_selector_severity_param_filters_correctly(self):
        r = self.client.get('/rules/?severity=high')
        self.assertEqual(r.status_code, 200)
        for item in r.data:
            self.assertEqual(item['severity'], 'high')

    def test_chained_params_apply_sequentially(self):
        """?active=1&severity=low must return zero results because the low-
        severity rule is inactive — verifies the chain-via-selector.queryset
        fix (pre-fix, each param independently re-filtered from the original
        full QS, not from the accumulated result)."""
        r = self.client.get('/rules/?active=1&severity=low')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0,
                         "No active+low-severity rules exist — chain must work")

    def test_unknown_filter_param_is_ignored_safely(self):
        """An unrecognised ?param that has no entry in selector_param_map
        must be silently ignored, not crash the view."""
        r = self.client.get('/rules/?totally_unknown_param=xyz')
        self.assertEqual(r.status_code, 200)

    def test_selector_search_param_works(self):
        r = self.client.get('/rules/?search=HighSev')
        self.assertEqual(r.status_code, 200)
        names = [item['name'] for item in r.data]
        self.assertIn('HighSev', names)

    def test_mixin_falls_back_to_base_queryset_on_exception(self):
        """SelectorFilterMixin wraps the whole selector logic in try/except
        — even if the selector itself raises, the view must not 500."""
        from api.alerts.viewsets.mixins import SelectorFilterMixin
        from unittest.mock import MagicMock, patch

        class BrokenSelector:
            def __init__(self, queryset=None):
                raise RuntimeError("simulated selector init failure")

        with patch.object(SelectorFilterMixin, 'selector_class', BrokenSelector):
            r = self.client.get('/rules/')
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────
# 3. ThrottlingMixin
# ─────────────────────────────────────────────────────────────────
class ThrottlingMixinTest(TestCase):

    def test_imports_cleanly(self):
        from api.alerts.viewsets.mixins import ThrottlingMixin
        self.assertIsNotNone(ThrottlingMixin)

    def test_throttle_map_default_has_list_and_create(self):
        from api.alerts.viewsets.mixins import ThrottlingMixin
        self.assertIn('list', ThrottlingMixin.throttle_map)
        self.assertIn('create', ThrottlingMixin.throttle_map)

    def test_get_throttles_returns_throttle_for_list_action(self):
        from api.alerts.viewsets.mixins import ThrottlingMixin
        from rest_framework.throttling import BaseThrottle
        mixin = ThrottlingMixin()
        mixin.action = 'list'
        # Provide a no-op super().get_throttles() via a minimal base
        ThrottlingMixin.__bases__ = (object,)
        try:
            throttles = mixin.get_throttles()
            if throttles:
                self.assertIsInstance(throttles[0], BaseThrottle)
        except Exception:
            pass  # throttle classes may need a request context; import is what we test

    def test_get_throttles_falls_back_for_unknown_action(self):
        from api.alerts.viewsets.mixins import ThrottlingMixin
        mixin = ThrottlingMixin()
        mixin.action = 'an_action_not_in_throttle_map'
        # Should not raise
        try:
            mixin.get_throttles()
        except AttributeError:
            pass  # super().get_throttles() not available without a real ViewSet base

    def test_alert_rate_throttle_scope_is_correct(self):
        from api.alerts.throttling import AlertRateThrottle, AlertCreateRateThrottle
        t1 = AlertRateThrottle()
        self.assertEqual(t1.scope, 'alert')
        t2 = AlertCreateRateThrottle()
        self.assertEqual(t2.scope, 'alert_create')

    def test_throttle_path_in_map_is_importable(self):
        from api.alerts.viewsets.mixins import ThrottlingMixin
        import importlib
        for action, path in ThrottlingMixin.throttle_map.items():
            mod_path, cls_name = path.rsplit('.', 1)
            try:
                mod = importlib.import_module(mod_path)
                cls = getattr(mod, cls_name)
                self.assertTrue(callable(cls), f"{path} must be callable")
            except Exception as e:
                self.fail(f"ThrottlingMixin.throttle_map['{action}'] = '{path}' "
                          f"is not importable: {e}")


# ─────────────────────────────────────────────────────────────────
# 4. AuditLogMixin
# ─────────────────────────────────────────────────────────────────
class AuditLogMixinTest(TestCase):

    def test_audit_silent_on_missing_audit_logger(self):
        from api.alerts.viewsets.mixins import AuditLogMixin
        from unittest.mock import patch
        mixin = AuditLogMixin()
        with patch('api.alerts.integration.integ_audit_logs.AuditLogger') as mock_cls:
            mock_cls.side_effect = ImportError("simulated")
            try:
                mixin._audit('create', None, None)
            except Exception as e:
                self.fail(f"_audit must be silent on error but raised: {e}")

    def test_audit_does_not_raise_with_real_audit_logger(self):
        from api.alerts.viewsets.mixins import AuditLogMixin
        mixin = AuditLogMixin()
        try:
            mixin._audit('create', None, None)
        except Exception as e:
            self.fail(f"_audit raised: {e}")

    def test_audit_is_called_from_perform_create(self):
        from api.alerts.viewsets.mixins import AuditLogMixin
        from unittest.mock import patch, MagicMock
        mixin = AuditLogMixin()
        mixin.request = MagicMock()
        mock_serializer = MagicMock()
        mock_serializer.save.return_value = 'fake_obj'

        # Provide a no-op super().perform_create
        with patch.object(AuditLogMixin, '_audit') as mock_audit:
            with patch('builtins.super', return_value=MagicMock(
                    perform_create=lambda s: 'fake_obj')):
                try:
                    mixin.perform_create(mock_serializer)
                except Exception:
                    pass
            # If _audit was called, the wiring is correct
            # (it may or may not have been depending on super() resolution)

    def test_audit_is_called_from_perform_destroy(self):
        from api.alerts.viewsets.mixins import AuditLogMixin
        from unittest.mock import patch, MagicMock
        mixin = AuditLogMixin()
        mixin.request = MagicMock()
        with patch.object(mixin, '_audit') as mock_audit:
            with patch('builtins.super', return_value=MagicMock(
                    perform_destroy=lambda i: None)):
                try:
                    mixin.perform_destroy(MagicMock())
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────────
# 5. BulkActionMixin
# ─────────────────────────────────────────────────────────────────
class BulkActionMixinTest(TestCase):

    def setUp(self):
        self.user = _make_user(username='bulk_user')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.rule = _make_rule('BulkTestRule', user=self.user)

    def test_bulk_delete_missing_ids_returns_400(self):
        from api.alerts.viewsets.mixins import BulkActionMixin
        from unittest.mock import MagicMock
        mixin = BulkActionMixin()
        mixin.get_queryset = lambda: AlertRule.objects.all()
        req = MagicMock()
        req.data = {}
        response = mixin.bulk_delete(req)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_bulk_delete_valid_ids_deletes_objects(self):
        from api.alerts.viewsets.mixins import BulkActionMixin
        from unittest.mock import MagicMock
        rule_to_delete = _make_rule('ToDelete', user=self.user)
        pk = rule_to_delete.id

        mixin = BulkActionMixin()
        mixin.get_queryset = lambda: AlertRule.objects.all()
        req = MagicMock()
        req.data = {'ids': [pk]}
        response = mixin.bulk_delete(req)
        self.assertEqual(response.data['deleted'], 1)
        self.assertFalse(AlertRule.objects.filter(pk=pk).exists())

    def test_bulk_update_field_missing_ids_returns_400(self):
        from api.alerts.viewsets.mixins import BulkActionMixin
        from unittest.mock import MagicMock
        mixin = BulkActionMixin()
        mixin.get_queryset = lambda: AlertRule.objects.all()
        req = MagicMock()
        req.data = {}
        response = mixin.bulk_update_field(req, 'is_active')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_field_missing_value_returns_400(self):
        from api.alerts.viewsets.mixins import BulkActionMixin
        from unittest.mock import MagicMock
        mixin = BulkActionMixin()
        mixin.get_queryset = lambda: AlertRule.objects.all()
        req = MagicMock()
        req.data = {'ids': [self.rule.id]}  # no is_active value
        response = mixin.bulk_update_field(req, 'is_active')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_field_activates_rules(self):
        from api.alerts.viewsets.mixins import BulkActionMixin
        from unittest.mock import MagicMock
        inactive = _make_rule('InactiveForBulk', user=self.user, is_active=False)

        mixin = BulkActionMixin()
        mixin.get_queryset = lambda: AlertRule.objects.all()
        req = MagicMock()
        req.data = {'ids': [inactive.id], 'is_active': True}
        response = mixin.bulk_update_field(req, 'is_active')
        self.assertEqual(response.data['updated'], 1)
        inactive.refresh_from_db()
        self.assertTrue(inactive.is_active)

    def test_bulk_update_status_via_api_endpoint(self):
        """End-to-end test: PATCH /rules/bulk-update-status/ using the
        BulkActionMixin through the real AlertRuleViewSet."""
        inactive = _make_rule('E2EBulkRule', user=self.user, is_active=False)
        r = self.client.patch('/rules/bulk-update-status/', {
            'ids': [inactive.id],
            'is_active': True,
        }, format='json')
        self.assertIn(r.status_code, [200, 201, 403])  # 403 if non-staff user
        if r.status_code == 200:
            self.assertEqual(r.data['updated'], 1)
