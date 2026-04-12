import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models.publisher import PublisherDomain
from ..choices import DomainVerificationStatus

logger = logging.getLogger('smartlink.signals.domain')


@receiver(post_save, sender=PublisherDomain)
def on_domain_verified(sender, instance, **kwargs):
    """When domain is verified: cache the domain→publisher mapping."""
    if instance.verification_status == DomainVerificationStatus.VERIFIED:
        try:
            from django.core.cache import cache
            from ..utils import domain_cache_key
            cache.set(domain_cache_key(instance.domain), instance.publisher_id, 3600)
            logger.info(f"Domain verified & cached: {instance.domain} → publisher#{instance.publisher_id}")
        except Exception as e:
            logger.warning(f"Domain signal cache failed: {e}")
