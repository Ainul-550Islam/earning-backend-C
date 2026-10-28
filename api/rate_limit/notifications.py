# api/rate_limit/notifications.py
"""
Notification service for rate limit module.
"""
import logging
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitNotificationService:
    """Handles notifications for rate limit alerts."""

    CHANNEL_EMAIL = 'email'
    CHANNEL_SLACK = 'slack'
    CHANNEL_WEBHOOK = 'webhook'
    CHANNEL_SMS = 'sms'

    def __init__(self):
        self.channels = getattr(settings, 'RATE_LIMIT_NOTIFICATION_CHANNELS', [self.CHANNEL_EMAIL])
        self.enabled = getattr(settings, 'RATE_LIMIT_NOTIFICATIONS_ENABLED', True)

    def send_notification(self, alert_data: Dict[str, Any], channel: Optional[str] = None) -> bool:
        """
        Send a notification for an alert.

        Args:
            alert_data: Alert information dict
            channel: Notification channel (email/slack/webhook/sms)

        Returns:
            bool: True if sent successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False

        channels = [channel] if channel else self.channels

        success = False
        for ch in channels:
            try:
                if ch == self.CHANNEL_EMAIL:
                    success = self._send_email(alert_data)
                elif ch == self.CHANNEL_SLACK:
                    success = self._send_slack(alert_data)
                elif ch == self.CHANNEL_WEBHOOK:
                    success = self._send_webhook(alert_data)
                elif ch == self.CHANNEL_SMS:
                    success = self._send_sms(alert_data)
            except Exception as e:
                logger.error(f"Failed to send notification via {ch}: {e}")

        return success

    def _send_email(self, alert_data: Dict[str, Any]) -> bool:
        """Send email notification."""
        try:
            from django.core.mail import send_mail
            subject = f"[Rate Limit Alert] {alert_data.get('severity', 'UNKNOWN').upper()}: {alert_data.get('name', 'Alert')}"
            message = self._format_message(alert_data)
            recipients = getattr(settings, 'RATE_LIMIT_ALERT_EMAILS', [])
            if not recipients:
                return False
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

    def _send_slack(self, alert_data: Dict[str, Any]) -> bool:
        """Send Slack notification."""
        try:
            import requests
            webhook_url = getattr(settings, 'RATE_LIMIT_SLACK_WEBHOOK', None)
            if not webhook_url:
                return False
            payload = {
                'text': f"*Rate Limit Alert*: {alert_data.get('name', 'Unknown')}",
                'attachments': [{
                    'color': 'danger' if alert_data.get('severity') == 'critical' else 'warning',
                    'text': self._format_message(alert_data),
                }]
            }
            response = requests.post(webhook_url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    def _send_webhook(self, alert_data: Dict[str, Any]) -> bool:
        """Send webhook notification."""
        try:
            import requests
            webhook_url = getattr(settings, 'RATE_LIMIT_WEBHOOK_URL', None)
            if not webhook_url:
                return False
            response = requests.post(webhook_url, json=alert_data, timeout=5)
            return response.status_code < 300
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False

    def _send_sms(self, alert_data: Dict[str, Any]) -> bool:
        """Send SMS notification (stub - integrate with SMS provider)."""
        logger.warning("SMS notifications not configured")
        return False

    def _format_message(self, alert_data: Dict[str, Any]) -> str:
        """Format alert data into readable message."""
        return (
            f"Alert: {alert_data.get('name', 'Unknown')}\n"
            f"Severity: {alert_data.get('severity', 'Unknown')}\n"
            f"Message: {alert_data.get('message', 'No message')}\n"
            f"Time: {alert_data.get('triggered_at', 'Unknown')}"
        )


__all__ = ['RateLimitNotificationService']
