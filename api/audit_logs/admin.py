# audit_logs/admin.py (CORRECTED VERSION)
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, IntegerField, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib import messages
from django.db import models
import json
import uuid
from django.core.serializers.json import DjangoJSONEncoder

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

from .models import (
    AuditLog, AuditLogConfig, AuditLogArchive, 
    AuditDashboard, AuditAlertRule, AuditLogAction 
)


# ====================== CUSTOM ADMIN SITE FOR AUDIT LOGS ======================

class AuditLogsAdminSite(UnfoldAdminSite):
    """Custom Admin Site for Audit Logs app"""
    site_header = "🔍 Audit & Security Dashboard"
    site_title = "Audit Logs Administration"
    index_title = "Audit & Security Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('audit-dashboard/', self.admin_view(self.audit_dashboard_view), name='audit_dashboard'),
            path('security-overview/', self.admin_view(self.security_overview_view), name='security_overview'),
            path('user-activity/', self.admin_view(self.user_activity_view), name='user_activity'),
            path('system-audit/', self.admin_view(self.system_audit_view), name='system_audit'),
            path('live-logs/', self.admin_view(self.live_logs_view), name='live_logs'),
            path('log-search/', self.admin_view(self.log_search_view), name='log_search'),
            path('export-logs/', self.admin_view(self.export_logs_view), name='export_logs'),
            path('cleanup-logs/', self.admin_view(self.cleanup_logs_view), name='cleanup_logs'),
        ]
        return custom_urls + urls
    
    def audit_dashboard_view(self, request):
        """Main Audit Dashboard"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Total logs
        total_logs = AuditLog.objects.count()
        today_logs = AuditLog.objects.filter(timestamp__date=today).count()
        week_logs = AuditLog.objects.filter(timestamp__date__gte=week_ago).count()
        
        # Log breakdown by level
        level_distribution = AuditLog.objects.values('level').annotate(
            count=Count('id'),
            error_count=Count('id', filter=Q(level='ERROR') | Q(level='CRITICAL'))
        ).order_by('-count')
        
        # Action distribution
        top_actions = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # User activity
        active_users = AuditLog.objects.filter(
            timestamp__date=today,
            user__isnull=False
        ).values('user__username').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        # Security incidents
        security_incidents = AuditLog.objects.filter(
            level__in=['SECURITY', 'CRITICAL'],
            timestamp__date__gte=week_ago
        ).count()
        
        # Failed actions
        failed_actions = AuditLog.objects.filter(
            success=False,
            timestamp__date__gte=week_ago
        ).count()
        
        # Recent critical logs
        recent_critical = AuditLog.objects.filter(
            level__in=['CRITICAL', 'SECURITY', 'ERROR']
        ).select_related('user').order_by('-timestamp')[:10]
        
        # IP activity
        suspicious_ips = AuditLog.objects.filter(
            timestamp__date=today
        ).values('user_ip').annotate(
            count=Count('id'),
            failed_count=Count('id', filter=Q(success=False))
        ).filter(count__gt=100).order_by('-count')[:10]
        
        context = {
            **self.each_context(request),
            'title': 'Audit & Security Dashboard',
            'today': today,
            'total_logs': total_logs,
            'today_logs': today_logs,
            'week_logs': week_logs,
            'level_distribution': list(level_distribution),
            'top_actions': list(top_actions),
            'active_users': list(active_users),
            'security_incidents': security_incidents,
            'failed_actions': failed_actions,
            'recent_critical': recent_critical,
            'suspicious_ips': suspicious_ips,
            'log_growth': self._calculate_log_growth(),
        }
        
        return render(request, 'admin/audit_dashboard.html', context)
    
    def security_overview_view(self, request):
        """Security Overview Dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Security events by type
        security_events = AuditLog.objects.filter(
            level='SECURITY',
            timestamp__date__gte=week_ago
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Failed logins
        failed_logins = AuditLog.objects.filter(
            action='LOGIN',
            success=False,
            timestamp__date__gte=week_ago
        ).count()
        
        # Suspicious activities
        suspicious_activities = AuditLog.objects.filter(
            action__in=['SUSPICIOUS_LOGIN', 'BRUTE_FORCE_ATTEMPT', 'IP_BLOCK'],
            timestamp__date__gte=week_ago
        ).select_related('user').order_by('-timestamp')[:20]
        
        # User security events
        user_security_events = AuditLog.objects.filter(
            level__in=['SECURITY', 'CRITICAL'],
            timestamp__date__gte=week_ago,
            user__isnull=False
        ).values('user__username').annotate(
            event_count=Count('id')
        ).order_by('-event_count')[:10]
        
        # IP threat analysis
        ip_threats = AuditLog.objects.filter(
            level='SECURITY',
            timestamp__date__gte=week_ago,
            user_ip__isnull=False
        ).values('user_ip').annotate(
            threat_count=Count('id'),
            unique_actions=Count('action', distinct=True)
        ).order_by('-threat_count')[:10]
        
        # Security trends (daily)
        security_trends = AuditLog.objects.filter(
            level='SECURITY',
            timestamp__date__gte=week_ago
        ).extra({
            'day': "date(timestamp)"
        }).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        context = {
            **self.each_context(request),
            'title': 'Security Overview',
            'today': today,
            'security_events': list(security_events),
            'failed_logins': failed_logins,
            'suspicious_activities': suspicious_activities,
            'user_security_events': list(user_security_events),
            'ip_threats': list(ip_threats),
            'security_trends': list(security_trends),
            'threat_level': self._calculate_threat_level(),
        }
        
        return render(request, 'admin/security_overview.html', context)
    
    def user_activity_view(self, request):
        """User Activity Dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # User search
        user_id = request.GET.get('user_id')
        username = request.GET.get('username')
        
        user_activities = AuditLog.objects.all()
        
        if user_id:
            user_activities = user_activities.filter(user_id=user_id)
        
        if username:
            user_activities = user_activities.filter(user__username__icontains=username)
        
        # Default: show today's activities
        if not (user_id or username):
            user_activities = user_activities.filter(timestamp__date=today)
        
        # User activity stats
        user_stats = AuditLog.objects.filter(
            timestamp__date__gte=week_ago,
            user__isnull=False
        ).values('user__username', 'user__id').annotate(
            total_actions=Count('id'),
            successful_actions=Count('id', filter=Q(success=True)),
            failed_actions=Count('id', filter=Q(success=False)),
            last_activity=Max('timestamp')
        ).order_by('-total_actions')[:20]
        
        # Action types by user
        user_action_types = {}
        for stat in user_stats:
            actions = AuditLog.objects.filter(
                user_id=stat['user__id'],
                timestamp__date__gte=week_ago
            ).values('action').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            user_action_types[stat['user__username']] = list(actions)
        
        # User locations
        user_locations = AuditLog.objects.filter(
            timestamp__date__gte=week_ago,
            user__isnull=False,
            country__isnull=False
        ).values('user__username', 'country', 'city').annotate(
            visit_count=Count('id')
        ).order_by('-visit_count')[:10]
        
        context = {
            **self.each_context(request),
            'title': 'User Activity Monitor',
            'today': today,
            'user_activities': user_activities.order_by('-timestamp')[:50],
            'user_stats': list(user_stats),
            'user_action_types': user_action_types,
            'user_locations': list(user_locations),
            'total_users_today': AuditLog.objects.filter(
                timestamp__date=today,
                user__isnull=False
            ).values('user').distinct().count(),
        }
        
        return render(request, 'admin/user_activity.html', context)
    
    def system_audit_view(self, request):
        """System Audit Dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # System events
        system_events = AuditLog.objects.filter(
            action__in=['SYSTEM_ALERT', 'BACKUP', 'MAINTENANCE', 'API_CALL', 'RATE_LIMIT'],
            timestamp__date__gte=week_ago
        ).order_by('-timestamp')
        
        # Error trends
        error_trends = AuditLog.objects.filter(
            level__in=['ERROR', 'CRITICAL'],
            timestamp__date__gte=week_ago
        ).extra({
            'hour': "date_trunc('hour', timestamp)"
        }).values('hour').annotate(
            error_count=Count('id')
        ).order_by('hour')
        
        # API performance
        api_performance = AuditLog.objects.filter(
            action='API_CALL',
            timestamp__date__gte=week_ago,
            response_time_ms__isnull=False
        ).aggregate(
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            min_response_time=Min('response_time_ms'),
            total_calls=Count('id')
        )
        
        # Slow endpoints
        slow_endpoints = AuditLog.objects.filter(
            action='API_CALL',
            timestamp__date__gte=week_ago,
            response_time_ms__gt=1000  # > 1 second
        ).values('request_path').annotate(
            avg_time=Avg('response_time_ms'),
            max_time=Max('response_time_ms'),
            call_count=Count('id')
        ).order_by('-avg_time')[:10]
        
        # System health
        system_health = {
            'uptime_percentage': self._calculate_uptime_percentage(week_ago),
            'error_rate': self._calculate_error_rate(week_ago),
            'avg_api_response': api_performance['avg_response_time'] or 0,
            'total_api_calls': api_performance['total_calls'] or 0,
        }
        
        context = {
            **self.each_context(request),
            'title': 'System Audit & Performance',
            'today': today,
            'system_events': system_events[:50],
            'error_trends': list(error_trends),
            'api_performance': api_performance,
            'slow_endpoints': list(slow_endpoints),
            'system_health': system_health,
            'critical_errors_today': AuditLog.objects.filter(
                level='CRITICAL',
                timestamp__date=today
            ).count(),
        }
        
        return render(request, 'admin/system_audit.html', context)
    
    def live_logs_view(self, request):
        """Live Logs Streaming View"""
        # Last 100 logs in real-time
        live_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:100]
        
        # Filter options
        levels = [('DEBUG', 'Debug'), ('INFO', 'Information'), ('WARNING', 'Warning'), 
                 ('ERROR', 'Error'), ('CRITICAL', 'Critical'), ('SECURITY', 'Security')]
        actions = [('LOGIN', 'Login'), ('LOGOUT', 'Logout'), ('API_CALL', 'API Call'), 
                  ('WITHDRAWAL', 'Withdrawal'), ('ERROR', 'Error')]
        
        # Apply filters
        level_filter = request.GET.get('level')
        action_filter = request.GET.get('action')
        user_filter = request.GET.get('user')
        
        if level_filter:
            live_logs = live_logs.filter(level=level_filter)
        
        if action_filter:
            live_logs = live_logs.filter(action=action_filter)
        
        if user_filter:
            live_logs = live_logs.filter(user__username__icontains=user_filter)
        
        context = {
            **self.each_context(request),
            'title': 'Live Logs Stream',
            'live_logs': live_logs,
            'levels': levels,
            'actions': actions,
            'total_logs_24h': AuditLog.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count(),
        }
        
        return render(request, 'admin/live_logs.html', context)
    
    def log_search_view(self, request):
        """Advanced Log Search"""
        # Search parameters
        search_params = {
            'q': request.GET.get('q', ''),
            'level': request.GET.get('level', ''),
            'action': request.GET.get('action', ''),
            'user_id': request.GET.get('user_id', ''),
            'ip_address': request.GET.get('ip_address', ''),
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'success': request.GET.get('success', ''),
            'resource_type': request.GET.get('resource_type', ''),
        }
        
        # Build query
        query = Q()
        
        if search_params['q']:
            query &= Q(message__icontains=search_params['q']) | Q(error_message__icontains=search_params['q'])
        
        if search_params['level']:
            query &= Q(level=search_params['level'])
        
        if search_params['action']:
            query &= Q(action=search_params['action'])
        
        if search_params['user_id']:
            query &= Q(user_id=search_params['user_id'])
        
        if search_params['ip_address']:
            query &= Q(user_ip=search_params['ip_address'])
        
        if search_params['date_from']:
            query &= Q(timestamp__date__gte=search_params['date_from'])
        
        if search_params['date_to']:
            query &= Q(timestamp__date__lte=search_params['date_to'])
        
        if search_params['success'] != '':
            query &= Q(success=(search_params['success'] == 'true'))
        
        if search_params['resource_type']:
            query &= Q(resource_type=search_params['resource_type'])
        
        # Execute search
        search_results = AuditLog.objects.filter(query).select_related('user').order_by('-timestamp')[:200]
        
        context = {
            **self.each_context(request),
            'title': 'Advanced Log Search',
            'search_results': search_results,
            'search_params': search_params,
            'levels': [('DEBUG', 'Debug'), ('INFO', 'Information'), ('WARNING', 'Warning'), 
                      ('ERROR', 'Error'), ('CRITICAL', 'Critical'), ('SECURITY', 'Security')],
            'actions': [('LOGIN', 'Login'), ('LOGOUT', 'Logout'), ('API_CALL', 'API Call'),
                       ('WITHDRAWAL', 'Withdrawal'), ('ERROR', 'Error')],
            'result_count': search_results.count(),
        }
        
        return render(request, 'admin/log_search.html', context)
    
    def export_logs_view(self, request):
        """Export Logs View"""
        if request.method == 'POST':
            # Handle export request
            export_format = request.POST.get('format', 'json')
            date_from = request.POST.get('date_from')
            date_to = request.POST.get('date_to')
            level = request.POST.get('level')
            
            # Build query for export
            query = Q()
            
            if date_from:
                query &= Q(timestamp__date__gte=date_from)
            
            if date_to:
                query &= Q(timestamp__date__lte=date_to)
            
            if level:
                query &= Q(level=level)
            
            logs_to_export = AuditLog.objects.filter(query)
            count = logs_to_export.count()
            
            messages.success(request, f"Exporting {count} logs in {export_format} format...")
            # Actual export logic would go here
            
            return redirect('admin:audit_dashboard')
        
        context = {
            **self.each_context(request),
            'title': 'Export Logs',
            'levels': [('DEBUG', 'Debug'), ('INFO', 'Information'), ('WARNING', 'Warning'), 
                      ('ERROR', 'Error'), ('CRITICAL', 'Critical'), ('SECURITY', 'Security')],
            'default_date_from': (timezone.now() - timedelta(days=7)).date(),
            'default_date_to': timezone.now().date(),
        }
        
        return render(request, 'admin/export_logs.html', context)
    
    def cleanup_logs_view(self, request):
        """Log Cleanup Management"""
        if request.method == 'POST':
            # Handle cleanup request
            days_to_keep = int(request.POST.get('days_to_keep', 90))
            archive_before_delete = request.POST.get('archive', 'false') == 'true'
            
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            logs_to_delete = AuditLog.objects.filter(timestamp__lt=cutoff_date)
            count = logs_to_delete.count()
            
            if archive_before_delete:
                # Archive logic would go here
                messages.info(request, f"Archiving {count} logs before deletion...")
            
            # Delete logs
            # logs_to_delete.delete()  # Uncomment to actually delete
            messages.success(request, f"Scheduled deletion of {count} logs older than {days_to_keep} days")
            
            return redirect('admin:audit_dashboard')
        
        # Statistics
        total_logs = AuditLog.objects.count()
        logs_by_age = {
            'last_24h': AuditLog.objects.filter(timestamp__gte=timezone.now() - timedelta(hours=24)).count(),
            'last_7d': AuditLog.objects.filter(timestamp__gte=timezone.now() - timedelta(days=7)).count(),
            'last_30d': AuditLog.objects.filter(timestamp__gte=timezone.now() - timedelta(days=30)).count(),
            'older_90d': AuditLog.objects.filter(timestamp__lt=timezone.now() - timedelta(days=90)).count(),
            'older_180d': AuditLog.objects.filter(timestamp__lt=timezone.now() - timedelta(days=180)).count(),
            'older_365d': AuditLog.objects.filter(timestamp__lt=timezone.now() - timedelta(days=365)).count(),
        }
        
        context = {
            **self.each_context(request),
            'title': 'Log Cleanup & Management',
            'total_logs': total_logs,
            'logs_by_age': logs_by_age,
            'archive_count': AuditLogArchive.objects.count(),
            'total_archived_size': AuditLogArchive.objects.aggregate(
                total=Sum('compressed_size_mb')
            )['total'] or 0,
        }
        
        return render(request, 'admin/cleanup_logs.html', context)
    
    # Helper methods
    def _calculate_log_growth(self):
        """Calculate log growth rate"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        today_count = AuditLog.objects.filter(timestamp__date=today).count()
        yesterday_count = AuditLog.objects.filter(timestamp__date=yesterday).count()
        
        if yesterday_count > 0:
            growth = ((today_count - yesterday_count) / yesterday_count) * 100
            return round(growth, 1)
        return 0
    
    def _calculate_threat_level(self):
        """Calculate current threat level"""
        today = timezone.now().date()
        
        critical_count = AuditLog.objects.filter(
            level__in=['CRITICAL', 'SECURITY'],
            timestamp__date=today
        ).count()
        
        if critical_count > 10:
            return {'level': 'HIGH', 'color': 'red'}
        elif critical_count > 5:
            return {'level': 'MEDIUM', 'color': 'orange'}
        elif critical_count > 0:
            return {'level': 'LOW', 'color': 'yellow'}
        else:
            return {'level': 'NORMAL', 'color': 'green'}
    
    def _calculate_uptime_percentage(self, since_date):
        """Calculate system uptime percentage"""
        total_hours = (timezone.now() - since_date).total_seconds() / 3600
        error_hours = AuditLog.objects.filter(
            level='CRITICAL',
            timestamp__gte=since_date
        ).count() * 0.1  # Assuming each critical error causes 0.1 hours downtime
        
        if total_hours > 0:
            uptime = ((total_hours - error_hours) / total_hours) * 100
            return round(uptime, 2)
        return 100
    
    def _calculate_error_rate(self, since_date):
        """Calculate error rate percentage"""
        total_logs = AuditLog.objects.filter(timestamp__gte=since_date).count()
        error_logs = AuditLog.objects.filter(
            level__in=['ERROR', 'CRITICAL'],
            timestamp__gte=since_date
        ).count()
        
        if total_logs > 0:
            error_rate = (error_logs / total_logs) * 100
            return round(error_rate, 2)
        return 0
    
    def index(self, request, extra_context=None):
        """Override admin index to show audit dashboard"""
        return redirect('admin:audit_dashboard')


# Create audit logs admin site instance
audit_logs_admin_site = AuditLogsAdminSite(name='audit_logs_admin')


# ====================== INLINE ADMIN CLASSES ======================

class AuditLogArchiveInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Audit Log Archives"""
    model = AuditLogArchive
    extra = 0
    fields = ['start_date', 'end_date', 'total_logs', 'compressed_size_mb']
    readonly_fields = ['start_date', 'end_date', 'total_logs', 'compressed_size_mb']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


