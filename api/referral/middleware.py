# api/referral/middleware.py
# Referral tracking middleware — cookie-based auto-attribution
# CPAlead style: /ref/<code>/ redirect + cookie set + attribution on signup
# ============================================================

import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

COOKIE_NAME = 'ref_code'
COOKIE_DAYS = 30


class ReferralTrackingMiddleware:
    """
    Middleware that:
    1. Detects ?ref=CODE or /ref/CODE URL patterns
    2. Sets a cookie with the referral code (30 days)
    3. Tracks the click via ReferralCodeService
    4. Makes the ref code available in request.referral_code
    
    Add to settings.py MIDDLEWARE:
        'api.referral.middleware.ReferralTrackingMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Step 1: Detect referral code from URL param or cookie
        ref_code = (
            request.GET.get('ref')
            or request.GET.get('referral')
            or request.GET.get('r')
            or request.COOKIES.get(COOKIE_NAME)
        )

        # Step 2: Attach to request
        request.referral_code = ref_code

        # Step 3: Track click if code from URL (not cookie)
        if ref_code and ref_code != request.COOKIES.get(COOKIE_NAME):
            self._track_click(request, ref_code)

        response = self.get_response(request)

        # Step 4: Set/refresh cookie if code found in URL param
        url_ref = (
            request.GET.get('ref')
            or request.GET.get('referral')
            or request.GET.get('r')
        )
        if url_ref:
            expires = timezone.now() + timedelta(days=COOKIE_DAYS)
            response.set_cookie(
                COOKIE_NAME,
                url_ref,
                max_age=COOKIE_DAYS * 86400,
                expires=expires.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                httponly=True,
                samesite='Lax',
            )

        return response

    def _track_click(self, request, code: str):
        """Referral code click record করো।"""
        try:
            from api.referral.services.ReferralCodeService import ReferralCodeService
            ip = self._get_client_ip(request)
            ReferralCodeService.track_click(code_value=code, ip=ip)
        except Exception as e:
            logger.debug(f"[Middleware] Click track failed: {e}")

    @staticmethod
    def _get_client_ip(request) -> str:
        """Real IP পাও (proxy-aware)।"""
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


def get_referral_code_from_request(request) -> str | None:
    """
    Helper: request থেকে referral code পাও।
    View বা serializer এ use করো।
    """
    # Try middleware-set attribute first
    if hasattr(request, 'referral_code') and request.referral_code:
        return request.referral_code
    # Fallback: check query params + cookie
    return (
        request.GET.get('ref')
        or request.GET.get('referral')
        or request.COOKIES.get(COOKIE_NAME)
    )


def get_referrer_from_request(request):
    """
    Request থেকে referrer user পাও।
    Registration view এ use করো।
    Returns User object or None।
    """
    code = get_referral_code_from_request(request)
    if not code:
        return None
    try:
        from api.referral.services.ReferralCodeService import ReferralCodeService
        result = ReferralCodeService.validate_code(code)
        if result['valid']:
            return result['user']
    except Exception as e:
        logger.debug(f"[Middleware] Referrer lookup failed: {e}")
    return None


def clear_referral_cookie(response):
    """
    Signup complete হলে referral cookie delete করো।
    """
    response.delete_cookie(COOKIE_NAME)
    return response