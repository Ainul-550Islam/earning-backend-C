# integration_system/integ_registry.py
"""
Integration Registry — Central plugin registry for all integrations.

Every module (notifications, wallet, tasks, etc.) registers itself here.
The registry provides:
  - Dynamic integration discovery
  - Enable/disable integrations at runtime
  - Integration health status
  - Dependency management between integrations

Usage:
    from .integ_registry import registry

    # Register (done in apps.py ready())
    registry.register('notifications', NotificationAdapter, depends_on=['users'])

    # Use
    adapter = registry.get('notifications')
    registry.is_enabled('wallet')
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Type
from datetime import datetime

from django.utils import timezone

from .integ_constants import HealthStatus, IntegStatus
from .integ_exceptions import (
    IntegrationNotRegistered, IntegrationDisabled,
    DuplicateIntegration, AdapterNotFound,
)

logger = logging.getLogger(__name__)


class IntegrationEntry:
    """Metadata container for a registered integration."""

    def __init__(
        self,
        name: str,
        adapter_class,
        description: str = '',
        version: str = '1.0.0',
        depends_on: Optional[List[str]] = None,
        enabled: bool = True,
        config: Optional[Dict] = None,
    ):
        self.name = name
        self.adapter_class = adapter_class
        self.description = description
        self.version = version
        self.depends_on = depends_on or []
        self.enabled = enabled
        self.config = config or {}

        # Runtime state
        self._instance = None
        self.health_status = HealthStatus.UNKNOWN
        self.registered_at = timezone.now()
        self.last_used = None
        self.error_count = 0
        self.success_count = 0
        self.last_error = ''

    def get_instance(self):
        """Lazy-init and return the adapter singleton instance."""
        if self._instance is None:
            self._instance = self.adapter_class(config=self.config)
        return self._instance

    def reset_instance(self):
        """Reset the singleton (useful after config changes)."""
        self._instance = None

    def record_success(self):
        self.success_count += 1
        self.last_used = timezone.now()

    def record_error(self, error: str):
        self.error_count += 1
        self.last_error = error
        self.last_used = timezone.now()

    @property
    def error_rate(self) -> float:
        total = self.success_count + self.error_count
        if total == 0:
            return 0.0
        return round(self.error_count / total * 100, 2)

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'enabled': self.enabled,
            'health_status': self.health_status.value,
            'depends_on': self.depends_on,
            'registered_at': self.registered_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'error_count': self.error_count,
            'success_count': self.success_count,
            'error_rate': self.error_rate,
            'last_error': self.last_error,
        }


class IntegrationRegistry:
    """
    Thread-safe singleton registry for all integrations.

    Supports:
    - Registration / deregistration
    - Enable / disable at runtime
    - Dependency resolution
    - Health status tracking
    - Bulk queries (all, enabled, by_module)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._integrations: Dict[str, IntegrationEntry] = {}
                    cls._instance._hooks: Dict[str, List[Callable]] = {}
        return cls._instance

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        adapter_class,
        description: str = '',
        version: str = '1.0.0',
        depends_on: Optional[List[str]] = None,
        enabled: bool = True,
        config: Optional[Dict] = None,
        overwrite: bool = False,
    ) -> IntegrationEntry:
        """
        Register an integration.

        Args:
            name:          Unique integration name (e.g. 'notifications').
            adapter_class: Class implementing BaseAdapter.
            description:   Human-readable description.
            version:       Semantic version string.
            depends_on:    List of integration names this one depends on.
            enabled:       Whether the integration is active.
            config:        Configuration dict passed to adapter __init__.
            overwrite:     If True, replace existing registration silently.

        Returns:
            IntegrationEntry

        Raises:
            DuplicateIntegration if name exists and overwrite=False.
        """
        with self._lock:
            if name in self._integrations and not overwrite:
                raise DuplicateIntegration(name)

            entry = IntegrationEntry(
                name=name,
                adapter_class=adapter_class,
                description=description,
                version=version,
                depends_on=depends_on or [],
                enabled=enabled,
                config=config or {},
            )
            self._integrations[name] = entry
            logger.info(f'IntegrationRegistry: registered "{name}" v{version}')
            return entry

    def unregister(self, name: str) -> bool:
        """Remove an integration from the registry."""
        with self._lock:
            if name in self._integrations:
                del self._integrations[name]
                logger.info(f'IntegrationRegistry: unregistered "{name}"')
                return True
        return False

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, name: str, raise_on_disabled: bool = True) -> Any:
        """
        Get the adapter instance for an integration.

        Args:
            name:              Integration name.
            raise_on_disabled: If True, raises IntegrationDisabled when disabled.

        Returns:
            Adapter instance.

        Raises:
            IntegrationNotRegistered, IntegrationDisabled.
        """
        entry = self._get_entry(name)

        if not entry.enabled:
            if raise_on_disabled:
                raise IntegrationDisabled(name)
            return None

        # Check dependencies
        for dep in entry.depends_on:
            if dep in self._integrations and not self._integrations[dep].enabled:
                logger.warning(
                    f'IntegrationRegistry: "{name}" dependency "{dep}" is disabled.'
                )

        return entry.get_instance()

    def get_entry(self, name: str) -> IntegrationEntry:
        """Get the IntegrationEntry (metadata) for an integration."""
        return self._get_entry(name)

    def _get_entry(self, name: str) -> IntegrationEntry:
        if name not in self._integrations:
            raise IntegrationNotRegistered(name)
        return self._integrations[name]

    def get_or_none(self, name: str):
        """Return adapter instance or None if not registered / disabled."""
        try:
            return self.get(name, raise_on_disabled=False)
        except IntegrationNotRegistered:
            return None

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    def enable(self, name: str):
        """Enable a registered integration."""
        entry = self._get_entry(name)
        entry.enabled = True
        logger.info(f'IntegrationRegistry: enabled "{name}"')

    def disable(self, name: str):
        """Disable a registered integration without removing it."""
        entry = self._get_entry(name)
        entry.enabled = False
        logger.info(f'IntegrationRegistry: disabled "{name}"')

    def is_enabled(self, name: str) -> bool:
        """Return True if the integration is registered and enabled."""
        try:
            return self._get_entry(name).enabled
        except IntegrationNotRegistered:
            return False

    def is_registered(self, name: str) -> bool:
        """Return True if the integration is registered."""
        return name in self._integrations

    # ------------------------------------------------------------------
    # Bulk queries
    # ------------------------------------------------------------------

    def all(self) -> Dict[str, IntegrationEntry]:
        """Return all registered integrations."""
        return dict(self._integrations)

    def enabled(self) -> Dict[str, IntegrationEntry]:
        """Return only enabled integrations."""
        return {k: v for k, v in self._integrations.items() if v.enabled}

    def names(self) -> List[str]:
        """Return list of all registered integration names."""
        return list(self._integrations.keys())

    def enabled_names(self) -> List[str]:
        """Return list of enabled integration names."""
        return [k for k, v in self._integrations.items() if v.enabled]

    def count(self) -> int:
        return len(self._integrations)

    # ------------------------------------------------------------------
    # Health & Stats
    # ------------------------------------------------------------------

    def update_health(self, name: str, status: HealthStatus):
        """Update the health status of an integration."""
        try:
            self._get_entry(name).health_status = status
        except IntegrationNotRegistered:
            pass

    def get_health_summary(self) -> Dict:
        """Return health summary for all integrations."""
        from collections import Counter
        statuses = [e.health_status.value for e in self._integrations.values()]
        counts = Counter(statuses)
        return {
            'total': len(self._integrations),
            'enabled': len(self.enabled()),
            'healthy': counts.get('healthy', 0),
            'degraded': counts.get('degraded', 0),
            'unhealthy': counts.get('unhealthy', 0),
            'unknown': counts.get('unknown', 0),
            'integrations': {
                name: entry.to_dict()
                for name, entry in self._integrations.items()
            },
        }

    # ------------------------------------------------------------------
    # Hooks (lifecycle callbacks)
    # ------------------------------------------------------------------

    def on_register(self, callback: Callable):
        """Register a callback called whenever a new integration is registered."""
        self._hooks.setdefault('register', []).append(callback)

    def on_error(self, name: str, error: str):
        """Record an error for an integration (called by adapter/handler)."""
        try:
            self._get_entry(name).record_error(error)
        except IntegrationNotRegistered:
            pass

    def on_success(self, name: str):
        """Record a successful operation for an integration."""
        try:
            self._get_entry(name).record_success()
        except IntegrationNotRegistered:
            pass

    # ------------------------------------------------------------------
    # Reset (testing)
    # ------------------------------------------------------------------

    def reset(self):
        """Clear all registrations. Use in tests only."""
        with self._lock:
            self._integrations.clear()
            logger.warning('IntegrationRegistry: RESET — all integrations cleared.')

    def __repr__(self):
        return f'<IntegrationRegistry: {self.count()} integrations registered>'


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
registry = IntegrationRegistry()
