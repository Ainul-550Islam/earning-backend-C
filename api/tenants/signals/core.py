"""
Core Signal Handlers

This module contains signal handlers for core tenant models including
Tenant, TenantSettings, TenantBilling, and TenantInvoice.
"""

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..services import TenantService, TenantBillingService
from ..models.security import TenantAuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tenant)
def tenant_created(sender, instance, created, **kwargs):
    """
    Handle tenant creation.
    
    Signal triggered when a new tenant is created.
    """
    if created:
        logger.info(f"Tenant created: {instance.name} (ID: {instance.id})")
        
        # Create related objects
        try:
            # Create tenant settings
            TenantSettings.objects.get_or_create(tenant=instance)
            
            # Create tenant billing
            TenantBilling.objects.get_or_create(tenant=instance)
            
            # Create onboarding session
            from ..models.onboarding import TenantOnboarding
            TenantOnboarding.objects.get_or_create(tenant=instance)
            
            # Create health score
            from ..models.analytics import TenantHealthScore
            TenantHealthScore.objects.get_or_create(tenant=instance)
            
            # Log creation
            TenantAuditLog.log_action(
                tenant=instance,
                action='create',
                model_name='Tenant',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Tenant '{instance.name}' created with plan '{instance.plan.name}'",
                metadata={
                    'plan_id': str(instance.plan.id),
                    'plan_name': instance.plan.name,
                    'tier': instance.tier,
                    'trial_ends_at': instance.trial_ends_at.isoformat() if instance.trial_ends_at else None,
                }
            )
            
            # Trigger welcome email task
            from ..tasks.notifications import send_welcome_emails
            send_welcome_emails.delay()
            
        except Exception as e:
            logger.error(f"Failed to create related objects for tenant {instance.id}: {str(e)}")


