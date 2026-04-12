"""
api/ai_engine/RECOMMENDATION_ENGINES/content_based_filtering.py
===============================================================
Content-Based Filtering — item attributes ও user preferences matching।
Offer categories, difficulty, reward amount, country matching।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class ContentBasedEngine:
    """Item content ও user preference matching engine।"""

    def recommend(self, user, item_type: str = 'offer', count: int = 10,
                  context: dict = None) -> List[Dict]:
        context = context or {}
        try:
            from ..models import PersonalizationProfile
            profile = PersonalizationProfile.objects.filter(user=user).first()
            prefs   = self._extract_preferences(profile, user, context)
            items   = self._score_items(item_type, prefs, count * 2)
            return sorted(items, key=lambda x: x['score'], reverse=True)[:count]
        except Exception as e:
            logger.error(f"Content-based error: {e}")
            from .popularity_recommender import PopularityRecommender
            return PopularityRecommender().recommend(item_type, count)

    def _extract_preferences(self, profile, user, context) -> dict:
        prefs = {
            'preferred_cats':      [],
            'preferred_types':     [],
            'country':             getattr(user, 'country', 'BD'),
            'device':              context.get('device', 'mobile'),
            'is_mobile':           context.get('device', 'mobile') == 'mobile',
            'preferred_difficulty': 'easy',
            'min_reward':          0,
        }
        if profile:
            prefs['preferred_cats']  = profile.preferred_categories or []
            prefs['preferred_types'] = profile.preferred_offer_types or []
            prefs['is_mobile_first'] = profile.is_mobile_first
        return prefs

    def _score_items(self, item_type: str, prefs: dict, count: int) -> List[Dict]:
        try:
            from api.ad_networks.models import Offer
            qs = Offer.objects.filter(status='active').select_related('category').order_by('-created_at')[:count*3]
            items = []
            for offer in qs:
                score = 0.50  # base
                # Category match
                cat_name = str(offer.category) if hasattr(offer, 'category') and offer.category else ''
                if cat_name and cat_name in prefs['preferred_cats']:
                    score += 0.25
                # Difficulty preference
                diff = getattr(offer, 'difficulty', 'medium')
                if diff == 'easy' and prefs.get('is_mobile'):
                    score += 0.15
                # Reward amount bonus
                reward = float(getattr(offer, 'reward_amount', 0))
                if reward >= 200:
                    score += 0.10
                # Country check
                allowed = getattr(offer, 'allowed_countries', '')
                if allowed and prefs['country'] not in str(allowed):
                    score -= 0.30
                items.append({
                    'item_id':   str(offer.id),
                    'item_type': item_type,
                    'score':     round(max(0.0, min(1.0, score)), 4),
                    'engine':    'content_based',
                    'category':  cat_name,
                    'reward':    reward,
                })
            return items
        except Exception as e:
            logger.error(f"Item scoring error: {e}")
            return []

    def compute_item_similarity(self, item1_features: dict, item2_features: dict) -> float:
        from ..utils import cosine_similarity
        common_keys = set(item1_features) & set(item2_features)
        if not common_keys: return 0.0
        v1 = [float(item1_features.get(k, 0)) for k in common_keys]
        v2 = [float(item2_features.get(k, 0)) for k in common_keys]
        return round(cosine_similarity(v1, v2), 4)
