"""
Onboarding Signal Handlers

This module contains signal handlers for onboarding-related models including
TenantOnboarding, TenantOnboardingStep, and TenantTrialExtension.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension
from ..models.security import TenantAuditLog
from ..models.analytics import TenantNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantOnboarding)
def onboarding_started(sender, instance, created, **kwargs):
    """
    Handle onboarding start.
    
    Signal triggered when onboarding is created or started.
    """
    if created:
        logger.info(f"Onboarding started for {instance.tenant.name}")
        
        # Log onboarding start
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='create',
            model_name='TenantOnboarding',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Onboarding process started for tenant",
            metadata={
                'onboarding_id': str(instance.id),
                'skip_welcome': instance.skip_welcome,
                'enable_tips': instance.enable_tips,
            },
        )
        
        # Trigger signal
        from . import onboarding_started
        onboarding_started.send(sender=TenantOnboarding, onboarding=instance)


@receiver(pre_save, sender=TenantOnboarding)
def onboarding_pre_save(sender, instance, **kwargs):
    """
    Handle onboarding pre-save operations.
    
    Signal triggered before onboarding is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantOnboarding.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
            
            # Track completion percentage changes
            if old_instance.completion_pct != instance.completion_pct:
                instance._completion_changed = True
                instance._old_completion = old_instance.completion_pct
                instance._new_completion = instance.completion_pct
                
        except TenantOnboarding.DoesNotExist:
            pass  # New onboarding, no changes to track


@receiver(post_save, sender=TenantOnboarding)
def onboarding_updated(sender, instance, created, **kwargs):
    """
    Handle onboarding updates.
    
    Signal triggered when onboarding is updated.
    """
    if not created:
        logger.info(f"Onboarding updated for {instance.tenant.name}: {instance.status}")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            if instance._new_status == 'completed':
                # Log completion
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantOnboarding',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Onboarding process completed ({instance.completion_pct}%)",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status},
                        'completion_pct': instance._new_completion,
                    },
                )
                
                # Trigger signal
                from . import onboarding_completed
                onboarding_completed.send(sender=TenantOnboarding, onboarding=instance)
                
                # Send completion notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='Setup Complete!',
                    message=f'Congratulations! You\'ve completed {instance.completion_pct}% of your setup.',
                    notification_type='onboarding',
                    priority='medium',
                    send_email=True,
                    send_push=True,
                    action_url='/dashboard',
                    action_text='Go to Dashboard',
                    metadata={
                        'onboarding_id': str(instance.id),
                        'completion_pct': instance.completion_pct,
                    },
                )
            
            elif instance._old_status == 'not_started' and instance._new_status == 'in_progress':
                # Log start
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantOnboarding',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Onboarding process started",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    },
                )


@receiver(post_save, sender=TenantOnboardingStep)
def onboarding_step_completed(sender, instance, created, **kwargs):
    """
    Handle onboarding step completion.
    
    Signal triggered when onboarding step is completed.
    """
    if not created and instance.status == 'done' and hasattr(instance, '_status_changed'):
        logger.info(f"Onboarding step completed for {instance.tenant.name}: {instance.step_key}")
        
        # Log step completion
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantOnboardingStep',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Onboarding step '{instance.label}' completed",
            metadata={
                'step_key': instance.step_key,
                'step_type': instance.step_type,
                'time_spent_seconds': instance.time_spent_seconds,
            },
        )
        
        # Update onboarding progress
        onboarding = instance.tenant.onboarding
        if onboarding:
            onboarding.update_progress()
        
        # Trigger signal
        from . import onboarding_step_completed
        onboarding_step_completed.send(sender=TenantOnboardingStep, step=instance)


@receiver(pre_save, sender=TenantOnboardingStep)
def onboarding_step_pre_save(sender, instance, **kwargs):
    """
    Handle onboarding step pre-save operations.
    
    Signal triggered before onboarding step is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantOnboardingStep.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
                
        except TenantOnboardingStep.DoesNotExist:
            pass  # New step, no changes to track


@receiver(post_save, sender=TenantOnboardingStep)
def onboarding_step_updated(sender, instance, created, **kwargs):
    """
    Handle onboarding step updates.
    
    Signal triggered when onboarding step is updated.
    """
    if not created:
        # Handle step start
        if hasattr(instance, '_status_changed') and instance._new_status == 'in_progress':
            logger.info(f"Onboarding step started for {instance.tenant.name}: {instance.step_key}")
            
            # Log step start
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantOnboardingStep',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Onboarding step '{instance.label}' started",
                metadata={
                    'step_key': instance.step_key,
                    'step_type': instance.step_type,
                },
            )


@receiver(post_save, sender=TenantTrialExtension)
def trial_extension_requested(sender, instance, created, **kwargs):
    """
    Handle trial extension request.
    
    Signal triggered when trial extension is requested.
    """
    if created:
        logger.info(f"Trial extension requested for {instance.tenant.name}: {instance.days_extended} days")
        
        # Log trial extension request
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantTrialExtension',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Trial extension requested: {instance.days_extended} days",
            metadata={
                'days_extended': instance.days_extended,
                'reason': instance.reason,
                'reason_details': instance.reason_details,
                'original_trial_end': instance.original_trial_end.isoformat(),
            },
        )
        
        # Trigger signal
        from . import trial_extension_requested
        trial_extension_requested.send(sender=TenantTrialExtension, extension=instance)
        
        # Send notification to administrators
        TenantNotification.objects.create(
            tenant=instance.tenant,
            title='Trial Extension Request',
            message=f'Trial extension requested: {instance.days_extended} days - {instance.reason_details}',
            notification_type='trial',
            priority='medium',
            send_email=True,
            send_push=False,  # Only email to admins
            action_url='/onboarding/trial-extensions',
            action_text='Review Request',
            metadata={
                'extension_id': str(instance.id),
                'days_extended': instance.days_extended,
            },
        )


@receiver(pre_save, sender=TenantTrialExtension)
def trial_extension_pre_save(sender, instance, **kwargs):
    """
    Handle trial extension pre-save operations.
    
    Signal triggered before trial extension is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantTrialExtension.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
                
        except TenantTrialExtension.DoesNotExist:
            pass  # New trial extension, no changes to track


