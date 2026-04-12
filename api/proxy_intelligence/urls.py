"""
Proxy Intelligence URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views

router = DefaultRouter()

# Core Detection
router.register(r'ip-intelligence',     views.IPIntelligenceViewSet,      basename='pi-ip-intelligence')
router.register(r'blacklist',           views.IPBlacklistViewSet,          basename='pi-blacklist')
router.register(r'whitelist',           views.IPWhitelistViewSet,          basename='pi-whitelist')

# Detection Logs
router.register(r'vpn-logs',            views.VPNDetectionLogViewSet,      basename='pi-vpn-log')
router.register(r'proxy-logs',          views.ProxyDetectionLogViewSet,    basename='pi-proxy-log')
router.register(r'tor-nodes',           views.TorExitNodeViewSet,          basename='pi-tor-node')
router.register(r'datacenter-ranges',   views.DatacenterIPRangeViewSet,    basename='pi-datacenter')

# Fraud
router.register(r'fraud-attempts',      views.FraudAttemptViewSet,         basename='pi-fraud-attempt')
router.register(r'user-risk-profiles',  views.UserRiskProfileViewSet,      basename='pi-risk-profile')

# Threat Intelligence
router.register(r'threat-feeds',        views.ThreatFeedProviderViewSet,   basename='pi-threat-feed')
router.register(r'malicious-ips',       views.MaliciousIPDatabaseViewSet,  basename='pi-malicious-ip')

# AI/ML
router.register(r'ml-models',           views.MLModelMetadataViewSet,      basename='pi-ml-model')
router.register(r'anomalies',           views.AnomalyDetectionLogViewSet,  basename='pi-anomaly')

# Config
router.register(r'fraud-rules',         views.FraudRuleViewSet,            basename='pi-fraud-rule')
router.register(r'alert-configs',       views.AlertConfigurationViewSet,   basename='pi-alert-config')

# Audit
router.register(r'api-logs',            views.APIRequestLogViewSet,        basename='pi-api-log')
router.register(r'audit-trail',         views.SystemAuditTrailViewSet,     basename='pi-audit-trail')

urlpatterns = [
    # Dashboard
    path('dashboard/', views.ProxyIntelligenceDashboardView.as_view(), name='pi-dashboard'),

    # Router URLs
    path('', include(router.urls)),
]

app_name = 'proxy_intelligence'
