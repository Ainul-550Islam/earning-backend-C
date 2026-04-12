import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import ClickFraudFlag

logger = logging.getLogger('smartlink.signals.fraud')


@receiver(post_save, sender=ClickFraudFlag)
def on_fraud_flag_created(sender, instance, created, **kwargs):
    """When a fraud flag is created: auto-block the IP if score is critical."""
    if created and instance.score >= 85:
        try:
            from django.core.cache import cache
            ip = instance.click.ip
            cache.set(f"fraud:blocked:{ip}", '1', 3600 * 24)
            logger.warning(f"IP auto-blocked via fraud signal: {ip} score={instance.score}")
        except Exception as e:
            logger.error(f"Fraud signal auto-block failed: {e}")
