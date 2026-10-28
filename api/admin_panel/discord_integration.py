# api/admin_panel/discord_integration.py
"""Discord webhook integration for platform events."""
from __future__ import annotations
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
WEBHOOK_URL = getattr(settings, 'DISCORD_WEBHOOK_URL', '')

COLORS = {'critical': 0xFF0000, 'high': 0xFF6600, 'medium': 0xFFCC00, 'info': 0x0066CC}

class DiscordIntegration:
    @classmethod
    def send(cls, title: str, description: str, severity: str = 'info', fields: list = None) -> bool:
        if not WEBHOOK_URL: return False
        try:
            import requests
            payload = {'embeds': [{'title': title, 'description': description,
                                    'color': COLORS.get(severity, 0x0066CC),
                                    'fields': fields or [],
                                    'footer': {'text': 'AdminPanel'}}]}
            r = requests.post(WEBHOOK_URL, json=payload, timeout=5)
            return r.status_code in (200, 204)
        except Exception as e:
            logger.error(f"[Discord] {e}")
            return False

    @classmethod
    def alert(cls, message: str, severity: str = 'medium') -> bool:
        emoji = {'critical': '🚨', 'high': '⚠️', 'medium': 'ℹ️'}.get(severity, 'ℹ️')
        return cls.send(f"{emoji} Admin Alert", message, severity)

discord = DiscordIntegration()