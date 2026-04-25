"""
ViewSet Tests

This module contains unit tests for all tenant viewsets including
TenantViewSet, PlanViewSet, and other viewset classes.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage
from ..models.branding import TenantBranding, TenantDomain
from ..models.security import TenantAPIKey, TenantAuditLog
from ..models.analytics import TenantMetric, TenantHealthScore

User = get_user_model()


class TestTenantViewSet(TestCase):
    """Test cases for TenantViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
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
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_tenants(self):
        """Test listing tenants."""
        url = reverse('tenant-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_tenant(self):
        """Test retrieving a specific tenant."""
        url = reverse('tenant-detail', kwargs={'pk': self.tenant.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.tenant.pk))
        self.assertEqual(response.data['name'], 'Test Tenant')
    
    def test_create_tenant(self):
        """Test creating a new tenant."""
        url = reverse('tenant-list')
        data = {
            'name': 'New Tenant',
            'slug': 'new-tenant',
            'plan': self.plan.pk,
            'owner': self.user.pk,
            'contact_email': 'new@example.com',
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Tenant')
        
        # Verify tenant was created
        self.assertTrue(Tenant.objects.filter(name='New Tenant').exists())
    
    def test_update_tenant(self):
        """Test updating a tenant."""
        url = reverse('tenant-detail', kwargs={'pk': self.tenant.pk})
        data = {
            'name': 'Updated Tenant',
            'contact_email': 'updated@example.com',
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Tenant')
        
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, 'Updated Tenant')
    
    def test_delete_tenant(self):
        """Test deleting a tenant."""
        url = reverse('tenant-detail', kwargs={'pk': self.tenant.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify tenant was soft deleted
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_deleted)
    
    def test_suspend_tenant_action(self):
        """Test suspend tenant custom action."""
        url = reverse('tenant-suspend', kwargs={'pk': self.tenant.pk})
        data = {'reason': 'Test suspension'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_suspended)
        self.assertEqual(self.tenant.suspension_reason, 'Test suspension')
    
    def test_unsuspend_tenant_action(self):
        """Test unsuspend tenant custom action."""
        # First suspend
        self.tenant.is_suspended = True
        self.tenant.suspension_reason = 'Test'
        self.tenant.save()
        
        url = reverse('tenant-unsuspend', kwargs={'pk': self.tenant.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_suspended)
    
    def test_statistics_action(self):
        """Test tenant statistics custom action."""
        url = reverse('tenant-statistics', kwargs={'pk': self.tenant.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
    
    def test_filtering(self):
        """Test filtering tenants."""
        # Create another tenant with different status
        other_plan = Plan.objects.create(
            name='Pro Plan',
            slug='pro',
            plan_type='professional',
            price_monthly=99.99,
        )
        
        Tenant.objects.create(
            name='Pro Tenant',
            slug='pro-tenant',
            owner=self.user,
            plan=other_plan,
            status='active',
        )
        
        url = reverse('tenant-list')
        response = self.client.get(url, {'status': 'trial'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'trial')
    
    def test_searching(self):
        """Test searching tenants."""
        url = reverse('tenant-list')
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Tenant')
    
    def test_ordering(self):
        """Test ordering tenants."""
        # Create another tenant
        other_plan = Plan.objects.create(
            name='Pro Plan',
            slug='pro',
            plan_type='professional',
            price_monthly=99.99,
        )
        
        Tenant.objects.create(
            name='A Tenant',
            slug='a-tenant',
            owner=self.user,
            plan=other_plan,
        )
        
        url = reverse('tenant-list')
        response = self.client.get(url, {'ordering': 'name'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['name'], 'A Tenant')
        self.assertEqual(response.data['results'][1]['name'], 'Test Tenant')


class TestPlanViewSet(TestCase):
    """Test cases for PlanViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_staff=True,
        )
        
        self.basic_plan = Plan.objects.create(
            name='Basic Plan',
            slug='basic',
            plan_type='basic',
            price_monthly=29.99,
            max_users=5,
            max_publishers=10,
            api_calls_per_day=1000,
            storage_gb=10,
        )
        
        self.pro_plan = Plan.objects.create(
            name='Pro Plan',
            slug='pro',
            plan_type='professional',
            price_monthly=99.99,
            max_users=20,
            max_publishers=50,
            api_calls_per_day=5000,
            storage_gb=50,
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_plans(self):
        """Test listing plans."""
        url = reverse('plan-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_retrieve_plan(self):
        """Test retrieving a specific plan."""
        url = reverse('plan-detail', kwargs={'pk': self.basic_plan.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Basic Plan')
    
    def test_create_plan(self):
        """Test creating a new plan."""
        url = reverse('plan-list')
        data = {
            'name': 'Enterprise Plan',
            'slug': 'enterprise',
            'plan_type': 'enterprise',
            'price_monthly': 299.99,
            'max_users': 100,
            'max_publishers': 200,
            'api_calls_per_day': 10000,
            'storage_gb': 100,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Enterprise Plan')
        
        # Verify plan was created
        self.assertTrue(Plan.objects.filter(name='Enterprise Plan').exists())
    
    def test_update_plan(self):
        """Test updating a plan."""
        url = reverse('plan-detail', kwargs={'pk': self.basic_plan.pk})
        data = {
            'name': 'Updated Basic Plan',
            'price_monthly': 39.99,
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Basic Plan')
        
        self.basic_plan.refresh_from_db()
        self.assertEqual(self.basic_plan.name, 'Updated Basic Plan')
    
    def test_activate_plan_action(self):
        """Test activate plan custom action."""
        # Deactivate plan first
        self.basic_plan.is_active = False
        self.basic_plan.save()
        
        url = reverse('plan-activate', kwargs={'pk': self.basic_plan.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.basic_plan.refresh_from_db()
        self.assertTrue(self.basic_plan.is_active)
    
    def test_deactivate_plan_action(self):
        """Test deactivate plan custom action."""
        url = reverse('plan-deactivate', kwargs={'pk': self.basic_plan.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.basic_plan.refresh_from_db()
        self.assertFalse(self.basic_plan.is_active)
    
    def test_compare_plans_action(self):
        """Test compare plans custom action."""
        url = reverse('plan-compare')
        data = {'plans': [self.basic_plan.pk, self.pro_plan.pk]}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('comparison', response.data)
    
    def test_filtering_by_type(self):
        """Test filtering plans by type."""
        url = reverse('plan-list')
        response = self.client.get(url, {'plan_type': 'basic'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['plan_type'], 'basic')
    
    def test_filtering_by_active_status(self):
        """Test filtering plans by active status."""
        # Deactivate one plan
        self.pro_plan.is_active = False
        self.pro_plan.save()
        
        url = reverse('plan-list')
        response = self.client.get(url, {'is_active': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue(response.data['results'][0]['is_active'])


class TestTenantAPIKeyViewSet(TestCase):
    """Test cases for TenantAPIKeyViewSet."""
    
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
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_api_keys(self):
        """Test listing API keys."""
        url = reverse('apikey-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_api_key(self):
        """Test creating a new API key."""
        url = reverse('apikey-list')
        data = {
            'name': 'New API Key',
            'scopes': ['read'],
            'rate_limit_per_minute': 30,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New API Key')
        self.assertIsNotNone(response.data['key_prefix'])
        
        # Verify API key was created
        self.assertTrue(TenantAPIKey.objects.filter(name='New API Key').exists())
    
    def test_revoke_api_key_action(self):
        """Test revoke API key custom action."""
        url = reverse('apikey-revoke', kwargs={'pk': self.api_key.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.api_key.refresh_from_db()
        self.assertEqual(self.api_key.status, 'revoked')
    
    def test_regenerate_api_key_action(self):
        """Test regenerate API key custom action."""
        original_prefix = self.api_key.key_prefix
        
        url = reverse('apikey-regenerate', kwargs={'pk': self.api_key.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.api_key.refresh_from_db()
        self.assertNotEqual(self.api_key.key_prefix, original_prefix)
    
    def test_filtering_by_status(self):
        """Test filtering API keys by status."""
        # Create another API key with different status
        TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Inactive API Key',
            status='inactive',
            scopes=['read'],
        )
        
        url = reverse('apikey-list')
        response = self.client.get(url, {'status': 'active'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'active')


class TestTenantMetricViewSet(TestCase):
    """Test cases for TenantMetricViewSet."""
    
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
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_metrics(self):
        """Test listing metrics."""
        url = reverse('metric-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_metric(self):
        """Test creating a new metric."""
        url = reverse('metric-list')
        data = {
            'metric_type': 'storage_usage',
            'value': 5.5,
            'unit': 'gb',
            'date': timezone.now().date().isoformat(),
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['metric_type'], 'storage_usage')
        self.assertEqual(response.data['value'], '5.5')
        
        # Verify metric was created
        self.assertTrue(TenantMetric.objects.filter(metric_type='storage_usage').exists())
    
    def test_record_metric_action(self):
        """Test record metric custom action."""
        url = reverse('metric-record')
        data = {
            'tenant': self.tenant.pk,
            'metric_type': 'user_count',
            'value': 10,
            'unit': 'count',
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metric', response.data)
        
        # Verify metric was recorded
        self.assertTrue(TenantMetric.objects.filter(metric_type='user_count').exists())
    
    def test_filtering_by_metric_type(self):
        """Test filtering metrics by type."""
        # Create another metric with different type
        TenantMetric.objects.create(
            tenant=self.tenant,
            metric_type='storage_usage',
            value=5.5,
            unit='gb',
            date=timezone.now().date(),
        )
        
        url = reverse('metric-list')
        response = self.client.get(url, {'metric_type': 'api_calls'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['metric_type'], 'api_calls')
    
    def test_filtering_by_date_range(self):
        """Test filtering metrics by date range."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Create metric for yesterday
        TenantMetric.objects.create(
            tenant=self.tenant,
            metric_type='api_calls',
            value=50,
            unit='count',
            date=yesterday,
        )
        
        url = reverse('metric-list')
        response = self.client.get(url, {
            'date_gte': today.isoformat(),
            'date_lte': today.isoformat(),
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class TestTenantAuditLogViewSet(TestCase):
    """Test cases for TenantAuditLogViewSet."""
    
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
        
        self.audit_log = TenantAuditLog.objects.create(
            tenant=self.tenant,
            action='create',
            model_name='Tenant',
            description='Tenant created',
            severity='low',
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_audit_logs(self):
        """Test listing audit logs."""
        url = reverse('auditlog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filtering_by_action(self):
        """Test filtering audit logs by action."""
        # Create another audit log with different action
        TenantAuditLog.objects.create(
            tenant=self.tenant,
            action='update',
            model_name='Tenant',
            description='Tenant updated',
            severity='low',
        )
        
        url = reverse('auditlog-list')
        response = self.client.get(url, {'action': 'create'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['action'], 'create')
    
    def test_filtering_by_severity(self):
        """Test filtering audit logs by severity."""
        # Create another audit log with different severity
        TenantAuditLog.objects.create(
            tenant=self.tenant,
            action='security_event',
            model_name='Tenant',
            description='Security event',
            severity='high',
        )
        
        url = reverse('auditlog-list')
        response = self.client.get(url, {'severity': 'low'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['severity'], 'low')
    
    def test_export_action(self):
        """Test export audit logs custom action."""
        url = reverse('auditlog-export')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('export_id', response.data)
    
    def test_date_hierarchy_filtering(self):
        """Test date hierarchy filtering."""
        # Create audit log for yesterday
        yesterday = timezone.now() - timedelta(days=1)
        
        TenantAuditLog.objects.create(
            tenant=self.tenant,
            action='create',
            model_name='Tenant',
            description='Old audit log',
            severity='low',
            created_at=yesterday,
        )
        
        url = reverse('auditlog-list')
        response = self.client.get(url, {
            'created_at__gte': timezone.now().date().isoformat(),
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