@receiver(post_save, sender=TenantTrialExtension)
def trial_extension_updated(sender, instance, created, **kwargs):
    """
    Handle trial extension updates.
    
    Signal triggered when trial extension is updated.
    """
    if not created:
        # Handle approval/rejection
        if hasattr(instance, '_status_changed'):
            if instance._new_status == 'approved':
                logger.info(f"Trial extension approved for {instance.tenant.name}: {instance.days_extended} days")
                
                # Update tenant trial end date
                if instance.new_trial_end:
                    instance.tenant.trial_ends_at = instance.new_trial_end
                    instance.tenant.save(update_fields=['trial_ends_at'])
                
                # Log approval
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantTrialExtension',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Trial extension approved: {instance.days_extended} days",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    },
                )
                
                # Trigger trial extension signal
                from . import trial_extended
                trial_extended.send(
                    sender=TenantTrialExtension,
                    tenant=instance.tenant,
                    days_extended=instance.days_extended,
                    new_trial_end=instance.new_trial_end,
                )
                
                # Send approval notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='Trial Extension Approved!',
                    message=f'Your trial has been extended by {instance.days_extended} days. Enjoy exploring more features!',
                    notification_type='trial',
                    priority='medium',
                    send_email=True,
                    send_push=True,
                    action_url='/dashboard',
                    action_text='Go to Dashboard',
                    metadata={
                        'extension_id': str(instance.id),
                        'days_extended': instance.days_extended,
                        'new_trial_end': instance.new_trial_end.isoformat(),
                    },
                )
            
            elif instance._new_status == 'rejected':
                logger.info(f"Trial extension rejected for {instance.tenant.name}")
                
                # Log rejection
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantTrialExtension',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Trial extension rejected",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    },
                    metadata={
                        'rejection_reason': instance.rejection_reason,
                    },
                )
                
                # Send rejection notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='Trial Extension Request',
                    message=f'Your trial extension request was not approved. {instance.rejection_reason}',
                    notification_type='trial',
                    priority='low',
                    send_email=True,
                    send_push=False,
                    action_url='/billing/plans',
                    action_text='View Plans',
                    metadata={
                        'extension_id': str(instance.id),
                        'rejection_reason': instance.rejection_reason,
                    },
                )


def track_onboarding_progress(tenant):
    """
    Track and update onboarding progress.
    
    Args:
        tenant: Tenant instance
    """
    try:
        onboarding = tenant.onboarding
        if onboarding and onboarding.status == 'in_progress':
            # Update progress
            onboarding.update_progress()
            
            # Check if all steps are completed
            completed_steps = onboarding.tenant.onboarding_steps.filter(status='done').count()
            total_steps = onboarding.tenant.onboarding_steps.count()
            
            if completed_steps == total_steps:
                # Complete onboarding
                onboarding.complete_onboarding()
            
    except Exception as e:
        logger.error(f"Failed to track onboarding progress for {tenant.name}: {str(e)}")


def send_onboarding_reminder(tenant, reminder_type):
    """
    Send onboarding reminder based on type.
    
    Args:
        tenant: Tenant instance
        reminder_type: Type of reminder
    """
    try:
        onboarding = tenant.onboarding
        if not onboarding:
            return
        
        if reminder_type == 'inactive':
            days_inactive = onboarding.days_since_start
            
            if days_inactive >= 14:
                title = 'Complete Your Setup'
                message = f'You started your setup {days_inactive} days ago. Complete the remaining steps to get the most out of your account.'
                priority = 'high'
            elif days_inactive >= 7:
                title = 'Continue Your Setup'
                message = f'You have incomplete setup steps. Continue your onboarding to unlock all features.'
                priority = 'medium'
            else:
                title = 'Setup Progress'
                message = f'You\'re {onboarding.completion_pct}% through setup. Complete the remaining steps when you have time.'
                priority = 'low'
        
        elif reminder_type == 'step_help':
            current_step = onboarding.current_step_obj
            if current_step:
                title = f'Need Help with {current_step.label}?'
                message = f'Here are some tips to help you complete the {current_step.label} step.'
                priority = 'low'
        
        else:
            return
        
        # Send notification
        TenantNotification.objects.create(
            tenant=tenant,
            title=title,
            message=message,
            notification_type='onboarding',
            priority=priority,
            send_email=True,
            send_push=True,
            action_url='/onboarding',
            action_text='Continue Setup',
            metadata={
                'onboarding_id': str(onboarding.id),
                'completion_pct': onboarding.completion_pct,
            },
        )
        
    except Exception as e:
        logger.error(f"Failed to send onboarding reminder to {tenant.name}: {str(e)}")
