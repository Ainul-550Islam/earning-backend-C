"""
Tests added by the v1.5.0 360-degree production-readiness audit.

Context: an empirical trace of every call site (not a read of docstrings —
several docstrings in this codebase claimed "WIRED" for methods that had
zero real callers) found that RealTimeMetricService, WidgetService, and
DashboardService each had CRUD methods the corresponding viewset never
called — the viewset reimplemented the same logic inline instead. The
same pattern showed up one layer down: WebSocketManagerService.
record_ping() existed specifically so consumers wouldn't need to touch
WebSocketConnection directly, but nothing called it — base_consumer.py's
track_ping() did its own inline ORM write instead.

This file is organised by what each class proves:

  TestMetricServiceDelegation       — perform_create/update/destroy on
  TestWidgetServiceDelegation         RealTimeMetricViewSet/
                                       DashboardWidgetViewSet genuinely
                                       call the service (spy-based: the
                                       service method is patched and
                                       asserted called, not just
                                       trusted-by-outcome).

  TestDashboardServiceDelegation    — same for UserDashboardViewSet.
                                       Also covers the latent bug found
                                       while tracing this: the old
                                       create_dashboard() did
                                       `layout_id=data.get('layout')`,
                                       but validated_data['layout'] is a
                                       DashboardLayout *instance*
                                       (PrimaryKeyRelatedField), not a
                                       raw id — a bug that could only
                                       have fired once the method was
                                       wired up, which it now is.

  TestDashboardLayoutByCreator      — new endpoint: DashboardLayout.
                                       created_by has had a DB index
                                       since the first migration but no
                                       endpoint ever queried by it.

  TestRecordPingWiring              — track_ping() now delegates to
                                       WebSocketManagerService.
                                       record_ping() instead of a
                                       duplicate inline ORM write.

  TestConsumerCoverageGaps          — the throttled-connect path and the
                                       cache.incr() ValueError fallback
                                       in base_consumer.py, neither of
                                       which any existing test triggered.

  TestDisconnectTrackingFailureIsLogged — the bandit B110 fix: a DB
                                       failure during disconnect tracking
                                       is now logged instead of silently
                                       swallowed.

  TestSanitizeToEmptyValidation     — dashboard name that sanitises to
                                       an empty string (all characters
                                       stripped) is rejected with a
                                       field-specific error rather than
                                       silently saving an empty name.

  TestDashboardEngineErrorBranches  — the three call sites that catch
                                       DashboardEngineError from a
                                       viewset action
                                       (DashboardWidgetViewSet.data,
                                       UserDashboardViewSet.widget_ids,
                                       UserDashboardViewSet.stats) had
                                       never actually seen that exception
                                       fire in a test.
"""
from unittest.mock import patch, MagicMock

import pytest
from django.core.cache import cache
from django.urls import reverse

from api.realtime_dashboard.exceptions import DashboardEngineError
from api.realtime_dashboard.models.dashboard_layout import DashboardLayout
from api.realtime_dashboard.models.user_dashboard import UserDashboard
from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
from api.realtime_dashboard.services.widget_service import WidgetService
from api.realtime_dashboard.services.dashboard_service import DashboardService
from api.realtime_dashboard.services.websocket_manager_service import WebSocketManagerService
from .fixtures import (
    create_real_time_metric,
    create_dashboard_widget,
    create_dashboard_layout,
    create_user_dashboard,
    create_websocket_connection,
)


@pytest.fixture
def ws_user(db):
    """Same as test_consumers.py's ws_user — not in conftest.py, so redefined locally."""
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(
        username='dryunif_wsuser', email='dryunif_ws@example.com', password='pass'
    )


# ─── CRUD delegation: RealTimeMetricViewSet -> RealTimeMetricService ─────────

