"""
api/tasks/plugins.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Plugin system for the task platform.
Allows third-party extensions to integrate with the task
system without modifying core code.

Plugins can:
  • Register custom offer types
  • Add custom fraud detection signals
  • Override payout calculation logic
  • Add custom postback handlers
  • Extend the admin panel with new sections

Usage:
    from api.tasks.plugins import PluginRegistry, BasePlugin

    class MyCustomPlugin(BasePlugin):
        name = 'my_plugin'
        version = '1.0.0'

        def on_task_complete(self, context):
            # Custom logic after task completion
            pass

    PluginRegistry.register(MyCustomPlugin())
"""

import logging
from typing import Any, Dict, List, Optional, Type
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BASE PLUGIN
# ══════════════════════════════════════════════════════════════════════════════

class BasePlugin:
    """
    Abstract base class for all task system plugins.
    Override any hook methods to add custom behavior.
    All hooks are called with a context dict and should return
    None or an updated context dict.
    """

    name:        str = 'unnamed_plugin'
    version:     str = '1.0.0'
    description: str = ''
    author:      str = ''
    enabled:     bool = True

    def on_plugin_load(self) -> None:
        """Called when plugin is registered. Use for initialization."""
        pass

    def on_plugin_unload(self) -> None:
        """Called when plugin is unregistered."""
        pass

    # ── Task lifecycle ─────────────────────────────────────────────────────

    def before_task_complete(self, context: Dict) -> Optional[Dict]:
        """Called before a task completion is processed. Raise to block."""
        return None

    def after_task_complete(self, context: Dict) -> Optional[Dict]:
        """Called after a task completion is credited."""
        return None

    def on_task_activated(self, task_id: str) -> None:
        """Called when a MasterTask is activated."""
        pass

    def on_task_deactivated(self, task_id: str) -> None:
        """Called when a MasterTask is deactivated."""
        pass

    # ── Payment lifecycle ──────────────────────────────────────────────────

    def before_withdrawal(self, context: Dict) -> Optional[Dict]:
        """Called before a withdrawal is processed. Raise to block."""
        return None

    def after_withdrawal_complete(self, context: Dict) -> Optional[Dict]:
        """Called after a withdrawal is completed."""
        return None

    def calculate_payout(self, gross: float, user_id: int,
                          offer_id: str, **kwargs) -> Optional[float]:
        """
        Override payout calculation. Return float or None to use default.
        Useful for custom revenue share logic.
        """
        return None

    # ── Offer lifecycle ────────────────────────────────────────────────────

    def on_offer_converted(self, context: Dict) -> Optional[Dict]:
        """Called when a postback conversion is received and verified."""
        return None

    def on_postback_received(self, postback_data: Dict) -> Optional[Dict]:
        """Called when a raw postback is received, before verification."""
        return None

    def filter_offer_wall(self, offers: List[Dict], context: Dict) -> List[Dict]:
        """
        Filter or re-rank offers in the offer wall.
        Return the modified offers list.
        """
        return offers

    # ── Fraud detection ────────────────────────────────────────────────────

    def compute_fraud_signals(self, user_id: int,
                               ip_address: str,
                               context: Dict) -> Dict[str, Any]:
        """
        Return additional fraud signals for a request.
        These are merged with the platform's built-in signals.
        """
        return {}

    def on_fraud_detected(self, user_id: int, fraud_score: int,
                           reason: str) -> None:
        """Called when fraud is detected for a user."""
        pass

    # ── User lifecycle ─────────────────────────────────────────────────────

    def on_user_registered(self, user_id: int, context: Dict) -> None:
        """Called when a new user registers."""
        pass

    def on_user_kyc_approved(self, user_id: int, tier: str) -> None:
        """Called when a user's KYC is approved."""
        pass

    def on_publisher_tier_change(self, user_id: int,
                                  old_tier: str, new_tier: str) -> None:
        """Called when a publisher's tier changes."""
        pass

    # ── Content lockers ────────────────────────────────────────────────────

    def on_content_unlocked(self, locker_id: str, user_id: int,
                             access_mode: str) -> None:
        """Called when a content locker is unlocked."""
        pass

    # ── Reporting ──────────────────────────────────────────────────────────

    def extend_daily_report(self, report: Dict) -> Dict:
        """Add custom data to the daily report."""
        return report

    def extend_user_stats(self, user_id: int, stats: Dict) -> Dict:
        """Add custom fields to user statistics."""
        return stats

    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version}>"


# ══════════════════════════════════════════════════════════════════════════════
# PLUGIN REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

