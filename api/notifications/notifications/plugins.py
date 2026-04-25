# earning_backend/api/notifications/plugins.py
"""
Plugins — Notification provider plugin system.
Allows third-party providers to be registered without modifying core code.
"""
import logging
from typing import Dict, Optional, Type
logger = logging.getLogger(__name__)


class ProviderPlugin:
    """Base class for notification provider plugins."""
    name: str = ''
    channel: str = 'in_app'
    supports_bulk: bool = False

    def is_available(self) -> bool:
        raise NotImplementedError

    def send(self, notification, **kwargs) -> dict:
        raise NotImplementedError

    def health_check(self) -> str:
        return 'healthy' if self.is_available() else 'unhealthy'


class PluginRegistry:
    """Registry for notification provider plugins."""

    def __init__(self):
        self._plugins: Dict[str, ProviderPlugin] = {}

    def register(self, plugin: ProviderPlugin, overwrite: bool = False):
        if plugin.name in self._plugins and not overwrite:
            logger.warning(f'Plugin "{plugin.name}" already registered.')
            return
        self._plugins[plugin.name] = plugin
        logger.info(f'Plugin registered: {plugin.name} (channel={plugin.channel})')

    def unregister(self, name: str):
        self._plugins.pop(name, None)

    def get(self, name: str) -> Optional[ProviderPlugin]:
        return self._plugins.get(name)

    def get_for_channel(self, channel: str) -> list:
        return [p for p in self._plugins.values() if p.channel == channel and p.is_available()]

    def all(self) -> Dict[str, ProviderPlugin]:
        return dict(self._plugins)

    def available(self) -> Dict[str, ProviderPlugin]:
        return {k: v for k, v in self._plugins.items() if v.is_available()}

    def health(self) -> dict:
        return {name: plugin.health_check() for name, plugin in self._plugins.items()}


# Register built-in providers
plugin_registry = PluginRegistry()

def register_builtin_providers():
    try:
        from api.notifications.services.providers.FCMProvider import fcm_provider
        class FCMPlugin(ProviderPlugin):
            name = 'fcm'; channel = 'push'; supports_bulk = True
            def is_available(self): return fcm_provider.is_available()
            def send(self, notification, **kwargs): return fcm_provider.send(kwargs.get('token',''), notification)
        plugin_registry.register(FCMPlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.SendGridProvider import sendgrid_provider
        class SendGridPlugin(ProviderPlugin):
            name = 'sendgrid'; channel = 'email'; supports_bulk = True
            def is_available(self): return sendgrid_provider.is_available()
            def send(self, notification, **kwargs): return sendgrid_provider.send(kwargs.get('email',''), notification.title, notification.message)
        plugin_registry.register(SendGridPlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.ShohoSMSProvider import shoho_sms_provider
        class ShohoPlugin(ProviderPlugin):
            name = 'shoho_sms'; channel = 'sms'
            def is_available(self): return shoho_sms_provider.is_available()
            def send(self, notification, **kwargs): return shoho_sms_provider.send_sms(kwargs.get('phone',''), notification.message)
        plugin_registry.register(ShohoPlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.SlackProvider import slack_provider
        class SlackPlugin(ProviderPlugin):
            name = 'slack'; channel = 'slack'
            def is_available(self): return slack_provider.is_available()
            def send(self, notification, **kwargs): return slack_provider.send(notification)
        plugin_registry.register(SlackPlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.DiscordProvider import discord_provider
        class DiscordPlugin(ProviderPlugin):
            name = 'discord'; channel = 'discord'
            def is_available(self): return discord_provider.is_available()
            def send(self, notification, **kwargs): return discord_provider.send(notification)
        plugin_registry.register(DiscordPlugin())
    except Exception as exc:
        import traceback
        logger.error(
            'DiscordPlugin failed to load — Discord notifications unavailable. '
            'Error: %s\n%s', str(exc), traceback.format_exc()
        )

    try:
        from api.notifications.services.providers.TwilioVoiceProvider import twilio_voice_provider
        class VoicePlugin(ProviderPlugin):
            name = 'voice'; channel = 'voice'
            def is_available(self): return twilio_voice_provider.is_available()
            def send(self, notification, **kwargs): return twilio_voice_provider.send(notification)
        plugin_registry.register(VoicePlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.TeamsProvider import teams_provider
        class TeamsPlugin(ProviderPlugin):
            name = 'teams'; channel = 'teams'
            def is_available(self): return teams_provider.is_available()
            def send(self, notification, **kwargs): return teams_provider.send(notification)
        plugin_registry.register(TeamsPlugin())
    except Exception: pass

    try:
        from api.notifications.services.providers.LineProvider import line_provider
        class LinePlugin(ProviderPlugin):
            name = 'line'; channel = 'line'
            def is_available(self): return line_provider.is_available()
            def send(self, notification, **kwargs): return line_provider.send(notification)
        plugin_registry.register(LinePlugin())
    except Exception: pass
    except Exception: pass
