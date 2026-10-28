# api/rate_limit/adapters/referral.py
"""
Referral System ↔ Rate Limit Adapter
=======================================
Covers: referral click, referral registration, commission payout,
        referral link generation.

Usage in api/referral/ (interactors, tasks, INTEGRATION_SYSTEM):
    from api.rate_limit.adapters.referral import ReferralRateLimitAdapter

    # In referral click handler:
    result = ReferralRateLimitAdapter.check_referral_click(request)
    if not result.allowed:
        return JsonResponse({'error': 'too many requests'}, status=429)

    # In commission celery task:
    result = ReferralRateLimitAdapter.check_commission_payout(user=referrer_user)
    result.raise_if_blocked()
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.referral')


class ReferralRateLimitAdapter:
    """Adapter for api/referral system."""

    # ── Referral Click ─────────────────────────────────────────

    @staticmethod
    def check_referral_click(request, referral_code: str = '') -> RateLimitResult:
        """
        Check when a referral link is clicked.
        Limits per IP to prevent fake referral clicks.

        Where to call:
            api/referral/interactors.py → ReferralClickInteractor
            api/referral/views.py → referral click endpoint
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'referral_click',
            request=request,
            ip_address=ip,
            extra_context={'referral_code': referral_code},
        )

    # ── Referral Registration ──────────────────────────────────

    @staticmethod
    def check_referral_register(request, referral_code: str = '') -> RateLimitResult:
        """
        Check when someone registers via a referral link.
        Prevents mass fake registrations under one referral code.

        Where to call:
            api/referral/interactors.py → on_referral_register()
            api/users/registration_view.py → when referral_code present
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'referral_register',
            request=request,
            ip_address=ip,
            extra_context={'referral_code': referral_code},
        )

    # ── Commission Payout ──────────────────────────────────────

    @staticmethod
    def check_commission_payout(user, level: int = 1) -> RateLimitResult:
        """
        Check before processing a referral commission payout.
        Prevents rapid commission stacking.

        Where to call:
            api/referral/tasks/commission_processing_tasks.py
            api/referral/INTEGRATION_SYSTEM/integ_adapter.py →
                WalletAdapter.credit_referral_commission()
        """
        return RateLimitIntegrationService.check(
            'referral_commission',
            user=user,
            extra_context={'level': level, 'source': 'commission_payout'},
        )

    # ── Link Generation ────────────────────────────────────────

    @staticmethod
    def check_link_generate(request, user=None) -> RateLimitResult:
        """
        Check before generating a referral link.

        Where to call:
            api/referral/ → referral link generation endpoint
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'referral_link_generate',
            request=request,
            user=user,
        )

    # ── INTEGRATION_SYSTEM bridge ──────────────────────────────

    @staticmethod
    def check_from_integration(action: str, user=None, ip_address: str = '', context: dict = None) -> RateLimitResult:
        """
        Generic check for api/referral/INTEGRATION_SYSTEM/*.
        Called from integ_adapter.py and integ_registry.py.

        Where to call:
            api/referral/INTEGRATION_SYSTEM/integ_adapter.py
            api/referral/INTEGRATION_SYSTEM/integ_registry.py
        """
        referral_action_map = {
            'click': 'referral_click',
            'register': 'referral_register',
            'commission': 'referral_commission',
            'link_generate': 'referral_link_generate',
        }
        mapped_action = referral_action_map.get(action, 'referral_click')
        return RateLimitIntegrationService.check(
            mapped_action,
            user=user,
            ip_address=ip_address,
            extra_context=context or {},
        )
