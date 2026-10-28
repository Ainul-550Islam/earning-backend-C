# api/rate_limit/alerts.py
"""
Alert management for rate limit module.
Re-exports from monitoring for backwards compatibility.
"""
from api.rate_limit.monitoring import AlertManager, AlertRule, Alert, AlertSeverity

# Alias for test compatibility
RateLimitAlertManager = AlertManager

__all__ = [
    'RateLimitAlertManager',
    'AlertManager',
    'AlertRule',
    'Alert',
    'AlertSeverity',
]
