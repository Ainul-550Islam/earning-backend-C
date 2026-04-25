"""
Reseller Signal Handlers

This module contains signal handlers for reseller-related models including
ResellerConfig and ResellerInvoice.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.reseller import ResellerConfig, ResellerInvoice
from ..models.security import TenantAuditLog
from ..models.analytics import TenantNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ResellerConfig)
def reseller_created(sender, instance, created, **kwargs):
    """
    Handle reseller creation.
    
    Signal triggered when a new reseller is created.
    """
    if created:
        logger.info(f"Reseller created: {instance.company_name} (ID: {instance.id})")
        
        # Log reseller creation
        TenantAuditLog.log_action(
            tenant=instance.parent_tenant,
            action='create',
            model_name='ResellerConfig',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Reseller '{instance.company_name}' created",
            metadata={
                'reseller_id': instance.reseller_id,
                'company_name': instance.company_name,
                'contact_email': instance.contact_email,
                'commission_type': instance.commission_type,
                'commission_pct': instance.commission_pct,
            },
        )
        
        # Trigger signal
        from . import reseller_created
        reseller_created.send(sender=ResellerConfig, reseller=instance)


@receiver(pre_save, sender=ResellerConfig)
def reseller_pre_save(sender, instance, **kwargs):
    """
    Handle reseller pre-save operations.
    
    Signal triggered before reseller is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = ResellerConfig.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
            
            # Track verification changes
            if old_instance.is_verified != instance.is_verified:
                instance._verification_changed = True
                instance._old_verified = old_instance.is_verified
                instance._new_verified = instance.is_verified
                
        except ResellerConfig.DoesNotExist:
            pass  # New reseller, no changes to track


@receiver(post_save, sender=ResellerConfig)
def reseller_updated(sender, instance, created, **kwargs):
    """
    Handle reseller updates.
    
    Signal triggered when reseller is updated.
    """
    if not created:
        logger.info(f"Reseller updated: {instance.company_name} - Status: {instance.status}")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            status_text = instance._new_status
            
            # Log status change
            TenantAuditLog.log_action(
                tenant=instance.parent_tenant,
                action='config_change',
                model_name='ResellerConfig',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Reseller '{instance.company_name}' status changed to '{status_text}'",
                changes={
                    'status': {'old': instance._old_status, 'new': instance._new_status}
                },
            )
        
        # Handle verification changes
        if hasattr(instance, '_verification_changed') and instance._new_verified:
            # Log verification
            TenantAuditLog.log_action(
                tenant=instance.parent_tenant,
                action='config_change',
                model_name='ResellerConfig',
                object_id=str(instance.id),
                description=f"Reseller '{instance.company_name}' verified",
                metadata={
                    'verified_at': timezone.now().isoformat(),
                },
            )
            
            # Send notification
            TenantNotification.objects.create(
                tenant=instance.parent_tenant,
                title='Reseller Account Verified',
                message=f'Reseller account for {instance.company_name} has been verified and is now active.',
                notification_type='system',
                priority='medium',
                send_email=True,
                send_push=True,
                action_url='/resellers',
                action_text='View Reseller',
                metadata={'reseller_id': str(instance.id)},
            )


@receiver(post_save, sender=ResellerInvoice)
def commission_calculated(sender, instance, created, **kwargs):
    """
    Handle commission calculation.
    
    Signal triggered when commission invoice is created.
    """
    if created:
        logger.info(f"Commission calculated for {instance.reseller.company_name}: ${instance.commission_amount:.2f}")
        
        # Log commission calculation
        TenantAuditLog.log_action(
            tenant=instance.reseller.parent_tenant,
            action='billing_event',
            model_name='ResellerInvoice',
            object_id=str(instance.id),
            object_repr=instance.invoice_number,
            description=f"Commission calculated: ${instance.commission_amount:.2f} for {instance.reseller.company_name}",
            metadata={
                'reseller_id': str(instance.reseller.id),
                'reseller_name': instance.reseller.company_name,
                'commission_amount': float(instance.commission_amount),
                'bonus_amount': float(instance.bonus_amount),
                'total_amount': float(instance.total_amount),
                'period_start': instance.period_start.isoformat(),
                'period_end': instance.period_end.isoformat(),
                'referral_count': instance.referral_count,
                'active_referrals': instance.active_referrals,
            },
        )
        
        # Trigger signal
        from . import commission_calculated
        commission_calculated.send(sender=ResellerInvoice, invoice=instance)


