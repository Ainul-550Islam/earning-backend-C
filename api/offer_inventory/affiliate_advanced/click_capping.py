# api/offer_inventory/affiliate_advanced/click_capping.py
"""Click Capping Engine — Prevent click flooding per user/IP/offer."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

CAPS = {
    'user_per_offer_daily' : 3,
    'user_per_offer_weekly': 10,
    'user_total_daily'     : 50,
    'ip_per_offer_daily'   : 10,
}


class ClickCappingEngine:
    """Multi-level click capping to prevent abuse."""

    @classmethod
    def check_all(cls, user_id, offer_id: str, ip: str) -> dict:
        """Run all click cap checks. Returns {'allowed': bool, 'reason': str}."""
        for check in [
            cls._user_offer_daily(user_id, offer_id),
            cls._user_total_daily(user_id),
            cls._ip_offer_daily(ip, offer_id),
        ]:
            if not check['allowed']:
                return check
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _user_offer_daily(cls, user_id, offer_id: str) -> dict:
        key   = f'cc:uod:{user_id}:{offer_id}'
        count = cache.get(key, 0)
        if count >= CAPS['user_per_offer_daily']:
            return {'allowed': False, 'reason': f'user_offer_daily:{CAPS["user_per_offer_daily"]}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _user_total_daily(cls, user_id) -> dict:
        key   = f'cc:utd:{user_id}'
        count = cache.get(key, 0)
        if count >= CAPS['user_total_daily']:
            return {'allowed': False, 'reason': f'user_total_daily:{CAPS["user_total_daily"]}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _ip_offer_daily(cls, ip: str, offer_id: str) -> dict:
        key   = f'cc:iod:{ip}:{offer_id}'
        count = cache.get(key, 0)
        if count >= CAPS['ip_per_offer_daily']:
            return {'allowed': False, 'reason': f'ip_offer_daily:{CAPS["ip_per_offer_daily"]}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def get_remaining(cls, user_id, offer_id: str, ip: str) -> dict:
        return {
            'user_offer_daily': CAPS['user_per_offer_daily'] - cache.get(f'cc:uod:{user_id}:{offer_id}', 0),
            'user_total_daily': CAPS['user_total_daily'] - cache.get(f'cc:utd:{user_id}', 0),
            'ip_offer_daily'  : CAPS['ip_per_offer_daily'] - cache.get(f'cc:iod:{ip}:{offer_id}', 0),
        }

    @classmethod
    def reset_user(cls, user_id, offer_id: str = None):
        """Reset caps for a user (admin action)."""
        if offer_id:
            cache.delete(f'cc:uod:{user_id}:{offer_id}')
        cache.delete(f'cc:utd:{user_id}')
