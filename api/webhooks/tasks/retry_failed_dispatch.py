"""Retry Failed Dispatch Task

This module contains the background task for retrying failed webhook deliveries.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from ..models import WebhookDeliveryLog
from ..services.core import DispatchService
from ..constants import DeliveryStatus


@shared_task(bind=True, max_retries=3)
def retry_failed_dispatch(self, delivery_log_id):
    """
    Retry a failed webhook delivery.
    
    Args:
        delivery_log_id: The ID of the delivery log to retry
        
    Returns:
        dict: Result of the retry operation
    """
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
    Retry all failed webhook deliveries that are ready for retry.
    
    Returns:
        dict: Summary of retry operations
    """
    # Get all failed deliveries that are ready for retry
    ready_retries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        attempt_number__lt=models.F('max_attempts')
    ).filter(
        Q(next_retry_at__lte=timezone.now()) | Q(next_retry_at__isnull=True)
    )
    
    retry_count = 0
    success_count = 0
    failed_count = 0
    
    for delivery_log in ready_retries:
        try:
            # Queue individual retry task
            retry_failed_dispatch.delay(str(delivery_log.id))
            retry_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to queue retry for {delivery_log.id}: {e}")
    
    return {
        'total_queued': retry_count,
        'success_count': success_count,
        'failed_count': failed_count
    }


@shared_task
def schedule_failed_retries():
    """
    Schedule retry tasks for failed deliveries.
    This task is typically run on a schedule (e.g., every minute).
    
    Returns:
        dict: Summary of scheduled retries
    """
    # Get failed deliveries that need retry scheduling
    failed_deliveries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        next_retry_at__isnull=True,
        attempt_number__lt=models.F('max_attempts')
    )
    
    scheduled_count = 0
    
    for delivery_log in failed_deliveries:
        try:
            # Calculate next retry time
            retry_delay = timedelta(minutes=2 ** delivery_log.attempt_number)  # Exponential backoff
            next_retry = timezone.now() + retry_delay
            
            # Update the delivery log
            delivery_log.next_retry_at = next_retry
            delivery_log.save()
            
            scheduled_count += 1
            
        except Exception as e:
            print(f"Failed to schedule retry for {delivery_log.id}: {e}")
    
    return {
        'scheduled_count': scheduled_count
    }


@shared_task
def cleanup_exhausted_retries():
    """
    Clean up exhausted retry attempts.
    Mark deliveries as exhausted if they've exceeded max attempts.
    
    Returns:
        dict: Summary of cleanup operations
    """
    # Get failed deliveries that have exceeded max attempts
    exhausted_deliveries = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.FAILED,
        attempt_number__gte=models.F('max_attempts')
    )
    
    exhausted_count = 0
    
    for delivery_log in exhausted_deliveries:
        try:
            # Mark as exhausted
            delivery_log.status = DeliveryStatus.EXHAUSTED
            delivery_log.save()
            exhausted_count += 1
            
        except Exception as e:
            print(f"Failed to mark {delivery_log.id} as exhausted: {e}")
    
    return {
        'exhausted_count': exhausted_count
    }
