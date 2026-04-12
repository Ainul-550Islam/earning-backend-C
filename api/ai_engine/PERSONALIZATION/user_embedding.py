"""
api/ai_engine/PERSONALIZATION/user_embedding.py
================================================
User Embedding Generator — behavioral vector representations।
User এর actions, preferences, history থেকে dense vector তৈরি করো।
Recommendation ও personalization system এর foundation।
"""

import logging
import math
import hashlib
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class UserEmbeddingGenerator:
    """
    User embedding vector generation engine।
    Behavioral signals → dense float vector।
    Used for: collaborative filtering, similarity search, personalization।
    """

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def generate(self, user, feature_data: dict) -> List[float]:
        """
        User feature data থেকে embedding vector তৈরি করো।
        Production এ: matrix factorization বা neural embedding use করো।
        """
        try:
            import numpy as np

            # Feature-guided deterministic embedding (consistent per user)
            seed_str = f"{user.id}:{sorted(feature_data.items())}"
            seed     = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % (2**31)
            rng      = np.random.RandomState(seed)

            # Base random vector
            base = rng.randn(self.dimensions).astype(float)

            # Inject behavioral signals into specific dimensions
            # (This makes similar users have similar embeddings)
            account_age  = float(feature_data.get('account_age_days', 0))
            earned       = float(feature_data.get('total_earned', 0))
            activity     = float(feature_data.get('activity_score', 0.5))
            referrals    = float(feature_data.get('referral_count', 0))

            # Normalize signals to [-1, 1]
            base[0]  = min(1.0, account_age / 365.0) * 2 - 1
            base[1]  = min(1.0, earned / 10000.0)    * 2 - 1
            base[2]  = activity * 2 - 1
            base[3]  = min(1.0, referrals / 50.0)    * 2 - 1

            # Country encoding
            country = str(feature_data.get('country', 'BD'))
            country_hash = int(hashlib.md5(country.encode()).hexdigest()[:4], 16) % 100
            base[4]  = (country_hash / 50.0) - 1.0

            # Normalize to unit sphere
            norm = np.linalg.norm(base)
            if norm > 0:
                base = base / norm

            return [round(float(v), 6) for v in base]

        except Exception as e:
            logger.error(f"Embedding generation error for user {getattr(user, 'id', '?')}: {e}")
            return self._fallback_embedding(user)

    def _fallback_embedding(self, user) -> List[float]:
        """Deterministic fallback when numpy unavailable।"""
        uid_hash = int(hashlib.md5(str(getattr(user, 'id', '0')).encode()).hexdigest(), 16)
        result   = []
        for i in range(self.dimensions):
            val = math.sin(uid_hash * (i + 1) * 0.0001) * math.cos(i * 0.1)
            result.append(round(val, 6))
        # Normalize
        norm = math.sqrt(sum(v ** 2 for v in result)) or 1.0
        return [round(v / norm, 6) for v in result]

    def store(self, user, vector: List[float],
              embedding_type: str = 'behavioral',
              ai_model=None, tenant_id=None):
        """Embedding DB তে save করো।"""
        try:
            from ..models import UserEmbedding
            obj, created = UserEmbedding.objects.update_or_create(
                user=user,
                embedding_type=embedding_type,
                ai_model=ai_model,
                defaults={
                    'vector':             vector,
                    'dimensions':         len(vector),
                    'is_stale':           False,
                    'interaction_count':  getattr(user, 'offers_completed_count', 0),
                    'tenant_id':          tenant_id,
                },
            )
            return obj
        except Exception as e:
            logger.error(f"Embedding store error: {e}")
            return None

    def get(self, user, embedding_type: str = 'behavioral') -> Optional[List[float]]:
        """User এর stored embedding retrieve করো।"""
        try:
            from ..models import UserEmbedding
            emb = UserEmbedding.objects.filter(
                user=user, embedding_type=embedding_type, is_stale=False
            ).first()
            return emb.vector if emb else None
        except Exception:
            return None

    def bulk_generate(self, users, feature_data_map: Dict,
                      embedding_type: str = 'behavioral',
                      tenant_id=None) -> Dict[str, List[float]]:
        """Multiple users এর embeddings একসাথে generate করো।"""
        results = {}
        for user in users:
            uid      = str(user.id)
            features = feature_data_map.get(uid, {})
            vector   = self.generate(user, features)
            self.store(user, vector, embedding_type, tenant_id=tenant_id)
            results[uid] = vector
        return results

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """দুটো user embedding এর similarity।"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot  = sum(a * b for a, b in zip(vec_a, vec_b))
        na   = math.sqrt(sum(a ** 2 for a in vec_a))
        nb   = math.sqrt(sum(b ** 2 for b in vec_b))
        return round(dot / (na * nb), 6) if na and nb else 0.0

    def find_similar_users(self, user, top_k: int = 20,
                            embedding_type: str = 'behavioral') -> List[Dict]:
        """User এর মতো similar users খুঁজে বের করো।"""
        try:
            from ..models import UserEmbedding
            my_emb = self.get(user, embedding_type)
            if not my_emb:
                return []

            candidates = UserEmbedding.objects.filter(
                embedding_type=embedding_type, is_stale=False
            ).exclude(user=user)[:500]

            scored = []
            for emb in candidates:
                if emb.vector:
                    sim = self.cosine_similarity(my_emb, emb.vector)
                    if sim > 0.50:
                        scored.append({'user_id': str(emb.user_id), 'similarity': sim})

            return sorted(scored, key=lambda x: x['similarity'], reverse=True)[:top_k]

        except Exception as e:
            logger.error(f"Find similar users error: {e}")
            return []

    def mark_stale(self, user_ids: List[str]):
        """Users এর embeddings stale mark করো — refresh trigger।"""
        try:
            from ..models import UserEmbedding
            UserEmbedding.objects.filter(
                user_id__in=user_ids
            ).update(is_stale=True)
        except Exception as e:
            logger.error(f"Mark stale error: {e}")

    def embedding_quality_score(self, vector: List[float]) -> float:
        """Embedding quality assess করো।"""
        if not vector:
            return 0.0
        norm = math.sqrt(sum(v ** 2 for v in vector))
        if norm < 0.01:
            return 0.0  # Zero vector
        non_zero = sum(1 for v in vector if abs(v) > 0.001)
        density  = non_zero / len(vector)
        return round(min(1.0, density * norm), 4)
