"""
adapters/registry.py – Adapter registry for postback network adapters.

Keeps a mapping of network_key → adapter instance.
Falls back to GenericAdapter when no specific adapter is registered.
"""
import logging
from typing import Dict, Optional, Type

from .base import BasePostbackAdapter

logger = logging.getLogger(__name__)

_registry: Dict[str, BasePostbackAdapter] = {}
_generic_adapter: Optional[BasePostbackAdapter] = None


class AdapterRegistry:
    """
    Registry that maps network_key strings to adapter instances.
    Thread-safe for reads (dict lookup).
    Registration should happen at startup only.
    """

    @staticmethod
    def register(adapter_class: Type[BasePostbackAdapter]) -> None:
        """
        Register an adapter class for all its declared network_keys.
        Call this once at app startup (e.g. AppConfig.ready()).
        """
        instance = adapter_class()
        for key in adapter_class.network_keys:
            if key == "*":
                global _generic_adapter
                _generic_adapter = instance
                logger.debug("AdapterRegistry: registered GenericAdapter as fallback")
            else:
                _registry[key.lower()] = instance
                logger.debug("AdapterRegistry: registered %s for key=%r", adapter_class.__name__, key)

    @staticmethod
    def get(network_key: str) -> BasePostbackAdapter:
        """
        Return the adapter for network_key, falling back to GenericAdapter.
        Never raises – always returns something usable.
        """
        adapter = _registry.get(network_key.lower())
        if adapter:
            return adapter
        if _generic_adapter:
            return _generic_adapter
        # Safety net: return a fresh GenericAdapter if registry was never initialised
        from .generic import GenericAdapter
        logger.warning("AdapterRegistry not initialised – returning bare GenericAdapter")
        return GenericAdapter()

    @staticmethod
    def registered_keys() -> list:
        return list(_registry.keys())


def get_adapter(network_key: str) -> BasePostbackAdapter:
    """Convenience function – get the right adapter for a network key."""
    return AdapterRegistry.get(network_key)


def register_all_adapters() -> None:
    """
    Register all 91 network adapters.
    Called from postback/apps.py ready().
    """
    from .networks import ALL_NETWORK_ADAPTERS
    from .generic import GenericAdapter

    for adapter_class in ALL_NETWORK_ADAPTERS:
        try:
            AdapterRegistry.register(adapter_class)
        except Exception as exc:
            logger.warning("Failed to register adapter %s: %s", adapter_class.__name__, exc)

    AdapterRegistry.register(GenericAdapter)  # must be last (wildcard fallback)
    logger.info(
        "PostbackAdapterRegistry: registered %d network adapters + GenericAdapter",
        len(AdapterRegistry.registered_keys()),
    )
