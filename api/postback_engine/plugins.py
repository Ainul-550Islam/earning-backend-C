"""
plugins.py
───────────
Plugin system for Postback Engine.
Allows third-party code to extend the engine without modifying core files.

Plugin types:
  NetworkPlugin       → Add support for new ad networks
  FraudPlugin         → Add custom fraud detection rules
  RewardPlugin        → Custom reward calculation logic
  NotificationPlugin  → Custom notification channels (Telegram, Discord, etc.)
  ExportPlugin        → Custom data export formats

Plugin lifecycle:
  1. Plugin is defined (subclass BasePlugin)
  2. Plugin is registered: plugin_registry.register(MyPlugin())
  3. At startup (apps.py ready()), plugin_registry.load_all() is called
  4. Plugins hooks into the event bus / hook registry

Usage:
    # myapp/plugins.py
    from api.postback_engine.plugins import NetworkPlugin, plugin_registry
    from api.postback_engine.network_adapters.base_adapter import BaseNetworkAdapter

    class MyNetworkAdapter(BaseNetworkAdapter):
        NETWORK_KEY = "mynetwork"
        FIELD_MAP = {"lead_id": "uid", "payout": "reward"}
        def get_network_key(self): return self.NETWORK_KEY

    class MyNetworkPlugin(NetworkPlugin):
        name = "mynetwork"
        def get_adapter(self): return MyNetworkAdapter()

    plugin_registry.register(MyNetworkPlugin())
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ── Base Plugin ────────────────────────────────────────────────────────────────

class BasePlugin(ABC):
    """Abstract base for all plugins."""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True

    def on_load(self) -> None:
        """Called when plugin is loaded. Override for setup logic."""

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""


# ── Network Plugin ─────────────────────────────────────────────────────────────

class NetworkPlugin(BasePlugin):
    """Add support for a new CPA network."""

    @abstractmethod
    def get_adapter(self):
        """Return an instance of a BaseNetworkAdapter subclass."""

    def on_load(self) -> None:
        """Register adapter in the ADAPTER_REGISTRY."""
        from .network_adapters.adapters import ADAPTER_REGISTRY
        adapter = self.get_adapter()
        key = adapter.get_network_key()
        ADAPTER_REGISTRY[key] = type(adapter)
        logger.info("NetworkPlugin: registered adapter for '%s'", key)


# ── Fraud Plugin ───────────────────────────────────────────────────────────────

class FraudPlugin(BasePlugin):
    """Add a custom fraud detection rule."""

    @abstractmethod
    def check(self, ip: str = "", user_agent: str = "", **kwargs) -> tuple:
        """
        Run custom fraud check.
        Returns (is_fraud, score, description).
        """

    def on_load(self) -> None:
        from .fraud_detection.fraud_scoring import fraud_score_calculator
        # Custom fraud plugins can extend the scoring pipeline
        logger.info("FraudPlugin: loaded '%s'", self.name)


# ── Reward Plugin ──────────────────────────────────────────────────────────────

class RewardPlugin(BasePlugin):
    """Custom reward calculation logic."""

    def calculate_reward(self, conversion, network) -> dict:
        """
        Return custom reward dict: {"points": int, "usd": float}.
        Return None to use default network reward rules.
        """
        return None


# ── Notification Plugin ────────────────────────────────────────────────────────

class NotificationPlugin(BasePlugin):
    """Custom notification channel."""

    @abstractmethod
    def notify(self, event_type: str, data: dict) -> None:
        """Send notification for an event."""

    def on_load(self) -> None:
        from .hooks import hook_registry, POST_REWARD, ON_FRAUD
        plugin_ref = self

        def hook(context):
            try:
                data = {
                    "user_id": str(getattr(context, "user_id", "")),
                    "network": getattr(context, "network_key", ""),
                    "payout": float(getattr(context, "payout", 0)),
                }
                plugin_ref.notify("conversion", data)
            except Exception as exc:
                logger.debug("NotificationPlugin hook failed: %s", exc)

        hook_registry.add(POST_REWARD, hook, name=f"notify_{self.name}")
        logger.info("NotificationPlugin: loaded '%s'", self.name)


# ── Export Plugin ──────────────────────────────────────────────────────────────

class ExportPlugin(BasePlugin):
    """Custom data export format."""

    @abstractmethod
    def export(self, queryset, **options) -> Any:
        """Export queryset in custom format. Returns file-like object or string."""


# ── Plugin Registry ────────────────────────────────────────────────────────────

class PluginRegistry:
    """Central registry for all PostbackEngine plugins."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin. Calls on_load() immediately."""
        if not plugin.name:
            raise ValueError("Plugin must have a name.")
        if not plugin.enabled:
            logger.info("Plugin '%s' is disabled, skipping.", plugin.name)
            return
        self._plugins[plugin.name] = plugin
        try:
            plugin.on_load()
        except Exception as exc:
            logger.error("Plugin '%s' on_load failed: %s", plugin.name, exc)
        logger.info("Plugin registered: '%s' v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> None:
        plugin = self._plugins.pop(name, None)
        if plugin:
            try:
                plugin.on_unload()
            except Exception:
                pass
            logger.info("Plugin unregistered: '%s'", name)

    def get(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def get_all(self, plugin_type: type = None) -> List[BasePlugin]:
        plugins = list(self._plugins.values())
        if plugin_type:
            plugins = [p for p in plugins if isinstance(p, plugin_type)]
        return plugins

    def get_notification_plugins(self) -> List[NotificationPlugin]:
        return self.get_all(NotificationPlugin)

    def get_reward_plugins(self) -> List[RewardPlugin]:
        return self.get_all(RewardPlugin)

    def load_from_settings(self) -> None:
        """
        Auto-load plugins defined in Django settings.
        POSTBACK_ENGINE = {"PLUGINS": ["myapp.plugins.MyPlugin"]}
        """
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            plugin_paths = pe_settings.get("PLUGINS", [])
            for path in plugin_paths:
                try:
                    module_path, class_name = path.rsplit(".", 1)
                    import importlib
                    module = importlib.import_module(module_path)
                    plugin_cls = getattr(module, class_name)
                    self.register(plugin_cls())
                except Exception as exc:
                    logger.error("Failed to load plugin '%s': %s", path, exc)
        except Exception as exc:
            logger.debug("load_from_settings failed: %s", exc)

    def list(self) -> dict:
        return {
            name: {
                "type": type(plugin).__name__,
                "version": plugin.version,
                "description": plugin.description,
            }
            for name, plugin in self._plugins.items()
        }


# Module-level registry singleton
plugin_registry = PluginRegistry()


# ── Built-in Telegram notification plugin (optional) ─────────────────────────

class TelegramNotificationPlugin(NotificationPlugin):
    """
    Send Telegram notifications for conversions.
    Enable by adding to settings:
        POSTBACK_ENGINE = {
            "PLUGINS": ["api.postback_engine.plugins.TelegramNotificationPlugin"],
            "TELEGRAM_BOT_TOKEN": "...",
            "TELEGRAM_CHAT_ID": "...",
        }
    """
    name = "telegram_notifications"
    description = "Send Telegram notifications for conversions and fraud alerts."

    def notify(self, event_type: str, data: dict) -> None:
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            token = pe_settings.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = pe_settings.get("TELEGRAM_CHAT_ID", "")
            if not token or not chat_id:
                return
            import requests
            msg = f"🎯 *{event_type.upper()}*\n"
            for key, val in data.items():
                msg += f"• {key}: `{val}`\n"
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=5,
            )
        except Exception as exc:
            logger.debug("TelegramNotificationPlugin.notify failed: %s", exc)
