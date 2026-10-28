"""
Analytics serializer. DRY: uses Serializer (no model) for computed responses.
"""
from rest_framework import serializers


class MetricAnalyticsSerializer(serializers.Serializer):
    """Response serializer for metric analytics."""
    metric_name    = serializers.CharField()
    period_hours   = serializers.IntegerField()
    count          = serializers.IntegerField()
    avg            = serializers.FloatField()
    min            = serializers.FloatField()
    max            = serializers.FloatField()
    sum            = serializers.FloatField()
    std_dev        = serializers.FloatField()
    percentile_50  = serializers.FloatField()
    percentile_95  = serializers.FloatField()
    percentile_99  = serializers.FloatField()


class LogAnalyticsSerializer(serializers.Serializer):
    """Response serializer for log analytics."""
    period_hours = serializers.IntegerField()
    total_logs   = serializers.IntegerField()
    level_counts = serializers.DictField(child=serializers.IntegerField())
    error_rate   = serializers.FloatField()


class TraceAnalyticsSerializer(serializers.Serializer):
    """Response serializer for trace analytics."""
    period_hours  = serializers.IntegerField()
    total_traces  = serializers.IntegerField()
    status_counts = serializers.DictField(child=serializers.IntegerField())
    error_rate    = serializers.FloatField()
    avg_duration_ms = serializers.FloatField()


class AlertAnalyticsSerializer(serializers.Serializer):
    """Response serializer for alert analytics."""
    period_hours     = serializers.IntegerField()
    total_alerts     = serializers.IntegerField()
    severity_counts  = serializers.DictField(child=serializers.IntegerField())
    status_counts    = serializers.DictField(child=serializers.IntegerField())
    resolution_rate  = serializers.FloatField()


class HealthAnalyticsSerializer(serializers.Serializer):
    """Response serializer for health analytics."""
    total_services   = serializers.IntegerField()
    status_counts    = serializers.DictField(child=serializers.IntegerField())
    avg_health_score = serializers.FloatField()
    health_percentage = serializers.FloatField()


class ServiceAnalyticsSerializer(serializers.Serializer):
    """Response serializer for per-service analytics."""
    service_name    = serializers.CharField()
    period_hours    = serializers.IntegerField()
    metric_count    = serializers.IntegerField()
    log_count       = serializers.IntegerField()
    error_log_count = serializers.IntegerField()
    error_rate      = serializers.FloatField()
    trace_count     = serializers.IntegerField()
    avg_duration_ms = serializers.FloatField()
    alert_count     = serializers.IntegerField()
    health_status   = serializers.CharField()
    health_score    = serializers.IntegerField()


class TrendDataPointSerializer(serializers.Serializer):
    """Single time-series data point."""
    time_period = serializers.DateTimeField()
    avg_value   = serializers.FloatField()
    count       = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer):
    """Response for the /analytics/overview/ endpoint."""
    period_hours    = serializers.IntegerField()
    total_metrics   = serializers.IntegerField()
    total_logs      = serializers.IntegerField()
    total_traces    = serializers.IntegerField()
    total_alerts    = serializers.IntegerField()
    open_alerts     = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    healthy_services   = serializers.IntegerField()
    unhealthy_services = serializers.IntegerField()
    avg_health_score   = serializers.FloatField()
