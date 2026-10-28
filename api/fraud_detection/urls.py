# =============================================================================
# fraud_detection/urls.py — SINGLE MASTER URL FILE  (DRY)
#
# Replaces ALL of:
#   urls.py (old)              161 routes — DELETED
#   urls_final_complete.py     494 routes — DELETED
#   urls_all_floating_fixed.py  70 routes — DELETED
#   urls_business.py            29 routes — DELETED
#   urls_subfolder_final.py     58 routes — DELETED
#
# Structure:
#   1. Router  — ViewSet CRUD (one registration per ViewSet, ONCE)
#   2. Detect  — fraud detection check endpoints
#   3. Auto-Ban / Review / Dashboard / Stats
#   4. Extended ViewSet actions (extra @action routes)
#   5. Case Services / Insights / Notifications
#   6. Sub-module includes:
#        security/urls_security.py  → security/*
#        detectors/urls.py          → detectors/*   [NEW]
#        services/urls.py           → services/*    [NEW]
#        INTEGRATION_SYSTEM/urls.py → integration/* [NEW]
#   7. Analytics / Monitoring / Compliance / Data-Export
#   8. Tasks / Signals / WebSocket / Business / Misc
#   9. router.urls (catch-all, always LAST)
# =============================================================================
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views
from .viewset                        import FraudCaseViewSet
from .views_extended                 import (
    FraudPatternViewSet,
    DeviceFingerprintViewSet,
    IPReputationViewSet,
    OfferCompletionViewSet,
    FraudSettingsViewSet,
    FraudCaseEvidenceViewSet,
    FraudCaseActionViewSet,
    FraudWhitelistViewSet,
    FraudNotificationViewSet,
)
from .views_analytics                import (
    FraudAnalyticsAPIView,
    GeographicAnalysisAPIView,
    RiskTimelineAPIView,
    AnalyticsDashboardAPIView,
    ExportAnalyticsAPIView,
)
from .views_services                 import (
    AutoBanServiceStatsAPIView,
    AutoBanServiceValidateConfigAPIView,
    AutoBanServiceBulkFraudAPIView,
    AutoBanServiceUnbanScheduledAPIView,
    ReviewServiceBatchAPIView,
    ReviewServiceStatsAPIView,
    FraudCaseServiceCreateAPIView,
    FraudCaseServiceStatusAPIView,
    FraudCaseServiceEvidenceAPIView,
    FraudCaseServiceActionAPIView,
    FraudCaseServiceDetailAPIView,
    FraudCaseServiceUserCasesAPIView,
    FraudCaseServiceBulkUpdateAPIView,
    FraudInsightOverviewAPIView,
    FraudInsightTrendsAPIView,
    FraudInsightRiskFactorsAPIView,
    IPReputationServiceCheckAPIView,
    IPReputationServiceBulkAPIView,
    IPReputationServiceStatsAPIView,
    WhitelistServiceAddAPIView,
    WhitelistServiceRemoveAPIView,
    WhitelistServiceCheckAPIView,
)
from .views_monitoring               import (
    SystemHealthAPIView,
    IntegrityVerificationAPIView,
    MonitoringMetricsAPIView,
    PerformanceSummaryAPIView,
)
from .views_notification_service     import (
    NotificationServiceSendAPIView,
    NotificationServiceBulkAPIView,
    NotificationServiceStatsAPIView,
)
from .views_missing                  import (
    fraud_statistics,
    quick_fraud_check,
)
from .views_compliance               import (
    ComplianceReportAPIView,
    ComplianceStatusAPIView,
    SanctionsCheckAPIView,
    SanctionsScreeningAPIView,
)
from .views_data_export              import (
    DataExportCreateAPIView,
    DataExportDownloadAPIView,
    DataExportListAPIView,
)
from .views_tasks                    import (
    TriggerFraudScanAPIView,
    TriggerBatchRiskAPIView,
    TaskStatusAPIView,
    CapitalTaskSubmitAPIView,
)
from .views_signals_monitor          import (
    SignalEventLogAPIView,
    SignalEventStatsAPIView,
)
from .views_search                   import (
    FraudSearchAPIView,
    FraudSearchSuggestAPIView,
)
from .views_caching                  import (
    CacheWarmupAPIView,
    CacheStatsAPIView,
    CacheInvalidateAPIView,
)
from .views_plugins_registry         import (
    PluginListAPIView,
    PluginActivateAPIView,
    PluginDeactivateAPIView,
    RegistryComponentsAPIView,
)
from .views_factories                import (
    FraudAttemptFactoryAPIView,
    FraudCaseFactoryAPIView,
)
from .views_interactors              import (
    FraudDetectionInteractorView,
    FraudCaseInteractorView,
    RiskProfileInteractorView,
    RepositoryStatsView,
    RepositoryQueryView,
)

