# fraud_detection/detectors/MultiAccountDetector.py
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

class MultiAccountDetector:
    def __init__(self):
        self._cfg = {"ip_account_threshold": 3, "device_account_threshold": 3}

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []
        user_id   = data.get("user_id")
        ip        = data.get("ip_address", "")
        device_id = data.get("device_id", "")

        if ip:
            ip_key   = f"mac:ip:{ip}"
            ip_users = cache.get(ip_key, set())
            if user_id: ip_users.add(str(user_id))
            cache.set(ip_key, ip_users, timeout=86400)
            if len(ip_users) > self._cfg["ip_account_threshold"]:
                risk += 60; reasons.append(f"ip_multi_account:{len(ip_users)}")

        if device_id:
            dev_key   = f"mac:dev:{device_id}"
            dev_users = cache.get(dev_key, set())
            if user_id: dev_users.add(str(user_id))
            cache.set(dev_key, dev_users, timeout=86400)
            if len(dev_users) > self._cfg["device_account_threshold"]:
                risk += 60; reasons.append(f"device_multi_account:{len(dev_users)}")

        # Email domain clustering
        email = data.get("email", "")
        if email and "@" in email:
            domain   = email.split("@")[1].lower()
            dom_key  = f"mac:dom:{domain}"
            dom_ids  = cache.get(dom_key, set())
            if user_id: dom_ids.add(str(user_id))
            cache.set(dom_key, dom_ids, timeout=86400)
            if len(dom_ids) > 10 and domain not in ("gmail.com","yahoo.com","outlook.com"):
                risk += 30; reasons.append(f"domain_cluster:{domain}:{len(dom_ids)}")

        risk = min(risk, 100)
        return {"risk_score": risk, "is_fraud": risk >= 60, "reasons": reasons}

    def batch_detect(self, users: List[Dict]) -> List[Dict]:
        return [self.detect(u) for u in users]
