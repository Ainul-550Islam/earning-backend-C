from django.dispatch import Signal
plan_quota_exceeded = Signal()

"""
Plan Signal Handlers

This module contains signal handlers for plan-related models including
Plan, PlanFeature, PlanUpgrade, PlanUsage, and PlanQuota.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.plan import Plan, PlanFeature, PlanUpgrade, PlanUsage, PlanQuota
from ..models.security import TenantAuditLog
from ..models.analytics import TenantNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Plan)
def plan_created(sender, instance, created, **kwargs):
    """
    Handle plan creation.
    
    Signal triggered when a new plan is created.
    """
    if created:
        logger.info(f"Plan created: {instance.name} (ID: {instance.id})")
        
        # Log plan creation
        TenantAuditLog.log_action(
            tenant=None,  # System-level action
            action='create',
            model_name='Plan',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Plan '{instance.name}' created",
            metadata={
                'plan_type': instance.plan_type,
                'price_monthly': float(instance.price_monthly),
                'price_yearly': float(instance.price_yearly),
                'max_users': instance.max_users,
                'is_active': instance.is_active,
            }
        )
        
        # Trigger signal
        from . import plan_created
        plan_created.send(sender=Plan, plan=instance)


@receiver(pre_save, sender=Plan)
def plan_pre_save(sender, instance, **kwargs):
    """
    Handle plan pre-save operations.
    
    Signal triggered before plan is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = Plan.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.is_active != instance.is_active:
                instance._status_changed = True
                instance._old_status = old_instance.is_active
                instance._new_status = instance.is_active
            
            # Track price changes
            if old_instance.price_monthly != instance.price_monthly:
                instance._price_changed = True
                instance._old_price = old_instance.price_monthly
                instance._new_price = instance.price_monthly
                
        except Plan.DoesNotExist:
            pass  # New plan, no changes to track


@receiver(post_save, sender=Plan)
def plan_updated(sender, instance, created, **kwargs):
    """
    Handle plan updates.
    
    Signal triggered when plan is updated.
    """
    if not created:
        logger.info(f"Plan updated: {instance.name} (ID: {instance.id})")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            status_text = 'activated' if instance._new_status else 'deactivated'
            
            # Log status change
            TenantAuditLog.log_action(
                tenant=None,
                action='config_change',
                model_name='Plan',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Plan '{instance.name}' {status_text}",
                changes={
                    'is_active': {'old': instance._old_status, 'new': instance._new_status}
                }
            )
        
        # Handle price changes
        if hasattr(instance, '_price_changed'):
            # Log price change
            TenantAuditLog.log_action(
                tenant=None,
                action='config_change',
                model_name='Plan',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Plan '{instance.name}' price changed from ${instance._old_price:.2f} to ${instance._new_price:.2f}",
                changes={
                    'price_monthly': {'old': float(instance._old_price), 'new': float(instance._new_price)}
                }
            )
        
        # Trigger signal
        from . import plan_updated
        plan_updated.send(sender=Plan, plan=instance)


@receiver(post_delete, sender=Plan)
def plan_deleted(sender, instance, **kwargs):
    """
    Handle plan deletion.
    
    Signal triggered when plan is deleted.
    """
    logger.info(f"Plan deleted: {instance.name} (ID: {instance.id})")
    
    # Log plan deletion
    TenantAuditLog.log_action(
        tenant=None,
        action='delete',
        model_name='Plan',
        object_id=str(instance.id),
        object_repr=str(instance),
        description=f"Plan '{instance.name}' deleted",
        metadata={
            'deleted_at': timezone.now().isoformat(),
            'plan_type': instance.plan_type,
        }
    )
    
    # Trigger signal
    from . import plan_deleted
    plan_deleted.send(sender=Plan, plan=instance)


