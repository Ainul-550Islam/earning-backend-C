# =============================================================================
# fraud_detection/detectors/ClickFraudDetector.py
# =============================================================================
"""Click-fraud detector: bots, duplicates, velocity abuse on offer completions."""
from __future__ import annotations
import hashlib, logging
from datetime import timedelta
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

class ClickFraudDetector:
    def __init__(self):
        self._cfg = {
            "max_clicks_per_ip_per_hour": 50,
            "max_clicks_per_user_per_offer": 3,
            "duplicate_window_seconds": 60,
            "bot_ua_patterns": [
                "HeadlessChrome","PhantomJS","Selenium","python-requests",
                "curl","wget","scrapy","bot","crawler","spider",
            ],
        }

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []
        user_id   = data.get("user_id")
        ip        = data.get("ip_address","")
        offer_id  = data.get("offer_id")
        ua        = data.get("user_agent","")
        click_id  = data.get("click_id","")
        ts        = data.get("timestamp")

        # 1. Bot UA check
        if any(p.lower() in ua.lower() for p in self._cfg["bot_ua_patterns"]):
            risk += 70; reasons.append("bot_user_agent")

        # 2. Duplicate click check
        if click_id:
            dup_key = f"click:dup:{hashlib.md5(click_id.encode()).hexdigest()}"
            if cache.get(dup_key):
                risk += 60; reasons.append("duplicate_click")
            else:
                cache.set(dup_key, 1, timeout=self._cfg["duplicate_window_seconds"])

        # 3. IP velocity check
        if ip:
            ip_key = f"click:ip_vel:{ip}:{timezone.now().strftime('%Y%m%d%H')}"
            count  = cache.get(ip_key, 0) + 1
            cache.set(ip_key, count, timeout=3600)
            if count > self._cfg["max_clicks_per_ip_per_hour"]:
                risk += 50; reasons.append(f"ip_velocity:{count}")

        # 4. User × offer velocity
        if user_id and offer_id:
            uo_key = f"click:user_offer:{user_id}:{offer_id}"
            uo_count = cache.get(uo_key, 0) + 1
            cache.set(uo_key, uo_count, timeout=86400)
            if uo_count > self._cfg["max_clicks_per_user_per_offer"]:
                risk += 40; reasons.append(f"user_offer_repeat:{uo_count}")

        risk = min(risk, 100)
        return {
            "risk_score": risk,
            "is_fraud":   risk >= 60,
            "reasons":    reasons,
            "user_id":    user_id,
            "ip_address": ip,
        }

    def batch_detect(self, events: List[Dict]) -> List[Dict]:
        return [self.detect(e) for e in events]


# =============================================================================
# fraud_detection/detectors/DeviceFingerprinter.py
# =============================================================================
