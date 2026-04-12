"""
api/monetization_tools/services.py
=====================================
Business logic layer — keeps views thin.
"""

import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    AdCampaign, Offer, OfferCompletion, RewardTransaction,
    UserSubscription, SubscriptionPlan, PaymentTransaction,
    RecurringBilling, UserLevel, Achievement, SpinWheelLog,
    LeaderboardRank, RevenueDailySummary,
)
from .exceptions import (
    OfferNotAvailable, OfferAlreadyCompleted, OfferExpired,
    OfferGeoRestricted, DailyOfferLimitReached, OfferFraudDetected,
    InsufficientBalance, SubscriptionAlreadyActive, PaymentFailed,
    SpinWheelDailyLimitReached, ScratchCardDailyLimitReached,
    AchievementAlreadyUnlocked,
)
from .constants import (
    MAX_DAILY_OFFERS_PER_USER, OFFER_FRAUD_BLOCK_THRESHOLD,
    SPIN_WHEEL_DAILY_LIMIT, SCRATCH_CARD_DAILY_LIMIT,
)
from .enums import (
    OfferCompletionStatus, RewardTransactionType,
    SubscriptionStatus, PaymentStatus, SpinWheelType, PrizeType,
    AchievementCategory,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ===========================================================================
# OFFER SERVICE
# ===========================================================================

class OfferService:
    """All business logic related to Offer completions and rewards."""

    @staticmethod
    def validate_offer_for_user(offer: Offer, user, ip_address: str = None) -> None:
        """Raise exception if offer cannot be started by this user."""
        if not offer.is_available:
            raise OfferNotAvailable()

        today = timezone.now().date()
        already = OfferCompletion.objects.filter(
            user=user, offer=offer,
            status=OfferCompletionStatus.APPROVED
        ).exists()
        if already:
            raise OfferAlreadyCompleted()

        # Daily limit check
        today_count = OfferCompletion.objects.filter(
            user=user,
            created_at__date=today,
        ).count()
        if today_count >= MAX_DAILY_OFFERS_PER_USER:
            raise DailyOfferLimitReached()

        # Geo check
        if offer.target_countries and user.country:
            if user.country.upper() not in [c.upper() for c in offer.target_countries]:
                raise OfferGeoRestricted()

    @staticmethod
    @transaction.atomic
    def start_offer(offer: Offer, user, ip_address: str, device_id: str = None,
                    user_agent: str = None) -> OfferCompletion:
        """Create a pending OfferCompletion record."""
        OfferService.validate_offer_for_user(offer, user, ip_address)

        completion = OfferCompletion.objects.create(
            user=user,
            offer=offer,
            status=OfferCompletionStatus.PENDING,
            reward_amount=offer.point_value,
            payout_amount=offer.payout_usd,
            ip_address=ip_address,
            device_id=device_id,
            user_agent=user_agent,
            clicked_at=timezone.now(),
        )
        logger.info("OfferCompletion started: user=%s offer=%s txn=%s",
                    user.id, offer.id, completion.transaction_id)
        return completion

    @staticmethod
    @transaction.atomic
    def approve_completion(completion: OfferCompletion) -> RewardTransaction:
        """Approve a pending completion and credit user."""
        if completion.status != OfferCompletionStatus.PENDING:
            raise OfferAlreadyCompleted()

        if completion.fraud_score >= OFFER_FRAUD_BLOCK_THRESHOLD:
            completion.status = OfferCompletionStatus.FRAUD
            completion.save(update_fields=['status', 'updated_at'])
            raise OfferFraudDetected()

        user = completion.user
        balance_before = user.coin_balance

        # Credit user
        user.coin_balance += completion.reward_amount
        user.total_earned += completion.reward_amount
        user.save(update_fields=['coin_balance', 'total_earned'])

        # Update completion
        completion.status = OfferCompletionStatus.APPROVED
        completion.completed_at = timezone.now()
        completion.approved_at  = timezone.now()
        completion.credited_at  = timezone.now()
        completion.save(update_fields=['status', 'completed_at', 'approved_at', 'credited_at', 'updated_at'])

        # Offer stats
        offer = completion.offer
        offer.total_completions += 1
        offer.save(update_fields=['total_completions', 'updated_at'])

        # Reward transaction log
        reward_txn = RewardTransaction.objects.create(
            user=user,
            transaction_type=RewardTransactionType.OFFER_REWARD,
            amount=completion.reward_amount,
            balance_before=balance_before,
            balance_after=user.coin_balance,
            description=f"Offer completed: {offer.title}",
            reference_id=str(completion.transaction_id),
        )

        logger.info("Offer approved: user=%s reward=%s", user.id, completion.reward_amount)
        return reward_txn

    @staticmethod
    @transaction.atomic
    def reject_completion(completion: OfferCompletion, reason: str = '') -> None:
        completion.status = OfferCompletionStatus.REJECTED
        completion.rejection_reason = reason
        completion.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        logger.info("Offer rejected: txn=%s reason=%s", completion.transaction_id, reason)


# ===========================================================================
# REWARD SERVICE
# ===========================================================================

class RewardService:
    """Credit / debit user point balance with full audit trail."""

    @staticmethod
    @transaction.atomic
    def credit(user, amount: Decimal, transaction_type: str,
               description: str = '', reference_id: str = '') -> RewardTransaction:
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")
        balance_before = user.coin_balance
        user.coin_balance += amount
        user.total_earned += amount
        user.save(update_fields=['coin_balance', 'total_earned'])
        return RewardTransaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=user.coin_balance,
            description=description,
            reference_id=reference_id,
        )

    @staticmethod
    @transaction.atomic
    def debit(user, amount: Decimal, transaction_type: str,
              description: str = '', reference_id: str = '') -> RewardTransaction:
        if amount <= 0:
            raise ValueError("Debit amount must be positive.")
        if user.coin_balance < amount:
            raise InsufficientBalance()
        balance_before = user.coin_balance
        user.coin_balance -= amount
        user.save(update_fields=['coin_balance'])
        return RewardTransaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=-amount,
            balance_before=balance_before,
            balance_after=user.coin_balance,
            description=description,
            reference_id=reference_id,
        )


# ===========================================================================
# SUBSCRIPTION SERVICE
# ===========================================================================

