"""
Tenant Admin - Improved Version with Enhanced Security and Features

This module contains comprehensive Django admin configuration for tenant management
with advanced security, proper filtering, and extensive functionality.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from django.forms import ModelForm, ValidationError
from django import forms
import json

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)


class TenantAdminForm(ModelForm):
    """
    Custom form for Tenant admin with enhanced validation.
    """
    
    class Meta:
        model = Tenant
        fields = '__all__'
        widgets = {
            'metadata': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }
    
    def clean_slug(self):
        """Validate slug uniqueness."""
        slug = self.cleaned_data.get('slug')
        if slug:
            # Check for reserved slugs
            reserved_slugs = ['www', 'mail', 'ftp', 'admin', 'api', 'app', 'www']
            if slug.lower() in reserved_slugs:
                raise ValidationError(_('This slug is reserved and cannot be used.'))
            
            # Check uniqueness
            instance = self.instance
            if Tenant.objects.filter(slug=slug).exclude(id=instance.id if instance else None).exists():
                raise ValidationError(_('Tenant slug already exists.'))
        
        return slug
    
    def clean_domain(self):
        """Validate domain uniqueness."""
        domain = self.cleaned_data.get('domain')
        if domain:
            instance = self.instance
            if Tenant.objects.filter(domain=domain).exclude(id=instance.id if instance else None).exists():
                raise ValidationError(_('Domain already exists.'))
        
        return domain
    
    def clean_max_users(self):
        """Validate max users."""
        max_users = self.cleaned_data.get('max_users')
        if max_users and (max_users < 1 or max_users > 10000):
            raise ValidationError(_('Max users must be between 1 and 10,000.'))
        
        return max_users
    
    def clean_primary_color(self):
        """Validate primary color."""
        color = self.cleaned_data.get('primary_color')
        if color and not color.startswith('#'):
            raise ValidationError(_('Color must start with #.'))
        
        return color
    
    def clean_secondary_color(self):
        """Validate secondary color."""
        color = self.cleaned_data.get('secondary_color')
        if color and not color.startswith('#'):
            raise ValidationError(_('Color must start with #.'))
        
        return color
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        
        # Validate parent tenant (prevent circular references)
        parent_tenant = cleaned_data.get('parent_tenant')
        if parent_tenant:
            instance = self.instance
            
            if instance and instance.id == parent_tenant.id:
                raise ValidationError(_('Tenant cannot be its own parent.'))
            
            # Check for circular reference
            parent = parent_tenant
            while parent:
                if instance and instance.id == parent.id:
                    raise ValidationError(_('Circular parent reference detected.'))
                parent = parent.parent_tenant
        
        return cleaned_data


class TenantSettingsAdminForm(ModelForm):
    """
    Custom form for TenantSettings admin with enhanced validation.
    """
    
    class Meta:
        model = TenantSettings
        fields = '__all__'
        widgets = {
            'custom_config': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'custom_css': forms.Textarea(attrs={'rows': 6, 'cols': 80}),
            'custom_js': forms.Textarea(attrs={'rows': 6, 'cols': 80}),
            'referral_percentages': forms.Textarea(attrs={'rows': 3, 'cols': 40}),
        }
    
    def clean_min_withdrawal(self):
        """Validate minimum withdrawal."""
        value = self.cleaned_data.get('min_withdrawal')
        if value and value <= 0:
            raise ValidationError(_('Minimum withdrawal must be greater than 0.'))
        return value
    
    def clean_max_withdrawal(self):
        """Validate maximum withdrawal."""
        value = self.cleaned_data.get('max_withdrawal')
        if value and value <= 0:
            raise ValidationError(_('Maximum withdrawal must be greater than 0.'))
        return value
    
    def clean_withdrawal_fee_percent(self):
        """Validate withdrawal fee percentage."""
        value = self.cleaned_data.get('withdrawal_fee_percent')
        if value and (value < 0 or value > 100):
            raise ValidationError(_('Withdrawal fee percentage must be between 0 and 100.'))
        return value
    
    def clean_referral_percentages(self):
        """Validate referral percentages."""
        value = self.cleaned_data.get('referral_percentages')
        if value:
            try:
                if isinstance(value, str):
                    percentages = json.loads(value)
                else:
                    percentages = value
                
                if not isinstance(percentages, list):
                    raise ValidationError(_('Referral percentages must be a list.'))
                
                for percentage in percentages:
                    if not isinstance(percentage, (int, float)):
                        raise ValidationError(_('Referral percentage must be a number.'))
                    if percentage < 0 or percentage > 100:
                        raise ValidationError(_('Referral percentage must be between 0 and 100.'))
                
                self.cleaned_data['referral_percentages'] = percentages
                
            except json.JSONDecodeError:
                raise ValidationError(_('Invalid JSON format for referral percentages.'))
        
        return value
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        
        min_withdrawal = cleaned_data.get('min_withdrawal')
        max_withdrawal = cleaned_data.get('max_withdrawal')
        daily_limit = cleaned_data.get('daily_withdrawal_limit')
        
        if min_withdrawal and max_withdrawal and min_withdrawal > max_withdrawal:
            raise ValidationError(_('Minimum withdrawal cannot be greater than maximum withdrawal.'))
        
        if min_withdrawal and daily_limit and daily_limit < min_withdrawal:
            raise ValidationError(_('Daily withdrawal limit cannot be less than minimum withdrawal.'))
        
        return cleaned_data


class TenantBillingAdminForm(ModelForm):
    """
    Custom form for TenantBilling admin with enhanced validation.
    """
    
    class Meta:
        model = TenantBilling
        fields = '__all__'
        widgets = {
            'billing_metadata': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
        }
    
    def clean_monthly_price(self):
        """Validate monthly price."""
        value = self.cleaned_data.get('monthly_price')
        if value and value < 0:
            raise ValidationError(_('Monthly price cannot be negative.'))
        return value
    
    def clean_setup_fee(self):
        """Validate setup fee."""
        value = self.cleaned_data.get('setup_fee')
        if value and value < 0:
            raise ValidationError(_('Setup fee cannot be negative.'))
        return value


class TenantInline(admin.TabularInline):
    """
    Inline admin for tenant-related models.
    """
    model = Tenant
    extra = 0
    fields = ['name', 'slug', 'plan', 'status', 'is_active', 'created_at']
    readonly_fields = ['created_at']
    can_delete = True


class TenantSettingsInline(admin.StackedInline):
    """
    Inline admin for tenant settings.
    """
    model = TenantSettings
    form = TenantSettingsAdminForm
    extra = 0
    can_delete = False
    fieldsets = (
        ('App Configuration', {
            'fields': ('app_name', 'app_description', 'support_email', 'privacy_policy_url', 'terms_url', 'about_url')
        }),
        ('Feature Flags', {
            'fields': ('enable_referral', 'enable_offerwall', 'enable_kyc', 'enable_leaderboard', 'enable_chat', 'enable_push_notifications', 'enable_analytics', 'enable_api_access')
        }),
        ('Payout Configuration', {
            'fields': ('min_withdrawal', 'max_withdrawal', 'withdrawal_fee_percent', 'withdrawal_fee_fixed', 'daily_withdrawal_limit')
        }),
        ('Referral Configuration', {
            'fields': ('referral_bonus_amount', 'referral_bonus_type', 'max_referral_levels', 'referral_percentages')
        }),
        ('Email Configuration', {
            'fields': ('email_from_name', 'email_from_address', 'email_reply_to')
        }),
        ('Security Configuration', {
            'fields': ('require_email_verification', 'require_phone_verification', 'enable_two_factor_auth', 'password_min_length', 'session_timeout_minutes')
        }),
        ('Rate Limiting', {
            'fields': ('api_rate_limit', 'login_rate_limit')
        }),
        ('Custom Configuration', {
            'fields': ('custom_config',),
            'classes': ('collapse',)
        }),
    )


class TenantBillingInline(admin.StackedInline):
    """
    Inline admin for tenant billing.
    """
    model = TenantBilling
    form = TenantBillingAdminForm
    extra = 0
    can_delete = False
    fieldsets = (
        ('Subscription Details', {
            'fields': ('status', 'billing_cycle', 'monthly_price', 'setup_fee', 'currency')
        }),
        ('Dates', {
            'fields': ('trial_ends_at', 'subscription_starts_at', 'subscription_ends_at', 'last_payment_at', 'next_payment_at')
        }),
        ('Payment Processing', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id', 'payment_method_id')
        }),
        ('Usage Tracking', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Metadata', {
            'fields': ('billing_metadata',),
            'classes': ('collapse',)
        }),
    )


class TenantInvoiceInline(admin.TabularInline):
    """
    Inline admin for tenant invoices.
    """
    model = TenantInvoice
    extra = 0
    fields = ['invoice_number', 'amount', 'total_amount', 'status', 'issue_date', 'due_date', 'paid_at']
    readonly_fields = ['invoice_number']
    can_delete = True


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Comprehensive admin interface for Tenant model.
    """
    form = TenantAdminForm
    list_display = [
        'name', 'slug', 'domain', 'plan', 'status', 'is_active',
        'user_count', 'billing_status', 'created_at', 'health_indicator'
    ]
    list_filter = [
        'plan', 'status', 'is_active', 'is_deleted', 'is_suspended',
        'country_code', 'currency_code', 'created_at'
    ]
    search_fields = ['name', 'slug', 'domain', 'admin_email', 'contact_phone']
    list_editable = ['is_active', 'status']
    readonly_fields = [
        'id', 'api_key', 'api_secret', 'webhook_secret', 'created_at', 
        'updated_at', 'deleted_at', 'trial_info_display', 'usage_stats_display'
    ]
    ordering = ['-created_at']
    
    inlines = [
        TenantSettingsInline,
        TenantBillingInline,
        TenantInvoiceInline,
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'domain', 'owner', 'parent_tenant')
        }),
        ('Contact Information', {
            'fields': ('admin_email', 'contact_phone', 'support_email')
        }),
        ('Branding', {
            'fields': ('logo', 'primary_color', 'secondary_color')
        }),
        ('Subscription', {
            'fields': ('plan', 'status', 'max_users', 'trial_ends_at')
        }),
        ('Mobile App Configuration', {
            'fields': ('android_package_name', 'ios_bundle_id', 'firebase_server_key')
        }),
        ('Geographic & Regional', {
            'fields': ('timezone', 'country_code', 'currency_code', 'data_region')
        }),
        ('Security & Access', {
            'fields': ('api_key', 'api_secret', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('Status & Management', {
            'fields': ('is_active', 'is_deleted', 'is_suspended', 'deleted_at')
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('trial_info_display', 'usage_stats_display'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_tenants', 'suspend_tenants', 'extend_trial', 
        'send_welcome_email', 'regenerate_api_keys', 'export_selected'
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related(
            'owner', 'parent_tenant'
        ).prefetch_related(
            'users', 'invoices', 'audit_logs'
        ).annotate(
            user_count=Count('users', filter=Q(users__is_active=True))
        )
    
    def user_count(self, obj):
        """Display user count with link."""
        count = obj.get_active_user_count()
        url = reverse('admin:auth_user_changelist') + f'?tenant__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    user_count.short_description = _('Active Users')
    
    def billing_status(self, obj):
        """Display billing status."""
        try:
            billing = obj.get_billing()
            status_color = {
                'active': 'green',
                'trial': 'blue',
                'past_due': 'orange',
                'cancelled': 'red',
                'expired': 'red'
            }.get(billing.status, 'gray')
            
            return format_html(
                '<span style="color: {};">{}</span>',
                status_color,
                billing.status.title()
            )
        except:
            return _('Unknown')
    billing_status.short_description = _('Billing Status')
    
    def health_indicator(self, obj):
        """Display health indicator."""
        issues = []
        
        if not obj.is_active:
            issues.append('Inactive')
        if obj.is_deleted:
            issues.append('Deleted')
        if obj.is_suspended:
            issues.append('Suspended')
        if obj.is_user_limit_reached():
            issues.append('User Limit')
        if obj.trial_expired:
            issues.append('Trial Expired')
        
        if issues:
            color = 'red'
            text = ', '.join(issues)
        else:
            color = 'green'
            text = 'Healthy'
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            text
        )
    health_indicator.short_description = _('Health')
    
    def trial_info_display(self, obj):
        """Display trial information."""
        if not obj.trial_ends_at:
            return _('No Trial')
        
        days_remaining = obj.days_until_trial_expires
        if obj.trial_expired:
            color = 'red'
            status = _('Expired')
        elif days_remaining <= 3:
            color = 'orange'
            status = _('Expiring Soon')
        else:
            color = 'green'
            status = _('Active')
        
        return format_html(
            '<span style="color: {};">{} ({} days)</span>',
            color,
            status,
            days_remaining
        )
    trial_info_display.short_description = _('Trial Info')
    
    def usage_stats_display(self, obj):
        """Display usage statistics."""
        stats = obj.get_usage_stats()
        users = stats.get('users', {})
        
        return format_html(
            '<strong>Users:</strong> {}/{} ({:.1f}% used)',
            users.get('active', 0),
            users.get('limit', 0),
            (users.get('active', 0) / max(1, users.get('limit', 1))) * 100
        )
    usage_stats_display.short_description = _('Usage Stats')
    
    # Admin Actions
    def activate_tenants(self, request, queryset):
        """Activate selected tenants."""
        updated = queryset.update(is_active=True, is_suspended=False)
        self.message_user(request, _(f'{updated} tenants activated successfully.'))
    activate_tenants.short_description = _('Activate selected tenants')
    
    def suspend_tenants(self, request, queryset):
        """Suspend selected tenants."""
        updated = queryset.update(is_active=False, is_suspended=True)
        self.message_user(request, _(f'{updated} tenants suspended successfully.'))
    suspend_tenants.short_description = _('Suspend selected tenants')
    
    def extend_trial(self, request, queryset):
        """Extend trial for selected tenants."""
        count = 0
        for tenant in queryset:
            try:
                billing = tenant.get_billing()
                billing.extend_trial(7)  # Extend by 7 days
                count += 1
            except Exception as e:
                self.message_user(request, _(f'Error extending trial for {tenant.name}: {e}'), level='error')
        
        self.message_user(request, _(f'Trial extended for {count} tenants.'))
    extend_trial.short_description = _('Extend trial by 7 days')
    
    def send_welcome_email(self, request, queryset):
        """Send welcome email to selected tenants."""
        from .services_improved import tenant_service
        
        count = 0
        for tenant in queryset:
            try:
                tenant_service._send_welcome_email(tenant)
                count += 1
            except Exception as e:
                self.message_user(request, _(f'Error sending welcome email to {tenant.name}: {e}'), level='error')
        
        self.message_user(request, _(f'Welcome email sent to {count} tenants.'))
    send_welcome_email.short_description = _('Send welcome email')
    
    def regenerate_api_keys(self, request, queryset):
        """Regenerate API keys for selected tenants."""
        from .services_improved import tenant_service
        
        count = 0
        for tenant in queryset:
            try:
                tenant_service.regenerate_api_credentials(tenant, 'api_key')
                count += 1
            except Exception as e:
                self.message_user(request, _(f'Error regenerating API keys for {tenant.name}: {e}'), level='error')
        
        self.message_user(request, _(f'API keys regenerated for {count} tenants.'))
    regenerate_api_keys.short_description = _('Regenerate API keys')
    
    def export_selected(self, request, queryset):
        """Export selected tenants data."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tenants_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Slug', 'Domain', 'Plan', 'Status', 'Active Users',
            'Max Users', 'Admin Email', 'Created At'
        ])
        
        for tenant in queryset:
            writer.writerow([
                tenant.name,
                tenant.slug,
                tenant.domain or '',
                tenant.plan,
                tenant.status,
                tenant.get_active_user_count(),
                tenant.max_users,
                tenant.admin_email,
                tenant.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected.short_description = _('Export selected tenants')


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantSettings model.
    """
    form = TenantSettingsAdminForm
    list_display = [
        'tenant', 'app_name', 'enable_referral', 'enable_offerwall',
        'enable_kyc', 'enable_leaderboard', 'min_withdrawal'
    ]
    list_filter = [
        'enable_referral', 'enable_offerwall', 'enable_kyc', 
        'enable_leaderboard', 'enable_chat', 'enable_push_notifications'
    ]
    search_fields = ['tenant__name', 'tenant__slug', 'app_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('App Configuration', {
            'fields': ('app_name', 'app_description', 'support_email', 'privacy_policy_url', 'terms_url', 'about_url')
        }),
        ('Feature Flags', {
            'fields': ('enable_referral', 'enable_offerwall', 'enable_kyc', 'enable_leaderboard', 'enable_chat', 'enable_push_notifications', 'enable_analytics', 'enable_api_access')
        }),
        ('Payout Configuration', {
            'fields': ('min_withdrawal', 'max_withdrawal', 'withdrawal_fee_percent', 'withdrawal_fee_fixed', 'daily_withdrawal_limit')
        }),
        ('Referral Configuration', {
            'fields': ('referral_bonus_amount', 'referral_bonus_type', 'max_referral_levels', 'referral_percentages')
        }),
        ('Email Configuration', {
            'fields': ('email_from_name', 'email_from_address', 'email_reply_to')
        }),
        ('Security Configuration', {
            'fields': ('require_email_verification', 'require_phone_verification', 'enable_two_factor_auth', 'password_min_length', 'session_timeout_minutes')
        }),
        ('Rate Limiting', {
            'fields': ('api_rate_limit', 'login_rate_limit')
        }),
        ('Custom Configuration', {
            'fields': ('custom_config', 'custom_css', 'custom_js'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TenantBilling)
class TenantBillingAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantBilling model.
    """
    form = TenantBillingAdminForm
    list_display = [
        'tenant', 'status', 'billing_cycle', 'monthly_price',
        'is_active', 'trial_ends_at', 'subscription_ends_at'
    ]
    list_filter = [
        'status', 'billing_cycle', 'currency', 'created_at'
    ]
    search_fields = ['tenant__name', 'tenant__slug', 'stripe_customer_id']
    readonly_fields = [
        'created_at', 'updated_at', 'is_active_display',
        'days_until_expiry_display'
    ]
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Subscription Details', {
            'fields': ('status', 'billing_cycle', 'monthly_price', 'setup_fee', 'currency')
        }),
        ('Dates', {
            'fields': ('trial_ends_at', 'subscription_starts_at', 'subscription_ends_at', 'last_payment_at', 'next_payment_at', 'cancelled_at')
        }),
        ('Payment Processing', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id', 'payment_method_id')
        }),
        ('Usage Tracking', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'is_active_display', 'days_until_expiry_display'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_display(self, obj):
        """Display subscription status."""
        if obj.is_active:
            return format_html('<span style="color: green;">Active</span>')
        else:
            return format_html('<span style="color: red;">Inactive</span>')
    is_active_display.short_description = _('Subscription Status')
    
    def days_until_expiry_display(self, obj):
        """Display days until expiry."""
        days = obj.days_until_expiry
        if days is None:
            return _('N/A')
        elif days <= 0:
            return format_html('<span style="color: red;">Expired</span>')
        elif days <= 7:
            return format_html('<span style="color: orange;">{} days</span>', days)
        else:
            return format_html('<span style="color: green;">{} days</span>', days)
    days_until_expiry_display.short_description = _('Days Until Expiry')


@admin.register(TenantInvoice)
class TenantInvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantInvoice model.
    """
    list_display = [
        'invoice_number', 'tenant', 'amount', 'total_amount', 'status',
        'issue_date', 'due_date', 'is_overdue_display'
    ]
    list_filter = [
        'status', 'currency', 'issue_date', 'due_date', 'created_at'
    ]
    search_fields = [
        'invoice_number', 'tenant__name', 'tenant__slug',
        'transaction_id', 'payment_method'
    ]
    readonly_fields = [
        'invoice_number', 'created_at', 'updated_at',
        'is_overdue_display', 'days_overdue_display', 'amount_due_display'
    ]
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'tenant', 'description')
        }),
        ('Amounts', {
            'fields': ('amount', 'tax_amount', 'total_amount', 'currency')
        }),
        ('Status & Dates', {
            'fields': ('status', 'issue_date', 'due_date', 'paid_at')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'transaction_id', 'payment_notes')
        }),
        ('Line Items', {
            'fields': ('line_items',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'is_overdue_display', 'days_overdue_display', 'amount_due_display'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_paid', 'send_invoice_email']
    
    def is_overdue_display(self, obj):
        """Display overdue status."""
        if obj.is_overdue:
            return format_html('<span style="color: red;">Overdue ({} days)</span>', obj.days_overdue)
        else:
            return format_html('<span style="color: green;">On Time</span>')
    is_overdue_display.short_description = _('Overdue Status')
    
    def days_overdue_display(self, obj):
        """Display days overdue."""
        return obj.days_overdue
    days_overdue_display.short_description = _('Days Overdue')
    
    def amount_due_display(self, obj):
        """Display amount due."""
        return format_html('${:.2f}', obj.amount_due)
    amount_due_display.short_description = _('Amount Due')
    
    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid."""
        count = 0
        for invoice in queryset.filter(status__in=['draft', 'sent', 'partially_paid', 'overdue']):
            try:
                invoice.mark_as_paid(
                    payment_method='manual',
                    notes=f'Marked as paid by admin: {request.user.username}'
                )
                count += 1
            except Exception as e:
                self.message_user(request, _(f'Error marking invoice {invoice.invoice_number} as paid: {e}'), level='error')
        
        self.message_user(request, _(f'{count} invoices marked as paid.'))
    mark_as_paid.short_description = _('Mark selected as paid')
    
    def send_invoice_email(self, request, queryset):
        """Send invoice emails."""
        count = 0
        for invoice in queryset:
            try:
                # Here you would implement email sending logic
                count += 1
            except Exception as e:
                self.message_user(request, _(f'Error sending invoice {invoice.invoice_number}: {e}'), level='error')
        
        self.message_user(request, _(f'Invoice emails sent for {count} invoices.'))
    send_invoice_email.short_description = _('Send invoice emails')


@admin.register(TenantAuditLog)
class TenantAuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantAuditLog model.
    """
    list_display = [
        'tenant', 'action', 'user_email', 'success', 'ip_address',
        'created_at', 'details_summary'
    ]
    list_filter = [
        'action', 'success', 'created_at', 'country'
    ]
    search_fields = [
        'tenant__name', 'tenant__slug', 'user_email', 'action',
        'ip_address', 'details'
    ]
    readonly_fields = [
        'tenant', 'action', 'details', 'old_values', 'new_values',
        'user', 'user_email', 'user_role', 'ip_address', 'user_agent',
        'request_id', 'country', 'city', 'success', 'error_message',
        'created_at', 'details_display'
    ]
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('tenant', 'action', 'success', 'created_at')
        }),
        ('User Information', {
            'fields': ('user', 'user_email', 'user_role')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'request_id', 'country', 'city')
        }),
        ('Change Details', {
            'fields': ('details', 'old_values', 'new_values', 'details_display'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def details_summary(self, obj):
        """Display summary of details."""
        if not obj.details:
            return '-'
        
        # Show first few key-value pairs
        items = list(obj.details.items())[:3]
        summary = ', '.join([f'{k}: {v}' for k, v in items])
        
        if len(obj.details) > 3:
            summary += '...'
        
        return summary
    details_summary.short_description = _('Details Summary')
    
    def details_display(self, obj):
        """Display formatted details."""
        if not obj.details:
            return '-'
        
        html = '<table>'
        for key, value in obj.details.items():
            html += f'<tr><td><strong>{key}:</strong></td><td>{value}</td></tr>'
        html += '</table>'
        
        return mark_safe(html)
    details_display.short_description = _('Full Details')
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only allow deletion by superusers."""
        return request.user.is_superuser


# Customize User admin to show tenant information
class UserTenantInline(admin.TabularInline):
    """
    Inline admin for user's tenant relationships.
    """
    model = Tenant
    fk_name = 'owner'
    extra = 0
    fields = ['name', 'slug', 'plan', 'status', 'is_active']
    readonly_fields = ['name', 'slug', 'plan', 'status']


# Extend UserAdmin
UserAdmin.inlines = UserAdmin.inlines + [UserTenantInline]

# Customize admin site header and title
admin.site.site_header = _('Tenant Management System')
admin.site.site_title = _('Tenant Admin')
admin.site.index_title = _('Welcome to Tenant Management System')
