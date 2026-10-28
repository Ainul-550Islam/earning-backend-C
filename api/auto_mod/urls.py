from .viewsets import (
    VirtualCurrencyConfigViewSet, OfferwallOfferTypeViewSet,
    OfferwallConfigViewSet, PostbackLogViewSet, SiteApprovalViewSet,
    PerformanceReportViewSet, PaymentScheduleViewSet, OfferwallPromotionViewSet,
)
# =============================================================================
# auto_mod/urls.py
# =============================================================================

from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import BulkModerationActionView, ModerationDashboardView, SubmissionRescanView
from .viewsets import (
    AutoApprovalRuleViewSet,
    ContentSignalViewSet,
    MLModelVersionViewSet,
    ModerationAppealViewSet,
    ModerationDecisionViewSet,
    ModerationQueueViewSet,
    ModerationRuleViewSet,
    ModerationActionViewSet,
    ModerationLogViewSet,
    ContentFlagViewSet,
    AutoModerationQueueViewSet,
    ModerationStatsViewSet,
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

# New viewsets for enhanced moderation system
router.register(r"queue",       ModerationQueueViewSet,        basename="queue")
router.register(r"decisions",   ModerationDecisionViewSet,     basename="decision")
router.register(r"appeals",     ModerationAppealViewSet,       basename="appeal")
router.register(r"models",      MLModelVersionViewSet,         basename="model")
router.register(r"signals",     ContentSignalViewSet,          basename="signal")

router.register(r"compliance/rules",    ModerationRuleViewSet,         basename="moderationrule")
router.register(r"compliance/actions",  ModerationActionViewSet,       basename="moderationaction")
router.register(r"compliance/logs",     ModerationLogViewSet,          basename="moderationlog")
router.register(r"compliance/flags",    ContentFlagViewSet,            basename="contentflag")
router.register(r"compliance/autoqueue", AutoModerationQueueViewSet,   basename="automoderationqueue")
router.register(r"compliance/stats",    ModerationStatsViewSet,        basename="moderationstats")
router.register(r"virtual-currency",    VirtualCurrencyConfigViewSet,  basename="virtualcurrency")
router.register(r"offer-types",         OfferwallOfferTypeViewSet,     basename="offertype")
router.register(r"offerwall-configs",   OfferwallConfigViewSet,        basename="offerwallconfig")
router.register(r"postback-logs",       PostbackLogViewSet,            basename="postbacklog")
router.register(r"site-approvals",      SiteApprovalViewSet,           basename="siteapproval")
router.register(r"performance-reports", PerformanceReportViewSet,      basename="performancereport")
router.register(r"payment-schedules",   PaymentScheduleViewSet,        basename="paymentschedule")
router.register(r"promotions",          OfferwallPromotionViewSet,     basename="offerwallpromotion")

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
