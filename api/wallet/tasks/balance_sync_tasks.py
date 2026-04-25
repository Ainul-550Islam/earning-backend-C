# api/wallet/tasks/balance_sync_tasks.py
"""
Balance synchronization and reconciliation tasks.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.balance")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.sync_balance")
def sync_balance(self, wallet_id: int):
    """
    Re-compute and validate a single wallet's current_balance
    by summing all approved/completed WalletTransaction amounts.
    Flags any discrepancy.
    """
    try:
        from ..models import Wallet, WalletTransaction
        from decimal import Decimal
        from django.db.models import Sum

        wallet = Wallet.objects.select_for_update().get(id=wallet_id)
        txn_sum = WalletTransaction.objects.filter(
            wallet=wallet,
            status__in=["approved","completed"],
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        discrepancy = wallet.current_balance - txn_sum
        if abs(discrepancy) > Decimal("0.00000001"):
            logger.error(
                f"BALANCE DISCREPANCY wallet={wallet_id} "
                f"db={wallet.current_balance} txn_sum={txn_sum} delta={discrepancy}"
            )
            return {"status": "discrepancy", "wallet_id": wallet_id, "delta": float(discrepancy)}

        return {"status": "ok", "wallet_id": wallet_id, "balance": float(wallet.current_balance)}

    except Exception as e:
        logger.error(f"sync_balance wallet={wallet_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.reconcile_all_balances")
def reconcile_all_balances(self):
    """
    Run reconciliation for all wallets.
    Called by Celery Beat daily at 2 AM.
    """
    try:
        from ..services import ReconciliationService
        result = ReconciliationService.run_all()
        logger.info(f"Reconcile all: {result}")
        return result
    except Exception as e:
        logger.error(f"reconcile_all_balances: {e}")
        raise self.retry(exc=e)
