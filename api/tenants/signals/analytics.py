"""
Analytics Signal Handlers

This module contains signal handlers for analytics-related models including
TenantMetric, TenantHealthScore, TenantFeatureFlag, and TenantNotification.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.analytics import TenantMetric, TenantHealthScore, TenantFeatureFlag, TenantNotification
from ..models.security import TenantAuditLog

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantMetric)
def metric_recorded(sender, instance, created, **kwargs):
    """
    Handle metric recording.
    
    Signal triggered when a metric is recorded.
    """
    if created:
        logger.info(f"Metric recorded for {instance.tenant.name}: {instance.metric_type} = {instance.value}")
        
        # Log metric recording
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantMetric',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Metric '{instance.metric_type}' recorded: {instance.value} {instance.unit}",
            metadata={
                'metric_type': instance.metric_type,
                'value': instance.value,
                'unit': instance.unit,
                'date': instance.date.isoformat(),
                'change_percentage': instance.change_percentage,
            },
        )
        
        # Trigger signal
        from . import metric_recorded
        metric_recorded.send(sender=TenantMetric, metric=instance)


@receiver(post_save, sender=TenantHealthScore)
def health_score_updated(sender, instance, created, **kwargs):
    """
    Handle health score updates.
    
    Signal triggered when health score is updated.
    """
    if not created:
        logger.info(f"Health score updated for {instance.tenant.name}: {instance.overall_score} ({instance.health_grade})")
        
        # Log health score update
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantHealthScore',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Health score updated: {instance.overall_score} ({instance.health_grade})",
            metadata={
                'overall_score': instance.overall_score,
                'health_grade': instance.health_grade,
                'risk_level': instance.risk_level,
                'churn_probability': instance.churn_probability,
                'engagement_score': instance.engagement_score,
                'usage_score': instance.usage_score,
                'payment_score': instance.payment_score,
                'support_score': instance.support_score,
            },
        )
        
        # Check for concerning health scores
        if instance.health_grade in ['D', 'F']:
            # Send alert to administrators
            from ..models.analytics import TenantNotification
            
            TenantNotification.objects.create(
                tenant=instance.tenant,
                title='Tenant Health Alert',
                message=f'Tenant health score is {instance.health_grade} ({instance.overall_score}). Risk level: {instance.risk_level}.',
                notification_type='system',
                priority='high' if instance.health_grade == 'F' else 'medium',
                send_email=True,
                send_push=False,
                action_url='/analytics/health',
                action_text='View Health Details',
                metadata={
                    'health_score_id': str(instance.id),
                    'health_grade': instance.health_grade,
                    'risk_level': instance.risk_level,
                },
            )
        
        # Trigger signal
        from . import health_score_updated
        health_score_updated.send(sender=TenantHealthScore, health_score=instance)


@receiver(pre_save, sender=TenantHealthScore)
def health_score_pre_save(sender, instance, **kwargs):
    """
    Handle health score pre-save operations.
    
    Signal triggered before health score is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantHealthScore.objects.get(pk=instance.pk)
            
            # Track grade changes
            if old_instance.health_grade != instance.health_grade:
                instance._grade_changed = True
                instance._old_grade = old_instance.health_grade
                instance._new_grade = instance.health_grade
            
            # Track risk level changes
            if old_instance.risk_level != instance.risk_level:
                instance._risk_changed = True
                instance._old_risk = old_instance.risk_level
                instance._new_risk = instance.risk_level
                
        except TenantHealthScore.DoesNotExist:
            pass  # New health score, no changes to track


