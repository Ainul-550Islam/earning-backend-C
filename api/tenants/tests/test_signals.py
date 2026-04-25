"""
Signal Tests

This module contains unit tests for all Django signals including
core signals, plan signals, security signals, and other signal handlers.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUsage, PlanQuota
from ..models.branding import TenantBranding, TenantDomain
from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantAuditLog
from ..models.onboarding import TenantOnboarding, TenantOnboardingStep
from ..models.analytics import TenantMetric, TenantHealthScore, TenantNotification
from ..models.reseller import ResellerConfig
from ..signals import (
    tenant_created, tenant_updated, tenant_deleted,
    plan_usage_recorded, quota_exceeded, api_key_created,
    onboarding_started, metric_recorded, branding_updated,
    reseller_created
)

User = get_user_model()


class TestCoreSignals(TestCase):
    """Test cases for core tenant signals."""
    
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
    
    @patch('tenants.signals.core.TenantService.create_related_objects')
    def test_tenant_created_signal(self, mock_create_objects):
        """Test tenant created signal."""
        # Connect signal handler
        from ..signals.core import tenant_created_handler
        
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Send signal
        tenant_created.send(sender=Tenant, tenant=tenant, created_by=self.user)
        
        # Verify signal was handled
        mock_create_objects.assert_called_once_with(tenant)
    
    @patch('tenants.signals.core.TenantAuditService.log_action')
    def test_tenant_updated_signal(self, mock_log_action):
        """Test tenant updated signal."""
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Connect signal handler
        from ..signals.core import tenant_updated_handler
        
        # Update tenant
        tenant.name = 'Updated Tenant'
        tenant.save()
        
        # Send signal with changes
        changes = {'name': {'old': 'Test Tenant', 'new': 'Updated Tenant'}}
        tenant_updated.send(
            sender=Tenant,
            tenant=tenant,
            changes=changes,
            updated_by=self.user
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.core.TenantNotification.objects.create')
    def test_tenant_deleted_signal(self, mock_create_notification):
        """Test tenant deleted signal."""
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Connect signal handler
        from ..signals.core import tenant_deleted_handler
        
        # Soft delete tenant
        tenant.is_deleted = True
        tenant.deleted_at = timezone.now()
        tenant.save()
        
        # Send signal
        tenant_deleted.send(
            sender=Tenant,
            tenant=tenant,
            deleted_by=self.user
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.core.TenantNotification.objects.create')
    def test_tenant_settings_updated_signal(self, mock_create_notification):
        """Test tenant settings updated signal."""
        # Create tenant and settings
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        settings = TenantSettings.objects.create(tenant=tenant)
        
        # Connect signal handler
        from ..signals.core import tenant_settings_updated_handler
        
        # Update settings
        settings.enable_smartlink = False
        settings.save()
        
        # Send signal
        from ..signals.core import tenant_settings_updated
        tenant_settings_updated.send(
            sender=TenantSettings,
            settings=settings,
            tenant=tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.core.TenantNotification.objects.create')
    def test_tenant_invoice_created_signal(self, mock_create_notification):
        """Test tenant invoice created signal."""
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            owner=self.user,
            plan=self.plan,
        )
        
        # Connect signal handler
        from ..signals.core import tenant_invoice_created_handler
        
        # Create invoice
        invoice = TenantInvoice.objects.create(
            tenant=tenant,
            invoice_number='INV-001',
            status='pending',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            total_amount=29.99,
        )
        
        # Send signal
        from ..signals.core import tenant_invoice_created
        tenant_invoice_created.send(
            sender=TenantInvoice,
            invoice=invoice,
            tenant=tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()


class TestPlanSignals(TestCase):
    """Test cases for plan-related signals."""
    
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
        )
    
    @patch('tenants.signals.plan.TenantNotification.objects.create')
    def test_plan_usage_recorded_signal(self, mock_create_notification):
        """Test plan usage recorded signal."""
        # Create usage
        usage = PlanUsage.objects.create(
            tenant=self.tenant,
            period='monthly',
            api_calls_used=1200,  # Exceeds limit
            api_calls_limit=1000,
            api_calls_percentage=120.0,
        )
        
        # Connect signal handler
        from ..signals.plan import plan_usage_recorded_handler
        
        # Send signal
        plan_usage_recorded.send(
            sender=PlanUsage,
            usage=usage,
            tenant=self.tenant
        )
        
        # Verify notification was created for quota exceeded
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.plan.TenantNotification.objects.create')
    def test_quota_exceeded_signal(self, mock_create_notification):
        """Test quota exceeded signal."""
        # Create usage that exceeds quota
        usage = PlanUsage.objects.create(
            tenant=self.tenant,
            period='monthly',
            api_calls_used=1500,
            api_calls_limit=1000,
            api_calls_percentage=150.0,
        )
        
        # Connect signal handler
        from ..signals.plan import quota_exceeded_handler
        
        # Send signal
        quota_exceeded.send(
            sender=PlanUsage,
            usage=usage,
            tenant=self.tenant,
            exceeded_metrics=['api_calls']
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.plan.TenantNotification.objects.create')
    def test_plan_upgrade_created_signal(self, mock_create_notification):
        """Test plan upgrade created signal."""
        # Create upgrade plan
        pro_plan = Plan.objects.create(
            name='Pro Plan',
            slug='pro',
            plan_type='professional',
            price_monthly=99.99,
        )
        
        # Create upgrade request
        from ..models.plan import PlanUpgrade
        upgrade = PlanUpgrade.objects.create(
            tenant=self.tenant,
            from_plan=self.plan,
            to_plan=pro_plan,
            price_difference=70.00,
            reason='Feature requirements',
        )
        
        # Connect signal handler
        from ..signals.plan import plan_upgrade_created_handler
        
        # Send signal
        from ..signals.plan import plan_upgrade_created
        plan_upgrade_created.send(
            sender=PlanUpgrade,
            upgrade=upgrade,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.plan.TenantAuditService.log_action')
    def test_plan_updated_signal(self, mock_log_action):
        """Test plan updated signal."""
        # Connect signal handler
        from ..signals.plan import plan_updated_handler
        
        # Update plan
        self.plan.price_monthly = 39.99
        self.plan.save()
        
        # Send signal with changes
        changes = {'price_monthly': {'old': 29.99, 'new': 39.99}}
        from ..signals.plan import plan_updated
        plan_updated.send(
            sender=Plan,
            plan=self.plan,
            changes=changes,
            updated_by=self.user
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()


class TestSecuritySignals(TestCase):
    """Test cases for security-related signals."""
    
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
    
    @patch('tenants.signals.security.TenantAuditService.log_action')
    def test_api_key_created_signal(self, mock_log_action):
        """Test API key created signal."""
        # Connect signal handler
        from ..signals.security import api_key_created_handler
        
        # Create API key
        api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Test API Key',
            scopes=['read', 'write'],
            rate_limit_per_minute=60,
        )
        
        # Send signal
        api_key_created.send(
            sender=TenantAPIKey,
            api_key=api_key,
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.security.TenantAuditService.log_action')
    def test_api_key_used_signal(self, mock_log_action):
        """Test API key used signal."""
        # Create API key
        api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Test API Key',
            scopes=['read', 'write'],
            rate_limit_per_minute=60,
        )
        
        # Connect signal handler
        from ..signals.security import api_key_used_handler
        
        # Send signal
        from ..signals.security import api_key_used
        api_key_used.send(
            sender=TenantAPIKey,
            api_key=api_key,
            tenant=self.tenant,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.security.TenantNotification.objects.create')
    def test_api_key_revoked_signal(self, mock_create_notification):
        """Test API key revoked signal."""
        # Create API key
        api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name='Test API Key',
            scopes=['read', 'write'],
            rate_limit_per_minute=60,
        )
        
        # Connect signal handler
        from ..signals.security import api_key_revoked_handler
        
        # Revoke API key
        api_key.status = 'revoked'
        api_key.save()
        
        # Send signal
        from ..signals.security import api_key_revoked
        api_key_revoked.send(
            sender=TenantAPIKey,
            api_key=api_key,
            tenant=self.tenant,
            revoked_by=self.user
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.security.TenantAuditService.log_action')
    def test_webhook_triggered_signal(self, mock_log_action):
        """Test webhook triggered signal."""
        # Create webhook config
        webhook = TenantWebhookConfig.objects.create(
            tenant=self.tenant,
            name='Test Webhook',
            url='https://example.com/webhook',
            events=['tenant.created'],
            is_active=True,
        )
        
        # Connect signal handler
        from ..signals.security import webhook_triggered_handler
        
        # Send signal
        from ..signals.security import webhook_triggered
        webhook_triggered.send(
            sender=TenantWebhookConfig,
            webhook=webhook,
            tenant=self.tenant,
            event='tenant.created',
            payload={'tenant_id': str(self.tenant.id)},
            status_code=200,
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.security.TenantNotification.objects.create')
    def test_security_event_detected_signal(self, mock_create_notification):
        """Test security event detected signal."""
        # Connect signal handler
        from ..signals.security import security_event_detected_handler
        
        # Send signal
        from ..signals.security import security_event_detected
        security_event_detected.send(
            sender=TenantAuditLog,
            tenant=self.tenant,
            event_type='suspicious_login',
            severity='high',
            details={
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'timestamp': timezone.now().isoformat(),
            }
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()


class TestOnboardingSignals(TestCase):
    """Test cases for onboarding-related signals."""
    
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
    
    @patch('tenants.signals.onboarding.TenantNotification.objects.create')
    def test_onboarding_started_signal(self, mock_create_notification):
        """Test onboarding started signal."""
        # Create onboarding
        onboarding = TenantOnboarding.objects.create(
            tenant=self.tenant,
            status='in_progress',
            current_step='profile_setup',
        )
        
        # Connect signal handler
        from ..signals.onboarding import onboarding_started_handler
        
        # Send signal
        onboarding_started.send(
            sender=TenantOnboarding,
            onboarding=onboarding,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.onboarding.TenantNotification.objects.create')
    def test_onboarding_step_completed_signal(self, mock_create_notification):
        """Test onboarding step completed signal."""
        # Create onboarding step
        step = TenantOnboardingStep.objects.create(
            tenant=self.tenant,
            step_key='profile_setup',
            step_type='manual',
            label='Profile Setup',
            status='done',
            sort_order=1,
        )
        
        # Connect signal handler
        from ..signals.onboarding import onboarding_step_completed_handler
        
        # Send signal
        from ..signals.onboarding import onboarding_step_completed
        onboarding_step_completed.send(
            sender=TenantOnboardingStep,
            step=step,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.onboarding.TenantNotification.objects.create')
    def test_onboarding_completed_signal(self, mock_create_notification):
        """Test onboarding completed signal."""
        # Create onboarding
        onboarding = TenantOnboarding.objects.create(
            tenant=self.tenant,
            status='completed',
            completed_at=timezone.now(),
            completion_pct=100,
        )
        
        # Connect signal handler
        from ..signals.onboarding import onboarding_completed_handler
        
        # Send signal
        from ..signals.onboarding import onboarding_completed
        onboarding_completed.send(
            sender=TenantOnboarding,
            onboarding=onboarding,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.onboarding.TenantNotification.objects.create')
    def test_trial_extension_requested_signal(self, mock_create_notification):
        """Test trial extension requested signal."""
        # Create trial extension
        from ..models.onboarding import TenantTrialExtension
        extension = TenantTrialExtension.objects.create(
            tenant=self.tenant,
            days_extended=7,
            reason='feature_evaluation',
            status='requested',
        )
        
        # Connect signal handler
        from ..signals.onboarding import trial_extension_requested_handler
        
        # Send signal
        from ..signals.onboarding import trial_extension_requested
        trial_extension_requested.send(
            sender=TenantTrialExtension,
            extension=extension,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()


class TestAnalyticsSignals(TestCase):
    """Test cases for analytics-related signals."""
    
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
    
    @patch('tenants.signals.analytics.TenantMetricService.record_metric')
    def test_metric_recorded_signal(self, mock_record_metric):
        """Test metric recorded signal."""
        # Connect signal handler
        from ..signals.analytics import metric_recorded_handler
        
        # Send signal
        metric_recorded.send(
            sender=TenantMetric,
            tenant=self.tenant,
            metric_type='api_calls',
            value=100,
            unit='count',
            date=timezone.now().date()
        )
        
        # Verify metric was recorded
        mock_record_metric.assert_called_once()
    
    @patch('tenants.signals.analytics.TenantNotification.objects.create')
    def test_health_score_updated_signal(self, mock_create_notification):
        """Test health score updated signal."""
        # Create health score
        health_score = TenantHealthScore.objects.create(
            tenant=self.tenant,
            overall_score=45.0,  # Poor score
            health_grade='F',
            risk_level='critical',
        )
        
        # Connect signal handler
        from ..signals.analytics import health_score_updated_handler
        
        # Send signal
        from ..signals.analytics import health_score_updated
        health_score_updated.send(
            sender=TenantHealthScore,
            health_score=health_score,
            tenant=self.tenant,
            previous_score=50.0,
        )
        
        # Verify notification was created for poor health score
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.analytics.TenantAuditService.log_action')
    def test_feature_flag_toggled_signal(self, mock_log_action):
        """Test feature flag toggled signal."""
        # Create feature flag
        from ..models.analytics import TenantFeatureFlag
        flag = TenantFeatureFlag.objects.create(
            tenant=self.tenant,
            flag_key='new_dashboard',
            flag_type='boolean',
            is_enabled=True,
        )
        
        # Connect signal handler
        from ..signals.analytics import feature_flag_toggled_handler
        
        # Toggle flag
        flag.is_enabled = False
        flag.save()
        
        # Send signal
        from ..signals.analytics import feature_flag_toggled
        feature_flag_toggled.send(
            sender=TenantFeatureFlag,
            flag=flag,
            tenant=self.tenant,
            previous_value=True,
            new_value=False
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.analytics.TenantAuditService.log_action')
    def test_notification_created_signal(self, mock_log_action):
        """Test notification created signal."""
        # Create notification
        notification = TenantNotification.objects.create(
            tenant=self.tenant,
            title='Test Notification',
            message='Test message',
            notification_type='system',
            priority='medium',
        )
        
        # Connect signal handler
        from ..signals.analytics import notification_created_handler
        
        # Send signal
        from ..signals.analytics import notification_created
        notification_created.send(
            sender=TenantNotification,
            notification=notification,
            tenant=self.tenant
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()


class TestBrandingSignals(TestCase):
    """Test cases for branding-related signals."""
    
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
    
    @patch('tenants.signals.branding.TenantAuditService.log_action')
    def test_branding_updated_signal(self, mock_log_action):
        """Test branding updated signal."""
        # Create branding
        branding = TenantBranding.objects.create(
            tenant=self.tenant,
            app_name='Test App',
            primary_color='#007bff',
        )
        
        # Connect signal handler
        from ..signals.branding import branding_updated_handler
        
        # Update branding
        branding.primary_color='#28a745'
        branding.save()
        
        # Send signal
        from ..signals.branding import branding_updated
        branding_updated.send(
            sender=TenantBranding,
            branding=branding,
            tenant=self.tenant,
            changes={'primary_color': {'old': '#007bff', 'new': '#28a745'}}
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.branding.TenantNotification.objects.create')
    def test_domain_verified_signal(self, mock_create_notification):
        """Test domain verified signal."""
        # Create domain
        domain = TenantDomain.objects.create(
            tenant=self.tenant,
            domain='test.example.com',
            dns_status='verified',
        )
        
        # Connect signal handler
        from ..signals.branding import domain_verified_handler
        
        # Send signal
        from ..signals.branding import domain_verified
        domain_verified.send(
            sender=TenantDomain,
            domain=domain,
            tenant=self.tenant
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.branding.TenantNotification.objects.create')
    def test_ssl_certificate_updated_signal(self, mock_create_notification):
        """Test SSL certificate updated signal."""
        # Create domain with SSL
        domain = TenantDomain.objects.create(
            tenant=self.tenant,
            domain='test.example.com',
            ssl_status='verified',
            ssl_expires_at=timezone.now() + timedelta(days=90),
        )
        
        # Connect signal handler
        from ..signals.branding import ssl_certificate_updated_handler
        
        # Update SSL certificate
        domain.ssl_expires_at = timezone.now() + timedelta(days=365)
        domain.save()
        
        # Send signal
        from ..signals.branding import ssl_certificate_updated
        ssl_certificate_updated.send(
            sender=TenantDomain,
            domain=domain,
            tenant=self.tenant,
            previous_expiry=timezone.now() + timedelta(days=90),
            new_expiry=timezone.now() + timedelta(days=365)
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()


class TestResellerSignals(TestCase):
    """Test cases for reseller-related signals."""
    
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
    
    @patch('tenants.signals.reseller.TenantAuditService.log_action')
    def test_reseller_created_signal(self, mock_log_action):
        """Test reseller created signal."""
        # Create reseller
        reseller = ResellerConfig.objects.create(
            parent_tenant=self.tenant,
            company_name='Test Reseller',
            reseller_id='RES001',
            commission_type='percentage',
            commission_pct=10.0,
        )
        
        # Connect signal handler
        from ..signals.reseller import reseller_created_handler
        
        # Send signal
        reseller_created.send(
            sender=ResellerConfig,
            reseller=reseller,
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
    
    @patch('tenants.signals.reseller.TenantNotification.objects.create')
    def test_commission_calculated_signal(self, mock_create_notification):
        """Test commission calculated signal."""
        # Create reseller
        reseller = ResellerConfig.objects.create(
            parent_tenant=self.tenant,
            company_name='Test Reseller',
            reseller_id='RES001',
            commission_type='percentage',
            commission_pct=10.0,
        )
        
        # Connect signal handler
        from ..signals.reseller import commission_calculated_handler
        
        # Send signal
        from ..signals.reseller import commission_calculated
        commission_calculated.send(
            sender=ResellerConfig,
            reseller=reseller,
            tenant=self.tenant,
            commission_amount=100.00,
            period='monthly'
        )
        
        # Verify notification was created
        mock_create_notification.assert_called_once()
    
    @patch('tenants.signals.reseller.TenantAuditService.log_action')
    def test_referral_activity_tracked_signal(self, mock_log_action):
        """Test referral activity tracked signal."""
        # Create reseller
        reseller = ResellerConfig.objects.create(
            parent_tenant=self.tenant,
            company_name='Test Reseller',
            reseller_id='RES001',
            commission_type='percentage',
            commission_pct=10.0,
        )
        
        # Connect signal handler
        from ..signals.reseller import referral_activity_tracked_handler
        
        # Send signal
        from ..signals.reseller import referral_activity_tracked
        referral_activity_tracked.send(
            sender=ResellerConfig,
            reseller=reseller,
            tenant=self.tenant,
            referral_type='new_sign_up',
            referral_data={
                'referral_code': 'REF123',
                'referred_tenant': 'new-tenant',
                'commission_amount': 50.00
            }
        )
        
        # Verify audit log was created
        mock_log_action.assert_called_once()
