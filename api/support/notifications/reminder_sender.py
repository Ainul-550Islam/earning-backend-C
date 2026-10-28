"""
api/support/notifications/reminder_sender.py
FILE 33/70 — Follow-up Reminder System

Auto-reminders:
- Waiting for user reply > 3 days → remind user
- Unresolved ticket > 5 days → remind agent
- Pending CSAT rating → remind user
- KYC incomplete → remind user
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReminderSender:
    """Automated reminder system"""

    def send_user_reply_reminders(self, idle_days: int = 3) -> int:
        """User reply না দিলে remind করো"""
        from api.support.models import SupportTicket
        from api.support.notifications.email_notifier import email_notifier

        cutoff  = timezone.now() - timedelta(days=idle_days)
        tickets = SupportTicket.objects.filter(
            status         = 'waiting_user',
            updated_at__lte= cutoff,
        ).select_related('user')

        sent = 0
        for ticket in tickets[:50]:
            subject = f'Reminder: Your ticket #{ticket.ticket_id} needs your response'
            body    = (
                f'Hello {ticket.user.username},\n\n'
                f'We are waiting for your reply on ticket #{ticket.ticket_id}.\n'
                f'Subject: {ticket.subject}\n\n'
                f'If we don\'t hear from you in 4 more days, the ticket will be auto-closed.\n\n'
                f'Reply here: {getattr(__import__("django.conf", fromlist=["settings"]), "settings", type("", (), {"SITE_URL": ""})()).SITE_URL}/support/tickets/{ticket.ticket_id}/\n\n'
                f'Best regards,\nSupport Team'
            )
            if email_notifier._send(ticket.user.email, subject, body):
                sent += 1

        logger.info(f'User reply reminders sent: {sent}')
        return sent

    def send_agent_followup_reminders(self, idle_days: int = 5) -> int:
        """Agent-এর long-pending tickets — remind"""
        from api.support.models import SupportTicket
        from api.support.notifications.email_notifier import email_notifier

        cutoff  = timezone.now() - timedelta(days=idle_days)
        tickets = SupportTicket.objects.filter(
            status__in     = ['open', 'in_progress'],
            assigned_to__isnull = False,
            updated_at__lte= cutoff,
        ).select_related('user', 'assigned_to')

        sent = 0
        for ticket in tickets[:50]:
            if not ticket.assigned_to:
                continue
            subject = f'Reminder: Ticket #{ticket.ticket_id} needs attention ({idle_days}+ days old)'
            body    = (
                f'Hello {ticket.assigned_to.username},\n\n'
                f'Ticket #{ticket.ticket_id} has been pending for {idle_days}+ days.\n'
                f'Subject: {ticket.subject}\n'
                f'User: {ticket.user.username}\n'
                f'Priority: {ticket.priority.upper()}\n\n'
                f'Please take action immediately.\n\n'
                f'Support Team'
            )
            if email_notifier._send(ticket.assigned_to.email, subject, body):
                sent += 1

        return sent

    def send_csat_reminders(self, hours_after_resolve: int = 48) -> int:
        """CSAT rating না দিলে remind করো"""
        from api.support.models import SupportTicket
        from api.support.notifications.email_notifier import email_notifier

        cutoff = timezone.now() - timedelta(hours=hours_after_resolve)
        tickets = SupportTicket.objects.filter(
            status              = 'resolved',
            resolved_at__lte    = cutoff,
            satisfaction_rating__isnull = True,
        ).select_related('user')

        sent = 0
        for ticket in tickets[:50]:
            if email_notifier.csat_request(ticket):
                sent += 1

        return sent

    def send_kyc_reminders(self) -> int:
        """KYC incomplete users-কে remind করো"""
        from django.contrib.auth import get_user_model
        User  = get_user_model()
        from api.support.notifications.email_notifier import email_notifier

        sent = 0
        # Users with pending withdrawal but no KYC
        try:
            from api.support.models import SupportTicket
            kyc_users = User.objects.filter(
                support_supportticket_user__category='kyc',
                support_supportticket_user__status__in=['open','in_progress'],
            ).distinct()[:50]

            for user in kyc_users:
                subject = 'Complete Your KYC Verification'
                body    = (
                    f'Hello {user.username},\n\n'
                    f'Your KYC verification is still pending.\n'
                    f'Complete it to unlock withdrawals and full platform features.\n\n'
                    f'Complete KYC: your-site.com/kyc\n\n'
                    f'Support Team'
                )
                if email_notifier._send(user.email, subject, body):
                    sent += 1
        except Exception as e:
            logger.error(f'KYC reminder failed: {e}')

        return sent

    def run_all_reminders(self) -> dict:
        """All reminders একসাথে run করো — Celery daily task"""
        return {
            'user_reply':   self.send_user_reply_reminders(idle_days=3),
            'agent_followup':self.send_agent_followup_reminders(idle_days=5),
            'csat':         self.send_csat_reminders(hours_after_resolve=48),
            'kyc':          self.send_kyc_reminders(),
            'run_at':       timezone.now().isoformat(),
        }


reminder_sender = ReminderSender()