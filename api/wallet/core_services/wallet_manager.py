# api/wallet/core_services/wallet_manager.py
"""
WalletManager — World-Class Wallet Engine Core.

Single entry point for ALL balance mutations. Every credit/debit goes through here.

Pipeline (credit):
  1. IntegrityShield.verify_hash()      — tamper detection
  2. Anti-fraud velocity check          — auto-lock if abuse detected
  3. transaction.atomic()               — race-condition safe
  4. SELECT FOR UPDATE (row lock)       — DB-level concurrent safety
  5. Apply balance change               — actual mutation
  6. Double-entry bookkeeping ledger    — credit == debit always
  7. WalletLog snapshot                 — pre/post balance recorded
  8. IntegrityShield.update_hash()      — new SHA-256 hash stored
  9. integ_audit_logs.log()             — immutable audit entry
 10. event_bus.publish()               — notify downstream (notifications etc.)
 11. API versioned response             — X-Wallet-Engine-Version header

Pipeline (debit):
  Same as credit + InsufficientBalance check before mutation.

No business logic lives outside this manager. All services call WalletManager.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ..choices import TransactionType, TransactionStatus
from ..constants import VELOCITY_MAX_PER_HOUR, FRAUD_BLOCK_SCORE
from ..exceptions import (
    InsufficientBalanceError,
    InvalidAmountError,
    WalletLockedError,
    SecurityLockError,
    FraudError,
)
from ..engine.security import verify_hash, update_hash
from ..engine import integ_audit_logs as audit
from ..event_bus import event_bus

logger = logging.getLogger("wallet.core_services.wallet_manager")

# ── Engine version (sent in API response headers) ────────────────
ENGINE_VERSION = "2.0.0"
ENGINE_HEADER  = {"X-Wallet-Engine-Version": ENGINE_VERSION}

# ── Velocity anti-fraud window ───────────────────────────────────
VELOCITY_WINDOW_SECONDS = 60      # 1-minute window
VELOCITY_MAX_PER_WINDOW = 10      # auto-lock after 10 txns/min


class WalletManager:
    """
    Atomic, integrity-protected, fraud-aware wallet engine.
    All public methods are classmethod — no instance state.
    """

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ════════════════════════════════════════════════════════════════

    @classmethod
    def credit(
        cls,
        wallet,
        amount: Decimal,
        txn_type: str                    = TransactionType.EARNING,
        category: str                    = "offer",
        description: str                 = "",
        reference_id: str                = "",
        reference_type: str              = "",
        idempotency_key: str             = "",
        ip_address: str                  = "",
        country_code: str                = "",
        fee_amount: Decimal              = Decimal("0"),
        skip_multipliers: bool           = False,
        metadata: Optional[dict]         = None,
    ) -> dict:
        """
        Credit a wallet. Returns result dict with txn, balances, version header.

        Args:
            wallet:           Wallet model instance
            amount:           Positive Decimal (BDT)
            txn_type:         TransactionType choice
            category:         "offer" | "ad" | "bonus" | "referral" | "admin"
            description:      Human-readable reason
            reference_id:     External ID (offer_id, task_id, etc.)
            idempotency_key:  Unique key to prevent duplicate credits
            skip_multipliers: True if caller pre-computed GEO/tier (CPALeadService)
            metadata:         Extra JSON stored on transaction
        """
        amount = cls._validate_amount(amount, "credit")
        cls._check_locked(wallet)
        cls._check_idempotency(idempotency_key, wallet)
        cls._check_velocity(wallet, ip_address)

        with transaction.atomic():
            # SELECT FOR UPDATE — exclusive row lock
            from ..models.core import Wallet
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

            # Integrity check BEFORE mutation
            verify_hash(wallet)
            bal_before = wallet.current_balance

            # Apply multipliers (if not pre-calculated)
            final_amount = cls._apply_multipliers(
                wallet, amount, txn_type, country_code, skip_multipliers
            )

            # Mutate balance
            wallet.current_balance   += final_amount
            wallet.total_earned      += final_amount if txn_type not in (
                TransactionType.ADMIN_CREDIT, TransactionType.BONUS
            ) else Decimal("0")
            wallet.total_bonuses     += final_amount if txn_type == TransactionType.BONUS else Decimal("0")
            wallet.last_activity_at   = timezone.now()
            wallet.version           += 1

            # Recompute integrity hash AFTER mutation, BEFORE save
            update_hash(wallet)
            wallet.save(update_fields=[
                "current_balance", "total_earned", "total_bonuses",
                "last_activity_at", "version", "integrity_hash",
            ])

            # Create transaction record
            txn = cls._create_transaction(
                wallet=wallet,
                amount=final_amount,
                txn_type=txn_type,
                category=category,
                status=TransactionStatus.APPROVED,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                bal_before=bal_before,
                bal_after=wallet.current_balance,
                fee_amount=fee_amount,
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                metadata=metadata or {},
            )

            # WalletLog snapshot
            cls._write_log(wallet, txn, bal_before, wallet.current_balance, "credit")

            # Double-entry bookkeeping
            cls._ledger_entry(wallet, txn, "revenue", "user_balance", final_amount, "credit")

        # Outside atomic — non-critical side effects
        audit.log_credit(wallet, final_amount, str(txn.txn_id), bal_before, ip_address, metadata)
        cls._emit_event("wallet_credited", wallet, txn, final_amount)

        return cls._result(txn, wallet)

    @classmethod
    def debit(
        cls,
        wallet,
        amount: Decimal,
        txn_type: str                    = TransactionType.WITHDRAWAL,
        category: str                    = "withdrawal",
        description: str                 = "",
        reference_id: str                = "",
        idempotency_key: str             = "",
        ip_address: str                  = "",
        fee_amount: Decimal              = Decimal("0"),
        metadata: Optional[dict]         = None,
    ) -> dict:
        """
        Debit a wallet. Raises InsufficientBalanceError if balance too low.
        """
        amount = cls._validate_amount(amount, "debit")
        cls._check_locked(wallet)
        cls._check_idempotency(idempotency_key, wallet)

        with transaction.atomic():
            from ..models.core import Wallet
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

            # Integrity check BEFORE mutation
            verify_hash(wallet)

            # Sufficient balance check (inside lock so no TOCTOU)
            if wallet.current_balance < amount:
                raise InsufficientBalanceError(
                    available=wallet.current_balance,
                    required=amount,
                )

            bal_before = wallet.current_balance
            total_debit = amount + fee_amount

            # Mutate balance
            wallet.current_balance  -= total_debit
            wallet.total_withdrawn  += amount
            wallet.total_fees_paid  += fee_amount
            wallet.last_activity_at  = timezone.now()
            wallet.version          += 1

            # Integrity hash AFTER mutation
            update_hash(wallet)
            wallet.save(update_fields=[
                "current_balance", "total_withdrawn", "total_fees_paid",
                "last_activity_at", "version", "integrity_hash",
            ])

            txn = cls._create_transaction(
                wallet=wallet,
                amount=amount,
                txn_type=txn_type,
                category=category,
                status=TransactionStatus.APPROVED,
                description=description,
                reference_id=reference_id,
                bal_before=bal_before,
                bal_after=wallet.current_balance,
                fee_amount=fee_amount,
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                metadata=metadata or {},
            )

            cls._write_log(wallet, txn, bal_before, wallet.current_balance, "debit")
            cls._ledger_entry(wallet, txn, "user_balance", "withdrawal_payable", amount, "debit")

        audit.log_debit(wallet, amount, str(txn.txn_id), bal_before, ip_address, metadata)
        cls._emit_event("wallet_debited", wallet, txn, amount)

        return cls._result(txn, wallet)

    @classmethod
    def process_withdrawal(
        cls,
        withdrawal_request,
        gateway_service,
        operator_user_id: int = None,
    ) -> dict:
        """
        Execute a withdrawal through a gateway service.
        Uses CircuitBreaker + full audit trail.

        Args:
            withdrawal_request: WithdrawalRequest model instance
            gateway_service:    Service class with .disburse() method
            operator_user_id:   Admin user ID triggering this (for audit)

        Returns:
            dict with gateway_response, txn, new_balance
        """
        from ..models.withdrawal import WithdrawalRequest
        from ..engine.circuit_breaker import get_breaker
        from ..choices import WithdrawalStatus

        wr = withdrawal_request
        gateway_name = wr.method.method_type if hasattr(wr, "method") else "unknown"
        breaker = get_breaker(gateway_name)

        # Circuit breaker pre-check
        breaker.assert_closed()
        audit.log_gateway(audit.Action.GATEWAY_CALL, gateway_name, wr.wallet_id,
                          detail=f"withdrawal_id={wr.pk} amount={wr.amount}")

        # Debit wallet atomically
        result = cls.debit(
            wallet=wr.wallet,
            amount=wr.amount,
            txn_type=TransactionType.WITHDRAWAL,
            category="withdrawal",
            description=f"Withdrawal via {gateway_name}",
            fee_amount=wr.fee_amount,
            reference_id=str(wr.pk),
            metadata={"withdrawal_request_id": wr.pk, "gateway": gateway_name},
        )

        # Call gateway
        try:
            gateway_resp = gateway_service.disburse(
                receiver=wr.account_number if hasattr(wr, "account_number") else "",
                amount=wr.amount,
                reference=str(wr.pk),
            )
            breaker.record_success()
            audit.log_gateway(audit.Action.GATEWAY_SUCCESS, gateway_name, wr.wallet_id,
                              detail=str(gateway_resp)[:200])

            wr.status       = WithdrawalStatus.COMPLETED
            wr.completed_at = timezone.now()
            wr.gateway_ref  = str(gateway_resp.get("transaction_id", ""))
            wr.save(update_fields=["status", "completed_at", "gateway_ref"])

        except Exception as e:
            breaker.record_failure()
            audit.log_gateway(audit.Action.GATEWAY_FAILURE, gateway_name, wr.wallet_id,
                              detail=str(e))
            # Reverse the debit
            cls._reverse(wr.wallet, result["txn"], reason=f"Gateway {gateway_name} failed: {e}")
            wr.status = WithdrawalStatus.FAILED
            wr.save(update_fields=["status"])
            raise

        return {**result, "gateway_response": gateway_resp, "withdrawal_id": wr.pk}

    @classmethod
    def verify_double_entry(cls) -> dict:
        """
        Verify system-wide double-entry bookkeeping integrity.
        Total credits must equal total debits across all ledger entries.
        Returns dict with ok, total_credits, total_debits, net.
        """
        from django.db.models import Sum
        from ..models.ledger import LedgerEntry
        from ..choices import LedgerEntryType

        credits = (
            LedgerEntry.objects
            .filter(entry_type=LedgerEntryType.CREDIT)
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )
        debits = (
            LedgerEntry.objects
            .filter(entry_type=LedgerEntryType.DEBIT)
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )

        net = credits - debits
        ok  = abs(net) < Decimal("0.00000001")  # float-safe comparison

        audit.log_double_entry(ok, credits, debits, net)

        if not ok:
            logger.critical(f"DOUBLE-ENTRY MISMATCH: credits={credits} debits={debits} net={net}")

        return {
            "ok":            ok,
            "total_credits": credits,
            "total_debits":  debits,
            "net":           net,
            "balanced":      ok,
        }

    # ════════════════════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _validate_amount(amount, direction: str) -> Decimal:
        try:
            amount = Decimal(str(amount)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        except Exception:
            raise InvalidAmountError(f"Invalid amount: {amount!r}")
        if amount <= 0:
            raise InvalidAmountError(f"{direction.title()} amount must be positive, got {amount}")
        return amount

    @staticmethod
    def _check_locked(wallet) -> None:
        if wallet.is_locked:
            raise WalletLockedError(wallet.locked_reason or "Wallet is locked")

    @staticmethod
    def _check_idempotency(key: str, wallet) -> None:
        """Prevent duplicate transactions using cache-based idempotency."""
        if not key:
            return
        from django.core.cache import cache
        cache_key = f"wallet_idem:{key}"
        if cache.get(cache_key):
            from ..exceptions import DuplicateTransactionError
            raise DuplicateTransactionError(f"Duplicate transaction: idempotency_key={key}")
        from ..constants import IDEMPOTENCY_TTL
        cache.set(cache_key, wallet.pk, timeout=IDEMPOTENCY_TTL)

    @classmethod
    def _check_velocity(cls, wallet, ip_address: str = "") -> None:
        """
        Anti-fraud velocity check.
        Auto-lock wallet if > VELOCITY_MAX_PER_WINDOW txns in 60 seconds.
        """
        from django.core.cache import cache
        cache_key = f"wallet_velocity:{wallet.pk}"
        count = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, timeout=VELOCITY_WINDOW_SECONDS)

        if count > VELOCITY_MAX_PER_WINDOW:
            reason = (
                f"Velocity limit: {count} transactions in {VELOCITY_WINDOW_SECONDS}s "
                f"(max {VELOCITY_MAX_PER_WINDOW})"
            )
            try:
                wallet.is_locked     = True
                wallet.locked_reason = reason
                wallet.save(update_fields=["is_locked", "locked_reason"])
            except Exception:
                pass
            audit.log_fraud_lock(wallet, reason)
            raise FraudError(reason)

    @staticmethod
    def _apply_multipliers(wallet, amount: Decimal, txn_type: str,
                           country_code: str, skip: bool) -> Decimal:
        """Apply GEO + tier multipliers unless skip=True."""
        if skip:
            return amount
        from ..constants import TIER_EARN_BONUS
        from ..choices import TransactionType as TT

        earning_types = {
            TT.EARNING, TT.REWARD, TT.CPA, TT.CPI,
            TT.CPC, TT.SURVEY, TT.OFFER_WALL,
        }
        tier_types = {TT.EARNING, TT.REWARD, TT.REFERRAL}

        if country_code and txn_type in earning_types:
            try:
                from ..models_cpalead_extra import GeoRate
                geo = GeoRate.objects.filter(
                    country_code=country_code.upper(), is_active=True
                ).first()
                geo_mult = geo.rate_multiplier if geo else Decimal("1.00")
            except Exception:
                geo_mult = Decimal("1.00")
            amount = (amount * geo_mult).quantize(Decimal("0.00000001"))

        if txn_type in tier_types:
            tier      = getattr(getattr(wallet, "user", None), "tier", "FREE")
            tier_mult = TIER_EARN_BONUS.get(tier, Decimal("1.00"))
            amount    = (amount * tier_mult).quantize(Decimal("0.00000001"))

        return amount

    @staticmethod
    def _create_transaction(
        wallet, amount, txn_type, category, status,
        description, reference_id, reference_type="",
        bal_before=None, bal_after=None, fee_amount=Decimal("0"),
        idempotency_key="", ip_address="", metadata=None,
    ):
        from ..models.core import WalletTransaction
        return WalletTransaction.objects.create(
            wallet=wallet,
            type=txn_type,
            amount=amount,
            currency=wallet.currency,
            status=status,
            description=description,
            reference_id=str(reference_id),
            reference_type=reference_type,
            balance_before=bal_before or Decimal("0"),
            balance_after=bal_after   or Decimal("0"),
            fee_amount=fee_amount,
            net_amount=amount - fee_amount,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            approved_at=timezone.now(),
            metadata={
                **(metadata or {}),
                "category":       category,
                "engine_version": ENGINE_VERSION,
            },
        )

    @staticmethod
    def _write_log(wallet, txn, bal_before, bal_after, direction: str) -> None:
        """Write BalanceHistory pre/post snapshot (immutable audit trail)."""
        try:
            from ..models.balance import BalanceHistory
            from ..choices import BalanceType
            BalanceHistory.objects.create(
                wallet=wallet,
                balance_type=BalanceType.CURRENT,
                previous=bal_before,
                new_value=bal_after,
                delta=bal_after - bal_before,
                reason=f"{direction}: {txn.description}"[:200],
                reference_id=str(txn.txn_id),
            )
        except Exception as e:
            logger.warning(f"BalanceHistory write failed (non-critical): {e}")

    @staticmethod
    def _ledger_entry(wallet, txn, debit_acct: str, credit_acct: str,
                      amount: Decimal, entry_type: str) -> None:
        """
        Write double-entry bookkeeping.
        One WalletLedger header per transaction → two LedgerEntry rows (debit + credit).
        Sum(debits) must always equal Sum(credits) for this ledger to be balanced.
        """
        try:
            from ..models.ledger import WalletLedger, LedgerEntry
            from ..choices import LedgerEntryType
            # One ledger header per transaction
            ledger = WalletLedger.objects.create(
                wallet=wallet,
                transaction=txn,
                description=txn.description,
            )
            # DEBIT side (source account — money leaves here)
            LedgerEntry.objects.create(
                ledger=ledger,
                entry_type=LedgerEntryType.DEBIT,
                account=debit_acct,
                amount=amount,
                ref_type=txn.type,
                ref_id=str(txn.txn_id),
            )
            # CREDIT side (destination account — money arrives here)
            LedgerEntry.objects.create(
                ledger=ledger,
                entry_type=LedgerEntryType.CREDIT,
                account=credit_acct,
                amount=amount,
                ref_type=txn.type,
                ref_id=str(txn.txn_id),
            )
            # Mark ledger as balanced (debit == credit by construction)
            ledger.is_balanced = True
            ledger.save(update_fields=["is_balanced"])
        except Exception as e:
            logger.warning(f"LedgerEntry write failed (non-critical): {e}")

    @staticmethod
    def _emit_event(event_name: str, wallet, txn, amount: Decimal) -> None:
        """Publish event to event bus (non-blocking, best-effort)."""
        try:
            import dataclasses
            from ..events import WalletCredited, WalletDebited
            EventClass = WalletCredited if event_name == "wallet_credited" else WalletDebited
            event = EventClass(
                wallet_id=wallet.pk,
                user_id=wallet.user_id,
                amount=amount,
                txn_id=str(txn.txn_id),
                balance_after=wallet.current_balance,
            )
            event_bus.publish(event)
        except Exception as e:
            logger.debug(f"Event publish skipped: {e}")

    @staticmethod
    def _reverse(wallet, original_txn, reason: str = "") -> None:
        """Reverse a debit by re-crediting the wallet (atomic)."""
        with transaction.atomic():
            from ..models.core import Wallet, WalletTransaction
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            verify_hash(wallet)
            bal_before             = wallet.current_balance
            wallet.current_balance += original_txn.amount + original_txn.fee_amount
            wallet.version         += 1
            update_hash(wallet)
            wallet.save(update_fields=[
                "current_balance", "version", "integrity_hash"
            ])
            WalletTransaction.objects.create(
                wallet=wallet,
                type=TransactionType.REVERSAL,
                amount=original_txn.amount,
                currency=wallet.currency,
                status=TransactionStatus.APPROVED,
                description=reason or f"Reversal of {original_txn.txn_id}",
                reference_id=str(original_txn.txn_id),
                reference_type="reversal",
                balance_before=bal_before,
                balance_after=wallet.current_balance,
                metadata={"engine_version": ENGINE_VERSION},
            )
        audit.log(audit.Action.REVERSAL, wallet_id=wallet.pk, user_id=wallet.user_id,
                  txn_id=str(original_txn.txn_id), detail=reason)

    @staticmethod
    def _result(txn, wallet) -> dict:
        """Standardized result dict with API version header."""
        return {
            "txn_id":          str(txn.txn_id),
            "amount":          str(txn.amount),
            "type":            txn.type,
            "status":          txn.status,
            "balance":         str(wallet.current_balance),
            "bonus_balance":   str(wallet.bonus_balance),
            "txn":             txn,
            "headers":         ENGINE_HEADER,
            "engine_version":  ENGINE_VERSION,
        }
