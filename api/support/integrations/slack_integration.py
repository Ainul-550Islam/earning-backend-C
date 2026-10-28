"""
api/support/integrations/slack_integration.py
FILE 5/70 — Slack Integration

Agent team-এর Slack channel-এ:
- New urgent tickets
- SLA breach alerts
- Daily summary
- Agent performance reports

Settings:
    SLACK_BOT_TOKEN    = 'xoxb-your-token'
    SLACK_WEBHOOK_URL  = 'https://hooks.slack.com/services/xxx'
    SLACK_CHANNEL      = '#support-alerts'
    SLACK_ADMIN_CHANNEL= '#support-admin'
"""
import json
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BOT_TOKEN     = getattr(settings, 'SLACK_BOT_TOKEN',     '')
WEBHOOK_URL   = getattr(settings, 'SLACK_WEBHOOK_URL',   '')
CHANNEL       = getattr(settings, 'SLACK_CHANNEL',       '#support-alerts')
ADMIN_CHANNEL = getattr(settings, 'SLACK_ADMIN_CHANNEL', '#support-admin')


class SlackIntegration:
    """
    Slack notifications for support team.
    Uses Incoming Webhooks (simple) + Bot API (advanced).
    """

    PRIORITY_COLORS = {
        'urgent': '#dc2626',   # Red
        'high':   '#ea580c',   # Orange
        'medium': '#ca8a04',   # Yellow
        'low':    '#16a34a',   # Green
    }

    PRIORITY_EMOJI = {
        'urgent': '🚨',
        'high':   '⚠️',
        'medium': '📢',
        'low':    'ℹ️',
    }

    # ─────────────────────────────────────
    # TICKET ALERTS
    # ─────────────────────────────────────
    def notify_new_ticket(self, ticket) -> bool:
        """New ticket created — agent channel-এ notify করো"""
        if ticket.priority not in ['urgent', 'high']:
            return False  # Only urgent/high go to Slack

        emoji = self.PRIORITY_EMOJI.get(ticket.priority, '📢')
        color = self.PRIORITY_COLORS.get(ticket.priority, '#6366f1')

        blocks = [
            {
                'type': 'header',
                'text': {'type': 'plain_text', 'text': f'{emoji} New {ticket.priority.upper()} Support Ticket'},
            },
            {
                'type': 'section',
                'fields': [
                    {'type': 'mrkdwn', 'text': f'*Ticket ID:*\n`{ticket.ticket_id}`'},
                    {'type': 'mrkdwn', 'text': f'*Priority:*\n{ticket.priority.upper()}'},
                    {'type': 'mrkdwn', 'text': f'*Category:*\n{ticket.category}'},
                    {'type': 'mrkdwn', 'text': f'*User:*\n{ticket.user.username}'},
                ],
            },
            {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f'*Subject:*\n{ticket.subject}'},
            },
            {
                'type': 'actions',
                'elements': [
                    {
                        'type': 'button',
                        'text': {'type': 'plain_text', 'text': 'View Ticket'},
                        'style': 'primary',
                        'url': f'{getattr(settings, "SITE_URL", "")}/admin/support/tickets/{ticket.ticket_id}/',
                    }
                ]
            },
        ]

        return self._send_blocks(CHANNEL, blocks, color=color)

    def notify_sla_breach(self, ticket, breach_type: str, overdue_hours: float) -> bool:
        """SLA breach — urgent alert"""
        blocks = [
            {
                'type': 'header',
                'text': {'type': 'plain_text', 'text': '🔴 SLA BREACH ALERT'},
            },
            {
                'type': 'section',
                'fields': [
                    {'type': 'mrkdwn', 'text': f'*Ticket:*\n`{ticket.ticket_id}`'},
                    {'type': 'mrkdwn', 'text': f'*Breach Type:*\n{breach_type.replace("_", " ").title()}'},
                    {'type': 'mrkdwn', 'text': f'*Overdue:*\n{overdue_hours:.1f} hours'},
                    {'type': 'mrkdwn', 'text': f'*Agent:*\n{ticket.assigned_to.username if ticket.assigned_to else "Unassigned"}'},
                ],
            },
            {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f'*Subject:*\n{ticket.subject}'},
            },
        ]
        return self._send_blocks(ADMIN_CHANNEL, blocks, color='#dc2626')

    def notify_ticket_resolved(self, ticket, by_agent) -> bool:
        """Ticket resolved — positive notification"""
        return self._send_webhook({
            'text': (
                f"✅ Ticket Resolved: `{ticket.ticket_id}`\n"
                f"Agent: {by_agent.username} | "
                f"Category: {ticket.category} | "
                f"Priority: {ticket.priority}"
            ),
            'channel': CHANNEL,
        })

    def notify_agent_assigned(self, ticket, agent) -> bool:
        """Ticket assigned to agent"""
        agent_slack = getattr(agent, 'slack_user_id', None)
        mention     = f'<@{agent_slack}>' if agent_slack else agent.username

        return self._send_webhook({
            'text': (
                f"📬 Ticket assigned to {mention}: "
                f"`{ticket.ticket_id}` — {ticket.subject[:60]} "
                f"[{ticket.priority.upper()}]"
            ),
            'channel': CHANNEL,
        })

    # ─────────────────────────────────────
    # DAILY DIGEST
    # ─────────────────────────────────────
    def send_daily_digest(self) -> bool:
        """Daily support summary — admin channel"""
        try:
            from api.support.models import SupportTicket, TicketRating
            from django.db.models import Avg, Count
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            created  = SupportTicket.objects.filter(created_at__gte=today).count()
            resolved = SupportTicket.objects.filter(resolved_at__gte=today).count()
            open_ct  = SupportTicket.objects.filter(status__in=['open', 'in_progress', 'waiting_user']).count()
            escalated= SupportTicket.objects.filter(escalated=True, status__in=['open','in_progress']).count()
            csat     = TicketRating.objects.filter(created_at__gte=today).aggregate(avg=Avg('rating'))['avg'] or 0

            blocks = [
                {
                    'type': 'header',
                    'text': {'type': 'plain_text', 'text': f'📊 Daily Support Digest — {today.strftime("%d %b %Y")}'},
                },
                {
                    'type': 'section',
                    'fields': [
                        {'type': 'mrkdwn', 'text': f'*📥 Created Today:*\n{created}'},
                        {'type': 'mrkdwn', 'text': f'*✅ Resolved Today:*\n{resolved}'},
                        {'type': 'mrkdwn', 'text': f'*📂 Open Tickets:*\n{open_ct}'},
                        {'type': 'mrkdwn', 'text': f'*🚨 Escalated:*\n{escalated}'},
                        {'type': 'mrkdwn', 'text': f'*⭐ CSAT Score:*\n{csat:.1f}/5.0'},
                        {'type': 'mrkdwn', 'text': f'*🕐 Report Time:*\n{timezone.now().strftime("%H:%M UTC")}'},
                    ],
                },
            ]

            return self._send_blocks(ADMIN_CHANNEL, blocks, color='#6366f1')

        except Exception as e:
            logger.error(f'Slack daily digest failed: {e}')
            return False

    def send_weekly_report(self) -> bool:
        """Weekly performance report"""
        from datetime import timedelta
        from api.support.models import SupportTicket, TicketRating
        from django.db.models import Avg
        since   = timezone.now() - timedelta(days=7)
        created = SupportTicket.objects.filter(created_at__gte=since).count()
        resolved= SupportTicket.objects.filter(resolved_at__gte=since).count()
        csat    = TicketRating.objects.filter(created_at__gte=since).aggregate(avg=Avg('rating'))['avg'] or 0
        rate    = round(resolved / created * 100, 1) if created else 0

        text = (
            f"📈 *Weekly Support Report*\n\n"
            f"• Tickets Created: *{created}*\n"
            f"• Tickets Resolved: *{resolved}*\n"
            f"• Resolution Rate: *{rate}%*\n"
            f"• CSAT Score: *{csat:.1f}/5.0*\n\n"
            f"_Week ending {timezone.now().strftime('%d %b %Y')}_"
        )
        return self._send_webhook({'text': text, 'channel': ADMIN_CHANNEL})

    # ─────────────────────────────────────
    # SEND HELPERS
    # ─────────────────────────────────────
    def _send_blocks(self, channel: str, blocks: list, color: str = '#6366f1') -> bool:
        """Rich block message পাঠাও"""
        # Try Webhook first (simpler)
        if WEBHOOK_URL:
            return self._send_webhook({
                'channel':     channel,
                'attachments': [{'color': color, 'blocks': blocks}],
            })
        # Fallback to Bot API
        return self._send_bot_api(channel, blocks)

    def _send_webhook(self, payload: dict) -> bool:
        if not WEBHOOK_URL:
            logger.debug('Slack: No webhook URL configured.')
            return False
        try:
            resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            if resp.status_code == 200 and resp.text == 'ok':
                return True
            logger.error(f'Slack webhook failed [{resp.status_code}]: {resp.text}')
            return False
        except Exception as e:
            logger.error(f'Slack webhook error: {e}')
            return False

    def _send_bot_api(self, channel: str, blocks: list) -> bool:
        if not BOT_TOKEN:
            logger.debug('Slack: No BOT_TOKEN configured.')
            return False
        try:
            resp = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers = {'Authorization': f'Bearer {BOT_TOKEN}', 'Content-Type': 'application/json'},
                json    = {'channel': channel, 'blocks': blocks},
                timeout = 10,
            )
            result = resp.json()
            if result.get('ok'):
                return True
            logger.error(f'Slack Bot API failed: {result.get("error")}')
            return False
        except Exception as e:
            logger.error(f'Slack Bot API error: {e}')
            return False

    def test_connection(self) -> dict:
        """Connection test"""
        result = {'webhook': False, 'bot_api': False}
        if WEBHOOK_URL:
            result['webhook'] = self._send_webhook({'text': '✅ Slack integration test successful!'})
        if BOT_TOKEN:
            try:
                resp = requests.get(
                    'https://slack.com/api/auth.test',
                    headers = {'Authorization': f'Bearer {BOT_TOKEN}'},
                    timeout = 10,
                )
                result['bot_api'] = resp.json().get('ok', False)
            except Exception:
                pass
        return result


# Singleton
slack_integration = SlackIntegration()