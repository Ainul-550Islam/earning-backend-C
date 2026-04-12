# api/offer_inventory/user_behavior_analysis/user_segmentation.py
"""
User Segmentation — Dynamic audience segmentation for targeting campaigns.
Segments: high_earners, new_users, churning, loyal, kyc_approved, power_users.
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

BUILT_IN_SEGMENTS = {
    'high_earners'   : {'min_earnings_bdt': 1000},
    'new_users'      : {'joined_days': 7},
    'churning'       : {'inactive_days_min': 14, 'inactive_days_max': 30},
    'loyal'          : {'min_conversions': 10},
    'kyc_approved'   : {'has_kyc': True},
    'power_users'    : {'min_daily_offers': 5},
    'no_withdrawal'  : {'no_withdrawal': True},
    'referrers'      : {'has_referrals': True},
    'high_loyalty'   : {'loyalty_tier': 'Gold'},
}


class UserSegmentationService:
    """Dynamic user segmentation for marketing and targeting."""

    @classmethod
    def build_audience(cls, criteria: dict) -> list:
        """Build a list of user IDs matching the given criteria."""
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import Conversion, WithdrawalRequest, UserKYC, UserReferral, Click

        User = get_user_model()
        qs   = User.objects.filter(is_active=True)
        now  = timezone.now()

        # Minimum earnings
        if 'min_earnings_bdt' in criteria:
            from django.db.models import Sum, Subquery, OuterRef
            earned_ids = (
                Conversion.objects.filter(status__name='approved')
                .values('user_id')
                .annotate(total=Sum('reward_amount'))
                .filter(total__gte=criteria['min_earnings_bdt'])
                .values_list('user_id', flat=True)
            )
            qs = qs.filter(id__in=earned_ids)

        # New users
        if 'joined_days' in criteria:
            since = now - timedelta(days=criteria['joined_days'])
            qs    = qs.filter(date_joined__gte=since)

        # Inactive users (churning)
        if 'inactive_days_min' in criteria:
            active_since = now - timedelta(days=criteria['inactive_days_min'])
            active_ids   = (
                Click.objects.filter(created_at__gte=active_since)
                .values_list('user_id', flat=True)
                .distinct()
            )
            qs = qs.exclude(id__in=active_ids)

        # KYC approved
        if criteria.get('has_kyc'):
            kyc_ids = UserKYC.objects.filter(status='approved').values_list('user_id', flat=True)
            qs      = qs.filter(id__in=kyc_ids)

        # Has referrals
        if criteria.get('has_referrals'):
            ref_ids = UserReferral.objects.filter(
                total_earnings_generated__gt=0
            ).values_list('referrer_id', flat=True)
            qs = qs.filter(id__in=ref_ids)

        # Loyalty tier
        if 'loyalty_tier' in criteria:
            from api.offer_inventory.models import UserProfile
            tier_ids = (
                UserProfile.objects.filter(loyalty_level__name=criteria['loyalty_tier'])
                .values_list('user_id', flat=True)
            )
            qs = qs.filter(id__in=tier_ids)

        return list(qs.values_list('id', flat=True)[:10000])

    @classmethod
    def compute_segment(cls, segment_name: str) -> list:
        """Get user IDs for a built-in segment."""
        criteria = BUILT_IN_SEGMENTS.get(segment_name)
        if not criteria:
            return []
        return cls.build_audience(criteria)

    @classmethod
    def update_segment_counts(cls):
        """Recompute user_count for all dynamic UserSegment records."""
        from api.offer_inventory.models import UserSegment
        for seg in UserSegment.objects.filter(is_dynamic=True):
            try:
                ids   = cls.build_audience(seg.criteria or {})
                UserSegment.objects.filter(id=seg.id).update(
                    user_count   =len(ids),
                    last_computed=timezone.now(),
                )
            except Exception as e:
                logger.error(f'Segment update error {seg.id}: {e}')

    @staticmethod
    def get_segment_summary() -> list:
        """Summary of all built-in segments with estimated sizes."""
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import ChurnRecord, UserKYC

        User  = get_user_model()
        total = User.objects.filter(is_active=True).count()

        return [
            {'segment': name, 'criteria': criteria}
            for name, criteria in BUILT_IN_SEGMENTS.items()
        ]
