import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import Click

logger = logging.getLogger('smartlink.signals.click')


@receiver(post_save, sender=Click)
def on_click_recorded(sender, instance, created, **kwargs):
    """On new click: update SmartLink last_click_at timestamp."""
    if created:
        try:
            from django.utils import timezone
            from ..models import SmartLink
            SmartLink.objects.filter(pk=instance.smartlink_id).update(
                last_click_at=timezone.now()
            )
        except Exception as e:
            logger.warning(f"Click signal failed for click#{instance.pk}: {e}")
