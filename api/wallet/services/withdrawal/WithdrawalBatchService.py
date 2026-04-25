# api/wallet/services/withdrawal/WithdrawalBatchService.py
"""
Batch withdrawal processing — group multiple requests into a single gateway call.
Used for bKash B2C bulk transfers and similar batch APIs.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ...models import WithdrawalBatch, WithdrawalRequest
from ...choices import WithdrawalStatus

logger = logging.getLogger("wallet.service.withdrawal_batch")


class WithdrawalBatchService:

    @staticmethod
    @transaction.atomic
    def create_batch(gateway: str, request_ids: list, created_by=None, notes: str = "") -> WithdrawalBatch:
        """
        Group a list of approved WithdrawalRequest IDs into a batch.
        All requests must be in APPROVED status and same gateway.
        """
        requests = WithdrawalRequest.objects.filter(
            id__in=request_ids,
            status=WithdrawalStatus.APPROVED,
            payment_method__method_type=gateway,
        ).select_related("wallet")

        if not requests.exists():
            raise ValueError("No valid approved withdrawal requests found for batch")

        total = sum(r.net_amount for r in requests)

        batch = WithdrawalBatch.objects.create(
            gateway=gateway,
            total_amount=total,
            total_count=requests.count(),
            created_by=created_by,
            notes=notes,
        )

        requests.update(batch=batch, status=WithdrawalStatus.BATCHED)
        logger.info(f"Batch created: {batch.batch_id} gateway={gateway} count={batch.total_count} total={total}")
        return batch

    @staticmethod
    @transaction.atomic
    def process_batch(batch: WithdrawalBatch, gateway_response: dict = None) -> dict:
        """
        Process a batch — call gateway API and update individual request statuses.
        Returns summary dict.
        """
        batch.status     = "processing"
        batch.started_at = timezone.now()
        batch.save(update_fields=["status", "started_at"])

        requests = batch.withdrawal_requests.filter(status=WithdrawalStatus.BATCHED)
        ok = fail = 0

        for wr in requests:
            try:
                from .WithdrawalService import WithdrawalService
                WithdrawalService.complete(
                    wr,
                    gateway_ref=gateway_response.get("batch_ref","") if gateway_response else "",
                    gateway_resp=gateway_response or {},
                )
                ok += 1
            except Exception as e:
                wr.mark_failed(str(e))
                fail += 1
                logger.error(f"Batch item failed wr={wr.withdrawal_id}: {e}")

        batch.processed_count = ok
        batch.failed_count    = fail
        batch.status          = "completed" if fail == 0 else ("partial" if ok > 0 else "failed")
        batch.gateway_response = gateway_response or {}
        batch.completed_at    = timezone.now()
        batch.save()

        logger.info(f"Batch processed: {batch.batch_id} ok={ok} fail={fail}")
        return {"batch_id": str(batch.batch_id), "ok": ok, "fail": fail}

    @staticmethod
    def get_pending_batches() -> "QuerySet":
        return WithdrawalBatch.objects.filter(status="pending").select_related("created_by")
