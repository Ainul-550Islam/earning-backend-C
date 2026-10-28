"""
api/support/notifications/notification_router.py
FILE 34/70 — Smart Notification Router

User-এর preference অনুযায়ী সঠিক channel-এ notification পাঠাও।
একটা event → multiple channels।

Routing Logic:
1. User preference check করো
2. Channel available কিনা check করো
3. Priority অনুযায়ী channel select করো
4. Fallback chain: Telegram → WhatsApp → Email → SMS
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class NotificationRouter:
    """
    Smart notification routing।
    Right message → right channel → right time।
    """

    # Default channel priorities
    DEFAULT_PRIORITY = ['telegram', 'push', 'email', 'whatsapp', 'sms']

    # Event → channels mapping
    EVENT_CHANNELS = {
        'ticket_created':   ['email', 'push', 'telegram'],
        'ticket_replied':   ['push', 'telegram', 'email'],
        'ticket_resolved':  ['email', 'push', 'telegram', 'whatsapp'],
        'ticket_closed':    ['email'],
        'csat_request':     ['email', 'push'],
        'sla_warning':      ['telegram', 'slack', 'email', 'sms'],
        'sla_breach':       ['telegram', 'slack', 'email', 'sms', 'whatsapp'],
        'agent_assigned':   ['telegram', 'push', 'email'],
        'agent_new_ticket': ['telegram', 'push', 'email'],
        'escalation':       ['slack', 'telegram', 'email'],
        'reminder':         ['email', 'push'],
    }

    def route(self, event: str, recipient, context: dict, urgency: str = 'normal') -> dict:
        """
        Event route করো।
        recipient = User object or dict with email/phone/chat_ids
        Returns: {sent_channels: [], failed_channels: []}
        """
        channels     = self._get_channels(event, recipient, urgency)
        sent         = []
        failed       = []

        for channel in channels:
            try:
                success = self._send_via_channel(channel, event, recipient, context)
                if success:
                    sent.append(channel)
                else:
                    failed.append(channel)
            except Exception as e:
                logger.warning(f'Route [{channel}] failed for {event}: {e}')
                failed.append(channel)

        result = {'sent_channels': sent, 'failed_channels': failed, 'event': event}
        self._log_routing(event, recipient, result)
        return result

    def route_ticket_event(self, event: str, ticket, **kwargs) -> dict:
        """Ticket event routing shortcut"""
        context = {
            'ticket_id':  ticket.ticket_id,
            'subject':    ticket.subject,
            'priority':   ticket.priority,
            'category':   ticket.category,
            **kwargs,
        }
        urgency = 'urgent' if ticket.priority in ['urgent', 'high'] else 'normal'
        return self.route(event, ticket.user, context, urgency)

    # ──────────────────────────────────────────
    # CHANNEL SELECTION
    # ──────────────────────────────────────────
    def _get_channels(self, event: str, recipient, urgency: str) -> list:
        """Which channels to use for this event + recipient"""
        # Get user preferences
        prefs = self._get_user_prefs(recipient)

        # Default channels for this event
        default_channels = self.EVENT_CHANNELS.get(event, ['email'])

        # Filter by user preferences
        if prefs:
            enabled = [ch for ch in default_channels if prefs.get(ch, True)]
        else:
            enabled = default_channels

        # Urgency boost — urgent events always use multiple channels
        if urgency == 'urgent' and 'email' not in enabled:
            enabled.append('email')

        return enabled[:3]  # Max 3 channels per notification

    # ──────────────────────────────────────────
    # CHANNEL SENDERS
    # ──────────────────────────────────────────
    def _send_via_channel(self, channel: str, event: str, recipient, context: dict) -> bool:
        if channel == 'email':
            return self._send_email(event, recipient, context)
        elif channel == 'telegram':
            return self._send_telegram(event, recipient, context)
        elif channel == 'whatsapp':
            return self._send_whatsapp(event, recipient, context)
        elif channel == 'sms':
            return self._send_sms(event, recipient, context)
        elif channel == 'push':
            return self._send_push(event, recipient, context)
        elif channel == 'slack':
            return self._send_slack(event, context)
        return False

    def _send_email(self, event: str, recipient, context: dict) -> bool:
        try:
            from api.support.notifications.email_notifier import email_notifier
            email = getattr(recipient, 'email', None) or context.get('email')
            if not email:
                return False
            subject = context.get('subject', f'Support Notification: {event}')
            body    = context.get('body', str(context))
            return email_notifier._send(email, subject, body)
        except Exception:
            return False

    def _send_telegram(self, event: str, recipient, context: dict) -> bool:
        try:
            from api.support.notifications.telegram_notifier import telegram_notifier
            chat_id = None
            if hasattr(recipient, 'support_agent'):
                chat_id = recipient.support_agent.telegram_chat_id
            elif hasattr(recipient, 'profile'):
                chat_id = getattr(recipient.profile, 'telegram_chat_id', None)
            if not chat_id:
                return False
            msg = context.get('telegram_msg') or self._format_telegram(event, context)
            return telegram_notifier.send_text(chat_id, msg)
        except Exception:
            return False

    def _send_whatsapp(self, event: str, recipient, context: dict) -> bool:
        try:
            from api.support.notifications.whatsapp_notifier import whatsapp_notifier
            phone = None
            if hasattr(recipient, 'profile'):
                phone = getattr(recipient.profile, 'phone_number', None)
            if not phone:
                return False
            msg = context.get('wa_msg') or self._format_whatsapp(event, context)
            return whatsapp_notifier.send_text(phone, msg)
        except Exception:
            return False

    def _send_sms(self, event: str, recipient, context: dict) -> bool:
        try:
            from api.support.notifications.sms_notifier import sms_notifier
            phone = sms_notifier.get_user_phone(recipient)
            if not phone:
                return False
            msg = context.get('sms_msg') or self._format_sms(event, context)
            return sms_notifier.send(phone, msg)
        except Exception:
            return False

    def _send_push(self, event: str, recipient, context: dict) -> bool:
        try:
            from api.support.notifications.push_notifier import push_notifier
            title = context.get('push_title', f'Support: {event}')
            body  = context.get('push_body', context.get('message', ''))
            return push_notifier.send_to_user(recipient, title, body, context)
        except Exception:
            return False

    def _send_slack(self, event: str, context: dict) -> bool:
        try:
            from api.support.integrations.slack_integration import slack_integration
            msg = context.get('slack_msg') or str(context)
            return slack_integration._send_webhook({'text': msg})
        except Exception:
            return False

    # ──────────────────────────────────────────
    # MESSAGE FORMATTERS
    # ──────────────────────────────────────────
    def _format_telegram(self, event: str, context: dict) -> str:
        tid = context.get('ticket_id', '')
        msg = context.get('message', event)
        return f'🔔 *Support Notification*\n\nTicket: `{tid}`\n{msg}'

    def _format_whatsapp(self, event: str, context: dict) -> str:
        tid = context.get('ticket_id', '')
        msg = context.get('message', event)
        return f'Support Update - Ticket {tid}: {msg}'

    def _format_sms(self, event: str, context: dict) -> str:
        tid = context.get('ticket_id', '')
        msg = context.get('message', event)
        return f'Support #{tid}: {msg}'[:160]

    # ──────────────────────────────────────────
    # USER PREFERENCES
    # ──────────────────────────────────────────
    def _get_user_prefs(self, user) -> dict | None:
        if not hasattr(user, 'id'):
            return None
        key    = f'notif_prefs:{user.id}'
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            from api.support.notifications.notification_prefs import prefs_manager
            prefs = prefs_manager.get_prefs(user)
            cache.set(key, prefs, timeout=3600)
            return prefs
        except Exception:
            return None

    def _log_routing(self, event: str, recipient, result: dict) -> None:
        logger.info(
            f'Notification routed: {event} → '
            f'sent={result["sent_channels"]}, failed={result["failed_channels"]}'
        )


notification_router = NotificationRouter()