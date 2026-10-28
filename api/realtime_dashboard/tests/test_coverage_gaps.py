"""
Coverage gap-fill tests — every uncovered line from the post-fix audit.

After fixes: 94% total. Target: 100% per-file, 100% total.

Modules covered (gap → target):
    tasks.py                       0% → 100%
    views.py                      74% → 100%
    permissions.py                78% → 100%
    app_settings.py               73% → 100%
    exceptions.py                 86% → 100%
    decorators.py                 86% → 100%
    services/widget_service.py    86% → 100%
    managers/*.py               86-89% → 100%
    pagination.py                 86% → 100%
    websocket_manager.py          96% → 100%
    viewsets/*.py               97-99% → 100%
    consumers/dashboard_consumer  74% → 100%
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIRequestFactory


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TASKS  (0% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='module')
def celery_test_app():
    """
    Create a minimal Celery application for task tests.

    @shared_task is a proxy that binds to the 'default' Celery app at runtime.
    Without an app, apply() raises RuntimeError. Setting task_always_eager=True
    makes apply() execute synchronously without a broker.
    """
    from celery import Celery
    app = Celery('realtime_dashboard_test')
    app.config_from_object({
        'task_always_eager': True,
        'task_eager_propagates': True,
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
    })
    app.set_default()
    return app


@pytest.mark.django_db
class TestCleanupStaleConnectionsTask:
    """tasks.cleanup_stale_connections — 0% → 100%."""

    def test_success_returns_cleaned_count(self, celery_test_app):
        """Happy path: service reports N cleaned; task returns dict."""
        from api.realtime_dashboard.tasks import cleanup_stale_connections
        with patch(
            'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
        ) as MockSvc:
            MockSvc.return_value.cleanup_old_connections.return_value = 7
            result = cleanup_stale_connections.apply(kwargs={'timeout_seconds': 300})
            assert result.result == {'cleaned': 7, 'timeout_seconds': 300}
            MockSvc.return_value.cleanup_old_connections.assert_called_once_with(300)

    def test_default_timeout_is_3600(self, celery_test_app):
        """Default timeout_seconds=3600 is forwarded to the service."""
        from api.realtime_dashboard.tasks import cleanup_stale_connections
        with patch(
            'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
        ) as MockSvc:
            MockSvc.return_value.cleanup_old_connections.return_value = 0
            result = cleanup_stale_connections.apply()
            assert result.result['timeout_seconds'] == 3600

    def test_zero_cleaned_is_valid(self, celery_test_app):
        """No stale connections is a valid, non-error result."""
        from api.realtime_dashboard.tasks import cleanup_stale_connections
        with patch(
            'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
        ) as MockSvc:
            MockSvc.return_value.cleanup_old_connections.return_value = 0
            result = cleanup_stale_connections.apply(kwargs={'timeout_seconds': 600})
            assert result.result == {'cleaned': 0, 'timeout_seconds': 600}

    def test_exception_triggers_retry(self, celery_test_app):
        """Service exception → task calls self.retry() → Celery Retry raised."""
        from api.realtime_dashboard.tasks import cleanup_stale_connections
        from celery.exceptions import Retry
        with patch(
            'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
        ) as MockSvc:
            MockSvc.return_value.cleanup_old_connections.side_effect = RuntimeError('boom')
            with pytest.raises((Retry, RuntimeError)):
                # task_eager_propagates=True causes the retry/exception to propagate
                cleanup_stale_connections.apply(kwargs={'timeout_seconds': 60})


@pytest.mark.django_db
class TestBroadcastActiveMetricsTask:
    """tasks.broadcast_active_metrics — 0% → 100%."""

    def test_broadcasts_all_active_metrics(self, celery_test_app):
        """With active metrics, EventStreamingService.stream_metric_updates is called."""
        from api.realtime_dashboard.tasks import broadcast_active_metrics
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        m1 = create_real_time_metric(name='CPU', status='active')
        m2 = create_real_time_metric(name='MEM', status='active')
        with patch(
            'api.realtime_dashboard.services.event_streaming_service.EventStreamingService'
        ) as MockStream:
            result = broadcast_active_metrics.apply()
            assert result.result['metric_count'] == 2
            MockStream.return_value.stream_metric_updates.assert_called_once()
            call_ids = set(MockStream.return_value.stream_metric_updates.call_args[0][0])
            assert {m1.pk, m2.pk} == call_ids

    def test_no_active_metrics_skips_stream(self, celery_test_app):
        """No active metrics → stream_metric_updates NOT called; count=0."""
        from api.realtime_dashboard.tasks import broadcast_active_metrics
        with patch(
            'api.realtime_dashboard.services.event_streaming_service.EventStreamingService'
        ) as MockStream:
            result = broadcast_active_metrics.apply()
            assert result.result == {'metric_count': 0}
            MockStream.return_value.stream_metric_updates.assert_not_called()

    def test_exception_triggers_retry(self, celery_test_app):
        """Service exception → task retries."""
        from api.realtime_dashboard.tasks import broadcast_active_metrics
        from celery.exceptions import Retry
        with patch(
            'api.realtime_dashboard.services.event_streaming_service.EventStreamingService'
        ) as MockStream:
            MockStream.return_value.stream_metric_updates.side_effect = RuntimeError('fail')
            from api.realtime_dashboard.tests.fixtures import create_real_time_metric
            create_real_time_metric(status='active')
            with pytest.raises((Retry, RuntimeError)):
                broadcast_active_metrics.apply()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. VIEWS  (74% → 100%)  — DB error + channel layer None/exception paths
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestHealthCheckUnhealthyPaths:
    """views.health_check — missing lines 54-56, 65-66, 76-78."""

    def test_db_error_returns_503(self, api_client):
        """OperationalError on SELECT 1 → status=unhealthy, db=error, HTTP 503."""
        from django.db import OperationalError
        with patch(
            'api.realtime_dashboard.views.connection'
        ) as mock_conn:
            mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = (
                OperationalError('connection refused')
            )
            response = api_client.get(reverse('health-check'))
        assert response.status_code == 503
        assert response.data['status'] == 'unhealthy'
        assert 'error' in response.data['database']

    def test_channel_layer_none_returns_503(self, api_client):
        """get_channel_layer() returning None → channel_layer='not configured', HTTP 503."""
        with patch('channels.layers.get_channel_layer', return_value=None):
            response = api_client.get(reverse('health-check'))
        assert response.status_code == 503
        assert response.data['channel_layer'] == 'not configured'
        assert response.data['status'] == 'unhealthy'

    def test_channel_layer_exception_returns_503(self, api_client):
        """Exception from group_send → channel_layer=error:..., HTTP 503."""
        mock_layer = MagicMock()
        with patch('channels.layers.get_channel_layer', return_value=mock_layer):
            with patch('asgiref.sync.async_to_sync') as mock_a2s:
                mock_a2s.return_value.side_effect = Exception('redis down')
                response = api_client.get(reverse('health-check'))
        assert response.status_code == 503
        assert 'error' in response.data['channel_layer']
        assert response.data['status'] == 'unhealthy'

    def test_both_db_and_channel_layer_down_returns_503(self, api_client):
        """Both failing → single 503 with both error fields."""
        from django.db import OperationalError
        with patch('api.realtime_dashboard.views.connection') as mock_conn:
            mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = (
                OperationalError('db down')
            )
            with patch('channels.layers.get_channel_layer', return_value=None):
                response = api_client.get(reverse('health-check'))
        assert response.status_code == 503
        assert 'error' in response.data['database']
        assert response.data['channel_layer'] == 'not configured'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PERMISSIONS  (78% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsAuthenticatedOrReadOnly:
    """permissions.IsAuthenticatedOrReadOnly — missing lines 16-18."""

    @pytest.fixture
    def perm(self):
        from api.realtime_dashboard.permissions import IsAuthenticatedOrReadOnly
        return IsAuthenticatedOrReadOnly()

    def test_get_allows_unauthenticated(self, perm):
        """Safe methods always return True regardless of auth state."""
        factory = APIRequestFactory()
        for method in ('get', 'head', 'options'):
            request = factory.generic(method.upper(), '/')
            request.user = MagicMock(is_authenticated=False)
            assert perm.has_permission(request, None) is True

    def test_post_requires_auth(self, perm):
        """Unsafe method with unauthenticated user → False."""
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = MagicMock(is_authenticated=False)
        assert perm.has_permission(request, None) is False

    def test_post_allows_authenticated(self, perm):
        """Unsafe method with authenticated user → True."""
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = MagicMock(is_authenticated=True)
        assert perm.has_permission(request, None) is True

    def test_delete_requires_auth(self, perm):
        """DELETE with unauthenticated user → False."""
        factory = APIRequestFactory()
        request = factory.delete('/')
        request.user = MagicMock(is_authenticated=False)
        assert perm.has_permission(request, None) is False


class TestIsAdminOrReadOnly:
    """permissions.IsAdminOrReadOnly — missing line 49 (unauthenticated path)."""

    @pytest.fixture
    def perm(self):
        from api.realtime_dashboard.permissions import IsAdminOrReadOnly
        return IsAdminOrReadOnly()

    def test_unauthenticated_request_denied(self, perm):
        """Line 49: unauthenticated user → False for ANY method."""
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = MagicMock(is_authenticated=False)
        assert perm.has_permission(request, None) is False

    def test_no_user_on_request_denied(self, perm):
        """request.user evaluates to falsy → False."""
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = None
        assert perm.has_permission(request, None) is False

    def test_authenticated_non_staff_get_allowed(self, perm):
        """Authenticated, non-staff GET → True."""
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        assert perm.has_permission(request, None) is True

    def test_authenticated_non_staff_post_denied(self, perm):
        """Authenticated, non-staff POST → False."""
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        assert perm.has_permission(request, None) is False

    def test_staff_post_allowed(self, perm):
        """Staff user POST → True."""
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = MagicMock(is_authenticated=True, is_staff=True)
        assert perm.has_permission(request, None) is True


# ═══════════════════════════════════════════════════════════════════════════════
# 4. APP_SETTINGS  (73% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppSettings:
    """app_settings._AppSettings — missing lines 107, 109, 118-119."""

    @pytest.fixture
    def settings_obj(self):
        from api.realtime_dashboard.app_settings import _AppSettings
        return _AppSettings()

    def test_underscore_name_raises_attribute_error(self, settings_obj):
        """Line 107: names starting with '_' raise AttributeError immediately."""
        with pytest.raises(AttributeError, match='_private'):
            _ = settings_obj._private

    def test_unknown_key_raises_attribute_error(self, settings_obj):
        """Line 109: unknown keys raise AttributeError with hint."""
        with pytest.raises(AttributeError, match='NONEXISTENT_KEY'):
            _ = settings_obj.NONEXISTENT_KEY

    def test_attribute_error_message_lists_valid_keys(self, settings_obj):
        """AttributeError message contains 'Valid keys' to help operators."""
        with pytest.raises(AttributeError, match='Valid keys'):
            _ = settings_obj.TOTALLY_WRONG

    def test_as_dict_returns_all_defaults(self, settings_obj):
        """Lines 118-119: as_dict() returns a dict containing all _DEFAULTS keys."""
        result = settings_obj.as_dict()
        assert isinstance(result, dict)
        assert 'WEBSOCKET_TIMEOUT' in result
        assert 'ENABLE_CACHING' in result
        assert 'DEFAULT_PAGE_SIZE' in result
        assert len(result) == len(settings_obj._DEFAULTS)

    def test_as_dict_reflects_user_overrides(self, settings_obj):
        """as_dict() returns user overrides from REALTIME_DASHBOARD setting."""
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'WEBSOCKET_TIMEOUT': 9999}):
            result = settings_obj.as_dict()
        assert result['WEBSOCKET_TIMEOUT'] == 9999
        # Other keys fall back to defaults
        assert result['DEFAULT_PAGE_SIZE'] == 20

    def test_valid_key_returns_default(self, settings_obj):
        """Known key without user override → _DEFAULTS value."""
        assert settings_obj.WEBSOCKET_TIMEOUT == 3600
        assert settings_obj.DEFAULT_PAGE_SIZE == 20

    def test_valid_key_returns_override(self, settings_obj):
        """Known key with user override in settings → override value."""
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'MAX_PAGE_SIZE': 500}):
            assert settings_obj.MAX_PAGE_SIZE == 500


# ═══════════════════════════════════════════════════════════════════════════════
# 5. EXCEPTIONS  (86% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomExceptionHandler:
    """exceptions.custom_exception_handler — missing lines 91-93, 103."""

    @pytest.fixture
    def mock_context(self):
        return {'request': MagicMock(), 'view': MagicMock()}

    def test_handles_metric_not_found_error(self, mock_context):
        """Lines 91-93: MetricNotFoundError → 404 response with success=False."""
        from api.realtime_dashboard.exceptions import (
            custom_exception_handler, MetricNotFoundError
        )
        exc = MetricNotFoundError('Metric 42 not found')
        response = custom_exception_handler(exc, mock_context)
        assert response is not None
        assert response.status_code == 404
        assert response.data['success'] is False
        assert 'Metric 42 not found' in response.data['error']

    def test_handles_dashboard_engine_error(self, mock_context):
        """DashboardEngineError → 404."""
        from api.realtime_dashboard.exceptions import (
            custom_exception_handler, DashboardEngineError
        )
        exc = DashboardEngineError('render failed')
        response = custom_exception_handler(exc, mock_context)
        assert response is not None
        assert response.status_code == 404

    def test_handles_invalid_widget_data_error(self, mock_context):
        """InvalidWidgetDataError → 400."""
        from api.realtime_dashboard.exceptions import (
            custom_exception_handler, InvalidWidgetDataError
        )
        exc = InvalidWidgetDataError('bad widget data')
        response = custom_exception_handler(exc, mock_context)
        assert response is not None
        assert response.status_code == 400

    def test_handles_websocket_connection_error(self, mock_context):
        """WebSocketConnectionError → 503."""
        from api.realtime_dashboard.exceptions import (
            custom_exception_handler, WebSocketConnectionError
        )
        exc = WebSocketConnectionError('WS failed')
        response = custom_exception_handler(exc, mock_context)
        assert response is not None
        assert response.status_code == 503

    def test_unknown_exception_returns_none(self, mock_context):
        """Line 103: non-app, non-DRF exception → None (Django 500 handler takes over)."""
        from api.realtime_dashboard.exceptions import custom_exception_handler
        exc = TypeError('unexpected type')
        response = custom_exception_handler(exc, mock_context)
        assert response is None

    def test_drf_exception_gets_success_false_envelope(self, mock_context):
        """DRF APIException → success=False envelope (existing handler branch)."""
        from rest_framework.exceptions import NotFound
        from api.realtime_dashboard.exceptions import custom_exception_handler
        exc = NotFound('not found')
        response = custom_exception_handler(exc, mock_context)
        assert response is not None
        assert response.data.get('success') is False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DECORATORS  (86% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRequireWidgetDecorator:
    """decorators.require_widget — missing lines 54-55 (DoesNotExist branch)."""

    def test_missing_widget_pk_returns_404(self, authenticated_api_client):
        """
        require_widget with a non-existent pk → 404 Response with success=False.
        DashboardWidgetViewSet exposes two @require_widget actions: activate and
        deactivate. POSTing to activate with a non-existent pk exercises lines 54-55.
        """
        response = authenticated_api_client.post(
            reverse('dashboardwidget-activate', kwargs={'pk': 999999})
        )
        assert response.status_code == 404
        assert response.data['success'] is False
        assert '999999' in response.data['error']

    def test_missing_widget_deactivate_returns_404(self, authenticated_api_client):
        """deactivate action also uses require_widget — same DoesNotExist path."""
        response = authenticated_api_client.post(
            reverse('dashboardwidget-deactivate', kwargs={'pk': 888888})
        )
        assert response.status_code == 404
        assert response.data['success'] is False


@pytest.mark.django_db
class TestRequireDashboardDecorator:
    """decorators.require_dashboard — missing lines 93-94 (DoesNotExist branch)."""

    def test_missing_dashboard_activate_returns_404(self, authenticated_api_client):
        """
        require_dashboard with non-existent pk → 404 before check_object_permissions
        is even called. This covers the DoesNotExist branch (lines 93-94).
        """
        response = authenticated_api_client.post(
            reverse('userdashboard-activate', kwargs={'pk': 999999})
        )
        assert response.status_code == 404
        assert response.data['success'] is False
        assert '999999' in response.data['error']

    def test_missing_dashboard_deactivate_returns_404(self, authenticated_api_client):
        """deactivate with non-existent pk also exercises require_dashboard 404."""
        response = authenticated_api_client.post(
            reverse('userdashboard-deactivate', kwargs={'pk': 777777})
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 7. WIDGET SERVICE  (86% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetServiceCachingDisabledPaths:
    """widget_service.py — missing lines 39, 45 (ENABLE_CACHING=False branches)."""

    @pytest.fixture
    def service_no_cache(self):
        """WidgetService with caching disabled via settings override."""
        from api.realtime_dashboard.services.widget_service import WidgetService
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': False}):
            # Force app_settings to re-read; since it's a lazy proxy, the
            # override_settings context is enough — no module reload needed.
            yield WidgetService()

    def test_get_cached_returns_none_when_caching_disabled(self, service_no_cache):
        """Line 39: _get_cached() returns None immediately when ENABLE_CACHING=False."""
        from django.test import override_settings
        from api.realtime_dashboard.services.widget_service import WidgetService
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': False}):
            svc = WidgetService()
            result = svc._get_cached(1)
        assert result is None

    def test_set_cached_noop_when_caching_disabled(self):
        """Line 45: _set_cached() returns immediately when ENABLE_CACHING=False."""
        from api.realtime_dashboard.services.widget_service import WidgetService
        from api.realtime_dashboard.tests.fixtures import create_dashboard_widget
        from django.test import override_settings
        widget = create_dashboard_widget(name='NoCacheWidget')
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': False}):
            svc = WidgetService()
            # Should not raise and should not write to cache
            with patch('api.realtime_dashboard.services.base_service.cache') as mock_cache:
                svc._set_cached(widget)
                mock_cache.set.assert_not_called()


@pytest.mark.django_db
class TestWidgetServiceCacheHit:
    """widget_service.py — missing lines 90-91 (cache hit returns cached)."""

    def test_get_widget_returns_cached_on_second_call(self):
        """Lines 90-91: cached instance returned without second DB hit."""
        from api.realtime_dashboard.services.widget_service import WidgetService
        from api.realtime_dashboard.tests.fixtures import create_dashboard_widget
        from django.test import override_settings
        widget = create_dashboard_widget(name='CachedWidget')
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': True}):
            svc = WidgetService()
            svc.get_widget(widget.pk)  # primes the cache; return value unused
            # Cache is now primed; second call should return cached
            with patch(
                'api.realtime_dashboard.services.widget_service.DashboardWidget.objects'
            ) as mock_objects:
                second = svc.get_widget(widget.pk)
                mock_objects.get.assert_not_called()
            assert second is not None


@pytest.mark.django_db
class TestWidgetServiceNotFoundPaths:
    """
    widget_service.py.

    v1.5.0: update_widget()/delete_widget() changed signature from
    (id, ...) to (instance, ...) as part of genuinely wiring them into
    DashboardWidgetViewSet.perform_update/perform_destroy (see
    test_dry_unification.py) — an already-fetched instance can't be
    "not found", so that case moved to the HTTP layer; see
    TestDashboardWidgetViewSet.test_update_widget_not_found and
    test_delete_widget_not_found in test_viewsets.py. get_widget()
    keeps its (id) signature and its not-found test below unchanged.
    """

    @pytest.fixture
    def svc(self):
        from api.realtime_dashboard.services.widget_service import WidgetService
        return WidgetService()

    def test_get_widget_missing_returns_none(self, svc):
        """get_widget() with non-existent ID → None (no exception)."""
        result = svc.get_widget(999999)
        assert result is None

    def test_update_widget_found_updates_and_returns(self, svc):
        """Positive control: update_widget(instance, data) returns the updated widget."""
        from api.realtime_dashboard.tests.fixtures import create_dashboard_widget
        w = create_dashboard_widget(name='Before')
        result = svc.update_widget(w, {'name': 'After'})
        assert result is not None
        assert result.name == 'After'

    def test_delete_widget_found_removes_it(self, svc):
        """Positive control: delete_widget(instance) removes the row."""
        from api.realtime_dashboard.tests.fixtures import create_dashboard_widget
        from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
        w = create_dashboard_widget(name='ToDelete')
        pk = w.pk
        svc.delete_widget(w)
        assert not DashboardWidget.objects.filter(pk=pk).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. MANAGERS  (86-89% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestManagerMissingMethods:
    """Cover all remaining manager method branches."""

    def test_dashboard_layout_by_creator(self):
        """dashboard_layout_manager.py:23 — by_creator() filter."""
        from api.realtime_dashboard.tests.fixtures import create_dashboard_layout
        from api.realtime_dashboard.models.dashboard_layout import DashboardLayout
        create_dashboard_layout(name='Mine', created_by='alice')
        create_dashboard_layout(name='Theirs', created_by='bob')
        result = list(DashboardLayout.objects.by_creator('alice'))
        assert len(result) == 1
        assert result[0].name == 'Mine'

    def test_dashboard_by_status(self):
        """dashboard_manager.py:22 — by_status() filter."""
        from api.realtime_dashboard.tests.fixtures import create_user_dashboard
        from api.realtime_dashboard.models.user_dashboard import UserDashboard
        create_user_dashboard(name='Active', status='active')
        create_user_dashboard(name='Inactive', status='inactive')
        result = list(UserDashboard.objects.by_status('active'))
        assert all(d.status == 'active' for d in result)
        names = [d.name for d in result]
        assert 'Active' in names and 'Inactive' not in names

    def test_websocket_connection_by_status(self):
        """websocket_manager.py:26 — by_status() filter."""
        from api.realtime_dashboard.tests.fixtures import create_websocket_connection
        from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
        create_websocket_connection(connection_id='cs1', status='connected')
        create_websocket_connection(connection_id='cs2', status='disconnected')
        result = list(WebSocketConnection.objects.by_status('disconnected'))
        ids = [c.connection_id for c in result]
        assert 'cs2' in ids and 'cs1' not in ids

    def test_widget_configuration_by_type(self):
        """widget_configuration_manager.py:25 — by_type() filter."""
        from api.realtime_dashboard.tests.fixtures import (
            create_dashboard_widget, create_widget_configuration
        )
        from api.realtime_dashboard.models.widget_configuration import WidgetConfiguration
        w = create_dashboard_widget()
        create_widget_configuration(w, key='k1', config_type='chart')
        create_widget_configuration(w, key='k2', config_type='table')
        result = list(WidgetConfiguration.objects.by_type('chart'))
        assert all(c.config_type == 'chart' for c in result)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 9. PAGINATION  (86% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPagination:
    """pagination.py — missing lines 43-44 (max_page_size property)."""

    def test_max_page_size_reads_from_app_settings(self):
        """max_page_size property (lines 43-44) delegates to app_settings."""
        from api.realtime_dashboard.pagination import StandardResultsSetPagination
        pager = StandardResultsSetPagination()
        assert pager.max_page_size == 100  # default from _DEFAULTS

    def test_max_page_size_respects_override(self):
        """max_page_size reflects REALTIME_DASHBOARD['MAX_PAGE_SIZE'] override."""
        from api.realtime_dashboard.pagination import StandardResultsSetPagination
        from django.test import override_settings
        pager = StandardResultsSetPagination()
        with override_settings(REALTIME_DASHBOARD={'MAX_PAGE_SIZE': 50}):
            assert pager.max_page_size == 50

    def test_page_size_reads_from_app_settings(self):
        """page_size property (lines 37-39) delegates to app_settings."""
        from api.realtime_dashboard.pagination import StandardResultsSetPagination
        pager = StandardResultsSetPagination()
        assert pager.page_size == 20  # default from _DEFAULTS

    def test_get_paginated_response_before_paginate_queryset_raises(self):
        """
        get_paginated_response() called before paginate_queryset() has
        populated self.page raises RuntimeError instead of silently
        exploding on `.page.paginator` (v9 mypy fix — self.page: Optional).
        """
        from api.realtime_dashboard.pagination import StandardResultsSetPagination
        pager = StandardResultsSetPagination()
        with pytest.raises(RuntimeError, match='before paginate_queryset'):
            pager.get_paginated_response([])


# ═══════════════════════════════════════════════════════════════════════════════
# 10. WEBSOCKET MANAGER  (96% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWebSocketManagerChannelLayerNonePaths:
    """websocket_manager.py — missing lines 145 and 192."""

    def test_broadcast_metric_update_returns_false_when_no_layer(self):
        """Line 145: broadcast_metric_update() returns False if channel_layer is None."""
        from api.realtime_dashboard.websocket_manager import WebSocketManager
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        metric = create_real_time_metric(name='NoBroadcast')
        mgr = WebSocketManager()
        with patch(
            'api.realtime_dashboard.websocket_manager.get_channel_layer',
            return_value=None
        ):
            result = mgr.broadcast_metric_update(metric)
        assert result is False

    def test_send_to_connection_returns_true_when_no_layer(self):
        """
        Line 192: _send_to_connection() returns True (safe no-op) when channel_layer is None.
        Callers that only check 'was delivery attempted' are unaffected.
        """
        from api.realtime_dashboard.websocket_manager import WebSocketManager
        mgr = WebSocketManager()
        with patch(
            'api.realtime_dashboard.websocket_manager.get_channel_layer',
            return_value=None
        ):
            result = mgr._send_to_connection('fake_channel', {'msg': 'test'})
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# 11. VIEWSET SMALL GAPS  (97-99% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestViewsetSmallGaps:
    """Cover lines 59 in real_time_metric_viewset, 67 in user_dashboard_viewset,
    39 in websocket_connection_viewset."""

    def test_perform_update_no_value_change_calls_plain_save(
        self, authenticated_api_client
    ):
        """
        real_time_metric_viewset.py:59 — perform_update() else branch:
        when value is missing from validated_data or is identical to current,
        serializer.save() is called WITHOUT setting previous_value.
        """
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        metric = create_real_time_metric(name='Stable', value=50.0, previous_value=None)
        # PATCH without changing value → else branch (line 59)
        response = authenticated_api_client.patch(
            reverse('realtimemetric-detail', kwargs={'pk': metric.pk}),
            {'name': 'Updated Name'},  # no 'value' key
            format='json',
        )
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.name == 'Updated Name'
        # previous_value stays None because value didn't change
        assert metric.previous_value is None

    def test_perform_update_same_value_calls_plain_save(
        self, authenticated_api_client
    ):
        """perform_update() else branch when value == current value."""
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        metric = create_real_time_metric(value=75.0, previous_value=None)
        response = authenticated_api_client.patch(
            reverse('realtimemetric-detail', kwargs={'pk': metric.pk}),
            {'value': 75.0},  # same value → else branch
            format='json',
        )
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.previous_value is None  # not updated

    def test_user_dashboard_staff_get_queryset_returns_all(
        self, authenticated_staff_client, test_user, second_user
    ):
        """
        user_dashboard_viewset.py:67 — staff branch of get_queryset().
        Staff can see ALL users' dashboards, not just their own.
        """
        from api.realtime_dashboard.tests.fixtures import create_user_dashboard
        create_user_dashboard(name='U1Dash', user_id=str(test_user.pk))
        create_user_dashboard(name='U2Dash', user_id=str(second_user.pk))
        response = authenticated_staff_client.get(reverse('userdashboard-list'))
        assert response.status_code == 200
        names = [d['name'] for d in response.data.get('results', response.data)]
        assert 'U1Dash' in names
        assert 'U2Dash' in names

    def test_websocket_connection_staff_get_queryset_returns_all(
        self, authenticated_staff_client, test_user, second_user
    ):
        """
        websocket_connection_viewset.py:39 — staff branch of get_queryset().
        Staff can see all users' connections.
        """
        from api.realtime_dashboard.tests.fixtures import create_websocket_connection
        create_websocket_connection(connection_id='conn_u1', user_id=str(test_user.pk))
        create_websocket_connection(connection_id='conn_u2', user_id=str(second_user.pk))
        response = authenticated_staff_client.get(reverse('websocketconnection-list'))
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data.get('results', response.data)]
        assert 'conn_u1' in ids
        assert 'conn_u2' in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 12. DASHBOARD CONSUMER  (74% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDashboardConsumerMissingPaths:
    """
    dashboard_consumer.py — missing lines 50-55 (ping handler) and 61 (dashboard_update).
    These require async Channels testing via WebsocketCommunicator.
    """

    async def test_receive_ping_sends_pong(self):
        """Lines 51-54: receiving {'type': 'ping'} → immediate {'type': 'pong'} reply."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from django.urls import re_path
        from unittest.mock import AsyncMock, patch
        from api.realtime_dashboard.consumers.dashboard_consumer import DashboardConsumer

        application = URLRouter([
            re_path(r'^ws/dashboard/(?P<dashboard_id>\d+)/$', DashboardConsumer.as_asgi())
        ])
        communicator = WebsocketCommunicator(application, '/ws/dashboard/1/')
        # Inject authenticated user into scope
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        communicator.scope['user'] = mock_user
        communicator.scope['url_route'] = {'kwargs': {'dashboard_id': '1'}}

        with patch.object(DashboardConsumer, 'track_connect', new_callable=AsyncMock):
            with patch.object(DashboardConsumer, 'track_ping', new_callable=AsyncMock) as mock_ping:
                connected, _ = await communicator.connect()
                assert connected
                # Send ping
                await communicator.send_json_to({'type': 'ping'})
                response = await communicator.receive_json_from()
                assert response == {'type': 'pong'}
                mock_ping.assert_called_once()
        await communicator.disconnect()

    async def test_dashboard_update_sends_event_data(self):
        """Line 61: dashboard_update() handler forwards event['data'] to WebSocket."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from django.urls import re_path
        from unittest.mock import AsyncMock, patch
        from api.realtime_dashboard.consumers.dashboard_consumer import DashboardConsumer

        application = URLRouter([
            re_path(r'^ws/dashboard/(?P<dashboard_id>\d+)/$', DashboardConsumer.as_asgi())
        ])
        communicator = WebsocketCommunicator(application, '/ws/dashboard/1/')
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        communicator.scope['user'] = mock_user
        communicator.scope['url_route'] = {'kwargs': {'dashboard_id': '1'}}

        with patch.object(DashboardConsumer, 'track_connect', new_callable=AsyncMock):
            connected, _ = await communicator.connect()
            assert connected
            # Simulate channel layer calling dashboard_update on this consumer
            consumer = DashboardConsumer()
            consumer.send = AsyncMock()
            event_data = {'widget_id': 5, 'value': 99}
            await consumer.dashboard_update({'type': 'dashboard_update', 'data': event_data})
            consumer.send.assert_called_once_with(
                text_data=json.dumps(event_data)
            )
        await communicator.disconnect()

    async def test_receive_non_ping_broadcasts_to_group(self):
        """Lines 55-58: non-ping messages are forwarded to the dashboard group."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from django.urls import re_path
        from unittest.mock import AsyncMock, patch
        from api.realtime_dashboard.consumers.dashboard_consumer import DashboardConsumer

        application = URLRouter([
            re_path(r'^ws/dashboard/(?P<dashboard_id>\d+)/$', DashboardConsumer.as_asgi())
        ])
        communicator = WebsocketCommunicator(application, '/ws/dashboard/1/')
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        communicator.scope['user'] = mock_user
        communicator.scope['url_route'] = {'kwargs': {'dashboard_id': '1'}}

        with patch.object(DashboardConsumer, 'track_connect', new_callable=AsyncMock):
            connected, _ = await communicator.connect()
            assert connected
            # Non-ping payload → group_send to 'dashboard_1' group.
            # The sender IS in that group so they receive the broadcast back.
            await communicator.send_json_to({'type': 'refresh', 'widget_id': 3})
            # The group_send triggers dashboard_update() which sends event['data']
            # back to every group member (including this sender).
            response = await communicator.receive_json_from()
            assert response == {'type': 'refresh', 'widget_id': 3}
        await communicator.disconnect()


