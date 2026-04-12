# api/offer_inventory/targeting/re_engagement_logic.py
"""
Re-Engagement Logic — Target lapsed users with personalized offers.
Identifies inactive users, scores their re-engagement probability,
and serves high-value offers to bring them back.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

INACTIVE_DAYS_THRESHOLD  = 7    # Days without activity = inactive
HIGH_VALUE_PAYOUT_MIN    = Decimal('0.5')
REENGAGEMENT_BONUS       = Decimal('5')   # BDT bonus for returning users


class ReEngagementEngine:
    """
    Re-engagement logic for lapsed users.
    Combines: inactivity scoring, offer personalization, bonus incentives.
    """

    @staticmethod
    def is_user_lapsed(user) -> bool:
        """Check if user is considered lapsed/inactive."""
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(days=INACTIVE_DAYS_THRESHOLD)
        return not Click.objects.filter(user=user, created_at__gte=since).exists()

    @staticmethod
    def get_inactivity_days(user) -> int:
        """How many days since user's last activity."""
        from api.offer_inventory.models import Click
        last = Click.objects.filter(user=user, is_fraud=False).order_by('-created_at').first()
        if not last:
            return 9999
        return (timezone.now() - last.created_at).days

    @staticmethod
    def get_reengagement_offers(user, limit: int = 5) -> list:
        """
        Get high-value offers for a lapsed user.
        Prioritizes: high payout + low completion + featured.
        """
        from api.offer_inventory.models import Offer, Conversion
        from django.db.models import Q

        done_ids = set(
            Conversion.objects.filter(
                user=user, status__name='approved'
            ).values_list('offer_id', flat=True)
        )
        return list(
            Offer.objects.filter(
                status='active',
                payout_amount__gte=HIGH_VALUE_PAYOUT_MIN,
            )
            .exclude(id__in=done_ids)
            .order_by('-is_featured', '-payout_amount', '-conversion_rate')
            [:limit]
        )

    @staticmethod
    def get_lapsed_users(days: int = 14, limit: int = 10000) -> list:
        """Get list of lapsed user IDs for campaign targeting."""
        from api.offer_inventory.models import Click
        from django.contrib.auth import get_user_model

        User  = get_user_model()
        since = timezone.now() - timedelta(days=days)

        active_ids = set(
            Click.objects.filter(created_at__gte=since)
            .values_list('user_id', flat=True)
            .distinct()
        )
        return list(
            User.objects.filter(is_active=True)
            .exclude(id__in=active_ids)
            .values_list('id', flat=True)[:limit]
        )

    @staticmethod
    def compute_reengagement_score(user) -> float:
        """
        Score 0–100: probability this user will re-engage.
        Higher = more likely to return.
        """
        from api.offer_inventory.models import Conversion, Click

        score = 0.0
        now   = timezone.now()

        # Factor 1: Past conversion count (loyal users re-engage more)
        conv_count = Conversion.objects.filter(
            user=user, status__name='approved'
        ).count()
        score += min(30.0, conv_count * 3.0)

        # Factor 2: Days since last activity (less = higher score)
        days_inactive = ReEngagementEngine.get_inactivity_days(user)
        if days_inactive < 14:
            score += 30.0
        elif days_inactive < 30:
            score += 15.0
        elif days_inactive < 60:
            score += 5.0

        # Factor 3: Referral user (more committed)
        from api.offer_inventory.models import UserReferral
        if UserReferral.objects.filter(referred=user).exists():
            score += 20.0

        # Factor 4: Had withdrawal before (high-intent user)
        from api.offer_inventory.models import WithdrawalRequest
        if WithdrawalRequest.objects.filter(user=user, status='completed').exists():
            score += 20.0

        return min(100.0, score)

    @staticmethod
    def send_reengagement_campaign(days_inactive: int = 14,
                                    bonus: Decimal = REENGAGEMENT_BONUS) -> dict:
        """Auto-run re-engagement campaign for lapsed users."""
        user_ids = ReEngagementEngine.get_lapsed_users(days=days_inactive)
        if not user_ids:
            return {'sent': 0, 'bonus_given': 0}

        # Send push + in-app notifications
        from api.offer_inventory.marketing.campaign_manager import MarketingCampaignService
        MarketingCampaignService.send_in_app_campaign(
            title    ='আমরা আপনাকে মিস করছি! 🎁',
            body     =f'ফিরে আসুন এবং {bonus} টাকা বোনাস পান!',
            user_ids =user_ids,
            action_url='/offers',
        )

        # Credit bonus
        from api.offer_inventory.repository import WalletRepository
        given = 0
        for uid in user_ids:
            try:
                WalletRepository.credit_user(
                    user_id    =uid,
                    amount     =bonus,
                    source     ='reengagement_bonus',
                    source_id  =f'reeng_{timezone.now().strftime("%Y%m%d")}',
                    description='ফিরে আসার বোনাস',
                )
                given += 1
            except Exception:
                pass

        from api.offer_inventory.models import ChurnRecord
        ChurnRecord.objects.filter(user_id__in=user_ids).update(reactivation_sent=True)

        logger.info(f'Re-engagement: {len(user_ids)} targeted, {given} bonus given')
        return {'targeted': len(user_ids), 'bonus_given': given}
