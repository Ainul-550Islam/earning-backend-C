"""
api/ai_engine/RECOMMENDATION_ENGINES/session_based_recommender.py
=================================================================
Session-Based Recommender — current session এর context use করো।
Last N interactions → next best item।
Cold-start এবং anonymous users এর জন্য ideal।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SessionBasedRecommender:
    """
    Session-based recommendation।
    Current session এর item sequence → next item predict।
    GRU4Rec / NARM architecture inspired (simplified)।
    """

    def recommend(self, session_items: List[str], item_type: str = "offer",
                  count: int = 10, user=None) -> List[Dict]:
        """
        Session item sequence থেকে next items recommend।
        session_items: ['offer_id_1', 'offer_id_2', ...]  (ordered)
        """
        if not session_items:
            return self._cold_start(item_type, count)

        # Last item → item-based similarity
        last_item = session_items[-1]
        try:
            from .item_based_recommender import ItemBasedRecommender
            similar = ItemBasedRecommender().recommend(last_item, item_type, count * 2)

            # Remove already seen items
            seen     = set(session_items)
            filtered = [i for i in similar if i.get("item_id") not in seen]

            if len(filtered) >= count:
                return [{"engine": "session_based", **i} for i in filtered[:count]]
        except Exception as e:
            logger.debug(f"Item-based session rec error: {e}")

        # Fallback: trending items not in session
        return self._trending_not_seen(session_items, item_type, count)

    def _cold_start(self, item_type: str, count: int) -> List[Dict]:
        """Session history নেই — popularity fallback।"""
        from .popularity_recommender import PopularityRecommender
        items = PopularityRecommender().recommend(item_type, count)
        return [{"engine": "session_coldstart", **i} for i in items]

    def _trending_not_seen(self, seen_items: List[str],
                            item_type: str, count: int) -> List[Dict]:
        """Trending items excluding already seen ones。"""
        try:
            from .trending_recommender import TrendingRecommender
            trending = TrendingRecommender().recommend(item_type, count * 2)
            seen     = set(seen_items)
            filtered = [i for i in trending if i.get("item_id") not in seen]
            return [{"engine": "session_trending", **i} for i in filtered[:count]]
        except Exception:
            return []

    def extract_session_features(self, session_items: List[str]) -> dict:
        """Session থেকে features extract করো।"""
        return {
            "session_length":   len(session_items),
            "unique_items":     len(set(session_items)),
            "repeat_clicks":    len(session_items) - len(set(session_items)),
            "engagement_depth": "deep" if len(session_items) >= 5 else "shallow",
        }

    def detect_intent(self, session_items: List[str]) -> str:
        """Session থেকে user intent detect করো।"""
        n = len(session_items)
        if n == 0:   return "browsing"
        if n <= 2:   return "exploring"
        if n <= 5:   return "comparing"
        if n > 10:   return "highly_engaged"
        return "considering"

    def recommend_next_step(self, session_items: List[str],
                             completed: List[str] = None) -> dict:
        """
        User কে next best action guide করো।
        e.g., complete offer → withdraw → refer friend
        """
        completed = completed or []
        n_completed = len(completed)

        if n_completed == 0:
            return {"next_action": "complete_first_offer",
                    "message":     "প্রথম অফার complete করে শুরু করুন!",
                    "priority":    "high"}
        elif n_completed < 5:
            return {"next_action": "explore_more_offers",
                    "message":     f"{n_completed}টি অফার শেষ। আরও করুন!",
                    "priority":    "medium"}
        elif n_completed >= 5 and not any("withdrawal" in s for s in session_items):
            return {"next_action": "withdraw_earnings",
                    "message":     "আপনার উপার্জন উত্তোলন করুন!",
                    "priority":    "high"}
        else:
            return {"next_action": "refer_friend",
                    "message":     "বন্ধুকে রেফার করুন এবং বোনাস পান!",
                    "priority":    "medium"}
