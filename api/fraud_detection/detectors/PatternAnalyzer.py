# fraud_detection/detectors/PatternAnalyzer.py
from __future__ import annotations
import logging, statistics
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

class PatternAnalyzer:
    """ML-inspired pattern analyzer using statistical heuristics on event streams."""

    def __init__(self):
        self._cfg = {
            "min_events_for_analysis": 3,
            "anomaly_std_threshold": 2.5,
            "velocity_window_secs": 3600,
        }

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []; patterns = []
        user_id = data.get("user_id")
        events  = data.get("events", [])

        if len(events) < self._cfg["min_events_for_analysis"]:
            return {"risk_score": 0, "is_anomaly": False, "patterns": [],
                    "reason": "insufficient_data"}

        # Timing analysis: check for unnaturally uniform intervals (bot)
        timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
        if len(timestamps) >= 3:
            try:
                ts_floats = [float(t) for t in timestamps]
                intervals = [ts_floats[i+1]-ts_floats[i] for i in range(len(ts_floats)-1)]
                if intervals:
                    mean_iv = statistics.mean(intervals)
                    stdev   = statistics.stdev(intervals) if len(intervals) > 1 else 0
                    cv      = stdev / mean_iv if mean_iv > 0 else 0
                    if cv < 0.05 and mean_iv < 2:
                        risk += 70; reasons.append("robotic_timing")
                        patterns.append({"type": "uniform_timing", "cv": round(cv, 4)})
            except Exception:
                pass

        # Event type diversity (bots repeat same event)
        event_types = [e.get("type") for e in events if e.get("type")]
        if event_types:
            unique_ratio = len(set(event_types)) / len(event_types)
            if unique_ratio < 0.15:
                risk += 40; reasons.append("low_event_diversity")
                patterns.append({"type": "repetitive_events", "unique_ratio": round(unique_ratio, 3)})

        # Velocity spike
        if user_id and len(events) > 30:
            risk += 30; reasons.append("high_event_volume")

        risk = min(risk, 100)
        return {
            "risk_score": risk,
            "is_anomaly": risk >= 50,
            "patterns":   patterns,
            "reasons":    reasons,
            "event_count": len(events),
        }

    def detect(self, data: Dict) -> Dict:
        return self.analyze(data)

    def batch_detect(self, users: List[Dict]) -> List[Dict]:
        return [self.analyze(u) for u in users]