@pytest.mark.django_db
class TestMetricServiceDelegation:
    """
    Proves perform_create/update/destroy genuinely call the service rather
    than reimplementing its logic inline (the pre-audit state) — by
    patching the service method and asserting it was called, not just by
    checking the HTTP outcome (a duplicate inline implementation could
    produce the same outcome and still be the DRY violation the audit
    flagged).
    """

    def test_perform_create_calls_create_metric(self, authenticated_api_client):
        with patch.object(RealTimeMetricService, 'create_metric', wraps=RealTimeMetricService().create_metric) as spy:
            response = authenticated_api_client.post(
                reverse('realtimemetric-list'),
                {'name': 'Spy Metric', 'metric_type': 'gauge', 'status': 'active', 'value': 1.0},
                format='json',
            )
        assert response.status_code == 201
        spy.assert_called_once()

    def test_perform_update_calls_update_metric(self, authenticated_api_client):
        metric = create_real_time_metric(value=1.0)
        with patch.object(RealTimeMetricService, 'update_metric', wraps=RealTimeMetricService().update_metric) as spy:
            response = authenticated_api_client.patch(
                reverse('realtimemetric-detail', kwargs={'pk': metric.pk}), {'value': 2.0}, format='json')
        assert response.status_code == 200
        spy.assert_called_once()
        called_instance = spy.call_args[0][0]
        assert called_instance.pk == metric.pk

    def test_perform_destroy_calls_delete_metric(self, authenticated_api_client):
        metric = create_real_time_metric()
        with patch.object(RealTimeMetricService, 'delete_metric', wraps=RealTimeMetricService().delete_metric) as spy:
            response = authenticated_api_client.delete(reverse('realtimemetric-detail', kwargs={'pk': metric.pk}))
        assert response.status_code == 204
        spy.assert_called_once()


# ─── CRUD delegation: DashboardWidgetViewSet -> WidgetService ────────────────

@pytest.mark.django_db
class TestWidgetServiceDelegation:

    def test_perform_create_calls_create_widget(self, authenticated_api_client):
        with patch.object(WidgetService, 'create_widget', wraps=WidgetService().create_widget) as spy:
            response = authenticated_api_client.post(
                reverse('dashboardwidget-list'),
                {'name': 'Spy Widget', 'widget_type': 'chart', 'status': 'active',
                 'configuration': {}, 'refresh_interval': 60, 'width': 6, 'height': 4},
                format='json',
            )
        assert response.status_code == 201
        spy.assert_called_once()

    def test_perform_update_calls_update_widget(self, authenticated_api_client):
        widget = create_dashboard_widget(name='Before')
        with patch.object(WidgetService, 'update_widget', wraps=WidgetService().update_widget) as spy:
            response = authenticated_api_client.patch(
                reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}), {'name': 'After'}, format='json')
        assert response.status_code == 200
        spy.assert_called_once()

    def test_perform_destroy_calls_delete_widget(self, authenticated_api_client):
        widget = create_dashboard_widget()
        with patch.object(WidgetService, 'delete_widget', wraps=WidgetService().delete_widget) as spy:
            response = authenticated_api_client.delete(reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}))
        assert response.status_code == 204
        spy.assert_called_once()


# ─── CRUD delegation: UserDashboardViewSet -> DashboardService ──────────────

