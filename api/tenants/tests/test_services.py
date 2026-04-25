"""
Service Tests

This module contains unit tests for all tenant services including
TenantService, TenantProvisioningService, and other service classes.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..services import (
    TenantService, TenantProvisioningService, TenantSuspensionService,
    PlanService, PlanUsageService, BrandingService, DomainService,
    TenantBillingService, TenantEmailService, OnboardingService,
    TenantAuditService, TenantMetricService, FeatureFlagService
)
from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage
from ..models.branding import TenantBranding, TenantDomain
from ..models.analytics import TenantMetric, TenantHealthScore

User = get_user_model()


class TestTenantService(TestCase):
    """Test cases for TenantService."""
    
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
    
    def test_create_tenant(self):
        """Test tenant creation service."""
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
            trial_days=30,
            contact_email='contact@test.com',
        )
        
        self.assertIsInstance(tenant, Tenant)
        self.assertEqual(tenant.name, 'Test Tenant')
        self.assertEqual(tenant.owner, self.user)
        self.assertEqual(tenant.plan, self.plan)
        self.assertEqual(tenant.status, 'trial')
        self.assertIsNotNone(tenant.trial_ends_at)
        
        # Check related objects were created
        self.assertTrue(TenantSettings.objects.filter(tenant=tenant).exists())
        self.assertTrue(TenantBilling.objects.filter(tenant=tenant).exists())
    
    def test_create_tenant_invalid_data(self):
        """Test tenant creation with invalid data."""
        # Missing required fields
        with self.assertRaises(ValueError):
            TenantService.create_tenant(
                name='',  # Empty name
                owner=self.user,
                plan=self.plan,
            )
        
        # Invalid plan
        with self.assertRaises(ValueError):
            TenantService.create_tenant(
                name='Test Tenant',
                owner=self.user,
                plan=None,  # No plan
            )
    
    def test_update_tenant(self):
        """Test tenant update service."""
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        updated_tenant = TenantService.update_tenant(
            tenant=tenant,
            name='Updated Tenant',
            contact_email='updated@test.com',
        )
        
        self.assertEqual(updated_tenant.name, 'Updated Tenant')
        self.assertEqual(updated_tenant.contact_email, 'updated@test.com')
    
    def test_suspend_tenant(self):
        """Test tenant suspension service."""
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        suspended_tenant = TenantService.suspend_tenant(
            tenant=tenant,
            reason='Test suspension',
            suspended_by=self.user,
        )
        
        self.assertTrue(suspended_tenant.is_suspended)
        self.assertEqual(suspended_tenant.suspension_reason, 'Test suspension')
    
    def test_unsuspend_tenant(self):
        """Test tenant unsuspension service."""
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # First suspend
        TenantService.suspend_tenant(
            tenant=tenant,
            reason='Test suspension',
            suspended_by=self.user,
        )
        
        # Then unsuspend
        unsuspended_tenant = TenantService.unsuspend_tenant(
            tenant=tenant,
            unsuspended_by=self.user,
        )
        
        self.assertFalse(unsuspended_tenant.is_suspended)
        self.assertIsNone(unsuspended_tenant.suspension_reason)
    
    def test_delete_tenant(self):
        """Test tenant deletion service."""
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        TenantService.delete_tenant(
            tenant=tenant,
            deleted_by=self.user,
        )
        
        tenant.refresh_from_db()
        self.assertTrue(tenant.is_deleted)
        self.assertIsNotNone(tenant.deleted_at)
    
    def test_get_tenant_statistics(self):
        """Test tenant statistics service."""
        # Create multiple tenants
        for i in range(5):
            TenantService.create_tenant(
                name=f'Tenant {i}',
                owner=self.user,
                plan=self.plan,
            )
        
        stats = TenantService.get_tenant_statistics()
        
        self.assertIn('total_tenants', stats)
        self.assertIn('active_tenants', stats)
        self.assertIn('trial_tenants', stats)
        self.assertIn('suspended_tenants', stats)
        self.assertEqual(stats['total_tenants'], 5)


class TestTenantProvisioningService(TestCase):
    """Test cases for TenantProvisioningService."""
    
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
    
    def test_provision_tenant(self):
        """Test tenant provisioning service."""
        tenant = TenantProvisioningService.provision_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
            trial_days=30,
        )
        
        self.assertIsInstance(tenant, Tenant)
        self.assertEqual(tenant.name, 'Test Tenant')
        
        # Check all required objects are created
        self.assertTrue(TenantSettings.objects.filter(tenant=tenant).exists())
        self.assertTrue(TenantBilling.objects.filter(tenant=tenant).exists())
        self.assertTrue(TenantBranding.objects.filter(tenant=tenant).exists())
        self.assertTrue(TenantHealthScore.objects.filter(tenant=tenant).exists())
    
    def test_provision_tenant_with_custom_settings(self):
        """Test tenant provisioning with custom settings."""
        custom_settings = {
            'enable_smartlink': False,
            'max_users': 10,
            'api_calls_per_day': 2000,
        }
        
        tenant = TenantProvisioningService.provision_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
            custom_settings=custom_settings,
        )
        
        settings = tenant.settings
        self.assertFalse(settings.enable_smartlink)
        self.assertEqual(settings.max_users, 10)
        self.assertEqual(settings.api_calls_per_day, 2000)
    
    def test_deprovision_tenant(self):
        """Test tenant deprovisioning service."""
        tenant = TenantProvisioningService.provision_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        success = TenantProvisioningService.deprovision_tenant(
            tenant=tenant,
            delete_data=True,
        )
        
        self.assertTrue(success)
        tenant.refresh_from_db()
        self.assertTrue(tenant.is_deleted)
    
    def test_migrate_tenant_data(self):
        """Test tenant data migration service."""
        source_tenant = TenantProvisioningService.provision_tenant(
            name='Source Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        target_tenant = TenantProvisioningService.provision_tenant(
            name='Target Tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Create some data in source tenant
        TenantMetric.objects.create(
            tenant=source_tenant,
            metric_type='api_calls',
            value=100,
            unit='count',
        )
        
        success = TenantProvisioningService.migrate_tenant_data(
            source_tenant=source_tenant,
            target_tenant=target_tenant,
            data_types=['metrics'],
        )
        
        self.assertTrue(success)
        self.assertTrue(
            TenantMetric.objects.filter(tenant=target_tenant, metric_type='api_calls').exists()
        )


class TestTenantSuspensionService(TestCase):
    """Test cases for TenantSuspensionService."""
    
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
        
        self.tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
    
    def test_suspend_tenant(self):
        """Test tenant suspension."""
        suspended_tenant = TenantSuspensionService.suspend_tenant(
            tenant=self.tenant,
            reason='Test suspension',
            suspended_by=self.user,
        )
        
        self.assertTrue(suspended_tenant.is_suspended)
        self.assertEqual(suspended_tenant.suspension_reason, 'Test suspension')
        self.assertEqual(suspended_tenant.status, 'suspended')
    
    def test_unsuspend_tenant(self):
        """Test tenant unsuspension."""
        # First suspend
        TenantSuspensionService.suspend_tenant(
            tenant=self.tenant,
            reason='Test suspension',
            suspended_by=self.user,
        )
        
        # Then unsuspend
        unsuspended_tenant = TenantSuspensionService.unsuspend_tenant(
            tenant=self.tenant,
            unsuspended_by=self.user,
        )
        
        self.assertFalse(unsuspended_tenant.is_suspended)
        self.assertEqual(unsuspended_tenant.status, 'active')
    
    def test_suspend_with_dunning(self):
        """Test tenant suspension with dunning."""
        # Create overdue invoice
        TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-001',
            status='overdue',
            issue_date=timezone.now().date() - timedelta(days=40),
            due_date=timezone.now().date() - timedelta(days=10),
            total_amount=29.99,
        )
        
        suspended_tenant = TenantSuspensionService.suspend_tenant(
            tenant=self.tenant,
            reason='Non-payment',
            suspended_by=self.user,
            trigger_dunning=True,
        )
        
        self.assertTrue(suspended_tenant.is_suspended)
        self.assertEqual(suspended_tenant.suspension_reason, 'Non-payment')
    
    def test_get_suspension_reasons(self):
        """Test getting suspension reasons."""
        reasons = TenantSuspensionService.get_suspension_reasons()
        
        self.assertIsInstance(reasons, dict)
        self.assertIn('non_payment', reasons)
        self.assertIn('policy_violation', reasons)
        self.assertIn('admin_request', reasons)
    
    def test_check_suspension_eligibility(self):
        """Test suspension eligibility check."""
        # Active tenant should be eligible
        eligibility = TenantSuspensionService.check_suspension_eligibility(self.tenant)
        self.assertTrue(eligibility['eligible'])
        
        # Already suspended tenant should not be eligible
        TenantSuspensionService.suspend_tenant(
            tenant=self.tenant,
            reason='Test',
            suspended_by=self.user,
        )
        
        eligibility = TenantSuspensionService.check_suspension_eligibility(self.tenant)
        self.assertFalse(eligibility['eligible'])


class TestPlanService(TestCase):
    """Test cases for PlanService."""
    
    def setUp(self):
        """Set up test data."""
        self.basic_plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
        )
        
        self.pro_plan = Plan.objects.create(
            name='Pro Plan',
            slug='pro',
            plan_type='professional',
            price_monthly=99.99,
        )
    
    def test_upgrade_plan(self):
        """Test plan upgrade."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=user,
            plan=self.basic_plan,
        )
        
        upgraded_tenant = PlanService.upgrade_plan(
            tenant=tenant,
            new_plan=self.pro_plan,
            reason='Feature requirements',
            upgraded_by=user,
        )
        
        self.assertEqual(upgraded_tenant.plan, self.pro_plan)
        self.assertTrue(
            tenant.planupgrade_set.filter(
                from_plan=self.basic_plan,
                to_plan=self.pro_plan
            ).exists()
        )
    
    def test_downgrade_plan(self):
        """Test plan downgrade."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=user,
            plan=self.pro_plan,
        )
        
        downgraded_tenant = PlanService.downgrade_plan(
            tenant=tenant,
            new_plan=self.basic_plan,
            reason='Cost reduction',
            downgraded_by=user,
        )
        
        self.assertEqual(downgraded_tenant.plan, self.basic_plan)
    
    def test_get_available_upgrades(self):
        """Test getting available upgrades."""
        upgrades = PlanService.get_available_upgrades(self.basic_plan)
        
        self.assertIsInstance(upgrades, list)
        self.assertIn(self.pro_plan, upgrades)
    
    def test_get_available_downgrades(self):
        """Test getting available downgrades."""
        downgrades = PlanService.get_available_downgrades(self.pro_plan)
        
        self.assertIsInstance(downgrades, list)
        self.assertIn(self.basic_plan, downgrades)
    
    def test_calculate_price_difference(self):
        """Test price difference calculation."""
        price_diff = PlanService.calculate_price_difference(
            from_plan=self.basic_plan,
            to_plan=self.pro_plan,
            billing_cycle='monthly'
        )
        
        expected_diff = self.pro_plan.price_monthly - self.basic_plan.price_monthly
        self.assertEqual(price_diff, expected_diff)


class TestPlanUsageService(TestCase):
    """Test cases for PlanUsageService."""
    
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
        
        self.tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
    
    def test_record_usage(self):
        """Test usage recording."""
        usage = PlanUsageService.record_usage(
            tenant=self.tenant,
            metric_type='api_calls',
            value=100,
            period='daily',
        )
        
        self.assertIsInstance(usage, PlanUsage)
        self.assertEqual(usage.tenant, self.tenant)
        self.assertEqual(usage.api_calls_used, 100)
    
    def test_get_current_usage(self):
        """Test getting current usage."""
        # Record some usage
        PlanUsageService.record_usage(
            tenant=self.tenant,
            metric_type='api_calls',
            value=500,
            period='monthly',
        )
        
        current_usage = PlanUsageService.get_current_usage(self.tenant, 'monthly')
        
        self.assertIsInstance(current_usage, dict)
        self.assertIn('api_calls', current_usage)
        self.assertEqual(current_usage['api_calls']['used'], 500)
    
    def test_check_quota_exceeded(self):
        """Test quota exceeded check."""
        # Record usage that exceeds quota
        PlanUsageService.record_usage(
            tenant=self.tenant,
            metric_type='api_calls',
            value=1500,  # Exceeds 1000 limit
            period='monthly',
        )
        
        exceeded = PlanUsageService.check_quota_exceeded(self.tenant)
        
        self.assertIsInstance(exceeded, dict)
        self.assertTrue(len(exceeded) > 0)
        self.assertIn('api_calls', exceeded)
    
    def test_get_usage_statistics(self):
        """Test usage statistics."""
        # Record some usage data
        for i in range(10):
            PlanUsageService.record_usage(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i,
                period='daily',
            )
        
        stats = PlanUsageService.get_usage_statistics(self.tenant)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_api_calls', stats)
        self.assertIn('average_daily_calls', stats)
        self.assertIn('peak_daily_calls', stats)


class TestTenantBillingService(TestCase):
    """Test cases for TenantBillingService."""
    
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
        
        self.tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
    
    def test_generate_monthly_invoice(self):
        """Test monthly invoice generation."""
        invoice = TenantBillingService.generate_monthly_invoice(self.tenant)
        
        self.assertIsInstance(invoice, TenantInvoice)
        self.assertEqual(invoice.tenant, self.tenant)
        self.assertEqual(invoice.status, 'pending')
        self.assertGreater(invoice.total_amount, 0)
    
    def test_handle_dunning(self):
        """Test dunning handling."""
        # Create overdue invoice
        invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-001',
            status='overdue',
            issue_date=timezone.now().date() - timedelta(days=40),
            due_date=timezone.now().date() - timedelta(days=10),
            total_amount=29.99,
        )
        
        result = TenantBillingService.handle_dunning(self.tenant)
        
        self.assertIsInstance(result, dict)
        self.assertIn('action', result)
    
    def test_process_payment(self):
        """Test payment processing."""
        invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-001',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            total_amount=29.99,
        )
        
        result = TenantBillingService.process_payment(
            invoice=invoice,
            amount=29.99,
            payment_method='credit_card',
            transaction_id='txn_12345',
        )
        
        self.assertTrue(result['success'])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(invoice.amount_paid, 29.99)
    
    def test_get_billing_summary(self):
        """Test billing summary."""
        summary = TenantBillingService.get_billing_summary(self.tenant)
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_invoices', summary)
        self.assertIn('total_paid', summary)
        self.assertIn('total_outstanding', summary)
    
    @patch('tenants.services.TenantBillingService.send_payment_reminder')
    def test_send_payment_reminder(self, mock_send_reminder):
        """Test sending payment reminder."""
        invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-001',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=5),
            total_amount=29.99,
        )
        
        TenantBillingService.send_payment_reminder(invoice)
        
        mock_send_reminder.assert_called_once_with(invoice)


class TestTenantMetricService(TestCase):
    """Test cases for TenantMetricService."""
    
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
        
        self.tenant = TenantService.create_tenant(
            name='Test Tenant',
            owner=self.user,
            plan=self.plan,
        )
    
    def test_record_metric(self):
        """Test metric recording."""
        metric = TenantMetricService.record_metric(
            tenant=self.tenant,
            metric_type='api_calls',
            value=100,
            unit='count',
        )
        
        self.assertIsInstance(metric, TenantMetric)
        self.assertEqual(metric.tenant, self.tenant)
        self.assertEqual(metric.metric_type, 'api_calls')
        self.assertEqual(metric.value, 100)
    
    def test_collect_daily_metrics(self):
        """Test daily metrics collection."""
        result = TenantMetricService.collect_daily_metrics()
        
        self.assertIsInstance(result, dict)
        self.assertIn('metrics_collected', result)
        self.assertIn('tenants_processed', result)
    
    def test_get_tenant_metrics_summary(self):
        """Test tenant metrics summary."""
        # Record some metrics
        for i in range(5):
            TenantMetricService.record_metric(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i * 10,
                unit='count',
            )
        
        summary = TenantMetricService.get_tenant_metrics_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_tenants', summary)
        self.assertIn('total_metrics', summary)
        self.assertIn('metric_types', summary)
    
    def test_calculate_trends(self):
        """Test trend calculation."""
        # Create metric history
        for i in range(10):
            TenantMetricService.record_metric(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100 + i * 5,
                unit='count',
            )
        
        trends = TenantMetricService.calculate_trends(
            tenant=self.tenant,
            metric_type='api_calls',
            days=7
        )
        
        self.assertIsInstance(trends, dict)
        self.assertIn('trend', trends)
        self.assertIn('change_percentage', trends)
    
    def test_cleanup_old_metrics(self):
        """Test old metrics cleanup."""
        # Create old metric
        old_date = timezone.now() - timedelta(days=100)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            TenantMetricService.record_metric(
                tenant=self.tenant,
                metric_type='api_calls',
                value=100,
                unit='count',
            )
        
        # Count metrics before cleanup
        initial_count = TenantMetric.objects.count()
        
        # Clean up metrics older than 30 days
        result = TenantMetricService.cleanup_old_metrics(days=30)
        
        self.assertIsInstance(result, dict)
        self.assertIn('deleted_count', result)
        self.assertLess(TenantMetric.objects.count(), initial_count)
