# api/referral/services/CommissionService.py
# Commission calculation, hold, and release logic
# ============================================================

from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import logging
from api.referral.models.commission import CommissionLog
from api.referral.models.commission import CommissionRule

logger = logging.getLogger(__name__)


class CommissionService:
    """
    Commission lifecycle management।
    Create → Hold → Release → Payout
    """

    @staticmethod
    @transaction.atomic
    def create_commission_log(
        user,
        referred_user,
        amount: Decimal,
        base_amount: Decimal,
        commission_rate: Decimal,
        level: int,
        action_type: str = 'task',
        source_reference: str = '',
        hold_days: int = 0,
        campaign=None,
        rule=None,
    ) -> 'CommissionLog':
        """
        CommissionLog তৈরি করো।
        hold_days > 0 হলে CommissionHold তৈরি করো।
        """
        from api.referral.models import CommissionLog, CommissionHold

        status = 'held' if hold_days > 0 else 'pending'

        log = CommissionLog.objects.create(
            user=user,
            referred_user=referred_user,
            amount=amount,
            base_amount=base_amount,
            commission_rate=commission_rate,
            level=level,
            action_type=action_type,
            source_reference=source_reference,
            campaign=campaign,
            rule=rule,
            status=status,
        )

        if hold_days > 0:
            release_at = timezone.now() + timedelta(days=hold_days)
            CommissionHold.objects.create(
                commission=log,
                hold_days=hold_days,
                release_at=release_at,
                reason='new_user',
            )
            logger.info(
                f"Commission held: {log.id} for {user.username}, "
                f"release at {release_at.date()}"
            )

        return log

    @staticmethod
    def get_pending_commissions(user) -> list:
        """User এর pending/held commissions।"""
        from api.referral.models import CommissionLog
        from django.db.models import Sum

        qs = CommissionLog.objects.filter(
            user=user,
            status__in=['pending', 'held']
        ).order_by('-created_at')

        total_pending = qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        return {
            'total_pending': float(total_pending),
            'commissions': [{
                'id': c.id,
                'amount': float(c.amount),
                'level': c.level,
                'action_type': c.action_type,
                'status': c.status,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
                'release_at': (
                    c.hold.release_at.strftime('%Y-%m-%d')
                    if hasattr(c, 'hold') and c.hold else None
                ),
            } for c in qs[:50]]
        }

    @staticmethod
    @transaction.atomic
    def release_held_commission(commission_log_id: int, admin_user=None) -> dict:
        """
        Specific commission hold release করো।
        Wallet এ add করো।
        """
        from api.referral.models import CommissionLog, CommissionHold

        try:
            log = CommissionLog.objects.select_related(
                'user', 'hold'
            ).get(id=commission_log_id, status='held')
        except CommissionLog.DoesNotExist:
            return {'success': False, 'error': 'Commission not found or not held'}

        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            wallet, _ = Wallet.objects.get_or_create(user=log.user)
            wallet_txn = WalletService.add_earnings(
                wallet=wallet,
                amount=log.amount,
                description=(
                    f"Level {log.level} referral commission released "
                    f"(from {log.referred_user.username})"
                ),
                source_type='referral_commission_released',
                source_id=str(log.referred_user.id),
            )

            log.status = 'released'
            log.wallet_transaction_id = str(
                getattr(wallet_txn, 'walletTransaction_id', '')
            )
            log.save(update_fields=['status', 'wallet_transaction_id'])

            # Hold record update
            if hasattr(log, 'hold'):
                log.hold.release(released_by=admin_user)

            logger.info(
                f"Commission released: {log.id} → "
                f"{log.user.username} +{log.amount}"
            )

            return {
                'success': True,
                'commission_id': log.id,
                'amount': float(log.amount),
                'user': log.user.username,
            }

        except Exception as e:
            logger.error(f"Commission release error: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def release_expired_holds(dry_run: bool = False) -> dict:
        """
        Hold period শেষ হয়ে গেছে এমন সব commissions release করো।
        Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import CommissionHold

        now = timezone.now()
        ready_holds = CommissionHold.objects.filter(
            is_released=False,
            release_at__lte=now,
            commission__status='held',
        ).select_related('commission', 'commission__user')

        released = 0
        errors = 0
        total_amount = Decimal('0')

        for hold in ready_holds:
            if dry_run:
                released += 1
                total_amount += hold.commission.amount
                continue

            result = CommissionService.release_held_commission(
                hold.commission.id
            )
            if result['success']:
                released += 1
                total_amount += hold.commission.amount
            else:
                errors += 1

        return {
            'released': released,
            'errors': errors,
            'total_amount': float(total_amount),
            'dry_run': dry_run,
        }

    @staticmethod
    @transaction.atomic
    def create_payout(user, period: str = 'weekly') -> dict:
        """
        User এর সব released commissions batch করে payout করো।
        """
        from api.referral.models import CommissionLog, CommissionPayout
        from django.db.models import Sum

        released_logs = CommissionLog.objects.filter(
            user=user,
            status='released',
            payouts__isnull=True,  # Not yet in any payout
        )

        total = released_logs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        if total <= 0:
            return {'success': False, 'reason': 'No released commissions to pay'}

        payout = CommissionPayout.objects.create(
            user=user,
            total_amount=total,
            period=period,
        )
        payout.commission_logs.set(released_logs)

        logger.info(
            f"Payout created: {user.username} ৳{total} [{period}]"
        )

        return {
            'success': True,
            'payout_id': payout.id,
            'total_amount': float(total),
            'commission_count': released_logs.count(),
        }

    @staticmethod
    def get_commission_summary(user, days: int = 30) -> dict:
        """User এর commission summary।"""
        from api.referral.models import CommissionLog
        from django.db.models import Sum, Count, Q

        cutoff = timezone.now() - timedelta(days=days)

        qs = CommissionLog.objects.filter(
            user=user,
            created_at__gte=cutoff,
        )

        agg = qs.aggregate(
            total=Sum('amount'),
            pending=Sum('amount', filter=Q(status='pending')),
            held=Sum('amount', filter=Q(status='held')),
            released=Sum('amount', filter=Q(status='released')),
            clawed_back=Sum('amount', filter=Q(status='clawed_back')),
            count=Count('id'),
        )

        return {
            'period_days': days,
            'total': float(agg['total'] or 0),
            'pending': float(agg['pending'] or 0),
            'held': float(agg['held'] or 0),
            'released': float(agg['released'] or 0),
            'clawed_back': float(agg['clawed_back'] or 0),
            'transaction_count': agg['count'] or 0,
        }

    @staticmethod
    def get_applicable_rule(level: int, action_type: str) -> 'CommissionRule | None':
        """
        Level + action_type এর জন্য সবচেয়ে priority অনুযায়ী rule দাও।
        """
        from api.referral.models import CommissionRule

        rule = CommissionRule.objects.filter(
            level=level,
            action_type__in=[action_type, 'any'],
            is_active=True,
        ).order_by('-priority').first()

        return rule

    @staticmethod
    def calculate_commission_amount(
        base_amount: Decimal,
        level: int,
        action_type: str = 'task',
    ) -> tuple:
        """
        Commission amount calculate করো।
        Returns (amount, rate, rule_used)
        Fallback: ReferralSettings এ defined rate।
        """
        from django.core.cache import cache

        # Try rule-based calculation first
        rule = CommissionService.get_applicable_rule(level, action_type)
        if rule:
            amount = rule.calculate_commission(base_amount)
            return amount, rule.rate_value, rule

        # Fallback to settings
        cached = cache.get('referral_settings')
        if cached:
            settings = cached
        else:
            from api.referral.models import ReferralSettings
            settings = ReferralSettings.objects.first()

        if settings:
            rate = settings.get_rate_for_level(level)
            amount = (base_amount * rate / 100).quantize(Decimal('0.01'))
            return amount, rate, None

        return Decimal('0'), Decimal('0'), None