from .views_repositories             import (
    RepositoryStatsAPIView,
    RepositoryQueryAPIView,
)
from .views_detectors                import (
    DetectorRunAPIView,
    DetectorListAPIView,
    DetectorStatusAPIView,
    DetectorBatchAPIView,
    DetectorMetricsAPIView,
)
from .views_business                 import (
    BusinessRuleListAPIView,
    BusinessRuleEvaluateAPIView,
    BusinessRuleCreateAPIView,
    BusinessRuleToggleAPIView,
)
from .views_integration_bridge       import (
    IntegrationBridgeStatusAPIView,
    IntegrationBridgeSyncAPIView,
    IntegrationBridgeHealthAPIView,
)
from .views_integration_advanced     import (
    IntegrationEventListAPIView,
    IntegrationEventPublishAPIView,
    IntegrationCircuitBreakerAPIView,
)
from .views_use_cases                import (
    UseCaseRunAPIView,
    UseCaseListAPIView,
)

from .views_management               import (
    ManagementCommandAPIView,
    SystemMaintenanceAPIView,
)
from .views_push_notifications       import (
    PushNotificationSendAPIView,
    PushNotificationBulkAPIView,
    PushNotificationStatusAPIView,
)
from .views_offerwall_v2             import (
    OfferwallFraudCheckAPIView,
    OfferwallBatchCheckAPIView,
    OfferwallAnalyticsAPIView,
)
from .attachment_upload_view         import AttachmentUploadAPIView
from .views_ai_enrichment            import AIFraudAnalysisView, AIBulkEnrichmentView
from .views_extended                 import (
    FraudPatternViewSet,
    DeviceFingerprintViewSet,
    IPReputationViewSet,
    OfferCompletionViewSet,
    FraudSettingsViewSet,
)


# =============================================================================
# ROUTER — each ViewSet registered EXACTLY ONCE
# =============================================================================
router = SimpleRouter()
router.register(r"rules",             views.FraudRuleViewSet,       basename="fraud-rule")
router.register(r"attempts",          views.FraudAttemptViewSet,    basename="fraud-attempt")
router.register(r"risk-profiles",     views.UserRiskProfileViewSet,  basename="risk-profile")
router.register(r"alerts",            views.FraudAlertViewSet,       basename="fraud-alert")
router.register(r"patterns",          FraudPatternViewSet,           basename="fraud-pattern")
router.register(r"devices",           DeviceFingerprintViewSet,      basename="device-fingerprint")
router.register(r"ip-reputation",     IPReputationViewSet,           basename="ip-reputation")
router.register(r"offer-completions", OfferCompletionViewSet,        basename="offer-completion")
router.register(r"settings",          FraudSettingsViewSet,          basename="fraud-settings")
router.register(r"cases",             FraudCaseViewSet,              basename="fraud-case")
router.register(r"evidence",          FraudCaseEvidenceViewSet,      basename="fraud-case-evidence")
router.register(r"actions",           FraudCaseActionViewSet,        basename="fraud-case-action")
router.register(r"whitelist",         FraudWhitelistViewSet,         basename="fraud-whitelist")
router.register(r"notifications",     FraudNotificationViewSet,      basename="fraud-notification")


