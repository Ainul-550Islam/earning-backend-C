# api/rate_limit/events.py
"""Event creation utilities for rate limit module."""
import logging
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


def create_rate_limit_exceeded_event(user=None, ip_address="", endpoint="", config=None):
    """Create a rate_limit_exceeded event dict."""
    return {
        "type": "rate_limit_exceeded",
        "timestamp": timezone.now().isoformat(),
        "user_id": getattr(user, "id", None) if user else None,
        "ip_address": ip_address,
        "endpoint": endpoint,
        "config_name": getattr(config, "name", "") if config else "",
    }


def create_abuse_detected_event(user=None, ip_address="", abuse_type="", severity=1):
    """Create an abuse_detected event dict."""
    return {
        "type": "abuse_detected",
        "timestamp": timezone.now().isoformat(),
        "user_id": getattr(user, "id", None) if user else None,
        "ip_address": ip_address,
        "abuse_type": abuse_type,
        "severity": severity,
    }


def create_ip_blocked_event(ip_address="", reason="", duration_hours=24):
    """Create an ip_blocked event dict."""
    return {
        "type": "ip_blocked",
        "timestamp": timezone.now().isoformat(),
        "ip_address": ip_address,
        "reason": reason,
        "duration_hours": duration_hours,
    }


__all__ = [
    "create_rate_limit_exceeded_event",
    "create_abuse_detected_event",
    "create_ip_blocked_event",
]
