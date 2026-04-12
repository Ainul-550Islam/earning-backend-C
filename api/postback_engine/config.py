"""
config.py
──────────
Runtime configuration for Postback Engine.
Reads from Django settings with sensible defaults.
All configurable values are centralised here.

Usage in settings.py:
    POSTBACK_ENGINE = {
        "MAX_RETRIES": 5,
        "FRAUD_BLOCK_THRESHOLD": 80,
        "ENCRYPTION_KEY": env("PE_ENCRYPTION_KEY", default=""),
        "IPINFO_TOKEN": env("IPINFO_TOKEN", default=""),
        "SLACK_WEBHOOK_URL": env("SLACK_WEBHOOK_URL", default=""),
        "ENABLE_FRAUD_DETECTION": True,
        "ENABLE_PROXY_DETECTION": True,
        "ENABLE_GEO_ENRICHMENT": True,
        "DEFAULT_CONVERSION_WINDOW_HOURS": 720,
        "REALTIME_WINDOW_MINUTES": 5,
    }
"""
from __future__ import annotations
from typing import Any


class PostbackEngineConfig:
    """
    Reads POSTBACK_ENGINE dict from Django settings.
    Falls back to hardcoded defaults for every key.
    """

    DEFAULTS = {
        # Retry
        "MAX_RETRIES":                  5,
        "RETRY_DELAYS":                 [60, 300, 1800, 7200, 21600],
        "WALLET_RETRY_DELAYS":          [30, 120, 600, 3600, 10800],
        "WEBHOOK_RETRY_DELAYS":         [60, 300, 900],

        # Fraud
        "FRAUD_FLAG_THRESHOLD":         60,
        "FRAUD_BLOCK_THRESHOLD":        80,
        "FRAUD_AUTO_BLACKLIST":         90,
        "MAX_IP_CONVERSIONS_PER_MINUTE": 5,
        "MAX_IP_CONVERSIONS_PER_HOUR":  50,
        "MAX_IP_CONVERSIONS_PER_DAY":   200,
        "MAX_USER_CONVERSIONS_PER_HOUR": 20,
        "MAX_DEVICE_CLICKS_PER_HOUR":   30,

        # Security
        "SIGNATURE_TOLERANCE_SECONDS":  300,
        "ENCRYPTION_KEY":               "",
        "IPINFO_TOKEN":                 "",

        # Click tracking
        "CLICK_EXPIRY_HOURS":           24,

        # Conversion
        "DEFAULT_CONVERSION_WINDOW_HOURS": 720,  # 30 days
        "MAX_PAYOUT_USD":               1000.0,

        # Analytics
        "REALTIME_WINDOW_MINUTES":      5,

        # Feature flags
        "ENABLE_FRAUD_DETECTION":       True,
        "ENABLE_PROXY_DETECTION":       True,
        "ENABLE_GEO_ENRICHMENT":        True,
        "ENABLE_WEBHOOK_DELIVERY":      True,
        "ENABLE_RATE_LIMITING":         True,
        "TEST_MODE":                    False,

        # Notifications
        "SLACK_WEBHOOK_URL":            "",
        "ALERT_EMAIL":                  "",

        # Log retention (days)
        "POSTBACK_LOG_RETENTION_DAYS":  90,
        "CLICK_LOG_RETENTION_DAYS":     180,
        "FRAUD_LOG_RETENTION_DAYS":     730,
    }

    def __init__(self):
        self._settings = None

    def _load(self):
        if self._settings is None:
            try:
                from django.conf import settings
                self._settings = getattr(settings, "POSTBACK_ENGINE", {}) or {}
            except Exception:
                self._settings = {}

    def get(self, key: str, default: Any = None) -> Any:
        self._load()
        if default is None:
            default = self.DEFAULTS.get(key)
        return self._settings.get(key, default)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        return self.get(key)

    def is_feature_enabled(self, feature: str) -> bool:
        return bool(self.get(f"ENABLE_{feature.upper()}", True))

    def to_dict(self) -> dict:
        self._load()
        return {**self.DEFAULTS, **self._settings}

    def reload(self) -> None:
        """Force reload from Django settings (useful in tests)."""
        self._settings = None
        self._load()


# Module-level singleton
pe_config = PostbackEngineConfig()
