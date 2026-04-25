# api/payment_gateways/throttling.py
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class DepositRateThrottle(UserRateThrottle):
    scope = 'deposit'
    THROTTLE_RATES = {'deposit': '10/hour'}


class WithdrawalRateThrottle(UserRateThrottle):
    scope = 'withdrawal'
    THROTTLE_RATES = {'withdrawal': '3/hour'}


class WebhookRateThrottle(AnonRateThrottle):
    """Generous limit for gateway webhooks."""
    scope = 'webhook'
    THROTTLE_RATES = {'webhook': '1000/minute'}


class PublisherAPIRateThrottle(UserRateThrottle):
    scope = 'publisher_api'
    THROTTLE_RATES = {'publisher_api': '1000/hour'}


class AdminRateThrottle(UserRateThrottle):
    scope = 'admin'
    THROTTLE_RATES = {'admin': '500/minute'}
