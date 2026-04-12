"""
api/ai_engine/RECOMMENDATION_ENGINES/personalized_recommender.py
================================================================
Deep Personalized Recommender — সবচেয়ে advanced personalization।
User embedding + preference + behavior + context সব combine করো।
Each user কে সম্পূর্ণ unique experience দাও।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PersonalizedRecommender:
    """
    Deep personalization engine।
    Multi-signal fusion: embeddings + profile + behavior + context।
    Marketing conversion maximize করার জন্য।
    """

    def recommend(self, user, item_type: str = "offer", count: int = 10,
                   context: dict = None, tenant_id=None) -> List[Dict]:
        """Fully personalized recommendations।"""
        context = context or {}

        # Step 1: Get user personalization profile
        profile = self._get_user_profile(user)

        # Step 2: Get multi-source candidates
        candidates = self._get_candidates(user, item_type, count * 3, profile, context)

        # Step 3: Score with personalization signals
        scored = self._personalization_score(candidates, user, profile, context)

        # Step 4: Diversify (avoid echo chamber)
        diversified = self._diversify(scored, count)

        # Step 5: Log for feedback loop
        self._log_impression(user, diversified, item_type, tenant_id)

        return diversified

    def _get_user_profile(self, user) -> dict:
        """User personalization profile niye aao।"""
        try:
            from ..models import PersonalizationProfile
            profile = PersonalizationProfile.objects.filter(user=user).first()
            if profile:
                return {
                    "preferred_categories":   profile.preferred_categories or [],
                    "preferred_offer_types":  profile.preferred_offer_types or [],
                    "preferred_devices":      profile.preferred_devices or [],
                    "is_deal_seeker":         profile.is_deal_seeker,
                    "is_high_engagement":     profile.is_high_engagement,
                    "price_sensitivity":      float(profile.price_sensitivity or 0.5),
                    "activity_score":         float(profile.activity_score or 0.5),
                    "ltv_segment":            profile.ltv_segment or "medium",
                    "engagement_score":       float(profile.engagement_score or 0.5),
                }
        except Exception:
            pass
        return {"preferred_categories": [], "activity_score": 0.5, "ltv_segment": "medium"}

    def _get_candidates(self, user, item_type: str, count: int,
                         profile: dict, context: dict) -> List[Dict]:
        """Multiple sources থেকে candidate items collect করো।"""
        candidates: Dict[str, Dict] = {}

        # Source 1: Hybrid recommendations
        try:
            from .hybrid_recommender import HybridRecommender
            hybrid_items = HybridRecommender().recommend(user, item_type, count // 2, context)
            for item in hybrid_items:
                candidates[item["item_id"]] = {**item, "source": "hybrid"}
        except Exception as e:
            logger.debug(f"Hybrid source error: {e}")

        # Source 2: Category-based (from user preferences)
        preferred_cats = profile.get("preferred_categories", [])
        if preferred_cats:
            try:
                from .offer_recommender import OfferRecommender
                cat_items = OfferRecommender().recommend_by_category(
                    user, preferred_cats[0], count // 4
                )
                for item in cat_items:
                    iid = item["item_id"]
                    if iid not in candidates:
                        candidates[iid] = {**item, "source": "category_pref"}
            except Exception as e:
                logger.debug(f"Category source error: {e}")

        # Source 3: Trending today
        try:
            from .popularity_recommender import PopularityRecommender
            trending = PopularityRecommender().recommend_trending_today(item_type, count // 4)
            for item in trending:
                iid = item["item_id"]
                if iid not in candidates:
                    candidates[iid] = {**item, "source": "trending"}
        except Exception as e:
            logger.debug(f"Trending source error: {e}")

        # Source 4: High reward items for deal seekers
        if profile.get("is_deal_seeker") or profile.get("ltv_segment") in ("high", "premium"):
            try:
                from .offer_recommender import OfferRecommender
                high_reward = OfferRecommender().recommend_high_reward(user, count=count // 4)
                for item in high_reward:
                    iid = item["item_id"]
                    if iid not in candidates:
                        candidates[iid] = {**item, "source": "high_reward"}
            except Exception as e:
                logger.debug(f"High reward source error: {e}")

        return list(candidates.values())

    def _personalization_score(self, candidates: List[Dict], user,
                                 profile: dict, context: dict) -> List[Dict]:
        """Each candidate item এ personalization signals apply করো।"""
        preferred_cats  = set(profile.get("preferred_categories", []))
        preferred_types = set(profile.get("preferred_offer_types", []))
        activity_score  = float(profile.get("activity_score", 0.5))
        ltv_segment     = profile.get("ltv_segment", "medium")
        hour            = context.get("hour", 12)
        device          = context.get("device", "mobile")
        country         = context.get("country", getattr(user, "country", "BD"))

        ltv_boost = {"premium": 1.30, "high": 1.15, "medium": 1.0, "low": 0.90}.get(ltv_segment, 1.0)

        scored = []
        for item in candidates:
            base_score = float(item.get("score", 0.50))
            boost      = 1.0

            # Category preference boost
            if item.get("category") in preferred_cats:
                boost *= 1.30

            # LTV-based boost
            boost *= ltv_boost

            # Evening + high reward boost
            reward = float(item.get("reward", 0))
            if 18 <= hour <= 22 and reward >= 200:
                boost *= 1.20

            # Mobile-friendly boost
            if device == "mobile" and item.get("difficulty") == "easy":
                boost *= 1.15

            # Activity score boost
            boost *= (0.7 + activity_score * 0.6)

            # Country eligibility
            allowed_countries = item.get("allowed_countries", [])
            if allowed_countries and country not in allowed_countries:
                boost *= 0.10  # Near-zero for ineligible

            final_score = round(min(1.0, base_score * boost), 4)
            scored.append({**item, "score": final_score, "personalized": True, "boost_applied": round(boost, 3)})

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def _diversify(self, items: List[Dict], count: int) -> List[Dict]:
        """Category diversity ensure করো।"""
        if len(items) <= count:
            return items[:count]

        selected: List[Dict]      = []
        category_counts: Dict     = {}
        MAX_PER_CATEGORY          = max(2, count // 3)

        # First pass: fill with category constraints
        for item in items:
            cat = item.get("category", "unknown")
            if category_counts.get(cat, 0) < MAX_PER_CATEGORY:
                selected.append(item)
                category_counts[cat] = category_counts.get(cat, 0) + 1
            if len(selected) >= count:
                break

        # Second pass: fill remaining slots
        if len(selected) < count:
            remaining_ids = {i["item_id"] for i in selected}
            for item in items:
                if item["item_id"] not in remaining_ids:
                    selected.append(item)
                    if len(selected) >= count:
                        break

        return selected[:count]

    def _log_impression(self, user, items: List[Dict],
                         item_type: str, tenant_id=None):
        """Impression log করো (feedback loop)।"""
        try:
            from ..models import RecommendationResult
            import uuid
            RecommendationResult.objects.create(
                user=user,
                engine="personalized",
                item_type=item_type,
                recommended_items=items,
                item_count=len(items),
                tenant_id=tenant_id,
                request_id=uuid.uuid4(),
            )
        except Exception as e:
            logger.debug(f"Impression log error: {e}")

    def explain_recommendation(self, user, item_id: str) -> dict:
        """Recommendation কেন করা হয়েছে সেটা explain করো।"""
        profile = self._get_user_profile(user)
        reasons = []

        preferred_cats = profile.get("preferred_categories", [])
        if preferred_cats:
            reasons.append(f"Matches your interest in {', '.join(preferred_cats[:2])}")

        ltv = profile.get("ltv_segment", "medium")
        if ltv in ("high", "premium"):
            reasons.append("Recommended for high-value members like you")

        activity = float(profile.get("activity_score", 0.5))
        if activity >= 0.70:
            reasons.append("Popular among highly active users")

        if not reasons:
            reasons.append("Trending in your region")

        return {
            "item_id":  item_id,
            "user_id":  str(user.id),
            "reasons":  reasons,
            "primary_reason": reasons[0] if reasons else "Recommended for you",
        }

    def get_user_recommendation_history(self, user, days: int = 30,
                                         item_type: str = "offer") -> dict:
        """User এর recommendation history analyze করো।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Avg, Count

            since = timezone.now() - timedelta(days=days)
            qs = RecommendationResult.objects.filter(
                user=user,
                item_type=item_type,
                created_at__gte=since,
            )
            total_recs      = qs.count()
            total_clicks    = qs.exclude(clicked_item_id="").count()
            total_converts  = qs.exclude(converted_item_id="").count()
            avg_ctr         = total_clicks / max(total_recs, 1)

            return {
                "period_days":           days,
                "total_recommendations": total_recs,
                "total_clicks":          total_clicks,
                "total_conversions":     total_converts,
                "avg_ctr":               round(avg_ctr, 4),
                "avg_cvr":               round(total_converts / max(total_clicks, 1), 4),
                "engagement_rate":       round(avg_ctr, 4),
            }
        except Exception as e:
            return {"error": str(e)}