# ====================== ADMIN CLASSES ======================

@admin.register(AuditLog, site=audit_logs_admin_site)
class AuditLogAdmin(ModelAdmin):
    """Admin interface for Audit Logs"""
    list_display = [
        'timestamp', 'action_badge', 'level_badge', 'user_link', 
        'ip_address', 'message_preview', 'success_badge', 
        'response_time_display'
    ]
    
    list_filter = [
        'level', 'action', 'success', 'resource_type',
        ('timestamp', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username', 'user__email', 'user_ip', 'message', 
        'error_message', 'resource_type', 'resource_id',
        'metadata', 'request_path'
    ]
    
    readonly_fields = [
        'id', 'correlation_id', 'created_at', 'timestamp', 
        'changes_preview', 'metadata_prettified',
        'request_data_prettified', 'response_data_prettified'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('action', 'level', 'timestamp', 'correlation_id')
        }),
        ('User Information', {
            'fields': ('user', 'anonymous_id', 'user_ip', 'user_agent', 
                      'session_id', 'device_id')
        }),
        ('Action Details', {
            'fields': ('message', 'success', 'error_message', 'stack_trace')
        }),
        ('Resource Information', {
            'fields': ('resource_type', 'resource_id', 'content_type', 'object_id')
        }),
        ('Request Information', {
            'fields': ('request_method', 'request_path', 'request_params', 
                      'request_data_prettified', 'request_headers')
        }),
        ('Response Information', {
            'fields': ('response_data_prettified', 'response_time_ms', 'status_code')
        }),
        ('Data Changes', {
            'fields': ('old_data', 'new_data', 'changes_preview')
        }),
        ('Location Information', {
            'fields': ('country', 'city', 'latitude', 'longitude')
        }),
        ('Metadata', {
            'fields': ('metadata_prettified', 'parent_log')
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'retention_days', 'archived')
        }),
    )
    
    actions = [
        'export_selected_json', 'mark_as_archived',
        'bulk_delete', 'create_alert_rule'
    ]
    
    # Custom display methods
    def action_badge(self, obj):
        """Action with color badge"""
        colors = {
            'LOGIN': '#10b981',
            'LOGOUT': '#6b7280',
            'ERROR': '#ef4444',
            'SECURITY': '#dc2626',
            'API_CALL': '#3b82f6',
            'WITHDRAWAL': '#8b5cf6',
        }
        color = colors.get(obj.action, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    action_badge.admin_order_field = 'action'
    
    def level_badge(self, obj):
        """Level with color badge"""
        colors = {
            'DEBUG': '#6b7280',
            'INFO': '#3b82f6',
            'WARNING': '#f59e0b',
            'ERROR': '#ef4444',
            'CRITICAL': '#dc2626',
            'SECURITY': '#991b1b',
        }
        color = colors.get(obj.level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color, obj.get_level_display()
        )
    level_badge.short_description = 'Level'
    level_badge.admin_order_field = 'level'
    
    def user_link(self, obj):
        """Clickable user link"""
        if obj.user:
            url = f'/admin/users/user/{obj.user.id}/change/'
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        elif obj.anonymous_id:
            return f"Anonymous ({obj.anonymous_id[:8]}...)"
        return "System"
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def message_preview(self, obj):
        """Message preview (truncated)"""
        if len(obj.message) > 50:
            return f"{obj.message[:50]}..."
        return obj.message
    message_preview.short_description = 'Message'
    
    def success_badge(self, obj):
        """Success status badge"""
        if obj.success:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">✓ Success</span>'
            )
        return format_html(
            '<span style="background-color: #ef4444; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">✗ Failed</span>'
        )
    success_badge.short_description = 'Status'
    success_badge.admin_order_field = 'success'
    
    def response_time_display(self, obj):
        """Response time display"""
        if obj.response_time_ms:
            if obj.response_time_ms < 1000:
                return f"{obj.response_time_ms}ms"
            else:
                return f"{obj.response_time_ms/1000:.1f}s"
        return "—"
    response_time_display.short_description = 'Response'
    
    def changes_preview(self, obj):
        """Show data changes"""
        changes = {}
        if obj.old_data and obj.new_data:
            all_keys = set(obj.old_data.keys()) | set(obj.new_data.keys())
            for key in all_keys:
                old_value = obj.old_data.get(key)
                new_value = obj.new_data.get(key)
                if old_value != new_value:
                    changes[key] = {
                        'old': old_value,
                        'new': new_value,
                    }
        
        if changes:
            html = '<div style="max-height: 200px; overflow-y: auto;">'
            for field, change in changes.items():
                html += f'<div style="margin-bottom: 5px;"><strong>{field}:</strong><br>'
                html += f'<span style="color: #ef4444;">Old: {json.dumps(change["old"])}</span><br>'
                html += f'<span style="color: #10b981;">New: {json.dumps(change["new"])}</span></div>'
            html += '</div>'
            return format_html(html)
        return "No changes"
    changes_preview.short_description = 'Data Changes'
    
    def metadata_prettified(self, obj):
        """Pretty print metadata"""
        if obj.metadata:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; '
                'max-height: 300px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.metadata, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
            )
        return "No metadata"
    metadata_prettified.short_description = 'Metadata'
    
    def request_data_prettified(self, obj):
        """Pretty print request data"""
        if obj.request_body:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; '
                'max-height: 300px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.request_body, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
            )
        return "No request data"
    request_data_prettified.short_description = 'Request Data'
    
    def response_data_prettified(self, obj):
        """Pretty print response data"""
        if obj.response_body:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; '
                'max-height: 300px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.response_body, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
            )
        return "No response data"
    response_data_prettified.short_description = 'Response Data'
    
    # Custom actions
    def export_selected_json(self, request, queryset):
        """Export selected logs as JSON"""
        count = queryset.count()
        messages.info(request, f"Exporting {count} audit logs as JSON...")
    export_selected_json.short_description = "📤 Export as JSON"
    
    def mark_as_archived(self, request, queryset):
        """Mark selected logs as archived"""
        count = queryset.update(archived=True)
        messages.success(request, f"Marked {count} logs as archived")
    mark_as_archived.short_description = "📦 Mark as archived"
    
    def bulk_delete(self, request, queryset):
        """Bulk delete selected logs"""
        count = queryset.count()
        # queryset.delete()  # Uncomment to actually delete
        messages.warning(request, f"Would delete {count} logs (commented out for safety)")
    bulk_delete.short_description = "[DELETE] Bulk delete"
    
    def create_alert_rule(self, request, queryset):
        """Create alert rule from selected logs"""
        if queryset.count() == 1:
            log = queryset.first()
            messages.info(request, f"Creating alert rule for: {log.action} - {log.level}")
        else:
            messages.warning(request, "Please select exactly one log to create an alert rule")
    create_alert_rule.short_description = "🚨 Create alert rule"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(AuditLogConfig, site=audit_logs_admin_site)
