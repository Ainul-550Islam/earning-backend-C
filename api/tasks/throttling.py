"""
api/tasks/throttling.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom DRF throttle classes for the task system.
Fine-grained rate limiting per endpoint type.
"""

from rest_framework.throttling import (
    UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
)


class TaskCompletionThrottle(UserRateThrottle):
    """
    Throttle for task completion submissions.
    Default: 20 completions per hour per user.
    Prevents automated bot completions.
    """
    scope = 'task_completion'
    rate  = '20/hour'


class WithdrawalThrottle(UserRateThrottle):
    """
    Throttle for withdrawal requests.
    Default: 5 withdrawals per day.
    """
    scope = 'withdrawal'
    rate  = '5/day'


class PostbackThrottle(SimpleRateThrottle):
    """
    Throttle for incoming S2S postback endpoints.
    High limit — postbacks can be frequent.
    Default: 10000 per hour per IP.
    """
    scope = 'postback'
    rate  = '10000/hour'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class OfferWallThrottle(UserRateThrottle):
    """
    Throttle for offer wall API requests.
    Default: 200 per hour per user.
    """
    scope = 'offerwall'
    rate  = '200/hour'


class PublisherStatsThrottle(UserRateThrottle):
    """
    Throttle for publisher stats/analytics API.
    Default: 100 per hour.
    """
    scope = 'publisher_stats'
    rate  = '100/hour'


class AnonPostbackThrottle(AnonRateThrottle):
    """
    Throttle for unauthenticated postback endpoints.
    Default: 1000 per hour per IP.
    """
    scope = 'anon_postback'
    rate  = '1000/hour'


class ReportGenerationThrottle(UserRateThrottle):
    """
    Throttle for report generation requests.
    Heavy operations — default: 5 per hour.
    """
    scope = 'report_generation'
    rate  = '5/hour'


class BulkOperationThrottle(UserRateThrottle):
    """
    Throttle for bulk operations (bulk activate, bulk export).
    Default: 10 per hour per user.
    """
    scope = 'bulk_operation'
    rate  = '10/hour'


class AdminOperationThrottle(UserRateThrottle):
    """
    Throttle for admin operations (DLQ flush, workflow trigger).
    Default: 50 per hour for staff users.
    """
    scope = 'admin_operation'
    rate  = '50/hour'

    def allow_request(self, request, view):
        # Staff get a higher limit
        if request.user.is_authenticated and request.user.is_staff:
            self.rate  = '200/hour'
            self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


class CryptoWithdrawalThrottle(UserRateThrottle):
    """
    Throttle for crypto withdrawal requests.
    Default: 3 per day (high-value operations).
    """
    scope = 'crypto_withdrawal'
    rate  = '3/day'


class QuizCompletionThrottle(UserRateThrottle):
    """
    Throttle for quiz completions.
    Default: 10 per hour per user.
    """
    scope = 'quiz_completion'
    rate  = '10/hour'


class EmailSubmitThrottle(UserRateThrottle):
    """
    Throttle for email submit offers.
    Default: 5 per hour per user.
    """
    scope = 'email_submit'
    rate  = '5/hour'


class ContentLockerThrottle(UserRateThrottle):
    """
    Throttle for content locker unlock requests.
    Default: 50 per hour per user.
    """
    scope = 'content_locker'
    rate  = '50/hour'


class ApiKeyGenerationThrottle(UserRateThrottle):
    """
    Throttle for API key generation.
    Default: 5 per day per user.
    """
    scope = 'api_key_generation'
    rate  = '5/day'


# ── THROTTLE RATE SETTINGS (add to settings.py) ───────────────────────────
DEFAULT_THROTTLE_RATES = {
    'task_completion':   '20/hour',
    'withdrawal':        '5/day',
    'postback':          '10000/hour',
    'offerwall':         '200/hour',
    'publisher_stats':   '100/hour',
    'anon_postback':     '1000/hour',
    'report_generation': '5/hour',
    'bulk_operation':    '10/hour',
    'admin_operation':   '50/hour',
    'crypto_withdrawal': '3/day',
    'quiz_completion':   '10/hour',
    'email_submit':      '5/hour',
    'content_locker':    '50/hour',
    'api_key_generation': '5/day',
}


__all__ = [
    'TaskCompletionThrottle', 'WithdrawalThrottle', 'PostbackThrottle',
    'OfferWallThrottle', 'PublisherStatsThrottle', 'AnonPostbackThrottle',
    'ReportGenerationThrottle', 'BulkOperationThrottle', 'AdminOperationThrottle',
    'CryptoWithdrawalThrottle', 'QuizCompletionThrottle', 'EmailSubmitThrottle',
    'ContentLockerThrottle', 'ApiKeyGenerationThrottle',
    'DEFAULT_THROTTLE_RATES',
]
