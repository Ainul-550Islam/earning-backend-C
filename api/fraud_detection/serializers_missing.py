# =============================================================================
# fraud_detection/serializers_missing.py — DRY SHIM
#
# All serializers that were in this file are now first-class exports from
# the serializers package (serializers/__init__.py).
# Import from there directly:
#   from api.fraud_detection.serializers import FraudNotificationSerializer
# =============================================================================
from api.fraud_detection.serializers import (  # noqa: F401
    FraudNotificationSerializer,
    FraudSettingsSerializer,
    OfferCompletionSerializer,
    OfferCompletionCreateSerializer,
    FraudCaseEvidenceFullSerializer,
    FraudCaseActionFullSerializer,
    FraudCaseFullSerializer,
    FraudWhitelistFullSerializer,
)

# Alias kept for backward compat only
FraudCaseEvidenceSerializer = FraudCaseEvidenceFullSerializer
FraudCaseActionSerializer   = FraudCaseActionFullSerializer
FraudCaseSerializer         = FraudCaseFullSerializer
