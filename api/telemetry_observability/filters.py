"""
Django-filter FilterSets for Telemetry Observability.

Wire into viewsets via:
    filterset_class = MetricEventFilter
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]

All choices imported from choices.py — never hardcoded here.
"""
from django_filters import rest_framework as django_filters
from django.utils import timezone
from datetime import timedelta

from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.alert import Alert
from .models.health_status import HealthStatus
from .models.dashboard_widget import DashboardWidget
from .choices import (
    MetricTypeChoices,
    LogLevelChoices,
    TraceStatusChoices,
    AlertTypeChoices,
    AlertSeverityChoices,
    AlertStatusChoices,
    HealthStatusChoices,
    EnvironmentChoices,
    WidgetTypeChoices,
    DataSourceChoices,
)


# ---------------------------------------------------------------------------
# Time-range helper (DRY: single implementation used by all FilterSets)
# ---------------------------------------------------------------------------

TIME_RANGE_CHOICES = [
    ('1h',  'Last Hour'),
    ('6h',  'Last 6 Hours'),
    ('24h', 'Last 24 Hours'),
    ('7d',  'Last 7 Days'),
    ('30d', 'Last 30 Days'),
]

TIME_RANGE_MAP = {
    '1h':  timedelta(hours=1),
    '6h':  timedelta(hours=6),
    '24h': timedelta(hours=24),
    '7d':  timedelta(days=7),
    '30d': timedelta(days=30),
}


def _apply_time_range(queryset, name, value, time_field='timestamp'):
    """
    Shared time-range filter method.
    Used by all FilterSets that have a `time_range` field.
    """
    delta = TIME_RANGE_MAP.get(value)
    if delta:
        since = timezone.now() - delta
        return queryset.filter(**{f'{time_field}__gte': since})
    return queryset


# ---------------------------------------------------------------------------
# MetricEvent
# ---------------------------------------------------------------------------

class MetricEventFilter(django_filters.FilterSet):
    """
    Filterset for MetricEvent.
    Supports: name, metric_type, source, service, environment,
              timestamp range, value range, and preset time_range.
    """
    name          = django_filters.CharFilter(lookup_expr='icontains')
    metric_type   = django_filters.ChoiceFilter(choices=MetricTypeChoices.choices)
    source        = django_filters.CharFilter(lookup_expr='icontains')
    service       = django_filters.CharFilter(lookup_expr='icontains')
    environment   = django_filters.ChoiceFilter(choices=EnvironmentChoices.choices)
    timestamp_gte = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_lte = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    value_gte     = django_filters.NumberFilter(field_name='value', lookup_expr='gte')
    value_lte     = django_filters.NumberFilter(field_name='value', lookup_expr='lte')
    time_range    = django_filters.ChoiceFilter(
        choices=TIME_RANGE_CHOICES,
        method='filter_time_range',
        label='Preset time range',
    )

    class Meta:
        model = MetricEvent
        fields = ['name', 'metric_type', 'source', 'service', 'environment']

    def filter_time_range(self, queryset, name, value):
        return _apply_time_range(queryset, name, value, time_field='timestamp')


# ---------------------------------------------------------------------------
# LogEntry
# ---------------------------------------------------------------------------

class LogEntryFilter(django_filters.FilterSet):
    """
    Filterset for LogEntry.
    Supports: level, message, logger_name, source, service, environment,
              timestamp range, and preset time_range.
    """
    level         = django_filters.ChoiceFilter(choices=LogLevelChoices.choices)
    message       = django_filters.CharFilter(lookup_expr='icontains')
    logger_name   = django_filters.CharFilter(lookup_expr='icontains')
    source        = django_filters.CharFilter(lookup_expr='icontains')
    service       = django_filters.CharFilter(lookup_expr='icontains')
    environment   = django_filters.ChoiceFilter(choices=EnvironmentChoices.choices)
    timestamp_gte = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_lte = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    time_range    = django_filters.ChoiceFilter(
        choices=TIME_RANGE_CHOICES,
        method='filter_time_range',
        label='Preset time range',
    )

    class Meta:
        model = LogEntry
        fields = ['level', 'logger_name', 'source', 'service', 'environment']

    def filter_time_range(self, queryset, name, value):
        return _apply_time_range(queryset, name, value, time_field='timestamp')


# ---------------------------------------------------------------------------
# TraceSpan
# ---------------------------------------------------------------------------