# ═══════════════════════════════════════════════════════════════════════════════
# 13. WEBSOCKET MANAGER SERVICE  (97% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWebSocketManagerServiceBroadcastToConnection:
    """websocket_manager_service.py:118 — broadcast_to_connection delegates to manager."""

    def test_broadcast_to_connection_delegates(self):
        """Line 118: service.broadcast_to_connection → manager._send_to_connection."""
        from api.realtime_dashboard.services.websocket_manager_service import WebSocketManagerService
        svc = WebSocketManagerService()
        with patch.object(svc.manager, '_send_to_connection', return_value=True) as mock_send:
            result = svc.broadcast_to_connection('chan_123', {'msg': 'hello'})
            mock_send.assert_called_once_with('chan_123', {'msg': 'hello'})
            assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# 14. METRIC SERVICE CACHE PATHS  (95% → 100%)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMetricServiceCachePaths:
    """real_time_metric_service.py — missing lines 44, 49, 93."""

    def test_get_cached_returns_none_when_caching_disabled(self):
        """Line 44: _get_cached() early-return when ENABLE_CACHING=False."""
        from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': False}):
            svc = RealTimeMetricService()
            result = svc._get_cached(999)
        assert result is None

    def test_set_cached_noop_when_caching_disabled(self):
        """Line 49: _set_cached() early-return when ENABLE_CACHING=False."""
        from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        from django.test import override_settings
        metric = create_real_time_metric(name='NoCacheMetric')
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': False}):
            svc = RealTimeMetricService()
            with patch('api.realtime_dashboard.services.base_service.cache') as mock_cache:
                svc._set_cached(metric)
                mock_cache.set.assert_not_called()

    def test_check_thresholds_delegates_to_util(self):
        """Line 93: check_thresholds() delegates to utils.check_metric_thresholds."""
        from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
        from api.realtime_dashboard.tests.fixtures import create_real_time_metric
        metric = create_real_time_metric(
            value=95.0, warning_threshold=80.0, critical_threshold=90.0
        )
        svc = RealTimeMetricService()
        with patch(
            'api.realtime_dashboard.services.real_time_metric_service.check_metric_thresholds',
            return_value='critical'
        ) as mock_util:
            result = svc.check_thresholds(metric)
            mock_util.assert_called_once_with(
                value=95.0, warning=80.0, critical=90.0
            )
            assert result == 'critical'
