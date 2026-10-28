import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.smartlink.models.publisher import PublisherDomain
from ..choices import DomainVerificationStatus

logger = logging.getLogger('smartlink.signals.domain')


@receiver(post_save, sender=PublisherDomain)
def on_domain_verified(sender, instance, **kwargs):
    """
    When domain is verified:
    1. Cache domain→publisher mapping  (was already wired)
    2. Fire webhook 'domain_verified'  ← FIX: was missing
    3. Notify publisher                ← FIX: was missing
    """
    if instance.verification_status != DomainVerificationStatus.VERIFIED:
        return

    # 1. Cache mapping (was already wired)
    try:
        from django.core.cache import cache
        from ..utils import domain_cache_key
        cache.set(domain_cache_key(instance.domain), instance.publisher_id, 3600)
        logger.info(
            f"Domain verified & cached: {instance.domain} → publisher#{instance.publisher_id}"
        )
    except Exception as e:
        logger.warning(f"Domain signal cache failed: {e}")

    # 2. Webhook dispatch — FIX: was missing
    try:
        from ..tasks.webhook_tasks import deliver_webhook_event
        deliver_webhook_event.delay(
            event='domain_verified',
            publisher_id=instance.publisher_id,
            smartlink_id=None,
            domain=instance.domain,
            verified_at=instance.verified_at.isoformat() if instance.verified_at else None,
        )
    except Exception as e:
        logger.warning(f"Domain signal webhook dispatch failed: {e}")

    # 3. Publisher notification — FIX: was missing
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        publisher = User.objects.get(pk=instance.publisher_id)
        from ..services.notification.NotificationService import NotificationService
        NotificationService()._dispatch(
            publisher,
            f"✅ Your domain <b>{instance.domain}</b> has been verified and is now active.",
            level='info',
        )
    except Exception as e:
        logger.warning(f"Domain signal notification failed: {e}")
