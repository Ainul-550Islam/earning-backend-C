"""
Serializer Tests

This module contains unit tests for all tenant serializers including
TenantSerializer, PlanSerializer, and other serializer classes.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from datetime import timedelta

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage
from ..models.branding import TenantBranding, TenantDomain
from ..models.security import TenantAPIKey, TenantAuditLog
from ..models.analytics import TenantMetric, TenantHealthScore
from ..serializers import (
    TenantSerializer, TenantSettingsSerializer, TenantBillingSerializer,
    TenantInvoiceSerializer, PlanSerializer, TenantAPIKeySerializer,
    TenantMetricSerializer, TenantHealthScoreSerializer
)

User = get_user_model()


class TestTenantSerializer(TestCase):
    """Test cases for TenantSerializer."""
    
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
    
    def test_tenant_serialization(self):
        """Test tenant serialization."""
        serializer = TenantSerializer(self.tenant)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.tenant.id))
        self.assertEqual(data['name'], 'Test Tenant')
        self.assertEqual(data['slug'], 'test-tenant')
        self.assertEqual(data['status'], 'trial')
        self.assertEqual(data['tier'], 'basic')
        self.assertEqual(data['owner']['id'], str(self.user.id))
        self.assertEqual(data['plan']['id'], str(self.plan.id))
        self.assertEqual(data['contact_email'], 'contact@test.com')
    
    def test_tenant_deserialization(self):
        """Test tenant deserialization."""
        data = {
            'name': 'New Tenant',
            'slug': 'new-tenant',
            'plan': self.plan.id,
            'owner': self.user.id,
            'contact_email': 'new@example.com',
        }
        
        serializer = TenantSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        tenant = serializer.save()
        self.assertEqual(tenant.name, 'New Tenant')
        self.assertEqual(tenant.slug, 'new-tenant')
        self.assertEqual(tenant.owner, self.user)
        self.assertEqual(tenant.plan, self.plan)
    
    def test_tenant_validation(self):
        """Test tenant validation."""
        # Test required fields
        serializer = TenantSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        self.assertIn('plan', serializer.errors)
        self.assertIn('owner', serializer.errors)
        
        # Test unique slug
        serializer = TenantSerializer(data={
            'name': 'Duplicate Tenant',
            'slug': 'test-tenant',  # Already exists
            'plan': self.plan.id,
            'owner': self.user.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('slug', serializer.errors)
        
        # Test invalid email
        serializer = TenantSerializer(data={
            'name': 'Invalid Email Tenant',
            'slug': 'invalid-email',
            'plan': self.plan.id,
            'owner': self.user.id,
            'contact_email': 'invalid-email',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('contact_email', serializer.errors)
    
    def test_tenant_readonly_fields(self):
        """Test tenant read-only fields."""
        data = {
            'name': 'Test Tenant',
            'slug': 'test-tenant',
            'plan': self.plan.id,
            'owner': self.user.id,
            'is_deleted': True,  # Should not be allowed
            'created_at': timezone.now(),  # Should not be allowed
        }
        
        serializer = TenantSerializer(data=data)
        # These fields should be ignored during deserialization
        self.assertTrue(serializer.is_valid())
    
    def test_tenant_nested_serialization(self):
        """Test nested serialization of related objects."""
        serializer = TenantSerializer(self.tenant)
        data = serializer.data
        
        # Check owner serialization
        self.assertIn('owner', data)
        self.assertEqual(data['owner']['id'], str(self.user.id))
        self.assertEqual(data['owner']['username'], self.user.username)
        self.assertEqual(data['owner']['email'], self.user.email)
        
        # Check plan serialization
        self.assertIn('plan', data)
        self.assertEqual(data['plan']['id'], str(self.plan.id))
        self.assertEqual(data['plan']['name'], self.plan.name)
        self.assertEqual(data['plan']['price_monthly'], str(self.plan.price_monthly))
    
    def test_tenant_trial_status_fields(self):
        """Test trial status related fields."""
        # Set trial end date
        self.tenant.trial_ends_at = timezone.now() + timedelta(days=7)
        self.tenant.save()
        
        serializer = TenantSerializer(self.tenant)
        data = serializer.data
        
        self.assertIn('is_trial_expired', data)
        self.assertIn('days_until_trial_expiry', data)
        self.assertFalse(data['is_trial_expired'])
        self.assertEqual(data['days_until_trial_expiry'], 7)


class TestPlanSerializer(TestCase):
    """Test cases for PlanSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
            price_yearly=299.99,
            max_users=5,
            max_publishers=10,
            api_calls_per_day=1000,
            storage_gb=10,
        )
    
    def test_plan_serialization(self):
        """Test plan serialization."""
        serializer = PlanSerializer(self.plan)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.plan.id))
        self.assertEqual(data['name'], 'Basic Plan')
        self.assertEqual(data['slug'], 'basic')
        self.assertEqual(data['plan_type'], 'basic')
        self.assertEqual(data['price_monthly'], str(self.plan.price_monthly))
        self.assertEqual(data['price_yearly'], str(self.plan.price_yearly))
        self.assertEqual(data['max_users'], 5)
        self.assertEqual(data['max_publishers'], 10)
        self.assertEqual(data['api_calls_per_day'], 1000)
        self.assertEqual(data['storage_gb'], 10)
    
    def test_plan_deserialization(self):
        """Test plan deserialization."""
        data = {
            'name': 'New Plan',
            'slug': 'new-plan',
            'plan_type': 'professional',
            'price_monthly': 99.99,
            'price_yearly': 999.99,
            'max_users': 20,
            'max_publishers': 50,
            'api_calls_per_day': 5000,
            'storage_gb': 50,
        }
        
        serializer = PlanSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        plan = serializer.save()
        self.assertEqual(plan.name, 'New Plan')
        self.assertEqual(plan.slug, 'new-plan')
        self.assertEqual(plan.plan_type, 'professional')
        self.assertEqual(float(plan.price_monthly), 99.99)
    
    def test_plan_validation(self):
        """Test plan validation."""
        # Test required fields
        serializer = PlanSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        self.assertIn('slug', serializer.errors)
        self.assertIn('plan_type', serializer.errors)
        
        # Test unique slug
        serializer = PlanSerializer(data={
            'name': 'Duplicate Plan',
            'slug': 'basic',  # Already exists
            'plan_type': 'basic',
            'price_monthly': 29.99,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('slug', serializer.errors)
        
        # Test invalid plan type
        serializer = PlanSerializer(data={
            'name': 'Invalid Plan',
            'slug': 'invalid',
            'plan_type': 'invalid_type',
            'price_monthly': 29.99,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('plan_type', serializer.errors)
        
        # Test negative prices
        serializer = PlanSerializer(data={
            'name': 'Negative Price Plan',
            'slug': 'negative',
            'plan_type': 'basic',
            'price_monthly': -29.99,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('price_monthly', serializer.errors)
    
    def test_plan_custom_fields(self):
        """Test plan custom fields."""
        # Test with features
        data = {
            'name': 'Feature Plan',
            'slug': 'feature',
            'plan_type': 'basic',
            'price_monthly': 29.99,
            'features': ['feature1', 'feature2'],
            'feature_flags': {'flag1': True, 'flag2': False},
        }
        
        serializer = PlanSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        plan = serializer.save()
        self.assertEqual(plan.features, ['feature1', 'feature2'])
        self.assertEqual(plan.feature_flags, {'flag1': True, 'flag2': False})


class TestTenantAPIKeySerializer(TestCase):
    """Test cases for TenantAPIKeySerializer."""
    
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
        
        self.api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Test API Key',
            scopes=['read', 'write'],
            rate_limit_per_minute=60,
        )
    
    def test_api_key_serialization(self):
        """Test API key serialization."""
        serializer = TenantAPIKeySerializer(self.api_key)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.api_key.id))
        self.assertEqual(data['name'], 'Test API Key')
        self.assertEqual(data['scopes'], ['read', 'write'])
        self.assertEqual(data['rate_limit_per_minute'], 60)
        self.assertEqual(data['status'], 'active')
        self.assertIsNotNone(data['key_prefix'])
        self.assertNotIn('key_hash', data)  # Should not expose hash
        self.assertNotIn('key', data)  # Should not expose full key
    
    def test_api_key_deserialization(self):
        """Test API key deserialization."""
        data = {
            'name': 'New API Key',
            'scopes': ['read'],
            'rate_limit_per_minute': 30,
            'expires_at': (timezone.now() + timedelta(days=30)).isoformat(),
        }
        
        serializer = TenantAPIKeySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        api_key = serializer.save()
        self.assertEqual(api_key.name, 'New API Key')
        self.assertEqual(api_key.scopes, ['read'])
        self.assertEqual(api_key.rate_limit_per_minute, 30)
        self.assertIsNotNone(api_key.expires_at)
    
    def test_api_key_validation(self):
        """Test API key validation."""
        # Test required fields
        serializer = TenantAPIKeySerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Test invalid scopes
        serializer = TenantAPIKeySerializer(data={
            'name': 'Invalid Scopes Key',
            'scopes': ['invalid_scope'],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('scopes', serializer.errors)
        
        # Test negative rate limit
        serializer = TenantAPIKeySerializer(data={
            'name': 'Negative Rate Key',
            'scopes': ['read'],
            'rate_limit_per_minute': -10,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('rate_limit_per_minute', serializer.errors)
    
    def test_api_key_expiration_validation(self):
        """Test API key expiration validation."""
        # Test past expiration date
        serializer = TenantAPIKeySerializer(data={
            'name': 'Expired Key',
            'scopes': ['read'],
            'expires_at': (timezone.now() - timedelta(days=1)).isoformat(),
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('expires_at', serializer.errors)


class TestTenantMetricSerializer(TestCase):
    """Test cases for TenantMetricSerializer."""
    
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
        
        self.metric = TenantMetric.objects.create(
            tenant=self.tenant,
            metric_type='api_calls',
            value=100,
            unit='count',
            date=timezone.now().date(),
        )
    
    def test_metric_serialization(self):
        """Test metric serialization."""
        serializer = TenantMetricSerializer(self.metric)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.metric.id))
        self.assertEqual(data['metric_type'], 'api_calls')
        self.assertEqual(data['value'], 100)
        self.assertEqual(data['unit'], 'count')
        self.assertEqual(data['date'], self.metric.date.isoformat())
        self.assertIn('tenant', data)
        self.assertEqual(data['tenant']['id'], str(self.tenant.id))
    
    def test_metric_deserialization(self):
        """Test metric deserialization."""
        data = {
            'metric_type': 'storage_usage',
            'value': 5.5,
            'unit': 'gb',
            'date': timezone.now().date().isoformat(),
            'tenant': self.tenant.id,
        }
        
        serializer = TenantMetricSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        metric = serializer.save()
        self.assertEqual(metric.metric_type, 'storage_usage')
        self.assertEqual(metric.value, 5.5)
        self.assertEqual(metric.unit, 'gb')
        self.assertEqual(metric.tenant, self.tenant)
    
    def test_metric_validation(self):
        """Test metric validation."""
        # Test required fields
        serializer = TenantMetricSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('metric_type', serializer.errors)
        self.assertIn('value', serializer.errors)
        self.assertIn('tenant', serializer.errors)
        
        # Test invalid metric type
        serializer = TenantMetricSerializer(data={
            'metric_type': 'invalid_type',
            'value': 100,
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('metric_type', serializer.errors)
        
        # Test invalid date
        serializer = TenantMetricSerializer(data={
            'metric_type': 'api_calls',
            'value': 100,
            'tenant': self.tenant.id,
            'date': 'invalid-date',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('date', serializer.errors)
    
    def test_metric_change_percentage(self):
        """Test change percentage calculation."""
        # Create previous metric
        previous_date = timezone.now().date() - timedelta(days=1)
        previous_metric = TenantMetric.objects.create(
            tenant=self.tenant,
            metric_type='api_calls',
            value=50,
            unit='count',
            date=previous_date,
        )
        
        # Create current metric with higher value
        current_metric = TenantMetric.objects.create(
            tenant=self.tenant,
            metric_type='api_calls',
            value=100,  # 100% increase
            unit='count',
            date=timezone.now().date(),
        )
        
        # Manually set previous value for testing
        current_metric.previous_value = previous_metric.value
        current_metric.calculate_change_percentage()
        
        serializer = TenantMetricSerializer(current_metric)
        data = serializer.data
        
        self.assertEqual(data['change_percentage'], 100.0)


class TestTenantHealthScoreSerializer(TestCase):
    """Test cases for TenantHealthScoreSerializer."""
    
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
        
        self.health_score = TenantHealthScore.objects.create(
            tenant=self.tenant,
            overall_score=85.5,
            health_grade='B',
            risk_level='low',
            engagement_score=90.0,
            usage_score=80.0,
            payment_score=85.0,
            support_score=87.0,
        )
    
    def test_health_score_serialization(self):
        """Test health score serialization."""
        serializer = TenantHealthScoreSerializer(self.health_score)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.health_score.id))
        self.assertEqual(data['overall_score'], 85.5)
        self.assertEqual(data['health_grade'], 'B')
        self.assertEqual(data['risk_level'], 'low')
        self.assertEqual(data['engagement_score'], 90.0)
        self.assertEqual(data['usage_score'], 80.0)
        self.assertEqual(data['payment_score'], 85.0)
        self.assertEqual(data['support_score'], 87.0)
        self.assertIn('tenant', data)
    
    def test_health_score_deserialization(self):
        """Test health score deserialization."""
        data = {
            'overall_score': 90.0,
            'health_grade': 'A',
            'risk_level': 'low',
            'engagement_score': 95.0,
            'usage_score': 85.0,
            'payment_score': 90.0,
            'support_score': 92.0,
            'tenant': self.tenant.id,
        }
        
        serializer = TenantHealthScoreSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        health_score = serializer.save()
        self.assertEqual(health_score.overall_score, 90.0)
        self.assertEqual(health_score.health_grade, 'A')
        self.assertEqual(health_score.risk_level, 'low')
    
    def test_health_score_validation(self):
        """Test health score validation."""
        # Test score range validation
        serializer = TenantHealthScoreSerializer(data={
            'overall_score': 150.0,  # Invalid: > 100
            'health_grade': 'A',
            'risk_level': 'low',
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('overall_score', serializer.errors)
        
        # Test invalid grade
        serializer = TenantHealthScoreSerializer(data={
            'overall_score': 85.0,
            'health_grade': 'Z',  # Invalid grade
            'risk_level': 'low',
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('health_grade', serializer.errors)
        
        # Test invalid risk level
        serializer = TenantHealthScoreSerializer(data={
            'overall_score': 85.0,
            'health_grade': 'B',
            'risk_level': 'invalid',  # Invalid risk level
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('risk_level', serializer.errors)
    
    def test_health_score_calculated_fields(self):
        """Test calculated fields in health score."""
        # Update last activity
        self.tenant.last_activity_at = timezone.now() - timedelta(days=5)
        self.tenant.save()
        
        # Refresh health score
        self.health_score.refresh_from_db()
        
        serializer = TenantHealthScoreSerializer(self.health_score)
        data = serializer.data
        
        self.assertIn('days_inactive', data)
        self.assertIn('churn_probability', data)
        self.assertGreaterEqual(data['days_inactive'], 0)
        self.assertGreaterEqual(data['churn_probability'], 0)
        self.assertLessEqual(data['churn_probability'], 100)


class TestTenantInvoiceSerializer(TestCase):
    """Test cases for TenantInvoiceSerializer."""
    
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
    
    def test_invoice_serialization(self):
        """Test invoice serialization."""
        serializer = TenantInvoiceSerializer(self.invoice)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.invoice.id))
        self.assertEqual(data['invoice_number'], 'INV-2024-001')
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['subtotal'], '29.99')
        self.assertEqual(data['tax_amount'], '3.00')
        self.assertEqual(data['total_amount'], '32.99')
        self.assertEqual(data['amount_paid'], '0')
        self.assertEqual(data['balance_due'], '32.99')
        self.assertIn('tenant', data)
    
    def test_invoice_deserialization(self):
        """Test invoice deserialization."""
        data = {
            'invoice_number': 'INV-2024-002',
            'status': 'pending',
            'issue_date': timezone.now().date().isoformat(),
            'due_date': (timezone.now().date() + timedelta(days=30)).isoformat(),
            'subtotal': 49.99,
            'tax_amount': 5.00,
            'discount_amount': 0,
            'total_amount': 54.99,
            'tenant': self.tenant.id,
        }
        
        serializer = TenantInvoiceSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        invoice = serializer.save()
        self.assertEqual(invoice.invoice_number, 'INV-2024-002')
        self.assertEqual(invoice.total_amount, 54.99)
    
    def test_invoice_validation(self):
        """Test invoice validation."""
        # Test required fields
        serializer = TenantInvoiceSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('invoice_number', serializer.errors)
        self.assertIn('tenant', serializer.errors)
        
        # Test negative amounts
        serializer = TenantInvoiceSerializer(data={
            'invoice_number': 'INV-INVALID',
            'subtotal': -29.99,
            'tax_amount': -3.00,
            'total_amount': -32.99,
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('subtotal', serializer.errors)
        self.assertIn('tax_amount', serializer.errors)
        self.assertIn('total_amount', serializer.errors)
        
        # Test invalid status
        serializer = TenantInvoiceSerializer(data={
            'invoice_number': 'INV-INVALID-STATUS',
            'status': 'invalid_status',
            'total_amount': 29.99,
            'tenant': self.tenant.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)
    
    def test_invoice_calculated_fields(self):
        """Test calculated fields in invoice."""
        # Create overdue invoice
        self.invoice.due_date = timezone.now().date() - timedelta(days=5)
        self.invoice.status = 'overdue'
        self.invoice.save()
        
        serializer = TenantInvoiceSerializer(self.invoice)
        data = serializer.data
        
        self.assertIn('days_overdue', data)
        self.assertEqual(data['days_overdue'], 5)
        
        # Create paid invoice
        self.invoice.status = 'paid'
        self.invoice.paid_date = timezone.now()
        self.invoice.amount_paid = 32.99
        self.invoice.save()
        
        serializer = TenantInvoiceSerializer(self.invoice)
        data = serializer.data
        
        self.assertIsNone(data['days_overdue'])  # Paid invoices don't have days_overdue
