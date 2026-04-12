# =============================================================================
# auto_mod/urls.py
# =============================================================================

from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import BulkModerationActionView, ModerationDashboardView, SubmissionRescanView
from .viewsets import (
    AutoApprovalRuleViewSet,
    ProofScannerViewSet,
    SuspiciousSubmissionViewSet,
    TaskBotViewSet,
)

app_name = "auto_mod"

router = DefaultRouter(trailing_slash=True)
router.register(r"rules",       AutoApprovalRuleViewSet,      basename="rule")
router.register(r"submissions", SuspiciousSubmissionViewSet,  basename="submission")
router.register(r"scans",       ProofScannerViewSet,          basename="scan")
router.register(r"bots",        TaskBotViewSet,               basename="bot")

urlpatterns = [
    path("", include(router.urls)),

    path("dashboard/",
         ModerationDashboardView.as_view(),
         name="dashboard"),

    path("submissions/<str:pk>/rescan/",
         SubmissionRescanView.as_view(),
         name="submission-rescan"),

    path("submissions/bulk-action/",
         BulkModerationActionView.as_view(),
         name="bulk-action"),
]
