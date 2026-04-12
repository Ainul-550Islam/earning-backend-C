"""
marketplace/plugins.py — Plugin Registry
==========================================
Third-party plugins can register themselves here to extend
marketplace functionality (e.g., extra payment gateways,
custom shipping calculators, loyalty engines).

Example plugin registration in any app's AppConfig.ready():

    from api.marketplace.plugins import registry

    registry.register("shipping_calculator", MyShippingPlugin())
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, Any] = {}

    def register(self, name: str, plugin: Any):
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' is already registered.")
        self._plugins[name] = plugin

    def get(self, name: str) -> Optional[Any]:
        return self._plugins.get(name)

    def all(self) -> Dict[str, Any]:
        return dict(self._plugins)

    def unregister(self, name: str):
        self._plugins.pop(name, None)


# Global registry singleton
registry = PluginRegistry()

# ── Plugin type hints / base classes ──────────────────────────
class BaseShippingPlugin:
    def calculate_rate(self, items, destination) -> float:
        raise NotImplementedError


class BasePaymentPlugin:
    def initiate(self, order, amount) -> dict:
        raise NotImplementedError

    def verify(self, transaction_id: str) -> bool:
        raise NotImplementedError


class BaseTaxPlugin:
    def calculate(self, amount, category, country) -> float:
        raise NotImplementedError
