"""Replay Tasks

This module contains background tasks for webhook replay operations.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import WebhookReplay, WebhookReplayBatch, WebhookDeliveryLog
from ..services.replay import ReplayService
from ..constants import ReplayStatus


@shared_task(bind=True, max_retries=3)
def process_replay(self, replay_id):
    """
    Process a webhook replay.
    
    Args:
        replay_id: The ID of the replay to process
        
    Returns:
        dict: Result of the replay processing
    """
    try:
        # Get the replay
        replay = WebhookReplay.objects.get(id=replay_id)
        
        # Check if replay is eligible for processing
        if replay.status not in [ReplayStatus.PENDING, ReplayStatus.FAILED]:
            return {
                'success': False,
                'reason': 'Replay is not eligible for processing',
                'replay_id': str(replay_id),
                'status': replay.status
            }
        
        # Process the replay
        replay_service = ReplayService()
        result = replay_service.process_replay(replay)
        
        return {
            'success': result['success'],
            'replay_id': str(replay_id),
            'new_log_id': str(result.get('new_log_id')) if result.get('new_log_id') else None,
            'processing_time': result.get('processing_time', 0)
        }
        
    except WebhookReplay.DoesNotExist:
        return {
            'success': False,
            'reason': 'Replay not found',
            'replay_id': str(replay_id)
        }
    except Exception as e:
        # Retry the task if there's an unexpected error
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_replay_batch(self, batch_id):
    """
    Process a webhook replay batch.
    
    Args:
        batch_id: The ID of the replay batch to process
        
    Returns:
        dict: Result of the batch processing
    """
    try:
        # Get the replay batch
        batch = WebhookReplayBatch.objects.get(id=batch_id)
        
        # Check if batch is eligible for processing
        if batch.status not in [ReplayStatus.PENDING, ReplayStatus.FAILED]:
            return {
                'success': False,
                'reason': 'Batch is not eligible for processing',
                'batch_id': str(batch_id),
                'status': batch.status
            }
        
        # Process the batch
        replay_service = ReplayService()
        result = replay_service.process_replay_batch(batch)
        
        return {
            'success': result['success'],
            'batch_id': str(batch_id),
            'processed_count': result.get('processed_count', 0),
            'success_count': result.get('success_count', 0),
            'failed_count': result.get('failed_count', 0),
            'processing_time': result.get('processing_time', 0)
        }
        
    except WebhookReplayBatch.DoesNotExist:
        return {
            'success': False,
            'reason': 'Replay batch not found',
            'batch_id': str(batch_id)
        }
    except Exception as e:
        # Retry the task if there's an unexpected error
        raise self.retry(exc=e, countdown=60)


@shared_task
def create_replay_batch(delivery_log_ids, replayed_by_id, reason="Batch replay"):
    """
    Create a replay batch from multiple delivery logs.
    
    Args:
        delivery_log_ids: List of delivery log IDs to replay
        replayed_by_id: ID of the user creating the replay
        reason: Reason for the replay batch
        
    Returns:
        dict: Result of batch creation
    """
    try:
        # Get the delivery logs
        delivery_logs = WebhookDeliveryLog.objects.filter(id__in=delivery_log_ids)
        
        # Create replay batch
        replay_service = ReplayService()
        batch = replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by_id=replayed_by_id,
            reason=reason
        )
        
        return {
            'success': True,
            'batch_id': str(batch.id),
            'batch_id_display': batch.batch_id,
            'item_count': batch.count,
            'creation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'delivery_log_ids': delivery_log_ids
        }


@shared_task
def cleanup_old_replays(days=30):
    """
    Clean up old replay records.
    
    Args:
        days: Number of days to keep replay records (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old replays
        old_replays = WebhookReplay.objects.filter(
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for replay in old_replays:
            try:
                replay.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete replay {replay.id}: {e}")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'days': days
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }


@shared_task
def cleanup_old_replay_batches(days=30):
    """
    Clean up old replay batch records.
    
    Args:
        days: Number of days to keep replay batch records (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old replay batches
        old_batches = WebhookReplayBatch.objects.filter(
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for batch in old_batches:
            try:
                batch.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete replay batch {batch.id}: {e}")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'days': days
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }


@shared_task
def process_pending_replays():
    """
    Process all pending replays.
    This task is typically run on a schedule (e.g., every minute).
    
    Returns:
        dict: Summary of processing operations
    """
    try:
        # Get pending replays
        pending_replays = WebhookReplay.objects.filter(status=ReplayStatus.PENDING)
        
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        for replay in pending_replays:
            try:
                # Queue individual replay task
                process_replay.delay(str(replay.id))
                processed_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to queue replay {replay.id}: {e}")
        
        return {
            'success': True,
            'pending_replays_found': pending_replays.count(),
            'replays_queued': processed_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'processing_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def process_pending_replay_batches():
    """
    Process all pending replay batches.
    This task is typically run on a schedule (e.g., every 5 minutes).
    
    Returns:
        dict: Summary of processing operations
    """
    try:
        # Get pending replay batches
        pending_batches = WebhookReplayBatch.objects.filter(status=ReplayStatus.PENDING)
        
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        for batch in pending_batches:
            try:
                # Queue individual batch task
                process_replay_batch.delay(str(batch.id))
                processed_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to queue replay batch {batch.id}: {e}")
        
        return {
            'success': True,
            'pending_batches_found': pending_batches.count(),
            'batches_queued': processed_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'processing_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def get_replay_statistics():
    """
    Get statistics about replay operations.
    
    Returns:
        dict: Replay statistics
    """
    try:
        from django.db.models import Count
        
        # Get overall statistics
        total_replays = WebhookReplay.objects.count()
        total_batches = WebhookReplayBatch.objects.count()
        
        # Get status breakdown
        replay_status_counts = WebhookReplay.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        batch_status_counts = WebhookReplayBatch.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Get recent statistics
        last_24h = timezone.now() - timedelta(hours=24)
        recent_replays = WebhookReplay.objects.filter(created_at__gte=last_24h).count()
        recent_batches = WebhookReplayBatch.objects.filter(created_at__gte=last_24h).count()
        
        # Get success rates
        successful_replays = WebhookReplay.objects.filter(status=ReplayStatus.COMPLETED).count()
        successful_batches = WebhookReplayBatch.objects.filter(status=ReplayStatus.COMPLETED).count()
        
        replay_success_rate = (successful_replays / total_replays * 100) if total_replays > 0 else 0
        batch_success_rate = (successful_batches / total_batches * 100) if total_batches > 0 else 0
        
        return {
            'success': True,
            'total_replays': total_replays,
            'total_batches': total_batches,
            'recent_replays_24h': recent_replays,
            'recent_batches_24h': recent_batches,
            'replay_success_rate': round(replay_success_rate, 2),
            'batch_success_rate': round(batch_success_rate, 2),
            'replay_status_counts': list(replay_status_counts),
            'batch_status_counts': list(batch_status_counts),
            'statistics_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def create_failed_delivery_replays(hours=24, reason="Auto-replay of failed deliveries"):
    """
    Create replays for failed deliveries within a time window.
    
    Args:
        hours: Time window in hours (default: 24)
        reason: Reason for the replays
        
    Returns:
        dict: Summary of replay creation
    """
    try:
        # Calculate time window
        since = timezone.now() - timedelta(hours=hours)
        
        # Get failed deliveries
        failed_deliveries = WebhookDeliveryLog.objects.filter(
            status='failed',
            created_at__gte=since
        )
        
        # Create replays for each failed delivery
        replay_service = ReplayService()
        created_count = 0
        
        for delivery in failed_deliveries:
            try:
                # Check if replay already exists
                if not WebhookReplay.objects.filter(original_log=delivery).exists():
                    replay = replay_service.create_replay(
                        original_log=delivery,
                        replayed_by=None,  # System replay
                        reason=reason
                    )
                    created_count += 1
                    
            except Exception as e:
                print(f"Failed to create replay for delivery {delivery.id}: {e}")
        
        return {
            'success': True,
            'failed_deliveries_found': failed_deliveries.count(),
            'replays_created': created_count,
            'hours': hours,
            'creation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'hours': hours
        }
