"""
Core Serializers

This module contains serializers for core tenant models including
Tenant, TenantSettings, TenantBilling, and TenantInvoice.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    """
    Serializer for Tenant model with comprehensive field mapping.
    """
    owner_details = serializers.SerializerMethodField()
    plan_details = serializers.SerializerMethodField()
    settings_summary = serializers.SerializerMethodField()
    billing_summary = serializers.SerializerMethodField()
    is_trial_expired = serializers.SerializerMethodField()
    days_until_trial_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'domain', 'plan', 'tier', 'status',
            'is_suspended', 'suspension_reason', 'parent_tenant',
            'timezone', 'country_code', 'currency_code', 'data_region',
            'owner', 'owner_details', 'contact_email', 'contact_phone',
            'trial_ends_at', 'is_trial_expired', 'days_until_trial_expiry',
            'billing_cycle_start', 'metadata', 'last_activity_at',
            'created_at', 'updated_at', 'plan_details', 'settings_summary',
            'billing_summary'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_activity_at',
            'is_trial_expired', 'days_until_trial_expiry'
        ]
    
    def get_owner_details(self, obj):
        """Get owner user details."""
        if obj.owner:
            return {
                'id': str(obj.owner.id),
                'username': obj.owner.username,
                'email': obj.owner.email,
                'first_name': obj.owner.first_name,
                'last_name': obj.owner.last_name,
            }
        return None
    
    def get_plan_details(self, obj):
        """Get plan details."""
        if obj.plan:
            return {
                'id': str(obj.plan.id),
                'name': obj.plan.name,
                'plan_type': obj.plan.plan_type,
                'price_monthly': float(obj.plan.price_monthly),
                'max_users': obj.plan.max_users,
                'max_publishers': obj.plan.max_publishers,
                'max_smartlinks': obj.plan.max_smartlinks,
                'api_calls_per_day': obj.plan.api_calls_per_day,
                'storage_gb': obj.plan.storage_gb,
            }
        return None
    
    def get_settings_summary(self, obj):
        """Get settings summary."""
        try:
            settings = obj.settings
            return {
                'enable_smartlink': settings.enable_smartlink,
                'enable_ai_engine': settings.enable_ai_engine,
                'enable_publisher_tools': settings.enable_publisher_tools,
                'enable_advertiser_portal': settings.enable_advertiser_portal,
                'max_users': settings.max_users,
                'max_publishers': settings.max_publishers,
                'max_smartlinks': settings.max_smartlinks,
                'api_calls_per_day': settings.api_calls_per_day,
                'storage_gb': settings.storage_gb,
                'default_language': settings.default_language,
                'enable_two_factor_auth': settings.enable_two_factor_auth,
            }
        except:
            return {}
    
    def get_billing_summary(self, obj):
        """Get billing summary."""
        try:
            billing = obj.billing
            return {
                'billing_cycle': billing.billing_cycle,
                'base_price': float(billing.base_price),
                'final_price': float(billing.final_price),
                'next_billing_date': billing.next_billing_date,
                'payment_method': billing.payment_method,
                'is_overdue': billing.is_overdue(),
                'dunning_count': billing.dunning_count,
            }
        except:
            return {}
    
    def get_is_trial_expired(self, obj):
        """Check if trial is expired."""
        return obj.is_trial_expired
    
    def get_days_until_trial_expiry(self, obj):
        """Get days until trial expiry."""
        return obj.days_until_trial_expiry


class TenantCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tenants with validation.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'slug', 'plan', 'owner', 'contact_email', 'contact_phone',
            'timezone', 'country_code', 'currency_code', 'data_region',
            'domain', 'parent_tenant', 'trial_ends_at', 'billing_cycle_start',
            'metadata', 'password', 'confirm_password'
        ]
    
    def validate(self, attrs):
        """Validate tenant creation data."""
        # Validate password confirmation
        password = attrs.get('password')
        confirm_password = attrs.pop('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")
        
        # Validate slug uniqueness
        slug = attrs.get('slug')
        if Tenant.objects.filter(slug=slug).exists():
            raise serializers.ValidationError("Tenant slug already exists.")
        
        # Validate owner exists and is active
        owner = attrs.get('owner')
        if not User.objects.filter(id=owner.id, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive owner user.")
        
        # Validate plan exists and is active
        plan = attrs.get('plan')
        if not plan.is_active:
            raise serializers.ValidationError("Selected plan is not active.")
        
        return attrs


class TenantUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing tenants.
    """
    class Meta:
        model = Tenant
        fields = [
            'name', 'domain', 'timezone', 'country_code', 'currency_code',
            'data_region', 'contact_email', 'contact_phone', 'metadata'
        ]
    
    def validate_slug(self, value):
        """Validate slug uniqueness for updates."""
        if self.instance and self.instance.slug != value:
            if Tenant.objects.filter(slug=value).exists():
                raise serializers.ValidationError("Tenant slug already exists.")
        return value


class TenantSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantSettings model.
    """
    class Meta:
        model = TenantSettings
        fields = [
            'enable_smartlink', 'enable_ai_engine', 'enable_publisher_tools',
            'enable_advertiser_portal', 'enable_coalition', 'max_withdrawal_per_day',
            'require_kyc_for_withdrawal', 'max_users', 'max_publishers',
            'max_smartlinks', 'api_calls_per_day', 'api_calls_per_hour',
            'storage_gb', 'bandwidth_gb_per_month', 'default_language',
            'default_currency', 'default_timezone', 'email_from_name',
            'email_from_address', 'email_logo', 'enable_two_factor_auth',
            'session_timeout_minutes', 'password_min_length', 'password_require_special',
            'password_require_numbers', 'enable_email_notifications',
            'enable_push_notifications', 'enable_sms_notifications',
            'notification_email_types', 'notification_push_types',
            'security_alert_email', 'security_alert_sms', 'login_notifications',
            'api_key_rotations', 'backup_frequency', 'retention_days',
            'custom_settings'
        ]
    
    def validate(self, attrs):
        """Validate settings data."""
        # Validate limits are positive
        limit_fields = [
            'max_withdrawal_per_day', 'max_users', 'max_publishers',
            'max_smartlinks', 'api_calls_per_day', 'api_calls_per_hour',
            'storage_gb', 'bandwidth_gb_per_month', 'session_timeout_minutes',
            'password_min_length', 'retention_days'
        ]
        
        for field in limit_fields:
            if field in attrs and attrs[field] < 0:
                raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate timezone
        if 'default_timezone' in attrs:
            try:
                import pytz
                pytz.timezone(attrs['default_timezone'])
            except:
                raise serializers.ValidationError("Invalid timezone.")
        
        return attrs


class TenantBillingSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantBilling model.
    """
    is_overdue = serializers.SerializerMethodField()
    days_until_next_billing = serializers.SerializerMethodField()
    dunning_status = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantBilling
        fields = [
            'tenant', 'stripe_customer_id', 'billing_cycle', 'billing_cycle_start',
            'payment_method', 'base_price', 'discount_pct', 'final_price',
            'next_billing_date', 'billing_email', 'billing_phone',
            'billing_address', 'tax_id', 'tax_exempt', 'vat_number',
            'dunning_count', 'max_dunning_attempts', 'last_dunning_sent',
            'metadata', 'is_overdue', 'days_until_next_billing', 'dunning_status'
        ]
        read_only_fields = [
            'tenant', 'dunning_count', 'max_dunning_attempts',
            'last_dunning_sent'
        ]
    
    def get_is_overdue(self, obj):
        """Check if billing is overdue."""
        return obj.is_overdue()
    
    def get_days_until_next_billing(self, obj):
        """Get days until next billing date."""
        if obj.next_billing_date:
            delta = obj.next_billing_date - timezone.now().date()
            return max(0, delta.days)
        return None
    
    def get_dunning_status(self, obj):
        """Get dunning status."""
        if obj.dunning_count == 0:
            return 'current'
        elif obj.dunning_count < obj.max_dunning_attempts:
            return 'overdue'
        else:
            return 'critical'
    
    def validate(self, attrs):
        """Validate billing data."""
        # Validate discount percentage
        if 'discount_pct' in attrs:
            discount = attrs['discount_pct']
            if discount < 0 or discount > 100:
                raise serializers.ValidationError("Discount percentage must be between 0 and 100.")
        
        # Validate billing cycle start
        if 'billing_cycle_start' in attrs:
            cycle_start = attrs['billing_cycle_start']
            if cycle_start < 1 or cycle_start > 31:
                raise serializers.ValidationError("Billing cycle start must be between 1 and 31.")
        
        return attrs


class TenantInvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantInvoice model.
    """
    tenant_details = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantInvoice
        fields = [
            'id', 'tenant', 'tenant_details', 'invoice_number', 'status',
            'status_display', 'issue_date', 'due_date', 'paid_date',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'amount_paid', 'balance_due', 'payment_method', 'transaction_id',
            'billing_period_start', 'billing_period_end', 'line_items',
            'notes', 'metadata', 'days_overdue', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'invoice_number', 'created_at', 'updated_at'
        ]
    
    def get_tenant_details(self, obj):
        """Get tenant details."""
        return {
            'id': str(obj.tenant.id),
            'name': obj.tenant.name,
            'slug': obj.tenant.slug,
        }
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_days_overdue(self, obj):
        """Get days overdue."""
        return obj.days_overdue
    
    def get_is_overdue(self, obj):
        """Check if invoice is overdue."""
        return obj.is_overdue


class TenantInvoiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new invoices.
    """
    class Meta:
        model = TenantInvoice
        fields = [
            'issue_date', 'due_date', 'billing_period_start', 'billing_period_end',
            'description', 'notes', 'line_items', 'metadata'
        ]
    
    def validate(self, attrs):
        """Validate invoice creation data."""
        # Validate date ranges
        issue_date = attrs.get('issue_date')
        due_date = attrs.get('due_date')
        period_start = attrs.get('billing_period_start')
        period_end = attrs.get('billing_period_end')
        
        if issue_date and due_date and issue_date > due_date:
            raise serializers.ValidationError("Issue date cannot be after due date.")
        
        if period_start and period_end and period_start > period_end:
            raise serializers.ValidationError("Billing period start cannot be after end.")
        
        # Validate line items
        line_items = attrs.get('line_items', [])
        if not line_items:
            raise serializers.ValidationError("At least one line item is required.")
        
        for item in line_items:
            if 'description' not in item or 'amount' not in item:
                raise serializers.ValidationError("Each line item must have description and amount.")
            
            if item['amount'] < 0:
                raise serializers.ValidationError("Line item amounts cannot be negative.")
        
        return attrs
