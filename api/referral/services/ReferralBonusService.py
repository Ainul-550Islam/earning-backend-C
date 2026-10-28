# api/referral/services/ReferralBonusService.py
# Milestone bonus detection and payout
# ============================================================

from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ReferralBonusService:
    """
    Milestone bonus service।
    User certain milestone reach করলে bonus দাও।
    e.g. 10 referrals → ৳500, 25 referrals → ৳1500
    """

    @staticmethod
    def check_and_award_milestones(user) -> list:
        """
        User এর current stats দেখো এবং eligible milestones award করো।
        Signup এর পরে এবং commission দেওয়ার পরে call করো।
        """
        from api.referral.models import ReferralBonus, ReferralBonusClaim
        from api.referral.services.ReferralCampaignService import ReferralCampaignService

        campaign = ReferralCampaignService.get_active_campaign()
        if not campaign:
            return []

        bonuses = ReferralBonus.objects.filter(
            campaign=campaign,
            is_active=True,
        ).order_by('milestone_value')

        if not bonuses.exists():
            return []

        user_stats = ReferralBonusService._get_user_stats(user)
        awarded = []

        for bonus in bonuses:
            # Already claimed check (non-repeatable)
            if not bonus.is_repeatable:
                already_claimed = ReferralBonusClaim.objects.filter(
                    user=user,
                    bonus=bonus,
                    status='paid',
                ).exists()
                if already_claimed:
                    continue

            # Check milestone
            stat_value = user_stats.get(bonus.milestone_type, 0)
            if Decimal(str(stat_value)) >= bonus.milestone_value:
                result = ReferralBonusService._award_bonus(user, bonus)
                if result['success']:
                    awarded.append({
                        'bonus_id': bonus.id,
                        'milestone': float(bonus.milestone_value),
                        'amount': float(bonus.bonus_amount),
                        'reward_type': bonus.reward_type,
                    })

        return awarded

    @staticmethod
    @transaction.atomic
    def _award_bonus(user, bonus) -> dict:
        """Specific bonus award করো।"""
        from api.referral.models import ReferralBonusClaim

        try:
            if bonus.reward_type == 'cash':
                from api.wallet.services import WalletService
                from api.wallet.models import Wallet

                wallet, _ = Wallet.objects.get_or_create(user=user)
                wallet_txn = WalletService.add_earnings(
                    wallet=wallet,
                    amount=bonus.bonus_amount,
                    description=(
                        f"Referral milestone bonus: "
                        f"{bonus.title or str(bonus.milestone_value) + ' referrals'}"
                    ),
                    source_type='referral_milestone_bonus',
                    source_id=str(bonus.id),
                )

                claim = ReferralBonusClaim.objects.create(
                    user=user,
                    bonus=bonus,
                    amount_paid=bonus.bonus_amount,
                    wallet_transaction_id=str(
                        getattr(wallet_txn, 'walletTransaction_id', '')
                    ),
                    status='paid',
                )

                logger.info(
                    f"Milestone bonus awarded: {user.username} "
                    f"৳{bonus.bonus_amount} "
                    f"(milestone={bonus.milestone_value})"
                )

                return {
                    'success': True,
                    'claim_id': claim.id,
                    'amount': float(bonus.bonus_amount),
                }

            elif bonus.reward_type == 'multiplier':
                # Temporary commission multiplier
                # Store in cache for duration
                from django.core.cache import cache
                cache_key = f"ref_multiplier:{user.id}"
                expires = timezone.now() + timedelta(
                    days=bonus.multiplier_duration_days
                )
                cache.set(
                    cache_key,
                    {
                        'multiplier': float(bonus.multiplier_value),
                        'expires': expires.isoformat(),
                        'bonus_id': bonus.id,
                    },
                    timeout=bonus.multiplier_duration_days * 86400,
                )

                claim = ReferralBonusClaim.objects.create(
                    user=user,
                    bonus=bonus,
                    amount_paid=Decimal('0'),
                    status='paid',
                )

                return {
                    'success': True,
                    'claim_id': claim.id,
                    'multiplier': float(bonus.multiplier_value),
                    'duration_days': bonus.multiplier_duration_days,
                }

            else:
                # badge, gift_card etc — create claim record
                claim = ReferralBonusClaim.objects.create(
                    user=user,
                    bonus=bonus,
                    amount_paid=bonus.bonus_amount,
                    status='paid',
                )
                return {'success': True, 'claim_id': claim.id}

        except Exception as e:
            logger.error(f"Bonus award error for {user.username}: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _get_user_stats(user) -> dict:
        """User এর milestone-relevant stats পাও।"""
        from api.referral.models import Referral, ReferralEarning, ReferralChain
        from django.db.models import Sum

        direct_count = Referral.objects.filter(referrer=user).count()
        active_count = Referral.objects.filter(
            referrer=user, referred_user__is_active=True
        ).count()

        l2_count = ReferralChain.objects.filter(
            beneficiary=user, level=2
        ).count()
        l3_count = ReferralChain.objects.filter(
            beneficiary=user, level=3
        ).count()
        team_size = direct_count + l2_count + l3_count

        total_commission = ReferralEarning.objects.filter(
            referrer=user
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        return {
            'referral_count': direct_count,
            'active_referral_count': active_count,
            'commission_earned': float(total_commission),
            'team_size': team_size,
        }

    @staticmethod
    def get_milestone_progress(user, campaign_id: int = None) -> dict:
        """User এর milestone progress দেখাও।"""
        from api.referral.models import ReferralBonus, ReferralBonusClaim
        from api.referral.services.ReferralCampaignService import ReferralCampaignService

        if campaign_id:
            from api.referral.models import ReferralCampaign
            try:
                campaign = ReferralCampaign.objects.get(id=campaign_id)
            except ReferralCampaign.DoesNotExist:
                return {'error': 'Campaign not found'}
        else:
            campaign = ReferralCampaignService.get_active_campaign()

        if not campaign:
            return {'milestones': [], 'campaign': None}

        bonuses = ReferralBonus.objects.filter(
            campaign=campaign, is_active=True
        ).order_by('milestone_value')

        user_stats = ReferralBonusService._get_user_stats(user)

        milestones = []
        for bonus in bonuses:
            stat_value = user_stats.get(bonus.milestone_type, 0)
            progress = min(100, (
                float(stat_value) / float(bonus.milestone_value) * 100
            ) if bonus.milestone_value > 0 else 0)

            is_claimed = ReferralBonusClaim.objects.filter(
                user=user, bonus=bonus, status='paid'
            ).exists()

            milestones.append({
                'bonus_id': bonus.id,
                'title': bonus.title or f"{bonus.milestone_value} Referrals",
                'milestone_type': bonus.milestone_type,
                'milestone_value': float(bonus.milestone_value),
                'current_value': float(stat_value),
                'progress_pct': round(progress, 1),
                'bonus_amount': float(bonus.bonus_amount),
                'reward_type': bonus.reward_type,
                'is_reached': float(stat_value) >= float(bonus.milestone_value),
                'is_claimed': is_claimed,
                'icon': bonus.icon,
            })

        return {
            'campaign': campaign.name,
            'milestones': milestones,
            'user_stats': user_stats,
        }