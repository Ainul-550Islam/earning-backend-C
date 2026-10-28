# api/rate_limit/adapters/users.py
"""
Users System ↔ Rate Limit Adapter
===================================
Covers: login, registration, 2FA, password reset, OTP, profile updates.

Usage in api/users/registration_view.py:
    from api.rate_limit.adapters.users import UsersRateLimitAdapter

    result = UsersRateLimitAdapter.check_register(request)
    if not result.allowed:
        return JsonResponse({'error': result.reason}, status=429)

Usage in api/users/auth/jwt_handler.py:
    result = UsersRateLimitAdapter.check_login(request)
    result.raise_if_blocked()
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.users')


class UsersRateLimitAdapter:
    """Adapter for api/users system."""

    # ── Registration ───────────────────────────────────────────

    @staticmethod
    def check_register(request) -> RateLimitResult:
        """
        Check before user registration.
        Limits by IP to prevent mass account creation.

        Where to call:
            api/users/registration_view.py → UserRegistrationView.post()
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'user_register',
            request=request,
            ip_address=ip,
            extra_context={'endpoint': 'register'},
        )

    # ── Login ──────────────────────────────────────────────────

    @staticmethod
    def check_login(request, username: str = '') -> RateLimitResult:
        """
        Check before login attempt.
        Limits by IP + username to block brute-force.

        Where to call:
            api/users/auth/jwt_handler.py → login endpoint
            api/users/Login/ → LoginView
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'user_login',
            request=request,
            ip_address=ip,
            extra_context={'username': username},
        )

    # ── 2FA ────────────────────────────────────────────────────

    @staticmethod
    def check_2fa(request, user=None) -> RateLimitResult:
        """
        Check before 2FA code verification.
        Prevents brute-force of 2FA codes.

        Where to call:
            api/users/views_2fa_session.py → TwoFactorVerifyView
        """
        user = user or (request.user if hasattr(request, 'user') and request.user.is_authenticated else None)
        return RateLimitIntegrationService.check(
            'user_2fa',
            request=request,
            user=user,
            extra_context={'endpoint': '2fa_verify'},
        )

    # ── Password Reset ─────────────────────────────────────────

    @staticmethod
    def check_password_reset(request) -> RateLimitResult:
        """
        Check before password reset request.
        Prevents email bombing.

        Where to call:
            api/users/auth/password_manager.py → PasswordResetView
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'user_password_reset',
            request=request,
            ip_address=ip,
        )

    # ── OTP ────────────────────────────────────────────────────

    @staticmethod
    def check_otp_request(request, user=None) -> RateLimitResult:
        """
        Check before sending OTP (SMS/email).
        Prevents OTP flood.

        Where to call:
            api/users/auth/ → OTP send endpoint
        """
        user = user or (request.user if hasattr(request, 'user') and request.user.is_authenticated else None)
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'user_otp_request',
            request=request,
            user=user,
            ip_address=ip,
        )

    # ── Profile Update ─────────────────────────────────────────

    @staticmethod
    def check_profile_update(request, user=None) -> RateLimitResult:
        """
        Check before profile update.
        Prevents rapid profile scraping/abuse.

        Where to call:
            api/users/profile/ → ProfileUpdateView
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'user_profile_update',
            request=request,
            user=user,
        )

    # ── Convenience: check all auth actions at once ────────────

    @staticmethod
    def get_auth_limits_status(user) -> dict:
        """
        Return current rate limit status for a user's auth actions.
        Used by admin panel / support tools.
        """
        return RateLimitIntegrationService.get_user_status(user)
