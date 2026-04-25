# api/wallet/plugins.py
"""
Plugin system — allows extending wallet without modifying core code.
External apps can register plugins to add gateways, earning sources, validators.

Usage (in another app's apps.py):
    class MyPlugin(WalletPlugin):
        name = "my_custom_gateway"
        def on_withdrawal_create(self, wallet, amount, method):
            # Custom logic
            pass

    # Register in ready():
    from api.wallet.plugins import plugin_registry
    plugin_registry.register(MyPlugin())
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("wallet.plugins")


class WalletPlugin:
    """Base class for wallet plugins."""
    name: str = "base"

    def on_wallet_created(self, wallet) -> None: pass
    def on_credit(self, wallet, amount, txn) -> None: pass
    def on_debit(self, wallet, amount, txn) -> None: pass
    def on_withdrawal_create(self, wallet, amount, method) -> None: pass
    def on_withdrawal_complete(self, wallet, withdrawal) -> None: pass
    def on_kyc_approved(self, user, level) -> None: pass
    def on_fraud_detected(self, wallet, score) -> None: pass
    def validate_credit(self, wallet, amount) -> Optional[str]: return None
    def validate_withdrawal(self, wallet, amount, method) -> Optional[str]: return None


class PluginRegistry:
    """Registry and dispatcher for wallet plugins."""

    def __init__(self):
        self._plugins: Dict[str, WalletPlugin] = {}

    def register(self, plugin: WalletPlugin) -> None:
        self._plugins[plugin.name] = plugin
        logger.info(f"Wallet plugin registered: {plugin.name}")

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def get(self, name: str) -> Optional[WalletPlugin]:
        return self._plugins.get(name)

    def all(self) -> List[WalletPlugin]:
        return list(self._plugins.values())

    def fire(self, event: str, **kwargs) -> None:
        """Fire event on all plugins."""
        for plugin in self._plugins.values():
            handler = getattr(plugin, f"on_{event}", None)
            if handler:
                try:
                    handler(**kwargs)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name}.on_{event} error: {e}")

    def validate(self, operation: str, **kwargs) -> Optional[str]:
        """
        Run all plugin validators for an operation.
        Returns first error message, or None if all pass.
        """
        for plugin in self._plugins.values():
            validator = getattr(plugin, f"validate_{operation}", None)
            if validator:
                try:
                    error = validator(**kwargs)
                    if error:
                        return error
                except Exception as e:
                    logger.error(f"Plugin {plugin.name}.validate_{operation} error: {e}")
        return None


# ── Singleton ─────────────────────────────────────────────────
plugin_registry = PluginRegistry()
