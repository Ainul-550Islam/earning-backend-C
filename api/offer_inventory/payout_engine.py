# api/offer_inventory/payout_engine.py
"""
Payout Engine — Bulletproof Payment Processing.

Guarantees:
  1. একজন user-কে একই conversion-এর জন্য দুইবার pay করা IMPOSSIBLE
     (select_for_update + paid_flag + DB constraint)
  2. সব amount Decimal — কোনো floating-point error নেই
  3. Wallet credit ও Conversion status update একই atomic transaction-এ
  4. Failure হলে সম্পূর্ণ rollback — partial state নেই
  5. Audit trail — প্রতিটি payout immutable log-এ থাকে
"""
import logging
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.core.cache import cache

from .models import (
    Conversion, ConversionStatus, WalletTransaction, WalletAudit,
    ReferralCommission, UserReferral, RevenueShare, BonusWallet,
)
from .exceptions import (
    InsufficientBalanceException,
    WalletLockedException,
    DuplicateConversionException,
)
from .finance_payment.revenue_calculator import RevenueCalculator, RevenueBreakdown

logger = logging.getLogger(__name__)

# ── Precision ────────────────────────────────────────────────────
PAYOUT_PRECISION = Decimal('0.0001')    # 4 decimal places


def to_decimal(value, default: str = '0') -> Decimal:
    """Safe Decimal conversion — never raises, never uses float."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)).quantize(PAYOUT_PRECISION, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default).quantize(PAYOUT_PRECISION)


# ════════════════════════════════════════════════════════════════
# PAYOUT GUARD  — prevents double-pay
# ════════════════════════════════════════════════════════════════

class PayoutGuard:
    """
    Two-phase guard against double payment:
      Phase 1: Redis lock (fast, cross-process)
      Phase 2: DB select_for_update on Conversion (row-level lock)
    """

    LOCK_TTL = 30  # seconds

    @staticmethod
    @contextmanager
    def acquire(conversion_id: str):
        lock_key = f'payout_lock:{conversion_id}'
        acquired = cache.add(lock_key, '1', PayoutGuard.LOCK_TTL)
        if not acquired:
            raise DuplicateConversionException(
                f'Payout for conversion {conversion_id} is already processing.'
            )
        try:
            yield
        finally:
            cache.delete(lock_key)

    @staticmethod
    def already_paid(conversion_id: str) -> bool:
        """Cache check — fastest path."""
        return bool(cache.get(f'payout_done:{conversion_id}'))

    @staticmethod
    def mark_paid(conversion_id: str):
        """Successful payout mark করো।"""
        cache.set(f'payout_done:{conversion_id}', '1', 86400 * 7)  # 7 days


# ════════════════════════════════════════════════════════════════
# PAYOUT ENGINE
# ════════════════════════════════════════════════════════════════

class PayoutEngine:
    """
    Processes approved conversions → credits user wallet.

    Call flow:
        PayoutEngine.pay_conversion(conversion_id)
            → PayoutGuard.already_paid? → skip
            → acquire Redis lock
            → DB transaction:
                → select_for_update Conversion
                → verify status == 'approved', not already paid
                → credit wallet (atomic)
                → update Conversion.approved_at
                → write RevenueShare + WalletAudit
                → process referral commission
            → mark paid in cache
            → release lock
    """

    @classmethod
    def pay_conversion(cls, conversion_id: str) -> Optional[dict]:
        """
        Pay a user for an approved conversion.

        Returns payout summary dict, or None if already paid.
        Raises DuplicateConversionException on race condition.
        """
        # ── Fast cache check ──────────────────────────────────────
        if PayoutGuard.already_paid(conversion_id):
            logger.info(f'Payout skipped (cache): {conversion_id}')
            return None

        # ── Acquire distributed lock ──────────────────────────────
        with PayoutGuard.acquire(conversion_id):
            return cls._execute_payout(conversion_id)

    @classmethod
    @transaction.atomic
    def _execute_payout(cls, conversion_id: str) -> dict:
        """Atomic payout execution."""

        # ── Lock Conversion row ────────────────────────────────────
        try:
            conversion = (
                Conversion.objects
                .select_for_update(nowait=True)
                .select_related('offer', 'user', 'status', 'offer__network')
                .get(id=conversion_id)
            )
        except Conversion.DoesNotExist:
            raise ValueError(f'Conversion {conversion_id} not found.')
        except Exception:
            raise DuplicateConversionException(
                'Conversion row is locked by another process.'
            )

        # ── Guard: already paid? ──────────────────────────────────
        if conversion.approved_at is not None:
            # approved_at being set = payout already done
            PayoutGuard.mark_paid(conversion_id)
            logger.warning(f'Payout already done: {conversion_id}')
            return None

        if not conversion.status or conversion.status.name != 'approved':
            raise ValueError(
                f'Cannot pay conversion {conversion_id}: '
                f'status is {conversion.status.name if conversion.status else "unknown"}'
            )

        user  = conversion.user
        offer = conversion.offer

        if not user:
            raise ValueError(f'Conversion {conversion_id} has no user.')

        # ── Calculate amounts (all Decimal) ───────────────────────
        breakdown = cls._get_breakdown(conversion)

        # ── Credit wallet (atomic, row-locked) ───────────────────
        cls._credit_wallet(
            user           = user,
            amount         = breakdown.net_to_user,
            source         = 'conversion',
            source_id      = str(conversion.id),
            description    = f'অফার সম্পন্ন: {offer.title if offer else "Unknown"}',
        )

        # ── Stamp approved_at (idempotency sentinel) ──────────────
        Conversion.objects.filter(id=conversion_id).update(
            approved_at=timezone.now()
        )

        # ── Record revenue share ───────────────────────────────────
        cls._record_revenue_share(conversion, breakdown)

        # ── Process referral commission ───────────────────────────
        referral_paid = Decimal('0')
        if breakdown.referral_bonus > 0:
            referral_paid = cls._pay_referral(user, conversion, breakdown)

        # ── Audit log (immutable) ──────────────────────────────────
        cls._write_audit(user, conversion, breakdown)

        # ── Mark paid in cache ────────────────────────────────────
        PayoutGuard.mark_paid(conversion_id)

        summary = {
            'conversion_id'  : str(conversion.id),
            'user_id'        : str(user.id),
            'gross_revenue'  : str(breakdown.gross_revenue),
            'platform_cut'   : str(breakdown.platform_cut),
            'user_reward'    : str(breakdown.net_to_user),
            'referral_paid'  : str(referral_paid),
            'tax_amount'     : str(breakdown.tax_amount),
        }
        logger.info(f'Payout complete: {summary}')
        return summary

    # ── Credit wallet ──────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def _credit_wallet(user, amount: Decimal, source: str,
                       source_id: str, description: str):
        """
        Credit user wallet — select_for_update prevents concurrent updates.
        Works with both api.wallet.models.Wallet and WalletTransaction direct.
        """
        from django.core.cache import cache as _cache

        amount = to_decimal(amount)

        # Try api.wallet app first, fall back to direct WalletTransaction
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.select_for_update().get(user=user)

            if wallet.is_locked:
                raise WalletLockedException(
                    f'Wallet for user {user.id} is locked.'
                )

            before = to_decimal(wallet.current_balance)
            after  = before + amount

            Wallet.objects.filter(id=wallet.id).update(
                current_balance=F('current_balance') + amount,
                total_earned   =F('total_earned')    + amount,
                updated_at     =timezone.now(),
            )
        except ImportError:
            # api.wallet not installed — use WalletTransaction direct
            before = to_decimal(0)
            after  = amount

        WalletTransaction.objects.create(
            user            = user,
            tx_type         = 'credit',
            amount          = amount,
            description     = description,
            source          = source,
            source_id       = source_id,
            balance_snapshot= after,
        )

    # ── Revenue Share ──────────────────────────────────────────────

    @staticmethod
    def _get_breakdown(conversion: Conversion) -> RevenueBreakdown:
        """Recalculate breakdown from Conversion amounts (Decimal-safe)."""
        gross    = to_decimal(conversion.payout_amount)
        user_net = to_decimal(conversion.reward_amount)
        platform = (gross - user_net).quantize(PAYOUT_PRECISION)

        from api.offer_inventory.models import UserReferral
        has_referral = UserReferral.objects.filter(referred=conversion.user).exists()

        # Use stored amounts — RevenueCalculator already ran at conversion time
        # Just re-derive referral split from net_to_user
        from .constants import DEFAULT_REFERRAL_PCT
        referral_bonus = Decimal('0')
        if has_referral:
            referral_bonus = (
                user_net * Decimal(str(DEFAULT_REFERRAL_PCT)) / Decimal('100')
            ).quantize(PAYOUT_PRECISION, rounding=ROUND_HALF_UP)

        return RevenueBreakdown(
            gross_revenue  = gross,
            platform_cut   = platform,
            user_reward    = user_net,
            referral_bonus = referral_bonus,
            tax_amount     = Decimal('0'),
            net_to_user    = user_net,
        )

    @staticmethod
    def _record_revenue_share(conversion: Conversion, breakdown: RevenueBreakdown):
        RevenueShare.objects.get_or_create(
            conversion=conversion,
            defaults={
                'offer'        : conversion.offer,
                'gross_revenue': breakdown.gross_revenue,
                'platform_cut' : breakdown.platform_cut,
                'user_share'   : breakdown.net_to_user,
                'referral_share': breakdown.referral_bonus,
            }
        )

    # ── Referral Commission ────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def _pay_referral(user, conversion: Conversion, breakdown: RevenueBreakdown) -> Decimal:
        """
        Pay referrer commission.
        Calculated on user_reward AFTER platform fee deduction.
        """
        try:
            referral = UserReferral.objects.select_for_update().get(referred=user)
        except UserReferral.DoesNotExist:
            return Decimal('0')

        commission = breakdown.referral_bonus
        if commission <= 0:
            return Decimal('0')

        # Prevent double-commission
        already = ReferralCommission.objects.filter(
            conversion=conversion, referrer=referral.referrer
        ).exists()
        if already:
            return Decimal('0')

        # Record commission
        ReferralCommission.objects.create(
            referrer      = referral.referrer,
            referred_user = user,
            conversion    = conversion,
            commission_pct= Decimal('5'),   # from constants
            amount        = commission,
            is_paid       = True,
            paid_at       = timezone.now(),
        )

        # Credit referrer wallet
        PayoutEngine._credit_wallet(
            user        = referral.referrer,
            amount      = commission,
            source      = 'referral_commission',
            source_id   = str(conversion.id),
            description = (
                f'Referral commission: {user.username} completed '
                f'{conversion.offer.title if conversion.offer else "an offer"}'
            ),
        )

        # Update lifetime referral earnings
        UserReferral.objects.filter(id=referral.id).update(
            total_earnings_generated=F('total_earnings_generated') + commission
        )

        logger.info(
            f'Referral commission paid: {commission} '
            f'to {referral.referrer.username} '
            f'for conversion {conversion.id}'
        )
        return commission

    # ── Audit ──────────────────────────────────────────────────────

    @staticmethod
    def _write_audit(user, conversion: Conversion, breakdown: RevenueBreakdown):
        """Immutable audit trail। এটি কখনো delete/update করা হয় না।"""
        balance_after = breakdown.net_to_user
        try:
            from api.wallet.models import Wallet
            wallet        = Wallet.objects.get(user=user)
            balance_after = to_decimal(wallet.current_balance)
        except Exception:
            # api.wallet not installed — derive from WalletTransaction
            try:
                from django.db.models import Sum
                total = WalletTransaction.objects.filter(
                    user=user, tx_type='credit'
                ).aggregate(t=Sum('amount'))['t']
                balance_after = to_decimal(total or breakdown.net_to_user)
            except Exception:
                balance_after = breakdown.net_to_user

        WalletAudit.objects.create(
            user             = user,
            transaction_type = 'conversion_payout',
            amount           = breakdown.net_to_user,
            balance_before   = balance_after - breakdown.net_to_user,
            balance_after    = balance_after,
            reference_id     = str(conversion.id),
            reference_type   = 'Conversion',
            note=(
                f'Offer: {conversion.offer.title if conversion.offer else "?"} | '
                f'Gross: {breakdown.gross_revenue} | '
                f'Platform: {breakdown.platform_cut} | '
                f'Referral: {breakdown.referral_bonus}'
            ),
        )


# ════════════════════════════════════════════════════════════════
# BULK PAYOUT (Celery-safe batch processing)
# ════════════════════════════════════════════════════════════════

class BulkPayoutProcessor:
    """
    Process multiple approved conversions safely.
    Each conversion processed independently — one failure ≠ all fail.
    """

    @staticmethod
    def process_batch(conversion_ids: list) -> dict:
        results = {'paid': [], 'skipped': [], 'failed': []}

        for conv_id in conversion_ids:
            try:
                result = PayoutEngine.pay_conversion(str(conv_id))
                if result is None:
                    results['skipped'].append(str(conv_id))
                else:
                    results['paid'].append(str(conv_id))
            except DuplicateConversionException:
                results['skipped'].append(str(conv_id))
            except Exception as e:
                logger.error(f'Payout failed for {conv_id}: {e}')
                results['failed'].append({'id': str(conv_id), 'error': str(e)})

        logger.info(
            f'BulkPayout complete: '
            f'paid={len(results["paid"])} '
            f'skipped={len(results["skipped"])} '
            f'failed={len(results["failed"])}'
        )
        return results

    @staticmethod
    def process_pending_approvals(limit: int = 500):
        """
        Auto-approve + pay conversions from trusted S2S networks.
        Only runs on high-trust offers (is_s2s_enabled=True).
        """
        eligible = (
            Conversion.objects
            .filter(
                status__name='pending',
                offer__network__is_s2s_enabled=True,
                approved_at__isnull=True,
            )
            .values_list('id', flat=True)[:limit]
        )

        # First approve all
        approved_status = ConversionStatus.objects.get(name='approved')
        Conversion.objects.filter(id__in=eligible).update(
            status=approved_status
        )

        # Then pay each
        return BulkPayoutProcessor.process_batch(list(eligible))
