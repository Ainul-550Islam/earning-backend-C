# fraud_detection/detectors/BehavioralBiometricsAnalyzer.py
from __future__ import annotations
import logging, statistics
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

class BehavioralBiometricsAnalyzer:
    """Session biometrics: typing cadence, mouse dynamics, scroll patterns."""

    def __init__(self):
        self._cfg = {
            "min_keystrokes":     10,
            "bot_wpm_threshold":  200,   # >200 WPM = bot
            "low_wpm_threshold":  5,     # <5 WPM = scripted slow-type
            "mouse_linearity_threshold": 0.98,  # Too linear = scripted
        }

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []; signals = {}
        user_id    = data.get("user_id")
        session_id = data.get("session_id", "")
        keystrokes = data.get("keystrokes", [])
        mouse      = data.get("mouse_events", [])
        duration   = data.get("duration_ms", 0)

        # 1. Typing speed analysis
        if len(keystrokes) >= self._cfg["min_keystrokes"] and duration > 0:
            chars_per_sec = len(keystrokes) / (duration / 1000)
            wpm           = chars_per_sec * 12  # approx words per minute
            signals["wpm"] = round(wpm, 1)
            if wpm > self._cfg["bot_wpm_threshold"]:
                risk += 70; reasons.append(f"superhuman_typing:{wpm:.0f}wpm")
            elif wpm < self._cfg["low_wpm_threshold"] and duration > 5000:
                risk += 20; reasons.append("scripted_slow_typing")

        # 2. Keystroke interval uniformity (bots have perfect timing)
        if len(keystrokes) >= 5:
            try:
                intervals = [abs(keystrokes[i+1] - keystrokes[i])
                             for i in range(len(keystrokes)-1)
                             if isinstance(keystrokes[i], (int, float))]
                if intervals:
                    stdev = statistics.stdev(intervals) if len(intervals) > 1 else 0
                    mean  = statistics.mean(intervals)
                    cv    = stdev / mean if mean > 0 else 0
                    signals["keystroke_cv"] = round(cv, 4)
                    if cv < 0.03:
                        risk += 60; reasons.append("robotic_keystroke_timing")
            except Exception:
                pass

        # 3. Mouse linearity (scripted mice move in straight lines)
        if len(mouse) >= 10:
            try:
                xs = [m[0] for m in mouse if isinstance(m, (list, tuple)) and len(m) >= 2]
                ys = [m[1] for m in mouse if isinstance(m, (list, tuple)) and len(m) >= 2]
                if len(xs) >= 3:
                    x_range = max(xs) - min(xs)
                    y_range = max(ys) - min(ys)
                    if x_range > 0:
                        linearity = y_range / x_range if x_range > 10 else 0
                        signals["mouse_linearity"] = round(linearity, 3)
                        if linearity > self._cfg["mouse_linearity_threshold"]:
                            risk += 40; reasons.append("scripted_mouse_movement")
            except Exception:
                pass

        # 4. No mouse events at all on a form page = likely script
        if not mouse and len(keystrokes) > 20:
            risk += 25; reasons.append("no_mouse_with_many_keystrokes")

        risk = min(risk, 100)
        return {
            "risk_score": risk,
            "is_bot":     risk >= 60,
            "reasons":    reasons,
            "signals":    signals,
            "user_id":    user_id,
            "session_id": session_id,
        }

    def detect(self, data: Dict) -> Dict:
        return self.analyze(data)

    def batch_detect(self, sessions: List[Dict]) -> List[Dict]:
        return [self.analyze(s) for s in sessions]
