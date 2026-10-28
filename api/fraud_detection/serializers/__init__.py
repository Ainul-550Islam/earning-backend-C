# =============================================================================
# fraud_detection/serializers/__init__.py
# =============================================================================
"""
Fraud Detection Serializers Package.

Re-exports from the structured per-model serializer files AND from the
consolidated flat serializers.py module so that any import style works:

    from api.fraud_detection.serializers import FraudRuleSerializer
    from api.fraud_detection.serializers import FraudSettingsSerializer
    from api.fraud_detection.serializers import FraudNotificationSerializer
    from api.fraud_detection.serializers.FraudCaseSerializer import FraudCaseListSerializer

All serializers from the former serializers_missing.py are now first-class
citizens here — that file should be considered deprecated.
"""

# ── Structured sub-module imports ──────────────────────────────────────────

from .FraudCaseSerializer import (
    FraudCaseSerializer,
    FraudCaseListSerializer,
    FraudCaseCreateSerializer,
    FraudCaseUpdateSerializer,
    FraudCaseStatusUpdateSerializer,
    FraudCaseBulkUpdateSerializer,
    FraudCaseEvidenceSerializer,
    FraudCaseActionSerializer as CaseActionSerializer,
)

from .FraudCaseActionSerializer import (
    FraudCaseActionSerializer,
    FraudCaseActionListSerializer,
    FraudCaseActionCreateSerializer,
    FraudCaseActionUpdateSerializer,
    FraudCaseBulkActionSerializer,
    FraudCaseActionTimelineSerializer,
    FraudCaseActionStatisticsSerializer,
)

from .FraudWhitelistSerializer import (
    FraudWhitelistSerializer,
    FraudWhitelistListSerializer,
    FraudWhitelistCreateSerializer,
    FraudWhitelistUpdateSerializer,
    FraudWhitelistDeactivateSerializer,
    FraudWhitelistBulkCreateSerializer,
    FraudWhitelistBulkUpdateSerializer,
    FraudWhitelistBulkDeactivateSerializer,
    FraudWhitelistStatisticsSerializer,
    FraudWhitelistSearchSerializer,
)

from .FraudInsightSerializer import (
    FraudOverviewSerializer,
    FraudTrendDataSerializer,
    FraudTrendsSerializer,
    RiskFactorSerializer,
    TopRiskFactorsSerializer,
    CountryRiskSerializer,
    GeographicAnalysisSerializer,
    PerformanceMetricsSerializer,
    ForecastDataSerializer,
    PredictiveInsightsSerializer,
    AnalyticsExportSerializer,
    AnalyticsDataSerializer,
    InsightRequestSerializer,
)

from .AdminFraudSerializer import (
    AdminFraudOverviewSerializer,
    AdminUserRiskProfileSerializer,
    AdminFraudAttemptSerializer,
    AdminBulkActionSerializer,
    AdminSystemSettingsSerializer,
    AdminDashboardConfigSerializer,
    AdminActivityLogSerializer,
    AdminQuickActionSerializer,
    AdminStatisticsSerializer,
)

# ── Flat module re-exports (core model serializers + previously missing ones) ─
# We use importlib so this package directory and the sibling serializers.py file
# can coexist without a circular import.
import importlib.util as _ilu
import pathlib as _pl

_flat_spec = _ilu.spec_from_file_location(
    '_fd_serializers_flat',
    _pl.Path(__file__).parent.parent / 'serializers.py',
)
_flat_mod = _ilu.module_from_spec(_flat_spec)
_flat_spec.loader.exec_module(_flat_mod)

# Core model serializers
FraudRuleSerializer              = _flat_mod.FraudRuleSerializer
FraudAttemptSerializer           = _flat_mod.FraudAttemptSerializer
FraudPatternSerializer           = _flat_mod.FraudPatternSerializer
UserRiskProfileSerializer        = _flat_mod.UserRiskProfileSerializer
DeviceFingerprintSerializer      = _flat_mod.DeviceFingerprintSerializer
IPReputationSerializer           = _flat_mod.IPReputationSerializer
FraudAlertSerializer             = _flat_mod.FraudAlertSerializer
FraudDetectionResponseSerializer = _flat_mod.FraudDetectionResponseSerializer
FraudStatisticsSerializer        = _flat_mod.FraudStatisticsSerializer

