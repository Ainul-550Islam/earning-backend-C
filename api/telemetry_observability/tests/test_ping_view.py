"""
Tests for PingView (GET /ping/) and ReadinessView (GET /readiness/).

Both views are unauthenticated — we use the plain api_client fixture.
ReadinessView hits the DB and cache, so tests that exercise those paths
need the db marker and a working cache backend (django's LocMemCache in test).
"""
import pytest
from unittest.mock import MagicMock, patch

from django.db import OperationalError as DbOperationalError
from django.core.cache import cache


# ── PingView ──────────────────────────────────────────────────────────────────

class TestPingView:
    """GET /ping/ — no auth, no DB, always 200 while the process is alive."""

    def test_returns_200(self, api_client):
        response = api_client.get('/ping/')
        assert response.status_code == 200

    def test_no_authentication_required(self, api_client):
        """Unauthenticated client must get 200, not 401/403."""
        response = api_client.get('/ping/')
        assert response.status_code not in (401, 403)

    def test_response_has_status_ok(self, api_client):
        response = api_client.get('/ping/')
        assert response.data['status'] == 'ok'

    def test_response_has_version(self, api_client):
        response = api_client.get('/ping/')
        assert 'version' in response.data

    def test_post_not_allowed(self, api_client):
        response = api_client.post('/ping/', {})
        assert response.status_code == 405

    def test_returns_json(self, api_client):
        response = api_client.get('/ping/')
        assert 'application/json' in response['Content-Type']


# ── ReadinessView ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReadinessView:
    """GET /readiness/ — checks DB, cache, and internet HealthStatus record."""

    def test_returns_200_when_all_healthy(self, api_client):
        response = api_client.get('/readiness/')
        # With a working test DB and LocMemCache, DB + cache should both pass.
        # Internet is 'unknown' (no HealthStatus row yet) — not a hard failure.
        assert response.status_code == 200

    def test_no_authentication_required(self, api_client):
        response = api_client.get('/readiness/')
        assert response.status_code not in (401, 403)

    def test_response_has_checks_dict(self, api_client):
        response = api_client.get('/readiness/')
        assert 'checks' in response.data
        assert isinstance(response.data['checks'], dict)

    def test_database_check_reported(self, api_client):
        response = api_client.get('/readiness/')
        assert 'database' in response.data['checks']

    def test_cache_check_reported(self, api_client):
        response = api_client.get('/readiness/')
        assert 'cache' in response.data['checks']

    def test_internet_check_reported(self, api_client):
        response = api_client.get('/readiness/')
        assert 'internet' in response.data['checks']

    def test_internet_unknown_when_no_health_record(self, api_client):
        """Before the Celery task runs, internet status should be 'unknown'."""
        from api.telemetry_observability.models.health_status import HealthStatus
        HealthStatus.objects.filter(service_name='internet').delete()
        response = api_client.get('/readiness/')
        assert response.data['checks']['internet'] == 'unknown'
        assert response.status_code == 200   # unknown is not a hard failure

    def test_internet_ok_when_healthy_record_exists(self, api_client):
        from api.telemetry_observability.models.health_status import HealthStatus
        HealthStatus.objects.update_or_create(
            service_name='internet', component_name='connectivity',
            defaults={'status': 'healthy', 'health_score': 100},
        )
        response = api_client.get('/readiness/')
        assert response.data['checks']['internet'] == 'ok'

    def test_internet_degraded_does_not_fail_readiness(self, api_client):
        """Degraded internet is a warning — traffic should still be routed."""
        from api.telemetry_observability.models.health_status import HealthStatus
        HealthStatus.objects.update_or_create(
            service_name='internet', component_name='connectivity',
            defaults={'status': 'degraded', 'health_score': 60},
        )
        response = api_client.get('/readiness/')
        assert response.data['checks']['internet'] == 'degraded'
        assert response.status_code == 200

    def test_internet_unhealthy_returns_503(self, api_client):
        """Fully unreachable internet should mark the pod unready."""
        from api.telemetry_observability.models.health_status import HealthStatus
        HealthStatus.objects.update_or_create(
            service_name='internet', component_name='connectivity',
            defaults={'status': 'unhealthy', 'health_score': 0},
        )
        response = api_client.get('/readiness/')
        assert response.data['checks']['internet'] == 'unhealthy'
        assert response.status_code == 503

    def test_503_when_database_down(self, api_client):
        with patch(
            'django.db.backends.base.base.DatabaseWrapper.ensure_connection',
            side_effect=DbOperationalError('DB gone'),
        ):
            response = api_client.get('/readiness/')

        assert response.status_code == 503
        assert response.data['checks']['database'] == 'error'

    def test_503_when_cache_fails_readback(self, api_client):
        with patch('django.core.cache.cache.set', return_value=None), \
             patch('django.core.cache.cache.get', return_value=None):
            response = api_client.get('/readiness/')

        assert response.status_code == 503
        assert response.data['checks']['cache'] == 'error'

    def test_response_has_status_field(self, api_client):
        response = api_client.get('/readiness/')
        assert 'status' in response.data
        assert response.data['status'] in ('ok', 'degraded')

    def test_response_has_version(self, api_client):
        response = api_client.get('/readiness/')
        assert 'version' in response.data

    def test_post_not_allowed(self, api_client):
        response = api_client.post('/readiness/', {})
        assert response.status_code == 405
