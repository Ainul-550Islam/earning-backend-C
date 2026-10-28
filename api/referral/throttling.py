# api/referral/throttling.py
# Referral-specific DRF throttle classes
# ============================================================

from rest_framework.throttling import (
    UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
)


class ReferralUserThrottle(UserRateThrottle):
    """
    Standard user throttle for referral endpoints.
    100 requests/hour per user.
    """
    scope = 'referral_user'
    THROTTLE_RATES = {'referral_user': '100/hour'}


class ReferralSignupThrottle(UserRateThrottle):
    """
    Throttle for signup referral processing.
    1 registration per user (prevent multiple accounts).
    """
    scope = 'referral_signup'
    THROTTLE_RATES = {'referral_signup': '5/hour'}


class ReferralInviteThrottle(UserRateThrottle):
    """
    Throttle for email invitation sending.
    20 invites per day per user.
    """
    scope = 'referral_invite'
    THROTTLE_RATES = {'referral_invite': '20/day'}


class ReferralAnonThrottle(AnonRateThrottle):
    """
    Throttle for anonymous referral link clicks.
    60 requests/minute per IP.
    """
    scope = 'referral_anon'
    THROTTLE_RATES = {'referral_anon': '60/minute'}


class ReferralRedirectThrottle(SimpleRateThrottle):
    """
    Throttle for /go/<code>/ redirect endpoint.
    30 redirects per minute per IP.
    """
    scope = 'referral_redirect'
    THROTTLE_RATES = {'referral_redirect': '30/minute'}

    def get_cache_key(self, request, view):
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        return f'throttle_{self.scope}_{ip}'


class AdminReferralThrottle(UserRateThrottle):
    """
    Throttle for admin referral endpoints.
    500 requests/hour for admins.
    """
    scope = 'referral_admin'
    THROTTLE_RATES = {'referral_admin': '500/hour'}

    def allow_request(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        return super().allow_request(request, view)


class FraudCheckThrottle(UserRateThrottle):
    """
    Throttle for fraud review actions.
    50/hour per admin.
    """
    scope = 'referral_fraud'
    THROTTLE_RATES = {'referral_fraud': '50/hour'}


class WebhookThrottle(SimpleRateThrottle):
    """
    Throttle for incoming postback webhooks.
    1000/minute (high traffic).
    """
    scope = 'referral_webhook'
    THROTTLE_RATES = {'referral_webhook': '1000/minute'}

    def get_cache_key(self, request, view):
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f'throttle_{self.scope}_{ip}'


# ── Settings snippet ──────────────────────────────────────────────────────────
# settings.py এ যোগ করুন:
#
# REST_FRAMEWORK = {
#     ...
#     'DEFAULT_THROTTLE_CLASSES': [
#         'api.referral.throttling.ReferralUserThrottle',
#     ],
#     'DEFAULT_THROTTLE_RATES': {
#         'referral_user':     '100/hour',
#         'referral_signup':   '5/hour',
#         'referral_invite':   '20/day',
#         'referral_anon':     '60/minute',
#         'referral_redirect': '30/minute',
#         'referral_admin':    '500/hour',
#         'referral_fraud':    '50/hour',
#         'referral_webhook':  '1000/minute',
#     },
# }