"""
api/ai_engine/RECOMMENDATION_ENGINES/hybrid_recommender.py
===========================================================
Hybrid Recommender — CF + Content-Based + Popularity combined।
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class HybridRecommender:
    """
    Hybrid recommendation engine।
    Collaborative Filtering + Content-Based + Popularity blend করো।
    """

    CF_WEIGHT      = 0.40
    CB_WEIGHT      = 0.35
    POP_WEIGHT     = 0.25

    def recommend(self, user, item_type: str = 'offer', count: int = 10, context: dict = None) -> List[Dict]:
        """
        User এর জন্য top-N recommendations।
        """
        context = context or {}
        cf_items  = self._collaborative_score(user, item_type, count * 2)
        cb_items  = self._content_score(user, item_type, count * 2, context)
        pop_items = self._popularity_score(item_type, count * 2)

        # Score merge করো
        merged = self._merge_scores(cf_items, cb_items, pop_items)

        # Sort + dedup + top-N
        seen = set()
        results = []
        for item in sorted(merged, key=lambda x: x['score'], reverse=True):
            iid = item['item_id']
            if iid not in seen:
                seen.add(iid)
                results.append(item)
            if len(results) >= count:
                break

        return results

    def _collaborative_score(self, user, item_type: str, count: int) -> List[Dict]:
        """Collaborative filtering — similar users এর items।"""
        try:
            from .collaborative_filtering import CollaborativeFilteringEngine
            return CollaborativeFilteringEngine().recommend(user, item_type, count)
        except Exception as e:
            logger.debug(f"CF fallback: {e}")
            return []

    def _content_score(self, user, item_type: str, count: int, context: dict) -> List[Dict]:
        """Content-based — user preference matching।"""
        try:
            from .content_based_filtering import ContentBasedEngine
            return ContentBasedEngine().recommend(user, item_type, count, context)
        except Exception as e:
            logger.debug(f"CB fallback: {e}")
            return []

    def _popularity_score(self, item_type: str, count: int) -> List[Dict]:
        """Popularity-based fallback।"""
        try:
            from .popularity_recommender import PopularityRecommender
            return PopularityRecommender().recommend(item_type, count)
        except Exception as e:
            logger.debug(f"Popularity fallback: {e}")
            return []

    def _merge_scores(self, cf: list, cb: list, pop: list) -> List[Dict]:
        """Weighted score merge।"""
        scores: Dict[str, Dict] = {}

        def add(items, weight):
            for item in items:
                iid = item.get('item_id', '')
                if iid not in scores:
                    scores[iid] = {**item, 'score': 0.0}
                scores[iid]['score'] += item.get('score', 0.5) * weight

        add(cf,  self.CF_WEIGHT)
        add(cb,  self.CB_WEIGHT)
        add(pop, self.POP_WEIGHT)

        return list(scores.values())
