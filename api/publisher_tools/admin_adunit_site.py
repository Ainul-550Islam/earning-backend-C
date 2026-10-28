# publisher_tools/admin_adunit_site.py
"""
Admin registrations for ad_unit_management/ and site_management/ subfolder models।

admin.py-তে import করো:
    try:
        from .admin_adunit_site import *   # noqa: F401,F403
    except ImportError:
        pass

Registered models (27):
  ad_unit_management/ (10):
    AdUnitCreativeSpec, AdSizePreset, AdUnitPositionData, AdUnitTargetingRule,
    FrequencyCap, BannerAdConfig, VideoAdConfig, NativeAdConfig,
    OfferwallAdConfig, RewardedVideoConfig

  site_management/ (13):
    SiteCategory, SiteCategoryMapping, SiteContentPolicy, SiteTechnology,
    SiteDomainVerificationToken, SiteApprovalRecord, SiteAudienceProfile,
    SiteBlacklistEntry, SiteWhitelistEntry, SiteGeoData, SiteGeoTargetingRule,
    SiteQualityScore, SiteTrafficSnapshot, TrafficAnomaly

  mediation_management/ (4):
    AdSource, DemandPartner, MediationConfig, NetworkPerformanceSnapshot
"""

from django.contrib import admin

try:
    from .ad_unit_management.ad_unit_model import AdUnitCreativeSpec
    from .ad_unit_management.ad_unit_size import AdSizePreset
    from .ad_unit_management.ad_unit_position import AdUnitPositionData
    from .ad_unit_management.ad_unit_targeting import AdUnitTargetingRule
    from .ad_unit_management.ad_unit_frequency import FrequencyCap, FrequencyLog
    from .ad_unit_management.banner_ad_unit import BannerAdConfig
    from .ad_unit_management.video_ad_unit import VideoAdConfig
    from .ad_unit_management.native_ad_unit import NativeAdConfig
    from .ad_unit_management.offerwall_unit import OfferwallAdConfig
    from .ad_unit_management.rewarded_video_unit import RewardedVideoConfig
    _ADUNIT_MODELS = True
except ImportError:
    _ADUNIT_MODELS = False

try:
    from .site_management.site_category import SiteCategory, SiteCategoryMapping
    from .site_management.site_model import SiteContentPolicy, SiteTechnology
    from .site_management.site_domain import SiteDomainVerificationToken
    from .site_management.site_approval import SiteApprovalRecord
    from .site_management.site_audience import SiteAudienceProfile, SiteAudienceSnapshot
    from .site_management.site_blacklist import SiteBlacklistEntry
    from .site_management.site_whitelist import SiteWhitelistEntry
    from .site_management.site_geo import SiteGeoData, SiteGeoTargetingRule
    from .site_management.site_quality_score import SiteQualityScore
    from .site_management.site_traffic import SiteTrafficSnapshot, TrafficAnomaly
    _SITE_MODELS = True
except ImportError:
    _SITE_MODELS = False

try:
    from .mediation_management.ad_source_manager import AdSource
    from .mediation_management.demand_partner_manager import DemandPartner
    from .mediation_management.mediation_manager import MediationConfig
    _MEDIATION_MODELS = True
except ImportError:
    _MEDIATION_MODELS = False


# ══════════════════════════════════════════════════════════════════════════════
# AD UNIT MANAGEMENT ADMIN
# ══════════════════════════════════════════════════════════════════════════════

