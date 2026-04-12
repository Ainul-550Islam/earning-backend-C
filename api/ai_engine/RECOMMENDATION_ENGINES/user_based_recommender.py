"""
api/ai_engine/RECOMMENDATION_ENGINES/user_based_recommender.py
===============================================================
User-Based Collaborative Filtering।
"""

import logging
from ..utils import cosine_similarity
logger = logging.getLogger(__name__)


class UserBasedRecommender:
    def recommend(self, user, item_type: str = 'offer', count: int = 10) -> list:
        from ..models import UserEmbedding
        import random

        my_emb = UserEmbedding.objects.filter(user=user, is_stale=False).first()
        if not my_emb or not my_emb.vector:
            return []

        other_embs = UserEmbedding.objects.filter(
            is_stale=False
        ).exclude(user=user)[:200]

        similar_users = []
        for emb in other_embs:
            sim = cosine_similarity(my_emb.vector, emb.vector)
            if sim > 0.5:
                similar_users.append((emb.user_id, sim))

        similar_users.sort(key=lambda x: x[1], reverse=True)
        similar_user_ids = [uid for uid, _ in similar_users[:10]]

        # Get items these users interacted with
        try:
            from ..models import RecommendationResult
            items_seen = set()
            results = []
            recs = RecommendationResult.objects.filter(
                user_id__in=similar_user_ids, item_type=item_type
            ).order_by('-ctr')[:50]
            for rec in recs:
                for item in rec.recommended_items[:3]:
                    iid = item.get('item_id', '')
                    if iid and iid not in items_seen:
                        items_seen.add(iid)
                        results.append({**item, 'engine': 'user_based', 'score': round(random.uniform(0.4, 0.9), 4)})
                if len(results) >= count:
                    break
            return results[:count]
        except Exception:
            return []


"""
api/ai_engine/RECOMMENDATION_ENGINES/item_based_recommender.py
=============================================================
Item-Based Collaborative Filtering।
"""


class ItemBasedRecommender:
    def recommend(self, item_id: str, item_type: str = 'offer', count: int = 10) -> list:
        from ..models import ItemEmbedding
        from ..utils import cosine_similarity

        ref_emb = ItemEmbedding.objects.filter(item_id=item_id, is_active=True).first()
        if not ref_emb or not ref_emb.vector:
            return []

        candidates = ItemEmbedding.objects.filter(
            item_type=item_type, is_active=True
        ).exclude(item_id=item_id)[:300]

        scored = []
        for emb in candidates:
            if emb.vector:
                sim = cosine_similarity(ref_emb.vector, emb.vector)
                scored.append({'item_id': emb.item_id, 'item_type': item_type, 'score': round(sim, 4), 'engine': 'item_based'})

        return sorted(scored, key=lambda x: x['score'], reverse=True)[:count]


"""
api/ai_engine/RECOMMENDATION_ENGINES/contextual_recommender.py
=============================================================
Contextual Recommender — context-aware recommendations।
"""


class ContextualRecommender:
    def recommend(self, user, context: dict, item_type: str = 'offer', count: int = 10) -> list:
        from .content_based_filtering import ContentBasedEngine
        return ContentBasedEngine().recommend(user, item_type, count, context)


"""
api/ai_engine/RECOMMENDATION_ENGINES/personalized_recommender.py
================================================================
Deep Personalized Recommender।
"""


class PersonalizedRecommender:
    def recommend(self, user, item_type: str = 'offer', count: int = 10) -> list:
        from .hybrid_recommender import HybridRecommender
        from ..models import PersonalizationProfile

        profile = PersonalizationProfile.objects.filter(user=user).first()
        context = {}
        if profile:
            context = {
                'preferred_categories': profile.preferred_categories,
                'preferred_offer_types': profile.preferred_offer_types,
                'ltv_segment': profile.ltv_segment,
            }
        return HybridRecommender().recommend(user, item_type, count, context)


"""
api/ai_engine/RECOMMENDATION_ENGINES/offer_recommender.py
=========================================================
Offer-specific Recommender।
"""


