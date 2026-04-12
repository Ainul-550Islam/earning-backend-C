import logging
from django.conf import settings
from ...models import SmartLink, SmartLinkFallback
from ...constants import DEFAULT_FALLBACK_URL

logger = logging.getLogger('smartlink.fallback')


class FallbackService:
    """
    Determine fallback URL when no offer matches targeting rules
    or all offers in the pool are capped/unavailable.
    """

    def get_url(self, smartlink: SmartLink) -> str:
        """
        Return fallback URL for a SmartLink.
        Priority: SmartLink-specific fallback → publisher default → global default.
        """
        # 1. SmartLink-specific fallback
        try:
            fallback = smartlink.fallback
            if fallback.is_active and fallback.url:
                logger.debug(f"[{smartlink.slug}] Using SmartLink fallback: {fallback.url[:60]}")
                return fallback.url
        except SmartLinkFallback.DoesNotExist:
            pass

        # 2. Publisher default fallback
        try:
            publisher = smartlink.publisher
            publisher_fallback = getattr(publisher, 'profile', None)
            if publisher_fallback and hasattr(publisher_fallback, 'default_fallback_url'):
                url = publisher_fallback.default_fallback_url
                if url:
                    logger.debug(f"[{smartlink.slug}] Using publisher fallback: {url[:60]}")
                    return url
        except Exception:
            pass

        # 3. Global platform default
        default = getattr(settings, 'SMARTLINK_DEFAULT_FALLBACK_URL', DEFAULT_FALLBACK_URL)
        logger.debug(f"[{smartlink.slug}] Using global fallback: {default}")
        return default

    def set_fallback(self, smartlink: SmartLink, url: str) -> SmartLinkFallback:
        """Set or update the fallback URL for a SmartLink."""
        from ...validators import validate_redirect_url
        validate_redirect_url(url)
        fallback, created = SmartLinkFallback.objects.update_or_create(
            smartlink=smartlink,
            defaults={'url': url, 'is_active': True},
        )
        action = 'created' if created else 'updated'
        logger.info(f"Fallback {action} for [{smartlink.slug}]: {url[:60]}")
        return fallback

    def disable_fallback(self, smartlink: SmartLink):
        """Disable the fallback for a SmartLink (traffic will get NoOfferAvailable error)."""
        SmartLinkFallback.objects.filter(smartlink=smartlink).update(is_active=False)
        logger.info(f"Fallback disabled for [{smartlink.slug}]")
