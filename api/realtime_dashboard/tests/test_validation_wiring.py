"""
Tests for validation wiring added in v1.3.0.

Covers:
  VAL-1  validate_positive_integer wired to DashboardWidget.refresh_interval
  VAL-2  validate_name_no_special_chars wired to DashboardWidget.name
  VAL-3  validate_name_no_special_chars wired to DashboardLayout.name
  VAL-4  DashboardLayout column/row bounds validation
  VAL-5  DashboardLayout metadata and tags validation
  VAL-6  WidgetConfigurationViewSet.by_widget uses @require_query_param (DRY)
  VAL-7  WebSocketConnection.disconnected_at set on disconnect
  VAL-8  constants.py re-exports model TextChoices (no duplication)
  VAL-9  export_metrics management command
  VAL-10 Retry-After header present on 429 (throttled) responses
  VAL-11 DashboardWidget perform_update cache invalidation
  VAL-12 WebSocketConnection.disconnected_at set on service-layer ("API") disconnect
"""
import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch

from api.realtime_dashboard.tests.fixtures import (
    create_dashboard_widget,
    create_websocket_connection,
    create_widget_configuration,
    create_real_time_metric,
)
from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
from api.realtime_dashboard.services.widget_service import WidgetService
from api.realtime_dashboard.services.websocket_manager_service import WebSocketManagerService
from api.realtime_dashboard.throttling import MetricUpdateThrottle


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-1: validate_positive_integer on refresh_interval
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRefreshIntervalValidation:

    def test_negative_refresh_interval_returns_400(self, authenticated_api_client):
        """refresh_interval=-1 must be rejected at serializer level."""
        data = {'name': 'W', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': -1, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 400
        assert 'refresh_interval' in (response.data.get('error') or response.data)

    def test_zero_refresh_interval_returns_400(self, authenticated_api_client):
        """refresh_interval=0 must be rejected (positive means > 0)."""
        data = {'name': 'W', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': 0, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_valid_refresh_interval_accepted(self, authenticated_api_client):
        """refresh_interval=30 must be accepted."""
        data = {'name': 'ValidW', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': 30, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-2: validate_name_no_special_chars on DashboardWidget.name
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetNameValidation:

    def test_script_injection_in_name_returns_400(self, authenticated_api_client):
        """Widget names with <script> tags must be rejected."""
        data = {'name': '<script>alert(1)</script>', 'widget_type': 'chart',
                'status': 'active', 'configuration': {},
                'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 400
        assert 'name' in (response.data.get('error') or response.data)

    def test_sql_injection_in_name_returns_400(self, authenticated_api_client):
        """Widget names with SQL injection chars must be rejected."""
        data = {'name': "'; DROP TABLE widgets; --", 'widget_type': 'chart',
                'status': 'active', 'configuration': {},
                'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_normal_name_accepted(self, authenticated_api_client):
        """Alphanumeric names with spaces, hyphens, underscores are valid."""
        data = {'name': 'Revenue Chart 2025', 'widget_type': 'chart',
                'status': 'active', 'configuration': {},
                'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(
            reverse('dashboardwidget-list'), data, format='json'
        )
        assert response.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-3 + VAL-4 + VAL-5: DashboardLayout full validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardLayoutValidation:

    def test_script_in_layout_name_returns_400(self, authenticated_staff_client):
        """Layout name with special chars → 400."""
        data = {'name': '<XSS>', 'layout_type': 'grid', 'columns': 12, 'rows': 12}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_negative_columns_returns_400(self, authenticated_staff_client):
        """columns < 1 → 400."""
        data = {'name': 'ValidName', 'layout_type': 'grid', 'columns': -1, 'rows': 12}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 400
        assert 'columns' in str(response.data.get('error', response.data))

    def test_columns_exceeding_max_returns_400(self, authenticated_staff_client):
        """columns > 24 → 400."""
        data = {'name': 'ValidName', 'layout_type': 'grid', 'columns': 25, 'rows': 12}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_negative_rows_returns_400(self, authenticated_staff_client):
        """rows < 1 → 400."""
        data = {'name': 'ValidName', 'layout_type': 'grid', 'columns': 12, 'rows': 0}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_rows_exceeding_max_returns_400(self, authenticated_staff_client):
        """rows > 100 → 400."""
        data = {'name': 'ValidName', 'layout_type': 'grid', 'columns': 12, 'rows': 101}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 400

    def test_valid_layout_accepted(self, authenticated_staff_client):
        """Valid name, valid columns/rows → 201."""
        data = {'name': 'Standard Grid', 'layout_type': 'grid', 'columns': 12, 'rows': 12}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-6: WidgetConfigurationViewSet.by_widget — DRY @require_query_param
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetConfigByWidgetDRY:

    def test_missing_widget_id_returns_400(self, authenticated_api_client):
        """GET /api/configurations/by_widget/ without widget_id → 400."""
        response = authenticated_api_client.get(reverse('widgetconfiguration-by-widget'))
        assert response.status_code == 400
        # Error message should mention the missing param name
        assert 'widget_id' in response.data.get('error', '')

    def test_with_widget_id_returns_200(self, authenticated_api_client):
        widget = create_dashboard_widget()
        create_widget_configuration(widget, key='k1')
        url = reverse('widgetconfiguration-by-widget') + f'?widget_id={widget.pk}'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        keys = [c['key'] for c in response.data]
        assert 'k1' in keys


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-7: WebSocketConnection.disconnected_at set on disconnect
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDisconnectedAtTracking:

    async def test_disconnected_at_set_on_disconnect(self):
        """track_disconnect() must set disconnected_at to timezone.now()."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from django.urls import re_path
        from asgiref.sync import sync_to_async
        from api.realtime_dashboard.consumers.dashboard_consumer import DashboardConsumer
        from api.realtime_dashboard.models.websocket_connection import WebSocketConnection

        application = URLRouter([
            re_path(r'^ws/dashboard/(?P<dashboard_id>\d+)/$', DashboardConsumer.as_asgi())
        ])
        communicator = WebsocketCommunicator(application, '/ws/dashboard/1/')
        from unittest.mock import MagicMock
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.pk = 'test-disconnect-user'
        communicator.scope['user'] = mock_user
        communicator.scope['url_route'] = {'kwargs': {'dashboard_id': '1'}}

        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

        # Give async tasks a moment to complete
        import asyncio
        await asyncio.sleep(0.1)

        conn = await sync_to_async(
            WebSocketConnection.objects.filter(user_id='test-disconnect-user').first
        )()
        if conn:
            assert conn.disconnected_at is not None, (
                "disconnected_at must be set when track_disconnect() runs"
            )
            assert conn.status == WebSocketConnection.ConnectionStatus.DISCONNECTED


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-8: constants.py re-exports (no duplication)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstantsReexport:

    def test_widget_type_from_constants_equals_model(self):
        from api.realtime_dashboard.constants import WidgetType
        from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
        assert WidgetType is DashboardWidget.WidgetType

    def test_metric_type_from_constants_equals_model(self):
        from api.realtime_dashboard.constants import MetricType
        from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
        assert MetricType is RealTimeMetric.MetricType

    def test_layout_type_from_constants_equals_model(self):
        from api.realtime_dashboard.constants import LayoutType
        from api.realtime_dashboard.models.dashboard_layout import DashboardLayout
        assert LayoutType is DashboardLayout.LayoutType

    def test_connection_status_from_constants_equals_model(self):
        from api.realtime_dashboard.constants import ConnectionStatus
        from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
        assert ConnectionStatus is WebSocketConnection.ConnectionStatus

    def test_no_duplicate_definitions(self):
        """constants.py must NOT define its own Enum classes."""
        import api.realtime_dashboard.constants as mod
        import enum
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and issubclass(obj, enum.Enum):
                # Should be a Django TextChoices re-export, not a standalone Enum
                assert hasattr(obj, 'choices'), (
                    f"{name} in constants.py is a standalone Enum — "
                    f"must be a Django TextChoices re-export from a model."
                )


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-9: export_metrics management command
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestExportMetricsCommand:

    def _run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        err = StringIO()
        call_command('export_metrics', *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_csv_export_has_headers(self):
        create_real_time_metric = __import__(
            'api.realtime_dashboard.tests.fixtures', fromlist=['create_real_time_metric']
        ).create_real_time_metric
        create_real_time_metric(name='ExportM', status='active', value=55.0)
        out, _ = self._run_command('--format', 'csv')
        assert 'name' in out
        assert 'ExportM' in out

    def test_json_export_is_parseable(self):
        import json as json_mod
        create_real_time_metric = __import__(
            'api.realtime_dashboard.tests.fixtures', fromlist=['create_real_time_metric']
        ).create_real_time_metric
        create_real_time_metric(name='JSONExport', status='active', value=10.0)
        out, _ = self._run_command('--format', 'json')
        parsed = json_mod.loads(out)
        assert isinstance(parsed, list)
        names = [m['name'] for m in parsed]
        assert 'JSONExport' in names

    def test_export_filters_by_status(self):
        create_real_time_metric = __import__(
            'api.realtime_dashboard.tests.fixtures', fromlist=['create_real_time_metric']
        ).create_real_time_metric
        create_real_time_metric(name='ActiveM', status='active')
        create_real_time_metric(name='InactiveM', status='inactive')
        # Default: active only
        out, _ = self._run_command('--format', 'csv')
        assert 'ActiveM' in out
        assert 'InactiveM' not in out

    def test_export_all_status(self):
        create_real_time_metric = __import__(
            'api.realtime_dashboard.tests.fixtures', fromlist=['create_real_time_metric']
        ).create_real_time_metric
        create_real_time_metric(name='ActiveM2', status='active')
        create_real_time_metric(name='InactiveM2', status='inactive')
        out, _ = self._run_command('--format', 'csv', '--status', 'all')
        assert 'ActiveM2' in out
        assert 'InactiveM2' in out

    def test_export_specific_ids(self):
        create_real_time_metric = __import__(
            'api.realtime_dashboard.tests.fixtures', fromlist=['create_real_time_metric']
        ).create_real_time_metric
        m1 = create_real_time_metric(name='M_ONE', status='active')
        create_real_time_metric(name='M_TWO', status='active')
        out, _ = self._run_command('--format', 'csv', '--ids', str(m1.pk))
        assert 'M_ONE' in out
        assert 'M_TWO' not in out


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-10: Retry-After header present on 429 (throttled) responses
# ═══════════════════════════════════════════════════════════════════════════════
#
# throttling.py's module docstring has claimed since v1.1.0 that DRF's
# Throttled exception carries a Retry-After header through
# custom_exception_handler "automatically... Verified via
# TestThrottleRetryAfterHeader" — but that test class never actually
# existed until now. This closes the gap.
#
# TEST DESIGN NOTE: tests/settings.py sets every DEFAULT_THROTTLE_RATES
# entry to a very high value (e.g. 'metric_update': '1000/min') so unrelated
# tests never get throttled. DRF's SimpleRateThrottle.THROTTLE_RATES is a
# class attribute bound to api_settings.DEFAULT_THROTTLE_RATES *once*, at
# the time rest_framework.throttling is first imported — django.test.
# override_settings does NOT retroactively change an already-bound class
# attribute (verified empirically: a throttle instantiated inside
# override_settings(REST_FRAMEWORK=...) still resolves the pre-override
# rate). The reliable, isolated way to force a throttle limit in a single
# test is to patch the `rate` attribute directly on the throttle class —
# SimpleRateThrottle.__init__ only calls get_rate() when `rate` is falsy,
# so a patched `rate` short-circuits the stale THROTTLE_RATES lookup
# entirely and is automatically restored when the `with` block exits.
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestThrottleRetryAfterHeader:

    def test_retry_after_header_present_on_429(self, authenticated_api_client):
        """Second request within the window must 429 with a Retry-After header."""
        metric = create_real_time_metric(name='ThrottledMetric', status='active')
        url = reverse('realtimemetric-activate', kwargs={'pk': metric.pk})

        with patch.object(MetricUpdateThrottle, 'rate', '1/min', create=True):
            first = authenticated_api_client.post(url)
            assert first.status_code == 200

            second = authenticated_api_client.post(url)
            assert second.status_code == 429
            assert 'Retry-After' in second.headers
            # Must be a positive, numeric wait hint - not just present-but-empty.
            assert float(second.headers['Retry-After']) > 0

    def test_throttled_response_still_uses_standard_error_envelope(self, authenticated_api_client):
        """custom_exception_handler must still wrap the 429 in {success, error, status_code}."""
        metric = create_real_time_metric(name='ThrottledMetric2', status='active')
        url = reverse('realtimemetric-activate', kwargs={'pk': metric.pk})

        with patch.object(MetricUpdateThrottle, 'rate', '1/min', create=True):
            authenticated_api_client.post(url)
            response = authenticated_api_client.post(url)

        assert response.status_code == 429
        assert response.data['success'] is False
        assert response.data['status_code'] == 429


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-11: DashboardWidget perform_update cache invalidation
# ═══════════════════════════════════════════════════════════════════════════════
#
# test_dry_wiring.py::TestWidgetServiceWiredToViewset already covers CREATE
# (cache primed) and DELETE (cache purged) via the API, but no test exercised
# UPDATE. perform_update() is the one lifecycle hook that both invalidates
# AND re-primes in the same call (viewsets/dashboard_widget_viewset.py):
#     WidgetService()._invalidate(serializer.instance.pk)
#     serializer.save()
#     WidgetService()._set_cached(serializer.instance)
# Two angles are covered below: the observable end-state (stale value is
# gone, fresh value is cached), and the wiring itself via a spy — the
# second guards against a regression where _invalidate() is removed but
# _set_cached() still runs, which would leave the correct end-state and
# silently pass the first test alone.
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetUpdateCacheInvalidation:

    def test_update_widget_via_api_replaces_stale_cache_with_fresh_value(
        self, authenticated_api_client
    ):
        """PATCH /api/widgets/<id>/ must leave the cache holding the NEW data, not the old."""
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': True}):
            widget = create_dashboard_widget(name='StaleName', refresh_interval=60)
            svc = WidgetService()
            svc._set_cached(widget)
            cache_key = svc._cache_key(widget.pk)
            assert cache.get(cache_key).name == 'StaleName'

            response = authenticated_api_client.patch(
                reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}),
                {'name': 'FreshName'}, format='json',
            )
            assert response.status_code == 200

            refreshed = cache.get(cache_key)
            assert refreshed is not None
            assert refreshed.name == 'FreshName'

    def test_perform_update_calls_invalidate_before_recaching(self, authenticated_api_client):
        """
        Regression guard: perform_update() must explicitly call
        WidgetService._invalidate(pk). Without this spy, removing that
        call would still pass the end-state test above because
        _set_cached() unconditionally overwrites the cache regardless of
        whether invalidation ran first.
        """
        widget = create_dashboard_widget(name='SpyWidget')

        with patch.object(WidgetService, '_invalidate') as mock_invalidate, \
                patch.object(WidgetService, '_set_cached') as mock_set_cached:
            response = authenticated_api_client.patch(
                reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}),
                {'name': 'SpyWidgetUpdated'}, format='json',
            )

        assert response.status_code == 200
        mock_invalidate.assert_called_once_with(widget.pk)
        mock_set_cached.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# VAL-12: WebSocketConnection.disconnected_at set on service-layer ("API") disconnect
# ═══════════════════════════════════════════════════════════════════════════════
#
# TestDisconnectedAtTracking (VAL-7, above) covers the *consumer* code path:
# TrackedConsumerMixin.track_disconnect() runs inside the ASGI consumer when
# a socket closes, and writes disconnected_at via its own direct
# `.filter(...).update(...)` call.
#
# WebSocketManagerService.remove_connection() -> WebSocketManager.
# remove_connection() is a COMPLETELY SEPARATE code path — the
# service/manager layer used for server-initiated disconnects (management
# commands, admin/API-triggered teardown, WebSocketManagerService callers
# generally). It has its own independent `.save()` call that must also set
# disconnected_at. A regression in one path is invisible to a test of the
# other, so both need direct coverage.
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestServiceLayerDisconnectSetsDisconnectedAt:

    def test_remove_connection_sets_disconnected_at(self):
        """WebSocketManagerService.remove_connection() must set disconnected_at + status."""
        connection = create_websocket_connection(
            connection_id='api-disconnect-conn',
            status=WebSocketConnection.ConnectionStatus.CONNECTED,
        )
        assert connection.disconnected_at is None

        result = WebSocketManagerService().remove_connection('api-disconnect-conn')

        assert result is True
        connection.refresh_from_db()
        assert connection.disconnected_at is not None
        assert connection.status == WebSocketConnection.ConnectionStatus.DISCONNECTED

    def test_remove_connection_returns_false_for_unknown_connection_id(self):
        """Disconnecting a connection_id with no matching row is a no-op, not an error."""
        result = WebSocketManagerService().remove_connection('does-not-exist-anywhere')
        assert result is False
