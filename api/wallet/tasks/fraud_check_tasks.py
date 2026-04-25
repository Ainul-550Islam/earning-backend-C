# api/wallet/tasks/fraud_check_tasks.py
"""
Background fraud detection and AML checks.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.fraud")


@shared_task(bind=True, max_retries=3, default_retry_delay=120, name="wallet.run_fraud_checks")
def run_fraud_checks(self):
    """
    Asynchronously score recent transactions for fraud.
    Flags high-risk transactions for admin review.
    Runs every 30 minutes.
    """
    try:
        from ..models import WalletTransaction
        from datetime import timedelta

        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_withdrawals = WalletTransaction.objects.filter(
            type="withdrawal",
            created_at__gte=one_hour_ago,
            status__in=["pending","approved"],
        ).select_related("wallet","wallet__user")[:200]

        scored = blocked = 0
        for txn in recent_withdrawals:
            try:
                from ..services_extra import FraudDetectionService
                result = FraudDetectionService.score_transaction(txn)
                scored += 1
                if result.get("is_blocked"):
                    blocked += 1
                    logger.warning(
                        f"FRAUD BLOCKED: txn={txn.txn_id} "
                        f"user={txn.wallet.user.username} "
                        f"score={result['score']}"
                    )
                    # Lock wallet for review
                    txn.wallet.lock(f"Fraud detected. Score={result['score']}. Signals={result['signals']}")
            except Exception as e:
                logger.debug(f"Fraud score skip txn={txn.txn_id}: {e}")

        return {"scored": scored, "blocked": blocked}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.run_aml_scan")
def run_aml_scan(self):
    """
    Daily AML (anti-money laundering) scan.
    Detects structuring, rapid fund movement, round numbers patterns.
    Runs daily at 4 AM.
    """
    try:
        from ..models import Wallet
        from decimal import Decimal

        flagged = 0
        for wallet in Wallet.objects.filter(is_locked=False).select_related("user"):
            try:
                from ..services_extra import AMLService
                flags = AMLService.check(wallet.user, wallet, Decimal("0"), "scan")
                if flags:
                    flagged += len(flags)
            except Exception as e:
                logger.debug(f"AML scan skip wallet={wallet.id}: {e}")

        logger.info(f"AML scan complete: {flagged} flags raised")
        return {"flags": flagged}
    except Exception as e:
        raise self.retry(exc=e)
