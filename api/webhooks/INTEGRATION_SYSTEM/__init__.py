# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Enterprise Integration System
INTEGRATION_SYSTEM/__init__.py

FIX APPLIED:
    Previously this file only listed __all__ strings with no actual imports.
    The 19 integration files were completely isolated (0 usage anywhere).

    Now:
    - Exposes get_integration() as the single entry point
    - Lazy-loads WebhooksIntegration so import cost is zero when disabled
    - is_enabled() lets callers check settings before calling the system
    - IntegrationStatus dataclass provides structured health/sync reporting

Enable integration in settings.py:
    WEBHOOKS = {
        "INTEGRATION_ENABLED": True,
        "INTEGRATION_CONFIG": {
            "timeout":            30,
            "max_retries":        3,
            "enable_validation":  True,
            "fallback_behavior":  "queue",   # "queue" | "fail"
            "sync_interval_hours": 6,
        }
    }

Usage:
    from api.webhooks.INTEGRATION_SYSTEM import get_integration, is_enabled

    if is_enabled():
        integ = get_integration()
        health = integ.health_check()
        integ.sync_endpoint(endpoint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger("ainul.webhooks.integration")

# ── Module-level singleton (lazy) ─────────────────────────────────────────────
_instance: Optional[Any] = None


def is_enabled() -> bool:
    """Return True when integration is enabled in WEBHOOKS settings."""
    cfg = getattr(settings, "WEBHOOKS", {})
    return bool(cfg.get("INTEGRATION_ENABLED", False))


def get_integration():
    """
    Return the WebhooksIntegration singleton.

    Creates it on first call; subsequent calls return the cached instance.
    Raises RuntimeError if called while integration is disabled.
    """
    global _instance

    if not is_enabled():
        raise RuntimeError(
            "Integration system is disabled. "
            "Set WEBHOOKS['INTEGRATION_ENABLED'] = True in settings.py."
        )

    if _instance is None:
        try:
            from .webhooks_integration import WebhooksIntegration
            _instance = WebhooksIntegration()
            logger.info("[Integration] WebhooksIntegration initialised")
        except Exception as exc:
            logger.exception("[Integration] Failed to initialise WebhooksIntegration")
            raise RuntimeError(f"Could not initialise integration system: {exc}") from exc

    return _instance


def reset_integration():
    """
    Reset the singleton (useful in tests or after config changes).
    """
    global _instance
    _instance = None
    logger.debug("[Integration] Singleton reset")


# ── Safe no-op fallback ───────────────────────────────────────────────────────

class _DisabledIntegration:
    """
    Returned by get_integration_safe() when integration is disabled.
    All methods are no-ops that return a disabled-status dict,
    so callers don't need to guard every call with is_enabled().
    """

    _STATUS = {"status": "disabled", "integration_enabled": False}

    def __getattr__(self, name: str):
        def _noop(*args, **kwargs):
            logger.debug("[Integration] Call to %s() skipped — integration disabled", name)
            return self._STATUS
        return _noop

    def health_check(self):
        return self._STATUS

    def sync_endpoint(self, endpoint):
        return self._STATUS


def get_integration_safe():
    """
    Return the integration instance OR a no-op stub if disabled.

    Prefer this over get_integration() in code paths that should degrade
    gracefully when integration is turned off.
    """
    if not is_enabled():
        return _DisabledIntegration()
    return get_integration()


# ── Status dataclass ──────────────────────────────────────────────────────────

@dataclass
class IntegrationStatus:
    """Structured result for integration health/sync status API responses."""
    enabled: bool = False
    connected: bool = False
    last_sync: Optional[str] = None
    synced_count: int = 0
    failed_count: int = 0
    health: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

__all__ = [
    "is_enabled",
    "get_integration",
    "get_integration_safe",
    "reset_integration",
    "IntegrationStatus",
    # Sub-modules (importable directly for advanced use)
    "webhooks_integration",
    "bridge",
    "auth_bridge",
    "data_bridge",
    "event_bus",
    "integ_handler",
    "integ_adapter",
    "integ_registry",
    "integ_constants",
    "integ_exceptions",
    "integ_signals",
    "integ_audit_logs",
    "data_validator",
    "fallback_logic",
    "health_check",
    "performance_monitor",
    "sync_manager",
    "message_queue",
]
