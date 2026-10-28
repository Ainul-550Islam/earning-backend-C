"""
alerts/viewsets/__init__.py
UPDATED: added integration viewsets (16 new ViewSets covering
the entire integration/ subfolder that was previously floating).
"""
from .core import (
    AlertRuleViewSet, AlertLogViewSet, NotificationViewSet, SystemHealthViewSet,
    AlertOverviewViewSet, AlertMaintenanceViewSet,
)
from .threshold import (
    ThresholdConfigViewSet, ThresholdBreachViewSet, AdaptiveThresholdViewSet,
    ThresholdHistoryViewSet, ThresholdProfileViewSet,
)
from .channel import (
    AlertChannelViewSet, ChannelRouteViewSet, ChannelHealthLogViewSet,
    ChannelRateLimitViewSet, AlertRecipientViewSet,
)
from .incident import (
    IncidentViewSet, IncidentTimelineViewSet, IncidentResponderViewSet,
    IncidentPostMortemViewSet, OnCallScheduleViewSet,
)
from .intelligence import (
    AlertCorrelationViewSet, AlertPredictionViewSet, AnomalyDetectionModelViewSet,
    AlertNoiseViewSet, RootCauseAnalysisViewSet, IntelligenceIntegrationViewSet,
)
from .reporting import (
    AlertReportViewSet, MTTRMetricViewSet, MTTDMetricViewSet,
    SLABreachViewSet, ReportingDashboardViewSet,
)

# ── Integration ViewSets (NEWLY ADDED) ────────────────────────────
from .integration import (
    CircuitBreakerViewSet,
    IntegrationHealthViewSet,
    IntegrationRegistryViewSet,
    AuditLogViewSet,
    PerformanceMonitorViewSet,
    MessageQueueViewSet,
    WebhookIntegrationViewSet,
    SyncManagerViewSet,
    VersioningViewSet,
    TransformerViewSet,
    IntegrationBridgeViewSet,
    EventBusViewSet,
    DataValidatorViewSet,
    AuthBridgeViewSet,
    FallbackLogicViewSet,
    IntegrationHandlerViewSet,
)

__all__ = [
    # Core
    'AlertRuleViewSet', 'AlertLogViewSet', 'NotificationViewSet',
    'SystemHealthViewSet', 'AlertOverviewViewSet', 'AlertMaintenanceViewSet',

    # Threshold
    'ThresholdConfigViewSet', 'ThresholdBreachViewSet', 'AdaptiveThresholdViewSet',
    'ThresholdHistoryViewSet', 'ThresholdProfileViewSet',

    # Channel
    'AlertChannelViewSet', 'ChannelRouteViewSet', 'ChannelHealthLogViewSet',
    'ChannelRateLimitViewSet', 'AlertRecipientViewSet',

    # Incident
    'IncidentViewSet', 'IncidentTimelineViewSet', 'IncidentResponderViewSet',
    'IncidentPostMortemViewSet', 'OnCallScheduleViewSet',

    # Intelligence
    'AlertCorrelationViewSet', 'AlertPredictionViewSet', 'AnomalyDetectionModelViewSet',
    'AlertNoiseViewSet', 'RootCauseAnalysisViewSet', 'IntelligenceIntegrationViewSet',

    # Reporting
    'AlertReportViewSet', 'MTTRMetricViewSet', 'MTTDMetricViewSet',
    'SLABreachViewSet', 'ReportingDashboardViewSet',

    # Integration (16 new ViewSets)
    'CircuitBreakerViewSet', 'IntegrationHealthViewSet', 'IntegrationRegistryViewSet',
    'AuditLogViewSet', 'PerformanceMonitorViewSet', 'MessageQueueViewSet',
    'WebhookIntegrationViewSet', 'SyncManagerViewSet', 'VersioningViewSet',
    'TransformerViewSet', 'IntegrationBridgeViewSet', 'EventBusViewSet',
    'DataValidatorViewSet', 'AuthBridgeViewSet', 'FallbackLogicViewSet',
    'IntegrationHandlerViewSet',
]
