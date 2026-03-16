# api/rate_limit/admin.py
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F, Max, Case, When
from django.core.exceptions import ValidationError
from django import forms
from django.contrib.auth.hashers import make_password
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import transaction
import json
import csv
from datetime import datetime, timedelta
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .models import RateLimitConfig, RateLimitLog, UserRateLimitProfile


# Custom Admin Site with Rate Limit Analytics
class RateLimitAdminSite(admin.AdminSite):
    site_header = "Rate Limit Management System"
    site_title = "Rate Limit Admin"
    index_title = "Dashboard Overview"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('rate-limit-analytics/', self.admin_view(self.rate_limit_analytics_view), name='rate_limit_analytics'),
            path('export-rate-logs/', self.admin_view(self.export_rate_logs), name='export_rate_logs'),
            path('bulk-activate-configs/', self.admin_view(self.bulk_activate_configs), name='bulk_activate_configs'),
            path('simulate-impact/<int:config_id>/', self.admin_view(self.simulate_impact), name='simulate_impact'),
            path('clear-old-logs/', self.admin_view(self.clear_old_logs), name='clear_old_logs'),
            path('generate-report/', self.admin_view(self.generate_report), name='generate_report'),
            path('api/rate-stats/', self.admin_view(self.rate_stats_api), name='rate_stats_api'),
        ]
        return custom_urls + urls
    
    def rate_limit_analytics_view(self, request):
        now = timezone.now()
        twentyfour_hours_ago = now - timedelta(hours=24)
        
        # Core Statistics
        total_configs = RateLimitConfig.objects.count()
        active_configs = RateLimitConfig.objects.filter(is_active=True).count()
        total_logs = RateLimitLog.objects.count()
        recent_logs = RateLimitLog.objects.filter(timestamp__gte=twentyfour_hours_ago).count()
        
        # Block Rate Analysis
        blocked_logs = RateLimitLog.objects.filter(status='blocked', timestamp__gte=twentyfour_hours_ago).count()
        allowed_logs = RateLimitLog.objects.filter(status='allowed', timestamp__gte=twentyfour_hours_ago).count()
        total_recent = blocked_logs + allowed_logs
        block_rate = (blocked_logs / total_recent * 100) if total_recent > 0 else 0
        
        # Top Offenders
        top_offenders = RateLimitLog.objects.filter(
            status='blocked',
            timestamp__gte=twentyfour_hours_ago
        ).values('ip_address').annotate(
            block_count=Count('id'),
            last_blocked=Max('timestamp')
        ).order_by('-block_count')[:10]
        
        # Most Blocked Endpoints
        blocked_endpoints = RateLimitLog.objects.filter(
            status='blocked',
            timestamp__gte=twentyfour_hours_ago
        ).values('endpoint').annotate(
            block_count=Count('id')
        ).order_by('-block_count')[:10]
        
        # Config Performance
        config_performance = RateLimitConfig.objects.annotate(
            hit_rate=Avg(
                Case(
                    When(ratelimitlog__status='allowed', then=100),
                    When(ratelimitlog__status='blocked', then=0),
                    default=0,
                    output_field=models.FloatField()
                )
            )
        ).order_by('-hit_rate')[:10]
        
        context = {
            'total_configs': total_configs,
            'active_configs': active_configs,
            'total_logs': total_logs,
            'recent_logs': recent_logs,
            'blocked_logs': blocked_logs,
            'block_rate': round(block_rate, 2),
            'top_offenders': top_offenders,
            'blocked_endpoints': blocked_endpoints,
            'config_performance': config_performance,
            'time_range': 'Last 24 Hours',
        }
        
        return render(request, 'admin/rate_limit_analytics.html', context)
    
    def export_rate_logs(self, request):
        format_type = request.GET.get('format', 'csv')
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="rate_limit_logs.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Timestamp', 'IP Address', 'User', 'Endpoint', 
                           'Method', 'Status', 'Request Count', 'Config', 'Task ID'])
            
            logs = RateLimitLog.objects.all().order_by('-timestamp')[:1000]
            for log in logs:
                writer.writerow([
                    log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    log.ip_address,
                    log.user.username if log.user else 'Anonymous',
                    log.endpoint,
                    log.request_method,
                    log.get_status_display(),
                    log.requests_count,
                    log.config.name if log.config else 'N/A',
                    log.task_id or 'N/A'
                ])
            
            return response
        
        return JsonResponse({'error': 'Invalid format'}, status=400)
    
    def bulk_activate_configs(self, request):
        if request.method == 'POST':
            config_ids = json.loads(request.body).get('config_ids', [])
            
            activated = 0
            for config_id in config_ids:
                try:
                    config = RateLimitConfig.objects.get(id=config_id)
                    config.is_active = True
                    config.save()
                    activated += 1
                except RateLimitConfig.DoesNotExist:
                    continue
            
            return JsonResponse({'activated': activated})
        
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    def simulate_impact(self, request, config_id):
        try:
            config = RateLimitConfig.objects.get(id=config_id)
            simulation = config.simulate_impact(hours=24)
            
            return JsonResponse({
                'config_name': config.name,
                'simulation': simulation
            })
            
        except RateLimitConfig.DoesNotExist:
            return JsonResponse({'error': 'Config not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def clear_old_logs(self, request):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        deleted_count = RateLimitLog.objects.filter(
            timestamp__lt=thirty_days_ago
        ).delete()[0]
        
        messages.success(request, f'{deleted_count} old logs cleared successfully.')
        return redirect('admin:rate_limit_analytics')
    
    def generate_report(self, request):
        buffer = io.BytesIO()
        
        # Create PDF
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph("Rate Limit Analysis Report", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Date
        date_text = Paragraph(f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        elements.append(date_text)
        elements.append(Spacer(1, 24))
        
        # Statistics Table
        now = timezone.now()
        twentyfour_hours_ago = now - timedelta(hours=24)
        
        data = [
            ['Metric', 'Value'],
            ['Total Configurations', str(RateLimitConfig.objects.count())],
            ['Active Configurations', str(RateLimitConfig.objects.filter(is_active=True).count())],
            ['Total Logs (24h)', str(RateLimitLog.objects.filter(timestamp__gte=twentyfour_hours_ago).count())],
            ['Blocked Requests (24h)', str(RateLimitLog.objects.filter(status='blocked', timestamp__gte=twentyfour_hours_ago).count())],
            ['Top Offender IP', RateLimitLog.objects.filter(status='blocked').values('ip_address').annotate(count=Count('id')).order_by('-count').first()['ip_address'] if RateLimitLog.objects.filter(status='blocked').exists() else 'N/A'],
        ]
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Return PDF
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="rate_limit_report.pdf"'
        return response
    
    def rate_stats_api(self, request):
        now = timezone.now()
        twentyfour_hours_ago = now - timedelta(hours=24)
        
        stats = {
            "total_configs": RateLimitConfig.objects.count(),
            "active_configs": RateLimitConfig.objects.filter(is_active=True).count(),
            "logs_24h": RateLimitLog.objects.filter(timestamp__gte=twentyfour_hours_ago).count(),
            "blocked_24h": RateLimitLog.objects.filter(status='blocked', timestamp__gte=twentyfour_hours_ago).count(),
            "top_endpoints": list(RateLimitLog.objects.filter(timestamp__gte=twentyfour_hours_ago).values('endpoint').annotate(count=Count('id')).order_by('-count')[:5]),
        }
        
        return JsonResponse(stats)


# Register custom admin site
admin_site = RateLimitAdminSite(name='rate_limit_admin')


# Custom forms
class RateLimitConfigForm(forms.ModelForm):
    class Meta:
        model = RateLimitConfig
        fields = '__all__'
        widgets = {
            'whitelist': forms.Textarea(attrs={'rows': 3}),
            'blacklist': forms.Textarea(attrs={'rows': 3}),
            'bypass_keys': forms.Textarea(attrs={'rows': 3}),
        }


class RateLimitLogForm(forms.ModelForm):
    class Meta:
        model = RateLimitLog
        fields = '__all__'
        widgets = {
            'user_agent': forms.Textarea(attrs={'rows': 2}),
        }


# Custom filters
class RateLimitTypeFilter(admin.SimpleListFilter):
    title = 'Rate Limit Type'
    parameter_name = 'rate_limit_type'
    
    def lookups(self, request, model_admin):
        return [
            ('user', 'User-based'),
            ('ip', 'IP-based'),
            ('endpoint', 'Endpoint-based'),
            ('global', 'Global'),
            ('referral', 'Referral-based'),
            ('task', 'Task-based'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(rate_limit_type=self.value())
        return queryset


class TimeUnitFilter(admin.SimpleListFilter):
    title = 'Time Unit'
    parameter_name = 'time_unit'
    
    def lookups(self, request, model_admin):
        return [
            ('second', 'Second'),
            ('minute', 'Minute'),
            ('hour', 'Hour'),
            ('day', 'Day'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(time_unit=self.value())
        return queryset


class StatusFilter(admin.SimpleListFilter):
    title = 'Log Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('allowed', 'Allowed'),
            ('blocked', 'Blocked'),
            ('exceeded', 'Exceeded'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class ActiveConfigFilter(admin.SimpleListFilter):
    title = 'Config Status'
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return [
            ('active', 'Active Configs'),
            ('inactive', 'Inactive Configs'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset


# RateLimitConfig Admin
@admin.register(RateLimitConfig, site=admin_site)
class RateLimitConfigAdmin(ModelAdmin):
    form = RateLimitConfigForm
    list_display = ('name', 'rate_limit_type_display', 'requests_per_unit',
                   'time_window_display', 'is_active', 'hit_count',
                   'block_count', 'api_health_display', 'created_at_display')
    list_filter = (RateLimitTypeFilter, TimeUnitFilter, ActiveConfigFilter)
    search_fields = ('name', 'endpoint', 'ip_address', 'task_type', 'offer_wall')
    readonly_fields = ('hit_count', 'block_count', 'last_hit_at', 'created_at', 'updated_at')
    list_editable = ('is_active',)
    list_per_page = 30
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'rate_limit_type', 'is_active')
        }),
        ('Rate Limits', {
            'fields': ('requests_per_unit', 'time_unit', 'time_value')
        }),
        ('Target Specification', {
            'fields': ('user', 'ip_address', 'endpoint', 'task_type', 'offer_wall'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('whitelist', 'blacklist', 'bypass_keys'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('hit_count', 'block_count', 'last_hit_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def rate_limit_type_display(self, obj):
        type_colors = {
            'user': 'green',
            'ip': 'blue',
            'endpoint': 'purple',
            'global': 'orange',
            'referral': 'teal',
            'task': 'brown',
        }
        color = type_colors.get(obj.rate_limit_type, 'gray')
        
        type_icons = {
            'user': '👤',
            'ip': '🌐',
            'endpoint': '🔗',
            'global': '🌍',
            'referral': '👥',
            'task': '📋',
        }
        icon = type_icons.get(obj.rate_limit_type, '⚙️')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_rate_limit_type_display()
        )
    rate_limit_type_display.short_description = 'Type'
    
    def time_window_display(self, obj):
        return f"{obj.time_value} {obj.get_time_unit_display()}(s)"
    time_window_display.short_description = 'Time Window'
    
    def api_health_display(self, obj):
        health = obj.get_api_health()
        if health >= 80:
            color = 'green'
            emoji = '[OK]'
        elif health >= 60:
            color = 'orange'
            emoji = '[WARN]'
        else:
            color = 'red'
            emoji = '[ERROR]'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, emoji, health
        )
    api_health_display.short_description = 'API Health'
    
    def created_at_display(self, obj):
        return timezone.localtime(obj.created_at).strftime('%Y-%m-%d')
    created_at_display.short_description = 'Created'
    
    actions = ['activate_configs', 'deactivate_configs', 'reset_statistics', 'export_configs']
    
    def activate_configs(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} rate limit configurations activated.')
    activate_configs.short_description = "Activate selected configs"
    
    def reset_statistics(self, request, queryset):
        updated = queryset.update(hit_count=0, block_count=0, last_hit_at=None)
        self.message_user(request, f'{updated} configurations statistics reset.')
    reset_statistics.short_description = "Reset statistics"


# RateLimitLog Admin
@admin.register(RateLimitLog, site=admin_site)
class RateLimitLogAdmin(ModelAdmin):
    form = RateLimitLogForm
    list_display = ('timestamp_display', 'ip_address', 'user_display', 
                   'endpoint_short', 'status_display', 'config_display',
                   'requests_count_display', 'suspicion_score_display')
    list_filter = (StatusFilter, 'timestamp', 'request_method')
    search_fields = ('ip_address', 'endpoint', 'user__username', 'task_id', 'offer_id')
    readonly_fields = ('timestamp', 'created_at', 'suspicion_score')
    list_per_page = 50
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'ip_address', 'endpoint', 'request_method', 'user_agent')
        }),
        ('Rate Limit Details', {
            'fields': ('config', 'status', 'requests_count')
        }),
        ('Earning App Context', {
            'fields': ('task_id', 'offer_id', 'referral_code'),
            'classes': ('collapse',)
        }),
        ('Security Analysis', {
            'fields': ('suspicion_score',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def timestamp_display(self, obj):
        return timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S')
    timestamp_display.short_description = 'Timestamp'
    
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<span style="color: blue; font-weight: bold;">{}</span>',
                obj.user.username
            )
        return format_html(
            '<span style="color: gray; font-style: italic;">Anonymous</span>'
        )
    user_display.short_description = 'User'
    
    def endpoint_short(self, obj):
        if len(obj.endpoint) > 50:
            return obj.endpoint[:50] + '...'
        return obj.endpoint
    endpoint_short.short_description = 'Endpoint'
    
    def status_display(self, obj):
        colors = {
            'allowed': 'green',
            'blocked': 'red',
            'exceeded': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        
        icons = {
            'allowed': '[OK]',
            'blocked': '⛔',
            'exceeded': '[WARN]',
        }
        icon = icons.get(obj.status, '❓')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def config_display(self, obj):
        if obj.config:
            return format_html(
                '<span style="color: purple;">{}</span>',
                obj.config.name
            )
        return format_html(
            '<span style="color: gray;">No Config</span>'
        )
    config_display.short_description = 'Config'
    
    def requests_count_display(self, obj):
        if obj.requests_count > 50:
            color = 'red'
        elif obj.requests_count > 20:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.requests_count
        )
    requests_count_display.short_description = 'Requests'
    
    def suspicion_score_display(self, obj):
        if obj.suspicion_score >= 70:
            return format_html(
                '<span style="color: red; font-weight: bold;">[WARN] {}</span>',
                obj.suspicion_score
            )
        elif obj.suspicion_score >= 40:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{}</span>',
                obj.suspicion_score
            )
        return format_html(
            '<span style="color: green;">{}</span>',
            obj.suspicion_score
        )
    suspicion_score_display.short_description = 'Suspicion'
    
    actions = ['export_selected_logs', 'mark_as_reviewed', 'add_to_blacklist']
    
    def export_selected_logs(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_rate_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Timestamp', 'IP', 'User', 'Endpoint', 'Status', 'Suspicion'])
        
        for log in queryset:
            writer.writerow([
                log.id,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.ip_address,
                log.user.username if log.user else 'Anonymous',
                log.endpoint,
                log.get_status_display(),
                log.suspicion_score
            ])
        
        return response
    export_selected_logs.short_description = "Export selected logs"


# UserRateLimitProfile Admin
@admin.register(UserRateLimitProfile, site=admin_site)
class UserRateLimitProfileAdmin(ModelAdmin):
    list_display = ('user', 'is_premium_display', 'total_requests_display',
                   'blocked_requests_display', 'block_rate_display',
                   'api_health_score_display', 'suspicion_score_display',
                   'last_request_display')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'last_request_at')
    list_per_page = 30
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Premium Status', {
            'fields': ('is_premium', 'premium_until')
        }),
        ('Custom Limits', {
            'fields': ('custom_daily_limit', 'custom_hourly_limit'),
            'classes': ('collapse',)
        }),
        ('Current Usage', {
            'fields': ('current_usage', 'daily_usage', 'hourly_usage'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_requests', 'blocked_requests', 'last_request_at')
        }),
        ('Health Metrics', {
            'fields': ('api_health_score', 'endpoint_health'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('suspicion_score',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_premium_display(self, obj):
        if obj.is_premium:
            if obj.premium_until and timezone.now() > obj.premium_until:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">[WARN] Expired</span>'
                )
            return format_html(
                '<span style="color: gold; font-weight: bold;">[STAR] Premium</span>'
            )
        return format_html(
            '<span style="color: gray;">Standard</span>'
        )
    is_premium_display.short_description = 'Premium'
    
    def total_requests_display(self, obj):
        return format_html(
            '<span style="color: blue; font-weight: bold;">{:,}</span>',
            obj.total_requests
        )
    total_requests_display.short_description = 'Total Requests'
    
    def blocked_requests_display(self, obj):
        return format_html(
            '<span style="color: red; font-weight: bold;">{}</span>',
            obj.blocked_requests
        )
    blocked_requests_display.short_description = 'Blocked'
    
    def block_rate_display(self, obj):
        if obj.total_requests > 0:
            rate = (obj.blocked_requests / obj.total_requests) * 100
            if rate > 30:
                color = 'red'
            elif rate > 15:
                color = 'orange'
            else:
                color = 'green'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, rate
            )
        return format_html(
            '<span style="color: gray;">0%</span>'
        )
    block_rate_display.short_description = 'Block Rate'
    
    def api_health_score_display(self, obj):
        if obj.api_health_score >= 80:
            color = 'green'
            emoji = '[OK]'
        elif obj.api_health_score >= 60:
            color = 'orange'
            emoji = '[WARN]'
        else:
            color = 'red'
            emoji = '[ERROR]'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, emoji, obj.api_health_score
        )
    api_health_score_display.short_description = 'API Health'
    
    def suspicion_score_display(self, obj):
        if obj.suspicion_score >= 70:
            return format_html(
                '<span style="color: red; font-weight: bold;">[WARN] {}</span>',
                obj.suspicion_score
            )
        elif obj.suspicion_score >= 40:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{}</span>',
                obj.suspicion_score
            )
        return format_html(
            '<span style="color: green;">{}</span>',
            obj.suspicion_score
        )
    suspicion_score_display.short_description = 'Suspicion'
    
    def last_request_display(self, obj):
        if obj.last_request_at:
            return timezone.localtime(obj.last_request_at).strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_request_display.short_description = 'Last Request'
    
    actions = ['upgrade_to_premium', 'downgrade_to_standard', 'reset_usage_stats']
    
    def upgrade_to_premium(self, request, queryset):
        updated = queryset.update(
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=30)
        )
        self.message_user(request, f'{updated} users upgraded to premium.')
    upgrade_to_premium.short_description = "Upgrade to premium (30 days)"
    
    def reset_usage_stats(self, request, queryset):
        updated = queryset.update(
            current_usage=0,
            daily_usage=0,
            hourly_usage=0,
            api_health_score=100,
            suspicion_score=0
        )
        self.message_user(request, f'{updated} user usage stats reset.')
    reset_usage_stats.short_description = "Reset usage statistics"
    
    
    
    
    # api/rate_limit/admin.py - একদম শেষে এই কোড যোগ করুন

# ==================== FORCE REGISTER IN DEFAULT ADMIN ====================
from django.contrib import admin

try:
    from .models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
    from .admin import RateLimitConfigAdmin, RateLimitLogAdmin, UserRateLimitProfileAdmin
    
    registered = 0
    
    # Register RateLimitConfig
    if not admin.site.is_registered(RateLimitConfig):
        admin.site.register(RateLimitConfig, RateLimitConfigAdmin)
        registered += 1
        print("[OK] Registered: RateLimitConfig in default admin")
    
    # Register RateLimitLog
    if not admin.site.is_registered(RateLimitLog):
        admin.site.register(RateLimitLog, RateLimitLogAdmin)
        registered += 1
        print("[OK] Registered: RateLimitLog in default admin")
    
    # Register UserRateLimitProfile
    if not admin.site.is_registered(UserRateLimitProfile):
        admin.site.register(UserRateLimitProfile, UserRateLimitProfileAdmin)
        registered += 1
        print("[OK] Registered: UserRateLimitProfile in default admin")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} rate_limit models registered in default admin")
    else:
        print("[OK] All rate_limit models already registered")
        
except Exception as e:
    print(f"[ERROR] Error registering rate_limit models: {e}")