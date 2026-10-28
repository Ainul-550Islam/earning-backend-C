# publisher_tools/admin.py  — COMPLETE VERSION
# All models registered with useful list_display, filters, search.

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Publisher, Site, App, InventoryVerification,
    AdUnit, AdPlacement, AdUnitTargeting,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric,
    PublisherWebhook, WebhookDeliveryLog, BlockedIP,
    ABTest, ABTestVariant,
)
from .app_management.app_approval import AppApprovalRecord
from .app_management.app_sdk import AppSDKConfig


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'display_name', 'status', 'tier', 'country', 'total_revenue', 'created_at')
    list_filter   = ('status', 'tier', 'business_type', 'is_kyc_verified', 'country')
    search_fields = ('publisher_id', 'display_name', 'contact_email', 'user__email')
    readonly_fields = ('publisher_id', 'api_key', 'total_revenue', 'total_paid_out', 'created_at', 'updated_at')
    fieldsets = (
        ('Identity', {'fields': ('publisher_id', 'user', 'display_name', 'business_type')}),
        ('Contact',  {'fields': ('contact_email', 'contact_phone', 'website', 'country', 'city', 'address')}),
        ('Status',   {'fields': ('status', 'tier', 'is_kyc_verified', 'is_email_verified')}),
        ('Finance',  {'fields': ('revenue_share_percentage', 'total_revenue', 'total_paid_out', 'pending_balance')}),
        ('API',      {'fields': ('api_key',)}),
    )


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display  = ('site_id', 'domain', 'publisher', 'status', 'quality_score', 'ads_txt_verified')
    list_filter   = ('status', 'category', 'ads_txt_verified', 'sellers_json_verified')
    search_fields = ('site_id', 'domain', 'publisher__publisher_id', 'publisher__display_name')
    readonly_fields = ('site_id', 'created_at', 'updated_at')


@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display  = ('app_id', 'name', 'platform', 'publisher', 'status', 'quality_score')
    list_filter   = ('status', 'platform', 'category')
    search_fields = ('app_id', 'name', 'package_name', 'publisher__publisher_id')
    readonly_fields = ('app_id', 'created_at', 'updated_at')


@admin.register(InventoryVerification)
class InventoryVerificationAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'site', 'method', 'status', 'attempt_count', 'created_at')
    list_filter   = ('status', 'method')
    search_fields = ('publisher__publisher_id', 'site__domain')


@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display  = ('unit_id', 'name', 'format', 'publisher', 'status', 'floor_price', 'avg_ecpm')
    list_filter   = ('status', 'format', 'inventory_type')
    search_fields = ('unit_id', 'name', 'publisher__publisher_id')
    readonly_fields = ('unit_id', 'tag_code', 'created_at', 'updated_at')


@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display  = ('name', 'ad_unit', 'position', 'is_active', 'refresh_interval_seconds')
    list_filter   = ('is_active', 'position')
    search_fields = ('name', 'ad_unit__name', 'ad_unit__unit_id')


@admin.register(AdUnitTargeting)
class AdUnitTargetingAdmin(admin.ModelAdmin):
    list_display  = ('ad_unit', 'device_type', 'is_active')
    list_filter   = ('device_type', 'is_active')


@admin.register(MediationGroup)
class MediationGroupAdmin(admin.ModelAdmin):
    list_display  = ('name', 'ad_unit', 'mediation_type', 'is_active', 'avg_ecpm', 'auto_optimize')
    list_filter   = ('is_active', 'mediation_type', 'auto_optimize')
    search_fields = ('name', 'ad_unit__unit_id')


@admin.register(WaterfallItem)
class WaterfallItemAdmin(admin.ModelAdmin):
    list_display  = ('network', 'mediation_group', 'priority', 'floor_ecpm', 'status', 'avg_ecpm')
    list_filter   = ('status',)
    ordering      = ('mediation_group', 'priority')


@admin.register(HeaderBiddingConfig)
class HeaderBiddingConfigAdmin(admin.ModelAdmin):
    list_display  = ('bidder_name', 'mediation_group', 'price_floor', 'status')
    list_filter   = ('status',)


