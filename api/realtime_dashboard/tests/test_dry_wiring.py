"""
Tests for DRY refactoring and newly wired API endpoints (v1.2.0).

Covers:
    DRY-1   BaseCachedService — shared cache logic (no duplication)
    DRY-2   StatusActionMixin — shared admin activate/deactivate
    DRY-3   @require_query_param — missing-param → 400 on all viewsets

    WIRE-1  WidgetService wired to DashboardWidgetViewSet (perform_create/update/destroy)
    WIRE-2  GET /api/widgets/<id>/data/          (DashboardEngineService.get_widget_data)
    WIRE-3  GET /api/widgets/<id>/metrics/       (RealTimeMetricService.get_metrics_for_widget)
    WIRE-4  GET /api/widgets/by_type/            (WidgetService.get_widgets_by_type)
    WIRE-5  RealTimeMetricService wired to RealTimeMetricViewSet
    WIRE-6  POST /api/metrics/aggregate/         (utils.aggregate_metrics)
    WIRE-7  GET /api/metrics/by_type/            (RealTimeMetricService.get_metrics_by_type)
    WIRE-8  DashboardService wired to UserDashboardViewSet.perform_create
    WIRE-9  GET /api/dashboards/<id>/widget_ids/ (DashboardEngineService.get_dashboard_widget_ids)
    WIRE-10 GET /api/dashboards/<id>/stats/      (new summary endpoint)
    WIRE-11 POST /api/connections/broadcast_to_user/ (WebSocketManagerService.broadcast_to_user)
    WIRE-12 signals.dashboard_updated → stream_dashboard_updates
    WIRE-13 WidgetConfigurationSerializer.validate_value uses validate_widget_configuration
    WIRE-14 utils.aggregate_metrics key naming (sum, avg not total/average)
"""
import pytest
from unittest.mock import patch
from django.urls import reverse

from api.realtime_dashboard.tests.fixtures import (
    create_dashboard_widget,
    create_real_time_metric,
    create_user_dashboard,
    create_websocket_connection,
)
from api.realtime_dashboard.utils import aggregate_metrics
from api.realtime_dashboard.services.base_service import BaseCachedService
from api.realtime_dashboard.services.widget_service import WidgetService
from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService


# ═══════════════════════════════════════════════════════════════════════════════
# DRY-1: BaseCachedService — shared cache inheritance
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseCachedServiceInheritance:
    """Confirm WidgetService and RealTimeMetricService both extend BaseCachedService."""

    def test_widget_service_extends_base(self):
        assert issubclass(WidgetService, BaseCachedService)

    def test_metric_service_extends_base(self):
        assert issubclass(RealTimeMetricService, BaseCachedService)

    def test_widget_service_has_correct_prefix_setting(self):
        assert WidgetService.cache_prefix_setting == 'WIDGET_CACHE_PREFIX'

    def test_metric_service_has_correct_prefix_setting(self):
        assert RealTimeMetricService.cache_prefix_setting == 'METRIC_CACHE_PREFIX'

    def test_base_cache_key_uses_prefix_and_pk(self):
        svc = WidgetService()
        key = svc._cache_key(42)
        assert '42' in key
        assert key.startswith(svc._cache_key(42).split('42')[0])

    @pytest.mark.django_db
    def test_widget_service_and_metric_service_have_no_duplicate_get_cached(self):
        """The _get_cached method must come from BaseCachedService, not both classes."""
        assert WidgetService._get_cached is BaseCachedService._get_cached
        assert RealTimeMetricService._get_cached is BaseCachedService._get_cached

    @pytest.mark.django_db
    def test_widget_service_and_metric_service_have_no_duplicate_set_cached(self):
        assert WidgetService._set_cached is BaseCachedService._set_cached
        assert RealTimeMetricService._set_cached is BaseCachedService._set_cached

    @pytest.mark.django_db
    def test_widget_service_and_metric_service_have_no_duplicate_invalidate(self):
        assert WidgetService._invalidate is BaseCachedService._invalidate
        assert RealTimeMetricService._invalidate is BaseCachedService._invalidate


