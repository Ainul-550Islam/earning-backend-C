# api/rate_limit/adapters/security.py
"""
Security System ↔ Rate Limit Adapter
=======================================
Covers: token validation, login attempts, endpoint protection.

Usage in api/security/endpoint.py:
    from api.rate_limit.adapters.security import SecurityRateLimitAdapter

    # In SecurityEndpoint._setup_handler():
    # Replace: from .decorators import rate_limit
    # With:
    handler = SecurityRateLimitAdapter.wrap_endpoint(handler, action='security_token_validate')
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.security')


class SecurityRateLimitAdapter:
    """Adapter for api/security system."""

    @staticmethod
    def check_token_validate(request) -> RateLimitResult:
        """
        Check before token validation.
        Where to call:
            api/security/endpoint.py → validate_token view
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'security_token_validate',
            request=request,
            ip_address=ip,
        )

    @staticmethod
    def check_login_attempt(request, username: str = '') -> RateLimitResult:
        """
        Check security login attempt.
        Where to call:
            api/security/ → auth endpoints
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'security_login_attempt',
            request=request,
            ip_address=ip,
            extra_context={'username': username},
        )

    @staticmethod
    def check_api_global(request) -> RateLimitResult:
        """
        Global API rate limit check.
        Where to call:
            api/security/endpoint.py → all endpoints
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'api_global',
            request=request,
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            ip_address=ip,
        )

    @staticmethod
    def wrap_endpoint(handler, action: str = 'api_global'):
        """
        Wrap a view handler with rate limiting.
        Drop-in for api/security/endpoint.py → SecurityEndpoint._setup_handler()

        Replace:
            from .decorators import rate_limit
            handler = rate_limit(**self.config.rate_limit)(handler)
        With:
            from api.rate_limit.adapters.security import SecurityRateLimitAdapter
            handler = SecurityRateLimitAdapter.wrap_endpoint(handler, action)
        """
        from api.rate_limit.integration_service import rate_limit_action
        return rate_limit_action(action)(handler)

    @staticmethod
    def block_suspicious_ip(ip_address: str, reason: str = 'security_violation', hours: int = 24) -> bool:
        """
        Block a suspicious IP from security system.
        Where to call:
            api/security/ → on repeated auth failures
        """
        return RateLimitIntegrationService.block_ip(
            ip_address=ip_address,
            reason=reason,
            hours=hours,
        )