@admin.register(PublisherEarning)
class PublisherEarningAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'date', 'granularity', 'country', 'publisher_revenue', 'ecpm', 'status')
    list_filter   = ('granularity', 'earning_type', 'status', 'country')
    search_fields = ('publisher__publisher_id',)
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PayoutThreshold)
class PayoutThresholdAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'payment_method', 'minimum_threshold', 'is_primary', 'is_verified')
    list_filter   = ('payment_method', 'is_verified', 'is_primary')
    search_fields = ('publisher__publisher_id',)


@admin.register(PublisherInvoice)
class PublisherInvoiceAdmin(admin.ModelAdmin):
    list_display  = ('invoice_number', 'publisher', 'status', 'net_payable', 'currency', 'period_start', 'period_end')
    list_filter   = ('status', 'currency')
    search_fields = ('invoice_number', 'publisher__publisher_id')
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')
    date_hierarchy  = 'period_start'


@admin.register(TrafficSafetyLog)
class TrafficSafetyLogAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'traffic_type', 'severity', 'fraud_score', 'ip_address', 'action_taken', 'is_false_positive', 'detected_at')
    list_filter   = ('traffic_type', 'severity', 'action_taken', 'is_false_positive')
    search_fields = ('publisher__publisher_id', 'ip_address')
    date_hierarchy  = 'detected_at'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SiteQualityMetric)
class SiteQualityMetricAdmin(admin.ModelAdmin):
    list_display  = ('site', 'date', 'overall_quality_score', 'has_alerts', 'invalid_traffic_percentage')
    list_filter   = ('has_alerts',)
    search_fields = ('site__domain', 'site__site_id')
    date_hierarchy = 'date'


@admin.register(PublisherWebhook)
class PublisherWebhookAdmin(admin.ModelAdmin):
    list_display  = ('name', 'publisher', 'endpoint_url', 'status', 'success_rate', 'total_deliveries')
    list_filter   = ('status', 'is_active')
    search_fields = ('name', 'publisher__publisher_id', 'endpoint_url')
    readonly_fields = ('secret_key', 'success_rate', 'total_deliveries', 'created_at', 'updated_at')


@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    list_display  = ('webhook', 'event_type', 'status', 'response_code', 'attempt', 'delivered_at')
    list_filter   = ('status', 'event_type')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy  = 'created_at'


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display  = ('ip_address', 'reason', 'fraud_score', 'is_permanent', 'is_auto_blocked', 'expires_at', 'is_active')
    list_filter   = ('is_permanent', 'is_auto_blocked')
    search_fields = ('ip_address', 'reason')
    readonly_fields = ('created_at', 'updated_at')

    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True


class ABTestVariantInline(admin.TabularInline):
    model  = ABTestVariant
    extra  = 0
    fields = ('name', 'is_control', 'traffic_split', 'total_impressions', 'ecpm', 'ctr')
    readonly_fields = ('total_impressions', 'ecpm', 'ctr')


@admin.register(ABTest)
class ABTestAdmin(admin.ModelAdmin):
    list_display  = ('test_id', 'name', 'test_type', 'status', 'publisher', 'ad_unit', 'start_date', 'concluded_at')
    list_filter   = ('status', 'test_type')
    search_fields = ('test_id', 'name', 'publisher__publisher_id')
    readonly_fields = ('test_id', 'created_at', 'updated_at')
    inlines       = [ABTestVariantInline]


@admin.register(ABTestVariant)
class ABTestVariantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'test', 'is_control', 'traffic_split', 'ecpm', 'total_impressions')
    list_filter   = ('is_control',)
    search_fields = ('name', 'test__test_id')


