"""
SmartLink Notification Service
Real-time alerts via WebSocket + Email + Telegram + Slack.
World #1: No competitor sends real-time Telegram/Slack alerts.
"""
import logging
import threading
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

logger = logging.getLogger('smartlink.notifications')
User = get_user_model()


class NotificationService:
    """Send alerts to publishers via multiple channels."""

    def notify_cap_reached(self, publisher, smartlink, offer, usage: dict):
        msg = (
            f"🚨 Offer Cap Reached!\n"
            f"SmartLink: [{smartlink.slug}]\n"
            f"Offer: {offer.name}\n"
            f"Daily clicks: {usage['daily_used']}/{usage['daily_cap']}"
        )
        self._dispatch(publisher, msg, level='warning')

    def notify_fraud_spike(self, publisher, smartlink, fraud_rate: float):
        msg = (
            f"⚠️ Fraud Alert!\n"
            f"SmartLink: [{smartlink.slug}]\n"
            f"Fraud rate: {fraud_rate:.1f}% (threshold: 20%)\n"
            f"Action: Check traffic sources."
        )
        self._dispatch(publisher, msg, level='critical')

    def notify_broken_smartlink(self, publisher, smartlink):
        msg = (
            f"🔴 Broken SmartLink!\n"
            f"[{smartlink.slug}] has no active offers in pool.\n"
            f"Traffic is going to fallback URL."
        )
        self._dispatch(publisher, msg, level='critical')

    def notify_ab_winner(self, publisher, smartlink, winner_version, uplift: float):
        msg = (
            f"🏆 A/B Test Winner!\n"
            f"SmartLink: [{smartlink.slug}]\n"
            f"Winner: {winner_version.name}\n"
            f"Uplift: +{uplift:.1f}% conversion rate"
        )
        self._dispatch(publisher, msg, level='info')

    def notify_daily_report(self, publisher, stats: dict):
        msg = (
            f"📊 Daily Report\n"
            f"Clicks: {stats.get('clicks', 0):,}\n"
            f"Conversions: {stats.get('conversions', 0):,}\n"
            f"Revenue: ${stats.get('revenue', 0):,.2f}\n"
            f"EPC: ${stats.get('epc', 0):.4f}"
        )
        self._dispatch(publisher, msg, level='info')

    def _dispatch(self, publisher, message: str, level: str = 'info'):
        """Dispatch notification via all configured channels."""
        threads = []

        # Email
        if getattr(publisher, 'notify_email', True):
            t = threading.Thread(
                target=self._send_email,
                args=(publisher.email, message),
                daemon=True,
            )
            threads.append(t)

        # Telegram
        telegram_chat_id = getattr(publisher, 'telegram_chat_id', None)
        telegram_token   = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if telegram_chat_id and telegram_token:
            t = threading.Thread(
                target=self._send_telegram,
                args=(telegram_chat_id, telegram_token, message),
                daemon=True,
            )
            threads.append(t)

        # Slack
        slack_webhook = getattr(publisher, 'slack_webhook_url', None)
        if slack_webhook:
            t = threading.Thread(
                target=self._send_slack,
                args=(slack_webhook, message, level),
                daemon=True,
            )
            threads.append(t)

        # WebSocket push
        t = threading.Thread(
            target=self._push_websocket,
            args=(publisher.pk, message, level),
            daemon=True,
        )
        threads.append(t)

        for t in threads:
            t.start()

    def _send_email(self, email: str, message: str):
        try:
            send_mail(
                subject='SmartLink Alert',
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@smartlink.io'),
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning(f"Email notification failed: {e}")

    def _send_telegram(self, chat_id: str, token: str, message: str):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                'chat_id': chat_id,
                'text':    message,
                'parse_mode': 'HTML',
            }, timeout=5)
        except Exception as e:
            logger.warning(f"Telegram notification failed: {e}")

    def _send_slack(self, webhook_url: str, message: str, level: str):
        try:
            color_map = {'info': '#36a64f', 'warning': '#ff9800', 'critical': '#f44336'}
            payload = {
                'attachments': [{
                    'color': color_map.get(level, '#36a64f'),
                    'text':  message,
                    'footer': 'SmartLink Platform',
                }]
            }
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Slack notification failed: {e}")

    def _push_websocket(self, publisher_id: int, message: str, level: str):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            group = f'publisher_dashboard_{publisher_id}'
            async_to_sync(channel_layer.group_send)(group, {
                'type':    'dashboard_update',
                'data':    {'type': 'notification', 'message': message, 'level': level},
            })
        except Exception as e:
            logger.debug(f"WebSocket push failed: {e}")