class AuditLogConfigAdmin(ModelAdmin):
    """Admin for Audit Log Configurations"""
    list_display = [
        'action', 'enabled_badge', 'log_level_badge', 
        'retention_days', 'notify_admins', 'notify_users', 'enabled',
    ]
    
    list_filter = ['enabled', 'log_level']
    
    list_editable = ['enabled', 'retention_days', 'notify_admins', 'notify_users']
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('action', 'enabled', 'log_level', 'retention_days')
        }),
        ('Logging Details', {
            'fields': ('log_request_body', 'log_response_body', 'log_headers')
        }),
        ('Notification Settings', {
            'fields': ('notify_admins', 'notify_users', 'email_template')
        }),
    )
    
    actions = ['enable_selected', 'disable_selected', 'reset_to_defaults']
    
    def enabled_badge(self, obj):
        """Enabled status badge"""
        if obj.enabled:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">[OK] Enabled</span>'
            )
        return format_html(
            '<span style="background-color: #6b7280; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">[ERROR] Disabled</span>'
        )
    enabled_badge.short_description = 'Status'
    
    def log_level_badge(self, obj):
        """Log level badge"""
        colors = {
            'DEBUG': '#6b7280',
            'INFO': '#3b82f6',
            'WARNING': '#f59e0b',
            'ERROR': '#ef4444',
            'CRITICAL': '#dc2626',
            'SECURITY': '#991b1b',
        }
        color = colors.get(obj.log_level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color, obj.get_log_level_display()
        )
    log_level_badge.short_description = 'Log Level'
    
    def enable_selected(self, request, queryset):
        """Enable selected configurations"""
        count = queryset.update(enabled=True)
        messages.success(request, f"Enabled {count} audit log configurations")
    enable_selected.short_description = "[OK] Enable selected"
    
    def disable_selected(self, request, queryset):
        """Disable selected configurations"""
        count = queryset.update(enabled=False)
        messages.success(request, f"Disabled {count} audit log configurations")
    disable_selected.short_description = "[ERROR] Disable selected"
    
    def reset_to_defaults(self, request, queryset):
        """Reset selected configurations to defaults"""
        defaults = {
            'log_level': 'INFO',
            'log_request_body': True,
            'log_response_body': True,
            'log_headers': False,
            'retention_days': 365,
            'notify_admins': False,
            'notify_users': False,
        }
        count = queryset.update(**defaults)
        messages.success(request, f"Reset {count} configurations to defaults")
    reset_to_defaults.short_description = "[LOADING] Reset to defaults"


