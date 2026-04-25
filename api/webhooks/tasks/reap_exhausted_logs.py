"""Reap Exhausted Logs Task

This module contains the background task for cleaning up exhausted webhook delivery logs.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import WebhookDeliveryLog
from ..constants import DeliveryStatus


@shared_task
def reap_exhausted_logs(days=7):
    """
    Clean up exhausted webhook delivery logs older than specified days.
    
    Args:
        days: Number of days to keep exhausted logs (default: 7)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get exhausted logs older than cutoff date
        exhausted_logs = WebhookDeliveryLog.objects.filter(
            status=DeliveryStatus.EXHAUSTED,
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in exhausted_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete exhausted log {log.id}: {e}")
        
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
def reap_failed_logs(days=30):
    """
    Clean up failed webhook delivery logs older than specified days.
    
    Args:
        days: Number of days to keep failed logs (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get failed logs older than cutoff date (excluding exhausted)
        failed_logs = WebhookDeliveryLog.objects.filter(
            status=DeliveryStatus.FAILED,
            created_at__lt=cutoff_date
        ).exclude(status=DeliveryStatus.EXHAUSTED)
        
        deleted_count = 0
        
        for log in failed_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete failed log {log.id}: {e}")
        
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
def reap_old_logs(days=90):
    """
    Clean up all webhook delivery logs older than specified days.
    
    Args:
        days: Number of days to keep logs (default: 90)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get all logs older than cutoff date
        old_logs = WebhookDeliveryLog.objects.filter(
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in old_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete log {log.id}: {e}")
        
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
def reap_logs_by_status(status, days=30):
    """
    Clean up webhook delivery logs by status.
    
    Args:
        status: The delivery status to clean up
        days: Number of days to keep logs (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get logs by status older than cutoff date
        logs = WebhookDeliveryLog.objects.filter(
            status=status,
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete log {log.id}: {e}")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'status': status,
            'cutoff_date': cutoff_date.isoformat(),
            'days': days
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'status': status,
            'days': days
        }


@shared_task
def archive_old_logs(days=180):
    """
    Archive old webhook delivery logs instead of deleting them.
    
    Args:
        days: Number of days after which to archive logs (default: 180)
        
    Returns:
        dict: Summary of archive operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get logs older than cutoff date
        old_logs = WebhookDeliveryLog.objects.filter(
            created_at__lt=cutoff_date
        )
        
        archived_count = 0
        
        for log in old_logs:
            try:
                # Create archive record (assuming there's an archive model)
                # This would need to be implemented based on your archive strategy
                # For now, we'll just mark as archived
                log.archived = True
                log.archived_at = timezone.now()
                log.save()
                archived_count += 1
            except Exception as e:
                print(f"Failed to archive log {log.id}: {e}")
        
        return {
            'success': True,
            'archived_count': archived_count,
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
def cleanup_logs_summary():
    """
    Get a summary of logs by status and age.
    
    Returns:
        dict: Summary statistics
    """
    try:
        from django.db.models import Count
        
        # Get counts by status
        status_counts = WebhookDeliveryLog.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Get counts by age
        now = timezone.now()
        age_counts = {
            'last_24h': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=1)).count(),
            'last_7d': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
            'last_30d': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
            'older_30d': WebhookDeliveryLog.objects.filter(created_at__lt=now - timedelta(days=30)).count(),
            'older_90d': WebhookDeliveryLog.objects.filter(created_at__lt=now - timedelta(days=90)).count(),
        }
        
        # Get total count
        total_count = WebhookDeliveryLog.objects.count()
        
        return {
            'success': True,
            'total_count': total_count,
            'status_counts': list(status_counts),
            'age_counts': age_counts,
            'summary_timestamp': now.isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
