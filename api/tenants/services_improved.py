"""
Tenant Services - Improved Version with Enhanced Security and Features

This module contains comprehensive service classes for tenant management
with advanced security, proper error handling, and extensive functionality.
"""

import uuid
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
import logging

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)
from .permissions_improved import BaseTenantPermission

logger = logging.getLogger(__name__)

User = get_user_model()


class TenantService:
    """
    Comprehensive service class for tenant management operations.
    
    This service encapsulates all business logic for tenant
    creation, updates, validation, and related operations with
    enhanced security and audit logging.
    """
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 300)  # 5 minutes
    
    def create_tenant(self, data: Dict[str, Any], created_by: Optional[User] = None) -> Tenant:
        """
        Create a new tenant with comprehensive validation and setup.
        
        Args:
            data: Tenant creation data
            created_by: User creating the tenant
            
        Returns:
            Created tenant instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Validate required fields
            self._validate_tenant_creation_data(data)
            
            # Check for existing tenant with same slug/domain
            self._check_tenant_uniqueness(data)
            
            # Get or validate owner
            owner = self._get_or_create_owner(data, created_by)
            
            # Create tenant
            tenant = self._create_tenant_instance(data, owner, created_by)
            
            # Create related objects
            self._create_tenant_defaults(tenant)
            
            # Send welcome email
            self._send_welcome_email(tenant)
            
            # Log creation
            tenant.audit_log(
                action='created',
                details={
                    'plan': tenant.plan,
                    'max_users': tenant.max_users,
                    'created_by': created_by.email if created_by else 'system',
                    'creation_source': 'tenant_service',
                },
                user=created_by
            )
            
            # Clear cache
            self._clear_tenant_cache(tenant)
            
            return tenant
    
    def _validate_tenant_creation_data(self, data: Dict[str, Any]) -> None:
        """Validate tenant creation data."""
        required_fields = ['name', 'plan']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(_(f'{field} is required.'))
        
        # Validate name
        name = data['name'].strip()
        if len(name) < 2:
            raise ValidationError(_('Tenant name must be at least 2 characters long.'))
        
        if len(name) > 255:
            raise ValidationError(_('Tenant name cannot exceed 255 characters.'))
        
        # Validate plan
        valid_plans = [choice[0] for choice in Tenant.PLAN_CHOICES]
        if data['plan'] not in valid_plans:
            raise ValidationError(_('Invalid plan choice.'))
        
        # Validate max_users
        max_users = data.get('max_users', 100)
        if not isinstance(max_users, int) or max_users < 1 or max_users > 10000:
            raise ValidationError(_('Max users must be between 1 and 10,000.'))
        
        # Validate email if provided
        if 'admin_email' in data:
            email = data['admin_email'].strip().lower()
            if not self._is_valid_email(email):
                raise ValidationError(_('Invalid admin email address.'))
    
    def _check_tenant_uniqueness(self, data: Dict[str, Any]) -> None:
        """Check for tenant uniqueness."""
        # Check slug uniqueness
        if 'slug' in data and data['slug']:
            if Tenant.objects.filter(slug=data['slug']).exists():
                raise ValidationError(_('Tenant slug already exists.'))
        
        # Check domain uniqueness
        if 'domain' in data and data['domain']:
            if Tenant.objects.filter(domain=data['domain']).exists():
                raise ValidationError(_('Domain already exists.'))
    
    def _get_or_create_owner(self, data: Dict[str, Any], created_by: Optional[User]) -> User:
        """Get or create tenant owner."""
        owner_email = data.get('owner_email') or data.get('admin_email')
        
        if not owner_email:
            raise ValidationError(_('Owner email is required.'))
        
        owner_email = owner_email.strip().lower()
        
        # Try to get existing user
        try:
            owner = User.objects.get(email=owner_email)
        except User.DoesNotExist:
            # Create new user if allowed
            if getattr(settings, 'TENANT_AUTO_CREATE_OWNER', False):
                owner = self._create_tenant_owner(owner_email, data)
            else:
                raise ValidationError(_('User with this email does not exist.'))
        
        return owner
    
    def _create_tenant_owner(self, email: str, data: Dict[str, Any]) -> User:
        """Create new tenant owner user."""
        password = data.get('password')
        if not password:
            password = User.objects.make_random_password()
        
        user_data = {
            'email': email,
            'username': email.split('@')[0],
            'is_active': True,
            'is_staff': False,
            'is_superuser': False,
        }
        
        # Add additional fields if available
        if 'first_name' in data:
            user_data['first_name'] = data['first_name']
        if 'last_name' in data:
            user_data['last_name'] = data['last_name']
        
        user = User.objects.create_user(**user_data, password=password)
        
        # Send password email
        self._send_owner_password_email(user, password)
        
        return user
    
    def _create_tenant_instance(self, data: Dict[str, Any], owner: User, created_by: Optional[User]) -> Tenant:
        """Create tenant instance."""
        # Generate slug if not provided
        slug = data.get('slug')
        if not slug:
            slug = self._generate_unique_slug(data['name'])
        
        # Create tenant
        tenant_data = {
            'name': data['name'].strip(),
            'slug': slug,
            'owner': owner,
            'plan': data['plan'],
            'max_users': data.get('max_users', 100),
            'admin_email': data.get('admin_email', owner.email),
            'contact_phone': data.get('contact_phone'),
            'primary_color': data.get('primary_color', '#007bff'),
            'secondary_color': data.get('secondary_color', '#6c757d'),
            'timezone': data.get('timezone', 'UTC'),
            'country_code': data.get('country_code'),
            'currency_code': data.get('currency_code', 'USD'),
            'data_region': data.get('data_region', 'us-east-1'),
            'domain': data.get('domain'),
            'android_package_name': data.get('android_package_name'),
            'ios_bundle_id': data.get('ios_bundle_id'),
            'created_by': created_by,
        }
        
        tenant = Tenant.objects.create(**tenant_data)
        return tenant
    
    def _create_tenant_defaults(self, tenant: Tenant) -> None:
        """Create default related objects for tenant."""
        # Create settings
        TenantSettings.objects.get_or_create(tenant=tenant)
        
        # Create billing
        billing, created = TenantBilling.objects.get_or_create(
            tenant=tenant,
            defaults={
                'status': 'trial',
                'trial_ends_at': timezone.now() + timedelta(days=14),
                'currency': tenant.currency_code or 'USD',
            }
        )
        
        # If billing was just created, set trial end date
        if created:
            tenant.trial_ends_at = billing.trial_ends_at
            tenant.status = 'trial'
            tenant.save(update_fields=['trial_ends_at', 'status'])
    
    def _generate_unique_slug(self, name: str) -> str:
        """Generate unique slug from name."""
        from django.utils.text import slugify
        
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _send_welcome_email(self, tenant: Tenant) -> None:
        """Send welcome email to tenant owner."""
        try:
            subject = _('Welcome to Your New Tenant!')
            
            context = {
                'tenant': tenant,
                'owner': tenant.owner,
                'trial_ends_at': tenant.trial_ends_at,
                'login_url': getattr(settings, 'TENANT_LOGIN_URL', '/login'),
            }
            
            html_message = render_to_string('tenants/welcome_email.html', context)
            text_message = render_to_string('tenants/welcome_email.txt', context)
            
            send_mail(
                subject=subject,
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[tenant.admin_email],
                html_message=html_message,
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {tenant.admin_email}: {e}")
    
    def _send_owner_password_email(self, user: User, password: str) -> None:
        """Send password email to newly created owner."""
        try:
            subject = _('Your Account Password')
            
            context = {
                'user': user,
                'password': password,
                'login_url': getattr(settings, 'TENANT_LOGIN_URL', '/login'),
            }
            
            html_message = render_to_string('tenants/password_email.html', context)
            text_message = render_to_string('tenants/password_email.txt', context)
            
            send_mail(
                subject=subject,
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Failed to send password email to {user.email}: {e}")
    
    def _clear_tenant_cache(self, tenant: Tenant) -> None:
        """Clear tenant-related cache."""
        cache_keys = [
            f'tenant_{tenant.slug}',
            f'tenant_{tenant.id}',
            f'tenant_settings_{tenant.id}',
            f'tenant_billing_{tenant.id}',
        ]
        
        for key in cache_keys:
            cache.delete(key)
    
    def update_tenant(self, tenant: Tenant, data: Dict[str, Any], updated_by: Optional[User] = None) -> Tenant:
        """
        Update tenant with validation and audit logging.
        
        Args:
            tenant: Tenant instance to update
            data: Update data
            updated_by: User making the update
            
        Returns:
            Updated tenant instance
        """
        with transaction.atomic():
            # Store old values for audit
            old_values = {field: getattr(tenant, field) for field in data.keys()}
            
            # Validate update data
            self._validate_tenant_update_data(tenant, data)
            
            # Update tenant
            for field, value in data.items():
                setattr(tenant, field, value)
            
            tenant.save()
            
            # Log changes
            changes = {
                field: {'old': old_value, 'new': value}
                for field, (old_value, value) in zip(old_values.keys(), old_values.values())
                if old_value != value
            }
            
            if changes:
                tenant.audit_log(
                    action='updated',
                    details={
                        'changes': changes,
                        'updated_by': updated_by.email if updated_by else 'system',
                    },
                    user=updated_by
                )
            
            # Clear cache
            self._clear_tenant_cache(tenant)
            
            return tenant
    
    def _validate_tenant_update_data(self, tenant: Tenant, data: Dict[str, Any]) -> None:
        """Validate tenant update data."""
        # Validate name if provided
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2:
                raise ValidationError(_('Tenant name must be at least 2 characters long.'))
        
        # Validate domain uniqueness if provided
        if 'domain' in data and data['domain']:
            if Tenant.objects.filter(domain=data['domain']).exclude(id=tenant.id).exists():
                raise ValidationError(_('Domain already exists.'))
        
        # Validate max_users if provided
        if 'max_users' in data:
            max_users = data['max_users']
            if not isinstance(max_users, int) or max_users < 1 or max_users > 10000:
                raise ValidationError(_('Max users must be between 1 and 10,000.'))
    
    def delete_tenant(self, tenant: Tenant, deleted_by: Optional[User] = None) -> bool:
        """
        Soft delete tenant with audit logging.
        
        Args:
            tenant: Tenant instance to delete
            deleted_by: User performing deletion
            
        Returns:
            True if successful
        """
        with transaction.atomic():
            # Store tenant info for audit
            tenant_info = {
                'name': tenant.name,
                'slug': tenant.slug,
                'plan': tenant.plan,
                'user_count': tenant.get_total_user_count(),
            }
            
            # Soft delete
            tenant.is_deleted = True
            tenant.is_active = False
            tenant.deleted_at = timezone.now()
            tenant.save()
            
            # Log deletion
            tenant.audit_log(
                action='deleted',
                details={
                    'tenant_info': tenant_info,
                    'deleted_by': deleted_by.email if deleted_by else 'system',
                },
                user=deleted_by
            )
            
            # Clear cache
            self._clear_tenant_cache(tenant)
            
            return True
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """
        Get tenant by slug with caching.
        
        Args:
            slug: Tenant slug
            
        Returns:
            Tenant instance or None
        """
        cache_key = f'tenant_{slug}'
        tenant = cache.get(cache_key)
        
        if not tenant:
            try:
                tenant = Tenant.objects.get(
                    slug=slug,
                    is_active=True,
                    is_deleted=False
                )
                cache.set(cache_key, tenant, self.cache_timeout)
            except Tenant.DoesNotExist:
                return None
        
        return tenant
    
    def get_tenant_usage_stats(self, tenant: Tenant) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Usage statistics dictionary
        """
        from django.db.models import Count, Sum, Avg, Q
        
        stats = {
            'users': {
                'total': tenant.get_total_user_count(),
                'active': tenant.get_active_user_count(),
                'limit': tenant.max_users,
                'remaining': tenant.get_user_limit_remaining(),
                'limit_reached': tenant.is_user_limit_reached(),
                'new_this_month': User.objects.filter(
                    tenant=tenant,
                    date_joined__gte=timezone.now().replace(day=1)
                ).count(),
            },
            'billing': {
                'status': tenant.status,
                'plan': tenant.plan,
                'trial_active': tenant.is_trial_active,
                'trial_days_remaining': tenant.days_until_trial_expires,
                'trial_expired': tenant.trial_expired,
            }
        }
        
        # Add activity stats if available
        try:
            from ..models.core import UserActivity
            
            activity_stats = UserActivity.objects.filter(
                user__tenant=tenant
            ).aggregate(
                total_activities=Count('id'),
                today_activities=Count('id', filter=Q(created_at__date=timezone.now().date())),
                avg_daily=Count('id') / max(1, (timezone.now() - tenant.created_at).days)
            )
            
            stats['activity'] = activity_stats
        except:
            stats['activity'] = {
                'total_activities': 0,
                'today_activities': 0,
                'avg_daily': 0,
            }
        
        return stats
    
    def regenerate_api_credentials(self, tenant: Tenant, credential_type: str = 'api_key') -> Dict[str, str]:
        """
        Regenerate API credentials for tenant.
        
        Args:
            tenant: Tenant instance
            credential_type: Type of credential to regenerate
            
        Returns:
            New credentials dictionary
        """
        with transaction.atomic():
            if credential_type == 'api_key':
                new_key = uuid.uuid4()
                new_secret = secrets.token_urlsafe(48)
                
                tenant.api_key = new_key
                tenant.api_secret = new_secret
                tenant.save(update_fields=['api_key', 'api_secret', 'updated_at'])
                
                credentials = {
                    'api_key': str(new_key),
                    'api_secret': new_secret
                }
                
            elif credential_type == 'webhook_secret':
                new_secret = secrets.token_urlsafe(32)
                
                tenant.webhook_secret = new_secret
                tenant.save(update_fields=['webhook_secret', 'updated_at'])
                
                credentials = {
                    'webhook_secret': new_secret
                }
                
            else:
                raise ValidationError(_('Invalid credential type.'))
            
            # Log credential regeneration
            tenant.audit_log(
                action=f'{credential_type}_regenerated',
                details={
                    'credential_type': credential_type,
                    'regenerated_at': timezone.now().isoformat(),
                }
            )
            
            # Clear cache
            self._clear_tenant_cache(tenant)
            
            return credentials


