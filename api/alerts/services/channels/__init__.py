"""
Alert Channel Services Package

Each service exposes a .send(notification, channel) classmethod.
PagerDutyService and OpsGenieService also expose .resolve() / .close().
DiscordAlertService and WebhookAlertService also expose .send_resolved().
"""
from ._shared import get_effective_alert_log
from .EmailAlertService import EmailAlertService
from .SMSAlertService import SMSAlertService
from .TelegramAlertService import TelegramAlertService
from .SlackAlertService import SlackAlertService
from .PagerDutyService import PagerDutyService
from .OpsGenieService import OpsGenieService
from .DiscordAlertService import DiscordAlertService
from .WebhookAlertService import WebhookAlertService

__all__ = [
    'EmailAlertService',
    'SMSAlertService',
    'TelegramAlertService',
    'SlackAlertService',
    'PagerDutyService',
    'OpsGenieService',
    'DiscordAlertService',
    'WebhookAlertService',
    'get_effective_alert_log',
]
