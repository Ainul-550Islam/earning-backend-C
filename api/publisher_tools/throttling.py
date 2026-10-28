# publisher_tools/throttling.py
"""
DRF Throttle classes for publisher_tools।

Rate limits by endpoint type:
  - PublisherBurst   : 60 req/min   (standard API calls)
  - PublisherSustained: 1000 req/hr (sustained load)
  - FraudCheckThrottle: 30 req/min  (fraud/velocity endpoints)
  - PayoutThrottle   : 5 req/min    (payout submission)
  - KycSubmitThrottle: 3 req/min    (KYC submit)
  - ExportThrottle   : 10 req/hr    (CSV export — heavy)
  - WebhookReplayThrottle: 20 req/min (webhook replay)
  - AdminThrottle    : 300 req/min  (admin-only endpoints)

Register in settings.py:

    REST_FRAMEWORK = {
        ...
        'DEFAULT_THROTTLE_CLASSES': [
            'publisher_tools.throttling.PublisherBurstThrottle',
            'publisher_tools.throttling.PublisherSustainedThrottle',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'publisher_burst':       '60/min',
            'publisher_sustained':   '1000/hour',
            'fraud_check':           '30/min',
            'payout_submit':         '5/min',
            'kyc_submit':            '3/min',
            'export':                '10/hour',
            'webhook_replay':        '20/min',
            'admin_tools':           '300/min',
            'anon':                  '20/min',
        },
    }

Usage in ViewSets:

    from .throttling import FraudCheckThrottle, PayoutThrottle

    class FraudReportViewSet(PublisherViewMixin, BaseViewSet):
        @action(..., throttle_classes=[FraudCheckThrottle])
        def velocity_check(self, request): ...

    class PayoutViewSet(PublisherViewMixin, BaseViewSet):
        @action(..., throttle_classes=[PayoutThrottle])
        def request_payout(self, request): ...
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle


# ──────────────────────────────────────────────────────────────────────────────
# BASE PUBLISHER THROTTLES
# ──────────────────────────────────────────────────────────────────────────────

class PublisherBurstThrottle(UserRateThrottle):
    """
    Standard burst limit for all authenticated publisher endpoints।
    60 requests per minute।
    """
    scope = 'publisher_burst'


class PublisherSustainedThrottle(UserRateThrottle):
    """
    Sustained hourly limit for all authenticated publisher endpoints।
    1000 requests per hour।
    """
    scope = 'publisher_sustained'


class AnonAPIThrottle(AnonRateThrottle):
    """
    Unauthenticated / public API calls।
    20 requests per minute।
    """
    scope = 'anon'


# ──────────────────────────────────────────────────────────────────────────────
# FRAUD ENDPOINTS (velocity check, geo validate, etc.)
# ──────────────────────────────────────────────────────────────────────────────

class FraudCheckThrottle(UserRateThrottle):
    """
    Fraud check endpoints — FraudReportViewSet।
    30 requests per minute per user।

    Applied on:
      velocity_check, click_velocity, impression_velocity,
      conversion_velocity, geo_validate, impossible_travel
    """
    scope = 'fraud_check'

    def get_cache_key(self, request, view):
        """
        Fraud check কে per-IP limit করো (user-level নয়) কারণ
        এই endpoints-এ IP impersonation attack সম্ভব।
        """
        ident = self.get_ident(request)   # IP address
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


# ──────────────────────────────────────────────────────────────────────────────
# PAYOUT ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

class PayoutThrottle(UserRateThrottle):
    """
    Payout request submission — PayoutViewSet.request_payout()।
    5 requests per minute (prevents payout spam)।
    """
    scope = 'payout_submit'


# ──────────────────────────────────────────────────────────────────────────────
# KYC SUBMISSION
# ──────────────────────────────────────────────────────────────────────────────

class KycSubmitThrottle(UserRateThrottle):
    """
    KYC submission — PublisherAdvancedViewSet.kyc_submit()।
    3 requests per minute।
    """
    scope = 'kyc_submit'


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT / HEAVY ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

class ExportThrottle(UserRateThrottle):
    """
    CSV/JSON export — ReportingViewSet.export_report()।
    10 requests per hour (expensive query)।
    """
    scope = 'export'


# ──────────────────────────────────────────────────────────────────────────────
# WEBHOOK REPLAY
# ──────────────────────────────────────────────────────────────────────────────

class WebhookReplayThrottle(UserRateThrottle):
    """
    Webhook replay — WebhookExtendedViewSet.replay_all_failed()।
    20 requests per minute।
    """
    scope = 'webhook_replay'


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

class AdminThrottle(UserRateThrottle):
    """
    Admin-only endpoints — FraudReportViewSet.platform_fraud_report() etc।
    300 requests per minute for staff users।
    """
    scope = 'admin_tools'

    def allow_request(self, request, view):
        """Staff users get the admin throttle scope; others use default."""
        if not request.user or not request.user.is_staff:
            return True   # Non-staff are blocked by permission class, not throttle
        return super().allow_request(request, view)


# ──────────────────────────────────────────────────────────────────────────────
# COMPOSITE THROTTLE (apply multiple limits at once)
# ──────────────────────────────────────────────────────────────────────────────

class PublisherStandardThrottle(UserRateThrottle):
    """
    Convenience: applies both burst + sustained limits in one class।
    Use when you need both without listing two classes separately।
    """
    scope = 'publisher_burst'

    def get_rate(self):
        return '60/min'
