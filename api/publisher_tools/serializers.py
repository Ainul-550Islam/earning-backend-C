# api/publisher_tools/serializers.py
"""
Publisher Tools — DRF Serializers।
সব Model-এর জন্য Create, Update, List, Detail serializer।
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
    active_sites    = serializers.IntegerField(source='active_sites_count', read_only=True)
    active_apps     = serializers.IntegerField(source='active_apps_count', read_only=True)
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    api_key_masked  = serializers.SerializerMethodField()

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
    publisher_id     = serializers.CharField()
    display_name     = serializers.CharField()
    total_revenue    = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_paid_out   = serializers.DecimalField(max_digits=14, decimal_places=4)
    pending_balance  = serializers.DecimalField(max_digits=14, decimal_places=4)
    available_balance= serializers.DecimalField(max_digits=14, decimal_places=4)
    active_sites     = serializers.IntegerField()
    active_apps      = serializers.IntegerField()
    total_ad_units   = serializers.IntegerField()
    period_revenue   = serializers.DecimalField(max_digits=14, decimal_places=4)
    period_impressions= serializers.IntegerField()
    period_clicks    = serializers.IntegerField()
    period_ecpm      = serializers.DecimalField(max_digits=10, decimal_places=4)


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
        # Domain already taken?
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
        """Verification code/snippet return করে"""
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

        # Check publisher owns site/app
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
    network_name = serializers.CharField(source='network.name', read_only=True)
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
    net_revenue    = serializers.DecimalField(
        source='net_publisher_revenue', max_digits=14, decimal_places=6, read_only=True
    )
    revenue_fmt    = serializers.SerializerMethodField()
    ad_unit_name   = serializers.CharField(source='ad_unit.name', read_only=True, default=None)
    network_name   = serializers.CharField(source='network.name', read_only=True, default=None)
    site_domain    = serializers.CharField(source='site.domain', read_only=True, default=None)
    app_package    = serializers.CharField(source='app.package_name', read_only=True, default=None)

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
    period_start      = serializers.DateField()
    period_end        = serializers.DateField()
    total_gross       = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_publisher   = serializers.DecimalField(max_digits=14, decimal_places=4)
    total_impressions = serializers.IntegerField()
    total_clicks      = serializers.IntegerField()
    total_ad_requests = serializers.IntegerField()
    avg_ecpm          = serializers.DecimalField(max_digits=10, decimal_places=4)
    avg_fill_rate     = serializers.DecimalField(max_digits=5, decimal_places=2)
    avg_ctr           = serializers.DecimalField(max_digits=6, decimal_places=4)
    top_earning_unit  = serializers.CharField(allow_null=True)
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
        extra_kwargs = {
            'payment_details': {'write_only': True},
        }

    def get_payment_details_masked(self, obj):
        """Payment details mask করে show করে"""
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
    reason = serializers.CharField(min_length=20, max_length=2000, help_text='Dispute reason (min 20 chars)')
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
    notes = serializers.CharField(required=False, allow_blank=True)
    deduction_amount = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False
    )


class MarkFalsePositiveSerializer(serializers.Serializer):
    is_false_positive = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class SiteQualityMetricSerializer(serializers.ModelSerializer):
    is_high_quality  = serializers.BooleanField(read_only=True)
    needs_attention  = serializers.BooleanField(read_only=True)
    site_domain      = serializers.CharField(source='site.domain', read_only=True)

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
    """Quality score trend data"""
    date                     = serializers.DateField()
    overall_quality_score    = serializers.IntegerField()
    viewability_rate         = serializers.DecimalField(max_digits=5, decimal_places=2)
    invalid_traffic_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    content_quality          = serializers.CharField()


# ──────────────────────────────────────────────────────────────────────────────
# DASHBOARD / REPORT SERIALIZERS
# ──────────────────────────────────────────────────────────────────────────────

class DateRangeSerializer(serializers.Serializer):
    """Date range input serializer"""
    start_date = serializers.DateField()
    end_date   = serializers.DateField()
    granularity = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )

    def validate(self, attrs):
        from .validators import validate_date_range
        validate_date_range(attrs['start_date'], attrs['end_date'])
        return attrs


class ReportFilterSerializer(serializers.Serializer):
    """Report filter parameters"""
    start_date   = serializers.DateField()
    end_date     = serializers.DateField()
    granularity  = serializers.ChoiceField(choices=['hourly', 'daily', 'weekly', 'monthly'], default='daily')
    site_ids     = serializers.ListField(child=serializers.UUIDField(), required=False)
    app_ids      = serializers.ListField(child=serializers.UUIDField(), required=False)
    ad_unit_ids  = serializers.ListField(child=serializers.UUIDField(), required=False)
    countries    = serializers.ListField(child=serializers.CharField(), required=False)
    earning_types= serializers.ListField(child=serializers.CharField(), required=False)
    group_by     = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        from .validators import validate_date_range
        validate_date_range(attrs['start_date'], attrs['end_date'])
        return attrs
