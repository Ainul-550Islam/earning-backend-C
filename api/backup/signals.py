# api/backup/signals.py
"""
Production-ready signals for api.backup.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    BackupRestoration, BackupNotificationConfig, RetentionPolicy,
    DeltaBackupTracker, BackupVerification, BackupEncryption, BackupAlert
)
from .tasks import (
    backup_database_task, restore_backup_task, cleanup_old_backups_task,
    perform_delta_backup, execute_gfs_retention_policy,
    send_multi_channel_notification, auto_cleanup_expired_backups,
    verify_backup_health_periodically, create_redundant_storage_copies,
    consolidate_delta_backup_chain
)

logger = logging.getLogger(__name__)

# ==================== CUSTOM SIGNALS ====================

# Backup lifecycle signals
backup_started = Signal()
backup_completed = Signal()
backup_failed = Signal()
backup_cancelled = Signal()
backup_verified = Signal()
backup_restored = Signal()

# Schedule signals
schedule_triggered = Signal()
schedule_completed = Signal()
schedule_failed = Signal()
schedule_paused = Signal()
schedule_resumed = Signal()

# Storage signals
storage_connected = Signal()
storage_disconnected = Signal()
storage_full = Signal()
storage_error = Signal()

# Alert signals
alert_created = Signal()
alert_resolved = Signal()
alert_escalated = Signal()

# System signals
maintenance_mode_enabled = Signal()
maintenance_mode_disabled = Signal()
retention_policy_executed = Signal()
health_check_completed = Signal()

# ==================== MODEL SIGNALS ====================

@receiver(pre_save, sender=Backup)
def backup_pre_save(sender, instance, **kwargs):
    """Handle backup pre-save operations"""
    try:
        # Set default values if not provided
        if not instance.backup_id:
            import uuid
            instance.backup_id = str(uuid.uuid4())
        
        # Set start time if status is changing to running
        if instance.pk:
            old_instance = Backup.objects.get(pk=instance.pk)
            if old_instance.status != 'running' and instance.status == 'running':
                instance.start_time = timezone.now()
                
                # Log backup start
                BackupLog.log_backup_start(
                    backup=instance,
                    message=f"Backup '{instance.name}' started",
                    details={'backup_type': instance.backup_type, 'storage_type': instance.storage_type}
                )
                
                # Send backup started signal
                backup_started.send(sender=Backup, backup=instance)
                
                # Send notification if configured
                if instance.notification_channels:
                    send_multi_channel_notification.delay(
                        backup_id=str(instance.id),
                        message=f"Backup started: {instance.name}",
                        level='info',
                        channels=instance.notification_channels
                    )
        
        # Calculate expiration if retention days is set
        if instance.retention_days and not instance.expires_at:
            instance.expires_at = timezone.now() + timezone.timedelta(days=instance.retention_days)
            
    except Exception as e:
        logger.error(f"Error in backup_pre_save: {str(e)}")


@receiver(post_save, sender=Backup)
def backup_post_save(sender, instance, created, **kwargs):
    """Handle backup post-save operations"""
    try:
        if created:
            # New backup created
            logger.info(f"New backup created: {instance.name}")
            
            # Log creation
            BackupLog.log_backup_start(
                backup=instance,
                message=f"Backup '{instance.name}' created",
                details={'backup_id': str(instance.backup_id)}
            )
        else:
            # Backup updated - check for status changes
            old_instance = Backup.objects.get(pk=instance.pk) if instance.pk else None
            if old_instance and old_instance.status != instance.status:
                
                if instance.status == 'completed':
                    # Backup completed
                    if not instance.end_time:
                        instance.end_time = timezone.now()
                        instance.save(update_fields=['end_time'])
                    
                    # Calculate duration
                    if instance.start_time:
                        duration = instance.end_time - instance.start_time
                        logger.info(f"Backup '{instance.name}' completed in {duration}")
                    
                    # Log completion
                    BackupLog.log_backup_complete(
                        backup=instance,
                        message=f"Backup '{instance.name}' completed successfully",
                        details={
                            'duration': str(duration) if instance.start_time else None,
                            'file_size': instance.file_size,
                            'storage_type': instance.storage_type
                        }
                    )
                    
                    # Send backup completed signal
                    backup_completed.send(sender=Backup, backup=instance)
                    
                    # Send notification if configured
                    if instance.notification_channels:
                        send_multi_channel_notification.delay(
                            backup_id=str(instance.id),
                            message=f"Backup completed successfully: {instance.name}",
                            level='success',
                            channels=instance.notification_channels
                        )
                    
                    # Trigger verification if configured
                    if instance.auto_verify:
                        verify_backup_health_periodically.delay(
                            backup_id=str(instance.id),
                            verification_method='hash'
                        )
                    
                    # Create redundant copies if configured
                    if instance.redundancy_level > 1:
                        create_redundant_storage_copies.delay(
                            backup_id=str(instance.id)
                        )
                
                elif instance.status == 'failed':
                    # Backup failed
                    logger.error(f"Backup '{instance.name}' failed: {instance.last_error}")
                    
                    # Log failure
                    BackupLog.log_backup_error(
                        backup=instance,
                        message=f"Backup '{instance.name}' failed",
                        details={'error': instance.last_error, 'status': instance.status}
                    )
                    
                    # Send backup failed signal
                    backup_failed.send(sender=Backup, backup=instance)
                    
                    # Create alert for failed backup
                    BackupAlert.create_alert(
                        alert_type='failed',
                        backup=instance,
                        message=f"Backup failed: {instance.name} - {instance.last_error}",
                        severity='high'
                    )
                    
                    # Send notification if configured
                    if instance.notification_channels:
                        send_multi_channel_notification.delay(
                            backup_id=str(instance.id),
                            message=f"Backup failed: {instance.name} - {instance.last_error}",
                            level='error',
                            channels=instance.notification_channels
                        )
                
                elif instance.status == 'cancelled':
                    # Backup cancelled
                    logger.warning(f"Backup '{instance.name}' was cancelled")
                    
                    # Log cancellation
                    BackupLog.log_backup_error(
                        backup=instance,
                        message=f"Backup '{instance.name}' cancelled",
                        details={'status': instance.status}
                    )
                    
                    # Send backup cancelled signal
                    backup_cancelled.send(sender=Backup, backup=instance)
                    
                    # Send notification if configured
                    if instance.notification_channels:
                        send_multi_channel_notification.delay(
                            backup_id=str(instance.id),
                            message=f"Backup cancelled: {instance.name}",
                            level='warning',
                            channels=instance.notification_channels
                        )
    
    except Exception as e:
        logger.error(f"Error in backup_post_save: {str(e)}")


@receiver(pre_delete, sender=Backup)
def backup_pre_delete(sender, instance, **kwargs):
    """Handle backup pre-delete operations"""
    try:
        logger.info(f"Backup '{instance.name}' being deleted")
        
        # Log deletion
        BackupLog.objects.create(
            backup=instance,
            level='warning',
            message=f"Backup '{instance.name}' being deleted",
            category='cleanup',
            action='delete',
            details={
                'backup_id': str(instance.backup_id),
                'file_size': instance.file_size,
                'storage_type': instance.storage_type
            }
        )
        
        # Check if backup file exists and delete it
        if instance.file_path:
            import os
            try:
                if os.path.exists(instance.file_path):
                    os.remove(instance.file_path)
                    logger.info(f"Deleted backup file: {instance.file_path}")
            except Exception as e:
                logger.error(f"Failed to delete backup file {instance.file_path}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in backup_pre_delete: {str(e)}")


@receiver(post_save, sender=BackupSchedule)
def backup_schedule_post_save(sender, instance, created, **kwargs):
    """Handle backup schedule post-save operations"""
    try:
        if created:
            logger.info(f"New backup schedule created: {instance.name}")
            
            # Log schedule creation
            BackupLog.objects.create(
                level='info',
                message=f"Backup schedule '{instance.name}' created",
                category='schedule',
                action='create',
                details={
                    'schedule_id': str(instance.id),
                    'frequency': instance.frequency,
                    'backup_type': instance.backup_type,
                    'next_run': instance.next_run.isoformat() if instance.next_run else None
                }
            )
        else:
            # Check if schedule was activated
            old_instance = BackupSchedule.objects.get(pk=instance.pk) if instance.pk else None
            if old_instance and not old_instance.is_active and instance.is_active:
                # Schedule was activated
                logger.info(f"Backup schedule '{instance.name}' activated")
                
                # Send schedule resumed signal
                schedule_resumed.send(sender=BackupSchedule, schedule=instance)
                
                # Log activation
                BackupLog.objects.create(
                    level='info',
                    message=f"Backup schedule '{instance.name}' activated",
                    category='schedule',
                    action='update',
                    details={'schedule_id': str(instance.id)}
                )
            
            elif old_instance and old_instance.is_active and not instance.is_active:
                # Schedule was deactivated
                logger.info(f"Backup schedule '{instance.name}' deactivated")
                
                # Send schedule paused signal
                schedule_paused.send(sender=BackupSchedule, schedule=instance)
                
                # Log deactivation
                BackupLog.objects.create(
                    level='warning',
                    message=f"Backup schedule '{instance.name}' deactivated",
                    category='schedule',
                    action='update',
                    details={'schedule_id': str(instance.id)}
                )
    
    except Exception as e:
        logger.error(f"Error in backup_schedule_post_save: {str(e)}")


@receiver(post_save, sender=BackupRestoration)
def backup_restoration_post_save(sender, instance, created, **kwargs):
    """Handle backup restoration post-save operations"""
    try:
        if created:
            logger.info(f"New backup restoration created: {instance.restoration_id}")
            
            # Log restoration start
            BackupLog.log_restoration_start(
                restoration=instance,
                message=f"Restoration '{instance.restoration_id}' started",
                details={
                    'restoration_type': instance.restoration_type,
                    'backup_id': str(instance.backup.backup_id) if instance.backup else None
                }
            )
        else:
            # Check for status changes
            old_instance = BackupRestoration.objects.get(pk=instance.pk) if instance.pk else None
            if old_instance and old_instance.status != instance.status:
                
                if instance.status == 'completed':
                    # Restoration completed
                    if not instance.completed_at:
                        instance.completed_at = timezone.now()
                        instance.save(update_fields=['completed_at'])
                    
                    # Calculate duration
                    if instance.started_at:
                        duration = instance.completed_at - instance.started_at
                        logger.info(f"Restoration '{instance.restoration_id}' completed in {duration}")
                    
                    # Log completion
                    BackupLog.objects.create(
                        backup=instance.backup,
                        level='info',
                        message=f"Restoration '{instance.restoration_id}' completed successfully",
                        category='restore',
                        action='complete',
                        details={
                            'restoration_id': str(instance.restoration_id),
                            'duration': str(duration) if instance.started_at else None,
                            'success': instance.success
                        }
                    )
                    
                    # Send backup restored signal
                    backup_restored.send(sender=BackupRestoration, restoration=instance)
                    
                    # Send notification if backup has notification channels
                    if instance.backup and instance.backup.notification_channels:
                        send_multi_channel_notification.delay(
                            backup_id=str(instance.backup.id),
                            message=f"Restoration completed: {instance.backup.name}",
                            level='success',
                            channels=instance.backup.notification_channels
                        )
                
                elif instance.status == 'failed':
                    # Restoration failed
                    logger.error(f"Restoration '{instance.restoration_id}' failed: {instance.error_message}")
                    
                    # Log failure
                    BackupLog.objects.create(
                        backup=instance.backup,
                        level='error',
                        message=f"Restoration '{instance.restoration_id}' failed",
                        category='restore',
                        action='fail',
                        details={
                            'restoration_id': str(instance.restoration_id),
                            'error': instance.error_message
                        }
                    )
                    
                    # Create alert for failed restoration
                    BackupAlert.create_alert(
                        alert_type='failed',
                        backup=instance.backup,
                        message=f"Restoration failed: {instance.restoration_id} - {instance.error_message}",
                        severity='critical'
                    )
                    
                    # Send notification if backup has notification channels
                    if instance.backup and instance.backup.notification_channels:
                        send_multi_channel_notification.delay(
                            backup_id=str(instance.backup.id),
                            message=f"Restoration failed: {instance.backup.name} - {instance.error_message}",
                            level='error',
                            channels=instance.backup.notification_channels
                        )
    
    except Exception as e:
        logger.error(f"Error in backup_restoration_post_save: {str(e)}")


@receiver(post_save, sender=BackupVerification)
def backup_verification_post_save(sender, instance, created, **kwargs):
    """Handle backup verification post-save operations"""
    try:
        if created:
            logger.info(f"New backup verification created: {instance.verification_id}")
            
            # Log verification start
            BackupLog.objects.create(
                backup=instance.backup,
                level='info',
                message=f"Verification '{instance.verification_id}' started",
                category='validation',
                action='start',
                details={
                    'verification_id': str(instance.verification_id),
                    'verification_method': instance.verification_method
                }
            )
        else:
            # Check if verification was completed
            if instance.is_valid and not BackupVerification.objects.filter(
                pk=instance.pk,
                is_valid=True
            ).exclude(pk=instance.pk).exists():
                # First time verification completed successfully
                logger.info(f"Backup verification '{instance.verification_id}' completed successfully")
                
                # Update backup verification status
                if instance.backup:
                    instance.backup.is_verified = True
                    instance.backup.verified_at = instance.verified_at
                    instance.backup.verified_by = instance.verified_by
                    instance.backup.save(update_fields=['is_verified', 'verified_at', 'verified_by'])
                
                # Log verification completion
                BackupLog.objects.create(
                    backup=instance.backup,
                    level='info',
                    message=f"Backup verification completed successfully",
                    category='validation',
                    action='complete',
                    details={
                        'verification_id': str(instance.verification_id),
                        'verification_method': instance.verification_method,
                        'is_valid': instance.is_valid
                    }
                )
                
                # Send backup verified signal
                backup_verified.send(sender=BackupVerification, verification=instance)
                
                # Send notification if backup has notification channels
                if instance.backup and instance.backup.notification_channels:
                    send_multi_channel_notification.delay(
                        backup_id=str(instance.backup.id),
                        message=f"Backup verification completed: {instance.backup.name}",
                        level='success',
                        channels=instance.backup.notification_channels
                    )
            
            elif not instance.is_valid and instance.error_message:
                # Verification failed
                logger.error(f"Backup verification '{instance.verification_id}' failed: {instance.error_message}")
                
                # Log verification failure
                BackupLog.objects.create(
                    backup=instance.backup,
                    level='error',
                    message=f"Backup verification failed",
                    category='validation',
                    action='fail',
                    details={
                        'verification_id': str(instance.verification_id),
                        'error': instance.error_message
                    }
                )
                
                # Create alert for failed verification
                BackupAlert.create_alert(
                    alert_type='verification_failed',
                    backup=instance.backup,
                    message=f"Verification failed: {instance.backup.name} - {instance.error_message}",
                    severity='medium'
                )
    
    except Exception as e:
        logger.error(f"Error in backup_verification_post_save: {str(e)}")


@receiver(post_save, sender=BackupAlert)
def backup_alert_post_save(sender, instance, created, **kwargs):
    """Handle backup alert post-save operations"""
    try:
        if created:
            logger.info(f"New backup alert created: {instance.alert_type}")
            
            # Send alert created signal
            alert_created.send(sender=BackupAlert, alert=instance)
            
            # Log alert creation
            BackupLog.objects.create(
                backup=instance.backup,
                level='warning' if instance.severity in ['low', 'medium'] else 'error',
                message=f"Alert created: {instance.alert_type}",
                category='system',
                action='create',
                details={
                    'alert_id': str(instance.id),
                    'alert_type': instance.alert_type,
                    'severity': instance.severity,
                    'message': instance.message
                }
            )
            
            # Send notification for critical alerts
            if instance.severity == 'critical':
                send_multi_channel_notification.delay(
                    backup_id=str(instance.backup.backup_id) if instance.backup else None,
                    message=f"CRITICAL ALERT: {instance.message}",
                    level='critical',
                    channels=['email', 'sms']  # Always use critical channels
                )
        else:
            # Check if alert was resolved
            old_instance = BackupAlert.objects.get(pk=instance.pk) if instance.pk else None
            if old_instance and not old_instance.is_resolved and instance.is_resolved:
                # Alert was resolved
                logger.info(f"Backup alert resolved: {instance.alert_type}")
                
                # Send alert resolved signal
                alert_resolved.send(sender=BackupAlert, alert=instance)
                
                # Log resolution
                BackupLog.objects.create(
                    backup=instance.backup,
                    level='info',
                    message=f"Alert resolved: {instance.alert_type}",
                    category='system',
                    action='update',
                    details={
                        'alert_id': str(instance.id),
                        'resolved_by': instance.resolved_by.username if instance.resolved_by else None,
                        'resolved_at': instance.resolved_at.isoformat() if instance.resolved_at else None
                    }
                )
    
    except Exception as e:
        logger.error(f"Error in backup_alert_post_save: {str(e)}")


@receiver(post_save, sender=BackupStorageLocation)
def backup_storage_location_post_save(sender, instance, created, **kwargs):
    """Handle backup storage location post-save operations"""
    try:
        if created:
            logger.info(f"New backup storage location created: {instance.name}")
            
            # Log storage location creation
            BackupLog.objects.create(
                level='info',
                message=f"Storage location '{instance.name}' created",
                category='storage',
                action='create',
                details={
                    'storage_id': str(instance.id),
                    'storage_type': instance.storage_type,
                    'is_active': instance.is_active
                }
            )
        else:
            # Check for connection status changes
            old_instance = BackupStorageLocation.objects.get(pk=instance.pk) if instance.pk else None
            if old_instance and old_instance.is_connected != instance.is_connected:
                
                if instance.is_connected:
                    # Storage connected
                    logger.info(f"Storage location '{instance.name}' connected")
                    
                    # Send storage connected signal
                    storage_connected.send(sender=BackupStorageLocation, location=instance)
                    
                    # Log connection
                    BackupLog.objects.create(
                        level='info',
                        message=f"Storage location '{instance.name}' connected",
                        category='storage',
                        action='update',
                        details={'storage_id': str(instance.id)}
                    )
                
                else:
                    # Storage disconnected
                    logger.warning(f"Storage location '{instance.name}' disconnected")
                    
                    # Send storage disconnected signal
                    storage_disconnected.send(sender=BackupStorageLocation, location=instance)
                    
                    # Log disconnection
                    BackupLog.objects.create(
                        level='warning',
                        message=f"Storage location '{instance.name}' disconnected",
                        category='storage',
                        action='update',
                        details={'storage_id': str(instance.id)}
                    )
                    
                    # Create alert for storage disconnection
                    BackupAlert.create_alert(
                        alert_type='storage_full',  # Reuse alert type for storage issues
                        backup=None,
                        message=f"Storage location '{instance.name}' disconnected",
                        severity='high'
                    )
            
            # Check for storage capacity issues
            if instance.space_used_percentage and instance.space_used_percentage > 90:
                # Storage is nearly full
                logger.warning(f"Storage location '{instance.name}' is {instance.space_used_percentage}% full")
                
                # Send storage full signal
                storage_full.send(sender=BackupStorageLocation, location=instance)
                
                # Create alert for storage full
                BackupAlert.create_alert(
                    alert_type='storage_full',
                    backup=None,
                    message=f"Storage location '{instance.name}' is {instance.space_used_percentage}% full",
                    severity='critical'
                )
    
    except Exception as e:
        logger.error(f"Error in backup_storage_location_post_save: {str(e)}")


# ==================== CUSTOM SIGNAL HANDLERS ====================

@receiver(backup_started)
def handle_backup_started(sender, backup, **kwargs):
    """Handle backup started signal"""
    try:
        logger.info(f"Handling backup started signal for: {backup.name}")
        
        # Update related schedule if this is a scheduled backup
        if backup.schedule:
            backup.schedule.last_run = timezone.now()
            backup.schedule.save(update_fields=['last_run'])
            
            # Calculate next run time
            if hasattr(backup.schedule, 'calculate_next_run'):
                backup.schedule.next_run = backup.schedule.calculate_next_run()
                backup.schedule.save(update_fields=['next_run'])
            
            # Send schedule triggered signal
            schedule_triggered.send(sender=BackupSchedule, schedule=backup.schedule)
    
    except Exception as e:
        logger.error(f"Error handling backup started signal: {str(e)}")


@receiver(backup_completed)
def handle_backup_completed(sender, backup, **kwargs):
    """Handle backup completed signal"""
    try:
        logger.info(f"Handling backup completed signal for: {backup.name}")
        
        # Update backup health score
        if backup.status == 'completed':
            backup.health_score = min(100, backup.health_score + 10)
            backup.is_healthy = True
            backup.last_health_check = timezone.now()
            backup.save(update_fields=['health_score', 'is_healthy', 'last_health_check'])
        
        # Send health check completed signal
        health_check_completed.send(sender=Backup, backup=backup, status='healthy')
        
        # Check if cleanup is needed
        if backup.retention_days and backup.retention_days > 0:
            auto_cleanup_expired_backups.delay()
    
    except Exception as e:
        logger.error(f"Error handling backup completed signal: {str(e)}")


@receiver(backup_failed)
def handle_backup_failed(sender, backup, **kwargs):
    """Handle backup failed signal"""
    try:
        logger.error(f"Handling backup failed signal for: {backup.name}")
        
        # Update backup health score
        backup.health_score = max(0, backup.health_score - 30)
        backup.is_healthy = False
        backup.last_health_check = timezone.now()
        backup.save(update_fields=['health_score', 'is_healthy', 'last_health_check'])
        
        # Send health check completed signal
        health_check_completed.send(sender=Backup, backup=backup, status='unhealthy')
        
        # Check if schedule needs to be paused due to repeated failures
        if backup.schedule:
            recent_failures = Backup.objects.filter(
                schedule=backup.schedule,
                status='failed',
                start_time__gte=timezone.now() - timezone.timedelta(days=1)
            ).count()
            
            if recent_failures >= 3:  # 3 failures in 24 hours
                backup.schedule.is_active = False
                backup.schedule.is_paused = True
                backup.schedule.save(update_fields=['is_active', 'is_paused'])
                
                # Send schedule failed signal
                schedule_failed.send(sender=BackupSchedule, schedule=backup.schedule)
                
                logger.warning(f"Schedule '{backup.schedule.name}' paused due to repeated failures")
    
    except Exception as e:
        logger.error(f"Error handling backup failed signal: {str(e)}")


@receiver(retention_policy_executed)
def handle_retention_policy_executed(sender, policy, **kwargs):
    """Handle retention policy executed signal"""
    try:
        logger.info(f"Handling retention policy executed signal for: {policy.name}")
        
        # Log policy execution
        BackupLog.objects.create(
            level='info',
            message=f"Retention policy '{policy.name}' executed",
            category='cleanup',
            action='execute',
            details={'policy_id': str(policy.id)}
        )
    
    except Exception as e:
        logger.error(f"Error handling retention policy executed signal: {str(e)}")


@receiver(alert_escalated)
def handle_alert_escalated(sender, alert, **kwargs):
    """Handle alert escalated signal"""
    try:
        logger.warning(f"Handling alert escalated signal for: {alert.alert_type}")
        
        # Send escalation notification
        send_multi_channel_notification.delay(
            backup_id=str(alert.backup.backup_id) if alert.backup else None,
            message=f"ESCALATED ALERT: {alert.message}",
            level='critical',
            channels=['email', 'sms', 'slack']  # Use all available channels
        )
    
    except Exception as e:
        logger.error(f"Error handling alert escalated signal: {str(e)}")


# ==================== UTILITY FUNCTIONS ====================

def trigger_backup_health_check():
    """Trigger health check for all backups"""
    try:
        backups = Backup.objects.filter(status='completed')
        for backup in backups:
            verify_backup_health_periodically.delay(
                backup_id=str(backup.id),
                verification_method='hash'
            )
        
        logger.info(f"Triggered health check for {backups.count()} backups")
    
    except Exception as e:
        logger.error(f"Error triggering backup health check: {str(e)}")


def trigger_retention_cleanup():
    """Trigger retention cleanup for all policies"""
    try:
        policies = RetentionPolicy.objects.filter(is_active=True)
        for policy in policies:
            execute_gfs_retention_policy.delay(policy_id=str(policy.id))
        
        logger.info(f"Triggered retention cleanup for {policies.count()} policies")
    
    except Exception as e:
        logger.error(f"Error triggering retention cleanup: {str(e)}")


def check_storage_capacity():
    """Check storage capacity for all locations"""
    try:
        locations = BackupStorageLocation.objects.filter(is_active=True)
        for location in locations:
            if location.space_used_percentage and location.space_used_percentage > 80:
                if location.space_used_percentage > 90:
                    storage_full.send(sender=BackupStorageLocation, location=location)
                else:
                    storage_error.send(sender=BackupStorageLocation, location=location)
        
        logger.info(f"Checked storage capacity for {locations.count()} locations")
    
    except Exception as e:
        logger.error(f"Error checking storage capacity: {str(e)}")


# ==================== SCHEDULED TASKS ====================

def setup_periodic_tasks():
    """Setup periodic tasks for backup operations"""
    try:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule
        
        # Daily health check at 2 AM
        daily_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*'
        )
        
        PeriodicTask.objects.get_or_create(
            name='daily_backup_health_check',
            defaults={
                'crontab': daily_schedule,
                'task': 'api.backup.signals.trigger_backup_health_check',
                'enabled': True
            }
        )
        
        # Weekly retention cleanup on Sunday at 3 AM
        weekly_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='3',
            day_of_week='0',  # Sunday
            day_of_month='*',
            month_of_year='*'
        )
        
        PeriodicTask.objects.get_or_create(
            name='weekly_retention_cleanup',
            defaults={
                'crontab': weekly_schedule,
                'task': 'api.backup.signals.trigger_retention_cleanup',
                'enabled': True
            }
        )
        
        # Hourly storage capacity check
        hourly_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='*',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*'
        )
        
        PeriodicTask.objects.get_or_create(
            name='hourly_storage_capacity_check',
            defaults={
                'crontab': hourly_schedule,
                'task': 'api.backup.signals.check_storage_capacity',
                'enabled': True
            }
        )
        
        logger.info("Periodic backup tasks setup completed")
    
    except Exception as e:
        logger.error(f"Error setting up periodic tasks: {str(e)}")


# Auto-setup periodic tasks when this module is imported
try:
    setup_periodic_tasks()
except Exception as e:
    logger.error(f"Error auto-setting up periodic tasks: {str(e)}")
