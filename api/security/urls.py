"""
Security URLs Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings

from .views import (
    DeviceInfoViewSet, SecurityLogViewSet, RiskScoreViewSet,
    SecurityDashboardViewSet, AutoBlockRuleViewSet, FraudPatternViewSet,
    RealTimeDetectionViewSet, UserBanViewSet, IPBlacklistViewSet,
    AuditTrailViewSet, ThreatIntelligenceViewSet, SecurityIncidentViewSet,
    TrustedDeviceViewSet, PasswordHistoryViewSet, SecurityPolicyViewSet,
    SecurityInsightViewSet, ClickTrackerViewSet, EnhancedClickTrackerViewSet,
    CountryViewSet, GeolocationViewSet, CountryBlockRuleViewSet,
    APIRateLimitViewSet, PasswordPolicyViewSet,
    security_health_check, security_system_status,
    batch_resolve_security_logs, recalculate_all_risk_scores,
    export_security_data, security_error_handler, security_dashboard,
)

# Try to import optional viewsets
try:
    from .views import (
        UserSessionViewSet, TwoFactorMethodViewSet,
        SelfPagination as RiskScoreViewSet2,
    )
    _has_session = True
except ImportError:
    _has_session = False

# Stub for missing user_security_info
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_security_info(request):
    return Response({"user": request.user.username, "status": "ok"})

router = DefaultRouter()
router.register(r"devices", DeviceInfoViewSet, basename="device")
router.register(r"security-logs", SecurityLogViewSet, basename="security-log")
router.register(r"risk-scores", RiskScoreViewSet, basename="risk-score")
router.register(r"dashboards", SecurityDashboardViewSet, basename="dashboard")
router.register(r"auto-block-rules", AutoBlockRuleViewSet, basename="auto-block-rule")
router.register(r"fraud-patterns", FraudPatternViewSet, basename="fraud-pattern")
router.register(r"real-time-detections", RealTimeDetectionViewSet, basename="real-time-detection")
router.register(r"user-bans", UserBanViewSet, basename="user-ban")
router.register(r"ip-blacklist", IPBlacklistViewSet, basename="ip-blacklist")
router.register(r"audit-trails", AuditTrailViewSet, basename="audit-trail")
router.register(r"threat-intelligence", ThreatIntelligenceViewSet, basename="threat-intelligence")
router.register(r"security-incidents", SecurityIncidentViewSet, basename="security-incident")
router.register(r"trusted-devices", TrustedDeviceViewSet, basename="trusted-device")
router.register(r"password-history", PasswordHistoryViewSet, basename="password-history")
router.register(r"security-policies", SecurityPolicyViewSet, basename="security-policy")
router.register(r"security-insights", SecurityInsightViewSet, basename="security-insight")
router.register(r"click-trackers", ClickTrackerViewSet, basename="click-tracker")
router.register(r"enhanced-click-trackers", EnhancedClickTrackerViewSet, basename="enhanced-click-tracker")
router.register(r"countries", CountryViewSet, basename="country")
router.register(r"geolocation-logs", GeolocationViewSet, basename="geolocation-log")
router.register(r"country-block-rules", CountryBlockRuleViewSet, basename="country-block-rule")
router.register(r"api-rate-limits", APIRateLimitViewSet, basename="api-rate-limit")
router.register(r"password-policies", PasswordPolicyViewSet, basename="password-policy")

if _has_session:
    router.register(r"sessions", UserSessionViewSet, basename="session")
    router.register(r"2fa-methods", TwoFactorMethodViewSet, basename="2fa-method")

urlpatterns = [
    path("", include(router.urls)),
    path("v2/", include(router.urls)),
    path("health/", security_health_check, name="security-health"),
    path("status/", security_system_status, name="security-status"),
    path("dashboard/", security_dashboard, name="security-dashboard"),
    path("user/security-info/", user_security_info, name="user-security-info"),
    path("bulk/resolve-logs/", batch_resolve_security_logs, name="bulk-resolve-logs"),
    path("bulk/recalculate-risks/", recalculate_all_risk_scores, name="recalculate-risks"),
    path("export/", export_security_data, name="export-security-data"),
]

handler404 = "api.security.views.security_error_handler"
handler500 = "api.security.views.security_error_handler"