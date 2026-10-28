# api/support/notifications.py
"""
Support-specific notification dispatcher.
Centralizes all notification sending for support events.
Each method fires the correct notification to the right channel.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SupportNotificationService:
    """
    Sends notifications for all support events.
    Calls notifications app adapter — does NOT implement notification logic.
    """

    def _send(self, user, title: str, body: str, data: dict = None, priority: str = 'medium') -> bool:
        """Base send — delegates to notifications adapter."""
        try:
            from api.support.integrations.integ_adapter import notifications_adapter
            return notifications_adapter.send(
                user=user, title=title, body=body,
                data=data or {}, priority=priority,
            )
        except Exception as e:
            logger.debug(f'SupportNotificationService._send: {e}')
            return self._email_fallback(user, title, body)

    def _email_fallback(self, user, title: str, body: str) -> bool:
        """Email fallback when notifications adapter unavailable."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            if user.email:
                send_mail(
                    title, body,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@site.com'),
                    [user.email], fail_silently=True
                )
                return True
        except Exception as e:
            logger.error(f'Email fallback failed: {e}')
        return False

    def _log(self, event: str, user, ticket, channel: str = 'app', status: str = 'sent') -> None:
        """Log notification to SupportNotificationLog."""
        try:
            from api.support.models import SupportNotificationLog
            SupportNotificationLog.objects.create(
                user=user, ticket=ticket,
                channel=channel, event=event,
                recipient=user.email if user else '',
                status=status,
            )
        except Exception:
            pass

    # ── Ticket Events ─────────────────────────────────────────
    def notify_ticket_created(self, ticket) -> bool:
        """Notify user when their ticket is created."""
        title = f'Ticket #{ticket.ticket_id} Created ✅'
        body  = (
            f'Your support ticket has been received.\n'
            f'Category: {ticket.get_category_display()}\n'
            f'Priority: {ticket.get_priority_display()}\n'
            f'We will respond within our SLA time.'
        )
        ok = self._send(ticket.user, title, body, data={
            'type': 'ticket_created', 'ticket_id': ticket.ticket_id
        })
        self._log('ticket_created', ticket.user, ticket)
        return ok

    def notify_ticket_replied(self, ticket, reply_message: str = '') -> bool:
        """Notify user when agent replies to their ticket."""
        title = f'Support Replied — #{ticket.ticket_id} 💬'
        body  = f'Your support agent has replied to ticket #{ticket.ticket_id}.'
        if reply_message:
            body += f'\n\n"{reply_message[:200]}"'
        ok = self._send(ticket.user, title, body, data={
            'type': 'ticket_replied', 'ticket_id': ticket.ticket_id
        })
        self._log('ticket_replied', ticket.user, ticket)
        return ok

    def notify_ticket_resolved(self, ticket) -> bool:
        """Notify user when ticket is resolved + request CSAT."""
        title = f'Ticket #{ticket.ticket_id} Resolved ✅'
        body  = (
            f'Your support ticket has been resolved!\n\n'
            f'Issue: {ticket.subject}\n\n'
            f'Please rate your support experience.'
        )
        ok = self._send(ticket.user, title, body, data={
            'type': 'ticket_resolved',
            'ticket_id': ticket.ticket_id,
            'action': 'rate_ticket',
        }, priority='medium')
        self._log('ticket_resolved', ticket.user, ticket)
        return ok

    def notify_ticket_closed(self, ticket) -> bool:
        """Notify user when ticket is closed."""
        title = f'Ticket #{ticket.ticket_id} Closed'
        body  = f'Your ticket #{ticket.ticket_id} has been closed.'
        ok    = self._send(ticket.user, title, body, data={
            'type': 'ticket_closed', 'ticket_id': ticket.ticket_id
        })
        self._log('ticket_closed', ticket.user, ticket)
        return ok

    def notify_ticket_escalated(self, ticket) -> bool:
        """Notify user their ticket was escalated (priority boost)."""
        title = f'Ticket Escalated 🔴 — #{ticket.ticket_id}'
        body  = (
            f'Your ticket #{ticket.ticket_id} has been escalated for priority handling.\n'
            f'A senior agent will respond soon.'
        )
        ok = self._send(ticket.user, title, body, data={
            'type': 'ticket_escalated', 'ticket_id': ticket.ticket_id
        }, priority='high')
        self._log('ticket_escalated', ticket.user, ticket)
        return ok

    # ── SLA Events ────────────────────────────────────────────
    def notify_sla_warning(self, ticket, hours_remaining: float = 0) -> bool:
        """Notify agent when SLA deadline is approaching."""
        if not ticket.assigned_to:
            return False
        title = f'⚠️ SLA Warning — #{ticket.ticket_id}'
        body  = (
            f'Ticket #{ticket.ticket_id} SLA deadline in {round(hours_remaining, 1)}h.\n'
            f'Priority: {ticket.get_priority_display()}\n'
            f'User: {ticket.user.username}'
        )
        ok = self._send(ticket.assigned_to, title, body, data={
            'type': 'sla_warning', 'ticket_id': ticket.ticket_id
        }, priority='high')
        self._log('sla_warning', ticket.assigned_to, ticket)
        return ok

    def notify_sla_breach(self, ticket, breach_type: str = 'first_response') -> bool:
        """Notify agent AND supervisor on SLA breach."""
        title = f'🚨 SLA BREACH — #{ticket.ticket_id}'
        body  = (
            f'SLA {breach_type.replace("_"," ")} deadline MISSED for #{ticket.ticket_id}.\n'
            f'User: {ticket.user.username} | Priority: {ticket.get_priority_display()}'
        )
        ok = False
        if ticket.assigned_to:
            ok = self._send(ticket.assigned_to, title, body, data={
                'type': 'sla_breach', 'ticket_id': ticket.ticket_id
            }, priority='urgent')
            self._log('sla_breach', ticket.assigned_to, ticket)
        # Also notify via webhooks
        try:
            from api.support.webhooks import webhook_sender
            webhook_sender.send_sla_breach(ticket, breach_type)
        except Exception:
            pass
        return ok

    # ── Chat Events ───────────────────────────────────────────
    def notify_chat_agent_assigned(self, session, agent) -> bool:
        """Notify user their chat was assigned to an agent."""
        title = 'Agent Connected 💬'
        body  = f'Support agent {agent.username} has joined your chat.'
        ok    = self._send(session.user, title, body, data={
            'type': 'chat_agent_assigned',
            'session_id': str(session.session_id),
        })
        self._log('chat_agent_assigned', session.user, None)
        return ok

    def notify_chat_ended(self, session) -> bool:
        """Notify user their chat session ended."""
        title = 'Chat Session Ended'
        body  = 'Your live chat session has ended. You can view the transcript in your ticket.'
        ok    = self._send(session.user, title, body, data={
            'type': 'chat_ended',
            'session_id': str(session.session_id),
        })
        return ok

    # ── Dispute Events ────────────────────────────────────────
    def notify_dispute_approved(self, dispute, amount) -> bool:
        """Notify user their dispute was approved and coins credited."""
        title = f'🎉 Dispute Approved — {amount} Credits Added!'
        body  = (
            f'Your offer dispute for "{dispute.offer_name or dispute.offer_id}" '
            f'has been approved!\n'
            f'{amount} credits have been added to your wallet.'
        )
        ok = self._send(dispute.user, title, body, data={
            'type': 'dispute_approved',
            'offer_id': dispute.offer_id,
            'amount': str(amount),
        }, priority='high')
        self._log('dispute_approved', dispute.user, dispute.ticket)
        return ok

    def notify_dispute_rejected(self, dispute, reason: str = '') -> bool:
        """Notify user their dispute was rejected."""
        title = f'Dispute Decision — {dispute.offer_id}'
        body  = (
            f'Your offer dispute has been reviewed.\n'
            f'Decision: Rejected.\n'
        )
        if reason:
            body += f'Reason: {reason}'
        ok = self._send(dispute.user, title, body, data={
            'type': 'dispute_rejected',
            'offer_id': dispute.offer_id,
        })
        self._log('dispute_rejected', dispute.user, dispute.ticket)
        return ok

    def notify_dispute_needs_proof(self, dispute) -> bool:
        """Ask user to submit additional proof for their dispute."""
        title = f'Action Required — Dispute #{dispute.id}'
        body  = (
            f'Your offer dispute needs additional proof.\n'
            f'Offer: {dispute.offer_name or dispute.offer_id}\n'
            f'Please reply to your ticket with: screenshot, click ID, or transaction receipt.'
        )
        ok = self._send(dispute.user, title, body, data={
            'type': 'dispute_needs_proof',
            'offer_id': dispute.offer_id,
        })
        return ok

    # ── System Notifications ──────────────────────────────────
    def notify_maintenance_upcoming(self, users_qs, message: str, starts_at) -> int:
        """Broadcast maintenance notification to all users."""
        title = '⚠️ Scheduled Maintenance'
        body  = f'{message}\nExpected start: {starts_at.strftime("%Y-%m-%d %H:%M")}'
        sent  = 0
        for user in users_qs[:500]:  # Batch limit
            try:
                self._send(user, title, body, data={'type': 'maintenance'})
                sent += 1
            except Exception:
                pass
        return sent

    def notify_new_kb_article(self, article) -> bool:
        """Broadcast new KB article if it's important."""
        logger.info(f'New KB article: {article.title}')
        return True  # Actual broadcast handled by Celery task

    def _email(self, to_email: str, subject: str, body: str) -> bool:
        """Direct email send (used by daily digest etc.)."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject, body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@site.com'),
                [to_email], fail_silently=False
            )
            return True
        except Exception as e:
            logger.error(f'SupportNotificationService._email: {e}')
            return False

    def notify_new_reply(self, ticket, sender, is_agent: bool = True) -> bool:
        """Alias used by NotificationMixin."""
        if is_agent:
            return self.notify_ticket_replied(
                ticket,
                ticket.admin_response[:200] if ticket.admin_response else ''
            )
        # User replied — notify assigned agent
        if ticket.assigned_to:
            title = f'User Replied — #{ticket.ticket_id}'
            body  = f'{ticket.user.username} replied to ticket #{ticket.ticket_id}.'
            return self._send(ticket.assigned_to, title, body, data={
                'type': 'user_replied', 'ticket_id': ticket.ticket_id
            })
        return False


# Singleton
notification_service = SupportNotificationService()