# DRY SHIM — Capital ViewSets merged into viewset.py
from api.fraud_detection.viewset import (  # noqa: F401
    BaseCapitalViewSet,
    CapitalFraudCaseViewSet,
    CapitalAlertViewSet,
    CapitalComplianceViewSet,
    CapitalAnalyticsViewSet,
)
