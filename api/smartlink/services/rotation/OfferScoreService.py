import math
import logging
from django.core.cache import cache
from ...models import OfferScoreCache
from ...constants import CACHE_TTL_EPC_SCORE, EPC_MIN_CLICKS_FOR_SCORE

logger = logging.getLogger('smartlink.offer_score')


class OfferScoreService:
    """
    Score offers by geo + device EPC for use in EPC-optimized rotation.
    Provides methods for reading, writing, and expiring score caches.
    """

    def get_score(self, offer_id: int, country: str, device_type: str) -> float:
        """Get computed score for an offer/geo/device combo."""
        cache_key = f"offer_score:{offer_id}:{country}:{device_type}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached.get('score', 0.0)

        try:
            obj = OfferScoreCache.objects.get(
                offer_id=offer_id, country=country, device_type=device_type
            )
            data = {
                'score': obj.score,
                'epc': float(obj.epc),
                'clicks': obj.total_clicks,
            }
            cache.set(cache_key, data, CACHE_TTL_EPC_SCORE)
            return obj.score
        except OfferScoreCache.DoesNotExist:
            return 0.0

    def get_top_offers(self, country: str, device_type: str, limit: int = 10) -> list:
        """
        Get top N offers by score for a specific geo/device.
        Used to pre-filter pools for high-traffic routes.
        """
        return list(
            OfferScoreCache.objects.filter(
                country=country,
                device_type=device_type,
                total_clicks__gte=EPC_MIN_CLICKS_FOR_SCORE,
            )
            .order_by('-score')
            .values('offer_id', 'score', 'epc', 'conversion_rate', 'total_clicks')[:limit]
        )

    def update_score(self, offer_id: int, country: str, device_type: str,
                     clicks: int, conversions: int, revenue: float):
        """
        Update or create score cache for an offer/geo/device combo.
        Called by EPCOptimizer.recalculate_scores().
        """
        epc = round(revenue / clicks, 4) if clicks > 0 else 0.0
        cr = round(conversions / clicks, 4) if clicks > 0 else 0.0
        score = epc * math.sqrt(max(clicks, 1))

        OfferScoreCache.objects.update_or_create(
            offer_id=offer_id,
            country=country,
            device_type=device_type,
            defaults={
                'epc': epc,
                'conversion_rate': cr,
                'total_clicks': clicks,
                'total_conversions': conversions,
                'score': score,
            }
        )

        # Bust cache
        cache_key = f"offer_score:{offer_id}:{country}:{device_type}"
        cache.delete(cache_key)

    def invalidate_offer(self, offer_id: int):
        """Invalidate all cached scores for an offer (e.g., on offer update)."""
        # Pattern delete — Redis SCAN-based
        try:
            from django_redis import get_redis_connection
            con = get_redis_connection('default')
            pattern = f"*offer_score:{offer_id}:*"
            keys = con.keys(pattern)
            if keys:
                con.delete(*keys)
        except Exception as e:
            logger.warning(f"Could not pattern-delete offer score cache for offer#{offer_id}: {e}")

    def get_summary(self, offer_id: int) -> list:
        """Get all geo/device scores for a single offer (for admin view)."""
        return list(
            OfferScoreCache.objects.filter(offer_id=offer_id)
            .order_by('-score')
            .values('country', 'device_type', 'score', 'epc', 'conversion_rate',
                    'total_clicks', 'total_conversions', 'calculated_at')
        )
