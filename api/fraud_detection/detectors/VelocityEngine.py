# fraud_detection/detectors/VelocityEngine.py
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default limits: (event_type, per_user_per_hour, per_ip_per_hour)
DEFAULT_LIMITS = {
    "login":        (10,  30),
    "withdrawal":   (5,   20),
    "offer_click":  (30, 100),
    "referral":     (5,   15),
    "kyc_attempt":  (3,   10),
    "api_call":     (500, 2000),
    "*":            (100, 500),    # catch-all
}

class VelocityEngine:
    """Sliding-window velocity check engine."""

    def __init__(self):
        self._cfg = {
            "window_secs":  3600,
            "limits":       DEFAULT_LIMITS,
            "burst_multiplier": 3,   # allow 3x limit in 60s burst window
            "burst_window_secs": 60,
        }

    def check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        user_id    = str(data.get("user_id", "anon"))
        event_type = data.get("event_type", "*")
        ip         = data.get("ip_address", "")
        now_bucket = int(timezone.now().timestamp() // self._cfg["window_secs"])

        limits     = self._cfg["limits"].get(event_type, self._cfg["limits"]["*"])
        user_limit, ip_limit = limits

        # User counter
        u_key   = f"vel:u:{user_id}:{event_type}:{now_bucket}"
        u_count = cache.get(u_key, 0) + 1
        cache.set(u_key, u_count, timeout=self._cfg["window_secs"] + 60)

        # IP counter
        ip_count = 0
        if ip:
            ip_key   = f"vel:ip:{ip}:{event_type}:{now_bucket}"
            ip_count = cache.get(ip_key, 0) + 1
            cache.set(ip_key, ip_count, timeout=self._cfg["window_secs"] + 60)

        # Burst check (60-second window)
        burst_bucket = int(timezone.now().timestamp() // self._cfg["burst_window_secs"])
        bu_key    = f"vel:burst:u:{user_id}:{event_type}:{burst_bucket}"
        bu_count  = cache.get(bu_key, 0) + 1
        cache.set(bu_key, bu_count, timeout=self._cfg["burst_window_secs"] + 10)
        burst_limit = max(1, user_limit // 10) * self._cfg["burst_multiplier"]

        user_breach  = u_count > user_limit
        ip_breach    = ip_count > ip_limit
        burst_breach = bu_count > burst_limit

        risk = 0; reasons = []
        if burst_breach: risk += 80; reasons.append(f"burst:{bu_count}>{burst_limit}")
        if user_breach:  risk += 60; reasons.append(f"user_velocity:{u_count}>{user_limit}")
        if ip_breach:    risk += 50; reasons.append(f"ip_velocity:{ip_count}>{ip_limit}")

        risk = min(risk, 100)
        return {
            "risk_score":    risk,
            "breach":        risk >= 60,
            "user_count":    u_count,
            "ip_count":      ip_count,
            "burst_count":   bu_count,
            "user_limit":    user_limit,
            "ip_limit":      ip_limit,
            "burst_limit":   burst_limit,
            "reasons":       reasons,
            "event_type":    event_type,
        }

    def batch_check(self, events: List[Dict]) -> List[Dict]:
        return [self.check(e) for e in events]

    def batch_detect(self, events: List[Dict]) -> List[Dict]:
        return self.batch_check(events)

    def detect(self, data: Dict) -> Dict:
        return self.check(data)

    def reset(self, user_id: Optional[str] = None,
              event_type: Optional[str] = None,
              ip_address: Optional[str] = None) -> Dict:
        """Clear velocity counters for a user / event_type / IP."""
        now_bucket  = int(timezone.now().timestamp() // self._cfg["window_secs"])
        burst_bucket = int(timezone.now().timestamp() // self._cfg["burst_window_secs"])
        cleared = 0

        event_types = [event_type] if event_type else list(DEFAULT_LIMITS.keys())
        for et in event_types:
            if user_id:
                for key in [f"vel:u:{user_id}:{et}:{now_bucket}",
                            f"vel:burst:u:{user_id}:{et}:{burst_bucket}"]:
                    if cache.delete(key): cleared += 1
            if ip_address:
                key = f"vel:ip:{ip_address}:{et}:{now_bucket}"
                if cache.delete(key): cleared += 1

        return {"reset": True, "keys_cleared": cleared,
                "user_id": user_id, "ip_address": ip_address}