class TenantSettingsService:
    """
    Service class for tenant settings management.
    
    Handles configuration of tenant-specific settings with validation
    and security considerations.
    """
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 300)
    
    def update_settings(self, tenant: Tenant, data: Dict[str, Any], updated_by: Optional[User] = None) -> TenantSettings:
        """
        Update tenant settings with validation.
        
        Args:
            tenant: Tenant instance
            data: Settings data
            updated_by: User making updates
            
        Returns:
            Updated settings instance
        """
        with transaction.atomic():
            settings = tenant.get_settings()
            
            # Store old values
            old_values = {field: getattr(settings, field) for field in data.keys()}
            
            # Validate settings data
            self._validate_settings_data(settings, data)
            
            # Update settings
            for field, value in data.items():
                setattr(settings, field, value)
            
            settings.save()
            
            # Log changes
            changes = {
                field: {'old': old_value, 'new': value}
                for field, (old_value, value) in zip(old_values.keys(), old_values.values())
                if old_value != value
            }
            
            if changes:
                tenant.audit_log(
                    action='settings_updated',
                    details={
                        'changes': changes,
                        'updated_by': updated_by.email if updated_by else 'system',
                    },
                    user=updated_by
                )
            
            # Clear cache
            cache.delete(f'tenant_settings_{tenant.id}')
            
            return settings
    
    def _validate_settings_data(self, settings: TenantSettings, data: Dict[str, Any]) -> None:
        """Validate settings data."""
        # Validate withdrawal amounts
        min_withdrawal = data.get('min_withdrawal', settings.min_withdrawal)
        max_withdrawal = data.get('max_withdrawal', settings.max_withdrawal)
        daily_limit = data.get('daily_withdrawal_limit', settings.daily_withdrawal_limit)
        
        if min_withdrawal and max_withdrawal and min_withdrawal > max_withdrawal:
            raise ValidationError(_('Minimum withdrawal cannot be greater than maximum withdrawal.'))
        
        if min_withdrawal and daily_limit and daily_limit < min_withdrawal:
            raise ValidationError(_('Daily withdrawal limit cannot be less than minimum withdrawal.'))
        
        # Validate referral percentages
        referral_percentages = data.get('referral_percentages', settings.referral_percentages)
        if referral_percentages:
            if not isinstance(referral_percentages, list):
                raise ValidationError(_('Referral percentages must be a list.'))
            
            for percentage in referral_percentages:
                if not isinstance(percentage, (int, float)):
                    raise ValidationError(_('Referral percentage must be a number.'))
                if percentage < 0 or percentage > 100:
                    raise ValidationError(_('Referral percentage must be between 0 and 100.'))
    
    def toggle_feature(self, tenant: Tenant, feature: str, enabled: bool, updated_by: Optional[User] = None) -> bool:
        """
        Toggle tenant feature on/off.
        
        Args:
            tenant: Tenant instance
            feature: Feature name
            enabled: Whether to enable the feature
            updated_by: User making the change
            
        Returns:
            True if successful
        """
        with transaction.atomic():
            settings = tenant.get_settings()
            
            # Validate feature
            valid_features = [
                'enable_referral', 'enable_offerwall', 'enable_kyc',
                'enable_leaderboard', 'enable_chat', 'enable_push_notifications',
                'enable_analytics', 'enable_api_access'
            ]
            
            if feature not in valid_features:
                raise ValidationError(_('Invalid feature name.'))
            
            # Update feature
            setattr(settings, feature, enabled)
            settings.save()
            
            # Log change
            tenant.audit_log(
                action='feature_enabled' if enabled else 'feature_disabled',
                details={
                    'feature': feature,
                    'enabled': enabled,
                    'updated_by': updated_by.email if updated_by else 'system',
                },
                user=updated_by
            )
            
            # Clear cache
            cache.delete(f'tenant_settings_{tenant.id}')
            
            return True
    
    def get_feature_flags(self, tenant: Tenant) -> Dict[str, bool]:
        """
        Get all feature flags for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Feature flags dictionary
        """
        cache_key = f'tenant_features_{tenant.id}'
        flags = cache.get(cache_key)
        
        if not flags:
            settings = tenant.get_settings()
            flags = {
                'enable_referral': settings.enable_referral,
                'enable_offerwall': settings.enable_offerwall,
                'enable_kyc': settings.enable_kyc,
                'enable_leaderboard': settings.enable_leaderboard,
                'enable_chat': settings.enable_chat,
                'enable_push_notifications': settings.enable_push_notifications,
                'enable_analytics': settings.enable_analytics,
                'enable_api_access': settings.enable_api_access,
            }
            cache.set(cache_key, flags, self.cache_timeout)
        
        return flags


