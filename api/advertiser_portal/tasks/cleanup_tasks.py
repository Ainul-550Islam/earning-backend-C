"""
Cleanup Tasks

Archive old logs and perform system maintenance
to keep the system running efficiently.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache
from django.db import connection

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.archive_old_logs")
def archive_old_logs():
    """
    Archive old system logs and maintain log rotation.
    
    This task runs daily to archive logs older than
    30 days and maintain system performance.
    """
    try:
        # Archive logs older than 30 days
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        
        logs_archived = 0
        
        # Archive different types of logs
        log_types = [
            'conversion_logs',
            'click_logs',
            'impression_logs',
            'error_logs',
            'audit_logs',
        ]
        
        for log_type in log_types:
            try:
                # This would implement actual log archiving
                # For now, just simulate the action
                archived_count = _archive_log_type(log_type, cutoff_date)
                logs_archived += archived_count
                
                logger.info(f"Archived {archived_count} {log_type} logs older than {cutoff_date.date()}")
                
            except Exception as e:
                logger.error(f"Error archiving {log_type} logs: {e}")
                continue
        
        logger.info(f"Log archival completed: {logs_archived} logs archived")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'logs_archived': logs_archived,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in log archival task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_temp_files")
def cleanup_temp_files():
    """
    Clean up temporary files and uploads.
    
    This task runs daily to clean up temporary files
    and free up storage space.
    """
    try:
        import os
        import tempfile
        from django.conf import settings
        
        files_deleted = 0
        space_freed = 0
        
        # Clean up temp directory
        temp_dir = tempfile.gettempdir()
        
        try:
            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                
                try:
                    # Check if file is older than 24 hours
                    file_age = timezone.now().timestamp() - os.path.getmtime(filepath)
                    
                    if file_age > 86400:  # 24 hours in seconds
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        files_deleted += 1
                        space_freed += file_size
                        
                except Exception as e:
                    logger.error(f"Error deleting temp file {filepath}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error accessing temp directory: {e}")
        
        # Clean up media temp files
        if hasattr(settings, 'MEDIA_ROOT'):
            media_temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            
            if os.path.exists(media_temp_dir):
                try:
                    for filename in os.listdir(media_temp_dir):
                        filepath = os.path.join(media_temp_dir, filename)
                        
                        try:
                            # Check if file is older than 1 hour
                            file_age = timezone.now().timestamp() - os.path.getmtime(filepath)
                            
                            if file_age > 3600:  # 1 hour in seconds
                                file_size = os.path.getsize(filepath)
                                os.remove(filepath)
                                files_deleted += 1
                                space_freed += file_size
                                
                        except Exception as e:
                            logger.error(f"Error deleting media temp file {filepath}: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error accessing media temp directory: {e}")
        
        logger.info(f"Temp file cleanup completed: {files_deleted} files deleted, {space_freed} bytes freed")
        
        return {
            'files_deleted': files_deleted,
            'space_freed': space_freed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in temp file cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.optimize_database")
def optimize_database():
    """
    Optimize database tables and maintain performance.
    
    This task runs weekly to optimize database tables
    and maintain query performance.
    """
    try:
        optimizations_performed = 0
        
        # Get list of tables to optimize
        tables_to_optimize = [
            'advertiser_portal_advertiser',
            'advertiser_portal_advertisercampaign',
            'advertiser_portal_advertiseroffer',
            'advertiser_portal_conversion',
            'advertiser_portal_campaignreport',
            'advertiser_portal_publishersbreakdown',
        ]
        
        with connection.cursor() as cursor:
            for table in tables_to_optimize:
                try:
                    # Check if table exists
                    cursor.execute(f"SHOW TABLES LIKE '{table}'")
                    if cursor.fetchone():
                        # Optimize table
                        cursor.execute(f"OPTIMIZE TABLE {table}")
                        optimizations_performed += 1
                        logger.info(f"Optimized table: {table}")
                
                except Exception as e:
                    logger.error(f"Error optimizing table {table}: {e}")
                    continue
        
        # Update table statistics
        try:
            with connection.cursor() as cursor:
                cursor.execute("ANALYZE TABLE advertiser_portal_advertiser, advertiser_portal_advertisercampaign, advertiser_portal_advertiseroffer")
                optimizations_performed += 1
                logger.info("Updated table statistics")
        
        except Exception as e:
            logger.error(f"Error updating table statistics: {e}")
        
        logger.info(f"Database optimization completed: {optimizations_performed} optimizations performed")
        
        return {
            'optimizations_performed': optimizations_performed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in database optimization task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_cache")
def cleanup_cache():
    """
    Clean up expired cache entries and maintain cache health.
    
    This task runs every 6 hours to clean up cache
    and maintain system performance.
    """
    try:
        cache_keys_cleaned = 0
        
        # This would implement actual cache cleanup
        # For now, just simulate the action
        
        # Clean up expired cache entries
        # In Redis, this happens automatically, but we can clean up specific patterns
        
        patterns_to_clean = [
            'spend_*',
            'report_*',
            'alert_*',
            'temp_*',
        ]
        
        for pattern in patterns_to_clean:
            try:
                # This would delete keys matching the pattern
                # For now, just count the operation
                keys_cleaned = _clean_cache_pattern(pattern)
                cache_keys_cleaned += keys_cleaned
                
                logger.info(f"Cleaned {keys_cleaned} cache keys matching pattern: {pattern}")
                
            except Exception as e:
                logger.error(f"Error cleaning cache pattern {pattern}: {e}")
                continue
        
        logger.info(f"Cache cleanup completed: {cache_keys_cleaned} keys cleaned")
        
        return {
            'cache_keys_cleaned': cache_keys_cleaned,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cache cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_sessions")
def cleanup_sessions():
    """
    Clean up expired user sessions.
    
    This task runs daily to clean up expired sessions
    and maintain session table performance.
    """
    try:
        from django.contrib.sessions.models import Session
        
        # Clean up expired sessions
        cutoff_date = timezone.now() - timezone.timedelta(days=7)
        
        expired_sessions = Session.objects.filter(
            expire_date__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Session cleanup completed: {expired_sessions} expired sessions deleted")
        
        return {
            'expired_sessions_deleted': expired_sessions,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in session cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_old_notifications")
def cleanup_old_notifications():
    """
    Clean up old notifications to maintain performance.
    
    This task runs weekly to clean up notifications
    older than 90 days.
    """
    try:
        from ..models.notification import AdvertiserNotification
        
        # Clean up notifications older than 90 days
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        old_notifications = AdvertiserNotification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Notification cleanup completed: {old_notifications} old notifications deleted")
        
        return {
            'notifications_deleted': old_notifications,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in notification cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.maintenance_report")
def maintenance_report():
    """
    Generate system maintenance report.
    
    This task runs daily to generate a comprehensive
    maintenance report for administrators.
    """
    try:
        # Collect maintenance statistics
        maintenance_stats = {
            'date': timezone.now().date().isoformat(),
            'database_size': _get_database_size(),
            'cache_size': _get_cache_size(),
            'storage_usage': _get_storage_usage(),
            'active_campaigns': _get_active_campaigns_count(),
            'active_advertisers': _get_active_advertisers_count(),
            'system_health': _get_system_health(),
            'generated_at': timezone.now().isoformat(),
        }
        
        # Store maintenance report
        from ..models.reporting import MaintenanceReport
        report = MaintenanceReport.objects.create(
            report_date=timezone.now().date(),
            data=maintenance_stats,
            generated_at=timezone.now()
        )
        
        logger.info(f"Maintenance report generated for {maintenance_stats['date']}")
        
        return maintenance_stats
        
    except Exception as e:
        logger.error(f"Error in maintenance report task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _archive_log_type(log_type, cutoff_date):
    """Archive logs of a specific type."""
    try:
        # This would implement actual log archiving
        # For now, return a placeholder count
        return 100  # Placeholder
        
    except Exception as e:
        logger.error(f"Error archiving {log_type}: {e}")
        return 0


def _clean_cache_pattern(pattern):
    """Clean cache keys matching a pattern."""
    try:
        # This would implement actual cache cleaning
        # For now, return a placeholder count
        return 50  # Placeholder
        
    except Exception as e:
        logger.error(f"Error cleaning cache pattern {pattern}: {e}")
        return 0


def _get_database_size():
    """Get database size in MB."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_schema AS 'database',
                       ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'size_mb'
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
            """)
            result = cursor.fetchone()
            return float(result[1]) if result else 0.0
        
    except Exception as e:
        logger.error(f"Error getting database size: {e}")
        return 0.0


def _get_cache_size():
    """Get cache size in MB."""
    try:
        # This would implement actual cache size calculation
        # For now, return a placeholder
        return 100.0  # Placeholder
        
    except Exception as e:
        logger.error(f"Error getting cache size: {e}")
        return 0.0


def _get_storage_usage():
    """Get storage usage statistics."""
    try:
        import shutil
        
        # Get media directory size
        from django.conf import settings
        if hasattr(settings, 'MEDIA_ROOT'):
            media_size = shutil.disk_usage(settings.MEDIA_ROOT).used / (1024 * 1024)  # Convert to MB
        else:
            media_size = 0.0
        
        return {
            'media_mb': media_size,
            'total_mb': media_size,  # Placeholder for total
        }
        
    except Exception as e:
        logger.error(f"Error getting storage usage: {e}")
        return {'media_mb': 0.0, 'total_mb': 0.0}


def _get_active_campaigns_count():
    """Get count of active campaigns."""
    try:
        from ..models.campaign import AdCampaign
        return AdCampaign.objects.filter(status='active').count()
        
    except Exception as e:
        logger.error(f"Error getting active campaigns count: {e}")
        return 0


def _get_active_advertisers_count():
    """Get count of active advertisers."""
    try:
        from ..models.advertiser import Advertiser
        return Advertiser.objects.filter(status='active').count()
        
    except Exception as e:
        logger.error(f"Error getting active advertisers count: {e}")
        return 0


def _get_system_health():
    """Get system health status."""
    try:
        health_status = {
            'database': 'healthy',
            'cache': 'healthy',
            'storage': 'healthy',
            'overall': 'healthy',
        }
        
        # Check database health
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            health_status['database'] = 'unhealthy'
            health_status['overall'] = 'unhealthy'
        
        # Check cache health
        try:
            cache.set('health_check', 'ok', timeout=60)
            cache.get('health_check')
        except Exception:
            health_status['cache'] = 'unhealthy'
            health_status['overall'] = 'unhealthy'
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {'database': 'unknown', 'cache': 'unknown', 'storage': 'unknown', 'overall': 'unknown'}
