"""
Core Alert Signals
"""
from django.db.models.signals import pre_save, post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.core import (
    AlertRule, AlertLog, Notification, AlertEscalation, AlertTemplate,
    AlertAnalytics, AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=AlertRule)
def alert_rule_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertRule"""
    try:
        # Auto-generate name if not provided
        if not instance.name:
            instance.name = f"Alert Rule for {instance.alert_type}"
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for AlertRule {instance.id}")
        
        # Set default cooldown if not provided
        if instance.cooldown_minutes is None:
            instance.cooldown_minutes = 30
            
    except Exception as e:
        logger.error(f"Error in alert_rule_pre_save: {e}")


@receiver(post_save, sender=AlertRule)
def alert_rule_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertRule"""
    try:
        if created:
            logger.info(f"Created new AlertRule: {instance.name} (ID: {instance.id})")
            
            # Create initial history record
            AlertRuleHistory.objects.create(
                rule=instance,
                change_type='created',
                old_values={},
                new_values={
                    'name': instance.name,
                    'alert_type': instance.alert_type,
                    'severity': instance.severity,
                    'threshold_value': instance.threshold_value,
                    'is_active': instance.is_active
                },
                change_reason="Initial creation"
            )
        else:
            logger.debug(f"Updated AlertRule: {instance.name} (ID: {instance.id})")
            
    except Exception as e:
        logger.error(f"Error in alert_rule_post_save: {e}")


@receiver(post_delete, sender=AlertRule)
def alert_rule_post_delete(sender, instance, **kwargs):
    """Signal handler after deleting AlertRule"""
    try:
        logger.info(f"Deleted AlertRule: {instance.name} (ID: {instance.id})")
        
        # Clean up related objects
        AlertRuleHistory.objects.filter(rule=instance).delete()
        
    except Exception as e:
        logger.error(f"Error in alert_rule_post_delete: {e}")


@receiver(pre_save, sender=AlertLog)
def alert_log_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertLog"""
    try:
        # Set default values if not provided
        if not instance.triggered_at:
            instance.triggered_at = timezone.now()
        
        if not instance.message:
            instance.message = f"Alert triggered: {instance.rule.name}"
        
        # Calculate processing time if not set
        if not instance.processing_time_ms and instance.triggered_at:
            instance.processing_time_ms = 0  # Will be updated after processing
            
    except Exception as e:
        logger.error(f"Error in alert_log_pre_save: {e}")


@receiver(post_save, sender=AlertLog)
def alert_log_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertLog"""
    try:
        if created:
            logger.info(f"Created new AlertLog: {instance.message[:50]}... (ID: {instance.id})")
            
            # Update rule trigger count
            instance.rule.trigger_count += 1
            instance.rule.last_triggered = instance.triggered_at
            instance.rule.save(update_fields=['trigger_count', 'last_triggered'])
            
            # Create notifications if rule is active
            if instance.rule.is_active:
                # This would trigger notification creation
                pass
                
        else:
            logger.debug(f"Updated AlertLog: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_log_post_save: {e}")


@receiver(pre_save, sender=Notification)
def notification_pre_save(sender, instance, **kwargs):
    """Signal handler before saving Notification"""
    try:
        # Set default values if not provided
        if not instance.created_at:
            instance.created_at = timezone.now()
        
        if not instance.status:
            instance.status = 'pending'
        
        # Set default retry count
        if instance.retry_count is None:
            instance.retry_count = 0
            
    except Exception as e:
        logger.error(f"Error in notification_pre_save: {e}")


@receiver(post_save, sender=Notification)
def notification_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving Notification"""
    try:
        if created:
            logger.info(f"Created new Notification: {instance.notification_type} to {instance.recipient[:20]}...")
            
            # Trigger notification sending task
            from ..tasks.notification import send_pending_notifications
            send_pending_notifications.delay()
            
        else:
            logger.debug(f"Updated Notification: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in notification_post_save: {e}")


@receiver(pre_save, sender=AlertEscalation)
def alert_escalation_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertEscalation"""
    try:
        # Set default values if not provided
        if not instance.escalation_delay_minutes:
            instance.escalation_delay_minutes = 60  # 1 hour default
        
        if not instance.escalate_after_failures:
            instance.escalate_after_failures = 3  # After 3 failed notifications
            
    except Exception as e:
        logger.error(f"Error in alert_escalation_pre_save: {e}")


