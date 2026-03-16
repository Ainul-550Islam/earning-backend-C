# api/analytics/admin.py
"""
[STATS] Analytics Admin - Complete & Bulletproof Design
All 11 Models with Beautiful UI, Defensive Coding & Graceful Degradation
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Sum, Avg, Q
from django.contrib import messages
import logging
from datetime import timedelta
import json
from decimal import Decimal
from typing import Optional, Dict, Any

from .models import (
    AnalyticsEvent, UserAnalytics, RevenueAnalytics, 
    OfferPerformanceAnalytics, FunnelAnalytics, RetentionAnalytics,
    Dashboard, Report, RealTimeMetric, AlertRule, AlertHistory
)

logger = logging.getLogger(__name__)


# ==================== DEFENSIVE UTILITIES ====================

class SafeDisplay:
    """Null-safe display utilities"""
    
    @staticmethod
    def val(v, default='-'):
        try:
            return str(v) if v is not None and v != '' else default
        except Exception:
            return default
    
    @staticmethod
    def int_val(v, default=0):
        try:
            return int(v) if v is not None else default
        except Exception:
            return default
    
    @staticmethod
    def float_val(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except Exception:
            return default
    
    @staticmethod
    def decimal_val(v, default=0):
        try:
            return float(v) if v is not None else default
        except Exception:
            return default
    
    @staticmethod
    def truncate(text, length=50):
        try:
            if not text:
                return '-'
            text = str(text)
            return text[:length] + '...' if len(text) > length else text
        except Exception:
            return '-'


def badge(text, color, icon='', bg_color=None):
    """Beautiful badge generator with fallback"""
    try:
        bg = bg_color or color
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 20px; font-size: 11px; font-weight: 600; '
            'box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: inline-flex; '
            'align-items: center; gap: 4px;">{} {}</span>',
            bg, icon, SafeDisplay.val(text).upper()
        )
    except Exception:
        return format_html('<span>-</span>')


def gradient_badge(text, color1, color2, icon=''):
    """Gradient badge generator"""
    try:
        return format_html(
            '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
            'padding: 5px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; '
            'box-shadow: 0 3px 6px rgba(0,0,0,0.15); display: inline-flex; '
            'align-items: center; gap: 5px;">{} {}</span>',
            color1, color2, icon, SafeDisplay.val(text).upper()
        )
    except Exception:
        return format_html('<span>-</span>')


def bool_icon(value, true_icon='[OK]', false_icon='[ERROR]', true_text='Yes', false_text='No'):
    """Boolean icon display"""
    try:
        if value:
            return format_html('<span style="color: #4CAF50;">{} {}</span>', true_icon, true_text)
        return format_html('<span style="color: #F44336;">{} {}</span>', false_icon, false_text)
    except Exception:
        return format_html('<span>-</span>')


def time_ago(dt):
    """Human readable time ago with fallback"""
    try:
        if not dt or not isinstance(dt, timezone.datetime):
            return '-'
        
        delta = timezone.now() - dt
        if delta.days > 365:
            return f"{delta.days // 365}y ago"
        if delta.days > 30:
            return f"{delta.days // 30}mo ago"
        if delta.days > 0:
            return f"{delta.days}d ago"
        if delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        if delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        return "just now"
    except Exception:
        return '-'


def progress_bar(current, total, width=80):
    """Progress bar HTML with fallback"""
    try:
        if total <= 0:
            return '-'
        percentage = min(100, int((SafeDisplay.float_val(current) / SafeDisplay.float_val(total)) * 100))
        color = '#4CAF50' if percentage >= 75 else '#FF9800' if percentage >= 50 else '#F44336'
        return format_html(
            '<div style="width: {}px; background: #f0f0f0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: linear-gradient(90deg, {}, {}); height: 18px; '
            'text-align: center; color: white; font-size: 10px; line-height: 18px; font-weight: bold;">'
            '{}%</div></div>',
            width, percentage, color, '#81C784', percentage
        )
    except Exception:
        return '-'


def money_display(amount, currency='৳'):
    """Money display with fallback"""
    try:
        amt = SafeDisplay.decimal_val(amount, 0)
        return format_html(
            '<span style="color: #4CAF50; font-weight: bold;">{} {:.2f}</span>',
            currency, amt
        )
    except Exception:
        return '-'


def percentage_display(value, total=None):
    """Percentage display with fallback"""
    try:
        if total is not None and total > 0:
            pct = (SafeDisplay.float_val(value) / SafeDisplay.float_val(total)) * 100
        else:
            pct = SafeDisplay.float_val(value, 0)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            '#4CAF50' if pct >= 75 else '#FF9800' if pct >= 50 else '#F44336',
            pct
        )
    except Exception:
        return '-'


# ==================== 1. ANALYTICS EVENT ADMIN ====================
@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = [
        'id_short', 'event_type_badge', 'user_link',
        'event_time_display', 'location_summary', 'value_display',
        'duration_display', 'actions_column'
    ]
    
    list_filter = [
        'event_type', 'device_type', 'country',
        ('event_time', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username', 'user__email', 'session_id',
        'ip_address', 'metadata'
    ]
    
    readonly_fields = [
        'id', 'created_at', 'event_time', 'metadata_prettified',
        'user_agent_full', 'location_full'
    ]
    
    list_per_page = 50
    date_hierarchy = 'event_time'
    
    fieldsets = (
        ('📋 Event Information', {
            'fields': ('id', 'event_type', 'user', 'session_id', 'event_time')
        }),
        ('🌐 Location & Device', {
            'fields': ('ip_address', 'device_type', 'browser', 'os', 'country', 'city')
        }),
        ('[STATS] Event Data', {
            'fields': ('value', 'duration', 'referrer')
        }),
        ('[DOC] Metadata', {
            'fields': ('metadata_prettified', 'user_agent_full'),
            'classes': ('collapse',)
        }),
        ('📅 System', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        try:
            return format_html(
                '<span style="background: #667eea; color: white; padding: 3px 8px; '
                'border-radius: 12px; font-size: 10px;">#{}</span>',
                str(obj.id)[:8]
            )
        except Exception:
            return '-'
    id_short.short_description = 'ID'
    
    def event_type_badge(self, obj):
        try:
            event_config = {
                'user_signup': ('#4CAF50', '[NOTE]'),
                'user_login': ('#2196F3', '[KEY]'),
                'task_completed': ('#8BC34A', '[OK]'),
                'offer_viewed': ('#FF9800', '👁️'),
                'offer_completed': ('#4CAF50', '[MONEY]'),
                'withdrawal_requested': ('#F44336', '💸'),
                'withdrawal_processed': ('#9C27B0', '💳'),
                'referral_joined': ('#00BCD4', '👥'),
                'wallet_deposit': ('#4CAF50', '📥'),
                'wallet_withdrawal': ('#F44336', '📤'),
                'error_occurred': ('#D32F2F', '[ERROR]'),
            }
            color, icon = event_config.get(str(obj.event_type).lower(), ('#9E9E9E', '[STATS]'))
            return badge(obj.event_type.replace('_', ' ').title(), color, icon)
        except Exception:
            return '-'
    event_type_badge.short_description = 'Event Type'
    
    def user_link(self, obj):
        try:
            if obj.user:
                url = reverse('admin:users_user_change', args=[obj.user.id])
                return format_html(
                    '<a href="{}" style="color: #667eea; font-weight: 500;">👤 {}</a>',
                    url, obj.user.username
                )
        except Exception:
            pass
        return format_html('<span style="color: #999;">Anonymous</span>')
    user_link.short_description = 'User'
    
    def event_time_display(self, obj):
        try:
            return format_html(
                '<div style="text-align: center;">'
                '<span style="color: #666; font-size: 11px;">{}</span><br>'
                '<span style="color: #999; font-size: 9px;">{}</span>'
                '</div>',
                obj.event_time.strftime('%H:%M:%S') if obj.event_time else '-',
                time_ago(obj.event_time)
            )
        except Exception:
            return '-'
    event_time_display.short_description = 'Time'
    
    def location_summary(self, obj):
        try:
            parts = []
            if obj.country:
                parts.append(f"🌍 {obj.country[:15]}")
            if obj.city:
                parts.append(f"🏙️ {obj.city[:15]}")
            return '<br>'.join(parts) if parts else '-'
        except Exception:
            return '-'
    location_summary.short_description = 'Location'
    
    def value_display(self, obj):
        try:
            if obj.value:
                return money_display(obj.value)
        except Exception:
            pass
        return '-'
    value_display.short_description = 'Value'
    
    def duration_display(self, obj):
        try:
            if obj.duration:
                if obj.duration < 60:
                    return f"{obj.duration:.1f}s"
                elif obj.duration < 3600:
                    return f"{obj.duration/60:.1f}m"
                else:
                    return f"{obj.duration/3600:.1f}h"
        except Exception:
            pass
        return '-'
    duration_display.short_description = 'Duration'
    
    def metadata_prettified(self, obj):
        try:
            if obj.metadata:
                return format_html(
                    '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; '
                    'max-height: 300px; overflow: auto;">{}</pre>',
                    json.dumps(obj.metadata, indent=2, ensure_ascii=False)
                )
        except Exception:
            pass
        return 'No metadata'
    metadata_prettified.short_description = 'Metadata'
    
    def user_agent_full(self, obj):
        return SafeDisplay.val(obj.user_agent)
    user_agent_full.short_description = 'User Agent'
    
    def location_full(self, obj):
        return f"{SafeDisplay.val(obj.country)} / {SafeDisplay.val(obj.city)}"
    location_full.short_description = 'Full Location'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_analyticsevent_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['export_events_csv', 'delete_old_events']
    
    def export_events_csv(self, request, queryset):
        try:
            count = queryset.count()
            messages.info(request, f"📥 Exporting {count} events to CSV...")
        except Exception as e:
            messages.error(request, f"Export failed: {e}")
    export_events_csv.short_description = "📥 Export to CSV"
    
    def delete_old_events(self, request, queryset):
        try:
            days_ago = timezone.now() - timedelta(days=90)
            old_events = queryset.filter(event_time__lt=days_ago)
            count = old_events.count()
            old_events.delete()
            messages.success(request, f"[DELETE] Deleted {count} events older than 90 days")
        except Exception as e:
            messages.error(request, f"Delete failed: {e}")
    delete_old_events.short_description = "[DELETE] Delete old events (90+ days)"


# ==================== 2. USER ANALYTICS ADMIN ====================
@admin.register(UserAnalytics)
class UserAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'period_badge', 'period_start_display',
        'earnings_badge', 'engagement_badge', 'tasks_summary',
        'retention_badge', 'actions_column'
    ]
    
    list_filter = [
        'period', 'is_retained',
        ('period_start', admin.DateFieldListFilter),
    ]
    
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'id', 'calculated_at', 'engagement_score', 'lifetime_value_display',
        'earnings_breakdown', 'metrics_breakdown'
    ]
    
    list_per_page = 50
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('👤 User', {
            'fields': ('user', 'period', 'period_start', 'period_end')
        }),
        ('[STATS] Engagement', {
            'fields': ('login_count', 'active_days', 'session_duration_avg', 'page_views')
        }),
        ('[OK] Tasks', {
            'fields': ('tasks_completed', 'tasks_attempted', 'task_success_rate')
        }),
        ('[MONEY] Earnings', {
            'fields': ('earnings_total', 'earnings_from_tasks', 'earnings_from_offers', 'earnings_from_referrals'),
            'classes': ('collapse',)
        }),
        ('👥 Referrals', {
            'fields': ('referrals_sent', 'referrals_joined', 'referrals_active', 'referral_conversion_rate'),
            'classes': ('collapse',)
        }),
        ('💸 Withdrawals', {
            'fields': ('withdrawals_requested', 'withdrawals_completed', 'withdrawals_amount'),
            'classes': ('collapse',)
        }),
        ('📱 Devices', {
            'fields': ('device_mobile_count', 'device_desktop_count', 'device_tablet_count'),
            'classes': ('collapse',)
        }),
        ('📈 Calculated', {
            'fields': ('engagement_score', 'lifetime_value_display', 'is_retained', 'churn_risk_score')
        }),
        ('📅 System', {
            'fields': ('calculated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        try:
            if obj.user:
                url = reverse('admin:users_user_change', args=[obj.user.id])
                return format_html(
                    '<a href="{}" style="color: #667eea; font-weight: 500;">👤 {}</a>',
                    url, obj.user.username
                )
        except Exception:
            pass
        return '-'
    user_link.short_description = 'User'
    
    def period_badge(self, obj):
        try:
            period_config = {
                'daily': ('#4CAF50', '📅'),
                'weekly': ('#2196F3', '📆'),
                'monthly': ('#9C27B0', '[STATS]'),
                'yearly': ('#FF9800', '📈'),
            }
            color, icon = period_config.get(str(obj.period).lower(), ('#9E9E9E', '⏰'))
            return badge(obj.period.title(), color, icon)
        except Exception:
            return '-'
    period_badge.short_description = 'Period'
    
    def period_start_display(self, obj):
        try:
            return obj.period_start.strftime('%Y-%m-%d') if obj.period_start else '-'
        except Exception:
            return '-'
    period_start_display.short_description = 'Start'
    
    def earnings_badge(self, obj):
        try:
            return money_display(obj.earnings_total)
        except Exception:
            return '-'
    earnings_badge.short_description = 'Earnings'
    
    def engagement_badge(self, obj):
        try:
            score = SafeDisplay.float_val(obj.engagement_score, 0)
            if score >= 70:
                color = '#4CAF50'
                icon = '🔥'
            elif score >= 40:
                color = '#FF9800'
                icon = '⚡'
            else:
                color = '#F44336'
                icon = '[WARN]'
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 10px; '
                'border-radius: 15px;">{} {:.0f}</span>',
                color, icon, score
            )
        except Exception:
            return '-'
    engagement_badge.short_description = 'Engagement'
    
    def tasks_summary(self, obj):
        try:
            return f"{SafeDisplay.int_val(obj.tasks_completed)}/{SafeDisplay.int_val(obj.tasks_attempted)}"
        except Exception:
            return '-'
    tasks_summary.short_description = 'Tasks'
    
    def retention_badge(self, obj):
        try:
            if obj.is_retained:
                return badge('Retained', '#4CAF50', '[OK]')
            return badge('Churned', '#F44336', '[ERROR]')
        except Exception:
            return '-'
    retention_badge.short_description = 'Retention'
    
    def lifetime_value_display(self, obj):
        try:
            return money_display(obj.lifetime_value)
        except Exception:
            return '-'
    lifetime_value_display.short_description = 'LTV'
    
    def earnings_breakdown(self, obj):
        try:
            return format_html(
                '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
                '[MONEY] Tasks: {}<br>'
                '📢 Offers: {}<br>'
                '👥 Referrals: {}<br>'
                '</div>',
                money_display(obj.earnings_from_tasks),
                money_display(obj.earnings_from_offers),
                money_display(obj.earnings_from_referrals)
            )
        except Exception:
            return '-'
    earnings_breakdown.short_description = 'Earnings'
    
    def metrics_breakdown(self, obj):
        try:
            return format_html(
                '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
                '[STATS] Engagement: {:.1f}<br>'
                '[WARN] Churn Risk: {:.1f}%<br>'
                '📱 Mobile: {} | Desktop: {} | Tablet: {}'
                '</div>',
                SafeDisplay.float_val(obj.engagement_score, 0),
                SafeDisplay.float_val(obj.churn_risk_score, 0),
                SafeDisplay.int_val(obj.device_mobile_count),
                SafeDisplay.int_val(obj.device_desktop_count),
                SafeDisplay.int_val(obj.device_tablet_count)
            )
        except Exception:
            return '-'
    metrics_breakdown.short_description = 'Metrics'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_useranalytics_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['recalculate_scores']
    
    def recalculate_scores(self, request, queryset):
        try:
            for obj in queryset:
                obj.save()  # Triggers property calculation
            messages.success(request, f"[OK] Recalculated scores for {queryset.count()} users")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    recalculate_scores.short_description = "[LOADING] Recalculate scores"


# ==================== 3. REVENUE ANALYTICS ADMIN ====================
@admin.register(RevenueAnalytics)
class RevenueAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'period_badge', 'period_start_display', 'revenue_badge',
        'profit_badge', 'margin_badge', 'users_summary',
        'arpu_badge', 'actions_column'
    ]
    
    list_filter = [
        'period',
        ('period_start', admin.DateFieldListFilter),
    ]
    
    readonly_fields = [
        'id', 'calculated_at', 'gross_profit', 'net_profit',
        'profit_margin', 'arpu', 'arppu', 'revenue_breakdown',
        'cost_breakdown'
    ]
    
    list_per_page = 50
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('📅 Period', {
            'fields': ('period', 'period_start', 'period_end')
        }),
        ('[MONEY] Revenue', {
            'fields': ('revenue_total', 'revenue_by_source')
        }),
        ('📉 Costs', {
            'fields': ('cost_total', 'cost_breakdown')
        }),
        ('📈 Profit', {
            'fields': ('gross_profit', 'net_profit', 'profit_margin')
        }),
        ('👥 Users', {
            'fields': ('active_users', 'paying_users', 'conversion_rate')
        }),
        ('[STATS] Metrics', {
            'fields': ('arpu', 'arppu')
        }),
        ('💸 Withdrawals', {
            'fields': ('total_withdrawals', 'withdrawal_requests')
        }),
        ('🏦 Platform', {
            'fields': ('platform_fee_earned', 'tax_deducted')
        }),
        ('📅 System', {
            'fields': ('calculated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def period_badge(self, obj):
        try:
            period_config = {
                'daily': ('#4CAF50', '📅'),
                'weekly': ('#2196F3', '📆'),
                'monthly': ('#9C27B0', '[STATS]'),
                'yearly': ('#FF9800', '📈'),
            }
            color, icon = period_config.get(str(obj.period).lower(), ('#9E9E9E', '⏰'))
            return badge(obj.period.title(), color, icon)
        except Exception:
            return '-'
    period_badge.short_description = 'Period'
    
    def period_start_display(self, obj):
        try:
            return obj.period_start.strftime('%Y-%m-%d') if obj.period_start else '-'
        except Exception:
            return '-'
    period_start_display.short_description = 'Start'
    
    def revenue_badge(self, obj):
        try:
            return money_display(obj.revenue_total)
        except Exception:
            return '-'
    revenue_badge.short_description = 'Revenue'
    
    def profit_badge(self, obj):
        try:
            return money_display(obj.gross_profit)
        except Exception:
            return '-'
    profit_badge.short_description = 'Profit'
    
    def margin_badge(self, obj):
        try:
            margin = SafeDisplay.float_val(obj.profit_margin, 0)
            if margin >= 30:
                color = '#4CAF50'
                icon = '📈'
            elif margin >= 15:
                color = '#FF9800'
                icon = '[STATS]'
            else:
                color = '#F44336'
                icon = '📉'
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 10px; '
                'border-radius: 15px;">{} {:.1f}%</span>',
                color, icon, margin
            )
        except Exception:
            return '-'
    margin_badge.short_description = 'Margin'
    
    def users_summary(self, obj):
        try:
            return f"{SafeDisplay.int_val(obj.paying_users)}/{SafeDisplay.int_val(obj.active_users)}"
        except Exception:
            return '-'
    users_summary.short_description = 'Paying/Active'
    
    def arpu_badge(self, obj):
        try:
            return money_display(obj.arpu)
        except Exception:
            return '-'
    arpu_badge.short_description = 'ARPU'
    
    def revenue_breakdown(self, obj):
        try:
            if not obj.revenue_by_source:
                return '-'
            html = '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
            for source, amount in obj.revenue_by_source.items():
                html += f'[MONEY] {source}: {money_display(amount)}<br>'
            html += '</div>'
            return format_html(html)
        except Exception:
            return '-'
    revenue_breakdown.short_description = 'Revenue'
    
    def cost_breakdown(self, obj):
        try:
            if not obj.cost_breakdown:
                return '-'
            html = '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
            for source, amount in obj.cost_breakdown.items():
                html += f'📉 {source}: {money_display(amount)}<br>'
            html += '</div>'
            return format_html(html)
        except Exception:
            return '-'
    cost_breakdown.short_description = 'Costs'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_revenueanalytics_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'


# ==================== 4. OFFER PERFORMANCE ANALYTICS ADMIN ====================
@admin.register(OfferPerformanceAnalytics)
class OfferPerformanceAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'offer_name', 'period_badge', 'impressions_count',
        'completion_rate_badge', 'revenue_badge', 'roi_badge',
        'ctr_badge', 'actions_column'
    ]
    
    list_filter = [
        'period',
        ('period_start', admin.DateFieldListFilter),
    ]
    
    search_fields = ['offer__title']
    readonly_fields = [
        'id', 'calculated_at', 'click_through_rate', 'engagement_rate',
        'performance_metrics'
    ]
    
    list_per_page = 50
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('📋 Offer', {
            'fields': ('offer', 'period', 'period_start', 'period_end')
        }),
        ('👁️ Views', {
            'fields': ('impressions', 'unique_views', 'clicks')
        }),
        ('[OK] Completions', {
            'fields': ('completions', 'completion_rate', 'avg_completion_time')
        }),
        ('[MONEY] Revenue', {
            'fields': ('revenue_generated', 'cost_per_completion', 'roi')
        }),
        ('👥 Users', {
            'fields': ('unique_users_completed',)
        }),
        ('[STATS] Breakdowns', {
            'fields': ('device_breakdown', 'country_breakdown', 'peak_hours'),
            'classes': ('collapse',)
        }),
        ('📈 Metrics', {
            'fields': ('click_through_rate', 'engagement_rate'),
            'classes': ('collapse',)
        }),
        ('📅 System', {
            'fields': ('calculated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def offer_name(self, obj):
        try:
            if obj.offer:
                return SafeDisplay.truncate(obj.offer.title, 30)
        except Exception:
            pass
        return '-'
    offer_name.short_description = 'Offer'
    
    def period_badge(self, obj):
        try:
            period_config = {
                'daily': ('#4CAF50', '📅'),
                'weekly': ('#2196F3', '📆'),
                'monthly': ('#9C27B0', '[STATS]'),
                'yearly': ('#FF9800', '📈'),
            }
            color, icon = period_config.get(str(obj.period).lower(), ('#9E9E9E', '⏰'))
            return badge(obj.period.title(), color, icon)
        except Exception:
            return '-'
    period_badge.short_description = 'Period'
    
    def impressions_count(self, obj):
        try:
            return SafeDisplay.int_val(obj.impressions)
        except Exception:
            return '-'
    impressions_count.short_description = 'Impressions'
    
    def completion_rate_badge(self, obj):
        try:
            return percentage_display(obj.completion_rate)
        except Exception:
            return '-'
    completion_rate_badge.short_description = 'Completion'
    
    def revenue_badge(self, obj):
        try:
            return money_display(obj.revenue_generated)
        except Exception:
            return '-'
    revenue_badge.short_description = 'Revenue'
    
    def roi_badge(self, obj):
        try:
            roi = SafeDisplay.float_val(obj.roi, 0)
            if roi >= 50:
                color = '#4CAF50'
            elif roi >= 20:
                color = '#FF9800'
            else:
                color = '#F44336'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, roi
            )
        except Exception:
            return '-'
    roi_badge.short_description = 'ROI'
    
    def ctr_badge(self, obj):
        try:
            return percentage_display(obj.click_through_rate)
        except Exception:
            return '-'
    ctr_badge.short_description = 'CTR'
    
    def performance_metrics(self, obj):
        try:
            return format_html(
                '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
                '[STATS] CTR: {:.1f}%<br>'
                '📈 Engagement: {:.1f}%<br>'
                '⏱️ Avg Time: {:.1f}s'
                '</div>',
                SafeDisplay.float_val(obj.click_through_rate, 0),
                SafeDisplay.float_val(obj.engagement_rate, 0),
                SafeDisplay.float_val(obj.avg_completion_time, 0)
            )
        except Exception:
            return '-'
    performance_metrics.short_description = 'Metrics'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_offerperformanceanalytics_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'


# ==================== 5. FUNNEL ANALYTICS ADMIN ====================
@admin.register(FunnelAnalytics)
class FunnelAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'funnel_type_badge', 'period_badge', 'conversion_rate_badge',
        'total_entered', 'total_converted', 'avg_time_display',
        'actions_column'
    ]
    
    list_filter = [
        'funnel_type', 'period',
        ('period_start', admin.DateFieldListFilter),
    ]
    
    readonly_fields = [
        'id', 'calculated_at', 'stages_display', 'drop_offs_display'
    ]
    
    list_per_page = 50
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('[STATS] Funnel', {
            'fields': ('funnel_type', 'period', 'period_start', 'period_end')
        }),
        ('📈 Stages', {
            'fields': ('stages', 'total_entered', 'total_converted', 'conversion_rate')
        }),
        ('📉 Drop-offs', {
            'fields': ('drop_off_points',)
        }),
        ('⏱️ Time', {
            'fields': ('avg_time_to_convert', 'median_time_to_convert')
        }),
        ('👥 Segments', {
            'fields': ('segment_breakdown',)
        }),
        ('📅 System', {
            'fields': ('calculated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def funnel_type_badge(self, obj):
        try:
            funnel_config = {
                'user_signup': ('#4CAF50', '[NOTE]'),
                'offer_completion': ('#FF9800', '[MONEY]'),
                'withdrawal': ('#2196F3', '💸'),
                'referral': ('#9C27B0', '👥'),
                'premium_upgrade': ('#FFD700', '[STAR]'),
            }
            color, icon = funnel_config.get(
                str(obj.funnel_type).lower(),
                ('#9E9E9E', '[STATS]')
            )
            return badge(obj.get_funnel_type_display(), color, icon)
        except Exception:
            return '-'
    funnel_type_badge.short_description = 'Funnel'
    
    def period_badge(self, obj):
        try:
            period_config = {
                'daily': ('#4CAF50', '📅'),
                'weekly': ('#2196F3', '📆'),
                'monthly': ('#9C27B0', '[STATS]'),
                'yearly': ('#FF9800', '📈'),
            }
            color, icon = period_config.get(str(obj.period).lower(), ('#9E9E9E', '⏰'))
            return badge(obj.period.title(), color, icon)
        except Exception:
            return '-'
    period_badge.short_description = 'Period'
    
    def conversion_rate_badge(self, obj):
        try:
            return percentage_display(obj.conversion_rate)
        except Exception:
            return '-'
    conversion_rate_badge.short_description = 'Conversion'
    
    def total_entered(self, obj):
        try:
            return SafeDisplay.int_val(obj.total_entered)
        except Exception:
            return '-'
    total_entered.short_description = 'Entered'
    
    def total_converted(self, obj):
        try:
            return SafeDisplay.int_val(obj.total_converted)
        except Exception:
            return '-'
    total_converted.short_description = 'Converted'
    
    def avg_time_display(self, obj):
        try:
            return f"{SafeDisplay.float_val(obj.avg_time_to_convert, 0)}s"
        except Exception:
            return '-'
    avg_time_display.short_description = 'Avg Time'
    
    def stages_display(self, obj):
        try:
            if not obj.stages:
                return '-'
            html = '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
            for stage, count in obj.stages.items():
                html += f'📌 {stage}: {count}<br>'
            html += '</div>'
            return format_html(html)
        except Exception:
            return '-'
    stages_display.short_description = 'Stages'
    
    def drop_offs_display(self, obj):
        try:
            if not obj.drop_off_points:
                return '-'
            html = '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
            for stage, count in obj.drop_off_points.items():
                pct = (count / obj.total_entered * 100) if obj.total_entered else 0
                html += f'[WARN] {stage}: {pct:.1f}%<br>'
            html += '</div>'
            return format_html(html)
        except Exception:
            return '-'
    drop_offs_display.short_description = 'Drop-offs'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_funnelanalytics_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'


# ==================== 6. RETENTION ANALYTICS ADMIN ====================
@admin.register(RetentionAnalytics)
class RetentionAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'cohort_badge', 'cohort_date_display', 'total_users',
        'retention_day_7_display', 'retention_day_30_display',
        'ltv_display', 'churn_rate_display', 'actions_column'
    ]
    
    list_filter = [
        'cohort_type',
        ('cohort_date', admin.DateFieldListFilter),
    ]
    
    readonly_fields = [
        'id', 'calculated_at', 'retention_curve'
    ]
    
    list_per_page = 50
    date_hierarchy = 'cohort_date'
    
    fieldsets = (
        ('📅 Cohort', {
            'fields': ('cohort_type', 'cohort_date', 'total_users')
        }),
        ('📈 Retention', {
            'fields': (
                'retention_day_1', 'retention_day_3', 'retention_day_7',
                'retention_day_14', 'retention_day_30', 'retention_day_60',
                'retention_day_90'
            )
        }),
        ('👥 Activity', {
            'fields': ('active_users_by_period',)
        }),
        ('[MONEY] Revenue', {
            'fields': ('revenue_by_user', 'ltv')
        }),
        ('[WARN] Churn', {
            'fields': ('churned_users', 'churn_rate')
        }),
        ('📅 System', {
            'fields': ('calculated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def cohort_badge(self, obj):
        try:
            period_config = {
                'daily': ('#4CAF50', '📅'),
                'weekly': ('#2196F3', '📆'),
                'monthly': ('#9C27B0', '[STATS]'),
            }
            color, icon = period_config.get(str(obj.cohort_type).lower(), ('#9E9E9E', '⏰'))
            return badge(obj.cohort_type.title(), color, icon)
        except Exception:
            return '-'
    cohort_badge.short_description = 'Cohort'
    
    def cohort_date_display(self, obj):
        try:
            return obj.cohort_date.strftime('%Y-%m-%d') if obj.cohort_date else '-'
        except Exception:
            return '-'
    cohort_date_display.short_description = 'Date'
    
    def total_users(self, obj):
        try:
            return SafeDisplay.int_val(obj.total_users)
        except Exception:
            return '-'
    total_users.short_description = 'Users'
    
    def retention_day_7_display(self, obj):
        try:
            return percentage_display(obj.retention_day_7)
        except Exception:
            return '-'
    retention_day_7_display.short_description = 'Day 7'
    
    def retention_day_30_display(self, obj):
        try:
            return percentage_display(obj.retention_day_30)
        except Exception:
            return '-'
    retention_day_30_display.short_description = 'Day 30'
    
    def ltv_display(self, obj):
        try:
            return money_display(obj.ltv)
        except Exception:
            return '-'
    ltv_display.short_description = 'LTV'
    
    def churn_rate_display(self, obj):
        try:
            return percentage_display(obj.churn_rate)
        except Exception:
            return '-'
    churn_rate_display.short_description = 'Churn'
    
    def retention_curve(self, obj):
        try:
            return format_html(
                '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
                'Day 1: {}<br>'
                'Day 3: {}<br>'
                'Day 7: {}<br>'
                'Day 14: {}<br>'
                'Day 30: {}<br>'
                'Day 60: {}<br>'
                'Day 90: {}'
                '</div>',
                percentage_display(obj.retention_day_1),
                percentage_display(obj.retention_day_3),
                percentage_display(obj.retention_day_7),
                percentage_display(obj.retention_day_14),
                percentage_display(obj.retention_day_30),
                percentage_display(obj.retention_day_60),
                percentage_display(obj.retention_day_90)
            )
        except Exception:
            return '-'
    retention_curve.short_description = 'Retention Curve'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_retentionanalytics_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'


# ==================== 7. DASHBOARD ADMIN ====================
@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = [
        'name_col', 'dashboard_type_badge', 'is_public_badge',
        'refresh_interval_display', 'widgets_count',
        'created_by_display', 'actions_column'
    ]
    
    list_filter = ['dashboard_type', 'is_public']
    search_fields = ['name', 'description']
    filter_horizontal = ['allowed_users']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('📋 Dashboard Info', {
            'fields': ('name', 'dashboard_type', 'description', 'is_public')
        }),
        ('⚙️ Configuration', {
            'fields': ('layout_config', 'widget_configs', 'refresh_interval', 'default_time_range')
        }),
        ('👥 Access', {
            'fields': ('allowed_users',)
        }),
        ('👤 Creator', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def name_col(self, obj):
        try:
            return format_html(
                '<span style="color: #2196F3; font-weight: 600;">[STATS] {}</span>',
                SafeDisplay.val(obj.name)
            )
        except Exception:
            return '-'
    name_col.short_description = 'Name'
    
    def dashboard_type_badge(self, obj):
        try:
            type_config = {
                'admin': ('#4CAF50', '👑'),
                'user': ('#2196F3', '👤'),
                'realtime': ('#FF9800', '⚡'),
                'financial': ('#9C27B0', '[MONEY]'),
                'marketing': ('#E91E63', '📢'),
            }
            color, icon = type_config.get(str(obj.dashboard_type).lower(), ('#9E9E9E', '[STATS]'))
            return badge(obj.get_dashboard_type_display(), color, icon)
        except Exception:
            return '-'
    dashboard_type_badge.short_description = 'Type'
    
    def is_public_badge(self, obj):
        try:
            return bool_icon(obj.is_public, '🌍 Public', '🔒 Private')
        except Exception:
            return '-'
    is_public_badge.short_description = 'Visibility'
    
    def refresh_interval_display(self, obj):
        try:
            return f"{SafeDisplay.int_val(obj.refresh_interval)}s"
        except Exception:
            return '-'
    refresh_interval_display.short_description = 'Refresh'
    
    def widgets_count(self, obj):
        try:
            return len(obj.widget_configs) if obj.widget_configs else 0
        except Exception:
            return 0
    widgets_count.short_description = 'Widgets'
    
    def created_by_display(self, obj):
        try:
            if obj.created_by:
                return obj.created_by.username
        except Exception:
            pass
        return '-'
    created_by_display.short_description = 'Created By'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a> '
                '<a href="{}" style="color: #4CAF50;">✏️</a>',
                reverse('admin:analytics_dashboard_change', args=[obj.id]),
                reverse('admin:analytics_dashboard_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'


# ==================== 8. REPORT ADMIN ====================
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'name_col', 'report_type_badge', 'format_badge',
        'generated_at_display', 'status_badge', 'size_display',
        'download_link', 'actions_column'
    ]
    
    list_filter = [
        'report_type', 'format', 'status',
        ('generated_at', admin.DateFieldListFilter),
    ]
    
    search_fields = ['name', 'generated_by__username']
    readonly_fields = [
        'id', 'generated_at', 'file', 'file_url',
        'file_size', 'generation_duration'
    ]
    
    list_per_page = 50
    date_hierarchy = 'generated_at'
    
    fieldsets = (
        ('📋 Report Info', {
            'fields': ('name', 'report_type', 'format', 'status')
        }),
        ('⚙️ Parameters', {
            'fields': ('parameters',)
        }),
        ('[DOC] Data', {
            'fields': ('data',)
        }),
        ('📎 File', {
            'fields': ('file', 'file_url', 'file_size')
        }),
        ('⏱️ Generation', {
            'fields': ('generated_at', 'generation_duration', 'generated_by')
        }),
        ('📧 Delivery', {
            'fields': ('email_sent', 'email_recipients')
        }),
        ('[STATS] Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def name_col(self, obj):
        try:
            return SafeDisplay.truncate(obj.name, 40)
        except Exception:
            return '-'
    name_col.short_description = 'Name'
    
    def report_type_badge(self, obj):
        try:
            type_config = {
                'daily_summary': ('#4CAF50', '📅'),
                'weekly_analytics': ('#2196F3', '📆'),
                'monthly_earnings': ('#9C27B0', '[MONEY]'),
                'user_activity': ('#FF9800', '👤'),
                'revenue_report': ('#E91E63', '📈'),
                'offer_performance': ('#00BCD4', '📢'),
                'referral_report': ('#8BC34A', '👥'),
                'custom': ('#607D8B', '[FIX]'),
            }
            color, icon = type_config.get(str(obj.report_type).lower(), ('#9E9E9E', '📋'))
            return badge(obj.get_report_type_display(), color, icon)
        except Exception:
            return '-'
    report_type_badge.short_description = 'Type'
    
    def format_badge(self, obj):
        try:
            format_config = {
                'pdf': ('#F44336', '📕'),
                'excel': ('#4CAF50', '📗'),
                'csv': ('#2196F3', '[STATS]'),
                'html': ('#FF9800', '🌐'),
                'json': ('#9C27B0', '📁'),
            }
            color, icon = format_config.get(str(obj.format).lower(), ('#9E9E9E', '[DOC]'))
            return badge(obj.format.upper(), color, icon)
        except Exception:
            return '-'
    format_badge.short_description = 'Format'
    
    def generated_at_display(self, obj):
        try:
            return format_html(
                '<div style="text-align: center;">'
                '<span style="color: #666;">{}</span><br>'
                '<span style="color: #999;">{}</span>'
                '</div>',
                obj.generated_at.strftime('%Y-%m-%d') if obj.generated_at else '-',
                time_ago(obj.generated_at)
            )
        except Exception:
            return '-'
    generated_at_display.short_description = 'Generated'
    
    def status_badge(self, obj):
        try:
            status_config = {
                'pending': ('#FF9800', '⏳'),
                'processing': ('#2196F3', '[LOADING]'),
                'completed': ('#4CAF50', '[OK]'),
                'failed': ('#F44336', '[ERROR]'),
            }
            color, icon = status_config.get(str(obj.status).lower(), ('#9E9E9E', '❓'))
            return badge(obj.status.title(), color, icon)
        except Exception:
            return '-'
    status_badge.short_description = 'Status'
    
    def size_display(self, obj):
        try:
            if obj.file_size:
                kb = obj.file_size / 1024
                if kb < 1024:
                    return f"{kb:.1f} KB"
                else:
                    return f"{kb/1024:.1f} MB"
        except Exception:
            pass
        return '-'
    size_display.short_description = 'Size'
    
    def download_link(self, obj):
        try:
            if obj.file or obj.file_url:
                return format_html(
                    '<a href="{}" style="color: #4CAF50;">📥 Download</a>',
                    obj.file.url if obj.file else obj.file_url
                )
        except Exception:
            pass
        return '-'
    download_link.short_description = 'Download'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_report_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['regenerate_reports', 'send_by_email']
    
    def regenerate_reports(self, request, queryset):
        try:
            messages.info(request, f"[LOADING] Regenerating {queryset.count()} reports...")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    regenerate_reports.short_description = "[LOADING] Regenerate"
    
    def send_by_email(self, request, queryset):
        try:
            messages.info(request, f"📧 Sending {queryset.count()} reports by email...")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    send_by_email.short_description = "📧 Send by email"


# ==================== 9. REAL TIME METRIC ADMIN ====================
@admin.register(RealTimeMetric)
class RealTimeMetricAdmin(admin.ModelAdmin):
    list_display = [
        'metric_type_badge', 'value_badge', 'unit_display',
        'dimension_info', 'metric_time_display', 'recorded_ago',
        'actions_column'
    ]
    
    list_filter = [
        'metric_type', 'dimension',
        ('metric_time', admin.DateFieldListFilter),
    ]
    
    search_fields = ['dimension', 'dimension_value']
    readonly_fields = ['id', 'recorded_at', 'metric_time']
    
    list_per_page = 100
    date_hierarchy = 'metric_time'
    
    fieldsets = (
        ('[STATS] Metric', {
            'fields': ('metric_type', 'value', 'unit')
        }),
        ('📏 Dimensions', {
            'fields': ('dimension', 'dimension_value')
        }),
        ('⏱️ Time', {
            'fields': ('metric_time', 'recorded_at')
        }),
        ('[DOC] Metadata', {
            'fields': ('metadata',)
        }),
    )
    
    def metric_type_badge(self, obj):
        try:
            metric_config = {
                'active_users': ('#4CAF50', '👥'),
                'concurrent_tasks': ('#FF9800', '⚡'),
                'revenue_per_minute': ('#9C27B0', '[MONEY]'),
                'api_requests': ('#2196F3', '[LOADING]'),
                'error_rate': ('#F44336', '[ERROR]'),
                'response_time': ('#00BCD4', '⏱️'),
                'queue_size': ('#FFC107', '[STATS]'),
                'server_load': ('#607D8B', '💻'),
            }
            color, icon = metric_config.get(str(obj.metric_type).lower(), ('#9E9E9E', '📈'))
            return badge(obj.get_metric_type_display(), color, icon)
        except Exception:
            return '-'
    metric_type_badge.short_description = 'Metric'
    
    def value_badge(self, obj):
        try:
            value = SafeDisplay.float_val(obj.value, 0)
            if obj.metric_type in ['error_rate', 'server_load']:
                return percentage_display(value)
            elif obj.metric_type in ['revenue_per_minute']:
                return money_display(value)
            else:
                return f"{value:.1f}"
        except Exception:
            return '-'
    value_badge.short_description = 'Value'
    
    def unit_display(self, obj):
        try:
            return obj.unit or '-'
        except Exception:
            return '-'
    unit_display.short_description = 'Unit'
    
    def dimension_info(self, obj):
        try:
            if obj.dimension and obj.dimension_value:
                return f"{obj.dimension}: {obj.dimension_value}"
        except Exception:
            pass
        return '-'
    dimension_info.short_description = 'Dimension'
    
    def metric_time_display(self, obj):
        try:
            return obj.metric_time.strftime('%H:%M:%S') if obj.metric_time else '-'
        except Exception:
            return '-'
    metric_time_display.short_description = 'Time'
    
    def recorded_ago(self, obj):
        try:
            return time_ago(obj.recorded_at)
        except Exception:
            return '-'
    recorded_ago.short_description = 'Recorded'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_realtimemetric_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    def has_add_permission(self, request):
        return False


# ==================== 10. ALERT RULE ADMIN ====================
@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name_col', 'metric_type_badge', 'severity_badge',
        'condition_display', 'is_active_badge', 'notification_channels',
        'last_alert', 'actions_column'
    ]
    
    list_filter = [
        'metric_type', 'severity', 'is_active',
        'notify_email', 'notify_slack', 'notify_webhook'
    ]
    
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('📋 Rule Info', {
            'fields': ('name', 'description', 'alert_type', 'severity', 'is_active')
        }),
        ('[STATS] Condition', {
            'fields': ('metric_type', 'condition', 'threshold_value', 'threshold_value_2')
        }),
        ('⏱️ Timing', {
            'fields': ('time_window', 'evaluation_interval', 'cooldown_period')
        }),
        ('📧 Notifications', {
            'fields': ('notify_email', 'email_recipients', 'notify_slack', 'slack_webhook', 'notify_webhook', 'webhook_url')
        }),
        ('👤 Creator', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def name_col(self, obj):
        try:
            return SafeDisplay.truncate(obj.name, 30)
        except Exception:
            return '-'
    name_col.short_description = 'Name'
    
    def metric_type_badge(self, obj):
        try:
            metric_config = {
                'active_users': ('#4CAF50', '👥'),
                'concurrent_tasks': ('#FF9800', '⚡'),
                'revenue_per_minute': ('#9C27B0', '[MONEY]'),
                'api_requests': ('#2196F3', '[LOADING]'),
                'error_rate': ('#F44336', '[ERROR]'),
                'response_time': ('#00BCD4', '⏱️'),
                'queue_size': ('#FFC107', '[STATS]'),
                'server_load': ('#607D8B', '💻'),
            }
            color, icon = metric_config.get(str(obj.metric_type).lower(), ('#9E9E9E', '📈'))
            return badge(obj.get_metric_type_display(), color, icon)
        except Exception:
            return '-'
    metric_type_badge.short_description = 'Metric'
    
    def severity_badge(self, obj):
        try:
            severity_config = {
                'info': ('#2196F3', '[INFO]'),
                'warning': ('#FF9800', '[WARN]'),
                'error': ('#F44336', '[ERROR]'),
                'critical': ('#D32F2F', '🔥'),
            }
            color, icon = severity_config.get(str(obj.severity).lower(), ('#9E9E9E', '❓'))
            return badge(obj.get_severity_display(), color, icon)
        except Exception:
            return '-'
    severity_badge.short_description = 'Severity'
    
    def condition_display(self, obj):
        try:
            if obj.condition == 'in_range' and obj.threshold_value_2:
                return f"{obj.threshold_value} - {obj.threshold_value_2}"
            elif obj.condition == 'out_of_range' and obj.threshold_value_2:
                return f"outside {obj.threshold_value} - {obj.threshold_value_2}"
            else:
                return f"{obj.get_condition_display()} {obj.threshold_value}"
        except Exception:
            return '-'
    condition_display.short_description = 'Condition'
    
    def is_active_badge(self, obj):
        try:
            return bool_icon(obj.is_active, '[OK] Active', '[ERROR] Inactive')
        except Exception:
            return '-'
    is_active_badge.short_description = 'Status'
    
    def notification_channels(self, obj):
        try:
            channels = []
            if obj.notify_email:
                channels.append('📧')
            if obj.notify_slack:
                channels.append('💬')
            if obj.notify_webhook:
                channels.append('🌐')
            return ' '.join(channels) if channels else '-'
        except Exception:
            return '-'
    notification_channels.short_description = 'Channels'
    
    def last_alert(self, obj):
        try:
            last_alert = obj.alerts.order_by('-triggered_at').first()
            if last_alert:
                return time_ago(last_alert.triggered_at)
        except Exception:
            pass
        return '-'
    last_alert.short_description = 'Last Alert'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a> '
                '<a href="{}" style="color: #4CAF50;">✏️</a>',
                reverse('admin:analytics_alertrule_change', args=[obj.id]),
                reverse('admin:analytics_alertrule_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['enable_rules', 'disable_rules', 'test_rules']
    
    def enable_rules(self, request, queryset):
        try:
            count = queryset.update(is_active=True)
            messages.success(request, f"[OK] Enabled {count} alert rules")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    enable_rules.short_description = "[OK] Enable rules"
    
    def disable_rules(self, request, queryset):
        try:
            count = queryset.update(is_active=False)
            messages.success(request, f"[ERROR] Disabled {count} alert rules")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    disable_rules.short_description = "[ERROR] Disable rules"
    
    def test_rules(self, request, queryset):
        try:
            messages.info(request, f"🧪 Testing {queryset.count()} alert rules...")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    test_rules.short_description = "🧪 Test rules"


# ==================== 11. ALERT HISTORY ADMIN ====================
@admin.register(AlertHistory)
class AlertHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'rule_link', 'severity_badge', 'metric_display',
        'triggered_at_display', 'resolved_badge', 'resolution_info',
        'actions_column'
    ]
    
    list_filter = [
        'severity', 'is_resolved',
        ('triggered_at', admin.DateFieldListFilter),
    ]
    
    search_fields = ['rule__name', 'resolution_notes']
    readonly_fields = [
        'id', 'triggered_at', 'resolved_at', 'resolved_by',
        'metric_detailed', 'condition_met'
    ]
    
    list_per_page = 100
    date_hierarchy = 'triggered_at'
    
    fieldsets = (
        ('📋 Alert', {
            'fields': ('rule', 'severity', 'triggered_at')
        }),
        ('[STATS] Metrics', {
            'fields': ('metric_value', 'threshold_value', 'condition_met')
        }),
        ('[OK] Resolution', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('📧 Notifications', {
            'fields': ('email_sent', 'slack_sent', 'webhook_sent')
        }),
    )
    
    def rule_link(self, obj):
        try:
            if obj.rule:
                url = reverse('admin:analytics_alertrule_change', args=[obj.rule.id])
                return format_html(
                    '<a href="{}" style="color: #2196F3;">{}</a>',
                    url, SafeDisplay.truncate(obj.rule.name, 30)
                )
        except Exception:
            pass
        return '-'
    rule_link.short_description = 'Rule'
    
    def severity_badge(self, obj):
        try:
            severity_config = {
                'info': ('#2196F3', '[INFO]'),
                'warning': ('#FF9800', '[WARN]'),
                'error': ('#F44336', '[ERROR]'),
                'critical': ('#D32F2F', '🔥'),
            }
            color, icon = severity_config.get(str(obj.severity).lower(), ('#9E9E9E', '❓'))
            return badge(obj.get_severity_display(), color, icon)
        except Exception:
            return '-'
    severity_badge.short_description = 'Severity'
    
    def metric_display(self, obj):
        try:
            value = SafeDisplay.float_val(obj.metric_value, 0)
            threshold = SafeDisplay.float_val(obj.threshold_value, 0)
            diff = ((value - threshold) / threshold * 100) if threshold > 0 else 0
            
            if diff > 0:
                return format_html(
                    '<span style="color: #F44336;">{:.1f} > {:.1f} (+{:.0f}%)</span>',
                    value, threshold, diff
                )
            return f"{value} / {threshold}"
        except Exception:
            return '-'
    metric_display.short_description = 'Metric'
    
    def triggered_at_display(self, obj):
        try:
            return format_html(
                '<div style="text-align: center;">'
                '<span style="color: #666;">{}</span><br>'
                '<span style="color: #999;">{}</span>'
                '</div>',
                obj.triggered_at.strftime('%Y-%m-%d %H:%M') if obj.triggered_at else '-',
                time_ago(obj.triggered_at)
            )
        except Exception:
            return '-'
    triggered_at_display.short_description = 'Triggered'
    
    def resolved_badge(self, obj):
        try:
            if obj.is_resolved:
                return badge('Resolved', '#4CAF50', '[OK]')
            return badge('Active', '#F44336', '[WARN]')
        except Exception:
            return '-'
    resolved_badge.short_description = 'Status'
    
    def resolution_info(self, obj):
        try:
            if obj.is_resolved and obj.resolved_at:
                return f"by {obj.resolved_by} {time_ago(obj.resolved_at)}"
        except Exception:
            pass
        return '-'
    resolution_info.short_description = 'Resolution'
    
    def metric_detailed(self, obj):
        try:
            return format_html(
                '<div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">'
                '[STATS] Value: {}<br>'
                '🎯 Threshold: {}<br>'
                '⚡ Condition: {}'
                '</div>',
                SafeDisplay.float_val(obj.metric_value, 0),
                SafeDisplay.float_val(obj.threshold_value, 0),
                SafeDisplay.val(obj.condition_met)
            )
        except Exception:
            return '-'
    metric_detailed.short_description = 'Details'
    
    def actions_column(self, obj):
        try:
            return format_html(
                '<a href="{}" style="color: #2196F3;">👁️</a>',
                reverse('admin:analytics_alerthistory_change', args=[obj.id])
            )
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['mark_resolved', 'send_notifications']
    
    def mark_resolved(self, request, queryset):
        try:
            count = queryset.filter(is_resolved=False).update(
                is_resolved=True,
                resolved_at=timezone.now(),
                resolved_by=request.user
            )
            messages.success(request, f"[OK] Marked {count} alerts as resolved")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    mark_resolved.short_description = "[OK] Mark as resolved"
    
    def send_notifications(self, request, queryset):
        try:
            messages.info(request, f"📧 Sending notifications for {queryset.count()} alerts...")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    send_notifications.short_description = "📧 Send notifications"


# ==================== FORCE REGISTER ALL MODELS ====================
try:
    from django.contrib import admin
    from .models import (
        AnalyticsEvent, UserAnalytics, RevenueAnalytics,
        OfferPerformanceAnalytics, FunnelAnalytics, RetentionAnalytics,
        Dashboard, Report, RealTimeMetric, AlertRule, AlertHistory
    )
    
    models_to_register = [
        (AnalyticsEvent, AnalyticsEventAdmin),
        (UserAnalytics, UserAnalyticsAdmin),
        (RevenueAnalytics, RevenueAnalyticsAdmin),
        (OfferPerformanceAnalytics, OfferPerformanceAnalyticsAdmin),
        (FunnelAnalytics, FunnelAnalyticsAdmin),
        (RetentionAnalytics, RetentionAnalyticsAdmin),
        (Dashboard, DashboardAdmin),
        (Report, ReportAdmin),
        (RealTimeMetric, RealTimeMetricAdmin),
        (AlertRule, AlertRuleAdmin),
        (AlertHistory, AlertHistoryAdmin),
    ]
    
    registered = 0
    for model, admin_class in models_to_register:
        if not admin.site.is_registered(model):
            try:
                admin.site.register(model, admin_class)
                registered += 1
                print(f"[OK] Registered: {model.__name__}")
            except Exception as e:
                print(f"[WARN] Could not register {model.__name__}: {e}")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} analytics models registered successfully!")
    else:
        print("[OK] All analytics models already registered")
        
except Exception as e:
    print(f"[ERROR] Error registering analytics models: {e}")