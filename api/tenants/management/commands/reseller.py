"""
Reseller Management Commands

This module contains Django management commands for reseller operations
including reseller creation, commission management, and reporting.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.contrib.auth import get_user_model
import json
from datetime import datetime, timedelta

from ...models.reseller import ResellerConfig, ResellerInvoice
from ...models.core import Tenant
from ...services import ResellerService

User = get_user_model()


class Command(BaseCommand):
    """
    Management command for reseller operations.
    
    Provides commands for:
    - Creating reseller configurations
    - Managing reseller commissions
    - Generating reseller reports
    - Reseller analytics
    """
    
    help = 'Manage reseller operations including creation, commissions, and reporting'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        subparsers = parser.add_subparsers(dest='action', help='Available actions')
        
        # Create reseller
        create_parser = subparsers.add_parser('create', help='Create a new reseller')
        create_parser.add_argument('--tenant-id', type=int, required=True, help='Tenant ID')
        create_parser.add_argument('--company-name', type=str, required=True, help='Company name')
        create_parser.add_argument('--contact-person', type=str, help='Contact person')
        create_parser.add_argument('--contact-email', type=str, help='Contact email')
        create_parser.add_argument('--contact-phone', type=str, help='Contact phone')
        create_parser.add_argument('--commission-type', type=str, choices=['percentage', 'fixed', 'tiered', 'hybrid'], default='percentage', help='Commission type')
        create_parser.add_argument('--commission-pct', type=float, default=10.0, help='Commission percentage')
        create_parser.add_argument('--commission-fixed', type=float, default=0.0, help='Commission fixed amount')
        create_parser.add_argument('--max-tenants', type=int, default=100, help='Maximum tenants')
        create_parser.add_argument('--status', type=str, choices=['active', 'inactive', 'pending'], default='pending', help='Reseller status')
        
        # List resellers
        list_parser = subparsers.add_parser('list', help='List resellers')
        list_parser.add_argument('--status', type=str, choices=['active', 'inactive', 'pending', 'suspended'], help='Filter by status')
        list_parser.add_argument('--verified', type=bool, help='Filter by verification status')
        list_parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
        
        # Reseller info
        info_parser = subparsers.add_parser('info', help='Get reseller information')
        info_parser.add_argument('--reseller-id', type=int, help='Reseller ID')
        info_parser.add_argument('--tenant-id', type=int, help='Tenant ID')
        info_parser.add_argument('--reseller-id', type=str, help='Reseller ID')
        
        # Activate reseller
        activate_parser = subparsers.add_parser('activate', help='Activate a reseller')
        activate_parser.add_argument('--reseller-id', type=int, required=True, help='Reseller ID')
        activate_parser.add_argument('--user-id', type=int, help='User ID who is activating')
        
        # Deactivate reseller
        deactivate_parser = subparsers.add_parser('deactivate', help='Deactivate a reseller')
        deactivate_parser.add_argument('--reseller-id', type=int, required=True, help='Reseller ID')
        deactivate_parser.add_argument('--user-id', type=int, help='User ID who is deactivating')
        deactivate_parser.add_argument('--reason', type=str, help='Deactivation reason')
        
        # Calculate commissions
        commission_parser = subparsers.add_parser('calculate-commission', help='Calculate reseller commissions')
        commission_parser.add_argument('--reseller-id', type=int, help='Reseller ID')
        commission_parser.add_argument('--period', type=str, choices=['daily', 'weekly', 'monthly', 'yearly'], default='monthly', help='Commission period')
        commission_parser.add_argument('--create-invoice', type=bool, default=False, help='Create commission invoice')
        
        # Generate commission report
        report_parser = subparsers.add_parser('commission-report', help='Generate commission report')
        report_parser.add_argument('--reseller-id', type=int, help='Reseller ID')
        report_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
        report_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
        report_parser.add_argument('--format', type=str, choices=['table', 'json', 'csv'], default='table', help='Output format')
        
        # Reseller statistics
        stats_parser = subparsers.add_parser('stats', help='Get reseller statistics')
        stats_parser.add_argument('--reseller-id', type=int, help='Reseller ID')
        stats_parser.add_argument('--days', type=int, default=30, help='Number of days to analyze')
        stats_parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
        
        # Verify reseller
        verify_parser = subparsers.add_parser('verify', help='Verify a reseller')
        verify_parser.add_argument('--reseller-id', type=int, required=True, help='Reseller ID')
        verify_parser.add_argument('--user-id', type=int, help='User ID who is verifying')
        
        # Bulk operations
        bulk_parser = subparsers.add_parser('bulk', help='Bulk operations')
        bulk_subparsers = bulk_parser.add_subparsers(dest='bulk_action', help='Bulk actions')
        
        # Bulk calculate commissions
        bulk_commission_parser = bulk_subparsers.add_parser('calculate-commissions', help='Calculate commissions for all resellers')
        bulk_commission_parser.add_argument('--period', type=str, choices=['daily', 'weekly', 'monthly', 'yearly'], default='monthly', help='Commission period')
        bulk_commission_parser.add_argument('--create-invoices', type=bool, default=False, help='Create commission invoices')
        
        # Bulk generate reports
        bulk_report_parser = bulk_subparsers.add_parser('generate-reports', help='Generate reports for all resellers')
        bulk_report_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
        bulk_report_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
        bulk_report_parser.add_argument('--output-dir', type=str, help='Output directory for reports')
    
    def handle(self, *args, **options):
        """Handle the command."""
        action = options.get('action')
        
        if not action:
            raise CommandError('Action is required. Use --help to see available actions.')
        
        if action == 'create':
            self.create_reseller(options)
        elif action == 'list':
            self.list_resellers(options)
        elif action == 'info':
            self.get_reseller_info(options)
        elif action == 'activate':
            self.activate_reseller(options)
        elif action == 'deactivate':
            self.deactivate_reseller(options)
        elif action == 'calculate-commission':
            self.calculate_commission(options)
        elif action == 'commission-report':
            self.generate_commission_report(options)
        elif action == 'stats':
            self.get_reseller_statistics(options)
        elif action == 'verify':
            self.verify_reseller(options)
        elif action == 'bulk':
            self.handle_bulk_operations(options)
        else:
            raise CommandError(f'Unknown action: {action}')
    
    def create_reseller(self, options):
        """Create a new reseller configuration."""
        try:
            tenant_id = options['tenant_id']
            company_name = options['company_name']
            
            # Get tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id, is_deleted=False)
            except Tenant.DoesNotExist:
                raise CommandError(f'Tenant with ID {tenant_id} not found')
            
            # Prepare reseller data
            reseller_data = {
                'company_name': company_name,
                'contact_person': options.get('contact_person', ''),
                'contact_email': options.get('contact_email', ''),
                'contact_phone': options.get('contact_phone', ''),
                'commission_type': options.get('commission_type', 'percentage'),
                'commission_pct': options.get('commission_pct', 10.0),
                'commission_fixed': options.get('commission_fixed', 0.0),
                'max_tenants': options.get('max_tenants', 100),
                'status': options.get('status', 'pending')
            }
            
            # Create reseller
            reseller = ResellerService.create_reseller_config(tenant, reseller_data)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created reseller configuration for {company_name}'
                )
            )
            self.stdout.write(f'Reseller ID: {reseller.id}')
            self.stdout.write(f'Reseller Code: {reseller.reseller_id}')
            self.stdout.write(f'Status: {reseller.status}')
            
        except Exception as e:
            raise CommandError(f'Failed to create reseller: {str(e)}')
    
    def list_resellers(self, options):
        """List resellers with optional filtering."""
        try:
            queryset = ResellerConfig.objects.all()
            
            # Apply filters
            if options.get('status'):
                queryset = queryset.filter(status=options['status'])
            
            if options.get('verified') is not None:
                queryset = queryset.filter(is_verified=options['verified'])
            
            resellers = queryset.order_by('-created_at')
            
            if not resellers.exists():
                self.stdout.write(self.style.WARNING('No resellers found'))
                return
            
            output_format = options.get('format', 'table')
            
            if output_format == 'json':
                reseller_data = []
                for reseller in resellers:
                    reseller_data.append({
                        'id': reseller.id,
                        'reseller_id': reseller.reseller_id,
                        'company_name': reseller.company_name,
                        'contact_person': reseller.contact_person,
                        'contact_email': reseller.contact_email,
                        'status': reseller.status,
                        'is_verified': reseller.is_verified,
                        'commission_type': reseller.commission_type,
                        'max_tenants': reseller.max_tenants,
                        'created_at': reseller.created_at.isoformat()
                    })
                
                self.stdout.write(json.dumps(reseller_data, indent=2))
            else:
                # Table format
                self.stdout.write(self.style.SUCCESS('Resellers:'))
                self.stdout.write(f"{'ID':<5} {'Reseller ID':<15} {'Company Name':<25} {'Status':<10} {'Verified':<8} {'Commission':<12}")
                self.stdout.write('-' * 85)
                
                for reseller in resellers:
                    verified = 'Yes' if reseller.is_verified else 'No'
                    commission_info = f"{reseller.commission_type}"
                    if reseller.commission_type == 'percentage':
                        commission_info += f" ({reseller.commission_pct}%)"
                    
                    self.stdout.write(
                        f"{reseller.id:<5} {reseller.reseller_id:<15} {reseller.company_name:<25} "
                        f"{reseller.status:<10} {verified:<8} {commission_info:<12}"
                    )
            
        except Exception as e:
            raise CommandError(f'Failed to list resellers: {str(e)}')
    
    def get_reseller_info(self, options):
        """Get detailed information about a reseller."""
        try:
            reseller = None
            
            # Find reseller by ID or tenant ID
            if options.get('reseller_id'):
                reseller = ResellerConfig.objects.get(id=options['reseller_id'])
            elif options.get('tenant_id'):
                reseller = ResellerConfig.objects.get(parent_tenant_id=options['tenant_id'])
            else:
                raise CommandError('Either --reseller-id or --tenant-id is required')
            
            # Get reseller tenants
            tenants = ResellerService.get_reseller_tenants(reseller)
            
            # Calculate current commission
            commission_result = ResellerService.calculate_commission(reseller)
            
            # Get recent invoices
            recent_invoices = ResellerInvoice.objects.filter(
                reseller=reseller
            ).order_by('-issue_date')[:5]
            
            self.stdout.write(self.style.SUCCESS(f'Reseller Information: {reseller.company_name}'))
            self.stdout.write(f"{'ID':<15} {reseller.id}")
            self.stdout.write(f"{'Reseller ID':<15} {reseller.reseller_id}")
            self.stdout.write(f"{'Status':<15} {reseller.status}")
            self.stdout.write(f"{'Verified':<15} {'Yes' if reseller.is_verified else 'No'}")
            self.stdout.write(f"{'Contact Person':<15} {reseller.contact_person}")
            self.stdout.write(f"{'Contact Email':<15} {reseller.contact_email}")
            self.stdout.write(f"{'Commission Type':<15} {reseller.commission_type}")
            
            if reseller.commission_type == 'percentage':
                self.stdout.write(f"{'Commission Rate':<15} {reseller.commission_pct}%")
            elif reseller.commission_type == 'fixed':
                self.stdout.write(f"{'Commission Fixed':<15} ${reseller.commission_fixed}")
            
            self.stdout.write(f"{'Max Tenants':<15} {reseller.max_tenants}")
            self.stdout.write(f"{'Current Tenants':<15} {tenants.count()}")
            self.stdout.write(f"{'Total Revenue':<15} ${commission_result.get('total_revenue', 0):,.2f}")
            self.stdout.write(f"{'Commission Amount':<15} ${commission_result.get('commission_amount', 0):,.2f}")
            self.stdout.write(f"{'Created At':<15} {reseller.created_at.strftime('%Y-%m-%d %H:%M')}")
            
            if reseller.activated_at:
                self.stdout.write(f"{'Activated At':<15} {reseller.activated_at.strftime('%Y-%m-%d %H:%M')}")
            
            # Show recent invoices
            if recent_invoices.exists():
                self.stdout.write(self.style.SUCCESS('\nRecent Invoices:'))
                self.stdout.write(f"{'Invoice #':<15} {'Period':<10} {'Amount':<12} {'Status':<10} {'Issue Date':<12}")
                self.stdout.write('-' * 65)
                
                for invoice in recent_invoices:
                    self.stdout.write(
                        f"{invoice.invoice_number:<15} {invoice.period:<10} "
                        f"${invoice.commission_amount:<11.2f} {invoice.status:<10} "
                        f"{invoice.issue_date.strftime('%Y-%m-%d'):<12}"
                    )
            
        except ResellerConfig.DoesNotExist:
            raise CommandError('Reseller not found')
        except Exception as e:
            raise CommandError(f'Failed to get reseller info: {str(e)}')
    
    def activate_reseller(self, options):
        """Activate a reseller."""
        try:
            reseller_id = options['reseller_id']
            user_id = options.get('user_id')
            
            # Get reseller
            try:
                reseller = ResellerConfig.objects.get(id=reseller_id)
            except ResellerConfig.DoesNotExist:
                raise CommandError(f'Reseller with ID {reseller_id} not found')
            
            # Get user if provided
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    raise CommandError(f'User with ID {user_id} not found')
            
            # Activate reseller
            activated_reseller = ResellerService.activate_reseller(reseller, user)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully activated reseller: {activated_reseller.company_name}'
                )
            )
            self.stdout.write(f'Activated at: {activated_reseller.activated_at}')
            
        except Exception as e:
            raise CommandError(f'Failed to activate reseller: {str(e)}')
    
    def deactivate_reseller(self, options):
        """Deactivate a reseller."""
        try:
            reseller_id = options['reseller_id']
            user_id = options.get('user_id')
            reason = options.get('reason', 'Deactivated by admin')
            
            # Get reseller
            try:
                reseller = ResellerConfig.objects.get(id=reseller_id)
            except ResellerConfig.DoesNotExist:
                raise CommandError(f'Reseller with ID {reseller_id} not found')
            
            # Get user if provided
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    raise CommandError(f'User with ID {user_id} not found')
            
            # Deactivate reseller
            deactivated_reseller = ResellerService.deactivate_reseller(reseller, user, reason)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deactivated reseller: {deactivated_reseller.company_name}'
                )
            )
            self.stdout.write(f'Deactivated at: {deactivated_reseller.deactivated_at}')
            self.stdout.write(f'Reason: {deactivated_reseller.deactivation_reason}')
            
        except Exception as e:
            raise CommandError(f'Failed to deactivate reseller: {str(e)}')
    
    def calculate_commission(self, options):
        """Calculate commission for a reseller."""
        try:
            reseller_id = options.get('reseller_id')
            period = options.get('period', 'monthly')
            create_invoice = options.get('create_invoice', False)
            
            if reseller_id:
                # Calculate for specific reseller
                try:
                    reseller = ResellerConfig.objects.get(id=reseller_id)
                except ResellerConfig.DoesNotExist:
                    raise CommandError(f'Reseller with ID {reseller_id} not found')
                
                commission_result = ResellerService.calculate_commission(reseller, period)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Commission Calculation for {reseller.company_name}')
                )
                self.stdout.write(f"{'Period':<15} {period}")
                self.stdout.write(f"{'Total Revenue':<15} ${commission_result.get('total_revenue', 0):,.2f}")
                self.stdout.write(f"{'Commission Amount':<15} ${commission_result.get('commission_amount', 0):,.2f}")
                self.stdout.write(f"{'Commission Type':<15} {commission_result.get('commission_type', 'N/A')}")
                self.stdout.write(f"{'Tenant Count':<15} {commission_result.get('tenant_count', 0)}")
                
                if create_invoice:
                    invoice = ResellerService.create_commission_invoice(reseller, commission_result)
                    self.stdout.write(f"{'Invoice Created':<15} {invoice.invoice_number}")
            else:
                # Calculate for all resellers
                resellers = ResellerConfig.objects.filter(status='active')
                
                self.stdout.write(self.style.SUCCESS('Commission Calculation for All Active Resellers'))
                self.stdout.write(f"{'Reseller':<25} {'Revenue':<12} {'Commission':<12} {'Tenants':<8}")
                self.stdout.write('-' * 65)
                
                total_commission = 0
                for reseller in resellers:
                    commission_result = ResellerService.calculate_commission(reseller, period)
                    commission_amount = commission_result.get('commission_amount', 0)
                    total_commission += commission_amount
                    
                    self.stdout.write(
                        f"{reseller.company_name:<25} ${commission_result.get('total_revenue', 0):<11.2f} "
                        f"${commission_amount:<11.2f} {commission_result.get('tenant_count', 0):<8}"
                    )
                
                self.stdout.write('-' * 65)
                self.stdout.write(f"{'Total':<25} {'':<12} ${total_commission:<11.2f} {''}")
            
        except Exception as e:
            raise CommandError(f'Failed to calculate commission: {str(e)}')
    
    def generate_commission_report(self, options):
        """Generate commission report for resellers."""
        try:
            reseller_id = options.get('reseller_id')
            start_date = options.get('start_date')
            end_date = options.get('end_date')
            output_format = options.get('format', 'table')
            
            # Parse dates
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date = timezone.now().date() - timedelta(days=30)
            
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end_date = timezone.now().date()
            
            if reseller_id:
                # Generate report for specific reseller
                try:
                    reseller = ResellerConfig.objects.get(id=reseller_id)
                except ResellerConfig.DoesNotExist:
                    raise CommandError(f'Reseller with ID {reseller_id} not found')
                
                report = ResellerService.get_commission_report(reseller, start_date, end_date)
                
                if output_format == 'json':
                    self.stdout.write(json.dumps(report, indent=2, default=str))
                elif output_format == 'csv':
                    self._output_csv_report(report)
                else:
                    self._output_table_report(report)
            else:
                # Generate reports for all resellers
                resellers = ResellerConfig.objects.filter(status='active')
                
                if output_format == 'json':
                    reports = []
                    for reseller in resellers:
                        report = ResellerService.get_commission_report(reseller, start_date, end_date)
                        reports.append(report)
                    self.stdout.write(json.dumps(reports, indent=2, default=str))
                else:
                    for reseller in resellers:
                        report = ResellerService.get_commission_report(reseller, start_date, end_date)
                        self.stdout.write(self.style.SUCCESS(f'Report for {reseller.company_name}:'))
                        self._output_table_report(report)
                        self.stdout.write('\n' + '='*80 + '\n')
            
        except Exception as e:
            raise CommandError(f'Failed to generate commission report: {str(e)}')
    
    def get_reseller_statistics(self, options):
        """Get reseller statistics."""
        try:
            reseller_id = options.get('reseller_id')
            days = options.get('days', 30)
            output_format = options.get('format', 'table')
            
            if reseller_id:
                # Get statistics for specific reseller
                try:
                    reseller = ResellerConfig.objects.get(id=reseller_id)
                except ResellerConfig.DoesNotExist:
                    raise CommandError(f'Reseller with ID {reseller_id} not found')
                
                stats = ResellerService.get_reseller_statistics(reseller, days)
            else:
                # Get statistics for all resellers
                stats = ResellerService.get_reseller_statistics(days=days)
            
            if output_format == 'json':
                self.stdout.write(json.dumps(stats, indent=2, default=str))
            else:
                self._output_statistics_table(stats)
            
        except Exception as e:
            raise CommandError(f'Failed to get reseller statistics: {str(e)}')
    
    def verify_reseller(self, options):
        """Verify a reseller."""
        try:
            reseller_id = options['reseller_id']
            user_id = options.get('user_id')
            
            # Get reseller
            try:
                reseller = ResellerConfig.objects.get(id=reseller_id)
            except ResellerConfig.DoesNotExist:
                raise CommandError(f'Reseller with ID {reseller_id} not found')
            
            # Get user if provided
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    raise CommandError(f'User with ID {user_id} not found')
            
            # Verify reseller
            verified_reseller = ResellerService.verify_reseller(reseller, user)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully verified reseller: {verified_reseller.company_name}'
                )
            )
            self.stdout.write(f'Verified at: {verified_reseller.verified_at}')
            
        except Exception as e:
            raise CommandError(f'Failed to verify reseller: {str(e)}')
    
    def handle_bulk_operations(self, options):
        """Handle bulk operations."""
        bulk_action = options.get('bulk_action')
        
        if not bulk_action:
            raise CommandError('Bulk action is required')
        
        if bulk_action == 'calculate-commissions':
            self.bulk_calculate_commissions(options)
        elif bulk_action == 'generate-reports':
            self.bulk_generate_reports(options)
        else:
            raise CommandError(f'Unknown bulk action: {bulk_action}')
    
    def bulk_calculate_commissions(self, options):
        """Calculate commissions for all resellers."""
        try:
            period = options.get('period', 'monthly')
            create_invoices = options.get('create_invoices', False)
            
            resellers = ResellerConfig.objects.filter(status='active')
            
            self.stdout.write(self.style.SUCCESS(f'Calculating commissions for {resellers.count()} active resellers'))
            
            total_commission = 0
            invoices_created = 0
            
            for reseller in resellers:
                try:
                    commission_result = ResellerService.calculate_commission(reseller, period)
                    commission_amount = commission_result.get('commission_amount', 0)
                    total_commission += commission_amount
                    
                    if create_invoices:
                        invoice = ResellerService.create_commission_invoice(reseller, commission_result)
                        invoices_created += 1
                        self.stdout.write(f"  {reseller.company_name}: ${commission_amount:.2f} (Invoice: {invoice.invoice_number})")
                    else:
                        self.stdout.write(f"  {reseller.company_name}: ${commission_amount:.2f}")
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Error calculating commission for {reseller.company_name}: {str(e)}")
                    )
            
            self.stdout.write('-' * 50)
            self.stdout.write(f"Total Commission: ${total_commission:.2f}")
            if create_invoices:
                self.stdout.write(f"Invoices Created: {invoices_created}")
            
        except Exception as e:
            raise CommandError(f'Failed to bulk calculate commissions: {str(e)}')
    
    def bulk_generate_reports(self, options):
        """Generate reports for all resellers."""
        try:
            start_date = options.get('start_date')
            end_date = options.get('end_date')
            output_dir = options.get('output_dir')
            
            # Parse dates
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date = timezone.now().date() - timedelta(days=30)
            
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end_date = timezone.now().date()
            
            resellers = ResellerConfig.objects.filter(status='active')
            
            self.stdout.write(self.style.SUCCESS(f'Generating reports for {resellers.count()} active resellers'))
            
            for reseller in resellers:
                try:
                    report = ResellerService.get_commission_report(reseller, start_date, end_date)
                    
                    if output_dir:
                        # Save report to file
                        import os
                        filename = f"reseller_report_{reseller.reseller_id}_{start_date}_{end_date}.json"
                        filepath = os.path.join(output_dir, filename)
                        
                        with open(filepath, 'w') as f:
                            json.dump(report, f, indent=2, default=str)
                        
                        self.stdout.write(f"  Report saved: {filepath}")
                    else:
                        self.stdout.write(f"  {reseller.company_name}: ${report['total_commission']:.2f}")
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Error generating report for {reseller.company_name}: {str(e)}")
                    )
            
        except Exception as e:
            raise CommandError(f'Failed to bulk generate reports: {str(e)}')
    
    def _output_table_report(self, report):
        """Output report in table format."""
        self.stdout.write(f"{'Invoice #':<15} {'Period':<10} {'Revenue':<12} {'Commission':<12} {'Status':<10} {'Issue Date':<12}")
        self.stdout.write('-' * 75)
        
        for invoice in report['invoices']:
            self.stdout.write(
                f"{invoice['invoice_number']:<15} {invoice['period']:<10} "
                f"${invoice['total_revenue']:<11.2f} ${invoice['commission_amount']:<11.2f} "
                f"{invoice['status']:<10} {invoice['issue_date']:<12}"
            )
        
        self.stdout.write('-' * 75)
        self.stdout.write(f"{'Total':<15} {'':<10} ${report['total_revenue']:<11.2f} ${report['total_commission']:<11.2f} {'':<10} {'':<12}")
    
    def _output_csv_report(self, report):
        """Output report in CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Invoice #', 'Period', 'Revenue', 'Commission', 'Status', 'Issue Date'])
        
        # Write data
        for invoice in report['invoices']:
            writer.writerow([
                invoice['invoice_number'],
                invoice['period'],
                invoice['total_revenue'],
                invoice['commission_amount'],
                invoice['status'],
                invoice['issue_date']
            ])
        
        # Write totals
        writer.writerow(['Total', '', report['total_revenue'], report['total_commission'], '', ''])
        
        self.stdout.write(output.getvalue())
    
    def _output_statistics_table(self, stats):
        """Output statistics in table format."""
        self.stdout.write(self.style.SUCCESS('Reseller Statistics'))
        self.stdout.write(f"{'Period':<15} {stats['period']['start_date']} to {stats['period']['end_date']}")
        self.stdout.write(f"{'Total Resellers':<15} {stats['total_resellers']}")
        self.stdout.write(f"{'Active Resellers':<15} {stats['active_resellers']}")
        self.stdout.write(f"{'Verified Resellers':<15} {stats['verified_resellers']}")
        self.stdout.write(f"{'Pending Resellers':<15} {stats['pending_resellers']}")
        self.stdout.write(f"{'Total Tenants':<15} {stats['total_tenants']}")
        self.stdout.write(f"{'Total Revenue':<15} ${stats['total_revenue']:,.2f}")
        self.stdout.write(f"{'Total Commission':<15} ${stats['total_commission']:,.2f}")
        
        self.stdout.write('\nResellers by Status:')
        for status, count in stats['resellers_by_status'].items():
            self.stdout.write(f"  {status}: {count}")
        
        self.stdout.write('\nCommission by Type:')
        for commission_type, count in stats['commission_by_type'].items():
            self.stdout.write(f"  {commission_type}: {count}")
