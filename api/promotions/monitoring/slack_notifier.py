# api/promotions/monitoring/slack_notifier.py
# Slack Notifier — Rich Slack messages for business events
import logging
from django.conf import settings
logger = logging.getLogger('monitoring.slack')

WEBHOOK = getattr(settings, 'SLACK_WEBHOOK', None)
CHANNELS = {
    'alerts':    getattr(settings, 'SLACK_ALERTS_CHANNEL', '#alerts'),
    'fraud':     getattr(settings, 'SLACK_FRAUD_CHANNEL', '#fraud'),
    'finance':   getattr(settings, 'SLACK_FINANCE_CHANNEL', '#finance'),
    'reports':   getattr(settings, 'SLACK_REPORTS_CHANNEL', '#reports'),
}

class SlackNotifier:
    """Rich Slack notifications with blocks UI。"""

    def notify_daily_report(self, report: dict) -> bool:
        blocks = [
            {'type': 'header', 'text': {'type': 'plain_text', 'text': f'📊 Daily Report — {report.get("date")}'}},
            {'type': 'section', 'fields': [
                {'type': 'mrkdwn', 'text': f'*Submissions:*\n{report.get("submissions",0)}'},
                {'type': 'mrkdwn', 'text': f'*Revenue:*\n${report.get("revenue_usd",0):.2f}'},
                {'type': 'mrkdwn', 'text': f'*Approved:*\n{report.get("approved",0)}'},
                {'type': 'mrkdwn', 'text': f'*Workers:*\n{report.get("unique_workers",0)}'},
            ]},
        ]
        return self._send_blocks(blocks, CHANNELS['reports'])

    def notify_fraud_detected(self, user_id: int, campaign_id: int, score: float) -> bool:
        return self._send_text(
            f'🚨 *Fraud Detected*\nUser #{user_id} | Campaign #{campaign_id}\nScore: `{score:.2f}`',
            CHANNELS['fraud']
        )

    def notify_large_payout(self, user_id: int, amount_usd: float, method: str) -> bool:
        return self._send_text(
            f'💰 *Large Payout*\nUser #{user_id} | ${amount_usd:.2f} via {method}',
            CHANNELS['finance']
        )

    def notify_system_error(self, component: str, error: str) -> bool:
        return self._send_text(f'⚠️ *System Error*\nComponent: {component}\n```{error[:500]}```', CHANNELS['alerts'])

    def _send_text(self, text: str, channel: str) -> bool:
        return self._send({'text': text, 'channel': channel})

    def _send_blocks(self, blocks: list, channel: str) -> bool:
        return self._send({'blocks': blocks, 'channel': channel})

    def _send(self, payload: dict) -> bool:
        if not WEBHOOK:
            logger.debug(f'Slack: {payload.get("text","[blocks]")[:100]}')
            return False
        try:
            import requests
            requests.post(WEBHOOK, json=payload, timeout=5)
            return True
        except Exception as e:
            logger.error(f'Slack send failed: {e}')
            return False
