"""
api/security/services/__init__.py
===================================
Security Services — Complete Public API
"এক কাজের জন্য একটাই মালিক।"
"""

# ── Existing services ─────────────────────────────────────────────────────────
from .IncidentService       import IncidentService
from .PasswordHistoryService import PasswordHistoryService
from .SecurityInsightService import SecurityInsightService
from .SecurityPolicyService  import SecurityPolicyService
from .ThreatIntelService     import ThreatIntelService
from .TrustedDeviceService   import TrustedDeviceService

# ── NEW: JWT Service ──────────────────────────────────────────────────────────
from .JWTService import (
    JWTManager,
    JWTAuthentication,
    TokenPair,
    TokenPayload,
    jwt_manager,
)

# ── NEW: Click Injection Prevention ──────────────────────────────────────────
from .ClickInjectionPrevention import (
    ClickInjectionPrevention,
    ClickValidationResult,
    click_injection_guard,
)

# ── NEW: Click Fraud Engine ────────────────────────────────────────────────────
from .ClickFraudEngine import (
    ClickFraudEngine,
    ClickFraudResult,
    FraudPattern,
    click_fraud_engine,
)

# ── NEW: Postback S2S Security ────────────────────────────────────────────────
from .PostbackS2SSecurity import (
    PostbackS2SSecurity,
    PostbackValidationResult,
    postback_security,
)

# ── NEW: SubID Tracking Security ──────────────────────────────────────────────
from .SubIDTrackingSecurity import (
    SubIDTrackingSecurity,
    SubIDValidationResult,
    SubIDReputation,
    subid_security,
)

# ── NEW: Advertiser Fraud Shield ──────────────────────────────────────────────
from .AdvertiserFraudShield import (
    AdvertiserFraudShield,
    AdvertiserProtectionResult,
    PublisherQualityReport,
    PublisherGrade,
    FraudType,
    FraudSignal,
    advertiser_fraud_shield,
)

# ── NEW: ML Bot Detection ──────────────────────────────────────────────────────
from .BotDetectionML import (
    BotDetectionML,
    BotDetectionResult,
    bot_detector_ml,
)


__all__ = [
    # Existing
    "IncidentService", "PasswordHistoryService", "SecurityInsightService",
    "SecurityPolicyService", "ThreatIntelService", "TrustedDeviceService",

    # JWT
    "JWTManager", "JWTAuthentication", "TokenPair", "TokenPayload", "jwt_manager",

    # Click Injection
    "ClickInjectionPrevention", "ClickValidationResult", "click_injection_guard",

    # Click Fraud
    "ClickFraudEngine", "ClickFraudResult", "FraudPattern", "click_fraud_engine",

    # Postback S2S
    "PostbackS2SSecurity", "PostbackValidationResult", "postback_security",

    # SubID
    "SubIDTrackingSecurity", "SubIDValidationResult", "SubIDReputation", "subid_security",

    # Advertiser Shield
    "AdvertiserFraudShield", "AdvertiserProtectionResult", "PublisherQualityReport",
    "PublisherGrade", "FraudType", "FraudSignal", "advertiser_fraud_shield",

    # ML Bot Detection
    "BotDetectionML", "BotDetectionResult", "bot_detector_ml",
]