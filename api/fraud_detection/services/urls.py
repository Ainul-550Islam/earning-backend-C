# =============================================================================
# fraud_detection/services/urls.py  — NEW FILE
# Included by master urls.py under: path("services/", include(...))
#
# Exposes every service method as a dedicated endpoint.
# Views live in root-level views_services.py (DRY — defined once).
# =============================================================================
from django.urls import path

from api.fraud_detection.views_services import (
    # AutoBan
    AutoBanServiceStatsAPIView, AutoBanServiceValidateConfigAPIView,
    AutoBanServiceBulkFraudAPIView, AutoBanServiceUnbanScheduledAPIView,
    # FraudCase
    FraudCaseServiceCreateAPIView, FraudCaseServiceStatusAPIView,
    FraudCaseServiceEvidenceAPIView, FraudCaseServiceActionAPIView,
    FraudCaseServiceDetailAPIView, FraudCaseServiceUserCasesAPIView,
    FraudCaseServiceBulkUpdateAPIView,
    # FraudScore / ML
    FraudScoreCalculatorRunAPIView, FraudScoreCalculatorBatchAPIView,
    FraudScoreCalculatorExplainAPIView,
    MLFraudScorerPredictAPIView, MLFraudScorerBatchAPIView,
    MLFraudScorerRetrainAPIView, MLFraudScorerStatusAPIView,
    # Insight
    FraudInsightOverviewAPIView, FraudInsightTrendsAPIView,
    FraudInsightRiskFactorsAPIView,
    # IP Reputation
    IPReputationServiceCheckAPIView, IPReputationServiceBulkAPIView,
    IPReputationServiceStatsAPIView,
    # Notification
    NotificationServiceSendAPIView, NotificationServiceBulkAPIView,
    NotificationServiceStatsAPIView,
    # Review
    ReviewServiceBatchAPIView, ReviewServiceStatsAPIView,
    # Whitelist
    WhitelistServiceAddAPIView, WhitelistServiceRemoveAPIView,
    WhitelistServiceCheckAPIView,
    # FraudDetection (main)
    FraudDetectionServiceRunAPIView, FraudDetectionServiceBatchAPIView,
    FraudDetectionServiceStatusAPIView,
)

app_name = "services"

urlpatterns = [

    # ── AutoBanService ────────────────────────────────────────────────────────
    path("auto-ban/stats/",           AutoBanServiceStatsAPIView.as_view(),          name="auto-ban-stats"),
    path("auto-ban/validate-config/", AutoBanServiceValidateConfigAPIView.as_view(), name="auto-ban-validate-config"),
    path("auto-ban/bulk-process/",    AutoBanServiceBulkFraudAPIView.as_view(),      name="auto-ban-bulk-process"),
    path("auto-ban/check-unban/",     AutoBanServiceUnbanScheduledAPIView.as_view(), name="auto-ban-check-unban"),

    # ── FraudCaseService ──────────────────────────────────────────────────────
    path("fraud-case/create/",                    FraudCaseServiceCreateAPIView.as_view(),    name="fraud-case-create"),
    path("fraud-case/<int:case_id>/status/",      FraudCaseServiceStatusAPIView.as_view(),    name="fraud-case-status"),
    path("fraud-case/<int:case_id>/evidence/",    FraudCaseServiceEvidenceAPIView.as_view(),  name="fraud-case-evidence"),
    path("fraud-case/<int:case_id>/action/",      FraudCaseServiceActionAPIView.as_view(),    name="fraud-case-action"),
    path("fraud-case/<int:case_id>/detail/",      FraudCaseServiceDetailAPIView.as_view(),    name="fraud-case-detail"),
    path("fraud-case/user/<int:user_id>/",        FraudCaseServiceUserCasesAPIView.as_view(), name="fraud-case-by-user"),
    path("fraud-case/bulk-update/",               FraudCaseServiceBulkUpdateAPIView.as_view(),name="fraud-case-bulk-update"),

    # ── FraudScoreCalculator ──────────────────────────────────────────────────
    path("fraud-score/run/",          FraudScoreCalculatorRunAPIView.as_view(),     name="fraud-score-run"),
    path("fraud-score/batch/",        FraudScoreCalculatorBatchAPIView.as_view(),   name="fraud-score-batch"),
    path("fraud-score/explain/",      FraudScoreCalculatorExplainAPIView.as_view(), name="fraud-score-explain"),

    # ── MLFraudScorer ─────────────────────────────────────────────────────────
    path("ml-scorer/predict/",  MLFraudScorerPredictAPIView.as_view(),  name="ml-scorer-predict"),
    path("ml-scorer/batch/",    MLFraudScorerBatchAPIView.as_view(),    name="ml-scorer-batch"),
    path("ml-scorer/retrain/",  MLFraudScorerRetrainAPIView.as_view(),  name="ml-scorer-retrain"),
    path("ml-scorer/status/",   MLFraudScorerStatusAPIView.as_view(),   name="ml-scorer-status"),

    # ── FraudInsightService ───────────────────────────────────────────────────
    path("insight/overview/",     FraudInsightOverviewAPIView.as_view(),    name="insight-overview"),
    path("insight/trends/",       FraudInsightTrendsAPIView.as_view(),      name="insight-trends"),
    path("insight/risk-factors/", FraudInsightRiskFactorsAPIView.as_view(), name="insight-risk-factors"),

    # ── IPReputationService ───────────────────────────────────────────────────
    path("ip-reputation/check/",  IPReputationServiceCheckAPIView.as_view(), name="ip-reputation-check"),
    path("ip-reputation/bulk/",   IPReputationServiceBulkAPIView.as_view(),  name="ip-reputation-bulk"),
    path("ip-reputation/stats/",  IPReputationServiceStatsAPIView.as_view(), name="ip-reputation-stats"),

    # ── FraudNotificationService ──────────────────────────────────────────────
    path("notification/send/",  NotificationServiceSendAPIView.as_view(),  name="notification-send"),
    path("notification/bulk/",  NotificationServiceBulkAPIView.as_view(),  name="notification-bulk"),
    path("notification/stats/", NotificationServiceStatsAPIView.as_view(), name="notification-stats"),

    # ── ReviewService ─────────────────────────────────────────────────────────
    path("review/batch/", ReviewServiceBatchAPIView.as_view(), name="review-batch"),
    path("review/stats/", ReviewServiceStatsAPIView.as_view(), name="review-stats"),

    # ── WhitelistService ──────────────────────────────────────────────────────
    path("whitelist/add/",    WhitelistServiceAddAPIView.as_view(),    name="whitelist-add"),
    path("whitelist/remove/", WhitelistServiceRemoveAPIView.as_view(), name="whitelist-remove"),
    path("whitelist/check/",  WhitelistServiceCheckAPIView.as_view(),  name="whitelist-check"),

    # ── FraudDetectionService (core) ──────────────────────────────────────────
    path("fraud-detection/run/",    FraudDetectionServiceRunAPIView.as_view(),    name="fraud-detection-run"),
    path("fraud-detection/batch/",  FraudDetectionServiceBatchAPIView.as_view(),  name="fraud-detection-batch"),
    path("fraud-detection/status/", FraudDetectionServiceStatusAPIView.as_view(), name="fraud-detection-status"),
]
