"""Retry Failed Dispatch Task

This module contains the background task for retrying failed webhook deliveries.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from ..models import WebhookDeliveryLog
from ..services.core.DispatchService import DispatchService
from ..constants import DeliveryStatus

import logging

logger = logging.getLogger('ainul.webhooks.tasks.retry.failed.dispatch')



@shared_task(bind=True, max_retries=3, name="ainul.webhooks.retry_failed_dispatch")
def retry_failed_dispatch(self, delivery_log_id):
    """
    Retry a failed webhook delivery.
    
    Args:
        delivery_log_id: The ID of the delivery log to retry
        
    Returns:
        dict: Result of the retry operation
    """
    logger.info('[Task] retry_failed_dispatch started')
    try:
        # Get the delivery log
        delivery_log = WebhookDeliveryLog.objects.get(id=delivery_log_id)
        
        # Check if it's eligible for retry
        if delivery_log.status != DeliveryStatus.FAILED:
            return {
                'success': False,
                'reason': 'Delivery log is not in failed status',
                'delivery_log_id': str(delivery_log_id)
            }
        
        # Check if we've exceeded max attempts
        if delivery_log.attempt_number >= delivery_log.max_attempts:
            # Mark as exhausted
            delivery_log.status = DeliveryStatus.EXHAUSTED
            delivery_log.save()
            
            return {
                'success': False,
                'reason': 'Maximum retry attempts exceeded',
                'delivery_log_id': str(delivery_log_id)
            }
        
        # Check if it's time to retry
        if delivery_log.next_retry_at and delivery_log.next_retry_at > timezone.now():
            return {
                'success': False,
                'reason': 'Not yet time to retry',
                'delivery_log_id': str(delivery_log_id),
                'next_retry_at': delivery_log.next_retry_at.isoformat()
            }
        
        # Perform the retry
        dispatch_service = DispatchService()
        result = dispatch_service.retry_delivery(delivery_log)
        
        return {
            'success': result,
            'delivery_log_id': str(delivery_log_id),
            'attempt_number': delivery_log.attempt_number
        }
        
    except WebhookDeliveryLog.DoesNotExist:
        return {
            'success': False,
            'reason': 'Delivery log not found',
            'delivery_log_id': str(delivery_log_id)
        }
    except Exception as e:
        # Retry the task if there's an unexpected error
        raise self.retry(exc=e, countdown=60)


@shared_task
def retry_all_failed_dispatches():
    """
    Queue retry tasks for all failed deliveries that are ready.

    DRY FIX:
        - Replaced the model-namespaced F() call (missing import caused
          NameError) with F() imported directly from django.db.models
        - Replaced the bare print statement with logger.error()
        - Removed success_count that was 0 forever; renamed to queued_count for accuracy

    Returns:
        dict: Summary of queued retries.
    """
    from django.db.models import F  # DRY FIX: the model-namespaced F() call was used without an import → NameError
    logger.info("[Task] retry_all_failed_dispatches started")

    ready_retries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        attempt_number__lt=F("max_attempts"),
    ).filter(
        Q(next_retry_at__lte=timezone.now()) | Q(next_retry_at__isnull=True)
    )

    total_eligible = ready_retries.count()  # capture before iterating
    queued_count = 0
    failed_count = 0

    for delivery_log in ready_retries:
        try:
            retry_failed_dispatch.delay(str(delivery_log.id))
            queued_count += 1
        except Exception as e:
            failed_count += 1
            logger.error("Failed to queue retry for %s: %s", delivery_log.id, e)

    return {
        "total_eligible": total_eligible,
        "queued_count": queued_count,
        "failed_count": failed_count,
    }


@shared_task
def schedule_failed_retries():
    """
    Schedule retry times for failed deliveries that have none yet.

    DRY FIX: Removed manual backoff calculation and delivery_log.save() that
    duplicated the logic already in DispatchService.schedule_retry(). That
    method is the single canonical implementation of retry scheduling with
    exponential backoff. Also fixed models.F() → F() and print() → logger.

    Returns:
        dict: Summary of scheduled retries.
    """
    from django.db.models import F  # DRY FIX: was models.F() → NameError
    logger.info("[Task] schedule_failed_retries started")

    dispatch_service = DispatchService()

    failed_deliveries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        next_retry_at__isnull=True,
        attempt_number__lt=F("max_attempts"),
    ).select_related("endpoint")

    total_eligible = failed_deliveries.count()
    scheduled_count = 0

    for delivery_log in failed_deliveries:
        try:
            # DRY: DispatchService.schedule_retry() owns the backoff + save logic
            if dispatch_service.schedule_retry(delivery_log):
                scheduled_count += 1
        except Exception as e:
            logger.error("Failed to schedule retry for %s: %s", delivery_log.id, e)

    return {
        "total_eligible": total_eligible,
        "scheduled_count": scheduled_count,
    }


@shared_task
def cleanup_exhausted_retries():
    """
    Mark failed deliveries that have exceeded max attempts as EXHAUSTED.

    DRY FIX: Replaced inline `delivery_log.status = EXHAUSTED; save()` with
    the model's own mark_as_exhausted() method, which is the single canonical
    place for that state transition. Also fixed models.F() → F() and print() → logger.

    Returns:
        dict: Summary of cleanup operations.
    """
    from django.db.models import F  # DRY FIX: was models.F() → NameError
    logger.info("[Task] cleanup_exhausted_retries started")

    exhausted_deliveries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        attempt_number__gte=F("max_attempts"),
    )

    total_eligible = exhausted_deliveries.count()
    exhausted_count = 0

    for delivery_log in exhausted_deliveries:
        try:
            # DRY: model method owns the status transition + completed_at + save
            delivery_log.mark_as_exhausted()
            exhausted_count += 1
        except Exception as e:
            logger.error("Failed to mark %s as exhausted: %s", delivery_log.id, e)

    return {
        "total_eligible": total_eligible,
        "exhausted_count": exhausted_count,
    }