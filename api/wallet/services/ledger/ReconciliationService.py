# api/wallet/services/ledger/ReconciliationService.py
"""
Daily reconciliation service — compares wallet balances vs ledger entries.
Flags discrepancies for admin investigation.
"""
import logging
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

from ...models import Wallet, LedgerReconciliation

logger = logging.getLogger("wallet.service.reconciliation")


class ReconciliationService:

    @staticmethod
    def run_all(batch_size: int = 100) -> dict:
        """
        Reconcile all wallets. Called by reconciliation_tasks daily.
        Processes in batches to avoid memory issues on large datasets.
        """
        ok = discrepancy = errors = 0
        total = Wallet.objects.count()

        for offset in range(0, total, batch_size):
            wallets = Wallet.objects.all()[offset:offset + batch_size]
            for wallet in wallets:
                try:
                    result = ReconciliationService.run_one(wallet)
                    if result["status"] == "ok":
                        ok += 1
                    else:
                        discrepancy += 1
                        logger.warning(
                            f"DISCREPANCY wallet={wallet.id} user={wallet.user_id} "
                            f"Δ={result['discrepancy']}"
                        )
                except Exception as e:
                    errors += 1
                    logger.error(f"Reconcile error wallet={wallet.id}: {e}")

        report = {"ok": ok, "discrepancy": discrepancy, "errors": errors, "total": total}
        logger.info(f"Reconciliation complete: {report}")
        return report

    @staticmethod
    def run_one(wallet: Wallet) -> dict:
        """Reconcile a single wallet. Returns status dict."""
        from ..ledger.LedgerService import LedgerService
        return LedgerService.reconcile(wallet)

    @staticmethod
    def get_unresolved() -> "QuerySet":
        """Return all unresolved reconciliation discrepancies."""
        return LedgerReconciliation.objects.filter(
            status__in=("discrepancy", "investigating")
        ).select_related("wallet__user").order_by("-reconciled_at")

    @staticmethod
    def resolve(recon_id: int, notes: str = "", resolved_by=None):
        """Mark a reconciliation discrepancy as resolved."""
        recon = LedgerReconciliation.objects.get(id=recon_id)
        recon.status      = "fixed"
        recon.notes       = notes
        recon.resolved_by = resolved_by
        recon.resolved_at = timezone.now()
        recon.save()
        return recon
