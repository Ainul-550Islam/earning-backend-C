# api/publisher_tools/admin.py
"""
Publisher Tools — Django Admin।
সব models-এর rich admin interface।
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.contrib import messages

from .models import (
    Publisher, Site, App, InventoryVerification,
    AdUnit, AdPlacement, AdUnitTargeting,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric,
)
from .services import (
    PublisherService, SiteService,
    InvoiceService, FraudDetectionService,
)


# ──────────────────────────────────────────────────────────────────────────────
# INLINE CLASSES
# ──────────────────────────────────────────────────────────────────────────────

class SiteInline(admin.TabularInline):
    model = Site
    extra = 0
    fields = ['site_id', 'name', 'domain', 'category', 'status', 'quality_score']
    readonly_fields = ['site_id', 'quality_score']
    can_delete = False
    show_change_link = True
    max_num = 10


class AppInline(admin.TabularInline):
    model = App
    extra = 0
    fields = ['app_id', 'name', 'platform', 'package_name', 'status', 'quality_score']
    readonly_fields = ['app_id', 'quality_score']
    can_delete = False
    show_change_link = True
    max_num = 10


class AdUnitInline(admin.TabularInline):
    model = AdUnit
    extra = 0
    fields = ['unit_id', 'name', 'format', 'status', 'floor_price', 'avg_ecpm', 'total_revenue']
    readonly_fields = ['unit_id', 'avg_ecpm', 'total_revenue']
    can_delete = False
    show_change_link = True
    max_num = 5


class WaterfallItemInline(admin.TabularInline):
    model = WaterfallItem
    extra = 0
    fields = ['priority', 'network', 'floor_ecpm', 'status', 'avg_ecpm', 'fill_rate']
    readonly_fields = ['avg_ecpm', 'fill_rate']
    ordering = ['priority']
    show_change_link = True


class AdPlacementInline(admin.TabularInline):
    model = AdPlacement
    extra = 0
    fields = ['name', 'position', 'is_active', 'refresh_type', 'floor_price_override']
    show_change_link = True


class PayoutThresholdInline(admin.TabularInline):
    model = PayoutThreshold
    extra = 0
    fields = ['payment_method', 'minimum_threshold', 'payment_frequency', 'is_primary', 'is_verified']
    readonly_fields = ['is_verified']
    show_change_link = True


class InvoiceInline(admin.TabularInline):
    model = PublisherInvoice
    extra = 0
    fields = ['invoice_number', 'period_start', 'period_end', 'net_payable', 'status']
    readonly_fields = ['invoice_number', 'net_payable']
    can_delete = False
    show_change_link = True
    max_num = 6


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = [
        'publisher_badge', 'display_name', 'business_type',
        'country', 'status_badge', 'tier_badge',
        'kyc_badge', 'revenue_display', 'sites_count',
        'apps_count', 'created_at',
    ]
    list_filter = [
        'status', 'tier', 'business_type',
        'is_kyc_verified', 'is_email_verified', 'country',
    ]
    search_fields = [
        'publisher_id', 'display_name', 'contact_email',
        'user__username', 'user__email',
    ]
    readonly_fields = [
        'publisher_id', 'api_key', 'api_secret',
        'total_revenue', 'total_paid_out', 'pending_balance',
        'created_at', 'updated_at', 'kyc_verified_at',
    ]
    inlines = [SiteInline, AppInline, PayoutThresholdInline, InvoiceInline]
    actions = ['approve_publishers', 'suspend_publishers']

    fieldsets = (
        ('🆔 Identity', {
            'fields': ('publisher_id', 'user', 'display_name', 'business_type'),
        }),
        ('📞 Contact', {
            'fields': ('contact_email', 'contact_phone', 'website', 'country', 'city', 'address'),
        }),
        ('📊 Status', {
            'fields': ('status', 'tier', 'is_kyc_verified', 'is_email_verified', 'kyc_verified_at'),
        }),
        ('💰 Financial', {
            'fields': (
                'revenue_share_percentage',
                'total_revenue', 'total_paid_out', 'pending_balance',
            ),
        }),
        ('🔑 API Access', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',),
        }),
        ('📝 Notes', {
            'fields': ('internal_notes', 'metadata'),
            'classes': ('collapse',),
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def publisher_badge(self, obj):
        return format_html(
            '<strong style="color:#2563eb">{}</strong>', obj.publisher_id
        )
    publisher_badge.short_description = 'Publisher ID'

    def status_badge(self, obj):
        colors = {
            'active':      '#22c55e',
            'pending':     '#f59e0b',
            'suspended':   '#ef4444',
            'banned':      '#7f1d1d',
            'under_review':'#8b5cf6',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def tier_badge(self, obj):
        colors = {'standard': '#6b7280', 'premium': '#f59e0b', 'enterprise': '#8b5cf6'}
        color = colors.get(obj.tier, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.get_tier_display()
        )
    tier_badge.short_description = 'Tier'

    def kyc_badge(self, obj):
        if obj.is_kyc_verified:
            return format_html('<span style="color:#22c55e">✅ KYC</span>')
        return format_html('<span style="color:#ef4444">❌ KYC</span>')
    kyc_badge.short_description = 'KYC'

    def revenue_display(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_revenue)
    revenue_display.short_description = 'Revenue'

    def sites_count(self, obj):
        count = obj.sites.filter(status='active').count()
        return format_html('<span style="color:#2563eb">{} sites</span>', count)
    sites_count.short_description = 'Active Sites'

    def apps_count(self, obj):
        count = obj.apps.filter(status='active').count()
        return format_html('<span style="color:#7c3aed">{} apps</span>', count)
    apps_count.short_description = 'Active Apps'

    @admin.action(description='✅ Approve selected publishers')
    def approve_publishers(self, request, queryset):
        count = 0
        for publisher in queryset.filter(status__in=['pending', 'under_review']):
            PublisherService.approve_publisher(publisher, approved_by=request.user)
            count += 1
        self.message_user(request, f'{count} publisher(s) approved.', messages.SUCCESS)

    @admin.action(description='🚫 Suspend selected publishers')
    def suspend_publishers(self, request, queryset):
        count = 0
        for publisher in queryset.filter(status='active'):
            PublisherService.suspend_publisher(publisher, 'Bulk admin action')
            count += 1
        self.message_user(request, f'{count} publisher(s) suspended.', messages.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# SITE ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = [
        'site_id', 'name', 'domain_link', 'category',
        'status_badge', 'quality_score_bar',
        'ads_txt_badge', 'revenue_display',
        'publisher_link', 'created_at',
    ]
    list_filter = [
        'status', 'category', 'ads_txt_verified',
        'content_rating', 'sellers_json_verified',
    ]
    search_fields = ['site_id', 'name', 'domain', 'publisher__display_name']
    readonly_fields = [
        'site_id', 'total_revenue', 'lifetime_impressions',
        'lifetime_clicks', 'approved_at', 'created_at', 'updated_at',
    ]
    inlines = [AdUnitInline]
    actions = ['approve_sites', 'reject_sites', 'refresh_ads_txt_bulk']

    fieldsets = (
        ('🌐 Site Identity', {
            'fields': ('site_id', 'publisher', 'name', 'domain', 'url'),
        }),
        ('📂 Classification', {
            'fields': ('category', 'subcategory', 'language', 'target_countries', 'content_rating'),
        }),
        ('📊 Status & Quality', {
            'fields': ('status', 'quality_score', 'rejection_reason'),
        }),
        ('✅ Verification', {
            'fields': ('ads_txt_verified', 'ads_txt_content', 'sellers_json_verified'),
        }),
        ('📈 Traffic', {
            'fields': ('monthly_pageviews', 'monthly_unique_visitors', 'avg_session_duration', 'bounce_rate'),
        }),
        ('💰 Revenue', {
            'fields': ('total_revenue', 'lifetime_impressions', 'lifetime_clicks'),
        }),
        ('👤 Review', {
            'fields': ('approved_at', 'approved_by'),
        }),
    )

    def domain_link(self, obj):
        return format_html('<a href="https://{}" target="_blank">{}</a>', obj.domain, obj.domain)
    domain_link.short_description = 'Domain'

    def status_badge(self, obj):
        colors = {
            'active': '#22c55e', 'pending': '#f59e0b',
            'rejected': '#ef4444', 'suspended': '#ef4444', 'inactive': '#6b7280',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def quality_score_bar(self, obj):
        score = obj.quality_score
        color = '#22c55e' if score >= 70 else '#f59e0b' if score >= 40 else '#ef4444'
        return format_html(
            '<div style="width:80px;background:#e5e7eb;border-radius:3px">'
            '<div style="width:{}%;background:{};height:12px;border-radius:3px"></div>'
            '</div> <small>{}/100</small>',
            score, color, score
        )
    quality_score_bar.short_description = 'Quality'

    def ads_txt_badge(self, obj):
        if obj.ads_txt_verified:
            return format_html('<span style="color:#22c55e">✅ ads.txt</span>')
        return format_html('<span style="color:#ef4444">❌ ads.txt</span>')
    ads_txt_badge.short_description = 'ads.txt'

    def revenue_display(self, obj):
        return format_html('${:.2f}', obj.total_revenue)
    revenue_display.short_description = 'Revenue'

    def publisher_link(self, obj):
        url = reverse('admin:publisher_tools_publisher_change', args=[obj.publisher.id])
        return format_html('<a href="{}">{}</a>', url, obj.publisher.publisher_id)
    publisher_link.short_description = 'Publisher'

    @admin.action(description='✅ Approve selected sites')
    def approve_sites(self, request, queryset):
        count = 0
        for site in queryset.filter(status='pending'):
            SiteService.approve_site(site, approved_by=request.user)
            count += 1
        self.message_user(request, f'{count} site(s) approved.', messages.SUCCESS)

    @admin.action(description='❌ Reject selected sites')
    def reject_sites(self, request, queryset):
        for site in queryset.filter(status='pending'):
            SiteService.reject_site(site, 'Does not meet content guidelines.')
        self.message_user(request, 'Sites rejected.', messages.WARNING)

    @admin.action(description='🔄 Refresh ads.txt for selected sites')
    def refresh_ads_txt_bulk(self, request, queryset):
        count = sum(1 for site in queryset if SiteService.refresh_ads_txt(site))
        self.message_user(request, f'ads.txt refreshed for {count} site(s).', messages.SUCCESS)


# ──────────────────────────────────────────────────────────────────────────────
# APP ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display = [
        'app_id', 'name', 'platform_badge', 'package_name',
        'category', 'status_badge', 'quality_score',
        'store_rating', 'total_downloads', 'publisher_link', 'created_at',
    ]
    list_filter = ['status', 'platform', 'category', 'content_rating']
    search_fields = ['app_id', 'name', 'package_name', 'publisher__display_name']
    readonly_fields = [
        'app_id', 'total_revenue', 'lifetime_impressions',
        'approved_at', 'created_at', 'updated_at',
    ]
    inlines = [AdUnitInline]
    actions = ['approve_apps', 'reject_apps']

    def platform_badge(self, obj):
        colors = {'android': '#22c55e', 'ios': '#2563eb', 'both': '#8b5cf6', 'web_app': '#f59e0b'}
        icons  = {'android': '🤖', 'ios': '🍎', 'both': '📱', 'web_app': '🌐'}
        color  = colors.get(obj.platform, '#6b7280')
        icon   = icons.get(obj.platform, '📱')
        return format_html(
            '<span style="color:{}">{} {}</span>', color, icon, obj.get_platform_display()
        )
    platform_badge.short_description = 'Platform'

    def status_badge(self, obj):
        colors = {'active': '#22c55e', 'pending': '#f59e0b', 'rejected': '#ef4444', 'suspended': '#ef4444'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def publisher_link(self, obj):
        url = reverse('admin:publisher_tools_publisher_change', args=[obj.publisher.id])
        return format_html('<a href="{}">{}</a>', url, obj.publisher.publisher_id)
    publisher_link.short_description = 'Publisher'

    @admin.action(description='✅ Approve selected apps')
    def approve_apps(self, request, queryset):
        from .services import AppService
        count = 0
        for app in queryset.filter(status='pending'):
            AppService.approve_app(app, approved_by=request.user)
            count += 1
        self.message_user(request, f'{count} app(s) approved.', messages.SUCCESS)

    @admin.action(description='❌ Reject selected apps')
    def reject_apps(self, request, queryset):
        from .services import AppService
        for app in queryset.filter(status='pending'):
            AppService.reject_app(app, 'Does not meet app guidelines.')
        self.message_user(request, 'Apps rejected.', messages.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# INVENTORY VERIFICATION ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(InventoryVerification)
class InventoryVerificationAdmin(admin.ModelAdmin):
    list_display = [
        'publisher', 'inventory_type', 'method',
        'status_badge', 'attempt_count',
        'verified_at', 'expires_at', 'created_at',
    ]
    list_filter = ['status', 'method', 'inventory_type']
    search_fields = ['publisher__display_name', 'publisher__publisher_id', 'verification_token']
    readonly_fields = ['verification_token', 'verified_at', 'last_checked_at', 'created_at']

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b', 'verified': '#22c55e',
            'failed': '#ef4444', 'expired': '#6b7280',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    status_badge.short_description = 'Status'


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = [
        'unit_id', 'name', 'format_badge', 'inventory_type',
        'status_badge', 'floor_price',
        'ecpm_display', 'fill_rate_display',
        'total_revenue', 'publisher_link', 'created_at',
    ]
    list_filter = ['status', 'format', 'inventory_type', 'is_test_mode']
    search_fields = ['unit_id', 'name', 'publisher__display_name']
    readonly_fields = [
        'unit_id', 'tag_code', 'total_impressions', 'total_clicks',
        'total_revenue', 'avg_ecpm', 'fill_rate', 'created_at', 'updated_at',
    ]
    inlines = [AdPlacementInline]

    def format_badge(self, obj):
        format_colors = {
            'banner': '#3b82f6', 'interstitial': '#8b5cf6',
            'rewarded_video': '#f59e0b', 'native': '#22c55e',
            'offerwall': '#ef4444', 'video': '#ec4899',
        }
        color = format_colors.get(obj.format, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.get_format_display()
        )
    format_badge.short_description = 'Format'

    def status_badge(self, obj):
        colors = {'active': '#22c55e', 'paused': '#f59e0b', 'archived': '#6b7280', 'pending': '#8b5cf6'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def ecpm_display(self, obj):
        return format_html('<strong>${:.4f}</strong>', obj.avg_ecpm)
    ecpm_display.short_description = 'eCPM'

    def fill_rate_display(self, obj):
        color = '#22c55e' if obj.fill_rate >= 80 else '#f59e0b' if obj.fill_rate >= 50 else '#ef4444'
        return format_html('<span style="color:{}">{:.1f}%</span>', color, obj.fill_rate)
    fill_rate_display.short_description = 'Fill Rate'

    def publisher_link(self, obj):
        url = reverse('admin:publisher_tools_publisher_change', args=[obj.publisher.id])
        return format_html('<a href="{}">{}</a>', url, obj.publisher.publisher_id)
    publisher_link.short_description = 'Publisher'


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION GROUP ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(MediationGroup)
class MediationGroupAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'ad_unit', 'mediation_type',
        'is_active', 'auto_optimize',
        'total_impressions', 'avg_ecpm', 'fill_rate',
        'last_optimized_at', 'created_at',
    ]
    list_filter = ['mediation_type', 'is_active', 'auto_optimize']
    search_fields = ['name', 'ad_unit__unit_id', 'ad_unit__publisher__display_name']
    readonly_fields = [
        'total_ad_requests', 'total_impressions', 'total_revenue',
        'avg_ecpm', 'fill_rate', 'last_optimized_at', 'created_at', 'updated_at',
    ]
    inlines = [WaterfallItemInline]

    actions = ['optimize_waterfalls']

    @admin.action(description='⚡ Optimize selected waterfall groups')
    def optimize_waterfalls(self, request, queryset):
        count = 0
        for group in queryset.filter(is_active=True):
            MediationService.optimize_waterfall(group)
            count += 1
        self.message_user(request, f'{count} waterfall(s) optimized.', messages.SUCCESS)


# ──────────────────────────────────────────────────────────────────────────────
# WATERFALL ITEM ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(WaterfallItem)
class WaterfallItemAdmin(admin.ModelAdmin):
    list_display = [
        'priority', 'network', 'mediation_group',
        'floor_ecpm', 'bidding_type', 'status',
        'avg_ecpm', 'fill_rate', 'avg_latency_ms',
        'total_revenue',
    ]
    list_filter = ['status', 'bidding_type', 'network']
    search_fields = ['network__name', 'mediation_group__name']
    ordering = ['mediation_group', 'priority']
    readonly_fields = [
        'total_ad_requests', 'total_impressions', 'total_revenue',
        'avg_ecpm', 'fill_rate', 'avg_latency_ms', 'created_at',
    ]


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER EARNING ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(PublisherEarning)
class PublisherEarningAdmin(admin.ModelAdmin):
    list_display = [
        'publisher', 'date', 'earning_type', 'country',
        'impressions', 'clicks',
        'gross_revenue_display', 'publisher_revenue_display',
        'ecpm', 'fill_rate', 'status', 'created_at',
    ]
    list_filter = [
        'status', 'earning_type', 'granularity',
        'country', ('date', admin.DateFieldListFilter),
    ]
    search_fields = ['publisher__display_name', 'publisher__publisher_id', 'ad_unit__unit_id']
    readonly_fields = [
        'ecpm', 'ctr', 'fill_rate', 'rpm',
        'publisher_revenue', 'platform_revenue', 'created_at',
    ]
    date_hierarchy = 'date'
    actions = ['finalize_earnings', 'mark_adjusted']

    def gross_revenue_display(self, obj):
        return format_html('${:.4f}', obj.gross_revenue)
    gross_revenue_display.short_description = 'Gross'

    def publisher_revenue_display(self, obj):
        return format_html('<strong>${:.4f}</strong>', obj.publisher_revenue)
    publisher_revenue_display.short_description = 'Publisher Revenue'

    @admin.action(description='✅ Finalize selected earnings')
    def finalize_earnings(self, request, queryset):
        count = queryset.filter(status='confirmed').update(status='finalized')
        self.message_user(request, f'{count} earning(s) finalized.', messages.SUCCESS)

    @admin.action(description='📝 Mark as adjusted')
    def mark_adjusted(self, request, queryset):
        count = queryset.update(status='adjusted')
        self.message_user(request, f'{count} earning(s) marked as adjusted.', messages.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# PAYOUT THRESHOLD ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(PayoutThreshold)
class PayoutThresholdAdmin(admin.ModelAdmin):
    list_display = [
        'publisher', 'payment_method', 'minimum_threshold',
        'payment_frequency', 'is_primary', 'is_verified', 'created_at',
    ]
    list_filter = ['payment_method', 'payment_frequency', 'is_primary', 'is_verified']
    search_fields = ['publisher__display_name', 'publisher__publisher_id']
    actions = ['verify_payment_methods']

    @admin.action(description='✅ Verify selected payment methods')
    def verify_payment_methods(self, request, queryset):
        count = queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f'{count} payment method(s) verified.', messages.SUCCESS)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER INVOICE ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(PublisherInvoice)
class PublisherInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'publisher', 'invoice_type',
        'period_display', 'gross_revenue', 'net_payable_display',
        'status_badge', 'is_overdue_badge',
        'due_date', 'paid_at', 'created_at',
    ]
    list_filter = ['status', 'invoice_type', ('period_start', admin.DateFieldListFilter)]
    search_fields = ['invoice_number', 'publisher__display_name', 'publisher__publisher_id']
    readonly_fields = [
        'invoice_number', 'net_payable', 'issued_at', 'paid_at', 'failed_at',
        'total_impressions', 'total_clicks', 'total_ad_requests',
        'created_at', 'updated_at',
    ]
    actions = ['issue_invoices', 'mark_invoices_paid']

    def period_display(self, obj):
        return f'{obj.period_start} → {obj.period_end}'
    period_display.short_description = 'Period'

    def net_payable_display(self, obj):
        return format_html('<strong style="color:#22c55e">${:.4f}</strong>', obj.net_payable)
    net_payable_display.short_description = 'Net Payable'

    def status_badge(self, obj):
        colors = {
            'draft': '#6b7280', 'issued': '#3b82f6', 'processing': '#f59e0b',
            'paid': '#22c55e', 'failed': '#ef4444', 'disputed': '#8b5cf6', 'cancelled': '#9ca3af',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def is_overdue_badge(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:#ef4444;font-weight:bold">⚠️ OVERDUE</span>')
        return format_html('<span style="color:#22c55e">OK</span>')
    is_overdue_badge.short_description = 'Overdue?'

    @admin.action(description='📤 Issue selected invoices (Draft → Issued)')
    def issue_invoices(self, request, queryset):
        count = 0
        for invoice in queryset.filter(status='draft'):
            InvoiceService.issue_invoice(invoice, issued_by=request.user)
            count += 1
        self.message_user(request, f'{count} invoice(s) issued.', messages.SUCCESS)

    @admin.action(description='✅ Mark selected invoices as paid')
    def mark_invoices_paid(self, request, queryset):
        count = 0
        for invoice in queryset.filter(status='issued'):
            InvoiceService.mark_as_paid(invoice, 'BULK_ADMIN_PAYMENT', processed_by=request.user)
            count += 1
        self.message_user(request, f'{count} invoice(s) marked as paid.', messages.SUCCESS)


# ──────────────────────────────────────────────────────────────────────────────
# TRAFFIC SAFETY LOG ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(TrafficSafetyLog)
class TrafficSafetyLogAdmin(admin.ModelAdmin):
    list_display = [
        'publisher', 'traffic_type_badge', 'severity_badge',
        'fraud_score_display', 'ip_address', 'country',
        'affected_impressions', 'revenue_at_risk',
        'action_badge', 'is_false_positive',
        'detected_at',
    ]
    list_filter = [
        'traffic_type', 'severity', 'action_taken',
        'is_false_positive',
        ('detected_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'publisher__display_name', 'ip_address',
        'device_id', 'country',
    ]
    readonly_fields = [
        'detection_signals', 'raw_data',
        'revenue_at_risk', 'detected_at', 'created_at',
    ]
    actions = ['auto_block_high_risk', 'mark_all_false_positive', 'deduct_revenue']
    date_hierarchy = 'detected_at'

    def traffic_type_badge(self, obj):
        colors = {
            'bot': '#ef4444', 'click_fraud': '#f59e0b', 'impression_fraud': '#f59e0b',
            'vpn': '#8b5cf6', 'proxy': '#8b5cf6', 'device_farm': '#dc2626',
            'sdk_spoofing': '#dc2626',
        }
        color = colors.get(obj.traffic_type, '#6b7280')
        return format_html('<span style="color:{};font-weight:bold">{}</span>', color, obj.traffic_type.upper())
    traffic_type_badge.short_description = 'Type'

    def severity_badge(self, obj):
        colors = {'low': '#22c55e', 'medium': '#f59e0b', 'high': '#ef4444', 'critical': '#7f1d1d'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.severity, '#6b7280'), obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'

    def fraud_score_display(self, obj):
        color = '#22c55e' if obj.fraud_score < 30 else '#f59e0b' if obj.fraud_score < 70 else '#ef4444'
        return format_html('<strong style="color:{}">{}/100</strong>', color, obj.fraud_score)
    fraud_score_display.short_description = 'Score'

    def action_badge(self, obj):
        colors = {
            'flagged': '#f59e0b', 'deducted': '#ef4444', 'warned': '#f97316',
            'suspended': '#dc2626', 'blocked': '#7f1d1d',
            'no_action': '#22c55e', 'pending': '#8b5cf6',
        }
        return format_html(
            '<span style="color:{}">{}</span>',
            colors.get(obj.action_taken, '#6b7280'), obj.action_taken.upper()
        )
    action_badge.short_description = 'Action'

    @admin.action(description='🚫 Auto-block high-risk logs (score > 80)')
    def auto_block_high_risk(self, request, queryset):
        count = 0
        for log in queryset.filter(fraud_score__gte=80, action_taken='pending'):
            FraudDetectionService.auto_block(log)
            count += 1
        self.message_user(request, f'{count} log(s) auto-blocked.', messages.WARNING)

    @admin.action(description='✅ Mark selected as false positive')
    def mark_all_false_positive(self, request, queryset):
        count = queryset.update(is_false_positive=True, action_taken='no_action')
        self.message_user(request, f'{count} log(s) marked as false positive.', messages.SUCCESS)

    @admin.action(description='💰 Apply revenue deduction')
    def deduct_revenue(self, request, queryset):
        count = queryset.filter(action_taken='pending').update(action_taken='deducted')
        self.message_user(request, f'{count} log(s) marked for revenue deduction.', messages.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(SiteQualityMetric)
class SiteQualityMetricAdmin(admin.ModelAdmin):
    list_display = [
        'site', 'date', 'quality_score_display',
        'viewability_display', 'ivt_display',
        'content_quality', 'has_alerts',
        'malware_detected', 'adult_content_detected',
        'page_speed_score',
    ]
    list_filter = [
        'content_quality', 'has_alerts',
        'malware_detected', 'adult_content_detected',
        'ads_txt_valid',
        ('date', admin.DateFieldListFilter),
    ]
    search_fields = ['site__domain', 'site__name', 'site__publisher__display_name']
    readonly_fields = ['overall_quality_score', 'score_change', 'created_at', 'updated_at']
    date_hierarchy = 'date'

    def quality_score_display(self, obj):
        score = obj.overall_quality_score
        color = '#22c55e' if score >= 70 else '#f59e0b' if score >= 40 else '#ef4444'
        change = obj.score_change
        arrow = '↑' if change > 0 else '↓' if change < 0 else '→'
        arrow_color = '#22c55e' if change > 0 else '#ef4444' if change < 0 else '#6b7280'
        return format_html(
            '<strong style="color:{}">{}/100</strong> <span style="color:{};font-size:11px">{}{}</span>',
            color, score, arrow_color, arrow, abs(change)
        )
    quality_score_display.short_description = 'Quality Score'

    def viewability_display(self, obj):
        rate = obj.viewability_rate
        color = '#22c55e' if rate >= 50 else '#f59e0b' if rate >= 30 else '#ef4444'
        return format_html('<span style="color:{}">{:.1f}%</span>', color, rate)
    viewability_display.short_description = 'Viewability'

    def ivt_display(self, obj):
        rate = obj.invalid_traffic_percentage
        color = '#22c55e' if rate <= 10 else '#f59e0b' if rate <= 20 else '#ef4444'
        return format_html('<span style="color:{}">{:.1f}%</span>', color, rate)
    ivt_display.short_description = 'IVT %'


# ──────────────────────────────────────────────────────────────────────────────
# AD PLACEMENT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'ad_unit', 'position', 'is_active',
        'refresh_type', 'floor_price_override',
        'avg_viewability', 'total_revenue', 'created_at',
    ]
    list_filter = ['position', 'is_active', 'refresh_type']
    search_fields = ['name', 'ad_unit__unit_id', 'ad_unit__publisher__display_name']


@admin.register(AdUnitTargeting)
class AdUnitTargetingAdmin(admin.ModelAdmin):
    list_display = [
        'ad_unit', 'name', 'device_type', 'target_os',
        'frequency_cap', 'is_active', 'created_at',
    ]
    list_filter = ['device_type', 'target_os', 'is_active']
    search_fields = ['ad_unit__unit_id', 'ad_unit__publisher__display_name', 'name']


@admin.register(HeaderBiddingConfig)
class HeaderBiddingConfigAdmin(admin.ModelAdmin):
    list_display = [
        'bidder_name', 'bidder_type', 'mediation_group',
        'timeout_ms', 'price_floor', 'status',
        'total_bid_wins', 'avg_bid_cpm', 'total_revenue', 'created_at',
    ]
    list_filter = ['bidder_type', 'status']
    search_fields = ['bidder_name', 'mediation_group__name']
    readonly_fields = [
        'total_bid_requests', 'total_bid_responses', 'total_bid_wins',
        'total_revenue', 'avg_bid_cpm', 'created_at',
    ]


def _force_register_publisher_tools():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (Publisher, PublisherAdmin),
            (Site, SiteAdmin),
            (App, AppAdmin),
            (InventoryVerification, InventoryVerificationAdmin),
            (AdUnit, AdUnitAdmin),
            (AdPlacement, AdPlacementAdmin),
            (AdUnitTargeting, AdUnitTargetingAdmin),
            (MediationGroup, MediationGroupAdmin),
            (WaterfallItem, WaterfallItemAdmin),
            (HeaderBiddingConfig, HeaderBiddingConfigAdmin),
            (PublisherEarning, PublisherEarningAdmin),
            (PayoutThreshold, PayoutThresholdAdmin),
            (PublisherInvoice, PublisherInvoiceAdmin),
            (TrafficSafetyLog, TrafficSafetyLogAdmin),
            (SiteQualityMetric, SiteQualityMetricAdmin),
        ]
        for model, model_admin in pairs:
            if model not in modern_site._registry:
                modern_site.register(model, model_admin)
                print(f'[OK] Publisher Tools registered: {model.__name__}')
    except Exception as e:
        print(f'[WARN] Publisher Tools force-register: {e}')
