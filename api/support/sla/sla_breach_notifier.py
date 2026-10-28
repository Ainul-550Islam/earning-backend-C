"""
api/support/sla/sla_breach_notifier.py
FILE 12/70 — SLA Breach Multi-Channel Notifier

SLA breach হলে:
- Agent-কে: Email + Telegram + Slack
- Supervisor-কে: Email + Slack
- User-কে: Email (empathetic apology)
- Management-কে: Slack digest
"""
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://yoursite.com')


class SLABreachNotifier:
    """
    Multi-channel SLA breach notifications।
    Warning → Agent | Breach → Agent + Supervisor | Critical → Management
    """

    # ──────────────────────────────────────────
    # WARNING (1 hour before breach)
    # ──────────────────────────────────────────
    def notify_warning(self, ticket, breach_type: str) -> None:
        """SLA breach কাছে — agent-কে warn করো"""
        logger.info(f'SLA Warning: {ticket.ticket_id} | {breach_type}')

        breach_labels = {
            'first_response': 'First Response SLA',
            'resolution':     'Resolution SLA',
        }
        label    = breach_labels.get(breach_type, breach_type)
        due_time = self._get_due_time(ticket, breach_type)

        # Notify assigned agent
        if ticket.assigned_to:
            self._notify_agent_warning(ticket, label, due_time)

        # Slack warning
        self._slack_warning(ticket, label, due_time)

    # ──────────────────────────────────────────
    # BREACH
    # ──────────────────────────────────────────
    def notify_breach(self, ticket, breach_type: str, overdue_hours: float) -> None:
        """SLA breach হয়েছে — সব channels-এ alert পাঠাও"""
        logger.warning(f'SLA BREACH: {ticket.ticket_id} | {breach_type} | {overdue_hours:.1f}h overdue')

        breach_labels = {
            'first_response': 'First Response SLA BREACHED',
            'resolution':     'Resolution SLA BREACHED',
        }
        label = breach_labels.get(breach_type, f'{breach_type} SLA BREACHED')

        # 1. Agent notification
        if ticket.assigned_to:
            self._notify_agent_breach(ticket, label, overdue_hours)

        # 2. Supervisor notification
        self._notify_supervisor_breach(ticket, label, overdue_hours, breach_type)

        # 3. User apology (only for resolution breach)
        if breach_type == 'resolution':
            self._notify_user_apology(ticket)

        # 4. Slack + Telegram alerts
        self._slack_breach_alert(ticket, label, overdue_hours)
        self._telegram_breach_alert(ticket, label, overdue_hours)

        # 5. DB log
        self._log_notification(ticket, breach_type, overdue_hours)

    # ──────────────────────────────────────────
    # AGENT NOTIFICATIONS
    # ──────────────────────────────────────────
    def _notify_agent_warning(self, ticket, label: str, due_time) -> None:
        try:
            agent = ticket.assigned_to

            # Email
            subject = f'⚠️ SLA Warning: {ticket.ticket_id} — {label}'
            body    = (
                f'Hello {agent.username},\n\n'
                f'SLA Warning for Ticket {ticket.ticket_id}:\n\n'
                f'Subject: {ticket.subject}\n'
                f'Priority: {ticket.priority.upper()}\n'
                f'User: {ticket.user.username}\n'
                f'Breach Type: {label}\n'
                f'Due At: {due_time}\n\n'
                f'Please respond immediately.\n\n'
                f'View ticket: {SITE_URL}/admin/support/tickets/{ticket.ticket_id}/'
            )
            self._send_email(agent.email, subject, body)

            # Telegram if configured
            if hasattr(agent, 'support_agent') and agent.support_agent.telegram_chat_id:
                self._send_telegram(
                    agent.support_agent.telegram_chat_id,
                    f'⚠️ *SLA Warning*\n\n'
                    f'Ticket: `{ticket.ticket_id}`\n'
                    f'Type: {label}\n'
                    f'Due: {due_time}\n\n'
                    f'Please respond NOW!'
                )

        except Exception as e:
            logger.error(f'Agent warning notification failed: {e}')

    def _notify_agent_breach(self, ticket, label: str, overdue_hours: float) -> None:
        try:
            agent   = ticket.assigned_to
            subject = f'🚨 SLA BREACH: {ticket.ticket_id} — {label}'
            body    = (
                f'Hello {agent.username},\n\n'
                f'URGENT: SLA has been BREACHED for Ticket {ticket.ticket_id}.\n\n'
                f'Subject: {ticket.subject}\n'
                f'Priority: {ticket.priority.upper()}\n'
                f'User: {ticket.user.username}\n'
                f'Breach Type: {label}\n'
                f'Overdue By: {overdue_hours:.1f} hours\n\n'
                f'IMMEDIATE ACTION REQUIRED.\n\n'
                f'View ticket: {SITE_URL}/admin/support/tickets/{ticket.ticket_id}/'
            )
            self._send_email(agent.email, subject, body)

            # Telegram
            if hasattr(agent, 'support_agent') and agent.support_agent.telegram_chat_id:
                self._send_telegram(
                    agent.support_agent.telegram_chat_id,
                    f'🚨 *SLA BREACH*\n\n'
                    f'Ticket: `{ticket.ticket_id}`\n'
                    f'Priority: {ticket.priority.upper()}\n'
                    f'Overdue: {overdue_hours:.1f} hours\n\n'
                    f'RESPOND IMMEDIATELY!'
                )

        except Exception as e:
            logger.error(f'Agent breach notification failed: {e}')

    # ──────────────────────────────────────────
    # SUPERVISOR NOTIFICATION
    # ──────────────────────────────────────────
    def _notify_supervisor_breach(self, ticket, label: str, overdue_hours: float, breach_type: str) -> None:
        try:
            from api.support.models import SupportAgent
            supervisors = SupportAgent.objects.filter(
                role__in  = ['supervisor', 'manager'],
                is_active = True,
            ).select_related('user')

            for sup_agent in supervisors:
                subject = f'🔴 SLA BREACH — Supervisor Alert: {ticket.ticket_id}'
                body    = (
                    f'Hello {sup_agent.user.username},\n\n'
                    f'A ticket has breached SLA under your supervision.\n\n'
                    f'Ticket ID: {ticket.ticket_id}\n'
                    f'Priority: {ticket.priority.upper()}\n'
                    f'Category: {ticket.category}\n'
                    f'User: {ticket.user.username}\n'
                    f'Assigned To: {ticket.assigned_to.username if ticket.assigned_to else "Unassigned"}\n'
                    f'Breach Type: {label}\n'
                    f'Overdue: {overdue_hours:.1f} hours\n\n'
                    f'Please take corrective action.\n\n'
                    f'View ticket: {SITE_URL}/admin/support/tickets/{ticket.ticket_id}/'
                )
                self._send_email(sup_agent.user.email, subject, body)

        except Exception as e:
            logger.error(f'Supervisor breach notification failed: {e}')

    # ──────────────────────────────────────────
    # USER APOLOGY
    # ──────────────────────────────────────────
    def _notify_user_apology(self, ticket) -> None:
        """Resolution breach হলে user-কে empathetic apology পাঠাও"""
        try:
            subject = f'Update on your support ticket #{ticket.ticket_id}'
            body    = (
                f'Hello {ticket.user.username},\n\n'
                f'We sincerely apologize for the delay in resolving your support ticket '
                f'#{ticket.ticket_id}.\n\n'
                f'We understand this is taking longer than expected, and we are sorry for '
                f'any inconvenience this has caused.\n\n'
                f'Our team is actively working on your issue and will respond to you '
                f'as soon as possible.\n\n'
                f'If this is urgent, please reply to this email or contact us directly.\n\n'
                f'Thank you for your patience and understanding.\n\n'
                f'Best regards,\n'
                f'Support Team'
            )
            self._send_email(ticket.user.email, subject, body)

        except Exception as e:
            logger.error(f'User apology notification failed: {e}')

    # ──────────────────────────────────────────
    # SLACK + TELEGRAM
    # ──────────────────────────────────────────
    def _slack_warning(self, ticket, label: str, due_time) -> None:
        try:
            from api.support.integrations.slack_integration import slack_integration
            slack_integration.notify_sla_breach(ticket, f'{label} (WARNING)', 0)
        except Exception:
            pass

    def _slack_breach_alert(self, ticket, label: str, overdue_hours: float) -> None:
        try:
            from api.support.integrations.slack_integration import slack_integration
            slack_integration.notify_sla_breach(ticket, label, overdue_hours)
        except Exception:
            pass

    def _telegram_breach_alert(self, ticket, label: str, overdue_hours: float) -> None:
        try:
            from django.conf import settings
            admin_chat = getattr(settings, 'TELEGRAM_ADMIN_CHAT', '')
            if admin_chat:
                from api.support.integrations.telegram_bot import telegram_bot
                telegram_bot.notify_admin_sla_breach(ticket, label)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _get_due_time(self, ticket, breach_type: str) -> str:
        try:
            sla = ticket.sla
            due = sla.first_response_due if breach_type == 'first_response' else sla.resolution_due
            return due.strftime('%d %b %Y %H:%M UTC') if due else 'Unknown'
        except Exception:
            return 'Unknown'

    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            from django.core.mail import send_mail
            send_mail(
                subject        = subject,
                message        = body,
                from_email     = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@yoursite.com'),
                recipient_list = [to_email],
                fail_silently  = True,
            )
            return True
        except Exception as e:
            logger.error(f'Email send failed to {to_email}: {e}')
            return False

    def _send_telegram(self, chat_id: str, message: str) -> bool:
        try:
            from api.support.integrations.telegram_bot import telegram_bot
            return bool(telegram_bot.send_message(chat_id, message, parse_mode='Markdown'))
        except Exception:
            return False

    def _log_notification(self, ticket, breach_type: str, overdue_hours: float) -> None:
        try:
            from api.support.models import SupportNotificationLog
            SupportNotificationLog.objects.create(
                ticket  = ticket,
                user    = ticket.user,
                channel = 'sla_breach',
                event   = f'sla_{breach_type}_breach',
                status  = 'sent',
            )
        except Exception:
            pass


# Singleton
sla_notifier = SLABreachNotifier()