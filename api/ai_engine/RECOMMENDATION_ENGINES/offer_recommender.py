"""
api/ai_engine/RECOMMENDATION_ENGINES/offer_recommender.py
=========================================================
Offer Recommender — earning app এর core recommendation।
User এর profile, history, preference অনুযায়ী best offers।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class OfferRecommender:
    """
    Offer-specific recommendation engine।
    Earning platform এর সবচেয়ে গুরুত্বপূর্ণ recommender।
    """

    def recommend(self, user, count: int = 10, context: dict = None,
                  tenant_id=None) -> List[Dict]:
        """User এর জন্য best offers recommend করো।"""
        context = context or {}

        try:
            from .hybrid_recommender import HybridRecommender
            items = HybridRecommender().recommend(
                user, item_type='offer', count=count * 2, context=context
            )
            # Offer-specific post-processing
            return self._post_process(items, user, count, context)
        except Exception as e:
            logger.error(f"Offer recommender error: {e}")
            return self._fallback(count, tenant_id)

    def _post_process(self, items: List[Dict], user, count: int, context: dict) -> List[Dict]:
        """Offer-specific business rules apply করো।"""
        filtered = []
        user_country = getattr(user, 'country', 'BD')

        for item in items:
            # Country eligibility check
            allowed = item.get('allowed_countries', [])
            if allowed and user_country not in allowed:
                continue

            # Daily limit check — placeholder
            filtered.append(item)

            if len(filtered) >= count:
                break

        return filtered

    def _fallback(self, count: int, tenant_id=None) -> List[Dict]:
        """Error fallback — popularity based।"""
        try:
            from .popularity_recommender import PopularityRecommender
            return PopularityRecommender().recommend('offer', count)
        except Exception:
            return []

    def recommend_by_category(self, user, category: str,
                               count: int = 10) -> List[Dict]:
        """Specific category এর offers recommend।"""
        try:
            from api.ad_networks.models import Offer
            offers = Offer.objects.filter(
                status='active',
                category__name__icontains=category
            ).order_by('-created_at')[:count * 2]

            return [
                {
                    'item_id':   str(o.id),
                    'item_type': 'offer',
                    'score':     0.75,
                    'engine':    'category_based',
                    'category':  category,
                }
                for o in offers[:count]
            ]
        except Exception as e:
            logger.error(f"Category offer recommend error: {e}")
            return []

    def recommend_high_reward(self, user, min_reward: float = 100,
                               count: int = 10) -> List[Dict]:
        """High reward offers recommend করো।"""
        try:
            from api.ad_networks.models import Offer
            offers = Offer.objects.filter(
                status='active',
                reward_amount__gte=min_reward,
            ).order_by('-reward_amount')[:count]

            return [
                {
                    'item_id':     str(o.id),
                    'item_type':   'offer',
                    'score':       round(min(1.0, float(o.reward_amount) / 1000), 4),
                    'engine':      'high_reward',
                    'reward':      float(o.reward_amount),
                }
                for o in offers
            ]
        except Exception as e:
            logger.error(f"High reward offer error: {e}")
            return []

    def recommend_easy_first(self, user, count: int = 10) -> List[Dict]:
        """নতুন users এর জন্য easy offers recommend করো।"""
        try:
            from api.ad_networks.models import Offer
            offers = Offer.objects.filter(
                status='active', difficulty='easy'
            ).order_by('-reward_amount')[:count]

            return [
                {'item_id': str(o.id), 'item_type': 'offer',
                 'score': 0.80, 'engine': 'easy_first', 'difficulty': 'easy'}
                for o in offers
            ]
        except Exception as e:
            logger.error(f"Easy first error: {e}")
            return []
