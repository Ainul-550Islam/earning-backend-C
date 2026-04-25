# api/wallet/tasks/withdrawal_batch_tasks.py
"""
Batch withdrawal processing tasks.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.batch")


@shared_task(bind=True, max_retries=3, default_retry_delay=120, name="wallet.process_withdrawal_batches")
def process_withdrawal_batches(self):
    """
    Process all pending withdrawal batches via gateway APIs.
    Runs every 30 minutes.
    """
    try:
        from ..services import WithdrawalBatchService
        from ..models import WithdrawalBatch

        pending_batches = WithdrawalBatch.objects.filter(status="pending")
        processed = failed = 0

        for batch in pending_batches:
            try:
                result = WithdrawalBatchService.process_batch(batch)
                if result["fail"] == 0:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"batch_process batch={batch.batch_id}: {e}")
                failed += 1

        return {"batches_processed": processed, "batches_failed": failed}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.auto_batch_approvals")
def auto_batch_approvals(self, gateway: str = "bkash", min_count: int = 5):
    """
    Automatically batch approved withdrawals of the same gateway.
    Runs hourly for bulk gateway efficiency.
    """
    try:
        from ..models import WithdrawalRequest
        from ..services import WithdrawalBatchService

        approved = WithdrawalRequest.objects.filter(
            status="approved",
            payment_method__method_type=gateway,
            batch__isnull=True,
        )

        if approved.count() >= min_count:
            ids = list(approved.values_list("id", flat=True)[:100])
            batch = WithdrawalBatchService.create_batch(gateway, ids)
            logger.info(f"Auto-batched {len(ids)} {gateway} withdrawals: {batch.batch_id}")
            return {"batch_id": str(batch.batch_id), "count": len(ids)}

        return {"status": "not_enough", "count": approved.count(), "min": min_count}
    except Exception as e:
        raise self.retry(exc=e)
