# api/wallet/services/withdrawal/WithdrawalService.py
"""
Full withdrawal lifecycle service.
  create()   — validate + debit wallet + create WithdrawalRequest
  approve()  — admin approves pending request
  reject()   — admin rejects (refunds to wallet)
  process()  — trigger gateway disbursement
  complete() — mark completed after gateway confirmation
  cancel()   — user or admin cancels (refunds to wallet)
  batch_process() — batch multiple requests
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ...models import (
    Wallet, WalletTransaction, WithdrawalRequest,
    WithdrawalMethod, WithdrawalBatch,
)
from ...choices import TransactionType, TransactionStatus, WithdrawalStatus
from ...exceptions import (
    WalletLockedError, InsufficientBalanceError,
    InvalidAmountError, WithdrawalLimitError,
)

logger = logging.getLogger("wallet.service.withdrawal")


class WithdrawalService:

    @staticmethod
    @transaction.atomic
    def create(
        wallet: Wallet,
        amount: Decimal,
        payment_method: WithdrawalMethod,
        created_by=None,
        ip_address: str = None,
        idempotency_key: str = "",
        note: str = "",
        priority: int = 5,
    ) -> WithdrawalRequest:
        """
        Create a withdrawal request.
        Steps:
          1. Validate wallet not locked
          2. Check withdrawal block
          3. Validate limits (WithdrawalLimitService)
          4. Calculate fee (WithdrawalFeeService)
          5. Debit wallet (current → pending)
          6. Create WalletTransaction
          7. Create WithdrawalRequest
        """
        from .WithdrawalLimitService import WithdrawalLimitService
        from .WithdrawalFeeService import WithdrawalFeeService
        from ..core.WalletService import WalletService

        amount = Decimal(str(amount))

        # ── Locked ───────────────────────────────────────────────────
        if wallet.is_locked:
            raise WalletLockedError(wallet.locked_reason)

        # ── Withdrawal block ─────────────────────────────────────────
        from ...models import WithdrawalBlock
        block = WithdrawalBlock.objects.filter(user=wallet.user, is_active=True).first()
        if block and block.is_currently_active():
            raise WalletLockedError(f"Withdrawals blocked: {block.reason}")

        # ── Limits ───────────────────────────────────────────────────
        WithdrawalLimitService.validate(wallet, amount, payment_method.method_type)

        # ── Fee ───────────────────────────────────────────────────────
        fee     = WithdrawalFeeService.calculate(amount, payment_method.method_type, wallet.user)
        net     = amount - fee
        if net <= 0:
            raise InvalidAmountError(f"Net amount after fee ({fee}) is zero or negative")

        # ── Debit wallet ─────────────────────────────────────────────
        txn = WalletService.debit(
            wallet=wallet,
            amount=amount,
            txn_type=TransactionType.WITHDRAWAL,
            description=(
                f"Withdrawal → {payment_method.get_method_type_display()} "
                f"****{payment_method.account_number[-4:]} "
                f"(net={net} fee={fee})"
            ),
            created_by=created_by,
            ip_address=ip_address,
            fee_amount=fee,
        )

        # ── Fee transaction ───────────────────────────────────────────
        if fee > 0:
            WalletTransaction.objects.create(
                wallet=wallet,
                type=TransactionType.WITHDRAWAL_FEE,
                amount=-fee,
                currency=wallet.currency,
                status=TransactionStatus.APPROVED,
                description=f"Fee for withdrawal {txn.txn_id}",
                reference_id=str(txn.txn_id),
                balance_before=wallet.current_balance,
                balance_after=wallet.current_balance,
                approved_at=timezone.now(),
            )
            wallet.total_fees_paid += fee
            wallet.save(update_fields=["total_fees_paid"])

        # ── Create WithdrawalRequest ─────────────────────────────────
        wr = WithdrawalRequest.objects.create(
            user=wallet.user,
            wallet=wallet,
            payment_method=payment_method,
            transaction=txn,
            amount=amount,
            fee=fee,
            net_amount=net,
            currency=wallet.currency,
            status=WithdrawalStatus.PENDING,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            admin_note=note,
            priority=priority,
        )

        logger.info(f"Withdrawal created: {wr.withdrawal_id} user={wallet.user_id} "
                    f"amount={amount} fee={fee} net={net}")
        return wr

    @staticmethod
    @transaction.atomic
    def approve(wr: WithdrawalRequest, by=None) -> WithdrawalRequest:
        """Admin approves a pending withdrawal."""
        if wr.status != WithdrawalStatus.PENDING:
            raise ValueError(f"Cannot approve: status='{wr.status}'")
        wr.approve(approved_by=by)
        if wr.transaction:
            wr.transaction.approve(approved_by=by)
        logger.info(f"Withdrawal approved: {wr.withdrawal_id} by={by}")
        return wr

    @staticmethod
    @transaction.atomic
    def reject(wr: WithdrawalRequest, reason: str, by=None) -> WithdrawalRequest:
        """Admin rejects → refunds full amount to wallet."""
        if wr.status not in (WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING):
            raise ValueError(f"Cannot reject: status='{wr.status}'")

        wr.reject(reason=reason, rejected_by=by)

        # Refund: pending_balance → current_balance
        wallet = wr.wallet
        wallet.current_balance += wr.amount
        wallet.pending_balance  = max(wallet.pending_balance - wr.amount, Decimal("0"))
        wallet.version         += 1
        wallet.save()

        if wr.transaction:
            wr.transaction.reject(reason)

        # Refund transaction record
        WalletTransaction.objects.create(
            wallet=wallet,
            type=TransactionType.REFUND,
            amount=wr.amount,
            currency=wallet.currency,
            status=TransactionStatus.APPROVED,
            description=f"Refund for rejected withdrawal {wr.withdrawal_id}: {reason}",
            reference_id=str(wr.withdrawal_id),
            reference_type="withdrawal_refund",
            balance_before=wallet.current_balance - wr.amount,
            balance_after=wallet.current_balance,
            approved_by=by,
            approved_at=timezone.now(),
        )

        logger.info(f"Withdrawal rejected: {wr.withdrawal_id} refunded={wr.amount}")
        return wr

    @staticmethod
    @transaction.atomic
    def complete(wr: WithdrawalRequest, gateway_ref: str = "",
                 gateway_resp: dict = None) -> WithdrawalRequest:
        """Mark withdrawal as completed after gateway confirmation."""
        if wr.status not in (WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING):
            raise ValueError(f"Cannot complete: status='{wr.status}'")

        wr.complete(gateway_ref=gateway_ref, gateway_resp=gateway_resp)

        wallet = wr.wallet
        wallet.pending_balance  = max(wallet.pending_balance - wr.amount, Decimal("0"))
        wallet.total_withdrawn += wr.amount
        wallet.save()

        if wr.transaction:
            wr.transaction.mark_completed()

        # Update payout schedule stats (CPAlead)
        try:
            from ...models_cpalead_extra import PayoutSchedule
            sched = PayoutSchedule.objects.get(wallet=wallet)
            sched.last_payout_date   = date.today()
            sched.last_payout_amount = wr.amount
            sched.total_payouts     += 1
            sched.save(update_fields=["last_payout_date","last_payout_amount","total_payouts","updated_at"])
        except Exception:
            pass

        logger.info(f"Withdrawal completed: {wr.withdrawal_id} gateway_ref={gateway_ref}")
        return wr

    @staticmethod
    @transaction.atomic
    def cancel(wr: WithdrawalRequest, reason: str = "", cancelled_by=None) -> WithdrawalRequest:
        """User or admin cancels a pending/approved withdrawal → refund."""
        if wr.status in (WithdrawalStatus.COMPLETED, WithdrawalStatus.REJECTED):
            raise ValueError(f"Cannot cancel: status='{wr.status}'")

        wr.cancel(reason=reason)

        wallet = wr.wallet
        wallet.current_balance += wr.amount
        wallet.pending_balance  = max(wallet.pending_balance - wr.amount, Decimal("0"))
        wallet.version         += 1
        wallet.save()

        logger.info(f"Withdrawal cancelled: {wr.withdrawal_id} refunded={wr.amount}")
        return wr

    @staticmethod
    def calculate_fee(amount: Decimal, method_type: str, user) -> Decimal:
        """Convenience wrapper for WithdrawalFeeService."""
        from .WithdrawalFeeService import WithdrawalFeeService
        return WithdrawalFeeService.calculate(amount, method_type, user)