@receiver(post_save, sender=TenantFeatureFlag)
def feature_flag_toggled(sender, instance, created, **kwargs):
    """
    Handle feature flag toggling.
    
    Signal triggered when feature flag is created or updated.
    """
    if not created:
        logger.info(f"Feature flag updated for {instance.tenant.name}: {instance.flag_key} = {instance.is_enabled}")
        
        # Log feature flag change
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantFeatureFlag',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Feature flag '{instance.flag_key}' {'enabled' if instance.is_enabled else 'disabled'}",
            metadata={
                'flag_key': instance.flag_key,
                'flag_type': instance.flag_type,
                'is_enabled': instance.is_enabled,
                'rollout_pct': instance.rollout_pct,
                'variant': instance.variant,
            },
        )
        
        # Trigger signal
        from . import feature_flag_toggled
        feature_flag_toggled.send(sender=TenantFeatureFlag, feature_flag=instance)


@receiver(pre_save, sender=TenantFeatureFlag)
def feature_flag_pre_save(sender, instance, **kwargs):
    """
    Handle feature flag pre-save operations.
    
    Signal triggered before feature flag is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantFeatureFlag.objects.get(pk=instance.pk)
            
            # Track enabled status changes
            if old_instance.is_enabled != instance.is_enabled:
                instance._enabled_changed = True
                instance._old_enabled = old_instance.is_enabled
                instance._new_enabled = instance.is_enabled
            
            # Track rollout percentage changes
            if old_instance.rollout_pct != instance.rollout_pct:
                instance._rollout_changed = True
                instance._old_rollout = old_instance.rollout_pct
                instance._new_rollout = instance.rollout_pct
                
        except TenantFeatureFlag.DoesNotExist:
            pass  # New feature flag, no changes to track


@receiver(post_save, sender=TenantNotification)
def notification_created(sender, instance, created, **kwargs):
    """
    Handle notification creation.
    
    Signal triggered when notification is created.
    """
    if created:
        logger.info(f"Notification created for {instance.tenant.name}: {instance.title}")
        
        # Log notification creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantNotification',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Notification '{instance.title}' created",
            metadata={
                'notification_type': instance.notification_type,
                'priority': instance.priority,
                'send_email': instance.send_email,
                'send_push': instance.send_push,
                'send_sms': instance.send_sms,
            },
        )
        
        # Trigger signal
        from . import notification_created
        notification_created.send(sender=TenantNotification, notification=instance)


@receiver(pre_save, sender=TenantNotification)
def notification_pre_save(sender, instance, **kwargs):
    """
    Handle notification pre-save operations.
    
    Signal triggered before notification is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantNotification.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
                
        except TenantNotification.DoesNotExist:
            pass  # New notification, no changes to track


@receiver(post_save, sender=TenantNotification)
def notification_updated(sender, instance, created, **kwargs):
    """
    Handle notification updates.
    
    Signal triggered when notification is updated.
    """
    if not created:
        # Handle status changes
        if hasattr(instance, '_status_changed') and instance._new_status == 'sent':
            logger.info(f"Notification sent to {instance.tenant.name}: {instance.title}")
            
            # Log notification sent
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantNotification',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Notification '{instance.title}' sent",
                changes={
                    'status': {'old': instance._old_status, 'new': instance._new_status}
                },
            )


def record_metric(tenant, metric_type, value, unit=None, metadata=None):
    """
    Record a metric for a tenant.
    
    Args:
        tenant: Tenant instance
        metric_type: Type of metric
        value: Metric value
        unit: Unit of measurement
        metadata: Additional metadata
    """
    try:
        metric = TenantMetric.objects.create(
            tenant=tenant,
            metric_type=metric_type,
            value=value,
            unit=unit or '',
            metadata=metadata or {},
            date=timezone.now().date(),
        )
        
        # Calculate change percentage
        try:
            previous_metric = TenantMetric.objects.filter(
                tenant=tenant,
                metric_type=metric_type,
                date=timezone.now().date() - timezone.timedelta(days=1)
            ).first()
            
            if previous_metric:
                metric.previous_value = previous_metric.value
                metric.calculate_change_percentage()
                metric.save()
        except:
            pass
        
        return metric
        
    except Exception as e:
        logger.error(f"Failed to record metric for {tenant.name}: {str(e)}")
        return None


