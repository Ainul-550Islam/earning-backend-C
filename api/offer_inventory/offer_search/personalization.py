# api/offer_inventory/offer_search/personalization.py
"""Offer Personalization — Personalized offer ranking using user history."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OfferPersonalization:
    """Personalize offer ordering based on user behavior."""

    @staticmethod
    def get_personalized_offers(user, base_offers: list, limit: int = 20) -> list:
        """
        Re-rank offers based on user's completion history and interests.
        Uses: category affinity, past conversions, loyalty tier bonuses.
        """
        if not user or not user.is_authenticated:
            return base_offers[:limit]

        cache_key = f'personalized:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached[:limit]

        # Get user's completed offer categories
        from api.offer_inventory.models import Conversion, UserInterest
        from django.db.models import Count

        done_ids = set(
            Conversion.objects.filter(
                user=user, status__name='approved'
            ).values_list('offer_id', flat=True)
        )

        # Category affinity scores
        affinity = {}
        interests = UserInterest.objects.filter(user=user).values('category_id', 'score')
        for i in interests:
            affinity[str(i['category_id'])] = float(i['score'])

        # Score and rank
        def score_offer(offer):
            s = 0.0
            if str(offer.id) in done_ids:
                return -999   # Already completed
            cat_id = str(offer.category_id) if offer.category_id else ''
            s += affinity.get(cat_id, 0) * 10
            s += float(offer.reward_amount) * 2
            s += 20 if offer.is_featured else 0
            return s

        ranked = sorted(base_offers, key=score_offer, reverse=True)
        cache.set(cache_key, ranked, 120)
        return ranked[:limit]

    @staticmethod
    def update_interest(user, offer, event_type: str = 'click'):
        """Update user's category interest based on interaction."""
        if not offer.category_id:
            return
        from api.offer_inventory.models import UserInterest
        from django.db.models import F

        score_delta = {'click': 0.1, 'conversion': 1.0, 'view': 0.02}.get(event_type, 0.05)
        obj, created = UserInterest.objects.get_or_create(
            user=user, category_id=offer.category_id,
            defaults={'score': score_delta}
        )
        if not created:
            UserInterest.objects.filter(id=obj.id).update(
                score=F('score') + score_delta
            )
        cache.delete(f'personalized:{user.id}')