class TraceSpanFilter(django_filters.FilterSet):
    """
    Filterset for TraceSpan.
    Supports: trace_id, span_id, operation_name, service, status,
              start_time range, duration range, and preset time_range.
    """
    trace_id         = django_filters.CharFilter(lookup_expr='icontains')
    span_id          = django_filters.CharFilter(lookup_expr='icontains')
    operation_name   = django_filters.CharFilter(lookup_expr='icontains')
    service          = django_filters.CharFilter(lookup_expr='icontains')
    status           = django_filters.ChoiceFilter(choices=TraceStatusChoices.choices)
    start_time_gte   = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='gte')
    start_time_lte   = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='lte')
    duration_ms_gte  = django_filters.NumberFilter(field_name='duration_ms', lookup_expr='gte')
    duration_ms_lte  = django_filters.NumberFilter(field_name='duration_ms', lookup_expr='lte')
    time_range       = django_filters.ChoiceFilter(
        choices=TIME_RANGE_CHOICES,
        method='filter_time_range',
        label='Preset time range',
    )

    class Meta:
        model = TraceSpan
        fields = ['trace_id', 'operation_name', 'service', 'status']

    def filter_time_range(self, queryset, name, value):
        return _apply_time_range(queryset, name, value, time_field='start_time')


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertFilter(django_filters.FilterSet):
    """
    Filterset for Alert.
    Supports: name, alert_type, severity, status, source, service, environment,
              triggered_at range, and preset time_range.
    """
    name             = django_filters.CharFilter(lookup_expr='icontains')
    alert_type       = django_filters.ChoiceFilter(choices=AlertTypeChoices.choices)
    severity         = django_filters.ChoiceFilter(choices=AlertSeverityChoices.choices)
    status           = django_filters.ChoiceFilter(choices=AlertStatusChoices.choices)
    source           = django_filters.CharFilter(lookup_expr='icontains')
    service          = django_filters.CharFilter(lookup_expr='icontains')
    environment      = django_filters.ChoiceFilter(choices=EnvironmentChoices.choices)
    triggered_at_gte = django_filters.DateTimeFilter(field_name='triggered_at', lookup_expr='gte')
    triggered_at_lte = django_filters.DateTimeFilter(field_name='triggered_at', lookup_expr='lte')
    time_range       = django_filters.ChoiceFilter(
        choices=TIME_RANGE_CHOICES,
        method='filter_time_range',
        label='Preset time range',
    )

    class Meta:
        model = Alert
        fields = ['name', 'alert_type', 'severity', 'status', 'source', 'service', 'environment']

    def filter_time_range(self, queryset, name, value):
        return _apply_time_range(queryset, name, value, time_field='triggered_at')


# ---------------------------------------------------------------------------
# HealthStatus
# ---------------------------------------------------------------------------

class HealthStatusFilter(django_filters.FilterSet):
    """
    Filterset for HealthStatus.
    Supports: service_name, component_name, status, environment,
              health_score range, and last_check range.
    """
    service_name      = django_filters.CharFilter(lookup_expr='icontains')
    component_name    = django_filters.CharFilter(lookup_expr='icontains')
    status            = django_filters.ChoiceFilter(choices=HealthStatusChoices.choices)
    environment       = django_filters.ChoiceFilter(choices=EnvironmentChoices.choices)
    health_score_gte  = django_filters.NumberFilter(field_name='health_score', lookup_expr='gte')
    health_score_lte  = django_filters.NumberFilter(field_name='health_score', lookup_expr='lte')
    last_check_gte    = django_filters.DateTimeFilter(field_name='last_check', lookup_expr='gte')
    last_check_lte    = django_filters.DateTimeFilter(field_name='last_check', lookup_expr='lte')

    class Meta:
        model = HealthStatus
        fields = ['service_name', 'component_name', 'status', 'environment']


# ---------------------------------------------------------------------------
# DashboardWidget
# ---------------------------------------------------------------------------

class DashboardWidgetFilter(django_filters.FilterSet):
    """
    Filterset for DashboardWidget.
    Supports: name, widget_type, data_source, is_active, dashboard.
    """
    name        = django_filters.CharFilter(lookup_expr='icontains')
    widget_type = django_filters.ChoiceFilter(choices=WidgetTypeChoices.choices)
    data_source = django_filters.ChoiceFilter(choices=DataSourceChoices.choices)
    is_active   = django_filters.BooleanFilter()
    dashboard   = django_filters.NumberFilter(field_name='dashboard__id')

    class Meta:
        model = DashboardWidget
        fields = ['name', 'widget_type', 'data_source', 'is_active']
