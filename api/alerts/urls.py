# alerts/urls.py - Updated for modular viewsets
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

# Create router for viewsets
router = DefaultRouter()

# Core viewsets
router.register(r'rules', viewsets.AlertRuleViewSet, basename='alertrule')
router.register(r'logs', viewsets.AlertLogViewSet, basename='alertlog')
router.register(r'notifications', viewsets.NotificationViewSet, basename='notification')
router.register(r'health', viewsets.SystemHealthViewSet, basename='systemhealth')
router.register(r'overview', viewsets.AlertOverviewViewSet, basename='alertoverview')
router.register(r'maintenance', viewsets.AlertMaintenanceViewSet, basename='alertmaintenance')

# Threshold viewsets
router.register(r'thresholds/configs', viewsets.ThresholdConfigViewSet, basename='thresholdconfig')
router.register(r'thresholds/breaches', viewsets.ThresholdBreachViewSet, basename='thresholdbreach')
router.register(r'thresholds/adaptive', viewsets.AdaptiveThresholdViewSet, basename='adaptivethreshold')
router.register(r'thresholds/history', viewsets.ThresholdHistoryViewSet, basename='thresholdhistory')
router.register(r'thresholds/profiles', viewsets.ThresholdProfileViewSet, basename='thresholdprofile')

# Channel viewsets
router.register(r'channels', viewsets.AlertChannelViewSet, basename='alertchannel')
router.register(r'channels/routes', viewsets.ChannelRouteViewSet, basename='channelroute')
router.register(r'channels/health_logs', viewsets.ChannelHealthLogViewSet, basename='channelhealthlog')
router.register(r'channels/rate_limits', viewsets.ChannelRateLimitViewSet, basename='channelratelimit')
router.register(r'channels/recipients', viewsets.AlertRecipientViewSet, basename='alertrecipient')

# Incident viewsets
router.register(r'incidents', viewsets.IncidentViewSet, basename='incident')
router.register(r'incidents/timelines', viewsets.IncidentTimelineViewSet, basename='incidenttimeline')
router.register(r'incidents/responders', viewsets.IncidentResponderViewSet, basename='incidentresponder')
router.register(r'incidents/postmortems', viewsets.IncidentPostMortemViewSet, basename='incidentpostmortem')
router.register(r'incidents/oncall_schedules', viewsets.OnCallScheduleViewSet, basename='oncallschedule')

# Intelligence viewsets
router.register(r'intelligence/correlations', viewsets.AlertCorrelationViewSet, basename='alertcorrelation')
router.register(r'intelligence/predictions', viewsets.AlertPredictionViewSet, basename='alertprediction')
router.register(r'intelligence/anomaly_models', viewsets.AnomalyDetectionModelViewSet, basename='anomalydetectionmodel')
router.register(r'intelligence/noise_filters', viewsets.AlertNoiseViewSet, basename='alertnoise')
router.register(r'intelligence/rca', viewsets.RootCauseAnalysisViewSet, basename='rootcauseanalysis')
router.register(r'intelligence/overview', viewsets.IntelligenceIntegrationViewSet, basename='intelligenceintegration')

# Reporting viewsets
router.register(r'reports', viewsets.AlertReportViewSet, basename='alertreport')
router.register(r'reports/mttr', viewsets.MTTRMetricViewSet, basename='mttrmetric')
router.register(r'reports/mttd', viewsets.MTTDMetricViewSet, basename='mttdmetric')
router.register(r'reports/sla_breaches', viewsets.SLABreachViewSet, basename='slabreach')
router.register(r'reports/dashboard', viewsets.ReportingDashboardViewSet, basename='reportingdashboard')

# API URLs
urlpatterns = [
    # Main API endpoint
    path('', viewsets.AlertOverviewViewSet.as_view({'get': 'list'}), name='alerts-overview'),
    
    # Router URLs
    path('api/alerts/', include(router.urls)),
    
    # Legacy compatibility URLs (redirect to new viewsets)
    path('', include('alerts.urls.core')),
    path('thresholds/', include('alerts.urls.threshold')),
    path('channels/', include('alerts.urls.channel')),
    path('incidents/', include('alerts.urls.incident')),
    path('intelligence/', include('alerts.urls.intelligence')),
    path('reports/', include('alerts.urls.reporting')),
]