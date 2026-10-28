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
        valid_severities = [c[0] for c in AlertRule._meta.get_field('severity').choices]
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for AlertRule {instance.id}")
        
        # Set default cooldown if not provided
        if instance.cooldown_minutes is None:
            instance.cooldown_minutes = 30

        # Stash prior is_active so post_save can detect a real enable/disable transition
        if instance.pk:
            try:
                instance._prev_is_active = AlertRule.objects.filter(pk=instance.pk).values_list('is_active', flat=True).first()
            except Exception:
                instance._prev_is_active = None
        else:
            instance._prev_is_active = None
            
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
                action='created',
                old_data={},
                new_data={
                    'name': instance.name,
                    'alert_type': instance.alert_type,
                    'severity': instance.severity,
                    'threshold_value': instance.threshold_value,
                    'is_active': instance.is_active
                },
                changed_fields=['all']
            )
        else:
            logger.debug(f"Updated AlertRule: {instance.name} (ID: {instance.id})")
            prev = getattr(instance, '_prev_is_active', None)
            if prev is not None and prev != instance.is_active:
                from api.alerts.signals.core import alert_rule_enabled, alert_rule_disabled
                (alert_rule_enabled if instance.is_active else alert_rule_disabled).send(
                    sender=sender, instance=instance)

        # Always clear the active-rules cache on any save
        try:
            from django.core.cache import cache
            cache.delete('active_alert_rules')
            cache.delete(f'alert_rule_{instance.pk}')
        except Exception:
            pass

        # Audit log the save event
        try:
            from api.alerts.integration import get_audit_logger
            from api.alerts.integration.integ_audit_logs import AuditEventType, AuditSeverity
            al = get_audit_logger()
            if al:
                al.log_event(
                    event_type=AuditEventType.RULE_CREATED if created else AuditEventType.RULE_UPDATED,
                    severity=AuditSeverity.INFO,
                    description=f"AlertRule {'created' if created else 'updated'}: {instance.name}",
                    details={'rule_id': instance.pk, 'is_active': instance.is_active}
                )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error in alert_rule_post_save: {e}")


@receiver(post_delete, sender=AlertRule)
def alert_rule_post_delete(sender, instance, **kwargs):
    """Signal handler after deleting AlertRule"""
    try:
        logger.info(f"Deleted AlertRule: {instance.name} (ID: {instance.id})")
        
        # Clean up related objects
        AlertRuleHistory.objects.filter(rule=instance).delete()
        from api.alerts.signals.core import alert_rule_deleted
        alert_rule_deleted.send(sender=sender, instance=instance)
        
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
                from api.alerts.tasks.notification import send_pending_notifications
                try:
                    send_pending_notifications.delay()
                except Exception:
                    pass

            # Auto-create incident for critical/high severity alerts
            try:
                from api.alerts.tasks.incident import create_incident_from_alert
                if hasattr(instance.rule, 'severity') and instance.rule.severity in ('critical', 'high'):
                    try:
                        create_incident_from_alert.delay(instance.pk)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(f"Could not trigger create_incident_from_alert for log {instance.pk}: {exc}")

            # Audit log alert creation
            try:
                from api.alerts.integration import get_audit_logger
                from api.alerts.integration.integ_audit_logs import AuditEventType, AuditSeverity
                al = get_audit_logger()
                if al:
                    al.log_event(
                        event_type=AuditEventType.ALERT_CREATED,
                        severity=AuditSeverity.WARNING if instance.rule.severity in ('critical','high') else AuditSeverity.INFO,
                        description=f"Alert fired: {instance.rule.name}",
                        details={'alert_log_id': instance.pk, 'rule_id': instance.rule_id, 'severity': getattr(instance.rule, 'severity', 'unknown')}
                    )
            except Exception:
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
            try:
                send_pending_notifications.delay()
            except Exception:
                pass
            
        else:
            logger.debug(f"Updated Notification: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in notification_post_save: {e}")


@receiver(pre_save, sender=AlertEscalation)
def alert_escalation_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertEscalation"""
    try:
        # Set default values if not provided
        if not instance.delay_minutes:
            instance.delay_minutes = 60  # 1 hour default
            
    except Exception as e:
        logger.error(f"Error in alert_escalation_pre_save: {e}")


@receiver(post_save, sender=AlertEscalation)
def alert_escalation_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertEscalation"""
    try:
        if created:
            logger.info(f"Created new AlertEscalation: Level {instance.level} for rule {instance.rule.name}")
            from api.alerts.signals.core import escalation_created
            escalation_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated AlertEscalation: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_escalation_post_save: {e}")


