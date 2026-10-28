# api/djoyalty/plugins.py
"""
Djoyalty Plugin System -- Drop-in extensions for loyalty features।
Register external plugins that extend earn rules, notifications, etc.

Usage:
    # In your external app's AppConfig.ready():
    from djoyalty.plugins import LoyaltyPluginRegistry
    LoyaltyPluginRegistry.register(MyPlugin())
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseLoyaltyPlugin(ABC):
    """Base class for all Djoyalty plugins।"""

    name: str = 'unnamed_plugin'
    version: str = '1.0.0'
    description: str = ''

    def on_register(self):
        """Called when plugin is registered।"""
        pass

    def on_points_earned(self, customer, points, source: str, **kwargs):
        """Called after points are earned।"""
        pass

    def on_points_redeemed(self, customer, points, reward_type: str, **kwargs):
        """Called after points are redeemed।"""
        pass

    def on_tier_changed(self, customer, old_tier, new_tier, **kwargs):
        """Called after tier upgrade/downgrade।"""
        pass

    def on_customer_created(self, customer, **kwargs):
        """Called after new customer created।"""
        pass

    def on_cashout_completed(self, cashout_request, **kwargs):
        """Called after cashout is completed।"""
        pass

    def get_extra_earn_points(self, customer, txn, base_points) -> float:
        """Return extra bonus points (0 = no bonus)।"""
        return 0

    def validate_redemption(self, customer, points, reward_type) -> Optional[str]:
        """Validate a redemption। Return error string or None if ok।"""
        return None


class LoyaltyPluginRegistry:
    """Registry for all active plugins।"""

    _plugins: Dict[str, BaseLoyaltyPlugin] = {}

    @classmethod
    def register(cls, plugin: BaseLoyaltyPlugin):
        """Register a plugin।"""
        cls._plugins[plugin.name] = plugin
        plugin.on_register()
        logger.info('LoyaltyPluginRegistry: registered plugin "%s" v%s',
                    plugin.name, plugin.version)

    @classmethod
    def get(cls, name: str) -> Optional[BaseLoyaltyPlugin]:
        return cls._plugins.get(name)

    @classmethod
    def all(cls) -> List[BaseLoyaltyPlugin]:
        return list(cls._plugins.values())

    @classmethod
    def fire(cls, method: str, **kwargs):
        """Call a method on all registered plugins।"""
        results = []
        for plugin in cls._plugins.values():
            fn = getattr(plugin, method, None)
            if fn:
                try:
                    result = fn(**kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error('Plugin [%s].%s error: %s', plugin.name, method, e)
        return results

    @classmethod
    def get_total_bonus_points(cls, customer, txn, base_points: float) -> float:
        """Sum bonus points from all plugins।"""
        total_bonus = 0
        for plugin in cls._plugins.values():
            try:
                bonus = plugin.get_extra_earn_points(customer, txn, base_points)
                total_bonus += bonus or 0
            except Exception as e:
                logger.debug('Plugin bonus error [%s]: %s', plugin.name, e)
        return total_bonus

    @classmethod
    def validate_redemption(cls, customer, points, reward_type) -> Optional[str]:
        """Check all plugins for redemption errors।"""
        for plugin in cls._plugins.values():
            try:
                error = plugin.validate_redemption(customer, points, reward_type)
                if error:
                    return error
            except Exception:
                pass
        return None

    @classmethod
    def list_plugins(cls) -> List[dict]:
        return [
            {'name': p.name, 'version': p.version, 'description': p.description}
            for p in cls._plugins.values()
        ]
