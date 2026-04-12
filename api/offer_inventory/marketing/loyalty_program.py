# api/offer_inventory/marketing/loyalty_program.py
"""
Loyalty Program Manager.
Points, tiers (Bronze/Silver/Gold/Platinum), badges, streaks.
Auto-upgrades users to next tier based on earnings/activity.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Tier thresholds (total earned BDT)
TIER_THRESHOLDS = {
    'Bronze'  : Decimal('0'),
    'Silver'  : Decimal('500'),
    'Gold'    : Decimal('2000'),
    'Platinum': Decimal('10000'),
}

# Points per action
POINTS_PER_CONVERSION = 10
POINTS_PER_REFERRAL   = 50
POINTS_PER_DAILY_LOGIN = 2
POINTS_STREAK_BONUS   = 5    # per day in streak


class LoyaltyManager:
    """Full loyalty program lifecycle."""

    @classmethod
    @transaction.atomic
    def award_conversion_points(cls, user, conversion) -> int:
        """Award points for completing an offer."""
        base_points = POINTS_PER_CONVERSION
        # Bonus for high-value offers
        if conversion.payout_amount >= Decimal('1'):
            base_points += int(float(conversion.payout_amount) * 5)

        cls._add_points(user, base_points, f'conversion:{conversion.id}')
        cls._check_tier_upgrade(user)
        cls._check_achievement(user, 'conversion')
        return base_points

    @classmethod
    @transaction.atomic
    def award_referral_points(cls, referrer, referred_user) -> int:
        """Award points for successful referral."""
        cls._add_points(referrer, POINTS_PER_REFERRAL, f'referral:{referred_user.id}')
        cls._check_tier_upgrade(referrer)
        cls._check_achievement(referrer, 'referral')
        return POINTS_PER_REFERRAL

    @classmethod
    def award_login_points(cls, user) -> int:
        """Daily login points with streak bonus."""
        from django.core.cache import cache
        streak_key = f'login_streak:{user.id}'
        streak     = cache.get(streak_key, 0) + 1
        cache.set(streak_key, streak, 86400 * 2)   # Reset if no login for 2 days

        points = POINTS_PER_DAILY_LOGIN + (POINTS_STREAK_BONUS if streak > 1 else 0)
        cls._add_points(user, points, 'daily_login')
        return points

    @classmethod
    def _add_points(cls, user, points: int, source: str):
        """Add points to user profile."""
        from api.offer_inventory.models import UserProfile
        from django.db.models import F
        UserProfile.objects.filter(user=user).update(
            total_points=F('total_points') + points,
            total_offers=F('total_offers') + (1 if 'conversion' in source else 0),
        )
        logger.debug(f'Points awarded: {points} to {user.id} for {source}')

    @classmethod
    def _check_tier_upgrade(cls, user):
        """Auto-upgrade user tier based on total earned."""
        from api.offer_inventory.models import UserProfile, LoyaltyLevel
        from api.wallet.models import Wallet

        try:
            profile = UserProfile.objects.select_related('loyalty_level').get(user=user)
            wallet  = Wallet.objects.get(user=user)
            earned  = wallet.total_earned

            # Find highest qualifying tier
            new_tier = None
            for tier_name, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
                if earned >= threshold:
                    new_tier = LoyaltyLevel.objects.filter(name=tier_name).first()
                    break

            if new_tier and (not profile.loyalty_level or
                             new_tier.level_order > profile.loyalty_level.level_order):
                old_tier = profile.loyalty_level.name if profile.loyalty_level else 'None'
                UserProfile.objects.filter(user=user).update(loyalty_level=new_tier)

                # Notify user
                from api.offer_inventory.repository import NotificationRepository
                NotificationRepository.create(
                    user_id   =user.id,
                    notif_type='success',
                    title     =f'🏆 আপনি {new_tier.name} tier-এ upgrade হয়েছেন!',
                    body      =f'অভিনন্দন! আপনি এখন {new_tier.name} member। অতিরিক্ত {new_tier.payout_bonus_pct}% reward পাচ্ছেন।',
                )
                logger.info(f'Tier upgrade: user={user.id} {old_tier}→{new_tier.name}')

        except Exception as e:
            logger.error(f'Tier check error: {e}')

    @classmethod
    def _check_achievement(cls, user, trigger: str):
        """Check and award achievements."""
        from api.offer_inventory.models import Achievement, UserAchievement, UserProfile

        try:
            profile = UserProfile.objects.get(user=user)
            achievements = Achievement.objects.filter(is_active=True)

            for ach in achievements:
                if UserAchievement.objects.filter(user=user, achievement=ach).exists():
                    continue

                req = ach.requirement or {}
                earned = True

                if 'offers_completed' in req:
                    if profile.total_offers < req['offers_completed']:
                        earned = False
                if 'total_points' in req:
                    if profile.total_points < req['total_points']:
                        earned = False

                if earned:
                    UserAchievement.objects.create(user=user, achievement=ach)
                    cls._add_points(user, ach.points_award, f'achievement:{ach.id}')
                    from api.offer_inventory.repository import NotificationRepository
                    NotificationRepository.create(
                        user_id   =user.id,
                        notif_type='success',
                        title     =f'🏅 Achievement Unlocked: {ach.name}',
                        body      =ach.description or 'আপনি একটি achievement অর্জন করেছেন!',
                    )
        except Exception as e:
            logger.error(f'Achievement check error: {e}')

    @staticmethod
    def get_leaderboard(days: int = 30, limit: int = 20) -> list:
        """Top earners leaderboard."""
        from api.offer_inventory.models import UserProfile
        from django.db.models import F
        return list(
            UserProfile.objects.select_related('user', 'loyalty_level')
            .order_by('-total_points')[:limit]
            .values('user__username', 'total_points', 'loyalty_level__name', 'total_offers')
        )

    @staticmethod
    def get_user_rank(user) -> int:
        """Get user's rank in the leaderboard."""
        from api.offer_inventory.models import UserProfile
        try:
            profile = UserProfile.objects.get(user=user)
            rank    = UserProfile.objects.filter(
                total_points__gt=profile.total_points
            ).count() + 1
            return rank
        except Exception:
            return 0
