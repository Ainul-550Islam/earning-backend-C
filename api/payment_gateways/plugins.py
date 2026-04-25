# api/payment_gateways/plugins.py
# Plugin system for extending payment_gateways without modifying core

_plugins = {}


class PaymentPlugin:
    """Base class for payment_gateways plugins."""
    name        = ''
    version     = '1.0.0'
    description = ''

    def on_deposit_completed(self, user, deposit): pass
    def on_withdrawal_processed(self, user, payout): pass
    def on_conversion_approved(self, conversion): pass
    def validate_deposit(self, user, amount, gateway): return True, []
    def validate_withdrawal(self, user, amount, gateway): return True, []


def register_plugin(plugin: PaymentPlugin):
    _plugins[plugin.name] = plugin


def get_plugin(name: str) -> PaymentPlugin:
    return _plugins.get(name)


def get_all_plugins() -> list:
    return list(_plugins.values())


def run_plugin_hooks(hook_name: str, **kwargs):
    for plugin in _plugins.values():
        hook = getattr(plugin, hook_name, None)
        if callable(hook):
            try:
                hook(**kwargs)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'Plugin {plugin.name}.{hook_name} failed: {e}')
