"""
api/ai_engine/RECOMMENDATION_ENGINES/trending_recommender.py
============================================================
Trending Recommender — real-time trending items detect ও recommend করো।
Social proof algorithm, viral coefficient, momentum scoring।
New users এবং home page এর জন্য ideal।
"""

import logging
from typing import List, Dict
from datetime import timedelta

logger = logging.getLogger(__name__)


class TrendingRecommender:
    """
    Trending item recommendation engine।
    Time-decay weighted popularity + velocity scoring।
    """

    def recommend(self, item_type: str = "offer", count: int = 10,
                   hours: int = 24, tenant_id=None) -> List[Dict]:
        """Currently trending items recommend করো।"""
        try:
            # Primary: recommendation request frequency
            trend_items = self._from_recommendation_logs(item_type, hours, count * 2)
            if len(trend_items) >= count:
                return self._apply_time_decay(trend_items)[:count]
        except Exception as e:
            logger.debug(f"Trending from logs error: {e}")

        # Fallback: conversion-based trending
        try:
            return self._from_conversions(item_type, hours, count)
        except Exception as e:
            logger.debug(f"Trending from conversions error: {e}")

        # Final fallback: recency-based
        return self._recent_items(item_type, count)

    def _from_recommendation_logs(self, item_type: str, hours: int, count: int) -> List[Dict]:
        """Recommendation request logs থেকে trending detect করো।"""
        from ..models import RecommendationResult
        from django.utils import timezone

        since = timezone.now() - timedelta(hours=hours)
        recs  = RecommendationResult.objects.filter(
            item_type=item_type, created_at__gte=since
        ).values("recommended_items", "created_at")[:2000]

        item_data: Dict[str, Dict] = {}

        for rec in recs:
            age_hours = (timezone.now() - rec["created_at"]).total_seconds() / 3600
            time_decay = 1.0 / (1.0 + age_hours / 6)  # Half-life = 6 hours

            for item in (rec["recommended_items"] or []):
                iid = item.get("item_id", "")
                if not iid:
                    continue

                if iid not in item_data:
                    item_data[iid] = {"count": 0, "weighted_score": 0.0, "ctr_sum": 0.0}

                item_data[iid]["count"]          += 1
                item_data[iid]["weighted_score"]  += time_decay
                item_data[iid]["ctr_sum"]         += float(item.get("score", 0.5))

        if not item_data:
            return []

        max_score = max(d["weighted_score"] for d in item_data.values()) or 1

        results = []
        for iid, data in item_data.items():
            normalized_score = data["weighted_score"] / max_score
            avg_ctr          = data["ctr_sum"] / max(data["count"], 1)
            trend_score      = round(normalized_score * 0.7 + avg_ctr * 0.3, 4)

            results.append({
                "item_id":       iid,
                "item_type":     item_type,
                "score":         trend_score,
                "engine":        "trending",
                "request_count": data["count"],
                "trend_score":   trend_score,
            })

        return sorted(results, key=lambda x: x["score"], reverse=True)[:count]

    def _from_conversions(self, item_type: str, hours: int, count: int) -> List[Dict]:
        """Conversion data থেকে trending।"""
        from ..models import PredictionLog
        from django.utils import timezone
        from django.db.models import Count

        since = timezone.now() - timedelta(hours=hours)
        top_items = (
            PredictionLog.objects.filter(
                prediction_type="conversion",
                created_at__gte=since,
            )
            .values("entity_id")
            .annotate(count=Count("id"))
            .order_by("-count")[:count]
        )

        return [
            {
                "item_id":       item["entity_id"],
                "item_type":     item_type,
                "score":         round(0.50 + min(0.45, item["count"] / 1000), 4),
                "engine":        "trending_conversions",
                "conversion_count": item["count"],
            }
            for item in top_items
            if item["entity_id"]
        ]

    def _recent_items(self, item_type: str, count: int) -> List[Dict]:
        """Most recently created items।"""
        try:
            if item_type == "offer":
                from api.ad_networks.models import Offer
                offers = Offer.objects.filter(status="active").order_by("-created_at")[:count]
                return [
                    {"item_id": str(o.id), "item_type": item_type,
                     "score": round(0.70 - i * 0.02, 4), "engine": "trending_recent"}
                    for i, o in enumerate(offers)
                ]
        except Exception:
            pass
        return []

    def _apply_time_decay(self, items: List[Dict]) -> List[Dict]:
        """Re-sort with time decay applied।"""
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)

    def get_trending_categories(self, hours: int = 24) -> List[Dict]:
        """Trending offer categories।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone

            since = timezone.now() - timedelta(hours=hours)
            recs  = RecommendationResult.objects.filter(
                created_at__gte=since
            ).values("recommended_items")[:500]

            cat_counts: Dict[str, int] = {}
            for rec in recs:
                for item in (rec["recommended_items"] or []):
                    cat = item.get("category", "")
                    if cat:
                        cat_counts[cat] = cat_counts.get(cat, 0) + 1

            sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
            return [{"category": cat, "count": cnt, "rank": i+1}
                    for i, (cat, cnt) in enumerate(sorted_cats[:10])]
        except Exception as e:
            logger.error(f"Trending categories error: {e}")
            return []

    def viral_coefficient(self, item_id: str, days: int = 7) -> dict:
        """Viral coefficient — k = invites * conversion_rate।"""
        try:
            from ..models import PredictionLog
            from django.utils import timezone
            from django.db.models import Count

            since = timezone.now() - timedelta(days=days)
            views  = PredictionLog.objects.filter(
                entity_id=item_id, created_at__gte=since
            ).count()
            converts = PredictionLog.objects.filter(
                entity_id=item_id, created_at__gte=since,
                predicted_class="positive"
            ).count()

            cvr          = converts / max(views, 1)
            # Assume each convert shares with 2 people on average
            viral_k      = cvr * 2.0

            return {
                "item_id":           item_id,
                "period_days":       days,
                "views":             views,
                "conversions":       converts,
                "conversion_rate":   round(cvr, 4),
                "viral_coefficient": round(viral_k, 4),
                "going_viral":       viral_k >= 1.0,
                "interpretation":    "Viral — exponential growth" if viral_k >= 1.0 else "Sub-viral — linear growth",
            }
        except Exception as e:
            return {"error": str(e)}
