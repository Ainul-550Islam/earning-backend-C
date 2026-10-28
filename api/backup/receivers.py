"""
Backup Module Signal Receivers
Signal handlers for backup-related events
"""

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

from .models import (
    Backup, BackupSchedule, BackupAlert, BackupLog,
    BackupVerification, BackupRestoration, BackupEncryption
)
from .tasks import (
    process_backup_completion, process_backup_failure,
    send_backup_notifications, cleanup_old_backups,
    verify_backup_integrity
)
from .services import BackupService
from .exceptions import BackupException

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Backup)
def backup_created_handler(sender, instance, created, **kwargs):
    """
    Handle backup creation
    """
    if created:
        logger.info(f"New backup created: {instance.id}")
        
        # Log the creation
        BackupLog.log_backup_start(
            action='create',
            backup_id=instance.id,
            details={
                'name': instance.name,
                'type': instance.backup_type,
                'storage_type': instance.storage_type,
                'created_by': instance.created_by.id if instance.created_by else None
            },
            user=instance.created_by
        )
        
        # If backup is scheduled to start immediately, trigger it
        if instance.status == 'pending' and instance.auto_start:
            from .tasks import execute_backup_task
            execute_backup_task.delay(str(instance.id))


@receiver(pre_save, sender=Backup)
def backup_status_change_handler(sender, instance, **kwargs):
    """
    Handle backup status changes
    """
    if instance.pk:
        try:
            old_instance = Backup.objects.get(pk=instance.pk)
            old_status = old_instance.status
            new_status = instance.status
            
            if old_status != new_status:
                logger.info(f"Backup {instance.id} status changed: {old_status} -> {new_status}")
                
                # Log status change
                BackupLog.log_backup_start(
                    action='status_change',
                    backup_id=instance.id,
                    details={
                        'old_status': old_status,
                        'new_status': new_status,
                        'changed_at': timezone.now().isoformat()
                    },
                    user=getattr(instance, 'updated_by', None)
                )
                
                # Handle specific status transitions
                if new_status == 'completed' and old_status in ['pending', 'running']:
                    # Backup completed successfully
                    _handle_backup_completion(instance)
                
                elif new_status == 'failed' and old_status in ['pending', 'running']:
                    # Backup failed
                    _handle_backup_failure(instance)
                
                elif new_status == 'running' and old_status == 'pending':
                    # Backup started
                    _handle_backup_start(instance)
                
                elif new_status == 'verifying':
                    # Backup verification started
                    _handle_backup_verification_start(instance)
                
        except Backup.DoesNotExist:
            pass  # New backup, no status change


@receiver(post_save, sender=BackupSchedule)
def backup_schedule_created_handler(sender, instance, created, **kwargs):
    """
    Handle backup schedule creation/update
    """
    if created:
        logger.info(f"New backup schedule created: {instance.id}")
        
        # Log the schedule creation
        BackupLog.log_backup_start(
            action='schedule_create',
            details={
                'name': instance.name,
                'frequency': instance.frequency,
                'backup_type': instance.backup_type,
                'next_run': instance.next_run.isoformat() if instance.next_run else None
            },
            user=instance.created_by
        )
    else:
        # Check if schedule was activated
        if getattr(instance, '_was_active', False) and instance.is_active:
            logger.info(f"Backup schedule activated: {instance.id}")
            
            # Log activation
            BackupLog.log_backup_start(
                action='schedule_activate',
                details={
                    'schedule_id': str(instance.id),
                    'next_run': instance.next_run.isoformat() if instance.next_run else None
                },
                user=getattr(instance, 'updated_by', None)
            )


