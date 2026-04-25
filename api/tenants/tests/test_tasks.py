"""
Task Tests

This module contains unit tests for all Celery tasks including
billing tasks, metrics tasks, notification tasks, and other task classes.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
import json

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage
from ..models.analytics import TenantMetric, TenantHealthScore, TenantNotification
from ..tasks.billing import (
    generate_monthly_invoices, process_dunning_workflow,
    send_payment_reminders, calculate_commission_payments,
    process_subscription_renewals, cleanup_old_invoices,
    generate_billing_reports
)
from ..tasks.metrics import (
    collect_daily_metrics, collect_weekly_metrics, collect_monthly_metrics,
    calculate_health_scores, cleanup_old_metrics,
    generate_usage_analytics, track_api_usage, calculate_trends
)
from ..tasks.notifications import (
    send_onboarding_reminders, send_trial_expiry_notifications,
    send_quota_exceeded_notifications, send_security_alerts,
    process_email_queue, send_welcome_emails, cleanup_old_notifications
)
from ..tasks.maintenance import (
    cleanup_expired_api_keys, cleanup_expired_feature_flags,
    renew_ssl_certificates, backup_tenant_data, archive_audit_logs,
    cleanup_soft_deleted_tenants, optimize_database, update_system_statistics,
    check_data_integrity, cleanup_temp_files
)
from ..tasks.monitoring import (
    monitor_ssl_expiry, check_disk_usage, monitor_api_usage,
    generate_system_health_report, check_service_health,
    track_performance_metrics
)
from ..tasks.onboarding import (
    complete_onboarding_steps, send_welcome_emails,
    schedule_trial_extensions, send_progress_tips,
    cleanup_old_onboarding_data, generate_onboarding_analytics
)

User = get_user_model()


class TestBillingTasks(TestCase):
    """Test cases for billing tasks."""
    
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
    
    @patch('tenants.tasks.billing.TenantBillingService.generate_monthly_invoice')
    def test_generate_monthly_invoices(self, mock_generate_invoice):
        """Test monthly invoice generation task."""
        # Mock the service method
        mock_invoice = MagicMock()
        mock_invoice.invoice_number = 'INV-001'
        mock_invoice.total_amount = 29.99
        mock_generate_invoice.return_value = mock_invoice
        
        result = generate_monthly_invoices()
        
        self.assertIsInstance(result, dict)
        self.assertIn('generated_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        self.assertIn('total_tenants', result)
        
        # Verify service was called for active tenants
        self.assertEqual(mock_generate_invoice.call_count, 1)
    
    @patch('tenants.tasks.billing.TenantBillingService.handle_dunning')
    def test_process_dunning_workflow(self, mock_handle_dunning):
        """Test dunning workflow processing task."""
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
        
        result = process_dunning_workflow()
        
        self.assertIsInstance(result, dict)
        self.assertIn('processed_count', result)
        self.assertIn('suspended_count', result)
        self.assertIn('errors', result)
        
        # Verify service was called for overdue invoices
        self.assertEqual(mock_handle_dunning.call_count, 1)
    
    @patch('tenants.tasks.billing.TenantNotification.objects.create')
    def test_send_payment_reminders(self, mock_create_notification):
        """Test payment reminder sending task."""
        # Create invoice due soon
        due_soon_invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-DUE-SOON',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=3),
            total_amount=29.99,
        )
        
        result = send_payment_reminders()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify notification was created for due soon invoices
        self.assertGreater(mock_create_notification.call_count, 0)
    
    def test_cleanup_old_invoices(self):
        """Test old invoice cleanup task."""
        # Create old invoice
        old_date = timezone.now() - timedelta(days=400)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_invoice = TenantInvoice.objects.create(
                tenant=self.tenant,
                invoice_number='INV-OLD',
                status='paid',
                issue_date=old_date.date(),
                due_date=old_date.date() + timedelta(days=30),
                total_amount=29.99,
                paid_date=old_date.date(),
            )
        
        result = cleanup_old_invoices()
        
        self.assertIsInstance(result, dict)
        self.assertIn('archived_count', result)
        self.assertIn('deleted_count', result)
        self.assertIn('errors', result)
    
    @patch('tenants.tasks.billing.TenantBillingService.get_billing_summary')
    def test_generate_billing_reports(self, mock_get_summary):
        """Test billing report generation task."""
        # Mock the service method
        mock_summary = {
            'total_revenue': 1000.00,
            'total_invoices': 10,
            'paid_invoices': 8,
            'overdue_invoices': 2,
        }
        mock_get_summary.return_value = mock_summary
        
        result = generate_billing_reports()
        
        self.assertIsInstance(result, dict)
        self.assertIn('report_data', result)
        self.assertIn('generated_at', result)
        
        # Verify service was called
        mock_get_summary.assert_called_once()


class TestMetricsTasks(TestCase):
    """Test cases for metrics tasks."""
    
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
        for i in range(10):
            TenantMetric.objects.create(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i * 10,
                unit='count',
                date=timezone.now().date() - timedelta(days=i),
            )
    
    @patch('tenants.tasks.metrics.TenantMetricService.collect_daily_metrics')
    def test_collect_daily_metrics(self, mock_collect_metrics):
        """Test daily metrics collection task."""
        mock_collect_metrics.return_value = {
            'metrics_collected': 50,
            'tenants_processed': 5,
        }
        
        result = collect_daily_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['metrics_collected'], 50)
        self.assertEqual(result['tenants_processed'], 5)
        
        mock_collect_metrics.assert_called_once()
    
    @patch('tenants.tasks.metrics.TenantMetricService.collect_weekly_metrics')
    def test_collect_weekly_metrics(self, mock_collect_metrics):
        """Test weekly metrics collection task."""
        mock_collect_metrics.return_value = {
            'metrics_collected': 350,
            'tenants_processed': 5,
        }
        
        result = collect_weekly_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['metrics_collected'], 350)
        self.assertEqual(result['tenants_processed'], 5)
        
        mock_collect_metrics.assert_called_once()
    
    @patch('tenants.tasks.metrics.TenantMetricService.collect_monthly_metrics')
    def test_collect_monthly_metrics(self, mock_collect_metrics):
        """Test monthly metrics collection task."""
        mock_collect_metrics.return_value = {
            'metrics_collected': 1500,
            'tenants_processed': 5,
        }
        
        result = collect_monthly_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['metrics_collected'], 1500)
        self.assertEqual(result['tenants_processed'], 5)
        
        mock_collect_metrics.assert_called_once()
    
    @patch('tenants.tasks.metrics.TenantMetricService.calculate_health_scores')
    def test_calculate_health_scores(self, mock_calculate_scores):
        """Test health score calculation task."""
        mock_calculate_scores.return_value = {
            'calculated_count': 5,
            'failed_count': 0,
        }
        
        result = calculate_health_scores()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['calculated_count'], 5)
        self.assertEqual(result['failed_count'], 0)
        
        mock_calculate_scores.assert_called_once()
    
    def test_cleanup_old_metrics(self):
        """Test old metrics cleanup task."""
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
        
        result = cleanup_old_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('deleted_count', result)
        self.assertIn('errors', result)
    
    @patch('tenants.tasks.metrics.TenantMetricService.get_usage_analytics')
    def test_generate_usage_analytics(self, mock_get_analytics):
        """Test usage analytics generation task."""
        mock_analytics = {
            'total_api_calls': 10000,
            'average_daily_calls': 333,
            'peak_usage': 500,
        }
        mock_get_analytics.return_value = mock_analytics
        
        result = generate_usage_analytics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('analytics_data', result)
        self.assertIn('generated_at', result)
        
        mock_get_analytics.assert_called_once()
    
    @patch('tenants.tasks.metrics.TenantAuditService.log_action')
    def test_track_api_usage(self, mock_log_action):
        """Test API usage tracking task."""
        result = track_api_usage(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            endpoint='/api/v1/data/',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('logged', result)
        self.assertTrue(result['logged'])
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    def test_calculate_trends(self):
        """Test trends calculation task."""
        result = calculate_trends(
            metric_type='api_calls',
            days=30,
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('trend', result)
        self.assertIn('change_percentage', result)
        self.assertIn('data_points', result)
        self.assertIn('first_value', result)
        self.assertIn('last_value', result)


class TestNotificationTasks(TestCase):
    """Test cases for notification tasks."""
    
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
            trial_ends_at=timezone.now() + timedelta(days=1),
        )
    
    @patch('tenants.tasks.notifications.TenantNotification.objects.create')
    def test_send_trial_expiry_notifications(self, mock_create_notification):
        """Test trial expiry notification sending task."""
        result = send_trial_expiry_notifications()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify notification was created for expiring trials
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.tasks.notifications.TenantNotification.objects.create')
    def test_send_quota_exceeded_notifications(self, mock_create_notification):
        """Test quota exceeded notification sending task."""
        # Create usage that exceeds quota
        PlanUsage.objects.create(
            tenant=self.tenant,
            period='monthly',
            api_calls_used=1500,  # Exceeds 1000 limit
            api_calls_limit=1000,
            api_calls_percentage=150.0,
        )
        
        result = send_quota_exceeded_notifications()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        
        # Verify notification was created for quota exceeded
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.tasks.notifications.TenantNotification.objects.create')
    def test_send_security_alerts(self, mock_create_notification):
        """Test security alert sending task."""
        # Create security event
        from ..models.security import TenantAuditLog
        
        TenantAuditLog.objects.create(
            tenant=self.tenant,
            action='security_event',
            severity='high',
            description='Suspicious login attempt',
        )
        
        result = send_security_alerts()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        
        # Verify notification was created for security events
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.tasks.notifications.TenantEmailService.send_email')
    def test_process_email_queue(self, mock_send_email):
        """Test email queue processing task."""
        # Create pending notifications
        TenantNotification.objects.create(
            tenant=self.tenant,
            title='Test Notification',
            message='Test message',
            notification_type='system',
            status='pending',
            send_email=True,
        )
        
        result = process_email_queue()
        
        self.assertIsInstance(result, dict)
        self.assertIn('processed_count', result)
        self.assertIn('failed_count', result)
        
        # Verify email was sent
        self.assertGreater(mock_send_email.call_count, 0)
    
    @patch('tenants.tasks.notifications.TenantNotification.objects.create')
    def test_send_welcome_emails(self, mock_create_notification):
        """Test welcome email sending task."""
        result = send_welcome_emails()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        
        # Verify notification was created for welcome emails
        self.assertGreater(mock_create_notification.call_count, 0)
    
    def test_cleanup_old_notifications(self):
        """Test old notifications cleanup task."""
        # Create old notification
        old_date = timezone.now() - timedelta(days=100)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_notification = TenantNotification.objects.create(
                tenant=self.tenant,
                title='Old Notification',
                message='Old message',
                notification_type='system',
                status='sent',
            )
        
        result = cleanup_old_notifications()
        
        self.assertIsInstance(result, dict)
        self.assertIn('deleted_count', result)
        self.assertIn('errors', result)


class TestMaintenanceTasks(TestCase):
    """Test cases for maintenance tasks."""
    
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
    
    def test_cleanup_expired_api_keys(self):
        """Test expired API key cleanup task."""
        # Create expired API key
        from ..models.security import TenantAPIKey
        
        expired_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Expired Key',
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )
        
        result = cleanup_expired_api_keys()
        
        self.assertIsInstance(result, dict)
        self.assertIn('deactivated_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify key was deactivated
        expired_key.refresh_from_db()
        self.assertEqual(expired_key.status, 'expired')
    
    @patch('tenants.tasks.maintenance.DomainService.monitor_ssl_expiration')
    def test_renew_ssl_certificates(self, mock_monitor_ssl):
        """Test SSL certificate renewal task."""
        # Mock SSL monitoring
        mock_monitor_ssl.return_value = [
            {
                'domain': MagicMock(),
                'priority': 'critical',
                'days_until_expiry': 2,
            }
        ]
        
        result = renew_ssl_certificates()
        
        self.assertIsInstance(result, dict)
        self.assertIn('renewed_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        mock_monitor_ssl.assert_called_once()
    
    @patch('tenants.tasks.maintenance.TenantAuditService.log_action')
    def test_backup_tenant_data(self, mock_log_action):
        """Test tenant data backup task."""
        result = backup_tenant_data()
        
        self.assertIsInstance(result, dict)
        self.assertIn('backed_up_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify backup was logged
        self.assertGreater(mock_log_action.call_count, 0)
    
    def test_archive_audit_logs(self):
        """Test audit log archival task."""
        # Create old audit log
        from ..models.security import TenantAuditLog
        
        old_date = timezone.now() - timedelta(days=100)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_log = TenantAuditLog.objects.create(
                tenant=self.tenant,
                action='create',
                description='Old action',
                severity='low',
                created_at=old_date,
            )
        
        result = archive_audit_logs()
        
        self.assertIsInstance(result, dict)
        self.assertIn('archived_count', result)
        self.assertIn('errors', result)
    
    @patch('tenants.tasks.maintenance.TenantMetricService.get_tenant_metrics_summary')
    def test_update_system_statistics(self, mock_get_summary):
        """Test system statistics update task."""
        mock_summary = {
            'total_tenants': 10,
            'active_tenants': 8,
            'trial_tenants': 2,
        }
        mock_get_summary.return_value = mock_summary
        
        result = update_system_statistics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('statistics', result)
        self.assertIn('updated_at', result)
        
        mock_get_summary.assert_called_once()
    
    def test_check_data_integrity(self):
        """Test data integrity check task."""
        result = check_data_integrity()
        
        self.assertIsInstance(result, dict)
        self.assertIn('checks_completed', result)
        self.assertIn('issues_found', result)
        self.assertIn('issues_fixed', result)
        self.assertIn('check_results', result)


class TestMonitoringTasks(TestCase):
    """Test cases for monitoring tasks."""
    
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
    
    @patch('tenants.tasks.monitoring.DomainService.get_domain_health')
    def test_monitor_ssl_expiry(self, mock_get_health):
        """Test SSL expiry monitoring task."""
        # Create domain
        from ..models.branding import TenantDomain
        
        domain = TenantDomain.objects.create(
            tenant=self.tenant,
            domain='test.example.com',
            ssl_status='verified',
            ssl_expires_at=timezone.now() + timedelta(days=5),
        )
        
        # Mock health check
        mock_get_health.return_value = {
            'score': 85,
            'checks': {
                'ssl_certificate': {
                    'days_until_expiry': 5,
                    'status': 'valid',
                }
            }
        }
        
        result = monitor_ssl_expiry()
        
        self.assertIsInstance(result, dict)
        self.assertIn('monitored_count', result)
        self.assertIn('alerts_sent', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        mock_get_health.assert_called_once()
    
    def test_check_disk_usage(self):
        """Test disk usage monitoring task."""
        result = check_disk_usage()
        
        self.assertIsInstance(result, dict)
        self.assertIn('system_stats', result)
        self.assertIn('alerts_sent', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Check system stats
        stats = result['system_stats']
        self.assertIn('total_gb', stats)
        self.assertIn('used_gb', stats)
        self.assertIn('free_gb', stats)
        self.assertIn('usage_percent', stats)
    
    @patch('tenants.tasks.monitoring.TenantAuditService.log_action')
    def test_monitor_api_usage(self, mock_log_action):
        """Test API usage monitoring task."""
        # Create API access logs
        from ..models.security import TenantAuditLog
        
        for i in range(5):
            TenantAuditLog.objects.create(
                tenant=self.tenant,
                action='api_access',
                description=f'API call {i}',
                severity='low',
                metadata={'endpoint': f'/api/v1/endpoint{i}'},
            )
        
        result = monitor_api_usage()
        
        self.assertIsInstance(result, dict)
        self.assertIn('anomalies_detected', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify anomalies were detected
        self.assertGreater(mock_log_action.call_count, 0)
    
    def test_generate_system_health_report(self):
        """Test system health report generation task."""
        result = generate_system_health_report()
        
        self.assertIsInstance(result, dict)
        self.assertIn('timestamp', result)
        self.assertIn('period', result)
        self.assertIn('overall_health', result)
        self.assertIn('sections', result)
        
        # Check sections
        sections = result['sections']
        self.assertIn('system_resources', sections)
        self.assertIn('tenant_statistics', sections)
        self.assertIn('api_activity', sections)
        self.assertIn('database_performance', sections)
    
    @patch('tenants.tasks.monitoring.TenantNotification.objects.create')
    def test_check_service_health(self, mock_create_notification):
        """Test service health check task."""
        result = check_service_health()
        
        self.assertIsInstance(result, dict)
        self.assertIn('timestamp', result)
        self.assertIn('services', result)
        self.assertIn('overall_health', result)
        self.assertIn('errors', result)
        
        # Check services
        services = result['services']
        self.assertIn('database', services)
        self.assertIn('cache', services)
    
    def test_track_performance_metrics(self):
        """Test performance metrics tracking task."""
        result = track_performance_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('timestamp', result)
        self.assertIn('cpu_percent', result)
        self.assertIn('memory_percent', result)
        self.assertIn('disk_usage_percent', result)


class TestOnboardingTasks(TestCase):
    """Test cases for onboarding tasks."""
    
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
        
        # Create onboarding
        from ..models.onboarding import TenantOnboarding, TenantOnboardingStep
        
        self.onboarding = TenantOnboarding.objects.create(
            tenant=self.tenant,
            status='in_progress',
            current_step='profile_setup',
        )
        
        # Create onboarding steps
        for step_key in ['profile_setup', 'team_invitation', 'integration_setup']:
            TenantOnboardingStep.objects.create(
                tenant=self.tenant,
                step_key=step_key,
                step_type='manual',
                label=step_key.replace('_', ' ').title(),
                status='not_started',
                sort_order=1,
            )
    
    @patch('tenants.tasks.onboarding.TenantNotification.objects.create')
    def test_send_welcome_emails(self, mock_create_notification):
        """Test welcome email sending task."""
        # Complete onboarding
        self.onboarding.status = 'completed'
        self.onboarding.completed_at = timezone.now()
        self.onboarding.save()
        
        result = send_welcome_emails()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify notification was created
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.tasks.onboarding.TenantNotification.objects.create')
    def test_schedule_trial_extensions(self, mock_create_notification):
        """Test trial extension scheduling task."""
        # Set trial to expire soon
        self.tenant.trial_ends_at = timezone.now() + timedelta(days=2)
        self.tenant.save()
        
        # Create recent activity
        from ..models.security import TenantAuditLog
        
        for i in range(25):
            TenantAuditLog.objects.create(
                tenant=self.tenant,
                action='api_access',
                description=f'API call {i}',
                severity='low',
            )
        
        result = schedule_trial_extensions()
        
        self.assertIsInstance(result, dict)
        self.assertIn('scheduled_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify extension was scheduled
        self.assertGreater(mock_create_notification.call_count, 0)
    
    @patch('tenants.tasks.onboarding.TenantNotification.objects.create')
    def test_send_progress_tips(self, mock_create_notification):
        """Test progress tips sending task."""
        result = send_progress_tips()
        
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        self.assertIn('errors', result)
        
        # Verify tips were sent
        self.assertGreater(mock_create_notification.call_count, 0)
    
    def test_cleanup_old_onboarding_data(self):
        """Test old onboarding data cleanup task."""
        # Create old onboarding
        old_date = timezone.now() - timedelta(days=200)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_onboarding = TenantOnboarding.objects.create(
                tenant=self.tenant,
                status='completed',
                completed_at=old_date,
            )
        
        result = cleanup_old_onboarding_data()
        
        self.assertIsInstance(result, dict)
        self.assertIn('archived_count', result)
        self.assertIn('errors', result)
    
    @patch('tenants.tasks.onboarding.OnboardingService.get_onboarding_analytics')
    def test_generate_onboarding_analytics(self, mock_get_analytics):
        """Test onboarding analytics generation task."""
        mock_analytics = {
            'total_onboardings': 10,
            'completed_onboardings': 8,
            'average_completion_rate': 80.0,
        }
        mock_get_analytics.return_value = mock_analytics
        
        result = generate_onboarding_analytics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('analytics_data', result)
        self.assertIn('generated_at', result)
        
        mock_get_analytics.assert_called_once()