if _ADUNIT_MODELS:

    @admin.register(AdUnitCreativeSpec)
    class AdUnitCreativeSpecAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'supported_formats', 'max_file_size_kb',
                         'supports_rich_media', 'supports_expandable', 'ssl_required')
        search_fields = ('ad_unit__name', 'ad_unit__unit_id')
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

        def supported_formats(self, obj):
            types = obj.accepted_mime_types or []
            return ', '.join(types[:3]) + ('...' if len(types) > 3 else '')
        supported_formats.short_description = 'Accepted MIME'

    @admin.register(AdSizePreset)
    class AdSizePresetAdmin(admin.ModelAdmin):
        list_display  = ('name', 'width', 'height', 'is_iab_standard',
                         'is_mobile_only', 'is_desktop_only', 'avg_ecpm_multiplier',
                         'is_active')
        list_filter   = ('is_iab_standard', 'is_mobile_only', 'is_desktop_only', 'is_active')
        search_fields = ('name',)
        ordering      = ('name',)
        readonly_fields = ('created_at', 'updated_at')

    @admin.register(AdUnitPositionData)
    class AdUnitPositionDataAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'position', 'avg_viewability',
                 'avg_ecpm', 'impressions', 'date')
        list_filter   = ('position', 'date')
        search_fields = ('ad_unit__name', 'ad_unit__unit_id')
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    class AdUnitTargetingRuleInline(admin.TabularInline):
        model  = AdUnitTargetingRule
        extra  = 0
        fields = ('rule_type', 'operator', 'values', 'is_active', 'priority')
        show_change_link = True

    @admin.register(AdUnitTargetingRule)
    class AdUnitTargetingRuleAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'rule_type', 'operator', 'is_active', 'priority')
        list_filter   = ('rule_type', 'operator', 'is_active')
        search_fields = ('ad_unit__name', 'ad_unit__unit_id')
        ordering      = ('-priority',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(FrequencyCap)
    class FrequencyCapAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'cap_type', 'max_count', 'window_type', 'window_hours', 'is_active')
        list_filter   = ('cap_type', 'window_type', 'is_active')
        search_fields = ('ad_unit__name',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(BannerAdConfig)
    class BannerAdConfigAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'lazy_load', 'is_sticky', 'auto_collapse',
                 'collapse_delay_ms', 'border_enabled')
        list_filter   = ('lazy_load', 'is_sticky', 'auto_collapse')
        search_fields = ('ad_unit__name', 'ad_unit__unit_id')
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(VideoAdConfig)
    class VideoAdConfigAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'player_width', 'player_height', 'autoplay',
                         'max_duration_sec', 'skippable', 'min_viewability_pct')
        list_filter   = ('autoplay', 'autoplay_muted', 'skippable')
        search_fields = ('ad_unit__name',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(NativeAdConfig)
    class NativeAdConfigAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'template_type', 'show_headline',
                 'show_description', 'show_image', 'show_cta_button')
        search_fields = ('ad_unit__name',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(OfferwallAdConfig)
    class OfferwallAdConfigAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'currency_name', 'exchange_rate',
                 'max_offers_shown', 'filter_by_device', 'min_offer_reward')
        search_fields = ('ad_unit__name',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'

    @admin.register(RewardedVideoConfig)
    class RewardedVideoConfigAdmin(admin.ModelAdmin):
        list_display  = ('get_unit', 'reward_name', 'reward_amount', 'reward_type',
                 'max_video_length_sec', 'min_video_watch_pct', 'prompt_dialog_title')
        search_fields = ('ad_unit__name',)
        readonly_fields = ('created_at', 'updated_at')

        def get_unit(self, obj):
            return obj.ad_unit.name if obj.ad_unit else '—'
        get_unit.short_description = 'Ad Unit'


# ══════════════════════════════════════════════════════════════════════════════
# SITE MANAGEMENT ADMIN
# ══════════════════════════════════════════════════════════════════════════════

if _SITE_MODELS:

    @admin.register(SiteCategory)
    class SiteCategoryAdmin(admin.ModelAdmin):
        list_display  = ('name', 'slug', 'iab_code', 'parent', 'is_active', 'sort_order')
        list_filter   = ('is_active',)
        search_fields = ('name', 'slug', 'iab_code')
        prepopulated_fields = {'slug': ('name',)}
        ordering      = ('sort_order', 'name')
        readonly_fields = ('created_at', 'updated_at')

    @admin.register(SiteCategoryMapping)
    class SiteCategoryMappingAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'get_category', 'is_primary', 'source', 'confidence')
        list_filter   = ('source', 'is_primary')
        search_fields = ('site__name', 'site__url', 'category__name')
        readonly_fields = ('created_at', 'updated_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

        def get_category(self, obj):
            return obj.category.name
        get_category.short_description = 'Category'

    @admin.register(SiteContentPolicy)
    class SiteContentPolicyAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'content_language', 'has_adult_content',
                         'is_children_site', 'coppa_compliant', 'gdpr_compliant',
                         'has_consent_banner', 'last_reviewed_at')
        list_filter   = ('has_adult_content', 'is_children_site', 'coppa_compliant', 'gdpr_compliant')
        search_fields = ('site__name', 'site__url')
        readonly_fields = ('created_at', 'updated_at', 'last_reviewed_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteTechnology)
    class SiteTechnologyAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'cms', 'framework', 'cdn_provider',
                         'has_amp', 'has_pwa', 'uses_https', 'mobile_friendly',
                         'avg_page_load_sec')
        list_filter   = ('has_amp', 'has_pwa', 'uses_https', 'mobile_friendly')
        search_fields = ('site__name', 'cms', 'framework')
        readonly_fields = ('created_at', 'updated_at', 'detected_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteDomainVerificationToken)
    class SiteDomainVerificationTokenAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'token', 'method', 'is_verified',
                         'verified_at', 'attempts', 'expires_at')
        list_filter   = ('method', 'is_verified')
        search_fields = ('site__name', 'token')
        readonly_fields = ('created_at', 'updated_at', 'verified_at', 'last_attempt')
        ordering      = ('-created_at',)

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

        actions = ['mark_verified']

        @admin.action(description='Mark selected tokens as verified')
        def mark_verified(self, request, queryset):
            from django.utils import timezone
            updated = queryset.update(is_verified=True, verified_at=timezone.now())
            self.message_user(request, f'{updated} tokens verified.')

    @admin.register(SiteApprovalRecord)
    class SiteApprovalRecordAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'action', 'reviewer', 'previous_status',
                         'review_completed_at', 'created_at')
        list_filter   = ('action',)
        search_fields = ('site__name', 'site__url')
        readonly_fields = ('created_at', 'updated_at', 'review_completed_at')
        ordering      = ('-created_at',)
        date_hierarchy = 'created_at'

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteAudienceProfile)
    class SiteAudienceProfileAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'desktop_pct', 'mobile_pct', 'tablet_pct',
                         'bounce_rate_pct', 'pages_per_session', 'last_updated_at')
        search_fields = ('site__name',)
        readonly_fields = ('created_at', 'updated_at', 'last_updated_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteBlacklistEntry)
    class SiteBlacklistEntryAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'entry_type', 'value', 'is_active', 'created_at')
        list_filter   = ('entry_type', 'is_active')
        search_fields = ('site__name', 'value')
        readonly_fields = ('created_at', 'updated_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteWhitelistEntry)
    class SiteWhitelistEntryAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'entry_type', 'value', 'is_active')
        list_filter   = ('entry_type', 'is_active')
        search_fields = ('site__name', 'value')
        readonly_fields = ('created_at', 'updated_at')

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteQualityScore)
    class SiteQualityScoreAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'overall_score', 'content_score', 'traffic_score',
                         'technical_score', 'compliance_score', 'fraud_risk_score',
                         'last_calculated_at')
        search_fields = ('site__name',)
        readonly_fields = ('created_at', 'updated_at', 'last_calculated_at')
        ordering      = ('overall_score',)

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(SiteTrafficSnapshot)
    class SiteTrafficSnapshotAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'snapshot_date', 'total_requests', 'unique_visitors',
                         'page_views', 'bot_traffic_pct', 'ivt_rate_pct')
        list_filter   = ('snapshot_date',)
        search_fields = ('site__name',)
        readonly_fields = ('created_at', 'updated_at')
        ordering      = ('-snapshot_date',)
        date_hierarchy = 'snapshot_date'

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

    @admin.register(TrafficAnomaly)
    class TrafficAnomalyAdmin(admin.ModelAdmin):
        list_display  = ('get_site', 'anomaly_type', 'severity', 'detected_at',
                         'is_resolved', 'auto_action_taken')
        list_filter   = ('anomaly_type', 'severity', 'is_resolved')
        search_fields = ('site__name',)
        readonly_fields = ('created_at', 'updated_at', 'detected_at', 'resolved_at')
        ordering      = ('-detected_at',)
        date_hierarchy = 'detected_at'

        def get_site(self, obj):
            return obj.site.name
        get_site.short_description = 'Site'

        actions = ['mark_resolved']

        @admin.action(description='Mark selected anomalies as resolved')
        def mark_resolved(self, request, queryset):
            from django.utils import timezone
            updated = queryset.update(is_resolved=True, resolved_at=timezone.now())
            self.message_user(request, f'{updated} anomalies marked resolved.')


