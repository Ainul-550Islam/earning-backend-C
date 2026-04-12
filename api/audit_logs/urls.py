"""
URL configuration for audit_logs app
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from rest_framework_nested import routers
from . import views


from .views import (
    AuditLogViewSet,
    AuditLogConfigViewSet,
    AuditLogArchiveViewSet,
    AuditDashboardViewSet,
    AuditAlertRuleViewSet,
    UserAuditLogView,
    LiveAuditView,
    AuditHealthCheckView,
)

# Create main router
router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-log')
router.register(r'configs', AuditLogConfigViewSet, basename='audit-config')
router.register(r'archives', AuditLogArchiveViewSet, basename='audit-archive')
router.register(r'dashboards', AuditDashboardViewSet, basename='audit-dashboard')
router.register(r'alert-rules', AuditAlertRuleViewSet, basename='audit-alert-rule')

# Create nested router for user-specific logs
user_router = DefaultRouter()
user_router.register(r'my-logs', UserAuditLogView, basename='user-audit-log')

# URL patterns
urlpatterns = [
    # Main API endpoints
    path('', include(router.urls)),
    
    # User-specific endpoints
#     path('users/', include(user_router.urls)),
    path('users/', views.UserAuditLogView.as_view(), name='user-audit-log'),
    
    # Special endpoints
    path('live/', LiveAuditView.as_view(), name='audit-live'),
    path('health/', AuditHealthCheckView.as_view(), name='audit-health'),
    
    # User audit log summary
    path('users/summary/', views.UserAuditLogView.as_view(), name='user-audit-summary'),
    
    # Statistics and analytics
    path('stats/', AuditLogViewSet.as_view({'get': 'stats'}), name='audit-stats'),
    path('stats/timeline/', AuditLogViewSet.as_view({'get': 'timeline'}), name='audit-timeline'),
    
    # Search endpoints
    path('search/', AuditLogViewSet.as_view({'post': 'search'}), name='audit-search'),
    
    # Export endpoints
    path('export/', AuditLogViewSet.as_view({'post': 'export'}), name='audit-export'),
    
    # Administrative endpoints
    path('purge/', AuditLogViewSet.as_view({'delete': 'purge'}), name='audit-purge'),
    
    # Dashboard preview
    path('dashboards/<uuid:pk>/preview/', 
         AuditDashboardViewSet.as_view({'get': 'preview'}), 
         name='dashboard-preview'),
    
    # Alert rule management
    path('alert-rules/<uuid:pk>/test/', 
         AuditAlertRuleViewSet.as_view({'post': 'test'}), 
         name='alert-rule-test'),
    path('alert-rules/<uuid:pk>/enable/', 
         AuditAlertRuleViewSet.as_view({'post': 'enable'}), 
         name='alert-rule-enable'),
    path('alert-rules/<uuid:pk>/disable/', 
         AuditAlertRuleViewSet.as_view({'post': 'disable'}), 
         name='alert-rule-disable'),
    path('alert-rules/triggered/', 
         AuditAlertRuleViewSet.as_view({'get': 'triggered'}), 
         name='alert-rules-triggered'),
    
    # Archive management
    path('archives/create/', 
         AuditLogArchiveViewSet.as_view({'post': 'create_archive'}), 
         name='create-archive'),
    path('archives/<uuid:pk>/download/', 
         AuditLogArchiveViewSet.as_view({'get': 'download'}), 
         name='download-archive'),
    
    # Log redaction (for GDPR/compliance)
    path('logs/<uuid:pk>/redact/', 
         AuditLogViewSet.as_view({'post': 'redact'}), 
         name='log-redact'),
]

# Add API documentation
urlpatterns += [
    path('api-docs/', include('rest_framework.urls', namespace='rest_framework')),
]

app_name = 'audit_logs'