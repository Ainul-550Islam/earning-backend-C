# api/support/background_jobs.py
"""
Background job management for support system.
Wraps Celery tasks with retry logic, priority, and error handling.
"""
import logging

logger = logging.getLogger(__name__)

CELERY_AVAILABLE = False
try:
    from celery import current_app
    CELERY_AVAILABLE = True
except ImportError:
    pass


def queue_dispute_verification(dispute_id: int, delay: int = 5) -> bool:
    """Queue offer dispute for background verification."""
    if not CELERY_AVAILABLE:
        # Sync fallback
        try:
            from api.support.models import OfferDispute
            from api.support.interactors import dispute_verification_interactor
            dispute = OfferDispute.objects.get(id=dispute_id)
            dispute_verification_interactor.run(dispute, dispute.ticket)
            return True
        except Exception as e:
            logger.error(f'queue_dispute_verification sync: {e}')
            return False
    try:
        from api.support.tasks_cap import verify_offer_dispute
        verify_offer_dispute.apply_async(args=[dispute_id], countdown=delay)
        logger.info(f'Dispute {dispute_id} queued for verification')
        return True
    except Exception as e:
        logger.error(f'queue_dispute_verification: {e}')
        return False


def queue_sla_check(countdown: int = 0) -> bool:
    """Queue SLA breach check."""
    if not CELERY_AVAILABLE:
        try:
            from api.support.interactors import sla_enforcement_interactor
            sla_enforcement_interactor.run_checks()
            return True
        except Exception as e:
            logger.error(f'queue_sla_check sync: {e}')
            return False
    try:
        from api.support.tasks import check_sla_breaches
        check_sla_breaches.apply_async(countdown=countdown)
        return True
    except Exception as e:
        logger.error(f'queue_sla_check: {e}')
        return False


def queue_csat_survey(ticket_id: int, delay_hours: int = 24) -> bool:
    """Queue CSAT survey email after ticket resolution."""
    if not CELERY_AVAILABLE:
        return False
    try:
        from api.support.tasks import send_csat_request
        send_csat_request.apply_async(args=[ticket_id], countdown=delay_hours * 3600)
        return True
    except Exception as e:
        logger.error(f'queue_csat_survey: {e}')
        return False


def queue_kb_suggestion(ticket_id: int) -> bool:
    """Queue KB article suggestion for a new ticket."""
    if not CELERY_AVAILABLE:
        return False
    try:
        from api.support.tasks import suggest_kb_for_new_tickets
        suggest_kb_for_new_tickets.apply_async(countdown=60)
        return True
    except Exception as e:
        logger.debug(f'queue_kb_suggestion: {e}')
        return False


def queue_auto_assign(ticket_id: int) -> bool:
    """Queue ticket auto-assignment job."""
    if not CELERY_AVAILABLE:
        try:
            from api.support.interactors import ticket_routing_interactor
            from api.support.models import SupportTicket
            ticket = SupportTicket.objects.get(id=ticket_id)
            ticket_routing_interactor.route(ticket)
            return True
        except Exception as e:
            logger.debug(f'queue_auto_assign sync: {e}')
            return False
    try:
        from api.support.tasks import assign_unassigned_tickets
        assign_unassigned_tickets.apply_async(countdown=30)
        return True
    except Exception as e:
        logger.debug(f'queue_auto_assign: {e}')
        return False


def queue_daily_digest() -> bool:
    """Queue daily digest email."""
    if not CELERY_AVAILABLE:
        return False
    try:
        from api.support.tasks import send_daily_digest
        send_daily_digest.apply_async()
        return True
    except Exception as e:
        logger.error(f'queue_daily_digest: {e}')
        return False


def queue_fraud_pattern_check() -> bool:
    """Queue fraud dispute pattern analysis."""
    if not CELERY_AVAILABLE:
        return False
    try:
        from api.support.tasks_cap import flag_suspicious_dispute_patterns
        flag_suspicious_dispute_patterns.apply_async()
        return True
    except Exception as e:
        logger.debug(f'queue_fraud_pattern_check: {e}')
        return False