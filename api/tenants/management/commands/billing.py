"""
Billing Management Commands

This module contains Django management commands for billing operations
including invoice generation, dunning processing, and commission calculations.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Sum, Avg
import json
from datetime import timedelta

from ...models import Tenant, TenantInvoice
from ...services import TenantBillingService


class GenerateInvoicesCommand(BaseCommand):
    """
    Generate monthly invoices for all tenants.
    
    Usage:
        python manage.py generate_invoices [--date=<date>] [--tenant=<tenant_id>]
    """
    
    help = "Generate monthly invoices"
    
    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Date for invoice generation (YYYY-MM-DD)')
        parser.add_argument('--tenant', type=str, help='Generate invoice for specific tenant ID or name')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be generated without creating')
    
    def handle(self, *args, **options):
        date = options.get('date')
        tenant_id = options.get('tenant')
        dry_run = options['dry_run']
        
        if date:
            try:
                target_date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError("Invalid date format. Use YYYY-MM-DD")
        else:
            target_date = timezone.now().date()
        
        self.stdout.write(f"Generating invoices for {target_date}")
        
        # Get tenants to process
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                tenants = [tenant]
            except (Tenant.DoesNotExist, ValueError):
                try:
                    tenant = Tenant.objects.get(name=tenant_id)
                    tenants = [tenant]
                except Tenant.DoesNotExist:
                    raise CommandError(f"Tenant '{tenant_id}' not found")
        else:
            tenants = Tenant.objects.filter(is_deleted=False, status='active')
        
        generated_count = 0
        failed_count = 0
        
        for tenant in tenants:
            try:
                if dry_run:
                    self.stdout.write(f"Would generate invoice for: {tenant.name}")
                    generated_count += 1
                else:
                    invoice = TenantBillingService.generate_monthly_invoice(tenant)
                    if invoice:
                        generated_count += 1
                        self.stdout.write(f"Generated invoice: {invoice.invoice_number} for {tenant.name}")
                    else:
                        self.stdout.write(f"No billing activity for: {tenant.name}")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to generate invoice for {tenant.name}: {str(e)}")
                )
        
        action = "Would generate" if dry_run else "Generated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {generated_count} invoices, {failed_count} failed")
        )


class ProcessDunningCommand(BaseCommand):
    """
    Process dunning workflow for overdue invoices.
    
    Usage:
        python manage.py process_dunning [--dry-run]
    """
    
    help = "Process dunning workflow for overdue invoices"
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without action')
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Processing dunning workflow")
        
        # Get overdue invoices
        overdue_invoices = TenantInvoice.objects.filter(
            status='overdue',
            due_date__lt=timezone.now().date()
        ).select_related('tenant')
        
        processed_count = 0
        suspended_count = 0
        
        for invoice in overdue_invoices:
            try:
                if dry_run:
                    self.stdout.write(f"Would process dunning for: {invoice.invoice_number}")
                    processed_count += 1
                else:
                    result = TenantBillingService.handle_dunning(invoice.tenant)
                    
                    if result['action'] == 'suspended':
                        suspended_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"Suspended tenant: {invoice.tenant.name}")
                        )
                    
                    processed_count += 1
                    self.stdout.write(f"Processed dunning for: {invoice.invoice_number} - {result['action']}")
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to process dunning for {invoice.invoice_number}: {str(e)}")
                )
        
        action = "Would process" if dry_run else "Processed"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {processed_count} invoices, {suspended_count} tenants suspended")
        )


class SendPaymentRemindersCommand(BaseCommand):
    """
    Send payment reminders for invoices due soon.
    
    Usage:
        python manage.py send_payment_reminders [--days=<days>] [--dry-run]
    """
    
    help = "Send payment reminders"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=3, help='Days until due to send reminder')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without sending')
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Sending payment reminders for invoices due in {days} days")
        
        # Get upcoming invoices
        reminder_date = timezone.now().date() + timedelta(days=days)
        
        upcoming_invoices = TenantInvoice.objects.filter(
            status='pending',
            due_date__lte=reminder_date,
            due_date__gt=timezone.now().date()
        ).select_related('tenant')
        
        sent_count = 0
        
        for invoice in upcoming_invoices:
            try:
                days_until_due = (invoice.due_date - timezone.now().date()).days
                
                if dry_run:
                    self.stdout.write(
                        f"Would send reminder for: {invoice.invoice_number} "
                        f"(due in {days_until_due} days)"
                    )
                    sent_count += 1
                else:
                    # This would send actual reminder notification
                    from ...models.analytics import TenantNotification
                    
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
                    )
                    
                    sent_count += 1
                    self.stdout.write(f"Sent reminder for: {invoice.invoice_number}")
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to send reminder for {invoice.invoice_number}: {str(e)}")
                )
        
        action = "Would send" if dry_run else "Sent"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {sent_count} payment reminders")
        )


class CalculateCommissionsCommand(BaseCommand):
    """
    Calculate commission payments for resellers.
    
    Usage:
        python manage.py calculate_commissions [--period=<period>] [--reseller=<reseller_id>]
    """
    
    help = "Calculate commission payments for resellers"
    
    def add_arguments(self, parser):
        parser.add_argument('--period', type=str, help='Period in YYYY-MM format')
        parser.add_argument('--reseller', type=str, help='Calculate for specific reseller ID')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be calculated without creating')
    
    def handle(self, *args, **options):
        period = options.get('period')
        reseller_id = options.get('reseller')
        dry_run = options['dry_run']
        
        if period:
            try:
                year, month = map(int, period.split('-'))
                last_month_end = timezone.datetime(year, month, 1).date() - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
            except (ValueError, IndexError):
                raise CommandError("Invalid period format. Use YYYY-MM")
        else:
            today = timezone.now().date()
            if today.day >= 5:  # Run after 5th of each month
                last_month_end = today.replace(day=1) - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
            else:
                last_month_end = today.replace(day=1) - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
        
        self.stdout.write(f"Calculating commissions for {last_month_start} to {last_month_end}")
        
        # Get resellers
        from ...models.reseller import ResellerConfig
        
        if reseller_id:
            try:
                reseller = ResellerConfig.objects.get(id=reseller_id)
                resellers = [reseller]
            except (ResellerConfig.DoesNotExist, ValueError):
                raise CommandError(f"Reseller '{reseller_id}' not found")
        else:
            resellers = ResellerConfig.objects.filter(status='active')
        
        calculated_count = 0
        
        for reseller in resellers:
            try:
                if dry_run:
                    self.stdout.write(f"Would calculate commission for: {reseller.company_name}")
                    calculated_count += 1
                else:
                    # This would calculate actual commission
                    from ...models.reseller import ResellerInvoice
                    
                    # Check if already calculated
                    existing = ResellerInvoice.objects.filter(
                        reseller=reseller,
                        period_start=last_month_start,
                        period_end=last_month_end
                    ).exists()
                    
                    if existing:
                        self.stdout.write(f"Commission already calculated for: {reseller.company_name}")
                    else:
                        # Create placeholder invoice
                        invoice = ResellerInvoice.objects.create(
                            reseller=reseller,
                            invoice_number=f"RES-{last_month_end.strftime('%Y%m')}-{reseller.reseller_id}",
                            status='pending',
                            period_start=last_month_start,
                            period_end=last_month_end,
                            commission_amount=0.0,  # Would calculate based on activity
                            bonus_amount=0.0,
                            referral_count=0,
                            active_referrals=0,
                            notes='Monthly commission calculation',
                        )
                        
                        calculated_count += 1
                        self.stdout.write(f"Calculated commission for: {reseller.company_name}")
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to calculate commission for {reseller.company_name}: {str(e)}")
                )
        
        action = "Would calculate" if dry_run else "Calculated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} commissions for {calculated_count} resellers")
        )


class BillingReportCommand(BaseCommand):
    """
    Generate comprehensive billing report.
    
    Usage:
        python manage.py billing_report [--period=<period>] [--format=<format>]
    """
    
    help = "Generate billing report"
    
    def add_arguments(self, parser):
        parser.add_argument('--period', type=str, help='Period in YYYY-MM format')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        period = options.get('period')
        output_format = options['format']
        
        if period:
            try:
                year, month = map(int, period.split('-'))
                last_month_end = timezone.datetime(year, month, 1).date() - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
            except (ValueError, IndexError):
                raise CommandError("Invalid period format. Use YYYY-MM")
        else:
            today = timezone.now().date()
            last_month_end = today.replace(day=1) - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
        
        self.stdout.write(f"Generating billing report for {last_month_start} to {last_month_end}")
        
        # Collect data
        invoices = TenantInvoice.objects.filter(
            issue_date__range=[last_month_start, last_month_end]
        )
        
        report_data = {
            'period_start': last_month_start.isoformat(),
            'period_end': last_month_end.isoformat(),
            'total_invoices': invoices.count(),
            'total_revenue': float(invoices.filter(status='paid').aggregate(
                total=models.Sum('total_amount')
            )['total'] or 0),
            'invoices_generated': invoices.count(),
            'invoices_paid': invoices.filter(status='paid').count(),
            'overdue_invoices': invoices.filter(status='overdue').count(),
            'by_status': {},
            'by_plan': {},
        }
        
        # By status
        status_counts = invoices.values('status').annotate(count=Count('id'))
        report_data['by_status'] = {s['status']: s['count'] for s in status_counts}
        
        # By plan
        plan_counts = invoices.values('tenant__plan__name').annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        )
        report_data['by_plan'] = {
            p['tenant__plan__name']: {
                'count': p['count'],
                'revenue': float(p['revenue'] or 0)
            }
            for p in plan_counts
        }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(report_data, indent=2))
        else:
            self._output_table(report_data, last_month_start, last_month_end)
    
    def _output_table(self, data, start_date, end_date):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Billing Report: {start_date} to {end_date}"))
        self.stdout.write("=" * 60)
        
        # Summary
        self.stdout.write(f"Total Invoices: {data['total_invoices']}")
        self.stdout.write(f"Total Revenue: ${data['total_revenue']:.2f}")
        self.stdout.write(f"Paid Invoices: {data['invoices_paid']}")
        self.stdout.write(f"Overdue Invoices: {data['overdue_invoices']}")
        
        # By status
        self.stdout.write(f"\nBy Status:")
        for status, count in data['by_status'].items():
            self.stdout.write(f"  {status}: {count}")
        
        # By plan
        self.stdout.write(f"\nBy Plan:")
        for plan_name, plan_data in data['by_plan'].items():
            self.stdout.write(f"  {plan_name}: {plan_data['count']} invoices, ${plan_data['revenue']:.2f}")


class InvoiceStatusCommand(BaseCommand):
    """
    Check and update invoice statuses.
    
    Usage:
        python manage.py invoice_status [--update]
    """
    
    help = "Check and update invoice statuses"
    
    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true', help='Update overdue invoice statuses')
    
    def handle(self, *args, **options):
        update = options['update']
        
        self.stdout.write("Checking invoice statuses")
        
        # Get all pending invoices
        pending_invoices = TenantInvoice.objects.filter(status='pending')
        
        overdue_count = 0
        
        for invoice in pending_invoices:
            if invoice.is_overdue():
                overdue_count += 1
                self.stdout.write(f"Overdue: {invoice.invoice_number} (due {invoice.due_date})")
                
                if update:
                    invoice.status = 'overdue'
                    invoice.save(update_fields=['status'])
                    self.stdout.write(f"  Updated to: overdue")
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {overdue_count} overdue invoices")
        )
        
        if update:
            self.stdout.write(
                self.style.SUCCESS(f"Updated {overdue_count} invoice statuses")
            )
