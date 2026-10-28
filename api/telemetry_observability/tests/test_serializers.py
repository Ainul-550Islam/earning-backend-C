"""
Tests for all serializers — valid data, invalid data, computed fields.
"""
import pytest
from django.utils import timezone

from ..serializers.metric_serializer import (
    MetricEventSerializer, MetricEventCreateSerializer,
    MetricStatisticsSerializer, MetricBatchCreateSerializer,
)
from ..serializers.log_serializer import LogEntrySerializer, LogEntryCreateSerializer
from ..serializers.trace_serializer import (
    TraceSpanSerializer, TraceSpanCreateSerializer, TraceSpanFinishSerializer,
)
from ..serializers.alert_serializer import (
    AlertSerializer, AlertCreateSerializer,
    AlertAcknowledgeSerializer, AlertStatisticsSerializer,
)
from ..serializers.health_serializer import HealthStatusSerializer, HealthStatusCreateSerializer
from ..serializers.dashboard_serializer import (
    DashboardWidgetSerializer, DashboardWidgetCreateSerializer,
)
from ..serializers.analytics_serializer import (
    MetricAnalyticsSerializer, LogAnalyticsSerializer,
    TraceAnalyticsSerializer, AlertAnalyticsSerializer,
    HealthAnalyticsSerializer, ServiceAnalyticsSerializer,
    OverviewSerializer,
)


# ── MetricEventSerializer ─────────────────────────────────────────────────────

class TestMetricEventCreateSerializer:
    def test_valid_data(self):
        s = MetricEventCreateSerializer(data={
            'name': 'cpu_usage', 'metric_type': 'gauge', 'value': 80.0,
        })
        assert s.is_valid(), s.errors

    def test_invalid_metric_type(self):
        s = MetricEventCreateSerializer(data={
            'name': 'cpu_usage', 'metric_type': 'unknown', 'value': 80.0,
        })
        assert not s.is_valid()
        assert 'metric_type' in s.errors

    def test_null_value_invalid(self):
        s = MetricEventCreateSerializer(data={
            'name': 'cpu_usage', 'metric_type': 'gauge', 'value': None,
        })
        assert not s.is_valid()

    def test_missing_name_invalid(self):
        s = MetricEventCreateSerializer(data={'metric_type': 'counter', 'value': 1.0})
        assert not s.is_valid()
        assert 'name' in s.errors

    @pytest.mark.parametrize("mtype", ['counter', 'gauge', 'histogram', 'summary'])
    def test_all_metric_types_valid(self, mtype):
        s = MetricEventCreateSerializer(data={
            'name': 'test', 'metric_type': mtype, 'value': 1.0,
        })
        assert s.is_valid(), s.errors


class TestMetricBatchCreateSerializer:
    def test_valid_batch(self):
        s = MetricBatchCreateSerializer(data={
            'metrics': [
                {'name': 'm1', 'metric_type': 'counter', 'value': 1.0},
                {'name': 'm2', 'metric_type': 'gauge',   'value': 2.0},
            ]
        })
        assert s.is_valid(), s.errors

    def test_empty_batch_invalid(self):
        s = MetricBatchCreateSerializer(data={'metrics': []})
        assert not s.is_valid()
        assert 'metrics' in s.errors

    def test_single_invalid_item_fails(self):
        s = MetricBatchCreateSerializer(data={
            'metrics': [{'name': 'm1', 'metric_type': 'bad_type', 'value': 1.0}]
        })
        assert not s.is_valid()


# ── LogEntrySerializer ────────────────────────────────────────────────────────