@receiver(post_save, sender=AlertEscalation)
def alert_escalation_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertEscalation"""
    try:
        if created:
            logger.info(f"Created new AlertEscalation: Level {instance.level} for rule {instance.rule.name}")
        else:
            logger.debug(f"Updated AlertEscalation: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_escalation_post_save: {e}")


@receiver(pre_save, sender=AlertTemplate)
def alert_template_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertTemplate"""
    try:
        # Set default values if not provided
        if not instance.template_type:
            instance.template_type = 'email'
        
        if not instance.is_default:
            instance.is_default = False
            
    except Exception as e:
        logger.error(f"Error in alert_template_pre_save: {e}")


@receiver(post_save, sender=AlertTemplate)
def alert_template_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertTemplate"""
    try:
        if created:
            logger.info(f"Created new AlertTemplate: {instance.name} ({instance.template_type})")
        else:
            logger.debug(f"Updated AlertTemplate: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in alert_template_post_save: {e}")


@receiver(pre_save, sender=AlertGroup)
def alert_group_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertGroup"""
    try:
        # Set default values if not provided
        if not instance.notification_threshold:
            instance.notification_threshold = 5  # Default: 5 alerts before group notification
        
        if not instance.notification_cooldown_minutes:
            instance.notification_cooldown_minutes = 60  # 1 hour default
            
    except Exception as e:
        logger.error(f"Error in alert_group_pre_save: {e}")


@receiver(post_save, sender=AlertGroup)
def alert_group_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertGroup"""
    try:
        if created:
            logger.info(f"Created new AlertGroup: {instance.name}")
        else:
            logger.debug(f"Updated AlertGroup: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in alert_group_post_save: {e}")


@receiver(pre_save, sender=AlertSuppression)
def alert_suppression_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertSuppression"""
    try:
        # Validate suppression logic
        instance.clean()
        
    except Exception as e:
        logger.error(f"Error in alert_suppression_pre_save: {e}")


@receiver(post_save, sender=AlertSuppression)
def alert_suppression_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertSuppression"""
    try:
        if created:
            logger.info(f"Created new AlertSuppression: {instance.name} ({instance.suppression_type})")
        else:
            logger.debug(f"Updated AlertSuppression: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in alert_suppression_post_save: {e}")


@receiver(pre_save, sender=SystemHealthCheck)
def system_health_check_pre_save(sender, instance, **kwargs):
    """Signal handler before saving SystemHealthCheck"""
    try:
        # Set default values if not provided
        if not instance.check_name:
            instance.check_name = f"Health Check - {instance.check_type}"
        
        if not instance.check_type:
            instance.check_type = 'connectivity'
            
    except Exception as e:
        logger.error(f"Error in system_health_check_pre_save: {e}")


@receiver(post_save, sender=SystemHealthCheck)
def system_health_check_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving SystemHealthCheck"""
    try:
        if created:
            logger.info(f"Created new SystemHealthCheck: {instance.check_name}")
        else:
            logger.debug(f"Updated SystemHealthCheck: {instance.check_name}")
            
        # Trigger alert if health check failed
        if instance.status == 'critical':
            from ..tasks.core import check_system_health
            check_system_health.delay()
            
    except Exception as e:
        logger.error(f"Error in system_health_check_post_save: {e}")


@receiver(pre_save, sender=AlertRuleHistory)
def alert_rule_history_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertRuleHistory"""
    try:
        # Set default values if not provided
        if not instance.changed_at:
            instance.changed_at = timezone.now()
            
    except Exception as e:
        logger.error(f"Error in alert_rule_history_pre_save: {e}")


@receiver(post_save, sender=AlertRuleHistory)
def alert_rule_history_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertRuleHistory"""
    try:
        if created:
            logger.info(f"Created AlertRuleHistory: {instance.change_type} for rule {instance.rule.name}")
        else:
            logger.debug(f"Updated AlertRuleHistory: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_rule_history_post_save: {e}")


