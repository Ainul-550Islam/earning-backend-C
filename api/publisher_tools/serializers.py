# api/publisher_tools/serializers.py
"""
Publisher Tools — DRF Serializers।
সব Model-এর জন্য Create, Update, List, Detail serializer।

আপডেট: নতুন serializers যোগ করা হয়েছে —
  ✅ PublisherKYCSerializer / KYCDocumentSerializer / KYCSubmitSerializer
  ✅ PublisherBankAccountSerializer / BankAccountAddSerializer
  ✅ PublisherStoreSerializer / StoreContactMessageSerializer
  ✅ PublisherSubscriptionSerializer / SubscriptionPlanSerializer / SubscriptionPaymentHistorySerializer
  ✅ PublisherVerificationSerializer
  ✅ PublisherBusinessSerializer
  ✅ PublisherRatingSerializer / PublisherRatingConfigSerializer
  ✅ PublisherRatingRecordSerializer / PublisherAggregateRatingSerializer
  ✅ PublisherCommissionSerializer / CommissionTierSerializer
  ✅ PublisherReferralSerializer
  ✅ PublisherBlacklistSerializer / PublisherBlacklistEntrySerializer
  ✅ PublisherLeaderboardSerializer
  ✅ PublisherPerformanceTargetSerializer / PublisherPerformanceSnapshotSerializer
"""
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Publisher, Site, App, InventoryVerification,
    AdUnit, AdPlacement, AdUnitTargeting,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric,
)
from .utils import (
    calculate_ecpm, calculate_ctr, calculate_fill_rate,
    format_currency, mask_sensitive_data,
)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class PublisherCreateSerializer(serializers.ModelSerializer):
    """নতুন Publisher তৈরির জন্য"""

    class Meta:
        model = Publisher
        fields = [
            'display_name', 'business_type', 'contact_email',
            'contact_phone', 'website', 'country', 'city',
            'address', 'revenue_share_percentage',
        ]

    def validate_contact_email(self, value):
        return value.lower().strip()

    def validate_website(self, value):
        if value:
            from .validators import validate_url_is_reachable_format
            validate_url_is_reachable_format(value)
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        if hasattr(user, 'publisher_profile'):
            from .exceptions import PublisherAlreadyExists
            raise PublisherAlreadyExists()
        validated_data['user'] = user
        return super().create(validated_data)


class PublisherUpdateSerializer(serializers.ModelSerializer):
    """Publisher profile update-এর জন্য"""

    class Meta:
        model = Publisher
        fields = [
            'display_name', 'business_type', 'contact_email',
            'contact_phone', 'website', 'country', 'city', 'address',
        ]
        read_only_fields = ['publisher_id', 'user', 'status', 'tier']

    def validate_contact_email(self, value):
        return value.lower().strip()


class PublisherListSerializer(serializers.ModelSerializer):
    """Publisher list (admin) — minimal fields"""
    active_sites  = serializers.IntegerField(source='active_sites_count', read_only=True)
    active_apps   = serializers.IntegerField(source='active_apps_count', read_only=True)
    available_bal = serializers.DecimalField(
        source='available_balance', max_digits=14, decimal_places=4, read_only=True
    )

    class Meta:
        model = Publisher
        fields = [
            'id', 'publisher_id', 'display_name', 'business_type',
            'country', 'status', 'tier', 'is_kyc_verified',
            'active_sites', 'active_apps', 'total_revenue',
            'available_bal', 'created_at',
        ]


class PublisherDetailSerializer(serializers.ModelSerializer):
    """Publisher detail — full fields"""
    active_sites      = serializers.IntegerField(source='active_sites_count', read_only=True)
    active_apps       = serializers.IntegerField(source='active_apps_count', read_only=True)
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    api_key_masked    = serializers.SerializerMethodField()

    class Meta:
        model = Publisher
        fields = [
            'id', 'publisher_id', 'display_name', 'business_type',
            'contact_email', 'contact_phone', 'website',
            'country', 'city', 'address',
            'status', 'tier', 'is_kyc_verified', 'is_email_verified',
            'kyc_verified_at',
            'revenue_share_percentage',
            'total_revenue', 'total_paid_out', 'pending_balance',
            'available_balance',
            'api_key_masked',
            'active_sites', 'active_apps',
            'internal_notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['publisher_id', 'status', 'tier', 'total_revenue', 'created_at']

    def get_api_key_masked(self, obj):
        if obj.api_key:
            return mask_sensitive_data(obj.api_key, 8)
        return None


class PublisherStatsSerializer(serializers.Serializer):
    """Publisher dashboard stats"""
    publisher_id      = serializers.CharField()
    display_name      = serializers.CharField()
    total_revenue     = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_paid_out    = serializers.DecimalField(max_digits=14, decimal_places=4)
    pending_balance   = serializers.DecimalField(max_digits=14, decimal_places=4)
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=4)
    active_sites      = serializers.IntegerField()
    active_apps       = serializers.IntegerField()
    total_ad_units    = serializers.IntegerField()
    period_revenue    = serializers.DecimalField(max_digits=14, decimal_places=4)
    period_impressions= serializers.IntegerField()
    period_clicks     = serializers.IntegerField()
    period_ecpm       = serializers.DecimalField(max_digits=10, decimal_places=4)


# ──────────────────────────────────────────────────────────────────────────────
# SITE SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class SiteCreateSerializer(serializers.ModelSerializer):
    """নতুন Site register করার জন্য"""

    class Meta:
        model = Site
        fields = [
            'name', 'domain', 'url', 'category', 'subcategory',
            'language', 'target_countries', 'content_rating',
            'monthly_pageviews', 'monthly_unique_visitors',
        ]

    def validate_domain(self, value):
        from .validators import validate_domain
        return validate_domain(value)

    def validate_url(self, value):
        from .validators import validate_url_is_reachable_format
        validate_url_is_reachable_format(value)
        return value

    def validate(self, attrs):
        domain = attrs.get('domain', '')
        if Site.objects.filter(domain=domain).exists():
            raise serializers.ValidationError({'domain': _('This domain is already registered.')})
        return attrs

    def create(self, validated_data):
        publisher = self.context['request'].user.publisher_profile
        validated_data['publisher'] = publisher
        return super().create(validated_data)


class SiteUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            'name', 'category', 'subcategory', 'language',
            'target_countries', 'content_rating',
            'monthly_pageviews', 'monthly_unique_visitors',
        ]
        read_only_fields = ['domain', 'site_id', 'publisher', 'status']


class SiteListSerializer(serializers.ModelSerializer):
    ctr = serializers.FloatField(read_only=True)

    class Meta:
        model = Site
        fields = [
            'id', 'site_id', 'name', 'domain', 'category',
            'status', 'quality_score', 'ads_txt_verified',
            'total_revenue', 'lifetime_impressions', 'ctr',
            'created_at',
        ]


class SiteDetailSerializer(serializers.ModelSerializer):
    ctr            = serializers.FloatField(read_only=True)
    is_active      = serializers.BooleanField(read_only=True)
    publisher_name = serializers.CharField(source='publisher.display_name', read_only=True)

    class Meta:
        model = Site
        fields = '__all__'
        read_only_fields = ['site_id', 'publisher', 'status', 'created_at', 'updated_at']


class SiteVerifySerializer(serializers.Serializer):
    """Verification trigger করার জন্য"""
    method = serializers.ChoiceField(choices=[
        'ads_txt', 'meta_tag', 'dns_record', 'file', 'api',
    ])


# ──────────────────────────────────────────────────────────────────────────────
# APP SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class AppCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = App
        fields = [
            'name', 'platform', 'package_name', 'category',
            'play_store_url', 'app_store_url', 'store_app_id',
            'content_rating', 'description', 'icon_url', 'version',
        ]

    def validate_package_name(self, value):
        from .validators import validate_android_package_name
        if '.' in value and value.replace('.', '').isalnum():
            validate_android_package_name(value)
        if App.objects.filter(package_name=value).exists():
            raise serializers.ValidationError(_('This package name is already registered.'))
        return value

    def create(self, validated_data):
        publisher = self.context['request'].user.publisher_profile
        validated_data['publisher'] = publisher
        return super().create(validated_data)


class AppUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = App
        fields = [
            'name', 'category', 'description', 'icon_url',
            'play_store_url', 'app_store_url', 'version',
            'screenshot_urls', 'content_rating',
        ]
        read_only_fields = ['package_name', 'app_id', 'platform', 'publisher', 'status']


class AppListSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = App
        fields = [
            'id', 'app_id', 'name', 'platform', 'package_name',
            'category', 'status', 'quality_score',
            'total_downloads', 'store_rating', 'total_revenue',
            'is_active', 'created_at',
        ]