@receiver(post_save, sender=BackupVerification)
def backup_verification_created_handler(sender, instance, created, **kwargs):
    """
    Handle backup verification creation
    """
    if created:
        logger.info(f"Backup verification created: {instance.id}")
        
        # Log verification start
        BackupLog.log_backup_start(
            action='verification_start',
            backup_id=instance.backup.id if instance.backup else None,
            details={
                'verification_id': str(instance.id),
                'method': instance.verification_method,
                'verified_by': instance.verified_by.id if instance.verified_by else None
            },
            user=instance.verified_by
        )
        
        # If verification is automated, trigger it
        if getattr(instance, '_auto_verify', False):
            verify_backup_integrity.delay(
                str(instance.backup.id),
                instance.verification_method
            )


@receiver(post_save, sender=BackupRestoration)
def backup_restoration_created_handler(sender, instance, created, **kwargs):
    """
    Handle backup restoration creation
    """
    if created:
        logger.info(f"Backup restoration created: {instance.id}")
        
        # Log restoration start
        BackupLog.log_restoration_start(
            action='restore_start',
            backup_id=instance.backup.id if instance.backup else None,
            details={
                'restoration_id': str(instance.id),
                'restoration_type': instance.restoration_type,
                'initiated_by': instance.initiated_by.id if instance.initiated_by else None
            },
            user=instance.initiated_by
        )
        
        # If restoration is automated, trigger it
        if getattr(instance, '_auto_restore', False):
            from .tasks import execute_restoration_task
            execute_restoration_task.delay(str(instance.id))


@receiver(post_save, sender=BackupAlert)
def backup_alert_created_handler(sender, instance, created, **kwargs):
    """
    Handle backup alert creation
    """
    if created:
        logger.info(f"Backup alert created: {instance.id} - {instance.alert_type}")
        
        # Log alert creation
        BackupLog.log_backup_start(
            action='alert_create',
            backup_id=instance.backup.id if instance.backup else None,
            details={
                'alert_id': str(instance.id),
                'alert_type': instance.alert_type,
                'severity': instance.severity,
                'message': instance.message
            }
        )
        
        # Send notification for critical alerts
        if instance.severity in ['high', 'critical']:
            send_backup_notifications.delay(
                alert_id=str(instance.id),
                notification_type='alert'
            )


@receiver(pre_delete, sender=Backup)
def backup_deletion_handler(sender, instance, **kwargs):
    """
    Handle backup deletion
    """
    logger.info(f"Backup being deleted: {instance.id}")
    
    # Log deletion
    BackupLog.log_backup_start(
        action='delete',
        backup_id=instance.id,
        details={
            'name': instance.name,
            'size': instance.file_size,
            'storage_type': instance.storage_type,
            'deleted_at': timezone.now().isoformat()
        }
    )
    
    # Create alert for backup deletion if it was important
    if instance.is_permanent or instance.health_score > 80:
        BackupAlert.create_alert(
            alert_type='security',
            backup=instance,
            message=f"Important backup '{instance.name}' was deleted",
            severity='high',
            metadata={
                'backup_id': str(instance.id),
                'backup_name': instance.name,
                'health_score': instance.health_score,
                'was_permanent': instance.is_permanent
            }
        )


@receiver(post_delete, sender=Backup)
def backup_deleted_handler(sender, instance, **kwargs):
    """
    Handle post-deletion cleanup
    """
    logger.info(f"Backup deleted: {instance.id}")
    
    # Schedule cleanup of related records
    from .tasks import cleanup_backup_related_records
    cleanup_backup_related_records.delay(str(instance.id))


@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """
    Handle user creation - set up default backup permissions
    """
    if created:
        # Check if user should have default backup permissions
        if getattr(settings, 'BACKUP_AUTO_ASSIGN_PERMISSIONS', False):
            from .permissions import assign_backup_permissions
            
            try:
                assign_backup_permissions(instance)
                logger.info(f"Assigned default backup permissions to user: {instance.id}")
            except Exception as e:
                logger.error(f"Failed to assign backup permissions to user {instance.id}: {e}")


