"""
Security App URLs Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from . import views
from .views import (
    DeviceInfoViewSet, SecurityLogViewSet, RiskScoreViewSet,
    SecurityDashboardViewSet, AutoBlockRuleViewSet, FraudPatternViewSet,
    RealTimeDetectionViewSet, UserSessionViewSet, TwoFactorMethodViewSet,
    UserBanViewSet, IPBlacklistViewSet, AuditTrailViewSet,
    security_health_check, security_system_status,
    batch_resolve_security_logs, recalculate_all_risk_scores,
    export_security_data, security_error_handler,
)

# ============================================================
# ROUTER
# ============================================================

router = DefaultRouter()

router.register(r'devices',              DeviceInfoViewSet,       basename='device')
router.register(r'security-logs',        SecurityLogViewSet,      basename='security-log')
router.register(r'risk-scores',          RiskScoreViewSet,        basename='risk-score')
router.register(r'dashboards',           SecurityDashboardViewSet, basename='dashboard')
router.register(r'auto-block-rules',     AutoBlockRuleViewSet,    basename='auto-block-rule')
router.register(r'fraud-patterns',       FraudPatternViewSet,     basename='fraud-pattern')
router.register(r'real-time-detections', RealTimeDetectionViewSet, basename='real-time-detection')
router.register(r'sessions',             UserSessionViewSet,      basename='session')       # ✅ /api/security/sessions/
router.register(r'2fa',                  TwoFactorMethodViewSet,  basename='2fa')
router.register(r'bans',                 UserBanViewSet,          basename='ban')
router.register(r'ip-blacklist',         IPBlacklistViewSet,      basename='ip-blacklist')
router.register(r'audit',               AuditTrailViewSet,        basename='audit')

# ============================================================
# URL PATTERNS  ← শুধু একটাই definition, নিচে আর নেই!
# ============================================================
# Frontend expects /api/security/logs/ (security.js getLogs) — alias to SecurityLogViewSet
_logs_list_create = SecurityLogViewSet.as_view({'get': 'list', 'post': 'create'})

urlpatterns = [
    # Alias: /api/security/logs/ (ফ্রন্টএন্ডের সাথে মিল রাখার জন্য)
    path('logs/', _logs_list_create, name='logs'),
    # All router URLs (sessions, devices, security-logs, bans, ip-blacklist, etc.)
    path('', include(router.urls)),

    # Device Special Endpoints
    path('devices/<int:device_id>/blacklist/', DeviceInfoViewSet.as_view({'post': 'blacklist_device'}),     name='device-blacklist'),
    path('devices/<int:device_id>/whitelist/', DeviceInfoViewSet.as_view({'post': 'whitelist_device'}),     name='device-whitelist'),
    path('devices/<int:device_id>/trust/',     DeviceInfoViewSet.as_view({'post': 'toggle_trust'}),  name='device-trust'),
    path('devices/analytics/overview/',        DeviceInfoViewSet.as_view({'get': 'analytics'}),      name='device-analytics'),

    # Security Logs Special Endpoints
    path('security-logs/bulk/resolve/',        batch_resolve_security_logs,                           name='bulk-resolve-logs'),
    path('security-logs/<int:log_id>/resolve/', SecurityLogViewSet.as_view({'post': 'resolve'}),     name='resolve-log'),
    path('security-logs/statistics/',          SecurityLogViewSet.as_view({'get': 'statistics'}),    name='log-statistics'),
    path('security-logs/export/',              export_security_data,                                  name='export-logs'),

    # Risk Management Special Endpoints
    path('risk-scores/bulk/recalculate/',      recalculate_all_risk_scores,                           name='recalculate-all-risks'),
    path('risk-scores/<int:risk_id>/recalculate/', RiskScoreViewSet.as_view({'post': 'recalculate'}), name='recalculate-risk'),
    path('risk-scores/distribution/',          RiskScoreViewSet.as_view({'get': 'distribution'}),    name='risk-distribution'),

    # Real-time Monitoring
    path('real-time-detections/<int:detection_id>/start/', RealTimeDetectionViewSet.as_view({'post': 'start'}),     name='start-detection'),
    path('real-time-detections/<int:detection_id>/stop/',  RealTimeDetectionViewSet.as_view({'post': 'stop'}),      name='stop-detection'),
    path('real-time-detections/status/',                   RealTimeDetectionViewSet.as_view({'get': 'monitoring'}), name='detection-status'),

    # Auto-Block Rules
    path('auto-block-rules/<int:rule_id>/test/', AutoBlockRuleViewSet.as_view({'post': 'test'}),        name='test-auto-block-rule'),
    path('auto-block-rules/statistics/',         AutoBlockRuleViewSet.as_view({'get': 'statistics'}),   name='auto-block-statistics'),

    # Fraud Patterns
    path('fraud-patterns/<int:pattern_id>/test/', FraudPatternViewSet.as_view({'post': 'test'}),            name='test-fraud-pattern'),
    path('fraud-patterns/detection-report/',      FraudPatternViewSet.as_view({'get': 'detection_report'}), name='fraud-detection-report'),

    # Health & Status
    path('health/',  security_health_check,   name='security-health'),
    path('status/',  security_system_status,  name='system-status'),
    path('dashboard/', views.security_dashboard, name='security-dashboard'),
]

# DEBUG-only
if settings.DEBUG:
    urlpatterns += [
        path('debug/test-error/',   security_error_handler, name='debug-test-error'),
        path('debug/test-webhook/', security_error_handler, name='debug-test-webhook'),
    ]

# Custom Error Handlers
handler404 = 'api.security.views.security_error_handler'
handler500 = 'api.security.views.security_error_handler'
handler403 = 'api.security.views.security_error_handler'
handler400 = 'api.security.views.security_error_handler'