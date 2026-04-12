# api/offer_inventory/security_fraud/duplicate_click_prevention.py
"""
Duplicate Click Prevention.
Detects and blocks repeated clicks from the same user/IP/device
within configurable time windows.
"""
import hashlib
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Windows: (seconds, max_allowed)
CLICK_WINDOWS = {
    'instant': (3,    1),    # Same user+offer within 3s
    'minute' : (60,   3),    # Same user+offer within 1 min
    'daily'  : (86400, 5),   # Same user+offer within 24h
}


class DuplicateClickPrevention:
    """
    Two-layer duplicate prevention:
    Layer 1 — Redis counters (fast, per time window)
    Layer 2 — DuplicateConversionFilter DB table (persistent)
    """

    @staticmethod
    def check_and_record(user_id, offer_id: str,
                         ip: str, click_token: str) -> dict:
        """
        Returns: {'allowed': bool, 'reason': str, 'window': str}
        """
        # Layer 1: Redis window check
        for window_name, (window_sec, max_allowed) in CLICK_WINDOWS.items():
            key   = DuplicateClickPrevention._window_key(
                user_id, offer_id, ip, window_name
            )
            count = cache.get(key, 0)

            if count >= max_allowed:
                logger.warning(
                    f'Duplicate click blocked | user={user_id} '
                    f'offer={offer_id} window={window_name} count={count}'
                )
                return {
                    'allowed': False,
                    'reason' : f'duplicate_{window_name}',
                    'window' : window_name,
                    'count'  : count,
                }

        # All windows OK → record the click
        DuplicateClickPrevention._record_click(user_id, offer_id, ip)

        return {'allowed': True, 'reason': '', 'window': '', 'count': 0}

    @staticmethod
    def _record_click(user_id, offer_id: str, ip: str):
        """Increment all window counters."""
        for window_name, (window_sec, _) in CLICK_WINDOWS.items():
            key   = DuplicateClickPrevention._window_key(
                user_id, offer_id, ip, window_name
            )
            count = cache.get(key, 0)
            cache.set(key, count + 1, window_sec)

    @staticmethod
    def _window_key(user_id, offer_id: str, ip: str, window: str) -> str:
        raw = f'{user_id}:{offer_id}:{ip}'
        h   = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return f'dup_click:{h}:{window}'

    @staticmethod
    def is_globally_blocked(user_id, offer_id: str) -> bool:
        """Check DB DuplicateConversionFilter."""
        from api.offer_inventory.models import DuplicateConversionFilter
        return DuplicateConversionFilter.objects.filter(
            user_id=user_id, offer_id=offer_id, is_blocked=True
        ).exists()

    @staticmethod
    def reset_for_offer(user_id, offer_id: str, ip: str):
        """Clear counters — used after reversal."""
        for window_name in CLICK_WINDOWS:
            key = DuplicateClickPrevention._window_key(user_id, offer_id, ip, window_name)
            cache.delete(key)
