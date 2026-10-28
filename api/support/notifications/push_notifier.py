"""
api/support/notifications/push_notifier.py
FILE 28/70 — FCM Push Notification System

Firebase Cloud Messaging (FCM) দিয়ে mobile push।
Android + iOS support।

Settings:
    FCM_SERVER_KEY = 'your_fcm_server_key'
    APNS_KEY_ID    = 'your_apns_key'  # iOS
"""
import logging
import requests
from django.conf import settings

logger      = logging.getLogger(__name__)
FCM_KEY     = getattr(settings, 'FCM_SERVER_KEY', '')
FCM_URL     = 'https://fcm.googleapis.com/fcm/send'


class PushNotifier:
    """FCM push notifications for mobile app users"""

    def send_to_user(self, user, title: str, body: str, data: dict = None) -> bool:
        """User-কে push পাঠাও"""
        token = self._get_fcm_token(user)
        if not token:
            return False
        return self._send(token, title, body, data or {})

    def send_to_token(self, token: str, title: str, body: str, data: dict = None) -> bool:
        return self._send(token, title, body, data or {})

    def ticket_created(self, ticket) -> bool:
        return self.send_to_user(ticket.user,
            title = f'Ticket Created: #{ticket.ticket_id}',
            body  = f'We received your {ticket.category} request.',
            data  = {'type': 'ticket', 'ticket_id': ticket.ticket_id},
        )

    def ticket_replied(self, ticket) -> bool:
        return self.send_to_user(ticket.user,
            title = f'New Reply: #{ticket.ticket_id}',
            body  = 'Support team has replied to your ticket.',
            data  = {'type': 'ticket_reply', 'ticket_id': ticket.ticket_id},
        )

    def ticket_resolved(self, ticket) -> bool:
        return self.send_to_user(ticket.user,
            title = f'Ticket Resolved ✅',
            body  = f'Your issue #{ticket.ticket_id} has been resolved!',
            data  = {'type': 'ticket_resolved', 'ticket_id': ticket.ticket_id},
        )

    def agent_new_ticket(self, ticket, agent) -> bool:
        return self.send_to_user(agent,
            title = f'New Ticket: {ticket.priority.upper()}',
            body  = f'{ticket.subject[:60]}',
            data  = {'type': 'agent_ticket', 'ticket_id': ticket.ticket_id},
        )

    def _send(self, token: str, title: str, body: str, data: dict) -> bool:
        if not FCM_KEY:
            logger.debug('FCM key not configured.')
            return False
        try:
            resp = requests.post(
                FCM_URL,
                headers = {
                    'Authorization': f'key={FCM_KEY}',
                    'Content-Type':  'application/json',
                },
                json = {
                    'to': token,
                    'notification': {'title': title, 'body': body, 'sound': 'default'},
                    'data': data,
                    'priority': 'high',
                },
                timeout=15,
            )
            ok = resp.status_code == 200 and resp.json().get('success', 0) > 0
            if ok:
                logger.info(f'Push sent: {title[:40]}')
            else:
                logger.warning(f'Push failed: {resp.text[:100]}')
            return ok
        except Exception as e:
            logger.error(f'Push notification error: {e}')
            return False

    def _get_fcm_token(self, user) -> str | None:
        try:
            if hasattr(user, 'profile'):
                return getattr(user.profile, 'fcm_token', None)
            return None
        except Exception:
            return None


push_notifier = PushNotifier()