class SubscriptionService:

    @staticmethod
    @transaction.atomic
    def create_subscription(user, plan: SubscriptionPlan,
                            gateway_sub_id: str = None) -> UserSubscription:
        existing = UserSubscription.objects.filter(
            user=user,
            status__in=[SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
        ).first()
        if existing:
            raise SubscriptionAlreadyActive()

        now = timezone.now()

        if plan.trial_days > 0:
            status = SubscriptionStatus.TRIAL
            trial_end = now + timezone.timedelta(days=plan.trial_days)
            period_start = trial_end
        else:
            status = SubscriptionStatus.ACTIVE
            trial_end = None
            period_start = now

        if plan.interval == 'monthly':
            period_end = period_start + timezone.timedelta(days=30)
        elif plan.interval == 'yearly':
            period_end = period_start + timezone.timedelta(days=365)
        elif plan.interval == 'weekly':
            period_end = period_start + timezone.timedelta(days=7)
        elif plan.interval == 'daily':
            period_end = period_start + timezone.timedelta(days=1)
        else:  # lifetime
            period_end = period_start + timezone.timedelta(days=36500)

        sub = UserSubscription.objects.create(
            user=user,
            plan=plan,
            status=status,
            started_at=now,
            trial_end_at=trial_end,
            current_period_start=period_start,
            current_period_end=period_end,
            gateway_subscription_id=gateway_sub_id,
        )
        logger.info("Subscription created: user=%s plan=%s", user.id, plan.name)
        return sub

    @staticmethod
    @transaction.atomic
    def cancel_subscription(subscription: UserSubscription, reason: str = '') -> None:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = reason
        subscription.is_auto_renew = False
        subscription.save(update_fields=[
            'status', 'cancelled_at', 'cancellation_reason', 'is_auto_renew', 'updated_at'
        ])
        logger.info("Subscription cancelled: sub=%s", subscription.subscription_id)

    @staticmethod
    @transaction.atomic
    def renew_subscription(subscription: UserSubscription) -> RecurringBilling:
        plan = subscription.plan
        if plan.interval == 'monthly':
            new_end = subscription.current_period_end + timezone.timedelta(days=30)
        elif plan.interval == 'yearly':
            new_end = subscription.current_period_end + timezone.timedelta(days=365)
        elif plan.interval == 'weekly':
            new_end = subscription.current_period_end + timezone.timedelta(days=7)
        else:
            new_end = subscription.current_period_end + timezone.timedelta(days=1)

        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end   = new_end
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.save(update_fields=['current_period_start', 'current_period_end', 'status', 'updated_at'])

        billing = RecurringBilling.objects.create(
            subscription=subscription,
            scheduled_at=timezone.now(),
            amount=plan.price,
            currency=plan.currency,
            status='success',
        )
        return billing


# ===========================================================================
# PAYMENT SERVICE
# ===========================================================================

class PaymentService:

    @staticmethod
    @transaction.atomic
    def create_transaction(user, gateway: str, amount: Decimal,
                           currency: str, purpose: str,
                           related_object_id: str = None) -> PaymentTransaction:
        txn = PaymentTransaction.objects.create(
            user=user,
            gateway=gateway,
            amount=amount,
            currency=currency,
            status=PaymentStatus.INITIATED,
            purpose=purpose,
            related_object_id=related_object_id,
        )
        logger.info("PaymentTransaction created: txn=%s user=%s", txn.txn_id, user.id)
        return txn

    @staticmethod
    @transaction.atomic
    def mark_success(txn: PaymentTransaction, gateway_txn_id: str,
                     gateway_response: dict = None) -> PaymentTransaction:
        txn.status = PaymentStatus.SUCCESS
        txn.gateway_txn_id    = gateway_txn_id
        txn.gateway_response  = gateway_response or {}
        txn.completed_at      = timezone.now()
        txn.save(update_fields=['status', 'gateway_txn_id', 'gateway_response', 'completed_at'])
        return txn

    @staticmethod
    @transaction.atomic
    def mark_failed(txn: PaymentTransaction, reason: str = '') -> PaymentTransaction:
        txn.status = PaymentStatus.FAILED
        txn.failure_reason = reason
        txn.save(update_fields=['status', 'failure_reason'])
        return txn


# ===========================================================================
# GAMIFICATION SERVICE
# ===========================================================================

class GamificationService:

    @staticmethod
    @transaction.atomic
    def spin_wheel(user, ip_address: str = None):
        """Perform a spin wheel action. Returns SpinWheelLog."""
        import random

        today = timezone.now().date()
        today_count = SpinWheelLog.objects.filter(
            user=user, log_type=SpinWheelType.SPIN_WHEEL, played_at__date=today
        ).count()
        if today_count >= SPIN_WHEEL_DAILY_LIMIT:
            raise SpinWheelDailyLimitReached()

        # Prize pool (customise weights as needed)
        PRIZES = [
            (PrizeType.COINS,    Decimal('10'),   30),
            (PrizeType.COINS,    Decimal('50'),   20),
            (PrizeType.COINS,    Decimal('100'),  15),
            (PrizeType.XP,       Decimal('25'),   20),
            (PrizeType.MULTIPLIER, Decimal('1.5'), 5),
            (PrizeType.NO_PRIZE, Decimal('0'),    10),
        ]
        prize_type, prize_value, _ = random.choices(
            PRIZES, weights=[p[2] for p in PRIZES]
        )[0]

        log = SpinWheelLog.objects.create(
            user=user,
            log_type=SpinWheelType.SPIN_WHEEL,
            prize_type=prize_type,
            prize_value=prize_value,
            ip_address=ip_address,
        )

        if prize_type == PrizeType.COINS and prize_value > 0:
            RewardService.credit(
                user, prize_value,
                RewardTransactionType.SPIN_WHEEL,
                description=f"Spin Wheel win: {prize_value} coins",
                reference_id=str(log.id),
            )
            log.is_credited = True
            log.save(update_fields=['is_credited'])

        return log

    @staticmethod
    @transaction.atomic
    def unlock_achievement(user, key: str, title: str, category: str,
                           xp_reward: int = 0, coin_reward: Decimal = Decimal('0'),
                           description: str = '', icon_url: str = None) -> Achievement:
        if Achievement.objects.filter(user=user, achievement_key=key).exists():
            raise AchievementAlreadyUnlocked()

        ach = Achievement.objects.create(
            user=user,
            achievement_key=key,
            title=title,
            description=description,
            category=category,
            icon_url=icon_url,
            xp_reward=xp_reward,
            coin_reward=coin_reward,
        )

        if xp_reward > 0:
            level_obj, _ = UserLevel.objects.get_or_create(user=user)
            level_obj.add_xp(xp_reward)

        if coin_reward > 0:
            RewardService.credit(
                user, coin_reward,
                RewardTransactionType.ACHIEVEMENT,
                description=f"Achievement unlocked: {title}",
                reference_id=str(ach.id),
            )

        return ach

    @staticmethod
    def update_leaderboard_rank(user, scope: str, board_type: str,
                                score: Decimal, period_label: str = None,
                                country: str = None) -> LeaderboardRank:
        """Upsert leaderboard rank for a user. Rank is recalculated afterwards."""
        obj, _ = LeaderboardRank.objects.update_or_create(
            user=user, scope=scope, board_type=board_type, period_label=period_label,
            defaults={'score': score, 'country': country},
        )
        # Recalculate rank in this scope/period
        LeaderboardService.recalculate_ranks(scope, board_type, period_label)
        return obj


# ===========================================================================
# LEADERBOARD SERVICE
# ===========================================================================

class LeaderboardService:

    @staticmethod
    def recalculate_ranks(scope: str, board_type: str, period_label: str = None) -> None:
        qs = LeaderboardRank.objects.filter(
            scope=scope, board_type=board_type, period_label=period_label
        ).order_by('-score')
        updates = []
        for rank, obj in enumerate(qs, start=1):
            obj.rank = rank
            updates.append(obj)
        LeaderboardRank.objects.bulk_update(updates, ['rank'])

    @staticmethod
    def get_top_n(scope: str, board_type: str, n: int = 50, period_label: str = None):
        return LeaderboardRank.objects.filter(
            scope=scope, board_type=board_type, period_label=period_label
        ).select_related('user').order_by('rank')[:n]


# ===========================================================================
# REVENUE SUMMARY SERVICE
# ===========================================================================

class RevenueSummaryService:

    @staticmethod
    def get_or_create_daily_summary(tenant, date, ad_network=None,
                                    campaign=None, country: str = '') -> RevenueDailySummary:
        obj, _ = RevenueDailySummary.objects.get_or_create(
            tenant=tenant,
            ad_network=ad_network,
            campaign=campaign,
            date=date,
            country=country,
        )
        return obj

    @staticmethod
    def update_summary_from_impression(summary: RevenueDailySummary,
                                       revenue: Decimal, ecpm: Decimal) -> None:
        summary.impressions   += 1
        summary.revenue_cpm   += revenue
        summary.total_revenue += revenue
        if summary.impressions > 0:
            summary.ecpm = summary.total_revenue / summary.impressions * 1000
        summary.save(update_fields=[
            'impressions', 'revenue_cpm', 'total_revenue', 'ecpm', 'updated_at'
        ])


# ============================================================================
# NEW SERVICES  (Phase-2)
# ============================================================================

class PostbackService:
    """Validates and processes ad-network postback callbacks."""

    @staticmethod
    @transaction.atomic
    def process(postback_id: int) -> dict:
        from .models import PostbackLog, OfferCompletion
        from django.utils import timezone as tz
        import time

        log = PostbackLog.objects.select_for_update().get(id=postback_id)
        if log.status != 'received':
            return {'status': log.status, 'skipped': True}

        start = time.time()
        log.status = 'processing'
        log.save(update_fields=['status'])

        try:
            network_txn_id = (log.body_parsed or log.query_params or {}).get('txn_id', '') or log.network_txn_id
            if not network_txn_id:
                log.status = 'rejected'
                log.rejection_reason = 'Missing network transaction ID'
                log.save(update_fields=['status', 'rejection_reason', 'processed_at'])
                return {'status': 'rejected', 'reason': 'missing txn_id'}

            # Duplicate check
            existing = OfferCompletion.objects.filter(
                network_transaction_id=network_txn_id
            ).first()
            if existing:
                log.status = 'duplicate'
                log.offer_completion = existing
                log.processed_at = tz.now()
                log.processing_time_ms = int((time.time() - start) * 1000)
                log.save(update_fields=['status', 'offer_completion', 'processed_at', 'processing_time_ms'])
                return {'status': 'duplicate', 'offer_completion_id': existing.id}

            log.status = 'accepted'
            log.processed_at = tz.now()
            log.processing_time_ms = int((time.time() - start) * 1000)
            log.save(update_fields=['status', 'processed_at', 'processing_time_ms'])
            return {'status': 'accepted'}

        except Exception as exc:
            logger.error("PostbackService.process error: %s", exc)
            log.status = 'error'
            log.processing_error = str(exc)
            log.save(update_fields=['status', 'processing_error'])
            raise


class PayoutService:
    """Handles user payout requests end-to-end."""

    @staticmethod
    @transaction.atomic
    def create_request(user, payout_method, coins: Decimal,
                       exchange_rate: Decimal = Decimal('1.00'),
                       processing_fee: Decimal = Decimal('0.00')) -> 'PayoutRequest':
        from .models import PayoutRequest
        from .exceptions import InsufficientBalance

        if user.coin_balance < coins:
            raise InsufficientBalance()

        config = MonetizationConfigService.get(getattr(user, 'tenant', None))
        if coins < config.min_withdrawal_coins:
            from .exceptions import InvalidPaymentAmount
            raise InvalidPaymentAmount(
                f"Minimum withdrawal is {config.min_withdrawal_coins} coins."
            )

        amount_usd   = (coins / config.coins_per_usd).quantize(Decimal('0.0001'))
        amount_local = (amount_usd * exchange_rate).quantize(Decimal('0.01'))
        net_amount   = (amount_local - processing_fee).quantize(Decimal('0.01'))

        # Debit coins
        RewardService.debit(
            user, coins,
            transaction_type='withdrawal',
            description=f"Withdrawal request — {amount_local} {payout_method.currency}",
        )

        return PayoutRequest.objects.create(
            user=user,
            payout_method=payout_method,
            tenant=getattr(user, 'tenant', None),
            coins_deducted=coins,
            amount_usd=amount_usd,
            amount_local=amount_local,
            currency=payout_method.currency,
            exchange_rate=exchange_rate,
            processing_fee=processing_fee,
            net_amount=net_amount,
            status='pending',
        )


class ReferralService:
    """Handles referral program logic."""

    @staticmethod
    def get_or_create_link(user, program) -> 'ReferralLink':
        from .models import ReferralLink
        import random, string
        link, created = ReferralLink.objects.get_or_create(
            user=user, program=program,
            defaults={
                'tenant': program.tenant,
                'code': ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
            }
        )
        return link

    @staticmethod
    @transaction.atomic
    def award_commission(referrer, referee, program, commission_type: str,
                         base_amount: Decimal, level: int = 1) -> 'ReferralCommission':
        from .models import ReferralCommission, ReferralLink

        pct_map = {
            1: program.l1_commission_pct,
            2: program.l2_commission_pct,
            3: program.l3_commission_pct,
            4: program.l4_commission_pct,
            5: program.l5_commission_pct,
        }
        pct   = pct_map.get(level, Decimal('0.00'))
        coins = (base_amount * pct / 100).quantize(Decimal('0.01'))

        link = ReferralLink.objects.filter(user=referrer, program=program).first()
        commission = ReferralCommission.objects.create(
            referrer=referrer,
            referee=referee,
            program=program,
            referral_link=link,
            level=level,
            commission_type=commission_type,
            base_amount=base_amount,
            commission_pct=pct,
            commission_coins=coins,
            tenant=program.tenant,
        )

        if coins > 0:
            RewardService.credit(
                referrer, coins,
                transaction_type='referral_bonus',
                description=f"Referral L{level} commission from {referee.username}",
                reference_id=str(commission.id),
            )

        # Update referral link stats
        if link:
            from django.db.models import F
            ReferralLink.objects.filter(pk=link.pk).update(
                total_earned=F('total_earned') + coins,
                total_conversions=F('total_conversions') + 1,
            )

        return commission

    @staticmethod
    def get_summary(user) -> dict:
        from .models import ReferralCommission, ReferralLink
        from django.db.models import Sum, Count
        links = ReferralLink.objects.filter(user=user)
        commissions = ReferralCommission.objects.filter(referrer=user)
        return {
            'total_referrals':    links.aggregate(s=Sum('total_signups'))['s'] or 0,
            'total_earned':       commissions.aggregate(s=Sum('commission_coins'))['s'] or Decimal('0'),
            'unpaid_commissions': commissions.filter(is_paid=False).aggregate(s=Sum('commission_coins'))['s'] or Decimal('0'),
            'active_links':       links.filter(is_active=True).count(),
        }


class CouponService:
    """Coupon validation and redemption."""

    @staticmethod
    def validate(code: str, user) -> tuple:
        from .models import Coupon
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if not coupon:
            return None, 'Coupon not found.'
        if not coupon.is_valid:
            return None, 'Coupon is expired or fully used.'
        if coupon.min_user_level > 1:
            from .models import UserLevel
            lvl = UserLevel.objects.filter(user=user).first()
            if not lvl or lvl.current_level < coupon.min_user_level:
                return None, f'Requires level {coupon.min_user_level} or above.'
        return coupon, None

    @staticmethod
    @transaction.atomic
    def redeem(code: str, user) -> dict:
        coupon, error = CouponService.validate(code, user)
        if error:
            return {'error': error}

        from .models import CouponUsage
        from django.db.models import F

        usage = CouponUsage.objects.create(
            coupon=coupon, user=user,
            tenant=coupon.tenant,
            coins_granted=coupon.coin_amount,
        )
        Coupon.objects.filter(pk=coupon.pk).update(current_uses=F('current_uses') + 1)

        if coupon.coin_amount > 0:
            RewardService.credit(
                user, coupon.coin_amount,
                transaction_type='promotion',
                description=f"Coupon redeemed: {coupon.code}",
                reference_id=str(usage.id),
            )

        return {
            'coupon_code':    coupon.code,
            'coins_granted':  str(coupon.coin_amount),
            'discount_pct':   str(coupon.discount_pct),
            'free_days':      coupon.free_days,
        }


class MonetizationConfigService:
    """Cached per-tenant config access."""

    @staticmethod
    def get(tenant) -> 'MonetizationConfig':
        from .models import MonetizationConfig
        from django.core.cache import cache
        key = f'mt_config_{getattr(tenant, "id", "none")}'
        cfg = cache.get(key)
        if cfg is None:
            cfg, _ = MonetizationConfig.objects.get_or_create(tenant=tenant)
            cache.set(key, cfg, timeout=300)
        return cfg

    @staticmethod
    def invalidate(tenant):
        from django.core.cache import cache
        cache.delete(f'mt_config_{getattr(tenant, "id", "none")}')


class FraudAlertService:
    """Creates and manages fraud alerts."""

    @staticmethod
    def create_alert(user, alert_type: str, severity: str, description: str,
                     evidence: dict = None, offer_completion=None,
                     postback_log=None, ip_address: str = None,
                     auto_block: bool = False, auto_reject: bool = False) -> 'FraudAlert':
        from .models import FraudAlert

        alert = FraudAlert.objects.create(
            user=user,
            tenant=getattr(user, 'tenant', None),
            alert_type=alert_type,
            severity=severity,
            description=description,
            evidence=evidence or {},
            offer_completion=offer_completion,
            postback_log=postback_log,
            ip_address=ip_address,
            user_blocked=auto_block,
            completion_rejected=auto_reject,
        )

        if auto_block:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=user.pk).update(account_level='blocked')

        if auto_reject and offer_completion:
            from .models import OfferCompletion
            OfferCompletion.objects.filter(pk=offer_completion.pk).update(status='fraud')

        logger.warning("FraudAlert created: user=%s type=%s severity=%s", user.id, alert_type, severity)
        return alert


