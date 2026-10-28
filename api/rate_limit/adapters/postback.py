# api/rate_limit/adapters/postback.py
"""
Postback Engine ↔ Rate Limit Adapter
=======================================
Covers: click tracking, conversion, impression, validation.

Usage in api/postback_engine/:
    from api.rate_limit.adapters.postback import PostbackRateLimitAdapter

    # In click handler:
    result = PostbackRateLimitAdapter.check_click(
        ip_address=request.META.get('REMOTE_ADDR'),
        network='cpalead',
        request=request,
    )
    if not result.allowed:
        return HttpResponse('rate limit exceeded', status=429)

    # In dependencies.py (replaces local rate_limiter):
    # get_rate_limiter() → PostbackRateLimitAdapter
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.postback')


class PostbackRateLimitAdapter:
    """
    Adapter for api/postback_engine system.

    Drop-in replacement for:
        api/postback_engine/security/rate_limiter.py → rate_limiter singleton
        api/postback_engine/dependencies.py → get_rate_limiter()
    """

    # ── Click ──────────────────────────────────────────────────

    @staticmethod
    def check_click(ip_address: str, network: str = '', request=None, user=None) -> RateLimitResult:
        """
        Check before recording a postback click.
        IP-based — clicks come from external networks.

        Where to call:
            api/postback_engine/postback_handlers/click_handler.py
            api/postback_engine/views.py → click endpoint
        """
        return RateLimitIntegrationService.check(
            'postback_click',
            request=request,
            user=user,
            ip_address=ip_address,
            extra_context={'network': network},
        )

    # ── Conversion ─────────────────────────────────────────────

    @staticmethod
    def check_conversion(ip_address: str, network: str = '', request=None, user=None) -> RateLimitResult:
        """
        Check before recording a conversion.
        Most important — prevents fake conversion flooding.

        Where to call:
            api/postback_engine/postback_handlers/conversion_handler.py
            api/postback_engine/conversion_tracking/
        """
        return RateLimitIntegrationService.check(
            'postback_conversion',
            request=request,
            user=user,
            ip_address=ip_address,
            extra_context={'network': network},
        )

    # ── Impression ─────────────────────────────────────────────

    @staticmethod
    def check_impression(ip_address: str, request=None) -> RateLimitResult:
        """
        Check before recording an ad impression.

        Where to call:
            api/postback_engine/ → impression endpoint
        """
        return RateLimitIntegrationService.check(
            'postback_impression',
            request=request,
            ip_address=ip_address,
        )

    # ── Validation ─────────────────────────────────────────────

    @staticmethod
    def check_validation(ip_address: str, request=None) -> RateLimitResult:
        """
        Check before postback signature/parameter validation.

        Where to call:
            api/postback_engine/validation_engines/
        """
        return RateLimitIntegrationService.check(
            'postback_validation',
            request=request,
            ip_address=ip_address,
        )

    # ── Dependency injection replacement ───────────────────────

    def allow(self, identifier: str, action: str = 'postback_click', **kwargs) -> bool:
        """
        Drop-in interface matching postback_engine/security/rate_limiter.py.

        Replaces:
            rate_limiter.allow(identifier, ...)
        With:
            PostbackRateLimitAdapter().allow(identifier, ...)
        """
        result = RateLimitIntegrationService.check(
            action,
            ip_address=identifier if identifier.count('.') == 3 else '',
            extra_context={'identifier': identifier},
        )
        return result.allowed

    def check(self, identifier: str, action: str = 'postback_click') -> tuple:
        """
        Returns (allowed: bool, remaining: int, reset_at).
        Matches existing rate_limiter.check() interface.
        """
        result = RateLimitIntegrationService.check(
            action,
            ip_address=identifier if '.' in identifier else '',
            extra_context={'identifier': identifier},
        )
        return result.allowed, result.remaining, result.reset_at

    # ── Fraud signal to rate_limit ─────────────────────────────

    @staticmethod
    def report_suspicious_postback(
        ip_address: str,
        user=None,
        risk_score: int = 0,
        fraud_type: str = '',
        auto_block: bool = False,
    ) -> dict:
        """
        Report a suspicious postback to rate_limit system.
        Called when fraud_score_calculator detects anomalies.

        Where to call:
            api/postback_engine/fraud_detection/fraud_scoring.py
            api/postback_engine/fraud_detection/velocity_checker.py
        """
        return RateLimitIntegrationService.sync_fraud_signal(
            user=user,
            ip_address=ip_address,
            risk_score=risk_score,
            fraud_type=fraud_type or 'postback_fraud',
            auto_block=auto_block,
        )
