"""
Tenant Serializers - Improved Version with Enhanced Security and Validation

This module contains comprehensive serializers for tenant management with
advanced validation, security features, and proper data handling.
"""

import secrets
from datetime import datetime, timedelta
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.conf import settings

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)

User = get_user_model()


class TenantSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant settings with comprehensive validation.
    """
    
    class Meta:
        model = TenantSettings
        exclude = ['tenant', 'firebase_server_key', 'custom_css', 'custom_js']
    
    def validate_min_withdrawal(self, value):
        """Validate minimum withdrawal amount."""
        if value <= 0:
            raise serializers.ValidationError(_("Minimum withdrawal must be greater than 0."))
        return value
    
    def validate_max_withdrawal(self, value):
        """Validate maximum withdrawal amount."""
        if value <= 0:
            raise serializers.ValidationError(_("Maximum withdrawal must be greater than 0."))
        return value
    
    def validate_withdrawal_fee_percent(self, value):
        """Validate withdrawal fee percentage."""
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Withdrawal fee percentage must be between 0 and 100."))
        return value
    
    def validate_referral_percentages(self, value):
        """Validate referral percentages array."""
        if not isinstance(value, list):
            raise serializers.ValidationError(_("Referral percentages must be a list."))
        
        if len(value) > 10:
            raise serializers.ValidationError(_("Maximum 10 referral levels allowed."))
        
        for i, percentage in enumerate(value):
            if not isinstance(percentage, (int, float)):
                raise serializers.ValidationError(_("Referral percentage must be a number."))
            if percentage < 0 or percentage > 100:
                raise serializers.ValidationError(_("Referral percentage must be between 0 and 100."))
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        min_withdrawal = attrs.get('min_withdrawal')
        max_withdrawal = attrs.get('max_withdrawal')
        daily_limit = attrs.get('daily_withdrawal_limit')
        
        if min_withdrawal and max_withdrawal and min_withdrawal > max_withdrawal:
            raise serializers.ValidationError(_("Minimum withdrawal cannot be greater than maximum withdrawal."))
        
        if min_withdrawal and daily_limit and daily_limit < min_withdrawal:
            raise serializers.ValidationError(_("Daily withdrawal limit cannot be less than minimum withdrawal."))
        
        return attrs


class TenantBillingSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant billing with validation and security.
    """
    
    is_active = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_past_due = serializers.SerializerMethodField()
    current_usage = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantBilling
        fields = '__all__'
        read_only_fields = [
            'stripe_customer_id', 'stripe_subscription_id', 
            'payment_method_id', 'created_at', 'updated_at'
        ]
    
    def get_is_active(self, obj):
        """Check if subscription is active."""
        return obj.is_active
    
    def get_days_until_expiry(self, obj):
        """Get days until subscription expires."""
        return obj.days_until_expiry
    
    def get_is_expired(self, obj):
        """Check if subscription is expired."""
        return obj.is_expired
    
    def get_is_past_due(self, obj):
        """Check if payment is past due."""
        return obj.is_past_due
    
    def get_current_usage(self, obj):
        """Get current billing period usage."""
        usage = obj.get_current_usage()
        if usage:
            return {
                'period_start': usage['period_start'].isoformat(),
                'period_end': usage['period_end'].isoformat(),
                'active_users': usage['active_users'],
                'total_users': usage['total_users'],
            }
        return None
    
    def validate_monthly_price(self, value):
        """Validate monthly price."""
        if value < 0:
            raise serializers.ValidationError(_("Monthly price cannot be negative."))
        return value
    
    def validate_setup_fee(self, value):
        """Validate setup fee."""
        if value < 0:
            raise serializers.ValidationError(_("Setup fee cannot be negative."))
        return value


class TenantInvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant invoices with validation.
    """
    
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantInvoice
        fields = '__all__'
        read_only_fields = [
            'invoice_number', 'tenant', 'created_at', 'updated_at'
        ]
    
    def get_is_overdue(self, obj):
        """Check if invoice is overdue."""
        return obj.is_overdue
    
    def get_days_overdue(self, obj):
        """Get days invoice is overdue."""
        return obj.days_overdue
    
    def get_amount_due(self, obj):
        """Get amount still due."""
        return float(obj.amount_due)
    
    def validate_amount(self, value):
        """Validate invoice amount."""
        if value <= 0:
            raise serializers.ValidationError(_("Amount must be greater than 0."))
        return value
    
    def validate_tax_amount(self, value):
        """Validate tax amount."""
        if value < 0:
            raise serializers.ValidationError(_("Tax amount cannot be negative."))
        return value
    
    def validate_due_date(self, value):
        """Validate due date."""
        if value and value < timezone.now():
            raise serializers.ValidationError(_("Due date cannot be in the past."))
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        amount = attrs.get('amount', 0)
        tax_amount = attrs.get('tax_amount', 0)
        
        if tax_amount > amount:
            raise serializers.ValidationError(_("Tax amount cannot be greater than invoice amount."))
        
        return attrs


class TenantAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant audit logs.
    """
    
    user_email_display = serializers.CharField(source='user_email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantAuditLog
        fields = '__all__'
        read_only_fields = [
            'tenant', 'user', 'created_at'
        ]
    
    def get_created_at_formatted(self, obj):
        """Format creation date."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S')


class TenantCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tenants with enhanced validation.
    """
    
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[
            RegexValidator(
                regex=r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
                message=_("Password must contain at least one lowercase letter, one uppercase letter, one digit, and one special character.")
            )
        ]
    )
    confirm_password = serializers.CharField(write_only=True)
    owner_email = serializers.EmailField(write_only=True)
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'slug', 'domain', 'admin_email', 'contact_phone',
            'primary_color', 'secondary_color', 'plan', 'max_users',
            'timezone', 'country_code', 'currency_code', 'data_region',
            'android_package_name', 'ios_bundle_id', 'password',
            'confirm_password', 'owner_email'
        ]
        extra_kwargs = {
            'slug': {
                'validators': [
                    UniqueValidator(
                        queryset=Tenant.objects.all(),
                        message=_("Tenant slug already exists.")
                    )
                ]
            },
            'domain': {
                'validators': [
                    UniqueValidator(
                        queryset=Tenant.objects.all(),
                        message=_("Domain already exists."),
                        lookup_expr='i'
                    )
                ]
            }
        }
    
    def validate_name(self, value):
        """Validate tenant name."""
        if len(value.strip()) < 2:
            raise serializers.ValidationError(_("Tenant name must be at least 2 characters long."))
        
        if len(value) > 255:
            raise serializers.ValidationError(_("Tenant name cannot exceed 255 characters."))
        
        return value.strip()
    
    def validate_slug(self, value):
        """Validate tenant slug."""
        if not value:
            raise serializers.ValidationError(_("Slug is required."))
        
        # Check for reserved slugs
        reserved_slugs = ['www', 'mail', 'ftp', 'admin', 'api', 'app', 'www']
        if value.lower() in reserved_slugs:
            raise serializers.ValidationError(_("This slug is reserved and cannot be used."))
        
        return value.lower()
    
    def validate_domain(self, value):
        """Validate domain."""
        if value and len(value) > 255:
            raise serializers.ValidationError(_("Domain cannot exceed 255 characters."))
        return value
    
    def validate_admin_email(self, value):
        """Validate admin email."""
        if not value:
            raise serializers.ValidationError(_("Admin email is required."))
        return value.lower()
    
    def validate_max_users(self, value):
        """Validate maximum users."""
        if value < 1:
            raise serializers.ValidationError(_("Maximum users must be at least 1."))
        if value > 10000:
            raise serializers.ValidationError(_("Maximum users cannot exceed 10,000."))
        return value
    
    def validate_primary_color(self, value):
        """Validate primary color."""
        if not value.startswith('#'):
            raise serializers.ValidationError(_("Color must start with #."))
        return value
    
    def validate_secondary_color(self, value):
        """Validate secondary color."""
        if not value.startswith('#'):
            raise serializers.ValidationError(_("Color must start with #."))
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        admin_email = attrs.get('admin_email')
        owner_email = attrs.get('owner_email')
        
        if password != confirm_password:
            raise serializers.ValidationError(_("Passwords do not match."))
        
        if admin_email and owner_email and admin_email != owner_email:
            raise serializers.ValidationError(_("Admin email and owner email must match."))
        
        # Check if owner user exists
        if owner_email:
            if not User.objects.filter(email=owner_email).exists():
                raise serializers.ValidationError(_("User with this email does not exist."))
        
        return attrs
    
    def create(self, validated_data):
        """Create tenant with owner."""
        from django.db import transaction
        
        password = validated_data.pop('password')
        confirm_password = validated_data.pop('confirm_password')
        owner_email = validated_data.pop('owner_email')
        
        with transaction.atomic():
            # Get or create owner user
            try:
                owner = User.objects.get(email=owner_email)
            except User.DoesNotExist:
                raise serializers.ValidationError(_("Owner user not found."))
            
            # Create tenant
            tenant = Tenant.objects.create(
                owner=owner,
                created_by=self.context['request'].user if 'request' in self.context else owner,
                **validated_data
            )
            
            # Log creation
            tenant.audit_log(
                action='created',
                details={
                    'plan': tenant.plan,
                    'max_users': tenant.max_users,
                    'created_by': self.context['request'].user.email if 'request' in self.context else 'system'
                },
                user=self.context['request'].user if 'request' in self.context else None
            )
            
            return tenant


class TenantUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating tenant information.
    """
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'domain', 'admin_email', 'contact_phone',
            'primary_color', 'secondary_color', 'timezone',
            'country_code', 'currency_code', 'android_package_name',
            'ios_bundle_id', 'logo'
        ]
    
    def validate_domain(self, value):
        """Validate domain uniqueness."""
        if value:
            instance = self.instance
            if Tenant.objects.filter(domain=value).exclude(id=instance.id).exists():
                raise serializers.ValidationError(_("Domain already exists."))
        return value
    
    def update(self, instance, validated_data):
        """Update tenant with audit logging."""
        from django.db import transaction
        
        with transaction.atomic():
            # Store old values for audit
            old_values = {
                field: getattr(instance, field)
                for field in validated_data.keys()
            }
            
            # Update instance
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            
            # Log changes
            changes = {
                field: {'old': old_value, 'new': value}
                for field, (old_value, value) in zip(old_values.keys(), old_values.values())
                if old_value != value
            }
            
            if changes:
                instance.audit_log(
                    action='updated',
                    details={'changes': changes},
                    user=self.context['request'].user if 'request' in self.context else None
                )
            
            return instance


class TenantSerializer(serializers.ModelSerializer):
    """
    Main tenant serializer with comprehensive fields and security.
    """
    
    logo_url = serializers.SerializerMethodField()
    settings = TenantSettingsSerializer(read_only=True)
    billing = TenantBillingSerializer(read_only=True)
    active_users = serializers.SerializerMethodField()
    total_users = serializers.SerializerMethodField()
    user_limit_remaining = serializers.SerializerMethodField()
    is_user_limit_reached = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()
    feature_flags = serializers.SerializerMethodField()
    trial_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'domain', 'admin_email', 'contact_phone',
            'primary_color', 'secondary_color', 'logo', 'logo_url',
            'plan', 'status', 'max_users', 'is_active', 'is_deleted',
            'timezone', 'country_code', 'currency_code', 'data_region',
            'android_package_name', 'ios_bundle_id',
            'created_at', 'updated_at',
            'settings', 'billing', 'active_users', 'total_users',
            'user_limit_remaining', 'is_user_limit_reached',
            'usage_stats', 'feature_flags', 'trial_info'
        ]
        read_only_fields = [
            'id', 'slug', 'created_at', 'updated_at', 'api_key',
            'api_secret', 'webhook_secret', 'is_deleted'
        ]
    
    def get_logo_url(self, obj):
        """Get full logo URL."""
        request = self.context.get('request')
        return obj.get_logo_url(request)
    
    def get_active_users(self, obj):
        """Get active user count."""
        return obj.get_active_user_count()
    
    def get_total_users(self, obj):
        """Get total user count."""
        return obj.get_total_user_count()
    
    def get_user_limit_remaining(self, obj):
        """Get remaining user slots."""
        return obj.get_user_limit_remaining()
    
    def get_is_user_limit_reached(self, obj):
        """Check if user limit is reached."""
        return obj.is_user_limit_reached()
    
    def get_usage_stats(self, obj):
        """Get usage statistics."""
        return obj.get_usage_stats()
    
    def get_feature_flags(self, obj):
        """Get feature flags."""
        return obj.get_feature_flags()
    
    def get_trial_info(self, obj):
        """Get trial information."""
        return {
            'is_trial_active': obj.is_trial_active,
            'days_until_expires': obj.days_until_trial_expires,
            'trial_expired': obj.trial_expired,
            'trial_ends_at': obj.trial_ends_at.isoformat() if obj.trial_ends_at else None,
        }


class TenantPublicSerializer(serializers.ModelSerializer):
    """
    Public tenant serializer for React Native app access.
    
    Only includes safe public information needed for app configuration.
    """
    
    logo_url = serializers.SerializerMethodField()
    app_config = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'slug', 'logo', 'logo_url', 'primary_color', 
            'secondary_color', 'plan', 'app_config'
        ]
    
    def get_logo_url(self, obj):
        """Get full logo URL."""
        request = self.context.get('request')
        return obj.get_logo_url(request)
    
    def get_app_config(self, obj):
        """Get app configuration for React Native."""
        settings = obj.get_settings()
        return {
            'app_name': settings.app_name,
            'enable_referral': settings.enable_referral,
            'enable_offerwall': settings.enable_offerwall,
            'enable_kyc': settings.enable_kyc,
            'enable_leaderboard': settings.enable_leaderboard,
            'enable_chat': settings.enable_chat,
            'enable_push_notifications': settings.enable_push_notifications,
            'min_withdrawal': float(settings.min_withdrawal),
            'max_withdrawal': float(settings.max_withdrawal),
            'withdrawal_fee_percent': float(settings.withdrawal_fee_percent),
            'referral_bonus_amount': float(settings.referral_bonus_amount),
            'referral_bonus_type': settings.referral_bonus_type,
            'support_email': settings.support_email or obj.admin_email,
            'privacy_policy_url': settings.privacy_policy_url,
            'terms_url': settings.terms_url,
            'about_url': settings.about_url,
        }


class TenantApiKeySerializer(serializers.Serializer):
    """
    Serializer for API key operations.
    """
    
    api_key = serializers.UUIDField(read_only=True)
    api_secret = serializers.CharField(read_only=True)
    
    def regenerate_secret(self, tenant):
        """Regenerate API secret."""
        new_secret = tenant.regenerate_api_secret()
        return {
            'api_key': tenant.api_key,
            'api_secret': new_secret
        }


class TenantWebhookSecretSerializer(serializers.Serializer):
    """
    Serializer for webhook secret operations.
    """
    
    webhook_secret = serializers.CharField(read_only=True)
    
    def regenerate_secret(self, tenant):
        """Regenerate webhook secret."""
        new_secret = tenant.regenerate_webhook_secret()
        return {
            'webhook_secret': new_secret
        }


class TenantFeatureToggleSerializer(serializers.Serializer):
    """
    Serializer for toggling tenant features.
    """
    
    feature = serializers.ChoiceField(choices=[
        ('enable_referral', 'Enable Referral'),
        ('enable_offerwall', 'Enable Offerwall'),
        ('enable_kyc', 'Enable KYC'),
        ('enable_leaderboard', 'Enable Leaderboard'),
        ('enable_chat', 'Enable Chat'),
        ('enable_push_notifications', 'Enable Push Notifications'),
        ('enable_analytics', 'Enable Analytics'),
        ('enable_api_access', 'Enable API Access'),
    ])
    enabled = serializers.BooleanField()
    
    def validate(self, attrs):
        """Validate feature toggle."""
        feature = attrs.get('feature')
        enabled = attrs.get('enabled')
        
        # Add any feature-specific validation here
        if feature == 'enable_api_access' and not enabled:
            # Warn about disabling API access
            pass
        
        return attrs
    
    def toggle_feature(self, tenant):
        """Toggle tenant feature."""
        feature = self.validated_data['feature']
        enabled = self.validated_data['enabled']
        
        settings = tenant.get_settings()
        setattr(settings, feature, enabled)
        settings.save()
        
        # Log the change
        tenant.audit_log(
            action='feature_enabled' if enabled else 'feature_disabled',
            details={'feature': feature},
            user=self.context['request'].user if 'request' in self.context else None
        )
        
        return {'success': True, 'feature': feature, 'enabled': enabled}


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription management.
    """
    
    extend_trial_days = serializers.IntegerField(
        write_only=True,
        min_value=1,
        max_value=365,
        required=False
    )
    
    class Meta:
        model = TenantBilling
        fields = [
            'status', 'billing_cycle', 'monthly_price', 'setup_fee',
            'trial_ends_at', 'subscription_starts_at', 'subscription_ends_at',
            'extend_trial_days'
        ]
        read_only_fields = [
            'stripe_customer_id', 'stripe_subscription_id', 'payment_method_id'
        ]
    
    def validate_extend_trial_days(self, value):
        """Validate trial extension days."""
        if value < 1 or value > 365:
            raise serializers.ValidationError(_("Trial extension must be between 1 and 365 days."))
        return value
    
    def validate_monthly_price(self, value):
        """Validate monthly price."""
        if value < 0:
            raise serializers.ValidationError(_("Monthly price cannot be negative."))
        return value
    
    def update(self, instance, validated_data):
        """Update subscription with audit logging."""
        extend_trial_days = validated_data.pop('extend_trial_days', None)
        
        # Handle trial extension
        if extend_trial_days:
            instance.extend_trial(extend_trial_days)
            instance.tenant.audit_log(
                action='billing_updated',
                details={'trial_extended_days': extend_trial_days},
                user=self.context['request'].user if 'request' in self.context else None
            )
        
        # Update other fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        return instance


class TenantOverviewSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant overview in admin dashboard.
    """
    
    active_users = serializers.SerializerMethodField()
    total_users = serializers.SerializerMethodField()
    billing_status = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'domain', 'plan', 'status',
            'is_active', 'created_at', 'active_users', 'total_users',
            'billing_status', 'subscription_status', 'health_status'
        ]
    
    def get_active_users(self, obj):
        """Get active user count."""
        return obj.get_active_user_count()
    
    def get_total_users(self, obj):
        """Get total user count."""
        return obj.get_total_user_count()
    
    def get_billing_status(self, obj):
        """Get billing status."""
        billing = obj.get_billing()
        return {
            'status': billing.status,
            'is_active': billing.is_active,
            'is_past_due': billing.is_past_due,
            'next_payment': billing.next_payment_at.isoformat() if billing.next_payment_at else None,
        }
    
    def get_subscription_status(self, obj):
        """Get subscription status."""
        return {
            'plan': obj.plan,
            'trial_active': obj.is_trial_active,
            'trial_days_remaining': obj.days_until_trial_expires,
            'trial_expired': obj.trial_expired,
            'user_limit_reached': obj.is_user_limit_reached(),
            'user_limit': obj.max_users,
        }
    
    def get_health_status(self, obj):
        """Get tenant health status."""
        issues = []
        
        if not obj.is_active:
            issues.append('Tenant is inactive')
        
        if obj.is_deleted:
            issues.append('Tenant is deleted')
        
        if obj.is_user_limit_reached():
            issues.append('User limit reached')
        
        if obj.trial_expired:
            issues.append('Trial expired')
        
        billing = obj.get_billing()
        if billing.is_past_due:
            issues.append('Payment past due')
        
        return {
            'status': 'healthy' if not issues else 'issues',
            'issues': issues,
            'score': max(0, 100 - len(issues) * 20),
        }
