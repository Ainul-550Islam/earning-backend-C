# fraud_detection/detectors/DeviceFingerprinter.py
from __future__ import annotations
import hashlib, logging
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

class DeviceFingerprinter:
    def __init__(self):
        self._cfg = {
            "max_users_per_device": 3,
            "max_devices_per_user": 10,
            "trust_score_threshold": 40,
        }

    def _build_fingerprint(self, data: Dict) -> str:
        parts = [
            data.get("user_agent", ""),
            data.get("screen_resolution", ""),
            data.get("timezone", ""),
            data.get("canvas_hash", ""),
        ]
        raw = "|".join(str(p) for p in parts if p)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.fingerprint(data)

    def fingerprint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []
        fp   = self._build_fingerprint(data)
        user_id = data.get("user_id")

        # Multiple users on same device
        device_users_key = f"fp:users:{fp}"
        users_set        = cache.get(device_users_key, set())
        if user_id:
            users_set.add(str(user_id))
            cache.set(device_users_key, users_set, timeout=86400 * 7)
        if len(users_set) > self._cfg["max_users_per_device"]:
            risk += 50; reasons.append(f"shared_device:{len(users_set)}_users")

        # Multiple devices per user
        if user_id:
            user_devices_key = f"fp:devices:{user_id}"
            devices_set      = cache.get(user_devices_key, set())
            devices_set.add(fp)
            cache.set(user_devices_key, devices_set, timeout=86400 * 7)
            if len(devices_set) > self._cfg["max_devices_per_user"]:
                risk += 30; reasons.append(f"many_devices:{len(devices_set)}")

        # Headless browser UA signals
        ua = data.get("user_agent", "")
        headless = ["HeadlessChrome","PhantomJS","Selenium","Puppeteer","playwright"]
        if any(h.lower() in ua.lower() for h in headless):
            risk += 60; reasons.append("headless_browser")

        risk = min(risk, 100)
        return {
            "fingerprint": fp,
            "risk_score":  risk,
            "is_suspicious": risk >= 50,
            "reasons":     reasons,
            "user_count":  len(users_set),
        }

    def batch_detect(self, devices: List[Dict]) -> List[Dict]:
        return [self.fingerprint(d) for d in devices]
