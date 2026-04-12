# alerts/urls/core.py
from django.urls import path
from ..viewsets import core as viewsets_core

app_name = 'core'

urlpatterns = [
    # Alert Rules
    path('rules/', viewsets_core.AlertRuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-rule-list'),
    path('rules/<int:pk>/', viewsets_core.AlertRuleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-rule-detail'),
    path('rules/<int:pk>/activate/', viewsets_core.AlertRuleViewSet.as_view({'post': 'activate'}), name='alert-rule-activate'),
    path('rules/<int:pk>/deactivate/', viewsets_core.AlertRuleViewSet.as_view({'post': 'deactivate'}), name='alert-rule-deactivate'),
    path('rules/<int:pk>/test/', viewsets_core.AlertRuleViewSet.as_view({'post': 'test'}), name='alert-rule-test'),
    path('rules/<int:pk>/statistics/', viewsets_core.AlertRuleViewSet.as_view({'get': 'statistics'}), name='alert-rule-statistics'),
    
    # Alert Logs
    path('logs/', viewsets_core.AlertLogViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-log-list'),
    path('logs/<int:pk>/', viewsets_core.AlertLogViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-log-detail'),
    path('logs/<int:pk>/resolve/', viewsets_core.AlertLogViewSet.as_view({'post': 'resolve'}), name='alert-log-resolve'),
    path('logs/<int:pk>/acknowledge/', viewsets_core.AlertLogViewSet.as_view({'post': 'acknowledge'}), name='alert-log-acknowledge'),
    path('logs/by_rule/<int:rule_id>/', viewsets_core.AlertLogViewSet.as_view({'get': 'by_rule'}), name='alert-log-by-rule'),
    path('logs/pending/', viewsets_core.AlertLogViewSet.as_view({'get': 'pending'}), name='alert-log-pending'),
    path('logs/resolved/', viewsets_core.AlertLogViewSet.as_view({'get': 'resolved'}), name='alert-log-resolved'),
    path('logs/by_severity/<str:severity>/', viewsets_core.AlertLogViewSet.as_view({'get': 'by_severity'}), name='alert-log-by-severity'),
    
    # Notifications
    path('notifications/', viewsets_core.NotificationViewSet.as_view({'get': 'list', 'post': 'create'}), name='notification-list'),
    path('notifications/<int:pk>/', viewsets_core.NotificationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='notification-detail'),
    path('notifications/<int:pk>/mark_sent/', viewsets_core.NotificationViewSet.as_view({'post': 'mark_sent'}), name='notification-mark-sent'),
    path('notifications/<int:pk>/mark_failed/', viewsets_core.NotificationViewSet.as_view({'post': 'mark_failed'}), name='notification-mark-failed'),
    path('notifications/<int:pk>/retry/', viewsets_core.NotificationViewSet.as_view({'post': 'retry'}), name='notification-retry'),
    path('notifications/by_status/<str:status>/', viewsets_core.NotificationViewSet.as_view({'get': 'by_status'}), name='notification-by-status'),
    path('notifications/by_type/<str:type>/', viewsets_core.NotificationViewSet.as_view({'get': 'by_type'}), name='notification-by-type'),
    path('notifications/failed/', viewsets_core.NotificationViewSet.as_view({'get': 'failed'}), name='notification-failed'),
    
    # System Health
    path('health/', viewsets_core.SystemHealthViewSet.as_view({'get': 'list'}), name='system-health-list'),
    path('health/metrics/', viewsets_core.SystemHealthViewSet.as_view({'get': 'metrics'}), name='system-health-metrics'),
    path('health/history/', viewsets_core.SystemHealthViewSet.as_view({'get': 'history'}), name='system-health-history'),
    path('health/check/', viewsets_core.SystemHealthViewSet.as_view({'post': 'check'}), name='system-health-check'),
    path('health/rules/', viewsets_core.SystemHealthViewSet.as_view({'get': 'rules'}), name='system-health-rules'),
    path('health/channels/', viewsets_core.SystemHealthViewSet.as_view({'get': 'channels'}), name='system-health-channels'),
    path('health/incidents/', viewsets_core.SystemHealthViewSet.as_view({'get': 'incidents'}), name='system-health-incidents'),
    
    # Overview
    path('overview/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'list'}), name='alert-overview-list'),
    path('overview/summary/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'summary'}), name='alert-overview-summary'),
    path('overview/recent_alerts/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'recent_alerts'}), name='alert-overview-recent-alerts'),
    path('overview/trends/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'trends'}), name='alert-overview-trends'),
    path('overview/top_rules/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'top_rules'}), name='alert-overview-top-rules'),
    path('overview/metrics/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'metrics'}), name='alert-overview-metrics'),
    path('overview/statistics/', viewsets_core.AlertOverviewViewSet.as_view({'get': 'statistics'}), name='alert-overview-statistics'),
    
    # Maintenance
    path('maintenance/', viewsets_core.AlertMaintenanceViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-maintenance-list'),
    path('maintenance/<int:pk>/', viewsets_core.AlertMaintenanceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-maintenance-detail'),
    path('maintenance/suppress_alerts/', viewsets_core.AlertMaintenanceViewSet.as_view({'post': 'suppress_alerts'}), name='alert-maintenance-suppress-alerts'),
    path('maintenance/impact/', viewsets_core.AlertMaintenanceViewSet.as_view({'get': 'impact'}), name='alert-maintenance-impact'),
    path('maintenance/<int:pk>/extend/', viewsets_core.AlertMaintenanceViewSet.as_view({'post': 'extend'}), name='alert-maintenance-extend'),
    path('maintenance/<int:pk>/complete/', viewsets_core.AlertMaintenanceViewSet.as_view({'post': 'complete'}), name='alert-maintenance-complete'),
    path('maintenance/history/', viewsets_core.AlertMaintenanceViewSet.as_view({'get': 'history'}), name='alert-maintenance-history'),
    path('maintenance/upcoming/', viewsets_core.AlertMaintenanceViewSet.as_view({'get': 'upcoming'}), name='alert-maintenance-upcoming'),
]
