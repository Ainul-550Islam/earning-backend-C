# fraud_detection/detectors/GeoVelocityDetector.py
from __future__ import annotations
import logging, math
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

class GeoVelocityDetector:
    """Impossible-travel detector using IP geolocation timestamps."""

    MAX_HUMAN_SPEED_KMH = 1000   # ~max commercial flight speed

    def __init__(self):
        self._cfg = {
            "max_speed_kmh":    self.MAX_HUMAN_SPEED_KMH,
            "cache_ttl":        3600 * 6,   # remember last location 6h
            "high_risk_speed":  5000,        # >5000 km/h = impossible
        }

    def _ip_to_coords(self, ip: str) -> Optional[tuple]:
        """Look up lat/lng for IP from DB (IPReputation model)."""
        try:
            from api.fraud_detection.models import IPReputation
            rec = IPReputation.objects.filter(ip_address=ip).first()
            if rec and rec.latitude and rec.longitude:
                return float(rec.latitude), float(rec.longitude)
        except Exception:
            pass
        return None

    def _haversine_km(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi       = math.radians(lat2 - lat1)
        dlambda    = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        user_id    = data.get("user_id")
        ip         = data.get("ip_address", "")
        now_ts     = float(data.get("timestamp", timezone.now().timestamp()))

        if not user_id or not ip:
            return {"risk_score": 0, "is_impossible_travel": False,
                    "reason": "insufficient_data"}

        coords = self._ip_to_coords(ip)
        cache_key = f"geo_vel:{user_id}"
        last_data = cache.get(cache_key)

        if coords:
            cache.set(cache_key,
                      {"coords": coords, "ts": now_ts, "ip": ip},
                      timeout=self._cfg["cache_ttl"])

        if last_data and coords and last_data.get("coords"):
            last_coords = last_data["coords"]
            last_ts     = last_data["ts"]
            time_diff_h = (now_ts - last_ts) / 3600

            if time_diff_h > 0.01:  # ignore < 36 seconds
                dist_km    = self._haversine_km(*last_coords, *coords)
                speed_kmh  = dist_km / time_diff_h if time_diff_h > 0 else 0

                if speed_kmh > self._cfg["high_risk_speed"]:
                    return {
                        "risk_score":           95,
                        "is_impossible_travel": True,
                        "speed_kmh":            round(speed_kmh, 1),
                        "distance_km":          round(dist_km, 1),
                        "time_diff_hours":      round(time_diff_h, 3),
                        "prev_ip":              last_data.get("ip"),
                        "current_ip":           ip,
                        "reason":               "impossible_travel",
                    }
                elif speed_kmh > self._cfg["max_speed_kmh"]:
                    return {
                        "risk_score":           75,
                        "is_impossible_travel": True,
                        "speed_kmh":            round(speed_kmh, 1),
                        "distance_km":          round(dist_km, 1),
                        "time_diff_hours":      round(time_diff_h, 3),
                        "reason":               "suspicious_travel_speed",
                    }

        return {
            "risk_score":           0,
            "is_impossible_travel": False,
            "ip":                   ip,
            "has_geolocation":      coords is not None,
        }

    def batch_detect(self, events: List[Dict]) -> List[Dict]:
        return [self.detect(e) for e in events]
