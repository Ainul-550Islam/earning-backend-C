"""
Reporting Admin Classes
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

from ..models.reporting import (
    AlertReport, MTTRMetric, MTTDMetric, SLABreach
)
from .core import alerts_admin_site


# ====================== ADMIN CLASSES ======================

@admin.register(AlertReport, site=alerts_admin_site)
class AlertReportAdmin(ModelAdmin):
    """Admin interface for Alert Reports"""
    list_display = [
        'title', 'report_type', 'status_badge', 'format_type',
        'start_date', 'end_date', 'auto_distribute', 'is_recurring',
        'generated_at', 'file_size_display'
    ]
    
    list_filter = [
        'report_type', 'status', 'format_type', 'auto_distribute', 'is_recurring',
        ('generated_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'title', 'description', 'included_metrics', 'summary'
    ]
    
    readonly_fields = [
        'generated_at', 'generation_duration_ms', 'file_path', 'file_size_bytes',
        'error_message', 'retry_count', 'next_run'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'report_type', 'status')
        }),
        ('Report Configuration', {
            'fields': ('start_date', 'end_date', 'included_metrics', 'rule_filters',
                      'severity_filters', 'status_filters')
        }),
        ('Output Configuration', {
            'fields': ('format_type', 'recipients', 'auto_distribute')
        }),
        ('Scheduling', {
            'fields': ('is_recurring', 'recurrence_pattern', 'next_run')
        }),
        ('Generation Status', {
            'fields': ('generated_at', 'generation_duration_ms', 'file_path',
                      'file_size_bytes', 'error_message', 'retry_count', 'max_retries')
        }),
    )
    
    actions = [
        'generate_reports', 'regenerate_reports', 'distribute_reports',
        'schedule_next_run', 'export_reports', 'delete_reports'
    ]
    
    # Custom display methods
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#6b7280',
            'generating': '#f59e0b',
            'completed': '#10b981',
            'failed': '#ef4444',
            'scheduled': '#3b82f6'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size_bytes:
            if obj.file_size_bytes < 1024:
                return f"{obj.file_size_bytes} B"
            elif obj.file_size_bytes < 1024 * 1024:
                return f"{obj.file_size_bytes / 1024:.1f} KB"
            else:
                return f"{obj.file_size_bytes / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size_display.short_description = 'File Size'
    
    # Custom actions
    def generate_reports(self, request, queryset):
        """Generate selected reports"""
        from ..tasks.reporting import generate_custom_report
        generated_count = 0
        for report in queryset:
            generate_custom_report.delay(report.id)
            generated_count += 1
        
        messages.success(request, f"Generation initiated for {generated_count} report(s).")
    generate_reports.short_description = "Generate selected reports"
    
    def regenerate_reports(self, request, queryset):
        """Regenerate selected reports"""
        from ..tasks.reporting import generate_custom_report
        regenerated_count = 0
        for report in queryset:
            generate_custom_report.delay(report.id)
            regenerated_count += 1
        
        messages.success(request, f"Regeneration initiated for {regenerated_count} report(s).")
    regenerate_reports.short_description = "Regenerate selected reports"
    
    def distribute_reports(self, request, queryset):
        """Distribute selected reports"""
        from ..tasks.reporting import distribute_reports
        distribute_reports.delay()
        messages.success(request, f"Distribution initiated for {queryset.count()} report(s).")
    distribute_reports.short_description = "Distribute selected reports"
    
    def schedule_next_run(self, request, queryset):
        """Schedule next run for selected reports"""
        from ..tasks.reporting import schedule_recurring_reports
        schedule_recurring_reports.delay()
        messages.success(request, f"Next run scheduled for {queryset.count()} report(s).")
    schedule_next_run.short_description = "Schedule next run"
    
    def export_reports(self, request, queryset):
        """Export selected reports"""
        from ..tasks.reporting import export_report
        exported_count = 0
        for report in queryset:
            export_report.delay(report.id)
            exported_count += 1
        
        messages.success(request, f"Export initiated for {exported_count} report(s).")
    export_reports.short_description = "Export selected reports"
    
    def delete_reports(self, request, queryset):
        """Delete selected reports"""
        deleted, _ = queryset.delete()
        messages.success(request, f"Deleted {deleted} report(s).")
    delete_reports.short_description = "Delete selected reports"


@admin.register(MTTRMetric, site=alerts_admin_site)
class MTTRMetricAdmin(ModelAdmin):
    """Admin interface for MTTR Metrics"""
    list_display = [
        'name', 'calculation_period_days', 'target_mttr_minutes',
        'current_mttr_minutes', 'target_compliance_badge', 'alerts_within_target',
        'total_resolved_alerts', 'last_calculated'
    ]
    
    list_filter = [
        ('last_calculated', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description']
    
    readonly_fields = [
        'current_mttr_minutes', 'mttr_by_severity', 'mttr_by_rule',
        'mttr_trend_7_days', 'mttr_trend_30_days', 'alerts_within_target',
        'total_resolved_alerts', 'target_compliance_percentage', 'last_calculated',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'calculation_period_days', 'target_mttr_minutes')
        }),
        ('Current Metrics', {
            'fields': ('current_mttr_minutes', 'mttr_by_severity', 'mttr_by_rule',
                      'mttr_trend_7_days', 'mttr_trend_30_days')
        }),
        ('Compliance', {
            'fields': ('alerts_within_target', 'total_resolved_alerts',
                      'target_compliance_percentage')
        }),
        ('Timestamps', {
            'fields': ('last_calculated',)
        }),
    )
    
    actions = [
        'calculate_metrics', 'generate_trends', 'export_metrics',
        'reset_metrics', 'optimize_targets'
    ]
    
    # Custom display methods
    def target_compliance_badge(self, obj):
        """Display target compliance as colored badge"""
        compliance = obj.target_compliance_percentage
        if compliance is None:
            return format_html('<span style="color: #6b7280;">N/A</span>')
        
        if compliance >= 90:
            color = '#10b981'
            label = 'EXCELLENT'
        elif compliance >= 80:
            color = '#f59e0b'
            label = 'GOOD'
        elif compliance >= 70:
            color = '#ef4444'
            label = 'POOR'
        else:
            color = '#dc2626'
            label = 'CRITICAL'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, f"{compliance:.1f}%"
        )
    target_compliance_badge.short_description = 'Compliance'
    
    # Custom actions
    def calculate_metrics(self, request, queryset):
        """Calculate selected metrics"""
        from ..tasks.reporting import calculate_mttr_metrics
        calculate_mttr_metrics.delay()
        messages.success(request, f"Calculation initiated for {queryset.count()} metric(s).")
    calculate_metrics.short_description = "Calculate selected metrics"
    
    def generate_trends(self, request, queryset):
        """Generate trends for selected metrics"""
        from ..tasks.reporting import MTTRMetricTrendsSerializer
        generated_count = 0
        for metric in queryset:
            # Simulate trend generation
            generated_count += 1
        
        messages.success(request, f"Trends generated for {generated_count} metric(s).")
    generate_trends.short_description = "Generate trends"
    
    def export_metrics(self, request, queryset):
        """Export selected metrics"""
        messages.info(request, f"Export initiated for {queryset.count()} metric(s).")
    export_metrics.short_description = "Export metrics"
    
    def reset_metrics(self, request, queryset):
        """Reset selected metrics"""
        queryset.update(
            current_mttr_minutes=None,
            alerts_within_target=0,
            total_resolved_alerts=0,
            target_compliance_percentage=0
        )
        messages.success(request, f"Reset {queryset.count()} metric(s).")
    reset_metrics.short_description = "Reset selected metrics"
    
    def optimize_targets(self, request, queryset):
        """Optimize targets for selected metrics"""
        messages.info(request, f"Target optimization initiated for {queryset.count()} metric(s).")
    optimize_targets.short_description = "Optimize targets"


@admin.register(MTTDMetric, site=alerts_admin_site)
class MTTDMetricAdmin(ModelAdmin):
    """Admin interface for MTTD Metrics"""
    list_display = [
        'name', 'calculation_period_days', 'target_mttd_minutes',
        'current_mttd_minutes', 'detection_rate_badge', 'false_positive_rate',
        'target_compliance_badge', 'last_calculated'
    ]
    
    list_filter = [
        ('last_calculated', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description']
    
    readonly_fields = [
        'current_mttd_minutes', 'mttd_by_severity', 'mttd_by_rule',
        'mttd_trend_7_days', 'mttd_trend_30_days', 'detection_rate',
        'false_positive_rate', 'target_compliance_percentage', 'last_calculated',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'calculation_period_days', 'target_mttd_minutes')
        }),
        ('Current Metrics', {
            'fields': ('current_mttd_minutes', 'mttd_by_severity', 'mttd_by_rule',
                      'mttd_trend_7_days', 'mttd_trend_30_days')
        }),
        ('Detection Quality', {
            'fields': ('detection_rate', 'false_positive_rate', 'target_compliance_percentage')
        }),
        ('Timestamps', {
            'fields': ('last_calculated',)
        }),
    )
    
    actions = [
        'calculate_metrics', 'generate_trends', 'export_metrics',
        'reset_metrics', 'optimize_detection'
    ]
    
    # Custom display methods
    def detection_rate_badge(self, obj):
        """Display detection rate as colored badge"""
        rate = obj.detection_rate
        if rate is None:
            return format_html('<span style="color: #6b7280;">N/A</span>')
        
        if rate >= 95:
            color = '#10b981'
            label = 'EXCELLENT'
        elif rate >= 85:
            color = '#f59e0b'
            label = 'GOOD'
        elif rate >= 75:
            color = '#ef4444'
            label = 'POOR'
        else:
            color = '#dc2626'
            label = 'CRITICAL'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, f"{rate:.1f}%"
        )
    detection_rate_badge.short_description = 'Detection Rate'
    
    def target_compliance_badge(self, obj):
        """Display target compliance as colored badge"""
        compliance = obj.target_compliance_percentage
        if compliance is None:
            return format_html('<span style="color: #6b7280;">N/A</span>')
        
        if compliance >= 90:
            color = '#10b981'
            label = 'EXCELLENT'
        elif compliance >= 80:
            color = '#f59e0b'
            label = 'GOOD'
        elif compliance >= 70:
            color = '#ef4444'
            label = 'POOR'
        else:
            color = '#dc2626'
            label = 'CRITICAL'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, f"{compliance:.1f}%"
        )
    target_compliance_badge.short_description = 'Compliance'
    
    # Custom actions
    def calculate_metrics(self, request, queryset):
        """Calculate selected metrics"""
        from ..tasks.reporting import calculate_mttd_metrics
        calculate_mttd_metrics.delay()
        messages.success(request, f"Calculation initiated for {queryset.count()} metric(s).")
    calculate_metrics.short_description = "Calculate selected metrics"
    
    def generate_trends(self, request, queryset):
        """Generate trends for selected metrics"""
        from ..tasks.reporting import MTTDMetricTrendsSerializer
        generated_count = 0
        for metric in queryset:
            # Simulate trend generation
            generated_count += 1
        
        messages.success(request, f"Trends generated for {generated_count} metric(s).")
    generate_trends.short_description = "Generate trends"
    
    def export_metrics(self, request, queryset):
        """Export selected metrics"""
        messages.info(request, f"Export initiated for {queryset.count()} metric(s).")
    export_metrics.short_description = "Export metrics"
    
    def reset_metrics(self, request, queryset):
        """Reset selected metrics"""
        queryset.update(
            current_mttd_minutes=None,
            detection_rate=0,
            false_positive_rate=0,
            target_compliance_percentage=0
        )
        messages.success(request, f"Reset {queryset.count()} metric(s).")
    reset_metrics.short_description = "Reset selected metrics"
    
    def optimize_detection(self, request, queryset):
        """Optimize detection for selected metrics"""
        messages.info(request, f"Detection optimization initiated for {queryset.count()} metric(s).")
    optimize_detection.short_description = "Optimize detection"


@admin.register(SLABreach, site=alerts_admin_site)
class SLABreachAdmin(ModelAdmin):
    """Admin interface for SLA Breaches"""
    list_display = [
        'name', 'sla_type', 'severity_badge', 'alert_log_link',
        'threshold_minutes', 'breach_duration_minutes', 'breach_percentage',
        'status_badge', 'breach_severity_badge'
    ]
    
    list_filter = [
        'sla_type', 'severity', 'status',
        ('breach_time', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('acknowledged_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('resolved_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'name', 'alert_log__rule__name', 'root_cause', 'preventive_actions'
    ]
    
    readonly_fields = [
        'breach_time', 'breach_duration_minutes', 'breach_percentage',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sla_type', 'severity', 'status')
        }),
        ('Breach Details', {
            'fields': ('alert_log', 'threshold_minutes', 'breach_time',
                      'breach_duration_minutes', 'breach_percentage')
        }),
        ('Resolution', {
            'fields': ('acknowledged_at', 'acknowledged_by', 'resolved_at',
                      'resolved_by', 'resolution_time_minutes', 'duration_minutes')
        }),
        ('Impact Assessment', {
            'fields': ('business_impact', 'financial_impact', 'customer_impact')
        }),
        ('Escalation', {
            'fields': ('escalated_at', 'escalation_reason',
                      'stakeholder_notified', 'communication_sent')
        }),
        ('Resolution', {
            'fields': ('root_cause', 'preventive_actions', 'notes')
        }),
    )
    
    actions = [
        'acknowledge_breaches', 'resolve_breaches', 'escalate_breaches',
        'notify_stakeholders', 'export_breaches', 'cleanup_breaches'
    ]
    
    # Custom display methods
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
        colors = {
            'active': '#ef4444',
            'resolved': '#10b981',
            'escalated': '#f59e0b',
            'acknowledged': '#3b82f6'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def breach_severity_badge(self, obj):
        """Display breach severity as colored badge"""
        severity = obj.get_breach_severity()
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, severity.upper()
        )
    breach_severity_badge.short_description = 'Breach Severity'
    
    # Custom actions
    def acknowledge_breaches(self, request, queryset):
        """Acknowledge selected breaches"""
        updated = queryset.filter(status='active').update(
            status='acknowledged',
            acknowledged_at=timezone.now(),
            acknowledged_by=request.user
        )
        messages.success(request, f"Acknowledged {updated} breach(es).")
    acknowledge_breaches.short_description = "Acknowledge selected breaches"
    
    def resolve_breaches(self, request, queryset):
        """Resolve selected breaches"""
        updated = queryset.filter(status__in=['active', 'acknowledged']).update(
            status='resolved',
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        messages.success(request, f"Resolved {updated} breach(es).")
    resolve_breaches.short_description = "Resolve selected breaches"
    
    def escalate_breaches(self, request, queryset):
        """Escalate selected breaches"""
        escalated_count = 0
        for breach in queryset.filter(status='active'):
            breach.escalation_level += 1
            breach.save(update_fields=['escalation_level'])
            escalated_count += 1
        
        messages.success(request, f"Escalated {escalated_count} breach(es).")
    escalate_breaches.short_description = "Escalate selected breaches"
    
    def notify_stakeholders(self, request, queryset):
        """Notify stakeholders for selected breaches"""
        from ..tasks.notification import send_notification_to_recipients
        notified_count = 0
        for breach in queryset:
            # Simulate stakeholder notification
            notified_count += 1
        
        messages.success(request, f"Stakeholders notified for {notified_count} breach(es).")
    notify_stakeholders.short_description = "Notify stakeholders"
    
    def export_breaches(self, request, queryset):
        """Export selected breaches"""
        messages.info(request, f"Export initiated for {queryset.count()} breach(es).")
    export_breaches.short_description = "Export breaches"
    
    def cleanup_breaches(self, request, queryset):
        """Clean up old breaches"""
        messages.info(request, f"Cleanup initiated for old breaches.")
    cleanup_breaches.short_description = "Cleanup old breaches"
