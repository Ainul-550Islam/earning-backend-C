# api/wallet/tasks/reconciliation_tasks.py
"""
Daily ledger reconciliation tasks.
"""
import logging
from celery import shared_task

logger = logging.getLogger("wallet.tasks.reconciliation")


@shared_task(bind=True, max_retries=3, default_retry_delay=600, name="wallet.run_daily_reconciliation")
def run_daily_reconciliation(self):
    """
    Run full ledger reconciliation for all wallets.
    Flags discrepancies for admin investigation.
    Runs weekly on Sunday at 3 AM.
    """
    try:
        from ..services import ReconciliationService
        result = ReconciliationService.run_all()
        logger.info(f"Reconciliation: {result}")
        if result["discrepancy"] > 0:
            logger.error(f"RECONCILIATION DISCREPANCIES: {result['discrepancy']} wallets affected!")
        return result
    except Exception as e:
        raise self.retry(exc=e)
