"""
Management Command Tests

This module contains unit tests for all Django management commands including
tenant commands, billing commands, metrics commands, and other command classes.
"""

from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from io import StringIO
import json
from datetime import timedelta

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage
from ..models.security import TenantAPIKey, TenantAuditLog
from ..models.analytics import TenantMetric, TenantHealthScore
from ..management.commands.tenants import (
    CreateTenantCommand, ListTenantsCommand, SuspendTenantCommand,
    UnsuspendTenantCommand, DeleteTenantCommand, TenantInfoCommand
)
from ..management.commands.billing import (
    GenerateInvoicesCommand, ProcessDunningCommand, SendPaymentRemindersCommand,
    CalculateCommissionsCommand, BillingReportCommand
)
from ..management.commands.metrics import (
    CollectMetricsCommand, CalculateHealthScoresCommand, CleanupOldMetricsCommand,
    GenerateUsageReportCommand, MetricSummaryCommand
)
from ..management.commands.security import (
    RotateAPIKeysCommand, CheckSecurityEventsCommand, GenerateSecurityReportCommand,
    SecurityScanCommand
)
from ..management.commands.analytics import (
    GenerateAnalyticsReportCommand, ExportTenantDataCommand, DataIntegrityCheckCommand
)

User = get_user_model()


class TestTenantCommands(TestCase):
    """Test cases for tenant management commands."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
            max_users=5,
            max_publishers=10,
            api_calls_per_day=1000,
            storage_gb=10,
        )
    
    def test_create_tenant_command(self):
        """Test create tenant command."""
        out = StringIO()
        
        call_command(
            'create_tenant',
            'Test Tenant',
            'test@example.com',
            '--plan', str(self.plan.id),
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Creating tenant: Test Tenant', output)
        self.assertIn('Tenant \'Test Tenant\' created successfully', output)
        
        # Verify tenant was created
        tenant = Tenant.objects.get(name='Test Tenant')
        self.assertEqual(tenant.owner, self.user)
        self.assertEqual(tenant.plan, self.plan)
    
    def test_create_tenant_command_with_options(self):
        """Test create tenant command with options."""
        out = StringIO()
        
        call_command(
            'create_tenant',
            'Advanced Tenant',
            'advanced@example.com',
            '--plan', str(self.plan.id),
            '--tier', 'professional',
            '--trial-days', '45',
            '--contact-email', 'contact@advanced.com',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Tenant \'Advanced Tenant\' created successfully', output)
        
        # Verify tenant was created with correct options
        tenant = Tenant.objects.get(name='Advanced Tenant')
        self.assertEqual(tenant.tier, 'professional')
        self.assertEqual(tenant.contact_email, 'contact@advanced.com')
    
    def test_create_tenant_command_invalid_user(self):
        """Test create tenant command with invalid user."""
        out = StringIO()
        
        with self.assertRaises(CommandError) as cm:
            call_command(
                'create_tenant',
                'Test Tenant',
                'nonexistent@example.com',
                '--plan', str(self.plan.id),
                stdout=out
            )
        
        self.assertIn('User with email \'nonexistent@example.com\' not found', str(cm.exception))
    
    def test_list_tenants_command(self):
        """Test list tenants command."""
        # Create multiple tenants
        for i in range(3):
            Tenant.objects.create(
                name=f'Tenant {i}',
                slug=f'tenant-{i}',
                owner=self.user,
                plan=self.plan,
            )
        
        out = StringIO()
        call_command('list_tenants', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Tenants:', output)
        self.assertIn('Tenant 0', output)
        self.assertIn('Tenant 1', output)
        self.assertIn('Tenant 2', output)
    
    def test_list_tenants_command_with_filter(self):
        """Test list tenants command with filter."""
        # Create tenants with different statuses
        Tenant.objects.create(
            name='Active Tenant',
            slug='active-tenant',
            owner=self.user,
            plan=self.plan,
            status='active',
        )
        
        Tenant.objects.create(
            name='Trial Tenant',
            slug='trial-tenant',
            owner=self.user,
            plan=self.plan,
            status='trial',
        )
        
        out = StringIO()
        call_command('list_tenants', '--status', 'active', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Active Tenant', output)
        self.assertNotIn('Trial Tenant', output)
    
    def test_list_tenants_command_json_format(self):
        """Test list tenants command with JSON format."""
        Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        out = StringIO()
        call_command('list_tenants', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Test Tenant')
    
    def test_suspend_tenant_command(self):
        """Test suspend tenant command."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        out = StringIO()
        call_command(
            'suspend_tenant',
            str(tenant.id),
            '--reason', 'Test suspension',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Suspending tenant: Test Tenant', output)
        self.assertIn('Tenant \'Test Tenant\' suspended successfully', output)
        
        # Verify tenant was suspended
        tenant.refresh_from_db()
        self.assertTrue(tenant.is_suspended)
        self.assertEqual(tenant.suspension_reason, 'Test suspension')
    
    def test_unsuspend_tenant_command(self):
        """Test unsuspend tenant command."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
            is_suspended=True,
            suspension_reason='Test',
        )
        
        out = StringIO()
        call_command('unsuspend_tenant', str(tenant.id), stdout=out)
        
        output = out.getvalue()
        self.assertIn('Unsuspending tenant: Test Tenant', output)
        self.assertIn('Tenant \'Test Tenant\' unsuspended successfully', output)
        
        # Verify tenant was unsuspended
        tenant.refresh_from_db()
        self.assertFalse(tenant.is_suspended)
        self.assertIsNone(tenant.suspension_reason)
    
    def test_delete_tenant_command(self):
        """Test delete tenant command."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        out = StringIO()
        call_command('delete_tenant', str(tenant.id), '--force', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Deleting tenant: Test Tenant', output)
        self.assertIn('Tenant \'Test Tenant\' deleted (soft delete)', output)
        
        # Verify tenant was soft deleted
        tenant.refresh_from_db()
        self.assertTrue(tenant.is_deleted)
        self.assertIsNotNone(tenant.deleted_at)
    
    def test_tenant_info_command(self):
        """Test tenant info command."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
            trial_ends_at=timezone.now() + timedelta(days=7),
        )
        
        out = StringIO()
        call_command('tenant_info', str(tenant.id), stdout=out)
        
        output = out.getvalue()
        self.assertIn('Tenant Information: Test Tenant', output)
        self.assertIn('ID:', output)
        self.assertIn('Slug: test-tenant', output)
        self.assertIn('Status: trial', output)
        self.assertIn('Plan: Basic Plan', output)
        self.assertIn('Owner:', output)
    
    def test_tenant_info_command_json_format(self):
        """Test tenant info command with JSON format."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        out = StringIO()
        call_command('tenant_info', str(tenant.id), '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertEqual(data['name'], 'Test Tenant')
        self.assertEqual(data['slug'], 'test-tenant')
        self.assertEqual(data['status'], 'trial')
        self.assertIn('plan', data)
        self.assertIn('owner', data)


class TestBillingCommands(TestCase):
    """Test cases for billing management commands."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
            status='active',
        )
        
        # Create billing
        self.billing = TenantBilling.objects.create(
            tenant=self.tenant,
            billing_cycle='monthly',
            payment_method='credit_card',
            base_price=29.99,
            final_price=29.99,
        )
    
    @patch('tenants.management.commands.billing.TenantBillingService.generate_monthly_invoice')
    def test_generate_invoices_command(self, mock_generate_invoice):
        """Test generate invoices command."""
        # Mock the service method
        mock_invoice = MagicMock()
        mock_invoice.invoice_number = 'INV-001'
        mock_invoice.total_amount = 29.99
        mock_generate_invoice.return_value = mock_invoice
        
        out = StringIO()
        call_command('generate_invoices', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Generating invoices for', output)
        self.assertIn('Generated invoice: INV-001 for Test Tenant', output)
        self.assertIn('Generated 1 invoices, 0 failed', output)
        
        mock_generate_invoice.assert_called_once()
    
    @patch('tenants.management.commands.billing.TenantBillingService.generate_monthly_invoice')
    def test_generate_invoices_command_dry_run(self, mock_generate_invoice):
        """Test generate invoices command with dry run."""
        out = StringIO()
        call_command('generate_invoices', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Would generate invoice for: Test Tenant', output)
        self.assertIn('Would generate 1 invoices, 0 failed', output)
        
        # Service should not be called in dry run
        mock_generate_invoice.assert_not_called()
    
    def test_generate_invoices_command_specific_tenant(self):
        """Test generate invoices command for specific tenant."""
        out = StringIO()
        
        with patch('tenants.management.commands.billing.TenantBillingService.generate_monthly_invoice') as mock_generate:
            mock_generate.return_value = MagicMock(invoice_number='INV-001')
            
            call_command(
                'generate_invoices',
                '--tenant', str(self.tenant.id),
                stdout=out
            )
            
            output = out.getvalue()
            self.assertIn('Would generate invoice for: Test Tenant', output)
            
            mock_generate.assert_called_once()
    
    @patch('tenants.management.commands.billing.TenantBillingService.handle_dunning')
    def test_process_dunning_command(self, mock_handle_dunning):
        """Test process dunning command."""
        # Create overdue invoice
        TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-OVERDUE',
            status='overdue',
            issue_date=timezone.now().date() - timedelta(days=40),
            due_date=timezone.now().date() - timedelta(days=10),
            total_amount=29.99,
        )
        
        # Mock the service method
        mock_handle_dunning.return_value = {'action': 'warning_sent'}
        
        out = StringIO()
        call_command('process_dunning', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing dunning workflow', output)
        self.assertIn('Processed dunning for: INV-OVERDUE - warning_sent', output)
        self.assertIn('Processed 1 invoices, 0 tenants suspended', output)
        
        mock_handle_dunning.assert_called_once()
    
    @patch('tenants.management.commands.billing.TenantNotification.objects.create')
    def test_send_payment_reminders_command(self, mock_create_notification):
        """Test send payment reminders command."""
        # Create invoice due soon
        TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-DUE-SOON',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=3),
            total_amount=29.99,
        )
        
        out = StringIO()
        call_command('send_payment_reminders', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Sending payment reminders for invoices due in 3 days', output)
        self.assertIn('Sent reminder for: INV-DUE-SOON', output)
        self.assertIn('Sent 1 payment reminders', output)
        
        # Verify notification was created
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.management.commands.billing.ResellerConfig.objects.filter')
    def test_calculate_commissions_command(self, mock_filter):
        """Test calculate commissions command."""
        # Mock reseller config
        mock_reseller = MagicMock()
        mock_reseller.company_name = 'Test Reseller'
        mock_filter.return_value = [mock_reseller]
        
        out = StringIO()
        call_command('calculate_commissions', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Calculating commissions for', output)
        self.assertIn('Calculated commission for: Test Reseller', output)
        self.assertIn('Calculated commissions for 1 resellers', output)
    
    def test_billing_report_command(self):
        """Test billing report command."""
        # Create some invoices
        for i in range(3):
            TenantInvoice.objects.create(
                tenant=self.tenant,
                invoice_number=f'INV-{i:03d}',
                status='paid' if i % 2 == 0 else 'pending',
                issue_date=timezone.now().date() - timedelta(days=i),
                due_date=timezone.now().date() + timedelta(days=30 - i),
                total_amount=29.99,
                paid_date=timezone.now().date() - timedelta(days=i) if i % 2 == 0 else None,
            )
        
        out = StringIO()
        call_command('billing_report', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Billing Report:', output)
        self.assertIn('Total Invoices: 3', output)
        self.assertIn('Paid Invoices: 2', output)
        self.assertIn('Overdue Invoices: 0', output)
    
    def test_billing_report_command_json_format(self):
        """Test billing report command with JSON format."""
        TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-001',
            status='paid',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            total_amount=29.99,
            paid_date=timezone.now().date(),
        )
        
        out = StringIO()
        call_command('billing_report', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIn('period_start', data)
        self.assertIn('period_end', data)
        self.assertIn('total_invoices', data)
        self.assertIn('total_revenue', data)


class TestMetricsCommands(TestCase):
    """Test cases for metrics management commands."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Create some metrics
        for i in range(5):
            TenantMetric.objects.create(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i * 10,
                unit='count',
                date=timezone.now().date() - timedelta(days=i),
            )
    
    @patch('tenants.management.commands.metrics.TenantMetricService.collect_daily_metrics')
    def test_collect_metrics_command(self, mock_collect_metrics):
        """Test collect metrics command."""
        mock_collect_metrics.return_value = {
            'metrics_collected': 50,
            'tenants_processed': 5,
        }
        
        out = StringIO()
        call_command('collect_metrics', '--type', 'daily', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Collecting daily metrics for', output)
        self.assertIn('Collected daily metrics for: Test Tenant', output)
        self.assertIn('Collected daily metrics for 1 tenants, 0 failed', output)
        
        mock_collect_metrics.assert_called_once()
    
    @patch('tenants.management.commands.metrics.TenantMetricService.collect_weekly_metrics')
    def test_collect_metrics_command_weekly(self, mock_collect_metrics):
        """Test collect metrics command for weekly type."""
        mock_collect_metrics.return_value = {
            'metrics_collected': 350,
            'tenants_processed': 5,
        }
        
        out = StringIO()
        call_command('collect_metrics', '--type', 'weekly', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Collecting weekly metrics for', output)
        self.assertIn('Collected weekly metrics for 1 tenants, 0 failed', output)
        
        mock_collect_metrics.assert_called_once()
    
    @patch('tenants.management.commands.metrics.TenantMetricService.calculate_health_scores')
    def test_calculate_health_scores_command(self, mock_calculate_scores):
        """Test calculate health scores command."""
        mock_calculate_scores.return_value = {
            'calculated_count': 5,
            'failed_count': 0,
        }
        
        out = StringIO()
        call_command('calculate_health_scores', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Calculating health scores', output)
        self.assertIn('Calculated health score for: Test Tenant (B)', output)
        self.assertIn('Calculated health scores for 1 tenants, 0 failed', output)
        
        mock_calculate_scores.assert_called_once()
    
    def test_cleanup_old_metrics_command(self):
        """Test cleanup old metrics command."""
        # Create old metric
        old_date = timezone.now() - timedelta(days=400)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_metric = TenantMetric.objects.create(
                tenant=self.tenant,
                metric_type='old_metric',
                value=100,
                unit='count',
                date=old_date.date(),
            )
        
        out = StringIO()
        call_command('cleanup_old_metrics', '--days', '365', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Cleaning up metrics older than 365 days', output)
        self.assertIn('Deleted 1 old metrics', output)
        self.assertIn('Cleanup completed (cutoff date:', output)
    
    def test_generate_usage_report_command(self):
        """Test generate usage report command."""
        out = StringIO()
        call_command('generate_usage_report', '--days', '30', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Generating monthly usage report for last 30 days', output)
        self.assertIn('Usage Report:', output)
        self.assertIn('Period: monthly (30 days)', output)
        self.assertIn('Total Tenants: 1', output)
        self.assertIn('Active Tenants: 1', output)
    
    def test_metric_summary_command(self):
        """Test metric summary command."""
        out = StringIO()
        call_command('metric_summary', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Generating metrics summary', output)
        self.assertIn('Metrics Summary', output)
        self.assertIn('Type', output)
        self.assertIn('Count', output)
        self.assertIn('Avg', output)
    
    def test_metric_summary_command_json_format(self):
        """Test metric summary command with JSON format."""
        out = StringIO()
        call_command('metric_summary', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIn('api_calls', data)
        self.assertIn('count', data['api_calls'])
        self.assertIn('avg_value', data['api_calls'])


class TestSecurityCommands(TestCase):
    """Test cases for security management commands."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Create API key
        self.api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Test API Key',
            scopes=['read', 'write'],
            rate_limit_per_minute=60,
        )
    
    def test_rotate_api_keys_command(self):
        """Test rotate API keys command."""
        # Create expired API key
        expired_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Expired Key',
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )
        
        out = StringIO()
        call_command('rotate_api_keys', '--days', '0', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Rotating API keys older than 0 days', output)
        self.assertIn('Rotated key: Expired Key (Test Tenant)', output)
        self.assertIn('Rotated 1 API keys, 0 failed', output)
        
        # Verify key was rotated
        expired_key.refresh_from_db()
        self.assertEqual(expired_key.status, 'active')  # Should be reactivated with new key
    
    def test_rotate_api_keys_command_dry_run(self):
        """Test rotate API keys command with dry run."""
        out = StringIO()
        call_command('rotate_api_keys', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Would rotate key: Test API Key (Test Tenant)', output)
        self.assertIn('Would rotate 2 API keys, 0 failed', output)
    
    @patch('tenants.management.commands.security.TenantAuditLog.objects.filter')
    def test_check_security_events_command(self, mock_filter):
        """Test check security events command."""
        # Mock security events
        mock_event = MagicMock()
        mock_event.tenant = self.tenant
        mock_event.action = 'security_event'
        mock_event.severity = 'high'
        mock_event.description = 'Suspicious activity'
        mock_filter.return_value = [mock_event]
        
        out = StringIO()
        call_command('check_security_events', '--hours', '24', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking security events for last 24 hours', output)
        self.assertIn('Security Events Report:', output)
        self.assertIn('Total Events: 1', output)
        self.assertIn('Affected Tenants: 1', output)
    
    def test_check_security_events_command_json_format(self):
        """Test check security events command with JSON format."""
        out = StringIO()
        call_command('check_security_events', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIn('period_hours', data)
        self.assertIn('total_events', data)
        self.assertIn('events_by_severity', data)
    
    @patch('tenants.management.commands.security.TenantAPIKey.objects.filter')
    @patch('tenants.management.commands.security.TenantAuditLog.objects.filter')
    def test_generate_security_report_command(self, mock_audit_filter, mock_api_filter):
        """Test generate security report command."""
        # Mock data
        mock_api_filter.return_value.count.return_value = 10
        mock_api_filter.return_value.filter.return_value.count.return_value = 2
        mock_audit_filter.return_value.count.return_value = 50
        mock_audit_filter.return_value.filter.return_value.count.return_value = 5
        
        out = StringIO()
        call_command('generate_security_report', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Generating security report for last 30 days', output)
        self.assertIn('Security Report:', output)
        self.assertIn('API Keys:', output)
        self.assertIn('Total: 10', output)
        self.assertIn('Expired: 2', output)
    
    @patch('tenants.management.commands.security.psutil')
    def test_security_scan_command(self, mock_psutil):
        """Test security scan command."""
        # Mock system resources
        mock_psutil.disk_usage.return_value.used = 1000000000  # 1GB
        mock_psutil.disk_usage.return_value.total = 10000000000  # 10GB
        mock_psutil.virtual_memory.return_value.percent = 50
        mock_psutil.cpu_percent.return_value = 25
        
        # Mock API keys
        with patch('tenants.management.commands.security.TenantAPIKey.objects.filter') as mock_filter:
            mock_filter.return_value.count.return_value = 10
            mock_filter.return_value.filter.return_value.count.return_value = 2
            
            out = StringIO()
            call_command('security_scan', stdout=out)
            
            output = out.getvalue()
            self.assertIn('Performing security scan', output)
            self.assertIn('Security Scan Results:', output)
            self.assertIn('Overall Security Score:', output)
            self.assertIn('API Keys: 10 total, 2 expired', output)


class TestAnalyticsCommands(TestCase):
    """Test cases for analytics management commands."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Create some metrics
        for i in range(5):
            TenantMetric.objects.create(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i * 10,
                unit='count',
                date=timezone.now().date() - timedelta(days=i),
            )
    
    def test_generate_analytics_report_command(self):
        """Test generate analytics report command."""
        out = StringIO()
        call_command('generate_analytics_report', '--days', '30', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Generating monthly analytics report for last 30 days', output)
        self.assertIn('Analytics Report:', output)
        self.assertIn('Tenant Metrics:', output)
        self.assertIn('Total: 1', output)
        self.assertIn('Active: 1', output)
    
    def test_generate_analytics_report_command_json_format(self):
        """Test generate analytics report command with JSON format."""
        out = StringIO()
        call_command('generate_analytics_report', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIn('period', data)
        self.assertIn('start_date', data)
        self.assertIn('end_date', data)
        self.assertIn('tenant_metrics', data)
    
    def test_export_tenant_data_command(self):
        """Test export tenant data command."""
        out = StringIO()
        call_command('export_tenant_data', str(self.tenant.id), stdout=out)
        
        output = out.getvalue()
        self.assertIn('Exporting data for tenant: Test Tenant', output)
        self.assertIn('Exported tenant data to', output)
        
        # Check if file was created
        self.assertTrue(output.endswith('.json') or output.endswith('.csv'))
    
    def test_export_tenant_data_command_json_format(self):
        """Test export tenant data command with JSON format."""
        out = StringIO()
        call_command('export_tenant_data', str(self.tenant.id), '--format', 'json', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Exported tenant data to', output)
        self.assertTrue(output.endswith('.json'))
    
    def test_import_tenant_data_command(self):
        """Test import tenant data command."""
        # Create export file first
        export_out = StringIO()
        call_command('export_tenant_data', str(self.tenant.id), '--format', 'json', stdout=export_out)
        
        # Get the filename from output
        export_output = export_out.getvalue()
        filename = export_output.split('Exported tenant data to ')[1].strip()
        
        # Now import it
        import_out = StringIO()
        call_command('import_tenant_data', filename, stdout=import_out)
        
        import_output = import_out.getvalue()
        self.assertIn('Importing tenant data from:', import_output)
    
    def test_import_tenant_data_command_dry_run(self):
        """Test import tenant data command with dry run."""
        # Create export file first
        export_out = StringIO()
        call_command('export_tenant_data', str(self.tenant.id), '--format', 'json', stdout=export_out)
        
        # Get the filename from output
        export_output = export_out.getvalue()
        filename = export_output.split('Exported tenant data to ')[1].strip()
        
        # Now import it with dry run
        import_out = StringIO()
        call_command('import_tenant_data', filename, '--dry-run', stdout=import_out)
        
        import_output = import_out.getvalue()
        self.assertIn('Would import tenant:', import_output)
    
    def test_data_integrity_check_command(self):
        """Test data integrity check command."""
        out = StringIO()
        call_command('data_integrity_check', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking data integrity', output)
        self.assertIn('Data Integrity Check', output)
        self.assertIn('Issues Found:', output)
        self.assertIn('Check Results:', output)
    
    def test_data_integrity_check_command_with_fix(self):
        """Test data integrity check command with fix."""
        # Create orphaned metric (without tenant)
        orphaned_metric = TenantMetric.objects.create(
            tenant=None,  # This will cause integrity issue
            metric_type='orphaned',
            value=100,
            unit='count',
            date=timezone.now().date(),
        )
        
        out = StringIO()
        call_command('data_integrity_check', '--fix', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking data integrity', output)
        self.assertIn('Issues Found:', output)
        self.assertIn('Issues Fixed:', output)
    
    def test_data_integrity_check_command_json_format(self):
        """Test data integrity check command with JSON format."""
        out = StringIO()
        call_command('data_integrity_check', '--format', 'json', stdout=out)
        
        output = out.getvalue()
        data = json.loads(output)
        self.assertIn('timestamp', data)
        self.assertIn('issues_found', data)
        self.assertIn('issues_fixed', data)
        self.assertIn('checks', data)
