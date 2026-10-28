# engagement/utils/throttling.py
from rest_framework.throttling import UserRateThrottle


class CheckInThrottle(UserRateThrottle):
    """Max 2 check-in attempts per minute per user (prevents accidental double-hits)."""
    scope = "checkin"
    rate  = "2/min"


class SpinThrottle(UserRateThrottle):
    """Max 10 spin requests per minute (UI debounce protection)."""
    scope = "spin"
    rate  = "10/min"


class ShopPurchaseThrottle(UserRateThrottle):
    """Max 5 purchases per minute."""
    scope = "shop_purchase"
    rate  = "5/min"


class LeaderboardThrottle(UserRateThrottle):
    """Max 30 leaderboard reads per minute."""
    scope = "leaderboard"
    rate  = "30/min"
