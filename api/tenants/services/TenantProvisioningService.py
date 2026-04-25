"""
Tenant Provisioning Service

This service handles tenant provisioning including setup,
initialization, and configuration of new tenant environments.
"""

import uuid
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant, TenantSettings, TenantOnboarding, TenantOnboardingStep
from ..models.security import TenantAPIKey, TenantAuditLog
from ..models.branding import TenantBranding

User = get_user_model()


class TenantProvisioningService:
    """
    Service class for tenant provisioning operations.
    
    This service handles the complete provisioning workflow
    for new tenants including setup, configuration, and onboarding.
    """
    
    # Default onboarding steps
    DEFAULT_ONBOARDING_STEPS = [
        ('welcome', 'Welcome', 'Welcome to the platform! Get started with a quick tour.'),
        ('profile_setup', 'Profile Setup', 'Complete your profile and company information.'),
        ('team_invitation', 'Team Invitation', 'Invite team members to collaborate.'),
        ('integration_setup', 'Integration Setup', 'Connect your existing tools and services.'),
        ('first_campaign', 'First Campaign', 'Create your first campaign to start earning.'),
        ('billing_setup', 'Billing Setup', 'Configure payment methods and billing preferences.'),
    ]
    
    @staticmethod
    def provision_tenant(data, created_by=None):
        """
        Complete tenant provisioning workflow.
        
        Args:
            data (dict): Tenant provisioning data
            created_by (User): User provisioning the tenant
            
        Returns:
            dict: Provisioning results with tenant and setup info
            
        Raises:
            ValidationError: If provisioning fails
        """
        with transaction.atomic():
            # Step 1: Create tenant
            from .TenantService import TenantService
            tenant = TenantService.create_tenant(data, created_by)
            
            # Step 2: Setup branding
            TenantProvisioningService._setup_branding(tenant, data)
            
            # Step 3: Create API key
            api_key = TenantProvisioningService._create_default_api_key(tenant, created_by)
            
            # Step 4: Setup onboarding
            onboarding = TenantProvisioningService._setup_onboarding(tenant, data)
            
            # Step 5: Initialize settings
            TenantProvisioningService._initialize_settings(tenant, data)
            
            # Step 6: Create initial resources
            TenantProvisioningService._create_initial_resources(tenant, data)
            
            # Step 7: Send notifications
            TenantProvisioningService._send_provisioning_notifications(tenant, created_by)
            
            # Log provisioning
            if created_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=created_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    description=f"Tenant {tenant.name} provisioned successfully"
                )
            
            return {
                'tenant': tenant,
                'api_key': api_key,
                'onboarding': onboarding,
                'status': 'success',
                'message': 'Tenant provisioned successfully'
            }
    
    @staticmethod
    def _setup_branding(tenant, data):
        """Setup tenant branding with defaults."""
        branding_data = {
            'tenant': tenant,
            'primary_color': data.get('primary_color', '#007bff'),
            'secondary_color': data.get('secondary_color', '#6c757d'),
            'accent_color': data.get('accent_color', '#28a745'),
            'font_family': data.get('font_family', 'Inter, sans-serif'),
            'button_radius': data.get('button_radius', '6px'),
            'app_name': data.get('app_name', tenant.name),
            'app_description': data.get('app_description'),
            'email_from_name': data.get('email_from_name', tenant.name),
            'website_url': data.get('website_url'),
        }
        
        return TenantBranding.objects.create(**branding_data)
    
    @staticmethod
    def _create_default_api_key(tenant, created_by=None):
        """Create default API key for tenant."""
        from ..models.security import TenantAPIKey
        
        key = TenantAPIKey.generate_key()
        api_key_data = {
            'tenant': tenant,
            'name': 'Default API Key',
            'description': 'Default API key created during provisioning',
            'scopes': ['read', 'write', 'admin'],
            'rate_limit_per_minute': 60,
            'rate_limit_per_hour': 1000,
            'rate_limit_per_day': 10000,
            'status': 'active',
            'created_by': created_by,
        }
        
        api_key = TenantAPIKey.objects.create(**api_key_data)
        api_key.set_key(key)
        api_key.save()
        
        # Store the actual key in the result (only shown once)
        api_key.actual_key = key
        
        return api_key
    
    @staticmethod
    def _setup_onboarding(tenant, data):
        """Setup tenant onboarding process."""
        # Create onboarding record
        onboarding_data = {
            'tenant': tenant,
            'completion_pct': 0,
            'current_step': 'welcome',
            'status': 'not_started',
            'skip_welcome': data.get('skip_welcome', False),
            'enable_tips': data.get('enable_tips', True),
            'send_reminders': data.get('send_reminders', True),
        }
        
        onboarding = TenantOnboarding.objects.create(**onboarding_data)
        
        # Create onboarding steps
        steps = data.get('onboarding_steps', TenantProvisioningService.DEFAULT_ONBOARDING_STEPS)
        
        for i, (step_key, label, description) in enumerate(steps):
            step_data = {
                'tenant': tenant,
                'step_key': step_key,
                'step_type': TenantProvisioningService._get_step_type(step_key),
                'label': label,
                'description': description,
                'sort_order': i,
                'is_required': step_key not in ['welcome'],
                'can_skip': step_key in ['team_invitation', 'integration_setup'],
            }
            TenantOnboardingStep.objects.create(**step_data)
        
        return onboarding
    
    @staticmethod
    def _get_step_type(step_key):
        """Get step type based on step key."""
        step_types = {
            'welcome': 'welcome',
            'profile_setup': 'profile_setup',
            'team_invitation': 'team_invitation',
            'integration_setup': 'integration_setup',
            'first_campaign': 'first_campaign',
            'billing_setup': 'billing_setup',
        }
        return step_types.get(step_key, 'custom')
    
    @staticmethod
    def _initialize_settings(tenant, data):
        """Initialize tenant-specific settings."""
        settings = tenant.settings
        
        # Apply provisioning-specific settings
        if 'enable_features' in data:
            features = data['enable_features']
            settings.enable_smartlink = features.get('smartlink', settings.enable_smartlink)
            settings.enable_ai_engine = features.get('ai_engine', settings.enable_ai_engine)
            settings.enable_publisher_tools = features.get('publisher_tools', settings.enable_publisher_tools)
            settings.enable_advertiser_portal = features.get('advertiser_portal', settings.enable_advertiser_portal)
        
        if 'notification_preferences' in data:
            notifications = data['notification_preferences']
            settings.enable_email_notifications = notifications.get('email', settings.enable_email_notifications)
            settings.enable_push_notifications = notifications.get('push', settings.enable_push_notifications)
            settings.enable_sms_notifications = notifications.get('sms', settings.enable_sms_notifications)
        
        if 'security_settings' in data:
            security = data['security_settings']
            settings.enable_two_factor_auth = security.get('two_factor', settings.enable_two_factor_auth)
            settings.session_timeout_minutes = security.get('session_timeout', settings.session_timeout_minutes)
            settings.password_min_length = security.get('password_min_length', settings.password_min_length)
        
        settings.save()
    
    @staticmethod
    def _create_initial_resources(tenant, data):
        """Create initial resources for tenant."""
        # Create default user roles if needed
        if data.get('create_default_roles', True):
            TenantProvisioningService._create_default_roles(tenant)
        
        # Create default templates if needed
        if data.get('create_default_templates', True):
            TenantProvisioningService._create_default_templates(tenant)
        
        # Setup default permissions
        TenantProvisioningService._setup_default_permissions(tenant, data.get('owner'))
    
    @staticmethod
    def _create_default_roles(tenant):
        """Create default user roles for tenant."""
        # This would create default roles like admin, user, etc.
        # Implementation depends on your role system
        pass
    
    @staticmethod
    def _create_default_templates(tenant):
        """Create default templates for tenant."""
        # This would create default email templates, campaign templates, etc.
        # Implementation depends on your template system
        pass
    
    @staticmethod
    def _setup_default_permissions(tenant, owner):
        """Setup default permissions for tenant owner."""
        # This would assign appropriate permissions to the tenant owner
        # Implementation depends on your permission system
        pass
    
    @staticmethod
    def _send_provisioning_notifications(tenant, created_by=None):
        """Send provisioning notifications."""
        # Send welcome email
        TenantProvisioningService._send_welcome_email(tenant)
        
        # Send notification to created_by if different from owner
        if created_by and created_by != tenant.owner:
            TenantProvisioningService._send_provisioning_complete_notification(tenant, created_by)
        
        # Trigger webhook if configured
        TenantProvisioningService._trigger_provisioning_webhook(tenant)
    
    @staticmethod
    def _send_welcome_email(tenant):
        """Send welcome email to tenant owner."""
        # This would send a welcome email using your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _send_provisioning_complete_notification(tenant, user):
        """Send provisioning complete notification."""
        # This would send a notification to the user who provisioned the tenant
        # Implementation depends on your notification system
        pass
    
    @staticmethod
    def _trigger_provisioning_webhook(tenant):
        """Trigger provisioning webhook if configured."""
        from ..models.security import TenantWebhookConfig
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        for webhook in webhooks:
            if webhook.can_send_event('tenant.provisioned'):
                # This would trigger the webhook
                # Implementation depends on your webhook system
                pass
    
    @staticmethod
    def start_onboarding(tenant, started_by=None):
        """
        Start tenant onboarding process.
        
        Args:
            tenant (Tenant): Tenant to start onboarding for
            started_by (User): User starting onboarding
            
        Returns:
            TenantOnboarding: Onboarding instance
        """
        onboarding = tenant.onboarding
        onboarding.start_onboarding()
        
        # Log onboarding start
        if started_by:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='access',
                actor=started_by,
                model_name='TenantOnboarding',
                object_id=str(onboarding.id),
                object_repr=str(onboarding),
                description=f"Onboarding started for {tenant.name}"
            )
        
        return onboarding
    
    @staticmethod
    def complete_onboarding_step(tenant, step_key, step_data=None, completed_by=None):
        """
        Complete an onboarding step.
        
        Args:
            tenant (Tenant): Tenant
            step_key (str): Step key to complete
            step_data (dict): Step data
            completed_by (User): User completing the step
            
        Returns:
            TenantOnboardingStep: Completed step instance
        """
        try:
            step = TenantOnboardingStep.objects.get(
                tenant=tenant,
                step_key=step_key
            )
        except TenantOnboardingStep.DoesNotExist:
            raise ValidationError(f"Onboarding step '{step_key}' not found.")
        
        step.complete_step(step_data)
        
        # Update onboarding progress
        onboarding = tenant.onboarding
        total_steps = TenantOnboardingStep.objects.filter(tenant=tenant).count()
        completed_steps = TenantOnboardingStep.objects.filter(
            tenant=tenant,
            is_done=True
        ).count()
        
        progress = int((completed_steps / total_steps) * 100)
        onboarding.update_progress(step_key, progress - onboarding.completion_pct)
        
        # Log step completion
        if completed_by:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='update',
                actor=completed_by,
                model_name='TenantOnboardingStep',
                object_id=str(step.id),
                object_repr=str(step),
                description=f"Onboarding step '{step.label}' completed"
            )
        
        return step
    
    @staticmethod
    def skip_onboarding_step(tenant, step_key, reason=None, skipped_by=None):
        """
        Skip an onboarding step.
        
        Args:
            tenant (Tenant): Tenant
            step_key (str): Step key to skip
            reason (str): Reason for skipping
            skipped_by (User): User skipping the step
            
        Returns:
            TenantOnboardingStep: Skipped step instance
        """
        try:
            step = TenantOnboardingStep.objects.get(
                tenant=tenant,
                step_key=step_key
            )
        except TenantOnboardingStep.DoesNotExist:
            raise ValidationError(f"Onboarding step '{step_key}' not found.")
        
        step.skip_step(reason)
        
        # Update onboarding progress
        onboarding = tenant.onboarding
        onboarding.skip_step(step_key)
        
        # Log step skip
        if skipped_by:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='update',
                actor=skipped_by,
                model_name='TenantOnboardingStep',
                object_id=str(step.id),
                object_repr=str(step),
                description=f"Onboarding step '{step.label}' skipped: {reason or 'No reason'}"
            )
        
        return step
    
    @staticmethod
    def get_provisioning_status(tenant):
        """
        Get comprehensive provisioning status.
        
        Args:
            tenant (Tenant): Tenant to check
            
        Returns:
            dict: Provisioning status information
        """
        status = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'status': tenant.status,
            'created_at': tenant.created_at,
            'is_trial': tenant.trial_ends_at is not None,
            'trial_ends_at': tenant.trial_ends_at,
            'days_until_trial_expiry': tenant.days_until_trial_expiry,
        }
        
        # Onboarding status
        if hasattr(tenant, 'onboarding'):
            onboarding = tenant.onboarding
            status['onboarding'] = {
                'status': onboarding.status,
                'completion_pct': onboarding.completion_pct,
                'current_step': onboarding.current_step,
                'started_at': onboarding.started_at,
                'completed_at': onboarding.completed_at,
                'days_since_start': onboarding.days_since_start,
                'needs_attention': onboarding.needs_attention,
            }
            
            # Step details
            steps = TenantOnboardingStep.objects.filter(tenant=tenant).order_by('sort_order')
            status['onboarding']['steps'] = [
                {
                    'key': step.step_key,
                    'label': step.label,
                    'status': step.status,
                    'is_done': step.is_done,
                    'is_required': step.is_required,
                    'can_skip': step.can_skip,
                    'time_spent': step.time_spent_display,
                }
                for step in steps
            ]
        
        # API keys status
        api_keys = TenantAPIKey.objects.filter(tenant=tenant, is_deleted=False)
        status['api_keys'] = {
            'total': api_keys.count(),
            'active': api_keys.filter(status='active').count(),
            'last_used': api_keys.order_by('-last_used_at').first().last_used_at if api_keys.exists() else None,
        }
        
        # Branding status
        if hasattr(tenant, 'branding'):
            branding = tenant.branding
            status['branding'] = {
                'has_logo': bool(branding.logo),
                'has_custom_colors': branding.primary_color != '#007bff',
                'has_custom_domain': bool(tenant.domain),
                'setup_complete': bool(branding.logo and branding.app_name),
            }
        
        return status
    
    @staticmethod
    def validate_provisioning_data(data):
        """
        Validate tenant provisioning data.
        
        Args:
            data (dict): Provisioning data to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate required fields
        required_fields = ['name', 'slug', 'owner', 'plan']
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f'{field} is required.')
        
        # Validate owner exists and is active
        if 'owner' in data:
            try:
                owner = User.objects.get(id=data['owner'])
                if not owner.is_active:
                    errors.append('Owner user is not active.')
            except User.DoesNotExist:
                errors.append('Owner user does not exist.')
        
        # Validate plan exists and is active
        if 'plan' in data:
            try:
                plan = Plan.objects.get(id=data['plan'])
                if not plan.is_active:
                    errors.append('Selected plan is not active.')
            except Plan.DoesNotExist:
                errors.append('Selected plan does not exist.')
        
        # Validate custom settings if provided
        if 'enable_features' in data:
            features = data['enable_features']
            if not isinstance(features, dict):
                errors.append('enable_features must be a dictionary.')
        
        # Validate notification preferences if provided
        if 'notification_preferences' in data:
            notifications = data['notification_preferences']
            valid_channels = ['email', 'push', 'sms']
            for channel in notifications:
                if channel not in valid_channels:
                    errors.append(f'Invalid notification channel: {channel}')
        
        return len(errors) == 0, errors
