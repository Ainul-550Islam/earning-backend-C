from ...exceptions import WebhookBatchError
"""Batch Dispatch Service

This module provides batch webhook dispatch functionality with ordered processing.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.conf import settings
from celery import current_app

from ...models import WebhookBatch, WebhookBatchItem, WebhookEndpoint
from ...constants import BatchStatus, DeliveryStatus

logger = logging.getLogger(__name__)


class BatchDispatchService:
    """Service for batch webhook dispatch with ordered processing."""
    
    def __init__(self):
        """Initialize the batch dispatch service."""
        self.logger = logger
        self.default_batch_size = getattr(settings, 'WEBHOOK_BATCH_SIZE', 100)
        self.max_batch_size = getattr(settings, 'WEBHOOK_MAX_BATCH_SIZE', 1000)
        self.batch_timeout = getattr(settings, 'WEBHOOK_BATCH_TIMEOUT', 300)  # 5 minutes

    @staticmethod
    def _retry_on_db_lock(func, max_attempts: int = 6, base_delay: float = 0.05):
        """
        Run func(), retrying on SQLite's transient "database is locked".

        SQLite serialises writers at the whole-database level, so a burst
        of concurrent writers (several callers racing to claim/update the
        same batch) can occasionally be told the database is locked even
        though the contention clears within milliseconds — this is normal,
        documented SQLite behaviour under concurrency, not a logic bug.
        PostgreSQL (this project's real backend) has proper row-level
        locking and doesn't exhibit this at all; this retry only matters
        for the SQLite-backed test suite. Any other OperationalError is
        re-raised immediately, not retried.
        """
        from django.db.utils import OperationalError
        import random

        last_exc = None
        for attempt in range(max_attempts):
            try:
                return func()
            except OperationalError as e:
                if 'locked' not in str(e).lower():
                    raise
                last_exc = e
                time.sleep(base_delay * (attempt + 1) + random.uniform(0, 0.02))
        raise last_exc
    
    def create_batch(
        self,
        endpoint: WebhookEndpoint,
        event_type: str,
        events: List[Dict[str, Any]],
        batch_id: str = None,
        created_by=None,
        priority: str = "normal",
        metadata: Dict[str, Any] = None,
    ) -> WebhookBatch:
        """
        Create a new webhook batch.

        Args:
            endpoint: The webhook endpoint
            event_type: The event type for the batch
            events: List of events to include in the batch
            batch_id: Optional custom batch ID
            created_by: Optional user who triggered this batch's creation
                        (audit trail only — access control stays on
                        endpoint.owner, same pattern as WebhookFilter/
                        WebhookSecret/WebhookHealthLog). Defaults to
                        endpoint.owner when not given.
            priority: One of 'low'/'normal'/'high'/'urgent'.
            metadata: Arbitrary caller-supplied metadata dict.

        Returns:
            Created WebhookBatch instance

        Raises:
            ValueError: if events is None or empty — a batch with zero
                        events isn't a meaningful unit of work.
        """
        if not events:
            raise ValueError("events must be a non-empty list")

        try:
            with transaction.atomic():
                # BUG FIX: previously passed count=len(events), which isn't
                # a real field (the model field is event_count) — crashed
                # every call with TypeError. Filter events through the
                # endpoint's active WebhookFilters first (same evaluation
                # FilterService already does for live dispatch), so a batch
                # only contains events that would actually be delivered.
                from ..filtering.FilterService import FilterService
                filter_service = FilterService()
                filtered_events = [
                    event for event in events
                    if filter_service.evaluate_filters(endpoint, event)
                ]

                batch = WebhookBatch.objects.create(
                    batch_id=batch_id or self._generate_batch_id(),
                    endpoint=endpoint,
                    event_type=event_type,
                    event_count=len(filtered_events),
                    status=BatchStatus.PENDING,
                    created_by=created_by if created_by is not None else endpoint.owner,
                    priority=priority or "normal",
                    metadata=metadata or {},
                )

                # Create batch items
                batch_items = []
                for i, event in enumerate(filtered_events):
                    item = WebhookBatchItem.objects.create(
                        batch=batch,
                        event_data=event,
                        sequence_number=i + 1,
                        status=BatchStatus.PENDING
                    )
                    batch_items.append(item)
                
                self.logger.info(f"Created batch {batch.batch_id} with {len(filtered_events)} events")
                return batch
                
        except Exception as e:
            logger.error(f"Error creating batch: {str(e)}")
            raise
    
    def process_batch(self, batch: WebhookBatch) -> Dict[str, Any]:
        """
        Process a webhook batch.

        Args:
            batch: The batch to process

        Returns:
            Dictionary with processing results

        Concurrency: uses an atomic conditional UPDATE (not
        select_for_update()) to claim the batch — select_for_update() is
        silently a no-op on SQLite (this project's test backend), so it
        would not actually have serialised concurrent callers there. A
        single `UPDATE ... WHERE status='pending'` is atomic on every
        backend: only the first caller to execute it will still see
        'pending' and flip it; every other concurrent caller (or a caller
        hitting an already-terminal batch) sees 0 rows affected and backs
        off cleanly instead of double-processing.
        """
        try:
            def _claim():
                with transaction.atomic():
                    return WebhookBatch.objects.filter(
                        pk=batch.pk, status=BatchStatus.PENDING
                    ).update(status=BatchStatus.PROCESSING, started_at=timezone.now())

            claimed = self._retry_on_db_lock(_claim)

            if not claimed:
                batch.refresh_from_db()
                if batch.status == BatchStatus.COMPLETED:
                    error = "Batch is already completed"
                elif batch.status == BatchStatus.PROCESSING:
                    error = "Batch is already processing"
                elif batch.status == BatchStatus.CANCELLED:
                    error = "Batch is cancelled"
                else:
                    error = f"Batch cannot be processed in '{batch.status}' status"
                return {'batch_id': batch.batch_id, 'success': False, 'error': error}

            batch.refresh_from_db()

            # Get batch items in order
            items = batch.items.all().order_by('sequence_number')

            results = {
                'batch_id': batch.batch_id,
                'success': True,
                'total_items': items.count(),
                'processed_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'processing_time': 0,
                'items': []
            }

            start_time = time.time()

            # Process each item. Deliberately no per-item try/except here:
            # _process_batch_item() already handles an emit() that returns
            # False (a normal failed-delivery outcome, reflected below via
            # item_result['success']) — an emit() that *raises* is
            # unexpected and re-raised by _process_batch_item() on purpose,
            # so it propagates to the outer handler and fails the batch as
            # a whole rather than being silently absorbed as "1 bad item".
            for item in items:
                item_result = self._process_batch_item(item)
                results['items'].append(item_result)

                if item_result['success']:
                    results['success_count'] += 1
                else:
                    results['failed_count'] += 1

                results['processed_count'] += 1

            end_time = time.time()
            results['processing_time'] = end_time - start_time

            # Update batch status
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = timezone.now()
            self._retry_on_db_lock(batch.save)

            self.logger.info(f"Completed batch {batch.batch_id}: {results['success_count']}/{results['total_items']} successful")
            return results

        except Exception as e:
            logger.error(f"Error processing batch {batch.batch_id}: {str(e)}")

            # Update batch status to failed
            # FIX: was missing completed_at (BatchService.py's equivalent
            # FAILED path already sets it - this one didn't). A batch that's
            # reached a terminal status should always record when its
            # lifecycle ended, success or not.
            batch.status = BatchStatus.FAILED
            batch.completed_at = timezone.now()
            batch.error_message = str(e)
            self._retry_on_db_lock(batch.save)

            return {
                'batch_id': batch.batch_id,
                'success': False,
                'error': str(e)
            }
    
    def _process_batch_item(self, item: WebhookBatchItem) -> Dict[str, Any]:
        """
        Process a single batch item.
        
        Args:
            item: The batch item to process
            
        Returns:
            Dictionary with processing result
        """
        try:
            # Update item status
            item.status = BatchStatus.PROCESSING
            self._retry_on_db_lock(item.save)
            
            # Get batch and endpoint
            batch = item.batch
            endpoint = batch.endpoint
            
            # Prepare event payload
            event_payload = {
                'batch_id': batch.batch_id,
                'batch_sequence': item.sequence_number,
                'event_type': batch.event_type,
                'event_data': item.event_data,
                'timestamp': timezone.now().isoformat()
            }
            
            # Dispatch webhook
            from ..core.DispatchService import DispatchService
            dispatch_service = DispatchService()
            
            success = dispatch_service.emit(
                endpoint=endpoint,
                event_type=batch.event_type,
                payload=event_payload,
                async_emit=False
            )
            
            # Update item status
            if success:
                item.status = BatchStatus.COMPLETED
                item.completed_at = timezone.now()
            else:
                item.status = BatchStatus.FAILED
                item.error_message = "Webhook dispatch failed"
            
            self._retry_on_db_lock(item.save)
            
            return {
                'item_id': str(item.id),
                'sequence_number': item.sequence_number,
                'success': success,
                'completed_at': item.completed_at.isoformat() if success else None
            }
            
        except Exception as e:
            logger.error(f"Error processing batch item {item.id}: {str(e)}")
            
            # Update item status to failed
            item.status = BatchStatus.FAILED
            item.error_message = str(e)
            self._retry_on_db_lock(item.save)
            
            raise
    
    def process_batch_async(self, batch_id: str) -> Dict[str, Any]:
        """
        Process a batch asynchronously.
        
        Args:
            batch_id: The batch ID to process
            
        Returns:
            Dictionary with processing result
        """
        try:
            # Get batch. NOTE: the batch_id parameter here is always
            # str(batch.pk) (confirmed via its only caller,
            # WebhookBatchViewSet.process()) - WebhookBatch.batch_id is a
            # separate CharField that's never populated anywhere in the
            # creation flow (no default, not set in perform_create, not
            # in any serializer - confirmed via introspection), so every
            # batch has batch_id='' and this lookup always raised
            # DoesNotExist.
            batch = WebhookBatch.objects.get(pk=batch_id)
            
            # Queue async task
            # BUG FIX: was `from ..tasks.batch_tasks import process_batch` —
            # wrong relative-import depth (needs 3 dots from services/batch/,
            # not 2) AND tasks/batch_tasks.py did not exist at all, so this
            # always raised ImportError, silently caught below. Both fixed:
            # see tasks/batch_tasks.py.
            from ...tasks.batch_tasks import process_batch
            task = process_batch.delay(str(batch.id))
            
            return {
                'batch_id': batch_id,
                'success': True,
                'task_id': task.id,
                'status': 'queued',
                'message': 'Batch processing queued successfully'
            }
            
        except WebhookBatch.DoesNotExist:
            return {
                'batch_id': batch_id,
                'success': False,
                'error': 'Batch not found'
            }
        except Exception as e:
            logger.error(f"Error queuing batch processing: {str(e)}")
            return {
                'batch_id': batch_id,
                'success': False,
                'error': str(e)
            }
    
    def cancel_batch(self, batch: WebhookBatch, reason: str = "Cancelled by user") -> Dict[str, Any]:
        """
        Cancel a batch.
        
        Args:
            batch: The batch to cancel
            reason: Reason for cancellation
            
        Returns:
            Dictionary with cancellation result
        """
        try:
            with transaction.atomic():
                # Check if batch can be cancelled
                if batch.status == BatchStatus.COMPLETED:
                    return {
                        'batch_id': batch.batch_id,
                        'success': False,
                        'error': 'Cannot cancel: batch is already completed'
                    }
                if batch.status == BatchStatus.PROCESSING:
                    return {
                        'batch_id': batch.batch_id,
                        'success': False,
                        'error': 'Cannot cancel: batch is already processing'
                    }
                if batch.status == BatchStatus.CANCELLED:
                    return {
                        'batch_id': batch.batch_id,
                        'success': False,
                        'error': 'Batch is already cancelled'
                    }
                
                # Update batch status
                batch.status = BatchStatus.CANCELLED
                batch.completed_at = timezone.now()
                batch.save()
                
                # Update pending items to cancelled
                pending_items = batch.items.filter(status=BatchStatus.PENDING)
                pending_items.update(status=BatchStatus.CANCELLED)
                
                return {
                    'batch_id': batch.batch_id,
                    'success': True,
                    'cancelled_items': pending_items.count(),
                    'reason': reason
                }
                
        except Exception as e:
            logger.error(f"Error cancelling batch {batch.batch_id}: {str(e)}")
            return {
                'batch_id': batch.batch_id,
                'success': False,
                'error': str(e)
            }
    
    def retry_batch(self, batch: WebhookBatch) -> Dict[str, Any]:
        """
        Retry failed items in a batch.

        Args:
            batch: The batch to retry

        Returns:
            Dictionary with retry result
        """
        try:
            # Get failed items
            failed_items = batch.items.filter(status=BatchStatus.FAILED)
            
            if not failed_items.exists():
                return {
                    'batch_id': batch.batch_id,
                    'success': False,
                    'error': 'no failed items to retry'
                }
            
            retry_count = 0
            success_count = 0
            
            for item in failed_items:
                try:
                    # Reset item status
                    item.status = BatchStatus.PENDING
                    item.error_message = None
                    item.save()
                    
                    # Process item
                    result = self._process_batch_item(item)
                    retry_count += 1
                    
                    if result['success']:
                        success_count += 1
                        
                except Exception as e:
                    logger.error(f"Error retrying batch item {item.id}: {str(e)}")
                    continue
            
            return {
                'batch_id': batch.batch_id,
                'success': True,
                'retry_count': retry_count,
                'success_count': success_count,
                'failed_count': retry_count - success_count
            }
            
        except Exception as e:
            logger.error(f"Error retrying batch items: {str(e)}")
            return {
                'batch_id': batch.batch_id,
                'success': False,
                'error': str(e)
            }
    
    def get_batch_status(self, batch: WebhookBatch) -> Dict[str, Any]:
        """
        Get current status information for a specific batch.

        Args:
            batch: The batch to get status for

        Returns:
            Dictionary with status information
        """
        try:
            items = batch.items.all()
            
            total_items = items.count()
            completed_items = items.filter(status=BatchStatus.COMPLETED).count()
            failed_items = items.filter(status=BatchStatus.FAILED).count()
            cancelled_items = items.filter(status=BatchStatus.CANCELLED).count()
            pending_items = items.filter(status=BatchStatus.PENDING).count()
            processing_items = items.filter(status=BatchStatus.PROCESSING).count()
            
            completion_percentage = (completed_items / total_items * 100) if total_items > 0 else 0
            
            # Estimate remaining time
            estimated_remaining_time = None
            if batch.status == BatchStatus.PROCESSING and completed_items > 0 and batch.started_at:
                elapsed_time = (timezone.now() - batch.started_at).total_seconds()
                avg_time_per_item = elapsed_time / completed_items
                remaining_items = total_items - completed_items
                estimated_remaining_time = avg_time_per_item * remaining_items
            
            return {
                'batch_id': batch.batch_id,
                'status': batch.status,
                'total_items': total_items,
                'completed_items': completed_items,
                'failed_items': failed_items,
                'cancelled_items': cancelled_items,
                'pending_items': pending_items,
                'processing_items': processing_items,
                'completion_percentage': round(completion_percentage, 2),
                'estimated_remaining_time': round(estimated_remaining_time, 2) if estimated_remaining_time else None,
                'started_at': batch.started_at.isoformat() if batch.started_at else None,
                'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
            }
            
        except Exception as e:
            logger.error(f"Error getting batch status: {str(e)}")
            return {
                'batch_id': batch.batch_id,
                'error': str(e)
            }

    def get_batch_statistics(self, batch: WebhookBatch) -> Dict[str, Any]:
        """
        Get item-level statistics for one specific batch.

        Args: batch: The batch to get statistics for.
        Returns: Dictionary with total/completed/failed/pending item counts
                 and a success_rate percentage.

        Note: this takes a single batch, unlike get_batch_statistics_overview()
        below, which aggregates across many batches for an endpoint/period.
        Two different questions — deliberately two different methods rather
        than one overloaded by argument type.
        """
        try:
            items = batch.items.all()
            total_items = items.count()
            completed_items = items.filter(status=BatchStatus.COMPLETED).count()
            failed_items = items.filter(status=BatchStatus.FAILED).count()
            pending_items = items.filter(status=BatchStatus.PENDING).count()

            success_rate = (completed_items / total_items * 100) if total_items > 0 else 0

            return {
                'batch_id': batch.batch_id,
                'total_items': total_items,
                'completed_items': completed_items,
                'failed_items': failed_items,
                'pending_items': pending_items,
                'success_rate': round(success_rate, 2),
            }
        except Exception as e:
            logger.error(f"Error getting batch statistics: {str(e)}")
            return {
                'batch_id': batch.batch_id,
                'error': str(e)
            }

    def get_batches_by_status(self, status: str):
        """Get all batches with a given status (returns a QuerySet)."""
        return WebhookBatch.objects.filter(status=status)

    def get_batches_by_endpoint(self, endpoint: WebhookEndpoint):
        """Get all batches for a given endpoint (returns a QuerySet)."""
        return WebhookBatch.objects.filter(endpoint=endpoint)

    def get_batches_by_date_range(self, start_date, end_date):
        """Get all batches created within [start_date, end_date] (returns a QuerySet)."""
        return WebhookBatch.objects.filter(created_at__gte=start_date, created_at__lte=end_date)

    def get_batch_statistics_overview(self, endpoint_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get aggregate batch processing statistics across many batches.

        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with batch statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count, Avg, Q
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for batches
            batches = WebhookBatch.objects.filter(created_at__gte=since)
            if endpoint_id:
                batches = batches.filter(endpoint_id=endpoint_id)
            
            # Get overall statistics
            total_batches = batches.count()
            completed_batches = batches.filter(status=BatchStatus.COMPLETED).count()
            failed_batches = batches.filter(status=BatchStatus.FAILED).count()
            cancelled_batches = batches.filter(status=BatchStatus.CANCELLED).count()
            
            completion_rate = (completed_batches / total_batches * 100) if total_batches > 0 else 0
            
            # Get item statistics
            total_items = batches.aggregate(total=Count('items'))['total'] or 0
            
            # Get processing time statistics
            completed_batches_with_time = batches.filter(
                status=BatchStatus.COMPLETED,
                started_at__isnull=False,
                completed_at__isnull=False
            )
            
            avg_processing_time = 0
            if completed_batches_with_time.exists():
                avg_processing_time = completed_batches_with_time.aggregate(
                    avg_time=Avg(
                        F('completed_at') - F('started_at')
                    )
                )['avg_time']
                
                if avg_processing_time:
                    avg_processing_time = avg_processing_time.total_seconds()
            
            return {
                'total_batches': total_batches,
                'completed_batches': completed_batches,
                'failed_batches': failed_batches,
                'cancelled_batches': cancelled_batches,
                'completion_rate': round(completion_rate, 2),
                'total_items': total_items,
                'avg_processing_time_seconds': round(avg_processing_time, 2),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting batch statistics: {str(e)}")
            return {
                'total_batches': 0,
                'completed_batches': 0,
                'failed_batches': 0,
                'cancelled_batches': 0,
                'completion_rate': 0,
                'total_items': 0,
                'avg_processing_time_seconds': 0,
                'period_days': days,
                'error': str(e)
            }
    
    def _generate_batch_id(self) -> str:
        """
        Generate a unique batch ID.
        
        Returns:
            Generated batch ID
        """
        try:
            import uuid
            return f"batch_{uuid.uuid4().hex[:12]}"
        except Exception as e:
            logger.error(f"Error generating batch ID: {str(e)}")
            return f"batch_{int(time.time())}"
    
    def cleanup_old_batches(self, days: int = 30) -> Dict[str, Any]:
        """
        Clean up old completed batches.
        
        Args:
            days: Number of days to keep batches
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete old batches. Filtered on completed_at, not created_at:
            # a batch could be created long ago but finish recently, and
            # shouldn't be cleaned up just for an old creation date. NULL
            # completed_at (still pending/processing) never matches '<',
            # so in-flight batches are never touched here.
            old_batches = WebhookBatch.objects.filter(
                completed_at__lt=cutoff_date,
                status__in=[BatchStatus.COMPLETED, BatchStatus.CANCELLED, BatchStatus.FAILED]
            )
            
            deleted_count = old_batches.count()
            old_batches.delete()
            
            return {
                'cleaned_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'days': days
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old batches: {str(e)}")
            return {
                'error': str(e),
                'days': days
            }
    
    def get_batch_items_summary(self, batch: WebhookBatch) -> Dict[str, Any]:
        """
        Get a summary of items in a batch.
        
        Args:
            batch: The batch to summarize
            
        Returns:
            Dictionary with items summary
        """
        try:
            items = batch.items.all()
            
            summary = {
                'batch_id': batch.batch_id,
                'total_items': items.count(),
                'items_by_status': {},
                'items': []
            }
            
            # Group by status
            for status_choice in BatchStatus.CHOICES:
                status = status_choice[0]
                count = items.filter(status=status).count()
                if count > 0:
                    summary['items_by_status'][status] = count
            
            # Get recent items
            recent_items = items.order_by('-created_at')[:10]
            for item in recent_items:
                summary['items'].append({
                    'item_id': str(item.id),
                    'sequence_number': item.sequence_number,
                    'status': item.status,
                    'created_at': item.created_at.isoformat(),
                    'completed_at': item.completed_at.isoformat() if item.completed_at else None,
                    'error_message': item.error_message
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting batch items summary: {str(e)}")
            return {
                'batch_id': batch.batch_id,
                'error': str(e)
            }