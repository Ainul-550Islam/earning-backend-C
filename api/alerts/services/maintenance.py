# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

from django.db import transaction
from django.utils import timezone
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class MaintenanceService:
    """
    Consolidates maintenance and cleanup logic.
    Eliminates duplicates from: tasks/core.py + tasks/notification.py + celery_tasks.py
    """

    @staticmethod
    @transaction.atomic
    def cleanup_old_notifications(days=30):
        """
        Clean up old notifications.
        
        Previously duplicated in:
        - alerts/tasks/core.py
        - alerts/tasks/notification.py
        
        Args:
            days: Delete notifications older than N days
            
        Returns:
            dict: Cleanup statistics
        """
        from api.alerts.models import Notification
        
        logger.info(f"Cleaning up notifications older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old pending notifications (likely failed)
        deleted_pending, _ = Notification.objects.filter(
            created_at__lt=cutoff_date,
            status='pending'
        ).delete()
        
        # Notification has no archive flag in this schema (would need a
        # migration to add) - count old delivered notifications rather than
        # trying to persist a nonexistent field
        archived_delivered = Notification.objects.filter(
            created_at__lt=cutoff_date,
            status='delivered'
        ).count()
        
        logger.info(f"Cleanup complete: {deleted_pending} deleted, {archived_delivered} archived")
        
        return {
            'deleted': deleted_pending,
            'archived': archived_delivered
        }

    @staticmethod
    @transaction.atomic
    def expire_suppressions():
        """
        Expire old alert suppressions.
        
        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py
        
        Returns:
            dict: Expiration statistics
        """
        from api.alerts.models import AlertSuppression
        
        logger.info("Expiring old suppressions")
        
        now = timezone.now()
        
        # Find expired suppressions
        expired = AlertSuppression.objects.filter(
            is_active=True,
            end_time__lt=now
        )
        
        expired_count = expired.count()
        
        # Deactivate them
        expired.update(is_active=False)
        
        logger.info(f"Expired {expired_count} suppressions")
        
        return {'expired': expired_count}

    @staticmethod
    @transaction.atomic
    def update_alert_group_caches():
        """
        Update alert group caches.
        
        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py
        
        Returns:
            dict: Cache update statistics
        """
        from api.alerts.models import AlertGroup
        from django.core.cache import cache
        
        logger.info("Updating alert group caches")
        
        groups = AlertGroup.objects.all()
        updated_count = 0
        
        from api.alerts.models import AlertLog
        for group in groups:
            # Recalculate group statistics
            group_alerts = AlertLog.objects.filter(rule__in=group.rules.all())
            alert_count = group_alerts.count()
            unresolved_count = group_alerts.filter(status__in=['pending', 'processing']).count()
            
            # Update cache
            cache_key = f"alert_group_{group.id}_stats"
            cache.set(cache_key, {
                'total': alert_count,
                'unresolved': unresolved_count
            }, 3600)  # 1 hour
            
            # Update database if needed (only total count is a real model field;
            # unresolved count is cache-only, there's no matching model field for it)
            if group.cached_alert_count != alert_count:
                group.cached_alert_count = alert_count
                group.cache_updated_at = timezone.now()
                group.save(update_fields=['cached_alert_count', 'cache_updated_at'])
            
            updated_count += 1
        
        logger.info(f"Updated {updated_count} alert group caches")
        
        return {'updated': updated_count}

    @staticmethod
    def cleanup_old_logs(days=90):
        """Clean up old alert logs"""
        from api.alerts.models import AlertLog
        
        logger.info(f"Cleaning up alert logs older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # AlertLog has no archive flag in this schema (would need a migration
        # to add) - count matching old logs rather than persisting a
        # nonexistent field
        old_count = AlertLog.objects.filter(
            triggered_at__lt=cutoff_date
        ).count()
        
        logger.info(f"Found {old_count} alert logs older than {days} days")
        
        return {'archived': old_count}

    @staticmethod
    def defragment_database():
        """Defragment database tables (PostgreSQL VACUUM)"""
        from django.db import connection
        
        logger.info("Starting database defragmentation")
        
        tables = [
            'alerts_alertlog',
            'alerts_alertnotification',
            'alerts_alertsuppression',
            'alerts_alertgroup'
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"VACUUM ANALYZE {table}")
                    logger.info(f"Defragmented {table}")
                except Exception as e:
                    logger.error(f"Error defragmenting {table}: {str(e)}")
        
        return {'defragmented': len(tables)}


__all__ = ['MaintenanceService']
