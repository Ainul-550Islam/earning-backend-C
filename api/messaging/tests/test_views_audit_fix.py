"""
test_views_audit_fix.py
=========================
Audit finding (Part 19): full line-by-line pass of views.py (previously
only its access-control-relevant parts had been checked). Two real bugs
found:

  1. MessageSearchView.get() called int() on unvalidated page/page_size
     query params before entering any try/except. A plain ValueError
     isn't an APIException, Http404, or PermissionDenied, so DRF's
     default exception handler doesn't format it and (even with
     messaging_exception_handler now correctly wired per the Part 6
     fix) it fell all the way through to a raw, unhandled 500 instead
     of a clean 400 for something as ordinary as ?page=abc.
  2. HealthCheckView (deliberately permission_classes=[] - load
     balancers must be able to probe it without auth) returned
     f"error: {exc}" for failed DB/cache/Elasticsearch checks straight
     to that same unauthenticated caller - potentially leaking internal
     hostnames, ports, or other infra detail from the raw exception
     text to anyone on the internet who requests the endpoint.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import UserFactory


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


class TestMessageSearchViewPageValidation(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_non_numeric_page_returns_400_not_500(self):
        r = _api(self.user).get("/messaging/search/?q=hello&page=abc")
        self.assertEqual(r.status_code, 400)

    def test_non_numeric_page_size_returns_400_not_500(self):
        r = _api(self.user).get("/messaging/search/?q=hello&page_size=xyz")
        self.assertEqual(r.status_code, 400)

    def test_negative_page_returns_400(self):
        r = _api(self.user).get("/messaging/search/?q=hello&page=-1")
        self.assertEqual(r.status_code, 400)

    def test_zero_page_size_returns_400(self):
        r = _api(self.user).get("/messaging/search/?q=hello&page_size=0")
        self.assertEqual(r.status_code, 400)

    def test_valid_page_still_works(self):
        with patch("messaging.utils.search_engine.search_messages") as mock_search:
            mock_search.return_value = {"results": [], "total": 0, "page": 2}
            r = _api(self.user).get("/messaging/search/?q=hello&page=2&page_size=10")
        self.assertEqual(r.status_code, 200)
        mock_search.assert_called_once()
        self.assertEqual(mock_search.call_args.kwargs["page"], 2)
        self.assertEqual(mock_search.call_args.kwargs["page_size"], 10)


class TestHealthCheckViewDoesNotLeakExceptionDetail(TestCase):
    def test_db_failure_does_not_leak_exception_text(self):
        with patch(
            "django.db.connection.ensure_connection",
            side_effect=RuntimeError("could not connect to server at 10.0.5.23:5432"),
        ):
            r = APIClient().get("/messaging/health/")
        self.assertEqual(r.status_code, 207)
        self.assertEqual(r.data["checks"]["database"], "error")
        self.assertNotIn("10.0.5.23", str(r.data))

    def test_cache_failure_does_not_leak_exception_text(self):
        real_cache_set = None
        from django.core.cache import cache as real_cache
        real_cache_set = real_cache.set

        def selective_fail(key, *args, **kwargs):
            if key == "health_check":
                raise RuntimeError("redis://internal-cache-host:6379 unreachable")
            return real_cache_set(key, *args, **kwargs)

        with patch("django.core.cache.cache.set", side_effect=selective_fail):
            r = APIClient().get("/messaging/health/")
        self.assertEqual(r.status_code, 207)
        self.assertEqual(r.data["checks"]["cache"], "error")
        self.assertNotIn("internal-cache-host", str(r.data))

    def test_elasticsearch_failure_does_not_leak_exception_text(self):
        with patch(
            "messaging.utils.search_engine.get_es_client",
            side_effect=RuntimeError("connection refused at es-cluster.internal:9200"),
        ):
            r = APIClient().get("/messaging/health/")
        self.assertEqual(r.data["checks"]["elasticsearch"], "error")
        self.assertNotIn("es-cluster.internal", str(r.data))

    def test_full_exception_still_reaches_logs(self):
        """The detail isn't lost, just not exposed publicly."""
        with self.assertLogs("messaging.views", level="ERROR") as cm:
            with patch(
                "django.db.connection.ensure_connection",
                side_effect=RuntimeError("secret-internal-detail"),
            ):
                APIClient().get("/messaging/health/")
        self.assertTrue(any("secret-internal-detail" in msg for msg in cm.output))

    def test_healthy_response_unaffected(self):
        r = APIClient().get("/messaging/health/")
        self.assertIn(r.status_code, (200, 207))
        self.assertIn(r.data["checks"]["database"], ("ok", "error"))
