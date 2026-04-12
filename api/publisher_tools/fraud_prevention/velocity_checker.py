# api/publisher_tools/fraud_prevention/velocity_checker.py
"""Velocity Checker — Rate limiting and velocity-based fraud detection."""
from typing import Dict
from django.core.cache import cache


class VelocityChecker:
    """Multi-window velocity checking."""

    @staticmethod
    def check(identifier: str, event_type: str, window_seconds: int = 60, max_count: int = 10) -> Dict:
        key = f"velocity:{event_type}:{identifier}:{window_seconds}"
        count = cache.get(key, 0) + 1
        cache.set(key, count, window_seconds)
        exceeded = count > max_count
        return {
            "count": count, "max": max_count, "window_seconds": window_seconds,
            "exceeded": exceeded, "rate": round(count / window_seconds * 60, 2),
        }

    @staticmethod
    def check_multi_window(identifier: str, event_type: str) -> Dict:
        windows = [(60, 10), (300, 30), (3600, 100), (86400, 500)]
        results = {}
        for window, max_count in windows:
            result = VelocityChecker.check(identifier, event_type, window, max_count)
            results[f"{window}s"] = result
        any_exceeded = any(r["exceeded"] for r in results.values())
        return {"identifier": identifier, "event_type": event_type, "exceeded": any_exceeded, "windows": results}

    @staticmethod
    def get_current_rate(identifier: str, event_type: str, window_seconds: int = 60) -> float:
        key = f"velocity:{event_type}:{identifier}:{window_seconds}"
        count = cache.get(key, 0)
        return round(count / window_seconds * 60, 2)


def check_click_velocity(identifier: str, unit_id: str) -> Dict:
    checker = VelocityChecker()
    return checker.check_multi_window(f"{identifier}:{unit_id}", "click")


def check_impression_velocity(ip: str, unit_id: str) -> Dict:
    checker = VelocityChecker()
    return checker.check(f"{ip}:{unit_id}", "impression", 60, 200)


def check_conversion_velocity(identifier: str) -> Dict:
    checker = VelocityChecker()
    return checker.check_multi_window(identifier, "conversion")