class DailyStreakService:
    """Daily login streak management."""

    @staticmethod
    @transaction.atomic
    def check_in(user) -> dict:
        from .models import DailyStreak, MonetizationConfig
        streak, _ = DailyStreak.objects.select_for_update().get_or_create(
            user=user, defaults={'tenant': getattr(user, 'tenant', None)}
        )
        result = streak.check_and_update()
        if result.get('already_claimed'):
            return {'already_claimed': True, 'current_streak': streak.current_streak}

        # Calculate streak day reward
        streak_day = streak.current_streak
        coins = DailyStreakService._calculate_reward(streak_day)

        if coins > 0:
            RewardService.credit(
                user, coins,
                transaction_type='streak_reward',
                description=f"Day {streak_day} streak reward",
                reference_id=f"streak_{streak_day}",
            )
            from django.db.models import F
            DailyStreak.objects.filter(pk=streak.pk).update(
                total_streak_coins=F('total_streak_coins') + coins,
                last_reward_date=timezone.now().date(),
            )

        return {
            'current_streak':  streak_day,
            'coins_awarded':   str(coins),
            'streak_broken':   result.get('streak_broken', False),
            'milestones':      DailyStreakService._get_milestones(streak),
        }

    @staticmethod
    def _calculate_reward(day: int) -> Decimal:
        """Base reward + milestone bonuses."""
        base = Decimal('10.00')
        if day >= 365: return Decimal('500.00')
        if day >= 180: return Decimal('200.00')
        if day >= 90:  return Decimal('100.00')
        if day >= 30:  return Decimal('50.00')
        if day >= 14:  return Decimal('30.00')
        if day >= 7:   return Decimal('20.00')
        return base

    @staticmethod
    def _get_milestones(streak) -> list:
        milestones = []
        for days, field in [(7, 'milestone_7'), (14, 'milestone_14'), (30, 'milestone_30'),
                             (60, 'milestone_60'), (90, 'milestone_90'), (180, 'milestone_180'),
                             (365, 'milestone_365')]:
            milestones.append({
                'days': days,
                'achieved': getattr(streak, field, False),
                'remaining': max(0, days - streak.current_streak),
            })
        return milestones


