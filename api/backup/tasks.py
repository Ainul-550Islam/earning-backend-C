# tasks.py
from django.db import models 
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import json
import os
from .models import (
    Backup, BackupLog, BackupStorageLocation, 
    BackupRestoration, BackupNotificationConfig,
    RetentionPolicy, DeltaBackupTracker
)
from django.core.mail import send_mail
from django.conf import settings
import requests
import hashlib
import psutil
import logging

logger = logging.getLogger(__name__)


# 🔴 ADVANCED FEATURE TASKS

@shared_task
def perform_delta_backup(backup_id, base_backup_id=None):
    """Perform delta backup (only changed data)"""
    try:
        backup = Backup.objects.get(id=backup_id)
        base_backup = Backup.objects.get(id=base_backup_id) if base_backup_id else None
        
        # Get changed tables since last backup
        changed_tables = get_changed_tables_since_last_backup(base_backup)
        
        if not changed_tables:
            backup.status = Backup.STATUS_COMPLETED
            backup.save()
            return {"success": True, "message": "No changes detected"}
        
        # Perform delta backup
        backup.changed_tables = changed_tables
        backup.changed_row_count = len(changed_tables)
        backup.delta_base = base_backup
        backup.save()
        
        # Update delta tracker
        if base_backup:
            tracker, created = DeltaBackupTracker.objects.get_or_create(
                base_backup=base_backup
            )
            tracker.calculate_chain_stats()
        
        return {"success": True, "changed_tables": len(changed_tables)}
        
    except Exception as e:
        logger.error(f"Delta backup failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def execute_gfs_retention_policy(policy_id):
    """Execute GFS retention policy"""
    try:
        policy = RetentionPolicy.objects.get(id=policy_id)
        
        if policy.policy_type == 'gfs':
            # Categorize backups
            categorize_backups_for_gfs()
            
            # Find backups to delete
            backups_to_delete = policy.get_backups_to_cleanup()
            
            # Execute cleanup
            result = policy.execute_cleanup()
            
            # Send notification
            if result['deleted_count'] > 0:
                send_backup_notification_task.delay(
                    backup_id=None,
                    message=f"GFS cleanup completed: {result['deleted_count']} backups deleted",
                    level='info',
                    channels=['email', 'slack']
                )
            
            return result
            
    except Exception as e:
        logger.error(f"GFS retention execution failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def send_multi_channel_notification(backup_id, message, level='info', channels=None):
    """Send notification through multiple channels"""
    try:
        backup = Backup.objects.get(id=backup_id)
        configs = BackupNotificationConfig.objects.filter(is_active=True)
        
        if not channels:
            channels = backup.notification_channels or ['email']
        
        notifications_sent = []
        
        for channel in channels:
            if channel == 'email':
                send_email_notification(backup, message, level)
                notifications_sent.append('email')
            
            elif channel == 'slack':
                send_slack_notification(backup, message, level)
                notifications_sent.append('slack')
            
            elif channel == 'telegram':
                send_telegram_notification(backup, message, level)
                notifications_sent.append('telegram')
            
            elif channel == 'webhook':
                send_webhook_notification(backup, message, level)
                notifications_sent.append('webhook')
        
        backup.notification_sent = True
        backup.save()
        
        return {"success": True, "channels_used": notifications_sent}
        
    except Exception as e:
        logger.error(f"Multi-channel notification failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def auto_cleanup_expired_backups():
    """Automatic cleanup of expired backups (run via cron)"""
    try:
        from django.utils import timezone
        
        # Find expired backups
        expired_backups = Backup.objects.filter(
            expires_at__lt=timezone.now(),
            is_permanent=False,
            auto_cleanup_enabled=True
        )
        
        deleted_count = 0
        failed_count = 0
        
        for backup in expired_backups:
            try:
                # Delete from storage first
                delete_backup_from_storage(backup)
                
                # Delete record
                backup.delete()
                deleted_count += 1
                
                # Log deletion
                BackupLog.objects.create(
                    level='info',
                    message=f"Auto-cleanup: Deleted expired backup {backup.name}",
                    details={
                        'backup_id': str(backup.id),
                        'expired_at': backup.expires_at.isoformat(),
                        'auto_cleanup': True
                    }
                )
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to auto-cleanup backup {backup.id}: {str(e)}")
        
        # Send summary notification
        if deleted_count > 0:
            send_multi_channel_notification.delay(
                backup_id=None,
                message=f"Auto-cleanup completed: {deleted_count} backups deleted, {failed_count} failed",
                level='info' if failed_count == 0 else 'warning'
            )
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "total_expired": expired_backups.count()
        }
        
    except Exception as e:
        logger.error(f"Auto-cleanup task failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def verify_backup_health_periodically():
    """Periodic health check for all backups"""
    try:
        # Get backups that need health check
        check_threshold = timezone.now() - timedelta(days=7)
        backups_to_check = Backup.objects.filter(
            models.Q(last_health_check__isnull=True) |
            models.Q(last_health_check__lt=check_threshold),
            status=Backup.STATUS_COMPLETED
        )[:50]  # Limit to 50 per run
        
        healthy_count = 0
        corrupted_count = 0
        
        for backup in backups_to_check:
            try:
                # Perform health check
                is_healthy = perform_backup_health_check(backup)
                
                backup.is_healthy = is_healthy
                backup.last_health_check = timezone.now()
                backup.health_check_count += 1
                
                if is_healthy:
                    healthy_count += 1
                    backup.health_score = min(100, backup.health_score + 10)
                else:
                    corrupted_count += 1
                    backup.health_score = max(0, backup.health_score - 30)
                    
                    # Alert on corruption
                    send_multi_channel_notification.delay(
                        backup_id=backup.id,
                        message=f"BACKUP CORRUPTION DETECTED: {backup.name}",
                        level='critical'
                    )
                
                backup.save()
                
            except Exception as e:
                logger.error(f"Health check failed for backup {backup.id}: {str(e)}")
        
        # Log summary
        BackupLog.objects.create(
            level='info',
            message=f"Periodic health check completed: {healthy_count} healthy, {corrupted_count} corrupted",
            details={
                'total_checked': len(backups_to_check),
                'healthy_count': healthy_count,
                'corrupted_count': corrupted_count
            }
        )
        
        return {
            "success": True,
            "checked_count": len(backups_to_check),
            "healthy_count": healthy_count,
            "corrupted_count": corrupted_count
        }
        
    except Exception as e:
        logger.error(f"Periodic health check failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def create_redundant_storage_copies(backup_id):
    """Create redundant copies across multiple storage locations"""
    try:
        backup = Backup.objects.get(id=backup_id)
        
        # Get active storage locations
        storage_locations = BackupStorageLocation.objects.filter(
            is_active=True,
            is_connected=True
        ).order_by('priority')
        
        if len(storage_locations) < 2:
            return {"success": False, "error": "Insufficient storage locations"}
        
        # Upload to multiple locations
        successful_copies = []
        
        for location in storage_locations[:backup.redundancy_level]:
            try:
                # Upload backup to this location
                upload_result = upload_to_storage_location(backup, location)
                
                if upload_result['success']:
                    successful_copies.append({
                        'location_id': location.id,
                        'location_name': location.name,
                        'storage_type': location.storage_type
                    })
                    
                    # Update storage usage
                    location.used_capacity += backup.file_size
                    location.save()
                
            except Exception as e:
                logger.error(f"Failed to upload to {location.name}: {str(e)}")
        
        # Update backup with storage locations
        backup.storage_locations = [copy['location_id'] for copy in successful_copies]
        backup.save()
        
        # Log redundancy creation
        BackupLog.objects.create(
            backup=backup,
            level='info',
            message=f"Created {len(successful_copies)} redundant copies",
            details={'locations': successful_copies}
        )
        
        return {
            "success": True,
            "copies_created": len(successful_copies),
            "locations": successful_copies
        }
        
    except Exception as e:
        logger.error(f"Redundant storage creation failed: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def consolidate_delta_backup_chain(chain_id):
    """Consolidate delta backup chain to reduce storage"""
    try:
        tracker = DeltaBackupTracker.objects.get(chain_id=chain_id)
        
        # Get all backups in chain
        chain_backups = tracker.get_chain_backups()
        
        if chain_backups.count() < 3:
            return {"success": False, "message": "Chain too short for consolidation"}
        
        # Find the most efficient consolidation point
        consolidation_point = find_optimal_consolidation_point(chain_backups)
        
        # Perform consolidation
        consolidated_backup = perform_consolidation(
            chain_backups, 
            consolidation_point
        )
        
        # Update tracker
        tracker.needs_consolidation = False
        tracker.last_consolidation = timezone.now()
        tracker.save()
        
        return {
            "success": True,
            "consolidated_to": consolidated_backup.id,
            "original_chain_length": chain_backups.count(),
            "space_saved": calculate_space_saved(chain_backups, consolidated_backup)
        }
        
    except Exception as e:
        logger.error(f"Delta consolidation failed: {str(e)}")
        return {"success": False, "error": str(e)}


# HELPER FUNCTIONS

def get_changed_tables_since_last_backup(base_backup):
    """Detect changed tables since last backup (simplified)"""
    # This is a simplified version. In production, you'd use:
    # 1. Database triggers
    # 2. WAL (Write-Ahead Log) parsing
    # 3. Timestamp-based detection
    
    changed_tables = []
    
    # Example implementation for PostgreSQL
    # You would need to implement actual database-specific logic
    try:
        import psycopg2
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Query for changed tables since base backup
            cursor.execute("""
                SELECT schemaname, tablename, 
                       n_tup_ins, n_tup_upd, n_tup_del
                FROM pg_stat_user_tables
                WHERE (n_tup_ins + n_tup_upd + n_tup_del) > 0
                AND last_autovacuum > %s
            """, [base_backup.start_time])
            
            rows = cursor.fetchall()
            changed_tables = [row[1] for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to detect changed tables: {str(e)}")
    
    return changed_tables


def categorize_backups_for_gfs():
    """Categorize backups for GFS retention policy"""
    from datetime import datetime, timedelta
    
    today = timezone.now().date()
    
    # Get all non-categorized backups
    backups = Backup.objects.filter(
        gfs_category__isnull=True,
        retention_policy=Backup.RETENTION_GFS
    )
    
    for backup in backups:
        backup_date = backup.start_time.date()
        days_diff = (today - backup_date).days
        
        # Categorize based on age
        if days_diff < 7:
            backup.gfs_category = 'son'  # Daily
        elif days_diff < 30:
            backup.gfs_category = 'father'  # Weekly
        else:
            backup.gfs_category = 'grandfather'  # Monthly
        
        backup.save()


def send_slack_notification(backup, message, level):
    """Send notification to Slack"""
    config = BackupNotificationConfig.objects.filter(
        is_active=True,
        channels__contains=['slack']
    ).first()
    
    if not config or 'slack' not in config.channel_config:
        return
    
    webhook_url = config.channel_config.get('slack', {}).get('webhook_url')
    
    if not webhook_url:
        return
    
    # Prepare Slack message
    color = {
        'info': '#36a64f',
        'warning': '#f2c744',
        'error': '#e01e5a',
        'critical': '#dc3545'
    }.get(level, '#36a64f')
    
    payload = {
        "attachments": [{
            "color": color,
            "title": f"Backup Notification: {backup.name}",
            "text": message,
            "fields": [
                {"title": "Backup Type", "value": backup.get_backup_type_display(), "short": True},
                {"title": "Status", "value": backup.get_status_display(), "short": True},
                {"title": "Size", "value": backup.file_size_human, "short": True},
                {"title": "Database", "value": backup.database_name, "short": True}
            ],
            "footer": "Backup System",
            "ts": int(timezone.now().timestamp())
        }]
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Slack notification failed: {str(e)}")


def send_telegram_notification(backup, message, level):
    """Send notification to Telegram"""
    config = BackupNotificationConfig.objects.filter(
        is_active=True,
        channels__contains=['telegram']
    ).first()
    
    if not config or 'telegram' not in config.channel_config:
        return
    
    bot_token = config.channel_config.get('telegram', {}).get('bot_token')
    chat_id = config.channel_config.get('telegram', {}).get('chat_id')
    
    if not bot_token or not chat_id:
        return
    
    # Prepare Telegram message
    emoji = {
        'info': '[INFO]',
        'warning': '[WARN]',
        'error': '[ERROR]',
        'critical': '🚨'
    }.get(level, '[INFO]')
    
    text = f"""
{emoji} *Backup Notification*
    
*Backup:* {backup.name}
*Message:* {message}
*Type:* {backup.get_backup_type_display()}
*Status:* {backup.get_status_display()}
*Size:* {backup.file_size_human}
*Database:* {backup.database_name}
    
_Time:_ {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Telegram notification failed: {str(e)}")


def perform_backup_health_check(backup):
    """Perform comprehensive health check on backup"""
    try:
        # Check 1: File exists
        if not backup.file_path or not os.path.exists(backup.file_path):
            return False
        
        # Check 2: Hash verification
        if backup.file_hash:
            current_hash = calculate_file_hash(backup.file_path)
            if current_hash != backup.file_hash:
                return False
        
        # Check 3: Size verification
        actual_size = os.path.getsize(backup.file_path)
        if backup.file_size and abs(actual_size - backup.file_size) > 1024:  # Allow 1KB tolerance
            return False
        
        # Check 4: Test restore (partial)
        if backup.verification_method == 'test_restore':
            # Perform a test restore of metadata only
            if not test_restore_metadata(backup):
                return False
        
        # Check 5: Storage location accessibility
        for location_id in backup.storage_locations:
            try:
                location = BackupStorageLocation.objects.get(id=location_id)
                if not location.is_connected:
                    return False
            except BackupStorageLocation.DoesNotExist:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Health check error for {backup.id}: {str(e)}")
        return False


def calculate_space_saved(original_backups, consolidated_backup):
    """Calculate storage space saved by consolidation"""
    original_size = sum(b.file_size for b in original_backups)
    consolidated_size = consolidated_backup.file_size
    return original_size - consolidated_size


# ============ ADMIN.PY এর জন্য REQUIRED TASKS ============

@shared_task
def backup_database_task(backup_id, **kwargs):
    """Main backup task (called from admin)"""
    try:
        from django.utils import timezone
        backup = Backup.objects.get(id=backup_id)
        
        # Update status
        backup.status = Backup.STATUS_RUNNING
        backup.start_time = timezone.now()
        backup.save()
        
        # Log start
        BackupLog.log_backup_start(backup)
        
        # Your actual backup logic here
        # For now, create a placeholder backup
        result = {
            'status': 'completed',
            'backup_id': backup_id,
            'message': 'Backup task executed successfully'
        }
        
        # Update backup
        backup.status = Backup.STATUS_COMPLETED
        backup.end_time = timezone.now()
        backup.save()
        
        # Log completion
        BackupLog.log_backup_complete(
            backup, 
            duration=(backup.end_time - backup.start_time).total_seconds(),
            file_size=backup.file_size
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Backup task failed: {str(e)}")
        
        # Mark as failed
        try:
            backup.status = Backup.STATUS_FAILED
            backup.end_time = timezone.now()
            backup.error_message = str(e)
            backup.save()
            
            BackupLog.log_backup_error(backup, str(e))
        except:
            pass
        
        return {'status': 'failed', 'error': str(e)}


@shared_task
def restore_backup_task(restoration_id, **kwargs):
    """Main restore task (called from admin)"""
    try:
        from django.utils import timezone
        restoration = BackupRestoration.objects.get(id=restoration_id)
        backup = restoration.backup
        
        # Update status
        restoration.status = 'running'
        restoration.save()
        
        # Log start
        BackupLog.log_restoration_start(restoration, restoration.initiated_by)
        
        # Your actual restore logic here
        # For now, simulate restore
        result = {
            'status': 'completed',
            'restoration_id': restoration_id,
            'message': 'Restore task executed successfully'
        }
        
        # Update restoration
        restoration.status = 'completed'
        restoration.completed_at = timezone.now()
        restoration.success = True
        restoration.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Restore task failed: {str(e)}")
        
        # Mark as failed
        try:
            restoration.status = 'failed'
            restoration.completed_at = timezone.now()
            restoration.error_message = str(e)
            restoration.save()
        except:
            pass
        
        return {'status': 'failed', 'error': str(e)}


@shared_task
def cleanup_old_backups_task(**kwargs):
    """Cleanup old backups task (called from admin)"""
    try:
        from django.utils import timezone
        from django.db.models import Q
        
        # Find expired backups
        expired_backups = Backup.objects.filter(
            Q(expires_at__lt=timezone.now()) & 
            Q(is_permanent=False) &
            Q(auto_cleanup_enabled=True)
        )
        
        deleted_count = 0
        errors = []
        
        for backup in expired_backups:
            try:
                # Delete backup file
                if backup.backup_file:
                    backup.backup_file.delete(save=False)
                
                # Delete record
                backup.delete()
                deleted_count += 1
                
                # Log
                BackupLog.create_log(
                    level=BackupLog.LOG_LEVEL_INFO,
                    category=BackupLog.LOG_CATEGORY_CLEANUP,
                    action=BackupLog.ACTION_CLEANUP,
                    source=BackupLog.SOURCE_TASK,
                    message=f"Deleted expired backup: {backup.name}",
                    details={
                        'backup_id': str(backup.id),
                        'backup_name': backup.name,
                        'expired_at': backup.expires_at.isoformat() if backup.expires_at else None
                    }
                )
                
            except Exception as e:
                errors.append(f"Backup {backup.id}: {str(e)}")
                logger.error(f"Failed to delete backup {backup.id}: {str(e)}")
        
        result = {
            'deleted_count': deleted_count,
            'error_count': len(errors),
            'errors': errors if errors else None,
            'message': f"Cleaned up {deleted_count} backups"
        }
        
        # Send notification if any were deleted
        if deleted_count > 0:
            # Use the send_multi_channel_notification function if it exists
            try:
                send_multi_channel_notification.delay(
                    backup_id=None,
                    message=f"Cleanup completed: {deleted_count} backups deleted",
                    level='info' if not errors else 'warning'
                )
            except:
                pass
        
        return result
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}