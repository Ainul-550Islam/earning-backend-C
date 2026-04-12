import logging
from django.core.cache import cache
from ...models import OfferScoreCache, OfferPoolEntry
from ...constants import EPC_MIN_CLICKS_FOR_SCORE, EPC_SMOOTHING_FACTOR, CACHE_TTL_EPC_SCORE

logger = logging.getLogger('smartlink.epc_optimizer')


class EPCOptimizer:
    """
    EPC-based offer selection optimizer.
    Automatically shifts traffic weight toward higher-EPC offers
    based on historical performance data per geo + device.
    """

    def select(self, entries: list, country: str, device_type: str):
        """
        Select the best offer entry based on EPC score for geo/device.
        Uses probabilistic selection: higher EPC = higher probability,
        but lower-EPC offers still get some traffic (exploration).

        Returns None if not enough data to optimize (caller uses fallback).
        """
        if not entries:
            return None

        scored = self._score_entries(entries, country, device_type)
        if not scored:
            return None

        # Check if we have enough data (at least one offer with min clicks)
        has_data = any(s['clicks'] >= EPC_MIN_CLICKS_FOR_SCORE for s in scored)
        if not has_data:
            logger.debug(
                f"EPC optimizer: insufficient data for {country}/{device_type}, "
                f"falling back to weighted random"
            )
            return None

        # Softmax-style weighted selection by EPC score
        total_score = sum(max(s['score'], 0.001) for s in scored)
        import random
        rand = random.uniform(0, total_score)
        cumulative = 0
        for s in scored:
            cumulative += max(s['score'], 0.001)
            if rand <= cumulative:
                logger.debug(
                    f"EPC optimizer selected offer#{s['entry'].offer_id} "
                    f"score={s['score']:.4f} for {country}/{device_type}"
                )
                return s['entry']

        return scored[-1]['entry']

    def _score_entries(self, entries: list, country: str, device_type: str) -> list:
        """Get EPC scores for all entries for given geo/device."""
        scored = []
        for entry in entries:
            score_data = self._get_score(entry.offer_id, country, device_type)
            # Use epc_override if set by admin
            if entry.epc_override is not None:
                score = float(entry.epc_override)
                clicks = EPC_MIN_CLICKS_FOR_SCORE  # treat as sufficient data
            else:
                score = score_data.get('score', 0.0)
                clicks = score_data.get('clicks', 0)

            scored.append({
                'entry': entry,
                'score': score,
                'clicks': clicks,
                'epc': score_data.get('epc', 0),
            })

        # Sort by score descending for logging
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored

    def _get_score(self, offer_id: int, country: str, device_type: str) -> dict:
        """
        Get cached EPC score for offer/country/device combo.
        Falls back to DB if cache miss.
        """
        cache_key = f"offer_score:{offer_id}:{country}:{device_type}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            obj = OfferScoreCache.objects.get(
                offer_id=offer_id,
                country=country,
                device_type=device_type,
            )
            data = {
                'score': obj.score,
                'epc': float(obj.epc),
                'clicks': obj.total_clicks,
                'cr': float(obj.conversion_rate),
            }
            cache.set(cache_key, data, CACHE_TTL_EPC_SCORE)
            return data
        except OfferScoreCache.DoesNotExist:
            return {'score': 0.0, 'epc': 0.0, 'clicks': 0, 'cr': 0.0}

    def recalculate_scores(self, smartlink_id: int = None):
        """
        Recalculate EPC scores for all offer/geo/device combos.
        Called by epc_update_tasks.py every 30 minutes.
        """
        from ...models import OfferPerformanceStat
        from django.db.models import Sum, Count, F
        from django.utils import timezone
        import datetime

        # Look at last 7 days of data
        cutoff = timezone.now().date() - datetime.timedelta(days=7)

        qs = OfferPerformanceStat.objects.filter(date__gte=cutoff)
        if smartlink_id:
            qs = qs.filter(smartlink_id=smartlink_id)

        # Aggregate by offer/country/device
        aggregated = qs.values('offer_id', 'country', 'device_type').annotate(
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_revenue=Sum('revenue'),
        )

        updated = 0
        for row in aggregated:
            clicks = row['total_clicks'] or 0
            conversions = row['total_conversions'] or 0
            revenue = float(row['total_revenue'] or 0)

            epc = round(revenue / clicks, 4) if clicks > 0 else 0.0
            cr = round(conversions / clicks, 4) if clicks > 0 else 0.0

            # Score = EPC × sqrt(clicks) — balances performance + confidence
            import math
            score = epc * math.sqrt(max(clicks, 1))

            OfferScoreCache.objects.update_or_create(
                offer_id=row['offer_id'],
                country=row['country'],
                device_type=row['device_type'],
                defaults={
                    'epc': epc,
                    'conversion_rate': cr,
                    'total_clicks': clicks,
                    'total_conversions': conversions,
                    'score': score,
                }
            )

            # Invalidate cache so new score is fetched
            cache_key = f"offer_score:{row['offer_id']}:{row['country']}:{row['device_type']}"
            cache.delete(cache_key)
            updated += 1

        logger.info(f"EPC scores recalculated: {updated} offer/geo/device combos updated.")
        return updated
