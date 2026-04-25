# api/wallet/services/ledger/LedgerService.py
"""
Double-entry bookkeeping ledger service.
Records every financial event as a pair of debit + credit entries.
Ensures sum(debits) == sum(credits) always.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from ...models import Wallet, WalletTransaction, WalletLedger, LedgerEntry
from ...choices import LedgerEntryType

logger = logging.getLogger("wallet.service.ledger")


class LedgerService:

    # Standard account names
    ACCOUNTS = {
        "user_balance":       "user_balance",
        "pending_withdrawal": "pending_withdrawal",
        "frozen_funds":       "frozen_funds",
        "bonus_liability":    "bonus_liability",
        "revenue":            "revenue",
        "fee_income":         "fee_income",
        "referral_expense":   "referral_expense",
        "bonus_expense":      "bonus_expense",
        "suspense":           "suspense",
    }

    @staticmethod
    @transaction.atomic
    def record(
        wallet: Wallet,
        txn: WalletTransaction,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
        ref_type: str = "",
        ref_id: str = "",
    ) -> WalletLedger:
        """
        Record a double-entry accounting event.
        Creates 1 WalletLedger + 2 LedgerEntries.
        Verifies that debits == credits before returning.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"Ledger amount must be positive, got {amount}")

        ledger = WalletLedger.objects.create(
            wallet=wallet,
            transaction=txn,
            description=txn.description,
        )

        # Debit entry (money leaving debit_account)
        LedgerEntry(
            ledger=ledger,
            entry_type=LedgerEntryType.DEBIT,
            account=debit_account,
            amount=amount,
            balance_after=Decimal("0"),  # caller can update if tracking account balance
            ref_type=ref_type or txn.type,
            ref_id=ref_id or str(txn.txn_id),
        ).save()

        # Credit entry (money entering credit_account)
        LedgerEntry(
            ledger=ledger,
            entry_type=LedgerEntryType.CREDIT,
            account=credit_account,
            amount=amount,
            balance_after=wallet.current_balance,
            ref_type=ref_type or txn.type,
            ref_id=ref_id or str(txn.txn_id),
        ).save()

        balanced = ledger.check_balance()
        if not balanced:
            logger.error(f"LEDGER UNBALANCED: ledger={ledger.ledger_id} txn={txn.txn_id}")

        logger.debug(f"Ledger recorded: {ledger.ledger_id} "
                     f"D:{debit_account} → C:{credit_account} amount={amount}")
        return ledger

    @staticmethod
    def reconcile(wallet: Wallet) -> dict:
        """
        Compare wallet.current_balance vs sum of ledger credits - debits.
        Returns dict with status and discrepancy amount.
        """
        from ...models import LedgerReconciliation
        from django.utils import timezone

        # Sum ledger: credits for user_balance minus debits for user_balance
        credits = LedgerEntry.objects.filter(
            ledger__wallet=wallet,
            entry_type=LedgerEntryType.CREDIT,
            account="user_balance",
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        debits = LedgerEntry.objects.filter(
            ledger__wallet=wallet,
            entry_type=LedgerEntryType.DEBIT,
            account="user_balance",
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        ledger_balance = credits - debits
        wallet_balance = wallet.current_balance
        discrepancy    = wallet_balance - ledger_balance

        status = "ok" if abs(discrepancy) < Decimal("0.00000001") else "discrepancy"

        recon = LedgerReconciliation.objects.create(
            wallet=wallet,
            period_start=wallet.created_at,
            period_end=timezone.now(),
            expected_balance=wallet_balance,
            actual_balance=ledger_balance,
            status=status,
        )

        if status == "discrepancy":
            logger.warning(f"Reconciliation discrepancy: wallet={wallet.id} "
                           f"wallet_bal={wallet_balance} ledger_bal={ledger_balance} "
                           f"Δ={discrepancy}")

        return {
            "status":      status,
            "wallet_bal":  str(wallet_balance),
            "ledger_bal":  str(ledger_balance),
            "discrepancy": str(discrepancy),
            "recon_id":    recon.id,
        }

    @staticmethod
    def get_account_balance(wallet: Wallet, account: str) -> Decimal:
        """Sum credits minus debits for a specific account on a wallet."""
        credits = LedgerEntry.objects.filter(
            ledger__wallet=wallet,
            entry_type=LedgerEntryType.CREDIT,
            account=account,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        debits = LedgerEntry.objects.filter(
            ledger__wallet=wallet,
            entry_type=LedgerEntryType.DEBIT,
            account=account,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        return credits - debits