class RevenueGoalService:
    """Tracks and updates revenue goal progress."""

    @staticmethod
    def refresh_all(tenant) -> int:
        """Recalculate current_value for all active goals for a tenant."""
        from .models import RevenueGoal, RevenueDailySummary, UserSubscription
        from django.db.models import Sum, Count
        goals = RevenueGoal.objects.filter(tenant=tenant, is_active=True)
        updated = 0
        for goal in goals:
            value = RevenueGoalService._compute_value(goal, tenant)
            goal.current_value = value
            goal.save(update_fields=['current_value', 'updated_at'])
            updated += 1
        return updated

    @staticmethod
    def _compute_value(goal, tenant) -> Decimal:
        from .models import RevenueDailySummary
        from django.db.models import Sum, Count
        qs = RevenueDailySummary.objects.filter(
            tenant=tenant,
            date__gte=goal.period_start,
            date__lte=goal.period_end,
        )
        if goal.goal_type == 'total_revenue':
            return qs.aggregate(v=Sum('total_revenue'))['v'] or Decimal('0')
        if goal.goal_type == 'ad_revenue':
            return qs.filter(ad_network__isnull=False).aggregate(v=Sum('total_revenue'))['v'] or Decimal('0')
        return Decimal('0')


# ============================================================================
# ADDITIONAL SERVICES  (Performance, Notification, Publisher, Segment, Creative)
# ============================================================================

