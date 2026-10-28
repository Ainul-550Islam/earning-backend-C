# api/referral/tasks_cap.py
# Capability-based Celery tasks — advanced/optional tasks
# These extend beyond core tasks with world-class features
# ============================================================

import logging
from django.db.models import Sum

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='referral.update_viral_coefficient')
    def update_viral_coefficient():
        """Recalculate K-factor for today."""
        from django.utils import timezone
        from decimal import Decimal
        try:
            from api.referral.models import ViralCoefficient, Referral, ReferralEmailInvitation, ReferralSocialShare
            today = timezone.now().date()
            total_referrers = Referral.objects.values('referrer').distinct().count()
            total_invites = ReferralEmailInvitation.objects.filter(
                created_at__date=today
            ).count() + ReferralSocialShare.objects.filter(
                last_shared__date=today
            ).aggregate(s=Sum('share_count'))['s'] or 0
            total_conversions = Referral.objects.filter(created_at__date=today).count()
            if total_referrers > 0:
                avg_invites = Decimal(str(total_invites)) / Decimal(str(total_referrers))
                conversion_rate = Decimal(str(total_conversions)) / Decimal(str(max(total_invites, 1))) * 100
                k_factor = avg_invites * (conversion_rate / 100)
            else:
                avg_invites = Decimal('0')
                conversion_rate = Decimal('0')
                k_factor = Decimal('0')
            ViralCoefficient.objects.update_or_create(
                date=today,
                defaults={
                    'total_referrers': total_referrers,
                    'total_invites_sent': total_invites,
                    'total_conversions': total_conversions,
                    'avg_invites_per_user': avg_invites,
                    'conversion_rate_pct': conversion_rate,
                    'k_factor': k_factor,
                    'is_viral': k_factor >= Decimal('1.0'),
                }
            )
            logger.info(f'[TasksCap] Viral K-factor: {k_factor}')
            return {'k_factor': float(k_factor)}
        except Exception as e:
            logger.error(f'[TasksCap] update_viral_coefficient failed: {e}')
            return {'error': str(e)}

    @shared_task(name='referral.check_streak_bonuses')
    def check_streak_bonuses():
        """Award streak bonuses to qualifying users."""
        from django.utils import timezone
        from datetime import timedelta
        try:
            from api.referral.models import UserStreakTracker, ReferralStreakBonus
            from api.referral.INTEGRATION_SYSTEM.integ_adapter import WalletAdapter
            active_rules = ReferralStreakBonus.objects.filter(is_active=True)
            awarded = 0
            for rule in active_rules:
                qualifying = UserStreakTracker.objects.filter(
                    current_streak_days__gte=rule.streak_days,
                    total_streak_bonuses__lt=1  # prevent double award
                ).select_related('user')
                for tracker in qualifying:
                    try:
                        if rule.bonus_cash_amount > 0:
                            WalletAdapter.credit_bonus(
                                user=tracker.user,
                                amount=rule.bonus_cash_amount,
                                description=f'Streak bonus: {rule.name}',
                            )
                        if rule.bonus_multiplier > 1:
                            tracker.active_multiplier = rule.bonus_multiplier
                            tracker.multiplier_expires_at = timezone.now() + timedelta(days=rule.bonus_duration_days)
                        tracker.total_streak_bonuses += 1
                        tracker.save()
                        awarded += 1
                    except Exception as e:
                        logger.warning(f'[TasksCap] streak bonus failed: {e}')
            return {'awarded': awarded}
        except Exception as e:
            logger.error(f'[TasksCap] check_streak_bonuses failed: {e}')
            return {'error': str(e)}

    @shared_task(name='referral.process_surge_bonuses')
    def process_surge_bonuses():
        """Check and apply active surge bonuses."""
        from django.utils import timezone
        try:
            from api.referral.models import ReferralSurgeBonus
            active_surges = [s for s in ReferralSurgeBonus.objects.filter(is_active=True)
                           if s.is_currently_active()]
            logger.info(f'[TasksCap] Active surge bonuses: {len(active_surges)}')
            return {'active': len(active_surges)}
        except Exception as e:
            return {'error': str(e)}

    @shared_task(name='referral.update_user_tier_progressions')
    def update_user_tier_progressions():
        """Check and upgrade user commission tiers based on performance."""
        from django.db.models import Count
        try:
            from api.referral.models import (
                UserCommissionTier, CommissionTierProgression, Referral
            )
            tiers = CommissionTierProgression.objects.filter(
                is_active=True
            ).order_by('-min_active_referrals')
            upgraded = 0
            for user_tier in UserCommissionTier.objects.select_related('user', 'current_tier'):
                active_refs = Referral.objects.filter(
                    referrer=user_tier.user, is_suspicious=False
                ).count()
                user_tier.total_active_referrals = active_refs
                new_tier = None
                for tier in tiers:
                    if active_refs >= tier.min_active_referrals:
                        new_tier = tier
                        break
                if new_tier and new_tier != user_tier.current_tier:
                    old_tier = user_tier.current_tier
                    user_tier.current_tier = new_tier
                    from django.utils import timezone
                    user_tier.tier_achieved_at = timezone.now()
                    user_tier.recalculate_rates()
                    user_tier.save()
                    upgraded += 1
                    from api.referral.signals_cap import referral_tier_upgraded
                    referral_tier_upgraded.send(
                        sender=UserCommissionTier,
                        user=user_tier.user,
                        old_tier=old_tier, new_tier=new_tier,
                    )
            return {'upgraded': upgraded}
        except Exception as e:
            logger.error(f'[TasksCap] tier progression failed: {e}')
            return {'error': str(e)}

    @shared_task(name='referral.expire_referral_credits')
    def expire_referral_credits():
        """Expire unused referral credits past their expiry date."""
        from django.utils import timezone
        try:
            from api.referral.models import ReferralCreditBalance
            from django.db.models import F
            expired = ReferralCreditBalance.objects.filter(
                credits_expire_at__lt=timezone.now(),
                balance__gt=0,
                credits_expire_days__gt=0,
            )
            count = expired.count()
            expired.update(balance=0)
            return {'expired_accounts': count}
        except Exception as e:
            return {'error': str(e)}

    @shared_task(name='referral.process_recurring_commissions')
    def process_recurring_commissions():
        """Process due recurring commissions."""
        try:
            from api.referral.services.AdvancedReferralService import RecurringCommissionService
            return RecurringCommissionService.process_due_recurring()
        except Exception as e:
            return {'error': str(e)}

    @shared_task(name='referral.expire_commissions')
    def expire_commissions():
        """Expire time-limited commissions."""
        try:
            from api.referral.services.AdvancedReferralService import CommissionExpiryService
            return CommissionExpiryService.check_and_expire_old()
        except Exception as e:
            return {'error': str(e)}

except ImportError:
    logger.debug('[TasksCap] Celery not available')