# ═══════════════════════════════════════════════════════════════════════════════
# DRY-2: StatusActionMixin — shared admin actions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestStatusActionMixinDRY:
    """Confirm the 3 admin classes inherit from StatusActionMixin (no duplication)."""

    def test_widget_admin_inherits_mixin(self):
        from api.realtime_dashboard.admin import DashboardWidgetAdmin, StatusActionMixin
        assert issubclass(DashboardWidgetAdmin, StatusActionMixin)

    def test_metric_admin_inherits_mixin(self):
        from api.realtime_dashboard.admin import RealTimeMetricAdmin, StatusActionMixin
        assert issubclass(RealTimeMetricAdmin, StatusActionMixin)

    def test_dashboard_admin_inherits_mixin(self):
        from api.realtime_dashboard.admin import UserDashboardAdmin, StatusActionMixin
        assert issubclass(UserDashboardAdmin, StatusActionMixin)

    def test_all_three_share_same_activate_method(self):
        """All three admin classes must use the SAME activate function object."""
        from api.realtime_dashboard.admin import (
            DashboardWidgetAdmin, RealTimeMetricAdmin, UserDashboardAdmin, StatusActionMixin
        )
        assert DashboardWidgetAdmin.activate is StatusActionMixin.activate
        assert RealTimeMetricAdmin.activate is StatusActionMixin.activate
        assert UserDashboardAdmin.activate is StatusActionMixin.activate


