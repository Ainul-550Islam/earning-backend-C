# api/wallet/tasks/withdrawal_processing_tasks.py
"""
Withdrawal processing automation tasks.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.withdrawal")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="wallet.process_pending_withdrawals")
def process_pending_withdrawals(self):
    """
    Process approved withdrawal requests via payment gateways.
    Runs every 15 minutes via Celery Beat.
    """
    try:
        from ..models import WithdrawalRequest
        from ..services import WithdrawalService

        approved = WithdrawalRequest.objects.filter(
            status="approved"
        ).select_related("wallet","payment_method","user")[:100]

        processed = failed = 0
        for wr in approved:
            try:
                result = _dispatch_to_gateway(wr)
                if result.get("success"):
                    WithdrawalService.complete(wr, gateway_ref=result.get("ref",""), gateway_resp=result)
                    processed += 1
                else:
                    wr.mark_failed(result.get("error","Gateway failed"))
                    failed += 1
            except Exception as e:
                logger.error(f"process_withdrawal wr={wr.withdrawal_id}: {e}")
                failed += 1

        return {"processed": processed, "failed": failed}
    except Exception as e:
        raise self.retry(exc=e)


def _dispatch_to_gateway(wr):
    """Dispatch withdrawal to appropriate gateway. Returns status dict."""
    pm = wr.payment_method
    if not pm:
        return {"success": False, "error": "No payment method"}
    gateway = pm.method_type
    logger.info(f"Dispatching {gateway} withdrawal {wr.withdrawal_id} amount={wr.net_amount}")
    # TODO: implement real gateway API calls (bKash B2C, Nagad, etc.)
    return {"success": False, "error": "Gateway not configured — manual processing required"}


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.auto_reject_stale_withdrawals")
def auto_reject_stale_withdrawals(self, hours: int = 72):
    """
    Auto-reject withdrawal requests stuck in pending for N hours.
    Runs daily at 1 AM.
    """
    try:
        from ..models import WithdrawalRequest
        from ..services import WithdrawalService

        cutoff = timezone.now() - timedelta(hours=hours)
        stale  = WithdrawalRequest.objects.filter(status="pending", created_at__lt=cutoff)
        count = 0
        for wr in stale:
            try:
                WithdrawalService.reject(wr, f"Auto-rejected after {hours}h inactivity")
                count += 1
            except Exception as e:
                logger.error(f"auto_reject wr={wr.withdrawal_id}: {e}")

        logger.info(f"Auto-rejected {count} stale withdrawals")
        return {"rejected": count}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.sync_gateway_statuses")
def sync_gateway_statuses(self):
    """
    Sync status of in-flight gateway transactions.
    Checks bKash/Nagad/Rocket APIs for pending completions.
    Runs every 10 minutes.
    """
    try:
        from ..models import WithdrawalRequest
        processing = WithdrawalRequest.objects.filter(
            status="processing"
        ).select_related("payment_method")[:50]

        updated = 0
        for wr in processing:
            try:
                # TODO: implement actual gateway status check
                logger.debug(f"Checking gateway status: wr={wr.withdrawal_id}")
            except Exception as e:
                logger.error(f"gateway_status_check wr={wr.withdrawal_id}: {e}")

        return {"checked": processing.count(), "updated": updated}
    except Exception as e:
        raise self.retry(exc=e)
