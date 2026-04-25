# api/wallet/tasks/ledger_snapshot_tasks.py
"""
Weekly ledger snapshot creation.
"""
import logging
from datetime import date
from celery import shared_task

logger = logging.getLogger("wallet.tasks.snapshot")


@shared_task(bind=True, max_retries=3, default_retry_delay=600, name="wallet.take_weekly_snapshots")
def take_weekly_snapshots(self, snapshot_date: str = None):
    """
    Take ledger balance snapshots for all wallets.
    Runs weekly on Sunday at 2 AM.
    Allows fast balance-at-date queries without full entry scan.
    """
    try:
        from ..services import LedgerSnapshotService

        snap_date = date.fromisoformat(snapshot_date) if snapshot_date else date.today()
        result = LedgerSnapshotService.take_all_snapshots(snap_date)
        logger.info(f"Ledger snapshots: {result}")
        return result
    except Exception as e:
        logger.error(f"take_weekly_snapshots: {e}")
        raise self.retry(exc=e)
