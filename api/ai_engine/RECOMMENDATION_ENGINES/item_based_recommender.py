"""
api/ai_engine/RECOMMENDATION_ENGINES/item_based_recommender.py
=============================================================
Item-Based Collaborative Filtering — similar items recommend করো।
"Users who engaged with X also engaged with Y" pattern।
Offer detail page এর "Similar Offers" section।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ItemBasedRecommender:
    """
    Item-based collaborative filtering engine।
    Item embedding similarity + co-occurrence matrix।
    """

    def recommend(self, item_id: str, item_type: str = "offer",
                   count: int = 10, exclude_ids: List[str] = None) -> List[Dict]:
        """Reference item এর similar items recommend করো।"""
        exclude_ids = exclude_ids or [item_id]

        # Try embedding-based similarity first
        embedding_recs = self._embedding_similarity(item_id, item_type, count * 2)
        if embedding_recs:
            filtered = [r for r in embedding_recs if r["item_id"] not in exclude_ids]
            if len(filtered) >= count:
                return filtered[:count]

        # Fallback: attribute-based similarity
        attr_recs = self._attribute_similarity(item_id, item_type, count * 2)
        filtered  = [r for r in attr_recs if r["item_id"] not in exclude_ids]
        return filtered[:count]

    def _embedding_similarity(self, item_id: str, item_type: str, count: int) -> List[Dict]:
        """Cosine similarity using item embeddings।"""
        try:
            from ..models import ItemEmbedding
            from ..utils import cosine_similarity

            ref_emb = ItemEmbedding.objects.filter(
                item_id=item_id, item_type=item_type, is_active=True
            ).first()

            if not ref_emb or not ref_emb.vector:
                return []

            candidates = ItemEmbedding.objects.filter(
                item_type=item_type, is_active=True
            ).exclude(item_id=item_id)[:500]

            scored = []
            for emb in candidates:
                if not emb.vector:
                    continue
                sim = cosine_similarity(ref_emb.vector, emb.vector)
                if sim > 0.3:  # Minimum similarity threshold
                    scored.append({
                        "item_id":   emb.item_id,
                        "item_type": item_type,
                        "score":     round(sim, 4),
                        "engine":    "item_based_embedding",
                        "item_name": emb.item_name or "",
                    })

            return sorted(scored, key=lambda x: x["score"], reverse=True)[:count]

        except Exception as e:
            logger.error(f"Embedding similarity error: {e}")
            return []

    def _attribute_similarity(self, item_id: str, item_type: str, count: int) -> List[Dict]:
        """Item attributes (category, difficulty, reward) based similarity।"""
        try:
            if item_type != "offer":
                return []

            from api.ad_networks.models import Offer

            ref_offer = Offer.objects.filter(id=item_id).first()
            if not ref_offer:
                return []

            # Same category, similar reward range
            reward       = float(getattr(ref_offer, "reward_amount", 100))
            difficulty   = getattr(ref_offer, "difficulty", "medium")
            ref_category = getattr(ref_offer, "category_id", None)

            qs = Offer.objects.filter(status="active").exclude(id=item_id)

            if ref_category:
                qs = qs.filter(category_id=ref_category)

            similar = qs.order_by("-created_at")[:count * 2]

            results = []
            for offer in similar:
                # Calculate similarity score
                reward_diff = abs(float(getattr(offer, "reward_amount", 0)) - reward)
                reward_sim  = max(0.0, 1.0 - reward_diff / max(reward, 1))
                diff_match  = 1.0 if getattr(offer, "difficulty", "") == difficulty else 0.5
                score       = round((reward_sim * 0.6 + diff_match * 0.4), 4)

                results.append({
                    "item_id":    str(offer.id),
                    "item_type":  item_type,
                    "score":      score,
                    "engine":     "item_based_attribute",
                    "title":      getattr(offer, "title", ""),
                    "difficulty": getattr(offer, "difficulty", ""),
                    "reward":     float(getattr(offer, "reward_amount", 0)),
                })

            return sorted(results, key=lambda x: x["score"], reverse=True)[:count]

        except Exception as e:
            logger.error(f"Attribute similarity error: {e}")
            return []

    def recommend_bundle(self, item_ids: List[str],
                          item_type: str = "offer",
                          count: int = 10) -> List[Dict]:
        """
        Multiple items দেখে similar items recommend করো।
        "Basket-based" or "session-based" similarity।
        """
        all_recs: Dict[str, Dict] = {}

        for item_id in item_ids:
            recs = self.recommend(item_id, item_type, count, exclude_ids=item_ids)
            for rec in recs:
                iid = rec["item_id"]
                if iid not in all_recs:
                    all_recs[iid] = {**rec, "support_count": 0}
                all_recs[iid]["score"]         += rec["score"]
                all_recs[iid]["support_count"] += 1

        # Normalize and sort
        n = len(item_ids) or 1
        for iid in all_recs:
            all_recs[iid]["score"] = round(all_recs[iid]["score"] / n, 4)
            all_recs[iid]["engine"] = "item_based_bundle"

        return sorted(all_recs.values(), key=lambda x: x["score"], reverse=True)[:count]

    def find_complementary_offers(self, offer_id: str, count: int = 5) -> List[Dict]:
        """
        Complementary offers — different category but same user profile।
        Cross-sell opportunities।
        """
        try:
            from api.ad_networks.models import Offer
            ref_offer    = Offer.objects.filter(id=offer_id).first()
            if not ref_offer:
                return []

            ref_category = getattr(ref_offer, "category_id", None)
            ref_reward   = float(getattr(ref_offer, "reward_amount", 0))

            # Different category, similar reward range
            qs = Offer.objects.filter(status="active").exclude(id=offer_id)
            if ref_category:
                qs = qs.exclude(category_id=ref_category)

            # Similar reward range (±50%)
            qs = qs.filter(
                reward_amount__gte=ref_reward * 0.5,
                reward_amount__lte=ref_reward * 1.5,
            ).order_by("-created_at")[:count]

            return [
                {
                    "item_id":    str(o.id),
                    "item_type":  "offer",
                    "score":      round(0.70 - i * 0.03, 4),
                    "engine":     "complementary",
                    "type":       "cross_sell",
                }
                for i, o in enumerate(qs)
            ]
        except Exception as e:
            logger.error(f"Complementary offers error: {e}")
            return []

    def get_co_occurrence_stats(self, item_id: str, days: int = 30) -> dict:
        """কোন items এর সাথে এই item frequently দেখা যায়।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone
            from datetime import timedelta

            since = timezone.now() - timedelta(days=days)
            recs  = RecommendationResult.objects.filter(
                created_at__gte=since
            ).values("recommended_items")[:1000]

            co_items: Dict[str, int] = {}
            for rec in recs:
                items_in_rec = [i.get("item_id") for i in (rec["recommended_items"] or [])]
                if item_id in items_in_rec:
                    for other_id in items_in_rec:
                        if other_id != item_id:
                            co_items[other_id] = co_items.get(other_id, 0) + 1

            top_co = sorted(co_items.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "item_id":     item_id,
                "period_days": days,
                "co_occurred_with": [{"item_id": iid, "count": cnt} for iid, cnt in top_co],
            }
        except Exception as e:
            return {"error": str(e)}
