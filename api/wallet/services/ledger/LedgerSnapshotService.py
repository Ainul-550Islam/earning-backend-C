# api/wallet/services/ledger/LedgerSnapshotService.py
"""
Periodic ledger snapshot management.
Snapshots store the running balance at a point in time,
allowing fast reconciliation without scanning all entries from genesis.
"""
import logging
from decimal import Decimal
from datetime import date
from django.db.models import Sum
from django.utils import timezone

from ...models import Wallet, LedgerSnapshot, LedgerEntry

logger = logging.getLogger("wallet.service.snapshot")


class LedgerSnapshotService:

    ACCOUNTS_TO_SNAPSHOT = [
        "user_balance",
        "pending_withdrawal",
        "frozen_funds",
        "bonus_liability",
        "revenue",
    ]

    @staticmethod
    def take_snapshot(wallet: Wallet, snapshot_date: date = None) -> list:
        """
        Take balance snapshot for all tracked accounts on a wallet.
        Called weekly by ledger_snapshot_tasks.
        Returns list of LedgerSnapshot objects created.
        """
        snap_date  = snapshot_date or date.today()
        snapshots  = []

        for account in LedgerSnapshotService.ACCOUNTS_TO_SNAPSHOT:
            credits = LedgerEntry.objects.filter(
                ledger__wallet=wallet,
                entry_type="credit",
                account=account,
                created_at__date__lte=snap_date,
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

            debits = LedgerEntry.objects.filter(
                ledger__wallet=wallet,
                entry_type="debit",
                account=account,
                created_at__date__lte=snap_date,
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

            balance     = credits - debits
            entry_count = LedgerEntry.objects.filter(
                ledger__wallet=wallet,
                account=account,
                created_at__date__lte=snap_date,
            ).count()

            last_entry = LedgerEntry.objects.filter(
                ledger__wallet=wallet,
                account=account,
                created_at__date__lte=snap_date,
            ).order_by("-id").values_list("id", flat=True).first()

            snap, _ = LedgerSnapshot.objects.update_or_create(
                wallet=wallet,
                snapshot_date=snap_date,
                account=account,
                defaults={
                    "balance":      balance,
                    "entry_count":  entry_count,
                    "last_entry_id": last_entry,
                },
            )
            snapshots.append(snap)

        logger.info(f"Snapshot taken: wallet={wallet.id} date={snap_date} accounts={len(snapshots)}")
        return snapshots

    @staticmethod
    def take_all_snapshots(snapshot_date: date = None) -> dict:
        """Take snapshots for all wallets. Called by ledger_snapshot_tasks weekly."""
        snap_date = snapshot_date or date.today()
        ok = errors = 0

        for wallet in Wallet.objects.all():
            try:
                LedgerSnapshotService.take_snapshot(wallet, snap_date)
                ok += 1
            except Exception as e:
                errors += 1
                logger.error(f"Snapshot error wallet={wallet.id}: {e}")

        return {"ok": ok, "errors": errors, "date": str(snap_date)}

    @staticmethod
    def get_balance_at(wallet: Wallet, account: str, as_of: date) -> Decimal:
        """
        Get account balance at a specific date using nearest snapshot + delta entries.
        """
        snap = LedgerSnapshot.objects.filter(
            wallet=wallet,
            account=account,
            snapshot_date__lte=as_of,
        ).order_by("-snapshot_date").first()

        base_balance = snap.balance if snap else Decimal("0")
        since_id     = snap.last_entry_id if snap else 0

        # Add delta entries after snapshot
        delta_qs = LedgerEntry.objects.filter(
            ledger__wallet=wallet,
            account=account,
            created_at__date__lte=as_of,
        )
        if since_id:
            delta_qs = delta_qs.filter(id__gt=since_id)

        for entry in delta_qs:
            if entry.entry_type == "credit":
                base_balance += entry.amount
            else:
                base_balance -= entry.amount

        return base_balance
