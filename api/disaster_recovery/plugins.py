"""Plugins — Extensible plugin system for DR system."""
import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

class DRPlugin:
    """Base class for all DR system plugins."""
    name: str = "base_plugin"
    version: str = "1.0.0"

    def initialize(self, config: Dict[str, Any]) -> bool:
        return True

    def on_backup_complete(self, backup_job: dict): pass
    def on_restore_complete(self, restore_request: dict): pass
    def on_failover(self, failover_event: dict): pass
    def on_incident_created(self, incident: dict): pass

class PluginManager:
    def __init__(self):
        self._plugins: Dict[str, DRPlugin] = {}

    def register(self, plugin: DRPlugin, config: dict = None):
        if plugin.initialize(config or {}):
            self._plugins[plugin.name] = plugin
            logger.info(f"Plugin registered: {plugin.name} v{plugin.version}")
        else:
            logger.warning(f"Plugin failed to initialize: {plugin.name}")

    def notify_backup_complete(self, backup_job: dict):
        for p in self._plugins.values():
            try:
                p.on_backup_complete(backup_job)
            except Exception as e:
                logger.error(f"Plugin error [{p.name}]: {e}")

    def notify_failover(self, event: dict):
        for p in self._plugins.values():
            try:
                p.on_failover(event)
            except Exception as e:
                logger.error(f"Plugin error [{p.name}]: {e}")

plugin_manager = PluginManager()
