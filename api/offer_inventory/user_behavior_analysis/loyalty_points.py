# api/offer_inventory/user_behavior_analysis/loyalty_points.py
"""
Loyalty Points Analytics — Track and analyze loyalty point distribution.
Separate from marketing/loyalty_program.py (which handles business logic).
This file handles analytics and reporting on the loyalty system.
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Avg

logger = logging.getLogger(__name__)


class LoyaltyPointsAnalytics:
    """Analytics for the loyalty points program."""

    @staticmethod
    def get_points_distribution() -> list:
        """Distribution of total_points across loyalty tiers."""
        from api.offer_inventory.models import UserProfile
        return list(
            UserProfile.objects.filter(total_points__gt=0)
            .values('loyalty_level__name')
            .annotate(
                user_count =Count('id'),
                avg_points =Avg('total_points'),
                total_points=Sum('total_points'),
            )
            .order_by('-avg_points')
        )

    @staticmethod
    def get_top_point_earners(limit: int = 20) -> list:
        """Top users by total loyalty points."""
        from api.offer_inventory.models import UserProfile
        return list(
            UserProfile.objects.select_related('user', 'loyalty_level')
            .order_by('-total_points')
            .values(
                'user__username',
                'total_points',
                'loyalty_level__name',
            )
            [:limit]
        )

    @staticmethod
    def get_tier_breakdown() -> list:
        """How many users are in each loyalty tier."""
        from api.offer_inventory.models import UserProfile
        return list(
            UserProfile.objects.values('loyalty_level__name', 'loyalty_level__level_order')
            .annotate(user_count=Count('id'))
            .order_by('loyalty_level__level_order')
        )

    @staticmethod
    def get_points_velocity(days: int = 7) -> dict:
        """Average points earned per user per day."""
        from api.offer_inventory.models import UserProfile
        from django.contrib.auth import get_user_model
        User = get_user_model()

        total_points = (
            UserProfile.objects.aggregate(s=Sum('total_points'))['s'] or 0
        )
        user_count   = User.objects.filter(is_active=True).count()
        per_user_day = round(total_points / max(user_count, 1) / max(days, 1), 2)
        return {
            'total_points'   : total_points,
            'active_users'   : user_count,
            'per_user_per_day': per_user_day,
            'days'           : days,
        }

    @staticmethod
    def get_tier_upgrade_candidates(target_tier: str = 'Silver') -> list:
        """Users close to upgrading to the next tier."""
        from api.offer_inventory.models import UserProfile, LoyaltyLevel
        try:
            tier = LoyaltyLevel.objects.get(name=target_tier)
            gap  = 200  # Within 200 points of upgrade
            return list(
                UserProfile.objects.filter(
                    total_points__gte=tier.min_points - gap,
                    total_points__lt =tier.min_points,
                ).values('user__username', 'total_points')
                .annotate(points_needed=tier.min_points - __import__('django.db.models', fromlist=['F']).F('total_points'))
                [:50]
            )
        except LoyaltyLevel.DoesNotExist:
            return []

    @staticmethod
    def award_points(user, points: int, reason: str = '') -> dict:
        """Award loyalty points to a user."""
        from api.offer_inventory.models import UserProfile, LoyaltyLevel
        from django.db.models import F

        UserProfile.objects.filter(user=user).update(
            total_points=F('total_points') + points
        )
        profile = UserProfile.objects.get(user=user)

        # Check tier upgrade
        new_tier = (
            LoyaltyLevel.objects.filter(
                min_points__lte=profile.total_points
            ).order_by('-min_points').first()
        )
        upgraded = False
        if new_tier and new_tier != profile.loyalty_level:
            UserProfile.objects.filter(user=user).update(loyalty_level=new_tier)
            upgraded = True
            logger.info(f'Loyalty upgrade: user={user.id} → {new_tier.name}')

        return {
            'points_awarded' : points,
            'total_points'   : profile.total_points + points,
            'tier_upgraded'  : upgraded,
            'new_tier'       : new_tier.name if new_tier else None,
        }