@receiver(pre_save, sender=Tenant)
def tenant_pre_save(sender, instance, **kwargs):
    """
    Handle tenant pre-save operations.
    
    Signal triggered before tenant is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = Tenant.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
            
            # Track plan changes
            if old_instance.plan_id != instance.plan_id:
                instance._plan_changed = True
                instance._old_plan = old_instance.plan
                instance._new_plan = instance.plan
                
        except Tenant.DoesNotExist:
            pass  # New tenant, no changes to track


@receiver(post_save, sender=Tenant)
def tenant_updated(sender, instance, created, **kwargs):
    """
    Handle tenant updates.
    
    Signal triggered when tenant is updated.
    """
    if not created:
        logger.info(f"Tenant updated: {instance.name} (ID: {instance.id})")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            if instance._new_status == 'suspended':
                # Log suspension
                TenantAuditLog.log_action(
                    tenant=instance,
                    action='config_change',
                    model_name='Tenant',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Tenant status changed to 'suspended'",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    }
                )
                
                # Trigger suspension signal
                from . import tenant_suspended
                tenant_suspended.send(sender=Tenant, tenant=instance)
                
            elif instance._old_status == 'suspended' and instance._new_status == 'active':
                # Log unsuspension
                TenantAuditLog.log_action(
                    tenant=instance,
                    action='config_change',
                    model_name='Tenant',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"Tenant status changed to 'active'",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    }
                )
                
                # Trigger unsuspension signal
                from . import tenant_unsuspended
                tenant_unsuspended.send(sender=Tenant, tenant=instance)
        
        # Handle plan changes
        if hasattr(instance, '_plan_changed'):
            # Log plan upgrade/downgrade
            TenantAuditLog.log_action(
                tenant=instance,
                action='config_change',
                model_name='Tenant',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Tenant plan changed from '{instance._old_plan.name}' to '{instance._new_plan.name}'",
                changes={
                    'plan': {
                        'old': {'id': str(instance._old_plan.id), 'name': instance._old_plan.name},
                        'new': {'id': str(instance._new_plan.id), 'name': instance._new_plan.name}
                    }
                }
            )
            
            # Create plan upgrade record
            from ..models.plan import PlanUpgrade
            PlanUpgrade.objects.create(
                tenant=instance,
                from_plan=instance._old_plan,
                to_plan=instance._new_plan,
                reason='plan_change',
                notes='Plan changed via tenant update',
            )


@receiver(pre_delete, sender=Tenant)
def tenant_pre_delete(sender, instance, **kwargs):
    """
    Handle tenant pre-delete operations.
    
    Signal triggered before tenant is deleted.
    """
    logger.info(f"Tenant being deleted: {instance.name} (ID: {instance.id})")
    
    # Log deletion
    TenantAuditLog.log_action(
        tenant=instance,
        action='delete',
        model_name='Tenant',
        object_id=str(instance.id),
        object_repr=str(instance),
        description=f"Tenant '{instance.name}' marked for deletion",
        metadata={
            'deleted_at': timezone.now().isoformat(),
            'status': instance.status,
            'plan': instance.plan.name,
        }
    )


@receiver(post_save, sender=TenantSettings)
def tenant_settings_updated(sender, instance, created, **kwargs):
    """
    Handle tenant settings updates.
    
    Signal triggered when tenant settings are updated.
    """
    if not created:
        logger.info(f"Tenant settings updated: {instance.tenant.name}")
        
        # Log settings change
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantSettings',
            object_id=str(instance.id),
            description="Tenant settings updated",
        )
        
        # Trigger signal
        from . import tenant_settings_updated
        tenant_settings_updated.send(sender=TenantSettings, settings=instance)


@receiver(post_save, sender=TenantBilling)
def tenant_billing_updated(sender, instance, created, **kwargs):
    """
    Handle tenant billing updates.
    
    Signal triggered when tenant billing is updated.
    """
    if not created:
        logger.info(f"Tenant billing updated: {instance.tenant.name}")
        
        # Log billing change
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='billing_event',
            model_name='TenantBilling',
            object_id=str(instance.id),
            description="Tenant billing configuration updated",
            metadata={
                'billing_cycle': instance.billing_cycle,
                'payment_method': instance.payment_method,
                'final_price': float(instance.final_price),
            }
        )
        
        # Trigger signal
        from . import tenant_billing_updated
        tenant_billing_updated.send(sender=TenantBilling, billing=instance)


@receiver(post_save, sender=TenantInvoice)
def tenant_invoice_created(sender, instance, created, **kwargs):
    """
    Handle tenant invoice creation.
    
    Signal triggered when tenant invoice is created.
    """
    if created:
        logger.info(f"Invoice created: {instance.invoice_number} for {instance.tenant.name}")
        
        # Log invoice creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='billing_event',
            model_name='TenantInvoice',
            object_id=str(instance.id),
            object_repr=instance.invoice_number,
            description=f"Invoice {instance.invoice_number} created for ${instance.total_amount:.2f}",
            metadata={
                'invoice_number': instance.invoice_number,
                'total_amount': float(instance.total_amount),
                'due_date': instance.due_date.isoformat(),
                'billing_period_start': instance.billing_period_start.isoformat(),
                'billing_period_end': instance.billing_period_end.isoformat(),
            }
        )
        
        # Trigger signal
        from . import tenant_invoice_created
        tenant_invoice_created.send(sender=TenantInvoice, invoice=instance)
        
        # Send notification
        from ..models.analytics import TenantNotification
        TenantNotification.objects.create(
            tenant=instance.tenant,
            title='New Invoice Available',
            message=f'Invoice {instance.invoice_number} for ${instance.total_amount:.2f} is now available.',
            notification_type='billing',
            priority='medium',
            send_email=True,
            send_push=True,
            action_url='/billing/invoices',
            action_text='View Invoice',
            metadata={'invoice_id': str(instance.id)},
        )


@receiver(post_save, sender=TenantInvoice)
def tenant_invoice_updated(sender, instance, created, **kwargs):
    """
    Handle tenant invoice updates.
    
    Signal triggered when tenant invoice is updated.
    """
    if not created:
        logger.info(f"Invoice updated: {instance.invoice_number} - Status: {instance.status}")
        
        # Log invoice update
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='billing_event',
            model_name='TenantInvoice',
            object_id=str(instance.id),
            object_repr=instance.invoice_number,
            description=f"Invoice {instance.invoice_number} status changed to '{instance.status}'",
            metadata={
                'invoice_number': instance.invoice_number,
                'status': instance.status,
                'paid_date': instance.paid_date.isoformat() if instance.paid_date else None,
                'amount_paid': float(instance.amount_paid),
            }
        )
        
        # Handle payment completion
        if instance.status == 'paid' and instance.paid_date:
            # Trigger payment processed signal
            from . import payment_processed
            payment_processed.send(
                sender=TenantInvoice,
                invoice=instance,
                amount=instance.amount_paid,
                payment_method=instance.payment_method,
            )
            
            # Send payment confirmation
            from ..models.analytics import TenantNotification
            TenantNotification.objects.create(
                tenant=instance.tenant,
                title='Payment Received',
                message=f'Payment of ${instance.amount_paid:.2f} for invoice {instance.invoice_number} has been received.',
                notification_type='billing',
                priority='low',
                send_email=True,
                send_push=True,
                action_url='/billing/invoices',
                action_text='View Invoice',
                metadata={'invoice_id': str(instance.id)},
            )
        
        # Trigger signal
        from . import tenant_invoice_updated
        tenant_invoice_updated.send(sender=TenantInvoice, invoice=instance)


@receiver(pre_delete, sender=Tenant)
def tenant_deleted(sender, instance, **kwargs):
    """
    Handle tenant deletion completion.
    
    Signal triggered after tenant is deleted.
    """
    logger.info(f"Tenant deleted: {instance.name} (ID: {instance.id})")
    
    # This would trigger cleanup tasks
    # For now, just log the deletion
