# =============================================================================
# fraud_detection/views_missing.py
#
# COMPATIBILITY SHIM — do not add new code here.
#
# All 16 ViewSets / APIViews have been moved to views_extended.py which is
# their permanent home.  This file simply re-exports everything so that
# existing imports in urls.py and tests continue to work unchanged:
#
#   from api.fraud_detection.views_missing import FraudPatternViewSet
#
# Once you have updated all import sites to point at views_extended, this
# file can be deleted.
# =============================================================================

from api.fraud_detection.views_extended import (  # noqa: F401
    StandardResultsPagination,

    # ViewSets
    FraudPatternViewSet,
    FraudSettingsViewSet,
    FraudWhitelistViewSet,
    FraudNotificationViewSet,
    FraudCaseEvidenceViewSet,
    FraudCaseActionViewSet,
    DeviceFingerprintViewSet,
    IPReputationViewSet,
    OfferCompletionViewSet,

    # APIViews
    FraudAnalyticsAPIView,
    GeographicAnalysisAPIView,
    RiskTimelineAPIView,
    IntegrityVerificationAPIView,
    SystemHealthAPIView,

    # Function-based views
    fraud_statistics,
    quick_fraud_check,
)
