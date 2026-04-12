"""
api/ai_engine/RECOMMENDATION_ENGINES/collaborative_filtering.py
===============================================================
Collaborative Filtering — similar users এর behavior based।
User-User CF: similar users এর liked items recommend করো।
Matrix factorization + embedding similarity।
"""
import logging
from typing import List, Dict
from ..utils import cosine_similarity
logger = logging.getLogger(__name__)

class CollaborativeFilteringEngine:
    """User-based collaborative filtering recommendation।"""

    MIN_SIMILARITY = 0.30

    def recommend(self, user, item_type: str = 'offer',
                  count: int = 10) -> List[Dict]:
        """Similar users এর পছন্দের items recommend করো।"""
        try:
            from ..models import UserEmbedding, RecommendationResult
            my_emb = UserEmbedding.objects.filter(
                user=user, is_stale=False
            ).order_by('-created_at').first()
            if not my_emb or not my_emb.vector:
                return self._fallback(item_type, count)

            # Find similar users
            other_embs = UserEmbedding.objects.filter(
                is_stale=False, dimensions=my_emb.dimensions
            ).exclude(user=user).select_related('user')[:200]

            similar_users = []
            for emb in other_embs:
                if not emb.vector: continue
                sim = cosine_similarity(my_emb.vector, emb.vector)
                if sim >= self.MIN_SIMILARITY:
                    similar_users.append((emb.user, sim))

            if not similar_users:
                return self._fallback(item_type, count)

            # Sort by similarity
            similar_users.sort(key=lambda x: x[1], reverse=True)
            top_users = similar_users[:10]

            # Get items these similar users interacted with
            item_scores: Dict[str, float] = {}
            for sim_user, sim_score in top_users:
                recs = RecommendationResult.objects.filter(
                    user=sim_user, item_type=item_type
                ).order_by('-ctr').first()
                if recs:
                    for item in recs.recommended_items[:5]:
                        iid = item.get('item_id', '')
                        if iid:
                            item_scores[iid] = item_scores.get(iid, 0) + sim_score * item.get('score', 0.5)

            # Sort and return top items
            sorted_items = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
            return [
                {'item_id': iid, 'item_type': item_type, 'score': round(s, 4), 'engine': 'collaborative'}
                for iid, s in sorted_items[:count]
            ]
        except Exception as e:
            logger.error(f"CF engine error: {e}")
            return self._fallback(item_type, count)

    def _fallback(self, item_type: str, count: int) -> List[Dict]:
        from .popularity_recommender import PopularityRecommender
        return PopularityRecommender().recommend(item_type, count)

    def compute_user_similarity_matrix(self, user_ids: List[str]) -> Dict:
        """User similarity matrix compute করো (offline)।"""
        from ..models import UserEmbedding
        embs = {str(e.user_id): e.vector for e in
                UserEmbedding.objects.filter(user_id__in=user_ids, is_stale=False) if e.vector}
        matrix = {}
        ids = list(embs.keys())
        for i, uid1 in enumerate(ids):
            for uid2 in ids[i+1:]:
                sim = cosine_similarity(embs[uid1], embs[uid2])
                if sim >= self.MIN_SIMILARITY:
                    matrix[f"{uid1}|{uid2}"] = round(sim, 4)
        return matrix

    def find_similar_users(self, user, top_n: int = 20) -> List[Dict]:
        """User এর most similar users খুঁজো।"""
        from ..models import UserEmbedding
        my_emb = UserEmbedding.objects.filter(user=user, is_stale=False).first()
        if not my_emb or not my_emb.vector:
            return []
        others = UserEmbedding.objects.filter(is_stale=False).exclude(user=user)[:500]
        scored = []
        for emb in others:
            if emb.vector:
                sim = cosine_similarity(my_emb.vector, emb.vector)
                if sim >= self.MIN_SIMILARITY:
                    scored.append({'user_id': str(emb.user_id), 'similarity': round(sim, 4)})
        return sorted(scored, key=lambda x: x['similarity'], reverse=True)[:top_n]