class AdPerformanceService:
    """Builds and updates AdPerformanceHourly / AdPerformanceDaily rollups."""

    @staticmethod
    @transaction.atomic
    def upsert_hourly(ad_unit, ad_network, hour_bucket, country: str = '',
                      device_type: str = '', impressions: int = 0,
                      clicks: int = 0, conversions: int = 0,
                      revenue_usd: Decimal = Decimal('0')) -> 'AdPerformanceHourly':
        from .models import AdPerformanceHourly
        obj, _ = AdPerformanceHourly.objects.update_or_create(
            tenant=getattr(ad_unit, 'tenant', None),
            ad_unit=ad_unit,
            ad_network=ad_network,
            hour_bucket=hour_bucket,
            country=country or '',
            device_type=device_type or '',
            defaults={
                'impressions': impressions,
                'clicks':      clicks,
                'conversions': conversions,
                'revenue_usd': revenue_usd,
            },
        )
        AdPerformanceHourly.recompute_kpis(obj)
        obj.save(update_fields=['ecpm', 'fill_rate', 'ctr', 'cvr'])
        return obj

    @staticmethod
    def aggregate_daily(date_val, tenant=None) -> int:
        """Aggregate hourly rows into AdPerformanceDaily. Returns count of rows updated."""
        from .models import AdPerformanceHourly, AdPerformanceDaily
        from django.db.models import Sum
        qs = AdPerformanceHourly.objects.filter(hour_bucket__date=date_val)
        if tenant:
            qs = qs.filter(tenant=tenant)
        grouped = (
            qs.values('ad_unit_id', 'ad_network_id', 'country', 'device_type')
              .annotate(
                  impressions=Sum('impressions'), clicks=Sum('clicks'),
                  conversions=Sum('conversions'), installs=Sum('installs'),
                  revenue=Sum('revenue_usd'),
              )
        )
        updated = 0
        for row in grouped:
            ecpm  = (row['revenue'] / row['impressions'] * 1000) if row['impressions'] else Decimal('0')
            ctr   = (Decimal(row['clicks']) / row['impressions'] * 100) if row['impressions'] else Decimal('0')
            AdPerformanceDaily.objects.update_or_create(
                tenant=tenant,
                ad_unit_id=row['ad_unit_id'],
                ad_network_id=row['ad_network_id'],
                date=date_val,
                country=row['country'] or '',
                device_type=row['device_type'] or '',
                defaults={
                    'impressions': row['impressions'],
                    'clicks':      row['clicks'],
                    'conversions': row['conversions'],
                    'total_revenue': row['revenue'],
                    'ecpm':         ecpm.quantize(Decimal('0.0001')),
                    'ctr':          ctr.quantize(Decimal('0.0001')),
                },
            )
            updated += 1
        logger.info("AdPerformanceService.aggregate_daily: %d rows for %s", updated, date_val)
        return updated

    @staticmethod
    def sync_network_stats(network) -> 'AdNetworkDailyStat':
        """Stub for pulling reporting API data from a network."""
        from .models import AdNetworkDailyStat
        from django.utils import timezone
        logger.info("Syncing stats for network: %s", network.display_name)
        # Real implementation calls network.reporting_api_key endpoint
        today = timezone.now().date()
        obj, _ = AdNetworkDailyStat.objects.get_or_create(
            ad_network=network, date=today,
            defaults={'fetched_at': timezone.now()},
        )
        return obj


