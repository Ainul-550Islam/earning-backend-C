"""REVENUE_MODELS/data_monetization.py — Data/analytics monetization model."""
from decimal import Decimal
from django.db.models import Count


class DataMonetizationAnalytics:
    """Tracks value generated from user data & analytics products."""

    @staticmethod
    def segment_value(segment_id: int) -> dict:
        from ..models import UserSegment, UserSegmentMembership
        try:
            seg = UserSegment.objects.get(pk=segment_id)
        except UserSegment.DoesNotExist:
            return {}
        member_count = UserSegmentMembership.objects.filter(segment=seg).count()
        return {
            "segment_name": seg.name,
            "member_count": member_count,
            "estimated_cpm": Decimal("2.00"),
            "estimated_value": (Decimal(member_count) / 1000 * Decimal("2.00")).quantize(Decimal("0.01")),
        }

    @staticmethod
    def audience_size(tenant=None) -> int:
        from django.contrib.auth import get_user_model
        qs = get_user_model().objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.count()
