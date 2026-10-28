# api/support/signals_dispute.py
"""Dispute-specific Django signals."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.OfferDispute')
def on_offer_dispute_analytics(sender, instance, created, **kwargs):
    """Track dispute events in analytics."""
    if not created and instance.status not in ('approved', 'rejected'):
        return
    try:
        from api.support.analytics import support_analytics
        if created:
            support_analytics.track_dispute_submitted(instance)
        elif instance.status == 'approved':
            support_analytics.track_dispute_approved(instance)
        elif instance.status == 'rejected':
            support_analytics.track_dispute_rejected(instance)
    except Exception as e:
        logger.debug(f'on_offer_dispute_analytics: {e}')


@receiver(post_save, sender='support.OfferDispute')
def on_dispute_approved_push(sender, instance, created, **kwargs):
    """Send push notification when dispute approved."""
    if created or instance.status != 'approved':
        return
    try:
        from api.support.notifications_push import push_notifications
        push_notifications.push_dispute_approved(instance, instance.expected_amount)
    except Exception as e:
        logger.debug(f'on_dispute_approved_push: {e}')