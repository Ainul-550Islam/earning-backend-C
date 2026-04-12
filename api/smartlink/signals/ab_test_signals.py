import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import ABTestResult
from ..choices import ABTestStatus

logger = logging.getLogger('smartlink.signals.ab_test')


@receiver(post_save, sender=ABTestResult)
def on_ab_test_winner_found(sender, instance, **kwargs):
    """When A/B test winner is found: log and optionally auto-apply."""
    if instance.status == ABTestStatus.WINNER_FOUND and instance.winner_version:
        logger.info(
            f"A/B Test Winner: sl=[{instance.smartlink.slug}] "
            f"winner=[{instance.winner_version.name}] "
            f"uplift={instance.uplift_percent:.2f}% "
            f"confidence={instance.confidence_level:.3f}"
        )
