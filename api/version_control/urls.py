# =============================================================================
# version_control/urls.py
# =============================================================================
"""
URL configuration for version_control.

Mount under project urls.py:
    path("api/version/", include("api.version_control.urls")),

All endpoints:
    GET  /api/version/check/                          → public version check
    GET  /api/version/maintenance-status/             → public maintenance banner
    POST /api/version/policies/<pk>/activate/         → activate draft policy
    POST /api/version/maintenance/<pk>/start/         → start maintenance
    POST /api/version/webhook/deploy/                 → CI/CD deploy hook

    GET  /api/version/check/     (ViewSet list)
    GET  /api/version/policies/
    POST /api/version/policies/
    ...
    GET  /api/version/maintenance/
    POST /api/version/maintenance/
    GET  /api/version/maintenance/status/
    GET  /api/version/redirects/
    GET  /api/version/redirects/resolve/
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    ActivatePolicyView,
    DeployWebhookView,
    PublicMaintenanceStatusView,
    PublicVersionCheckView,
    StartMaintenanceView,
)
from .viewsets import (
    AppUpdatePolicyViewSet,
    MaintenanceScheduleViewSet,
    PlatformRedirectViewSet,
    VersionCheckViewSet,
)

app_name = "version_control"

router = DefaultRouter(trailing_slash=True)
router.register(r"check",       VersionCheckViewSet,        basename="version-check")
router.register(r"policies",    AppUpdatePolicyViewSet,     basename="policy")
router.register(r"maintenance", MaintenanceScheduleViewSet, basename="maintenance")
router.register(r"redirects",   PlatformRedirectViewSet,    basename="redirect")

urlpatterns = [
    path("", include(router.urls)),

    # Public views
    path("version-check/",
         PublicVersionCheckView.as_view(),
         name="public-version-check"),

    path("maintenance-status/",
         PublicMaintenanceStatusView.as_view(),
         name="public-maintenance-status"),

    # Staff views
    path("policies/<str:pk>/activate/",
         ActivatePolicyView.as_view(),
         name="activate-policy"),

    path("maintenance/<str:pk>/start/",
         StartMaintenanceView.as_view(),
         name="start-maintenance"),

    # Webhook
    path("webhook/deploy/",
         DeployWebhookView.as_view(),
         name="deploy-webhook"),
]
