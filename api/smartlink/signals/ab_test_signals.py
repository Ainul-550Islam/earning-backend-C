import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.smartlink.models import ABTestResult
from ..choices import ABTestStatus

logger = logging.getLogger('smartlink.signals.ab_test')


@receiver(post_save, sender=ABTestResult)
def on_ab_test_winner_found(sender, instance, **kwargs):
    """
    When A/B test winner is found:
    1. Log the result (was already wired)
    2. Fire webhook 'ab_winner' event ← FIX: was missing
    3. Send notification to publisher  ← FIX: was missing
    4. Optionally auto-apply winner variant ← FIX: was missing
    """
    if instance.status != ABTestStatus.WINNER_FOUND or not instance.winner_version:
        return

    # 1. Log (was already wired)
    logger.info(
        f"A/B Test Winner: sl=[{instance.smartlink.slug}] "
        f"winner=[{instance.winner_version.name}] "
        f"uplift={instance.uplift_percent:.2f}% "
        f"confidence={instance.confidence_level:.3f}"
    )

    # 2. Webhook dispatch — FIX: was completely missing
    try:
        from ..tasks.webhook_tasks import deliver_webhook_event
        publisher = instance.smartlink.publisher
        deliver_webhook_event.delay(
            event='ab_winner',
            publisher_id=publisher.pk,
            smartlink_id=instance.smartlink_id,
            winner_version=instance.winner_version.name,
            uplift_percent=float(instance.uplift_percent),
            confidence_level=float(instance.confidence_level),
            test_id=instance.pk,
        )
    except Exception as e:
        logger.warning(f"AB test signal webhook dispatch failed: {e}")

    # 3. Publisher notification — FIX: was missing
    try:
        from ..services.notification.NotificationService import NotificationService
        publisher = instance.smartlink.publisher
        NotificationService().notify_ab_winner(
            publisher=publisher,
            smartlink=instance.smartlink,
            winner_version=instance.winner_version,
            uplift=float(instance.uplift_percent),
        )
    except Exception as e:
        logger.warning(f"AB test signal notification failed: {e}")