def _handle_backup_completion(backup):
    """
    Handle successful backup completion
    """
    try:
        logger.info(f"Backup {backup.id} completed successfully")
        
        # Update completion timestamp
        backup.completed_at = timezone.now()
        backup.save(update_fields=['completed_at'])
        
        # Process completion asynchronously
        process_backup_completion.delay(str(backup.id))
        
        # Create completion log
        BackupLog.log_backup_complete(
            backup_id=backup.id,
            details={
                'duration': backup.duration,
                'file_size': backup.file_size,
                'compression_ratio': backup.compression_ratio,
                'health_score': backup.health_score
            }
        )
        
        # Check if verification is needed
        if getattr(settings, 'BACKUP_AUTO_VERIFY_ON_COMPLETION', False):
            verify_backup_integrity.delay(str(backup.id), 'hash')
        
        # Check for retention policy cleanup
        if backup.retention_policy_ref:
            cleanup_old_backups.delay(
                retention_policy_id=str(backup.retention_policy_ref.id)
            )
        
    except Exception as e:
        logger.error(f"Error handling backup completion for {backup.id}: {e}")


def _handle_backup_failure(backup):
    """
    Handle backup failure
    """
    try:
        logger.error(f"Backup {backup.id} failed: {backup.error_message}")
        
        # Process failure asynchronously
        process_backup_failure.delay(str(backup.id))
        
        # Create failure log
        BackupLog.log_backup_error(
            backup_id=backup.id,
            error_message=backup.error_message or "Unknown error",
            error_type=backup.error_type or "UNKNOWN",
            details={
                'duration': backup.duration,
                'progress': backup.progress,
                'failed_at': timezone.now().isoformat()
            }
        )
        
        # Create alert for backup failure
        BackupAlert.create_alert(
            alert_type='failed',
            backup=backup,
            message=f"Backup '{backup.name}' failed: {backup.error_message or 'Unknown error'}",
            severity='high' if backup.backup_type == 'full' else 'medium',
            metadata={
                'backup_id': str(backup.id),
                'backup_type': backup.backup_type,
                'error_type': backup.error_type,
                'progress': backup.progress
            }
        )
        
        # Retry logic if configured
        if getattr(backup, '_should_retry', False) and backup.retry_count < backup.max_retries:
            from .tasks import retry_backup_task
            retry_backup_task.delay(str(backup.id))
        
    except Exception as e:
        logger.error(f"Error handling backup failure for {backup.id}: {e}")