# ──────────────────────────────────────────────────────────────────────────────
# APP MANAGEMENT MODELS
# (app_management/ subfolder — app_label = 'publisher_tools')
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(AppApprovalRecord)
class AppApprovalRecordAdmin(admin.ModelAdmin):
    """
    Admin for AppApprovalRecord — app review/approval/rejection log।

    Registered from: publisher_tools/app_management/app_approval.py
    DB table:        publisher_tools_app_approval_records
    Migration:       0008_app_approval_sdk_snapshot (NEW model)
    """

    list_display = (
        'get_app_name',
        'get_app_id',
        'action',
        'decided_by',
        'is_resubmission',
        'reviewed_at',
        'created_at',
    )
    list_filter   = ('action', 'is_resubmission')
    search_fields = (
        'app__name',
        'app__app_id',
        'decided_by',
        'reason',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'reviewed_at',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('App Reference', {
            'fields': ('app', 'reviewer'),
        }),
        ('Decision', {
            'fields': (
                'action', 'previous_action', 'reason',
                'decided_by', 'reviewed_at',
            ),
        }),
        ('Details', {
            'fields': (
                'notes', 'rejection_feedback',
                'is_resubmission', 'metadata',
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_app_name(self, obj) -> str:
        """App display name — list_display column।"""
        app = getattr(obj, 'app', None)
        return getattr(app, 'name', '—') if app else '—'
    get_app_name.short_description = 'App'
    get_app_name.admin_order_field = 'app__name'

    def get_app_id(self, obj) -> str:
        """App slug/app_id — list_display column।"""
        app = getattr(obj, 'app', None)
        return getattr(app, 'app_id', '—') if app else '—'
    get_app_id.short_description = 'App ID'
    get_app_id.admin_order_field = 'app__app_id'


@admin.register(AppSDKConfig)
class AppSDKConfigAdmin(admin.ModelAdmin):
    """
    Admin for AppSDKConfig — per-app SDK integration settings।

    Registered from: publisher_tools/app_management/app_sdk.py
    DB table:        publisher_tools_app_sdk_configs
    Migration:       0008_app_approval_sdk_snapshot (NEW model)
    """

    list_display = (
        'get_app_name',
        'sdk_version',
        'sdk_platform',
        'status',
        'is_sdk_integrated',
        'test_mode',
        'last_sdk_ping',
        'updated_at',
    )
    list_filter   = ('status', 'sdk_platform', 'is_sdk_integrated', 'test_mode')
    search_fields = (
        'app__name',
        'app__app_id',
        'sdk_version',
    )
    readonly_fields = (
        'last_sdk_ping',
        'error_message',
        'created_at',
        'updated_at',
    )
    ordering = ('-updated_at',)

    fieldsets = (
        ('App Reference', {
            'fields': ('app',),
        }),
        ('SDK Identity', {
            'fields': (
                'sdk_version', 'sdk_platform', 'status',
                'is_sdk_integrated', 'last_sdk_ping',
            ),
        }),
        ('Credentials', {
            'fields': ('sdk_key', 'sdk_secret'),
            'classes': ('collapse',),
            'description': '⚠ SDK keys are sensitive — handle with care.',
        }),
        ('Configuration', {
            'fields': (
                'sdk_config_json', 'initialization_options',
                'allowed_ad_formats', 'mediation_config',
                'test_mode', 'auto_init',
            ),
            'classes': ('collapse',),
        }),
        ('Compliance', {
            'fields': (
                'consent_required', 'coppa_compliant', 'gdpr_compliant',
            ),
        }),
        ('Notes & Errors', {
            'fields': ('integration_notes', 'error_message'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_app_name(self, obj) -> str:
        """App display name — list_display column।"""
        app = getattr(obj, 'app', None)
        return getattr(app, 'name', '—') if app else '—'
    get_app_name.short_description = 'App'
    get_app_name.admin_order_field = 'app__name'


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER MANAGEMENT ADMIN REGISTRATIONS
# publisher_management/ subfolder — 19 models
# Requires migration 0009 to be applied first.
# ──────────────────────────────────────────────────────────────────────────────
try:
    from .admin_publisher_management import *   # noqa: F401,F403
except ImportError:
    pass   # migration 0009 not yet applied

# ── Ad Unit + Site + Mediation admin (migration 0010 required) ────────────────
try:
    from .admin_adunit_site import *   # noqa: F401,F403
except ImportError:
    pass
