"""OPTIMIZATION_ENGINES/audience_optimizer.py — Audience targeting optimization."""
from decimal import Decimal


class AudienceOptimizer:
    """Optimizes ad targeting for high-value audience segments."""

    @staticmethod
    def top_segments_by_ecpm(tenant=None, limit: int = 10) -> list:
        from ..models import UserSegment, UserSegmentMembership, AdPerformanceDaily
        from django.db.models import Avg
        segments = list(
            UserSegment.objects.filter(is_active=True)
              .values("id", "name", "member_count")[:limit]
        )
        for seg in segments:
            seg["estimated_ecpm"] = Decimal("2.00")  # placeholder
        return segments

    @staticmethod
    def high_value_users(tenant=None, min_earned: Decimal = Decimal("100")) -> list:
        from ..models import RewardTransaction
        from django.db.models import Sum
        return list(
            RewardTransaction.objects.filter(amount__gt=0)
              .values("user_id", "user__username")
              .annotate(total=Sum("amount"))
              .filter(total__gte=min_earned)
              .order_by("-total")[:100]
        )

    @staticmethod
    def segment_for_user(user, tenant=None) -> list:
        from ..repository import SegmentRepository
        return SegmentRepository.user_segments(user)