def update_health_score(tenant):
    """
    Update health score for a tenant.
    
    Args:
        tenant: Tenant instance
    """
    try:
        health_score, created = TenantHealthScore.objects.get_or_create(
            tenant=tenant,
            defaults={
                'last_activity_at': tenant.last_activity_at or timezone.now(),
            }
        )
        
        # Calculate scores
        engagement_score = 0
        if tenant.last_activity_at:
            days_inactive = (timezone.now() - tenant.last_activity_at).days
            if days_inactive == 0:
                engagement_score = 100
            elif days_inactive <= 7:
                engagement_score = 80
            elif days_inactive <= 30:
                engagement_score = 60
            elif days_inactive <= 90:
                engagement_score = 40
            else:
                engagement_score = 20
        
        # Calculate usage score
        usage_score = 50  # Base score
        try:
            from ..models.plan import PlanUsage
            usage = PlanUsage.objects.filter(
                tenant=tenant,
                period='monthly'
            ).first()
            
            if usage and hasattr(usage, 'api_calls_percentage'):
                usage_score = min(100, usage.api_calls_percentage * 2)
        except:
            pass
        
        # Calculate payment score
        payment_score = 100  # Default to good
        try:
            from ..models import TenantInvoice
            overdue_invoices = TenantInvoice.objects.filter(
                tenant=tenant,
                status='overdue'
            ).count()
            
            if overdue_invoices > 0:
                payment_score = max(0, 100 - (overdue_invoices * 20))
        except:
            pass
        
        # Calculate support score
        support_score = 80  # Default to good
        
        # Calculate overall score
        overall_score = (engagement_score + usage_score + payment_score + support_score) / 4
        
        # Determine health grade
        if overall_score >= 90:
            health_grade = 'A'
            risk_level = 'low'
        elif overall_score >= 80:
            health_grade = 'B'
            risk_level = 'low'
        elif overall_score >= 70:
            health_grade = 'C'
            risk_level = 'medium'
        elif overall_score >= 60:
            health_grade = 'D'
            risk_level = 'high'
        else:
            health_grade = 'F'
            risk_level = 'critical'
        
        # Update health score
        health_score.engagement_score = engagement_score
        health_score.usage_score = usage_score
        health_score.payment_score = payment_score
        health_score.support_score = support_score
        health_score.overall_score = overall_score
        health_score.health_grade = health_grade
        health_score.risk_level = risk_level
        health_score.churn_probability = max(0, 100 - overall_score)
        health_score.last_activity_at = tenant.last_activity_at or timezone.now()
        health_score.days_inactive = (timezone.now() - (tenant.last_activity_at or timezone.now())).days
        health_score.save()
        
        return health_score
        
    except Exception as e:
        logger.error(f"Failed to update health score for {tenant.name}: {str(e)}")
        return None


def trigger_feature_flag_evaluation(tenant, flag_key, user=None, context=None):
    """
    Trigger feature flag evaluation and logging.
    
    Args:
        tenant: Tenant instance
        flag_key: Feature flag key
        user: User instance
        context: Evaluation context
    """
    try:
        from ..models.analytics import TenantFeatureFlag
        
        feature_flag = TenantFeatureFlag.objects.filter(
            tenant=tenant,
            flag_key=flag_key
        ).first()
        
        if feature_flag and feature_flag.is_active():
            # Evaluate flag
            is_enabled = feature_flag.is_enabled_for_user(user)
            variant = feature_flag.get_variant_for_user(user)
            
            # Log evaluation
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                model_name='TenantFeatureFlag',
                object_id=str(feature_flag.id),
                description=f"Feature flag '{flag_key}' evaluated: enabled={is_enabled}, variant={variant}",
                metadata={
                    'flag_key': flag_key,
                    'is_enabled': is_enabled,
                    'variant': variant,
                    'user_id': str(user.id) if user else None,
                    'context': context or {},
                },
            )
            
            return {
                'enabled': is_enabled,
                'variant': variant,
                'flag': feature_flag,
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to evaluate feature flag {flag_key} for {tenant.name}: {str(e)}")
        return None
