"""
Webhook Handler
===============
Sends real-time threat alerts to configured external systems (Slack, Discord, custom webhooks).
"""
import json
import logging
import requests
from django.utils import timezone
from ..utils import format_risk_badge

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Sends alert payloads to configured webhook URLs.
    Supports generic HTTP webhooks, Slack, and Discord.
    """

    DEFAULT_TIMEOUT = 5

    def __init__(self, webhook_url: str, webhook_type: str = 'generic'):
        self.webhook_url = webhook_url
        self.webhook_type = webhook_type  # 'generic', 'slack', 'discord'

    def send_threat_alert(self, ip_address: str, risk_score: int,
                          risk_level: str, flags: list, tenant_name: str = '') -> bool:
        """Send a threat detection alert."""
        badge = format_risk_badge(risk_level)
        payload = self._build_payload(
            title=f"{badge} Threat Detected: {ip_address}",
            message=(
                f"IP: {ip_address}\n"
                f"Risk Score: {risk_score}/100\n"
                f"Risk Level: {risk_level.upper()}\n"
                f"Flags: {', '.join(flags) or 'none'}\n"
                f"Tenant: {tenant_name or 'global'}\n"
                f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            ),
            color='#ff0000' if risk_score >= 81 else '#ff9900',
        )
        return self._send(payload)

    def send_fraud_alert(self, ip_address: str, fraud_type: str,
                         user_id: int = None) -> bool:
        """Send a fraud detection alert."""
        payload = self._build_payload(
            title=f"🚨 Fraud Detected: {fraud_type}",
            message=(
                f"IP: {ip_address}\n"
                f"Fraud Type: {fraud_type}\n"
                f"User ID: {user_id or 'unknown'}\n"
                f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            ),
            color='#cc0000',
        )
        return self._send(payload)

    def _build_payload(self, title: str, message: str, color: str = '#333333') -> dict:
        if self.webhook_type == 'slack':
            return {
                'attachments': [{
                    'title': title,
                    'text': message,
                    'color': color,
                    'footer': 'Proxy Intelligence System',
                }]
            }
        elif self.webhook_type == 'discord':
            return {
                'embeds': [{
                    'title': title,
                    'description': message,
                    'color': int(color.lstrip('#'), 16),
                    'footer': {'text': 'Proxy Intelligence'},
                }]
            }
        else:
            return {'title': title, 'message': message, 'timestamp': timezone.now().isoformat()}

    def _send(self, payload: dict) -> bool:
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.DEFAULT_TIMEOUT,
                headers={'Content-Type': 'application/json'},
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Webhook delivery failed to {self.webhook_url}: {e}")
            return False


class AlertDispatcher:
    """
    Dispatches alerts to all configured alert channels for a given trigger.
    """

    @classmethod
    def dispatch(cls, trigger: str, context: dict, tenant=None) -> list:
        """
        Find all active AlertConfiguration objects matching the trigger
        and send notifications via their configured channels.
        """
        from ..models import AlertConfiguration
        configs = AlertConfiguration.objects.filter(trigger=trigger, is_active=True)
        if tenant:
            configs = configs.filter(tenant=tenant)

        sent = []
        for config in configs:
            if context.get('risk_score', 0) < config.threshold_score:
                continue
            try:
                if config.channel == 'webhook' and config.webhook_url:
                    handler = WebhookHandler(config.webhook_url, 'generic')
                    handler.send_threat_alert(
                        ip_address=context.get('ip_address', ''),
                        risk_score=context.get('risk_score', 0),
                        risk_level=context.get('risk_level', ''),
                        flags=context.get('flags', []),
                    )
                    sent.append(config.name)
                # Email, Slack, SMS would be dispatched here similarly
                config.last_sent = timezone.now()
                config.save(update_fields=['last_sent'])
            except Exception as e:
                logger.error(f"Alert dispatch failed for config '{config.name}': {e}")

        return sent