@pytest.mark.django_db
class TestDashboardServiceDelegation:

    def test_perform_create_calls_create_dashboard(self, authenticated_api_client):
        with patch.object(DashboardService, 'create_dashboard', wraps=DashboardService().create_dashboard) as spy:
            response = authenticated_api_client.post(
                reverse('userdashboard-list'), {'name': 'Spy Dashboard', 'status': 'active'}, format='json')
        assert response.status_code == 201
        spy.assert_called_once()

    def test_perform_create_ignores_client_supplied_user_id(self, authenticated_api_client, test_user):
        """user_id always comes from request.user — never from client input."""
        response = authenticated_api_client.post(
            reverse('userdashboard-list'),
            {'name': 'Not Mine', 'status': 'active', 'user_id': 'someone-else'},
            format='json',
        )
        assert response.status_code == 201
        dashboard = UserDashboard.objects.get(pk=response.data['id'])
        assert dashboard.user_id == str(test_user.pk)
        assert dashboard.user_id != 'someone-else'

    def test_create_dashboard_with_layout_assigns_it_correctly(self, authenticated_api_client):
        """
        Regression test for the bug found while wiring create_dashboard():
        the old implementation did `layout_id=data.get('layout')`, but
        validated_data['layout'] is a DashboardLayout *instance* (DRF
        auto-generates a PrimaryKeyRelatedField for the FK), not a raw
        id — assigning an instance to a `_id`-suffixed kwarg is wrong.
        No prior test exercised "create a dashboard with a layout" end
        to end, which is exactly why this stayed hidden until the
        method was actually wired up and traced.
        """
        layout = create_dashboard_layout(name='Grid Layout')
        response = authenticated_api_client.post(
            reverse('userdashboard-list'),
            {'name': 'Dashboard With Layout', 'status': 'active', 'layout': layout.pk},
            format='json',
        )
        assert response.status_code == 201, response.data
        dashboard = UserDashboard.objects.get(pk=response.data['id'])
        assert dashboard.layout_id == layout.pk

    def test_create_dashboard_service_rejects_instance_vs_id_mismatch_directly(self):
        """
        Unit-level pin for the same bug: calling the service exactly as
        the viewset now does (validated_data with an actual model
        instance under 'layout') must work without raising.
        """
        layout = create_dashboard_layout(name='Direct Layout')
        dashboard = DashboardService().create_dashboard({
            'name': 'Direct', 'status': 'active', 'user_id': 'u1', 'layout': layout,
        })
        assert dashboard.layout_id == layout.pk


# ─── New endpoint: DashboardLayoutViewSet.by_creator ─────────────────────────

@pytest.mark.django_db
class TestDashboardLayoutByCreator:
    """
    DashboardLayout.created_by has had a dedicated DB index
    (dl_created_by_idx) since the initial migration, and
    DashboardLayoutManager.by_creator() existed, but no endpoint ever
    queried by it — found while checking why a DB index existed with no
    corresponding query pattern anywhere in the API surface.
    """

    def test_by_creator_action(self, authenticated_api_client):
        create_dashboard_layout(name='Mine', created_by='alice')
        create_dashboard_layout(name='Not Mine', created_by='bob')
        response = authenticated_api_client.get(reverse('dashboardlayout-by-creator'), {'created_by': 'alice'})
        assert response.status_code == 200
        names = [item['name'] for item in response.data]
        assert 'Mine' in names
        assert 'Not Mine' not in names

    def test_by_creator_missing_param(self, authenticated_api_client):
        response = authenticated_api_client.get(reverse('dashboardlayout-by-creator'))
        assert response.status_code == 400

    def test_manager_by_creator_direct(self):
        """Direct manager-method test — this line had 0 callers anywhere before v1.5.0."""
        create_dashboard_layout(name='X', created_by='carol')
        qs = DashboardLayout.objects.by_creator('carol')
        assert qs.filter(name='X').exists()


# ─── record_ping wiring: consumer -> WebSocketManagerService ────────────────

@pytest.mark.django_db
class TestRecordPingWiring:

    def test_websocket_manager_service_record_ping_updates_last_ping(self):
        """
        Direct unit test of the method the OWNERSHIP FIX wires
        track_ping() to — previously had 0 callers anywhere in the
        codebase despite its own docstring warning that
        cleanup_old_connections() depends on something calling it.
        """
        import time
        conn = create_websocket_connection(connection_id='chan-1')
        original_ping = conn.last_ping
        time.sleep(0.01)

        result = WebSocketManagerService().record_ping('chan-1')

        assert result is True
        conn.refresh_from_db()
        assert conn.last_ping > original_ping

    def test_record_ping_unknown_connection_returns_false(self):
        result = WebSocketManagerService().record_ping('does-not-exist')
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_consumer_track_ping_delegates_to_service(self):
        """
        track_ping() must call WebSocketManagerService.record_ping()
        rather than writing to WebSocketConnection directly — the
        OWNERSHIP FIX this audit pass made. Exercised directly against
        the mixin rather than through a full WebSocket handshake to keep
        the test focused on the delegation itself.
        """
        from api.realtime_dashboard.consumers.base_consumer import TrackedConsumerMixin

        mixin = TrackedConsumerMixin()
        mixin.channel_name = 'test-channel-xyz'

        with patch(
            'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
        ) as MockSvc:
            MockSvc.return_value.record_ping = MagicMock(return_value=True)
            await mixin.track_ping()

        MockSvc.return_value.record_ping.assert_called_once_with('test-channel-xyz')