def _handle_backup_start(backup):
    """
    Handle backup start
    """
    try:
        logger.info(f"Backup {backup.id} started")
        
        # Update start timestamp
        backup.started_at = timezone.now()
        backup.save(update_fields=['started_at'])
        
        # Create start log
        BackupLog.log_backup_start(
            action='start',
            backup_id=backup.id,
            details={
                'started_at': backup.started_at.isoformat(),
                'estimated_size': backup.estimated_size
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling backup start for {backup.id}: {e}")


def _handle_backup_verification_start(backup):
    """
    Handle backup verification start
    """
    try:
        logger.info(f"Backup verification started for {backup.id}")
        
        # Create verification log
        BackupLog.log_backup_start(
            action='verification_start',
            backup_id=backup.id,
            details={
                'verification_started_at': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling backup verification start for {backup.id}: {e}")


# Custom signal handlers for backup events
def handle_backup_storage_event(backup, event_type, details=None):
    """
    Handle backup storage events
    """
    logger.info(f"Backup storage event: {backup.id} - {event_type}")
    
    BackupLog.log_backup_start(
        action='storage_event',
        backup_id=backup.id,
        details={
            'event_type': event_type,
            'details': details or {}
        }
    )
    
    # Create alerts for critical storage events
    if event_type in ['storage_full', 'storage_error', 'connection_lost']:
        BackupAlert.create_alert(
            alert_type='storage_full' if event_type == 'storage_full' else 'security',
            backup=backup,
            message=f"Storage issue for backup '{backup.name}': {event_type}",
            severity='critical' if event_type == 'storage_full' else 'high',
            metadata={
                'backup_id': str(backup.id),
                'event_type': event_type,
                'details': details or {}
            }
        )


def handle_backup_security_event(backup, event_type, details=None):
    """
    Handle backup security events
    """
    logger.warning(f"Backup security event: {backup.id} - {event_type}")
    
    BackupLog.log_security_event(
        backup_id=backup.id,
        details={
            'event_type': event_type,
            'details': details or {}
        }
    )
    
    # Always create alerts for security events
    BackupAlert.create_alert(
        alert_type='security',
        backup=backup,
        message=f"Security event for backup '{backup.name}': {event_type}",
        severity='critical',
        metadata={
            'backup_id': str(backup.id),
            'event_type': event_type,
            'details': details or {}
        }
    )


def handle_backup_performance_event(backup, event_type, metrics=None):
    """
    Handle backup performance events
    """
    logger.info(f"Backup performance event: {backup.id} - {event_type}")
    
    BackupLog.log_backup_start(
        action='performance_event',
        backup_id=backup.id,
        details={
            'event_type': event_type,
            'metrics': metrics or {}
        }
    )
    
    # Create alerts for performance issues
    if event_type in ['slow_backup', 'high_memory_usage', 'disk_space_low']:
        severity = 'medium'
        if event_type == 'disk_space_low':
            severity = 'high'
        
        BackupAlert.create_alert(
            alert_type='schedule_missed' if event_type == 'slow_backup' else 'security',
            backup=backup,
            message=f"Performance issue for backup '{backup.name}': {event_type}",
            severity=severity,
            metadata={
                'backup_id': str(backup.id),
                'event_type': event_type,
                'metrics': metrics or {}
            }
        )


# Email notification handlers
def send_backup_email_notification(recipient_list, subject, message, backup=None):
    """
    Send backup email notification
    """
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives
        
        # Render HTML template if available
        html_content = None
        if backup:
            html_content = render_to_string('backup/email/notification.html', {
                'backup': backup,
                'subject': subject,
                'message': message
            })
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=getattr(settings, 'BACKUP_EMAIL_FROM', settings.DEFAULT_FROM_EMAIL),
            to=recipient_list
        )
        
        if html_content:
            email.attach_alternative(html_content, "text/html")
        
        email.send()
        
        logger.info(f"Backup email notification sent to {len(recipient_list)} recipients")
        
    except Exception as e:
        logger.error(f"Failed to send backup email notification: {e}")


# Signal registration utilities
def register_backup_signals():
    """
    Register all backup-related signals
    """
    logger.info("Backup signals registered")
    
    # Add any additional signal registrations here
    from django.db.models.signals import m2m_changed
    
    @receiver(m2m_changed, sender=BackupSchedule.databases.through)
    def backup_schedule_databases_changed(sender, instance, action, pk_set, **kwargs):
        """
        Handle changes to backup schedule databases
        """
        if action in ['post_add', 'post_remove', 'post_clear']:
            logger.info(f"Backup schedule {instance.id} databases changed: {action}")
            
            BackupLog.log_backup_start(
                action='schedule_databases_changed',
                details={
                    'schedule_id': str(instance.id),
                    'action': action,
                    'database_count': len(pk_set) if pk_set else 0
                },
                user=getattr(instance, 'updated_by', None)
            )


# Initialize signals on module import
register_backup_signals()


# Export signal handlers
__all__ = [
    'backup_created_handler',
    'backup_status_change_handler',
    'backup_schedule_created_handler',
    'backup_verification_created_handler',
    'backup_restoration_created_handler',
    'backup_alert_created_handler',
    'backup_deletion_handler',
    'backup_deleted_handler',
    'user_created_handler',
    'handle_backup_storage_event',
    'handle_backup_security_event',
    'handle_backup_performance_event',
    'send_backup_email_notification',
    'register_backup_signals',
]
