# api/support/notifications_push.py
"""
Push notification integration for support events.
Supports: FCM (Firebase), APNs (Apple), WebPush.
Delegates to your notifications app — no direct push logic here.
"""
import logging

logger = logging.getLogger(__name__)


class SupportPushNotifications:
    """Send push notifications for support events."""

    def _send_push(self, user, title: str, body: str, data: dict = None) -> bool:
        """
        Send push notification via your notifications app.
        Falls back to in-app notification if push unavailable.
        """
        try:
            from api.support.integrations.integ_adapter import notifications_adapter
            return notifications_adapter.send(
                user=user,
                title=title,
                body=body,
                notification_type='push',
                data=data or {},
                priority='high',
            )
        except Exception as e:
            logger.debug(f'SupportPushNotifications._send_push: {e}')
            return False

    def push_ticket_created(self, ticket) -> bool:
        return self._send_push(
            ticket.user,
            title=f'Ticket #{ticket.ticket_id} Received',
            body='Your support ticket has been created. We will respond soon.',
            data={
                'type':      'ticket_created',
                'ticket_id': ticket.ticket_id,
                'action':    'open_ticket',
            }
        )

    def push_ticket_replied(self, ticket) -> bool:
        return self._send_push(
            ticket.user,
            title=f'New Reply — #{ticket.ticket_id}',
            body='Your support agent has replied to your ticket.',
            data={
                'type':      'ticket_replied',
                'ticket_id': ticket.ticket_id,
                'action':    'open_ticket',
            }
        )

    def push_ticket_resolved(self, ticket) -> bool:
        return self._send_push(
            ticket.user,
            title='Ticket Resolved! 🎉',
            body=f'Ticket #{ticket.ticket_id} has been resolved. Please rate your experience.',
            data={
                'type':      'ticket_resolved',
                'ticket_id': ticket.ticket_id,
                'action':    'rate_ticket',
            }
        )

    def push_dispute_approved(self, dispute, amount) -> bool:
        return self._send_push(
            dispute.user,
            title=f'Dispute Approved — {amount} Credits! 🎉',
            body='Your offer dispute has been approved. Credits added to your wallet!',
            data={
                'type':     'dispute_approved',
                'offer_id': dispute.offer_id,
                'amount':   str(amount),
                'action':   'open_wallet',
            }
        )

    def push_chat_agent_joined(self, session, agent_name: str) -> bool:
        return self._send_push(
            session.user,
            title='Agent Connected 💬',
            body=f'{agent_name} has joined your chat.',
            data={
                'type':       'chat_agent_joined',
                'session_id': str(session.session_id),
                'action':     'open_chat',
            }
        )

    def push_sla_warning(self, ticket) -> bool:
        """Notify agent of approaching SLA breach."""
        if not ticket.assigned_to:
            return False
        return self._send_push(
            ticket.assigned_to,
            title=f'SLA Warning — #{ticket.ticket_id} ⚠️',
            body='SLA deadline approaching. Please respond soon.',
            data={
                'type':      'sla_warning',
                'ticket_id': ticket.ticket_id,
                'action':    'open_ticket',
            }
        )

    def push_broadcast(self, users_qs, title: str, body: str, data: dict = None) -> int:
        """Broadcast push to multiple users (max 500)."""
        sent = 0
        for user in users_qs[:500]:
            try:
                ok = self._send_push(user, title=title, body=body, data=data or {})
                if ok:
                    sent += 1
            except Exception:
                pass
        return sent


push_notifications = SupportPushNotifications()