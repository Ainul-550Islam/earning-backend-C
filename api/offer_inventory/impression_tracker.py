# api/offer_inventory/impression_tracker.py
"""
Impression Tracker.
Records every time an offer is shown to a user.
Calculates CTR (Click-through Rate) and viewability metrics.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

IMPRESSION_CACHE_TTL = 60   # 1 min dedup window


class ImpressionTracker:
    """Records offer impressions with deduplication."""

    @staticmethod
    def record(offer, user=None, ip: str = '', country: str = '',
               device: str = 'desktop', is_viewable: bool = True):
        """
        Record an offer impression.
        Deduplicated per user+offer per minute.
        """
        from api.offer_inventory.models import Impression

        # Dedup: same user+offer within 1 min = skip
        dedup_key = f'imp_dedup:{user.id if user else ip}:{offer.id}'
        if cache.get(dedup_key):
            return None

        try:
            impression = Impression.objects.create(
                offer      =offer,
                user       =user,
                ip_address =ip or '0.0.0.0',
                country    =country,
                device     =device,
                is_viewable=is_viewable,
            )
            cache.set(dedup_key, '1', IMPRESSION_CACHE_TTL)
            return impression
        except Exception as e:
            logger.error(f'Impression record error: {e}')
            return None

    @staticmethod
    def record_bulk(offer_ids: list, user=None, ip: str = '',
                     country: str = '', device: str = 'desktop'):
        """Record impressions for multiple offers at once (offer list view)."""
        from api.offer_inventory.models import Offer, Impression

        offers = Offer.objects.filter(id__in=offer_ids, status='active')
        created = []
        for offer in offers:
            imp = ImpressionTracker.record(offer, user, ip, country, device)
            if imp:
                created.append(imp)
        return created

    @staticmethod
    def get_ctr(offer_id: str, days: int = 7) -> float:
        """
        Click-through Rate = Clicks / Impressions × 100.
        """
        from api.offer_inventory.models import Click, Impression
        from django.db.models import Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        imps  = Impression.objects.filter(offer_id=offer_id, created_at__gte=since).count()
        clicks = Click.objects.filter(offer_id=offer_id, created_at__gte=since, is_fraud=False).count()
        if imps == 0:
            return 0.0
        return round(clicks / imps * 100, 2)

    @staticmethod
    def get_top_by_impressions(days: int = 7, limit: int = 10) -> list:
        """Offers with highest impression count."""
        from api.offer_inventory.models import Impression
        from django.db.models import Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return list(
            Impression.objects.filter(created_at__gte=since)
            .values('offer__title', 'offer_id')
            .annotate(impressions=Count('id'))
            .order_by('-impressions')[:limit]
        )

    @staticmethod
    def get_viewability_rate(offer_id: str) -> float:
        """Percentage of impressions that were viewable."""
        from api.offer_inventory.models import Impression
        from django.db.models import Count, Q

        qs    = Impression.objects.filter(offer_id=offer_id)
        total = qs.count()
        if total == 0:
            return 0.0
        viewed = qs.filter(is_viewable=True).count()
        return round(viewed / total * 100, 2)