class AppDetailSerializer(serializers.ModelSerializer):
    is_active      = serializers.BooleanField(read_only=True)
    publisher_name = serializers.CharField(source='publisher.display_name', read_only=True)

    class Meta:
        model = App
        fields = '__all__'
        read_only_fields = ['app_id', 'publisher', 'status', 'created_at', 'updated_at']


# ──────────────────────────────────────────────────────────────────────────────
# INVENTORY VERIFICATION SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class InventoryVerificationSerializer(serializers.ModelSerializer):
    is_verified = serializers.BooleanField(read_only=True)
    is_expired  = serializers.BooleanField(read_only=True)
    snippet     = serializers.SerializerMethodField()

    class Meta:
        model = InventoryVerification
        fields = [
            'id', 'inventory_type', 'method', 'status',
            'verification_token', 'snippet',
            'is_verified', 'is_expired',
            'verified_at', 'expires_at', 'attempt_count',
            'failure_reason', 'created_at',
        ]
        read_only_fields = [
            'verification_token', 'status', 'verified_at',
            'attempt_count', 'failure_reason',
        ]

    def get_snippet(self, obj):
        if obj.method == 'ads_txt':
            from .utils import build_ads_txt_entry
            return build_ads_txt_entry(obj.publisher.publisher_id)
        elif obj.method == 'meta_tag':
            from .utils import build_verification_meta_tag
            return build_verification_meta_tag(obj.verification_token)
        elif obj.method == 'dns_record':
            from .utils import build_verification_dns_record
            return build_verification_dns_record(obj.verification_token)
        return obj.verification_code


class VerifyInventorySerializer(serializers.Serializer):
    """Manual verification trigger"""
    force = serializers.BooleanField(default=False, help_text='Force re-verify even if already verified')


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class AdUnitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdUnit
        fields = [
            'name', 'inventory_type', 'site', 'app',
            'format', 'width', 'height', 'is_responsive',
            'floor_price', 'description',
        ]

    def validate(self, attrs):
        inv_type = attrs.get('inventory_type', 'site')
        site = attrs.get('site')
        app  = attrs.get('app')
        if inv_type == 'site' and not site:
            raise serializers.ValidationError({'site': _('Site is required for website ad units.')})
        if inv_type == 'app' and not app:
            raise serializers.ValidationError({'app': _('App is required for mobile app ad units.')})
        publisher = self.context['request'].user.publisher_profile
        if site and site.publisher != publisher:
            raise serializers.ValidationError({'site': _('You do not own this site.')})
        if app and app.publisher != publisher:
            raise serializers.ValidationError({'app': _('You do not own this app.')})
        return attrs

    def validate_floor_price(self, value):
        from .validators import validate_floor_price
        validate_floor_price(value)
        return value

    def create(self, validated_data):
        publisher = self.context['request'].user.publisher_profile
        validated_data['publisher'] = publisher
        return super().create(validated_data)


class AdUnitUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdUnit
        fields = [
            'name', 'floor_price', 'is_test_mode', 'description',
            'width', 'height', 'is_responsive',
        ]
        read_only_fields = ['unit_id', 'publisher', 'format', 'site', 'app']


class AdUnitListSerializer(serializers.ModelSerializer):
    ctr      = serializers.FloatField(read_only=True)
    size_lbl = serializers.CharField(source='size_label', read_only=True)

    class Meta:
        model = AdUnit
        fields = [
            'id', 'unit_id', 'name', 'format', 'size_lbl',
            'inventory_type', 'status', 'floor_price',
            'total_impressions', 'total_clicks', 'total_revenue',
            'avg_ecpm', 'fill_rate', 'ctr', 'is_test_mode',
            'created_at',
        ]


class AdUnitDetailSerializer(serializers.ModelSerializer):
    ctr      = serializers.FloatField(read_only=True)
    size_lbl = serializers.CharField(source='size_label', read_only=True)

    class Meta:
        model = AdUnit
        fields = '__all__'
        read_only_fields = ['unit_id', 'publisher', 'created_at', 'updated_at']