# ══════════════════════════════════════════════════════════════════════════════
# MEDIATION MANAGEMENT ADMIN
# ══════════════════════════════════════════════════════════════════════════════

if _MEDIATION_MODELS:

    @admin.register(AdSource)
    class AdSourceAdmin(admin.ModelAdmin):
        list_display  = ('network', 'get_mediation_group', 'status', 'is_active',
                         'floor_price', 'bid_price', 'priority', 'is_bidder', 'last_ping')
        list_filter   = ('network', 'status', 'is_active', 'is_bidder')
        search_fields = ('network', 'placement_id', 'app_id')
        readonly_fields = ('created_at', 'updated_at', 'last_ping', 'error_message')
        ordering      = ('-priority', 'network')

        def get_mediation_group(self, obj):
            return obj.mediation_group.name if obj.mediation_group else '—'
        get_mediation_group.short_description = 'Mediation Group'

    @admin.register(DemandPartner)
    class DemandPartnerAdmin(admin.ModelAdmin):
        list_display  = ('name', 'partner_type', 'is_active', 'revenue_share_pct',
                         'payment_terms', 'total_spend',
                         'contract_start_date', 'contract_end_date')
        list_filter   = ('partner_type', 'is_active')
        search_fields = ('name', 'slug', 'contact_email')
        readonly_fields = ('created_at', 'updated_at', 'total_spend')
        ordering      = ('name',)
        prepopulated_fields = {'slug': ('name',)}

    try:
        @admin.register(MediationConfig)
        class MediationConfigAdmin(admin.ModelAdmin):
            list_display  = ('get_group', 'strategy', 'timeout_ms', 'enable_auto_ecpm',
                             'prebid_enabled', 'ab_test_enabled')
            list_filter   = ('strategy', 'prebid_enabled', 'ab_test_enabled')
            readonly_fields = ('created_at', 'updated_at')

            def get_group(self, obj):
                return obj.mediation_group.name if obj.mediation_group else '—'
            get_group.short_description = 'Mediation Group'
    except Exception:
        pass
