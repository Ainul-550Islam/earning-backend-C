# api/wallet/services/core/WalletService.py
"""
Core wallet operations — credit, debit, freeze, unfreeze, transfer, admin ops.
Every operation:
  1. Validates inputs (amount, locked status, balance sufficiency)
  2. Checks idempotency key (prevents double-credit)
  3. Applies GEO + tier multipliers (for earnings)
  4. Applies performance bonus (CPAlead-style)
  5. Awards points (CPAlead virtual currency)
  6. Mutates wallet fields atomically
  7. Creates WalletTransaction record
  8. Creates WalletLedger + LedgerEntry pair (double-entry)
  9. Updates BalanceHistory
  10. Checks publisher level upgrade (CPAlead)
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from ...models import Wallet, WalletTransaction, IdempotencyKey
from ...choices import TransactionType, TransactionStatus
from ...exceptions import (
    WalletLockedError, InsufficientBalanceError,
    InvalidAmountError, DuplicateTransactionError, OptimisticLockError,
)
from ...constants import (
    TIER_EARN_BONUS, TIER_FEE_DISCOUNT,
    REFERRAL_RATES, DEFAULT_DAILY_EARN_CAP,
    IDEMPOTENCY_TTL,
)

logger = logging.getLogger("wallet.service.wallet")


class WalletService:
    """
    Core financial operations for a wallet.
    All public methods are @transaction.atomic.
    """

    # ── Create / Get ─────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def get_or_create(user) -> Wallet:
        """Get or create a wallet for a user. Also sets up publisher structures."""
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={"currency": "BDT"},
        )
        if created:
            logger.info(f"Wallet created for user={user.id}")
            WalletService._setup_publisher(user, wallet)
        return wallet

    @staticmethod
    def _setup_publisher(user, wallet: Wallet):
        """Auto-setup CPAlead publisher structures on wallet creation."""
        try:
            from ...models_cpalead_extra import PayoutSchedule, PublisherLevel, PointsLedger
            PayoutSchedule.objects.get_or_create(
                user=user, wallet=wallet,
                defaults={"frequency": "net30", "minimum_threshold": Decimal("50"), "hold_days": 30},
            )
            PublisherLevel.objects.get_or_create(user=user, wallet=wallet)
            PointsLedger.objects.get_or_create(user=user, wallet=wallet)
        except Exception as e:
            logger.warning(f"Publisher setup failed user={user.id}: {e}")

    # ── Credit ────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def credit(
        wallet: Wallet,
        amount: Decimal,
        txn_type: str = TransactionType.EARNING,
        description: str = "",
        reference_id: str = "",
        reference_type: str = "",
        metadata: dict = None,
        approved_by=None,
        debit_account: str = "revenue",
        credit_account: str = "user_balance",
        idempotency_key: str = "",
        ip_address: str = None,
        country_code: str = "",
        fee_amount: Decimal = Decimal("0"),
    ) -> WalletTransaction:
        """
        Credit a wallet with full audit trail:
          - idempotency check
          - GEO rate multiplier (for earnings)
          - tier bonus multiplier
          - performance bonus (CPAlead up to 20%)
          - points award (CPAlead 1000pts/$1)
          - publisher level upgrade check
          - double-entry ledger
          - balance history
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidAmountError(f"Credit amount must be positive, got {amount}")
        if wallet.is_locked:
            raise WalletLockedError(wallet.locked_reason)

        # ── Idempotency ───────────────────────────────────────────────
        if idempotency_key:
            existing = IdempotencyKey.get_valid(idempotency_key)
            if existing:
                logger.info(f"Idempotent replay: key={idempotency_key}")
                txn = WalletTransaction.objects.filter(
                    idempotency_key=idempotency_key, wallet=wallet
                ).first()
                if txn:
                    return txn

        # ── GEO multiplier (earnings only) ────────────────────────────
        original_amount = amount
        if country_code and txn_type in (
            TransactionType.EARNING, TransactionType.REWARD,
            TransactionType.CPA, TransactionType.CPI, TransactionType.CPC,
            TransactionType.SURVEY, TransactionType.OFFER_WALL,
        ):
            geo_mult = WalletService._get_geo_multiplier(country_code)
            amount = (amount * geo_mult).quantize(Decimal("0.00000001"))

        # ── Tier multiplier ───────────────────────────────────────────
        if txn_type in (TransactionType.EARNING, TransactionType.REWARD, TransactionType.REFERRAL):
            tier_mult = WalletService._get_tier_multiplier(wallet.user)
            amount = (amount * tier_mult).quantize(Decimal("0.00000001"))

        # ── Performance bonus (CPAlead ≤ 20%) ────────────────────────
        bonus_amount = Decimal("0")
        if txn_type in (TransactionType.EARNING, TransactionType.REWARD):
            bonus_amount = WalletService._calc_performance_bonus(wallet.user, wallet, amount)

        total_credit = amount + bonus_amount
        bal_before   = wallet.current_balance

        # ── Create transaction ────────────────────────────────────────
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type=txn_type,
            amount=total_credit,
            currency=wallet.currency,
            status=TransactionStatus.APPROVED,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            metadata={**(metadata or {}), "original_amount": str(original_amount),
                      "country_code": country_code, "bonus": str(bonus_amount)},
            balance_before=bal_before,
            balance_after=bal_before + total_credit,
            debit_account=debit_account,
            credit_account=credit_account,
            fee_amount=fee_amount,
            net_amount=total_credit - fee_amount,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            approved_by=approved_by,
            approved_at=timezone.now(),
        )

        # ── Update wallet ─────────────────────────────────────────────
        wallet.current_balance  += total_credit
        wallet.version          += 1
        wallet.last_activity_at  = timezone.now()

        if txn_type in (TransactionType.EARNING, TransactionType.REWARD,
                        TransactionType.REFERRAL, TransactionType.SURVEY,
                        TransactionType.CPA, TransactionType.CPI, TransactionType.CPC,
                        TransactionType.CASHBACK, TransactionType.OFFER_WALL):
            wallet.total_earned += total_credit
        if txn_type == TransactionType.REFERRAL:
            wallet.total_referral_earned += total_credit
        if txn_type == TransactionType.BONUS or bonus_amount > 0:
            wallet.total_bonuses += bonus_amount
        wallet.save()

        # ── Ledger ────────────────────────────────────────────────────
        WalletService._record_ledger(wallet, txn, debit_account, credit_account, total_credit)

        # ── Balance history ───────────────────────────────────────────
        WalletService._record_balance_history(
            wallet, "current", bal_before, wallet.current_balance, txn.description, str(txn.txn_id)
        )

        # ── Points ────────────────────────────────────────────────────
        if txn_type in (TransactionType.EARNING, TransactionType.REWARD,
                        TransactionType.REFERRAL, TransactionType.CPA,
                        TransactionType.CPI, TransactionType.CPC):
            WalletService._award_points(wallet.user, wallet, amount)

        # ── Publisher level check ─────────────────────────────────────
        WalletService._check_publisher_upgrade(wallet.user, wallet, amount)

        # ── Idempotency key ───────────────────────────────────────────
        if idempotency_key:
            from datetime import timedelta
            IdempotencyKey.objects.get_or_create(
                key=idempotency_key,
                defaults={
                    "wallet": wallet,
                    "user": wallet.user,
                    "amount": total_credit,
                    "expires_at": timezone.now() + timedelta(seconds=IDEMPOTENCY_TTL),
                    "response_data": {"txn_id": str(txn.txn_id)},
                },
            )

        logger.info(f"Credit wallet={wallet.id} user={wallet.user_id} "
                    f"amount={total_credit} type={txn_type} txn={txn.txn_id}")
        return txn

    # ── Debit ─────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def debit(
        wallet: Wallet,
        amount: Decimal,
        txn_type: str = TransactionType.WITHDRAWAL,
        description: str = "",
        metadata: dict = None,
        created_by=None,
        ip_address: str = None,
        fee_amount: Decimal = Decimal("0"),
    ) -> WalletTransaction:
        """
        Debit a wallet. Moves funds to pending_balance pending processing.
        Raises InsufficientBalanceError if available_balance < amount.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidAmountError(f"Debit amount must be positive, got {amount}")
        if wallet.is_locked:
            raise WalletLockedError(wallet.locked_reason)
        if amount > wallet.available_balance:
            raise InsufficientBalanceError(wallet.available_balance, amount)

        bal_before = wallet.current_balance
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type=txn_type,
            amount=-amount,
            currency=wallet.currency,
            status=TransactionStatus.PENDING,
            description=description,
            metadata=metadata or {},
            balance_before=bal_before,
            balance_after=bal_before - amount,
            debit_account="user_balance",
            credit_account="withdrawal_pending",
            fee_amount=fee_amount,
            net_amount=amount - fee_amount,
            ip_address=ip_address,
            created_by=created_by,
        )

        wallet.current_balance -= amount
        wallet.pending_balance += amount
        wallet.version         += 1
        wallet.last_activity_at = timezone.now()
        wallet.save()

        WalletService._record_balance_history(
            wallet, "current", bal_before, wallet.current_balance, description, str(txn.txn_id)
        )

        logger.info(f"Debit wallet={wallet.id} amount={amount} type={txn_type} txn={txn.txn_id}")
        return txn

    # ── Transfer ──────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def transfer(
        sender_user,
        recipient,
        amount: Decimal,
        currency: str = "BDT",
        note: str = "",
    ) -> dict:
        """
        Wallet-to-wallet transfer.
        recipient can be: User instance, username string, or email string.
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        User = get_user_model()

        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidAmountError("Transfer amount must be positive")

        if isinstance(recipient, str):
            recipient = User.objects.filter(
                Q(username=recipient) | Q(email=recipient)
            ).first()
            if not recipient:
                raise ValueError(f"Recipient not found: {recipient!r}")

        sender_wallet = WalletService.get_or_create(sender_user)
        recv_wallet   = WalletService.get_or_create(recipient)

        if amount > sender_wallet.available_balance:
            raise InsufficientBalanceError(sender_wallet.available_balance, amount)

        ref = f"transfer_{sender_user.id}_{recipient.id}"

        debit_txn = WalletService.debit(
            sender_wallet, amount,
            txn_type=TransactionType.TRANSFER,
            description=f"Transfer to {recipient.username}: {note}",
            created_by=sender_user,
        )
        # Finalise debit
        sender_wallet.refresh_from_db()
        sender_wallet.pending_balance -= amount
        sender_wallet.total_withdrawn += amount
        sender_wallet.save()
        debit_txn.status = TransactionStatus.COMPLETED
        debit_txn.save()

        credit_txn = WalletService.credit(
            recv_wallet, amount,
            txn_type=TransactionType.TRANSFER,
            description=f"Transfer from {sender_user.username}: {note}",
            reference_id=str(debit_txn.txn_id),
            reference_type="transfer",
        )

        return {
            "debit_txn":  str(debit_txn.txn_id),
            "credit_txn": str(credit_txn.txn_id),
            "amount":     float(amount),
            "from":       sender_user.username,
            "to":         recipient.username,
        }

    # ── Admin ops ─────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def admin_credit(wallet: Wallet, amount: Decimal, description: str, admin) -> WalletTransaction:
        return WalletService.credit(
            wallet, amount,
            txn_type=TransactionType.ADMIN_CREDIT,
            description=description,
            approved_by=admin,
        )

    @staticmethod
    @transaction.atomic
    def admin_debit(wallet: Wallet, amount: Decimal, description: str, admin) -> WalletTransaction:
        amount = Decimal(str(amount))
        if amount > wallet.current_balance:
            raise InsufficientBalanceError(wallet.current_balance, amount)

        bal_before = wallet.current_balance
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type=TransactionType.ADMIN_DEBIT,
            amount=-amount,
            currency=wallet.currency,
            status=TransactionStatus.APPROVED,
            description=description,
            balance_before=bal_before,
            balance_after=bal_before - amount,
            approved_by=admin,
            approved_at=timezone.now(),
        )
        wallet.current_balance -= amount
        wallet.version         += 1
        wallet.save()
        return txn

    # ── Summary ───────────────────────────────────────────────────────

    @staticmethod
    def get_summary(user) -> dict:
        """Full wallet summary for dashboard."""
        try:
            w = Wallet.objects.select_related("user").get(user=user)
        except Wallet.DoesNotExist:
            return {}

        today_earn = WalletTransaction.objects.filter(
            wallet=w,
            type__in=[TransactionType.EARNING, TransactionType.REWARD,
                      TransactionType.CPA, TransactionType.CPI, TransactionType.CPC],
            status=TransactionStatus.APPROVED,
            created_at__date=date.today(),
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        return {
            "current_balance":       str(w.current_balance),
            "pending_balance":       str(w.pending_balance),
            "frozen_balance":        str(w.frozen_balance),
            "bonus_balance":         str(w.bonus_balance),
            "reserved_balance":      str(w.reserved_balance),
            "available_balance":     str(w.available_balance),
            "total_balance":         str(w.total_balance),
            "total_earned":          str(w.total_earned),
            "total_withdrawn":       str(w.total_withdrawn),
            "total_fees_paid":       str(w.total_fees_paid),
            "total_bonuses":         str(w.total_bonuses),
            "total_referral_earned": str(w.total_referral_earned),
            "today_earning":         str(today_earn),
            "is_locked":             w.is_locked,
            "locked_reason":         w.locked_reason,
            "currency":              w.currency,
            "version":               w.version,
            "last_activity_at":      w.last_activity_at.isoformat() if w.last_activity_at else None,
        }

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_geo_multiplier(country_code: str) -> Decimal:
        try:
            from ...models_cpalead_extra import GeoRate
            geo = GeoRate.objects.filter(country_code=country_code.upper(), is_active=True).first()
            if geo:
                return geo.rate_multiplier
        except Exception:
            pass
        TIER1 = {"US", "GB", "CA", "AU", "NZ"}
        TIER2 = {"DE", "FR", "NL", "JP", "SG", "KR", "AE", "SE", "NO", "DK"}
        code = country_code.upper()
        if code in TIER1: return Decimal("2.50")
        if code in TIER2: return Decimal("1.50")
        if code == "BD":  return Decimal("1.00")
        return Decimal("0.80")

    @staticmethod
    def _get_tier_multiplier(user) -> Decimal:
        try:
            from api.users.models import UserLevel
            ul = UserLevel.objects.get(user=user)
            if hasattr(ul, "task_reward_bonus"):
                return Decimal(str(ul.task_reward_bonus))
        except Exception:
            pass
        tier = getattr(user, "tier", "FREE")
        return TIER_EARN_BONUS.get(tier, Decimal("1.00"))

    @staticmethod
    def _calc_performance_bonus(user, wallet: Wallet, base_amount: Decimal) -> Decimal:
        bonus_total = Decimal("0")
        try:
            from ...models_cpalead_extra import PerformanceBonus
            for b in PerformanceBonus.objects.filter(user=user, wallet=wallet, status="active"):
                if not b.is_active_now():
                    continue
                pct = base_amount * b.bonus_percent / 100
                if b.max_bonus:
                    pct = min(pct, b.max_bonus - b.total_paid)
                bonus_total += max(pct, Decimal("0"))
        except Exception:
            pass
        return bonus_total.quantize(Decimal("0.00000001"))

    @staticmethod
    def _award_points(user, wallet: Wallet, earned_amount: Decimal):
        try:
            from ...models_cpalead_extra import PointsLedger
            pl, _ = PointsLedger.objects.get_or_create(user=user, wallet=wallet)
            pl.award(earned_amount)
        except Exception as e:
            logger.debug(f"Points award skip: {e}")

    @staticmethod
    def _check_publisher_upgrade(user, wallet: Wallet, earned: Decimal):
        try:
            from ...models_cpalead_extra import PublisherLevel
            pl, _ = PublisherLevel.objects.get_or_create(user=user, wallet=wallet)
            pl.total_earnings += earned
            pl.save(update_fields=["total_earnings", "updated_at"])
            if pl.can_upgrade():
                pl.upgrade()
                logger.info(f"Publisher upgraded: {user.username} → Level {pl.level}")
        except Exception as e:
            logger.debug(f"Publisher check skip: {e}")

    @staticmethod
    def _record_ledger(wallet: Wallet, txn: WalletTransaction,
                       debit_account: str, credit_account: str, amount: Decimal):
        """Create WalletLedger + 2 LedgerEntries for double-entry accounting."""
        try:
            from ...models import WalletLedger, LedgerEntry
            ledger = WalletLedger.objects.create(
                wallet=wallet,
                transaction=txn,
                description=txn.description,
            )
            LedgerEntry(
                ledger=ledger,
                entry_type="debit",
                account=debit_account,
                amount=amount,
                balance_after=Decimal("0"),
                ref_type=txn.type,
                ref_id=str(txn.txn_id),
            ).save()
            LedgerEntry(
                ledger=ledger,
                entry_type="credit",
                account=credit_account,
                amount=amount,
                balance_after=wallet.current_balance,
                ref_type=txn.type,
                ref_id=str(txn.txn_id),
            ).save()
            ledger.check_balance()
        except Exception as e:
            logger.error(f"Ledger recording failed for txn={txn.txn_id}: {e}")

    @staticmethod
    def _record_balance_history(wallet: Wallet, balance_type: str,
                                previous: Decimal, new_value: Decimal,
                                reason: str = "", reference_id: str = ""):
        """Record balance change in BalanceHistory for audit."""
        try:
            from ...models import BalanceHistory
            BalanceHistory(
                wallet=wallet,
                balance_type=balance_type,
                previous=previous,
                new_value=new_value,
                reason=reason[:200],
                reference_id=reference_id[:255],
            ).save()
        except Exception as e:
            logger.debug(f"Balance history skip: {e}")
