import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.smartlink.models import ClickFraudFlag

logger = logging.getLogger('smartlink.signals.fraud')


@receiver(post_save, sender=ClickFraudFlag)
def on_fraud_flag_created(sender, instance, created, **kwargs):
    """
    When a fraud flag is created:
    1. Auto-block IP in Redis if score is critical (was already wired)
    2. Fire webhook 'fraud_spike' event ← FIX: was missing
    3. Trigger notification if fraud rate threshold exceeded ← FIX: was missing
    """
    if not created:
        return

    # 1. IP auto-block (was already wired)
    if instance.score >= 85:
        try:
            from django.core.cache import cache
            ip = instance.click.ip
            cache.set(f"fraud:blocked:{ip}", '1', 3600 * 24)
            logger.warning(
                f"IP auto-blocked via fraud signal: {ip} score={instance.score}"
            )
        except Exception as e:
            logger.error(f"Fraud signal auto-block failed: {e}")

    # 2. Webhook dispatch — FIX: was completely missing
    try:
        from ..tasks.webhook_tasks import deliver_webhook_event
        publisher = instance.click.smartlink.publisher
        deliver_webhook_event.delay(
            event='fraud_spike',
            publisher_id=publisher.pk,
            smartlink_id=instance.click.smartlink_id,
            click_id=instance.click_id,
            fraud_score=instance.score,
            fraud_reasons=instance.reasons if hasattr(instance, 'reasons') else [],
            ip=instance.click.ip,
        )
    except Exception as e:
        logger.warning(f"Fraud signal webhook dispatch failed: {e}")

    # 3. In-app notification for critical fraud — FIX: was missing
    if instance.score >= 90:
        try:
            from ..services.notification.NotificationService import NotificationService
            publisher = instance.click.smartlink.publisher
            sl = instance.click.smartlink
            NotificationService().notify_fraud_spike(
                publisher=publisher,
                smartlink=sl,
                fraud_rate=instance.score / 100,
            )
        except Exception as e:
            logger.warning(f"Fraud signal notification failed: {e}")