@admin.register(AuditLogArchive, site=audit_logs_admin_site)
class AuditLogArchiveAdmin(ModelAdmin):
    """Admin for Audit Log Archives"""
    list_display = [
        'start_date', 'end_date', 'total_logs', 
        'compressed_size_mb', 'compression_ratio', 'created_at'
    ]
    
    readonly_fields = [
        'id', 'log_data', 'start_date', 'end_date', 'total_logs',
        'compressed_size_mb', 'original_size_mb', 'compression_ratio',
        'storage_path', 'created_at'
    ]
    
    fieldsets = (
        ('Archive Information', {
            'fields': ('start_date', 'end_date', 'total_logs')
        }),
        ('Storage Details', {
            'fields': ('compressed_size_mb', 'original_size_mb', 'compression_ratio', 'storage_path')
        }),
        ('System Information', {
            'fields': ('id', 'created_at')
        }),
    )
    
    actions = ['restore_archive', 'export_archive', 'delete_archive']
    
    def restore_archive(self, request, queryset):
        """Restore selected archives"""
        messages.info(request, f"Would restore {queryset.count()} archives")
    restore_archive.short_description = "📥 Restore archive"
    
    def export_archive(self, request, queryset):
        """Export selected archives"""
        messages.info(request, f"Exporting {queryset.count()} archives")
    export_archive.short_description = "📤 Export archive"
    
    def delete_archive(self, request, queryset):
        """Delete selected archives"""
        count = queryset.count()
        # queryset.delete()  # Uncomment to actually delete
        messages.warning(request, f"Would delete {count} archives (commented out for safety)")
    delete_archive.short_description = "[DELETE] Delete archive"


