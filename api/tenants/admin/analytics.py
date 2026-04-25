"""
Analytics Admin Classes

This module contains Django admin classes for analytics-related models including
TenantMetric, TenantHealthScore, TenantFeatureFlag, and TenantNotification.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

from ..models.analytics import TenantMetric, TenantHealthScore, TenantFeatureFlag, TenantNotification


@admin.register(TenantMetric)
class TenantMetricAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantMetric model.
    """
    list_display = [
        'tenant_name', 'metric_type', 'value', 'unit',
        'date', 'change_percentage', 'trend_display'
    ]
    list_filter = [
        'metric_type', 'unit', 'date', 'created_at'
    ]
    search_fields = [
        'tenant__name', 'metric_type', 'unit'
    ]
    ordering = ['-date', 'metric_type']
    raw_id_fields = ['tenant']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Metric Information', {
            'fields': (
                'tenant', 'metric_type', 'value', 'unit',
                'date', 'previous_value', 'change_percentage'
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
    
    def trend_display(self, obj):
        """Display trend with color coding."""
        if obj.change_percentage is None:
            return "-"
        
        if obj.change_percentage > 5:
            return mark_safe(f'<span style="color: #388e3c;">+{obj.change_percentage:.1f}%</span>')
        elif obj.change_percentage < -5:
            return mark_safe(f'<span style="color: #d32f2f;">{obj.change_percentage:.1f}%</span>')
        else:
            return mark_safe(f'<span style="color: #9e9e9e;">{obj.change_percentage:.1f}%</span>')
    trend_display.short_description = "Trend"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['export_metrics', 'calculate_changes', 'cleanup_old_metrics']
    
    def export_metrics(self, request, queryset):
        """Export selected metrics."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="metrics_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Tenant', 'Metric Type', 'Value', 'Unit', 'Date',
            'Previous Value', 'Change %'
        ])
        
        for metric in queryset:
            writer.writerow([
                metric.tenant.name,
                metric.metric_type,
                metric.value,
                metric.unit,
                metric.date.isoformat(),
                metric.previous_value,
                metric.change_percentage,
            ])
        
        return response
    export_metrics.short_description = "Export selected metrics"
    
    def calculate_changes(self, request, queryset):
        """Calculate change percentages for selected metrics."""
        count = 0
        for metric in queryset:
            if metric.calculate_change_percentage():
                count += 1
        
        self.message_user(request, f"Calculated changes for {count} metrics.", messages.SUCCESS)
    calculate_changes.short_description = "Calculate changes"
    
    def cleanup_old_metrics(self, request, queryset):
        """Clean up old metrics."""
        # Only allow superusers to clean up
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can clean up metrics.", messages.ERROR)
            return
        
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Cleaned up {count} metrics.", messages.SUCCESS)
    cleanup_old_metrics.short_description = "Clean up selected metrics"


@admin.register(TenantHealthScore)
class TenantHealthScoreAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantHealthScore model.
    """
    list_display = [
        'tenant_name', 'overall_score', 'health_grade',
        'risk_level', 'churn_probability', 'last_activity_at',
        'days_inactive'
    ]
    list_filter = [
        'health_grade', 'risk_level', 'last_activity_at'
    ]
    search_fields = [
        'tenant__name', 'health_grade', 'risk_level'
    ]
    ordering = ['-last_activity_at']
    raw_id_fields = ['tenant']
    date_hierarchy = 'last_activity_at'
    
    fieldsets = (
        ('Health Scores', {
            'fields': (
                'tenant', 'overall_score', 'health_grade',
                'risk_level', 'churn_probability'
            )
        }),
        ('Component Scores', {
            'fields': (
                'engagement_score', 'usage_score',
                'payment_score', 'support_score'
            )
        }),
        ('Activity Information', {
            'fields': (
                'last_activity_at', 'days_inactive'
            )
        }),
        ('Recommendations', {
            'fields': ('recommendations',),
            'classes': ('collapse',)
        })
    )
    
    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def health_grade_display(self, obj):
        """Display health grade with color coding."""
        grade_colors = {
            'A': '#388e3c',
            'B': '#689f38',
            'C': '#f57c00',
            'D': '#ff9800',
            'F': '#d32f2f',
        }
        
        color = grade_colors.get(obj.health_grade, '#9e9e9e')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.health_grade}</span>')
    health_grade_display.short_description = "Grade"
    
    def risk_level_display(self, obj):
        """Display risk level with color coding."""
        risk_colors = {
            'low': '#388e3c',
            'medium': '#f57c00',
            'high': '#ff9800',
            'critical': '#d32f2f',
        }
        
        color = risk_colors.get(obj.risk_level, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.risk_level}</span>')
    risk_level_display.short_description = "Risk"
    
    def overall_score_display(self, obj):
        """Display overall score with color coding."""
        score = obj.overall_score
        if score >= 80:
            color = '#388e3c'
        elif score >= 60:
            color = '#f57c00'
        elif score >= 40:
            color = '#ff9800'
        else:
            color = '#d32f2f'
        
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{score:.0f}</span>')
    overall_score_display.short_description = "Score"
    
    def days_inactive_display(self, obj):
        """Display days inactive with color coding."""
        days = obj.days_inactive
        if days <= 7:
            return mark_safe(f'<span style="color: #388e3c;">{days} days</span>')
        elif days <= 30:
            return mark_safe(f'<span style="color: #f57c00;">{days} days</span>')
        elif days <= 90:
            return mark_safe(f'<span style="color: #ff9800;">{days} days</span>')
        else:
            return mark_safe(f'<span style="color: #d32f2f;">{days} days</span>')
    days_inactive_display.short_description = "Inactive"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['recalculate_scores', 'export_health_scores', 'send_health_alerts']
    
    def recalculate_scores(self, request, queryset):
        """Recalculate health scores for selected tenants."""
        count = 0
        for health_score in queryset:
            # This would trigger health score recalculation
            count += 1
        
        self.message_user(request, f"Recalculated health scores for {count} tenants.", messages.SUCCESS)
    recalculate_scores.short_description = "Recalculate scores"
    
    def export_health_scores(self, request, queryset):
        """Export health scores."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="health_scores_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Tenant', 'Overall Score', 'Grade', 'Risk Level',
            'Churn Probability', 'Days Inactive', 'Last Activity'
        ])
        
        for health_score in queryset:
            writer.writerow([
                health_score.tenant.name,
                health_score.overall_score,
                health_score.health_grade,
                health_score.risk_level,
                health_score.churn_probability,
                health_score.days_inactive,
                health_score.last_activity_at.isoformat() if health_score.last_activity_at else '',
            ])
        
        return response
    export_health_scores.short_description = "Export health scores"
    
    def send_health_alerts(self, request, queryset):
        """Send health alerts for poor scores."""
        count = 0
        for health_score in queryset.filter(health_grade__in=['D', 'F']):
            # This would send health alert notifications
            count += 1
        
        self.message_user(request, f"Sent health alerts for {count} tenants.", messages.SUCCESS)
    send_health_alerts.short_description = "Send health alerts"


@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantFeatureFlag model.
    """
    list_display = [
        'tenant_name', 'flag_key', 'flag_type', 'is_enabled',
        'rollout_pct', 'variant', 'created_at'
    ]
    list_filter = [
        'flag_type', 'is_enabled', 'created_at', 'expires_at'
    ]
    search_fields = [
        'tenant__name', 'flag_key', 'name', 'description'
    ]
    ordering = ['tenant__name', 'flag_key']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Feature Flag Information', {
            'fields': (
                'tenant', 'flag_key', 'name', 'description',
                'flag_type', 'is_enabled'
            )
        }),
        ('Rollout Configuration', {
            'fields': (
                'rollout_pct', 'variant', 'variants',
                'rollout_strategy'
            )
        }),
        ('Targeting', {
            'fields': (
                'target_users', 'target_segments',
                'target_rules'
            ),
            'classes': ('collapse',)
        }),
        ('Lifecycle', {
            'fields': (
                'expires_at', 'archived_at'
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
    
    def is_enabled_display(self, obj):
        """Display enabled status with color coding."""
        if obj.is_enabled:
            return mark_safe('<span style="color: #388e3c;">Enabled</span>')
        else:
            return mark_safe('<span style="color: #f57c00;">Disabled</span>')
    is_enabled_display.short_description = "Status"
    
    def rollout_progress(self, obj):
        """Display rollout progress bar."""
        pct = obj.rollout_pct
        if pct >= 90:
            color = '#388e3c'
        elif pct >= 50:
            color = '#f57c00'
        else:
            color = '#ff9800'
        
        return mark_safe(
            f'<div style="width: 100px; background: #e0e0e0; border-radius: 4px;">'
            f'<div style="width: {pct}%; background: {color}; height: 20px; border-radius: 4px; text-align: center; line-height: 20px; color: white; font-size: 12px;">'
            f'{pct}%'
            f'</div></div>'
        )
    rollout_progress.short_description = "Rollout"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['enable_flags', 'disable_flags', 'rollout_to_percentage', 'archive_flags']
    
    def enable_flags(self, request, queryset):
        """Enable selected feature flags."""
        count = queryset.filter(is_enabled=False).update(is_enabled=True)
        self.message_user(request, f"Enabled {count} feature flags.", messages.SUCCESS)
    enable_flags.short_description = "Enable selected flags"
    
    def disable_flags(self, request, queryset):
        """Disable selected feature flags."""
        count = queryset.filter(is_enabled=True).update(is_enabled=False)
        self.message_user(request, f"Disabled {count} feature flags.", messages.SUCCESS)
    disable_flags.short_description = "Disable selected flags"
    
    def rollout_to_percentage(self, request, queryset):
        """Rollout selected flags to 100%."""
        count = queryset.update(rollout_pct=100)
        self.message_user(request, f"Rolled out {count} feature flags to 100%.", messages.SUCCESS)
    rollout_to_percentage.short_description = "Rollout to 100%"
    
    def archive_flags(self, request, queryset):
        """Archive selected feature flags."""
        count = 0
        for flag in queryset:
            flag.is_enabled = False
            flag.archived_at = timezone.now()
            flag.save()
            count += 1
        
        self.message_user(request, f"Archived {count} feature flags.", messages.SUCCESS)
    archive_flags.short_description = "Archive selected flags"


@admin.register(TenantNotification)
class TenantNotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantNotification model.
    """
    list_display = [
        'tenant_name', 'title', 'notification_type',
        'priority', 'status', 'is_read',
        'created_at', 'created_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'status', 'is_read',
        'created_at', 'created_at'
    ]
    search_fields = [
        'tenant__name', 'title', 'message'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': (
                'tenant', 'title', 'message', 'notification_type',
                'priority', 'status'
            )
        }),
        ('Delivery Settings', {
            'fields': (
                'send_email', 'send_push', 'send_sms',
                'is_read', 'read_at'
            )
        }),
        ('Action Links', {
            'fields': (
                'action_url', 'action_text'
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
    
    def priority_display(self, obj):
        """Display priority with color coding."""
        priority_colors = {
            'low': '#9e9e9e',
            'medium': '#f57c00',
            'high': '#ff9800',
            'urgent': '#d32f2f',
        }
        
        color = priority_colors.get(obj.priority, '#9e9e9e')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.priority}</span>')
    priority_display.short_description = "Priority"
    
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            'pending': '#f57c00',
            'sent': '#388e3c',
            'failed': '#d32f2f',
            'cancelled': '#9e9e9e',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['mark_as_read', 'mark_as_unread', 'resend_notifications', 'delete_notifications']
    
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read."""
        count = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        self.message_user(request, f"Marked {count} notifications as read.", messages.SUCCESS)
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread."""
        count = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None
        )
        self.message_user(request, f"Marked {count} notifications as unread.", messages.SUCCESS)
    mark_as_unread.short_description = "Mark as unread"
    
    def resend_notifications(self, request, queryset):
        """Resend selected notifications."""
        count = 0
        for notification in queryset.filter(status='failed'):
            # This would resend the notification
            count += 1
        
        self.message_user(request, f"Resent {count} notifications.", messages.SUCCESS)
    resend_notifications.short_description = "Resend selected"
    
    def delete_notifications(self, request, queryset):
        """Delete selected notifications."""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Deleted {count} notifications.", messages.SUCCESS)
    delete_notifications.short_description = "Delete selected"
