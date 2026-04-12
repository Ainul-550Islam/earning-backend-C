"""
api/users/throttling.py
Per-user, per-action rate limiting
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Login endpoint — anonymous"""
    scope = 'login'
    rate  = '10/hour'

    def get_cache_key(self, request, view):
        ip = self.get_ident(request)
        return f'throttle_login_{ip}'


class OTPRequestThrottle(AnonRateThrottle):
    """OTP request — abuse রোধ করো"""
    scope = 'otp_request'
    rate  = '5/hour'


class OTPVerifyThrottle(AnonRateThrottle):
    scope = 'otp_verify'
    rate  = '10/hour'


class RegistrationThrottle(AnonRateThrottle):
    scope = 'registration'
    rate  = '5/hour'


class ProfileUpdateThrottle(UserRateThrottle):
    scope = 'profile_update'
    rate  = '30/hour'


class PasswordChangeThrottle(UserRateThrottle):
    scope = 'password_change'
    rate  = '5/hour'


class AvatarUploadThrottle(UserRateThrottle):
    scope = 'avatar_upload'
    rate  = '10/day'


class MagicLinkThrottle(AnonRateThrottle):
    scope = 'magic_link'
    rate  = '3/hour'


class APIKeyThrottle(SimpleRateThrottle):
    """API key দিয়ে access করলে"""
    scope = 'api_key'
    rate  = '1000/hour'

    def get_cache_key(self, request, view):
        if hasattr(request, 'api_key_id'):
            return f'throttle_apikey_{request.api_key_id}'
        return None


class TierBasedThrottle(UserRateThrottle):
    """
    Tier অনুযায়ী আলাদা rate limit।
    Free user কম, Diamond user বেশি।
    """
    scope = 'tier_based'

    TIER_RATES = {
        'FREE':     '100/hour',
        'BRONZE':   '200/hour',
        'SILVER':   '500/hour',
        'GOLD':     '1000/hour',
        'PLATINUM': '2000/hour',
        'DIAMOND':  '5000/hour',
    }

    def get_rate(self):
        if self.request and self.request.user.is_authenticated:
            tier = getattr(self.request.user, 'tier', 'FREE')
            return self.TIER_RATES.get(tier, '100/hour')
        return '50/hour'


# ─────────────────────────────────────────
# settings.py-তে যোগ করো:
# ─────────────────────────────────────────
# REST_FRAMEWORK = {
#     'DEFAULT_THROTTLE_CLASSES': [
#         'rest_framework.throttling.AnonRateThrottle',
#         'rest_framework.throttling.UserRateThrottle',
#     ],
#     'DEFAULT_THROTTLE_RATES': {
#         'anon':          '100/day',
#         'user':          '1000/day',
#         'login':         '10/hour',
#         'otp_request':   '5/hour',
#         'otp_verify':    '10/hour',
#         'registration':  '5/hour',
#         'profile_update':'30/hour',
#         'password_change':'5/hour',
#         'avatar_upload': '10/day',
#         'magic_link':    '3/hour',
#         'api_key':       '1000/hour',
#         'tier_based':    '100/hour',
#     }
# }