@receiver(pre_save, sender=AlertDashboardConfig)
def alert_dashboard_config_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertDashboardConfig"""
    try:
        # Set default values if not provided
        if not instance.dashboard_layout:
            instance.dashboard_layout = 'default'
            
    except Exception as e:
        logger.error(f"Error in alert_dashboard_config_pre_save: {e}")


@receiver(post_save, sender=AlertDashboardConfig)
def alert_dashboard_config_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertDashboardConfig"""
    try:
        if created:
            logger.info(f"Created AlertDashboardConfig for user {instance.user.username}")
        else:
            logger.debug(f"Updated AlertDashboardConfig for user {instance.user.username}")
            
    except Exception as e:
        logger.error(f"Error in alert_dashboard_config_post_save: {e}")


@receiver(pre_save, sender=SystemMetrics)
def system_metrics_pre_save(sender, instance, **kwargs):
    """Signal handler before saving SystemMetrics"""
    try:
        # Set default values if not provided
        if not instance.timestamp:
            instance.timestamp = timezone.now()
        
        if not instance.data_source:
            instance.data_source = 'system'
            
    except Exception as e:
        logger.error(f"Error in system_metrics_pre_save: {e}")


@receiver(post_save, sender=SystemMetrics)
def system_metrics_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving SystemMetrics"""
    try:
        if created:
            logger.info(f"Created SystemMetrics: CPU {instance.cpu_usage_percent}%, Memory {instance.memory_usage_percent}%")
        else:
            logger.debug(f"Updated SystemMetrics: {instance.id}")
            
        # Check for threshold breaches
        if instance.cpu_usage_percent > 90 or instance.memory_usage_percent > 90:
            logger.warning(f"High system resource usage detected: CPU {instance.cpu_usage_percent}%, Memory {instance.memory_usage_percent}%")
            
    except Exception as e:
        logger.error(f"Error in system_metrics_post_save: {e}")


# Custom signal handlers for business logic
def trigger_alert_creation(alert_rule, trigger_value, message=None, details=None):
    """Custom function to trigger alert creation"""
    try:
        from ..models.core import AlertLog
        
        alert = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=trigger_value,
            threshold_value=alert_rule.threshold_value,
            message=message or f"Alert triggered: {alert_rule.name}",
            details=details or {}
        )
        
        logger.info(f"Triggered alert creation: {alert.id}")
        return alert
        
    except Exception as e:
        logger.error(f"Error in trigger_alert_creation: {e}")
        return None


def trigger_notification_creation(alert_log, notification_types=None):
    """Custom function to trigger notification creation"""
    try:
        from ..models.core import Notification
        
        if not notification_types:
            notification_types = []
            if alert_log.rule.send_email:
                notification_types.append('email')
            if alert_log.rule.send_telegram:
                notification_types.append('telegram')
            if alert_log.rule.send_sms:
                notification_types.append('sms')
            if alert_log.rule.send_webhook:
                notification_types.append('webhook')
        
        notifications = []
        for notification_type in notification_types:
            notification = Notification.objects.create(
                alert_log=alert_log,
                notification_type=notification_type,
                recipient="default",  # Will be updated based on routing
                subject=f"Alert: {alert_log.rule.name}",
                message=alert_log.message,
                status='pending'
            )
            notifications.append(notification)
        
        logger.info(f"Created {len(notifications)} notifications for alert {alert_log.id}")
        return notifications
        
    except Exception as e:
        logger.error(f"Error in trigger_notification_creation: {e}")
        return []


def trigger_escalation_check(alert_log):
    """Custom function to trigger escalation check"""
    try:
        # Check if alert needs escalation
        if alert_log.escalation_level > 0:
            logger.info(f"Alert {alert_log.id} requires escalation level {alert_log.escalation_level}")
            
            # Trigger escalation task
            from ..tasks.core import escalate_alerts
            escalate_alerts.delay()
            
    except Exception as e:
        logger.error(f"Error in trigger_escalation_check: {e}")


def trigger_group_notification(alert_group):
    """Custom function to trigger group notification"""
    try:
        logger.info(f"Triggering group notification for {alert_group.name}")
        
        # Trigger group alert task
        from ..tasks.core import send_group_alerts
        send_group_alerts.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_group_notification: {e}")


# Signal registration
def register_core_signals():
    """Register all core signals"""
    try:
        logger.info("Core signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering core signals: {e}")


# Auto-register signals when module is imported
register_core_signals()