@receiver(post_save, sender=PlanUsage)
def plan_usage_recorded(sender, instance, created, **kwargs):
    """
    Handle plan usage recording.
    
    Signal triggered when plan usage is recorded.
    """
    if created:
        logger.info(f"Plan usage recorded for {instance.tenant.name}: {instance.period}")
        
        # Check for quota violations
        quota_violations = []
        
        if instance.api_calls_limit > 0 and instance.api_calls_used > instance.api_calls_limit:
            quota_violations.append({
                'metric': 'api_calls',
                'used': instance.api_calls_used,
                'limit': instance.api_calls_limit,
                'percentage': instance.api_calls_percentage,
            })
        
        if instance.storage_limit_gb > 0 and instance.storage_used_gb > instance.storage_limit_gb:
            quota_violations.append({
                'metric': 'storage',
                'used': instance.storage_used_gb,
                'limit': instance.storage_limit_gb,
                'percentage': instance.storage_percentage,
            })
        
        if instance.users_limit > 0 and instance.users_used > instance.users_limit:
            quota_violations.append({
                'metric': 'users',
                'used': instance.users_used,
                'limit': instance.users_limit,
                'percentage': instance.users_percentage,
            })
        
        # Send quota exceeded notifications
        if quota_violations:
            violations_text = ', '.join([f"{v['metric']} ({v['percentage']:.1f}%)" for v in quota_violations])
            
            TenantNotification.objects.create(
                tenant=instance.tenant,
                title='Quota Limits Exceeded',
                message=f'You have exceeded your quota limits: {violations_text}. Consider upgrading your plan.',
                notification_type='quota',
                priority='high',
                send_email=True,
                send_push=True,
                action_url='/billing/plans',
                action_text='Upgrade Plan',
                metadata={
                    'quota_violations': quota_violations,
                    'usage_id': str(instance.id),
                },
            )
            
            # Trigger quota warning signal
            from . import quota_warning
            quota_warning.send(
                sender=PlanUsage,
                tenant=instance.tenant,
                violations=quota_violations,
                usage=instance,
            )
        
        # Trigger signal
        from . import plan_usage_recorded
        plan_usage_recorded.send(sender=PlanUsage, usage=instance, violations=quota_violations)


@receiver(post_save, sender=PlanUpgrade)
def plan_upgrade_created(sender, instance, created, **kwargs):
    """
    Handle plan upgrade creation.
    
    Signal triggered when a plan upgrade is created.
    """
    if created:
        logger.info(f"Plan upgrade created for {instance.tenant.name}: {instance.from_plan.name} -> {instance.to_plan.name}")
        
        # Log upgrade
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='PlanUpgrade',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Plan upgrade requested: {instance.from_plan.name} -> {instance.to_plan.name}",
            metadata={
                'from_plan_id': str(instance.from_plan.id),
                'to_plan_id': str(instance.to_plan.id),
                'reason': instance.reason,
                'price_difference': float(instance.price_difference),
            }
        )


@receiver(post_save, sender=PlanFeature)
def plan_feature_created(sender, instance, created, **kwargs):
    """
    Handle plan feature creation.
    
    Signal triggered when a plan feature is created.
    """
    if created:
        logger.info(f"Plan feature created: {instance.name} (Key: {instance.key})")
        
        # Log feature creation
        TenantAuditLog.log_action(
            tenant=None,
            action='create',
            model_name='PlanFeature',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Plan feature '{instance.name}' created",
            metadata={
                'key': instance.key,
                'feature_type': instance.feature_type,
                'is_active': instance.is_active,
            }
        )


@receiver(post_save, sender=PlanQuota)
def plan_quota_created(sender, instance, created, **kwargs):
    """
    Handle plan quota creation.
    
    Signal triggered when a plan quota is created.
    """
    if created:
        logger.info(f"Plan quota created for {instance.plan.name}: {instance.feature_key}")
        
        # Log quota creation
        TenantAuditLog.log_action(
            tenant=None,
            action='create',
            model_name='PlanQuota',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Plan quota for '{instance.feature_key}' created",
            metadata={
                'plan_id': str(instance.plan.id),
                'feature_key': instance.feature_key,
                'hard_limit': instance.hard_limit,
                'soft_limit': instance.soft_limit,
            }
        )


@receiver(pre_save, sender=PlanUsage)
def plan_usage_pre_save(sender, instance, **kwargs):
    """
    Handle plan usage pre-save operations.
    
    Signal triggered before plan usage is saved.
    """
    # Calculate percentages
    if instance.api_calls_limit > 0:
        instance.api_calls_percentage = (instance.api_calls_used / instance.api_calls_limit) * 100
    
    if instance.storage_limit_gb > 0:
        instance.storage_percentage = (instance.storage_used_gb / instance.storage_limit_gb) * 100
    
    if instance.users_limit > 0:
        instance.users_percentage = (instance.users_used / instance.users_limit) * 100


def check_quota_exceeded(tenant, metric, used, limit):
    """
    Check if quota is exceeded and trigger appropriate actions.
    
    Args:
        tenant: Tenant instance
        metric: Metric name
        used: Current usage
        limit: Usage limit
    """
    if limit > 0 and used > limit:
        # Trigger quota exceeded signal
        from . import plan_quota_exceeded
        plan_quota_exceeded.send(
            sender=None,
            tenant=tenant,
            metric=metric,
            used=used,
            limit=limit,
            percentage=(used / limit) * 100,
        )
        
        # Log quota exceeded
        TenantAuditLog.log_action(
            tenant=tenant,
            action='config_change',
            model_name='PlanUsage',
            description=f"Quota exceeded for {metric}: {used} > {limit}",
            metadata={
                'metric': metric,
                'used': used,
                'limit': limit,
                'percentage': (used / limit) * 100,
            },
            severity='medium',
        )
