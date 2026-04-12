# api/offer_inventory/offer_search/trending_offers.py
"""Trending Offers — Real-time trending offer detection."""
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TrendingOffersEngine:
    """Detect and serve trending offers based on recent activity."""

    @staticmethod
    def get_trending(limit: int = 10, hours: int = 24, tenant=None) -> list:
        """Get offers with highest recent click/conversion velocity."""
        cache_key = f'trending_offers:{tenant}:{hours}'
        cached    = cache.get(cache_key)
        if cached:
            return cached[:limit]

        from api.offer_inventory.models import Click, Offer
        from django.db.models import Count, Q

        since = timezone.now() - timedelta(hours=hours)
        trending_ids = list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('offer_id')
            .annotate(clicks=Count('id'))
            .order_by('-clicks')
            .values_list('offer_id', flat=True)
            [:limit * 2]
        )

        if not trending_ids:
            # Fallback to featured offers
            offers = list(Offer.objects.filter(status='active', is_featured=True)[:limit])
        else:
            # Preserve trending order
            offers_map = {
                str(o.id): o for o in
                Offer.objects.filter(id__in=trending_ids, status='active')
            }
            offers = [offers_map[str(tid)] for tid in trending_ids if str(tid) in offers_map]

        result = [
            {
                'id'           : str(o.id),
                'title'        : o.title,
                'reward_amount': str(o.reward_amount),
                'category'     : o.category.name if o.category else '',
                'is_featured'  : o.is_featured,
                'image_url'    : o.image_url or '',
                'trending'     : True,
            }
            for o in offers[:limit]
        ]
        cache.set(cache_key, result, 300)
        return result

    @staticmethod
    def get_new_offers(limit: int = 10, days: int = 7, tenant=None) -> list:
        """Get recently added offers."""
        from api.offer_inventory.models import Offer
        since = timezone.now() - timedelta(days=days)
        qs    = Offer.objects.filter(status='active', created_at__gte=since).order_by('-created_at')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return [
            {'id': str(o.id), 'title': o.title, 'reward_amount': str(o.reward_amount), 'new': True}
            for o in qs[:limit]
        ]

    @staticmethod
    def get_highest_paying(limit: int = 10, tenant=None) -> list:
        """Get highest reward amount offers."""
        from api.offer_inventory.models import Offer
        qs = Offer.objects.filter(status='active').order_by('-reward_amount')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return [
            {'id': str(o.id), 'title': o.title, 'reward_amount': str(o.reward_amount)}
            for o in qs[:limit]
        ]
