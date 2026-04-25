"""
Billing Tasks

This module contains Celery tasks for billing operations including
invoice generation, payment processing, dunning workflows, and commission calculations.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..services import TenantBillingService
from ..models import Tenant, TenantInvoice
from ..models.reseller import ResellerInvoice

logger = logging.getLogger(__name__)


@shared_task(name='tenants.billing.generate_monthly_invoices')
def generate_monthly_invoices():
    """
    Generate monthly invoices for all active tenants.
    
    This task runs daily to check for tenants whose billing cycle
    is due and generate appropriate invoices.
    """
    logger.info("Starting monthly invoice generation")
    
    generated_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(
        is_deleted=False,
        status='active'
    ).select_related('billing', 'plan')
    
    for tenant in tenants:
        try:
            # Check if invoice should be generated today
            billing = tenant.billing
            today = timezone.now().date()
            
            if billing.should_generate_invoice_today():
                invoice = TenantBillingService.generate_monthly_invoice(tenant)
                
                if invoice:
                    generated_count += 1
                    logger.info(f"Generated invoice {invoice.invoice_number} for {tenant.name}")
                else:
                    logger.info(f"No billing activity for {tenant.name}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to generate invoice for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'generated_count': generated_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Invoice generation completed: {result}")
    return result


@shared_task(name='tenants.billing.process_dunning_workflow')
def process_dunning_workflow():
    """
    Process dunning workflow for overdue invoices.
    
    This task runs daily to handle overdue invoices and send
    appropriate notifications based on dunning stage.
    """
    logger.info("Starting dunning workflow processing")
    
    processed_count = 0
    suspended_count = 0
    errors = []
    
    # Get all overdue invoices
    overdue_invoices = TenantInvoice.objects.filter(
        status='overdue',
        due_date__lt=timezone.now().date()
    ).select_related('tenant')
    
    for invoice in overdue_invoices:
        try:
            # Process dunning for the tenant
            result = TenantBillingService.handle_dunning(invoice.tenant)
            
            if result['action'] == 'suspended':
                suspended_count += 1
                logger.warning(f"Tenant {invoice.tenant.name} suspended due to payment overdue")
            
            processed_count += 1
            logger.info(f"Processed dunning for {invoice.tenant.name}: {result['action']}")
            
        except Exception as e:
            error_msg = f"Failed to process dunning for {invoice.tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'processed_count': processed_count,
        'suspended_count': suspended_count,
        'failed_count': len(errors),
        'errors': errors,
        'total_overdue': overdue_invoices.count(),
    }
    
    logger.info(f"Dunning workflow completed: {result}")
    return result


@shared_task(name='tenants.billing.send_payment_reminders')
def send_payment_reminders():
    """
    Send payment reminders for invoices due soon.
    
    This task runs daily to send reminders for invoices
    that are due within the next few days.
    """
    logger.info("Starting payment reminder sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get invoices due in the next 3 days
    reminder_date = timezone.now().date() + timedelta(days=3)
    
    upcoming_invoices = TenantInvoice.objects.filter(
        status='pending',
        due_date__lte=reminder_date,
        due_date__gt=timezone.now().date()
    ).select_related('tenant')
    
    for invoice in upcoming_invoices:
        try:
            # Send reminder notification
            from ..models.analytics import TenantNotification
            
            days_until_due = (invoice.due_date - timezone.now().date()).days
            
            if days_until_due <= 1:
                title = 'Payment Due Tomorrow'
                priority = 'high'
            elif days_until_due <= 3:
                title = 'Payment Due Soon'
                priority = 'medium'
            else:
                title = 'Upcoming Payment'
                priority = 'low'
            
            TenantNotification.objects.create(
                tenant=invoice.tenant,
                title=title,
                message=f'Invoice {invoice.invoice_number} is due in {days_until_due} days. Amount: ${invoice.balance_due:.2f}',
                notification_type='billing',
                priority=priority,
                send_email=True,
                send_push=True,
                action_url='/billing/invoices',
                action_text='View Invoice',
                metadata={'invoice_id': str(invoice.id)},
            )
            
            sent_count += 1
            logger.info(f"Sent payment reminder for {invoice.invoice_number}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send reminder for {invoice.invoice_number}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_upcoming': upcoming_invoices.count(),
    }
    
    logger.info(f"Payment reminders completed: {result}")
    return result


@shared_task(name='tenants.billing.calculate_commission_payments')
def calculate_commission_payments():
    """
    Calculate commission payments for resellers.
    
    This task runs monthly to calculate commissions for all
    active resellers based on their referral activity.
    """
    logger.info("Starting commission payment calculation")
    
    calculated_count = 0
    failed_count = 0
    errors = []
    
    # Get all active resellers
    from ..models.reseller import ResellerConfig
    
    resellers = ResellerConfig.objects.filter(status='active').select_related('parent_tenant')
    
    for reseller in resellers:
        try:
            # Calculate commission for the previous month
            from datetime import date
            today = date.today()
            
            if today.day >= 5:  # Run after 5th of each month
                last_month_end = today.replace(day=1) - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                
                # This would calculate actual commission based on referral activity
                # For now, create placeholder invoice
                commission_data = {
                    'period_start': last_month_start,
                    'period_end': last_month_end,
                    'commission_amount': 0.0,  # Would calculate based on activity
                    'bonus_amount': 0.0,
                    'referral_count': 0,
                    'active_referrals': 0,
                    'notes': 'Monthly commission calculation',
                }
                
                invoice = ResellerInvoice.objects.create(
                    reseller=reseller,
                    invoice_number=f"RES-{last_month_end.strftime('%Y%m')}-{reseller.reseller_id}",
                    status='pending',
                    **commission_data
                )
                
                calculated_count += 1
                logger.info(f"Calculated commission invoice for {reseller.company_name}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to calculate commission for {reseller.company_name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'calculated_count': calculated_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_resellers': resellers.count(),
    }
    
    logger.info(f"Commission calculation completed: {result}")
    return result


@shared_task(name='tenants.billing.process_subscription_renewals')
def process_subscription_renewals():
    """
    Process automatic subscription renewals.
    
    This task runs daily to handle automatic renewals for
    subscriptions with auto-renewal enabled.
    """
    logger.info("Starting subscription renewal processing")
    
    renewed_count = 0
    failed_count = 0
    errors = []
    
    # Get tenants with auto-renewal enabled
    from ..models import TenantBilling
    
    auto_renew_tenants = Tenant.objects.filter(
        is_deleted=False,
        status='active',
        billing__auto_renew=True
    ).select_related('billing', 'plan')
    
    for tenant in auto_renew_tenants:
        try:
            billing = tenant.billing
            
            # Check if renewal is due today
            if billing.is_renewal_due():
                # Process renewal
                from ..services import PlanService
                
                # Create new invoice for next period
                invoice = TenantBillingService.generate_monthly_invoice(tenant)
                
                if invoice:
                    renewed_count += 1
                    logger.info(f"Processed renewal for {tenant.name}: {invoice.invoice_number}")
                else:
                    logger.warning(f"No renewal activity for {tenant.name}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to process renewal for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'renewed_count': renewed_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_auto_renew': auto_renew_tenants.count(),
    }
    
    logger.info(f"Subscription renewal processing completed: {result}")
    return result


@shared_task(name='tenants.billing.cleanup_old_invoices')
def cleanup_old_invoices(days_to_keep=365):
    """
    Clean up old paid invoices to maintain database performance.
    
    Args:
        days_to_keep (int): Number of days to keep invoices
    """
    logger.info(f"Starting cleanup of invoices older than {days_to_keep} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Archive old paid invoices
    old_invoices = TenantInvoice.objects.filter(
        status='paid',
        paid_date__lt=cutoff_date
    )
    
    archived_count = old_invoices.count()
    
    # This would archive invoices to cold storage
    # For now, just log the count
    old_invoices.update(is_archived=True)
    
    result = {
        'archived_count': archived_count,
        'cutoff_date': cutoff_date.date(),
    }
    
    logger.info(f"Invoice cleanup completed: {result}")
    return result


@shared_task(name='tenants.billing.generate_billing_reports')
def generate_billing_reports():
    """
    Generate monthly billing reports for administrators.
    
    This task runs monthly to generate comprehensive billing reports.
    """
    logger.info("Starting billing report generation")
    
    try:
        from datetime import date
        today = date.today()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        # Generate report data
        report_data = {
            'period_start': last_month_start,
            'period_end': last_month_end,
            'total_revenue': 0.0,
            'new_customers': 0,
            'churned_customers': 0,
            'active_customers': 0,
            'invoices_generated': 0,
            'invoices_paid': 0,
            'overdue_invoices': 0,
        }
        
        # Calculate metrics
        invoices = TenantInvoice.objects.filter(
            issue_date__range=[last_month_start, last_month_end]
        )
        
        report_data['invoices_generated'] = invoices.count()
        report_data['total_revenue'] = float(
            invoices.filter(status='paid').aggregate(
                total=models.Sum('total_amount')
            )['total'] or 0
        )
        report_data['invoices_paid'] = invoices.filter(status='paid').count()
        report_data['overdue_invoices'] = invoices.filter(status='overdue').count()
        
        # Customer metrics
        tenants = Tenant.objects.filter(is_deleted=False)
        report_data['active_customers'] = tenants.filter(status='active').count()
        report_data['new_customers'] = tenants.filter(
            created_at__date__range=[last_month_start, last_month_end]
        ).count()
        report_data['churned_customers'] = tenants.filter(
            updated_at__date__range=[last_month_start, last_month_end],
            status='suspended'
        ).count()
        
        # This would send the report to administrators
        logger.info(f"Billing report generated: {report_data}")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Failed to generate billing report: {str(e)}")
        return {'error': str(e)}