class NotificationService:
    """Sends monetization notifications using MonetizationNotificationTemplate."""

    @staticmethod
    def send(user, event_type: str, channel: str = 'in_app', context: dict = None,
             tenant=None) -> bool:
        from .models import MonetizationNotificationTemplate
        try:
            tmpl = MonetizationNotificationTemplate.objects.filter(
                tenant=tenant,
                event_type=event_type,
                channel=channel,
                is_active=True,
                language=getattr(user, 'language', 'bn') or 'bn',
            ).first()
            if not tmpl:
                logger.debug("No template for event=%s channel=%s", event_type, channel)
                return False
            rendered = tmpl.render(context or {})
            logger.info("NotificationService.send: user=%s event=%s channel=%s",
                        user.id, event_type, channel)
            # Hook for real notification dispatch (FCM, email, SMS)
            from .events import emit_reward_credited
            return True
        except Exception as exc:
            logger.error("NotificationService.send error: %s", exc)
            return False

    @staticmethod
    def send_bulk(users, event_type: str, channel: str = 'in_app',
                  context: dict = None, tenant=None) -> int:
        count = 0
        for user in users:
            if NotificationService.send(user, event_type, channel, context, tenant):
                count += 1
        return count


class PublisherService:
    """Business logic for PublisherAccount management."""

    @staticmethod
    @transaction.atomic
    def verify_account(account, reviewed_by=None) -> 'PublisherAccount':
        from .models import PublisherAccount
        account.is_verified = True
        account.verified_at = timezone.now()
        account.status      = 'active'
        account.save(update_fields=['is_verified', 'verified_at', 'status', 'updated_at'])
        from .events import emit_publisher_verified
        emit_publisher_verified(str(account.account_id), account.company_name)
        logger.info("Publisher verified: %s", account.company_name)
        return account

    @staticmethod
    @transaction.atomic
    def suspend_account(account, reason: str = '') -> 'PublisherAccount':
        account.status = 'suspended'
        account.notes  = f"{account.notes or ''}\nSuspended: {reason}".strip()
        account.save(update_fields=['status', 'notes', 'updated_at'])
        from .events import emit_publisher_suspended
        emit_publisher_suspended(str(account.account_id), reason)
        logger.warning("Publisher suspended: %s reason=%s", account.company_name, reason)
        return account

    @staticmethod
    def update_spend(account, amount: Decimal) -> None:
        from django.db.models import F
        from .models import PublisherAccount
        PublisherAccount.objects.filter(pk=account.pk).update(
            total_spend_usd=F('total_spend_usd') + amount,
            current_balance_usd=F('current_balance_usd') + amount,
        )

    @staticmethod
    def update_revenue(account, amount: Decimal) -> None:
        from django.db.models import F
        from .models import PublisherAccount
        PublisherAccount.objects.filter(pk=account.pk).update(
            total_revenue_usd=F('total_revenue_usd') + amount,
        )


class SegmentService:
    """User segment management and evaluation."""

    @staticmethod
    def add_user_to_segment(segment, user, score: float = 0.0) -> bool:
        from .repository import SegmentRepository
        created = SegmentRepository.add_user(segment, user, score)
        if created:
            from django.core.cache import cache
            cache.delete(f'mt:seg_members:{segment.id}')
        return created

    @staticmethod
    def remove_user_from_segment(segment, user) -> bool:
        from .models import UserSegmentMembership
        from django.db.models import F
        deleted, _ = UserSegmentMembership.objects.filter(
            segment=segment, user=user
        ).delete()
        if deleted:
            from .models import UserSegment
            UserSegment.objects.filter(pk=segment.pk).update(
                member_count=F('member_count') - 1
            )
        return bool(deleted)

    @staticmethod
    def get_user_segment_slugs(user) -> list:
        from .repository import SegmentRepository
        return list(SegmentRepository.user_segments(user))

    @staticmethod
    def recompute_dynamic_segment(segment) -> int:
        """
        Re-evaluate all memberships for a dynamic segment.
        Returns number of members after recomputation.
        """
        from .models import UserSegmentMembership
        from django.utils import timezone
        logger.info("Recomputing segment: %s", segment.name)
        count = UserSegmentMembership.objects.filter(segment=segment).count()
        segment.member_count  = count
        segment.last_computed = timezone.now()
        segment.save(update_fields=['member_count', 'last_computed'])
        return count


class CreativeService:
    """Ad creative lifecycle management."""

    @staticmethod
    @transaction.atomic
    def approve(creative, reviewed_by=None) -> 'AdCreative':
        creative.status      = 'approved'
        creative.reviewed_by = reviewed_by
        creative.rejection_reason = None
        creative.save(update_fields=['status', 'reviewed_by', 'rejection_reason', 'updated_at'])
        from .events import emit_creative_approved
        emit_creative_approved(str(creative.creative_id), creative.ad_unit_id)
        return creative

    @staticmethod
    @transaction.atomic
    def reject(creative, reason: str, reviewed_by=None) -> 'AdCreative':
        creative.status           = 'rejected'
        creative.reviewed_by      = reviewed_by
        creative.rejection_reason = reason
        creative.save(update_fields=['status', 'reviewed_by', 'rejection_reason', 'updated_at'])
        from .events import emit_creative_rejected
        emit_creative_rejected(str(creative.creative_id), reason)
        return creative

    @staticmethod
    def get_approved_for_unit(ad_unit_id, creative_type: str = None):
        from .models import AdCreative
        qs = AdCreative.objects.filter(ad_unit_id=ad_unit_id, status='approved', is_active=True)
        if creative_type:
            qs = qs.filter(creative_type=creative_type)
        return qs.order_by('-clicks')

    @staticmethod
    def update_counters(creative_id: int, impressions: int = 0,
                        clicks: int = 0, revenue: Decimal = Decimal('0')) -> None:
        from .models import AdCreative
        from django.db.models import F
        AdCreative.objects.filter(pk=creative_id).update(
            impressions=F('impressions') + impressions,
            clicks=F('clicks') + clicks,
            revenue=F('revenue') + revenue,
        )


# ── Per-model service methods for remaining gaps ─────────────────────────────

class AdUnitService:
    """AdUnit lifecycle and counter management."""

    @staticmethod
    @transaction.atomic
    def update_counters(unit_id: int, impressions: int = 0,
                        clicks: int = 0, revenue: Decimal = Decimal('0')) -> None:
        from .models import AdUnit
        from django.db.models import F
        AdUnit.objects.filter(pk=unit_id).update(
            impressions=F('impressions') + impressions,
            clicks=F('clicks') + clicks,
            revenue=F('revenue') + revenue,
        )

    @staticmethod
    def get_active_for_campaign(campaign_id):
        from .models import AdUnit
        return AdUnit.objects.filter(campaign_id=campaign_id, is_active=True)


