"""
Core Admin Classes
"""
from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils.html import format_html
from django.db.models import Count, Q, Sum, Avg, F, Min, Max
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.db import models
import json
from collections import OrderedDict

# Unfold imports
try:
    from unfold.admin import ModelAdmin, TabularInline, StackedInline
    from unfold.sites import UnfoldAdminSite
    from unfold.forms import UserCreationForm, UserChangeForm
    from unfold.filters import DateRangeFilter, RelatedDropdownFilter, ChoiceDropdownFilter
    from unfold.contrib.filters.admin import RangeFilter
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
    from django.contrib.admin import AdminSite as UnfoldAdminSite
    from django.contrib.auth.forms import UserCreationForm, UserChangeForm
    from django.contrib.admin import DateFieldListFilter

from ..models.core import (
    AlertRule, AlertLog, Notification, AlertEscalation, AlertTemplate,
    AlertAnalytics, AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)


# ====================== CUSTOM ADMIN SITE FOR ALERTS ======================

class AlertsAdminSite(UnfoldAdminSite):
    """Custom Admin Site for Alerts app"""
    site_header = "Alerts & Monitoring Dashboard"
    site_title = "Alerts Administration"
    index_title = "Alerts Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('alerts-dashboard/', self.admin_view(self.alerts_dashboard_view), name='alerts_dashboard'),
            path('alerts-analytics/', self.admin_view(self.alerts_analytics_view), name='alerts_analytics'),
            path('api/alert-stats/', self.admin_view(self.alert_stats_api), name='alert_stats_api'),
            path('api/alert-trends/', self.admin_view(self.alert_trends_api), name='alert_trends_api'),
        ]
        return custom_urls + urls
    
    def alerts_dashboard_view(self, request):
        """Custom Alerts Dashboard with Chart.js integration"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Statistics
        total_rules = AlertRule.objects.count()
        active_rules = AlertRule.objects.filter(is_active=True).count()
        
        # Alert statistics
        total_alerts = AlertLog.objects.count()
        unresolved_alerts = AlertLog.objects.filter(is_resolved=False).count()
        today_alerts = AlertLog.objects.filter(triggered_at__date=today).count()
        week_alerts = AlertLog.objects.filter(triggered_at__date__gte=week_ago).count()
        month_alerts = AlertLog.objects.filter(triggered_at__date__gte=month_ago).count()
        
        # Severity breakdown for chart
        severity_data = AlertLog.objects.values('rule__severity').annotate(
            count=Count('id')
        ).order_by('rule__severity')
        
        severity_counts = {item['rule__severity']: item['count'] for item in severity_data}
        
        # For chart labels - use display names
        SEVERITY_DISPLAY = dict(AlertRule.SEVERITY)
        severity_labels = []
        severity_values = []
        
        for severity, display in SEVERITY_DISPLAY.items():
            severity_labels.append(display)
            severity_values.append(severity_counts.get(severity, 0))
        
        # Daily trends for last 7 days
        daily_trends = []
        daily_labels = []
        daily_totals = []
        daily_resolved = []
        
        for i in range(6, -1, -1):  # Last 7 days including today
            date = today - timedelta(days=i)
            daily_total = AlertLog.objects.filter(triggered_at__date=date).count()
            daily_resolved_count = AlertLog.objects.filter(
                triggered_at__date=date, 
                is_resolved=True
            ).count()
            
            daily_trends.append({
                'date': date,
                'total': daily_total,
                'resolved': daily_resolved_count
            })
            daily_labels.append(date.strftime('%b %d'))
            daily_totals.append(daily_total)
            daily_resolved.append(daily_resolved_count)
        
        # Alert types distribution
        alert_types = AlertLog.objects.values('rule__alert_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Recent alerts
        recent_alerts = AlertLog.objects.select_related('rule', 'resolved_by').order_by('-triggered_at')[:10]
        
        # Latest system metrics
        latest_metrics = SystemMetrics.objects.order_by('-timestamp').first()
        
        # Prepare context
        context = {
            **self.each_context(request),
            'title': 'Alerts & Monitoring Dashboard',
            'current_time': timezone.now().strftime("%H:%M:%S"),
            'today': today,
            
            # Stats
            'total_rules': total_rules,
            'active_rules': active_rules,
            'total_alerts': total_alerts,
            'unresolved_alerts': unresolved_alerts,
            'today_alerts': today_alerts,
            'week_alerts': week_alerts,
            'month_alerts': month_alerts,
            
            # Chart data
            'severity_stats': list(severity_data),
            'severity_labels': json.dumps(severity_labels),
            'severity_data': json.dumps(severity_values),
            
            'daily_trends': daily_trends,
            'daily_trends_labels': json.dumps(daily_labels),
            'daily_trends_data': json.dumps(daily_totals),
            'daily_resolved_data': json.dumps(daily_resolved),
            
            # Lists
            'recent_alerts': recent_alerts,
            'alert_types': list(alert_types),
            'latest_metrics': latest_metrics,
            
            # Calculation
            'alert_resolution_rate': self._calculate_resolution_rate(),
        }
        
        return render(request, 'alerts/alerts_dashboard.html', context)
    
    def alerts_analytics_view(self, request):
        """Alert Analytics View"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Daily trends for charts
        daily_trends = AlertLog.objects.filter(
            triggered_at__date__gte=week_ago
        ).extra(
            {'day': "date(triggered_at)"}
        ).values('day').annotate(
            total=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True))
        ).order_by('day')
        
        # Alert type distribution with resolution times
        type_distribution = AlertLog.objects.values('rule__alert_type').annotate(
            total=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True)),
            avg_resolution_seconds=Avg(
                models.ExpressionWrapper(
                    models.F('resolved_at') - models.F('triggered_at'),
                    output_field=models.DurationField()
                ),
                filter=Q(is_resolved=True, resolved_at__isnull=False)
            )
        ).order_by('-total')
        
        # Severity analysis
        severity_analysis = AlertLog.objects.values('rule__severity').annotate(
            total=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True)),
            unresolved=Count('id', filter=Q(is_resolved=False))
        ).order_by('rule__severity')
        
        # Resolution time statistics
        resolved_alerts = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__isnull=False
        )
        
        resolution_stats = {}
        if resolved_alerts.exists():
            resolution_times = resolved_alerts.annotate(
                resolution_time=models.ExpressionWrapper(
                    models.F('resolved_at') - models.F('triggered_at'),
                    output_field=models.DurationField()
                )
            ).values_list('resolution_time', flat=True)
            
            # Convert to minutes
            resolution_minutes = [rt.total_seconds() / 60 for rt in resolution_times]
            
            if resolution_minutes:
                resolution_stats = {
                    'min': min(resolution_minutes),
                    'max': max(resolution_minutes),
                    'avg': sum(resolution_minutes) / len(resolution_minutes),
                    'median': sorted(resolution_minutes)[len(resolution_minutes) // 2]
                }
        
        context = {
            **self.each_context(request),
            'title': 'Alert Analytics',
            'daily_trends': list(daily_trends),
            'type_distribution': list(type_distribution),
            'severity_analysis': list(severity_analysis),
            'resolution_stats': resolution_stats,
            'total_alerts': AlertLog.objects.count(),
            'resolved_alerts': AlertLog.objects.filter(is_resolved=True).count(),
            'unresolved_alerts': AlertLog.objects.filter(is_resolved=False).count(),
        }
        
        return render(request, 'admin/alerts_analytics.html', context)
    
    def alert_stats_api(self, request):
        """API endpoint for alert statistics"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Daily trends
        daily_stats = []
        for i in range(6, -1, -1):  # Last 7 days
            date = today - timedelta(days=i)
            daily_total = AlertLog.objects.filter(triggered_at__date=date).count()
            daily_resolved = AlertLog.objects.filter(
                triggered_at__date=date,
                is_resolved=True
            ).count()
            
            daily_stats.append({
                'date': date.isoformat(),
                'total': daily_total,
                'resolved': daily_resolved,
                'pending': daily_total - daily_resolved
            })
        
        return JsonResponse({
            'daily_stats': daily_stats,
            'timestamp': timezone.now().isoformat()
        })
    
    def alert_trends_api(self, request):
        """API endpoint for alert trends"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Prepare data for Chart.js
        labels = []
        data = []
        
        for i in range(6, -1, -1):  # Last 7 days
            date = today - timedelta(days=i)
            daily_total = AlertLog.objects.filter(triggered_at__date=date).count()
            daily_resolved = AlertLog.objects.filter(
                triggered_at__date=date,
                is_resolved=True
            ).count()
            
            data.append({
                'date': date.isoformat(),
                'total': daily_total,
                'resolved': daily_resolved,
                'pending': daily_total - daily_resolved
            })
            labels.append(date.strftime('%b %d'))
        
        return JsonResponse({
            'labels': labels,
            'data': data,
            'timestamp': timezone.now().isoformat()
        })
    
    def _calculate_resolution_rate(self):
        """Calculate alert resolution rate"""
        total_alerts = AlertLog.objects.count()
        resolved_alerts = AlertLog.objects.filter(is_resolved=True).count()
        
        if total_alerts > 0:
            return (resolved_alerts / total_alerts) * 100
        return 0
    
    def index(self, request, extra_context=None):
        """Override admin index to redirect to alerts dashboard"""
        return redirect('alerts_admin:alerts_dashboard')


# Create alerts admin site instance
alerts_admin_site = AlertsAdminSite(name='alerts_admin')


# ====================== INLINE ADMIN CLASSES ======================

class AlertLogInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Alert Logs in Alert Rule"""
    model = AlertLog
    extra = 0
    fields = ['triggered_at', 'trigger_value', 'threshold_value', 'is_resolved', 'resolved_at']
    readonly_fields = ['triggered_at', 'trigger_value', 'threshold_value']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class NotificationInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Notifications in Alert Log"""
    model = Notification
    extra = 0
    fields = ['notification_type', 'recipient', 'status', 'sent_at']
    readonly_fields = ['notification_type', 'recipient', 'status', 'sent_at']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class AlertRuleHistoryInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Alert Rule History"""
    model = AlertRuleHistory
    extra = 0
    fields = ['changed_at']
    readonly_fields = ['changed_at']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


# ====================== ADMIN CLASSES ======================

@admin.register(AlertRule, site=alerts_admin_site)
class AlertRuleAdmin(ModelAdmin):
    """Admin interface for Alert Rules"""
    list_display = [
        'name', 'alert_type', 'severity_badge', 'threshold_value', 
        'time_window_minutes', 'is_active', 'last_triggered', 
        'alert_channels', 'total_triggers', 'resolution_rate'
    ]
    
    list_filter = [
        'alert_type', 'severity', 'is_active', 'send_email', 'send_telegram', 'send_sms',
        ('last_triggered', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'alert_type', 'email_recipients', 'telegram_chat_id', 'sms_recipients']
    
    list_editable = ['is_active', 'threshold_value', 'time_window_minutes']
    
    readonly_fields = [
        'last_triggered', 'created_at', 'total_triggers', 
        'avg_resolution_time', 'resolution_rate', 'success_rate'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'alert_type', 'severity', 'description')
        }),
        ('Threshold Configuration', {
            'fields': ('threshold_value', 'time_window_minutes', 'cooldown_minutes')
        }),
        ('Alert Channels', {
            'fields': ('send_email', 'send_telegram', 'send_sms')
        }),
        ('Recipients', {
            'fields': ('email_recipients', 'telegram_chat_id', 'sms_recipients')
        }),
        ('Status & Statistics', {
            'fields': ('is_active', 'last_triggered', 'created_at', 
                      'total_triggers', 'avg_resolution_time', 'resolution_rate', 'success_rate')
        }),
    )

    inlines = [AlertLogInline, AlertRuleHistoryInline]

    actions = [
        'activate_rules', 
        'deactivate_rules', 
        'test_alert_rules', 
        'reset_last_triggered', 
        'duplicate_rules'
    ]
    
    # Custom display methods
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
            color, obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'
    severity_badge.admin_order_field = 'severity'
    
    def alert_channels(self, obj):
        """Show enabled alert channels"""
        channels = []
        if obj.send_email:
            channels.append('Email')
        if obj.send_telegram:
            channels.append('Telegram')
        if obj.send_sms:
            channels.append('SMS')
        return ', '.join(channels) if channels else 'None'
    alert_channels.short_description = 'Channels'
    
    def total_triggers(self, obj):
        """Total number of triggers"""
        return obj.alertlog_set.count()
    total_triggers.short_description = 'Total Triggers'
    
    def resolution_rate(self, obj):
        """Calculate resolution rate for this rule"""
        total = obj.alertlog_set.count()
        resolved = obj.alertlog_set.filter(is_resolved=True).count()
        if total > 0:
            return f"{(resolved / total) * 100:.1f}%"
        return "N/A"
    resolution_rate.short_description = 'Resolution Rate'
    
    def avg_resolution_time(self, obj):
        """Average resolution time in minutes"""
        resolved_alerts = obj.alertlog_set.filter(
            is_resolved=True, 
            resolved_at__isnull=False
        )
        if resolved_alerts.exists():
            total_time = sum(
                (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                for alert in resolved_alerts
            )
            return f"{total_time / resolved_alerts.count():.1f} min"
        return "N/A"
    avg_resolution_time.short_description = 'Avg Resolution Time'
    
    def success_rate(self, obj):
        """Success rate of notifications"""
        notifications = Notification.objects.filter(alert_log__rule=obj)
        if notifications.exists():
            sent = notifications.filter(status='sent').count()
            return f"{(sent / notifications.count()) * 100:.1f}%"
        return "N/A"
    success_rate.short_description = 'Notification Success Rate'
    
    # Custom actions
    def activate_rules(self, request, queryset):
        """Activate selected rules"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} rule(s).")
    activate_rules.short_description = "Activate selected rules"
    
    def deactivate_rules(self, request, queryset):
        """Deactivate selected rules"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} rule(s).")
    deactivate_rules.short_description = "Deactivate selected rules"
    
    def test_alert_rules(self, request, queryset):
        """Create test alerts for selected rules"""
        for rule in queryset:
            AlertLog.objects.create(
                rule=rule,
                trigger_value=rule.threshold_value * 1.5,
                threshold_value=rule.threshold_value,
                message=f"Test alert triggered for rule: {rule.name}",
                details={
                    'test': True, 
                    'triggered_by': request.user.username,
                    'timestamp': timezone.now().isoformat()
                },
                email_sent=rule.send_email,
                telegram_sent=rule.send_telegram,
                sms_sent=rule.send_sms
            )
            
            # Update last triggered time
            rule.last_triggered = timezone.now()
            rule.save(update_fields=['last_triggered'])
        
        messages.success(request, f"Created test alerts for {queryset.count()} rule(s).")
    test_alert_rules.short_description = "Test selected rules"
    
    def reset_last_triggered(self, request, queryset):
        """Reset last triggered time"""
        queryset.update(last_triggered=None)
        messages.success(request, f"Reset last triggered time for {queryset.count()} rule(s).")
    reset_last_triggered.short_description = "Reset trigger time"
    
    def duplicate_rules(self, request, queryset):
        """Duplicate selected alert rules"""
        duplicated_count = 0
        for rule in queryset:
            # Create a copy of the rule
            rule.pk = None
            rule.name = f"{rule.name} (Copy)"
            rule.is_active = False  # Deactivate the copy by default
            rule.last_triggered = None
            rule.save()
            duplicated_count += 1
        
        messages.success(request, f"Duplicated {duplicated_count} rule(s).")
    duplicate_rules.short_description = "Duplicate selected rules"


@admin.register(AlertLog, site=alerts_admin_site)
class AlertLogAdmin(ModelAdmin):
    """Admin interface for Alert Logs"""
    list_display = [
        'id', 'rule_link', 'severity_badge', 'triggered_at', 
        'status_badge', 'trigger_value', 'threshold_value', 
        'channels_used', 'resolved_by', 'resolution_time'
    ]
    
    list_filter = [
        'rule__alert_type', 'rule__severity', 'is_resolved',
        'email_sent', 'telegram_sent', 'sms_sent',
        ('triggered_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('resolved_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'rule__name', 'message', 'details', 
        'resolution_note', 'resolved_by__username', 'resolved_by__email'
    ]
    
    readonly_fields = [
        'triggered_at', 'trigger_value', 'threshold_value', 
        'message', 'details', 'email_sent', 'telegram_sent', 
        'sms_sent', 'resolution_time',
    ]
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('rule', 'triggered_at', 'trigger_value', 'threshold_value', 'message')
        }),
        ('Details', {
            'fields': ('details',)
        }),
        ('Notification Status', {
            'fields': ('email_sent', 'telegram_sent', 'sms_sent', 'channels_used')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by', 'resolution_note', 
                      'resolution_time', 'age')
        }),
    )
    
    inlines = [NotificationInline]
    
    actions = ['mark_as_resolved', 'mark_as_unresolved', 'send_notifications', 'export_alerts', 'bulk_delete']
    
    # Custom display methods
    def rule_link(self, obj):
        """Clickable rule name"""
        url = reverse('alerts_admin:alerts_alertrule_change', args=[obj.rule.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.rule.name)
    rule_link.short_description = 'Rule'
    rule_link.admin_order_field = 'rule__name'
    
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(obj.rule.severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.rule.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'
    severity_badge.admin_order_field = 'rule__severity'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        if obj.is_resolved:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">RESOLVED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">PENDING</span>'
            )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'is_resolved'
    
    def channels_used(self, obj):
        """Show channels used for this alert"""
        channels = []
        if obj.email_sent:
            channels.append('Email')
        if obj.telegram_sent:
            channels.append('Telegram')
        if obj.sms_sent:
            channels.append('SMS')
        return ', '.join(channels) if channels else 'None'
    channels_used.short_description = 'Channels'
    
    def resolution_time(self, obj):
        """Resolution time in minutes"""
        if obj.is_resolved and obj.resolved_at:
            minutes = (obj.resolved_at - obj.triggered_at).total_seconds() / 60
            return f"{minutes:.1f} min"
        return "N/A"
    resolution_time.short_description = 'Resolution Time'
    
    def age(self, obj):
        """Age of the alert"""
        if not obj.is_resolved:
            age = timezone.now() - obj.triggered_at
            if age.days > 0:
                return f"{age.days} days"
            elif age.seconds > 3600:
                return f"{age.seconds // 3600} hours"
            else:
                return f"{age.seconds // 60} minutes"
        return "Resolved"
    age.short_description = 'Age'
    
    # Custom actions
    def mark_as_resolved(self, request, queryset):
        """Mark selected alerts as resolved"""
        updated = queryset.filter(is_resolved=False).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user,
            resolution_note="Bulk resolved by admin"
        )
        messages.success(request, f"Resolved {updated} alert(s).")
    mark_as_resolved.short_description = "Mark as resolved"
    
    def mark_as_unresolved(self, request, queryset):
        """Mark selected alerts as unresolved"""
        updated = queryset.filter(is_resolved=True).update(
            is_resolved=False,
            resolved_at=None,
            resolved_by=None,
            resolution_note=""
        )
        messages.success(request, f"Unresolved {updated} alert(s).")
    mark_as_unresolved.short_description = "Mark as unresolved"
    
    def send_notifications(self, request, queryset):
        """Send notifications for selected alerts"""
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        messages.success(request, f"Queued notifications for {queryset.count()} alert(s).")
    send_notifications.short_description = "Send notifications"
    
    def export_alerts(self, request, queryset):
        """Export selected alerts"""
        messages.info(request, f"Export initiated for {queryset.count()} alert(s).")
    export_alerts.short_description = "Export alerts"
    
    def bulk_delete(self, request, queryset):
        """Bulk delete selected alerts"""
        deleted, _ = queryset.delete()
        messages.success(request, f"Deleted {deleted} alert(s).")
    bulk_delete.short_description = "Delete selected alerts"


@admin.register(SystemMetrics, site=alerts_admin_site)
class SystemMetricsAdmin(ModelAdmin):
    """Admin interface for System Metrics"""
    list_display = [
        'timestamp', 'total_users', 'active_users_1h', 
        'total_earnings_1h', 'fraud_indicators_1h', 
        'avg_response_time_ms', 'health_status', 'error_count_1h'
    ]
    
    list_filter = [
        ('timestamp', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = []
    
    readonly_fields = [
        'timestamp', 'total_users', 'active_users_1h', 'active_users_24h',
        'new_signups_1h', 'total_earnings_1h', 'total_tasks_1h',
        'avg_earning_per_user', 'pending_payments', 'payment_requests_1h',
        'total_payout_pending', 'fraud_indicators_1h', 'banned_users_24h',
        'vpn_blocks_1h', 'avg_response_time_ms', 'error_count_1h',
        'db_connections', 'redis_memory_mb'
    ]
    
    fieldsets = (
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
        ('User Metrics', {
            'fields': ('total_users', 'active_users_1h', 'active_users_24h', 'new_signups_1h')
        }),
        ('Earning Metrics', {
            'fields': ('total_earnings_1h', 'total_tasks_1h', 'avg_earning_per_user')
        }),
        ('Payment Metrics', {
            'fields': ('pending_payments', 'payment_requests_1h', 'total_payout_pending')
        }),
        ('Security Metrics', {
            'fields': ('fraud_indicators_1h', 'banned_users_24h', 'vpn_blocks_1h')
        }),
        ('System Health', {
            'fields': ('avg_response_time_ms', 'error_count_1h', 'db_connections', 'redis_memory_mb')
        }),
    )
    
    actions = ['export_metrics', 'generate_health_report']
    
    def has_add_permission(self, request):
        """System metrics are auto-generated, cannot add manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """System metrics are read-only"""
        return False
    
    def health_status(self, obj):
        """Calculate health status based on metrics"""
        if obj.avg_response_time_ms < 500 and obj.error_count_1h < 5:
            return format_html(
                '<span style="color: #10b981; font-weight: bold;">Healthy</span>'
            )
        elif obj.avg_response_time_ms < 1000 and obj.error_count_1h < 10:
            return format_html(
                '<span style="color: #f59e0b; font-weight: bold;">Warning</span>'
            )
        else:
            return format_html(
                '<span style="color: #ef4444; font-weight: bold;">Critical</span>'
            )
    health_status.short_description = 'Health Status'
    
    def export_metrics(self, request, queryset):
        """Export selected metrics"""
        messages.info(request, f"Export initiated for {queryset.count()} metric(s).")
    export_metrics.short_description = "Export metrics"
    
    def generate_health_report(self, request, queryset):
        """Generate health report for selected metrics"""
        messages.info(request, f"Health report generated for {queryset.count()} metric(s).")
    generate_health_report.short_description = "Generate health report"
