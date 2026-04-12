# api/publisher_tools/plugins.py
"""Publisher Tools — Plugin system. 3rd party extensions support।"""
import logging
from typing import Dict, Type, Any

logger = logging.getLogger(__name__)

_registered_plugins: Dict[str, Any] = {}


class PublisherToolsPlugin:
    """Base plugin class। সব plugins এটা extend করবে।"""
    name: str = 'base_plugin'
    version: str = '1.0.0'
    description: str = ''
    author: str = ''

    def on_install(self):
        """Plugin install হলে called।"""
        pass

    def on_uninstall(self):
        """Plugin remove হলে called।"""
        pass

    def on_publisher_approved(self, publisher):
        """Publisher approve event।"""
        pass

    def on_earning_finalized(self, publisher, year: int, month: int):
        """Earning finalized event।"""
        pass

    def on_fraud_detected(self, log):
        """Fraud detected event।"""
        pass

    def on_invoice_generated(self, invoice):
        """Invoice generated event।"""
        pass


def register_plugin(plugin_class: Type[PublisherToolsPlugin]):
    """Plugin register করে।"""
    plugin = plugin_class()
    _registered_plugins[plugin.name] = plugin
    plugin.on_install()
    logger.info(f'Plugin registered: {plugin.name} v{plugin.version}')
    return plugin


def unregister_plugin(plugin_name: str):
    """Plugin remove করে।"""
    plugin = _registered_plugins.pop(plugin_name, None)
    if plugin:
        plugin.on_uninstall()
        logger.info(f'Plugin removed: {plugin_name}')


def get_plugin(plugin_name: str) -> Any:
    return _registered_plugins.get(plugin_name)


def get_all_plugins() -> Dict[str, Any]:
    return dict(_registered_plugins)


def broadcast_to_plugins(event_name: str, **kwargs):
    """সব plugins-এ event broadcast করে।"""
    for plugin in _registered_plugins.values():
        handler = getattr(plugin, f'on_{event_name}', None)
        if callable(handler):
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f'Plugin error [{plugin.name}] on {event_name}: {e}')


# ── Built-in plugins ───────────────────────────────────────────────────────────
class SlackNotificationPlugin(PublisherToolsPlugin):
    """Slack notification plugin।"""
    name = 'slack_notifications'
    version = '1.0.0'
    description = 'Send Slack notifications for important publisher events'

    def on_publisher_approved(self, publisher):
        logger.info(f'[Slack] Publisher approved: {publisher.publisher_id}')

    def on_fraud_detected(self, log):
        if log.severity in ('high', 'critical'):
            logger.info(f'[Slack] Critical fraud: {log.publisher.publisher_id} — score: {log.fraud_score}')


class EmailNotificationPlugin(PublisherToolsPlugin):
    """Email notification plugin।"""
    name = 'email_notifications'
    version = '1.0.0'
    description = 'Send email notifications for publisher events'

    def on_invoice_generated(self, invoice):
        logger.info(f'[Email] Invoice generated: {invoice.invoice_number} for {invoice.publisher.contact_email}')

    def on_earning_finalized(self, publisher, year: int, month: int):
        logger.info(f'[Email] Earnings finalized for {publisher.publisher_id}: {year}-{month:02d}')
