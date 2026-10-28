"""
SmartLink — Missing Model Serializers
=======================================
Adds serializers for all 12 models that had none:
  RedirectRule, PublisherSubID, BrowserTargeting,
  UniqueClick, ClickFraudFlag, SmartLinkDomain,
  SmartLinkTagging, OfferPerformanceStat,
  GeoPerformanceStat, DevicePerformanceStat, OfferCapTracker, OfferBlacklist,
  SmartLinkRotation, SmartLinkFallback, SmartLinkVersion.
"""
from rest_framework import serializers

from ..models.redirect import RedirectRule
from ..models.publisher import PublisherSubID
from ..models.targeting import BrowserTargeting
from ..models.click import UniqueClick, ClickFraudFlag, ClickHeatmap
from ..models.smartlink import (
    SmartLinkDomain, SmartLinkTagging,
    SmartLinkRotation, SmartLinkFallback, SmartLinkVersion,
)
from ..models.analytics import (
    OfferPerformanceStat, GeoPerformanceStat,
    DevicePerformanceStat, SmartLinkDailyStat,
)
from ..models.offer_pool import OfferCapTracker, OfferBlacklist


# ── RedirectRule ──────────────────────────────────────────────────────────────

class RedirectRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedirectRule
        fields = [
            'id', 'smartlink', 'name', 'description',
            'condition_type', 'condition_value',
            'target_url', 'priority', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── PublisherSubID ────────────────────────────────────────────────────────────

class PublisherSubIDSerializer(serializers.ModelSerializer):
    """
    Sub-ID parameter definitions — what sub1/sub2/sub3 mean for this publisher.
    Example: sub1 = campaign_id, sub2 = adset_id, sub3 = creative_id
    """
    class Meta:
        model = PublisherSubID
        fields = [
            'id', 'publisher', 'smartlink',
            'sub1_label', 'sub2_label', 'sub3_label',
            'sub4_label', 'sub5_label',
            'sub1_description', 'sub2_description',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'publisher', 'created_at', 'updated_at']


# ── BrowserTargeting ──────────────────────────────────────────────────────────

class BrowserTargetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrowserTargeting
        fields = [
            'id', 'smartlink', 'browsers',
            'exclude_browsers', 'min_browser_version',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── UniqueClick ───────────────────────────────────────────────────────────────

class UniqueClickSerializer(serializers.ModelSerializer):
    """Read-only deduplication record."""
    class Meta:
        model = UniqueClick
        fields = [
            'id', 'fingerprint', 'smartlink', 'offer',
            'ip', 'date', 'first_click', 'created_at',
        ]
        read_only_fields = fields


# ── ClickFraudFlag ────────────────────────────────────────────────────────────

class ClickFraudFlagSerializer(serializers.ModelSerializer):
    """Read-only fraud detection result per click."""
    class Meta:
        model = ClickFraudFlag
        fields = [
            'id', 'click', 'score', 'signals',
            'action', 'reason', 'detected_at',
        ]
        read_only_fields = fields


class ClickFraudFlagListSerializer(serializers.ModelSerializer):
    """Compact fraud flag for list views."""
    class Meta:
        model = ClickFraudFlag
        fields = ['id', 'click', 'score', 'action', 'detected_at']
        read_only_fields = fields


# ── SmartLinkDomain ───────────────────────────────────────────────────────────

class SmartLinkDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkDomain
        fields = [
            'id', 'smartlink', 'domain',
            'is_primary', 'is_verified', 'ssl_status',
            'verified_at', 'created_at',
        ]
        read_only_fields = ['id', 'is_verified', 'ssl_status', 'verified_at', 'created_at']


# ── SmartLinkTagging ──────────────────────────────────────────────────────────

class SmartLinkTaggingSerializer(serializers.ModelSerializer):
    tag_name = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkTagging
        fields = ['id', 'smartlink', 'tag', 'tag_name', 'created_at']
        read_only_fields = ['id', 'tag_name', 'created_at']

    def get_tag_name(self, obj):
        return obj.tag.name if obj.tag else ''


# ── OfferPerformanceStat ──────────────────────────────────────────────────────

class OfferPerformanceStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferPerformanceStat
        fields = [
            'id', 'smartlink', 'offer_id', 'date',
            'clicks', 'unique_clicks', 'conversions',
            'revenue', 'epc', 'cvr', 'created_at',
        ]
        read_only_fields = fields


# ── GeoPerformanceStat ────────────────────────────────────────────────────────

class GeoPerformanceStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoPerformanceStat
        fields = [
            'id', 'smartlink', 'country', 'date',
            'clicks', 'unique_clicks', 'conversions',
            'revenue', 'epc', 'cvr', 'created_at',
        ]
        read_only_fields = fields


# ── DevicePerformanceStat ─────────────────────────────────────────────────────

class DevicePerformanceStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevicePerformanceStat
        fields = [
            'id', 'smartlink', 'device_type', 'date',
            'clicks', 'unique_clicks', 'conversions',
            'revenue', 'epc', 'cvr', 'created_at',
        ]
        read_only_fields = fields


# ── OfferCapTracker ───────────────────────────────────────────────────────────

class OfferCapTrackerSerializer(serializers.ModelSerializer):
    pool_entry_offer = serializers.SerializerMethodField()
    utilization_pct  = serializers.SerializerMethodField()

    class Meta:
        model = OfferCapTracker
        fields = [
            'id', 'pool_entry', 'pool_entry_offer',
            'period', 'period_date',
            'clicks_count', 'cap_limit', 'is_capped',
            'utilization_pct', 'last_updated',
        ]
        read_only_fields = fields

    def get_pool_entry_offer(self, obj):
        return str(obj.pool_entry.offer_id) if obj.pool_entry else ''

    def get_utilization_pct(self, obj):
        if not obj.cap_limit:
            return 0.0
        return round(obj.clicks_count / obj.cap_limit * 100, 2)


# ── OfferBlacklist ────────────────────────────────────────────────────────────

class OfferBlacklistSerializer(serializers.ModelSerializer):
    """Previously had no serializer — using inline in the viewset."""
    added_by_username = serializers.SerializerMethodField()

    class Meta:
        model = OfferBlacklist
        fields = [
            'id', 'smartlink', 'offer',
            'reason', 'added_by', 'added_by_username',
            'created_at',
        ]
        read_only_fields = ['id', 'added_by', 'added_by_username', 'created_at']

    def get_added_by_username(self, obj):
        return obj.added_by.username if obj.added_by else ''


# ── SmartLinkRotation ─────────────────────────────────────────────────────────

class SmartLinkRotationSerializer(serializers.ModelSerializer):
    """Serializer for SmartLinkRotation — was floating, now wired."""
    class Meta:
        model = SmartLinkRotation
        fields = [
            'id', 'smartlink', 'method', 'auto_optimize_epc',
            'optimization_interval_minutes', 'epc_min_clicks',
            'last_optimized_at', 'updated_at',
        ]
        read_only_fields = ['id', 'smartlink', 'last_optimized_at', 'updated_at']


# ── SmartLinkFallback ─────────────────────────────────────────────────────────

class SmartLinkFallbackSerializer(serializers.ModelSerializer):
    """Serializer for SmartLinkFallback — was floating, now wired."""
    class Meta:
        model = SmartLinkFallback
        fields = [
            'id', 'smartlink', 'url', 'reason', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'smartlink', 'created_at', 'updated_at']


# ── SmartLinkVersion ──────────────────────────────────────────────────────────

class SmartLinkVersionSerializer(serializers.ModelSerializer):
    """Serializer for SmartLinkVersion A/B variant — was floating, now wired."""
    conversion_rate = serializers.SerializerMethodField()
    epc             = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkVersion
        fields = [
            'id', 'smartlink', 'name', 'description', 'traffic_split',
            'is_control', 'is_active', 'is_winner',
            'clicks', 'conversions', 'revenue',
            'conversion_rate', 'epc',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'smartlink', 'clicks', 'conversions', 'revenue',
            'is_winner', 'created_at', 'updated_at',
        ]

    def get_conversion_rate(self, obj):
        if not obj.clicks:
            return 0.0
        return round(obj.conversions / obj.clicks * 100, 4)

    def get_epc(self, obj):
        if not obj.clicks:
            return 0.0
        return round(float(obj.revenue) / obj.clicks, 6)
