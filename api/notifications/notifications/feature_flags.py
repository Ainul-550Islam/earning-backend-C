# earning_backend/api/notifications/feature_flags.py
"""
Feature Flags — Runtime feature toggle system for the notification system.

Allows enabling/disabling notification features without code deployments.
Flags are read from Django settings and can be overridden at runtime via cache.

Usage:
    from api.notifications.feature_flags import flags

    if flags.is_enabled("SMART_SEND_TIME"):
        optimal_time = smart_send_time_service.get_optimal_send_time(user)

    # Override in tests:
    flags.enable("PUSH_NOTIFICATIONS")
    flags.disable("SMS_NOTIFICATIONS")
"""
import logging
from typing import Dict, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_PREFIX = "notif:flag:"
CACHE_TTL = 300  # 5 minutes


# Default feature flag values
DEFAULT_FLAGS: Dict[str, bool] = {
    # Channels
    "PUSH_NOTIFICATIONS":         True,
    "EMAIL_NOTIFICATIONS":        True,
    "SMS_NOTIFICATIONS":          True,
    "TELEGRAM_NOTIFICATIONS":     True,
    "WHATSAPP_NOTIFICATIONS":     True,
    "BROWSER_PUSH":               True,
    "SLACK_NOTIFICATIONS":        True,
    "DISCORD_NOTIFICATIONS":      True,

    # Features
    "SMART_SEND_TIME":            True,
    "AB_TESTING":                 True,
    "JOURNEY_SYSTEM":             True,
    "NOTIFICATION_FATIGUE":       True,
    "OPT_OUT_SYSTEM":             True,
    "WEBSOCKET_REALTIME":         True,
    "WEBHOOK_SIGNATURE_VERIFY":   True,
    "CAMPAIGN_SYSTEM":            True,
    "BATCH_SEND":                 True,
    "NOTIFICATION_ANALYTICS":     True,
    "PII_MASKING":                True,
    "RICH_PUSH":                  True,
    "SILENT_PUSH":                True,
    "AUTO_DISCOVERY":             True,
    "INTEGRATION_SYSTEM":         True,
    "AI_CONTENT_GENERATION":      False,   # Requires OPENAI_API_KEY
    "GDPR_STRICT_MODE":           False,   # Enable for EU deployments
    "DND_ENFORCEMENT":            True,
    "RATE_LIMITING":              True,
    "AUDIT_LOGGING":              True,
    "PERFORMANCE_MONITORING":     True,
    "MAINTENANCE_MODE":           False,
    "SEND_DURING_MAINTENANCE":    False,

    # Bangladesh-specific
    "SHOHO_SMS_PRIMARY":          True,    # Use ShohoSMS first for BD numbers
    "BKASH_WEBHOOK":              True,
    "NAGAD_WEBHOOK":              True,
}


class FeatureFlagService:
    """Runtime feature flag manager for the notification system."""

    def is_enabled(self, flag: str, default: Optional[bool] = None) -> bool:
        """Check if a feature flag is enabled."""
        # 1. Check cache (runtime overrides)
        cached = cache.get(f"{CACHE_PREFIX}{flag}")
        if cached is not None:
            return cached

        # 2. Check Django settings overrides
        setting_flags = getattr(settings, "NOTIFICATION_FEATURES", {})
        if flag in setting_flags:
            return bool(setting_flags[flag])

        # 3. Use default
        if default is not None:
            return default
        return DEFAULT_FLAGS.get(flag, False)

    def enable(self, flag: str, ttl: int = CACHE_TTL):
        """Enable a feature flag at runtime."""
        cache.set(f"{CACHE_PREFIX}{flag}", True, ttl)
        logger.info(f"Feature flag enabled: {flag}")

    def disable(self, flag: str, ttl: int = CACHE_TTL):
        """Disable a feature flag at runtime."""
        cache.set(f"{CACHE_PREFIX}{flag}", False, ttl)
        logger.info(f"Feature flag disabled: {flag}")

    def reset(self, flag: str):
        """Reset a flag to its default value."""
        cache.delete(f"{CACHE_PREFIX}{flag}")

    def get_all(self) -> Dict[str, bool]:
        """Return all feature flags with their current values."""
        return {flag: self.is_enabled(flag) for flag in DEFAULT_FLAGS}

    def set_maintenance_mode(self, enabled: bool):
        """Toggle system maintenance mode."""
        if enabled:
            self.enable("MAINTENANCE_MODE", ttl=3600)
            self.disable("SEND_DURING_MAINTENANCE", ttl=3600)
        else:
            self.disable("MAINTENANCE_MODE")
            self.enable("SEND_DURING_MAINTENANCE")

    def check_channel_enabled(self, channel: str) -> bool:
        """Check if a notification channel is enabled."""
        channel_flags = {
            "push":     "PUSH_NOTIFICATIONS",
            "email":    "EMAIL_NOTIFICATIONS",
            "sms":      "SMS_NOTIFICATIONS",
            "telegram": "TELEGRAM_NOTIFICATIONS",
            "whatsapp": "WHATSAPP_NOTIFICATIONS",
            "browser":  "BROWSER_PUSH",
            "slack":    "SLACK_NOTIFICATIONS",
            "discord":  "DISCORD_NOTIFICATIONS",
            "in_app":   True,   # In-app is always enabled
        }
        flag = channel_flags.get(channel)
        if flag is True:
            return True
        if flag is None:
            return True
        return self.is_enabled(flag)


flags = FeatureFlagService()