# Full-field serializers (previously only in serializers_missing.py)
FraudCaseEvidenceFullSerializer  = _flat_mod.FraudCaseEvidenceFullSerializer
FraudCaseActionFullSerializer    = _flat_mod.FraudCaseActionFullSerializer
FraudCaseFullSerializer          = _flat_mod.FraudCaseFullSerializer
FraudWhitelistFullSerializer     = _flat_mod.FraudWhitelistFullSerializer

# Newly promoted serializers (previously only in serializers_missing.py)
FraudNotificationSerializer      = _flat_mod.FraudNotificationSerializer
FraudSettingsSerializer          = _flat_mod.FraudSettingsSerializer
OfferCompletionSerializer        = _flat_mod.OfferCompletionSerializer
OfferCompletionCreateSerializer  = _flat_mod.OfferCompletionCreateSerializer

# Admin convenience serializer
AdminFraudSerializer             = _flat_mod.AdminFraudSerializer

# ── __all__ ────────────────────────────────────────────────────────────────

__all__ = [
    # Case Serializers (sub-module)
    'FraudCaseSerializer',
    'FraudCaseListSerializer',
    'FraudCaseCreateSerializer',
    'FraudCaseUpdateSerializer',
    'FraudCaseStatusUpdateSerializer',
    'FraudCaseBulkUpdateSerializer',
    'FraudCaseEvidenceSerializer',
    'CaseActionSerializer',

    # Case Action Serializers (sub-module)
    'FraudCaseActionSerializer',
    'FraudCaseActionListSerializer',
    'FraudCaseActionCreateSerializer',
    'FraudCaseActionUpdateSerializer',
    'FraudCaseBulkActionSerializer',
    'FraudCaseActionTimelineSerializer',
    'FraudCaseActionStatisticsSerializer',

    # Whitelist Serializers (sub-module)
    'FraudWhitelistSerializer',
    'FraudWhitelistListSerializer',
    'FraudWhitelistCreateSerializer',
    'FraudWhitelistUpdateSerializer',
    'FraudWhitelistDeactivateSerializer',
    'FraudWhitelistBulkCreateSerializer',
    'FraudWhitelistBulkUpdateSerializer',
    'FraudWhitelistBulkDeactivateSerializer',
    'FraudWhitelistStatisticsSerializer',
    'FraudWhitelistSearchSerializer',

    # Insight Serializers (sub-module)
    'FraudOverviewSerializer',
    'FraudTrendDataSerializer',
    'FraudTrendsSerializer',
    'RiskFactorSerializer',
    'TopRiskFactorsSerializer',
    'CountryRiskSerializer',
    'GeographicAnalysisSerializer',
    'PerformanceMetricsSerializer',
    'ForecastDataSerializer',
    'PredictiveInsightsSerializer',
    'AnalyticsExportSerializer',
    'AnalyticsDataSerializer',
    'InsightRequestSerializer',

    # Admin Serializers (sub-module)
    'AdminFraudOverviewSerializer',
    'AdminUserRiskProfileSerializer',
    'AdminFraudAttemptSerializer',
    'AdminBulkActionSerializer',
    'AdminSystemSettingsSerializer',
    'AdminDashboardConfigSerializer',
    'AdminActivityLogSerializer',
    'AdminQuickActionSerializer',
    'AdminStatisticsSerializer',

    # Core model serializers (flat module)
    'FraudRuleSerializer',
    'FraudAttemptSerializer',
    'FraudPatternSerializer',
    'UserRiskProfileSerializer',
    'DeviceFingerprintSerializer',
    'IPReputationSerializer',
    'FraudAlertSerializer',
    'FraudDetectionResponseSerializer',
    'FraudStatisticsSerializer',
    'AdminFraudSerializer',

    # Full-field serializers (flat module — formerly in serializers_missing.py)
    'FraudCaseEvidenceFullSerializer',
    'FraudCaseActionFullSerializer',
    'FraudCaseFullSerializer',
    'FraudWhitelistFullSerializer',

    # Newly promoted (formerly in serializers_missing.py)
    'FraudNotificationSerializer',
    'FraudSettingsSerializer',
    'OfferCompletionSerializer',
    'OfferCompletionCreateSerializer',
]
