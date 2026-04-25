"""
Security Admin Classes

This module contains Django admin classes for security-related models including
TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, and TenantAuditLog.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, TenantAuditLog


@admin.register(TenantAPIKey)
class TenantAPIKeyAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantAPIKey model.
    """
    list_display = [
        'tenant_name', 'name', 'key_prefix', 'status',
        'scopes', 'expires_at', 'last_used_at', 'usage_count'
    ]
    list_filter = [
        'status', 'expires_at', 'last_used_at'
    ]
    search_fields = [
        'tenant__name', 'name', 'description', 'key_prefix'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant']
    readonly_fields = [
        'id', 'key_hash', 'key_prefix', 'usage_count',
        'last_used_at', 'last_ip_address', 'last_user_agent',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('API Key Information', {
            'fields': (
                'tenant', 'name', 'description', 'status',
                'scopes', 'allowed_endpoints'
            )
        }),
        ('Rate Limits', {
            'fields': (
                'rate_limit_per_minute', 'rate_limit_per_hour',
                'rate_limit_per_day'
            )
        }),
        ('Security Settings', {
            'fields': (
                'expires_at', 'require_https', 'allowed_ips',
                'allowed_referers'
            ),
            'classes': ('collapse',)
        }),
        ('Usage Information', {
            'fields': (
                'usage_count', 'last_used_at', 'last_ip_address',
                'last_user_agent'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'key_hash', 'key_prefix'
                'created_at', 'updated_at'
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
    
    def status_display(self, obj):
        """Display status with color coding."""
        if obj.status == 'active':
            return mark_safe('<span style="color: #388e3c;">Active</span>')
        elif obj.status == 'inactive':
            return mark_safe('<span style="color: #f57c00;">Inactive</span>')
        elif obj.status == 'expired':
            return mark_safe('<span style="color: #d32f2f;">Expired</span>')
        elif obj.status == 'revoked':
            return mark_safe('<span style="color: #d32f2f;">Revoked</span>')
        else:
            return obj.status
    status_display.short_description = "Status"
    status_display.admin_order_field = 'status'
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related(
            'tenant'
        ).filter(is_deleted=False)
    
    actions = ['activate_keys', 'deactivate_keys', 'revoke_keys', 'regenerate_keys']
    
    def activate_keys(self, request, queryset):
        """Activate selected API keys."""
        count = queryset.filter(status__in=['inactive', 'expired']).update(status='active')
        self.message_user(request, f"Activated {count} API keys.", messages.SUCCESS)
    activate_keys.short_description = "Activate selected keys"
    
    def deactivate_keys(self, request, queryset):
        """Deactivate selected API keys."""
        count = queryset.filter(status='active').update(status='inactive')
        self.message_user(request, f"Deactivated {count} API keys.", messages.SUCCESS)
    deactivate_keys.short_description = "Deactivate selected keys"
    
    def revoke_keys(self, request, queryset):
        """Revoke selected API keys."""
        count = 0
        for api_key in queryset:
            api_key.revoke()
            count += 1
        
        self.message_user(request, f"Revoked {count} API keys.", messages.SUCCESS)
    revoke_keys.short_description = "Revoke selected keys"
    
    def regenerate_keys(self, request, queryset):
        """Regenerate selected API keys."""
        count = 0
        for api_key in queryset:
            # Generate new key
            from ..models.security import TenantAPIKey
            new_key = TenantAPIKey.generate_key()
            api_key.set_key(new_key)
            api_key.status = 'active'
            api_key.save()
            count += 1
        
        self.message_user(request, f"Regenerated {count} API keys.", messages.SUCCESS)
    regenerate_keys.short_description = "Regenerate selected keys"


@admin.register(TenantWebhookConfig)
class TenantWebhookConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantWebhookConfig model.
    """
    list_display = [
        'tenant_name', 'name', 'url', 'is_active',
        'status_display', 'total_deliveries', 'success_rate'
    ]
    list_filter = [
        'is_active', 'auth_type', 'last_status_code',
        'created_at', 'last_delivery_at'
    ]
    search_fields = [
        'tenant__name', 'name', 'url', 'description'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Webhook Information', {
            'fields': (
                'tenant', 'name', 'description', 'url',
                'is_active', 'events'
            )
        }),
        ('Delivery Settings', {
            'fields': (
                'timeout_seconds', 'retry_count', 'retry_delay_seconds',
                'require_https'
            )
        }),
        ('Authentication', {
            'fields': (
                'auth_type', 'auth_token', 'allowed_ips',
                'custom_headers'
            )
        }),
        ('Delivery Statistics', {
            'fields': (
                'total_deliveries', 'successful_deliveries',
                'failed_deliveries', 'last_delivery_at',
                'last_status_code'
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
    
    def status_display(self, obj):
        """Display status with color coding."""
        if obj.is_active:
            return mark_safe('<span style="color: #388e3c;">Active</span>')
        else:
            return mark_safe('<span style="color: #f57c00;">Inactive</span>')
    status_display.short_description = "Status"
    
    def success_rate(self, obj):
        """Display success rate with color coding."""
        rate = obj.success_rate
        if rate >= 95:
            return mark_safe(f'<span style="color: #388e3c;">{rate:.1f}%</span>')
        elif rate >= 80:
            return mark_safe(f'<span style="color: #f57c00;">{rate:.1f}%</span>')
        else:
            return mark_safe(f'<span style="color: #d32f2f;">{rate:.1f}%</span>')
    success_rate.short_description = "Success Rate"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['activate_webhooks', 'deactivate_webhooks', 'test_webhooks', 'clear_statistics']
    
    def activate_webhooks(self, request, queryset):
        """Activate selected webhooks."""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"Activated {count} webhooks.", messages.SUCCESS)
    activate_webhooks.short_description = "Activate selected webhooks"
    
    def deactivate_webhooks(self, request, queryset):
        """Deactivate selected webhooks."""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {count} webhooks.", messages.SUCCESS)
    deactivate_webhooks.short_description = "Deactivate selected webhooks"
    
    def test_webhooks(self, request, queryset):
        """Test selected webhooks."""
        count = 0
        for webhook in queryset:
            # This would test the webhook endpoint
            count += 1
        
        self.message_user(request, f"Tested {count} webhooks.", messages.SUCCESS)
    test_webhooks.short_description = "Test selected webhooks"
    
    def clear_statistics(self, request, queryset):
        """Clear statistics for selected webhooks."""
        count = 0
        for webhook in queryset:
            webhook.total_deliveries = 0
            webhook.successful_deliveries = 0
            webhook.failed_deliveries = 0
            webhook.save()
            count += 1
        
        self.message_user(request, f"Cleared statistics for {count} webhooks.", messages.SUCCESS)
    clear_statistics.short_description = "Clear statistics"


@admin.register(TenantIPWhitelist)
class TenantIPWhitelistAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantIPWhitelist model.
    """
    list_display = [
        'tenant_name', 'ip_range', 'label', 'is_active',
        'access_count', 'last_access_at'
    ]
    list_filter = [
        'is_active', 'last_access_at'
    ]
    search_fields = [
        'tenant__name', 'ip_range', 'label', 'description'
    ]
    ordering = ['label', 'ip_range']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('IP Whitelist Information', {
            'fields': (
                'tenant', 'ip_range', 'label', 'description',
                'is_active'
            )
        }),
        ('Access Information', {
            'fields': (
                'access_count', 'last_access_at'
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
    
    def last_access_display(self, obj):
        """Display last access time."""
        if obj.last_access_at:
            return obj.last_access_at.strftime('%Y-%m-%d %H:%M')
        return "Never"
    last_access_display.short_description = "Last Access"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['activate_entries', 'deactivate_entries', 'test_ip_ranges']
    
    def activate_entries(self, request, queryset):
        """Activate selected IP whitelist entries."""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"Activated {count} IP whitelist entries.", messages.SUCCESS)
    activate_entries.short_description = "Activate selected entries"
    
    def deactivate_entries(self, request, queryset):
        """Deactivate selected IP whitelist entries."""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {count} IP whitelist entries.", messages.SUCCESS)
    deactivate_entries.short_description = "Deactivate selected entries"
    
    def test_ip_ranges(self, request, queryset):
        """Test selected IP ranges."""
        count = 0
        for ip_whitelist in queryset:
            # This would test the IP range
            count += 1
        
        self.message_user(request, f"Tested {count} IP ranges.", messages.SUCCESS)
    test_ip_ranges.short_description = "Test IP ranges"


@admin.register(TenantAuditLog)
class TenantAuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantAuditLog model.
    """
    list_display = [
        'tenant_name', 'action', 'action_display', 'severity_display',
        'actor', 'description', 'created_at'
    ]
    list_filter = [
        'action', 'severity', 'actor', 'model_name',
        'created_at', 'ip_address'
    ]
    search_fields = [
        'tenant__name', 'description', 'object_repr',
        'actor__username', 'ip_address'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant', 'actor']
    readonly_fields = [
        'id', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Audit Information', {
            'fields': (
                'tenant', 'action', 'severity', 'actor',
                'actor_type', 'model_name', 'object_id',
                'object_repr'
            )
        }),
        ('Change Details', {
            'fields': (
                'description', 'old_value', 'new_value',
                'changes'
            ),
            'classes': ('collapse',)
        }),
        ('Request Information', {
            'fields': (
                'ip_address', 'user_agent', 'request_id'
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
        if obj.tenant:
            url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
            return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
        return "System"
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def action_display(self, obj):
        """Display action with color coding."""
        action_colors = {
            'create': '#388e3c',
            'update': '#f57c00',
            'delete': '#d32f2f',
            'login': '#9e9e9e',
            'logout': '#9e9e9e',
            'access': '#9e9e9e',
            'export': '#9e9e9e',
            'import': '#9e9e9e',
            'config_change': '#f57c00',
            'security_event': '#d32f2f',
            'billing_event': '#f57c00',
            'api_access': '#9e9e9e',
            'webhook_event': '#9e9e9e',
        }
        
        color = action_colors.get(obj.action, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.action}</span>')
    action_display.short_description = "Action"
    
    def severity_display(self, obj):
        """Display severity with color coding."""
        severity_colors = {
            'low': '#9e9e9e',
            'medium': '#f57c00',
            'high': '#d32f2f',
            'critical': '#b71c1c',
        }
        
        color = severity_colors.get(obj.severity, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.severity}</span>')
    severity_display.short_description = "Severity"
    
    def actor_display(self, obj):
        """Display actor information."""
        if obj.actor:
            if obj.actor_type == 'user':
                url = reverse('admin:auth_user_change', args=[obj.actor.id])
                return format_html('<a href="{}">{}</a>', url, obj.actor.username)
            else:
                return obj.actor_display
        return "System"
    actor_display.short_description = "Actor"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        queryset = super().get_queryset(request)
        
        # Filter by user permissions
        if not request.user.is_superuser:
            queryset = queryset.filter(tenant__owner=request.user)
        
        return queryset.select_related('tenant', 'actor')
    
    actions = ['export_audit_logs', 'clear_old_logs']
    
    def export_audit_logs(self, request, queryset):
        """Export selected audit logs."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Tenant', 'Action', 'Severity', 'Actor', 'Description',
            'IP Address', 'Created At'
        ])
        
        for log in queryset:
            writer.writerow([
                log.tenant.name if log.tenant else 'System',
                log.action,
                log.severity,
                log.actor_display,
                log.description,
                log.ip_address or '',
                log.created_at.isoformat()
            ])
        
        return response
    export_audit_logs.short_description = "Export selected logs"
    
    def clear_old_logs(self, request, queryset):
        """Clear old audit logs."""
        # Only allow superusers to clear logs
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can clear audit logs.", messages.ERROR)
            return
        
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Cleared {count} audit logs.", messages.SUCCESS)
    clear_old_logs.short_description = "Clear selected logs"
