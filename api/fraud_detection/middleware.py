# api/fraud_detection/middleware.py
"""
Cross-app fraud detection middleware.
Runs risk check on financial and task operations; attaches result to request.
"""
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden, JsonResponse

logger = logging.getLogger(__name__)

# Path prefixes that require fraud check
FINANCIAL_PATHS = (
    '/api/wallet/withdraw',
    '/api/wallet/withdrawal',
    '/api/payment-request',
    '/api/payment_request',
    '/api/create_payment_request',
)
TASK_PATHS = (
    '/api/tasks/complete',
    '/api/tasks/submit',
    '/api/complete-ad',
)


def _get_user_risk(user):
    """Return (allowed, reason, risk_score)."""
    if not user or not user.is_authenticated:
        return True, "", 0
    try:
        from api.fraud_detection.models import UserRiskProfile
        profile = UserRiskProfile.objects.filter(user=user).first()
        if not profile:
            return True, "", 0
        if profile.is_restricted:
            return False, "Account is restricted.", getattr(profile, 'overall_risk_score', 100)
        if profile.is_flagged and getattr(profile, 'overall_risk_score', 0) >= 80:
            return False, "Account flagged for review.", profile.overall_risk_score
        return True, "", getattr(profile, 'overall_risk_score', 0)
    except ImportError as e:
        logger.debug("Fraud detection not available: %s", e)
        return True, "", 0
    except Exception as e:
        logger.exception("Risk check failed: %s", e)
        return True, "", 0  # Fail open for availability


class FraudDetectionMiddleware(MiddlewareMixin):
    """
    Attach fraud check to requests for financial/task endpoints.
    Optionally block high-risk users (set FRAUD_MIDDLEWARE_BLOCK_HIGH_RISK = True).
    """
    def process_request(self, request):
        path = (request.path or '').strip()
        if not path.startswith('/api/'):
            request.fraud_risk_checked = False
            return None
        is_financial = any(path.startswith(p) for p in FINANCIAL_PATHS)
        is_task = any(path.startswith(p) for p in TASK_PATHS)
        if not is_financial and not is_task:
            request.fraud_risk_checked = False
            request.fraud_risk_allowed = True
            return None
        allowed, reason, score = _get_user_risk(getattr(request, 'user', None))
        request.fraud_risk_checked = True
        request.fraud_risk_allowed = allowed
        request.fraud_risk_reason = reason
        request.fraud_risk_score = score
        from django.conf import settings
        block_high_risk = getattr(settings, 'FRAUD_MIDDLEWARE_BLOCK_HIGH_RISK', False)
        if not allowed and block_high_risk:
            logger.warning("Blocked request for user %s: %s", getattr(request.user, 'id', None), reason)
            return JsonResponse(
                {'detail': reason or 'Action not allowed.', 'code': 'fraud_risk'},
                status=403
            )
        return None
