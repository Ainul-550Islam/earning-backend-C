# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""Replay Service

BUG FIX: this module did not exist at all, despite being imported by
tasks/replay_tasks.py, management/commands/replay_events.py, and (indirectly,
through those) tasks/auto_suspend_endpoints.py, tasks/integration_sync_tasks.py,
tasks/cleanup_tasks.py, tests/test_replay_service.py, and tests/test_tasks.py.
Found via a real per-file import check, not via the urls.py chain (viewsets/
WebhookReplayViewSet.py never needed this file since it has its own inline
logic - see note on batch methods below).

Batch-related methods (create_replay_batch, get_batch_progress, get_batch_status,
cancel handling) are adapted directly from the proven, already-working logic in
viewsets/WebhookReplayViewSet.py (create_batch/batch_progress/batch_status), kept
as close to that original logic as the different call signature allows.

process_replay/process_replay_batch (single-item and batch dispatch) are new
code written for this fix, using the existing, proven DispatchService.emit()/
retry_delivery() rather than duplicating HTTP-dispatch logic. These have not
been exercised by any existing passing test, unlike the batch-management
methods above - flagging that distinction honestly rather than presenting both
as equally proven.

preview_replay/start_batch_processing, used only by
management/commands/replay_events.py, are also new code with no existing
precedent elsewhere in the codebase to adapt from.
"""

import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from ..models import (
    WebhookReplay,
    WebhookReplayBatch,
    WebhookReplayItem,
    WebhookDeliveryLog,
    WebhookEndpoint,
)
from ..constants import ReplayStatus, DeliveryStatus
from .core.DispatchService import DispatchService

logger = logging.getLogger("ainul.webhooks.services.replay")


class ReplayService:
    """Service for creating, dispatching, and tracking webhook replays."""

    def __init__(self):
        self.dispatch_service = DispatchService()

    # ── Single-item replay (used by tasks.replay_tasks.process_replay) ────────

    def process_replay(self, replay: WebhookReplay) -> Dict[str, Any]:
        """Re-dispatch a single failed delivery and record the outcome.

        Creates a fresh WebhookDeliveryLog via DispatchService.emit() (rather
        than mutating the original log, unlike DispatchService.retry_delivery())
        so the original delivery history stays intact, matching what the
        WebhookReplay model's own original_log/new_log split implies.
        """
        start = time.monotonic()

        if replay.status == ReplayStatus.COMPLETED:
            return {"success": False, "error": "Replay is already completed",
                    "new_log_id": None, "new_log_status": None,
                    "processing_time": time.monotonic() - start}
        if replay.status == ReplayStatus.PROCESSING:
            return {"success": False, "error": "Replay is already processing",
                    "new_log_id": None, "new_log_status": None,
                    "processing_time": time.monotonic() - start}

        replay.status = ReplayStatus.PROCESSING
        replay.save(update_fields=["status"])

        original_log = replay.original_log
        endpoint = original_log.endpoint

        try:
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type=original_log.event_type,
                payload=original_log.payload,
                async_emit=False,
            )
        except Exception as exc:
            logger.error("process_replay: emit failed for replay %s: %s", replay.id, exc)
            replay.status = ReplayStatus.FAILED
            replay.replayed_at = timezone.now()
            replay.save(update_fields=["status", "replayed_at"])
            return {"success": False, "error": str(exc), "new_log_id": None,
                    "new_log_status": None, "processing_time": time.monotonic() - start}

        new_log_status = DeliveryStatus.SUCCESS if success else DeliveryStatus.FAILED
        new_log = WebhookDeliveryLog.objects.create(
            endpoint=endpoint,
            event_type=original_log.event_type,
            payload=original_log.payload,
            status=new_log_status,
        )

        replay.status = ReplayStatus.COMPLETED if success else ReplayStatus.FAILED
        replay.replayed_at = timezone.now()
        replay.new_log = new_log
        replay.save(update_fields=["status", "replayed_at", "new_log"])

        return {
            "success": success,
            "new_log_id": new_log.id,
            "new_log_status": new_log_status,
            "processing_time": time.monotonic() - start,
        }

    # ── Batch replay (adapted from WebhookReplayViewSet.create_batch/etc.) ────

    def create_replay_batch(
        self,
        delivery_logs=None,
        replayed_by_id=None,
        reason: str = "Batch replay",
        event_type: Optional[str] = None,
        event_type_filter: Optional[str] = None,
        from_date=None,
        to_date=None,
        batch_size: int = 100,
        user_id=None,
    ):
        """Create a replay batch.

        Accepts two call shapes because the two real callers in this codebase
        use different ones:
          - tasks.replay_tasks.create_replay_batch passes an explicit
            `delivery_logs` queryset/list plus `replayed_by_id` + `reason`,
            optionally narrowed further by `event_type_filter`.
          - management/commands/replay_events.py passes `event_type` /
            `from_date` / `to_date` / `batch_size` / `user_id` and expects a
            dict back (not a model instance) - see the `_as_dict` branch.
        """
        is_command_style = delivery_logs is None

        if is_command_style:
            qs = WebhookDeliveryLog.objects.filter(status__in=["failed", "exhausted"])
            if event_type:
                qs = qs.filter(event_type=event_type)
            if from_date:
                qs = qs.filter(created_at__date__gte=from_date)
            if to_date:
                qs = qs.filter(created_at__date__lte=to_date)
            delivery_logs = qs[:batch_size]
            replayed_by_id = user_id
            reason = f"Replay via management command ({event_type or 'ALL'})"

        delivery_logs = list(delivery_logs)
        if not delivery_logs:
            raise ValueError("delivery_logs must not be empty")
        if event_type_filter:
            delivery_logs = [log for log in delivery_logs if log.event_type == event_type_filter]

        today = timezone.now().date()
        batch = WebhookReplayBatch.objects.create(
            event_type=event_type or event_type_filter or "mixed",
            reason=reason,
            created_by_id=replayed_by_id,
            count=len(delivery_logs),
            date_from=from_date or today,
            date_to=to_date or today,
        )

        items = [
            WebhookReplayItem(
                batch=batch,
                original_log=log,
                status=ReplayStatus.PENDING,
            )
            for log in delivery_logs
        ]
        WebhookReplayItem.objects.bulk_create(items)

        if is_command_style:
            return {
                "batch_id": str(batch.pk),
                "event_count": len(delivery_logs),
                "batch": batch,
            }
        return batch

    def create_replay(self, original_log, replayed_by=None, reason: str = ""):
        """Create a single WebhookReplay record (not yet processed)."""
        if original_log is None:
            raise ValueError("original_log is required")
        if replayed_by is None:
            raise ValueError("replayed_by is required")
        if not reason:
            raise ValueError("reason is required")
        return WebhookReplay.objects.create(
            original_log=original_log,
            replayed_by=replayed_by,
            reason=reason,
            status=ReplayStatus.PENDING,
        )

    def process_replay_batch(self, batch: WebhookReplayBatch) -> Dict[str, Any]:
        """Process every pending WebhookReplayItem in a batch, sequentially.

        BUG FIX: previously queried WebhookReplay.objects.filter(batch=batch,
        ...) - WebhookReplay has no `batch` field at all (confirmed via a
        real FieldError), so this crashed on every call. Batch membership is
        tracked via WebhookReplayItem (batch, original_log, status), which
        is what create_replay_batch() actually populates.
        """
        start = time.monotonic()

        if batch.status == ReplayStatus.COMPLETED:
            return {"success": False, "error": "Batch is already completed",
                    "processing_time": time.monotonic() - start}
        if batch.status == ReplayStatus.PROCESSING:
            return {"success": False, "error": "Batch is already processing",
                    "processing_time": time.monotonic() - start}

        batch.status = ReplayStatus.PROCESSING
        batch.save(update_fields=["status"])

        items = WebhookReplayItem.objects.filter(batch=batch, status=ReplayStatus.PENDING)

        processed = success_count = failed_count = 0
        for item in items:
            original_log = item.original_log
            try:
                success = self.dispatch_service.emit(
                    endpoint=original_log.endpoint,
                    event_type=original_log.event_type,
                    payload=original_log.payload,
                    async_emit=False,
                )
            except Exception as exc:
                logger.error("process_replay_batch: emit failed for item %s: %s", item.id, exc)
                success = False

            item.status = ReplayStatus.COMPLETED if success else ReplayStatus.FAILED
            item.save(update_fields=["status"])

            processed += 1
            if success:
                success_count += 1
            else:
                failed_count += 1

        batch.status = ReplayStatus.COMPLETED if success_count > 0 or processed == 0 else ReplayStatus.FAILED
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at"])

        return {
            "success": success_count > 0,
            "processed_count": processed,
            "success_count": success_count,
            "failed_count": failed_count,
            "processing_time": time.monotonic() - start,
        }

    def get_batch_progress(self, batch_id) -> Dict[str, Any]:
        """Adapted from WebhookReplayViewSet.batch_progress.

        BUG FIX: was querying WebhookReplay.objects.filter(batch_id=...) -
        WebhookReplay has no batch field at all (confirmed via a real
        FieldError: "Cannot resolve keyword 'batch_id' into field"), so this
        crashed on every call. Same bug class already documented and fixed
        in process_replay_batch() above, just missed here during that same
        adaptation from WebhookReplayViewSet.batch_progress (which
        correctly queries WebhookReplayItem.objects.filter(batch=batch)).
        """
        items = WebhookReplayItem.objects.filter(batch_id=batch_id)
        total = items.count()
        completed = items.filter(status=ReplayStatus.COMPLETED).count()
        return {
            "total_items": total,
            "processed_items": completed + items.filter(status=ReplayStatus.FAILED).count(),
            "completion_percentage": round((completed / total) * 100, 1) if total else 0,
        }

    def get_batch_status(self, batch_id) -> Dict[str, Any]:
        """Adapted from WebhookReplayViewSet.batch_status."""
        batch = WebhookReplayBatch.objects.get(pk=batch_id)
        return {"status": batch.status, "batch_id": str(batch.pk)}

    def get_replay_batch_status(self, batch: WebhookReplayBatch) -> Dict[str, Any]:
        """Combined status+progress snapshot for a batch, given the object
        directly (unlike get_batch_status, which takes an id)."""
        items = WebhookReplayItem.objects.filter(batch=batch)
        total = items.count()
        completed = items.filter(status=ReplayStatus.COMPLETED).count()
        failed = items.filter(status=ReplayStatus.FAILED).count()
        return {
            'batch_id': batch.id,
            'status': batch.status,
            'total_items': total,
            'completed_items': completed,
            'failed_items': failed,
            'completion_percentage': round((completed / total) * 100, 2) if total else 0.0,
        }

    def start_batch_processing(self, batch: WebhookReplayBatch) -> bool:
        """Queue a batch for async processing, mirroring
        WebhookReplayViewSet.start_batch's use of the same Celery task.

        BUG FIX: previously set batch.status = "processing" unconditionally
        right after calling process_replay_batch.delay(...). Under
        CELERY_TASK_ALWAYS_EAGER=True (this test suite - possibly other
        eager-mode usage too), .delay() runs the task to completion
        synchronously before the next line even executes, so whatever real
        terminal status (completed/failed) processing just set got
        silently overwritten straight back to "processing" - permanently,
        since nothing else would ever revisit this row afterward. Combined
        with callers that poll until a terminal status (e.g.
        replay_events.py's _show_progress()), this risked a genuine
        infinite loop. Confirmed empirically (see FIXES_APPLIED_SESSION9.md
        for a 0-item-batch trace and a real-item end-to-end trace).

        Fixed by refreshing from the DB after delay() and only setting
        "processing" if the batch isn't already in a terminal state -
        correct either way: under eager execution delay() has already done
        the real work, so this becomes a no-op; under real async execution
        delay() returns almost immediately with the batch still "pending",
        so this still gives the original immediate "processing" signal
        while a real worker picks it up later.
        """
        try:
            from ..tasks import process_replay_batch
            process_replay_batch.delay(str(batch.pk))
            batch.refresh_from_db()
            if batch.status not in (ReplayStatus.COMPLETED, ReplayStatus.FAILED):
                batch.status = "processing"
                batch.save(update_fields=["status"])
            return True
        except Exception as exc:
            logger.error("start_batch_processing failed for batch %s: %s", batch.pk, exc)
            return False

    def preview_replay(
        self,
        event_type: Optional[str] = None,
        from_date=None,
        to_date=None,
        batch_size: int = 100,
        user_id=None,
    ) -> Dict[str, Any]:
        """Preview what create_replay_batch would do, without creating anything."""
        qs = WebhookDeliveryLog.objects.filter(status__in=["failed", "exhausted"])
        if event_type:
            qs = qs.filter(event_type=event_type)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        total = qs.count()
        return {
            "total_events": total,
            "estimated_batches": (total + batch_size - 1) // batch_size if batch_size else 0,
        }

    # ── Newer management/reporting methods (test-driven) ────────────────────

    def cancel_replay(self, replay: WebhookReplay, reason: str = "") -> Dict[str, Any]:
        """Cancel a pending replay. Fails if it's already completed/failed."""
        if replay.status in (ReplayStatus.COMPLETED, ReplayStatus.FAILED):
            return {'success': False, 'error': f"Replay is already {replay.status}"}

        replay.status = ReplayStatus.CANCELLED
        update_fields = ['status']
        if hasattr(replay, 'reason') and reason:
            replay.reason = reason
            update_fields.append('reason')
        replay.save(update_fields=update_fields)
        return {'success': True}

    def cancel_replay_batch(self, batch: WebhookReplayBatch, reason: str = "") -> Dict[str, Any]:
        """Cancel a replay batch. Fails if it's already completed."""
        if batch.status == ReplayStatus.COMPLETED:
            return {'success': False, 'error': "Batch is already completed"}

        batch.status = ReplayStatus.CANCELLED
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'completed_at'])
        return {'success': True}

    def get_replay_status(self, replay: WebhookReplay) -> Dict[str, Any]:
        """Point-in-time status snapshot for a single replay."""
        return {
            'replay_id': replay.id,
            'status': replay.status,
            'original_log_id': replay.original_log_id,
            'reason': getattr(replay, 'reason', ''),
            'new_log_id': replay.new_log_id,
            'replayed_at': replay.replayed_at,
        }

    def get_replay_statistics(self, endpoint: WebhookEndpoint = None, days: int = 30, event_type: str = None) -> Dict[str, Any]:
        """Replay success-rate statistics over a window, optionally scoped
        to one endpoint and/or event type."""
        since = timezone.now() - timedelta(days=days)
        replays = WebhookReplay.objects.filter(created_at__gte=since)
        if endpoint is not None:
            replays = replays.filter(original_log__endpoint=endpoint)
        if event_type is not None:
            replays = replays.filter(original_log__event_type=event_type)

        total = replays.count()
        completed = replays.filter(status=ReplayStatus.COMPLETED).count()
        failed = replays.filter(status=ReplayStatus.FAILED).count()
        pending = replays.filter(status=ReplayStatus.PENDING).count()
        success_rate = round((completed / total) * 100, 2) if total else 0.0

        return {
            'total_replays': total,
            'completed_replays': completed,
            'failed_replays': failed,
            'pending_replays': pending,
            'success_rate': success_rate,
        }

    def cleanup_old_replays(self, days: int = 90) -> Dict[str, Any]:
        """Delete WebhookReplay rows older than `days` (by created_at)."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = WebhookReplay.objects.filter(created_at__lt=cutoff).delete()
        return {'cleaned_count': deleted_count}

    def cleanup_old_replay_batches(self, days: int = 90) -> Dict[str, Any]:
        """Delete WebhookReplayBatch rows older than `days` (by created_at)."""
        cutoff = timezone.now() - timedelta(days=days)
        qs = WebhookReplayBatch.objects.filter(created_at__lt=cutoff)
        # .delete()'s first return value is the TOTAL rows deleted across
        # cascades (each batch cascades to its WebhookReplayItems too), not
        # just the batch count - count before deleting.
        batch_count = qs.count()
        qs.delete()
        return {'cleaned_count': batch_count}

    def get_replay_recommendations(self, endpoint: WebhookEndpoint, days: int = 30) -> List[str]:
        """Recommendation identifiers based on an endpoint's recent failure
        patterns, e.g. ['high_failure_rate', 'recent_failures']."""
        since = timezone.now() - timedelta(days=days)
        logs = WebhookDeliveryLog.objects.filter(endpoint=endpoint, created_at__gte=since)
        total = logs.count()
        if total == 0:
            return []

        failed = logs.filter(status__in=["failed", "exhausted"]).count()
        recommendations = []
        if total and (failed / total) > 0.3:
            recommendations.append('high_failure_rate')
        recent_since = timezone.now() - timedelta(hours=24)
        if logs.filter(status__in=["failed", "exhausted"], created_at__gte=recent_since).exists():
            recommendations.append('recent_failures')

        return recommendations

    def validate_replay_eligibility(self, delivery_log: WebhookDeliveryLog, max_age_days: int = 7) -> Dict[str, Any]:
        """Check whether a delivery log is eligible for replay: must have
        actually failed, not already have a pending/completed replay, and
        not be older than max_age_days."""
        if delivery_log.status not in ("failed", "exhausted"):
            return {'eligible': False, 'reason': 'Log is already successful'}

        if WebhookReplay.objects.filter(original_log=delivery_log).exists():
            return {'eligible': False, 'reason': 'This log was already replayed'}

        cutoff = timezone.now() - timedelta(days=max_age_days)
        if delivery_log.created_at < cutoff:
            return {'eligible': False, 'reason': f'Log is too old to replay (> {max_age_days} days)'}

        return {'eligible': True, 'reason': ''}
