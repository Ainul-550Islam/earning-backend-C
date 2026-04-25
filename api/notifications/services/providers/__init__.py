# earning_backend/api/notifications/services/providers/__init__.py
"""
Notification channel providers package.

Each provider wraps a third-party messaging service and exposes a
consistent dict-based response API used by NotificationDispatcher.

All providers are instantiated as module-level singletons so that
heavy initialisation (Firebase app, Twilio client, etc.) happens once
at import time rather than on every notification send.

Usage:
    from notifications.services.providers.FCMProvider import fcm_provider
    from notifications.services.providers.APNsProvider import apns_provider
    from notifications.services.providers.SendGridProvider import sendgrid_provider
    from notifications.services.providers.TwilioProvider import twilio_provider
    from notifications.services.providers.ShohoSMSProvider import shoho_sms_provider
    from notifications.services.providers.WebPushProvider import web_push_provider
"""

from .FCMProvider import fcm_provider, FCMProvider
from .APNsProvider import apns_provider, APNsProvider
from .SendGridProvider import sendgrid_provider, SendGridProvider
from .TwilioProvider import twilio_provider, TwilioProvider
from .ShohoSMSProvider import shoho_sms_provider, ShohoSMSProvider
from .WebPushProvider import web_push_provider, WebPushProvider

__all__ = [
    # Singletons
    'fcm_provider',
    'apns_provider',
    'sendgrid_provider',
    'twilio_provider',
    'shoho_sms_provider',
    'web_push_provider',
    # Classes (for testing / sub-classing)
    'FCMProvider',
    'APNsProvider',
    'SendGridProvider',
    'TwilioProvider',
    'ShohoSMSProvider',
    'WebPushProvider',
]

from .SlackProvider import slack_provider, SlackProvider       # noqa: F401
from .DiscordProvider import discord_provider, DiscordProvider # noqa: F401

from .TwilioVoiceProvider import twilio_voice_provider, TwilioVoiceProvider  # noqa
from .LineProvider import line_provider, LineProvider  # noqa
from .TeamsProvider import teams_provider, TeamsProvider  # noqa
