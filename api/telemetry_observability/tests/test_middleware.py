"""
Tests for middleware.py — TelemetryMiddleware request recording.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

from ..middleware import TelemetryMiddleware


def make_request(path='/api/test/', method='GET'):
    factory = RequestFactory()
    req = getattr(factory, method.lower())(path)
    req.user = AnonymousUser()
    return req


def make_response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


class TestTelemetryMiddleware:
    def setup_method(self):
        self.get_response = MagicMock(return_value=make_response(200))
        self.middleware    = TelemetryMiddleware(self.get_response)

    def test_middleware_passes_response_through(self):
        req  = make_request()
        resp = self.middleware(req)
        assert resp.status_code == 200

    def test_get_response_called_once(self):
        req = make_request()
        self.middleware(req)
        self.get_response.assert_called_once_with(req)

    def test_middleware_does_not_raise_on_metric_error(self):
        """Middleware should never block a request even if recording fails."""
        with patch('api.telemetry_observability.middleware.MetricsCollector',
                   side_effect=Exception("DB down")):
            req  = make_request()
            resp = self.middleware(req)
            assert resp is not None

    def test_middleware_does_not_raise_on_trace_error(self):
        with patch('api.telemetry_observability.middleware.TracingService',
                   side_effect=Exception("trace error")):
            req  = make_request()
            resp = self.middleware(req)
            assert resp is not None

    def test_500_response_does_not_raise(self):
        self.get_response.return_value = make_response(500)
        req  = make_request()
        resp = self.middleware(req)
        assert resp.status_code == 500

    def test_404_response_passes_through(self):
        self.get_response.return_value = make_response(404)
        req  = make_request('/nonexistent/')
        resp = self.middleware(req)
        assert resp.status_code == 404

    def test_records_http_request_total_metric(self):
        recorded = []
        with patch('api.telemetry_observability.middleware.MetricsCollector') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            req  = make_request()
            self.middleware(req)
            counter_calls = [
                c for c in mock_instance.record_counter.call_args_list
            ]
            names = [c[1].get('name') or c[0][0] for c in counter_calls
                     if c[0] or c[1]]
            # At least one counter call with http_request_total
            assert any('http_request_total' in str(c) for c in counter_calls)

    def test_records_duration_gauge(self):
        with patch('api.telemetry_observability.middleware.MetricsCollector') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            req = make_request()
            self.middleware(req)
            gauge_calls = mock_instance.record_gauge.call_args_list
            assert any('duration_ms' in str(c) for c in gauge_calls)


@pytest.mark.django_db
class TestTelemetryMiddlewareLogCreation:
    def test_5xx_creates_log_entry(self):
        from ..models.log_entry import LogEntry
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = RequestFactory()
        req     = factory.get('/api/broken/')
        req.user = AnonymousUser()
        req.build_absolute_uri = lambda: 'http://testserver/api/broken/'

        get_response  = MagicMock(return_value=make_response(500))
        middleware    = TelemetryMiddleware(get_response)
        before_count  = LogEntry.objects.count()
        middleware(req)
        after_count   = LogEntry.objects.count()
        assert after_count > before_count

    def test_2xx_does_not_create_error_log(self):
        from ..models.log_entry import LogEntry
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = RequestFactory()
        req     = factory.get('/api/ok/')
        req.user = AnonymousUser()
        req.build_absolute_uri = lambda: 'http://testserver/api/ok/'

        get_response  = MagicMock(return_value=make_response(200))
        middleware    = TelemetryMiddleware(get_response)
        before_count  = LogEntry.objects.filter(level='error', source='middleware').count()
        middleware(req)
        after_count   = LogEntry.objects.filter(level='error', source='middleware').count()
        assert after_count == before_count
