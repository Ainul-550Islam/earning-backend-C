# api/ad_networks/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import json
import logging
from datetime import datetime
from django.contrib import admin, messages
from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    BlacklistedIP, FraudDetectionRule, KnownBadIP
)


# ==================== Inline Admin Classes ====================

class OfferInline(admin.TabularInline):
    model = Offer
    extra = 0
    fields = ['title', 'reward_amount', 'status', 'is_featured', 'total_conversions']
    readonly_fields = ['total_conversions']
    can_delete = False
    show_change_link = True
    max_num = 5


class NetworkStatisticInline(admin.TabularInline):
    model = NetworkStatistic
    extra = 0
    fields = ['date', 'clicks', 'conversions', 'payout', 'commission']
    readonly_fields = ['date', 'clicks', 'conversions', 'payout', 'commission']
    can_delete = False
    max_num = 7


# ==================== Ad Network Admin ====================

@admin.register(AdNetwork)
class AdNetworkAdmin(admin.ModelAdmin):
    list_display = [
        'network_badge',
        'category_badge',
        'status_indicator',
        'performance_score',
        'financial_summary',
        'features_display',
        'last_sync_display',
        'priority',           # ডাটাবেস ফিল্ড
        'trust_score',        # ডাটাবেস ফিল্ড
        'total_payout',       # ডাটাবেস ফিল্ড
        'last_sync',
        'name',     
        'is_active', 
        'created_at'
    ]
    
    list_filter = [
        'category',
        'is_active',
        'is_testing',
        'country_support',
        'supports_postback',
        'supports_surveys',
        'supports_video',
        'is_verified',
    ]
    
    search_fields = [
        'name',
        'network_type',
        'publisher_id',
        'api_key',
        'description'
    ]
    
    readonly_fields = [
        'network_overview',
        'performance_metrics',
        'api_configuration_status',
        'feature_support_matrix',
        'financial_analytics',
        'recent_activity',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('🎯 Network Overview', {
            'fields': ('network_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Basic Information', {
            'fields': (
                'name',
                'network_type',
                'category',
                'description',
                ('website', 'dashboard_url'),
                ('logo', 'logo_url'),
                'banner_url',
            ),
            'classes': ('collapse',)
        }),
        
        ('[KEY] API Configuration', {
            'fields': (
                'api_configuration_status',
                ('api_key', 'api_secret'),
                ('publisher_id', 'sub_publisher_id'),
                'api_token',
                ('base_url', 'webhook_url'),
                ('callback_url', 'support_url'),
            ),
            'classes': ('collapse',)
        }),
        
        ('📬 Postback Configuration', {
            'fields': (
                ('postback_url', 'postback_key'),
                'postback_password',
            ),
            'classes': ('collapse',),
            'description': '[WARN] Configure postback settings for automatic conversion tracking'
        }),
        
        ('⚙️ Settings & Status', {
            'fields': (
                ('is_active', 'is_testing', 'is_verified'),
                ('priority', 'rating', 'trust_score'),
                'verification_date',
            )
        }),
        
        ('[MONEY] Financial Settings', {
            'fields': (
                'financial_analytics',
                ('min_payout', 'max_payout'),
                'commission_rate',
                'payment_methods',
                'payment_duration',
            ),
            'classes': ('collapse',)
        }),
        
        ('✨ Feature Support', {
            'fields': (
                'feature_support_matrix',
                ('supports_postback', 'supports_webhook', 'supports_offers'),
                ('supports_surveys', 'supports_video', 'supports_app_install'),
                ('supports_gaming', 'supports_quiz', 'supports_tasks'),
            ),
            'classes': ('collapse',)
        }),
        
        ('🌍 Geo & Platform Targeting', {
            'fields': (
                'country_support',
                'countries',
                'platforms',
                'device_types',
            ),
            'classes': ('collapse',)
        }),
        
        ('[STATS] Performance Metrics', {
            'fields': (
                'performance_metrics',
                ('total_payout', 'total_conversions'),
                ('total_clicks', 'conversion_rate'),
                'epc',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏱️ Sync Settings', {
            'fields': (
                'offer_refresh_interval',
                ('last_sync', 'next_sync'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Advanced Configuration', {
            'fields': (
                'config',
                'metadata',
                'notes',
            ),
            'classes': ('collapse',)
        }),
        
        ('📈 Recent Activity', {
            'fields': ('recent_activity',),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [NetworkStatisticInline, OfferInline]
    
    actions = [
        'activate_networks',
        'deactivate_networks',
        'mark_as_verified',
        'sync_offers_now',
        'export_performance_report'
    ]
    
    # ==================== Custom Display Methods ====================
    
    def network_badge(self, obj):
        """Display network with logo and name"""
        if obj.logo:
            logo_url = obj.logo.url
        elif obj.logo_url:
            logo_url = obj.logo_url
        else:
            logo_url = '/static/default-network.png'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<img src="{}" style="width: 40px; height: 40px; border-radius: 5px; object-fit: cover;"/>'
            '<div>'
            '<strong style="font-size: 14px;">{}</strong><br/>'
            '<span style="color: #6c757d; font-size: 11px;">{}</span>'
            '</div>'
            '</div>',
            logo_url,
            obj.name,
            obj.get_network_type_display()
        )
    network_badge.short_description = 'Network'
    
    def category_badge(self, obj):
        """Display category with color"""
        colors = {
            'offerwall': '#3498db',
            'survey': '#9b59b6',
            'video': '#e74c3c',
            'gaming': '#2ecc71',
            'app_install': '#f39c12',
            'cashback': '#1abc9c',
            'cpi_cpa': '#34495e',
            'cpe': '#e67e22',
        }
        color = colors.get(obj.category, '#95a5a6')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'
    
    def status_indicator(self, obj):
        """Display comprehensive status"""
        status_html = []
        
        # Active/Inactive
        if obj.is_active:
            status_html.append(
                '<span style="background: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px; margin-right: 3px;">✓ ACTIVE</span>'
            )
        else:
            status_html.append(
                '<span style="background: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px; margin-right: 3px;">✗ INACTIVE</span>'
            )
        
        # Testing
        if obj.is_testing:
            status_html.append(
                '<span style="background: #ffc107; color: #333; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px; margin-right: 3px;">🧪 TEST</span>'
            )
        
        # Verified
        if obj.is_verified:
            status_html.append(
                '<span style="background: #17a2b8; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px;">✓ VERIFIED</span>'
            )
        
        return format_html('<div style="display: flex; flex-wrap: wrap; gap: 3px;">{}</div>', 
                          ''.join(status_html))
    status_indicator.short_description = 'Status'
    
    def performance_score(self, obj):
        """Display performance metrics"""
        if obj.total_clicks > 0:
            cr = (obj.total_conversions / obj.total_clicks) * 100
        else:
            cr = 0
        
        # Determine color based on conversion rate
        if cr >= 10:
            color = '#28a745'
            emoji = '🔥'
        elif cr >= 5:
            color = '#ffc107'
            emoji = '[STAR]'
        else:
            color = '#dc3545'
            emoji = '📉'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 14px;">{:.2f}%</div>'
            '<div style="color: #6c757d; font-size: 10px;">CR</div>'
            '</div>',
            emoji,
            color,
            cr
        )
    performance_score.short_description = 'Performance'
    
    def financial_summary(self, obj):
        """Display financial summary"""
        return format_html(
            '<div style="text-align: right;">'
            '<div style="font-weight: bold; color: #28a745; font-size: 14px;">৳{:,.2f}</div>'
            '<div style="color: #6c757d; font-size: 10px;">{} conversions</div>'
            '<div style="color: #f39c12; font-size: 11px;">EPC: ৳{:.2f}</div>'
            '</div>',
            obj.total_payout,
            obj.total_conversions,
            float(obj.epc)
        )
    financial_summary.short_description = 'Financials'
    
    def features_display(self, obj):
        """Display supported features"""
        features = []
        
        if obj.supports_offers:
            features.append('📋')
        if obj.supports_surveys:
            features.append('[STATS]')
        if obj.supports_video:
            features.append('🎥')
        if obj.supports_app_install:
            features.append('📱')
        if obj.supports_gaming:
            features.append('🎮')
        if obj.supports_tasks:
            features.append('[OK]')
        
        return format_html(
            '<div style="font-size: 18px; letter-spacing: 3px;">{}</div>',
            ' '.join(features) if features else '—'
        )
    features_display.short_description = 'Features'
    
    def last_sync_display(self, obj):
        """Display last sync time"""
        if obj.last_sync:
            time_diff = timezone.now() - obj.last_sync
            
            if time_diff < timedelta(hours=1):
                color = '#28a745'
                status = 'Just now'
            elif time_diff < timedelta(hours=24):
                color = '#ffc107'
                hours = int(time_diff.total_seconds() / 3600)
                status = f'{hours}h ago'
            else:
                color = '#dc3545'
                days = time_diff.days
                status = f'{days}d ago'
            
            return format_html(
                '<div style="text-align: center;">'
                '<div style="color: {}; font-weight: bold;">{}</div>'
                '<div style="color: #6c757d; font-size: 10px;">Last Sync</div>'
                '</div>',
                color,
                status
            )
        
        return format_html('<span style="color: #999;">Never</span>')
    last_sync_display.short_description = 'Last Sync'
    
    def quick_actions(self, obj):
        """Display quick action buttons"""
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 3px;">'
            '<a href="{}" class="button" style="font-size: 11px; padding: 3px 8px;">[NOTE] Edit</a>'
            '<a href="{}" class="button" style="font-size: 11px; padding: 3px 8px;">[STATS] Stats</a>'
            '<a href="{}" class="button" style="font-size: 11px; padding: 3px 8px;">[LOADING] Sync</a>'
            '</div>',
            reverse('admin:ad_networks_adnetwork_change', args=[obj.pk]),
            reverse('admin:ad_networks_networkstatistic_changelist') + f'?ad_network__id__exact={obj.pk}',
            reverse('admin:ad_networks_adnetwork_changelist')  # Add actual sync URL
        )
    quick_actions.short_description = 'Actions'
    
    # ==================== Readonly Summary Fields ====================
    
    def network_overview(self, obj):
        """Comprehensive network overview"""
        html = '<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        # Header
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">'
        html += f'<h2 style="margin: 0; font-size: 24px;">{obj.name}</h2>'
        
        if obj.rating:
            stars = '[STAR]' * int(obj.rating)
            html += f'<div style="font-size: 20px;">{stars}</div>'
        
        html += '</div>'
        
        # Quick Stats Grid
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px;">'
        
        stats = [
            ('[MONEY] Total Payout', f'৳{obj.total_payout:,.2f}'),
            ('🎯 Conversions', f'{obj.total_conversions:,}'),
            ('👆 Clicks', f'{obj.total_clicks:,}'),
            ('📈 CR', f'{obj.success_rate:.2f}%'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 11px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 20px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    network_overview.short_description = ''
    
    def performance_metrics(self, obj):
        """Detailed performance metrics"""
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f8f9fa;"><th style="padding: 10px; text-align: left;">Metric</th>' \
                '<th style="padding: 10px; text-align: right;">Value</th></tr>'
        
        metrics = [
            ('Total Payout', f'৳{obj.total_payout:,.2f}'),
            ('Total Conversions', f'{obj.total_conversions:,}'),
            ('Total Clicks', f'{obj.total_clicks:,}'),
            ('Conversion Rate', f'{obj.success_rate:.2f}%'),
            ('EPC (Earnings Per Click)', f'৳{float(obj.epc):.4f}'),
            ('Average Payout', f'৳{obj.avg_payout:,.2f}'),
            ('Success Rate', f'{obj.success_rate:.2f}%'),
        ]
        
        for label, value in metrics:
            html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{label}</td>' \
                   f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{value}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    performance_metrics.short_description = '[STATS] Performance Metrics'
    
    def api_configuration_status(self, obj):
        """API configuration status check"""
        checks = [
            ('API Key', bool(obj.api_key)),
            ('API Secret', bool(obj.api_secret)),
            ('Publisher ID', bool(obj.publisher_id)),
            ('Base URL', bool(obj.base_url)),
            ('Webhook URL', bool(obj.webhook_url)),
            ('Postback URL', bool(obj.postback_url)),
        ]
        
        configured_count = sum(1 for _, status in checks if status)
        total_count = len(checks)
        percentage = (configured_count / total_count) * 100
        
        if percentage == 100:
            color = '#28a745'
            status_text = '[OK] Fully Configured'
        elif percentage >= 50:
            color = '#ffc107'
            status_text = '[WARN] Partially Configured'
        else:
            color = '#dc3545'
            status_text = '[ERROR] Not Configured'
        
        html = f'<div style="margin-bottom: 15px; padding: 15px; background: {color}20; border-left: 4px solid {color}; border-radius: 5px;">'
        html += f'<strong style="color: {color}; font-size: 16px;">{status_text}</strong>'
        html += f'<div style="margin-top: 10px;"><strong>{configured_count}/{total_count}</strong> fields configured</div>'
        html += '</div>'
        
        html += '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        
        for label, status in checks:
            status_icon = '[OK]' if status else '[ERROR]'
            status_color = '#28a745' if status else '#dc3545'
            
            html += f'<tr><td style="padding: 5px;">{label}</td>' \
                   f'<td style="padding: 5px; text-align: right; color: {status_color};">{status_icon}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    api_configuration_status.short_description = '[KEY] API Configuration Status'
    
    def feature_support_matrix(self, obj):
        """Feature support matrix"""
        features = [
            ('Postback', obj.supports_postback),
            ('Webhook', obj.supports_webhook),
            ('Offers', obj.supports_offers),
            ('Surveys', obj.supports_surveys),
            ('Video', obj.supports_video),
            ('App Install', obj.supports_app_install),
            ('Gaming', obj.supports_gaming),
            ('Quiz', obj.supports_quiz),
            ('Tasks', obj.supports_tasks),
        ]
        
        html = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">'
        
        for label, supported in features:
            if supported:
                bg_color = '#d4edda'
                text_color = '#155724'
                icon = '[OK]'
            else:
                bg_color = '#f8d7da'
                text_color = '#721c24'
                icon = '[ERROR]'
            
            html += f'<div style="background: {bg_color}; color: {text_color}; padding: 10px; ' \
                   f'border-radius: 5px; text-align: center; font-size: 12px;">'
            html += f'{icon} {label}'
            html += '</div>'
        
        html += '</div>'
        return format_html(html)
    feature_support_matrix.short_description = '✨ Feature Support'
    
    def financial_analytics(self, obj):
        """Financial analytics summary"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        
        # Revenue breakdown
        html += '<h4 style="margin-top: 0; color: #495057;">[MONEY] Revenue Breakdown</h4>'
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">'
        
        revenue_stats = [
            ('Total Payout', obj.total_payout, '#28a745'),
            ('Commission Rate', f'{obj.commission_rate}%', '#17a2b8'),
            ('Min Payout', obj.min_payout, '#ffc107'),
            ('Max Payout', obj.max_payout or 0, '#6c757d'),
        ]
        
        for label, value, color in revenue_stats:
            html += f'<div style="background: white; padding: 12px; border-radius: 5px; border-left: 3px solid {color};">'
            html += f'<div style="color: #6c757d; font-size: 11px; margin-bottom: 5px;">{label}</div>'
            
            if isinstance(value, (int, float)):
                html += f'<div style="font-size: 18px; font-weight: bold; color: {color};">৳{value:,.2f}</div>'
            else:
                html += f'<div style="font-size: 18px; font-weight: bold; color: {color};">{value}</div>'
            
            html += '</div>'
        
        html += '</div>'
        
        # Payment methods
        if obj.payment_methods:
            html += '<h4 style="color: #495057;">💳 Payment Methods</h4>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 5px;">'
            
            for method in obj.payment_methods:
                html += f'<span style="background: #007bff; color: white; padding: 5px 10px; ' \
                       f'border-radius: 15px; font-size: 11px;">{method}</span>'
            
            html += '</div>'
        
        html += '</div>'
        return format_html(html)
    financial_analytics.short_description = '[MONEY] Financial Analytics'
    
    def recent_activity(self, obj):
        """Recent activity and sync logs"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        
        # Recent sync logs
        recent_syncs = obj.sync_logs.all()[:5]
        
        if recent_syncs:
            html += '<h4 style="margin-top: 0;">[LOADING] Recent Syncs</h4>'
            html += '<table style="width: 100%; border-collapse: collapse;">'
            html += '<tr style="background: white;"><th style="padding: 8px; text-align: left;">Date</th>' \
                   '<th>Status</th><th>Offers</th><th>Duration</th></tr>'
            
            for sync in recent_syncs:
                status_color = '#28a745' if sync.status == 'success' else '#dc3545'
                
                html += f'<tr style="border-bottom: 1px solid #dee2e6;">'
                html += f'<td style="padding: 8px;">{sync.created_at.strftime("%Y-%m-%d %H:%M")}</td>'
                html += f'<td style="padding: 8px; text-align: center; color: {status_color};">{sync.status}</td>'
                html += f'<td style="padding: 8px; text-align: center;">{sync.offers_fetched}</td>'
                html += f'<td style="padding: 8px; text-align: center;">{sync.sync_duration:.2f}s</td>'
                html += '</tr>'
            
            html += '</table>'
        else:
            html += '<p style="color: #6c757d; text-align: center; margin: 20px 0;">No recent sync activity</p>'
        
        html += '</div>'
        return format_html(html)
    recent_activity.short_description = '📅 Recent Activity'
    
    # ==================== Admin Actions ====================
    
    def activate_networks(self, request, queryset):
        """Activate selected networks"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} networks activated successfully.')
    activate_networks.short_description = '[OK] Activate selected networks'
    
    def deactivate_networks(self, request, queryset):
        """Deactivate selected networks"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} networks deactivated successfully.')
    deactivate_networks.short_description = '[ERROR] Deactivate selected networks'
    
    def mark_as_verified(self, request, queryset):
        """Mark networks as verified"""
        count = queryset.update(
            is_verified=True,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{count} networks marked as verified.')
    mark_as_verified.short_description = '✓ Mark as verified'
    
    def sync_offers_now(self, request, queryset):
        """Sync offers for selected networks"""
        # Implement actual sync logic here
        self.message_user(
            request,
            f'Sync initiated for {queryset.count()} networks. Check sync logs for details.',
            level='warning'
        )
    sync_offers_now.short_description = '[LOADING] Sync offers now'
    
    def export_performance_report(self, request, queryset):
        """Export performance report"""
        self.message_user(
            request,
            'Performance report export will be available soon.',
            level='info'
        )
    export_performance_report.short_description = '[STATS] Export performance report'
    
    class Media:
        css = {
            'all': ('admin/css/ad_networks.css',)
        }
        js = ('admin/js/ad_networks.js',)
        
        
        
        # api/ad_networks/admin.py (continued)

# ==================== Offer Category Admin ====================

@admin.register(OfferCategory)
class OfferCategoryAdmin(admin.ModelAdmin):
    list_display = [
        'category_display',
        'type_badge',
        'active_status',
        'stats_summary',
        'display_order',
        'featured_badge',
        'quick_edit'
    ]
    
    list_filter = [
        'category_type',
        'is_active',
        'is_featured',
    ]
    
    search_fields = ['name', 'slug', 'description']
    
    prepopulated_fields = {'slug': ('name',)}
    
    readonly_fields = [
        'category_overview',
        'performance_stats',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('[STATS] Category Overview', {
            'fields': ('category_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Basic Information', {
            'fields': (
                'name',
                'slug',
                'category_type',
                'description',
            )
        }),
        
        ('🎨 Display Settings', {
            'fields': (
                ('icon', 'image'),
                'color',
                ('order', 'display_order'),
            )
        }),
        
        ('⚙️ Status', {
            'fields': (
                ('is_active', 'is_featured'),
            )
        }),
        
        ('📈 Performance', {
            'fields': ('performance_stats',),
            'classes': ('collapse',)
        }),
        
        ('🔍 SEO', {
            'fields': (
                'meta_title',
                'meta_description',
                'keywords',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_editable = ['display_order',]
    
    # ==================== Display Methods ====================
    
    def category_display(self, obj):
        """Display category with icon and color"""
        icon = obj.icon or '📁'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<div style="background: {}; width: 40px; height: 40px; border-radius: 50%; '
            'display: flex; align-items: center; justify-content: center; font-size: 20px;">'
            '{}</div>'
            '<div>'
            '<strong style="font-size: 14px;">{}</strong><br/>'
            '<span style="color: #6c757d; font-size: 11px;">{}</span>'
            '</div>'
            '</div>',
            obj.color,
            icon,
            obj.name,
            obj.slug
        )
    category_display.short_description = 'Category'
    
    def type_badge(self, obj):
        """Display category type badge"""
        colors = {
            'survey': '#9b59b6',
            'offer': '#3498db',
            'video': '#e74c3c',
            'game': '#2ecc71',
            'app_install': '#f39c12',
            'quiz': '#1abc9c',
            'task': '#34495e',
            'signup': '#e67e22',
            'shopping': '#c0392b',
            'cashback': '#16a085',
        }
        color = colors.get(obj.category_type, '#95a5a6')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 15px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_category_type_display()
        )
    type_badge.short_description = 'Type'
    
    def active_status(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 11px;">✓ Active</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 11px;">✗ Inactive</span>'
        )
    active_status.short_description = 'Status'
    
    def stats_summary(self, obj):
        """Display statistics summary"""
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 18px; font-weight: bold; color: #3498db;">{}</div>'
            '<div style="color: #6c757d; font-size: 10px;">Active Offers</div>'
            '<div style="font-size: 12px; color: #28a745; margin-top: 3px;">৳{:,.0f} avg</div>'
            '</div>',
            obj.active_offers_count,
            obj.avg_reward
        )
    stats_summary.short_description = 'Stats'
    
    def order_display(self, obj):
        """Display order"""
        return format_html(
            '<div style="text-align: center; font-size: 16px; font-weight: bold; color: #6c757d;">'
            '{}'
            '</div>',
            obj.display_order
        )
    order_display.short_description = 'Order'
    
    def featured_badge(self, obj):
        """Display featured badge"""
        if obj.is_featured:
            return format_html(
                '<span style="font-size: 20px;" title="Featured">[STAR]</span>'
            )
        return '—'
    featured_badge.short_description = 'Featured'
    
    def quick_edit(self, obj):
        """Quick edit button"""
        return format_html(
            '<a href="{}" class="button" style="font-size: 11px; padding: 5px 10px;">Edit</a>',
            reverse('admin:ad_networks_offercategory_change', args=[obj.pk])
        )
    quick_edit.short_description = 'Actions'
    
    def category_overview(self, obj):
        """Category overview"""
        html = f'<div style="background: linear-gradient(135deg, {obj.color} 0%, {obj.color}dd 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        icon = obj.icon or '📁'
        html += f'<div style="display: flex; align-items: center; gap: 15px;">'
        html += f'<div style="font-size: 48px;">{icon}</div>'
        html += f'<div>'
        html += f'<h2 style="margin: 0; font-size: 28px;">{obj.name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9;">{obj.get_category_type_display()}</p>'
        html += f'</div>'
        html += f'</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 20px;">'
        
        stats = [
            ('Active Offers', obj.active_offers_count),
            ('Total Conversions', obj.total_conversions),
            ('Avg Reward', f'৳{obj.avg_reward:,.2f}'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 11px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 20px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    category_overview.short_description = ''
    
    def performance_stats(self, obj):
        """Performance statistics"""
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f8f9fa;"><th style="padding: 10px; text-align: left;">Metric</th>' \
                '<th style="padding: 10px; text-align: right;">Value</th></tr>'
        
        stats = [
            ('Total Offers', obj.total_offers),
            ('Active Offers', obj.active_offers_count),
            ('Total Conversions', obj.total_conversions),
            ('Average Reward', f'৳{obj.avg_reward:,.2f}'),
        ]
        
        for label, value in stats:
            html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{label}</td>' \
                   f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{value}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    performance_stats.short_description = '[STATS] Performance Statistics'


# ==================== Offer Admin ====================

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = [
        'offer_card',
        'category_tag',
        'reward_display',
        'status_badges',
        'performance_indicator',
        'availability_info',
        'last_updated_display',
    ]
    
    list_filter = [
        'status',
        'category',
        'ad_network',
        'difficulty',
        'is_featured',
        'is_hot',
        'is_new',
        'device_type',
        'gender_targeting',
        'created_at',
    ]
    
    search_fields = [
        'title',
        'external_id',
        'description',
        'ad_network__name',
    ]
    
    readonly_fields = [
        'offer_overview',
        'performance_dashboard',
        'targeting_summary',
        'availability_status',
        'created_at',
        'last_updated',
    ]
    
    fieldsets = (
        ('🎯 Offer Overview', {
            'fields': ('offer_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Basic Information', {
            'fields': (
                ('ad_network', 'category'),
                ('external_id', 'internal_id'),
                'title',
                'description',
                'instructions',
                ('thumbnail', 'preview_images'),
            )
        }),
        
        ('[MONEY] Reward & Financial', {
            'fields': (
                ('reward_amount', 'reward_currency'),
                ('network_payout', 'commission'),
            )
        }),
        
        ('[STATS] Offer Details', {
            'fields': (
                ('difficulty', 'estimated_time'),
                'steps_required',
            )
        }),
        
        ('📈 Limits & Availability', {
            'fields': (
                'availability_status',
                ('max_conversions', 'total_conversions'),
                ('max_daily_conversions', 'daily_conversions'),
                ('user_daily_limit', 'user_lifetime_limit'),
            )
        }),
        
        ('🎯 Targeting', {
            'fields': (
                'targeting_summary',
                'countries',
                'platforms',
                'device_type',
                ('min_age', 'max_age'),
                ('gender_targeting', 'age_group'),
            ),
            'classes': ('collapse',)
        }),
        
        ('🔗 URLs', {
            'fields': (
                'click_url',
                'tracking_url',
                'preview_url',
                ('terms_url', 'privacy_url'),
            ),
            'classes': ('collapse',)
        }),
        
        ('⚙️ Status & Visibility', {
            'fields': (
                'status',
                ('is_featured', 'is_hot', 'is_new'),
                ('is_exclusive', 'requires_approval'),
            )
        }),
        
        ('⏰ Time Settings', {
            'fields': (
                ('starts_at', 'expires_at'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[STATS] Performance', {
            'fields': (
                'performance_dashboard',
                ('click_count', 'conversion_rate'),
                ('avg_completion_time', 'quality_score'),
            ),
            'classes': ('collapse',)
        }),
        
        ('🔒 Fraud Protection', {
            'fields': (
                ('fraud_score', 'requires_screenshot'),
                'requires_verification',
            ),
            'classes': ('collapse',)
        }),
        
        ('🏷️ Metadata', {
            'fields': (
                'tags',
                'requirements',
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'last_updated',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_offers',
        'deactivate_offers',
        'mark_as_featured',
        'mark_as_hot',
        'export_offers'
    ]
    
    # ==================== Display Methods ====================
    
    def offer_card(self, obj):
        """Display offer as card"""
        thumb = obj.thumbnail or '/static/default-offer.png'
        
        return format_html(
            '<div style="display: flex; gap: 12px; align-items: start; max-width: 400px;">'
            '<img src="{}" style="width: 60px; height: 60px; border-radius: 8px; object-fit: cover; '
            'border: 2px solid #e9ecef;"/>'
            '<div style="flex: 1;">'
            '<strong style="font-size: 13px; line-height: 1.4; display: block; margin-bottom: 4px;">{}</strong>'
            '<div style="font-size: 10px; color: #6c757d; display: flex; gap: 8px; align-items: center;">'
            '<span>⏱️ {} min</span>'
            '<span>[STATS] {}</span>'
            '<span>🔢 #{}</span>'
            '</div>'
            '</div>'
            '</div>',
            thumb,
            obj.title[:50] + ('...' if len(obj.title) > 50 else ''),
            obj.estimated_time,
            obj.get_difficulty_display(),
            obj.external_id[:10]
        )
    offer_card.short_description = 'Offer'
    
    def category_tag(self, obj):
        """Display category"""
        if obj.category:
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
                obj.category.color,
                obj.category.name
            )
        return '—'
    category_tag.short_description = 'Category'
    
    def reward_display(self, obj):
        """Display reward with visual emphasis"""
        return format_html(
            '<div style="text-align: center; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); '
            'padding: 10px; border-radius: 8px; color: white;">'
            '<div style="font-size: 20px; font-weight: bold;">৳{:,.2f}</div>'
            '<div style="font-size: 9px; opacity: 0.9; margin-top: 2px;">REWARD</div>'
            '</div>',
            obj.reward_amount
        )
    reward_display.short_description = 'Reward'
    
    def status_badges(self, obj):
        """Display status badges"""
        badges = []
        
        # Status
        status_colors = {
            'active': '#28a745',
            'paused': '#ffc107',
            'completed': '#6c757d',
            'expired': '#dc3545',
            'pending': '#17a2b8',
            'rejected': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        
        badges.append(
            f'<span style="background: {color}; color: white; padding: 3px 8px; '
            f'border-radius: 10px; font-size: 9px; font-weight: 600;">{obj.get_status_display().upper()}</span>'
        )
        
        # Featured
        if obj.is_featured:
            badges.append(
                '<span style="background: #ffd700; color: #333; padding: 3px 8px; '
                'border-radius: 10px; font-size: 9px; font-weight: 600;">[STAR] FEATURED</span>'
            )
        
        # Hot
        if obj.is_hot:
            badges.append(
                '<span style="background: #ff4757; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 9px; font-weight: 600;">🔥 HOT</span>'
            )
        
        # New
        if obj.is_new:
            badges.append(
                '<span style="background: #5f27cd; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 9px; font-weight: 600;">🆕 NEW</span>'
            )
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 3px;">{}</div>',
            ''.join(badges)
        )
    status_badges.short_description = 'Status'
    
    def performance_indicator(self, obj):
        """Display performance metrics"""
        cr = obj.completion_rate
        
        if cr >= 20:
            color = '#28a745'
            emoji = '🔥'
            label = 'Excellent'
        elif cr >= 10:
            color = '#17a2b8'
            emoji = '[STAR]'
            label = 'Good'
        elif cr >= 5:
            color = '#ffc107'
            emoji = '[STATS]'
            label = 'Average'
        else:
            color = '#dc3545'
            emoji = '📉'
            label = 'Low'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 13px;">{:.1f}%</div>'
            '<div style="color: #6c757d; font-size: 9px;">{}</div>'
            '<div style="color: #6c757d; font-size: 9px; margin-top: 2px;">{} / {}</div>'
            '</div>',
            emoji,
            color,
            cr,
            label,
            obj.total_conversions,
            obj.click_count
        )
    performance_indicator.short_description = 'Performance'
    
    def availability_info(self, obj):
        """Display availability information"""
        is_available = obj.is_available
        remaining = obj.remaining_conversions
        
        if is_available:
            status_color = '#28a745'
            status_icon = '[OK]'
            status_text = 'Available'
        else:
            status_color = '#dc3545'
            status_icon = '[ERROR]'
            status_text = 'Unavailable'
        
        html = f'<div style="text-align: center;">'
        html += f'<div style="color: {status_color}; font-size: 16px;">{status_icon}</div>'
        html += f'<div style="color: {status_color}; font-size: 11px; font-weight: 600;">{status_text}</div>'
        
        if remaining is not None:
            html += f'<div style="color: #6c757d; font-size: 9px; margin-top: 2px;">{remaining} left</div>'
        
        html += '</div>'
        
        return format_html(html)
    availability_info.short_description = 'Availability'
    
    def last_updated_display(self, obj):
        """Display last updated time"""
        time_diff = timezone.now() - obj.last_updated
        
        if time_diff < timedelta(hours=1):
            display = 'Just now'
            color = '#28a745'
        elif time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            display = f'{hours}h ago'
            color = '#17a2b8'
        else:
            days = time_diff.days
            display = f'{days}d ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px;">{}</div>',
            color,
            display
        )
    last_updated_display.short_description = 'Updated'
    
    # ==================== Readonly Summary Fields ====================
    
    def offer_overview(self, obj):
        """Comprehensive offer overview"""
        html = '<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        # Header with thumbnail
        html += '<div style="display: flex; gap: 20px; align-items: start; margin-bottom: 20px;">'
        
        if obj.thumbnail:
            html += f'<img src="{obj.thumbnail}" style="width: 100px; height: 100px; border-radius: 10px; ' \
                   'object-fit: cover; border: 3px solid rgba(255,255,255,0.3);"/>'
        
        html += '<div style="flex: 1;">'
        html += f'<h2 style="margin: 0 0 10px 0; font-size: 24px;">{obj.title}</h2>'
        html += f'<div style="opacity: 0.9; font-size: 13px; line-height: 1.6;">{obj.description[:200]}...</div>'
        html += '</div>'
        html += '</div>'
        
        # Quick stats
        html += '<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;">'
        
        
        def safe_val(val):
           return val if val is not None else 0

        stats = [
           ('[MONEY] Reward', f'৳{safe_val(obj.reward_amount):,.2f}'),
           ('🎯 Conversions', f'{safe_val(obj.total_conversions):,}'),
           ('👆 Clicks', f'{safe_val(obj.click_count):,}'),
           ('📈 CR', f'{safe_val(obj.completion_rate):.1f}%'),
           ('[STAR] Quality', f'{safe_val(obj.quality_score):.1f}/10'),
        ]        
        # def safe_val(val):
        #     return val if val is not None else 0
        # stats = [
        #     ('[MONEY] Reward', f'৳{obj.reward_amount:,.2f}'),
        #     ('🎯 Conversions', f'{obj.total_conversions:,}'),
        #     ('👆 Clicks', f'{obj.click_count:,}'),
        #     ('📈 CR', f'{obj.completion_rate:.1f}%'),
        #     ('[STAR] Quality', f'{obj.quality_score:.1f}/10'),
        # ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 16px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    offer_overview.short_description = ''
    
    def performance_dashboard(self, obj):
        """Performance dashboard"""
        html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">'
        
        # Left column - Metrics
        html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0; color: #495057;">[STATS] Key Metrics</h4>'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        metrics = [
            ('Click Count', f'{obj.click_count:,}'),
            ('Total Conversions', f'{obj.total_conversions:,}'),
            ('Conversion Rate', f'{obj.conversion_rate:.2f}%'),
            ('Completion Rate', f'{obj.completion_rate:.2f}%'),
            ('Quality Score', f'{obj.quality_score:.1f}/10'),
            ('Average Time', f'{obj.avg_completion_time}s'),
        ]
        
        for label, value in metrics:
            html += f'<tr><td style="padding: 6px 0; color: #6c757d; font-size: 12px;">{label}</td>' \
                   f'<td style="padding: 6px 0; text-align: right; font-weight: 600; font-size: 13px;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        # Right column - Visual indicators
        html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0; color: #495057;">🎯 Performance Rating</h4>'
        
        # Performance bars
        performance_items = [
            ('Conversion Rate', obj.conversion_rate, 100),
            ('Quality Score', obj.quality_score * 10, 100),
            ('Completion Rate', obj.completion_rate, 100),
        ]
        
        for label, value, max_value in performance_items:
            percentage = min((value / max_value) * 100, 100)
            
            if percentage >= 70:
                bar_color = '#28a745'
            elif percentage >= 40:
                bar_color = '#ffc107'
            else:
                bar_color = '#dc3545'
            
            html += f'<div style="margin-bottom: 15px;">'
            html += f'<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 11px;">'
            html += f'<span style="color: #6c757d;">{label}</span>'
            html += f'<span style="font-weight: 600;">{value:.1f}%</span>'
            html += '</div>'
            html += f'<div style="background: #e9ecef; border-radius: 10px; height: 8px; overflow: hidden;">'
            html += f'<div style="background: {bar_color}; width: {percentage}%; height: 100%; border-radius: 10px;"></div>'
            html += '</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    performance_dashboard.short_description = '[STATS] Performance Dashboard'
    
    def targeting_summary(self, obj):
        """Targeting summary"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        
        # Countries
        html += '<div style="margin-bottom: 15px;">'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">🌍 Countries</h4>'
        
        if obj.countries:
            html += '<div style="display: flex; flex-wrap: wrap; gap: 5px;">'
            for country in obj.countries[:10]:
                html += f'<span style="background: #007bff; color: white; padding: 4px 10px; ' \
                       f'border-radius: 12px; font-size: 10px;">{country}</span>'
            
            if len(obj.countries) > 10:
                html += f'<span style="background: #6c757d; color: white; padding: 4px 10px; ' \
                       f'border-radius: 12px; font-size: 10px;">+{len(obj.countries) - 10} more</span>'
            
            html += '</div>'
        else:
            html += '<span style="color: #6c757d;">All countries</span>'
        
        html += '</div>'
        
        # Platforms
        html += '<div style="margin-bottom: 15px;">'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">💻 Platforms</h4>'
        
        if obj.platforms:
            html += '<div style="display: flex; gap: 5px;">'
            platform_icons = {
                'android': '🤖',
                'ios': '🍎',
                'web': '🌐',
            }
            
            for platform in obj.platforms:
                icon = platform_icons.get(platform, '📱')
                html += f'<span style="background: #28a745; color: white; padding: 4px 10px; ' \
                       f'border-radius: 12px; font-size: 10px;">{icon} {platform.upper()}</span>'
            
            html += '</div>'
        
        html += '</div>'
        
        # Demographics
        html += '<div>'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">👥 Demographics</h4>'
        html += '<table style="width: 100%; font-size: 12px;">'
        html += f'<tr><td style="color: #6c757d; padding: 3px 0;">Age Range:</td>' \
               f'<td style="font-weight: 600; text-align: right;">{obj.min_age} - {obj.max_age} years</td></tr>'
        html += f'<tr><td style="color: #6c757d; padding: 3px 0;">Gender:</td>' \
               f'<td style="font-weight: 600; text-align: right;">{obj.get_gender_targeting_display()}</td></tr>'
        html += f'<tr><td style="color: #6c757d; padding: 3px 0;">Device:</td>' \
               f'<td style="font-weight: 600; text-align: right;">{obj.get_device_type_display()}</td></tr>'
        html += '</table>'
        html += '</div>'
        
        html += '</div>'
        return format_html(html)
    targeting_summary.short_description = '🎯 Targeting Summary'
    
    def availability_status(self, obj):
        """Availability status"""
        is_available = obj.is_available
        
        if is_available:
            bg_color = '#d4edda'
            text_color = '#155724'
            icon = '[OK]'
            status_text = 'Available'
        else:
            bg_color = '#f8d7da'
            text_color = '#721c24'
            icon = '[ERROR]'
            status_text = 'Not Available'
        
        html = f'<div style="background: {bg_color}; color: {text_color}; padding: 15px; ' \
               f'border-radius: 8px; border-left: 4px solid {text_color};">'
        
        html += f'<h3 style="margin: 0 0 10px 0;">{icon} {status_text}</h3>'
        
        # Availability details
        html += '<table style="width: 100%; font-size: 13px;">'
        
        if obj.max_conversions:
            remaining = obj.remaining_conversions
            percentage = (remaining / obj.max_conversions) * 100 if obj.max_conversions > 0 else 0
            
            html += f'<tr><td style="padding: 5px 0;">Total Limit:</td>' \
                   f'<td style="text-align: right; font-weight: 600;">{obj.max_conversions:,}</td></tr>'
            html += f'<tr><td style="padding: 5px 0;">Completed:</td>' \
                   f'<td style="text-align: right; font-weight: 600;">{obj.total_conversions:,}</td></tr>'
            html += f'<tr><td style="padding: 5px 0;">Remaining:</td>' \
                   f'<td style="text-align: right; font-weight: 600; color: {text_color};">{remaining:,} ({percentage:.1f}%)</td></tr>'
        
        if obj.expires_at:
            time_left = obj.expires_at - timezone.now()
            
            if time_left.total_seconds() > 0:
                days_left = time_left.days
                hours_left = int(time_left.seconds / 3600)
                
                html += f'<tr><td style="padding: 5px 0;">Expires In:</td>' \
                       f'<td style="text-align: right; font-weight: 600;">{days_left}d {hours_left}h</td></tr>'
            else:
                html += f'<tr><td style="padding: 5px 0;">Status:</td>' \
                       f'<td style="text-align: right; font-weight: 600; color: #dc3545;">Expired</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    availability_status.short_description = '🎯 Availability Status'
    
    # ==================== Actions ====================
    
    def activate_offers(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, f'{count} offers activated.')
    activate_offers.short_description = '[OK] Activate selected offers'
    
    def deactivate_offers(self, request, queryset):
        count = queryset.update(status='paused')
        self.message_user(request, f'{count} offers paused.')
    deactivate_offers.short_description = '⏸️ Pause selected offers'
    
    def mark_as_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} offers marked as featured.')
    mark_as_featured.short_description = '[STAR] Mark as featured'
    
    def mark_as_hot(self, request, queryset):
        count = queryset.update(is_hot=True)
        self.message_user(request, f'{count} offers marked as hot.')
    mark_as_hot.short_description = '🔥 Mark as hot'
    
    def export_offers(self, request, queryset):
        self.message_user(request, 'Export feature coming soon.', level='info')
    export_offers.short_description = '📥 Export selected offers'
    

# api/ad_networks/admin.py (continued)

# ==================== User Offer Engagement Admin ====================

@admin.register(UserOfferEngagement)
class UserOfferEngagementAdmin(admin.ModelAdmin):
    list_display = [
        'engagement_info',
        'user_display',
        'offer_preview',
        'status_timeline',
        'reward_info',
        'device_info_display',
        'time_info',
        'actions_display'
    ]
    
    list_filter = [
        'status',
        'created_at',
        'completed_at',
        'offer__category',
        'offer__ad_network',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'offer__title',
        'click_id',
        'conversion_id',
        'ip_address',
    ]
    
    readonly_fields = [
        'engagement_overview',
        'user_details',
        'offer_details',
        'timeline_visualization',
        'device_location_info',
        'verification_status',
        'clicked_at',
        'started_at',
        'completed_at',
        'verified_at',
        'rewarded_at',
    ]
    
    fieldsets = (
        ('[STATS] Engagement Overview', {
            'fields': ('engagement_overview',),
            'classes': ('wide',)
        }),
        
        ('👤 User & Offer', {
            'fields': (
                'user_details',
                'offer_details',
                ('user', 'offer'),
            )
        }),
        
        ('📈 Status & Progress', {
            'fields': (
                'status',
                'progress',
                'timeline_visualization',
            )
        }),
        
        ('🔢 Tracking IDs', {
            'fields': (
                'click_id',
                ('conversion_id', 'transaction_id'),
                ('campaign_id', 'tracking_id'),
                'device_id',
            ),
            'classes': ('collapse',)
        }),
        
        ('[MONEY] Reward Information', {
            'fields': (
                ('reward_earned', 'network_payout'),
                'commission_earned',
            )
        }),
        
        ('🌐 Device & Location', {
            'fields': (
                'device_location_info',
                ('ip_address', 'user_agent'),
                'device_info',
                'location_data',
                ('browser', 'os'),
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timeline', {
            'fields': (
                'clicked_at',
                'started_at',
                'completed_at',
                'verified_at',
                'rewarded_at',
                'expired_at',
            ),
            'classes': ('collapse',)
        }),
        
        ('[OK] Verification', {
            'fields': (
                'verification_status',
                ('rejection_reason', 'rejection_details'),
                'verified_by',
                ('screenshot', 'proof_data'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Advanced', {
            'fields': (
                ('session_id', 'referrer_url'),
                'metadata',
                'notes',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    actions = [
        'approve_engagements',
        'reject_engagements',
        'mark_as_verified',
        'process_rewards'
    ]
    
    # ==================== Display Methods ====================
    
    def engagement_info(self, obj):
        """Display engagement info"""
        status_colors = {
            'clicked': '#17a2b8',
            'started': '#ffc107',
            'in_progress': '#007bff',
            'completed': '#28a745',
            'pending': '#fd7e14',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'canceled': '#6c757d',
            'expired': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        
        return format_html(
            '<div style="border-left: 4px solid {}; padding-left: 10px;">'
            '<div style="font-weight: bold; font-size: 12px; color: {};">{}</div>'
            '<div style="font-size: 10px; color: #6c757d; margin-top: 3px;">ID: {}</div>'
            '<div style="font-size: 10px; color: #6c757d;">Progress: {}%</div>'
            '</div>',
            color,
            color,
            obj.get_status_display().upper(),
            obj.click_id[:12] + '...',
            int(obj.progress)
        )
    engagement_info.short_description = 'Engagement'
    
    def user_display(self, obj):
        """Display user info"""
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
            'border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; '
            'font-weight: bold; font-size: 14px;">{}</div>'
            '<div>'
            '<a href="{}" style="font-weight: 600; font-size: 12px; text-decoration: none;">{}</a><br/>'
            '<span style="font-size: 10px; color: #6c757d;">{}</span>'
            '</div>'
            '</div>',
            obj.user.username[0].upper(),
            reverse('admin:auth_user_change', args=[obj.user.pk]),
            obj.user.username,
            obj.user.email
        )
    user_display.short_description = 'User'
    
    def offer_preview(self, obj):
        """Display offer preview"""
        thumb = obj.offer.thumbnail or '/static/default-offer.png'
        
        return format_html(
            '<div style="display: flex; gap: 8px; align-items: center; max-width: 250px;">'
            '<img src="{}" style="width: 40px; height: 40px; border-radius: 6px; object-fit: cover;"/>'
            '<div style="flex: 1;">'
            '<div style="font-size: 11px; font-weight: 600; line-height: 1.3;">{}</div>'
            '<div style="font-size: 9px; color: #6c757d; margin-top: 2px;">৳{} • {}</div>'
            '</div>'
            '</div>',
            thumb,
            obj.offer.title[:40] + ('...' if len(obj.offer.title) > 40 else ''),
            obj.offer.reward_amount,
            obj.offer.ad_network.name
        )
    offer_preview.short_description = 'Offer'
    
    def status_timeline(self, obj):
        """Display status timeline"""
        stages = [
            ('👆', 'Clicked', obj.clicked_at, '#17a2b8'),
            ('▶️', 'Started', obj.started_at, '#ffc107'),
            ('[OK]', 'Completed', obj.completed_at, '#28a745'),
            ('🎁', 'Rewarded', obj.rewarded_at, '#6f42c1'),
        ]
        
        html = '<div style="display: flex; gap: 2px;">'
        
        for icon, label, timestamp, color in stages:
            if timestamp:
                opacity = '1'
                bg_color = color
            else:
                opacity = '0.3'
                bg_color = '#dee2e6'
            
            html += f'<div style="width: 32px; height: 32px; background: {bg_color}; opacity: {opacity}; ' \
                   f'border-radius: 50%; display: flex; align-items: center; justify-content: center; ' \
                   f'font-size: 14px;" title="{label}: {timestamp or "Not yet"}">{icon}</div>'
        
        html += '</div>'
        
        # Time spent
        if obj.time_spent:
            minutes = int(obj.time_spent / 60)
            seconds = int(obj.time_spent % 60)
            html += f'<div style="font-size: 9px; color: #6c757d; margin-top: 5px; text-align: center;">' \
                   f'⏱️ {minutes}m {seconds}s</div>'
        
        return format_html(html)
    status_timeline.short_description = 'Timeline'
    
    def reward_info(self, obj):
        """Display reward information"""
        if obj.reward_earned > 0:
            return format_html(
                '<div style="text-align: center; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); '
                'padding: 8px; border-radius: 8px; color: white;">'
                '<div style="font-size: 16px; font-weight: bold;">৳{:,.2f}</div>'
                '<div style="font-size: 8px; opacity: 0.9; margin-top: 2px;">EARNED</div>'
                '</div>',
                obj.reward_earned
            )
        else:
            return format_html(
                '<div style="text-align: center; color: #6c757d; font-size: 11px;">No reward yet</div>'
            )
    reward_info.short_description = 'Reward'
    
    def device_info_display(self, obj):
        """Display device info"""
        browser = obj.browser or 'Unknown'
        os = obj.os or 'Unknown'
        
        # Browser icons
        browser_icons = {
            'chrome': '🌐',
            'firefox': '🦊',
            'safari': '🧭',
            'edge': '🔷',
        }
        icon = browser_icons.get(browser.lower(), '💻')
        
        return format_html(
            '<div style="text-align: center; font-size: 11px;">'
            '<div style="font-size: 18px; margin-bottom: 3px;">{}</div>'
            '<div style="color: #6c757d;">{}</div>'
            '<div style="color: #6c757d; font-size: 9px;">{}</div>'
            '</div>',
            icon,
            browser[:15],
            os[:15]
        )
    device_info_display.short_description = 'Device'
    
    def time_info(self, obj):
        """Display time information"""
        time_ago = timezone.now() - obj.clicked_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
            color = '#28a745'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#17a2b8'
        else:
            display = f'{time_ago.days}d ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="color: {}; font-weight: 600; font-size: 11px;">{}</div>'
            '<div style="color: #6c757d; font-size: 9px; margin-top: 2px;">{}</div>'
            '</div>',
            color,
            display,
            obj.clicked_at.strftime('%b %d, %H:%M')
        )
    time_info.short_description = 'Time'
    
    def actions_display(self, obj):
        """Display action buttons"""
        buttons = []
        
        if obj.status == 'pending':
            buttons.append(
                f'<a href="#" class="button" style="background: #28a745; color: white; '
                f'font-size: 10px; padding: 4px 8px; text-decoration: none; border-radius: 3px;">✓ Approve</a>'
            )
            buttons.append(
                f'<a href="#" class="button" style="background: #dc3545; color: white; '
                f'font-size: 10px; padding: 4px 8px; text-decoration: none; border-radius: 3px;">✗ Reject</a>'
            )
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 3px;">{}</div>',
            ''.join(buttons) if buttons else '—'
        )
    actions_display.short_description = 'Actions'
    
    # ==================== Readonly Summary Fields ====================
    
    def engagement_overview(self, obj):
        """Engagement overview"""
        status_colors = {
            'clicked': '#17a2b8',
            'started': '#ffc107',
            'in_progress': '#007bff',
            'completed': '#28a745',
            'pending': '#fd7e14',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        # Header
        html += '<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">'
        html += f'<div>'
        html += f'<h2 style="margin: 0; font-size: 24px;">{obj.get_status_display()}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 13px;">Engagement #{obj.click_id[:16]}</p>'
        html += f'</div>'
        
        # Progress circle
        progress = int(obj.progress)
        html += f'<div style="width: 80px; height: 80px; background: rgba(255,255,255,0.2); border-radius: 50%; ' \
               f'display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold;">'
        html += f'{progress}%'
        html += '</div>'
        html += '</div>'
        
        # Stats grid
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">'
        
        stats = [
            ('User', obj.user.username),
            ('Offer', obj.offer.title[:20] + '...'),
            ('Reward', f'৳{obj.reward_earned}'),
            ('Time', f'{int(obj.time_spent / 60)}m' if obj.time_spent else 'N/A'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 3px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    engagement_overview.short_description = ''
    
    def user_details(self, obj):
        """User details"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">👤 User Information</h4>'
        html += '<table style="width: 100%; font-size: 12px;">'
        
        user_info = [
            ('Username', obj.user.username),
            ('Email', obj.user.email),
            ('Balance', f'৳{obj.user.balance:,.2f}'),
            ('IP Address', obj.ip_address or 'N/A'),
        ]
        
        for label, value in user_info:
            html += f'<tr><td style="padding: 5px 0; color: #6c757d;">{label}:</td>' \
                   f'<td style="padding: 5px 0; font-weight: 600; text-align: right;">{value}</td></tr>'
        
        html += '</table>'
        html += f'<a href="{reverse("admin:auth_user_change", args=[obj.user.pk])}" class="button" ' \
               'style="margin-top: 10px; display: inline-block;">View User Profile</a>'
        html += '</div>'
        
        return format_html(html)
    user_details.short_description = '👤 User Details'
    
    def offer_details(self, obj):
        """Offer details"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        
        if obj.offer.thumbnail:
            html += f'<img src="{obj.offer.thumbnail}" style="width: 100%; max-width: 300px; ' \
                   'border-radius: 8px; margin-bottom: 15px;"/>'
        
        html += f'<h4 style="margin-top: 0;">🎯 {obj.offer.title}</h4>'
        html += '<table style="width: 100%; font-size: 12px;">'
        
        offer_info = [
            ('Network', obj.offer.ad_network.name),
            ('Category', obj.offer.category.name if obj.offer.category else 'N/A'),
            ('Reward', f'৳{obj.offer.reward_amount}'),
            ('Difficulty', obj.offer.get_difficulty_display()),
            ('Estimated Time', f'{obj.offer.estimated_time} min'),
        ]
        
        for label, value in offer_info:
            html += f'<tr><td style="padding: 5px 0; color: #6c757d;">{label}:</td>' \
                   f'<td style="padding: 5px 0; font-weight: 600; text-align: right;">{value}</td></tr>'
        
        html += '</table>'
        html += f'<a href="{reverse("admin:ad_networks_offer_change", args=[obj.offer.pk])}" class="button" ' \
               'style="margin-top: 10px; display: inline-block;">View Offer Details</a>'
        html += '</div>'
        
        return format_html(html)
    offer_details.short_description = '🎯 Offer Details'
    
    def timeline_visualization(self, obj):
        """Timeline visualization"""
        html = '<div style="position: relative; padding: 20px 0;">'
        
        events = [
            ('Clicked', obj.clicked_at, '#17a2b8', '👆'),
            ('Started', obj.started_at, '#ffc107', '▶️'),
            ('Completed', obj.completed_at, '#28a745', '[OK]'),
            ('Verified', obj.verified_at, '#6f42c1', '🔍'),
            ('Rewarded', obj.rewarded_at, '#20c997', '🎁'),
        ]
        
        for i, (label, timestamp, color, icon) in enumerate(events):
            if timestamp:
                opacity = '1'
                time_display = timestamp.strftime('%b %d, %Y %H:%M')
            else:
                opacity = '0.3'
                time_display = 'Not yet'
            
            html += f'<div style="display: flex; align-items: center; margin-bottom: 20px; opacity: {opacity};">'
            
            # Timeline dot
            html += f'<div style="width: 40px; height: 40px; background: {color}; border-radius: 50%; ' \
                   f'display: flex; align-items: center; justify-content: center; font-size: 18px; ' \
                   f'box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: relative; z-index: 1;">{icon}</div>'
            
            # Timeline line
            if i < len(events) - 1:
                html += f'<div style="position: absolute; left: 19px; top: {40 + i * 60}px; ' \
                       f'width: 2px; height: 60px; background: {color if timestamp else "#dee2e6"};"></div>'
            
            # Event info
            html += f'<div style="margin-left: 15px; flex: 1;">'
            html += f'<div style="font-weight: 600; font-size: 14px; color: {color};">{label}</div>'
            html += f'<div style="color: #6c757d; font-size: 11px; margin-top: 2px;">{time_display}</div>'
            html += f'</div>'
            
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    timeline_visualization.short_description = '⏱️ Timeline'
    
    def device_location_info(self, obj):
        """Device and location information"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        
        # Device Info
        html += '<h4 style="margin-top: 0;">💻 Device Information</h4>'
        html += '<table style="width: 100%; font-size: 12px; margin-bottom: 15px;">'
        
        device_data = [
            ('Browser', obj.browser or 'Unknown'),
            ('Operating System', obj.os or 'Unknown'),
            ('User Agent', (obj.user_agent[:50] + '...') if obj.user_agent else 'N/A'),
            ('IP Address', obj.ip_address or 'N/A'),
        ]
        
        for label, value in device_data:
            html += f'<tr><td style="padding: 5px 0; color: #6c757d; width: 40%;">{label}:</td>' \
                   f'<td style="padding: 5px 0; font-weight: 600;">{value}</td></tr>'
        
        html += '</table>'
        
        # Location Data
        if obj.location_data:
            html += '<h4 style="margin-top: 15px;">🌍 Location Data</h4>'
            html += '<pre style="background: #fff; padding: 10px; border-radius: 5px; font-size: 11px; ' \
                   'overflow-x: auto;">'
            html += json.dumps(obj.location_data, indent=2)
            html += '</pre>'
        
        html += '</div>'
        
        return format_html(html)
    device_location_info.short_description = '💻 Device & Location'
    
    def verification_status(self, obj):
        """Verification status"""
        if obj.status == 'approved':
            bg_color = '#d4edda'
            text_color = '#155724'
            icon = '[OK]'
            title = 'Approved'
        elif obj.status == 'rejected':
            bg_color = '#f8d7da'
            text_color = '#721c24'
            icon = '[ERROR]'
            title = 'Rejected'
        elif obj.status == 'pending':
            bg_color = '#fff3cd'
            text_color = '#856404'
            icon = '⏳'
            title = 'Pending Verification'
        else:
            bg_color = '#d1ecf1'
            text_color = '#0c5460'
            icon = '[INFO]'
            title = 'Not Verified'
        
        html = f'<div style="background: {bg_color}; color: {text_color}; padding: 15px; ' \
               f'border-radius: 8px; border-left: 4px solid {text_color};">'
        
        html += f'<h3 style="margin: 0 0 10px 0;">{icon} {title}</h3>'
        
        if obj.verified_by:
            html += f'<p style="margin: 5px 0; font-size: 12px;">Verified by: <strong>{obj.verified_by.username}</strong></p>'
        
        if obj.verified_at:
            html += f'<p style="margin: 5px 0; font-size: 12px;">Verified at: <strong>{obj.verified_at.strftime("%b %d, %Y %H:%M")}</strong></p>'
        
        if obj.rejection_reason:
            html += f'<p style="margin: 10px 0 5px 0; font-size: 12px;"><strong>Rejection Reason:</strong></p>'
            html += f'<p style="margin: 5px 0; font-size: 12px;">{obj.get_rejection_reason_display()}</p>'
        
        if obj.rejection_details:
            html += f'<p style="margin: 5px 0; font-size: 12px;"><strong>Details:</strong> {obj.rejection_details}</p>'
        
        if obj.screenshot:
            html += f'<div style="margin-top: 10px;">'
            html += f'<img src="{obj.screenshot.url}" style="max-width: 100%; border-radius: 5px;"/>'
            html += f'</div>'
        
        html += '</div>'
        
        return format_html(html)
    verification_status.short_description = '[OK] Verification Status'
    
    # ==================== Actions ====================
    
    def approve_engagements(self, request, queryset):
        count = queryset.filter(status='pending').update(
            status='approved',
            verified_at=timezone.now(),
            verified_by=request.user
        )
        self.message_user(request, f'{count} engagements approved.')
    approve_engagements.short_description = '[OK] Approve selected engagements'
    
    def reject_engagements(self, request, queryset):
        count = queryset.filter(status='pending').update(
            status='rejected',
            verified_at=timezone.now(),
            verified_by=request.user,
            rejection_reason='other'
        )
        self.message_user(request, f'{count} engagements rejected.')
    reject_engagements.short_description = '[ERROR] Reject selected engagements'
    
    def mark_as_verified(self, request, queryset):
        count = queryset.update(
            verified_at=timezone.now(),
            verified_by=request.user
        )
        self.message_user(request, f'{count} engagements marked as verified.')
    mark_as_verified.short_description = '🔍 Mark as verified'
    
    def process_rewards(self, request, queryset):
        count = 0
        for engagement in queryset.filter(status='approved', rewarded_at__isnull=True):
            # Process reward
            engagement.user.balance += engagement.reward_earned
            engagement.user.save()
            engagement.rewarded_at = timezone.now()
            engagement.save()
            count += 1
        
        self.message_user(request, f'{count} rewards processed successfully.')
    process_rewards.short_description = '[MONEY] Process rewards'


# ==================== Offer Conversion Admin ====================

@admin.register(OfferConversion)
class OfferConversionAdmin(admin.ModelAdmin):
    list_display = [
        'conversion_badge',
        'user_offer_info',
        'payout_display',
        'status_indicator',
        'fraud_score_display',
        'verification_status',
        'payment_info',
        'created_display'
    ]
    
    list_filter = [
        'conversion_status',
        'is_verified',
        'risk_level',
        'chargeback_processed',
        'created_at',
    ]
    
    search_fields = [
        'engagement__user__username',
        'engagement__user__email',
        'engagement__offer__title',
        'payment_reference',
    ]
    
    readonly_fields = [
        'conversion_overview',
        'fraud_analysis',
        'payment_tracking',
        'postback_details',
        'created_at',
        'verified_at',
        'payment_date',
        'chargeback_at',
    ]
    
    fieldsets = (
        ('[STATS] Conversion Overview', {
            'fields': ('conversion_overview',),
            'classes': ('wide',)
        }),
        
        ('🔗 Engagement', {
            'fields': ('engagement',)
        }),
        
        ('[MONEY] Payout Information', {
            'fields': (
                ('payout', 'network_currency'),
                'exchange_rate',
                'postback_data',
            )
        }),
        
        ('[OK] Verification', {
            'fields': (
                'conversion_status',
                ('is_verified', 'verified_by'),
                'verified_at',
            )
        }),
        
        ('🚨 Fraud Detection', {
            'fields': (
                'fraud_analysis',
                ('fraud_score', 'risk_level'),
                'fraud_reasons',
            ),
            'classes': ('collapse',)
        }),
        
        ('↩️ Chargeback & Rejection', {
            'fields': (
                'rejection_reason',
                ('chargeback_at', 'chargeback_reason'),
                'chargeback_processed',
            ),
            'classes': ('collapse',)
        }),
        
        ('💳 Payment Tracking', {
            'fields': (
                'payment_tracking',
                ('payment_reference', 'payment_method'),
                'payment_date',
            ),
            'classes': ('collapse',)
        }),
        
        ('[STATS] Analytics', {
            'fields': (
                ('processing_time', 'retry_count'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Advanced', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    actions = [
        'approve_conversions',
        'mark_as_fraud',
        'process_chargebacks',
        'export_conversions'
    ]
    
    # ==================== Display Methods ====================
    
    def conversion_badge(self, obj):
        """Display conversion ID with status color"""
        status_colors = {
            'pending': '#ffc107',
            'verified': '#17a2b8',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'chargeback': '#6f42c1',
            'disputed': '#fd7e14',
            'paid': '#20c997',
        }
        color = status_colors.get(obj.conversion_status, '#6c757d')
        
        return format_html(
            '<div style="border-left: 4px solid {}; padding-left: 10px;">'
            '<div style="font-weight: bold; font-size: 11px; color: {};">#{}</div>'
            '<div style="font-size: 9px; color: #6c757d; margin-top: 2px;">{}</div>'
            '</div>',
            color,
            color,
            obj.pk,
            obj.get_conversion_status_display().upper()
        )
    conversion_badge.short_description = 'Conversion'
    
    def user_offer_info(self, obj):
        """Display user and offer info"""
        return format_html(
            '<div style="font-size: 11px;">'
            '<div style="font-weight: 600; margin-bottom: 3px;">👤 {}</div>'
            '<div style="color: #6c757d;">🎯 {}</div>'
            '</div>',
            obj.engagement.user.username,
            obj.engagement.offer.title[:30] + '...'
        )
    user_offer_info.short_description = 'User & Offer'
    
    def payout_display(self, obj):
        """Display payout information"""
        local_amount = obj.local_payout
        
        return format_html(
            '<div style="text-align: center; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); '
            'padding: 10px; border-radius: 8px; color: white;">'
            '<div style="font-size: 16px; font-weight: bold;">৳{:,.2f}</div>'
            '<div style="font-size: 8px; opacity: 0.9; margin-top: 2px;">{} {}</div>'
            '</div>',
            local_amount,
            obj.payout,
            obj.network_currency
        )
    payout_display.short_description = 'Payout'
    
    def status_indicator(self, obj):
        """Display status with icon"""
        status_config = {
            'pending': ('⏳', '#ffc107', 'Pending'),
            'verified': ('[OK]', '#17a2b8', 'Verified'),
            'approved': ('✓', '#28a745', 'Approved'),
            'rejected': ('[ERROR]', '#dc3545', 'Rejected'),
            'chargeback': ('↩️', '#6f42c1', 'Chargeback'),
            'disputed': ('[WARN]', '#fd7e14', 'Disputed'),
            'paid': ('[MONEY]', '#20c997', 'Paid'),
        }
        
        icon, color, label = status_config.get(obj.conversion_status, ('•', '#6c757d', 'Unknown'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div style="color: {}; font-weight: 600; font-size: 10px; margin-top: 3px;">{}</div>'
            '</div>',
            icon,
            color,
            label
        )
    status_indicator.short_description = 'Status'
    
    def fraud_score_display(self, obj):
        """Display fraud score"""
        score = obj.fraud_score
        
        if score >= 70:
            color = '#dc3545'
            label = 'HIGH RISK'
            icon = '🚨'
        elif score >= 40:
            color = '#ffc107'
            label = 'MEDIUM'
            icon = '[WARN]'
        else:
            color = '#28a745'
            label = 'LOW'
            icon = '[OK]'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 14px;">{:.0f}</div>'
            '<div style="color: {}; font-size: 9px; font-weight: 600;">{}</div>'
            '</div>',
            icon,
            color,
            score,
            color,
            label
        )
    fraud_score_display.short_description = 'Fraud Score'
    
    def verification_status(self, obj):
        """Display verification status"""
        if obj.is_verified:
            icon = '[OK]'
            color = '#28a745'
            text = 'Verified'
        else:
            icon = '⏳'
            color = '#ffc107'
            text = 'Unverified'
        
        html = f'<div style="text-align: center; color: {color};">'
        html += f'<div style="font-size: 18px;">{icon}</div>'
        html += f'<div style="font-size: 10px; font-weight: 600; margin-top: 2px;">{text}</div>'
        
        if obj.verified_by:
            html += f'<div style="font-size: 8px; color: #6c757d; margin-top: 2px;">by {obj.verified_by.username}</div>'
        
        html += '</div>'
        
        return format_html(html)
    verification_status.short_description = 'Verified'
    
    def payment_info(self, obj):
        """Display payment information"""
        if obj.payment_date:
            return format_html(
                '<div style="text-align: center; font-size: 10px;">'
                '<div style="color: #28a745; font-weight: 600;">💳 PAID</div>'
                '<div style="color: #6c757d; margin-top: 2px;">{}</div>'
                '</div>',
                obj.payment_date.strftime('%b %d')
            )
        elif obj.conversion_status == 'approved':
            return format_html(
                '<div style="text-align: center; font-size: 10px; color: #ffc107; font-weight: 600;">⏳ PENDING</div>'
            )
        else:
            return format_html('<div style="text-align: center; color: #6c757d;">—</div>')
    payment_info.short_description = 'Payment'
    
    def created_display(self, obj):
        """Display creation time"""
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m'
            color = '#28a745'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h'
            color = '#17a2b8'
        else:
            display = f'{time_ago.days}d'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    created_display.short_description = 'Age'
    
    # ==================== Readonly Summary Fields ====================
    def conversion_overview(self, obj=None):
        """Conversion overview with complete protection"""
        
        # ১. যদি object None হয় (add পেজের ক্ষেত্রে)
        if obj is None or not obj.pk:
            return format_html('<div style="padding: 20px; background: #f8f9fa; border-radius: 10px; text-align: center;">'
                              '<p style="margin: 0; color: #6c757d;">No conversion data available yet</p>'
                              '</div>')
        
        # ২. সেফটি চেক: সব ভ্যালু None-safe করা
        try:
            # local_payout property থেকে value নিন, যদি থাকে
            if hasattr(obj, 'local_payout'):
                local_payout_value = obj.local_payout or 0
            else:
                local_payout_value = 0
            
            # payout নেওয়ার সময় সেফ
            payout_value = getattr(obj, 'payout', 0) or 0
            network_currency = getattr(obj, 'network_currency', 'USD') or 'USD'
            
            # fraud_score সেফলি নেওয়া
            fraud_score_value = getattr(obj, 'fraud_score', 0)
            if fraud_score_value is None:
                fraud_score_value = 0
            
            # user নাম সেফলি নেওয়া
            username = "Unknown User"
            try:
                if obj.engagement and hasattr(obj.engagement, 'user'):
                    username = obj.engagement.user.username or "Unknown User"
            except:
                username = "Unknown User"
            
            # conversion_status সেফলি নেওয়া
            conversion_status = getattr(obj, 'conversion_status', 'pending') or 'pending'
            
            status_colors = {
                'pending': '#ffc107',
                'verified': '#17a2b8',
                'approved': '#28a745',
                'rejected': '#dc3545',
                'chargeback': '#6f42c1',
            }
            
            # Color নিরাপদভাবে নিন
            color = status_colors.get(conversion_status, '#6c757d')
            
            # ৩. HTML তৈরি করুন
            html = f'''
            <div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); 
                        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">
                
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin: 0; color: white;">Conversion #{obj.pk or "N/A"}</h2>
                        <p style="margin: 5px 0 0 0; opacity: 0.9;">{obj.get_conversion_status_display() if hasattr(obj, 'get_conversion_status_display') else 'Pending'}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 32px; font-weight: bold;">৳{local_payout_value:,.2f}</div>
                        <div style="font-size: 12px; opacity: 0.9;">{payout_value} {network_currency}</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 20px;">
            '''
            
            stats = [
                ('User', username),
                ('Fraud Score', f'{fraud_score_value:.0f}'),
                ('Verified', '[OK] Yes' if getattr(obj, 'is_verified', False) else '[ERROR] No'),
                ('Paid', '[OK] Yes' if getattr(obj, 'payment_date', None) else '⏳ No'),
            ]
            
            for label, value in stats:
                html += f'''
                <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10px; opacity: 0.9;">{label}</div>
                    <div style="font-size: 14px; font-weight: bold; margin-top: 3px;">{value}</div>
                </div>
                '''
            
            html += '</div></div>'
            
            return format_html(html)
        
        except Exception as e:
            # যদি কোনো error হয়, তো error দেখাবে না, বরং একটি সিম্পল message দেখাবে
            return format_html(f'''
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #dc3545;">
                <p style="margin: 0; color: #6c757d; font-weight: bold;">
                    Conversion overview could not be displayed
                </p>
                <p style="margin: 5px 0 0 0; color: #999; font-size: 12px;">
                    Error: {str(e)[:50]}...
                </p>
            </div>
            ''')

    # এই লাইনটি অবশ্যই ফাংশনের একদম নিচে এবং বাইরে থাকবে
    conversion_overview.short_description = 'Conversion Details'
    
    def fraud_analysis(self, obj):
        """Fraud analysis"""
        score = obj.fraud_score
        
        if score >= 70:
            bg_color = '#f8d7da'
            text_color = '#721c24'
            border_color = '#dc3545'
            risk_label = '🚨 HIGH RISK'
        elif score >= 40:
            bg_color = '#fff3cd'
            text_color = '#856404'
            border_color = '#ffc107'
            risk_label = '[WARN] MEDIUM RISK'
        else:
            bg_color = '#d4edda'
            text_color = '#155724'
            border_color = '#28a745'
            risk_label = '[OK] LOW RISK'
        
        html = f'<div style="background: {bg_color}; color: {text_color}; padding: 15px; ' \
               f'border-radius: 8px; border-left: 4px solid {border_color};">'
        
        html += f'<h3 style="margin: 0 0 15px 0;">{risk_label}</h3>'
        
        # Fraud score bar
        html += '<div style="margin-bottom: 15px;">'
        html += '<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12px;">'
        html += f'<span>Fraud Score</span><span style="font-weight: 600;">{score:.0f}/100</span>'
        html += '</div>'
        html += '<div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 10px; overflow: hidden;">'
        html += f'<div style="background: {border_color}; width: {score}%; height: 100%; border-radius: 10px;"></div>'
        html += '</div>'
        html += '</div>'
        
        # Fraud reasons
        if obj.fraud_reasons:
            html += '<div style="margin-top: 10px;">'
            html += '<strong style="font-size: 12px;">Fraud Indicators:</strong>'
            html += '<ul style="margin: 5px 0; padding-left: 20px; font-size: 11px;">'
            
            for reason in obj.fraud_reasons:
                html += f'<li>{reason}</li>'
            
            html += '</ul>'
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    fraud_analysis.short_description = '🔍 Fraud Analysis'
    
    def payment_tracking(self, obj):
        """Payment tracking information"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        payment_info = [
            ('Payment Reference', obj.payment_reference or 'Not assigned'),
            ('Payment Method', obj.payment_method or 'Not specified'),
            ('Payment Date', obj.payment_date.strftime('%B %d, %Y %H:%M') if obj.payment_date else 'Not paid'),
            ('Processing Time', f'{obj.processing_time}s'),
            ('Retry Count', obj.retry_count),
        ]
        
        for label, value in payment_info:
            html += f'<tr><td style="padding: 8px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>' \
                   f'<td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    payment_tracking.short_description = '💳 Payment Tracking'
    
    def postback_details(self, obj):
        """Postback data details"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">📬 Postback Data</h4>'
        html += '<pre style="background: #fff; padding: 10px; border-radius: 5px; font-size: 11px; overflow-x: auto; max-height: 300px;">'
        html += json.dumps(obj.postback_data, indent=2)
        html += '</pre>'
        html += '</div>'
        
        return format_html(html)
    postback_details.short_description = '📬 Postback Details'
    
    # ==================== Actions ====================
    
    def approve_conversions(self, request, queryset):
        count = queryset.filter(conversion_status='verified').update(
            conversion_status='approved',
            verified_by=request.user,
            verified_at=timezone.now()
        )
        self.message_user(request, f'{count} conversions approved.')
    approve_conversions.short_description = '[OK] Approve conversions'
    
    def mark_as_fraud(self, request, queryset):
        count = queryset.update(
            conversion_status='rejected',
            fraud_score=100,
            risk_level='high'
        )
        self.message_user(request, f'{count} conversions marked as fraud.')
    mark_as_fraud.short_description = '🚨 Mark as fraud'
    
    def process_chargebacks(self, request, queryset):
        count = queryset.filter(conversion_status='chargeback', chargeback_processed=False).update(
            chargeback_processed=True
        )
        self.message_user(request, f'{count} chargebacks processed.')
    process_chargebacks.short_description = '↩️ Process chargebacks'
    
    def export_conversions(self, request, queryset):
        self.message_user(request, 'Export feature coming soon.', level='info')
    export_conversions.short_description = '📥 Export conversions'
    
    
    # api/ad_networks/admin.py (continued)

# ==================== Blacklisted IP Admin ====================

@admin.register(BlacklistedIP)
class BlacklistedIPAdmin(admin.ModelAdmin):
    list_display = [
        'ip_badge',
        'reason_display',
        'status_indicator',
        'expiry_info',
        'created_display',
        'metadata_summary',
        'quick_actions'
    ]
    
    list_filter = [
        'reason',
        'is_active',
        'created_at',
        'expiry_date',
    ]
    
    search_fields = [
        'ip_address',
        'metadata',
    ]
    
    readonly_fields = [
        'ip_overview',
        'expiry_countdown',
        'activity_timeline',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('🚫 IP Blacklist Overview', {
            'fields': ('ip_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 IP Information', {
            'fields': (
                'ip_address',
                'reason',
                'is_active',
            )
        }),
        
        ('⏰ Expiry Settings', {
            'fields': (
                'expiry_countdown',
                'expiry_date',
            ),
            'description': '[WARN] Leave empty for permanent block. Set date for temporary block.'
        }),
        
        ('[STATS] Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('📅 Activity Timeline', {
            'fields': (
                'activity_timeline',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    actions = [
        'activate_ips',
        'deactivate_ips',
        'extend_expiry',
        'make_permanent',
        'cleanup_expired',
        'export_blacklist'
    ]
    
    # ==================== Display Methods ====================
    
    def ip_badge(self, obj):
        """Display IP address with visual indicator"""
        if obj.is_effectively_active:
            color = '#dc3545'
            icon = '🚫'
            status = 'BLOCKED'
        else:
            color = '#6c757d'
            icon = '[OK]'
            status = 'INACTIVE'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div>'
            '<div style="font-family: monospace; font-weight: 600; font-size: 13px; color: {};">{}</div>'
            '<div style="font-size: 9px; color: {}; font-weight: 600; margin-top: 2px;">{}</div>'
            '</div>'
            '</div>',
            icon,
            color,
            obj.ip_address,
            color,
            status
        )
    ip_badge.short_description = 'IP Address'
    
    def reason_display(self, obj):
        """Display reason with color coding"""
        reason_config = {
            'fraud': ('#dc3545', '🚨', 'Fraud'),
            'bot': ('#6f42c1', '🤖', 'Bot'),
            'vpn': ('#fd7e14', '[SECURE]', 'VPN/Proxy'),
            'datacenter': ('#17a2b8', '🏢', 'Datacenter'),
            'abuse': ('#e83e8c', '[WARN]', 'Abuse'),
            'manual': ('#6c757d', '✋', 'Manual'),
            'test': ('#20c997', '🧪', 'Test'),
        }
        
        color, icon, label = reason_config.get(obj.reason, ('#6c757d', '•', 'Unknown'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600; margin-top: 5px; display: inline-block;">{}</div>'
            '</div>',
            icon,
            color,
            label
        )
    reason_display.short_description = 'Reason'
    
    def status_indicator(self, obj):
        """Display current status"""
        if obj.is_effectively_active:
            if obj.expiry_date:
                bg_color = '#ffc107'
                icon = '⏳'
                text = 'TEMP BLOCK'
            else:
                bg_color = '#dc3545'
                icon = '🔒'
                text = 'PERMANENT'
        else:
            bg_color = '#6c757d'
            icon = '[OK]'
            text = 'INACTIVE'
        
        return format_html(
            '<div style="text-align: center; background: {}; color: white; '
            'padding: 10px; border-radius: 8px;">'
            '<div style="font-size: 20px;">{}</div>'
            '<div style="font-size: 9px; font-weight: 600; margin-top: 3px;">{}</div>'
            '</div>',
            bg_color,
            icon,
            text
        )
    status_indicator.short_description = 'Status'
    
    def expiry_info(self, obj):
        """Display expiry information"""
        if not obj.expiry_date:
            return format_html(
                '<div style="text-align: center; color: #dc3545; font-weight: 600;">'
                '<div style="font-size: 18px;">∞</div>'
                '<div style="font-size: 9px; margin-top: 2px;">PERMANENT</div>'
                '</div>'
            )
        
        now = timezone.now()
        time_diff = obj.expiry_date - now
        
        if time_diff.total_seconds() <= 0:
            return format_html(
                '<div style="text-align: center; color: #28a745; font-weight: 600;">'
                '<div style="font-size: 18px;">✓</div>'
                '<div style="font-size: 9px; margin-top: 2px;">EXPIRED</div>'
                '</div>'
            )
        
        days = time_diff.days
        hours = int(time_diff.seconds / 3600)
        
        if days > 0:
            display = f'{days}d {hours}h'
            color = '#ffc107'
        elif hours > 0:
            display = f'{hours}h'
            color = '#fd7e14'
        else:
            minutes = int(time_diff.seconds / 60)
            display = f'{minutes}m'
            color = '#dc3545'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-weight: 600;">'
            '<div style="font-size: 14px;">{}</div>'
            '<div style="font-size: 8px; margin-top: 2px;">REMAINING</div>'
            '<div style="font-size: 9px; color: #6c757d; margin-top: 3px;">{}</div>'
            '</div>',
            color,
            display,
            obj.expiry_date.strftime('%b %d, %H:%M')
        )
    expiry_info.short_description = 'Expiry'
    
    def created_display(self, obj):
        """Display creation time"""
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
            color = '#dc3545'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#ffc107'
        else:
            display = f'{time_ago.days}d ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    created_display.short_description = 'Created'
    
    def metadata_summary(self, obj):
        """Display metadata summary"""
        if obj.metadata:
            count = len(obj.metadata)
            return format_html(
                '<div style="text-align: center; font-size: 11px; color: #6c757d;">'
                '[STATS] {} fields'
                '</div>',
                count
            )
        return format_html('<div style="text-align: center; color: #dee2e6;">—</div>')
    metadata_summary.short_description = 'Metadata'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        buttons = []
        
        if obj.is_active:
            buttons.append(
                '<a href="#" class="button" style="background: #28a745; color: white; '
                'font-size: 10px; padding: 4px 8px; text-decoration: none; border-radius: 3px;">✓ Unblock</a>'
            )
        else:
            buttons.append(
                '<a href="#" class="button" style="background: #dc3545; color: white; '
                'font-size: 10px; padding: 4px 8px; text-decoration: none; border-radius: 3px;">🚫 Block</a>'
            )
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 3px;">{}</div>',
            ''.join(buttons)
        )
    quick_actions.short_description = 'Actions'
    
    # ==================== Readonly Summary Fields ====================
    
    def ip_overview(self, obj):
        """IP blacklist overview"""
        if obj.is_effectively_active:
            if obj.expiry_date:
                bg_gradient = 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
                status_text = 'Temporarily Blocked'
            else:
                bg_gradient = 'linear-gradient(135deg, #ff0844 0%, #ffb199 100%)'
                status_text = 'Permanently Blocked'
        else:
            bg_gradient = 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)'
            status_text = 'Inactive / Expired'
        
        html = f'<div style="background: {bg_gradient}; ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        # Header
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">'
        html += '<div>'
        html += f'<div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">{status_text}</div>'
        html += f'<h2 style="margin: 0; font-size: 32px; font-family: monospace;">{obj.ip_address}</h2>'
        html += '</div>'
        
        # Status icon
        icon = '🚫' if obj.is_effectively_active else '[OK]'
        html += f'<div style="font-size: 64px; opacity: 0.3;">{icon}</div>'
        
        html += '</div>'
        
        # Quick stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">'
        
        reason_label = obj.get_reason_display()
        created = obj.created_at.strftime('%b %d, %Y')
        
        if obj.expiry_date:
            if obj.is_expired:
                expiry_display = 'Expired'
            else:
                time_left = obj.expiry_date - timezone.now()
                days = time_left.days
                hours = int(time_left.seconds / 3600)
                expiry_display = f'{days}d {hours}h left'
        else:
            expiry_display = 'Never'
        
        stats = [
            ('Reason', reason_label),
            ('Created', created),
            ('Expires', expiry_display),
            ('Status', 'Active' if obj.is_active else 'Inactive'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    ip_overview.short_description = ''
    
    def expiry_countdown(self, obj):
        """Expiry countdown visualization"""
        if not obj.expiry_date:
            return format_html(
                '<div style="background: #f8d7da; color: #721c24; padding: 20px; '
                'border-radius: 8px; text-align: center; border-left: 4px solid #dc3545;">'
                '<div style="font-size: 48px; margin-bottom: 10px;">∞</div>'
                '<h3 style="margin: 0;">PERMANENT BLOCK</h3>'
                '<p style="margin: 10px 0 0 0; opacity: 0.8;">This IP is permanently blocked</p>'
                '</div>'
            )
        
        now = timezone.now()
        
        if obj.is_expired:
            return format_html(
                '<div style="background: #d4edda; color: #155724; padding: 20px; '
                'border-radius: 8px; text-align: center; border-left: 4px solid #28a745;">'
                '<div style="font-size: 48px; margin-bottom: 10px;">[OK]</div>'
                '<h3 style="margin: 0;">EXPIRED</h3>'
                '<p style="margin: 10px 0 0 0; opacity: 0.8;">Expired on {}</p>'
                '</div>',
                obj.expiry_date.strftime('%B %d, %Y at %H:%M')
            )
        
        time_left = obj.expiry_date - now
        total_seconds = time_left.total_seconds()
        
        days = time_left.days
        hours = int((total_seconds % 86400) / 3600)
        minutes = int((total_seconds % 3600) / 60)
        seconds = int(total_seconds % 60)
        
        # Calculate percentage (assume 90 days max for visualization)
        max_duration = 90 * 24 * 3600
        percentage = min((total_seconds / max_duration) * 100, 100)
        
        if percentage > 66:
            bar_color = '#28a745'
        elif percentage > 33:
            bar_color = '#ffc107'
        else:
            bar_color = '#dc3545'
        
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0; text-align: center; color: #495057;">⏳ Time Until Expiry</h4>'
        
        # Countdown display
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;">'
        
        countdown_items = [
            (days, 'Days'),
            (hours, 'Hours'),
            (minutes, 'Minutes'),
            (seconds, 'Seconds'),
        ]
        
        for value, label in countdown_items:
            html += '<div style="background: white; padding: 15px; border-radius: 8px; text-align: center; border: 2px solid #e9ecef;">'
            html += f'<div style="font-size: 32px; font-weight: bold; color: {bar_color};">{value:02d}</div>'
            html += f'<div style="font-size: 11px; color: #6c757d; margin-top: 5px;">{label}</div>'
            html += '</div>'
        
        html += '</div>'
        
        # Progress bar
        html += '<div style="margin-bottom: 10px;">'
        html += '<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12px; color: #6c757d;">'
        html += '<span>Progress</span>'
        html += f'<span>{percentage:.1f}%</span>'
        html += '</div>'
        html += '<div style="background: #e9ecef; border-radius: 10px; height: 12px; overflow: hidden;">'
        html += f'<div style="background: {bar_color}; width: {percentage}%; height: 100%; border-radius: 10px; transition: width 0.3s;"></div>'
        html += '</div>'
        html += '</div>'
        
        # Expiry date
        html += f'<div style="text-align: center; color: #6c757d; font-size: 13px; margin-top: 15px;">'
        html += f'📅 Expires on: <strong>{obj.expiry_date.strftime("%B %d, %Y at %H:%M")}</strong>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    expiry_countdown.short_description = '⏳ Expiry Countdown'
    
    def activity_timeline(self, obj):
        """Activity timeline"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        timeline_events = [
            ('Created', obj.created_at, '#17a2b8'),
            ('Last Updated', obj.updated_at, '#6c757d'),
        ]
        
        if obj.expiry_date:
            timeline_events.append(('Expires', obj.expiry_date, '#ffc107'))
        
        for label, timestamp, color in timeline_events:
            html += f'<tr><td style="padding: 10px 0; color: #6c757d; border-bottom: 1px solid #dee2e6; width: 30%;">{label}</td>'
            html += f'<td style="padding: 10px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6; color: {color};">'
            html += timestamp.strftime('%B %d, %Y %H:%M:%S')
            html += '</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    activity_timeline.short_description = '📅 Activity Timeline'
    
    # ==================== Actions ====================
    
    def activate_ips(self, request, queryset):
        """Activate selected IPs"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} IP addresses activated (blocked).')
    activate_ips.short_description = '🚫 Activate (Block) selected IPs'
    
    def deactivate_ips(self, request, queryset):
        """Deactivate selected IPs"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} IP addresses deactivated (unblocked).')
    deactivate_ips.short_description = '[OK] Deactivate (Unblock) selected IPs'
    
    def extend_expiry(self, request, queryset):
        """Extend expiry by 30 days"""
        from datetime import timedelta
        
        count = 0
        for ip in queryset:
            if ip.expiry_date:
                ip.expiry_date = ip.expiry_date + timedelta(days=30)
                ip.save()
                count += 1
        
        self.message_user(request, f'{count} IP expiry dates extended by 30 days.')
    extend_expiry.short_description = '⏰ Extend expiry by 30 days'
    
    def make_permanent(self, request, queryset):
        """Make blocks permanent"""
        count = queryset.update(expiry_date=None, is_active=True)
        self.message_user(request, f'{count} IP blocks made permanent.')
    make_permanent.short_description = '♾️ Make permanent'
    
    def cleanup_expired(self, request, queryset):
        """Cleanup expired entries"""
        stats = BlacklistedIP.cleanup_expired_entries()
        
        self.message_user(
            request,
            f'Cleanup complete: {stats["deactivated"]} expired IPs deactivated.',
            level='success'
        )
    cleanup_expired.short_description = '🧹 Cleanup expired IPs'
    
    def export_blacklist(self, request, queryset):
        """Export blacklist"""
        self.message_user(request, 'Export feature coming soon.', level='info')
    export_blacklist.short_description = '📥 Export blacklist'
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist"""
        extra_context = extra_context or {}
        
        stats = BlacklistedIP.get_statistics()
        extra_context['blacklist_stats'] = stats
        
        return super().changelist_view(request, extra_context=extra_context)


# ==================== Known Bad IP Admin ====================

@admin.register(KnownBadIP)
class KnownBadIPAdmin(admin.ModelAdmin):
    list_display = [
        'ip_display',
        'threat_badge',
        'confidence_display',
        'source_badge',
        'status_display',
        'expiry_display',
        'last_seen_display',
    ]
    
    list_filter = [
        'threat_type',
        'source',
        'is_active',
        'confidence_score',
        'first_seen',
        'last_seen',
    ]
    
    search_fields = [
        'ip_address',
        'description',
    ]
    
    readonly_fields = [
        'threat_overview',
        'confidence_meter',
        'activity_info',
        'first_seen',
        'last_seen',
    ]
    
    fieldsets = (
        ('🔍 Threat Overview', {
            'fields': ('threat_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 IP Information', {
            'fields': (
                'ip_address',
                'threat_type',
                'source',
                'is_active',
            )
        }),
        
        ('[STATS] Threat Assessment', {
            'fields': (
                'confidence_meter',
                'confidence_score',
                'description',
            )
        }),
        
        ('⏰ Expiry & Activity', {
            'fields': (
                'expires_at',
                'activity_info',
                'first_seen',
                'last_seen',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'first_seen'
    
    actions = [
        'mark_as_active',
        'mark_as_inactive',
        'increase_confidence',
        'decrease_confidence',
        'remove_expired'
    ]
    
    # ==================== Display Methods ====================
    
    def ip_display(self, obj):
        """Display IP with icon"""
        return format_html(
            '<div style="font-family: monospace; font-weight: 600; font-size: 13px;">'
            '🌐 {}'
            '</div>',
            obj.ip_address
        )
    ip_display.short_description = 'IP Address'
    
    def threat_badge(self, obj):
        """Display threat type badge"""
        threat_config = {
            'bot': ('#6f42c1', '🤖'),
            'vpn': ('#fd7e14', '[SECURE]'),
            'scanner': ('#dc3545', '🔍'),
            'spam': ('#e83e8c', '📧'),
            'malware': ('#dc3545', '🦠'),
            'phishing': ('#dc3545', '🎣'),
            'ddos': ('#6f42c1', '💥'),
            'credential_stuffing': ('#dc3545', '[KEY]'),
        }
        
        color, icon = threat_config.get(obj.threat_type, ('#6c757d', '[WARN]'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px; margin-bottom: 5px;">{}</div>'
            '<div style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 9px; font-weight: 600; display: inline-block;">{}</div>'
            '</div>',
            icon,
            color,
            obj.get_threat_type_display().upper()
        )
    threat_badge.short_description = 'Threat Type'
    
    def confidence_display(self, obj):
        """Display confidence score"""
        score = obj.confidence_score
        
        if score >= 80:
            color = '#dc3545'
            label = 'HIGH'
            icon = '🔴'
        elif score >= 50:
            color = '#ffc107'
            label = 'MEDIUM'
            icon = '🟡'
        else:
            color = '#28a745'
            label = 'LOW'
            icon = '🟢'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px; margin-bottom: 3px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 16px;">{}</div>'
            '<div style="color: {}; font-size: 9px; font-weight: 600; margin-top: 2px;">{}</div>'
            '</div>',
            icon,
            color,
            score,
            color,
            label
        )
    confidence_display.short_description = 'Confidence'
    
    def source_badge(self, obj):
        """Display source badge"""
        source_colors = {
            'internal': '#17a2b8',
            'ipqualityscore': '#6f42c1',
            'abuseipdb': '#dc3545',
            'maxmind': '#fd7e14',
            'firehol': '#28a745',
            'custom': '#6c757d',
        }
        
        color = source_colors.get(obj.source, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 10px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_source_display()
        )
    source_badge.short_description = 'Source'
    
    def status_display(self, obj):
        """Display active status"""
        if obj.is_active:
            if obj.is_expired():
                return format_html(
                    '<span style="background: #6c757d; color: white; padding: 4px 10px; '
                    'border-radius: 12px; font-size: 10px;">⏰ EXPIRED</span>'
                )
            else:
                return format_html(
                    '<span style="background: #28a745; color: white; padding: 4px 10px; '
                    'border-radius: 12px; font-size: 10px;">✓ ACTIVE</span>'
                )
        else:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✗ INACTIVE</span>'
            )
    status_display.short_description = 'Status'
    
    def expiry_display(self, obj):
        """Display expiry info"""
        if not obj.expires_at:
            return format_html('<span style="color: #6c757d;">Never</span>')
        
        if obj.is_expired():
            return format_html(
                '<div style="text-align: center; color: #dc3545; font-size: 11px; font-weight: 600;">EXPIRED</div>'
            )
        
        time_left = obj.expires_at - timezone.now()
        days = time_left.days
        
        if days > 30:
            display = f'{days}d'
            color = '#28a745'
        elif days > 7:
            display = f'{days}d'
            color = '#ffc107'
        else:
            display = f'{days}d'
            color = '#dc3545'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    expiry_display.short_description = 'Expires'
    
    def last_seen_display(self, obj):
        """Display last seen time"""
        time_ago = timezone.now() - obj.last_seen
        
        if time_ago < timedelta(hours=1):
            display = 'Just now'
            color = '#dc3545'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#ffc107'
        else:
            display = f'{time_ago.days}d ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px;">{}</div>',
            color,
            display
        )
    last_seen_display.short_description = 'Last Seen'
    
    # ==================== Readonly Summary Fields ====================
    
    def threat_overview(self, obj):
        """Threat overview"""
        threat_colors = {
            'bot': '#6f42c1',
            'vpn': '#fd7e14',
            'scanner': '#dc3545',
            'spam': '#e83e8c',
            'malware': '#dc3545',
            'phishing': '#dc3545',
            'ddos': '#6f42c1',
            'credential_stuffing': '#dc3545',
        }
        
        color = threat_colors.get(obj.threat_type, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        # Header
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += f'<h2 style="margin: 0; font-size: 28px; font-family: monospace;">{obj.ip_address}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">{obj.get_threat_type_display()}</p>'
        html += '</div>'
        
        # Confidence badge
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 15px 25px; border-radius: 50px;">'
        html += f'<div style="font-size: 28px; font-weight: bold;">{obj.confidence_score}%</div>'
        html += f'<div style="font-size: 10px; opacity: 0.9;">CONFIDENCE</div>'
        html += '</div>'
        
        html += '</div>'
        
        # Quick stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Source', obj.get_source_display()),
            ('First Seen', obj.first_seen.strftime('%b %d')),
            ('Last Seen', obj.last_seen.strftime('%b %d')),
            ('Status', 'Active' if obj.is_active else 'Inactive'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    threat_overview.short_description = ''
    
    def confidence_meter(self, obj):
        """Confidence meter visualization"""
        score = obj.confidence_score
        
        if score >= 80:
            bar_color = '#dc3545'
            bg_color = '#f8d7da'
            text_color = '#721c24'
            label = 'HIGH CONFIDENCE THREAT'
        elif score >= 50:
            bar_color = '#ffc107'
            bg_color = '#fff3cd'
            text_color = '#856404'
            label = 'MEDIUM CONFIDENCE'
        else:
            bar_color = '#28a745'
            bg_color = '#d4edda'
            text_color = '#155724'
            label = 'LOW CONFIDENCE'
        
        html = f'<div style="background: {bg_color}; color: {text_color}; padding: 20px; ' \
               f'border-radius: 8px; border-left: 4px solid {bar_color};">'
        
        html += f'<h3 style="margin: 0 0 15px 0;">{label}</h3>'
        
        # Confidence bar
        html += '<div style="margin-bottom: 10px;">'
        html += '<div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px;">'
        html += f'<span style="font-weight: 600;">Confidence Score</span>'
        html += f'<span style="font-weight: bold; font-size: 16px;">{score}%</span>'
        html += '</div>'
        html += '<div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 20px; overflow: hidden;">'
        html += f'<div style="background: {bar_color}; width: {score}%; height: 100%; border-radius: 10px; ' \
               'display: flex; align-items: center; justify-content: center; color: white; font-size: 11px; font-weight: 600;">'
        
        if score > 10:
            html += f'{score}%'
        
        html += '</div></div></div>'
        
        # Recommendation
        if score >= 80:
            html += '<p style="margin: 15px 0 0 0; font-size: 13px; opacity: 0.9;">' \
                   '[WARN] <strong>Recommendation:</strong> This IP should be blocked immediately.</p>'
        elif score >= 50:
            html += '<p style="margin: 15px 0 0 0; font-size: 13px; opacity: 0.9;">' \
                   '[INFO] <strong>Recommendation:</strong> Monitor this IP closely for suspicious activity.</p>'
        else:
            html += '<p style="margin: 15px 0 0 0; font-size: 13px; opacity: 0.9;">' \
                   '✓ <strong>Recommendation:</strong> Low threat level. Review periodically.</p>'
        
        html += '</div>'
        
        return format_html(html)
    confidence_meter.short_description = '[STATS] Confidence Assessment'
    


    def activity_info(self, obj=None):
        """Advanced defensive coding with full protection"""
        
        # ১. Helper functions (এগুলো ফাংশনের ভেতরেই থাকবে)
        def get_safe_datetime(obj_attr, default=None):
            """Safely get datetime attribute"""
            if obj is None:
                return default
            
            # Method 1: Try getattr
            value = getattr(obj, obj_attr, default)
            
            # Method 2: Check if it's a callable
            if callable(value):
                try:
                    return value()
                except:
                    return default
            
            # Method 3: Check if it's a property
            if value is None and hasattr(obj.__class__, obj_attr):
                attr = getattr(obj.__class__, obj_attr, None)
                if isinstance(attr, property):
                    try:
                        return attr.fget(obj)
                    except:
                        return default
            
            return value
        
        def format_duration(dt1, dt2):
            """Safely format duration between two datetimes"""
            if not dt1 or not dt2:
                return "Not available"
            
            try:
                # Ensure both are datetime objects
                if isinstance(dt1, str):
                    dt1 = datetime.fromisoformat(dt1.replace('Z', '+00:00'))
                if isinstance(dt2, str):
                    dt2 = datetime.fromisoformat(dt2.replace('Z', '+00:00'))
                
                diff = dt2 - dt1
                days = diff.days
                hours = diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                
                parts = []
                if days > 0:
                    parts.append(f"{days} days")
                if hours > 0:
                    parts.append(f"{hours} hours")
                if minutes > 0 and days == 0:  # Only show minutes if less than a day
                    parts.append(f"{minutes} minutes")
                
                return ", ".join(parts) if parts else "Less than a minute"
            except Exception:
                return "Duration calculation failed"
        
        def is_expired_safe(expires_at):
            """Safely check if expired"""
            if not expires_at:
                return False
            
            try:
                now = timezone.now()
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                return now > expires_at
            except Exception:
                return False
        
        # ২. Main logic with full protection
        try:
            if obj is None or not hasattr(obj, 'pk') or not obj.pk:
                return format_html(
                    '<div class="alert alert-info" style="padding:10px; background:#e1f5fe; border-radius:5px;">No data available</div>'
                )
            
            # Get all values safely
            first_seen = get_safe_datetime('first_seen')
            last_seen = get_safe_datetime('last_seen')
            expires_at = get_safe_datetime('expires_at')
            
            # Create data table
            html = '<div class="activity-info">'
            html += '<table class="activity-table" style="width:100%; border-collapse: collapse;">'
            
            rows = [
                ('First Seen', first_seen.strftime('%Y-%m-%d %H:%M') 
                 if first_seen and hasattr(first_seen, 'strftime') else 'Not recorded'),
                
                ('Last Seen', last_seen.strftime('%Y-%m-%d %H:%M') 
                 if last_seen and hasattr(last_seen, 'strftime') else 'Not recorded'),
                
                ('Activity Duration', format_duration(first_seen, last_seen)),
                
                ('Expires At', expires_at.strftime('%Y-%m-%d') 
                 if expires_at and hasattr(expires_at, 'strftime') else 'Never'),
                
                ('Is Expired', 
                 '<span style="color: #dc3545; font-weight:bold;">[OK] Yes</span>' 
                 if is_expired_safe(expires_at) 
                 else '<span style="color: #28a745; font-weight:bold;">[ERROR] No</span>')
            ]
            
            for label, value in rows:
                html += f'''
                <tr style="border-bottom: 1px solid #eee;">
                    <td class="label-cell" style="padding: 8px; font-weight: bold; color: #555;">{label}</td>
                    <td class="value-cell" style="padding: 8px; color: #333;">{value}</td>
                </tr>
                '''
            
            html += '</table></div>'
            return format_html(html)
            
        except Exception as e:
            # Log the error but don't crash the admin
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in activity_info: {str(e)}", exc_info=True)
            
            return format_html(
                f'<div style="color: #856404; background-color: #fff3cd; padding: 10px; border: 1px solid #ffeeba; border-radius: 5px;">'
                f'Could not display activity info. Error: {type(e).__name__}'
                f'</div>'
            )

    # ডেসক্রিপশন সেট করা (ফাংশনের বাইরে)
    activity_info.short_description = '📅 Activity Information'
    
    # ==================== Actions ====================
    
    def mark_as_active(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} IPs marked as active.')
    mark_as_active.short_description = '✓ Mark as active'
    
    def mark_as_inactive(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} IPs marked as inactive.')
    mark_as_inactive.short_description = '✗ Mark as inactive'
    
    def increase_confidence(self, request, queryset):
        for ip in queryset:
            ip.confidence_score = min(ip.confidence_score + 10, 100)
            ip.save()
        
        self.message_user(request, f'{queryset.count()} IP confidence scores increased.')
    increase_confidence.short_description = '⬆️ Increase confidence (+10)'
    
    def decrease_confidence(self, request, queryset):
        for ip in queryset:
            ip.confidence_score = max(ip.confidence_score - 10, 0)
            ip.save()
        
        self.message_user(request, f'{queryset.count()} IP confidence scores decreased.')
    decrease_confidence.short_description = '⬇️ Decrease confidence (-10)'
    
    def remove_expired(self, request, queryset):
        count = 0
        for ip in queryset:
            if ip.is_expired():
                ip.delete()
                count += 1
        
        self.message_user(request, f'{count} expired IPs removed.')
    remove_expired.short_description = '[DELETE] Remove expired IPs'


# ==================== Fraud Detection Rule Admin ====================

@admin.register(FraudDetectionRule)
class FraudDetectionRuleAdmin(admin.ModelAdmin):
    list_display = [
        'rule_name',
        'type_badge',
        'severity_badge',
        'action_badge',
        'status_indicator',
        'priority_display',
        'created_display'
    ]
    
    list_filter = [
        'rule_type',
        'action',
        'severity',
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'description',
    ]
    
    readonly_fields = [
        'rule_overview',
        'condition_details',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('🛡️ Rule Overview', {
            'fields': ('rule_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Basic Information', {
            'fields': (
                'name',
                'description',
                'rule_type',
            )
        }),
        
        ('⚙️ Configuration', {
            'fields': (
                'condition_details',
                'condition',
                'action',
                ('severity', 'priority'),
                'is_active',
            )
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # ==================== Display Methods ====================
    
    def rule_name(self, obj):
        """Display rule name with icon"""
        return format_html(
            '<div style="font-weight: 600; font-size: 13px;">🛡️ {}</div>',
            obj.name
        )
    rule_name.short_description = 'Rule Name'
    
    def type_badge(self, obj):
        """Display rule type"""
        type_colors = {
            'ip': '#17a2b8',
            'device': '#6f42c1',
            'behavior': '#fd7e14',
            'velocity': '#e83e8c',
            'pattern': '#28a745',
        }
        
        color = type_colors.get(obj.rule_type, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_rule_type_display()
        )
    type_badge.short_description = 'Type'
    
    def severity_badge(self, obj):
        """Display severity"""
        severity_config = {
            'low': ('#28a745', '[INFO]'),
            'medium': ('#ffc107', '[WARN]'),
            'high': ('#fd7e14', '[WARN]'),
            'critical': ('#dc3545', '🚨'),
        }
        
        color, icon = severity_config.get(obj.severity, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 18px;">{}</div>'
            '<div style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 9px; font-weight: 600; margin-top: 3px; display: inline-block;">{}</div>'
            '</div>',
            icon,
            color,
            obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'
    
    def action_badge(self, obj):
        """Display action"""
        action_colors = {
            'block': '#dc3545',
            'flag': '#ffc107',
            'review': '#17a2b8',
            'limit': '#fd7e14',
        }
        
        color = action_colors.get(obj.action, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_action_display().upper()
        )
    action_badge.short_description = 'Action'
    
    def status_indicator(self, obj):
        """Display status"""
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✗ INACTIVE</span>'
        )
    status_indicator.short_description = 'Status'
    
    def priority_display(self, obj):
        """Display priority"""
        if obj.priority >= 10:
            color = '#dc3545'
            icon = '🔴'
        elif obj.priority >= 5:
            color = '#ffc107'
            icon = '🟡'
        else:
            color = '#28a745'
            icon = '🟢'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-weight: 600;">'
            '<div style="font-size: 18px;">{}</div>'
            '<div style="font-size: 12px;">{}</div>'
            '</div>',
            color,
            icon,
            obj.priority
        )
    priority_display.short_description = 'Priority'
    
    def created_display(self, obj):
        """Display creation time"""
        return format_html(
            '<div style="font-size: 11px; color: #6c757d;">{}</div>',
            obj.created_at.strftime('%b %d, %Y')
        )
    created_display.short_description = 'Created'
    
    # ==================== Readonly Fields ====================
    
    def rule_overview(self, obj):
        """Rule overview"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545',
        }
        
        color = severity_colors.get(obj.severity, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0 0 10px 0;">{obj.name}</h2>'
        html += f'<p style="margin: 0; opacity: 0.9;">{obj.description or "No description"}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 15px;">'
        
        stats = [
            ('Type', obj.get_rule_type_display()),
            ('Action', obj.get_action_display()),
            ('Severity', obj.get_severity_display()),
            ('Priority', obj.priority),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 3px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    rule_overview.short_description = ''
    
    def condition_details(self, obj=None):
        """Display condition details with complete defensive coding"""
        
        # 1. Null Object Pattern - যদি object None হয় বা নতুন এন্ট্রি হয়
        if obj is None or not getattr(obj, 'pk', None):
            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">'
                '<p style="margin: 0; color: #6c757d;">'
                '[WARN] No rule selected. Conditions will be displayed after saving.'
                '</p>'
                '</div>'
            )
        
        # 2. Graceful Degradation - সবকিছু try-except-এ wrap
        try:
            # 3. Type Hinting & Validation - condition attribute exists কিনা চেক
            if not hasattr(obj, 'condition'):
                return format_html('<div style="color: orange;">Object has no condition attribute</div>')
            
            # 4. Get condition safely
            condition_data = getattr(obj, 'condition', {})
            
            # 5. Validate type - ensure it's dict-like
            if condition_data is None:
                condition_data = {}
            
            # 6. Convert to dict if it's JSON string
            if isinstance(condition_data, str):
                try:
                    condition_data = json.loads(condition_data)
                except json.JSONDecodeError:
                    condition_data = {"error": "Invalid JSON format", "raw": condition_data}
            
            # 7. Ensure it's serializable
            if not isinstance(condition_data, (dict, list)):
                condition_data = {"value": str(condition_data)}
            
            # 8. Format JSON with error handling
            try:
                formatted_json = json.dumps(condition_data, indent=2, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                formatted_json = json.dumps({
                    "error": "Could not serialize condition",
                    "message": str(e),
                    "raw_type": str(type(condition_data)),
                    "raw_value": str(condition_data)[:500]
                }, indent=2)
            
            # 9. Create HTML with safety checks
            rule_type = getattr(obj, 'rule_type', 'unknown')
            html = f'''
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="margin: 0; color: #343a40;">[FIX] Rule Conditions</h4>
                    <span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">
                        {rule_type.upper()}
                    </span>
                </div>
            '''
            
            # Condition statistics if it's a dict
            if isinstance(condition_data, dict) and condition_data:
                stats = []
                stats.append(f'Keys: {len(condition_data)}')
                
                common_keys = ['threshold', 'limit', 'count', 'period', 'operator']
                found_keys = [k for k in common_keys if k in condition_data]
                if found_keys:
                    stats.append(f'Rules: {", ".join(found_keys)}')
                
                severity = getattr(obj, 'severity', 'medium')
                severity_colors = {
                    'low': '#28a745',
                    'medium': '#ffc107',
                    'high': '#fd7e14',
                    'critical': '#dc3545'
                }
                stats.append(f'Severity: <span style="color: {severity_colors.get(severity, "#6c757d")}; font-weight: 600;">{severity.upper()}</span>')
                
                html += f'<div style="background: #e9ecef; padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 12px;">'
                html += ' | '.join(stats)
                html += '</div>'
            
            # JSON display with scroll protection
            html += f'''
            <div style="position: relative;">
                <pre style="background: #fff; padding: 12px; border-radius: 6px; font-size: 11px; 
                           overflow-x: auto; max-height: 300px; margin: 0; border: 1px solid #dee2e6;
                           font-family: \'Courier New\', monospace;">{formatted_json}</pre>
                <div style="position: absolute; top: 10px; right: 10px;">
                    <button type="button" onclick="copyConditionJson(this)" 
                            style="background: #007bff; color: white; border: none; padding: 4px 8px; 
                                   border-radius: 4px; font-size: 10px; cursor: pointer;">
                        📋 Copy
                    </button>
                </div>
            </div>
            '''
            
            # Condition analysis
            if isinstance(condition_data, dict) and condition_data:
                analysis_points = []
                if 'threshold' in condition_data: analysis_points.append(f"Threshold: {condition_data['threshold']}")
                if 'operator' in condition_data: analysis_points.append(f"Operator: {condition_data['operator']}")
                if 'period' in condition_data: analysis_points.append("Time-based rule")
                
                analysis_text = " • ".join(analysis_points) if analysis_points else "Custom condition structure"
                html += f'''
                <div style="margin-top: 12px; font-size: 11px; color: #6c757d;">
                    <strong>Quick Analysis:</strong>
                    <div style="margin-top: 5px;">{analysis_text}</div>
                </div>
                '''
            
            # JavaScript for copy functionality
            html += '''
            <script>
            function copyConditionJson(button) {
                const pre = button.closest('div').querySelector('pre');
                const text = pre.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    const originalText = button.textContent;
                    button.textContent = '[OK] Copied!';
                    setTimeout(() => { button.textContent = originalText; }, 2000);
                });
            }
            </script>
            '''
            html += '</div>'
            return format_html(html)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in condition_details: {str(e)}")
            return format_html('<div style="color:red;">Error: {}</div>', str(e))

    # ডেসক্রিপশন সেট করা (এটি ক্লাসের ভেতরেই থাকতে হবে)
    condition_details.short_description = '[FIX] Condition Details'    



@admin.register(OfferWall)
class OfferWallAdmin(admin.ModelAdmin):
    list_display = ['name', 'wall_type', 'is_active', 'is_default']
    list_filter = ['wall_type', 'is_active']
    search_fields = ['name']


@admin.register(AdNetworkWebhookLog)
class AdNetworkWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['ad_network', 'event_type', 'processed', 'created_at']
    list_filter = ['ad_network', 'processed', 'created_at']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False  # Webhook logs shouldn't be added manually


@admin.register(NetworkStatistic)
class NetworkStatisticAdmin(admin.ModelAdmin):
    list_display = ['ad_network', 'date', 'clicks', 'conversions', 'payout']
    list_filter = ['ad_network', 'date']
    date_hierarchy = 'date'
    readonly_fields = ['date']


@admin.register(UserOfferLimit)
class UserOfferLimitAdmin(admin.ModelAdmin):
    list_display = ['user', 'offer', 'daily_count', 'total_count', 'last_completed']
    list_filter = ['last_completed']
    search_fields = ['user__username', 'offer__title']


@admin.register(OfferSyncLog)
class OfferSyncLogAdmin(admin.ModelAdmin):
    list_display = ['ad_network', 'status', 'offers_fetched', 'sync_duration', 'created_at']
    list_filter = ['status', 'ad_network', 'created_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(SmartOfferRecommendation)
class SmartOfferRecommendationAdmin(admin.ModelAdmin):
    list_display = ['user', 'offer', 'score', 'is_displayed', 'is_clicked', 'is_converted']
    list_filter = ['is_displayed', 'is_clicked', 'is_converted']
    search_fields = ['user__username', 'offer__title']


@admin.register(OfferPerformanceAnalytics)
class OfferPerformanceAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['offer', 'completion_rate', 'avg_session_duration', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']


#যদি @admin.register() decorator কাজ না করে, তাহলে manually register করুন
admin.site.register(AdNetwork, AdNetworkAdmin)
admin.site.register(OfferCategory, OfferCategoryAdmin)
admin.site.register(Offer, OfferAdmin)
admin.site.register(UserOfferEngagement, UserOfferEngagementAdmin)
admin.site.register(OfferConversion, OfferConversionAdmin)
admin.site.register(BlacklistedIP, BlacklistedIPAdmin)
admin.site.register(KnownBadIP, KnownBadIPAdmin)
admin.site.register(FraudDetectionRule, FraudDetectionRuleAdmin)

# ==================== Custom CSS & JS ====================

# Add this at the end of the file
class MediaMixin:
    """Add custom CSS and JS to all admin pages"""
    class Media:
        css = {
            'all': ('admin/css/ad_networks_custom.css',)
        }
        js = ('admin/js/ad_networks_custom.js',)


# Register custom admin site title
admin.site.site_header = "🎯 Ad Networks Administration"
admin.site.site_title = "Ad Networks Admin"
admin.site.index_title = "Welcome to Ad Networks Management"








def _force_register_ad_networks():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(AdNetwork, AdNetworkAdmin), (OfferCategory, OfferCategoryAdmin), (Offer, OfferAdmin), (UserOfferEngagement, UserOfferEngagementAdmin), (OfferConversion, OfferConversionAdmin), (BlacklistedIP, BlacklistedIPAdmin), (KnownBadIP, KnownBadIPAdmin), (FraudDetectionRule, FraudDetectionRuleAdmin), (OfferWall, OfferWallAdmin), (AdNetworkWebhookLog, AdNetworkWebhookLogAdmin), (NetworkStatistic, NetworkStatisticAdmin), (UserOfferLimit, UserOfferLimitAdmin), (OfferSyncLog, OfferSyncLogAdmin), (SmartOfferRecommendation, SmartOfferRecommendationAdmin), (OfferPerformanceAnalytics, OfferPerformanceAnalyticsAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] ad_networks registered {registered} models")
    except Exception as e:
        print(f"[WARN] ad_networks: {e}")
