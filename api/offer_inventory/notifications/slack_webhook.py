# api/offer_inventory/notifications/slack_webhook.py
"""
Slack Webhook Integration — Operational alerts for Slack channels.
Sends formatted messages for: fraud, errors, conversions, daily summaries.
"""
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Slack webhook notification sender."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or getattr(settings, 'SLACK_WEBHOOK_URL', '')

    def send(self, message: str, channel: str = None,
              color: str = 'good', fields: list = None,
              title: str = '') -> bool:
        """Send a Slack message via webhook."""
        if not self.webhook_url:
            logger.debug('Slack webhook not configured.')
            return False

        attachment = {
            'color'     : color,
            'text'      : message,
            'footer'    : 'Offer Inventory System',
            'footer_icon': 'https://platform.com/favicon.ico',
            'ts'        : int(time.time()),
        }
        if title:
            attachment['title'] = title
        if fields:
            attachment['fields'] = fields

        payload = {'attachments': [attachment]}
        if channel:
            payload['channel'] = channel

        try:
            import requests
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'Slack notification error: {e}')
            return False

    def alert_fraud(self, stats: dict) -> bool:
        """Send fraud spike alert."""
        return self.send(
            message=f'🚨 *Fraud Spike Detected*\nFraud Rate: {stats.get("fraud_rate", 0):.1f}%',
            color  ='danger',
            title  ='Fraud Alert',
            fields =[
                {'title': 'Fraud Clicks', 'value': str(stats.get('fraud_clicks', 0)),  'short': True},
                {'title': 'Total Clicks', 'value': str(stats.get('total_clicks', 0)), 'short': True},
                {'title': 'Threshold',    'value': '15%',                               'short': True},
            ],
        )

    def alert_new_conversion(self, conversion) -> bool:
        """Notify on high-value conversion."""
        payout = float(conversion.payout_amount) if conversion.payout_amount else 0
        if payout < 1.0:  # Only notify for meaningful amounts
            return True
        return self.send(
            message=f'✅ New Conversion — {conversion.offer.title if conversion.offer else "?"}',
            color  ='good',
            fields =[
                {'title': 'Payout',   'value': f'৳{payout:.2f}',     'short': True},
                {'title': 'Country',  'value': conversion.country_code or '?', 'short': True},
            ],
        )

    def alert_system_error(self, error: str) -> bool:
        """Send critical error alert."""
        return self.send(
            message=f'🔴 *System Error*\n```{error[:400]}```',
            color  ='danger',
            title  ='Critical System Error',
        )

    def alert_offer_capped(self, offer) -> bool:
        """Notify when offer hits cap."""
        return self.send(
            message=f'⚠️ *Offer Capped & Paused*: {offer.title}',
            color  ='warning',
            fields =[
                {'title': 'Offer ID', 'value': str(offer.id)[:8], 'short': True},
                {'title': 'Status',   'value': 'Paused',           'short': True},
            ],
        )

    def daily_summary(self, stats: dict) -> bool:
        """Send daily platform summary."""
        return self.send(
            message='📊 *Daily Summary — Offer Inventory*',
            color  ='#36a64f',
            title  =f'Daily Report — {stats.get("date", "")}',
            fields =[
                {'title': 'Revenue',     'value': f'৳{stats.get("gross_revenue", 0):.2f}',    'short': True},
                {'title': 'Conversions', 'value': str(stats.get('total_conversions', 0)),      'short': True},
                {'title': 'Clicks',      'value': str(stats.get('total_clicks', 0)),           'short': True},
                {'title': 'CVR',         'value': f'{stats.get("cvr_pct", 0):.1f}%',          'short': True},
                {'title': 'Fraud Rate',  'value': f'{stats.get("fraud_rate_pct", 0):.1f}%',   'short': True},
                {'title': 'New Users',   'value': str(stats.get('new_users', 0)),              'short': True},
            ],
        )

    def send_withdrawal_alert(self, count: int, total_amount: float) -> bool:
        """Alert for pending withdrawal queue."""
        return self.send(
            message=f'💸 *{count} Withdrawals Pending*\nTotal: ৳{total_amount:.2f}',
            color  ='warning',
        )
