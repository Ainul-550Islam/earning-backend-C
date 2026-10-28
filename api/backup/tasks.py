# api/backup/tasks.py
"""
Comprehensive Celery tasks for backup operations.
"""
import os
import json
import time
import hashlib
import psutil
import requests
import logging
from datetime import timedelta, datetime
from celery import shared_task
from django.db import transaction, models
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import (
    Backup, BackupLog, BackupStorageLocation, BackupRestoration, 
    BackupNotificationConfig, RetentionPolicy, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from .services import BackupService
from .services.factory import BackupServiceFactory
from .services.DatabaseBackup import DatabaseBackupService
from .services.BackupValidator import BackupValidator
from api.backup.models import BackupSchedule

User = get_user_model()
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

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def backup_database_task(self, backup_id, **kwargs):
    """Main backup task with comprehensive error handling and retry logic"""
    try:
        backup = Backup.objects.get(id=backup_id)
        
        # Update status to running
        backup.status = 'running'
        backup.start_time = timezone.now()
        backup.progress = 0
        backup.save(update_fields=['status', 'start_time', 'progress'])
        
        # Log backup start
        BackupLog.log_backup_start(
            backup=backup,
            message=f"Starting backup: {backup.name}",
            details={
                'backup_type': backup.backup_type,
                'storage_type': backup.storage_type,
                'database': backup.database_name
            }
        )
        
        # Initialize backup service
        backup_service = BackupService()
        
        # Perform backup based on type
        if backup.backup_type == 'full':
            result = _perform_full_backup(backup, backup_service)
        elif backup.backup_type == 'incremental':
            result = _perform_incremental_backup(backup, backup_service)
        elif backup.backup_type == 'differential':
            result = _perform_differential_backup(backup, backup_service)
        elif backup.backup_type == 'delta':
            result = _perform_delta_backup(backup, backup_service)
        else:
            raise ValueError(f"Unsupported backup type: {backup.backup_type}")
        
        # Update backup with results
        backup.status = 'completed' if result['success'] else 'failed'
        backup.end_time = timezone.now()
        backup.progress = 100 if result['success'] else 0
        
        if result['success']:
            backup.file_size = result.get('file_size', 0)
            backup.file_path = result.get('file_path', '')
            backup.file_hash = result.get('file_hash', '')
            backup.compression_method = result.get('compression_method', '')
            backup.encryption_method = result.get('encryption_method', '')
            backup.storage_locations = result.get('storage_locations', [])
            
            # Log completion
            BackupLog.log_backup_complete(
                backup=backup,
                message=f"Backup completed successfully: {backup.name}",
                details={
                    'duration': (backup.end_time - backup.start_time).total_seconds(),
                    'file_size': backup.file_size,
                    'compression': backup.compression_method,
                    'encryption': backup.encryption_method
                }
            )
            
            # Trigger post-backup tasks
            if backup.auto_verify:
                verify_backup_health_periodically.delay(
                    backup_id=str(backup.id),
                    verification_method='hash'
                )
            
            if backup.redundancy_level > 1:
                create_redundant_storage_copies.delay(backup_id=str(backup.id))
            
        else:
            backup.last_error = result.get('error', 'Unknown error')
            
            # Log failure
            BackupLog.log_backup_error(
                backup=backup,
                message=f"Backup failed: {backup.name}",
                details={'error': backup.last_error}
            )
            
            # Create alert for failed backup
            BackupAlert.create_alert(
                alert_type='failed',
                backup=backup,
                message=f"Backup failed: {backup.name} - {backup.last_error}",
                severity='high'
            )
        
        backup.save()
        
        return {
            'success': result['success'],
            'backup_id': backup_id,
            'status': backup.status,
            'message': result.get('message', ''),
            'error': result.get('error', '')
        }
        
    except Backup.DoesNotExist:
        logger.error(f"Backup {backup_id} not found")
        return {'success': False, 'error': 'Backup not found'}
    
    except Exception as e:
        logger.error(f"Backup task failed: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying backup task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        # Mark as failed after max retries
        try:
            backup = Backup.objects.get(id=backup_id)
            backup.status = 'failed'
            backup.end_time = timezone.now()
            backup.last_error = str(e)
            backup.save(update_fields=['status', 'end_time', 'last_error'])
            
            BackupLog.log_backup_error(
                backup=backup,
                message=f"Backup failed after retries: {backup.name}",
                details={'error': str(e), 'retries': self.request.retries}
            )
        except:
            pass
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def restore_backup_task(self, restoration_id, **kwargs):
    """Main restore task with comprehensive error handling and validation"""
    try:
        restoration = BackupRestoration.objects.get(id=restoration_id)
        backup = restoration.backup
        
        # Update status to running
        restoration.status = 'running'
        restoration.started_at = timezone.now()
        restoration.progress = 0
        restoration.save(update_fields=['status', 'started_at', 'progress'])
        
        # Log restoration start
        BackupLog.log_restoration_start(
            restoration=restoration,
            message=f"Starting restoration: {backup.name}",
            details={
                'restoration_type': restoration.restoration_type,
                'backup_id': str(backup.backup_id),
                'target_database': restoration.target_database
            }
        )
        
        # Validate backup before restoration
        if not backup.is_healthy:
            raise ValueError(f"Backup {backup.name} is not healthy for restoration")
        
        # Initialize backup service
        backup_service = BackupService()
        
        # Perform restoration based on type
        if restoration.restoration_type == 'full':
            result = _perform_full_restoration(restoration, backup, backup_service)
        elif restoration.restoration_type == 'partial':
            result = _perform_partial_restoration(restoration, backup, backup_service)
        elif restoration.restoration_type == 'schema_only':
            result = _perform_schema_restoration(restoration, backup, backup_service)
        elif restoration.restoration_type == 'data_only':
            result = _perform_data_restoration(restoration, backup, backup_service)
        else:
            raise ValueError(f"Unsupported restoration type: {restoration.restoration_type}")
        
        # Update restoration with results
        restoration.status = 'completed' if result['success'] else 'failed'
        restoration.completed_at = timezone.now()
        restoration.progress = 100 if result['success'] else 0
        restoration.success = result['success']
        
        if result['success']:
            restoration.rows_restored = result.get('rows_restored', 0)
            restoration.tables_restored = result.get('tables_restored', [])
            restoration.verification_passed = result.get('verification_passed', False)
            
            # Log completion
            BackupLog.objects.create(
                backup=backup,
                level='info',
                message=f"Restoration completed successfully: {backup.name}",
                category='restore',
                action='complete',
                details={
                    'restoration_id': str(restoration.restoration_id),
                    'duration': (restoration.completed_at - restoration.started_at).total_seconds(),
                    'rows_restored': restoration.rows_restored,
                    'tables_restored': restoration.tables_restored
                }
            )
            
            # Create verification record
            BackupVerification.objects.create(
                backup=backup,
                verification_method='test_restore',
                is_valid=True,
                verified_at=timezone.now(),
                verified_by=restoration.initiated_by,
                verification_details={
                    'restoration_id': str(restoration.restoration_id),
                    'rows_restored': restoration.rows_restored,
                    'success': True
                }
            )
            
        else:
            restoration.error_message = result.get('error', 'Unknown error')
            
            # Log failure
            BackupLog.objects.create(
                backup=backup,
                level='error',
                message=f"Restoration failed: {backup.name}",
                category='restore',
                action='fail',
                details={
                    'restoration_id': str(restoration.restoration_id),
                    'error': restoration.error_message
                }
            )
            
            # Create alert for failed restoration
            BackupAlert.create_alert(
                alert_type='failed',
                backup=backup,
                message=f"Restoration failed: {backup.name} - {restoration.error_message}",
                severity='critical'
            )
        
        restoration.save()
        
        return {
            'success': result['success'],
            'restoration_id': restoration_id,
            'status': restoration.status,
            'message': result.get('message', ''),
            'error': result.get('error', '')
        }
        
    except BackupRestoration.DoesNotExist:
        logger.error(f"Restoration {restoration_id} not found")
        return {'success': False, 'error': 'Restoration not found'}
    
    except Exception as e:
        logger.error(f"Restore task failed: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying restore task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        # Mark as failed after max retries
        try:
            restoration = BackupRestoration.objects.get(id=restoration_id)
            restoration.status = 'failed'
            restoration.completed_at = timezone.now()
            restoration.error_message = str(e)
            restoration.save(update_fields=['status', 'completed_at', 'error_message'])
            
            BackupLog.objects.create(
                backup=restoration.backup,
                level='error',
                message=f"Restoration failed after retries: {restoration.backup.name}",
                category='restore',
                action='fail',
                details={'error': str(e), 'retries': self.request.retries}
            )
        except:
            pass
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def cleanup_old_backups_task(self, **kwargs):
    """Comprehensive cleanup task with retention policy execution"""
    try:
        cleanup_type = kwargs.get('cleanup_type', 'expired')
        dry_run = kwargs.get('dry_run', False)
        batch_size = kwargs.get('batch_size', 50)
        
        deleted_count = 0
        failed_count = 0
        space_freed = 0
        errors = []
        
        if cleanup_type == 'expired':
            # Clean expired backups
            expired_backups = Backup.objects.filter(
                models.Q(expires_at__lt=timezone.now()) &
                models.Q(is_permanent=False) &
                models.Q(auto_cleanup_enabled=True)
            )[:batch_size]
            
            for backup in expired_backups:
                try:
                    if not dry_run:
                        # Delete from storage first
                        storage_service = BackupServiceFactory.get_service(backup.storage_type)
                        if storage_service:
                            storage_service.delete_backup(backup.file_path)
                        
                        # Get file size for space calculation
                        file_size = backup.file_size or 0
                        space_freed += file_size
                        
                        # Delete backup record
                        backup.delete()
                        deleted_count += 1
                        
                        # Log deletion
                        BackupLog.objects.create(
                            level='info',
                            message=f"Cleaned up expired backup: {backup.name}",
                            category='cleanup',
                            action='delete',
                            details={
                                'backup_id': str(backup.backup_id),
                                'file_size': file_size,
                                'expired_at': backup.expires_at.isoformat() if backup.expires_at else None
                            }
                        )
                    else:
                        deleted_count += 1  # Count for dry run
                        
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Backup {backup.backup_id}: {str(e)}")
                    logger.error(f"Failed to cleanup backup {backup.backup_id}: {str(e)}")
        
        elif cleanup_type == 'retention_policy':
            # Execute retention policies
            policies = RetentionPolicy.objects.filter(is_active=True)
            
            for policy in policies:
                try:
                    result = execute_gfs_retention_policy(str(policy.id))
                    if result.get('success'):
                        deleted_count += result.get('deleted_count', 0)
                        space_freed += result.get('space_freed', 0)
                    else:
                        failed_count += 1
                        errors.append(f"Policy {policy.name}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Policy {policy.name}: {str(e)}")
                    logger.error(f"Failed to execute retention policy {policy.name}: {str(e)}")
        
        elif cleanup_type == 'orphaned':
            # Clean orphaned backup files
            orphaned_count = _cleanup_orphaned_files(dry_run=dry_run)
            deleted_count = orphaned_count
        
        # Log cleanup summary
        BackupLog.objects.create(
            level='info',
            message=f"Cleanup completed: {deleted_count} deleted, {failed_count} failed",
            category='cleanup',
            action='execute',
            details={
                'cleanup_type': cleanup_type,
                'deleted_count': deleted_count,
                'failed_count': failed_count,
                'space_freed': space_freed,
                'dry_run': dry_run,
                'errors': errors[:5]  # Limit errors in log
            }
        )
        
        # Send notification if significant cleanup occurred
        if deleted_count > 0:
            level = 'info' if failed_count == 0 else 'warning'
            message = f"Cleanup completed: {deleted_count} backups deleted"
            if space_freed > 0:
                message += f", {_format_bytes(space_freed)} freed"
            if failed_count > 0:
                message += f", {failed_count} failed"
            
            send_multi_channel_notification.delay(
                backup_id=None,
                message=message,
                level=level
            )
        
        return {
            'success': True,
            'cleanup_type': cleanup_type,
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'space_freed': space_freed,
            'dry_run': dry_run,
            'errors': errors if errors else None,
            'message': f"Cleanup completed: {deleted_count} deleted, {failed_count} failed"
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying cleanup task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=300 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(e)}


# ==================== HELPER FUNCTIONS ====================

def _perform_full_backup(backup, backup_service):
    """Perform full backup"""
    try:
        # Initialize database backup service
        db_service = DatabaseBackupService()
        
        # Create database dump
        dump_result = db_service.create_backup(
            database_name=backup.database_name,
            backup_type='full',
            tables_include=backup.tables_include,
            tables_exclude=backup.tables_exclude
        )
        
        if not dump_result['success']:
            return {'success': False, 'error': dump_result.get('error', 'Database dump failed')}
        
        # Process backup file (compress, encrypt)
        processed_file = _process_backup_file(
            dump_result['file_path'],
            backup.compression_method,
            backup.encryption_method
        )
        
        # Save to storage
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        if not storage_service:
            return {'success': False, 'error': f'Storage service {backup.storage_type} not available'}
        
        storage_result = storage_service.save_backup(
            file_path=processed_file,
            backup_name=backup.name,
            metadata={
                'backup_id': str(backup.backup_id),
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'created_at': backup.start_time.isoformat()
            }
        )
        
        if not storage_result['success']:
            return {'success': False, 'error': storage_result.get('error', 'Storage upload failed')}
        
        # Calculate file hash
        file_hash = _calculate_file_hash(processed_file)
        
        return {
            'success': True,
            'file_path': processed_file,
            'file_size': os.path.getsize(processed_file),
            'file_hash': file_hash,
            'storage_locations': [storage_result.get('location_id')],
            'compression_method': backup.compression_method,
            'encryption_method': backup.encryption_method
        }
        
    except Exception as e:
        logger.error(f"Full backup failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_incremental_backup(backup, backup_service):
    """Perform incremental backup"""
    try:
        # Get last full backup as base
        last_full = Backup.objects.filter(
            backup_type='full',
            database_name=backup.database_name,
            status='completed'
        ).order_by('-start_time').first()
        
        if not last_full:
            return {'success': False, 'error': 'No full backup found for incremental backup'}
        
        backup.parent_backup = last_full
        backup.save(update_fields=['parent_backup'])
        
        # Get changed tables since last backup
        changed_tables = _get_changed_tables_since(last_full.start_time)
        
        if not changed_tables:
            return {'success': True, 'message': 'No changes detected'}
        
        # Create incremental dump
        db_service = DatabaseBackupService()
        dump_result = db_service.create_backup(
            database_name=backup.database_name,
            backup_type='incremental',
            tables_include=changed_tables,
            base_backup=last_full
        )
        
        if not dump_result['success']:
            return {'success': False, 'error': dump_result.get('error', 'Incremental dump failed')}
        
        # Process and save
        processed_file = _process_backup_file(
            dump_result['file_path'],
            backup.compression_method,
            backup.encryption_method
        )
        
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        storage_result = storage_service.save_backup(
            file_path=processed_file,
            backup_name=backup.name,
            metadata={
                'backup_id': str(backup.backup_id),
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'parent_backup': str(last_full.backup_id),
                'changed_tables': changed_tables
            }
        )
        
        return {
            'success': True,
            'file_path': processed_file,
            'file_size': os.path.getsize(processed_file),
            'file_hash': _calculate_file_hash(processed_file),
            'storage_locations': [storage_result.get('location_id')],
            'changed_tables': changed_tables
        }
        
    except Exception as e:
        logger.error(f"Incremental backup failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_differential_backup(backup, backup_service):
    """Perform differential backup"""
    try:
        # Get last full backup as base
        last_full = Backup.objects.filter(
            backup_type='full',
            database_name=backup.database_name,
            status='completed'
        ).order_by('-start_time').first()
        
        if not last_full:
            return {'success': False, 'error': 'No full backup found for differential backup'}
        
        backup.parent_backup = last_full
        backup.save(update_fields=['parent_backup'])
        
        # Get all changes since last full backup
        changed_tables = _get_changed_tables_since(last_full.start_time)
        
        if not changed_tables:
            return {'success': True, 'message': 'No changes detected'}
        
        # Create differential dump
        db_service = DatabaseBackupService()
        dump_result = db_service.create_backup(
            database_name=backup.database_name,
            backup_type='differential',
            tables_include=changed_tables,
            base_backup=last_full
        )
        
        if not dump_result['success']:
            return {'success': False, 'error': dump_result.get('error', 'Differential dump failed')}
        
        # Process and save
        processed_file = _process_backup_file(
            dump_result['file_path'],
            backup.compression_method,
            backup.encryption_method
        )
        
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        storage_result = storage_service.save_backup(
            file_path=processed_file,
            backup_name=backup.name,
            metadata={
                'backup_id': str(backup.backup_id),
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'parent_backup': str(last_full.backup_id),
                'changed_tables': changed_tables
            }
        )
        
        return {
            'success': True,
            'file_path': processed_file,
            'file_size': os.path.getsize(processed_file),
            'file_hash': _calculate_file_hash(processed_file),
            'storage_locations': [storage_result.get('location_id')],
            'changed_tables': changed_tables
        }
        
    except Exception as e:
        logger.error(f"Differential backup failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_delta_backup(backup, backup_service):
    """Perform delta backup (binary-level changes)"""
    try:
        # Get last backup as base
        last_backup = Backup.objects.filter(
            database_name=backup.database_name,
            status='completed'
        ).order_by('-start_time').first()
        
        if not last_backup:
            return {'success': False, 'error': 'No previous backup found for delta backup'}
        
        backup.parent_backup = last_backup
        backup.save(update_fields=['parent_backup'])
        
        # Create delta backup using WAL or binary diff
        db_service = DatabaseBackupService()
        dump_result = db_service.create_backup(
            database_name=backup.database_name,
            backup_type='delta',
            base_backup=last_backup
        )
        
        if not dump_result['success']:
            return {'success': False, 'error': dump_result.get('error', 'Delta backup failed')}
        
        # Process and save
        processed_file = _process_backup_file(
            dump_result['file_path'],
            backup.compression_method,
            backup.encryption_method
        )
        
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        storage_result = storage_service.save_backup(
            file_path=processed_file,
            backup_name=backup.name,
            metadata={
                'backup_id': str(backup.backup_id),
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'parent_backup': str(last_backup.backup_id)
            }
        )
        
        # Create delta tracker
        DeltaBackupTracker.objects.create(
            parent_backup=last_backup,
            child_backup=backup,
            changed_tables=dump_result.get('changed_tables', []),
            changed_row_count=dump_result.get('changed_row_count', 0),
            change_percentage=dump_result.get('change_percentage', 0)
        )
        
        return {
            'success': True,
            'file_path': processed_file,
            'file_size': os.path.getsize(processed_file),
            'file_hash': _calculate_file_hash(processed_file),
            'storage_locations': [storage_result.get('location_id')]
        }
        
    except Exception as e:
        logger.error(f"Delta backup failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_full_restoration(restoration, backup, backup_service):
    """Perform full database restoration"""
    try:
        # Download backup from storage
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        download_result = storage_service.download_backup(
            backup.file_path,
            target_path=f"/tmp/restore_{backup.backup_id}.bak"
        )
        
        if not download_result['success']:
            return {'success': False, 'error': 'Failed to download backup'}
        
        local_file = download_result['file_path']
        
        # Decrypt if needed
        if backup.encryption_method:
            local_file = _decrypt_backup_file(local_file, backup.encryption_method)
        
        # Decompress if needed
        if backup.compression_method:
            local_file = _decompress_backup_file(local_file, backup.compression_method)
        
        # Perform restoration
        db_service = DatabaseBackupService()
        restore_result = db_service.restore_backup(
            backup_file=local_file,
            target_database=restoration.target_database,
            restoration_type='full'
        )
        
        if restore_result['success']:
            # Verify restoration
            verification_result = _verify_restoration(
                restoration.target_database,
                backup.database_name
            )
            
            return {
                'success': True,
                'rows_restored': restore_result.get('rows_restored', 0),
                'tables_restored': restore_result.get('tables_restored', []),
                'verification_passed': verification_result['success']
            }
        else:
            return {'success': False, 'error': restore_result.get('error', 'Restoration failed')}
        
    except Exception as e:
        logger.error(f"Full restoration failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_partial_restoration(restoration, backup, backup_service):
    """Perform partial database restoration"""
    try:
        # Similar to full restoration but with specific tables
        tables_to_restore = restoration.tables_include or []
        
        if not tables_to_restore:
            return {'success': False, 'error': 'No tables specified for partial restoration'}
        
        # Download and process backup
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        download_result = storage_service.download_backup(
            backup.file_path,
            target_path=f"/tmp/restore_{backup.backup_id}.bak"
        )
        
        if not download_result['success']:
            return {'success': False, 'error': 'Failed to download backup'}
        
        local_file = download_result['file_path']
        
        if backup.encryption_method:
            local_file = _decrypt_backup_file(local_file, backup.encryption_method)
        
        if backup.compression_method:
            local_file = _decompress_backup_file(local_file, backup.compression_method)
        
        # Perform partial restoration
        db_service = DatabaseBackupService()
        restore_result = db_service.restore_backup(
            backup_file=local_file,
            target_database=restoration.target_database,
            restoration_type='partial',
            tables_include=tables_to_restore
        )
        
        return {
            'success': restore_result['success'],
            'rows_restored': restore_result.get('rows_restored', 0),
            'tables_restored': restore_result.get('tables_restored', []),
            'error': restore_result.get('error', '')
        }
        
    except Exception as e:
        logger.error(f"Partial restoration failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_schema_restoration(restoration, backup, backup_service):
    """Perform schema-only restoration"""
    try:
        # Download and process backup
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        download_result = storage_service.download_backup(
            backup.file_path,
            target_path=f"/tmp/restore_{backup.backup_id}.bak"
        )
        
        if not download_result['success']:
            return {'success': False, 'error': 'Failed to download backup'}
        
        local_file = download_result['file_path']
        
        if backup.encryption_method:
            local_file = _decrypt_backup_file(local_file, backup.encryption_method)
        
        if backup.compression_method:
            local_file = _decompress_backup_file(local_file, backup.compression_method)
        
        # Perform schema restoration
        db_service = DatabaseBackupService()
        restore_result = db_service.restore_backup(
            backup_file=local_file,
            target_database=restoration.target_database,
            restoration_type='schema_only'
        )
        
        return {
            'success': restore_result['success'],
            'tables_restored': restore_result.get('tables_restored', []),
            'error': restore_result.get('error', '')
        }
        
    except Exception as e:
        logger.error(f"Schema restoration failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _perform_data_restoration(restoration, backup, backup_service):
    """Perform data-only restoration"""
    try:
        # Download and process backup
        storage_service = BackupServiceFactory.get_service(backup.storage_type)
        download_result = storage_service.download_backup(
            backup.file_path,
            target_path=f"/tmp/restore_{backup.backup_id}.bak"
        )
        
        if not download_result['success']:
            return {'success': False, 'error': 'Failed to download backup'}
        
        local_file = download_result['file_path']
        
        if backup.encryption_method:
            local_file = _decrypt_backup_file(local_file, backup.encryption_method)
        
        if backup.compression_method:
            local_file = _decompress_backup_file(local_file, backup.compression_method)
        
        # Perform data restoration
        db_service = DatabaseBackupService()
        restore_result = db_service.restore_backup(
            backup_file=local_file,
            target_database=restoration.target_database,
            restoration_type='data_only'
        )
        
        return {
            'success': restore_result['success'],
            'rows_restored': restore_result.get('rows_restored', 0),
            'tables_restored': restore_result.get('tables_restored', []),
            'error': restore_result.get('error', '')
        }
        
    except Exception as e:
        logger.error(f"Data restoration failed: {str(e)}")
        return {'success': False, 'error': str(e)}


def _process_backup_file(file_path, compression_method, encryption_method):
    """Process backup file with compression and encryption"""
    processed_file = file_path
    
    try:
        # Apply compression
        if compression_method:
            processed_file = _compress_file(processed_file, compression_method)
        
        # Apply encryption
        if encryption_method:
            processed_file = _encrypt_file(processed_file, encryption_method)
        
        return processed_file
        
    except Exception as e:
        logger.error(f"File processing failed: {str(e)}")
        raise


def _calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file"""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Hash calculation failed: {str(e)}")
        return ""


def _get_changed_tables_since(since_time):
    """Get list of changed tables since given time"""
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Query for changed tables (PostgreSQL example)
            cursor.execute("""
                SELECT schemaname, tablename
                FROM pg_stat_user_tables
                WHERE last_vacuum > %s OR last_autovacuum > %s
                   OR last_analyze > %s OR last_autoanalyze > %s
            """, [since_time, since_time, since_time, since_time])
            
            rows = cursor.fetchall()
            return [f"{row[0]}.{row[1]}" for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get changed tables: {str(e)}")
        return []


def _cleanup_orphaned_files(dry_run=False):
    """Clean up orphaned backup files"""
    try:
        # Get all backup records
        backup_files = set()
        for backup in Backup.objects.all():
            if backup.file_path and os.path.exists(backup.file_path):
                backup_files.add(backup.file_path)
        
        # Get all files in backup directories
        all_backup_files = set()
        backup_dirs = getattr(settings, 'BACKUP_DIRS', ['/tmp/backups'])
        
        for backup_dir in backup_dirs:
            if os.path.exists(backup_dir):
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        all_backup_files.add(file_path)
        
        # Find orphaned files
        orphaned_files = all_backup_files - backup_files
        
        deleted_count = 0
        for file_path in orphaned_files:
            try:
                if not dry_run:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted orphaned file: {file_path}")
                else:
                    deleted_count += 1
                    logger.info(f"Would delete orphaned file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete orphaned file {file_path}: {str(e)}")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Orphaned file cleanup failed: {str(e)}")
        return 0


def _format_bytes(bytes_count):
    """Format bytes in human readable format"""
    try:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"
    except:
        return f"{bytes_count} bytes"


# Placeholder functions for encryption/compression (would be implemented in services)
def _compress_file(file_path, method):
    """Compress file using specified method"""
    # This would be implemented using the compression services
    return file_path


def _encrypt_file(file_path, method):
    """Encrypt file using specified method"""
    # This would be implemented using the encryption services
    return file_path


def _decrypt_backup_file(file_path, method):
    """Decrypt backup file"""
    # This would be implemented using the encryption services
    return file_path


def _decompress_backup_file(file_path, method):
    """Decompress backup file"""
    # This would be implemented using the compression services
    return file_path


def _verify_restoration(target_db, source_db):
    """Verify restoration integrity"""
    # This would implement restoration verification logic
    return {'success': True}


# ==================== ADDITIONAL COMPREHENSIVE TASKS ====================

@shared_task
def schedule_backup_monitoring():
    """Monitor backup schedules and trigger missed backups"""
    try:
        now = timezone.now()
        
        # Get schedules that should have run
        missed_schedules = BackupSchedule.objects.filter(
            is_active=True,
            is_paused=False,
            next_run__lt=now,
            last_run__lt=now - timezone.timedelta(hours=1)  # Allow 1 hour grace period
        )
        
        for schedule in missed_schedules:
            # Create alert for missed schedule
            BackupAlert.create_alert(
                alert_type='schedule_missed',
                backup=None,
                message=f"Schedule '{schedule.name}' missed its run time",
                severity='medium',
                metadata={'schedule_id': str(schedule.id), 'missed_time': schedule.next_run.isoformat()}
            )
            
            # Calculate next run time
            if hasattr(schedule, 'calculate_next_run'):
                schedule.next_run = schedule.calculate_next_run()
                schedule.save(update_fields=['next_run'])
            
            # Send notification
            send_multi_channel_notification.delay(
                backup_id=None,
                message=f"Schedule '{schedule.name}' missed its run time",
                level='warning'
            )
        
        return {
            'success': True,
            'missed_schedules': missed_schedules.count(),
            'message': f"Found {missed_schedules.count()} missed schedules"
        }
        
    except Exception as e:
        logger.error(f"Schedule monitoring failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def backup_storage_health_check():
    """Check health of all backup storage locations"""
    try:
        locations = BackupStorageLocation.objects.filter(is_active=True)
        
        healthy_count = 0
        unhealthy_count = 0
        issues = []
        
        for location in locations:
            try:
                # Test connectivity
                storage_service = BackupServiceFactory.get_service(location.storage_type)
                if storage_service and storage_service.test_connection():
                    location.is_connected = True
                    location.last_checked = timezone.now()
                    location.connection_errors = 0
                    healthy_count += 1
                else:
                    location.is_connected = False
                    location.connection_errors += 1
                    unhealthy_count += 1
                    issues.append(f"{location.name}: Connection failed")
                    
                    # Create alert for storage issues
                    if location.connection_errors >= 3:
                        BackupAlert.create_alert(
                            alert_type='storage_full',
                            backup=None,
                            message=f"Storage location '{location.name}' is unreachable",
                            severity='high'
                        )
                
                location.save(update_fields=['is_connected', 'last_checked', 'connection_errors'])
                
            except Exception as e:
                logger.error(f"Storage health check failed for {location.name}: {str(e)}")
                unhealthy_count += 1
                issues.append(f"{location.name}: {str(e)}")
        
        return {
            'success': True,
            'healthy_count': healthy_count,
            'unhealthy_count': unhealthy_count,
            'issues': issues,
            'message': f"Storage health check: {healthy_count} healthy, {unhealthy_count} unhealthy"
        }
        
    except Exception as e:
        logger.error(f"Storage health check failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def backup_analytics_report():
    """Generate comprehensive backup analytics report"""
    try:
        # Get statistics
        total_backups = Backup.objects.count()
        completed_backups = Backup.objects.filter(status='completed').count()
        failed_backups = Backup.objects.filter(status='failed').count()
        
        # Storage usage
        total_storage = Backup.objects.aggregate(
            models.Sum('file_size')
        )['file_size__sum'] or 0
        
        # Success rate
        success_rate = (completed_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_backups = Backup.objects.filter(start_time__gte=week_ago).count()
        
        # Health status
        healthy_backups = Backup.objects.filter(is_healthy=True).count()
        
        # Create report
        report_data = {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'success_rate': round(success_rate, 2),
            'total_storage_bytes': total_storage,
            'total_storage_human': _format_bytes(total_storage),
            'recent_backups_7_days': recent_backups,
            'healthy_backups': healthy_backups,
            'generated_at': timezone.now().isoformat()
        }
        
        # Log report
        BackupLog.objects.create(
            level='info',
            message="Backup analytics report generated",
            category='system',
            action='report',
            details=report_data
        )
        
        return {
            'success': True,
            'report_data': report_data,
            'message': 'Analytics report generated successfully'
        }
        
    except Exception as e:
        logger.error(f"Analytics report failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def backup_encryption_key_rotation():
    """Rotate encryption keys for old backups"""
    try:
        # Get backups with old encryption
        rotation_threshold = timezone.now() - timezone.timedelta(days=90)
        old_encrypted_backups = Backup.objects.filter(
            encryption_method__isnull=False,
            start_time__lt=rotation_threshold
        )
        
        rotated_count = 0
        failed_count = 0
        
        for backup in old_encrypted_backups:
            try:
                # Re-encrypt with new key
                encrypt_backup_task.delay(
                    backup_id=str(backup.id),
                    re_encrypt=True,
                    rotate_key=True
                )
                rotated_count += 1
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to rotate key for backup {backup.id}: {str(e)}")
        
        return {
            'success': True,
            'rotated_count': rotated_count,
            'failed_count': failed_count,
            'message': f"Key rotation initiated for {rotated_count} backups"
        }
        
    except Exception as e:
        logger.error(f"Key rotation failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def backup_performance_optimization():
    """Optimize backup performance based on historical data"""
    try:
        # Analyze backup performance
        recent_backups = Backup.objects.filter(
            status='completed',
            start_time__gte=timezone.now() - timezone.timedelta(days=30)
        )
        
        optimizations = []
        
        if recent_backups.exists():
            # Calculate average backup duration
            from django.db.models import Avg
            avg_duration = recent_backups.aggregate(
                avg_duration=Avg(
                    models.F('end_time') - models.F('start_time')
                )
            )['avg_duration']
            
            if avg_duration and avg_duration.total_seconds() > 3600:  # More than 1 hour
                optimizations.append({
                    'type': 'parallel_processing',
                    'recommendation': 'Consider enabling parallel processing for large databases',
                    'impact': 'high'
                })
            
            # Check compression efficiency
            compressed_backups = recent_backups.filter(
                compression_method__isnull=False
            )
            
            if compressed_backups.exists():
                avg_compression_ratio = compressed_backups.aggregate(
                    avg_ratio=Avg('file_size') / Avg('original_size')
                )['avg_ratio']
                
                if avg_compression_ratio and avg_compression_ratio > 0.8:
                    optimizations.append({
                        'type': 'compression_method',
                        'recommendation': 'Consider using more efficient compression method',
                        'impact': 'medium'
                    })
        
        # Log optimizations
        if optimizations:
            BackupLog.objects.create(
                level='info',
                message="Backup performance optimizations identified",
                category='performance',
                action='analyze',
                details={'optimizations': optimizations}
            )
        
        return {
            'success': True,
            'optimizations': optimizations,
            'message': f"Found {len(optimizations)} optimization opportunities"
        }
        
    except Exception as e:
        logger.error(f"Performance optimization failed: {str(e)}")
        return {'success': False, 'error': str(e)}