class AdPlacementService:
    """AdPlacement lookup and management."""

    @staticmethod
    def get_by_key(placement_key: str, tenant=None):
        from .models import AdPlacement
        qs = AdPlacement.objects.filter(placement_key=placement_key, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related('ad_unit', 'ad_network').first()

    @staticmethod
    def get_for_screen(screen_name: str, tenant=None):
        from .models import AdPlacement
        qs = AdPlacement.objects.filter(screen_name=screen_name, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related('ad_unit', 'ad_network').order_by('position')


class OfferwallService:
    """Offerwall display and configuration."""

    @staticmethod
    def get_active(tenant=None):
        from .models import Offerwall
        qs = Offerwall.objects.filter(is_active=True).select_related('network')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('sort_order', 'name')

    @staticmethod
    def get_offers(offerwall_id, user=None, country: str = None, device_type: str = None):
        from .models import Offer, OfferCompletion
        from django.utils import timezone as tz
        now = tz.now()
        qs  = Offer.objects.filter(
            offerwall_id=offerwall_id, status='active',
        ).filter(
            models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gt=now)
        ).filter(
            models.Q(available_from__isnull=True) | models.Q(available_from__lte=now)
        )
        if country:
            qs = qs.filter(
                models.Q(target_countries=[]) |
                models.Q(target_countries__contains=[country.upper()])
            )
        if device_type:
            qs = qs.filter(
                models.Q(target_devices=[]) |
                models.Q(target_devices__contains=[device_type.lower()])
            )
        if user:
            completed_ids = OfferCompletion.objects.filter(
                user=user, status='approved'
            ).values_list('offer_id', flat=True)
            qs = qs.exclude(id__in=completed_ids)
        return qs.order_by('-is_featured', '-is_hot', '-point_value')


class SpinWheelConfigService:
    """Spin Wheel & Scratch Card prize pool logic."""

    @staticmethod
    def get_active_config(wheel_type: str = 'spin_wheel', tenant=None):
        from .models import SpinWheelConfig
        from django.utils import timezone as tz
        now = tz.now()
        qs  = SpinWheelConfig.objects.filter(
            is_active=True, wheel_type=wheel_type
        ).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def pick_prize(config):
        """Weighted random prize selection."""
        import random
        from .models import PrizeConfig
        prizes = list(PrizeConfig.objects.filter(
            wheel_config=config, is_active=True
        ).order_by('id'))
        if not prizes:
            return None
        weights = [p.weight for p in prizes]
        return random.choices(prizes, weights=weights, k=1)[0]

    @staticmethod
    @transaction.atomic
    def play(user, wheel_type: str = 'spin_wheel', ip_address: str = '') -> dict:
        from .models import SpinWheelLog
        from .enums import SpinWheelType, PrizeType
        from .exceptions import SpinWheelDailyLimitReached, ScratchCardDailyLimitReached

        config = SpinWheelConfigService.get_active_config(
            wheel_type, getattr(user, 'tenant', None)
        )
        if not config:
            return {'error': 'No active wheel configuration.'}

        # Check daily limit
        from django.utils import timezone as tz
        today_count = SpinWheelLog.objects.filter(
            user=user, log_type=wheel_type,
            played_at__date=tz.now().date()
        ).count()

        if today_count >= config.daily_limit:
            if wheel_type == 'spin_wheel':
                raise SpinWheelDailyLimitReached()
            raise ScratchCardDailyLimitReached()

        # Check cost
        if config.cost_per_spin > 0:
            RewardService.debit(
                user, config.cost_per_spin,
                transaction_type='withdrawal',
                description=f"{wheel_type} spin cost",
            )

        # Pick prize
        prize = SpinWheelConfigService.pick_prize(config)
        prize_type  = prize.prize_type if prize else 'no_prize'
        prize_value = prize.prize_value if prize else Decimal('0.00')
        result_label = prize.label if prize else 'Better luck next time!'

        log = SpinWheelLog.objects.create(
            user=user, log_type=wheel_type,
            prize_type=prize_type, prize_value=prize_value,
            result_label=result_label, ip_address=ip_address,
            tenant=getattr(user, 'tenant', None),
        )

        if prize_type == 'coins' and prize_value > 0:
            RewardService.credit(
                user, prize_value,
                transaction_type='spin_wheel',
                description=f"{wheel_type} win: {prize_value} coins",
                reference_id=str(log.id),
            )
            SpinWheelLog.objects.filter(pk=log.pk).update(is_credited=True)

        from .events import emit_spin_wheel_played
        emit_spin_wheel_played(user.id, prize_type, prize_value)

        return {
            'prize_type':   prize_type,
            'prize_value':  str(prize_value),
            'result_label': result_label,
            'log_id':       log.id,
        }


class RevenueDailySummaryService:
    """Daily summary management."""

    @staticmethod
    def get_mtd(tenant=None) -> dict:
        from .models import RevenueDailySummary
        from django.db.models import Sum, Avg
        from django.utils import timezone as tz
        today = tz.now().date()
        qs    = RevenueDailySummary.objects.filter(
            date__year=today.year, date__month=today.month
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.aggregate(
            total_revenue=Sum('total_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            avg_ecpm=Avg('ecpm'),
            avg_ctr=Avg('ctr'),
        )

    @staticmethod
    def get_trend(tenant=None, days: int = 30):
        from .models import RevenueDailySummary
        from django.db.models import Sum
        from django.utils import timezone as tz
        from datetime import timedelta
        cutoff = tz.now().date() - timedelta(days=days)
        qs     = RevenueDailySummary.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return (
            qs.values('date')
              .annotate(revenue=Sum('total_revenue'), impressions=Sum('impressions'))
              .order_by('date')
        )


class PointLedgerService:
    """Point ledger snapshot and balance management."""

    @staticmethod
    def take_snapshot(user) -> 'PointLedgerSnapshot':
        from .models import PointLedgerSnapshot
        from django.utils import timezone as tz
        obj, _ = PointLedgerSnapshot.objects.update_or_create(
            user=user, snapshot_date=tz.now().date(),
            defaults={
                'balance':      user.coin_balance,
                'total_earned': user.total_earned,
                'tenant':       getattr(user, 'tenant', None),
            },
        )
        return obj


class ImpressionClickService:
    """Log impression and click events."""

    @staticmethod
    def log_impression(ad_unit, placement=None, ad_network=None, user=None,
                       country: str = '', device_type: str = '', os: str = '',
                       ecpm: Decimal = Decimal('0'), revenue: Decimal = Decimal('0'),
                       is_viewable: bool = True, is_bot: bool = False,
                       session_id: str = '', ip_address: str = '') -> 'ImpressionLog':
        from .models import ImpressionLog
        return ImpressionLog.objects.create(
            ad_unit=ad_unit, placement=placement, ad_network=ad_network, user=user,
            tenant=getattr(ad_unit, 'tenant', None),
            country=country or '', device_type=device_type or '', os=os or '',
            ecpm=ecpm, revenue=revenue, is_viewable=is_viewable, is_bot=is_bot,
            session_id=session_id or '', ip_address=ip_address or '127.0.0.1',
        )

    @staticmethod
    def log_click(ad_unit, impression=None, user=None,
                  country: str = '', device_type: str = '',
                  revenue: Decimal = Decimal('0'),
                  is_valid: bool = True, ip_address: str = '') -> 'ClickLog':
        from .models import ClickLog
        return ClickLog.objects.create(
            ad_unit=ad_unit, impression=impression, user=user,
            tenant=getattr(ad_unit, 'tenant', None),
            country=country or '', device_type=device_type or '',
            revenue=revenue, is_valid=is_valid,
            ip_address=ip_address or '127.0.0.1',
        )


class ConversionService:
    """Log and verify conversions."""

    @staticmethod
    def log_conversion(campaign, conversion_type: str,
                       click=None, user=None,
                       payout: Decimal = Decimal('0'),
                       is_verified: bool = False) -> 'ConversionLog':
        from .models import ConversionLog
        return ConversionLog.objects.create(
            campaign=campaign, click=click, user=user,
            tenant=getattr(campaign, 'tenant', None),
            conversion_type=conversion_type,
            payout=payout, is_verified=is_verified,
        )


class InAppPurchaseService:
    """Handle in-app purchase fulfilment."""

    @staticmethod
    @transaction.atomic
    def fulfil(purchase) -> bool:
        from .models import InAppPurchase
        from django.utils import timezone as tz
        if purchase.status != 'completed':
            return False
        if purchase.fulfilled_at:
            return False  # already fulfilled
        if purchase.coins_granted > 0:
            RewardService.credit(
                purchase.user, purchase.coins_granted,
                transaction_type='subscription',
                description=f"IAP fulfilled: {purchase.product_name}",
                reference_id=str(purchase.purchase_id),
            )
        InAppPurchase.objects.filter(pk=purchase.pk).update(fulfilled_at=tz.now())
        return True


class PayoutMethodService:
    """Manage user payout methods."""

    @staticmethod
    @transaction.atomic
    def set_default(user, method) -> None:
        from .models import PayoutMethod
        PayoutMethod.objects.filter(user=user, is_default=True).update(is_default=False)
        PayoutMethod.objects.filter(pk=method.pk).update(is_default=True)

    @staticmethod
    def verify(method, verified_by=None) -> None:
        from .models import PayoutMethod
        from django.utils import timezone as tz
        PayoutMethod.objects.filter(pk=method.pk).update(
            is_verified=True, verified_at=tz.now()
        )


class ReferralProgramService:
    """Referral program lifecycle."""

    @staticmethod
    def get_active(tenant=None):
        from .models import ReferralProgram
        from django.utils import timezone as tz
        now = tz.now()
        qs  = ReferralProgram.objects.filter(is_active=True).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def award_signup_bonus(program, referrer, referee) -> dict:
        result = {}
        if program.referrer_bonus_coins > 0:
            RewardService.credit(
                referrer, program.referrer_bonus_coins,
                transaction_type='referral_bonus',
                description=f"Referral signup bonus: {referee.username}",
            )
            result['referrer_coins'] = program.referrer_bonus_coins
        if program.referee_bonus_coins > 0:
            RewardService.credit(
                referee, program.referee_bonus_coins,
                transaction_type='referral_bonus',
                description=f"Welcome bonus via referral",
            )
            result['referee_coins'] = program.referee_bonus_coins
        return result


class FlashSaleService:
    """Flash sale management."""

    @staticmethod
    def get_live(tenant=None):
        from .models import FlashSale
        from django.utils import timezone as tz
        now = tz.now()
        qs  = FlashSale.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-multiplier')

    @staticmethod
    def get_best_multiplier(tenant=None, offer_type: str = None) -> Decimal:
        sales = FlashSaleService.get_live(tenant).filter(
            sale_type__in=['offer_boost', 'double_points']
        )
        if offer_type:
            sales = sales.filter(
                models.Q(target_offer_types=[]) |
                models.Q(target_offer_types__contains=[offer_type])
            )
        result = sales.order_by('-multiplier').values_list('multiplier', flat=True).first()
        return result or Decimal('1.00')


class WaterfallService:
    """Mediation waterfall ordering."""

    @staticmethod
    def get_ordered(ad_unit_id, floor_ecpm: Decimal = Decimal('0')) -> list:
        from .models import WaterfallConfig
        return list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True,
                floor_ecpm__lte=floor_ecpm if floor_ecpm else Decimal('99999'),
            ).select_related('ad_network').order_by('priority')
        )


class ABTestService:
    """A/B test assignment and results."""

    @staticmethod
    def assign_user(test, user):
        from .DATABASE_MODELS import ABTestAssignmentManager
        from .models import ABTestAssignment
        mgr = ABTestAssignmentManager()
        mgr.model = ABTestAssignment
        return mgr.get_or_assign(test, user)

    @staticmethod
    def declare_winner(test, variant_name: str) -> None:
        from .models import ABTest
        from django.utils import timezone as tz
        ABTest.objects.filter(pk=test.pk).update(
            status='completed',
            winner_variant=variant_name,
            ended_at=tz.now(),
        )
        from .events import emit_ab_test_winner
        emit_ab_test_winner(str(test.test_id), test.name, variant_name, test.winner_criteria)


class RevenueSummaryExtService:
    """Extra Revenue Daily Summary helpers."""

    @staticmethod
    def get_revenue_daily_summary(tenant=None, start=None, end=None):
        from .models import RevenueDailySummary
        qs = RevenueDailySummary.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.order_by('-date')