class TenantBillingService:
    """
    Service class for tenant billing management.
    
    Handles subscription management, payments, and billing operations
    with comprehensive validation and audit logging.
    """
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 300)
    
    def create_subscription(self, tenant: Tenant, plan_data: Dict[str, Any], created_by: Optional[User] = None) -> TenantBilling:
        """
        Create or update tenant subscription.
        
        Args:
            tenant: Tenant instance
            plan_data: Plan configuration data
            created_by: User creating subscription
            
        Returns:
            Billing instance
        """
        with transaction.atomic():
            billing = tenant.get_billing()
            
            # Validate plan data
            self._validate_plan_data(plan_data)
            
            # Update billing
            billing.plan = plan_data.get('plan', tenant.plan)
            billing.monthly_price = Decimal(str(plan_data.get('monthly_price', 0)))
            billing.billing_cycle = plan_data.get('billing_cycle', 'monthly')
            billing.currency = plan_data.get('currency', 'USD')
            
            # Calculate subscription dates
            now = timezone.now()
            billing.subscription_starts_at = now
            
            if billing.billing_cycle == 'monthly':
                billing.subscription_ends_at = now + timedelta(days=30)
            elif billing.billing_cycle == 'quarterly':
                billing.subscription_ends_at = now + timedelta(days=90)
            elif billing.billing_cycle == 'yearly':
                billing.subscription_ends_at = now + timedelta(days=365)
            
            billing.current_period_start = now
            billing.current_period_end = billing.subscription_ends_at
            billing.next_payment_at = billing.subscription_ends_at
            
            billing.status = 'active'
            billing.save()
            
            # Update tenant status
            tenant.status = 'active'
            tenant.save(update_fields=['status'])
            
            # Log subscription creation
            tenant.audit_log(
                action='subscription_created',
                details={
                    'plan': billing.plan,
                    'monthly_price': float(billing.monthly_price),
                    'billing_cycle': billing.billing_cycle,
                    'subscription_ends_at': billing.subscription_ends_at.isoformat(),
                    'created_by': created_by.email if created_by else 'system',
                },
                user=created_by
            )
            
            # Clear cache
            cache.delete(f'tenant_billing_{tenant.id}')
            
            return billing
    
    def _validate_plan_data(self, plan_data: Dict[str, Any]) -> None:
        """Validate plan data."""
        # Validate monthly price
        monthly_price = plan_data.get('monthly_price', 0)
        try:
            monthly_price = Decimal(str(monthly_price))
            if monthly_price < 0:
                raise ValidationError(_('Monthly price cannot be negative.'))
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid monthly price.'))
        
        # Validate billing cycle
        valid_cycles = ['monthly', 'quarterly', 'yearly', 'custom']
        billing_cycle = plan_data.get('billing_cycle', 'monthly')
        if billing_cycle not in valid_cycles:
            raise ValidationError(_('Invalid billing cycle.'))
    
    def extend_trial(self, tenant: Tenant, days: int, extended_by: Optional[User] = None) -> bool:
        """
        Extend tenant trial period.
        
        Args:
            tenant: Tenant instance
            days: Number of days to extend
            extended_by: User extending trial
            
        Returns:
            True if successful
        """
        with transaction.atomic():
            if days < 1 or days > 365:
                raise ValidationError(_('Trial extension must be between 1 and 365 days.'))
            
            billing = tenant.get_billing()
            
            # Extend trial
            if billing.trial_ends_at:
                billing.trial_ends_at += timedelta(days=days)
            else:
                billing.trial_ends_at = timezone.now() + timedelta(days=days)
            
            billing.save()
            
            # Update tenant trial end date
            tenant.trial_ends_at = billing.trial_ends_at
            tenant.save(update_fields=['trial_ends_at'])
            
            # Log trial extension
            tenant.audit_log(
                action='trial_extended',
                details={
                    'days_extended': days,
                    'new_trial_end': billing.trial_ends_at.isoformat(),
                    'extended_by': extended_by.email if extended_by else 'system',
                },
                user=extended_by
            )
            
            return True
    
    def create_invoice(self, tenant: Tenant, invoice_data: Dict[str, Any], created_by: Optional[User] = None) -> TenantInvoice:
        """
        Create invoice for tenant.
        
        Args:
            tenant: Tenant instance
            invoice_data: Invoice configuration data
            created_by: User creating invoice
            
        Returns:
            Invoice instance
        """
        with transaction.atomic():
            # Validate invoice data
            self._validate_invoice_data(invoice_data)
            
            # Create invoice
            invoice = TenantInvoice.objects.create(
                tenant=tenant,
                amount=Decimal(str(invoice_data['amount'])),
                tax_amount=Decimal(str(invoice_data.get('tax_amount', 0))),
                description=invoice_data.get('description', 'Invoice'),
                due_date=invoice_data.get('due_date', timezone.now() + timedelta(days=7)),
                currency=invoice_data.get('currency', 'USD'),
                line_items=invoice_data.get('line_items', [])
            )
            
            # Log invoice creation
            tenant.audit_log(
                action='invoice_created',
                details={
                    'invoice_id': invoice.id,
                    'amount': float(invoice.total_amount),
                    'description': invoice.description,
                    'due_date': invoice.due_date.isoformat(),
                    'created_by': created_by.email if created_by else 'system',
                },
                user=created_by
            )
            
            return invoice
    
    def _validate_invoice_data(self, invoice_data: Dict[str, Any]) -> None:
        """Validate invoice data."""
        # Validate amount
        amount = invoice_data.get('amount', 0)
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValidationError(_('Invoice amount must be greater than 0.'))
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid invoice amount.'))
        
        # Validate tax amount
        tax_amount = invoice_data.get('tax_amount', 0)
        try:
            tax_amount = Decimal(str(tax_amount))
            if tax_amount < 0:
                raise ValidationError(_('Tax amount cannot be negative.'))
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid tax amount.'))
        
        # Validate due date
        due_date = invoice_data.get('due_date')
        if due_date and due_date < timezone.now():
            raise ValidationError(_('Due date cannot be in the past.'))
    
    def mark_invoice_paid(self, invoice: TenantInvoice, payment_data: Dict[str, Any], paid_by: Optional[User] = None) -> bool:
        """
        Mark invoice as paid.
        
        Args:
            invoice: Invoice instance
            payment_data: Payment information
            paid_by: User recording payment
            
        Returns:
            True if successful
        """
        with transaction.atomic():
            # Validate payment data
            if not payment_data.get('payment_method'):
                raise ValidationError(_('Payment method is required.'))
            
            # Mark as paid
            invoice.mark_as_paid(
                payment_method=payment_data['payment_method'],
                transaction_id=payment_data.get('transaction_id'),
                notes=payment_data.get('payment_notes')
            )
            
            # Log payment
            invoice.tenant.audit_log(
                action='payment_processed',
                details={
                    'invoice_id': invoice.id,
                    'amount': float(invoice.total_amount),
                    'payment_method': payment_data['payment_method'],
                    'transaction_id': payment_data.get('transaction_id'),
                    'paid_by': paid_by.email if paid_by else 'system',
                },
                user=paid_by
            )
            
            return True


