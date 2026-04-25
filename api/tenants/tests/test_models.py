"""
Model Tests

This module contains unit tests for all tenant models including
Tenant, TenantSettings, TenantBilling, and TenantInvoice.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan

User = get_user_model()


class TestTenant(TestCase):
    """Test cases for Tenant model."""
    
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
            contact_email='contact@test.com',
        )
    
    def test_tenant_creation(self):
        """Test tenant creation."""
        self.assertEqual(self.tenant.name, 'Test Tenant')
        self.assertEqual(self.tenant.slug, 'test-tenant')
        self.assertEqual(self.tenant.owner, self.user)
        self.assertEqual(self.tenant.plan, self.plan)
        self.assertEqual(self.tenant.status, 'trial')
        self.assertEqual(self.tenant.tier, 'basic')
        self.assertFalse(self.tenant.is_deleted)
        self.assertFalse(self.tenant.is_suspended)
    
    def test_tenant_str_representation(self):
        """Test tenant string representation."""
        self.assertEqual(str(self.tenant), 'Test Tenant')
    
    def test_tenant_trial_expiry(self):
        """Test trial expiry calculations."""
        # Set trial end date to tomorrow
        self.tenant.trial_ends_at = timezone.now() + timedelta(days=1)
        self.tenant.save()
        
        self.assertFalse(self.tenant.is_trial_expired)
        self.assertEqual(self.tenant.days_until_trial_expiry, 1)
        
        # Set trial end date to yesterday
        self.tenant.trial_ends_at = timezone.now() - timedelta(days=1)
        self.tenant.save()
        
        self.assertTrue(self.tenant.is_trial_expired)
        self.assertEqual(self.tenant.days_until_trial_expiry, -1)
        
        # No trial end date
        self.tenant.trial_ends_at = None
        self.tenant.save()
        
        self.assertFalse(self.tenant.is_trial_expired)
        self.assertIsNone(self.tenant.days_until_trial_expiry)
    
    def test_tenant_soft_delete(self):
        """Test tenant soft delete."""
        self.assertFalse(self.tenant.is_deleted)
        self.assertIsNone(self.tenant.deleted_at)
        
        # Soft delete
        self.tenant.delete()
        
        # Check tenant is soft deleted
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_deleted)
        self.assertIsNotNone(self.tenant.deleted_at)
        
        # Should still be in database
        self.assertTrue(Tenant.objects.filter(id=self.tenant.id).exists())
    
    def test_tenant_unique_slug(self):
        """Test tenant slug uniqueness."""
        with self.assertRaises(Exception):  # Should raise IntegrityError
            Tenant.objects.create(
                name='Another Tenant',
                slug='test-tenant',  # Same slug
                owner=self.user,
                plan=self.plan,
            )
    
    def test_tenant_status_transitions(self):
        """Test tenant status transitions."""
        # Trial to active
        self.tenant.status = 'active'
        self.tenant.save()
        self.assertEqual(self.tenant.status, 'active')
        
        # Active to suspended
        self.tenant.status = 'suspended'
        self.tenant.is_suspended = True
        self.tenant.save()
        self.assertEqual(self.tenant.status, 'suspended')
        self.assertTrue(self.tenant.is_suspended)
        
        # Suspended to active
        self.tenant.status = 'active'
        self.tenant.is_suspended = False
        self.tenant.save()
        self.assertEqual(self.tenant.status, 'active')
        self.assertFalse(self.tenant.is_suspended)


class TestTenantSettings(TestCase):
    """Test cases for TenantSettings model."""
    
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
        
        self.settings = TenantSettings.objects.create(
            tenant=self.tenant,
            enable_smartlink=True,
            enable_ai_engine=False,
            max_users=5,
            api_calls_per_day=1000,
        )
    
    def test_settings_creation(self):
        """Test settings creation."""
        self.assertEqual(self.settings.tenant, self.tenant)
        self.assertTrue(self.settings.enable_smartlink)
        self.assertFalse(self.settings.enable_ai_engine)
        self.assertEqual(self.settings.max_users, 5)
        self.assertEqual(self.settings.api_calls_per_day, 1000)
    
    def test_settings_str_representation(self):
        """Test settings string representation."""
        self.assertEqual(str(self.settings), f'Settings for {self.tenant.name}')
    
    def test_settings_defaults(self):
        """Test settings default values."""
        settings = TenantSettings.objects.create(tenant=self.tenant)
        
        self.assertTrue(settings.enable_smartlink)
        self.assertTrue(settings.enable_ai_engine)
        self.assertTrue(settings.enable_publisher_tools)
        self.assertTrue(settings.enable_advertiser_portal)
        self.assertEqual(settings.max_withdrawal_per_day, 1000)
        self.assertTrue(settings.require_kyc_for_withdrawal)
        self.assertEqual(settings.api_calls_per_minute, 60)
        self.assertEqual(settings.api_calls_per_hour, 1000)
        self.assertEqual(settings.storage_gb, 10)
        self.assertEqual(settings.bandwidth_gb_per_month, 100)
        self.assertEqual(settings.default_language, 'en')
        self.assertEqual(settings.default_currency, 'USD')
        self.assertEqual(settings.default_timezone, 'UTC')
        self.assertTrue(settings.enable_two_factor_auth)
        self.assertEqual(settings.session_timeout_minutes, 30)
        self.assertEqual(settings.password_min_length, 8)
        self.assertTrue(settings.password_require_special)
        self.assertTrue(settings.password_require_numbers)
        self.assertTrue(settings.enable_email_notifications)
        self.assertTrue(settings.enable_push_notifications)
        self.assertFalse(settings.enable_sms_notifications)
        self.assertEqual(settings.api_key_rotations, 90)
        self.assertEqual(settings.backup_frequency, 'daily')
        self.assertEqual(settings.retention_days, 365)


class TestTenantBilling(TestCase):
    """Test cases for TenantBilling model."""
    
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
        
        self.billing = TenantBilling.objects.create(
            tenant=self.tenant,
            billing_cycle='monthly',
            payment_method='credit_card',
            base_price=29.99,
            final_price=29.99,
        )
    
    def test_billing_creation(self):
        """Test billing creation."""
        self.assertEqual(self.billing.tenant, self.tenant)
        self.assertEqual(self.billing.billing_cycle, 'monthly')
        self.assertEqual(self.billing.payment_method, 'credit_card')
        self.assertEqual(self.billing.base_price, 29.99)
        self.assertEqual(self.billing.final_price, 29.99)
        self.assertEqual(self.billing.discount_pct, 0)
    
    def test_billing_str_representation(self):
        """Test billing string representation."""
        self.assertEqual(str(self.billing), f'Billing for {self.tenant.name}')
    
    def test_billing_calculate_final_price(self):
        """Test final price calculation."""
        # Test with discount
        self.billing.discount_pct = 10  # 10% discount
        self.billing.calculate_final_price()
        
        expected_price = 29.99 * (1 - 0.10)  # 26.991
        self.assertAlmostEqual(float(self.billing.final_price), expected_price, places=2)
        
        # Test with setup fee
        self.billing.setup_fee = 50.00
        self.billing.calculate_final_price()
        
        expected_price = (29.99 * (1 - 0.10)) + 50.00  # 76.991
        self.assertAlmostEqual(float(self.billing.final_price), expected_price, places=2)
    
    def test_billing_is_overdue(self):
        """Test overdue status."""
        # Not overdue (future due date)
        self.billing.next_billing_date = timezone.now() + timedelta(days=30)
        self.billing.save()
        self.assertFalse(self.billing.is_overdue())
        
        # Overdue
        self.billing.next_billing_date = timezone.now() - timedelta(days=1)
        self.billing.save()
        self.assertTrue(self.billing.is_overdue())
        
        # No due date
        self.billing.next_billing_date = None
        self.billing.save()
        self.assertFalse(self.billing.is_overdue())
    
    def test_billing_defaults(self):
        """Test billing default values."""
        billing = TenantBilling.objects.create(tenant=self.tenant)
        
        self.assertEqual(billing.billing_cycle, 'monthly')
        self.assertEqual(billing.payment_method, 'credit_card')
        self.assertEqual(billing.base_price, 0)
        self.assertEqual(billing.final_price, 0)
        self.assertEqual(billing.discount_pct, 0)
        self.assertEqual(billing.setup_fee, 0)
        self.assertEqual(billing.dunning_count, 0)
        self.assertEqual(billing.max_dunning_attempts, 3)
        self.assertIsNone(billing.last_dunning_sent)


class TestTenantInvoice(TestCase):
    """Test cases for TenantInvoice model."""
    
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
        
        self.invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            invoice_number='INV-2024-001',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            subtotal=29.99,
            tax_amount=3.00,
            discount_amount=0,
            total_amount=32.99,
        )
    
    def test_invoice_creation(self):
        """Test invoice creation."""
        self.assertEqual(self.invoice.tenant, self.tenant)
        self.assertEqual(self.invoice.invoice_number, 'INV-2024-001')
        self.assertEqual(self.invoice.status, 'pending')
        self.assertEqual(self.invoice.subtotal, 29.99)
        self.assertEqual(self.invoice.tax_amount, 3.00)
        self.assertEqual(self.invoice.total_amount, 32.99)
        self.assertEqual(self.invoice.amount_paid, 0)
        self.assertEqual(self.invoice.balance_due, 32.99)
    
    def test_invoice_str_representation(self):
        """Test invoice string representation."""
        self.assertEqual(str(self.invoice), self.invoice.invoice_number)
    
    def test_invoice_days_overdue(self):
        """Test days overdue calculation."""
        # Not overdue (future due date)
        self.invoice.due_date = timezone.now().date() + timedelta(days=30)
        self.invoice.save()
        self.assertEqual(self.invoice.days_overdue, -30)
        
        # Due today
        self.invoice.due_date = timezone.now().date()
        self.invoice.save()
        self.assertEqual(self.invoice.days_overdue, 0)
        
        # Overdue by 5 days
        self.invoice.due_date = timezone.now().date() - timedelta(days=5)
        self.invoice.save()
        self.assertEqual(self.invoice.days_overdue, 5)
        
        # Paid (should return None)
        self.invoice.status = 'paid'
        self.invoice.paid_date = timezone.now()
        self.invoice.save()
        self.assertIsNone(self.invoice.days_overdue)
    
    def test_invoice_payment_processing(self):
        """Test payment processing."""
        self.assertEqual(self.invoice.amount_paid, 0)
        self.assertEqual(self.invoice.balance_due, 32.99)
        
        # Partial payment
        self.invoice.amount_paid = 10.00
        self.invoice.save()
        
        self.assertEqual(self.invoice.amount_paid, 10.00)
        self.assertEqual(self.invoice.balance_due, 22.99)
        
        # Full payment
        self.invoice.amount_paid = 32.99
        self.invoice.status = 'paid'
        self.invoice.paid_date = timezone.now()
        self.invoice.save()
        
        self.assertEqual(self.invoice.amount_paid, 32.99)
        self.assertEqual(self.invoice.balance_due, 0)
    
    def test_invoice_line_items(self):
        """Test invoice line items."""
        line_items = [
            {
                'description': 'Basic Plan - Monthly',
                'quantity': 1,
                'unit_price': 29.99,
                'total': 29.99
            },
            {
                'description': 'Tax',
                'quantity': 1,
                'unit_price': 3.00,
                'total': 3.00
            }
        ]
        
        self.invoice.line_items = line_items
        self.invoice.save()
        
        self.assertEqual(len(self.invoice.line_items), 2)
        self.assertEqual(self.invoice.line_items[0]['description'], 'Basic Plan - Monthly')
        self.assertEqual(self.invoice.line_items[0]['total'], 29.99)
    
    def test_invoice_defaults(self):
        """Test invoice default values."""
        invoice = TenantInvoice.objects.create(tenant=self.tenant)
        
        self.assertEqual(invoice.status, 'pending')
        self.assertEqual(invoice.subtotal, 0)
        self.assertEqual(invoice.tax_amount, 0)
        self.assertEqual(invoice.discount_amount, 0)
        self.assertEqual(invoice.total_amount, 0)
        self.assertEqual(invoice.amount_paid, 0)
        self.assertEqual(invoice.balance_due, 0)
        self.assertEqual(invoice.payment_method, 'credit_card')
        self.assertIsNone(invoice.paid_date)
        self.assertIsNone(invoice.transaction_id)
    
    def test_invoice_number_generation(self):
        """Test automatic invoice number generation."""
        # Create invoice without number
        invoice = TenantInvoice.objects.create(
            tenant=self.tenant,
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            total_amount=29.99,
        )
        
        # Should generate invoice number
        self.assertIsNotNone(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith('INV-'))
    
    def test_invoice_status_validation(self):
        """Test invoice status validation."""
        # Valid statuses
        valid_statuses = ['pending', 'paid', 'overdue', 'cancelled', 'refunded']
        
        for status in valid_statuses:
            invoice = TenantInvoice.objects.create(
                tenant=self.tenant,
                status=status,
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=30),
                total_amount=29.99,
            )
            self.assertEqual(invoice.status, status)
