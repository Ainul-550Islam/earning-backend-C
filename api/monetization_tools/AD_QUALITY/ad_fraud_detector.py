"""AD_QUALITY/ad_fraud_detector.py — Comprehensive ad fraud detection."""
from decimal import Decimal


class AdFraudDetector:
    """Multi-signal fraud scoring for offer completions and clicks."""

    @classmethod
    def score(cls, user=None, ip: str = "", user_agent: str = "",
               is_vpn: bool = False, is_proxy: bool = False,
               device_id: str = "", completion_time_sec: int = None,
               offer_type: str = "") -> dict:
        score   = 0
        signals = []

        if is_vpn:
            score += 30; signals.append("vpn_detected")
        if is_proxy:
            score += 40; signals.append("proxy_detected")

        bot_uas = ["bot", "spider", "crawler", "curl", "wget"]
        if any(b in (user_agent or "").lower() for b in bot_uas):
            score += 50; signals.append("bot_user_agent")

        if completion_time_sec is not None and completion_time_sec < 5:
            score += 25; signals.append("too_fast_completion")

        if user and hasattr(user, "account_level") and user.account_level == "blocked":
            score += 100; signals.append("blocked_account")

        return {
            "fraud_score": min(100, score),
            "signals":     signals,
            "is_fraud":    score >= 70,
            "should_flag": score >= 50,
        }

    @classmethod
    def check_duplicate(cls, user, offer_id: int) -> bool:
        from ..models import OfferCompletion
        return OfferCompletion.objects.filter(
            user=user, offer_id=offer_id, status="approved"
        ).exists()
