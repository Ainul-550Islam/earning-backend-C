# api/admin_panel/offer_matching.py
"""SmartLink offer matching engine — match users to best offers."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class OfferMatcher:
    """Match users to highest-converting offers for SmartLink."""

    @classmethod
    def get_best_offers(cls, user_id: Any, country: str = '', platform: str = '',
                         limit: int = 5, exclude_ids: List[Any] = None) -> List[Dict]:
        """Get best offers for a user based on GEO, platform, history."""
        cache_key = f'offer_match:{user_id}:{country}:{platform}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.offer_inventory.models import Offer
            from django.db.models import Q, F
            qs = Offer.objects.filter(is_active=True)

            # GEO filter
            if country:
                qs = qs.filter(Q(countries__contains=country) | Q(countries=''))

            # Platform filter
            if platform:
                qs = qs.filter(Q(platforms__contains=platform) | Q(platforms=''))

            # Exclude already completed
            if exclude_ids:
                qs = qs.exclude(pk__in=exclude_ids)

            # Sort by payout * conversion_rate (EPC)
            offers = list(qs.values(
                'id', 'title', 'offer_type', 'payout', 'total_conversions',
                'countries', 'platforms'
            ).order_by('-payout', '-total_conversions')[:limit])

            cache.set(cache_key, offers, 60)
            return offers
        except Exception as e:
            logger.error(f"[OfferMatcher] {e}")
            return []

    @classmethod
    def get_smartlink_redirect_url(cls, smartlink_id: Any, user_id: Any,
                                    country: str, platform: str) -> Optional[str]:
        """Get best offer URL for SmartLink redirect."""
        offers = cls.get_best_offers(user_id, country, platform, limit=1)
        if not offers:
            return None
        offer = offers[0]
        try:
            from api.offer_inventory.models import Offer
            offer_obj = Offer.objects.get(pk=offer['id'])
            return getattr(offer_obj, 'offer_url', '') or getattr(offer_obj, 'redirect_url', '')
        except Exception:
            return None

    @classmethod
    def update_offer_stats(cls, offer_id: Any, event: str) -> None:
        """Update offer performance stats after click/conversion."""
        try:
            from api.offer_inventory.models import Offer
            if event == 'click':
                Offer.objects.filter(pk=offer_id).update(
                    total_clicks=F('total_clicks') + 1
                )
            elif event == 'conversion':
                Offer.objects.filter(pk=offer_id).update(
                    total_conversions=F('total_conversions') + 1
                )
            cache.delete(f'offer_match:*')
        except Exception:
            pass


from django.db.models import F
offer_matcher = OfferMatcher()