class TenantSecurityService:
    """
    Service class for tenant security operations.
    
    Handles authentication, authorization, and security-related
    operations with comprehensive logging and monitoring.
    """
    
    def __init__(self):
        self.max_login_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        self.lockout_duration = getattr(settings, 'LOGIN_LOCKOUT_DURATION', 300)  # 5 minutes
    
    def verify_webhook_signature(self, tenant: Tenant, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature for tenant.
        
        Args:
            tenant: Tenant instance
            payload: Request payload
            signature: Webhook signature
            
        Returns:
            True if signature is valid
        """
        try:
            # Calculate expected signature
            expected_signature = hmac.new(
                tenant.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False
    
    def check_rate_limit(self, tenant: Tenant, action: str, identifier: str, max_requests: int = 100) -> bool:
        """
        Check rate limiting for tenant actions.
        
        Args:
            tenant: Tenant instance
            action: Action being performed
            identifier: Unique identifier (IP, user ID, etc.)
            max_requests: Maximum allowed requests
            
        Returns:
            True if within rate limit
        """
        try:
            cache_key = f"rate_limit:{tenant.id}:{action}:{identifier}"
            
            # Get current count
            count = cache.get(cache_key, 0)
            
            if count >= max_requests:
                return False
            
            # Increment count
            cache.set(cache_key, count + 1, timeout=self.lockout_duration)
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error
    
    def log_security_event(self, tenant: Tenant, event_type: str, details: Dict[str, Any], user: Optional[User] = None) -> None:
        """
        Log security event for tenant.
        
        Args:
            tenant: Tenant instance
            event_type: Type of security event
            details: Event details
            user: User involved in event
        """
        try:
            tenant.audit_log(
                action=f'security_{event_type}',
                details={
                    'event_type': event_type,
                    'security_details': details,
                    'timestamp': timezone.now().isoformat(),
                },
                user=user
            )
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    def check_login_attempts(self, tenant: Tenant, identifier: str) -> bool:
        """
        Check if login attempts are within limits.
        
        Args:
            tenant: Tenant instance
            identifier: User identifier (email, IP, etc.)
            
        Returns:
            True if login is allowed
        """
        try:
            cache_key = f"login_attempts:{tenant.id}:{identifier}"
            attempts = cache.get(cache_key, 0)
            
            if attempts >= self.max_login_attempts:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Login attempts check failed: {e}")
            return True
    
    def record_login_attempt(self, tenant: Tenant, identifier: str, success: bool) -> None:
        """
        Record login attempt for security monitoring.
        
        Args:
            tenant: Tenant instance
            identifier: User identifier
            success: Whether login was successful
        """
        try:
            cache_key = f"login_attempts:{tenant.id}:{identifier}"
            
            if success:
                # Clear attempts on successful login
                cache.delete(cache_key)
            else:
                # Increment attempts on failed login
                attempts = cache.get(cache_key, 0)
                cache.set(cache_key, attempts + 1, timeout=self.lockout_duration)
            
            # Log security event
            self.log_security_event(
                tenant,
                'login_attempt',
                {
                    'identifier': identifier,
                    'success': success,
                    'attempts': attempts + 1 if not success else 0,
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to record login attempt: {e}")


# Global service instances
tenant_service = TenantService()
tenant_settings_service = TenantSettingsService()
tenant_billing_service = TenantBillingService()
tenant_security_service = TenantSecurityService()
