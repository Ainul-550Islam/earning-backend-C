# api/wallet/use_cases.py
"""
Use Cases — Clean Architecture application layer.
Each use case is a single class with a single execute() method.
Use cases orchestrate services, selectors, and events.

Pattern:
  1. Validate input
  2. Call selectors (read) / services (write)
  3. Publish domain events
  4. Return result

Usage:
    uc = CreditWalletUseCase(wallet=wallet, amount=Decimal("500"), source="task")
    result = uc.execute()
"""
import logging
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("wallet.use_cases")


# ══════════════════════════════════════════════════
# INPUT / OUTPUT DATA CLASSES
# ══════════════════════════════════════════════════

@dataclass
class CreditInput:
    wallet_id: int
    amount: Decimal
    source_type: str
    source_id: str = ""
    idempotency_key: str = ""
    country_code: str = "BD"
    description: str = ""

@dataclass
class CreditOutput:
    success: bool
    txn_id: str = ""
    amount_credited: Decimal = Decimal("0")
    balance_after: Decimal = Decimal("0")
    error: str = ""

@dataclass
class WithdrawalInput:
    user_id: int
    wallet_id: int
    payment_method_id: int
    amount: Decimal
    note: str = ""
    idempotency_key: str = ""
    ip_address: str = ""

@dataclass
class WithdrawalOutput:
    success: bool
    withdrawal_id: str = ""
    amount: Decimal = Decimal("0")
    fee: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    status: str = ""
    error: str = ""

@dataclass
class TransferInput:
    from_user_id: int
    to_username: str
    amount: Decimal
    note: str = ""

@dataclass
class TransferOutput:
    success: bool
    debit_txn_id: str = ""
    credit_txn_id: str = ""
    amount: Decimal = Decimal("0")
    error: str = ""


# ══════════════════════════════════════════════════
# USE CASES
# ══════════════════════════════════════════════════

class CreditWalletUseCase:
    """
    Credit a wallet from an earning source.
    Pipeline:
      1. Load wallet
      2. Check earning cap
      3. Apply GEO × tier multipliers
      4. Idempotency check
      5. Credit via WalletService
      6. Publish WalletCredited event
      7. Update user stats
    """

    def __init__(self, *, inp: CreditInput):
        self.inp = inp

    def execute(self) -> CreditOutput:
        try:
            from .selectors import wallet_get_by_id
            from .services.core.WalletService import WalletService
            from .services.earning.EarningCapService import EarningCapService
            from .services.cpalead.CPALeadService import CPALeadService
            from .event_bus import event_bus
            from .events import WalletCredited

            wallet = wallet_get_by_id(wallet_id=self.inp.wallet_id)
            if not wallet:
                return CreditOutput(success=False, error="Wallet not found")
            if wallet.is_locked:
                return CreditOutput(success=False, error=f"Wallet locked: {wallet.locked_reason}")

            # Cap check
            allowed, remaining = EarningCapService.check(
                wallet, self.inp.amount, self.inp.source_type
            )
            if not allowed:
                return CreditOutput(success=False,
                                     error=f"Daily cap reached. Remaining: {remaining}")

            # Multipliers
            geo_mult  = CPALeadService.get_geo_rate(self.inp.country_code)
            tier_mult = CPALeadService.get_tier_multiplier(wallet.user)
            final_amt = (self.inp.amount * geo_mult * tier_mult).quantize(
                Decimal("0.00000001")
            )

            # Credit
            txn = WalletService.credit(
                wallet=wallet,
                amount=final_amt,
                txn_type=self.inp.source_type,
                description=self.inp.description or f"Earning: {self.inp.source_type}",
                idempotency_key=self.inp.idempotency_key,
                country_code=self.inp.country_code,
            )

            # Events
            event_bus.publish(WalletCredited(
                wallet_id=wallet.id,
                user_id=wallet.user_id,
                amount=final_amt,
                txn_type=self.inp.source_type,
                txn_id=str(txn.txn_id),
                balance_after=txn.balance_after or Decimal("0"),
            ))

            return CreditOutput(
                success=True,
                txn_id=str(txn.txn_id),
                amount_credited=final_amt,
                balance_after=txn.balance_after or Decimal("0"),
            )

        except Exception as e:
            logger.error(f"CreditWalletUseCase error: {e}", exc_info=True)
            return CreditOutput(success=False, error=str(e))


