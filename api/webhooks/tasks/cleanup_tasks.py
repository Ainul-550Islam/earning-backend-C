"""Cleanup Tasks

This module contains background tasks for cleaning up old webhook data.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import (
    WebhookDeliveryLog, WebhookHealthLog, WebhookAnalytics,
    WebhookEventStat, WebhookRateLimit, WebhookReplay, WebhookReplayBatch
)


@shared_task
def cleanup_old_delivery_logs(days=90):
    """
    Clean up old webhook delivery logs.
    
    Args:
        days: Number of days to keep delivery logs (default: 90)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old delivery logs
        old_logs = WebhookDeliveryLog.objects.filter(
            created_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in old_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete delivery log {log.id}: {e}")
        
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
def cleanup_old_health_logs(days=30):
    """
    Clean up old webhook health logs.
    
    Args:
        days: Number of days to keep health logs (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old health logs
        old_logs = WebhookHealthLog.objects.filter(
            checked_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in old_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete health log {log.id}: {e}")
        
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
def cleanup_old_analytics(days=365):
    """
    Clean up old webhook analytics records.
    
    Args:
        days: Number of days to keep analytics records (default: 365)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old analytics records
        old_analytics = WebhookAnalytics.objects.filter(
            date__lt=cutoff_date.date()
        )
        
        deleted_count = 0
        
        for analytics in old_analytics:
            try:
                analytics.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete analytics record {analytics.id}: {e}")
        
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
def cleanup_all_old_data(days=90):
    """
    Clean up all old webhook data.
    
    Args:
        days: Number of days to keep data (default: 90)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up delivery logs
        delivery_logs_deleted = WebhookDeliveryLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        # Clean up health logs
        health_logs_deleted = WebhookHealthLog.objects.filter(
            checked_at__lt=cutoff_date
        ).delete()[0]
        
        # Clean up analytics (keep for longer period)
        analytics_cutoff = timezone.now() - timedelta(days=365)
        analytics_deleted = WebhookAnalytics.objects.filter(
            date__lt=analytics_cutoff.date()
        ).delete()[0]
        
        # Clean up event stats
        event_stats_deleted = WebhookEventStat.objects.filter(
            date__lt=cutoff_date.date()
        ).delete()[0]
        
        # Clean up replays
        replays_deleted = WebhookReplay.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        # Clean up replay batches
        replay_batches_deleted = WebhookReplayBatch.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        return {
            'success': True,
            'delivery_logs_deleted': delivery_logs_deleted,
            'health_logs_deleted': health_logs_deleted,
            'analytics_deleted': analytics_deleted,
            'event_stats_deleted': event_stats_deleted,
            'replays_deleted': replays_deleted,
            'replay_batches_deleted': replay_batches_deleted,
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
def archive_old_data(days=180):
    """
    Archive old webhook data instead of deleting it.
    
    Args:
        days: Number of days after which to archive data (default: 180)
        
    Returns:
        dict: Summary of archive operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Archive delivery logs
        delivery_logs_archived = 0
        delivery_logs = WebhookDeliveryLog.objects.filter(
            created_at__lt=cutoff_date
        )
        
        for log in delivery_logs:
            try:
                # Mark as archived (this assumes there's an archived field)
                log.archived = True
                log.archived_at = timezone.now()
                log.save()
                delivery_logs_archived += 1
            except Exception as e:
                print(f"Failed to archive delivery log {log.id}: {e}")
        
        # Archive health logs
        health_logs_archived = 0
        health_logs = WebhookHealthLog.objects.filter(
            checked_at__lt=cutoff_date
        )
        
        for log in health_logs:
            try:
                log.archived = True
                log.archived_at = timezone.now()
                log.save()
                health_logs_archived += 1
            except Exception as e:
                print(f"Failed to archive health log {log.id}: {e}")
        
        return {
            'success': True,
            'delivery_logs_archived': delivery_logs_archived,
            'health_logs_archived': health_logs_archived,
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
def cleanup_data_by_model(model_name, days=90):
    """
    Clean up old data for a specific model.
    
    Args:
        model_name: Name of the model to clean up
        days: Number of days to keep data (default: 90)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = 0
        
        if model_name == 'WebhookDeliveryLog':
            deleted_count = WebhookDeliveryLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
        elif model_name == 'WebhookHealthLog':
            deleted_count = WebhookHealthLog.objects.filter(
                checked_at__lt=cutoff_date
            ).delete()[0]
        elif model_name == 'WebhookAnalytics':
            deleted_count = WebhookAnalytics.objects.filter(
                date__lt=cutoff_date.date()
            ).delete()[0]
        elif model_name == 'WebhookEventStat':
            deleted_count = WebhookEventStat.objects.filter(
                date__lt=cutoff_date.date()
            ).delete()[0]
        elif model_name == 'WebhookReplay':
            deleted_count = WebhookReplay.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
        elif model_name == 'WebhookReplayBatch':
            deleted_count = WebhookReplayBatch.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
        else:
            return {
                'success': False,
                'error': f'Unknown model: {model_name}',
                'model_name': model_name
            }
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'model_name': model_name,
            'cutoff_date': cutoff_date.isoformat(),
            'days': days
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'model_name': model_name,
            'days': days
        }


@shared_task
def get_cleanup_statistics():
    """
    Get statistics about data that could be cleaned up.
    
    Returns:
        dict: Cleanup statistics
    """
    try:
        from django.db.models import Count
        
        # Get counts by age
        now = timezone.now()
        
        # Delivery logs
        delivery_stats = {
            'total': WebhookDeliveryLog.objects.count(),
            'last_24h': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=1)).count(),
            'last_7d': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
            'last_30d': WebhookDeliveryLog.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
            'older_30d': WebhookDeliveryLog.objects.filter(created_at__lt=now - timedelta(days=30)).count(),
            'older_90d': WebhookDeliveryLog.objects.filter(created_at__lt=now - timedelta(days=90)).count(),
            'older_180d': WebhookDeliveryLog.objects.filter(created_at__lt=now - timedelta(days=180)).count(),
        }
        
        # Health logs
        health_stats = {
            'total': WebhookHealthLog.objects.count(),
            'last_24h': WebhookHealthLog.objects.filter(checked_at__gte=now - timedelta(days=1)).count(),
            'last_7d': WebhookHealthLog.objects.filter(checked_at__gte=now - timedelta(days=7)).count(),
            'last_30d': WebhookHealthLog.objects.filter(checked_at__gte=now - timedelta(days=30)).count(),
            'older_30d': WebhookHealthLog.objects.filter(checked_at__lt=now - timedelta(days=30)).count(),
            'older_90d': WebhookHealthLog.objects.filter(checked_at__lt=now - timedelta(days=90)).count(),
        }
        
        # Analytics
        analytics_stats = {
            'total': WebhookAnalytics.objects.count(),
            'last_30d': WebhookAnalytics.objects.filter(date__gte=now.date() - timedelta(days=30)).count(),
            'last_90d': WebhookAnalytics.objects.filter(date__gte=now.date() - timedelta(days=90)).count(),
            'older_90d': WebhookAnalytics.objects.filter(date__lt=now.date() - timedelta(days=90)).count(),
            'older_365d': WebhookAnalytics.objects.filter(date__lt=now.date() - timedelta(days=365)).count(),
        }
        
        # Replays
        replay_stats = {
            'total': WebhookReplay.objects.count(),
            'last_24h': WebhookReplay.objects.filter(created_at__gte=now - timedelta(days=1)).count(),
            'last_7d': WebhookReplay.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
            'last_30d': WebhookReplay.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
            'older_30d': WebhookReplay.objects.filter(created_at__lt=now - timedelta(days=30)).count(),
            'older_90d': WebhookReplay.objects.filter(created_at__lt=now - timedelta(days=90)).count(),
        }
        
        return {
            'success': True,
            'delivery_stats': delivery_stats,
            'health_stats': health_stats,
            'analytics_stats': analytics_stats,
            'replay_stats': replay_stats,
            'statistics_timestamp': now.isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def optimize_database_tables():
    """
    Optimize webhook-related database tables.
    
    Returns:
        dict: Summary of optimization operations
    """
    try:
        from django.db import connection
        
        optimized_tables = []
        
        # List of webhook-related tables to optimize
        webhook_tables = [
            'webhooks_webhookdeliverylog',
            'webhooks_webhookhealthlog',
            'webhooks_webhookanalytics',
            'webhooks_webhookeventstat',
            'webhooks_webhookreplay',
            'webhooks_webhookreplaybatch',
            'webhooks_webhookreplayitem',
        ]
        
        with connection.cursor() as cursor:
            for table in webhook_tables:
                try:
                    # Check if table exists
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = DATABASE() AND table_name = '{table}'
                    """)
                    
                    if cursor.fetchone()[0] > 0:
                        # Optimize table
                        cursor.execute(f"OPTIMIZE TABLE {table}")
                        optimized_tables.append(table)
                        
                except Exception as e:
                    print(f"Failed to optimize table {table}: {e}")
        
        return {
            'success': True,
            'optimized_tables': optimized_tables,
            'optimization_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def vacuum_database_tables():
    """
    Vacuum webhook-related database tables (PostgreSQL only).
    
    Returns:
        dict: Summary of vacuum operations
    """
    try:
        from django.db import connection
        
        vacuumed_tables = []
        
        # List of webhook-related tables to vacuum
        webhook_tables = [
            'webhooks_webhookdeliverylog',
            'webhooks_webhookhealthlog',
            'webhooks_webhookanalytics',
            'webhooks_webhookeventstat',
            'webhooks_webhookreplay',
            'webhooks_webhookreplaybatch',
            'webhooks_webhookreplayitem',
        ]
        
        with connection.cursor() as cursor:
            for table in webhook_tables:
                try:
                    # Check if table exists
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = '{table}'
                    """)
                    
                    if cursor.fetchone()[0] > 0:
                        # Vacuum table
                        cursor.execute(f"VACUUM ANALYZE {table}")
                        vacuumed_tables.append(table)
                        
                except Exception as e:
                    print(f"Failed to vacuum table {table}: {e}")
        
        return {
            'success': True,
            'vacuumed_tables': vacuumed_tables,
            'vacuum_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
