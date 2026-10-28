"""
Serializers for Telemetry Observability.
All serializers inherit from BaseSerializer (DRY: created_at/updated_at defined once).
"""
from .base_serializer import BaseSerializer
from .metric_serializer import (
    MetricEventSerializer, MetricEventCreateSerializer,
    MetricEventListSerializer, MetricStatisticsSerializer,
    MetricBatchCreateSerializer,
)
from .log_serializer import (
    LogEntrySerializer, LogEntryCreateSerializer, LogBatchCreateSerializer,
)
from .trace_serializer import (
    TraceSpanSerializer, TraceSpanCreateSerializer,
    TraceSpanFinishSerializer, TraceBatchCreateSerializer,
)
from .alert_serializer import (
    AlertSerializer, AlertCreateSerializer,
    AlertAcknowledgeSerializer, AlertStatisticsSerializer, AlertBatchCreateSerializer,
)
from .health_serializer import HealthStatusSerializer, HealthStatusCreateSerializer
from .dashboard_serializer import (
    DashboardWidgetSerializer, DashboardWidgetCreateSerializer, DashboardWidgetUpdateSerializer,
)
from .analytics_serializer import (
    MetricAnalyticsSerializer, LogAnalyticsSerializer, TraceAnalyticsSerializer,
    AlertAnalyticsSerializer, HealthAnalyticsSerializer, ServiceAnalyticsSerializer,
    TrendDataPointSerializer, OverviewSerializer,
)

__all__ = [
    'BaseSerializer',
    'MetricEventSerializer', 'MetricEventCreateSerializer',
    'MetricEventListSerializer', 'MetricStatisticsSerializer', 'MetricBatchCreateSerializer',
    'LogEntrySerializer', 'LogEntryCreateSerializer', 'LogBatchCreateSerializer',
    'TraceSpanSerializer', 'TraceSpanCreateSerializer',
    'TraceSpanFinishSerializer', 'TraceBatchCreateSerializer',
    'AlertSerializer', 'AlertCreateSerializer',
    'AlertAcknowledgeSerializer', 'AlertStatisticsSerializer', 'AlertBatchCreateSerializer',
    'HealthStatusSerializer', 'HealthStatusCreateSerializer',
    'DashboardWidgetSerializer', 'DashboardWidgetCreateSerializer', 'DashboardWidgetUpdateSerializer',
    'MetricAnalyticsSerializer', 'LogAnalyticsSerializer', 'TraceAnalyticsSerializer',
    'AlertAnalyticsSerializer', 'HealthAnalyticsSerializer', 'ServiceAnalyticsSerializer',
    'TrendDataPointSerializer', 'OverviewSerializer',
]
