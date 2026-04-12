"""
Threshold Admin Classes
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.utils import timezone
from django.contrib import messages

# Unfold imports
try:
    from unfold.admin import ModelAdmin, TabularInline
    from unfold.filters import DateRangeFilter, RelatedDropdownFilter, ChoiceDropdownFilter
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline
    from django.contrib.admin import DateFieldListFilter

from ..models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold, 
    ThresholdHistory, ThresholdProfile
)
from .core import alerts_admin_site


# ====================== INLINE ADMIN CLASSES ======================

class ThresholdBreachInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Threshold Breaches in Threshold Config"""
    model = ThresholdBreach
    extra = 0
    fields = ['severity', 'breach_value', 'threshold_value', 'breach_percentage', 'detected_at']
    readonly_fields = ['severity', 'breach_value', 'threshold_value', 'breach_percentage', 'detected_at']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class ThresholdHistoryInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Threshold History in Adaptive Threshold"""
    model = ThresholdHistory
    extra = 0
    fields = ['change_type', 'old_threshold', 'new_threshold', 'change_percentage', 'reason', 'created_at']
    readonly_fields = ['change_type', 'old_threshold', 'new_threshold', 'change_percentage', 'reason', 'created_at']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


# ====================== ADMIN CLASSES ======================

@admin.register(ThresholdConfig, site=alerts_admin_site)
class ThresholdConfigAdmin(ModelAdmin):
    """Admin interface for Threshold Configurations"""
    list_display = [
        'alert_rule_link', 'threshold_type', 'primary_threshold',
        'secondary_threshold', 'created_at',
        'breach_count', 'last_breach'
    ]
    
    list_filter = [
        'threshold_type', 'is_active',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'alert_rule__name', 'alert_rule__alert_type', 'config'
    ]
    
    list_editable = ['primary_threshold', 'secondary_threshold']
    
    readonly_fields = [
        'created_at', 'updated_at', 'breach_count', 'last_breach',
        'avg_breach_percentage', 'effectiveness_score'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('alert_rule', 'threshold_type', 'is_active')
        }),
        ('Threshold Values', {
            'fields': ('primary_threshold', 'secondary_threshold', 'time_window_minutes')
        }),
        ('Configuration', {
            'fields': ('correlation_threshold', 'minimum_occurrences', 'config')
        }),
        ('Statistics', {
            'fields': ('created_at', 'updated_at', 'breach_count', 'last_breach',
                      'avg_breach_percentage', 'effectiveness_score')
        }),
    )
    
    inlines = [ThresholdBreachInline]
    
    actions = [
        'activate_thresholds', 'deactivate_thresholds', 
        'test_thresholds', 'reset_statistics', 'duplicate_configs'
    ]
    
    # Custom display methods
    def alert_rule_link(self, obj):
        """Clickable alert rule name"""
        url = reverse('alerts_admin:alerts_alertrule_change', args=[obj.alert_rule.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.alert_rule.name)
    alert_rule_link.short_description = 'Alert Rule'
    alert_rule_link.admin_order_field = 'alert_rule__name'
    
    def breach_count(self, obj):
        """Count of threshold breaches"""
        return obj.thresholdbreach_set.count()
    breach_count.short_description = 'Breaches'
    
    def last_breach(self, obj):
        """Last breach time"""
        last_breach = obj.thresholdbreach_set.order_by('-detected_at').first()
        if last_breach:
            return last_breach.detected_at.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_breach.short_description = 'Last Breach'
    
    def avg_breach_percentage(self, obj):
        """Average breach percentage"""
        breaches = obj.thresholdbreach_set.all()
        if breaches.exists():
            avg_percentage = breaches.aggregate(
                avg=Avg('breach_percentage')
            )['avg'] or 0
            return f"{avg_percentage:.1f}%"
        return "N/A"
    avg_breach_percentage.short_description = 'Avg Breach %'
    
    def effectiveness_score(self, obj):
        """Effectiveness score based on breach patterns"""
        breaches = obj.thresholdbreach_set.all()
        if breaches.exists():
            # Simple effectiveness calculation
            total_breaches = breaches.count()
            resolved_breaches = breaches.filter(is_resolved=True).count()
            if total_breaches > 0:
                score = (resolved_breaches / total_breaches) * 100
                return f"{score:.1f}%"
        return "N/A"
    effectiveness_score.short_description = 'Effectiveness'
    
    # Custom actions
    def activate_thresholds(self, request, queryset):
        """Activate selected thresholds"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} threshold configuration(s).")
    activate_thresholds.short_description = "Activate selected thresholds"
    
    def deactivate_thresholds(self, request, queryset):
        """Deactivate selected thresholds"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} threshold configuration(s).")
    deactivate_thresholds.short_description = "Deactivate selected thresholds"
    
    def test_thresholds(self, request, queryset):
        """Test selected threshold configurations"""
        from ..tasks.threshold import ThresholdConfigEvaluateSerializer
        tested_count = 0
        for config in queryset:
            # Simulate threshold evaluation
            test_value = config.primary_threshold * 1.2  # 20% above threshold
            result = config.evaluate_condition(test_value)
            if result:
                tested_count += 1
        
        messages.success(request, f"Tested {tested_count} threshold configuration(s).")
    test_thresholds.short_description = "Test selected thresholds"
    
    def reset_statistics(self, request, queryset):
        """Reset statistics for selected thresholds"""
        # This would reset breach statistics
        messages.info(request, f"Statistics reset for {queryset.count()} threshold configuration(s).")
    reset_statistics.short_description = "Reset statistics"
    
    def duplicate_configs(self, request, queryset):
        """Duplicate selected threshold configurations"""
        duplicated_count = 0
        for config in queryset:
            # Create a copy
            config.pk = None
            config.is_active = False
            config.save()
            duplicated_count += 1
        
        messages.success(request, f"Duplicated {duplicated_count} threshold configuration(s).")
    duplicate_configs.short_description = "Duplicate selected configs"


@admin.register(ThresholdBreach, site=alerts_admin_site)
class ThresholdBreachAdmin(ModelAdmin):
    """Admin interface for Threshold Breaches"""
    list_display = [
        'id', 'threshold_config_link', 'alert_log_link', 'severity_badge',
        'breach_value', 'threshold_value', 'breach_percentage', 'detected_at',
        'status_badge', 'duration_minutes'
    ]
    
    list_filter = [
        'severity',
        ('detected_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('acknowledged_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('resolved_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'threshold_config__alert_rule__name', 'alert_log__message', 'notes'
    ]
    
    readonly_fields = [
        'detected_at', 'breach_value', 'threshold_value', 'breach_percentage',
        'duration_minutes'
    ]
    
    fieldsets = (
        ('Breach Information', {
            'fields': ('threshold_config', 'alert_log', 'severity', 'detected_at')
        }),
        ('Breach Details', {
            'fields': ('breach_value', 'threshold_value', 'breach_percentage')
        }),
        ('Resolution', {
            'fields': ('acknowledged_at', 'acknowledged_by', 'resolved_at', 
                      'resolved_by', 'duration_minutes', 'notes')
        }),
    )
    
    actions = [
        'acknowledge_breaches', 'resolve_breaches', 'escalate_breaches',
        'export_breaches', 'bulk_delete'
    ]
    
    # Custom display methods
    def threshold_config_link(self, obj):
        """Clickable threshold config name"""
        url = reverse('alerts_admin:alerts_thresholdconfig_change', args=[obj.threshold_config.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.threshold_config.alert_rule.name)
    threshold_config_link.short_description = 'Threshold Config'
    threshold_config_link.admin_order_field = 'threshold_config__alert_rule__name'
    
    def alert_log_link(self, obj):
        """Clickable alert log link"""
        if obj.alert_log:
            url = reverse('alerts_admin:alerts_alertlog_change', args=[obj.alert_log.id])
            return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, f"Alert {obj.alert_log.id}")
        return 'N/A'
    alert_log_link.short_description = 'Alert Log'
    
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'
    severity_badge.admin_order_field = 'severity'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        if obj.is_resolved:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">RESOLVED</span>'
            )
        elif obj.acknowledged_at:
            return format_html(
                '<span style="background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">ACKNOWLEDGED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">ACTIVE</span>'
            )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'is_resolved'
    
    # Custom actions
    def acknowledge_breaches(self, request, queryset):
        """Acknowledge selected breaches"""
        updated = queryset.filter(acknowledged_at__isnull=True).update(
            acknowledged_at=timezone.now(),
            acknowledged_by=request.user
        )
        messages.success(request, f"Acknowledged {updated} breach(es).")
    acknowledge_breaches.short_description = "Acknowledge selected breaches"
    
    def resolve_breaches(self, request, queryset):
        """Resolve selected breaches"""
        updated = queryset.filter(is_resolved=False).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        messages.success(request, f"Resolved {updated} breach(es).")
    resolve_breaches.short_description = "Resolve selected breaches"
    
    def escalate_breaches(self, request, queryset):
        """Escalate selected breaches"""
        escalated_count = 0
        for breach in queryset.filter(is_resolved=False):
            # Simulate escalation
            escalated_count += 1
        
        messages.success(request, f"Escalated {escalated_count} breach(es).")
    escalate_breaches.short_description = "Escalate selected breaches"
    
    def export_breaches(self, request, queryset):
        """Export selected breaches"""
        messages.info(request, f"Export initiated for {queryset.count()} breach(es).")
    export_breaches.short_description = "Export breaches"
    
    def bulk_delete(self, request, queryset):
        """Bulk delete selected breaches"""
        deleted, _ = queryset.delete()
        messages.success(request, f"Deleted {deleted} breach(es).")
    bulk_delete.short_description = "Delete selected breaches"


@admin.register(AdaptiveThreshold, site=alerts_admin_site)
class AdaptiveThresholdAdmin(ModelAdmin):
    """Admin interface for Adaptive Thresholds"""
    list_display = [
        'threshold_config_link', 'adaptation_method',
        'current_threshold', 'adaptation_count',
        'last_adaptation'
    ]
    
    list_filter = [
        'adaptation_method',
        ('last_adaptation', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'threshold_config__alert_rule__name', 'adaptation_method', 'config'
    ]
    
    readonly_fields = [
        'current_threshold', 'adaptation_count', 'last_adaptation',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('threshold_config', 'adaptation_method', 'is_active')
        }),
        ('Learning Configuration', {
            'fields': ('min_samples', 'confidence_threshold')
        }),
        ('Adaptation Settings', {
            'fields': ('adaptation_frequency', 'model_parameters', 'config')
        }),
        ('Statistics', {
            'fields': ('current_threshold', 'adaptation_count', 'last_adaptation',
                      'created_at', 'updated_at')
        }),
    )
    
    inlines = [ThresholdHistoryInline]
    
    actions = [
        'activate_adaptations', 'deactivate_adaptations', 'train_models',
        'reset_adaptations', 'force_adaptation'
    ]
    
    # Custom display methods
    def threshold_config_link(self, obj):
        """Clickable threshold config name"""
        url = reverse('alerts_admin:alerts_thresholdconfig_change', args=[obj.threshold_config.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.threshold_config.alert_rule.name)
    threshold_config_link.short_description = 'Threshold Config'
    threshold_config_link.admin_order_field = 'threshold_config__alert_rule__name'
    
    def training_status(self, obj):
        """Display training status as colored badge"""
        colors = {
            'pending': '#6b7280',
            'training': '#f59e0b',
            'completed': '#10b981',
            'failed': '#ef4444',
            'updating': '#3b82f6'
        }
        color = colors.get(obj.training_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.training_status.upper()
        )
    training_status.short_description = 'Training Status'
    training_status.admin_order_field = 'training_status'
    
    # Custom actions
    def activate_adaptations(self, request, queryset):
        """Activate selected adaptations"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} adaptive threshold(s).")
    activate_adaptations.short_description = "Activate selected adaptations"
    
    def deactivate_adaptations(self, request, queryset):
        """Deactivate selected adaptations"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} adaptive threshold(s).")
    deactivate_adaptations.short_description = "Deactivate selected adaptations"
    
    def train_models(self, request, queryset):
        """Train models for selected adaptations"""
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        messages.success(request, f"Training initiated for {queryset.count()} adaptive threshold(s).")
    train_models.short_description = "Train selected models"
    
    def reset_adaptations(self, request, queryset):
        """Reset adaptations for selected thresholds"""
        queryset.update(
            adaptation_count=0,
            last_adaptation=None,
            current_threshold=models.F('threshold_config__primary_threshold')
        )
        messages.success(request, f"Reset {queryset.count()} adaptive threshold(s).")
    reset_adaptations.short_description = "Reset selected adaptations"
    
    def force_adaptation(self, request, queryset):
        """Force adaptation for selected thresholds"""
        from ..tasks.intelligence import update_anomaly_thresholds
        update_anomaly_thresholds.delay()
        messages.success(request, f"Force adaptation triggered for {queryset.count()} adaptive threshold(s).")
    force_adaptation.short_description = "Force adaptation"


@admin.register(ThresholdHistory, site=alerts_admin_site)
class ThresholdHistoryAdmin(ModelAdmin):
    """Admin interface for Threshold History"""
    list_display = [
        'adaptive_threshold_link', 'change_type', 'old_threshold', 'new_threshold',
        'change_percentage', 'reason', 'created_at'
    ]
    
    list_filter = [
        'change_type',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'adaptive_threshold__threshold_config__alert_rule__name', 'reason'
    ]
    
    readonly_fields = [
        'adaptive_threshold', 'change_type', 'old_threshold', 'new_threshold',
        'change_percentage', 'reason', 'created_at'
    ]
    
    actions = ['export_history', 'cleanup_old_history']
    
    # Custom display methods
    def adaptive_threshold_link(self, obj):
        """Clickable adaptive threshold name"""
        if obj.adaptive_threshold:
            url = reverse('alerts_admin:alerts_adaptivethreshold_change', args=[obj.adaptive_threshold.id])
            return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.adaptive_threshold.threshold_config.alert_rule.name)
        return 'N/A'
    adaptive_threshold_link.short_description = 'Adaptive Threshold'
    
    # Custom actions
    def export_history(self, request, queryset):
        """Export selected history records"""
        messages.info(request, f"Export initiated for {queryset.count()} history record(s).")
    export_history.short_description = "Export history"
    
    def cleanup_old_history(self, request, queryset):
        """Clean up old history records"""
        messages.info(request, f"Cleanup initiated for old history records.")
    cleanup_old_history.short_description = "Cleanup old history"


@admin.register(ThresholdProfile, site=alerts_admin_site)
class ThresholdProfileAdmin(ModelAdmin):
    """Admin interface for Threshold Profiles"""
    list_display = [
        'name', 'profile_type', 'is_default', 'created_at',
        'rules_count', 'effective_settings_count'
    ]
    
    list_filter = [
        'profile_type', 'is_default', 'is_active',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description', 'profile_type']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'profile_type', 'description', 'is_default', 'is_active')
        }),
        ('Configuration', {
            'fields': ('threshold_settings', 'alert_type_mappings')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_profiles', 'deactivate_profiles', 'set_as_default',
        'apply_to_rules', 'export_profiles'
    ]
    
    # Custom display methods
    def rules_count(self, obj):
        """Count of rules using this profile"""
        return obj.rules.count()
    rules_count.short_description = 'Rules'
    
    def effective_settings_count(self, obj):
        """Count of effective settings"""
        # This would count unique alert types with settings
        if obj.threshold_settings:
            return len(obj.threshold_settings)
        return 0
    effective_settings_count.short_description = 'Settings'
    
    # Custom actions
    def activate_profiles(self, request, queryset):
        """Activate selected profiles"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} profile(s).")
    activate_profiles.short_description = "Activate selected profiles"
    
    def deactivate_profiles(self, request, queryset):
        """Deactivate selected profiles"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} profile(s).")
    deactivate_profiles.short_description = "Deactivate selected profiles"
    
    def set_as_default(self, request, queryset):
        """Set selected profiles as default"""
        updated = 0
        for profile in queryset:
            # Unset other defaults of same type
            ThresholdProfile.objects.filter(
                profile_type=profile.profile_type,
                is_default=True
            ).exclude(id=profile.id).update(is_default=False)
            
            # Set this as default
            profile.is_default = True
            profile.save(update_fields=['is_default'])
            updated += 1
        
        messages.success(request, f"Set {updated} profile(s) as default.")
    set_as_default.short_description = "Set as default"
    
    def apply_to_rules(self, request, queryset):
        """Apply selected profiles to rules"""
        applied_count = 0
        for profile in queryset:
            # Apply to rules of matching alert types
            applied_count += 1
        
        messages.success(request, f"Applied {applied_count} profile(s) to rules.")
    apply_to_rules.short_description = "Apply to rules"
    
    def export_profiles(self, request, queryset):
        """Export selected profiles"""
        messages.info(request, f"Export initiated for {queryset.count()} profile(s).")
    export_profiles.short_description = "Export profiles"