@receiver(pre_save, sender=ResellerInvoice)
def reseller_invoice_pre_save(sender, instance, **kwargs):
    """
    Handle reseller invoice pre-save operations.
    
    Signal triggered before reseller invoice is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = ResellerInvoice.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
                
        except ResellerInvoice.DoesNotExist:
            pass  # New invoice, no changes to track


@receiver(post_save, sender=ResellerInvoice)
def reseller_invoice_updated(sender, instance, created, **kwargs):
    """
    Handle reseller invoice updates.
    
    Signal triggered when reseller invoice is updated.
    """
    if not created:
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            status_text = instance._new_status
            
            # Log status change
            TenantAuditLog.log_action(
                tenant=instance.reseller.parent_tenant,
                action='billing_event',
                model_name='ResellerInvoice',
                object_id=str(instance.id),
                object_repr=instance.invoice_number,
                description=f"Commission invoice '{instance.invoice_number}' status changed to '{status_text}'",
                changes={
                    'status': {'old': instance._old_status, 'new': instance._new_status}
                },
                metadata={
                    'reseller_name': instance.reseller.company_name,
                    'commission_amount': float(instance.commission_amount),
                },
            )
            
            # Handle payment completion
            if instance._new_status == 'paid' and instance.paid_date:
                # Send payment confirmation
                TenantNotification.objects.create(
                    tenant=instance.reseller.parent_tenant,
                    title='Commission Payment Received',
                    message=f'Commission payment of ${instance.total_amount:.2f} for {instance.reseller.company_name} has been received.',
                    notification_type='billing',
                    priority='low',
                    send_email=True,
                    send_push=True,
                    action_url='/resellers/commissions',
                    action_text='View Commissions',
                    metadata={'invoice_id': str(instance.id)},
                )


def track_referral_activity(tenant, reseller_config, activity_type, metadata=None):
    """
    Track referral activity for reseller.
    
    Args:
        tenant: Tenant instance (referred tenant)
        reseller_config: ResellerConfig instance
        activity_type: Type of activity
        metadata: Additional metadata
    """
    try:
        # Log referral activity
        TenantAuditLog.log_action(
            tenant=reseller_config.parent_tenant,
            action='config_change',
            model_name='ReferralActivity',
            object_id=str(tenant.id),
            description=f"Referral activity: {activity_type}",
            metadata={
                'referred_tenant_id': str(tenant.id),
                'referred_tenant_name': tenant.name,
                'reseller_id': str(reseller_config.id),
                'reseller_name': reseller_config.company_name,
                'activity_type': activity_type,
                **(metadata or {}),
            },
        )
        
        # Update referral counts
        reseller_config.total_referrals += 1
        if tenant.status == 'active':
            reseller_config.active_referrals += 1
        reseller_config.save(update_fields=['total_referrals', 'active_referrals'])
        
        logger.info(f"Referral activity tracked: {activity_type} for {reseller_config.company_name}")
        
    except Exception as e:
        logger.error(f"Failed to track referral activity for {reseller_config.company_name}: {str(e)}")


def calculate_reseller_commission(reseller_config, period_start, period_end):
    """
    Calculate commission for reseller for a specific period.
    
    Args:
        reseller_config: ResellerConfig instance
        period_start: Start date for period
        period_end: End date for period
    """
    try:
        # Get referred tenants in the period
        from ..models import Tenant
        
        referred_tenants = Tenant.objects.filter(
            parent_tenant=reseller_config.parent_tenant,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )
        
        # Calculate commission based on reseller's commission type
        commission_amount = 0.0
        bonus_amount = 0.0
        
        if reseller_config.commission_type == 'percentage':
            # Calculate based on revenue from referred tenants
            from ..models import TenantInvoice
            
            total_revenue = TenantInvoice.objects.filter(
                tenant__in=referred_tenants,
                status='paid',
                paid_date__date__gte=period_start,
                paid_date__date__lte=period_end
            ).aggregate(total=models.Sum('total_amount'))['total'] or 0
            
            commission_amount = float(total_revenue) * (reseller_config.commission_pct / 100)
        
        elif reseller_config.commission_type == 'fixed':
            # Fixed commission per referral
            commission_amount = float(referred_tenants.count()) * float(reseller_config.fixed_commission)
        
        elif reseller_config.commission_type == 'tiered':
            # Tiered commission based on number of referrals
            referral_count = referred_tenants.count()
            
            for tier in reseller_config.commission_tiers:
                if referral_count >= tier.get('min_referrals', 0):
                    commission_amount = float(tier.get('commission', 0))
                    break
        
        # Calculate bonus for high performance
        if referred_tenants.count() >= 10:
            bonus_amount = commission_amount * 0.1  # 10% bonus
        
        total_amount = commission_amount + bonus_amount
        
        # Create commission invoice
        invoice = ResellerInvoice.objects.create(
            reseller=reseller_config,
            invoice_number=f"RES-{period_end.strftime('%Y%m')}-{reseller_config.reseller_id}",
            status='pending',
            period_start=period_start,
            period_end=period_end,
            commission_amount=commission_amount,
            bonus_amount=bonus_amount,
            total_amount=total_amount,
            referral_count=referred_tenants.count(),
            active_referrals=referred_tenants.filter(status='active').count(),
            notes=f"Commission calculation for {period_start} to {period_end}",
        )
        
        logger.info(f"Commission calculated for {reseller_config.company_name}: ${total_amount:.2f}")
        
        return invoice
        
    except Exception as e:
        logger.error(f"Failed to calculate commission for {reseller_config.company_name}: {str(e)}")
        return None


def log_reseller_performance(reseller_config, performance_data):
    """
    Log reseller performance metrics.
    
    Args:
        reseller_config: ResellerConfig instance
        performance_data: Performance data dictionary
    """
    try:
        # Log performance metrics
        TenantAuditLog.log_action(
            tenant=reseller_config.parent_tenant,
            action='config_change',
            model_name='ResellerPerformance',
            description=f"Reseller performance metrics recorded",
            metadata={
                'reseller_id': str(reseller_config.id),
                'reseller_name': reseller_config.company_name,
                **performance_data,
            },
        )
        
        # Check for performance alerts
        if performance_data.get('conversion_rate', 0) < 0.1:  # Less than 10% conversion
            TenantNotification.objects.create(
                tenant=reseller_config.parent_tenant,
                title='Low Reseller Performance',
                message=f'Reseller {reseller_config.company_name} has low conversion rate: {performance_data.get("conversion_rate", 0):.1%}',
                notification_type='system',
                priority='medium',
                send_email=True,
                send_push=False,
                action_url='/resellers',
                action_text='View Performance',
                metadata={'reseller_id': str(reseller_config.id)},
            )
        
    except Exception as e:
        logger.error(f"Failed to log reseller performance for {reseller_config.company_name}: {str(e)}")