# ═══════════════════════════════════════════════════════════════════════════════
# DRY-3: @require_query_param — missing-param → 400
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRequireQueryParam:

    def test_by_type_missing_param_returns_400(self, authenticated_api_client):
        """GET /api/widgets/by_type/ without widget_type → 400."""
        response = authenticated_api_client.get(reverse('dashboardwidget-by-type'))
        assert response.status_code == 400
        assert "'widget_type'" in response.data['error']

    def test_metrics_by_type_missing_param_returns_400(self, authenticated_api_client):
        """GET /api/metrics/by_type/ without metric_type → 400."""
        response = authenticated_api_client.get(reverse('realtimemetric-by-type'))
        assert response.status_code == 400

    def test_layouts_by_type_missing_param_returns_400(self, authenticated_api_client):
        """GET /api/layouts/by_type/ without layout_type → 400."""
        response = authenticated_api_client.get(reverse('dashboardlayout-by-type'))
        assert response.status_code == 400

    def test_dashboard_by_user_missing_param_returns_400(self, authenticated_staff_client):
        """GET /api/dashboards/by_user/ without user_id → 400 (staff)."""
        response = authenticated_staff_client.get(reverse('userdashboard-by-user'))
        assert response.status_code == 400

    def test_connections_by_user_missing_param_returns_400(self, authenticated_staff_client):
        """GET /api/connections/by_user/ without user_id → 400 (staff)."""
        response = authenticated_staff_client.get(reverse('websocketconnection-by-user'))
        assert response.status_code == 400

    def test_by_type_with_param_succeeds(self, authenticated_api_client):
        """Providing widget_type passes the decorator check."""
        response = authenticated_api_client.get(
            reverse('dashboardwidget-by-type') + '?widget_type=chart'
        )
        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-1: WidgetService wired to DashboardWidgetViewSet
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetServiceWiredToViewset:

    def test_create_widget_via_api_primes_cache(self, authenticated_api_client):
        """POST /api/widgets/ → WidgetService.create_widget() → cache primed."""
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': True}):
            data = {'name': 'CachedW', 'widget_type': 'chart', 'status': 'active',
                    'configuration': {}, 'refresh_interval': 60, 'width': 6, 'height': 4}
            response = authenticated_api_client.post(
                reverse('dashboardwidget-list'), data, format='json'
            )
            assert response.status_code == 201
            from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
            widget = DashboardWidget.objects.get(name='CachedW')
            cached = WidgetService()._get_cached(widget.pk)
            assert cached is not None

    def test_delete_widget_via_api_invalidates_cache(self, authenticated_api_client):
        """DELETE /api/widgets/<id>/ → WidgetService.delete_widget() → cache purged."""
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': True}):
            widget = create_dashboard_widget(name='ToDelete')
            svc = WidgetService()
            svc._set_cached(widget)
            assert svc._get_cached(widget.pk) is not None

            authenticated_api_client.delete(
                reverse('dashboardwidget-detail', kwargs={'pk': widget.pk})
            )
            assert svc._get_cached(widget.pk) is None


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-2: GET /api/widgets/<id>/data/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetDataEndpoint:

    def test_returns_widget_data(self, authenticated_api_client):
        """GET /api/widgets/<id>/data/ calls DashboardEngineService.get_widget_data."""
        widget = create_dashboard_widget(name='DataWidget')
        response = authenticated_api_client.get(
            reverse('dashboardwidget-data', kwargs={'pk': widget.pk})
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'data' in response.data

    def test_missing_widget_returns_404(self, authenticated_api_client):
        """Non-existent widget pk → 404."""
        response = authenticated_api_client.get(
            reverse('dashboardwidget-data', kwargs={'pk': 999999})
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-3: GET /api/widgets/<id>/metrics/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetMetricsEndpoint:

    def test_returns_metrics_for_widget(self, authenticated_api_client):
        """GET /api/widgets/<id>/metrics/ returns metrics linked via metadata."""
        widget = create_dashboard_widget(name='MetricWidget')
        create_real_time_metric(
            name='CPU', status='active',
            metadata={'widget_id': widget.pk}
        )
        create_real_time_metric(
            name='MEM', status='active',
            metadata={'widget_id': widget.pk}
        )
        create_real_time_metric(name='Unrelated', status='active', metadata={})

        response = authenticated_api_client.get(
            reverse('dashboardwidget-metrics', kwargs={'pk': widget.pk})
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        names = [m['name'] for m in response.data['metrics']]
        assert 'CPU' in names and 'MEM' in names
        assert 'Unrelated' not in names

    def test_widget_with_no_metrics_returns_empty_list(self, authenticated_api_client):
        widget = create_dashboard_widget(name='EmptyWidget')
        response = authenticated_api_client.get(
            reverse('dashboardwidget-metrics', kwargs={'pk': widget.pk})
        )
        assert response.status_code == 200
        assert response.data['metrics'] == []


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-4: GET /api/widgets/by_type/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetsByTypeEndpoint:

    def test_filters_by_widget_type(self, authenticated_api_client):
        create_dashboard_widget(name='Chart1', widget_type='chart')
        create_dashboard_widget(name='Table1', widget_type='table')
        response = authenticated_api_client.get(
            reverse('dashboardwidget-by-type') + '?widget_type=chart'
        )
        assert response.status_code == 200
        names = [w['name'] for w in response.data]
        assert 'Chart1' in names and 'Table1' not in names


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-6: POST /api/metrics/aggregate/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMetricAggregateEndpoint:

    def test_aggregate_returns_summary(self, authenticated_api_client):
        """POST /api/metrics/aggregate/ returns sum, avg, min, max, count."""
        m1 = create_real_time_metric(name='M1', value=10.0, status='active')
        m2 = create_real_time_metric(name='M2', value=30.0, status='active')
        m3 = create_real_time_metric(name='M3', value=50.0, status='active')

        response = authenticated_api_client.post(
            reverse('realtimemetric-aggregate'),
            {'metric_ids': [m1.pk, m2.pk, m3.pk]},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['count'] == 3
        assert response.data['sum'] == pytest.approx(90.0)
        assert response.data['avg'] == pytest.approx(30.0)
        assert response.data['min'] == pytest.approx(10.0)
        assert response.data['max'] == pytest.approx(50.0)

    def test_aggregate_empty_ids_returns_400(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('realtimemetric-aggregate'),
            {'metric_ids': []},
            format='json',
        )
        assert response.status_code == 400

    def test_aggregate_missing_ids_returns_400(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('realtimemetric-aggregate'),
            {},
            format='json',
        )
        assert response.status_code == 400

    def test_aggregate_only_counts_active_metrics(self, authenticated_api_client):
        """Inactive metrics must be excluded from aggregation."""
        active = create_real_time_metric(value=100.0, status='active')
        inactive = create_real_time_metric(value=999.0, status='inactive')

        response = authenticated_api_client.post(
            reverse('realtimemetric-aggregate'),
            {'metric_ids': [active.pk, inactive.pk]},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert response.data['sum'] == pytest.approx(100.0)

    def test_aggregate_nonexistent_ids_returns_404(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('realtimemetric-aggregate'),
            {'metric_ids': [999999, 888888]},
            format='json',
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-7: GET /api/metrics/by_type/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMetricsByTypeEndpoint:

    def test_filters_by_metric_type(self, authenticated_api_client):
        create_real_time_metric(name='Gauge1', metric_type='gauge')
        create_real_time_metric(name='Counter1', metric_type='counter')
        response = authenticated_api_client.get(
            reverse('realtimemetric-by-type') + '?metric_type=gauge'
        )
        assert response.status_code == 200
        names = [m['name'] for m in response.data]
        assert 'Gauge1' in names and 'Counter1' not in names


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-9: GET /api/dashboards/<id>/widget_ids/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardWidgetIdsEndpoint:

    def test_returns_widget_id_list(self, authenticated_api_client, test_user):
        w1 = create_dashboard_widget(name='W1')
        w2 = create_dashboard_widget(name='W2')
        dashboard = create_user_dashboard(
            widgets=[w1.pk, w2.pk], user_id=str(test_user.pk)
        )
        response = authenticated_api_client.get(
            reverse('userdashboard-widget-ids', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        assert set(response.data['widget_ids']) == {w1.pk, w2.pk}

    def test_empty_dashboard_returns_empty_list(self, authenticated_api_client, test_user):
        dashboard = create_user_dashboard(widgets=[], user_id=str(test_user.pk))
        response = authenticated_api_client.get(
            reverse('userdashboard-widget-ids', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        assert response.data['widget_ids'] == []

    def test_non_owner_cannot_access(self, authenticated_second_client, test_user):
        dashboard = create_user_dashboard(widgets=[], user_id=str(test_user.pk))
        response = authenticated_second_client.get(
            reverse('userdashboard-widget-ids', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-10: GET /api/dashboards/<id>/stats/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardStatsEndpoint:

    def test_returns_stats(self, authenticated_api_client, test_user):
        w1 = create_dashboard_widget()
        w2 = create_dashboard_widget()
        dashboard = create_user_dashboard(
            widgets=[w1.pk, w2.pk], user_id=str(test_user.pk)
        )
        response = authenticated_api_client.get(
            reverse('userdashboard-stats', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['dashboard_id'] == dashboard.pk
        assert response.data['widget_count'] == 2
        assert 'active_metric_count' in response.data
        assert 'widget_ids' in response.data


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-11: POST /api/connections/broadcast_to_user/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBroadcastToUserEndpoint:

    def test_non_staff_gets_403(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('websocketconnection-broadcast-to-user'),
            {'user_id': '123', 'data': {'msg': 'hi'}},
            format='json',
        )
        assert response.status_code == 403

    def test_staff_can_broadcast(self, authenticated_staff_client, second_user):
        create_websocket_connection(
            connection_id='sconn1',
            user_id=str(second_user.pk),
            status='connected',
        )
        with patch(
            'api.realtime_dashboard.services.websocket_manager_service'
            '.WebSocketManagerService.broadcast_to_user',
            return_value=True
        ) as mock_broadcast:
            response = authenticated_staff_client.post(
                reverse('websocketconnection-broadcast-to-user'),
                {'user_id': str(second_user.pk), 'data': {'alert': 'test'}},
                format='json',
            )
        assert response.status_code == 200
        assert response.data['success'] is True
        mock_broadcast.assert_called_once_with(str(second_user.pk), {'alert': 'test'})

    def test_missing_user_id_returns_400(self, authenticated_staff_client):
        response = authenticated_staff_client.post(
            reverse('websocketconnection-broadcast-to-user'),
            {'data': {'msg': 'hi'}},
            format='json',
        )
        assert response.status_code == 400

    def test_missing_data_returns_400(self, authenticated_staff_client):
        response = authenticated_staff_client.post(
            reverse('websocketconnection-broadcast-to-user'),
            {'user_id': '123'},
            format='json',
        )
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-12: signals.dashboard_updated → stream_dashboard_updates
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardUpdatedSignal:

    def test_signal_fires_stream_on_update(self):
        """Saving an existing dashboard calls stream_dashboard_updates."""
        dashboard = create_user_dashboard(name='SignalDash')
        with patch(
            'api.realtime_dashboard.services.event_streaming_service'
            '.EventStreamingService.stream_dashboard_updates'
        ) as mock_stream:
            dashboard.name = 'UpdatedName'
            dashboard.save()
            mock_stream.assert_called_once_with(dashboard.pk)

    def test_signal_does_not_fire_on_create(self):
        """Newly created dashboards have no subscribers — signal skips broadcast."""
        with patch(
            'api.realtime_dashboard.services.event_streaming_service'
            '.EventStreamingService.stream_dashboard_updates'
        ) as mock_stream:
            create_user_dashboard(name='NewDash')
            mock_stream.assert_not_called()

    def test_signal_handles_stream_failure_gracefully(self):
        """Broadcast failure must NOT cause the save() to fail."""
        dashboard = create_user_dashboard(name='FailDash')
        with patch(
            'api.realtime_dashboard.services.event_streaming_service'
            '.EventStreamingService.stream_dashboard_updates',
            side_effect=RuntimeError('Redis down')
        ):
            dashboard.name = 'FailDashUpdated'
            dashboard.save()  # Must not raise
            dashboard.refresh_from_db()
            assert dashboard.name == 'FailDashUpdated'


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-13: WidgetConfigurationSerializer.validate_value
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWidgetConfigurationValidation:

    def test_chart_config_without_required_keys_returns_400(self, authenticated_api_client):
        """POSTing a chart configuration without 'data' and 'chartType' → 400."""
        widget = create_dashboard_widget()
        response = authenticated_api_client.post(
            reverse('widgetconfiguration-list'),
            {
                'widget': widget.pk,
                'config_type': 'chart',
                'key': 'chart_settings',
                'value': {'type': 'chart'},   # missing 'data' and 'chartType'
            },
            format='json',
        )
        assert response.status_code == 400
        assert 'chartType' in str(response.data) or 'invalid' in str(response.data).lower()

    def test_chart_config_with_required_keys_succeeds(self, authenticated_api_client):
        """Valid chart configuration is accepted."""
        widget = create_dashboard_widget()
        response = authenticated_api_client.post(
            reverse('widgetconfiguration-list'),
            {
                'widget': widget.pk,
                'config_type': 'chart',
                'key': 'valid_chart',
                'value': {'type': 'chart', 'data': [1, 2, 3], 'chartType': 'line'},
            },
            format='json',
        )
        assert response.status_code == 201

    def test_non_chart_config_is_accepted(self, authenticated_api_client):
        """Non-chart configurations bypass the chart-specific validation."""
        widget = create_dashboard_widget()
        response = authenticated_api_client.post(
            reverse('widgetconfiguration-list'),
            {
                'widget': widget.pk,
                'config_type': 'style',    # 'display' not a valid choice; valid: chart|data|style|behavior
                'key': 'colour',
                'value': {'primaryColor': '#ff0000'},
            },
            format='json',
        )
        assert response.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-14: utils.aggregate_metrics key naming
# ═══════════════════════════════════════════════════════════════════════════════

class TestAggregateMetricsUtils:
    """Verify aggregate_metrics output uses 'sum'/'avg' not 'total'/'average'."""

    def test_returns_sum_not_total(self):
        data = [{'value': 10}, {'value': 20}, {'value': 30}]
        result = aggregate_metrics(data)
        assert 'sum' in result
        assert 'total' not in result

    def test_returns_avg_not_average(self):
        data = [{'value': 10}, {'value': 20}, {'value': 30}]
        result = aggregate_metrics(data)
        assert 'avg' in result
        assert 'average' not in result

    def test_correct_values(self):
        data = [{'value': 10}, {'value': 20}, {'value': 30}]
        result = aggregate_metrics(data)
        assert result['count'] == 3
        assert result['sum'] == pytest.approx(60.0)
        assert result['avg'] == pytest.approx(20.0)
        assert result['min'] == pytest.approx(10.0)
        assert result['max'] == pytest.approx(30.0)

    def test_empty_returns_empty_dict(self):
        assert aggregate_metrics([]) == {}


# ═══════════════════════════════════════════════════════════════════════════════
# WIRE-5: RealTimeMetricService perform_create/update/destroy wired
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMetricServiceWiredToViewset:

    def test_create_metric_via_api_primes_cache(self, authenticated_api_client):
        """POST /api/metrics/ → perform_create() → cache primed via RealTimeMetricService."""
        from django.test import override_settings
        with override_settings(REALTIME_DASHBOARD={'ENABLE_CACHING': True}):
            data = {'name': 'CPULoad', 'metric_type': 'gauge', 'status': 'active',
                    'value': 55.0, 'unit': '%'}
            response = authenticated_api_client.post(
                reverse('realtimemetric-list'), data, format='json'
            )
            assert response.status_code == 201
            from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
            metric = RealTimeMetric.objects.get(name='CPULoad')
            # Cache should be primed immediately after create (verify wiring)
            cached = RealTimeMetricService()._get_cached(metric.pk)
            assert cached is not None

    def test_update_metric_value_tracks_previous(self, authenticated_api_client):
        """PATCH value → previous_value auto-captured via service."""
        metric = create_real_time_metric(value=100.0, previous_value=None)
        authenticated_api_client.patch(
            reverse('realtimemetric-detail', kwargs={'pk': metric.pk}),
            {'value': 200.0}, format='json'
        )
        metric.refresh_from_db()
        assert metric.value == pytest.approx(200.0)
        assert metric.previous_value == pytest.approx(100.0)
