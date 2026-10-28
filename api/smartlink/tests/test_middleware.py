"""
Tests for SmartLink Middleware
================================
Previously 0% coverage for both middleware classes.

1. SmartLinkRedirectMiddleware  — /go/<slug>/ fast-path cache redirect
2. SmartLinkPerformanceMiddleware — X-SmartLink-Time header + slow-request logging
"""
import uuid
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse, HttpResponseRedirect
from django.core.cache import cache


# ─── Middleware imports ────────────────────────────────────────────────────────

from api.smartlink.middleware import (
    SmartLinkRedirectMiddleware,
    SmartLinkPerformanceMiddleware,
)
from api.smartlink.constants import CACHE_PREFIX_SMARTLINK, CACHE_PREFIX_FRAUD


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_request(path='/', method='GET', ip='1.2.3.4'):
    rf      = RequestFactory()
    request = rf.get(path)
    request.META['REMOTE_ADDR'] = ip
    return request


def _make_mw(mw_class, next_response=None):
    """Build a middleware instance with a simple get_response stub."""
    if next_response is None:
        next_response = HttpResponse('next', status=200)
    def get_response(request):
        return next_response
    return mw_class(get_response)


# ═════════════════════════════════════════════════════════════════════════════
# 1. SmartLinkRedirectMiddleware
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkRedirectMiddlewareTest(TestCase):

    def setUp(self):
        cache.clear()
        self.mw = _make_mw(SmartLinkRedirectMiddleware)

    def _cache_key(self, slug):
        return f"{CACHE_PREFIX_SMARTLINK}{slug}:simple"

    # ── Cache HIT path ────────────────────────────────────────────────────────

    def test_cache_hit_returns_302_redirect(self):
        """Cached slug → 302 redirect to cached URL (fast path)."""
        slug = 'test-sl'
        dest = 'https://offer.example.com/?c=1'
        cache.set(self._cache_key(slug), dest)

        request  = _make_request(f'/go/{slug}/')
        response = self.mw(request)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response['Location'], dest)

    def test_cache_hit_adds_x_smartlink_time_header(self):
        """Cache-hit response includes X-SmartLink-Time header."""
        slug = 'hdr-sl'
        cache.set(self._cache_key(slug), 'https://offer.example.com/')

        request  = _make_request(f'/go/{slug}/')
        response = self.mw(request)

        self.assertIn('X-SmartLink-Time', response)

    def test_x_smartlink_time_is_numeric_ms(self):
        """X-SmartLink-Time value is a valid float in ms."""
        slug = 'time-sl'
        cache.set(self._cache_key(slug), 'https://offer.example.com/')
        response = self.mw(_make_request(f'/go/{slug}/'))
        time_val = float(response['X-SmartLink-Time'].replace('ms', ''))
        self.assertGreaterEqual(time_val, 0)

    # ── Blocked IP path ───────────────────────────────────────────────────────

    def test_blocked_ip_returns_403(self):
        """Request from a blocked IP returns 403 even when slug is cached."""
        slug = 'blocked-sl'
        ip   = '9.9.9.9'
        cache.set(self._cache_key(slug), 'https://offer.example.com/')
        cache.set(f"{CACHE_PREFIX_FRAUD}blocked:{ip}", '1')

        request  = _make_request(f'/go/{slug}/', ip=ip)
        response = self.mw(request)

        self.assertEqual(response.status_code, 403)

    def test_non_blocked_ip_gets_redirect(self):
        """Non-blocked IP is not affected by the fraud cache check."""
        slug = 'ok-sl'
        ip   = '5.5.5.5'
        cache.set(self._cache_key(slug), 'https://ok.example.com/')
        # Do NOT set a blocked entry for this IP

        response = self.mw(_make_request(f'/go/{slug}/', ip=ip))
        self.assertIsInstance(response, HttpResponseRedirect)

    # ── Cache MISS path ───────────────────────────────────────────────────────

    def test_cache_miss_falls_through_to_view(self):
        """Cache miss → middleware returns None and passes to the next handler."""
        slug = 'miss-sl'
        # No cache.set — cache miss

        next_resp = HttpResponse('view response', status=200)
        mw        = _make_mw(SmartLinkRedirectMiddleware, next_resp)
        response  = mw(_make_request(f'/go/{slug}/'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'view response')

    # ── Non-redirect path ─────────────────────────────────────────────────────

    def test_non_redirect_path_passes_through(self):
        """Requests to /api/... are not intercepted by the redirect middleware."""
        request  = _make_request('/api/smartlink/smartlinks/')
        next_resp = HttpResponse('api response', status=200)
        mw        = _make_mw(SmartLinkRedirectMiddleware, next_resp)
        response  = mw(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'api response')

    def test_root_path_passes_through(self):
        """GET / passes through without being redirected."""
        next_resp = HttpResponse('root', status=200)
        mw        = _make_mw(SmartLinkRedirectMiddleware, next_resp)
        response  = mw(_make_request('/'))
        self.assertEqual(response.status_code, 200)

    # ── Empty slug ────────────────────────────────────────────────────────────

    def test_empty_slug_passes_through(self):
        """GET /go/ (no slug) passes through to the view."""
        next_resp = HttpResponse('no slug', status=200)
        mw        = _make_mw(SmartLinkRedirectMiddleware, next_resp)
        response  = mw(_make_request('/go/'))
        self.assertEqual(response.status_code, 200)

    # ── IP extraction ─────────────────────────────────────────────────────────

    def test_cloudflare_ip_header_used(self):
        """X-CF-Connecting-IP takes priority over REMOTE_ADDR."""
        slug = 'cf-sl'
        real_ip = '203.0.113.1'
        proxy_ip = '10.0.0.1'
        cache.set(self._cache_key(slug), 'https://dest.example.com/')
        cache.set(f"{CACHE_PREFIX_FRAUD}blocked:{real_ip}", '1')

        rf      = RequestFactory()
        request = rf.get(f'/go/{slug}/')
        request.META['REMOTE_ADDR']            = proxy_ip
        request.META['HTTP_CF_CONNECTING_IP']  = real_ip

        response = self.mw(request)
        self.assertEqual(response.status_code, 403)

    def test_x_forwarded_for_used_when_no_cf_header(self):
        """X-Forwarded-For first IP used when CF header absent."""
        slug = 'xff-sl'
        real_ip = '203.0.113.99'
        cache.set(self._cache_key(slug), 'https://dest.example.com/')
        cache.set(f"{CACHE_PREFIX_FRAUD}blocked:{real_ip}", '1')

        rf      = RequestFactory()
        request = rf.get(f'/go/{slug}/')
        request.META['REMOTE_ADDR']             = '10.0.0.2'
        request.META['HTTP_X_FORWARDED_FOR']    = f'{real_ip}, 10.0.0.2'

        response = self.mw(request)
        self.assertEqual(response.status_code, 403)

    # ── Custom redirect prefix ────────────────────────────────────────────────

    @override_settings(SMARTLINK_REDIRECT_PREFIX='/track/')
    def test_custom_redirect_prefix(self):
        """Respects SMARTLINK_REDIRECT_PREFIX setting."""
        mw   = _make_mw(SmartLinkRedirectMiddleware)
        slug = 'custom-sl'
        cache.set(f"{CACHE_PREFIX_SMARTLINK}{slug}:simple", 'https://custom.example.com/')

        response = mw(_make_request(f'/track/{slug}/'))
        self.assertIsInstance(response, HttpResponseRedirect)

    @override_settings(SMARTLINK_REDIRECT_PREFIX='/track/')
    def test_default_go_prefix_not_intercepted_when_custom(self):
        """When custom prefix is set, /go/ is NOT intercepted."""
        mw   = _make_mw(SmartLinkRedirectMiddleware, HttpResponse('ok', 200))
        slug = 'custom-sl'
        cache.set(f"{CACHE_PREFIX_SMARTLINK}{slug}:simple", 'https://custom.example.com/')

        response = mw(_make_request(f'/go/{slug}/'))
        # Falls through to next — not a redirect
        self.assertEqual(response.status_code, 200)


# ═════════════════════════════════════════════════════════════════════════════
# 2. SmartLinkPerformanceMiddleware
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkPerformanceMiddlewareTest(TestCase):

    def setUp(self):
        self.mw = _make_mw(SmartLinkPerformanceMiddleware)

    # ── Header injection ──────────────────────────────────────────────────────

    def test_api_request_gets_timing_header(self):
        """Requests to /api/smartlink/ receive X-SmartLink-Time header."""
        response = self.mw(_make_request('/api/smartlink/smartlinks/'))
        self.assertIn('X-SmartLink-Time', response)

    def test_go_request_gets_timing_header(self):
        """Requests to /go/ receive X-SmartLink-Time header."""
        response = self.mw(_make_request('/go/test-sl/'))
        self.assertIn('X-SmartLink-Time', response)

    def test_non_monitored_path_no_timing_header(self):
        """Requests to /admin/ do NOT get the timing header."""
        response = self.mw(_make_request('/admin/'))
        self.assertNotIn('X-SmartLink-Time', response)

    def test_timing_header_format(self):
        """X-SmartLink-Time value ends with 'ms' and is a valid float."""
        response = self.mw(_make_request('/api/smartlink/smartlinks/'))
        val = response['X-SmartLink-Time']
        self.assertTrue(val.endswith('ms'), f"Expected 'ms' suffix, got: {val}")
        float_val = float(val.replace('ms', ''))
        self.assertGreaterEqual(float_val, 0)

    def test_timing_value_is_positive(self):
        """Elapsed time is a non-negative float (can be 0.00ms for trivial in-memory calls)."""
        response = self.mw(_make_request('/api/smartlink/smartlinks/'))
        elapsed = float(response['X-SmartLink-Time'].replace('ms', ''))
        self.assertGreaterEqual(elapsed, 0)

    # ── Slow request logging ──────────────────────────────────────────────────

    def test_slow_request_triggers_warning_log(self):
        """Request taking > 100ms triggers a WARNING log."""
        import time as _time

        slow_response = HttpResponse('slow', 200)
        call_count    = [0]

        def slow_get_response(request):
            _time.sleep(0.105)  # 105ms — exceeds 100ms threshold
            return slow_response

        mw = SmartLinkPerformanceMiddleware(slow_get_response)

        with self.assertLogs('smartlink.performance', level='WARNING') as log:
            mw(_make_request('/api/smartlink/smartlinks/'))

        self.assertTrue(any('Slow' in line for line in log.output),
                        msg="Expected 'Slow' in warning log output")

    def test_fast_request_no_warning_log(self):
        """Fast request (< 100ms) does NOT produce a 'Slow' WARNING log."""
        with patch.object(
            __import__('api.smartlink.middleware', fromlist=['perf_logger']).perf_logger,
            'warning',
        ) as mock_warning:
            self.mw(_make_request('/api/smartlink/smartlinks/'))

        mock_warning.assert_not_called()

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_v2_api_path_monitored(self):
        """Requests to /api/smartlink/ paths including v2 get timing header."""
        response = self.mw(_make_request('/api/smartlink/v2/smartlinks/'))
        self.assertIn('X-SmartLink-Time', response)

    def test_static_files_not_monitored(self):
        """/static/ files do not get the timing header."""
        response = self.mw(_make_request('/static/css/app.css'))
        self.assertNotIn('X-SmartLink-Time', response)

    def test_favicon_not_monitored(self):
        """/favicon.ico does not get the timing header."""
        response = self.mw(_make_request('/favicon.ico'))
        self.assertNotIn('X-SmartLink-Time', response)

    def test_response_content_unchanged(self):
        """Middleware does not modify the response body."""
        body      = b'{"smartlinks": []}'
        next_resp = HttpResponse(body, content_type='application/json')
        mw        = _make_mw(SmartLinkPerformanceMiddleware, next_resp)
        response  = mw(_make_request('/api/smartlink/smartlinks/'))
        self.assertEqual(response.content, body)

    def test_multiple_monitored_prefixes(self):
        """/go/ and /api/smartlink/ are both monitored."""
        for path in ['/go/some-slug/', '/api/smartlink/clicks/']:
            response = self.mw(_make_request(path))
            self.assertIn('X-SmartLink-Time', response,
                          msg=f"Path {path} should receive timing header")

    def test_middleware_does_not_swallow_exceptions(self):
        """Middleware propagates exceptions from the next handler."""
        def raising_handler(request):
            raise ValueError("Simulated view error")

        mw = SmartLinkPerformanceMiddleware(raising_handler)
        with self.assertRaises(ValueError):
            mw(_make_request('/api/smartlink/smartlinks/'))
