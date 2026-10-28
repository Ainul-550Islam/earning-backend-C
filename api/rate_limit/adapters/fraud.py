# api/rate_limit/adapters/fraud.py
"""
Fraud Detection ↔ Rate Limit Adapter
========================================
Bidirectional bridge:
  fraud_detection → rate_limit  (report fraud signals, block IPs)
  rate_limit → fraud_detection  (suspicion scores feed back to fraud)

Usage in api/fraud_detection/middleware.py:
    from api.rate_limit.adapters.fraud import FraudRateLimitAdapter

    # In FraudDetectionMiddleware.process_request():
    FraudRateLimitAdapter.sync_risk_signal(
        user=request.user,
        ip_address=get_client_ip(request),
        risk_score=profile.overall_risk_score,
        fraud_type='velocity',
    )
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.fraud')


class FraudRateLimitAdapter:
    """Adapter for api/fraud_detection system."""

    # ── Fraud → Rate Limit signals ─────────────────────────────

    @staticmethod
    def sync_risk_signal(
        user=None,
        ip_address: str = '',
        risk_score: int = 0,
        fraud_type: str = '',
        auto_block: bool = False,
    ) -> dict:
        """
        Send a fraud risk signal to rate_limit.
        Updates suspicion score; optionally blocks IP.

        Where to call:
            api/fraud_detection/middleware.py → FraudDetectionMiddleware
            api/fraud_detection/detectors/MultiAccountDetector.py
            api/fraud_detection/detectors/VPNProxyDetector.py
            api/fraud_detection/detectors/ClickFraudDetector.py
            api/fraud_detection/detectors/PatternAnalyzer.py
        """
        return RateLimitIntegrationService.sync_fraud_signal(
            user=user,
            ip_address=ip_address,
            risk_score=risk_score,
            fraud_type=fraud_type,
            auto_block=auto_block,
        )

    @staticmethod
    def block_fraudulent_ip(ip_address: str, reason: str, hours: int = 48, blocked_by=None) -> bool:
        """
        Immediately block a detected fraudulent IP.

        Where to call:
            api/fraud_detection/detectors/VPNProxyDetector.py
            api/fraud_detection/detectors/ClickFraudDetector.py
        """
        return RateLimitIntegrationService.block_ip(
            ip_address=ip_address,
            reason=f'fraud:{reason}',
            hours=hours,
            blocked_by=blocked_by,
        )

    @staticmethod
    def increase_suspicion(user, delta: int = 10, reason: str = '') -> bool:
        """
        Increase a user's suspicion score.

        Where to call:
            api/fraud_detection/detectors/MultiAccountDetector.py
            api/fraud_detection/detectors/DeviceFingerprinter.py
        """
        return RateLimitIntegrationService.update_user_suspicion(user, delta, reason)

    @staticmethod
    def decrease_suspicion(user, delta: int = 10, reason: str = '') -> bool:
        """
        Decrease suspicion (e.g., user passed manual review).

        Where to call:
            api/fraud_detection/ → manual review approval
        """
        return RateLimitIntegrationService.update_user_suspicion(user, -abs(delta), reason)

    # ── Rate Limit → Fraud info ────────────────────────────────

    @staticmethod
    def get_user_suspicion(user) -> int:
        """
        Get current suspicion score from rate_limit.
        Used by fraud_detection to combine with its own scoring.

        Where to call:
            api/fraud_detection/detectors/PatternAnalyzer.py
        """
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile = UserRateLimitProfile.objects.filter(user=user).first()
            return getattr(profile, 'suspicion_score', 0) or 0
        except Exception as e:
            logger.debug(f'get_user_suspicion error: {e}')
            return 0

    @staticmethod
    def get_ip_block_status(ip_address: str) -> dict:
        """
        Check if an IP is blocked in rate_limit.
        Used by fraud_detection to skip processing on blocked IPs.

        Where to call:
            api/fraud_detection/middleware.py → fast path check
        """
        return RateLimitIntegrationService.get_ip_status(ip_address)

    # ── Rate limit check for fraud endpoints ───────────────────

    @staticmethod
    def check_fraud_report(request) -> RateLimitResult:
        """
        Limit how fast fraud reports can be submitted.
        Where to call: api/fraud_detection/ → report endpoint
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check('fraud_report', request=request, user=user)
