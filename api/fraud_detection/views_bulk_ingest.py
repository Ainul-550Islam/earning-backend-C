# =============================================================================
# fraud_detection/views_bulk_ingest.py  — BULK TRANSACTION INGEST API
#
# Business purpose:
#   - Accept 1-10,000 transactions in a single API call
#   - Fan out to Celery workers for async fraud scoring
#   - Return a batch_id for polling results
#   - Support synchronous mode for small batches (≤20 records)
# DRY: fraud-check logic delegates to FraudDetectionService
# =============================================================================
from __future__ import annotations
import logging
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

logger = logging.getLogger(__name__)

MAX_SYNC_BATCH  = 20
MAX_ASYNC_BATCH = 10_000


class BulkTransactionIngestAPIView(APIView):
    """
    POST /bulk-ingest/transactions/
    Body: { "transactions": [...], "mode": "async"|"sync" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        transactions = request.data.get("transactions", [])
        mode         = request.data.get("mode", "async")

        if not transactions:
            return Response({"error": "transactions list is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(transactions) > MAX_ASYNC_BATCH:
            return Response(
                {"error": f"Maximum {MAX_ASYNC_BATCH} transactions per batch"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch_id = str(uuid.uuid4())

        # ── Synchronous mode (≤20 records, returns results immediately) ──────
        if mode == "sync" and len(transactions) <= MAX_SYNC_BATCH:
            results = self._process_sync(transactions, batch_id, request.user.pk)
            return Response({
                "batch_id": batch_id,
                "mode":     "sync",
                "count":    len(transactions),
                "results":  results,
            }, status=status.HTTP_200_OK)

        # ── Async mode (all sizes, poll for results) ─────────────────────────
        self._enqueue_batch(transactions, batch_id, request.user.pk)
        return Response({
            "batch_id":   batch_id,
            "mode":       "async",
            "count":      len(transactions),
            "status":     "queued",
            "poll_url":   f"/api/fraud/bulk-ingest/batches/{batch_id}/status/",
        }, status=status.HTTP_202_ACCEPTED)

    def _process_sync(self, transactions, batch_id, user_id):
        from api.fraud_detection.services import get_fraud_detection_service
        svc     = get_fraud_detection_service()
        results = []
        for i, tx in enumerate(transactions):
            try:
                result = svc.check_user(
                    tx.get("user_id", user_id), tx
                )
                results.append({
                    "index":      i,
                    "tx_id":      tx.get("transaction_id", f"tx_{i}"),
                    "risk_score": result.get("risk_score", 0),
                    "is_fraud":   result.get("risk_score", 0) >= 70,
                    "status":     "scored",
                })
            except Exception as exc:
                results.append({"index": i, "status": "error", "error": str(exc)})
        return results

    def _enqueue_batch(self, transactions, batch_id, user_id):
        try:
            from api.fraud_detection.tasks import batch_risk_assessment
            user_ids = list({tx.get("user_id", user_id) for tx in transactions})
            job = batch_risk_assessment.apply_async(
                args=[user_ids],
                task_id=batch_id,
            )
            from django.core.cache import cache
            cache.set(f"bulk_batch:{batch_id}", {
                "batch_id":   batch_id,
                "count":      len(transactions),
                "user_id":    str(user_id),
                "status":     "queued",
                "task_id":    job.id,
            }, timeout=3600)
        except Exception as exc:
            logger.error("_enqueue_batch %s: %s", batch_id, exc)
            raise


class BulkBatchStatusAPIView(APIView):
    """GET /bulk-ingest/batches/<batch_id>/status/ — poll async batch status."""
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id: str):
        from django.core.cache import cache
        batch = cache.get(f"bulk_batch:{batch_id}")
        if not batch:
            return Response({"error": "Batch not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            from celery.result import AsyncResult
            task   = AsyncResult(batch.get("task_id", batch_id))
            rstatus = task.status
            result  = task.result if task.ready() else None
        except Exception:
            rstatus = "unknown"
            result  = None
        return Response({
            "batch_id": batch_id,
            "count":    batch.get("count", 0),
            "status":   rstatus,
            "result":   result,
        })


class BulkUserRiskIngestAPIView(APIView):
    """
    POST /bulk-ingest/risk-scores/
    Bulk recalculate risk scores for a list of user IDs.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_ids = request.data.get("user_ids", [])
        if not user_ids:
            return Response({"error": "user_ids required"},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(user_ids) > MAX_ASYNC_BATCH:
            return Response({"error": f"Max {MAX_ASYNC_BATCH} user_ids"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from api.fraud_detection.tasks import calculate_user_risk_scores
            job = calculate_user_risk_scores.apply_async(args=[user_ids])
            return Response({
                "task_id":  job.id,
                "count":    len(user_ids),
                "status":   "queued",
                "poll_url": f"/api/fraud/tasks/{job.id}/status/",
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            logger.error("BulkUserRiskIngestAPIView: %s", exc)
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