class OfferRecommender:
    def recommend(self, user, count: int = 10, context: dict = None) -> list:
        from .hybrid_recommender import HybridRecommender
        return HybridRecommender().recommend(user, item_type='offer', count=count, context=context or {})


"""
api/ai_engine/RECOMMENDATION_ENGINES/product_recommender.py
============================================================
Product Recommender।
"""


class ProductRecommender:
    def recommend(self, user, count: int = 10) -> list:
        from .popularity_recommender import PopularityRecommender
        return PopularityRecommender().recommend('product', count)


"""
api/ai_engine/RECOMMENDATION_ENGINES/content_recommender.py
============================================================
Content Recommender।
"""


class ContentRecommender:
    def recommend(self, user, count: int = 10) -> list:
        from .popularity_recommender import PopularityRecommender
        return PopularityRecommender().recommend('content', count)


"""
api/ai_engine/RECOMMENDATION_ENGINES/real_time_recommender.py
=============================================================
Real-Time Recommender — <100ms recommendations।
"""

import time


class RealTimeRecommender:
    def recommend(self, user, item_type: str = 'offer', count: int = 5) -> dict:
        start = time.time()
        from .popularity_recommender import PopularityRecommender
        items  = PopularityRecommender().recommend(item_type, count)
        return {
            'items':       items,
            'latency_ms':  round((time.time() - start) * 1000, 2),
            'engine':      'realtime',
        }


"""
api/ai_engine/RECOMMENDATION_ENGINES/session_based_recommender.py
=================================================================
Session-Based Recommender — last N interactions based।
"""


class SessionBasedRecommender:
    def recommend(self, session_items: list, item_type: str = 'offer', count: int = 10) -> list:
        if not session_items:
            from .popularity_recommender import PopularityRecommender
            return PopularityRecommender().recommend(item_type, count)

        last_item_id = session_items[-1] if session_items else None
        if last_item_id:
            from .item_based_recommender import ItemBasedRecommender
            return ItemBasedRecommender().recommend(last_item_id, item_type, count)
        return []


"""
api/ai_engine/RECOMMENDATION_ENGINES/trending_recommender.py
============================================================
Trending Recommender — currently trending items。
"""


class TrendingRecommender:
    def recommend(self, item_type: str = 'offer', count: int = 10,
                  hours: int = 24) -> list:
        try:
            from django.utils import timezone
            from datetime import timedelta
            from ..models import RecommendationResult

            since = timezone.now() - timedelta(hours=hours)
            recent = RecommendationResult.objects.filter(
                item_type=item_type,
                created_at__gte=since,
            ).values('recommended_items')[:200]

            item_counts: dict = {}
            for rec in recent:
                for item in rec['recommended_items']:
                    iid = item.get('item_id', '')
                    if iid:
                        item_counts[iid] = item_counts.get(iid, 0) + 1

            sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
            return [
                {'item_id': iid, 'item_type': item_type,
                 'score': round(0.3 + cnt / max(item_counts.values(), default=1) * 0.6, 4),
                 'engine': 'trending'}
                for iid, cnt in sorted_items[:count]
            ]
        except Exception as e:
            logger.error(f"Trending recommender error: {e}")
            return []


"""
api/ai_engine/RECOMMENDATION_ENGINES/diversity_optimizer.py
============================================================
Diversity Optimizer — ensure recommendation diversity。
"""


class DiversityOptimizer:
    """Ensure diverse recommendations — avoid echo chamber。"""

    def optimize(self, items: list, diversity_factor: float = 0.3) -> list:
        if not items or diversity_factor <= 0:
            return items

        # MMR (Maximal Marginal Relevance) simplified
        selected   = [items[0]]
        candidates = items[1:]

        while candidates and len(selected) < len(items):
            best_item  = None
            best_score = -float('inf')

            for item in candidates:
                # Relevance score
                relevance = item.get('score', 0.5)
                # Diversity: different category from already selected
                selected_cats = [s.get('category', '') for s in selected]
                item_cat = item.get('category', '')
                diversity = 0 if item_cat in selected_cats else 1

                mmr_score = (1 - diversity_factor) * relevance + diversity_factor * diversity
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item  = item

            if best_item:
                selected.append(best_item)
                candidates.remove(best_item)

        return selected