@receiver(pre_save, sender=AlertTemplate)
def alert_template_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertTemplate"""
    try:
        # Set default values if not provided
        if not instance.is_default:
            instance.is_default = False
            
    except Exception as e:
        logger.error(f"Error in alert_template_pre_save: {e}")


@receiver(post_save, sender=AlertTemplate)
def alert_template_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertTemplate"""
    try:
        if created:
            logger.info(f"Created new AlertTemplate: {instance.name} ({instance.alert_type})")
            from api.alerts.signals.core import template_created
            template_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated AlertTemplate: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in alert_template_post_save: {e}")


@receiver(pre_save, sender=AlertGroup)
def alert_group_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertGroup"""
    try:
        # Set default values if not provided
        if not instance.group_threshold:
            instance.group_threshold = 3  # Default: 3 alerts before group notification
        
        if not instance.cooldown_minutes:
            instance.cooldown_minutes = 60  # 1 hour default
            
    except Exception as e:
        logger.error(f"Error in alert_group_pre_save: {e}")


@receiver(post_save, sender=AlertGroup)
def alert_group_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertGroup"""
    try:
        if created:
            logger.info(f"Created new AlertGroup: {instance.name}")
            from api.alerts.signals.core import group_created
            group_created.send(sender=sender, instance=instance)
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
            from api.alerts.signals.core import suppression_created
            suppression_created.send(sender=sender, instance=instance)
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
            from api.alerts.signals.core import health_check_created
            health_check_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated SystemHealthCheck: {instance.check_name}")
            
        # Trigger alert if health check failed
        if instance.status == 'critical':
            from ..tasks.core import check_system_health
            try:
                check_system_health.delay()
            except Exception:
                pass
            
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
            rule_name = instance.rule.name if instance.rule else '(no rule)'
            logger.info(f"Created AlertRuleHistory: {instance.action} for rule {rule_name}")
            from api.alerts.signals.core import rule_history_created
            rule_history_created.send(sender=sender, instance=instance)
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
            from api.alerts.signals.core import dashboard_config_created
            dashboard_config_created.send(sender=sender, instance=instance)
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
            from api.alerts.signals.core import metrics_created
            metrics_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated SystemMetrics: {instance.id}")
            
        # Check for threshold breaches
        if instance.cpu_usage_percent > 90 or instance.memory_usage_percent > 90:
            logger.warning(f"High system resource usage detected: CPU {instance.cpu_usage_percent}%, Memory {instance.memory_usage_percent}%")
            
    except Exception as e:
        logger.error(f"Error in system_metrics_post_save: {e}")


@receiver(post_save, sender=AlertAnalytics)
def alert_analytics_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertAnalytics"""
    try:
        if created:
            logger.info(f"Created AlertAnalytics for {instance.date}: {instance.total_alerts} total alerts")
            from api.alerts.signals.core import analytics_created
            analytics_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated AlertAnalytics for {instance.date}")
    except Exception as e:
        logger.error(f"Error in alert_analytics_post_save: {e}")


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
            try:
                escalate_alerts.delay()
            except Exception:
                pass
            
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


# ── Custom Signal objects (were missing — imported in __init__.py but undefined) ─
from django.dispatch import Signal

alert_rule_created       = Signal()
alert_rule_updated       = Signal()
alert_rule_deleted       = Signal()
alert_rule_enabled       = Signal()
alert_rule_disabled      = Signal()
alert_log_created        = Signal()
alert_log_updated        = Signal()
notification_created     = Signal()
notification_updated     = Signal()
escalation_created       = Signal()
template_created         = Signal()
analytics_created        = Signal()
group_created            = Signal()
suppression_created      = Signal()
health_check_created     = Signal()
rule_history_created     = Signal()
dashboard_config_created = Signal()
metrics_created          = Signal()


# ── Connect handlers to Django model signals so custom signals fire ────────────
from django.db.models.signals import post_save as _post_save

def _fire_rule_created(sender, instance, created, **kwargs):
    if created:
        alert_rule_created.send(sender=sender, instance=instance)
    else:
        alert_rule_updated.send(sender=sender, instance=instance)

def _fire_log_created(sender, instance, created, **kwargs):
    if created:
        alert_log_created.send(sender=sender, instance=instance)
    else:
        alert_log_updated.send(sender=sender, instance=instance)

def _fire_notification_created(sender, instance, created, **kwargs):
    if created:
        notification_created.send(sender=sender, instance=instance)
    else:
        notification_updated.send(sender=sender, instance=instance)

try:
    from ..models.core import AlertRule as _AR, AlertLog as _AL, Notification as _N
    _post_save.connect(_fire_rule_created, sender=_AR, weak=False)
    _post_save.connect(_fire_log_created,  sender=_AL, weak=False)
    _post_save.connect(_fire_notification_created, sender=_N, weak=False)
except Exception:
    pass
