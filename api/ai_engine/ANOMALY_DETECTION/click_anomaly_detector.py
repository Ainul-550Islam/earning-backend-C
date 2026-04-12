"""
api/ai_engine/ANOMALY_DETECTION/click_anomaly_detector.py
==========================================================
Click Anomaly Detector — click fraud detection।
Bot clicks, incentivized clicks, click farms।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class ClickAnomalyDetector:
    """Click fraud and anomaly detection।"""

    def detect(self, click_data: dict) -> dict:
        score  = 0.0
        flags  = []

        # Click velocity
        clicks_per_min = float(click_data.get("clicks_per_minute", 0))
        if clicks_per_min > 60:  score += 0.70; flags.append("bot_speed_clicks")
        elif clicks_per_min > 30: score += 0.40; flags.append("high_click_velocity")
        elif clicks_per_min > 10: score += 0.15; flags.append("elevated_click_rate")

        # Same IP multiple clicks
        same_ip_clicks = int(click_data.get("same_ip_clicks", 0))
        if same_ip_clicks > 100: score += 0.60; flags.append("ip_click_farm")
        elif same_ip_clicks > 20: score += 0.30; flags.append("ip_click_abuse")

        # Click-through time
        avg_visit_seconds = float(click_data.get("avg_visit_duration", 30))
        if avg_visit_seconds < 2:  score += 0.50; flags.append("immediate_bounce_bot")
        elif avg_visit_seconds < 5: score += 0.25; flags.append("very_short_visit")

        # Device distribution
        unique_devices    = int(click_data.get("unique_devices", 1))
        total_clicks      = int(click_data.get("total_clicks", 1))
        clicks_per_device = total_clicks / max(unique_devices, 1)
        if clicks_per_device > 50: score += 0.40; flags.append("device_click_farm")

        # VPN/Proxy
        if click_data.get("vpn_pct", 0) > 0.30:   score += 0.30; flags.append("high_vpn_clicks")
        if click_data.get("datacenter_pct", 0) > 0.20: score += 0.40; flags.append("datacenter_traffic")

        score = min(1.0, score)
        return {
            "is_fraud":          score >= 0.65,
            "fraud_score":       round(score, 4),
            "severity":          "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.40 else "low",
            "flags":             flags,
            "recommendation":    "block_source" if score >= 0.85 else "investigate" if score >= 0.65 else "monitor",
            "estimated_invalid": round(min(score, 1.0) * 100, 1),
        }

    def batch_analyze(self, clicks: List[Dict]) -> dict:
        if not clicks: return {"invalid_rate": 0.0}
        results    = [self.detect(c) for c in clicks]
        fraud_count = sum(1 for r in results if r["is_fraud"])
        return {
            "total_clicks":     len(clicks),
            "invalid_clicks":   fraud_count,
            "invalid_rate":     round(fraud_count / len(clicks), 4),
            "avg_fraud_score":  round(sum(r["fraud_score"] for r in results) / len(results), 4),
            "top_flags":        self._count_flags(results),
        }

    def _count_flags(self, results: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in results:
            for flag in r.get("flags", []):
                counts[flag] = counts.get(flag, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5])

    def real_time_gate(self, click_data: dict) -> bool:
        """Real-time click accept/reject (<10ms)।"""
        result = self.detect(click_data)
        return not result["is_fraud"]