# ─── base_consumer.py coverage gaps ──────────────────────────────────────────

@pytest.mark.django_db
class TestConsumerCoverageGaps:
    """
    _check_and_increment_rate()'s ValueError fallback and track_connect()'s
    throttled-close path — neither triggered by any test prior to v1.5.0
    because doing so through a real WebSocket handshake requires either a
    genuine cache race (the ValueError case) or actually exceeding the
    connection-rate limit (10/user by default). Both are exercised more
    directly here instead of trying to engineer either scenario through
    real timing/volume.
    """

    def test_check_and_increment_rate_falls_back_on_value_error(self):
        from api.realtime_dashboard.consumers.base_consumer import TrackedConsumerMixin

        mixin = TrackedConsumerMixin()
        mixin.scope = {'user': None, 'headers': [], 'client': ('127.0.0.1', 0)}

        with patch('api.realtime_dashboard.consumers.base_consumer.cache') as mock_cache:
            mock_cache.add.return_value = True
            mock_cache.incr.side_effect = ValueError('key expired between add and incr')
            allowed = mixin._check_and_increment_rate(window_seconds=60, max_rate=10)

        assert allowed is True  # falls back to count=1, which is <= max_rate

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_track_connect_closes_when_throttled(self, ws_user):
        """
        Pre-seeds the rate-limit cache counter at the limit so the very
        first connect attempt in this test trips the throttle, rather
        than needing MAX_CONNECTIONS_PER_USER+1 real connections.
        """
        from api.realtime_dashboard.consumers.base_consumer import TrackedConsumerMixin
        from api.realtime_dashboard.app_settings import app_settings

        key = f'ws_connect_rate:user:{ws_user.pk}'
        cache.set(key, app_settings.MAX_CONNECTIONS_PER_USER)

        mixin = TrackedConsumerMixin()
        mixin.scope = {'user': ws_user}
        mixin.close = MagicMock(return_value=_async_none())

        allowed = await mixin.track_connect()

        assert allowed is False
        mixin.close.assert_called_once()
        _, kwargs = mixin.close.call_args
        assert kwargs.get('code') == 4029  # WS_CLOSE_THROTTLED

        cache.delete(key)


def _async_none():
    """Small helper: an already-resolved coroutine returning None, for mocking `await self.close(...)`."""
    async def _coro():
        return None
    return _coro()


# ─── track_disconnect: failure is logged, not swallowed ─────────────────────

@pytest.mark.django_db
class TestDisconnectTrackingFailureIsLogged:
    """
    bandit B110 fix: track_disconnect()'s `except Exception: pass` became
    `except Exception: logger.exception(...)`. A silent `pass` and a
    logged-then-continued exception are indistinguishable from the
    caller's point of view (disconnect must never raise either way), so
    this is verified by asserting the log call rather than an outcome.
    """

    @pytest.mark.asyncio
    async def test_disconnect_tracking_failure_is_logged_not_silent(self):
        from api.realtime_dashboard.consumers.base_consumer import TrackedConsumerMixin

        mixin = TrackedConsumerMixin()
        mixin.channel_name = 'chan-fail'

        with patch(
            'api.realtime_dashboard.models.websocket_connection.WebSocketConnection.objects.filter'
        ) as mock_filter, patch(
            'api.realtime_dashboard.consumers.base_consumer.logger'
        ) as mock_logger:
            mock_filter.side_effect = RuntimeError('DB unavailable')
            # track_disconnect() also logs a normal "WebSocket disconnected"
            # info line after the try/except — that call is unaffected.
            await mixin.track_disconnect(close_code=1000)

        mock_logger.exception.assert_called_once()
        assert 'failed to update connection status' in mock_logger.exception.call_args[0][0]


