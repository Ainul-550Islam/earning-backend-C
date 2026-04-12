"""
api/ai_engine/RECOMMENDATION_ENGINES/popularity_recommender.py
==============================================================
Popularity-Based Recommender — সবচেয়ে জনপ্রিয় items recommend করো।
Cold-start problem এর সবচেয়ে কার্যকর fallback।
New users, anonymous users, low-data situations।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PopularityRecommender:
    """
    Popularity-based recommendation engine।
    Global popularity + recency + conversion rate based ranking।
    """

    def recommend(self, item_type: str = "offer", count: int = 10,
                   tenant_id=None, country: str = None) -> List[Dict]:
        """Most popular items recommend করো।"""
        try:
            if item_type == "offer":
                return self._popular_offers(count, tenant_id, country)
            elif item_type == "product":
                return self._popular_products(count, tenant_id)
            elif item_type == "content":
                return self._popular_content(count, tenant_id)
            else:
                return self._popular_offers(count, tenant_id, country)
        except Exception as e:
            logger.error(f"Popularity recommender error [{item_type}]: {e}")
            return self._fallback_items(item_type, count)

    def _popular_offers(self, count: int, tenant_id=None, country: str = None) -> List[Dict]:
        """Most popular offers by completion rate + reward।"""
        try:
            from api.ad_networks.models import Offer
            from django.db.models import F, ExpressionWrapper, FloatField

            qs = Offer.objects.filter(status="active")

            if country:
                qs = qs.filter(
                    models.Q(allowed_countries__icontains=country) |
                    models.Q(allowed_countries="")
                )

            # Sort by reward amount (proxy for popularity when no analytics)
            offers = qs.order_by("-reward_amount", "-created_at")[:count * 2]

            return [
                {
                    "item_id":      str(o.id),
                    "item_type":    "offer",
                    "score":        self._popularity_score(o, i),
                    "engine":       "popularity",
                    "reward":       float(getattr(o, "reward_amount", 0)),
                    "difficulty":   getattr(o, "difficulty", "medium"),
                    "title":        getattr(o, "title", ""),
                    "rank":         i + 1,
                }
                for i, o in enumerate(offers[:count])
            ]
        except Exception as e:
            logger.error(f"Popular offers error: {e}")
            return self._fallback_items("offer", count)

    def _popular_products(self, count: int, tenant_id=None) -> List[Dict]:
        """Popular products — placeholder।"""
        return self._fallback_items("product", count)

    def _popular_content(self, count: int, tenant_id=None) -> List[Dict]:
        """Popular content items।"""
        return self._fallback_items("content", count)

    def _popularity_score(self, item, rank: int) -> float:
        """Item popularity score calculate করো।"""
        # Position decay
        base    = 1.0 - (rank * 0.03)
        reward  = float(getattr(item, "reward_amount", 0))
        reward_boost = min(0.20, reward / 1000)
        return round(max(0.1, base + reward_boost), 4)

    def _fallback_items(self, item_type: str, count: int) -> List[Dict]:
        """DB query fail হলে synthetic fallback।"""
        return [
            {
                "item_id":   f"{item_type}_popular_{i+1}",
                "item_type": item_type,
                "score":     round(0.90 - i * 0.03, 4),
                "engine":    "popularity_fallback",
                "rank":      i + 1,
            }
            for i in range(count)
        ]

    def recommend_trending_today(self, item_type: str = "offer",
                                  count: int = 10, hours: int = 24) -> List[Dict]:
        """আজকের trending items।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone
            from datetime import timedelta

            since = timezone.now() - timedelta(hours=hours)
            recent_recs = RecommendationResult.objects.filter(
                item_type=item_type,
                created_at__gte=since,
            ).values("recommended_items")[:500]

            item_counts: Dict[str, int] = {}
            for rec in recent_recs:
                for item in (rec["recommended_items"] or []):
                    iid = item.get("item_id", "")
                    if iid:
                        item_counts[iid] = item_counts.get(iid, 0) + 1

            sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)

            if not sorted_items:
                return self.recommend(item_type, count)

            max_count = sorted_items[0][1] or 1
            return [
                {
                    "item_id":       iid,
                    "item_type":     item_type,
                    "score":         round(0.3 + (cnt / max_count) * 0.65, 4),
                    "engine":        "trending_today",
                    "request_count": cnt,
                    "rank":          i + 1,
                }
                for i, (iid, cnt) in enumerate(sorted_items[:count])
            ]
        except Exception as e:
            logger.error(f"Trending today error: {e}")
            return self.recommend(item_type, count)

    def recommend_new_arrivals(self, item_type: str = "offer",
                                count: int = 10, days: int = 7) -> List[Dict]:
        """নতুন items (last N days)।"""
        try:
            from django.utils import timezone
            from datetime import timedelta

            since = timezone.now() - timedelta(days=days)

            if item_type == "offer":
                from api.ad_networks.models import Offer
                from django.db import models as dj_models
                offers = Offer.objects.filter(
                    status="active",
                    created_at__gte=since,
                ).order_by("-created_at")[:count]

                return [
                    {
                        "item_id":    str(o.id),
                        "item_type":  item_type,
                        "score":      round(0.75 - i * 0.02, 4),
                        "engine":     "new_arrivals",
                        "days_old":   (timezone.now() - o.created_at).days,
                        "rank":       i + 1,
                    }
                    for i, o in enumerate(offers)
                ]
        except Exception as e:
            logger.error(f"New arrivals error: {e}")

        return self._fallback_items(item_type, count)

    def recommend_by_country(self, country: str, item_type: str = "offer",
                              count: int = 10) -> List[Dict]:
        """Country-specific popular items।"""
        return self._popular_offers(count, country=country)

    def get_popularity_stats(self, item_type: str = "offer",
                              days: int = 7) -> dict:
        """Popularity statistics summary।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count, Avg

            since = timezone.now() - timedelta(days=days)
            qs = RecommendationResult.objects.filter(
                item_type=item_type,
                created_at__gte=since,
            )
            return {
                "total_recommendations": qs.count(),
                "avg_ctr":               round(float(qs.aggregate(Avg("ctr"))["ctr__avg"] or 0), 4),
                "period_days":           days,
                "item_type":             item_type,
            }
        except Exception as e:
            return {"error": str(e)}