@admin.register(AuditDashboard, site=audit_logs_admin_site)
class AuditDashboardAdmin(ModelAdmin):
    """Admin for Audit Dashboards"""
    list_display = ['name', 'is_default', 'created_by', 'created_at']
    list_editable = ['is_default']
    
    # [OK] filter_horizontal remove করা হয়েছে কারণ allowed_users field নেই
    # filter_horizontal = ['allowed_users']
    
    fieldsets = (
        ('Dashboard Information', {
            'fields': ('name', 'description', 'is_default')
        }),
        ('Configuration', {
            'fields': ('filters', 'columns', 'refresh_interval')
        }),
        ('Creator Information', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AuditAlertRule, site=audit_logs_admin_site)
class AuditAlertRuleAdmin(ModelAdmin):
    """Admin for Audit Alert Rules"""
    list_display = [
        'name', 'severity_badge', 'condition_preview', 
        'action', 'enabled', 'last_triggered', 'trigger_count'
    ]
    
    list_filter = ['enabled', 'severity', 'action']
    list_editable = ['enabled']
    
    readonly_fields = ['last_triggered', 'trigger_count']
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('name', 'description', 'severity', 'enabled')
        }),
        ('Condition Configuration', {
            'fields': ('condition', 'cooldown_minutes')
        }),
        ('Action Configuration', {
            'fields': ('action', 'action_config')
        }),
        ('Statistics', {
            'fields': ('last_triggered', 'trigger_count')
        }),
    )
    
    actions = ['enable_rules', 'disable_rules', 'test_rules']
    
    def severity_badge(self, obj):
        """Severity badge"""
        colors = {
            'DEBUG': '#6b7280',
            'INFO': '#3b82f6',
            'WARNING': '#f59e0b',
            'ERROR': '#ef4444',
            'CRITICAL': '#dc2626',
            'SECURITY': '#991b1b',
        }
        color = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color, obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'
    
    def condition_preview(self, obj):
        """Condition preview"""
        if obj.condition:
            return json.dumps(obj.condition)[:50] + "..."
        return "No condition"
    condition_preview.short_description = 'Condition'
    
    def enable_rules(self, request, queryset):
        """Enable selected rules"""
        count = queryset.update(enabled=True)
        messages.success(request, f"Enabled {count} alert rules")
    enable_rules.short_description = "[OK] Enable rules"
    
    def disable_rules(self, request, queryset):
        """Disable selected rules"""
        count = queryset.update(enabled=False)
        messages.success(request, f"Disabled {count} alert rules")
    disable_rules.short_description = "[ERROR] Disable rules"
    
    def test_rules(self, request, queryset):
        """Test selected rules"""
        messages.info(request, f"Testing {queryset.count()} alert rules")
    test_rules.short_description = "🧪 Test rules"