class TestLogEntryCreateSerializer:
    def test_valid_data(self):
        s = LogEntryCreateSerializer(data={'level': 'info', 'message': 'Test message'})
        assert s.is_valid(), s.errors

    def test_invalid_level(self):
        s = LogEntryCreateSerializer(data={'level': 'trace', 'message': 'msg'})
        assert not s.is_valid()
        assert 'level' in s.errors

    def test_empty_message_invalid(self):
        s = LogEntryCreateSerializer(data={'level': 'info', 'message': ''})
        assert not s.is_valid()
        assert 'message' in s.errors

    def test_whitespace_message_invalid(self):
        s = LogEntryCreateSerializer(data={'level': 'info', 'message': '   '})
        assert not s.is_valid()

    @pytest.mark.parametrize("level", ['debug', 'info', 'warning', 'error', 'critical'])
    def test_all_levels_valid(self, level):
        s = LogEntryCreateSerializer(data={'level': level, 'message': 'msg'})
        assert s.is_valid(), s.errors


# ── TraceSpanSerializer ───────────────────────────────────────────────────────

class TestTraceSpanCreateSerializer:
    def test_valid_data(self):
        s = TraceSpanCreateSerializer(data={'operation_name': 'GET /api'})
        assert s.is_valid(), s.errors

    def test_empty_operation_name_invalid(self):
        s = TraceSpanCreateSerializer(data={'operation_name': ''})
        assert not s.is_valid()
        assert 'operation_name' in s.errors

    def test_optional_trace_id(self):
        s = TraceSpanCreateSerializer(data={
            'operation_name': 'op', 'trace_id': 'trace-123'
        })
        assert s.is_valid(), s.errors

    def test_optional_parent_span_id(self):
        s = TraceSpanCreateSerializer(data={
            'operation_name': 'op', 'parent_span_id': 'span-456'
        })
        assert s.is_valid(), s.errors


class TestTraceSpanFinishSerializer:
    def test_default_status_success(self):
        s = TraceSpanFinishSerializer(data={})
        assert s.is_valid(), s.errors
        assert s.validated_data['status'] == 'success'

    def test_invalid_status(self):
        s = TraceSpanFinishSerializer(data={'status': 'unknown_status'})
        assert not s.is_valid()
        assert 'status' in s.errors

    @pytest.mark.parametrize("status", ['success', 'error', 'timeout'])
    def test_all_statuses_valid(self, status):
        s = TraceSpanFinishSerializer(data={'status': status})
        assert s.is_valid(), s.errors


# ── AlertSerializer ───────────────────────────────────────────────────────────

class TestAlertCreateSerializer:
    def test_valid_data(self):
        s = AlertCreateSerializer(data={
            'name': 'High CPU', 'alert_type': 'metric',
            'severity': 'warning', 'message': 'CPU is high',
        })
        assert s.is_valid(), s.errors

    def test_invalid_severity(self):
        s = AlertCreateSerializer(data={
            'name': 'Alert', 'alert_type': 'metric',
            'severity': 'extreme', 'message': 'msg',
        })
        assert not s.is_valid()
        assert 'severity' in s.errors

    def test_empty_name_invalid(self):
        s = AlertCreateSerializer(data={
            'name': '', 'alert_type': 'metric',
            'severity': 'warning', 'message': 'msg',
        })
        assert not s.is_valid()
        assert 'name' in s.errors

    @pytest.mark.parametrize("severity", ['info', 'warning', 'error', 'critical'])
    def test_all_severities_valid(self, severity):
        s = AlertCreateSerializer(data={
            'name': 'Alert', 'alert_type': 'metric',
            'severity': severity, 'message': 'msg',
        })
        assert s.is_valid(), s.errors


class TestAlertAcknowledgeSerializer:
    def test_valid_user(self):
        s = AlertAcknowledgeSerializer(data={'user': 'ops-team'})
        assert s.is_valid(), s.errors

    def test_empty_user_invalid(self):
        s = AlertAcknowledgeSerializer(data={'user': ''})
        assert not s.is_valid()
        assert 'user' in s.errors

    def test_whitespace_user_invalid(self):
        s = AlertAcknowledgeSerializer(data={'user': '   '})
        assert not s.is_valid()


