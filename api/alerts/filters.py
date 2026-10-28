"""
Custom filters for Alerts API using django-filter
"""
import django_filters
from django.db.models import Q
from datetime import datetime, timedelta

from .models.core import AlertRule, AlertLog, Notification, SystemHealthCheck
from .models.threshold import ThresholdConfig, ThresholdBreach
from .models.incident import Incident
from .models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach
from .models.channel import AlertChannel, ChannelRoute
from .models.intelligence import AlertCorrelation

from .choices import (
    ALERT_TYPES, SEVERITY_LEVELS, NOTIFICATION_STATUS, ALERT_STATUS,
    NOTIFICATION_TYPES, REPORT_TYPES,
)


class AlertRuleFilter(django_filters.FilterSet):
    """Filter for AlertRule model"""

    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    alert_type = django_filters.ChoiceFilter(choices=ALERT_TYPES)
    severity = django_filters.ChoiceFilter(choices=SEVERITY_LEVELS)
    is_active = django_filters.BooleanFilter()
    threshold_value_min = django_filters.NumberFilter(field_name='threshold_value', lookup_expr='gte')
    threshold_value_max = django_filters.NumberFilter(field_name='threshold_value', lookup_expr='lte')
    created_by = django_filters.NumberFilter(field_name='created_by__id')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = AlertRule
        fields = ['name', 'alert_type', 'severity', 'is_active']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AlertLogFilter(django_filters.FilterSet):
    """Filter for AlertLog model"""

    rule = django_filters.NumberFilter(field_name='rule__id')
    rule_name = django_filters.CharFilter(field_name='rule__name', lookup_expr='icontains')
    severity = django_filters.ChoiceFilter(choices=SEVERITY_LEVELS, field_name='rule__severity')
    is_resolved = django_filters.BooleanFilter()
    triggered_after = django_filters.DateTimeFilter(field_name='triggered_at', lookup_expr='gte')
    triggered_before = django_filters.DateTimeFilter(field_name='triggered_at', lookup_expr='lte')
    resolved_after = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='gte')
    resolved_before = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='lte')
    trigger_value_min = django_filters.NumberFilter(field_name='trigger_value', lookup_expr='gte')
    trigger_value_max = django_filters.NumberFilter(field_name='trigger_value', lookup_expr='lte')
    recent = django_filters.BooleanFilter(method='filter_recent')

    class Meta:
        model = AlertLog
        fields = ['rule', 'is_resolved', 'triggered_at', 'resolved_at']

    def filter_recent(self, queryset, name, value):
        if value:
            return queryset.filter(triggered_at__gte=datetime.now() - timedelta(hours=24))
        return queryset


class NotificationFilter(django_filters.FilterSet):
    """Filter for Notification model"""

    alert_log = django_filters.NumberFilter(field_name='alert_log__id')
    notification_type = django_filters.ChoiceFilter(choices=NOTIFICATION_TYPES)
    status = django_filters.ChoiceFilter(choices=NOTIFICATION_STATUS)
    recipient = django_filters.CharFilter(lookup_expr='icontains')
    sent_after = django_filters.DateTimeFilter(field_name='sent_at', lookup_expr='gte')
    sent_before = django_filters.DateTimeFilter(field_name='sent_at', lookup_expr='lte')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Notification
        fields = ['alert_log', 'notification_type', 'status', 'recipient']


class ThresholdConfigFilter(django_filters.FilterSet):
    """Filter for ThresholdConfig model"""

    name = django_filters.CharFilter(lookup_expr='icontains')
    threshold_type = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()
    alert_rule = django_filters.NumberFilter(field_name='alert_rule__id')
    primary_threshold_min = django_filters.NumberFilter(field_name='primary_threshold', lookup_expr='gte')
    primary_threshold_max = django_filters.NumberFilter(field_name='primary_threshold', lookup_expr='lte')

    class Meta:
        model = ThresholdConfig
        fields = ['name', 'threshold_type', 'is_active', 'alert_rule']


class ThresholdBreachFilter(django_filters.FilterSet):
    """Filter for ThresholdBreach model"""

    severity = django_filters.ChoiceFilter(choices=SEVERITY_LEVELS)
    threshold_config = django_filters.NumberFilter(field_name='threshold_config__id')
    is_resolved = django_filters.BooleanFilter(method='filter_is_resolved')
    detected_after = django_filters.DateTimeFilter(field_name='detected_at', lookup_expr='gte')
    detected_before = django_filters.DateTimeFilter(field_name='detected_at', lookup_expr='lte')

    class Meta:
        model = ThresholdBreach
        fields = ['severity', 'threshold_config']

    def filter_is_resolved(self, queryset, name, value):
        if value:
            return queryset.filter(resolved_at__isnull=False)
        return queryset.filter(resolved_at__isnull=True)