# ──────────────────────────────────────────────────────────────────────────────
# AD PLACEMENT SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class AdPlacementSerializer(serializers.ModelSerializer):
    effective_floor = serializers.DecimalField(
        source='effective_floor_price', max_digits=8, decimal_places=4, read_only=True
    )

    class Meta:
        model = AdPlacement
        fields = [
            'id', 'ad_unit', 'name', 'position',
            'is_active', 'show_on_mobile', 'show_on_tablet', 'show_on_desktop',
            'refresh_type', 'refresh_interval_seconds',
            'floor_price_override', 'effective_floor',
            'min_viewability_percentage', 'avg_viewability',
            'css_selector', 'custom_css',
            'total_impressions', 'total_clicks', 'total_revenue',
            'description', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_refresh_interval_seconds(self, value):
        from .validators import validate_refresh_interval
        validate_refresh_interval(value)
        return value


class AdPlacementCreateSerializer(AdPlacementSerializer):
    def validate_ad_unit(self, value):
        publisher = self.context['request'].user.publisher_profile
        if value.publisher != publisher:
            raise serializers.ValidationError(_('You do not own this ad unit.'))
        return value


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT TARGETING SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class AdUnitTargetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdUnitTargeting
        fields = [
            'id', 'ad_unit', 'name',
            'target_countries', 'exclude_countries',
            'target_regions', 'target_cities',
            'device_type', 'target_os', 'min_os_version',
            'target_browsers', 'target_languages',
            'frequency_cap', 'frequency_window_hours',
            'schedule_days', 'schedule_hours_start', 'schedule_hours_end',
            'is_active', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_target_countries(self, value):
        from .validators import validate_country_codes
        if value and value != ['ALL']:
            validate_country_codes(value)
        return value

    def validate(self, attrs):
        start = attrs.get('schedule_hours_start', 0)
        end   = attrs.get('schedule_hours_end', 23)
        from .validators import validate_schedule_hours
        validate_schedule_hours(start, end)
        return attrs


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class MediationGroupSerializer(serializers.ModelSerializer):
    waterfall_count = serializers.SerializerMethodField()

    class Meta:
        model = MediationGroup
        fields = [
            'id', 'ad_unit', 'name', 'mediation_type',
            'auto_optimize', 'optimization_interval_hours', 'last_optimized_at',
            'is_active',
            'total_ad_requests', 'total_impressions', 'total_revenue',
            'avg_ecpm', 'fill_rate',
            'waterfall_count',
            'description', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_optimized_at', 'created_at', 'updated_at']

    def get_waterfall_count(self, obj):
        return obj.waterfall_items.filter(status='active').count()


class WaterfallItemSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source='network_label', read_only=True)
    win_rate     = serializers.SerializerMethodField()

    class Meta:
        model = WaterfallItem
        fields = [
            'id', 'mediation_group', 'network', 'network_name',
            'name', 'priority', 'floor_ecpm', 'bidding_type',
            'network_app_id', 'network_unit_id',
            'status',
            'total_ad_requests', 'total_impressions', 'total_revenue',
            'avg_ecpm', 'fill_rate', 'avg_latency_ms',
            'win_rate',
            'extra_config', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_win_rate(self, obj):
        if obj.total_ad_requests > 0:
            return round((obj.total_impressions / obj.total_ad_requests) * 100, 2)
        return 0.0

    def validate_priority(self, value):
        from .validators import validate_waterfall_priority
        validate_waterfall_priority(value)
        return value

    def validate_floor_ecpm(self, value):
        from .validators import validate_floor_price
        validate_floor_price(value)
        return value


class WaterfallReorderSerializer(serializers.Serializer):
    """Waterfall items reorder করার জন্য"""
    items = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField()),
        help_text='[{"id": 1, "priority": 1}, {"id": 2, "priority": 2}, ...]'
    )

    def validate_items(self, value):
        priorities = [item['priority'] for item in value]
        if len(priorities) != len(set(priorities)):
            raise serializers.ValidationError(_('Duplicate priorities are not allowed.'))
        return value


class HeaderBiddingConfigSerializer(serializers.ModelSerializer):
    bid_response_rate = serializers.FloatField(read_only=True)
    win_rate          = serializers.FloatField(read_only=True)

    class Meta:
        model = HeaderBiddingConfig
        fields = [
            'id', 'mediation_group', 'bidder_name', 'bidder_type',
            'bidder_params', 'endpoint_url',
            'timeout_ms', 'price_floor', 'status',
            'total_bid_requests', 'total_bid_responses', 'total_bid_wins',
            'total_revenue', 'avg_bid_cpm',
            'bid_response_rate', 'win_rate',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_timeout_ms(self, value):
        from .validators import validate_bid_timeout
        validate_bid_timeout(value)
        return value


# ──────────────────────────────────────────────────────────────────────────────
# EARNING SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class PublisherEarningSerializer(serializers.ModelSerializer):
    net_revenue  = serializers.DecimalField(
        source='net_publisher_revenue', max_digits=14, decimal_places=6, read_only=True
    )
    revenue_fmt  = serializers.SerializerMethodField()
    ad_unit_name = serializers.CharField(source='ad_unit.name', read_only=True, default=None)
    network_name = serializers.CharField(source='network.name', read_only=True, default=None)
    site_domain  = serializers.CharField(source='site.domain', read_only=True, default=None)
    app_package  = serializers.CharField(source='app.package_name', read_only=True, default=None)

    class Meta:
        model = PublisherEarning
        fields = [
            'id', 'publisher', 'ad_unit', 'ad_unit_name',
            'site', 'site_domain', 'app', 'app_package',
            'network', 'network_name',
            'granularity', 'date', 'hour',
            'earning_type', 'country', 'country_name',
            'ad_requests', 'impressions', 'clicks', 'conversions',
            'video_starts', 'video_completions',
            'gross_revenue', 'publisher_revenue', 'platform_revenue',
            'ecpm', 'ctr', 'fill_rate', 'rpm',
            'status',
            'invalid_traffic_deduction', 'adjustment_amount', 'adjustment_reason',
            'net_revenue', 'revenue_fmt',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_revenue_fmt(self, obj):
        return format_currency(obj.publisher_revenue)


class EarningsSummarySerializer(serializers.Serializer):
    """Aggregated earnings summary"""
    period_start        = serializers.DateField()
    period_end          = serializers.DateField()
    total_gross         = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_publisher     = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_impressions   = serializers.IntegerField()
    total_clicks        = serializers.IntegerField()
    total_ad_requests   = serializers.IntegerField()
    avg_ecpm            = serializers.DecimalField(max_digits=10, decimal_places=4)
    avg_fill_rate       = serializers.DecimalField(max_digits=5, decimal_places=2)
    avg_ctr             = serializers.DecimalField(max_digits=6, decimal_places=4)
    top_earning_unit    = serializers.CharField(allow_null=True)
    top_earning_country = serializers.CharField(allow_null=True)


# ──────────────────────────────────────────────────────────────────────────────
# PAYOUT THRESHOLD SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class PayoutThresholdSerializer(serializers.ModelSerializer):
    payment_details_masked = serializers.SerializerMethodField()

    class Meta:
        model = PayoutThreshold
        fields = [
            'id', 'publisher', 'payment_method',
            'minimum_threshold', 'payment_frequency',
            'processing_fee_flat', 'processing_fee_percentage',
            'withholding_tax_percentage',
            'payment_details_masked',
            'is_primary', 'is_verified', 'verified_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'publisher', 'is_verified', 'verified_at', 'created_at']
        extra_kwargs = {'payment_details': {'write_only': True}}

    def get_payment_details_masked(self, obj):
        details = obj.payment_details
        if not details:
            return {}
        masked = {}
        for key, value in details.items():
            if any(s in key.lower() for s in ['account', 'number', 'email', 'key', 'id']):
                masked[key] = mask_sensitive_data(str(value))
            else:
                masked[key] = value
        return masked

    def validate_minimum_threshold(self, value):
        from .validators import validate_payout_threshold
        validate_payout_threshold(value)
        return value

    def create(self, validated_data):
        publisher = self.context['request'].user.publisher_profile
        validated_data['publisher'] = publisher
        return super().create(validated_data)


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class PublisherInvoiceListSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = PublisherInvoice
        fields = [
            'id', 'invoice_number', 'invoice_type',
            'period_start', 'period_end',
            'gross_revenue', 'publisher_share', 'net_payable', 'currency',
            'status', 'is_overdue', 'due_date', 'paid_at',
            'created_at',
        ]


class PublisherInvoiceDetailSerializer(serializers.ModelSerializer):
    is_overdue     = serializers.BooleanField(read_only=True)
    publisher_name = serializers.CharField(source='publisher.display_name', read_only=True)

    class Meta:
        model = PublisherInvoice
        fields = '__all__'
        read_only_fields = [
            'invoice_number', 'publisher', 'created_at', 'updated_at',
            'issued_at', 'paid_at', 'failed_at', 'processed_by',
        ]


class InvoiceDisputeSerializer(serializers.Serializer):
    reason          = serializers.CharField(min_length=20, max_length=2000)
    disputed_amount = serializers.DecimalField(max_digits=14, decimal_places=4, required=False)


# ──────────────────────────────────────────────────────────────────────────────
# TRAFFIC SAFETY LOG SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class TrafficSafetyLogSerializer(serializers.ModelSerializer):
    is_high_risk    = serializers.BooleanField(read_only=True)
    requires_action = serializers.BooleanField(read_only=True)
    publisher_name  = serializers.CharField(source='publisher.display_name', read_only=True)

    class Meta:
        model = TrafficSafetyLog
        fields = [
            'id', 'publisher', 'publisher_name',
            'site', 'app', 'ad_unit',
            'traffic_type', 'severity', 'detected_at',
            'ip_address', 'country', 'device_id',
            'fraud_score', 'confidence_score', 'detection_method',
            'detection_signals',
            'affected_impressions', 'affected_clicks',
            'revenue_at_risk', 'revenue_deducted',
            'action_taken', 'action_taken_at',
            'is_false_positive', 'notes',
            'is_high_risk', 'requires_action',
            'created_at',
        ]
        read_only_fields = [
            'id', 'fraud_score', 'confidence_score', 'detected_at',
            'revenue_at_risk', 'revenue_deducted', 'created_at',
        ]


class FraudActionSerializer(serializers.Serializer):
    """Fraud log-এ action নেওয়ার জন্য"""
    action = serializers.ChoiceField(choices=[
        'flagged', 'deducted', 'warned', 'suspended', 'blocked', 'no_action',
    ])
    notes            = serializers.CharField(required=False, allow_blank=True)
    deduction_amount = serializers.DecimalField(max_digits=12, decimal_places=4, required=False)


class MarkFalsePositiveSerializer(serializers.Serializer):
    is_false_positive = serializers.BooleanField()
    notes             = serializers.CharField(required=False, allow_blank=True)


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class SiteQualityMetricSerializer(serializers.ModelSerializer):
    is_high_quality = serializers.BooleanField(read_only=True)
    needs_attention = serializers.BooleanField(read_only=True)
    site_domain     = serializers.CharField(source='site.domain', read_only=True)

    class Meta:
        model = SiteQualityMetric
        fields = [
            'id', 'site', 'site_domain', 'date',
            'viewability_rate', 'avg_time_in_view',
            'measured_impressions', 'viewable_impressions',
            'bot_traffic_percentage', 'invalid_traffic_percentage', 'vpn_traffic_percentage',
            'content_quality', 'content_score', 'spam_score',
            'adult_content_detected', 'malware_detected',
            'page_speed_score', 'lcp_ms', 'fid_ms', 'cls_score',
            'overall_quality_score', 'score_change',
            'ads_txt_present', 'ads_txt_valid', 'ad_density_score',
            'has_alerts', 'alert_details',
            'is_high_quality', 'needs_attention',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class QualityTrendSerializer(serializers.Serializer):
    date                       = serializers.DateField()
    overall_quality_score      = serializers.IntegerField()
    viewability_rate           = serializers.DecimalField(max_digits=5, decimal_places=2)
    invalid_traffic_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    content_quality            = serializers.CharField()


# ──────────────────────────────────────────────────────────────────────────────
# DASHBOARD / REPORT SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class DateRangeSerializer(serializers.Serializer):
    start_date  = serializers.DateField()
    end_date    = serializers.DateField()
    granularity = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )

    def validate(self, attrs):
        from .validators import validate_date_range
        validate_date_range(attrs['start_date'], attrs['end_date'])
        return attrs


class ReportFilterSerializer(serializers.Serializer):
    start_date    = serializers.DateField()
    end_date      = serializers.DateField()
    granularity   = serializers.ChoiceField(choices=['hourly', 'daily', 'weekly', 'monthly'], default='daily')
    site_ids      = serializers.ListField(child=serializers.UUIDField(), required=False)
    app_ids       = serializers.ListField(child=serializers.UUIDField(), required=False)
    ad_unit_ids   = serializers.ListField(child=serializers.UUIDField(), required=False)
    countries     = serializers.ListField(child=serializers.CharField(), required=False)
    earning_types = serializers.ListField(child=serializers.CharField(), required=False)
    group_by      = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        from .validators import validate_date_range
        validate_date_range(attrs['start_date'], attrs['end_date'])
        return attrs


# ══════════════════════════════════════════════════════════════════════════════
# ══  NEW SERIALIZERS — publisher_management subfolder floating models  ═══════
# ══════════════════════════════════════════════════════════════════════════════

# ── KYC ───────────────────────────────────────────────────────────────────────

class KYCDocumentSerializer(serializers.Serializer):
    """KYCDocument model (publisher_management/publisher_kyc.py)"""
    pk            = serializers.IntegerField(read_only=True)
    document_type = serializers.CharField(max_length=50)
    file_url      = serializers.URLField()
    status        = serializers.CharField(max_length=20, read_only=True)
    is_expired    = serializers.BooleanField(read_only=True, default=False)
    uploaded_at   = serializers.DateTimeField(source='created_at', read_only=True)


class PublisherKYCSerializer(serializers.Serializer):
    """PublisherKYC model (publisher_management/publisher_kyc.py)"""
    pk               = serializers.IntegerField(read_only=True)
    kyc_type         = serializers.ChoiceField(choices=['individual', 'business'])
    full_name        = serializers.CharField(max_length=200)
    date_of_birth    = serializers.DateField(required=False, allow_null=True)
    nationality      = serializers.CharField(max_length=3, required=False, allow_blank=True)
    id_type          = serializers.ChoiceField(choices=[
        'passport', 'national_id', 'driving_license', 'tax_id', 'other'
    ])
    id_number        = serializers.CharField(max_length=100)
    address          = serializers.CharField(max_length=500, required=False, allow_blank=True)
    city             = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country          = serializers.CharField(max_length=3)
    postal_code      = serializers.CharField(max_length=20, required=False, allow_blank=True)
    status           = serializers.CharField(read_only=True)
    is_approved      = serializers.BooleanField(read_only=True, default=False)
    is_expired       = serializers.BooleanField(read_only=True, default=False)
    can_submit       = serializers.BooleanField(read_only=True, default=True)
    submitted_at     = serializers.DateTimeField(read_only=True, allow_null=True)
    reviewed_at      = serializers.DateTimeField(read_only=True, allow_null=True)
    expires_at       = serializers.DateTimeField(read_only=True, allow_null=True)
    rejection_reason = serializers.CharField(read_only=True, allow_blank=True)
    documents        = KYCDocumentSerializer(many=True, read_only=True)


class KYCSubmitSerializer(serializers.Serializer):
    """POST /publisher-advanced/kyc-submit/ input validation"""
    kyc_type      = serializers.ChoiceField(choices=['individual', 'business'])
    full_name     = serializers.CharField(max_length=200)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    nationality   = serializers.CharField(max_length=3, required=False, allow_blank=True)
    id_type       = serializers.ChoiceField(choices=[
        'passport', 'national_id', 'driving_license', 'tax_id', 'other'
    ])
    id_number     = serializers.CharField(max_length=100)
    address       = serializers.CharField(max_length=500, required=False, allow_blank=True)
    city          = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country       = serializers.CharField(max_length=3)
    postal_code   = serializers.CharField(max_length=20, required=False, allow_blank=True)
    documents     = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text='[{"document_type": "id_front", "file_url": "https://..."}]',
    )


# ── Bank Account ──────────────────────────────────────────────────────────────

class PublisherBankAccountSerializer(serializers.Serializer):
    """PublisherBankAccount model (publisher_management/publisher_bank_account.py)"""
    pk                  = serializers.IntegerField(read_only=True)
    account_type        = serializers.ChoiceField(choices=[
        'bank_transfer', 'paypal', 'wise', 'payoneer', 'crypto', 'other'
    ])
    account_holder_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    masked_number       = serializers.SerializerMethodField()
    is_primary          = serializers.BooleanField(read_only=True)
    is_verified         = serializers.BooleanField(read_only=True)
    status              = serializers.CharField(read_only=True)
    display_info        = serializers.CharField(read_only=True, allow_blank=True)
    currency            = serializers.CharField(max_length=3, default='USD')
    added_at            = serializers.DateTimeField(source='created_at', read_only=True)

    def get_masked_number(self, obj):
        if hasattr(obj, 'masked_account_number'):
            return obj.masked_account_number()
        return '****'


class BankAccountAddSerializer(serializers.Serializer):
    """POST /publisher-advanced/bank-accounts/add/ input validation"""
    account_type        = serializers.ChoiceField(choices=[
        'bank_transfer', 'paypal', 'wise', 'payoneer', 'crypto', 'other'
    ])
    account_holder_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    account_number      = serializers.CharField(max_length=50, required=False, allow_blank=True)
    routing_number      = serializers.CharField(max_length=20, required=False, allow_blank=True)
    bank_name           = serializers.CharField(max_length=200, required=False, allow_blank=True)
    bank_country        = serializers.CharField(max_length=3, required=False, allow_blank=True)
    swift_code          = serializers.CharField(max_length=15, required=False, allow_blank=True)
    iban                = serializers.CharField(max_length=40, required=False, allow_blank=True)
    email               = serializers.EmailField(required=False, allow_blank=True)
    currency            = serializers.CharField(max_length=3, default='USD')
    set_as_primary      = serializers.BooleanField(default=False)

    def validate(self, attrs):
        account_type = attrs.get('account_type', '')
        if account_type == 'bank_transfer' and not attrs.get('account_number'):
            raise serializers.ValidationError({'account_number': 'Required for bank transfer.'})
        if account_type in ('paypal', 'wise') and not attrs.get('email'):
            raise serializers.ValidationError({'email': f'Required for {account_type}.'})
        return attrs


# ── Store ─────────────────────────────────────────────────────────────────────

class StoreContactMessageSerializer(serializers.Serializer):
    """StoreContactMessage model (publisher_management/publisher_store.py)"""
    pk           = serializers.IntegerField(read_only=True)
    sender_name  = serializers.CharField(max_length=200)
    sender_email = serializers.EmailField()
    subject      = serializers.CharField(max_length=300, required=False, allow_blank=True)
    message      = serializers.CharField(max_length=5000)
    sent_at      = serializers.DateTimeField(source='created_at', read_only=True)


class PublisherStoreSerializer(serializers.Serializer):
    """PublisherStore model (publisher_management/publisher_store.py)"""
    pk            = serializers.IntegerField(read_only=True)
    store_name    = serializers.CharField(max_length=200)
    description   = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    slug          = serializers.SlugField(max_length=100, read_only=True)
    logo_url      = serializers.URLField(required=False, allow_blank=True)
    banner_url    = serializers.URLField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    is_active     = serializers.BooleanField(read_only=True)
    store_url     = serializers.SerializerMethodField()
    created_at    = serializers.DateTimeField(read_only=True)

    def get_store_url(self, obj):
        if hasattr(obj, 'get_absolute_url'):
            return obj.get_absolute_url()
        return ''


# ── Subscription ──────────────────────────────────────────────────────────────

class SubscriptionPlanSerializer(serializers.Serializer):
    """SubscriptionPlan model (publisher_management/publisher_subscription.py)"""
    pk            = serializers.IntegerField(read_only=True)
    name          = serializers.CharField(max_length=100)
    tier          = serializers.CharField(max_length=20, required=False, allow_blank=True)
    monthly_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    annual_price  = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    max_sites     = serializers.IntegerField(read_only=True)
    max_apps      = serializers.IntegerField(read_only=True)
    max_ad_units  = serializers.IntegerField(read_only=True)
    features      = serializers.ListField(child=serializers.CharField(), read_only=True)
    is_active     = serializers.BooleanField(read_only=True)
    discount_pct  = serializers.SerializerMethodField()

    def get_discount_pct(self, obj):
        if hasattr(obj, 'get_discount_pct'):
            return obj.get_discount_pct()
        return 0


class PublisherSubscriptionSerializer(serializers.Serializer):
    """PublisherSubscription model (publisher_management/publisher_subscription.py)"""
    pk           = serializers.IntegerField(read_only=True)
    plan         = SubscriptionPlanSerializer(read_only=True)
    status       = serializers.CharField(read_only=True)
    started_at   = serializers.DateTimeField(source='created_at', read_only=True)
    expires_at   = serializers.DateTimeField(read_only=True, allow_null=True)
    can_add_site = serializers.SerializerMethodField()
    can_add_app  = serializers.SerializerMethodField()

    def get_can_add_site(self, obj):
        if hasattr(obj, 'can_add_site'):
            return obj.can_add_site()
        return True

    def get_can_add_app(self, obj):
        if hasattr(obj, 'can_add_app'):
            return obj.can_add_app()
        return True


class SubscriptionPaymentHistorySerializer(serializers.Serializer):
    """SubscriptionPaymentHistory model"""
    pk         = serializers.IntegerField(read_only=True)
    amount     = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    currency   = serializers.CharField(max_length=3, read_only=True)
    status     = serializers.CharField(read_only=True)
    method     = serializers.CharField(max_length=50, read_only=True, allow_blank=True)
    paid_at    = serializers.DateTimeField(source='created_at', read_only=True)


# ── Verification ──────────────────────────────────────────────────────────────

class PublisherVerificationSerializer(serializers.Serializer):
    """PublisherVerification model (publisher_management/publisher_verification.py)"""
    pk                = serializers.IntegerField(read_only=True)
    verification_type = serializers.CharField(max_length=50, read_only=True)
    target            = serializers.CharField(max_length=500, read_only=True)
    method            = serializers.CharField(max_length=50, read_only=True)
    status            = serializers.CharField(max_length=20, read_only=True)
    verified_at       = serializers.DateTimeField(read_only=True, allow_null=True)
    expires_at        = serializers.DateTimeField(read_only=True, allow_null=True)
    is_expired        = serializers.SerializerMethodField()

    def get_is_expired(self, obj):
        if hasattr(obj, 'is_expired'):
            return obj.is_expired()
        return False


# ── Business ──────────────────────────────────────────────────────────────────

class PublisherBusinessSerializer(serializers.Serializer):
    """PublisherBusiness model (publisher_management/publisher_business.py)"""
    pk                      = serializers.IntegerField(read_only=True)
    legal_name              = serializers.CharField(max_length=300)
    registration_number     = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tax_id                  = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_type           = serializers.CharField(max_length=50, required=False, allow_blank=True)
    incorporation_country   = serializers.CharField(max_length=3, required=False, allow_blank=True)
    incorporation_date      = serializers.DateField(required=False, allow_null=True)
    website                 = serializers.URLField(required=False, allow_blank=True)
    is_verified             = serializers.BooleanField(read_only=True)
    verified_at             = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at              = serializers.DateTimeField(read_only=True)


# ── Rating ────────────────────────────────────────────────────────────────────

class PublisherRatingConfigSerializer(serializers.Serializer):
    """PublisherRatingConfig model"""
    pk             = serializers.IntegerField(read_only=True)
    content_weight = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    traffic_weight = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    tech_weight    = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    is_active      = serializers.BooleanField(read_only=True)


class PublisherRatingRecordSerializer(serializers.Serializer):
    """PublisherRatingRecord model"""
    pk              = serializers.IntegerField(read_only=True)
    rating_date     = serializers.DateField(read_only=True)
    content_score   = serializers.IntegerField(read_only=True)
    traffic_score   = serializers.IntegerField(read_only=True)
    technical_score = serializers.IntegerField(read_only=True)
    overall_score   = serializers.IntegerField(read_only=True)
    notes           = serializers.CharField(read_only=True, allow_blank=True)


class PublisherAggregateRatingSerializer(serializers.Serializer):
    """PublisherAggregateRating model"""
    pk              = serializers.IntegerField(read_only=True)
    avg_score       = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    min_score       = serializers.IntegerField(read_only=True)
    max_score       = serializers.IntegerField(read_only=True)
    total_records   = serializers.IntegerField(read_only=True)
    period_start    = serializers.DateField(read_only=True)
    period_end      = serializers.DateField(read_only=True)


class PublisherRatingSerializer(serializers.Serializer):
    """PublisherRating model — combined view"""
    pk              = serializers.IntegerField(read_only=True)
    overall_score   = serializers.IntegerField(read_only=True)
    weighted_score  = serializers.SerializerMethodField()
    content_score   = serializers.IntegerField(read_only=True)
    traffic_score   = serializers.IntegerField(read_only=True)
    technical_score = serializers.IntegerField(read_only=True)
    tier            = serializers.CharField(read_only=True, allow_blank=True)
    updated_at      = serializers.DateTimeField(read_only=True)

    def get_weighted_score(self, obj):
        if hasattr(obj, 'weighted_score'):
            return obj.weighted_score()
        return getattr(obj, 'overall_score', 0)


# ── Commission & Referral ─────────────────────────────────────────────────────

class CommissionTierSerializer(serializers.Serializer):
    """CommissionTier model"""
    pk             = serializers.IntegerField(read_only=True)
    tier_name      = serializers.CharField(max_length=50, read_only=True)
    min_revenue    = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    max_revenue    = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)
    commission_pct = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_active      = serializers.BooleanField(read_only=True)


class PublisherCommissionSerializer(serializers.Serializer):
    """PublisherCommission model (publisher_management/publisher_commission.py)"""
    pk              = serializers.IntegerField(read_only=True)
    commission_type = serializers.CharField(max_length=50, read_only=True)
    amount          = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    gross_revenue   = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True, allow_null=True)
    commission_pct  = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    status          = serializers.CharField(max_length=20, read_only=True)
    period_start    = serializers.DateField(read_only=True, allow_null=True)
    period_end      = serializers.DateField(read_only=True, allow_null=True)
    paid_at         = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at      = serializers.DateTimeField(read_only=True)


class PublisherReferralSerializer(serializers.Serializer):
    """PublisherReferral model"""
    pk              = serializers.IntegerField(read_only=True)
    referred_id     = serializers.CharField(read_only=True)
    referred_name   = serializers.CharField(read_only=True, allow_blank=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    total_earned    = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    status          = serializers.CharField(max_length=20, read_only=True)
    joined_at       = serializers.DateTimeField(source='created_at', read_only=True)


# ── Blacklist ─────────────────────────────────────────────────────────────────

class PublisherBlacklistEntrySerializer(serializers.Serializer):
    """PublisherBlacklistEntry model"""
    pk           = serializers.IntegerField(read_only=True)
    reason       = serializers.CharField(max_length=500, read_only=True)
    is_active    = serializers.BooleanField(read_only=True)
    added_by     = serializers.CharField(max_length=100, read_only=True, allow_blank=True)
    expires_at   = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at   = serializers.DateTimeField(read_only=True)


class PublisherBlacklistSerializer(serializers.Serializer):
    """PublisherBlacklist model"""
    pk           = serializers.IntegerField(read_only=True)
    is_active    = serializers.BooleanField(read_only=True)
    reason       = serializers.CharField(max_length=500, read_only=True, allow_blank=True)
    expires_at   = serializers.DateTimeField(read_only=True, allow_null=True)
    blacklisted_at = serializers.DateTimeField(source='created_at', read_only=True)


# ── Leaderboard ───────────────────────────────────────────────────────────────

class PublisherLeaderboardSerializer(serializers.Serializer):
    """PublisherLeaderboard model"""
    pk           = serializers.IntegerField(read_only=True)
    rank         = serializers.IntegerField(read_only=True, allow_null=True)
    score        = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    tier         = serializers.CharField(max_length=20, read_only=True, allow_blank=True)
    revenue_rank = serializers.IntegerField(read_only=True, allow_null=True)
    quality_rank = serializers.IntegerField(read_only=True, allow_null=True)
    period       = serializers.CharField(max_length=20, read_only=True, allow_blank=True)
    updated_at   = serializers.DateTimeField(read_only=True)


# ── Performance Targets ───────────────────────────────────────────────────────

class PublisherPerformanceTargetSerializer(serializers.Serializer):
    """PublisherPerformanceTarget model"""
    pk           = serializers.IntegerField(read_only=True)
    metric       = serializers.CharField(max_length=50, read_only=True)
    target_value = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    period       = serializers.CharField(max_length=20, read_only=True, allow_blank=True)
    start_date   = serializers.DateField(read_only=True, allow_null=True)
    end_date     = serializers.DateField(read_only=True, allow_null=True)
    created_at   = serializers.DateTimeField(read_only=True)


class PublisherPerformanceSnapshotSerializer(serializers.Serializer):
    """PublisherPerformanceSnapshot model"""
    pk            = serializers.IntegerField(read_only=True)
    snapshot_date = serializers.DateField(read_only=True)
    revenue       = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    impressions   = serializers.IntegerField(read_only=True)
    ecpm          = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)
    fill_rate     = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    quality_score = serializers.IntegerField(read_only=True, allow_null=True)
    created_at    = serializers.DateTimeField(read_only=True)


# ══════════════════════════════════════════════════════════════════════════════
# FIX: Missing model serializers + floating model methods wired
# ══════════════════════════════════════════════════════════════════════════════
from .models import PublisherWebhook, WebhookDeliveryLog, BlockedIP, ABTest, ABTestVariant

# ══════════════════════════════════════════════════════════════════════════════
# 1. PublisherWebhookSerializer  (was missing — views_webhooks.py-তে used)
# ══════════════════════════════════════════════════════════════════════════════

class PublisherWebhookSerializer(serializers.ModelSerializer):
    """
    Publisher-configured webhook endpoint।
    Wires model methods: mark_failed(), mark_success(), is_healthy()
    GET/PATCH /webhooks/{id}/
    """
    is_healthy     = serializers.SerializerMethodField()
    delivery_count = serializers.SerializerMethodField()
    success_rate   = serializers.SerializerMethodField()

    class Meta:
        model  = PublisherWebhook
        fields = [
            'id', 'name', 'endpoint_url',
            'subscribed_events', 'subscribe_all',
            'status', 'is_active',
            'timeout_seconds', 'max_retries', 'retry_backoff',
            'total_deliveries', 'successful_deliveries', 'failed_deliveries',
            'last_triggered_at', 'last_success_at', 'last_failure_at',
            'consecutive_failures', 'failure_reason',
            'is_healthy', 'delivery_count', 'success_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_deliveries', 'successful_deliveries',
            'failed_deliveries', 'last_triggered_at',
            'last_success_at', 'last_failure_at',
            'consecutive_failures', 'failure_reason',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {'secret_key': {'write_only': True}}

    def get_is_healthy(self, obj) -> bool:
        """Wires floating model method: is_healthy()"""
        if hasattr(obj, 'is_healthy'):
            return obj.is_healthy()
        return obj.status == 'active' and obj.consecutive_failures == 0

    def get_delivery_count(self, obj) -> int:
        return getattr(obj, 'total_deliveries', 0)

    def get_success_rate(self, obj) -> float:
        total = getattr(obj, 'total_deliveries', 0)
        if not total:
            return 0.0
        return round(getattr(obj, 'successful_deliveries', 0) / total * 100, 2)


class WebhookCreateSerializer(serializers.ModelSerializer):
    """POST /webhooks/ — new webhook registration।"""

    class Meta:
        model  = PublisherWebhook
        fields = [
            'name', 'endpoint_url', 'secret_key',
            'subscribed_events', 'subscribe_all',
            'timeout_seconds', 'max_retries', 'retry_backoff',
        ]

    def validate_endpoint_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Endpoint URL must use HTTPS.')
        return value

    def validate_subscribed_events(self, value):
        valid_events = [
            'publisher.approved', 'publisher.suspended',
            'site.approved', 'site.rejected',
            'app.approved', 'app.rejected',
            'payment.processed', 'invoice.issued',
            'fraud.detected', 'ab_test.completed',
        ]
        if value and not isinstance(value, list):
            raise serializers.ValidationError('subscribed_events must be a list.')
        invalid = [e for e in (value or []) if e not in valid_events]
        if invalid:
            raise serializers.ValidationError(f'Unknown events: {invalid}')
        return value

    def create(self, validated_data):
        publisher = self.context['request'].user.publisher_profile
        validated_data['publisher'] = publisher
        return super().create(validated_data)


class WebhookActionSerializer(serializers.Serializer):
    """
    POST /webhooks/{id}/mark-failed/ or /mark-success/
    Wires floating model methods: mark_failed(), mark_success()
    """
    action = serializers.ChoiceField(choices=['mark_failed', 'mark_success'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class WebhookUpdateSerializer(serializers.ModelSerializer):
    """PATCH /webhooks/{id}/"""

    class Meta:
        model  = PublisherWebhook
        fields = [
            'name', 'endpoint_url', 'secret_key',
            'subscribed_events', 'subscribe_all',
            'timeout_seconds', 'max_retries', 'retry_backoff',
            'is_active',
        ]


# ══════════════════════════════════════════════════════════════════════════════
# 2. WebhookDeliveryLogSerializer  (was missing)
# ══════════════════════════════════════════════════════════════════════════════

class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """
    Webhook delivery attempt log।
    Wires:
      is_successful()          → is_successful field
      response_latency_display()→ latency_display field
    GET /webhooks/{id}/deliveries/
    """
    is_successful   = serializers.SerializerMethodField()
    latency_display = serializers.SerializerMethodField()
    webhook_name    = serializers.CharField(source='webhook.name', read_only=True)

    class Meta:
        model  = WebhookDeliveryLog
        fields = [
            'id', 'webhook', 'webhook_name',
            'event_type', 'payload',
            'attempt_number', 'status',
            'response_status_code', 'response_body',
            'delivery_duration_ms',
            'error_message', 'next_retry_at',
            'is_successful', 'latency_display',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_is_successful(self, obj) -> bool:
        """Wires floating model method: is_successful()"""
        if hasattr(obj, 'is_successful'):
            return obj.is_successful()
        return getattr(obj, 'status', '') == 'success'

    def get_latency_display(self, obj) -> str:
        """Wires floating model method: response_latency_display()"""
        if hasattr(obj, 'response_latency_display'):
            return obj.response_latency_display()
        ms = getattr(obj, 'delivery_duration_ms', None)
        if ms is None:
            return '—'
        if ms < 1000:
            return f'{ms}ms'
        return f'{round(ms / 1000, 2)}s'


class WebhookDeliveryLogListSerializer(serializers.ModelSerializer):
    """Minimal list view for delivery logs।"""
    is_successful = serializers.SerializerMethodField()

    class Meta:
        model  = WebhookDeliveryLog
        fields = [
            'id', 'event_type', 'attempt_number',
            'status', 'response_status_code',
            'delivery_duration_ms', 'is_successful',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_is_successful(self, obj) -> bool:
        if hasattr(obj, 'is_successful'):
            return obj.is_successful()
        return getattr(obj, 'status', '') == 'success'


# ══════════════════════════════════════════════════════════════════════════════
# 3. BlockedIPSerializer  (was missing — views_fraud.py-তে used)
# ══════════════════════════════════════════════════════════════════════════════

class BlockedIPSerializer(serializers.ModelSerializer):
    """
    Fraud-blocked IP address।
    Wires:
      is_active_block() → is_currently_blocked field
      block_type()      → block_type field
    GET /fraud/blocked-ips/
    """
    is_currently_blocked = serializers.SerializerMethodField()
    block_type           = serializers.SerializerMethodField()
    publisher_name       = serializers.CharField(
        source='publisher.display_name', read_only=True, default=''
    )

    class Meta:
        model  = BlockedIP
        fields = [
            'id', 'ip_address', 'reason',
            'fraud_score', 'is_auto_blocked',
            'expires_at', 'is_permanent', 'unblocked_at',
            'notes',
            'publisher', 'publisher_name',
            'is_currently_blocked', 'block_type',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'unblocked_at', 'created_at', 'updated_at']

    def get_is_currently_blocked(self, obj) -> bool:
        """Wires floating model method: is_active_block()"""
        if hasattr(obj, 'is_active_block'):
            return obj.is_active_block()
        from django.utils import timezone
        if getattr(obj, 'unblocked_at', None):
            return False
        expires = getattr(obj, 'expires_at', None)
        if expires and expires < timezone.now():
            return False
        return True

    def get_block_type(self, obj) -> str:
        """Wires floating model method: block_type()"""
        if hasattr(obj, 'block_type'):
            return obj.block_type()
        if getattr(obj, 'is_permanent', False):
            return 'permanent'
        if getattr(obj, 'expires_at', None):
            return 'temporary'
        return 'manual'


class BlockIPSerializer(serializers.Serializer):
    """POST /fraud/block-ip/ — input validation।"""
    ip_address  = serializers.IPAddressField()
    reason      = serializers.CharField(max_length=200)
    is_permanent= serializers.BooleanField(default=False)
    expires_at  = serializers.DateTimeField(required=False, allow_null=True)
    notes       = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('is_permanent') and not attrs.get('expires_at'):
            raise serializers.ValidationError(
                'Either is_permanent=True or expires_at must be provided.'
            )
        return attrs


class UnblockIPSerializer(serializers.Serializer):
    """POST /fraud/unblock-ip/ — input validation।"""
    ip_address = serializers.IPAddressField()
    reason     = serializers.CharField(max_length=200, required=False, allow_blank=True)


# ══════════════════════════════════════════════════════════════════════════════
# 4. ABTestSerializer  (was missing — views_abtest.py-তে used)
# ══════════════════════════════════════════════════════════════════════════════

class ABTestVariantSerializer(serializers.ModelSerializer):
    """Single A/B test variant।"""

    class Meta:
        model  = ABTestVariant
        fields = [
            'id', 'ab_test', 'name', 'is_control',
            'traffic_allocation',
            'ad_unit', 'placement_config', 'floor_price_override',
            'ad_format',
            'total_impressions', 'total_clicks', 'total_revenue',
            'ecpm', 'ctr', 'fill_rate',
            'statistical_significance', 'is_winner',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_impressions', 'total_clicks', 'total_revenue',
            'ecpm', 'ctr', 'fill_rate',
            'statistical_significance', 'is_winner',
            'created_at', 'updated_at',
        ]

    def validate_traffic_allocation(self, value):
        if not 0 < value <= 100:
            raise serializers.ValidationError('Traffic allocation must be between 1 and 100.')
        return value


class ABTestSerializer(serializers.ModelSerializer):
    """
    A/B test full detail।
    Wires floating model method: is_running()
    GET /ab-tests/{id}/
    """
    variants   = ABTestVariantSerializer(many=True, read_only=True)
    is_running = serializers.SerializerMethodField()
    winner     = serializers.SerializerMethodField()
    ad_unit_name = serializers.CharField(source='ad_unit.name', read_only=True, default='')

    class Meta:
        model  = ABTest
        fields = [
            'id', 'ad_unit', 'ad_unit_name',
            'name', 'description', 'test_type', 'status',
            'traffic_split_percentage',
            'start_date', 'end_date', 'duration_days',
            'min_sample_size', 'confidence_threshold',
            'primary_metric',
            'total_impressions', 'total_revenue',
            'winner_variant', 'winner_declared_at',
            'is_running', 'winner',
            'variants',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_impressions', 'total_revenue',
            'winner_variant', 'winner_declared_at',
            'created_at', 'updated_at',
        ]

    def get_is_running(self, obj) -> bool:
        """Wires floating model method: is_running()"""
        if hasattr(obj, 'is_running'):
            return obj.is_running()
        return getattr(obj, 'status', '') == 'running'

    def get_winner(self, obj):
        winner_id = getattr(obj, 'winner_variant_id', None)
        if not winner_id:
            return None
        return {'variant_id': winner_id, 'declared_at': str(obj.winner_declared_at)}


class ABTestListSerializer(serializers.ModelSerializer):
    """Minimal list view।"""
    is_running   = serializers.SerializerMethodField()
    variant_count = serializers.IntegerField(source='variants.count', read_only=True)

    class Meta:
        model  = ABTest
        fields = [
            'id', 'name', 'test_type', 'status',
            'start_date', 'end_date',
            'total_impressions', 'total_revenue',
            'is_running', 'variant_count',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_is_running(self, obj) -> bool:
        if hasattr(obj, 'is_running'):
            return obj.is_running()
        return getattr(obj, 'status', '') == 'running'


class ABTestCreateSerializer(serializers.ModelSerializer):
    """POST /ab-tests/ — create new A/B test।"""
    variants = ABTestVariantSerializer(many=True, required=False)

    class Meta:
        model  = ABTest
        fields = [
            'ad_unit', 'name', 'description', 'test_type',
            'traffic_split_percentage',
            'start_date', 'end_date', 'duration_days',
            'min_sample_size', 'confidence_threshold',
            'primary_metric',
            'variants',
        ]

    def validate_traffic_split_percentage(self, value):
        if not 0 < value <= 100:
            raise serializers.ValidationError('Traffic split must be 1–100.')
        return value

    def validate(self, attrs):
        start = attrs.get('start_date')
        end   = attrs.get('end_date')
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': 'end_date must be after start_date.'})
        return attrs

    def create(self, validated_data):
        variants_data = validated_data.pop('variants', [])
        test = ABTest.objects.create(**validated_data)
        for vdata in variants_data:
            ABTestVariant.objects.create(ab_test=test, **vdata)
        return test


class ABTestResultSerializer(serializers.Serializer):
    """GET /ab-tests/{id}/results/ — statistical results।"""
    test_id          = serializers.IntegerField()
    test_name        = serializers.CharField()
    status           = serializers.CharField()
    is_running       = serializers.BooleanField()
    total_impressions = serializers.IntegerField()
    total_revenue    = serializers.DecimalField(max_digits=14, decimal_places=4)
    confidence_threshold = serializers.FloatField()
    variants         = serializers.ListField(child=serializers.DictField())
    winner           = serializers.DictField(allow_null=True)
    statistical_significance = serializers.FloatField(allow_null=True)
    can_declare_winner = serializers.BooleanField()


# ══════════════════════════════════════════════════════════════════════════════
# 5. Patch serializers — wire remaining floating methods
# ══════════════════════════════════════════════════════════════════════════════

class PayoutThresholdWithFeeSerializer(serializers.Serializer):
    """
    Extends PayoutThresholdSerializer with floating method: effective_fee()
    Use this instead of PayoutThresholdSerializer when fee calculation is needed।
    """
    id                   = serializers.IntegerField(read_only=True)
    payment_method       = serializers.CharField()
    minimum_threshold    = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency    = serializers.CharField()
    processing_fee_flat  = serializers.DecimalField(max_digits=8, decimal_places=2)
    processing_fee_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    withholding_tax_percentage= serializers.DecimalField(max_digits=5, decimal_places=2)
    is_primary           = serializers.BooleanField()
    is_verified          = serializers.BooleanField()
    effective_fee        = serializers.SerializerMethodField()

    def get_effective_fee(self, obj) -> dict:
        """Wires floating model method: effective_fee()"""
        if hasattr(obj, 'effective_fee'):
            result = obj.effective_fee()
            return result if isinstance(result, dict) else {'fee': result}
        amount = getattr(obj, 'minimum_threshold', 0)
        flat   = float(getattr(obj, 'processing_fee_flat', 0))
        pct    = float(getattr(obj, 'processing_fee_percentage', 0))
        return {
            'flat_fee':       flat,
            'percentage_fee': round(float(amount) * pct / 100, 2),
            'total_fee':      round(flat + float(amount) * pct / 100, 2),
        }


class InvoiceWithNetPayableSerializer(serializers.Serializer):
    """
    Extends PublisherInvoiceDetailSerializer with floating method: calculate_net_payable()
    Use when exact net payable is needed after adjustments।
    """
    id                = serializers.IntegerField(read_only=True)
    invoice_number    = serializers.CharField(read_only=True)
    gross_revenue     = serializers.DecimalField(max_digits=14, decimal_places=4)
    publisher_share   = serializers.DecimalField(max_digits=14, decimal_places=4)
    tax_withheld      = serializers.DecimalField(max_digits=14, decimal_places=4, default=0)
    adjustments       = serializers.DecimalField(max_digits=14, decimal_places=4, default=0)
    net_payable       = serializers.DecimalField(max_digits=14, decimal_places=4)
    calculated_net    = serializers.SerializerMethodField()
    currency          = serializers.CharField()
    status            = serializers.CharField()

    def get_calculated_net(self, obj) -> dict:
        """Wires floating model method: calculate_net_payable()"""
        if hasattr(obj, 'calculate_net_payable'):
            result = obj.calculate_net_payable()
            return result if isinstance(result, dict) else {'net_payable': result}
        share      = float(getattr(obj, 'publisher_share', 0))
        tax        = float(getattr(obj, 'tax_withheld', 0))
        adjustment = float(getattr(obj, 'adjustments', 0))
        return {
            'gross_payable':  share,
            'tax_deduction':  tax,
            'adjustments':    adjustment,
            'net_payable':    round(share - tax + adjustment, 2),
        }


class SiteQualityMetricWithScoreSerializer(serializers.Serializer):
    """
    Extends SiteQualityMetricSerializer with floating method: calculate_overall_score()
    """
    id                    = serializers.IntegerField(read_only=True)
    site                  = serializers.IntegerField()
    date                  = serializers.DateField()
    viewability_rate      = serializers.DecimalField(max_digits=5, decimal_places=2)
    bot_traffic_percentage= serializers.DecimalField(max_digits=5, decimal_places=2)
    content_score         = serializers.IntegerField()
    page_speed_score      = serializers.IntegerField()
    overall_quality_score = serializers.IntegerField()
    recalculated_score    = serializers.SerializerMethodField()

    def get_recalculated_score(self, obj) -> dict:
        """Wires floating model method: calculate_overall_score()"""
        if hasattr(obj, 'calculate_overall_score'):
            score = obj.calculate_overall_score()
            return {'score': score, 'recalculated': True}
        viewability = float(getattr(obj, 'viewability_rate', 0))
        bot_pct     = float(getattr(obj, 'bot_traffic_percentage', 0))
        content     = float(getattr(obj, 'content_score', 0))
        speed       = float(getattr(obj, 'page_speed_score', 0))
        score       = round((viewability * 0.3) + ((100 - bot_pct) * 0.3) + (content * 0.2) + (speed * 0.2))
        return {'score': max(0, min(100, score)), 'recalculated': True}


class EarningWithRPISerializer(serializers.Serializer):
    """
    Extends PublisherEarningSerializer with floating method: revenue_per_impression()
    """
    id                     = serializers.IntegerField(read_only=True)
    date                   = serializers.DateField()
    impressions            = serializers.IntegerField()
    gross_revenue          = serializers.DecimalField(max_digits=14, decimal_places=6)
    publisher_revenue      = serializers.DecimalField(max_digits=14, decimal_places=6)
    ecpm                   = serializers.DecimalField(max_digits=10, decimal_places=4)
    revenue_per_impression = serializers.SerializerMethodField()

    def get_revenue_per_impression(self, obj):
        """Wires floating model method: revenue_per_impression()"""
        if hasattr(obj, 'revenue_per_impression'):
            return str(obj.revenue_per_impression())
        imps = getattr(obj, 'impressions', 0)
        rev  = float(getattr(obj, 'publisher_revenue', 0))
        if not imps:
            return '0.000000'
        return f'{rev / imps:.6f}'


class PublisherIsHealthySerializer(serializers.Serializer):
    """
    Adds floating method: is_healthy() to Publisher context।
    Used in PublisherDetailSerializer.
    """
    publisher_id  = serializers.CharField()
    display_name  = serializers.CharField()
    status        = serializers.CharField()
    is_healthy    = serializers.SerializerMethodField()

    def get_is_healthy(self, obj) -> bool:
        """Wires floating model method: is_healthy()"""
        if hasattr(obj, 'is_healthy'):
            return obj.is_healthy()
        return getattr(obj, 'status', '') == 'active'


class MediationGroupRecalcSerializer(serializers.Serializer):
    """
    POST /mediation-groups/{id}/recalculate/
    Wires floating model method: recalculate_metrics()
    """
    force = serializers.BooleanField(default=False)
    confirm = serializers.BooleanField(
        default=True,
        help_text='True হলে recalculate_metrics() call হবে।'
    )


# ──────────────────────────────────────────────────────────────────────────────
# APP MANAGEMENT SERIALIZERS
# (app_management/ subfolder — AppApprovalRecord, AppSDKConfig, AppDownloadSnapshot)
# ──────────────────────────────────────────────────────────────────────────────

class AppApprovalRecordSerializer(serializers.ModelSerializer):
    """
    App review/approval/rejection history record।

    Used by:
      views_app_management_full.py → approval_history() action
      GET /app-management/approval-history/?app_id=<id>

    Fields wired from AppApprovalRecord model
    (app_management/app_approval.py):
      app, action, reason, decided_by, notes,
      rejection_feedback, reviewed_at, is_resubmission,
      previous_action, metadata, created_at
    """

    app_name = serializers.SerializerMethodField()
    app_id   = serializers.SerializerMethodField()

    class Meta:
        from .app_management.app_approval import AppApprovalRecord
        model  = AppApprovalRecord
        fields = [
            'id',
            'app',
            'app_id',
            'app_name',
            'action',
            'reason',
            'decided_by',
            'notes',
            'rejection_feedback',
            'reviewed_at',
            'is_resubmission',
            'previous_action',
            'metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'app_id',
            'app_name',
            'created_at',
            'updated_at',
        ]

    def get_app_id(self, obj) -> str:
        """App-এর slug/app_id field।"""
        app = getattr(obj, 'app', None)
        if app is None:
            return ''
        return getattr(app, 'app_id', str(app.pk))

    def get_app_name(self, obj) -> str:
        """App-এর display name।"""
        app = getattr(obj, 'app', None)
        if app is None:
            return ''
        return getattr(app, 'name', '')

    def validate_action(self, value: str) -> str:
        """action field-এর value valid choices-এ আছে কিনা check করে।"""
        from .app_management.app_approval import AppApprovalRecord
        valid = [c[0] for c in AppApprovalRecord.ACTION_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid action "{value}". Valid choices: {valid}'
            )
        return value


class AppSDKConfigSerializer(serializers.ModelSerializer):
    """
    Per-app SDK integration configuration।

    Used by:
      views_app_management_full.py → sdk_config() action
      GET /app-management/sdk-config/?app_id=<id>

    Fields wired from AppSDKConfig model
    (app_management/app_sdk.py):
      app, sdk_version, sdk_platform, status,
      is_sdk_integrated, sdk_key, sdk_secret (write-only),
      last_sdk_ping, sdk_config_json, initialization_options,
      allowed_ad_formats, mediation_config, test_mode,
      auto_init, consent_required, coppa_compliant,
      gdpr_compliant, integration_notes, error_message,
      created_at, updated_at
    """

    integration_status = serializers.SerializerMethodField()
    has_error          = serializers.SerializerMethodField()

    class Meta:
        from .app_management.app_sdk import AppSDKConfig
        model  = AppSDKConfig
        fields = [
            'id',
            'app',
            'sdk_version',
            'sdk_platform',
            'status',
            'is_sdk_integrated',
            'sdk_key',
            'sdk_secret',
            'last_sdk_ping',
            'sdk_config_json',
            'initialization_options',
            'allowed_ad_formats',
            'mediation_config',
            'test_mode',
            'auto_init',
            'consent_required',
            'coppa_compliant',
            'gdpr_compliant',
            'integration_notes',
            'error_message',
            'integration_status',
            'has_error',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'integration_status',
            'has_error',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            # sdk_secret is sensitive — never expose in GET responses
            'sdk_secret': {'write_only': True},
        }

    def get_integration_status(self, obj) -> str:
        """Human-readable integration state for the front-end."""
        if not getattr(obj, 'is_sdk_integrated', False):
            return 'not_integrated'
        status = getattr(obj, 'status', 'pending')
        return status

    def get_has_error(self, obj) -> bool:
        """SDK integration-এ error আছে কিনা।"""
        from .app_management.app_sdk import AppSDKConfig
        return getattr(obj, 'status', '') == AppSDKConfig.STATUS_ERROR


class AppDownloadSnapshotSerializer(serializers.ModelSerializer):
    """
    Daily app download count snapshot।

    Used by:
      views_app_management_full.py → download_trend() action
      GET /app-management/download-trend/?app_id=<id>&days=30

    Key fields from AppDownloadSnapshot model
    (app_management/app_downloads.py):
      app, snapshot_date (renamed from `date` in v2 — db_column='date'),
      new_downloads, cumulative_downloads, new_installs,
      uninstalls, net_installs, active_installs,
      country_breakdown, platform, source

    Note: snapshot_date is explicitly declared as DateField to ensure
    serialization uses the Python attribute name (not the legacy db_column 'date').
    """

    # Explicit declaration ensures the Python name `snapshot_date` is used
    # (the DB column is still `date` — migration 0008 SeparateDatabaseAndState)
    snapshot_date = serializers.DateField()

    # Computed aliases that match AppDownloadSnapshot @property helpers
    total_downloads    = serializers.SerializerMethodField()
    daily_active_users = serializers.SerializerMethodField()

    class Meta:
        from .app_management.app_downloads import AppDownloadSnapshot
        model  = AppDownloadSnapshot
        fields = [
            'id',
            'app',
            'snapshot_date',
            'new_downloads',
            'cumulative_downloads',
            'new_installs',
            'uninstalls',
            'net_installs',
            'active_installs',
            'country_breakdown',
            'platform',
            'source',
            'total_downloads',
            'daily_active_users',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'total_downloads',
            'daily_active_users',
            'created_at',
            'updated_at',
        ]

    def get_total_downloads(self, obj) -> int:
        """
        Wires AppDownloadSnapshot.total_downloads property
        (alias for cumulative_downloads, added in v2).
        """
        if hasattr(obj, 'total_downloads') and callable(
            getattr(type(obj), 'total_downloads', None)
        ):
            # It's a @property — access via instance, not call
            return obj.total_downloads
        return getattr(obj, 'cumulative_downloads', 0)

    def get_daily_active_users(self, obj) -> int:
        """
        Wires AppDownloadSnapshot.daily_active_users property
        (alias for active_installs, added in v2).
        """
        if hasattr(obj, 'daily_active_users') and callable(
            getattr(type(obj), 'daily_active_users', None)
        ):
            return obj.daily_active_users
        return getattr(obj, 'active_installs', 0)

    def validate_snapshot_date(self, value):
        """Future dates are not allowed for historical snapshots।"""
        from django.utils import timezone
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError(
                'snapshot_date cannot be in the future.'
            )
        return value