# ── HealthStatusSerializer ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthStatusSerializer:
    def test_computed_is_healthy_true(self, health):
        s = HealthStatusSerializer(health)
        assert s.data['is_healthy'] is True

    def test_computed_is_healthy_false(self, db):
        from ..models.health_status import HealthStatus
        h = HealthStatus.objects.create(
            service_name='bad-svc', status='unhealthy', health_score=0
        )
        s = HealthStatusSerializer(h)
        assert s.data['is_healthy'] is False

    def test_computed_is_unhealthy_true(self, db):
        from ..models.health_status import HealthStatus
        h = HealthStatus.objects.create(
            service_name='bad-svc2', status='unhealthy', health_score=10
        )
        s = HealthStatusSerializer(h)
        assert s.data['is_unhealthy'] is True

    def test_health_score_validation(self):
        s = HealthStatusCreateSerializer(data={
            'service_name': 'svc', 'status': 'healthy', 'health_score': 150,
        })
        assert not s.is_valid()
        assert 'health_score' in s.errors

    def test_negative_health_score_invalid(self):
        s = HealthStatusCreateSerializer(data={
            'service_name': 'svc', 'status': 'healthy', 'health_score': -1,
        })
        assert not s.is_valid()


# ── DashboardWidgetSerializer ─────────────────────────────────────────────────

class TestDashboardWidgetCreateSerializer:
    def test_valid_data(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': 'CPU Widget', 'widget_type': 'line_chart', 'data_source': 'metric',
        })
        assert s.is_valid(), s.errors

    def test_invalid_widget_type(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': 'Widget', 'widget_type': 'unknown_type', 'data_source': 'metric',
        })
        assert not s.is_valid()
        assert 'widget_type' in s.errors

    def test_width_too_large(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': 'Widget', 'widget_type': 'gauge',
            'data_source': 'metric', 'width': 13,
        })
        assert not s.is_valid()
        assert 'width' in s.errors

    def test_width_zero_invalid(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': 'Widget', 'widget_type': 'gauge',
            'data_source': 'metric', 'width': 0,
        })
        assert not s.is_valid()

    def test_negative_refresh_interval_invalid(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': 'Widget', 'widget_type': 'gauge',
            'data_source': 'metric', 'refresh_interval': -1,
        })
        assert not s.is_valid()

    def test_empty_name_invalid(self):
        s = DashboardWidgetCreateSerializer(data={
            'name': '', 'widget_type': 'gauge', 'data_source': 'metric',
        })
        assert not s.is_valid()


# ── Analytics Serializers ─────────────────────────────────────────────────────

class TestAnalyticsSerializers:
    def test_metric_analytics_serializer(self):
        data = {
            'metric_name': 'cpu', 'period_hours': 24,
            'count': 100, 'avg': 50.0, 'min': 10.0, 'max': 90.0, 'sum': 5000.0,
            'std_dev': 15.0, 'percentile_50': 50.0, 'percentile_95': 85.0, 'percentile_99': 89.0,
        }
        s = MetricAnalyticsSerializer(data)
        assert s.data['metric_name'] == 'cpu'
        assert s.data['count'] == 100

    def test_log_analytics_serializer(self):
        data = {
            'period_hours': 24, 'total_logs': 500,
            'level_counts': {'info': 400, 'error': 100},
            'error_rate': 20.0,
        }
        s = LogAnalyticsSerializer(data)
        assert s.data['total_logs'] == 500
        assert s.data['error_rate'] == 20.0

    def test_overview_serializer(self):
        data = {
            'period_hours': 24, 'total_metrics': 1000, 'total_logs': 500,
            'total_traces': 200, 'total_alerts': 10, 'open_alerts': 3,
            'critical_alerts': 1, 'healthy_services': 8, 'unhealthy_services': 2,
            'avg_health_score': 85.0,
        }
        s = OverviewSerializer(data)
        assert s.data['total_metrics'] == 1000
        assert s.data['healthy_services'] == 8