class RequestWithdrawalUseCase:
    """
    Create a withdrawal request.
    Pipeline:
      1. Validate wallet + payment method
      2. KYC + fraud check
      3. Limit check
      4. Fee calculation
      5. Create withdrawal
      6. Publish WithdrawalRequested event
    """

    def __init__(self, *, inp: WithdrawalInput):
        self.inp = inp

    def execute(self) -> WithdrawalOutput:
        try:
            from .selectors import wallet_get_by_id
            from .services.withdrawal.WithdrawalService import WithdrawalService
            from .services.withdrawal.WithdrawalLimitService import WithdrawalLimitService
            from .models.withdrawal import WithdrawalMethod
            from .event_bus import event_bus
            from .events import WithdrawalRequested
            from django.contrib.auth import get_user_model

            user   = get_user_model().objects.get(id=self.inp.user_id)
            wallet = wallet_get_by_id(wallet_id=self.inp.wallet_id)
            if not wallet:
                return WithdrawalOutput(success=False, error="Wallet not found")
            if wallet.is_locked:
                return WithdrawalOutput(success=False, error="Wallet is locked")

            # Payment method
            try:
                pm = WithdrawalMethod.objects.get(
                    id=self.inp.payment_method_id, user=user
                )
            except WithdrawalMethod.DoesNotExist:
                return WithdrawalOutput(success=False, error="Payment method not found")

            # Limit check
            try:
                WithdrawalLimitService.validate(wallet, self.inp.amount, pm.method_type)
            except Exception as e:
                return WithdrawalOutput(success=False, error=str(e))

            # Create
            wr = WithdrawalService.create(
                wallet=wallet,
                amount=self.inp.amount,
                payment_method=pm,
                created_by=user,
                ip_address=self.inp.ip_address,
                idempotency_key=self.inp.idempotency_key,
                note=self.inp.note,
            )

            # Event
            event_bus.publish(WithdrawalRequested(
                withdrawal_id=str(wr.withdrawal_id),
                wallet_id=wallet.id,
                user_id=user.id,
                amount=wr.amount,
                fee=wr.fee,
                net_amount=wr.net_amount,
                gateway=pm.method_type,
                account=pm.account_number,
            ))

            return WithdrawalOutput(
                success=True,
                withdrawal_id=str(wr.withdrawal_id),
                amount=wr.amount,
                fee=wr.fee,
                net_amount=wr.net_amount,
                status=wr.status,
            )

        except Exception as e:
            logger.error(f"RequestWithdrawalUseCase error: {e}", exc_info=True)
            return WithdrawalOutput(success=False, error=str(e))


class TransferFundsUseCase:
    """
    Transfer funds from one user wallet to another.
    Pipeline:
      1. Validate sender wallet
      2. Find recipient
      3. Balance check
      4. Atomic debit + credit
      5. Publish TransferCompleted event
    """

    def __init__(self, *, inp: TransferInput):
        self.inp = inp

    def execute(self) -> TransferOutput:
        try:
            from .services.core.WalletService import WalletService
            from .event_bus import event_bus
            from .events import TransferCompleted
            from django.contrib.auth import get_user_model

            User       = get_user_model()
            from_user  = User.objects.get(id=self.inp.from_user_id)

            # Find recipient
            try:
                to_user = User.objects.get(username=self.inp.to_username)
            except User.DoesNotExist:
                try:
                    to_user = User.objects.get(email=self.inp.to_username)
                except User.DoesNotExist:
                    return TransferOutput(success=False, error="Recipient not found")

            if from_user.id == to_user.id:
                return TransferOutput(success=False, error="Cannot transfer to yourself")

            result = WalletService.transfer(
                from_user, to_user, self.inp.amount, note=self.inp.note
            )

            event_bus.publish(TransferCompleted(
                from_wallet_id=result.get("from_wallet_id", 0),
                to_wallet_id=result.get("to_wallet_id", 0),
                debit_txn_id=str(result.get("debit_txn", {}).get("txn_id", "")),
                credit_txn_id=str(result.get("credit_txn", {}).get("txn_id", "")),
                amount=self.inp.amount,
            ))

            return TransferOutput(
                success=True,
                amount=self.inp.amount,
            )

        except Exception as e:
            logger.error(f"TransferFundsUseCase error: {e}", exc_info=True)
            return TransferOutput(success=False, error=str(e))


class ApproveWithdrawalUseCase:
    """Admin: approve a withdrawal."""

    def __init__(self, *, withdrawal_id: str, admin_user):
        self.withdrawal_id = withdrawal_id
        self.admin_user    = admin_user

    def execute(self) -> dict:
        try:
            from .selectors import withdrawal_get
            from .services.withdrawal.WithdrawalService import WithdrawalService
            from .event_bus import event_bus
            from .events import WithdrawalApproved

            wr = withdrawal_get(withdrawal_id=self.withdrawal_id)
            if not wr:
                return {"success": False, "error": "Withdrawal not found"}

            WithdrawalService.approve(wr, by=self.admin_user)

            event_bus.publish(WithdrawalApproved(
                withdrawal_id=str(wr.withdrawal_id),
                wallet_id=wr.wallet_id,
                user_id=wr.user_id,
                amount=wr.amount,
                approved_by_id=self.admin_user.id,
            ))

            return {"success": True, "status": wr.status}

        except Exception as e:
            return {"success": False, "error": str(e)}
