# =============================================================================
# fraud_detection/services/__init__.py — CANONICAL EXPORTS (DRY)
#
# Every service class + its singleton accessor exported from ONE place.
# Import pattern:
#   from api.fraud_detection.services import AutoBanService, get_auto_ban_service
# =============================================================================
from .AutoBanService          import AutoBanService
from .FraudCaseService        import FraudCaseService
from .FraudInsightService     import FraudInsightService
from .FraudNotificationService import FraudNotificationService
from .FraudScoreCalculator    import FraudScoreCalculator
from .IPReputationService     import IPReputationService
from .MLFraudScorer           import MLFraudScorer
from .ReviewService           import ReviewService
from .WhitelistService        import WhitelistService
from .fraud_detection_service import FraudDetectionService

# ── Singleton accessors ───────────────────────────────────────────────────────
_instances: dict = {}


def _get(cls):
    if cls not in _instances:
        _instances[cls] = cls()
    return _instances[cls]


def get_auto_ban_service()          -> AutoBanService:           return _get(AutoBanService)
def get_fraud_case_service()        -> FraudCaseService:         return _get(FraudCaseService)
def get_fraud_insight_service()     -> FraudInsightService:      return _get(FraudInsightService)
def get_fraud_notification_service()-> FraudNotificationService: return _get(FraudNotificationService)
def get_fraud_score_calculator()    -> FraudScoreCalculator:     return _get(FraudScoreCalculator)
def get_ip_reputation_service()     -> IPReputationService:      return _get(IPReputationService)
def get_ml_fraud_scorer()           -> MLFraudScorer:            return _get(MLFraudScorer)
def get_review_service()            -> ReviewService:            return _get(ReviewService)
def get_whitelist_service()         -> WhitelistService:         return _get(WhitelistService)
def get_fraud_detection_service()   -> FraudDetectionService:    return _get(FraudDetectionService)

# ── Module-level singletons (for backwards-compat import style) ───────────────
class _LazyService:
    """Resolve the real service on first attribute access."""
    def __init__(self, getter):
        self._getter = getter

    def __getattr__(self, name):
        return getattr(self._getter(), name)


fraud_detection_service = _LazyService(get_fraud_detection_service)
risk_assessment_service = _LazyService(get_fraud_score_calculator)

__all__ = [
    "AutoBanService", "FraudCaseService", "FraudInsightService",
    "FraudNotificationService", "FraudScoreCalculator", "IPReputationService",
    "MLFraudScorer", "ReviewService", "WhitelistService", "FraudDetectionService",
    "get_auto_ban_service", "get_fraud_case_service", "get_fraud_insight_service",
    "get_fraud_notification_service", "get_fraud_score_calculator",
    "get_ip_reputation_service", "get_ml_fraud_scorer", "get_review_service",
    "get_whitelist_service", "get_fraud_detection_service",
]


# =============================================================================
# NEW SERVICES  (added by business gap fixes)
# =============================================================================
try:
    from api.fraud_detection.services.ChargebackService import ChargebackService, get_chargeback_service
except ImportError:
    ChargebackService = None; get_chargeback_service = lambda: None  # type: ignore

# KYC and MFA live at app root level (not services/) — re-exported here for DRY
try:
    from api.fraud_detection.kyc_service import KYCService, get_kyc_service
except ImportError:
    KYCService = None; get_kyc_service = lambda: None  # type: ignore

try:
    from api.fraud_detection.mfa_validator import MFAService, get_mfa_service
except ImportError:
    MFAService = None; get_mfa_service = lambda: None  # type: ignore

try:
    from api.fraud_detection.sla_manager import SLAManager, get_sla_manager
except ImportError:
    SLAManager = None; get_sla_manager = lambda: None  # type: ignore

try:
    from api.fraud_detection.feedback import FeedbackService, get_feedback_service
except ImportError:
    FeedbackService = None; get_feedback_service = lambda: None  # type: ignore

try:
    from api.fraud_detection.report_scheduler import ReportScheduler, get_report_scheduler
except ImportError:
    ReportScheduler = None; get_report_scheduler = lambda: None  # type: ignore
