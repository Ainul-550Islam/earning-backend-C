# api/support/singals_cap.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.OfferDispute')
def on_offer_dispute_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from api.support.tasks_cap import verify_offer_dispute
        verify_offer_dispute.apply_async(args=[instance.id], countdown=5)
    except Exception as e:
        logger.debug(f'Dispute verification queue: {e}')


@receiver(post_save, sender='support.OfferDispute')
def on_offer_dispute_resolved(sender, instance, created, **kwargs):
    if created or instance.status != 'approved':
        return
    try:
        from api.support.integrations.project_specific.audit_log_bridge import audit_bridge
        audit_bridge.log_dispute_approved(instance, instance.expected_amount)
    except Exception:
        pass
    try:
        from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
        if instance.ticket:
            gamification_bridge.award_resolution_points(instance.ticket)
    except Exception:
        pass


@receiver(post_save, sender='support.TicketRating')
def on_ticket_rated(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
        from api.support.integrations.project_specific.behavior_tracker import behavior_tracker
        ticket = instance.ticket
        gamification_bridge.award_rating_points(ticket, instance.score)
        behavior_tracker.track_csat_rating(ticket, instance.score)
        if ticket.assigned_to and instance.score == 5:
            gamification_bridge.reward_agent_high_csat(ticket.assigned_to, ticket, instance.score)
    except Exception as e:
        logger.debug(f'Rating signals: {e}')