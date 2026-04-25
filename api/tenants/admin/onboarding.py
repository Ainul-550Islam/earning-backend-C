"""
Onboarding Admin Classes

This module contains Django admin classes for onboarding-related models including
TenantOnboarding, TenantOnboardingStep, and TenantTrialExtension.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

from ..models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension


@admin.register(TenantOnboarding)
class TenantOnboardingAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantOnboarding model.
    """
    list_display = [
        'tenant_name', 'status', 'completion_pct',
        'current_step', 'started_at', 'completed_at',
        'days_since_start'
    ]
    list_filter = [
        'status', 'completion_pct', 'started_at', 'completed_at',
        'skip_welcome', 'enable_tips', 'send_reminders'
    ]
    search_fields = [
        'tenant__name', 'tenant__slug', 'notes', 'feedback'
    ]
    ordering = ['-started_at']
    raw_id_fields = ['tenant']
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Onboarding Information', {
            'fields': (
                'tenant', 'status', 'completion_pct',
                'current_step', 'progress'
            )
        }),
        ('Timeline', {
            'fields': (
                'started_at', 'completed_at', 'last_activity_at',
                'last_reminder_sent'
            )
        }),
        ('Settings', {
            'fields': (
                'skip_welcome', 'enable_tips', 'send_reminders',
                'reminder_frequency'
            )
        }),
        ('Feedback', {
            'fields': (
                'notes', 'feedback', 'rating'
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
        status_colors = {
            'not_started': '#9e9e9e',
            'in_progress': '#f57c00',
            'completed': '#388e3c',
            'paused': '#d32f2f',
            'skipped': '#9e9e9e',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def completion_progress(self, obj):
        """Display completion progress bar."""
        pct = obj.completion_pct
        if pct >= 90:
            color = '#388e3c'
        elif pct >= 70:
            color = '#f57c00'
        elif pct >= 50:
            color = '#ff9800'
        else:
            color = '#d32f2f'
        
        return mark_safe(
            f'<div style="width: 100px; background: #e0e0e0; border-radius: 4px;">'
            f'<div style="width: {pct}%; background: {color}; height: 20px; border-radius: 4px; text-align: center; line-height: 20px; color: white; font-size: 12px;">'
            f'{pct}%'
            f'</div></div>'
        )
    completion_progress.short_description = "Progress"
    
    def days_since_start(self, obj):
        """Display days since start."""
        days = obj.days_since_start
        if days is None:
            return "-"
        
        if days >= 30:
            return mark_safe(f'<span style="color: #d32f2f;">{days} days</span>')
        elif days >= 14:
            return mark_safe(f'<span style="color: #f57c00;">{days} days</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{days} days</span>')
    days_since_start.short_description = "Days Active"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['start_onboarding', 'complete_onboarding', 'pause_onboarding', 'send_reminders']
    
    def start_onboarding(self, request, queryset):
        """Start onboarding for selected tenants."""
        count = 0
        for onboarding in queryset.filter(status='not_started'):
            onboarding.status = 'in_progress'
            onboarding.started_at = timezone.now()
            onboarding.save()
            count += 1
        
        self.message_user(request, f"Started onboarding for {count} tenants.", messages.SUCCESS)
    start_onboarding.short_description = "Start onboarding"
    
    def complete_onboarding(self, request, queryset):
        """Complete onboarding for selected tenants."""
        count = 0
        for onboarding in queryset.filter(status='in_progress'):
            onboarding.complete_onboarding()
            count += 1
        
        self.message_user(request, f"Completed onboarding for {count} tenants.", messages.SUCCESS)
    complete_onboarding.short_description = "Complete onboarding"
    
    def pause_onboarding(self, request, queryset):
        """Pause onboarding for selected tenants."""
        count = 0
        for onboarding in queryset.filter(status='in_progress'):
            onboarding.pause_onboarding()
            count += 1
        
        self.message_user(request, f"Paused onboarding for {count} tenants.", messages.SUCCESS)
    pause_onboarding.short_description = "Pause onboarding"
    
    def send_reminders(self, request, queryset):
        """Send reminders for selected onboarding."""
        count = 0
        for onboarding in queryset:
            # This would send reminder notifications
            onboarding.last_reminder_sent = timezone.now()
            onboarding.save()
            count += 1
        
        self.message_user(request, f"Sent reminders for {count} onboarding sessions.", messages.SUCCESS)
    send_reminders.short_description = "Send reminders"


@admin.register(TenantOnboardingStep)
class TenantOnboardingStepAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantOnboardingStep model.
    """
    list_display = [
        'tenant_name', 'step_key', 'step_type', 'label',
        'status', 'is_required', 'sort_order', 'time_spent_display'
    ]
    list_filter = [
        'step_type', 'status', 'is_required'
    ]
    search_fields = [
        'tenant__name', 'step_key', 'label', 'description'
    ]
    ordering = ['tenant__name', 'sort_order']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Step Information', {
            'fields': (
                'tenant', 'step_key', 'step_type', 'label',
                'description', 'status', 'is_required'
            )
        }),
        ('Progress', {
            'fields': (
                'sort_order', 'started_at', 'done_at',
                'time_spent_seconds'
            )
        }),
        ('Configuration', {
            'fields': (
                'help_text', 'video_url', 'documentation_url',
                'validation_rules'
            ),
            'classes': ('collapse',)
        }),
        ('Step Data', {
            'fields': ('step_data',),
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
        status_colors = {
            'not_started': '#9e9e9e',
            'in_progress': '#f57c00',
            'done': '#388e3c',
            'skipped': '#9e9e9e',
            'failed': '#d32f2f',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def time_spent_display(self, obj):
        """Display time spent."""
        if obj.time_spent_seconds:
            minutes = obj.time_spent_seconds // 60
            seconds = obj.time_spent_seconds % 60
            return f"{minutes}m {seconds}s"
        return "-"
    time_spent_display.short_description = "Time Spent"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['start_steps', 'complete_steps', 'skip_steps', 'reset_steps']
    
    def start_steps(self, request, queryset):
        """Start selected steps."""
        count = 0
        for step in queryset.filter(status='not_started'):
            step.start_step()
            count += 1
        
        self.message_user(request, f"Started {count} onboarding steps.", messages.SUCCESS)
    start_steps.short_description = "Start selected steps"
    
    def complete_steps(self, request, queryset):
        """Complete selected steps."""
        count = 0
        for step in queryset.filter(status__in=['not_started', 'in_progress']):
            step.status = 'done'
            step.done_at = timezone.now()
            step.save()
            count += 1
        
        self.message_user(request, f"Completed {count} onboarding steps.", messages.SUCCESS)
    complete_steps.short_description = "Complete selected steps"
    
    def skip_steps(self, request, queryset):
        """Skip selected steps."""
        count = 0
        for step in queryset.filter(status__in=['not_started', 'in_progress']):
            if step.can_skip:
                step.status = 'skipped'
                step.done_at = timezone.now()
                step.save()
                count += 1
        
        self.message_user(request, f"Skipped {count} onboarding steps.", messages.SUCCESS)
    skip_steps.short_description = "Skip selected steps"
    
    def reset_steps(self, request, queryset):
        """Reset selected steps."""
        count = 0
        for step in queryset:
            step.status = 'not_started'
            step.started_at = None
            step.done_at = None
            step.time_spent_seconds = 0
            step.step_data = {}
            step.save()
            count += 1
        
        self.message_user(request, f"Reset {count} onboarding steps.", messages.SUCCESS)
    reset_steps.short_description = "Reset selected steps"


@admin.register(TenantTrialExtension)
class TenantTrialExtensionAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantTrialExtension model.
    """
    list_display = [
        'tenant_name', 'days_extended', 'reason',
        'status', 'created_at', 'new_trial_end'
    ]
    list_filter = [
        'status', 'reason', 'created_at', 'approved_at'
    ]
    search_fields = [
        'tenant__name', 'reason_details', 'notes', 'rejection_reason'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['tenant', 'approved_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Extension Information', {
            'fields': (
                'tenant', 'days_extended', 'reason',
                'reason_details', 'status'
            )
        }),
        ('Trial Dates', {
            'fields': (
                'original_trial_end', 'new_trial_end',
                'days_until_new_trial_end'
            )
        }),
        ('Approval', {
            'fields': (
                'approved_by', 'approved_at', 'notes',
                'rejection_reason'
            )
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
        status_colors = {
            'requested': '#f57c00',
            'approved': '#388e3c',
            'rejected': '#d32f2f',
            'cancelled': '#9e9e9e',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color};">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def days_until_new_trial_end(self, obj):
        """Display days until new trial end."""
        days = obj.days_until_new_trial_end
        if days is None:
            return "-"
        
        if days <= 3:
            return mark_safe(f'<span style="color: #d32f2f;">{days} days</span>')
        elif days <= 7:
            return mark_safe(f'<span style="color: #f57c00;">{days} days</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{days} days</span>')
    days_until_new_trial_end.short_description = "Days Until End"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant', 'approved_by')
    
    actions = ['approve_extensions', 'reject_extensions', 'cancel_extensions']
    
    def approve_extensions(self, request, queryset):
        """Approve selected trial extensions."""
        count = 0
        for extension in queryset.filter(status='requested'):
            extension.approve(request.user)
            count += 1
        
        self.message_user(request, f"Approved {count} trial extensions.", messages.SUCCESS)
    approve_extensions.short_description = "Approve selected extensions"
    
    def reject_extensions(self, request, queryset):
        """Reject selected trial extensions."""
        count = 0
        for extension in queryset.filter(status='requested'):
            extension.reject(request.user, "Admin rejection")
            count += 1
        
        self.message_user(request, f"Rejected {count} trial extensions.", messages.SUCCESS)
    reject_extensions.short_description = "Reject selected extensions"
    
    def cancel_extensions(self, request, queryset):
        """Cancel selected trial extensions."""
        count = 0
        for extension in queryset.filter(status__in=['requested', 'approved']):
            extension.cancel()
            count += 1
        
        self.message_user(request, f"Cancelled {count} trial extensions.", messages.SUCCESS)
    cancel_extensions.short_description = "Cancel selected extensions"
