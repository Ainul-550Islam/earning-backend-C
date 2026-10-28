# api/support/ai_service.py  — WORLD #1 COMPLETE
"""
AI service helpers — bridge to ai/ module.
"""
import logging
logger = logging.getLogger(__name__)


def classify_ticket_async(ticket_id: int) -> None:
    """Async AI classify — called from ticket_service.create()"""
    try:
        # Try Celery
        from api.support.tasks import ai_classify_ticket
        ai_classify_ticket.delay(ticket_id)
    except Exception:
        # Sync fallback
        try:
            from api.support.models import SupportTicket
            from api.support.ai.ai_ticket_classifier import ai_classifier
            ticket = SupportTicket.objects.get(id=ticket_id)
            result = ai_classifier.classify(ticket)
            logger.info(f'AI classified ticket {ticket.ticket_id}: {result}')
        except Exception as e:
            logger.debug(f'AI classify failed (non-critical): {e}')