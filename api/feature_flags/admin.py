"""
Django admin configuration for Feature Flags & A/B Testing.
"""
from django.contrib import admin
from django.utils import timezone

from .models.feature_flag import FeatureFlag
from .models.flag_variant import FlagVariant
from .models.experiment import Experiment
from .models.experiment_participant import ExperimentParticipant
from .models.rollout_rule import RolloutRule
from .models.flag_analytics import FlagAnalytics


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """
    Admin configuration for FeatureFlag.
    """
    
    list_display = ['name', 'flag_type', 'status', 'rollout_percentage', 'environment', 'created_at']
    list_filter = ['status', 'flag_type', 'environment', 'created_at']
    search_fields = ['name', 'description', 'owner', 'team']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'flag_type', 'status')
        }),
        ('Configuration', {
            'fields': ('default_value', 'rollout_percentage', 'targeting_rules')
        }),
        ('Organization', {
            'fields': ('owner', 'team', 'tags', 'environment')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_flags', 'pause_flags', 'archive_flags']
    
    def activate_flags(self, request, queryset):
        """Activate selected flags."""
        count = queryset.update(status=FeatureFlag.Status.ACTIVE)
        self.message_user(request, f'{count} flag(s) activated successfully.')
    
    activate_flags.short_description = 'Activate selected flags'
    
    def pause_flags(self, request, queryset):
        """Pause selected flags."""
        count = queryset.update(status=FeatureFlag.Status.PAUSED)
        self.message_user(request, f'{count} flag(s) paused successfully.')
    
    pause_flags.short_description = 'Pause selected flags'
    
    def archive_flags(self, request, queryset):
        """Archive selected flags."""
        count = queryset.update(status=FeatureFlag.Status.ARCHIVED)
        self.message_user(request, f'{count} flag(s) archived successfully.')
    
    archive_flags.short_description = 'Archive selected flags'


@admin.register(FlagVariant)
class FlagVariantAdmin(admin.ModelAdmin):
    """
    Admin configuration for FlagVariant.
    """
    
    list_display = ['name', 'flag', 'weight', 'is_control', 'is_active', 'created_at']
    list_filter = ['is_control', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'flag__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('flag', 'name', 'description')
        }),
        ('Configuration', {
            'fields': ('value', 'weight', 'is_control', 'is_active')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    """
    Admin configuration for Experiment.
    """
    
    list_display = ['name', 'flag', 'status', 'start_date', 'end_date', 'owner', 'created_at']
    list_filter = ['status', 'start_date', 'end_date', 'created_at']
    search_fields = ['name', 'description', 'owner', 'team']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'flag', 'status')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date')
        }),
        ('Configuration', {
            'fields': ('target_audience', 'success_metrics', 'min_sample_size', 'significance_threshold')
        }),
        ('Organization', {
            'fields': ('owner', 'team')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['start_experiments', 'pause_experiments', 'complete_experiments']
    
    def start_experiments(self, request, queryset):
        """Start selected experiments."""
        count = queryset.filter(status=Experiment.Status.DRAFT).update(status=Experiment.Status.RUNNING)
        self.message_user(request, f'{count} experiment(s) started successfully.')
    
    start_experiments.short_description = 'Start selected experiments'
    
    def pause_experiments(self, request, queryset):
        """Pause selected experiments."""
        count = queryset.update(status=Experiment.Status.PAUSED)
        self.message_user(request, f'{count} experiment(s) paused successfully.')
    
    pause_experiments.short_description = 'Pause selected experiments'
    
    def complete_experiments(self, request, queryset):
        """Complete selected experiments."""
        count = queryset.update(status=Experiment.Status.COMPLETED)
        self.message_user(request, f'{count} experiment(s) completed successfully.')
    
    complete_experiments.short_description = 'Complete selected experiments'


@admin.register(ExperimentParticipant)
class ExperimentParticipantAdmin(admin.ModelAdmin):
    """
    Admin configuration for ExperimentParticipant.
    """
    
    list_display = ['experiment', 'variant', 'user_id', 'converted', 'converted_at', 'created_at']
    list_filter = ['converted', 'created_at']
    search_fields = ['user_id', 'session_id', 'experiment__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('experiment', 'variant', 'user_id', 'session_id')
        }),
        ('Conversion', {
            'fields': ('converted', 'converted_at')
        }),
        ('Context', {
            'fields': ('context',)
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(RolloutRule)
class RolloutRuleAdmin(admin.ModelAdmin):
    """
    Admin configuration for RolloutRule.
    """
    
    list_display = ['flag', 'rule_type', 'field', 'operator', 'priority', 'is_active', 'created_at']
    list_filter = ['rule_type', 'operator', 'is_active', 'created_at']
    search_fields = ['flag__name', 'field', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('flag', 'rule_type', 'description')
        }),
        ('Rule Configuration', {
            'fields': ('field', 'operator', 'value', 'priority', 'is_active')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(FlagAnalytics)
class FlagAnalyticsAdmin(admin.ModelAdmin):
    """
    Admin configuration for FlagAnalytics.
    """
    
    list_display = ['flag', 'variant', 'date', 'hour', 'evaluation_count', 'enabled_count', 'unique_users', 'environment']
    list_filter = ['date', 'environment']
    search_fields = ['flag__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('flag', 'variant', 'date', 'hour', 'environment')
        }),
        ('Metrics', {
            'fields': ('evaluation_count', 'enabled_count', 'disabled_count', 'unique_users', 'conversion_count')
        }),
        ('Additional Metrics', {
            'fields': ('metrics',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


# ============================================================
# NEW — admin registrations for production-readiness additions
# ============================================================
from .models.permissions import Role, Permission, UserRole
from .models.audit import AuditLog
from .models.approval import FlagChangeRequest
from .models.versioning import FeatureFlagVersion
from .models.scheduling import ScheduledChange
from .models.notification import NotificationPreference
from .models.organization import Organization, OrganizationMember, Team


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    filter_horizontal = ['roles']


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    list_filter = ['role']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only by design: audit entries are system-generated only."""
    list_display = ['flag_name_snapshot', 'action', 'user', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['flag_name_snapshot']
    readonly_fields = ['user', 'flag', 'flag_name_snapshot', 'action', 'old_values', 'new_values', 'timestamp', 'ip_address']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(FlagChangeRequest)
class FlagChangeRequestAdmin(admin.ModelAdmin):
    list_display = ['flag', 'status', 'requested_by', 'reviewed_by', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FeatureFlagVersion)
class FeatureFlagVersionAdmin(admin.ModelAdmin):
    list_display = ['flag', 'version_number', 'created_by', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['flag', 'version_number', 'config', 'created_by', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(ScheduledChange)
class ScheduledChangeAdmin(admin.ModelAdmin):
    list_display = ['flag', 'change_type', 'scheduled_for', 'executed']
    list_filter = ['change_type', 'executed']


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'notify_email', 'notify_slack']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'owner', 'created_at']
    search_fields = ['name', 'slug']


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['organization', 'user', 'role']
    list_filter = ['role']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization']
    filter_horizontal = ['members']
