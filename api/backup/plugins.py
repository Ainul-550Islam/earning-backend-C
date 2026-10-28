"""
Backup Module Plugin Architecture
Allows third-party extensions to hook into backup lifecycle events.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plugin Base
# ---------------------------------------------------------------------------

class BackupPlugin(ABC):
    """
    Base class for all backup plugins.
    Subclass and override the hooks you care about.
    """

    name: str = "unnamed_plugin"
    version: str = "0.1.0"
    enabled: bool = True

    # --- Lifecycle hooks ---

    def on_backup_start(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        """Called just before a backup begins"""

    def on_backup_complete(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        """Called when a backup finishes successfully"""

    def on_backup_fail(self, backup_id: str, error: Exception, metadata: Dict[str, Any]) -> None:
        """Called when a backup fails"""

    def on_restore_start(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        """Called just before a restore begins"""

    def on_restore_complete(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        """Called when a restore finishes successfully"""

    def on_cleanup(self, deleted_backup_ids: List[str]) -> None:
        """Called after old backups are purged"""

    def on_health_check(self, results: Dict[str, Any]) -> None:
        """Called after a health check completes"""

    @abstractmethod
    def setup(self, config: Dict[str, Any]) -> None:
        """Called once during plugin registration with plugin-specific config"""

    def teardown(self) -> None:
        """Called during plugin unregistration"""


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """
    Central registry for backup plugins.
    Plugins are singletons keyed by name.
    """

    _instance: Optional["PluginRegistry"] = None
    _plugins: Dict[str, BackupPlugin] = {}

    def __new__(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
        return cls._instance

    def register(self, plugin: BackupPlugin, config: Optional[Dict[str, Any]] = None) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered.")
        plugin.setup(config or {})
        self._plugins[plugin.name] = plugin
        logger.info("Plugin registered: %s v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> None:
        plugin = self._plugins.pop(name, None)
        if plugin:
            plugin.teardown()
            logger.info("Plugin unregistered: %s", name)

    def get(self, name: str) -> Optional[BackupPlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    def enabled_plugins(self) -> List[BackupPlugin]:
        return [p for p in self._plugins.values() if p.enabled]

    def _fire(self, hook: str, *args, **kwargs) -> None:
        for plugin in self.enabled_plugins():
            method = getattr(plugin, hook, None)
            if callable(method):
                try:
                    method(*args, **kwargs)
                except Exception as exc:
                    logger.error("Plugin %s raised in %s: %s", plugin.name, hook, exc)

    # Public event dispatch methods
    def fire_backup_start(self, backup_id: str, metadata: Dict) -> None:
        self._fire("on_backup_start", backup_id, metadata)

    def fire_backup_complete(self, backup_id: str, metadata: Dict) -> None:
        self._fire("on_backup_complete", backup_id, metadata)

    def fire_backup_fail(self, backup_id: str, error: Exception, metadata: Dict) -> None:
        self._fire("on_backup_fail", backup_id, error, metadata)

    def fire_restore_start(self, backup_id: str, metadata: Dict) -> None:
        self._fire("on_restore_start", backup_id, metadata)

    def fire_restore_complete(self, backup_id: str, metadata: Dict) -> None:
        self._fire("on_restore_complete", backup_id, metadata)

    def fire_cleanup(self, deleted_ids: List[str]) -> None:
        self._fire("on_cleanup", deleted_ids)

    def fire_health_check(self, results: Dict) -> None:
        self._fire("on_health_check", results)


# Singleton accessor
plugin_registry = PluginRegistry()


# ---------------------------------------------------------------------------
# Built-in example plugins
# ---------------------------------------------------------------------------

class LoggingPlugin(BackupPlugin):
    """Simple plugin that logs all backup events"""

    name = "logging_plugin"
    version = "1.0.0"

    def setup(self, config: Dict[str, Any]) -> None:
        self._log_level = config.get("log_level", "INFO")

    def on_backup_complete(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        logger.info("[LoggingPlugin] Backup completed: %s | meta=%s", backup_id, metadata)

    def on_backup_fail(self, backup_id: str, error: Exception, metadata: Dict[str, Any]) -> None:
        logger.error("[LoggingPlugin] Backup FAILED: %s | error=%s", backup_id, error)


class MetricsPlugin(BackupPlugin):
    """Plugin that records backup metrics to a counter store"""

    name = "metrics_plugin"
    version = "1.0.0"

    def setup(self, config: Dict[str, Any]) -> None:
        self._counters: Dict[str, int] = {
            "backup_started": 0,
            "backup_completed": 0,
            "backup_failed": 0,
            "restore_completed": 0,
        }

    def on_backup_start(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        self._counters["backup_started"] += 1

    def on_backup_complete(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        self._counters["backup_completed"] += 1

    def on_backup_fail(self, backup_id: str, error: Exception, metadata: Dict[str, Any]) -> None:
        self._counters["backup_failed"] += 1

    def on_restore_complete(self, backup_id: str, metadata: Dict[str, Any]) -> None:
        self._counters["restore_completed"] += 1

    def get_counters(self) -> Dict[str, int]:
        return dict(self._counters)
