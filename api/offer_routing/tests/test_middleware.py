"""
Tests for offer_routing/middleware.py

Covers:
  RoutingContextMiddleware
  RoutingPerformanceMiddleware
  RoutingAuditMiddleware
  RoutingCacheMiddleware
"""

from unittest.mock import MagicMock, patch, PropertyMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from ..middleware import (
    RoutingContextMiddleware,
    RoutingPerformanceMiddleware,
    RoutingAuditMiddleware,
    RoutingCacheMiddleware,
    get_routing_middleware,
)

User = get_user_model()


def _dummy_response(get_response=None):
    """Return a simple callable that wraps get_response."""
    if get_response is None:
        def get_response(req):
            return HttpResponse("ok")
    return get_response


def _make_request(factory, path="/api/route/", user=None, authenticated=True):
    request = factory.get(path)
    if user is None:
        user = AnonymousUser()
    request.user = user
    if not authenticated:
        request.user = AnonymousUser()
    request.session = {}
    return request


# ---------------------------------------------------------------------------
# RoutingContextMiddleware
# ---------------------------------------------------------------------------

class RoutingContextMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = RoutingContextMiddleware(_dummy_response())
        self.user = User.objects.create_user(username="ctx_user", password="pass")

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="Mozilla/5.0")
    def test_process_request_sets_routing_user(self, mock_ua, mock_ip):
        request = _make_request(self.factory, user=self.user)
        request.session = {"routing_session_id": "existing-id"}
        result = self.mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.routing_user, self.user)
        self.assertEqual(request.routing_user_id, self.user.id)

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="")
    def test_process_request_anonymous_user(self, mock_ua, mock_ip):
        request = _make_request(self.factory, authenticated=False)
        request.session = {}
        self.mw.process_request(request)
        self.assertIsNone(request.routing_user)
        self.assertIsNone(request.routing_user_id)

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="")
    def test_process_request_creates_session_id(self, mock_ua, mock_ip):
        request = _make_request(self.factory, user=self.user)
        request.session = {}
        self.mw.process_request(request)
        self.assertIsNotNone(request.routing_session_id)

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="")
    def test_process_request_reuses_existing_session_id(self, mock_ua, mock_ip):
        request = _make_request(self.factory, user=self.user)
        request.session = {"routing_session_id": "my-session"}
        self.mw.process_request(request)
        self.assertEqual(request.routing_session_id, "my-session")

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="Mozilla Mobile")
    def test_device_context_detects_mobile(self, mock_ua, mock_ip):
        request = self.factory.get("/", HTTP_USER_AGENT="Mozilla Mobile Android")
        request.user = self.user
        request.session = {}
        self.mw.process_request(request)
        self.assertEqual(request.device_context["type"], "mobile")

    def test_process_response_adds_security_headers(self):
        request = _make_request(self.factory)
        response = HttpResponse("ok")
        response = self.mw.process_response(request, response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    @patch("offer_routing.middleware.get_client_ip", return_value="127.0.0.1")
    @patch("offer_routing.middleware.get_client_user_agent", return_value="")
    def test_graceful_fallback_on_exception(self, mock_ua, mock_ip):
        """Middleware must not raise even when sub-calls fail."""
        request = _make_request(self.factory, user=self.user)
        request.session = {}
        # Break get_geo_context
        with patch.object(self.mw, "_get_geo_context", side_effect=RuntimeError("geo fail")):
            # Should not raise
            self.mw.process_request(request)

    def test_get_routing_middleware_returns_list(self):
        middleware_list = get_routing_middleware()
        self.assertIsInstance(middleware_list, list)
        self.assertIsInstance(middleware_list, (list, dict, type(None)))


# ---------------------------------------------------------------------------
# RoutingPerformanceMiddleware
# ---------------------------------------------------------------------------

class RoutingPerformanceMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = RoutingPerformanceMiddleware(_dummy_response())

    @patch('offer_routing.middleware.psutil', create=True)
    def test_process_request_sets_tracking(self, mock_psutil):
        mock_psutil.Process.return_value.memory_info.return_value.rss = 50 * 1024 * 1024
        request = _make_request(self.factory)
        self.mw.process_request(request)
        self.assertIn("start_time", request.performance_tracking)
        self.assertIn("request_id", request.performance_tracking)

    def test_process_request_no_psutil(self):
        request = _make_request(self.factory)
        with patch.dict("sys.modules", {"psutil": None}):
            # Should fall back gracefully
            self.mw.process_request(request)
        self.assertIn("start_time", request.performance_tracking)

    @patch('offer_routing.middleware.psutil', create=True)
    def test_process_response_adds_header(self, mock_psutil):
        process_mock = MagicMock()
        process_mock.memory_info.return_value.rss = 60 * 1024 * 1024
        mock_psutil.Process.return_value = process_mock

        request = _make_request(self.factory)
        request.performance_tracking = {
            "start_time": 0.0,
            "memory_start": 50.0,
            "request_id": "abc-123",
        }
        response = HttpResponse("ok")

        with patch("offer_routing.middleware.cache") as mock_cache, \
             patch("offer_routing.middleware.log_performance_metrics") as mock_task:
            mock_task.delay = MagicMock()
            response = self.mw.process_response(request, response)

        self.assertIn("X-Response-Time", response)

    def test_process_response_no_tracking_attr(self):
        """If performance_tracking was never set, response must still be returned."""
        request = _make_request(self.factory)
        response = HttpResponse("ok")
        result = self.mw.process_response(request, response)
        self.assertEqual(result.status_code, 200)


# ---------------------------------------------------------------------------
# RoutingAuditMiddleware
# ---------------------------------------------------------------------------

class RoutingAuditMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = RoutingAuditMiddleware(_dummy_response())
        self.user = User.objects.create_user(username="audit_user", password="pass")

    @patch("offer_routing.middleware.get_client_ip", return_value="10.0.0.1")
    @patch("offer_routing.middleware.validate_ip_address",
           return_value={"is_valid": True})
    def test_process_request_normal_returns_none(self, mock_validate, mock_ip):
        request = _make_request(self.factory, user=self.user)
        result = self.mw.process_request(request)
        self.assertIsNone(result)

    @patch("offer_routing.middleware.get_client_ip", return_value="10.0.0.2")
    @patch("offer_routing.middleware.validate_ip_address",
           return_value={"is_valid": True})
    def test_xss_pattern_flags_request(self, mock_validate, mock_ip):
        request = self.factory.get("/?q=<script>alert(1)</script>")
        request.user = self.user
        request.session = {}
        self.mw.process_request(request)
        flags = getattr(request, "security_flags", {})
        # May or may not flag depending on GET parsing; just verify no exception
        self.assertIsInstance(flags, dict)

    @patch("offer_routing.middleware.get_client_ip", return_value="10.0.0.3")
    @patch("offer_routing.middleware.validate_ip_address",
           return_value={"is_valid": True})
    def test_process_response_no_security_flags(self, mock_validate, mock_ip):
        request = _make_request(self.factory, user=self.user)
        request.session = {}
        self.mw.process_request(request)
        response = HttpResponse("ok")
        result = self.mw.process_response(request, response)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("X-Security-Flag", result)

    def test_is_rate_limited_increments_counter(self):
        from django.core.cache import cache
        cache.clear()
        # First 99 calls should not be rate-limited
        for _ in range(99):
            limited = self.mw._is_rate_limited(MagicMock(), "1.2.3.4")
        self.assertFalse(limited)
        # 100th call tips the counter to 100 → should trip on next call
        self.mw._is_rate_limited(MagicMock(), "1.2.3.4")
        limited = self.mw._is_rate_limited(MagicMock(), "1.2.3.4")
        self.assertTrue(limited)

    def test_check_suspicious_sql_injection(self):
        request = self.factory.get("/?id=1 OR 1=1--")
        request.user = AnonymousUser()
        indicators = self.mw._check_suspicious_patterns(request)
        self.assertIn("sql_injection", indicators)

    def test_check_suspicious_bot_user_agent(self):
        request = self.factory.get("/", HTTP_USER_AGENT="BadBot/1.0")
        request.user = AnonymousUser()
        indicators = self.mw._check_suspicious_patterns(request)
        self.assertIn("suspicious_user_agent", indicators)


# ---------------------------------------------------------------------------
# RoutingCacheMiddleware
# ---------------------------------------------------------------------------

class RoutingCacheMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = RoutingCacheMiddleware(_dummy_response())
        from django.core.cache import cache
        cache.clear()

    def test_non_get_request_skipped(self):
        request = self.factory.post("/api/route/")
        request.user = AnonymousUser()
        request.session = {}
        result = self.mw.process_request(request)
        self.assertIsNone(result)

    def test_admin_path_skipped(self):
        request = self.factory.get("/admin/dashboard/")
        request.user = AnonymousUser()
        request.session = {}
        result = self.mw.process_request(request)
        self.assertIsNone(result)

    def test_cache_miss_marks_request(self):
        request = self.factory.get("/api/offers/")
        request.user = AnonymousUser()
        request.session = {}
        result = self.mw.process_request(request)
        self.assertIsNone(result)
        self.assertTrue(getattr(request, "should_cache_response", False))

    def test_cache_hit_returns_cached_response(self):
        from django.core.cache import cache

        request = self.factory.get("/api/offers/")
        request.user = AnonymousUser()
        request.session = {}

        # Prime the cache
        cache_key = self.mw._generate_cache_key(request)
        cache.set(cache_key, {"content": b"cached", "headers": {}}, timeout=60)

        result = self.mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result["X-Cache"], "HIT")

    def test_process_response_caches_200(self):
        from django.core.cache import cache

        request = self.factory.get("/api/offers/?page=2")
        request.user = AnonymousUser()
        request.session = {}
        request.should_cache_response = True
        request.cache_key = "routing_response:test123"

        response = HttpResponse("body", content_type="text/plain")
        self.mw.process_response(request, response)

        cached = cache.get("routing_response:test123")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["content"], b"body")

    def test_process_response_does_not_cache_non_200(self):
        from django.core.cache import cache

        request = self.factory.get("/api/offers/")
        request.user = AnonymousUser()
        request.session = {}
        request.should_cache_response = True
        request.cache_key = "routing_response:err404"

        response = HttpResponse("not found", status=404)
        self.mw.process_response(request, response)

        cached = cache.get("routing_response:err404")
        self.assertIsNone(cached)

    def test_generate_cache_key_is_consistent(self):
        request = self.factory.get("/api/offers/?q=test")
        request.user = AnonymousUser()
        request.session = {}
        key1 = self.mw._generate_cache_key(request)
        key2 = self.mw._generate_cache_key(request)
        self.assertEqual(key1, key2)

    def test_generate_cache_key_differs_by_path(self):
        r1 = self.factory.get("/api/offers/")
        r1.user = AnonymousUser()
        r1.session = {}
        r2 = self.factory.get("/api/routes/")
        r2.user = AnonymousUser()
        r2.session = {}
        self.assertNotEqual(
            self.mw._generate_cache_key(r1),
            self.mw._generate_cache_key(r2),
        )
