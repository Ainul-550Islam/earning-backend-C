"""
api/support/notifications/escalation_notifier.py
FILE 32/70 — Escalation Notification System

Escalation events-এর multi-channel notification।
"""
import logging
logger = logging.getLogger(__name__)


class EscalationNotifier:
    """Escalation notifications — Email + Slack + Telegram"""

    def notify_ticket_escalated(self, ticket, reason: str = '') -> None:
        """Ticket escalate হলে supervisor + management notify করো"""
        try:
            # Email to supervisors
            from api.support.models import SupportAgent
            supervisors = SupportAgent.objects.filter(
                role__in=['supervisor','manager'], is_active=True
            ).select_related('user')

            from api.support.notifications.email_notifier import email_notifier
            for sup in supervisors:
                email_notifier.escalation_notice(ticket, sup.user)

            # Slack alert
            from api.support.integrations.slack_integration import slack_integration
            slack_integration.notify_sla_breach(ticket, f'Ticket Escalated: {reason}', 0)

            # Telegram admin alert
            from api.support.integrations.telegram_bot import telegram_bot
            telegram_bot.notify_admin_new_ticket(ticket)

            logger.warning(f'Escalation notified: {ticket.ticket_id}')
        except Exception as e:
            logger.error(f'Escalation notification failed: {e}')

    def notify_sla_breach_all_channels(self, ticket, breach_type: str, overdue_hours: float) -> None:
        """SLA breach — সব channels"""
        try:
            # Agent email
            if ticket.assigned_to:
                from api.support.notifications.email_notifier import email_notifier
                email_notifier.sla_breach(ticket, ticket.assigned_to, breach_type, overdue_hours)

                # Agent SMS
                from api.support.notifications.sms_notifier import sms_notifier
                phone = sms_notifier.get_user_phone(ticket.assigned_to)
                if phone:
                    sms_notifier.sla_breach_alert(ticket, phone, breach_type)

                # Agent Telegram
                from api.support.notifications.telegram_notifier import telegram_notifier
                telegram_notifier.sla_breach_admin(ticket, breach_type)

            # Slack
            from api.support.integrations.slack_integration import slack_integration
            slack_integration.notify_sla_breach(ticket, breach_type, overdue_hours)

        except Exception as e:
            logger.error(f'SLA breach all-channel notification failed: {e}')


escalation_notifier = EscalationNotifier()