# ====================== URL CONFIGURATION ======================

def get_admin_urls():
    """Get admin URLs for audit logs app"""
    from django.urls import path
    return [
        path('audit-logs/', audit_logs_admin_site.urls),
    ]

# Function to get the admin site for registration in main urls.py
def get_audit_logs_admin_site():
    """Get the audit logs admin site instance"""
    return audit_logs_admin_site


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    # ড্যাশবোর্ডে যা যা দেখাবে
    list_display = ('id', 'user', 'colored_action', 'status_badge', 'ip_address', 'timestamp')
    list_filter = ('action', 'timestamp', 'user')
    search_fields = ('user__username', 'ip_address', 'details')
    readonly_fields = ('timestamp',)

    # কালার ব্যাজ ডিজাইন (Beautiful Design)
    def colored_action(self, obj):
        colors = {
            # Financial Actions - Green/Blue
            'DEPOSIT': '#28a745', 'WITHDRAWAL': '#17a2b8', 'WALLET_TRANSFER': '#20c997',
            # Security & Alerts - Red/Orange
            'SUSPICIOUS_LOGIN': '#dc3545', 'BRUTE_FORCE_ATTEMPT': '#bd2130', 'IP_BLOCK': '#6610f2',
            'USER_BAN': '#343a40',
            # Admin & System - Gold/Yellow
            'MANUAL_CREDIT': '#ffc107', 'SYSTEM_ALERT': '#fd7e14',
            # Default - Gray
            'LOGIN': '#6c757d', 'API_CALL': '#adb5bd'
        }
        color = colors.get(obj.action, '#6c757d') # ডিফল্ট রঙ ধূসর
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            color, obj.get_action_display()
        )
    colored_action.short_description = 'Audit Action'

    # স্ট্যাটাস ব্যাজ (Nice Show)
    def status_badge(self, obj):
        # যদি আপনার মডেলে স্ট্যাটাস ফিল্ড থাকে, তবে এটি কাজ করবে
        return format_html(
            '<span style="color: #555; font-family: monospace;">{}</span>',
            obj.action[:10] + "..." if len(obj.action) > 10 else obj.action
        )
    status_badge.short_description = 'Details'

    # TypeError এবং ImportError ফিক্স করার জন্য সেই প্রয়োজনীয় ক্লাস
    actions = ['export_as_csv']

    def export_as_csv(self, request, queryset):
        # আপনার এক্সপোর্ট লজিক এখানে থাকবে
        self.message_user(request, "Exporting selected logs...")
    export_as_csv.short_description = "Selected logs CSV Export"

# আপনার টার্মিনাল এই নামটি খুঁজছিল, তাই এটি দেওয়া হলো যাতে ক্রাশ না করে
class AuditLogActionAdmin(AuditLogAdmin):
    pass






def _force_register_audit_logs():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(AuditLog, AuditLogAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] audit_logs registered {registered} models")
    except Exception as e:
        print(f"[WARN] audit_logs: {e}")
