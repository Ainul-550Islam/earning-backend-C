import logging
from django.core.cache import cache
from django.utils import timezone
from ...models import UniqueClick
from ...utils import click_fingerprint
from ...constants import CACHE_TTL_UNIQUE_CLICK, CLICK_DEDUP_WINDOW_HOURS

logger = logging.getLogger('smartlink.dedup')


class ClickDeduplicationService:
    """
    Unique click deduplication by IP + offer + day.
    Redis-first: check cache before hitting DB.
    """

    def is_duplicate(self, ip: str, user_agent: str, offer_id: int, smartlink_id: int) -> bool:
        """
        Returns True if this click is a duplicate (already seen).
        Checks Redis cache first; falls back to DB on cache miss.
        """
        fingerprint = click_fingerprint(ip, user_agent, offer_id)
        cache_key = f"unique_click:{fingerprint}"

        if cache.get(cache_key):
            logger.debug(f"Duplicate click detected (cache): {fingerprint[:16]}...")
            return True

        # DB check
        today = timezone.now().date()
        exists = UniqueClick.objects.filter(
            fingerprint=fingerprint,
            date=today,
        ).exists()

        if exists:
            # Repopulate cache
            cache.set(cache_key, '1', CACHE_TTL_UNIQUE_CLICK)
            logger.debug(f"Duplicate click detected (db): {fingerprint[:16]}...")
            return True

        return False

    def mark_seen(self, ip: str, user_agent: str, offer_id: int, smartlink_id: int, click=None):
        """
        Mark a click as seen (first occurrence).
        Writes to Redis cache and creates UniqueClick DB record.
        """
        from ...models import SmartLink
        fingerprint = click_fingerprint(ip, user_agent, offer_id)
        cache_key = f"unique_click:{fingerprint}"
        today = timezone.now().date()

        # Set cache
        cache.set(cache_key, '1', CACHE_TTL_UNIQUE_CLICK)

        # Create or update DB record
        try:
            unique_click, created = UniqueClick.objects.get_or_create(
                fingerprint=fingerprint,
                date=today,
                defaults={
                    'smartlink_id': smartlink_id,
                    'offer_id': offer_id,
                    'ip': ip,
                    'first_click': click,
                    'click_count': 1,
                }
            )
            if not created:
                from django.db.models import F
                UniqueClick.objects.filter(pk=unique_click.pk).update(
                    click_count=F('click_count') + 1
                )
        except Exception as e:
            logger.warning(f"UniqueClick DB write error: {e}")

    def get_unique_count(self, smartlink_id: int, offer_id: int = None, date=None) -> int:
        """Get unique click count for a SmartLink (optionally filtered by offer and date)."""
        qs = UniqueClick.objects.filter(smartlink_id=smartlink_id)
        if offer_id:
            qs = qs.filter(offer_id=offer_id)
        if date:
            qs = qs.filter(date=date)
        else:
            qs = qs.filter(date=timezone.now().date())
        return qs.count()
