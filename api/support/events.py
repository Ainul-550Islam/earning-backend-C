# api/support/events.py
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

TICKET_CREATED   = 'ticket.created'
TICKET_UPDATED   = 'ticket.updated'
TICKET_RESOLVED  = 'ticket.resolved'
TICKET_CLOSED    = 'ticket.closed'
TICKET_ESCALATED = 'ticket.escalated'
TICKET_REPLIED   = 'ticket.replied'
TICKET_RATED     = 'ticket.rated'
SLA_WARNING      = 'sla.warning'
SLA_BREACH       = 'sla.breach'
DISPUTE_CREATED  = 'dispute.created'
DISPUTE_APPROVED = 'dispute.approved'
DISPUTE_REJECTED = 'dispute.rejected'
CHAT_STARTED     = 'chat.started'
CHAT_ENDED       = 'chat.ended'


def dispatch(event_type: str, **data) -> None:
    try:
        from api.support.integrations.event_bus import event_bus
        event_bus.publish(event_type, **data)
    except Exception as e:
        logger.debug(f'Event dispatch [{event_type}]: {e}')


def dispatch_ticket(event_type: str, ticket) -> None:
    dispatch(event_type, ticket=ticket, user=ticket.user)


def dispatch_dispute(event_type: str, dispute, ticket=None) -> None:
    dispatch(event_type, dispute=dispute, ticket=ticket)