"""USER_MONETIZATION/user_segmentation.py — User segmentation engine."""
from ..services import SegmentService


class UserSegmentationEngine:
    """Assigns users to segments based on behavioral signals."""

    @classmethod
    def segment_user(cls, user) -> list:
        return SegmentService.get_user_segment_slugs(user)

    @classmethod
    def add_to_segment(cls, segment_slug: str, user, tenant=None) -> bool:
        from ..models import UserSegment
        seg = UserSegment.objects.filter(slug=segment_slug, is_active=True)
        if tenant:
            seg = seg.filter(tenant=tenant)
        seg = seg.first()
        if seg:
            return SegmentService.add_user_to_segment(seg, user)
        return False

    @classmethod
    def get_high_value_users(cls, min_earned=100, tenant=None) -> list:
        from ..OPTIMIZATION_ENGINES.audience_optimizer import AudienceOptimizer
        from decimal import Decimal
        return AudienceOptimizer.high_value_users(tenant, Decimal(str(min_earned)))