# ─── Sanitize-to-empty validation ────────────────────────────────────────────

@pytest.mark.django_db
class TestSanitizeToEmptyValidation:
    """
    utils.sanitize_dashboard_name() strips characters outside its allow-
    list. If a client submits a name made up ENTIRELY of disallowed
    characters (e.g. only emoji/control characters), sanitizing produces
    an empty string — UserDashboardSerializer.validate_name() must catch
    that and reject it with a field-specific error rather than silently
    creating a dashboard with an empty name.
    """

    def test_name_that_sanitizes_to_empty_is_rejected(self, authenticated_api_client):
        """
        '###$$$%%%' has no \\w/whitespace/hyphen characters, so
        sanitize_dashboard_name() strips it entirely — deliberately
        avoiding NUL/control characters here, which DRF's CharField
        rejects on its own before validate_name() ever runs; this test
        is specifically about the sanitize-to-empty branch inside
        validate_name(), not DRF's separate built-in check.
        """
        response = authenticated_api_client.post(
            reverse('userdashboard-list'),
            {'name': '###$$$%%%', 'status': 'active'},
            format='json',
        )
        assert response.status_code == 400
        assert 'name' in response.data['error']

    def test_normal_name_is_unaffected(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('userdashboard-list'), {'name': 'Perfectly Normal Name', 'status': 'active'}, format='json')
        assert response.status_code == 201


# ─── DashboardEngineError branches ───────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardEngineErrorBranches:
    """
    Three call sites catch DashboardEngineError from a viewset action.
    Under normal HTTP flow, self.get_object() already 404s before any of
    these actions' bodies run, so the exception's only realistic trigger
    is the service layer itself failing after the instance was
    confirmed to exist (e.g. a concurrent delete, or any other internal
    engine failure) — reproduced here by patching the service directly,
    which exercises the same except-branch without needing to engineer
    a real race.
    """

    def test_widget_data_action_returns_404_on_engine_error(self, authenticated_api_client):
        widget = create_dashboard_widget()
        with patch(
            'api.realtime_dashboard.viewsets.dashboard_widget_viewset.DashboardEngineService'
        ) as MockSvc:
            MockSvc.return_value.get_widget_data.side_effect = DashboardEngineError('boom')
            response = authenticated_api_client.get(reverse('dashboardwidget-data', kwargs={'pk': widget.pk}))
        assert response.status_code == 404
        assert response.data['success'] is False

    def test_dashboard_widget_ids_action_returns_404_on_engine_error(self, authenticated_api_client, test_user):
        dashboard = create_user_dashboard(user_id=str(test_user.pk))
        with patch(
            'api.realtime_dashboard.viewsets.user_dashboard_viewset.DashboardEngineService'
        ) as MockSvc:
            MockSvc.return_value.get_dashboard_widget_ids.side_effect = DashboardEngineError('boom')
            response = authenticated_api_client.get(
                reverse('userdashboard-widget-ids', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 404
        assert response.data['success'] is False

    def test_dashboard_stats_action_degrades_gracefully_on_engine_error(self, authenticated_api_client, test_user):
        """
        Unlike the two branches above, stats() intentionally does NOT
        fail the request when DashboardEngineError fires — it degrades
        to an empty widget_ids list so a dashboard summary is still
        returned. Different behavior, so it needs its own test rather
        than reusing the 404 assertion.
        """
        dashboard = create_user_dashboard(user_id=str(test_user.pk))
        with patch(
            'api.realtime_dashboard.viewsets.user_dashboard_viewset.DashboardEngineService'
        ) as MockSvc:
            MockSvc.return_value.get_dashboard_widget_ids.side_effect = DashboardEngineError('boom')
            response = authenticated_api_client.get(reverse('userdashboard-stats', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['widget_ids'] == []
        assert response.data['active_metric_count'] == 0
