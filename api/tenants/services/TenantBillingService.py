"""
Tenant Billing Service

This service handles tenant billing operations including
invoice generation, payment processing, and subscription management.
"""

from datetime import timedelta, date
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant, TenantInvoice
from ..models.plan import PlanUsage
from ..models.security import TenantAuditLog

User = get_user_model()


class TenantBillingService:
    """
    Service class for tenant billing operations.
    
    This service handles invoice generation, payment processing,
    dunning management, and subscription billing.
    """
    
    @staticmethod
    def generate_invoice(tenant, billing_data, generated_by=None):
        """
        Generate invoice for tenant.
        
        Args:
            tenant (Tenant): Tenant to generate invoice for
            billing_data (dict): Invoice data
            generated_by (User): User generating the invoice
            
        Returns:
            TenantInvoice: Generated invoice
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Generate invoice number
            invoice_number = TenantBillingService._generate_invoice_number(tenant)
            
            # Create invoice
            invoice = TenantInvoice.objects.create(
                tenant=tenant,
                invoice_number=invoice_number,
                status='draft',
                issue_date=billing_data.get('issue_date', timezone.now().date()),
                due_date=billing_data.get('due_date', timezone.now().date() + timedelta(days=30)),
                billing_period_start=billing_data.get('billing_period_start'),
                billing_period_end=billing_data.get('billing_period_end'),
                description=billing_data.get('description'),
                notes=billing_data.get('notes'),
                line_items=billing_data.get('line_items', []),
                metadata=billing_data.get('metadata', {}),
            )
            
            # Calculate totals
            invoice.calculate_totals()
            invoice.save()
            
            # Log generation
            if generated_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='billing_event',
                    actor=generated_by,
                    model_name='TenantInvoice',
                    object_id=str(invoice.id),
                    object_repr=str(invoice),
                    description=f"Invoice {invoice_number} generated",
                    metadata={
                        'invoice_number': invoice_number,
                        'total_amount': float(invoice.total_amount),
                    }
                )
            
            return invoice
    
    @staticmethod
    def _generate_invoice_number(tenant):
        """Generate unique invoice number for tenant."""
        from django.db.models import Max
        
        # Get last invoice number for tenant
        last_invoice = TenantInvoice.objects.filter(
            tenant=tenant
        ).order_by('-created_at').first()
        
        if last_invoice:
            # Extract number part and increment
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        # Format: TENANT-YYYYMMDD-NNNN
        date_str = timezone.now().strftime('%Y%m%d')
        return f"{tenant.slug.upper()}-{date_str}-{new_num:04d}"
    
    @staticmethod
    def generate_monthly_invoice(tenant):
        """
        Generate monthly invoice for tenant.
        
        Args:
            tenant (Tenant): Tenant to generate invoice for
            
        Returns:
            TenantInvoice: Generated invoice or None if no billing needed
        """
        billing = tenant.billing
        
        # Check if invoice already exists for this period
        period_start = billing.get_current_period_start()
        period_end = billing.get_current_period_end()
        
        existing_invoice = TenantInvoice.objects.filter(
            tenant=tenant,
            billing_period_start=period_start,
            billing_period_end=period_end
        ).first()
        
        if existing_invoice:
            return existing_invoice
        
        # Get usage data for the period
        usage_data = TenantBillingService._get_usage_for_period(tenant, period_start, period_end)
        
        # Calculate line items
        line_items = []
        
        # Base plan fee
        line_items.append({
            'description': f"{tenant.plan.name} - {billing.billing_cycle.title()}",
            'quantity': 1,
            'unit_price': float(billing.final_price),
            'amount': float(billing.final_price),
            'type': 'subscription',
        })
        
        # Overage charges
        overage_charges = TenantBillingService._calculate_overage_charges(tenant, usage_data)
        for charge in overage_charges:
            line_items.append(charge)
        
        # Additional services
        additional_services = TenantBillingService._get_additional_services(tenant, period_start, period_end)
        for service in additional_services:
            line_items.append(service)
        
        if not line_items:
            return None
        
        # Generate invoice
        billing_data = {
            'issue_date': timezone.now().date(),
            'due_date': billing.next_billing_date,
            'billing_period_start': period_start,
            'billing_period_end': period_end,
            'description': f"Monthly billing for {tenant.name}",
            'line_items': line_items,
        }
        
        return TenantBillingService.generate_invoice(tenant, billing_data)
    
    @staticmethod
    def _get_usage_for_period(tenant, period_start, period_end):
        """Get usage data for billing period."""
        try:
            usage = PlanUsage.objects.get(
                tenant=tenant,
                period='monthly',
                period_start=period_start
            )
            return usage
        except PlanUsage.DoesNotExist:
            return None
    
    @staticmethod
    def _calculate_overage_charges(tenant, usage_data):
        """Calculate overage charges for usage beyond plan limits."""
        overage_charges = []
        
        if not usage_data:
            return overage_charges
        
        from ..models.plan import PlanQuota
        
        quotas = PlanQuota.objects.filter(plan=tenant.plan, overage_allowed=True)
        
        for quota in quotas:
            current_usage = getattr(usage_data, f'usage_{quota.feature_key}', 0)
            overage_cost = quota.calculate_overage_cost(current_usage)
            
            if overage_cost > 0:
                overage_units = current_usage - (quota.hard_limit or quota.soft_limit)
                overage_charges.append({
                    'description': f"Overage: {quota.feature_key} ({overage_units} units)",
                    'quantity': overage_units,
                    'unit_price': float(quota.overage_price_per_unit),
                    'amount': float(overage_cost),
                    'type': 'overage',
                })
        
        return overage_charges
    
    @staticmethod
    def _get_additional_services(tenant, period_start, period_end):
        """Get additional services for billing period."""
        # This would integrate with your service usage tracking
        # For now, return empty list
        return []
    
    @staticmethod
    def process_payment(invoice, payment_data, processed_by=None):
        """
        Process payment for invoice.
        
        Args:
            invoice (TenantInvoice): Invoice to process payment for
            payment_data (dict): Payment information
            processed_by (User): User processing payment
            
        Returns:
            dict: Payment processing result
            
        Raises:
            ValidationError: If payment cannot be processed
        """
        with transaction.atomic():
            if invoice.is_paid:
                raise ValidationError(_('Invoice is already paid.'))
            
            # Process payment (this would integrate with payment gateway)
            payment_result = TenantBillingService._process_payment_gateway(invoice, payment_data)
            
            if payment_result['success']:
                # Update invoice
                invoice.mark_as_paid(
                    amount=payment_data.get('amount', invoice.balance_due),
                    payment_method=payment_data.get('payment_method'),
                    transaction_id=payment_result.get('transaction_id')
                )
                
                # Reset dunning
                invoice.tenant.billing.reset_dunning()
                
                # Log payment
                if processed_by:
                    TenantAuditLog.log_action(
                        tenant=invoice.tenant,
                        action='billing_event',
                        actor=processed_by,
                        model_name='TenantInvoice',
                        object_id=str(invoice.id),
                        object_repr=str(invoice),
                        description=f"Payment processed for invoice {invoice.invoice_number}",
                        metadata={
                            'amount': float(payment_data.get('amount', invoice.balance_due)),
                            'payment_method': payment_data.get('payment_method'),
                            'transaction_id': payment_result.get('transaction_id'),
                        }
                    )
                
                return {
                    'success': True,
                    'message': 'Payment processed successfully',
                    'amount_paid': float(payment_data.get('amount', invoice.balance_due)),
                    'transaction_id': payment_result.get('transaction_id'),
                }
            else:
                # Mark as failed and increment dunning
                invoice.tenant.billing.increment_dunning()
                
                return {
                    'success': False,
                    'error': payment_result.get('error', 'Payment processing failed'),
                }
    
    @staticmethod
    def _process_payment_gateway(invoice, payment_data):
        """Process payment through payment gateway."""
        # This would integrate with actual payment gateway (Stripe, PayPal, etc.)
        # For now, simulate successful payment
        return {
            'success': True,
            'transaction_id': f"txn_{timezone.now().strftime('%Y%m%d%H%M%S')}",
        }
    
    @staticmethod
    def handle_dunning(tenant):
        """
        Handle dunning process for overdue invoices.
        
        Args:
            tenant (Tenant): Tenant to handle dunning for
            
        Returns:
            dict: Dunning process result
        """
        billing = tenant.billing
        overdue_invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            status='overdue'
        ).order_by('due_date')
        
        if not overdue_invoices:
            return {
                'success': True,
                'message': 'No overdue invoices found',
                'invoices_processed': 0,
            }
        
        # Get dunning count
        dunning_count = billing.dunning_count
        max_attempts = billing.max_dunning_attempts
        
        if dunning_count >= max_attempts:
            # Suspend tenant
            from .TenantSuspensionService import TenantSuspensionService
            TenantSuspensionService.suspend_tenant(
                tenant,
                reason="Payment overdue - maximum dunning attempts reached",
                notify=True
            )
            
            return {
                'success': True,
                'message': 'Tenant suspended due to payment overdue',
                'action': 'suspended',
                'invoices_processed': len(overdue_invoices),
            }
        
        # Send dunning notification
        TenantBillingService._send_dunning_notification(tenant, dunning_count)
        
        # Increment dunning count
        billing.increment_dunning()
        
        return {
            'success': True,
            'message': f'Dunning notification sent (attempt {dunning_count + 1})',
            'action': 'notification_sent',
            'invoices_processed': len(overdue_invoices),
        }
    
    @staticmethod
    def _send_dunning_notification(tenant, dunning_count):
        """Send dunning notification to tenant."""
        from ..models.analytics import TenantNotification
        
        # Determine message based on dunning count
        if dunning_count == 0:
            title = _('Payment Overdue Reminder')
            message = _('Your payment is overdue. Please update your payment method to avoid service interruption.')
            priority = 'medium'
        elif dunning_count == 1:
            title = _('Final Payment Notice')
            message = _('Your payment is severely overdue. Service will be suspended if payment is not received soon.')
            priority = 'high'
        else:
            title = _('Service Suspension Notice')
            message = _('Your account will be suspended due to non-payment. Please contact support immediately.')
            priority = 'urgent'
        
        TenantNotification.objects.create(
            tenant=tenant,
            title=title,
            message=message,
            notification_type='billing',
            priority=priority,
            send_email=True,
            send_push=True,
            action_url='/billing',
            action_text=_('Update Payment'),
        )
    
    @staticmethod
    def get_billing_summary(tenant):
        """
        Get comprehensive billing summary for tenant.
        
        Args:
            tenant (Tenant): Tenant to get summary for
            
        Returns:
            dict: Billing summary
        """
        billing = tenant.billing
        
        # Get recent invoices
        recent_invoices = TenantInvoice.objects.filter(
            tenant=tenant
        ).order_by('-issue_date')[:10]
        
        # Calculate totals
        total_invoices = TenantInvoice.objects.filter(tenant=tenant).count()
        paid_invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            status='paid'
        ).count()
        overdue_invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            status='overdue'
        ).count()
        
        total_revenue = TenantInvoice.objects.filter(
            tenant=tenant,
            status='paid'
        ).aggregate(total=models.Sum('total_amount'))['total'] or 0
        
        # Get current month usage
        current_usage = TenantBillingService._get_usage_for_period(
            tenant,
            billing.get_current_period_start(),
            billing.get_current_period_end()
        )
        
        summary = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'plan': {
                'name': tenant.plan.name,
                'price_monthly': float(billing.final_price),
                'billing_cycle': billing.billing_cycle,
            },
            'billing_status': {
                'dunning_count': billing.dunning_count,
                'max_dunning_attempts': billing.max_dunning_attempts,
                'is_overdue': billing.is_overdue(),
                'next_billing_date': billing.next_billing_date,
            },
            'statistics': {
                'total_invoices': total_invoices,
                'paid_invoices': paid_invoices,
                'overdue_invoices': overdue_invoices,
                'total_revenue': float(total_revenue),
                'payment_success_rate': (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0,
            },
            'recent_invoices': [
                {
                    'invoice_number': inv.invoice_number,
                    'issue_date': inv.issue_date,
                    'due_date': inv.due_date,
                    'total_amount': float(inv.total_amount),
                    'status': inv.status,
                    'balance_due': float(inv.balance_due),
                }
                for inv in recent_invoices
            ],
            'current_usage': {
                'api_calls': current_usage.api_calls_used if current_usage else 0,
                'storage_gb': float(current_usage.storage_used_gb) if current_usage else 0,
                'users': current_usage.users_used if current_usage else 0,
            } if current_usage else {},
        }
        
        return summary
    
    @staticmethod
    def get_billing_analytics(tenant, months=12):
        """
        Get billing analytics for tenant.
        
        Args:
            tenant (Tenant): Tenant to get analytics for
            months (int): Number of months to analyze
            
        Returns:
            dict: Billing analytics
        """
        from django.db.models import Sum
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            issue_date__gte=start_date,
            issue_date__lte=end_date
        ).order_by('issue_date')
        
        # Monthly revenue
        monthly_revenue = {}
        for invoice in invoices:
            month_key = invoice.issue_date.strftime('%Y-%m')
            if month_key not in monthly_revenue:
                monthly_revenue[month_key] = 0
            if invoice.status == 'paid':
                monthly_revenue[month_key] += float(invoice.total_amount)
        
        # Payment trends
        payment_trends = {
            'on_time': 0,
            'late': 0,
            'very_late': 0,
        }
        
        for invoice in invoices:
            if invoice.status == 'paid' and invoice.paid_date:
                days_late = (invoice.paid_date - invoice.due_date).days
                if days_late <= 0:
                    payment_trends['on_time'] += 1
                elif days_late <= 7:
                    payment_trends['late'] += 1
                else:
                    payment_trends['very_late'] += 1
        
        analytics = {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'months': months,
            },
            'revenue': {
                'total': sum(monthly_revenue.values()),
                'average': sum(monthly_revenue.values()) / len(monthly_revenue) if monthly_revenue else 0,
                'monthly_breakdown': monthly_revenue,
            },
            'payment_trends': payment_trends,
            'invoice_count': {
                'total': invoices.count(),
                'paid': invoices.filter(status='paid').count(),
                'overdue': invoices.filter(status='overdue').count(),
            },
        }
        
        return analytics
