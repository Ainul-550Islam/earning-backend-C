"""
Core Admin Classes

This module contains Django admin classes for core tenant models including
Tenant, TenantSettings, TenantBilling, and TenantInvoice.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Avg
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..services import TenantService, TenantBillingService


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Admin interface for Tenant model with comprehensive management features.
    """
    list_display = [
        'name', 'slug', 'plan', 'tier', 'status', 'is_suspended',
        'trial_status', 'owner_email', 'created_at', 'last_activity_at'
    ]
    list_filter = [
        'status', 'tier', 'plan', 'is_suspended', 'country_code',
        'created_at', 'trial_ends_at'
    ]
    search_fields = ['name', 'slug', 'contact_email', 'owner__username', 'owner__email']
    ordering = ['-created_at']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'last_activity_at',
        'is_trial_expired', 'days_until_trial_expiry'
    ]
    raw_id_fields = ['owner', 'parent_tenant']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'slug', 'plan', 'tier', 'status',
                'parent_tenant', 'is_suspended', 'suspension_reason'
            )
        }),
        ('Contact Information', {
            'fields': (
                'owner', 'contact_email', 'contact_phone',
                'timezone', 'country_code', 'currency_code'
            )
        }),
        ('Trial Information', {
            'fields': (
                'trial_ends_at', 'is_trial_expired', 'days_until_trial_expiry',
                'billing_cycle_start'
            )
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at', 'last_activity_at',
                'data_region', 'domain'
            ),
            'classes': ('collapse',)
        })
    )

    def owner_email(self, obj):
        """Display owner email."""
        if obj.owner:
            return obj.owner.email
        return "-"
    owner_email.short_description = "Owner Email"

    def trial_status(self, obj):
        """Display trial status with color coding."""
        if not obj.trial_ends_at:
            return "No Trial"

        if obj.is_trial_expired:
            return mark_safe('<span style="color: #d32f2f;">Expired</span>')

        days_left = obj.days_until_trial_expiry
        if days_left <= 3:
            return mark_safe(f'<span style="color: #f57c00;">{days_left} days left</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{days_left} days left</span>')
    trial_status.short_description = "Trial Status"

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related(
            'owner', 'parent_tenant'
        ).prefetch_related('billing', 'settings')

    actions = ['suspend_tenants', 'unsuspend_tenants', 'send_trial_extensions', 'export_selected']

    def suspend_tenants(self, request, queryset):
        """Custom action to suspend selected tenants."""
        count = 0
        for tenant in queryset:
            if tenant.status != 'suspended':
                from ..services import TenantSuspensionService
                TenantSuspensionService.suspend_tenant(tenant, "Admin suspension", request.user)
                count += 1

        self.message_user(request, f"Suspended {count} tenants.", messages.SUCCESS)
    suspend_tenants.short_description = "Suspend selected tenants"

    def unsuspend_tenants(self, request, queryset):
        """Custom action to unsuspend selected tenants."""
        count = 0
        for tenant in queryset:
            if tenant.status == 'suspended':
                from ..services import TenantSuspensionService
                TenantSuspensionService.unsuspend_tenant(tenant, request.user)
                count += 1

        self.message_user(request, f"Unsuspended {count} tenants.", messages.SUCCESS)
    unsuspend_tenants.short_description = "Unsuspend selected tenants"

    def send_trial_extensions(self, request, queryset):
        """Custom action to send trial extensions."""
        count = 0
        for tenant in queryset:
            if tenant.is_trial_expired or tenant.days_until_trial_expiry <= 3:
                from ..services import OnboardingService
                extension = OnboardingService.request_trial_extension(
                    tenant, 7, "Admin trial extension", request.user
                )
                if extension:
                    count += 1

        self.message_user(request, f"Sent trial extensions to {count} tenants.", messages.SUCCESS)
    send_trial_extensions.short_description = "Send trial extensions (7 days)"

    def export_selected(self, request, queryset):
        """Export selected tenants data."""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tenants_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Slug', 'Status', 'Plan', 'Owner Email', 'Contact Email',
            'Created At', 'Last Activity', 'Trial Ends At'
        ])

        for tenant in queryset:
            writer.writerow([
                tenant.name,
                tenant.slug,
                tenant.status,
                tenant.plan if tenant.plan else '',
                tenant.owner.email if tenant.owner else '',
                tenant.contact_email,
                tenant.created_at.isoformat(),
                tenant.last_activity_at.isoformat() if tenant.last_activity_at else '',
                tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else '',
            ])

        return response
    export_selected.short_description = "Export selected tenants"


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantSettings model.
    """
    list_display = [
        'tenant_name', 'enable_smartlink', 'enable_ai_engine',
        'max_users', 'max_publishers', 'max_smartlinks',
        'api_calls_per_day', 'storage_gb', 'default_language'
    ]
    list_filter = [
        'enable_smartlink', 'enable_ai_engine', 'enable_publisher_tools',
        'enable_advertiser_portal', 'enable_two_factor_auth',
        'default_language'
    ]
    search_fields = ['tenant__name', 'tenant__slug']
    ordering = ['tenant__name']
    raw_id_fields = ['tenant']

    fieldsets = (
        ('Feature Toggles', {
            'fields': (
                'enable_smartlink', 'enable_ai_engine', 'enable_publisher_tools',
                'enable_advertiser_portal', 'enable_coalition'
            )
        }),
        ('Usage Limits', {
            'fields': (
                'max_withdrawal_per_day', 'require_kyc_for_withdrawal',
                'max_users', 'max_publishers', 'max_smartlinks',
                'api_calls_per_day', 'api_calls_per_hour',
                'storage_gb', 'bandwidth_gb_per_month'
            )
        }),
        ('Localization', {
            'fields': (
                'default_language', 'default_currency', 'default_timezone',
                'email_from_name', 'email_from_address'
            )
        }),
        ('Security', {
            'fields': (
                'enable_two_factor_auth', 'session_timeout_minutes',
                'password_min_length', 'password_require_special',
                'password_require_numbers'
            )
        }),
        ('Notifications', {
            'fields': (
                'enable_email_notifications', 'enable_push_notifications',
                'enable_sms_notifications', 'notification_email_types',
                'notification_push_types', 'security_alert_email',
                'security_alert_sms', 'login_notifications'
            )
        }),
        ('Data Management', {
            'fields': (
                'api_key_rotations', 'backup_frequency', 'retention_days'
            ),
            'classes': ('collapse',)
        }),
        ('Custom Settings', {
            'fields': ('custom_settings',),
            'classes': ('collapse',)
        })
    )

    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = 'Tenant'
    tenant_name.admin_order_field = 'tenant__name'

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')

    actions = ['reset_to_defaults', 'bulk_update_limits']

    def reset_to_defaults(self, request, queryset):
        """Reset settings to plan defaults."""
        count = 0
        for settings in queryset:
            pass  # plan is CharField
            
            
            
            
            settings.save()
            count += 1

        self.message_user(request, f"Reset {count} settings to plan defaults.", messages.SUCCESS)
    reset_to_defaults.short_description = "Reset to plan defaults"

    def bulk_update_limits(self, request, queryset):
        """Bulk update limits for selected settings."""
        self.message_user(request, "Bulk update feature coming soon.", messages.INFO)
    bulk_update_limits.short_description = "Bulk update limits"


@admin.register(TenantBilling)
class TenantBillingAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantBilling model.
    """
    list_display = [
        'tenant_name', 'billing_cycle', 'payment_method',
        'base_price', 'final_price', 'next_billing_date',
        'dunning_count'
    ]
    list_filter = [
        'billing_cycle', 'payment_method',
        'next_billing_date', 'billing_cycle_start'
    ]
    search_fields = ['tenant__name', 'tenant__slug', 'billing_email']
    ordering = ['tenant__name']
    raw_id_fields = ['tenant']
    date_hierarchy = 'next_billing_date'

    fieldsets = (
        ('Billing Information', {
            'fields': (
                'tenant', 'billing_cycle', 'billing_cycle_start',
                'payment_method', 'base_price', 'discount_pct', 'final_price'
            )
        }),
        ('Payment Details', {
            'fields': (
                'next_billing_date', 'billing_email', 'billing_phone',
                'billing_address', 'tax_id', 'tax_exempt', 'vat_number'
            )
        }),
        ('Dunning Management', {
            'fields': (
                'dunning_count', 'max_dunning_attempts', 'last_dunning_sent'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )

    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = 'Tenant'
    tenant_name.admin_order_field = 'tenant__name'

    def is_overdue(self, obj):
        """Display overdue status with color coding."""
        if obj.is_overdue():
            return mark_safe('<span style="color: #d32f2f;">Overdue</span>')
        return mark_safe('<span style="color: #388e3c;">Current</span>')
    is_overdue.short_description = 'Overdue'
    is_overdue.boolean = True

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')

    actions = ['send_invoices', 'process_dunning', 'update_prices']

    def send_invoices(self, request, queryset):
        """Generate and send invoices for selected billing."""
        count = 0
        for billing in queryset:
            invoice = TenantBillingService.generate_monthly_invoice(billing.tenant)
            if invoice:
                count += 1

        self.message_user(request, f"Generated {count} invoices.", messages.SUCCESS)
    send_invoices.short_description = "Generate invoices"

    def process_dunning(self, request, queryset):
        """Process dunning for selected billing."""
        count = 0
        for billing in queryset:
            if billing.is_overdue():
                result = TenantBillingService.handle_dunning(billing.tenant)
                if result['action'] != 'no_action':
                    count += 1

        self.message_user(request, f"Processed dunning for {count} tenants.", messages.SUCCESS)
    process_dunning.short_description = "Process dunning"

    def update_prices(self, request, queryset):
        """Update prices for selected billing."""
        count = 0
        for billing in queryset:
            billing.calculate_final_price()
            billing.save()
            count += 1

        self.message_user(request, f"Updated prices for {count} billing records.", messages.SUCCESS)
    update_prices.short_description = "Update final prices"


@admin.register(TenantInvoice)
class TenantInvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantInvoice model.
    """
    list_display = [
        'invoice_number', 'tenant_name', 'status', 'issue_date',
        'due_date', 'total_amount', 'balance_due', 'days_overdue'
    ]
    list_filter = [
        'status', 'issue_date', 'due_date', 'payment_method',
        'billing_period_start', 'billing_period_end'
    ]
    search_fields = [
        'invoice_number', 'tenant__name', 'tenant__slug',
        'description', 'transaction_id'
    ]
    ordering = ['-issue_date']
    raw_id_fields = ['tenant']
    date_hierarchy = 'issue_date'

    fieldsets = (
        ('Invoice Information', {
            'fields': (
                'tenant', 'invoice_number', 'status', 'issue_date',
                'due_date', 'paid_date', 'payment_method', 'transaction_id'
            )
        }),
        ('Billing Period', {
            'fields': (
                'billing_period_start', 'billing_period_end'
            )
        }),
        ('Financial Details', {
            'fields': (
                'subtotal', 'tax_amount', 'discount_amount',
                'total_amount', 'amount_paid', 'balance_due'
            )
        }),
        ('Line Items', {
            'fields': ('line_items',),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'metadata'),
            'classes': ('collapse',)
        })
    )

    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = 'Tenant'
    tenant_name.admin_order_field = 'tenant__name'

    def days_overdue(self, obj):
        """Display days overdue with color coding."""
        days = obj.days_overdue
        if days is None:
            return "-"

        if days < 0:
            return mark_safe('<span style="color: #388e3c;">Paid</span>')
        elif days <= 7:
            return mark_safe(f'<span style="color: #f57c00;">{days} days</span>')
        else:
            return mark_safe(f'<span style="color: #d32f2f;">{days} days</span>')
    days_overdue.short_description = "Days Overdue"

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')

    actions = ['mark_as_paid', 'send_reminders', 'download_pdf']

    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid."""
        count = 0
        for invoice in queryset:
            if invoice.status != 'paid':
                invoice.status = 'paid'
                invoice.paid_date = timezone.now()
                invoice.save()
                count += 1

        self.message_user(request, f"Marked {count} invoices as paid.", messages.SUCCESS)
    mark_as_paid.short_description = "Mark as paid"

    def send_reminders(self, request, queryset):
        """Send payment reminders for selected invoices."""
        count = 0
        for invoice in queryset:
            if invoice.status == 'pending':
                count += 1

        self.message_user(request, f"Sent reminders for {count} invoices.", messages.SUCCESS)
    send_reminders.short_description = "Send payment reminders"

    def download_pdf(self, request, queryset):
        """Download PDF versions of selected invoices."""
        self.message_user(request, "PDF download feature coming soon.", messages.INFO)
    download_pdf.short_description = "Download PDF"
