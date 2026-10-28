# engagement/services/adapters/__init__.py
"""
Engagement External System Adapters
=====================================
Each adapter wraps ONE external app with:
  - Safe import (no ImportError crash if app missing)
  - Canonical engagement-facing API
  - Full fallback when external app unavailable
  - Structured result dicts (never raw ORM objects)

Adapters:
    RateLimitAdapter       — api.rate_limit   → check spin/checkin/task velocity
    FraudDetectionAdapter  — api.fraud_detection → score + auto-ban user
    SecurityAdapter        — api.security     → bot/click-fraud/device trust
    ProxyIntelAdapter      — api.proxy_intelligence → IP/VPN/proxy check
    KYCAdapter             — api.kyc          → verification status + compliance
    AuditLogAdapter        — api.audit_logs   → write structured audit events
    BehaviorAnalyticsAdapter— api.behavior_analytics → track + score behavior
    AlertsAdapter          — api.alerts       → fire system alerts
    AutoModAdapter         — api.auto_mod     → content/action moderation
    AnalyticsAdapter       — api.analytics    → track engagement metrics

Usage inside engagement services:
    from api.engagement.services.adapters import RateLimitAdapter, FraudDetectionAdapter

    # Before awarding spin reward
    rl = RateLimitAdapter.check_action(user, "spin", ip=request.META.get("REMOTE_ADDR"))
    if not rl["allowed"]:
        raise ThrottledError(rl["retry_after"])

    # After checkin
    FraudDetectionAdapter.score_and_act(user, action="checkin", ip=ip)
"""

from .rate_limit_adapter      import RateLimitAdapter
from .fraud_detection_adapter import FraudDetectionAdapter
from .security_adapter        import SecurityAdapter
from .proxy_intel_adapter     import ProxyIntelAdapter
from .kyc_adapter             import KYCAdapter
from .audit_log_adapter       import AuditLogAdapter
from .behavior_analytics_adapter import BehaviorAnalyticsAdapter
from .alerts_adapter          import AlertsAdapter
from .auto_mod_adapter        import AutoModAdapter
from .analytics_adapter       import AnalyticsAdapter

__all__ = [
    "RateLimitAdapter",
    "FraudDetectionAdapter",
    "SecurityAdapter",
    "ProxyIntelAdapter",
    "KYCAdapter",
    "AuditLogAdapter",
    "BehaviorAnalyticsAdapter",
    "AlertsAdapter",
    "AutoModAdapter",
    "AnalyticsAdapter",
]
