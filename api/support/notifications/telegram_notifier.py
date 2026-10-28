"""
api/support/notifications/telegram_notifier.py
FILE 30/70 — Telegram Notification Sender

Telegram Bot API দিয়ে notification পাঠাও।
User + Agent + Admin group notification।
"""
import logging
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram notification wrapper"""

    def _get_bot(self):
        from api.support.integrations.telegram_bot import telegram_bot
        return telegram_bot

    def _get_chat_id(self, user) -> str | None:
        try:
            # Try agent profile first
            if hasattr(user, 'support_agent'):
                return user.support_agent.telegram_chat_id or None
            if hasattr(user, 'profile'):
                return getattr(user.profile, 'telegram_chat_id', None)
            return None
        except Exception:
            return None

    def ticket_created_user(self, ticket) -> bool:
        chat_id = self._get_chat_id(ticket.user)
        if not chat_id:
            return False
        msg = (
            f"✅ *Ticket Created*\n\n"
            f"ID: `{ticket.ticket_id}`\n"
            f"Subject: {ticket.subject[:80]}\n"
            f"Priority: {ticket.priority.upper()}"
        )
        return bool(self._get_bot().send_message(chat_id, msg, parse_mode='Markdown'))

    def ticket_replied_user(self, ticket, reply: str) -> bool:
        chat_id = self._get_chat_id(ticket.user)
        if not chat_id:
            return False
        msg = (
            f"💬 *New Reply: #{ticket.ticket_id}*\n\n"
            f"{reply[:300]}"
        )
        return bool(self._get_bot().send_message(chat_id, msg, parse_mode='Markdown'))

    def ticket_resolved_user(self, ticket) -> bool:
        chat_id = self._get_chat_id(ticket.user)
        if not chat_id:
            return False
        msg = (
            f"✅ *Ticket Resolved!*\n\n"
            f"Ticket #{ticket.ticket_id} has been resolved.\n"
            f"Please rate: 1-5"
        )
        return bool(self._get_bot().send_message(chat_id, msg, parse_mode='Markdown'))

    def new_ticket_admin(self, ticket) -> bool:
        return self._get_bot().notify_admin_new_ticket(ticket)

    def sla_breach_admin(self, ticket, breach_type: str) -> bool:
        return self._get_bot().notify_admin_sla_breach(ticket, breach_type)

    def agent_assigned(self, ticket, agent) -> bool:
        chat_id = self._get_chat_id(agent)
        if not chat_id:
            return False
        return self._get_bot().notify_agent_assigned(ticket, chat_id)

    def send_text(self, chat_id: str, message: str) -> bool:
        return bool(self._get_bot().send_message(chat_id, message))


telegram_notifier = TelegramNotifier()