class IncidentFilter(django_filters.FilterSet):
    """Filter for Incident model"""

    title = django_filters.CharFilter(lookup_expr='icontains')
    severity = django_filters.ChoiceFilter(choices=SEVERITY_LEVELS)
    status = django_filters.CharFilter()
    assigned_to = django_filters.NumberFilter(field_name='assigned_to__id')
    detected_after = django_filters.DateTimeFilter(field_name='detected_at', lookup_expr='gte')
    detected_before = django_filters.DateTimeFilter(field_name='detected_at', lookup_expr='lte')
    resolved_after = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='gte')
    resolved_before = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='lte')
    is_resolved = django_filters.BooleanFilter(method='filter_is_resolved')

    class Meta:
        model = Incident
        fields = ['severity', 'status', 'assigned_to']

    def filter_is_resolved(self, queryset, name, value):
        if value:
            return queryset.filter(resolved_at__isnull=False)
        return queryset.filter(resolved_at__isnull=True)


class AlertReportFilter(django_filters.FilterSet):
    """Filter for AlertReport model"""

    title = django_filters.CharFilter(lookup_expr='icontains')
    report_type = django_filters.ChoiceFilter(choices=REPORT_TYPES)
    status = django_filters.CharFilter()
    created_by = django_filters.NumberFilter(field_name='created_by__id')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    generated_after = django_filters.DateTimeFilter(field_name='generated_at', lookup_expr='gte')
    generated_before = django_filters.DateTimeFilter(field_name='generated_at', lookup_expr='lte')

    class Meta:
        model = AlertReport
        fields = ['report_type', 'status', 'created_by']


class AlertChannelFilter(django_filters.FilterSet):
    """Filter for AlertChannel model"""

    name = django_filters.CharFilter(lookup_expr='icontains')
    channel_type = django_filters.CharFilter()
    is_enabled = django_filters.BooleanFilter()
    status = django_filters.CharFilter()

    class Meta:
        model = AlertChannel
        fields = ['name', 'channel_type', 'is_enabled', 'status']


class ChannelRouteFilter(django_filters.FilterSet):
    """Filter for ChannelRoute model"""

    name = django_filters.CharFilter(lookup_expr='icontains')
    route_type = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = ChannelRoute
        fields = ['name', 'route_type', 'is_active']


class SystemHealthCheckFilter(django_filters.FilterSet):
    """Filter for SystemHealthCheck model"""

    check_name = django_filters.CharFilter(lookup_expr='icontains')
    check_type = django_filters.CharFilter()
    status = django_filters.CharFilter()
    checked_after = django_filters.DateTimeFilter(field_name='checked_at', lookup_expr='gte')
    checked_before = django_filters.DateTimeFilter(field_name='checked_at', lookup_expr='lte')
    response_time_min = django_filters.NumberFilter(field_name='response_time_ms', lookup_expr='gte')
    response_time_max = django_filters.NumberFilter(field_name='response_time_ms', lookup_expr='lte')

    class Meta:
        model = SystemHealthCheck
        fields = ['check_name', 'check_type', 'status']


class AlertCorrelationFilter(django_filters.FilterSet):
    """Filter for AlertCorrelation model"""

    name = django_filters.CharFilter(lookup_expr='icontains')
    correlation_type = django_filters.CharFilter()
    status = django_filters.CharFilter()
    analyzed_after = django_filters.DateTimeFilter(field_name='last_analyzed', lookup_expr='gte')
    analyzed_before = django_filters.DateTimeFilter(field_name='last_analyzed', lookup_expr='lte')

    class Meta:
        model = AlertCorrelation
        fields = ['name', 'correlation_type', 'status']


class MTTRMetricFilter(django_filters.FilterSet):
    """Filter for MTTRMetric model"""

    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = MTTRMetric
        fields = ['name']


class MTTDMetricFilter(django_filters.FilterSet):
    """Filter for MTTDMetric model"""

    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = MTTDMetric
        fields = ['name']


class SLABreachFilter(django_filters.FilterSet):
    """Filter for SLABreach model"""

    sla_type = django_filters.CharFilter()
    severity = django_filters.ChoiceFilter(choices=SEVERITY_LEVELS)
    status = django_filters.CharFilter()
    breach_after = django_filters.DateTimeFilter(field_name='breach_time', lookup_expr='gte')
    breach_before = django_filters.DateTimeFilter(field_name='breach_time', lookup_expr='lte')

    class Meta:
        model = SLABreach
        fields = ['sla_type', 'severity', 'status']