# =============================================================================
# EXPLICIT PATHS — must be before router.urls to avoid pk/ shadowing
# =============================================================================
urlpatterns = [

    # ── 1. FRAUD DETECTION ────────────────────────────────────────────────────
    path("detect/check-user/",        views.FraudDetectionAPIView.as_view(), name="fraud-detect-check-user"),
    path("detect/check-transaction/", views.FraudDetectionAPIView.as_view(),
         kwargs={"action": "check_transaction"}, name="fraud-detect-check-transaction"),
    path("detect/check-offer/",       views.FraudDetectionAPIView.as_view(),
         kwargs={"action": "check_offer"},       name="fraud-detect-check-offer"),
    path("detect/check-device/",      views.FraudDetectionAPIView.as_view(),
         kwargs={"action": "check_device"},      name="fraud-detect-check-device"),

    # ── 2. AUTO-BAN ───────────────────────────────────────────────────────────
    path("auto-ban/process-attempt/", views.AutoBanAPIView.as_view(),
         kwargs={"action": "process_attempt"}, name="auto-ban-process-attempt"),
    path("auto-ban/ban-user/",        views.AutoBanAPIView.as_view(),
         kwargs={"action": "ban_user"},         name="auto-ban-user"),
    path("auto-ban/suspend-user/",    views.AutoBanAPIView.as_view(),
         kwargs={"action": "suspend_user"},     name="auto-ban-suspend-user"),
    path("auto-ban/restrict-user/",   views.AutoBanAPIView.as_view(),
         kwargs={"action": "restrict_user"},    name="auto-ban-restrict-user"),
    path("auto-ban/unban-users/",     views.AutoBanAPIView.as_view(),
         kwargs={"action": "unban_users"},      name="auto-ban-unban-users"),
    path("auto-ban/service/stats/",           AutoBanServiceStatsAPIView.as_view(),          name="auto-ban-service-stats"),
    path("auto-ban/service/validate-config/", AutoBanServiceValidateConfigAPIView.as_view(), name="auto-ban-service-validate-config"),
    path("auto-ban/service/process-bulk/",    AutoBanServiceBulkFraudAPIView.as_view(),      name="auto-ban-service-process-bulk"),
    path("auto-ban/service/check-unban/",     AutoBanServiceUnbanScheduledAPIView.as_view(), name="auto-ban-service-check-unban"),

    # ── 3. REVIEW ─────────────────────────────────────────────────────────────
    path("review/pending/",               views.ReviewAPIView.as_view(), kwargs={"action": "pending"},  name="review-pending"),
    path("review/case/<uuid:attempt_id>/",views.ReviewAPIView.as_view(), kwargs={"action": "case"},    name="review-case"),
    path("review/stats/",                 views.ReviewAPIView.as_view(), kwargs={"action": "stats"},    name="review-stats"),
    path("review/decide/",                views.ReviewAPIView.as_view(), kwargs={"action": "decide"},   name="review-decide"),
    path("review/escalate/",              views.ReviewAPIView.as_view(), kwargs={"action": "escalate"}, name="review-escalate"),
    path("review/comment/",               views.ReviewAPIView.as_view(), kwargs={"action": "comment"},  name="review-comment"),
    path("review/batch/",                 views.ReviewAPIView.as_view(), kwargs={"action": "batch"},    name="review-batch"),
    path("review/service/batch/", ReviewServiceBatchAPIView.as_view(), name="review-service-batch"),
    path("review/service/stats/", ReviewServiceStatsAPIView.as_view(), name="review-service-stats"),

    # ── 4. DASHBOARD / STATISTICS ─────────────────────────────────────────────
    path("dashboard/",          views.FraudDashboardAPIView.as_view(), name="fraud-dashboard"),
    path("statistics/",         fraud_statistics,                      name="fraud-statistics"),
    path("quick-check/",        quick_fraud_check,                     name="fraud-quick-check"),
    path("settings/block-vpn/", views.FraudSettingsAPIView.as_view(),  name="fraud-settings-block-vpn"),

    # ── 5. EXTENDED VIEWSET ACTIONS ───────────────────────────────────────────
    path("rules/types/",                views.FraudRuleViewSet.as_view({"get": "types"}),                    name="fraud-rule-types"),
    path("rules/stats/",                views.FraudRuleViewSet.as_view({"get": "stats"}),                    name="fraud-rule-stats"),
    path("attempts/statistics/",        views.FraudAttemptViewSet.as_view({"get": "statistics"}),            name="fraud-attempts-statistics"),
    path("attempts/bulk-update/",       views.FraudAttemptViewSet.as_view({"post": "bulk_update"}),          name="fraud-attempts-bulk-update"),
    path("risk-profiles/high-risk/",    views.UserRiskProfileViewSet.as_view({"get": "high_risk_users"}),    name="risk-profiles-high-risk"),
    path("risk-profiles/distribution/", views.UserRiskProfileViewSet.as_view({"get": "risk_distribution"}), name="risk-profiles-distribution"),
    path("alerts/dashboard-stats/",     views.FraudAlertViewSet.as_view({"get": "dashboard_stats"}),        name="alerts-dashboard-stats"),
    path("alerts/bulk-resolve/",        views.FraudAlertViewSet.as_view({"post": "bulk_resolve"}),          name="alerts-bulk-resolve"),
    path("patterns/accuracy/",          FraudPatternViewSet.as_view({"get": "accuracy_stats"}),             name="fraud-patterns-accuracy"),
    path("devices/suspicious/",         DeviceFingerprintViewSet.as_view({"get": "suspicious_devices"}),    name="devices-suspicious"),
    path("devices/bulk-verify/",        DeviceFingerprintViewSet.as_view({"post": "bulk_verify"}),          name="devices-bulk-verify"),
    path("ip-reputation/bulk-check/",   IPReputationViewSet.as_view({"post": "bulk_check"}),                name="ip-reputation-bulk-check"),
    path("ip-reputation/blacklist/",    IPReputationViewSet.as_view({"post": "bulk_blacklist"}),            name="ip-reputation-bulk-blacklist"),
    path("offer-completions/fraud/",    OfferCompletionViewSet.as_view({"get": "fraud_analysis"}),          name="offer-completions-fraud"),
    path("cases/timeline/",             FraudCaseViewSet.as_view({"get": "timeline"}),                      name="fraud-cases-timeline"),
    path("cases/bulk-close/",           FraudCaseViewSet.as_view({"post": "bulk_close"}),                   name="fraud-cases-bulk-close"),
    path("evidence/bulk-upload/",       FraudCaseEvidenceViewSet.as_view({"post": "bulk_upload"}),          name="evidence-bulk-upload"),
    path("actions/bulk-create/",        FraudCaseActionViewSet.as_view({"post": "bulk_create"}),            name="actions-bulk-create"),
    path("whitelist/bulk-add/",         FraudWhitelistViewSet.as_view({"post": "bulk_add"}),                name="whitelist-bulk-add"),
    path("notifications/bulk-send/",    FraudNotificationViewSet.as_view({"post": "bulk_send"}),            name="notifications-bulk-send"),

    # ── 6. CASE SERVICES ─────────────────────────────────────────────────────
    path("cases/service/create/",                    FraudCaseServiceCreateAPIView.as_view(),     name="case-service-create"),
    path("cases/service/<int:case_id>/status/",      FraudCaseServiceStatusAPIView.as_view(),     name="case-service-status"),
    path("cases/service/<int:case_id>/evidence/",    FraudCaseServiceEvidenceAPIView.as_view(),   name="case-service-evidence"),
    path("cases/service/<int:case_id>/action/",      FraudCaseServiceActionAPIView.as_view(),     name="case-service-action"),
    path("cases/service/<int:case_id>/detail/",      FraudCaseServiceDetailAPIView.as_view(),     name="case-service-detail"),
    path("cases/service/user/<int:user_id>/",        FraudCaseServiceUserCasesAPIView.as_view(),  name="case-service-user-cases"),
    path("cases/service/bulk-update/",               FraudCaseServiceBulkUpdateAPIView.as_view(), name="case-service-bulk-update"),

    # ── 7. INSIGHTS ───────────────────────────────────────────────────────────
    path("insights/overview/",     FraudInsightOverviewAPIView.as_view(),    name="insight-overview"),
    path("insights/trends/",       FraudInsightTrendsAPIView.as_view(),      name="insight-trends"),
    path("insights/risk-factors/", FraudInsightRiskFactorsAPIView.as_view(), name="insight-risk-factors"),

    # ── 8. IP REPUTATION SERVICE ──────────────────────────────────────────────
    path("ip-reputation/service/check/",  IPReputationServiceCheckAPIView.as_view(), name="ip-rep-service-check"),
    path("ip-reputation/service/bulk/",   IPReputationServiceBulkAPIView.as_view(),  name="ip-rep-service-bulk"),
    path("ip-reputation/service/stats/",  IPReputationServiceStatsAPIView.as_view(), name="ip-rep-service-stats"),

    # ── 9. WHITELIST SERVICE ──────────────────────────────────────────────────
    path("whitelist/service/add/",    WhitelistServiceAddAPIView.as_view(),    name="whitelist-service-add"),
    path("whitelist/service/remove/", WhitelistServiceRemoveAPIView.as_view(), name="whitelist-service-remove"),
    path("whitelist/service/check/",  WhitelistServiceCheckAPIView.as_view(),  name="whitelist-service-check"),

    # ── 10. ANALYTICS ─────────────────────────────────────────────────────────
    path("analytics/real-time/",     FraudAnalyticsAPIView.as_view(),      name="fraud-analytics-real-time"),
    path("analytics/geographic/",    GeographicAnalysisAPIView.as_view(),  name="fraud-analytics-geographic"),
    path("analytics/risk-timeline/", RiskTimelineAPIView.as_view(),        name="fraud-analytics-risk-timeline"),
    path("analytics/dashboard/",     AnalyticsDashboardAPIView.as_view(),  name="fraud-analytics-dashboard"),
    path("analytics/export/",        ExportAnalyticsAPIView.as_view(),     name="fraud-analytics-export"),

    # ── 11. MONITORING / INTEGRITY ────────────────────────────────────────────
    path("monitoring/system-health/",         SystemHealthAPIView.as_view(),          name="fraud-monitoring-system-health"),
    path("monitoring/metrics/",               MonitoringMetricsAPIView.as_view(),     name="fraud-monitoring-metrics"),
    path("monitoring/performance-summary/",   PerformanceSummaryAPIView.as_view(),    name="fraud-monitoring-performance"),
    path("integrity/verify-all/",             IntegrityVerificationAPIView.as_view(), name="fraud-integrity-verify-all"),
    path("integrity/verify/<uuid:case_id>/",  IntegrityVerificationAPIView.as_view(), name="fraud-integrity-verify-case"),

    # ── 12. NOTIFICATIONS SERVICE ─────────────────────────────────────────────
    path("notifications/service/send/",  NotificationServiceSendAPIView.as_view(),  name="notification-service-send"),
    path("notifications/service/bulk/",  NotificationServiceBulkAPIView.as_view(),  name="notification-service-bulk"),
    path("notifications/service/stats/", NotificationServiceStatsAPIView.as_view(), name="notification-service-stats"),

    # ── 13. PUSH NOTIFICATIONS ────────────────────────────────────────────────
    path("push/send/",   PushNotificationSendAPIView.as_view(),   name="push-send"),
    path("push/bulk/",   PushNotificationBulkAPIView.as_view(),   name="push-bulk"),
    path("push/status/", PushNotificationStatusAPIView.as_view(), name="push-status"),

    # ── 14. COMPLIANCE / SANCTIONS ────────────────────────────────────────────
    path("compliance/report/",      ComplianceReportAPIView.as_view(),   name="compliance-report"),
    path("compliance/status/",      ComplianceStatusAPIView.as_view(),   name="compliance-status"),
    path("sanctions/check/",        SanctionsCheckAPIView.as_view(),     name="sanctions-check"),
    path("sanctions/screen/",       SanctionsScreeningAPIView.as_view(), name="sanctions-screen"),

    # ── 15. DATA EXPORT ───────────────────────────────────────────────────────
    path("data-export/create/",             DataExportCreateAPIView.as_view(),   name="data-export-create"),
    path("data-export/download/<int:pk>/",  DataExportDownloadAPIView.as_view(), name="data-export-download"),
    path("data-export/list/",               DataExportListAPIView.as_view(),     name="data-export-list"),

    # ── 16. TASKS (async trigger) ─────────────────────────────────────────────
    path("tasks/fraud-scan/trigger/",  TriggerFraudScanAPIView.as_view(),   name="task-trigger-fraud-scan"),
    path("tasks/batch-risk/trigger/",  TriggerBatchRiskAPIView.as_view(),   name="task-trigger-batch-risk"),
    path("tasks/<str:task_id>/status/",TaskStatusAPIView.as_view(),         name="task-status"),
    path("tasks/capital/submit/",      CapitalTaskSubmitAPIView.as_view(),  name="task-capital-submit"),

    # ── 17. SIGNALS MONITOR ───────────────────────────────────────────────────
    path("signals/events/",       SignalEventLogAPIView.as_view(),   name="signal-events"),
    path("signals/events/stats/", SignalEventStatsAPIView.as_view(), name="signal-events-stats"),

    # ── 18. SEARCH ────────────────────────────────────────────────────────────
    path("search/",         FraudSearchAPIView.as_view(),        name="fraud-search"),
    path("search/suggest/", FraudSearchSuggestAPIView.as_view(), name="fraud-search-suggest"),

    # ── 19. CACHE ─────────────────────────────────────────────────────────────
    path("cache/warmup/",     CacheWarmupAPIView.as_view(),     name="cache-warmup"),
    path("cache/stats/",      CacheStatsAPIView.as_view(),      name="cache-stats"),
    path("cache/invalidate/", CacheInvalidateAPIView.as_view(), name="cache-invalidate"),

    # ── 20. PLUGINS / REGISTRY ───────────────────────────────────────────────
    path("plugins/",                    PluginListAPIView.as_view(),        name="plugin-list"),
    path("plugins/<str:name>/activate/",PluginActivateAPIView.as_view(),   name="plugin-activate"),
    path("plugins/<str:name>/deactivate/",PluginDeactivateAPIView.as_view(),name="plugin-deactivate"),
    path("registry/components/",        RegistryComponentsAPIView.as_view(),name="registry-components"),

    # ── 20b. INTERACTORS — previously floating interactors.py now connected ─────
    path("interactors/fraud-detection/execute/", FraudDetectionInteractorView.as_view(), name="interactor-fraud-detection"),
    path("interactors/fraud-case/execute/",      FraudCaseInteractorView.as_view(),      name="interactor-fraud-case"),
    path("interactors/risk-profile/update/",     RiskProfileInteractorView.as_view(),    name="interactor-risk-profile"),

    # ── 20c. REPOSITORIES — previously floating repositories.py now connected ──
    path("repositories/stats/",                  RepositoryStatsView.as_view(),          name="repository-stats-all"),
    path("repositories/<str:repo_name>/query/",  RepositoryQueryView.as_view(),          name="repository-query"),

    # ── 21. FACTORIES / REPOSITORIES (dev/test utilities) ────────────────────
    path("factory/fraud-attempt/", FraudAttemptFactoryAPIView.as_view(), name="factory-fraud-attempt"),
    path("factory/fraud-case/",    FraudCaseFactoryAPIView.as_view(),     name="factory-fraud-case"),
    path("repository/stats/",      RepositoryStatsAPIView.as_view(),      name="repository-stats"),
    path("repository/query/",      RepositoryQueryAPIView.as_view(),      name="repository-query"),

    # ── 22. BUSINESS RULES ────────────────────────────────────────────────────
    path("business-rules/",                      BusinessRuleListAPIView.as_view(),     name="business-rule-list"),
    path("business-rules/evaluate/",             BusinessRuleEvaluateAPIView.as_view(), name="business-rule-evaluate"),
    path("business-rules/create/",               BusinessRuleCreateAPIView.as_view(),   name="business-rule-create"),
    path("business-rules/<str:rule_id>/toggle/", BusinessRuleToggleAPIView.as_view(),   name="business-rule-toggle"),

    # ── 23. OFFERWALL V2 ─────────────────────────────────────────────────────
    path("offerwall/check/",     OfferwallFraudCheckAPIView.as_view(), name="offerwall-check"),
    path("offerwall/batch/",     OfferwallBatchCheckAPIView.as_view(), name="offerwall-batch"),
    path("offerwall/analytics/", OfferwallAnalyticsAPIView.as_view(),  name="offerwall-analytics"),

    # ── 24. MANAGEMENT COMMANDS (admin-only) ──────────────────────────────────
    path("management/command/",     ManagementCommandAPIView.as_view(), name="management-command"),
    path("management/maintenance/", SystemMaintenanceAPIView.as_view(), name="management-maintenance"),

    # ── 24b. AI ENRICHMENT — previously floating openai.py now connected ──────
    path("ai/analyze-transaction/",   AIFraudAnalysisView.as_view(),   name="ai-analyze-transaction"),
    path("ai/bulk-enrich/",           AIBulkEnrichmentView.as_view(),  name="ai-bulk-enrich"),

    # ── 25. ATTACHMENT UPLOAD ─────────────────────────────────────────────────
    path("attachments/upload/", AttachmentUploadAPIView.as_view(), name="attachment-upload"),

    # ── 26. SUB-MODULE INCLUDES ───────────────────────────────────────────────
    #    Each sub-module owns its own URL namespace; no routes duplicated here.
    path("security/",    include("api.fraud_detection.security.urls_security")),
    path("detectors/",   include("api.fraud_detection.detectors.urls")),
    path("services/",    include("api.fraud_detection.services.urls")),
    path("integration/", include("api.fraud_detection.INTEGRATION_SYSTEM.urls")),

    # ── 25b. USE CASES — previously floating use_cases.py now connected ─────────
    path("use-cases/",                   UseCaseListAPIView.as_view(),         name="use-case-list"),
    path("use-cases/<str:use_case_name>/run/", UseCaseRunAPIView.as_view(),   name="use-case-run"),

    # ── 25c. RESOURCES — previously floating resources.py now routed ───────────

    # ── 26a. EXTERNAL ENDPOINTS — previously floating endpoint.py now connected ──

    # ── 26b. OFFERWALL V2 — previously floating, now connected ──────────────────
    path("offerwall-v2/", include("api.fraud_detection.urls_offerwall_complete")),

    path("bulk-ingest/", include("api.fraud_detection.urls_bulk_ingest")),
    path("reports/", include("api.fraud_detection.urls_reports")),
    path("feedback/", include("api.fraud_detection.urls_feedback")),
    path("sla/", include("api.fraud_detection.urls_sla")),
    path("chargebacks/", include("api.fraud_detection.urls_chargeback")),
    path("mfa/", include("api.fraud_detection.urls_mfa")),
    path("kyc/", include("api.fraud_detection.urls_kyc")),
    # ── TENANT — multi-org isolation ────────────────────────────────────────────
    path("tenant/", include("api.fraud_detection.urls_tenant")),

    # ── 27. ROUTER (catch-all — MUST BE LAST) ─────────────────────────────────
    path("", include(router.urls)),
]
