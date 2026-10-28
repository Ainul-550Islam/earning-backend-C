# api/support/integrations/project_specific/messaging_bridge.py
"""
Messaging Bridge — connects support.SupportTicket with messaging.SupportThread.

YOUR messaging app already has SupportThread + SupportMessage models.
This bridge syncs them bidirectionally so agents can work from either app.

Flow:
    SupportTicket created → auto-create SupportThread in messaging
    SupportMessage in messaging → sync to TicketMessage in support
    Agent replies in support → appears in messaging.SupportMessage
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)


class MessagingBridge:
    """Bridge between support tickets and messaging.SupportThread."""

    def sync_ticket_to_thread(self, ticket) -> Optional[object]:
        """
        When support ticket created → create SupportThread in messaging app.
        Agents can then work from messaging dashboard too.
        """
        try:
            from django.apps import apps
            SupportThread = apps.get_model("messaging", "SupportThread")

            # Check if thread already exists for this ticket
            thread_ref = f"ticket:{ticket.ticket_id}"
            existing = SupportThread.objects.filter(
                user=ticket.user,
                subject__startswith=f"[{ticket.ticket_id}]",
            ).first()
            if existing:
                return existing

            thread = SupportThread.objects.create(
                user           = ticket.user,
                subject        = f"[{ticket.ticket_id}] {ticket.subject or ticket.category}",
                status         = "open",
                priority       = ticket.priority or "medium",
            )
            logger.info(f"Messaging thread created for ticket {ticket.ticket_id}")
            return thread
        except Exception as e:
            logger.debug(f"MessagingBridge.sync_ticket_to_thread: {e}")
            return None

    def sync_message_to_thread(self, ticket_message, thread) -> Optional[object]:
        """
        When agent replies in support → also post to messaging.SupportMessage.
        """
        if not thread:
            return None
        try:
            from django.apps import apps
            SupportMessage = apps.get_model("messaging", "SupportMessage")

            msg = SupportMessage.objects.create(
                thread         = thread,
                sender         = ticket_message.sender,
                content        = ticket_message.content,
                is_agent_reply = ticket_message.is_agent,
                is_internal_note = ticket_message.is_internal,
            )
            return msg
        except Exception as e:
            logger.debug(f"MessagingBridge.sync_message_to_thread: {e}")
            return None

    def sync_thread_status(self, ticket, thread) -> bool:
        """Keep messaging SupportThread status in sync with ticket status."""
        if not thread:
            return False
        try:
            STATUS_MAP = {
                "open":         "open",
                "in_progress":  "in_progress",
                "waiting_user": "waiting_user",
                "resolved":     "resolved",
                "closed":       "closed",
            }
            new_status = STATUS_MAP.get(ticket.status, "open")
            if thread.status != new_status:
                thread.status = new_status
                thread.save(update_fields=["status"])
            return True
        except Exception as e:
            logger.debug(f"MessagingBridge.sync_thread_status: {e}")
            return False

    def get_thread_for_ticket(self, ticket) -> Optional[object]:
        """Find existing messaging thread for a ticket."""
        try:
            from django.apps import apps
            SupportThread = apps.get_model("messaging", "SupportThread")
            return SupportThread.objects.filter(
                user=ticket.user,
                subject__startswith=f"[{ticket.ticket_id}]",
            ).first()
        except Exception:
            return None

    def import_thread_messages(self, thread, ticket) -> int:
        """Import all messaging thread messages into support ticket thread."""
        try:
            from django.apps import apps
            SupportMessage = apps.get_model("messaging", "SupportMessage")
            from api.support.models import TicketMessage
            msgs = SupportMessage.objects.filter(thread=thread)
            imported = 0
            for msg in msgs:
                if not TicketMessage.objects.filter(ticket=ticket, content=msg.content).exists():
                    TicketMessage.objects.create(
                        ticket      = ticket,
                        sender      = msg.sender,
                        content     = msg.content,
                        is_agent    = msg.is_agent_reply,
                        is_internal = msg.is_internal_note,
                    )
                    imported += 1
            return imported
        except Exception as e:
            logger.debug(f"MessagingBridge.import_thread_messages: {e}")
            return 0


messaging_bridge = MessagingBridge()