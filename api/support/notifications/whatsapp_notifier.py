"""
api/support/notifications/whatsapp_notifier.py
FILE 29/70 — WhatsApp Notification Sender

WhatsApp Business API দিয়ে notification পাঠাও।
Integration layer — whatsapp_integration.py ব্যবহার করে।
"""
import logging
logger = logging.getLogger(__name__)


class WhatsAppNotifier:
    """WhatsApp notification wrapper"""

    def _get_wa_api(self):
        from api.support.integrations.whatsapp_integration import whatsapp_api
        return whatsapp_api

    def _get_phone(self, user) -> str | None:
        try:
            if hasattr(user, 'profile'):
                return getattr(user.profile, 'whatsapp_number', None) or \
                       getattr(user.profile, 'phone_number', None)
            return None
        except Exception:
            return None

    def ticket_created(self, ticket) -> bool:
        phone = self._get_phone(ticket.user)
        if not phone:
            return False
        return self._get_wa_api().send_ticket_confirmation(phone, ticket)

    def ticket_replied(self, ticket, reply: str) -> bool:
        phone = self._get_phone(ticket.user)
        if not phone:
            return False
        return self._get_wa_api().send_ticket_reply(phone, ticket, reply)

    def ticket_resolved(self, ticket) -> bool:
        phone = self._get_phone(ticket.user)
        if not phone:
            return False
        return self._get_wa_api().send_ticket_resolved(phone, ticket)

    def sla_breach_agent(self, ticket, agent) -> bool:
        phone = self._get_phone(agent)
        if not phone:
            return False
        return self._get_wa_api().send_sla_breach_alert(phone, ticket, 'SLA Breached')

    def send_text(self, phone: str, message: str) -> bool:
        return self._get_wa_api().send_text(phone, message)


whatsapp_notifier = WhatsAppNotifier()