class PluginRegistry:
    """
    Central registry for task system plugins.
    Maintains ordered list of active plugins and routes hook calls.
    """

    _plugins: List[BasePlugin] = []

    @classmethod
    def register(cls, plugin: BasePlugin) -> None:
        """Register a plugin instance."""
        if not plugin.enabled:
            logger.info(f"[PLUGIN] Skipped disabled plugin: {plugin.name}")
            return
        # Avoid duplicate registration
        existing = [p.name for p in cls._plugins]
        if plugin.name in existing:
            logger.warning(f"[PLUGIN] Already registered: {plugin.name}, replacing.")
            cls._plugins = [p for p in cls._plugins if p.name != plugin.name]
        cls._plugins.append(plugin)
        try:
            plugin.on_plugin_load()
        except Exception as e:
            logger.error(f"[PLUGIN] Load error '{plugin.name}': {e}")
        logger.info(f"[PLUGIN] Registered: {plugin.name} v{plugin.version}")

    @classmethod
    def unregister(cls, plugin_name: str) -> bool:
        """Unregister a plugin by name."""
        for plugin in cls._plugins:
            if plugin.name == plugin_name:
                try:
                    plugin.on_plugin_unload()
                except Exception:
                    pass
                cls._plugins = [p for p in cls._plugins if p.name != plugin_name]
                logger.info(f"[PLUGIN] Unregistered: {plugin_name}")
                return True
        return False

    @classmethod
    def get(cls, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return next((p for p in cls._plugins if p.name == plugin_name), None)

    @classmethod
    def list_plugins(cls) -> List[Dict]:
        """Return metadata for all registered plugins."""
        return [
            {
                'name':        p.name,
                'version':     p.version,
                'description': p.description,
                'author':      p.author,
                'enabled':     p.enabled,
            }
            for p in cls._plugins
        ]

    @classmethod
    def run_hook(cls, hook_name: str, context: Dict, **kwargs) -> Dict:
        """
        Run a hook on all registered plugins.
        Context is passed and merged through each plugin.
        """
        for plugin in cls._plugins:
            fn = getattr(plugin, hook_name, None)
            if not fn:
                continue
            try:
                result = fn(context, **kwargs) if kwargs else fn(context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.error(f"[PLUGIN] Hook '{hook_name}' error in '{plugin.name}': {e}")
        return context

    @classmethod
    def run_void_hook(cls, hook_name: str, *args, **kwargs) -> None:
        """Run a void hook (no context mutation) on all plugins."""
        for plugin in cls._plugins:
            fn = getattr(plugin, hook_name, None)
            if not fn:
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"[PLUGIN] Void hook '{hook_name}' error in '{plugin.name}': {e}")

    @classmethod
    def collect(cls, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Collect non-None results from all plugins for a hook.
        Useful for 'calculate_payout' where first non-None wins.
        """
        results = []
        for plugin in cls._plugins:
            fn = getattr(plugin, hook_name, None)
            if not fn:
                continue
            try:
                result = fn(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"[PLUGIN] Collect '{hook_name}' error in '{plugin.name}': {e}")
        return results

    @classmethod
    def first_result(cls, hook_name: str, *args, **kwargs) -> Any:
        """Return the first non-None result from plugins for a hook."""
        results = cls.collect(hook_name, *args, **kwargs)
        return results[0] if results else None

    @classmethod
    def clear(cls) -> None:
        """Unregister all plugins (used in testing)."""
        for plugin in cls._plugins:
            try:
                plugin.on_plugin_unload()
            except Exception:
                pass
        cls._plugins.clear()


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN EXAMPLE PLUGINS
# ══════════════════════════════════════════════════════════════════════════════

class BDPlugin(BasePlugin):
    """
    Bangladesh-specific plugin.
    Adjusts minimum payouts and enables bKash/Nagad for BD users.
    """
    name        = 'bd_plugin'
    version     = '1.0.0'
    description = 'Bangladesh localization plugin (bKash, Nagad, BD rates)'
    author      = 'Platform Team'

    def calculate_payout(self, gross: float, user_id: int,
                          offer_id: str, **kwargs) -> Optional[float]:
        """Apply BD geo-specific payout boost for Tier-3 traffic."""
        country = kwargs.get('country', '')
        if country == 'BD':
            # 5% boost for BD traffic to incentivize publishers
            return round(gross * 1.05, 8)
        return None

    def filter_offer_wall(self, offers: List[Dict], context: Dict) -> List[Dict]:
        """Boost local BD offers to top of the wall for BD users."""
        country = context.get('country', '')
        if country != 'BD':
            return offers
        bd_offers    = [o for o in offers if 'BD' in (o.get('countries') or [])]
        other_offers = [o for o in offers if o not in bd_offers]
        return bd_offers + other_offers


class DebugPlugin(BasePlugin):
    """
    Development-only debug plugin.
    Logs all hook calls for debugging.
    Only active when DEBUG=True.
    """
    name        = 'debug_plugin'
    version     = '1.0.0'
    description = 'Debug logging plugin (dev only)'
    enabled     = False   # Must be manually enabled in dev

    def on_plugin_load(self) -> None:
        logger.info("[DEBUG PLUGIN] Loaded — all hooks will be logged")

    def before_task_complete(self, context: Dict) -> None:
        logger.debug(f"[DEBUG PLUGIN] before_task_complete: {context}")

    def after_task_complete(self, context: Dict) -> None:
        logger.debug(f"[DEBUG PLUGIN] after_task_complete: {context}")

    def on_offer_converted(self, context: Dict) -> None:
        logger.debug(f"[DEBUG PLUGIN] on_offer_converted: {context}")


def load_plugins_from_settings() -> None:
    """
    Auto-load plugins declared in settings.TASK_PLUGINS.
    settings.TASK_PLUGINS = ['myapp.plugins.MyPlugin']
    """
    try:
        from django.conf import settings
        plugin_paths = getattr(settings, 'TASK_PLUGINS', [])
        for path in plugin_paths:
            try:
                parts     = path.rsplit('.', 1)
                mod_path  = parts[0]
                cls_name  = parts[1]
                import importlib
                mod       = importlib.import_module(mod_path)
                plugin_cls = getattr(mod, cls_name)
                PluginRegistry.register(plugin_cls())
            except Exception as e:
                logger.error(f"[PLUGIN] Failed to load '{path}': {e}")
    except Exception:
        pass


__all__ = [
    'BasePlugin', 'PluginRegistry',
    'BDPlugin', 'DebugPlugin',
    'load_plugins_from_settings',
]
