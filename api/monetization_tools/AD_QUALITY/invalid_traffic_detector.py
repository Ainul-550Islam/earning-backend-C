"""AD_QUALITY/invalid_traffic_detector.py — IVT (Invalid Traffic) detection."""
from decimal import Decimal
from django.core.cache import cache


class InvalidTrafficDetector:
    MAX_CLICKS_PER_IP_PER_HOUR = 30
    MAX_IMP_PER_USER_PER_UNIT  = 100

    @classmethod
    def check_click(cls, ip: str, ad_unit_id: int,
                     user_agent: str = "") -> dict:
        key   = f"mt:ivt_click:{ip}:{ad_unit_id}"
        count = int(cache.get(key, 0))
        if count >= cls.MAX_CLICKS_PER_IP_PER_HOUR:
            return {"is_ivt": True, "reason": "click_velocity_exceeded"}
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)
        bot_uas = ["bot", "spider", "crawler", "curl", "wget", "python-requests"]
        if any(b in (user_agent or "").lower() for b in bot_uas):
            return {"is_ivt": True, "reason": "bot_user_agent"}
        return {"is_ivt": False, "reason": None}

    @classmethod
    def fraud_score(cls, ip: str, user_agent: str = "",
                     is_vpn: bool = False, is_proxy: bool = False) -> int:
        score = 0
        if is_vpn:   score += 30
        if is_proxy: score += 40
        bot_uas = ["bot", "spider", "crawler"]
        if any(b in (user_agent or "").lower() for b in bot_uas):
            score += 50
        return min(100, score)
