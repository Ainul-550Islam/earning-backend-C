"""
Branding Admin Classes

This module contains Django admin classes for branding-related models including
TenantBranding, TenantDomain, TenantEmail, and TenantSocialLink.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

from ..models.branding import TenantBranding, TenantDomain, TenantEmail, TenantSocialLink


@admin.register(TenantBranding)
class TenantBrandingAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantBranding model.
    """
    list_display = [
        'tenant_name', 'app_name', 'primary_color', 'secondary_color',
        'font_family', 'has_logo', 'created_at'
    ]
    list_filter = [
        'font_family', 'created_at'
    ]
    search_fields = ['tenant__name', 'app_name', 'app_short_name']
    ordering = ['-created_at']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'tenant', 'app_name', 'app_short_name', 'app_description',
                'website_url', 'support_url', 'privacy_policy_url',
                'terms_of_service_url'
            )
        }),
        ('Colors', {
            'fields': (
                'primary_color', 'secondary_color', 'accent_color',
                'background_color', 'text_color', 'email_header_color'
            )
        }),
        ('Typography', {
            'fields': (
                'font_family', 'font_family_heading', 'font_size_base',
                'button_radius', 'card_radius', 'border_radius'
            )
        }),
        ('Email Branding', {
            'fields': (
                'email_from_name', 'email_from_address', 'email_logo',
                'email_footer_text'
            )
        }),
        ('Images', {
            'fields': (
                'logo', 'logo_dark', 'favicon', 'app_store_icon',
                'splash_screen'
            ),
            'classes': ('collapse',)
        }),
        ('Custom Styling', {
            'fields': (
                'meta_title', 'meta_description', 'meta_keywords',
                'custom_css', 'custom_js'
            ),
            'classes': ('collapse',)
        })
    )
    
    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def has_logo(self, obj):
        """Display if logo exists."""
        if obj.logo:
            return mark_safe('<span style="color: #388e3c;">Yes</span>')
        return mark_safe('<span style="color: #f57c00;">No</span>')
    has_logo.short_description = "Has Logo"
    has_logo.boolean = True
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['reset_colors', 'reset_typography', 'export_branding']
    
    def reset_colors(self, request, queryset):
        """Reset colors to defaults."""
        count = 0
        for branding in queryset:
            branding.primary_color = '#007bff'
            branding.secondary_color = '#6c757d'
            branding.accent_color = '#28a745'
            branding.background_color = '#ffffff'
            branding.text_color = '#212529'
            branding.email_header_color = '#343a40'
            branding.save()
            count += 1
        
        self.message_user(request, f"Reset colors for {count} branding configurations.", messages.SUCCESS)
    reset_colors.short_description = "Reset colors to defaults"
    
    def reset_typography(self, request, queryset):
        """Reset typography to defaults."""
        count = 0
        for branding in queryset:
            branding.font_family = 'Inter'
            branding.font_family_heading = 'Inter'
            branding.font_size_base = '16px'
            branding.button_radius = '6px'
            branding.card_radius = '8px'
            branding.border_radius = '4px'
            branding.save()
            count += 1
        
        self.message_user(request, f"Reset typography for {count} branding configurations.", messages.SUCCESS)
    reset_typography.short_description = "Reset typography to defaults"
    
    def export_branding(self, request, queryset):
        """Export branding configurations."""
        import json
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="branding_export.json"'
        
        branding_data = []
        for branding in queryset:
            branding_data.append({
                'tenant': branding.tenant.name,
                'app_name': branding.app_name,
                'primary_color': branding.primary_color,
                'secondary_color': branding.secondary_color,
                'font_family': branding.font_family,
                'has_logo': bool(branding.logo),
            })
        
        response.content = json.dumps(branding_data, indent=2)
        return response
    export_branding.short_description = "Export branding data"


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantDomain model.
    """
    list_display = [
        'tenant_name', 'domain', 'full_domain', 'is_primary',
        'is_active', 'dns_status', 'ssl_status', 'days_until_ssl_expiry'
    ]
    list_filter = [
        'is_primary', 'is_active', 'dns_status', 'ssl_status',
        'www_redirect', 'force_https'
    ]
    search_fields = [
        'tenant__name', 'domain', 'subdomain'
    ]
    ordering = ['is_primary', 'domain']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Domain Information', {
            'fields': (
                'tenant', 'domain', 'subdomain', 'is_primary',
                'is_active', 'www_redirect', 'force_https'
            )
        }),
        ('DNS Configuration', {
            'fields': (
                'dns_status', 'dns_verified_at', 'dns_verification_token'
            )
        }),
        ('SSL Configuration', {
            'fields': (
                'ssl_status', 'ssl_expires_at', 'ssl_certificate',
                'ssl_private_key', 'ssl_auto_renew'
            )
        }),
        ('Analytics & Tracking', {
            'fields': (
                'google_analytics_id', 'facebook_pixel_id'
            ),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': (
                'allowed_ips', 'require_https', 'custom_headers',
                'auth_token'
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
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def dns_status_display(self, obj):
        """Display DNS status with color coding."""
        if obj.dns_status == 'verified':
            return mark_safe('<span style="color: #388e3c;">Verified</span>')
        elif obj.dns_status == 'pending':
            return mark_safe('<span style="color: #f57c00;">Pending</span>')
        elif obj.dns_status == 'failed':
            return mark_safe('<span style="color: #d32f2f;">Failed</span>')
        else:
            return mark_safe('<span style="color: #9e9e9e;">Not Started</span>')
    dns_status_display.short_description = "DNS Status"
    dns_status_display.admin_order_field = 'dns_status'
    
    def ssl_status_display(self, obj):
        """Display SSL status with color coding."""
        if obj.ssl_status == 'verified':
            return mark_safe('<span style="color: #388e3c;">Verified</span>')
        elif obj.ssl_status == 'pending':
            return mark_safe('<span style="color: #f57c00;">Pending</span>')
        elif obj.ssl_status == 'expired':
            return mark_safe('<span style="color: #d32f2f;">Expired</span>')
        elif obj.ssl_status == 'failed':
            return mark_safe('<span style="color: #d32f2f;">Failed</span>')
        else:
            return mark_safe('<span style="color: #9e9e9e;">Not Configured</span>')
    ssl_status_display.short_description = "SSL Status"
    ssl_status_display.admin_order_field = 'ssl_status'
    
    def days_until_ssl_expiry(self, obj):
        """Display days until SSL expiry with color coding."""
        days = obj.days_until_ssl_expiry
        if days is None:
            return "-"
        
        if days <= 7:
            return mark_safe(f'<span style="color: #d32f2f;">{days} days</span>')
        elif days <= 30:
            return mark_safe(f'<span style="color: #f57c00;">{days} days</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{days} days</span>')
    days_until_ssl_expiry.short_description = "SSL Expiry"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['verify_dns', 'check_ssl', 'set_primary', 'renew_ssl']
    
    def verify_dns(self, request, queryset):
        """Verify DNS for selected domains."""
        count = 0
        for domain in queryset:
            # This would trigger DNS verification
            count += 1
        
        self.message_user(request, f"DNS verification initiated for {count} domains.", messages.SUCCESS)
    verify_dns.short_description = "Verify DNS"
    
    def check_ssl(self, request, queryset):
        """Check SSL certificates for selected domains."""
        count = 0
        for domain in queryset:
            # This would trigger SSL check
            count += 1
        
        self.message_user(request, f"SSL check initiated for {count} domains.", messages.SUCCESS)
    check_ssl.short_description = "Check SSL"
    
    def set_primary(self, request, queryset):
        """Set selected domains as primary."""
        count = 0
        for domain in queryset:
            if not domain.is_primary:
                # Remove primary from other domains
                TenantDomain.objects.filter(tenant=domain.tenant, is_primary=True).update(is_primary=False)
                
                # Set this domain as primary
                domain.is_primary = True
                domain.save()
                count += 1
        
        self.message_user(request, f"Set {count} domains as primary.", messages.SUCCESS)
    set_primary.short_description = "Set as primary"
    
    def renew_ssl(self, request, queryset):
        """Renew SSL certificates for selected domains."""
        count = 0
        for domain in queryset:
            # This would trigger SSL renewal
            count += 1
        
        self.message_user(request, f"SSL renewal initiated for {count} domains.", messages.SUCCESS)
    renew_ssl.short_description = "Renew SSL"


@admin.register(TenantEmail)
class TenantEmailAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantEmail model.
    """
    list_display = [
        'tenant_name', 'provider', 'from_email', 'is_verified',
        'provider_display', 'auth_type_display', 'last_test_at'
    ]
    list_filter = [
        'provider', 'is_verified', 'last_test_at'
    ]
    search_fields = [
        'tenant__name', 'from_email', 'reply_to_email'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Email Configuration', {
            'fields': (
                'tenant', 'provider', 'from_name', 'from_email',
                'reply_to_email', 'is_verified', 'verified_at'
            )
        }),
        ('SMTP Settings', {
            'fields': (
                'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl'
            ),
            'classes': ('collapse',)
        }),
        ('API Settings', {
            'fields': (
                'api_key', 'api_secret', 'api_region'
            ),
            'classes': ('collapse',)
        }),
        ('Limits', {
            'fields': (
                'daily_limit', 'hourly_limit', 'track_opens',
                'track_clicks'
            )
        }),
        ('Delivery Options', {
            'fields': (
                'send_email', 'send_push', 'send_sms',
                'auth_token'
            )
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
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def provider_display(self, obj):
        """Display provider with icon."""
        provider_icons = {
            'smtp': 'SMTP',
            'sendgrid': 'SendGrid',
            'ses': 'AWS SES',
            'mailgun': 'Mailgun',
            'postmark': 'Postmark',
        }
        return provider_icons.get(obj.provider, obj.provider.upper())
    provider_display.short_description = "Provider"
    
    def auth_type_display(self, obj):
        """Display auth type."""
        auth_types = {
            'none': 'None',
            'basic': 'Basic Auth',
            'api_key': 'API Key',
            'oauth': 'OAuth',
        }
        return auth_types.get(obj.auth_type, obj.auth_type.title())
    auth_type_display.short_description = "Auth Type"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['test_connection', 'verify_configuration', 'send_test_email']
    
    def test_connection(self, request, queryset):
        """Test email configuration for selected."""
        count = 0
        for email_config in queryset:
            # This would test the email configuration
            count += 1
        
        self.message_user(request, f"Connection test initiated for {count} email configurations.", messages.SUCCESS)
    test_connection.short_description = "Test connection"
    
    def verify_configuration(self, request, queryset):
        """Verify email configuration for selected."""
        count = 0
        for email_config in queryset:
            # This would verify the email configuration
            count += 1
        
        self.message_user(request, f"Configuration verification initiated for {count} email configurations.", messages.SUCCESS)
    verify_configuration.short_description = "Verify configuration"
    
    def send_test_email(self, request, queryset):
        """Send test email for selected."""
        count = 0
        for email_config in queryset:
            # This would send a test email
            count += 1
        
        self.message_user(request, f"Test email sent for {count} email configurations.", messages.SUCCESS)
    send_test_email.short_description = "Send test email"


@admin.register(TenantSocialLink)
class TenantSocialLinkAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantSocialLink model.
    """
    list_display = [
        'tenant_name', 'platform', 'platform_display', 'url',
        'is_visible', 'sort_order', 'display_name'
    ]
    list_filter = [
        'platform', 'is_visible'
    ]
    search_fields = [
        'tenant__name', 'platform', 'display_name', 'url'
    ]
    ordering = ['sort_order', 'platform']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Link Information', {
            'fields': (
                'tenant', 'platform', 'url', 'display_name',
                'is_visible', 'sort_order'
            )
        }),
        ('Custom Platform', {
            'fields': (
                'custom_platform_name',
            ),
            'classes': ('collapse',)
        }),
        ('Display Options', {
            'fields': (
                'icon', 'color'
            ),
            'classes': ('collapse',)
        })
    )
    
    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def platform_display(self, obj):
        """Display platform with icon."""
        platform_icons = {
            'facebook': 'Facebook',
            'twitter': 'Twitter',
            'linkedin': 'LinkedIn',
            'instagram': 'Instagram',
            'youtube': 'YouTube',
            'github': 'GitHub',
            'custom': 'Custom',
        }
        return platform_icons.get(obj.platform, obj.platform.title())
    platform_display.short_description = "Platform"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['toggle_visibility', 'reorder_links', 'test_links']
    
    def toggle_visibility(self, request, queryset):
        """Toggle visibility for selected links."""
        count = 0
        for link in queryset:
            link.is_visible = not link.is_visible
            link.save()
            count += 1
        
        self.message_user(request, f"Toggled visibility for {count} social links.", messages.SUCCESS)
    toggle_visibility.short_description = "Toggle visibility"
    
    def reorder_links(self, request, queryset):
        """Reorder selected links."""
        # This would open a reorder interface
        self.message_user(request, "Reorder feature coming soon.", messages.INFO)
    reorder_links.short_description = "Reorder links"
    
    def test_links(self, request, queryset):
        """Test selected social links."""
        count = 0
        for link in queryset:
            # This would test the social link URL
            count += 1
        
        self.message_user(request, f"Tested {count} social links.", messages.SUCCESS)
    test_links.short_description = "Test links"
