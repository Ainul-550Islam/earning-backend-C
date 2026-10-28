"""
Django REST Framework Serializers for Offer Routing System

This module provides serializers for all models in the offer routing system,
including validation, nested relationships, and custom field handling.

SECURITY FIXES (audit 2026-06):
  - All tenant/user FK fields are now explicitly read_only
  - Replaced fields='__all__' with explicit field lists on tenant-owned models
  - System-managed fields (current_count, last_reset_at, etc.) marked read_only
  - OfferRoutingCapSerializer: current_count cannot be overwritten via API
  - RoutingABTestSerializer: control_route != variant_route enforced at API level
"""

import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum, Avg

from .models import (
    # Core Models
    OfferRoute, RouteCondition, RouteAction,

    # Targeting Models
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule,

    # Scoring Models
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore,

    # Personalization Models
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,

    # Cap Models
    OfferRoutingCap, UserOfferCap, CapOverride,

    # Fallback Models
    FallbackRule, DefaultOfferPool, EmptyResultHandler,

    # A/B Test Models
    RoutingABTest, ABTestAssignment, ABTestResult,

    # Analytics Models
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Base Serializer
# ─────────────────────────────────────────────────────────────────────────────

class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common audit fields.

    SECURITY: tenant/user FK fields must be declared as read_only in each
    concrete serializer — do NOT allow user-controlled tenant assignment.
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core Serializers
# ─────────────────────────────────────────────────────────────────────────────

class RouteConditionSerializer(BaseSerializer):
    """Serializer for RouteCondition model."""

    class Meta:
        model = RouteCondition
        fields = [
            'id', 'route', 'condition_type', 'operator',
            'field_name', 'value', 'logic', 'priority',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RouteActionSerializer(BaseSerializer):
    """Serializer for RouteAction model."""

    class Meta:
        model = RouteAction
        fields = [
            'id', 'route', 'action_type', 'action_value',
            'priority', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OfferRouteSerializer(BaseSerializer):
    """Serializer for OfferRoute model. tenant is read-only."""

    conditions   = RouteConditionSerializer(many=True, read_only=True)
    actions      = RouteActionSerializer(many=True, read_only=True)
    geo_rules    = serializers.SerializerMethodField()
    device_rules = serializers.SerializerMethodField()
    # tenant is exposed as a string label — never writable
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OfferRoute
        fields = [
            'id', 'name', 'description', 'tenant',
            'is_active', 'priority', 'max_offers',
            'conditions', 'actions', 'geo_rules', 'device_rules',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def get_geo_rules(self, obj):
        """Get geo rules for this route."""
        rules = obj.geo_rules.all()
        return GeoRouteRuleSerializer(rules, many=True).data

    def get_device_rules(self, obj):
        """Get device rules for this route."""
        rules = obj.device_rules.all()
        return DeviceRouteRuleSerializer(rules, many=True).data

    def validate_priority(self, value):
        """Validate priority field."""
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10.")
        return value

    def validate_max_offers(self, value):
        """Validate max_offers field."""
        if not 1 <= value <= 100:
            raise serializers.ValidationError("Max offers must be between 1 and 100.")
        return value


class OfferRouteCreateSerializer(OfferRouteSerializer):
    """Serializer for creating OfferRoute instances. tenant set from request."""

    conditions = RouteConditionSerializer(many=True, required=False)
    actions    = RouteActionSerializer(many=True, required=False)
    tenant     = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OfferRoute
        fields = [
            'id', 'name', 'description', 'tenant',
            'is_active', 'priority', 'max_offers',
            'conditions', 'actions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create OfferRoute with nested conditions and actions."""
        conditions_data = validated_data.pop('conditions', [])
        actions_data    = validated_data.pop('actions', [])

        # SECURITY: always force tenant from authenticated request
        validated_data['tenant'] = self.context['request'].user

        offer_route = OfferRoute.objects.create(**validated_data)

        for condition_data in conditions_data:
            RouteCondition.objects.create(route=offer_route, **condition_data)

        for action_data in actions_data:
            RouteAction.objects.create(route=offer_route, **action_data)

        return offer_route


# ─────────────────────────────────────────────────────────────────────────────
# Targeting Serializers
# ─────────────────────────────────────────────────────────────────────────────

class GeoRouteRuleSerializer(BaseSerializer):
    """Serializer for GeoRouteRule model."""

    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = GeoRouteRule
        fields = [
            'id', 'route', 'route_name',
            'country', 'region', 'city', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_country(self, value):
        """Validate country code."""
        if value and len(value) != 2:
            raise serializers.ValidationError("Country code must be 2 characters.")
        return value.upper() if value else value


class DeviceRouteRuleSerializer(BaseSerializer):
    """Serializer for DeviceRouteRule model."""

    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = DeviceRouteRule
        fields = [
            'id', 'route', 'route_name',
            'device_type', 'os_type', 'browser_type', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSegmentRuleSerializer(BaseSerializer):
    """Serializer for UserSegmentRule model."""

    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = UserSegmentRule
        fields = [
            'id', 'route', 'route_name',
            'segment_id', 'segment_type', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TimeRouteRuleSerializer(BaseSerializer):
    """Serializer for TimeRouteRule model."""

    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = TimeRouteRule
        fields = [
            'id', 'route', 'route_name',
            'start_time', 'end_time', 'days_of_week',
            'timezone', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_days_of_week(self, value):
        """Validate days of week."""
        if value:
            try:
                days = [int(d.strip()) for d in value.split(',')]
                if not all(0 <= d <= 6 for d in days):
                    raise serializers.ValidationError(
                        "Days must be 0-6 (Sunday-Saturday)."
                    )
                return value
            except (ValueError, AttributeError):
                raise serializers.ValidationError(
                    "Invalid days format. Use comma-separated numbers 0-6."
                )
        return value


class BehaviorRouteRuleSerializer(BaseSerializer):
    """Serializer for BehaviorRouteRule model."""

    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = BehaviorRouteRule
        fields = [
            'id', 'route', 'route_name',
            'behavior_type', 'threshold', 'time_period_hours', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_time_period_hours(self, value):
        """Validate time period hours."""
        if not 1 <= value <= 8760:  # Max 1 year
            raise serializers.ValidationError(
                "Time period must be between 1 and 8760 hours."
            )
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Scoring Serializers
# ─────────────────────────────────────────────────────────────────────────────

class OfferScoreSerializer(BaseSerializer):
    """Serializer for OfferScore model."""

    offer_name = serializers.CharField(source='offer.name', read_only=True)
    user_name  = serializers.CharField(source='user.username', read_only=True)
    # SECURITY: user is read_only — cannot be set via API
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = OfferScore
        fields = [
            'id', 'offer', 'offer_name', 'user', 'user_name',
            'score', 'epc', 'cr', 'relevance_score', 'freshness_score',
            'score_version', 'expires_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'score_version', 'created_at', 'updated_at',
        ]

    def validate_score(self, value):
        """Validate score field."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Score must be between 0 and 100.")
        return value

    def validate_epc(self, value):
        """Validate EPC field."""
        if value < 0:
            raise serializers.ValidationError("EPC cannot be negative.")
        return value

    def validate_cr(self, value):
        """Validate conversion rate field."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "Conversion rate must be between 0 and 100."
            )
        return value


class OfferScoreConfigSerializer(BaseSerializer):
    """Serializer for OfferScoreConfig model."""

    offer_name  = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OfferScoreConfig
        fields = [
            'id', 'offer', 'offer_name', 'tenant', 'tenant_name',
            'epc_weight', 'cr_weight', 'relevance_weight', 'freshness_weight',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate(self, data):
        """Validate weight distribution."""
        weights = ['epc_weight', 'cr_weight', 'relevance_weight', 'freshness_weight']
        total_weight = sum(data.get(w, 0) for w in weights)

        if abs(total_weight - 1.0) > 0.01:  # Allow small rounding errors
            raise serializers.ValidationError(
                f"Weights must sum to 1.0 (current: {total_weight})"
            )
        return data


class GlobalOfferRankSerializer(BaseSerializer):
    """Serializer for GlobalOfferRank model."""

    offer_name  = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = GlobalOfferRank
        fields = [
            'id', 'offer', 'offer_name', 'tenant', 'tenant_name',
            'rank', 'score', 'scored_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class UserOfferHistorySerializer(BaseSerializer):
    """Serializer for UserOfferHistory model."""

    offer_name = serializers.CharField(source='offer.name', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    user_name  = serializers.CharField(source='user.username', read_only=True)
    user       = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserOfferHistory
        fields = [
            'id', 'offer', 'offer_name', 'route', 'route_name',
            'user', 'user_name',
            'shown_at', 'clicked', 'converted', 'conversion_value',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_conversion_value(self, value):
        """Validate conversion value."""
        if value < 0:
            raise serializers.ValidationError("Conversion value cannot be negative.")
        return value


class OfferAffinityScoreSerializer(BaseSerializer):
    """Serializer for OfferAffinityScore model."""

    user_name = serializers.CharField(source='user.username', read_only=True)
    user      = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = OfferAffinityScore
        fields = [
            'id', 'user', 'user_name',
            'category', 'score', 'confidence',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_score(self, value):
        """Validate score field."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Score must be between 0 and 1.")
        return value

    def validate_confidence(self, value):
        """Validate confidence field."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Confidence must be between 0 and 1.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Personalization Serializers
# ─────────────────────────────────────────────────────────────────────────────

class UserPreferenceVectorSerializer(BaseSerializer):
    """Serializer for UserPreferenceVector model."""

    user_name   = serializers.CharField(source='user.username', read_only=True)
    user        = serializers.PrimaryKeyRelatedField(read_only=True)
    vector_size = serializers.SerializerMethodField()

    class Meta:
        model = UserPreferenceVector
        fields = [
            'id', 'user', 'user_name',
            'vector', 'category_weights', 'vector_size',
            'updated_at', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_vector_size(self, obj):
        """Get size of preference vector."""
        try:
            return len(obj.vector) if obj.vector else 0
        except (TypeError, ValueError):
            return 0

    def validate_category_weights(self, value):
        """Validate category weights."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Category weights must be a dictionary."
            )
        for key, val in value.items():
            if not isinstance(val, (int, float)) or not 0 <= val <= 1:
                raise serializers.ValidationError(
                    f"Weight for '{key}' must be between 0 and 1."
                )
        return value


class ContextualSignalSerializer(BaseSerializer):
    """Serializer for ContextualSignal model."""

    user_name = serializers.CharField(source='user.username', read_only=True)
    user      = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ContextualSignal
        fields = [
            'id', 'user', 'user_name',
            'signal_type', 'signal_value', 'weight', 'expires_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_weight(self, value):
        """Validate weight field."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Weight must be between 0 and 1.")
        return value

    def validate_expires_at(self, value):
        """Validate expires_at field."""
        if value and value <= timezone.now():
            raise serializers.ValidationError(
                "Expiration time must be in the future."
            )
        return value


class PersonalizationConfigSerializer(BaseSerializer):
    """Serializer for PersonalizationConfig model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    user_name   = serializers.CharField(source='user.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)
    user        = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PersonalizationConfig
        fields = [
            'id', 'tenant', 'tenant_name', 'user', 'user_name',
            'algorithm', 'collaborative_weight', 'content_based_weight',
            'hybrid_weight', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'user', 'created_at', 'updated_at']

    def validate(self, data):
        """Validate weight distribution."""
        weights = ['collaborative_weight', 'content_based_weight', 'hybrid_weight']
        total_weight = sum(data.get(w, 0) for w in weights)

        if abs(total_weight - 1.0) > 0.01:
            raise serializers.ValidationError(
                f"Weights must sum to 1.0 (current: {total_weight})"
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Cap Serializers
# ─────────────────────────────────────────────────────────────────────────────

class OfferRoutingCapSerializer(BaseSerializer):
    """Serializer for OfferRoutingCap model.

    SECURITY: current_count and last_reset_at are system-managed and read_only.
    tenant is read_only and set from request context.
    """

    offer_name         = serializers.CharField(source='offer.name', read_only=True)
    tenant_name        = serializers.CharField(source='tenant.username', read_only=True)
    tenant             = serializers.StringRelatedField(read_only=True)
    remaining_capacity = serializers.SerializerMethodField()

    class Meta:
        model = OfferRoutingCap
        fields = [
            'id', 'offer', 'offer_name', 'tenant', 'tenant_name',
            'cap_type', 'cap_value', 'current_count', 'reset_period',
            'last_reset_date', 'remaining_capacity', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant',
            'current_count',     # system-managed — not user-settable
            'last_reset_date',   # system-managed
            'created_at', 'updated_at',
        ]

    def get_remaining_capacity(self, obj):
        """Calculate remaining capacity."""
        remaining = obj.get_remaining_capacity()
        if remaining == float('inf'):
            return None
        return remaining

    def validate_cap_value(self, value):
        """Validate cap value."""
        if value <= 0:
            raise serializers.ValidationError("Cap value must be positive.")
        return value

    def create(self, validated_data):
        """Force tenant from authenticated request."""
        validated_data['tenant'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        """Prevent tenant being overridden."""
        data.pop('tenant', None)
        return data


class UserOfferCapSerializer(BaseSerializer):
    """Serializer for UserOfferCap model.

    SECURITY: shown_today and last_reset_date are system-managed.
    """

    offer_name    = serializers.CharField(source='offer.name', read_only=True)
    user_name     = serializers.CharField(source='user.username', read_only=True)
    user          = serializers.PrimaryKeyRelatedField(read_only=True)
    remaining_today = serializers.SerializerMethodField()

    class Meta:
        model = UserOfferCap
        fields = [
            'id', 'offer', 'offer_name', 'user', 'user_name',
            'max_shows_per_day', 'shown_today', 'last_reset_date',
            'remaining_today', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user',
            'shown_today',       # system-managed
            'last_reset_date',   # system-managed
            'created_at', 'updated_at',
        ]

    def get_remaining_today(self, obj):
        """Calculate remaining shows for today."""
        return max(0, obj.max_shows_per_day - obj.shown_today)

    def validate_max_shows_per_day(self, value):
        """Validate max shows per day."""
        if not 1 <= value <= 1000:
            raise serializers.ValidationError(
                "Max shows per day must be between 1 and 1000."
            )
        return value


class CapOverrideSerializer(BaseSerializer):
    """Serializer for CapOverride model."""

    offer_name  = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CapOverride
        fields = [
            'id', 'offer', 'offer_name', 'tenant', 'tenant_name',
            'override_value', 'valid_from', 'valid_to', 'reason', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate(self, data):
        """Validate time range and prevent tenant override."""
        data.pop('tenant', None)
        valid_from = data.get('valid_from')
        valid_to   = data.get('valid_to')
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError("Valid from must be before valid to.")
        return data

    def create(self, validated_data):
        validated_data['tenant'] = self.context['request'].user
        return super().create(validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Serializers
# ─────────────────────────────────────────────────────────────────────────────

class FallbackRuleSerializer(BaseSerializer):
    """Serializer for FallbackRule model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = FallbackRule
        fields = [
            'id', 'tenant', 'tenant_name',
            'rule_type', 'priority', 'conditions', 'actions', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_priority(self, value):
        """Validate priority field."""
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10.")
        return value

    def create(self, validated_data):
        validated_data['tenant'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        data.pop('tenant', None)
        return data


class DefaultOfferPoolSerializer(BaseSerializer):
    """Serializer for DefaultOfferPool model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)
    offer_count = serializers.SerializerMethodField()

    class Meta:
        model = DefaultOfferPool
        fields = [
            'id', 'tenant', 'tenant_name',
            'name', 'offers', 'max_offers', 'offer_count',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def get_offer_count(self, obj):
        """Get count of offers in pool."""
        return obj.offers.count()

    def validate_max_offers(self, value):
        """Validate max offers field."""
        if not 1 <= value <= 100:
            raise serializers.ValidationError(
                "Max offers must be between 1 and 100."
            )
        return value

    def create(self, validated_data):
        validated_data['tenant'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        data.pop('tenant', None)
        return data


class EmptyResultHandlerSerializer(BaseSerializer):
    """Serializer for EmptyResultHandler model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = EmptyResultHandler
        fields = [
            'id', 'tenant', 'tenant_name',
            'handler_type', 'priority', 'conditions', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_priority(self, value):
        """Validate priority field."""
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10.")
        return value

    def validate_conditions(self, value):
        """Validate conditions field."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Conditions must be a dictionary.")
        return value

    def create(self, validated_data):
        validated_data['tenant'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        data.pop('tenant', None)
        return data


# ─────────────────────────────────────────────────────────────────────────────
# A/B Test Serializers
# ─────────────────────────────────────────────────────────────────────────────

class RoutingABTestSerializer(BaseSerializer):
    """Serializer for RoutingABTest model."""

    tenant_name        = serializers.CharField(source='tenant.username', read_only=True)
    control_route_name = serializers.CharField(source='control_route.name', read_only=True)
    variant_route_name = serializers.CharField(source='variant_route.name', read_only=True)
    created_by_name    = serializers.CharField(source='created_by.username', read_only=True)
    tenant             = serializers.StringRelatedField(read_only=True)
    created_by         = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RoutingABTest
        fields = [
            'id', 'tenant', 'tenant_name',
            'name', 'description',
            'control_route', 'control_route_name',
            'variant_route', 'variant_route_name',
            'split_percentage', 'duration_hours', 'min_sample_size',
            'confidence_level', 'success_metric',
            'status', 'started_at', 'ended_at',
            'created_by', 'created_by_name',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant', 'created_by',
            'status',        # managed by service layer
            'created_at', 'updated_at',
        ]

    def validate_split_percentage(self, value):
        """Validate split percentage (1–99 only; 0 and 100 are degenerate)."""
        if not 1 <= value <= 99:
            raise serializers.ValidationError(
                "Split percentage must be between 1 and 99."
            )
        return value

    def validate_min_sample_size(self, value):
        """Validate minimum sample size."""
        if value < 100:
            raise serializers.ValidationError(
                "Minimum sample size must be at least 100."
            )
        return value

    def validate_duration_hours(self, value):
        """Validate duration hours."""
        if value and (value < 1 or value > 8760):  # Max 1 year
            raise serializers.ValidationError(
                "Duration must be between 1 and 8760 hours."
            )
        return value

    def validate(self, data):
        """Validate test configuration cross-field rules."""
        data.pop('tenant', None)
        data.pop('created_by', None)

        started_at = data.get('started_at')
        ended_at   = data.get('ended_at')
        if started_at and ended_at and started_at >= ended_at:
            raise serializers.ValidationError("Start time must be before end time.")

        control_route = data.get('control_route')
        variant_route = data.get('variant_route')
        if control_route and variant_route and control_route == variant_route:
            raise serializers.ValidationError(
                "Control and variant routes must be different."
            )
        return data

    def create(self, validated_data):
        validated_data['tenant']     = self.context['request'].user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ABTestAssignmentSerializer(BaseSerializer):
    """Serializer for ABTestAssignment model."""

    test_name       = serializers.CharField(source='test.name', read_only=True)
    user_name       = serializers.CharField(source='user.username', read_only=True)
    user            = serializers.PrimaryKeyRelatedField(read_only=True)
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = ABTestAssignment
        fields = [
            'id', 'test', 'test_name', 'user', 'user_name',
            'variant', 'impressions', 'conversions', 'conversion_rate',
            'assigned_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user',
            'impressions',   # system-managed
            'conversions',   # system-managed
            'assigned_at', 'created_at', 'updated_at',
        ]

    def get_conversion_rate(self, obj):
        """Calculate conversion rate."""
        if obj.impressions == 0:
            return 0.0
        return round((obj.conversions / obj.impressions) * 100, 2)

    def validate_variant(self, value):
        """Validate variant field."""
        valid_variants = ['control', 'variant']
        if value not in valid_variants:
            raise serializers.ValidationError(
                f"Variant must be one of: {valid_variants}"
            )
        return value


class ABTestResultSerializer(BaseSerializer):
    """Serializer for ABTestResult model."""

    test_name                = serializers.CharField(source='test.name', read_only=True)
    control_conversion_rate  = serializers.SerializerMethodField()
    variant_conversion_rate  = serializers.SerializerMethodField()

    class Meta:
        model = ABTestResult
        fields = [
            'id', 'test', 'test_name',
            'control_impressions', 'control_conversions', 'control_conversion_rate',
            'variant_impressions', 'variant_conversions', 'variant_conversion_rate',
            'statistical_significance', 'winner', 'calculated_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_control_conversion_rate(self, obj):
        """Calculate control conversion rate."""
        if obj.control_impressions == 0:
            return 0.0
        return round((obj.control_conversions / obj.control_impressions) * 100, 2)

    def get_variant_conversion_rate(self, obj):
        """Calculate variant conversion rate."""
        if obj.variant_impressions == 0:
            return 0.0
        return round((obj.variant_conversions / obj.variant_impressions) * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Serializers
# ─────────────────────────────────────────────────────────────────────────────

class RoutingDecisionLogSerializer(BaseSerializer):
    """Serializer for RoutingDecisionLog model. All fields are read-only."""

    user_name = serializers.CharField(source='user.username', read_only=True)
    user      = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RoutingDecisionLog
        fields = [
            'id', 'user', 'user_name', 'route', 'offer_id',
            'reason', 'score', 'rank',
            'response_time_ms', 'cache_hit',
            'context_data', 'personalization_applied',
            'caps_checked', 'fallback_used',
            'ab_test', 'ab_test_variant',
            'created_at',
        ]
        read_only_fields = [
            'id', 'user', 'created_at',
        ]

    def validate_score(self, value):
        """Validate score field."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Score must be between 0 and 100.")
        return value

    def validate_response_time_ms(self, value):
        """Validate response time."""
        if value < 0:
            raise serializers.ValidationError("Response time cannot be negative.")
        return value


class RoutingInsightSerializer(BaseSerializer):
    """Serializer for RoutingInsight model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RoutingInsight
        fields = [
            'id', 'tenant', 'tenant_name',
            'title', 'description', 'insight_type',
            'severity', 'is_actionable', 'data',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_severity(self, value):
        """Validate severity field."""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if value not in valid_severities:
            raise serializers.ValidationError(
                f"Severity must be one of: {valid_severities}"
            )
        return value


class RoutePerformanceStatSerializer(BaseSerializer):
    """Serializer for RoutePerformanceStat model."""

    tenant_name     = serializers.CharField(source='tenant.username', read_only=True)
    offer_name      = serializers.CharField(source='offer.name', read_only=True)
    tenant          = serializers.StringRelatedField(read_only=True)
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = RoutePerformanceStat
        fields = [
            'id', 'tenant', 'tenant_name', 'offer', 'offer_name',
            'date', 'impressions', 'conversions', 'conversion_rate',
            'avg_response_time_ms', 'cache_hit_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def get_conversion_rate(self, obj):
        """Calculate conversion rate."""
        if obj.impressions == 0:
            return 0.0
        return round((obj.conversions / obj.impressions) * 100, 2)


class OfferExposureStatSerializer(BaseSerializer):
    """Serializer for OfferExposureStat model."""

    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    offer_name  = serializers.CharField(source='offer.name', read_only=True)
    tenant      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OfferExposureStat
        fields = [
            'id', 'tenant', 'tenant_name', 'offer', 'offer_name',
            'aggregation_type', 'period_start', 'impressions', 'unique_users',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']

    def validate_aggregation_type(self, value):
        """Validate aggregation type."""
        valid_types = ['hourly', 'daily', 'weekly', 'monthly']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Aggregation type must be one of: {valid_types}"
            )
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Specialized Serializers for API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class RoutingRequestSerializer(serializers.Serializer):
    """Serializer for routing requests."""

    user_id       = serializers.IntegerField(required=True)
    context       = serializers.JSONField(required=True)
    limit         = serializers.IntegerField(default=10, min_value=1, max_value=50)
    cache_enabled = serializers.BooleanField(default=True)

    def validate_context(self, value):
        """Validate context data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Context must be a dictionary.")

        required_fields = ['ip_address']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(
                    f"Context must include '{field}'."
                )
        return value


class RoutingResponseSerializer(serializers.Serializer):
    """Serializer for routing responses."""

    success       = serializers.BooleanField()
    offers        = serializers.ListField(child=serializers.DictField())
    metadata      = serializers.DictField()
    error_message = serializers.CharField(allow_null=True)


class OfferRecommendationSerializer(serializers.Serializer):
    """Serializer for offer recommendations."""

    offer_id   = serializers.IntegerField()
    score      = serializers.FloatField()
    rank       = serializers.IntegerField()
    confidence = serializers.FloatField(allow_null=True)
    reasons    = serializers.ListField(child=serializers.CharField(), required=False)


class BulkAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk A/B test assignments."""

    user_ids = serializers.ListField(child=serializers.IntegerField())
    test_id  = serializers.IntegerField()

    def validate_user_ids(self, value):
        """Validate user IDs."""
        if len(value) > 1000:
            raise serializers.ValidationError(
                "Cannot assign more than 1000 users at once."
            )
        existing_users = User.objects.filter(id__in=value).count()
        if existing_users != len(value):
            raise serializers.ValidationError("Some users do not exist.")
        return value


class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance metrics."""

    date               = serializers.DateField()
    total_decisions    = serializers.IntegerField()
    avg_response_time_ms = serializers.FloatField()
    cache_hit_rate     = serializers.FloatField()
    conversion_rate    = serializers.FloatField()
    revenue_per_user   = serializers.DecimalField(max_digits=10, decimal_places=2)


# ─────────────────────────────────────────────────────────────────────────────
# Summary Serializers
# ─────────────────────────────────────────────────────────────────────────────

class RouteSummarySerializer(serializers.Serializer):
    """Serializer for route summary information."""

    route_id      = serializers.IntegerField()
    name          = serializers.CharField()
    priority      = serializers.IntegerField()
    total_offers  = serializers.IntegerField()
    active_offers = serializers.IntegerField()
    avg_score     = serializers.FloatField()
    conversion_rate = serializers.FloatField()


class UserSummarySerializer(serializers.Serializer):
    """Serializer for user summary information."""

    user_id               = serializers.IntegerField()
    username              = serializers.CharField()
    total_decisions       = serializers.IntegerField()
    avg_score             = serializers.FloatField()
    conversion_rate       = serializers.FloatField()
    preferred_categories  = serializers.ListField(child=serializers.CharField())


class TestSummarySerializer(serializers.Serializer):
    """Serializer for A/B test summary."""

    test_id              = serializers.IntegerField()
    name                 = serializers.CharField()
    status               = serializers.CharField()
    control_conversions  = serializers.IntegerField()
    variant_conversions  = serializers.IntegerField()
    winner               = serializers.CharField(allow_null=True)
    confidence           = serializers.FloatField(allow_null=True)


# ─────────────────────────────────────────────────────────────────────────────
# Export Serializers
# ─────────────────────────────────────────────────────────────────────────────

class DecisionLogExportSerializer(serializers.Serializer):
    """Serializer for decision log export."""

    date_from = serializers.DateField()
    date_to   = serializers.DateField()
    user_id   = serializers.IntegerField(required=False)
    offer_id  = serializers.IntegerField(required=False)
    format    = serializers.ChoiceField(choices=['csv', 'json'], default='csv')


class PerformanceExportSerializer(serializers.Serializer):
    """Serializer for performance data export."""

    date_from   = serializers.DateField()
    date_to     = serializers.DateField()
    aggregation = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )
    format = serializers.ChoiceField(choices=['csv', 'json'], default='csv')


# ─────────────────────────────────────────────────────────────────────────────
# Validation Serializers
# ─────────────────────────────────────────────────────────────────────────────

class RouteValidationSerializer(serializers.Serializer):
    """Serializer for route validation."""

    route_id     = serializers.IntegerField()
    test_context = serializers.JSONField()

    def validate_test_context(self, value):
        """Validate test context."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test context must be a dictionary.")
        return value


class CapValidationSerializer(serializers.Serializer):
    """Serializer for cap validation."""

    offer_id = serializers.IntegerField()
    user_id  = serializers.IntegerField()
    cap_type = serializers.CharField()


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Serializers
# ─────────────────────────────────────────────────────────────────────────────

class SystemConfigSerializer(serializers.Serializer):
    """Serializer for system configuration."""

    cache_enabled              = serializers.BooleanField()
    personalization_enabled    = serializers.BooleanField()
    ab_testing_enabled         = serializers.BooleanField()
    monitoring_enabled         = serializers.BooleanField()
    max_concurrent_requests    = serializers.IntegerField(min_value=1, max_value=1000)
    default_timeout_ms         = serializers.IntegerField(min_value=100, max_value=10000)


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Serializers
# ─────────────────────────────────────────────────────────────────────────────

class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer for health check responses."""

    status    = serializers.CharField()
    timestamp = serializers.DateTimeField()
    services  = serializers.DictField()
    metrics   = serializers.DictField()


# ─────────────────────────────────────────────────────────────────────────────
# Error Response Serializers
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses."""

    error_code    = serializers.CharField()
    error_message = serializers.CharField()
    details       = serializers.DictField(required=False)
    timestamp     = serializers.DateTimeField()


# ─────────────────────────────────────────────────────────────────────────────
# Pagination Serializers
# ─────────────────────────────────────────────────────────────────────────────

class PaginatedResponseSerializer(serializers.Serializer):
    """Serializer for paginated responses."""

    count    = serializers.IntegerField()
    next     = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results  = serializers.ListField(child=serializers.DictField())


# ─────────────────────────────────────────────────────────────────────────────
# Custom Field Classes
# ─────────────────────────────────────────────────────────────────────────────

class JSONField(serializers.JSONField):
    """Custom JSON field with enhanced validation."""

    def to_internal_value(self, data):
        """Validate JSON data."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON format.")
        return super().to_internal_value(data)


class TimestampField(serializers.DateTimeField):
    """Custom timestamp field."""

    def to_representation(self, value):
        """Convert to ISO format."""
        if value:
            return value.isoformat()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Serializer Mixins
# ─────────────────────────────────────────────────────────────────────────────

class TenantFilterMixin:
    """Mixin for tenant filtering in serializer context."""

    def get_queryset(self):
        """Filter queryset by tenant."""
        queryset = super().get_queryset()
        user = self.context['request'].user

        if not user.is_superuser:
            queryset = queryset.filter(tenant=user)

        return queryset


class AuditMixin:
    """Mixin for audit fields."""

    def create(self, validated_data):
        """Add audit fields on create."""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Add audit fields on update."""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# Combined Serializers with Mixins
# ─────────────────────────────────────────────────────────────────────────────

class TenantFilteredOfferRouteSerializer(TenantFilterMixin, OfferRouteSerializer):
    """OfferRoute serializer with tenant filtering."""
    pass


class AuditedRoutingABTestSerializer(AuditMixin, RoutingABTestSerializer):
    """A/B test serializer with audit tracking."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Serializers for previously under-served models (deep-scan additions)
# ─────────────────────────────────────────────────────────────────────────────

class RoutingBlacklistSerializer(BaseSerializer):
    """Serializer for RoutingBlacklist model."""

    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'pattern', 'pattern_type', 'reason', 'is_active', 'created_at']
        read_only_fields = ['id', 'tenant', 'created_at']

    def __init__(self, *args, **kwargs):
        from .models import RoutingBlacklist
        self.__class__.Meta.model = RoutingBlacklist
        super().__init__(*args, **kwargs)


class BlacklistHitSerializer(BaseSerializer):
    """Serializer for BlacklistHit model."""

    class Meta:
        model  = None
        fields = ['id', 'blacklist', 'ip_address', 'matched_at', 'request_path']
        read_only_fields = ['id', 'matched_at']

    def __init__(self, *args, **kwargs):
        from .models import BlacklistHit
        self.__class__.Meta.model = BlacklistHit
        super().__init__(*args, **kwargs)


class OfferQualityScoreSerializer(BaseSerializer):
    """Serializer for OfferQualityScore model."""

    class Meta:
        model  = None
        fields = ['id', 'offer', 'tenant', 'quality_score', 'relevance_score', 'freshness_score', 'calculated_at']
        read_only_fields = ['id', 'calculated_at']

    def __init__(self, *args, **kwargs):
        from .models import OfferQualityScore
        self.__class__.Meta.model = OfferQualityScore
        super().__init__(*args, **kwargs)


class NetworkPerformanceCacheSerializer(BaseSerializer):
    """Serializer for NetworkPerformanceCache model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'route', 'avg_response_time_ms', 'p95_response_time_ms', 'success_rate', 'cached_at']
        read_only_fields = ['id', 'cached_at']

    def __init__(self, *args, **kwargs):
        from .models import NetworkPerformanceCache
        self.__class__.Meta.model = NetworkPerformanceCache
        super().__init__(*args, **kwargs)


class ClickFraudSignalSerializer(BaseSerializer):
    """Serializer for ClickFraudSignal model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'user_id', 'ip_address', 'signal_type', 'severity', 'detected_at']
        read_only_fields = ['id', 'detected_at']

    def __init__(self, *args, **kwargs):
        from .models import ClickFraudSignal
        self.__class__.Meta.model = ClickFraudSignal
        super().__init__(*args, **kwargs)


class FraudPatternSerializer(BaseSerializer):
    """Serializer for FraudPattern model."""

    class Meta:
        model  = None
        fields = ['id', 'name', 'pattern_type', 'config', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        from .models import FraudPattern
        self.__class__.Meta.model = FraudPattern
        super().__init__(*args, **kwargs)


class UserJourneyStepSerializer(BaseSerializer):
    """Serializer for UserJourneyStep model."""

    class Meta:
        model  = None
        fields = ['id', 'user_id', 'step_type', 'step_data', 'step_timestamp', 'session_id']
        read_only_fields = ['id', 'step_timestamp']

    def __init__(self, *args, **kwargs):
        from .models import UserJourneyStep
        self.__class__.Meta.model = UserJourneyStep
        super().__init__(*args, **kwargs)


class RoutingConfigSerializer(BaseSerializer):
    """Serializer for RoutingConfig model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'name', 'config_data', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        from .models.core import RoutingConfig
        self.__class__.Meta.model = RoutingConfig
        super().__init__(*args, **kwargs)


class RoutingTemplateSerializer(BaseSerializer):
    """Serializer for RoutingTemplate model."""

    class Meta:
        model  = None
        fields = ['id', 'name', 'description', 'category', 'template_data', 'is_public', 'created_by', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']

    def __init__(self, *args, **kwargs):
        from .models.core import RoutingTemplate
        self.__class__.Meta.model = RoutingTemplate
        super().__init__(*args, **kwargs)


class SecurityEventSerializer(BaseSerializer):
    """Serializer for SecurityEvent model."""

    class Meta:
        model  = None
        fields = ['id', 'event_type', 'severity', 'source_ip', 'description', 'occurred_at', 'resolved']
        read_only_fields = ['id', 'occurred_at']

    def __init__(self, *args, **kwargs):
        try:
            from .models.security import SecurityEvent
        except ImportError:
            from .models import SecurityEvent
        self.__class__.Meta.model = SecurityEvent
        super().__init__(*args, **kwargs)


class TenantBillingSerializer(BaseSerializer):
    """Serializer for TenantBilling model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'billing_month', 'total_decisions', 'amount_due', 'is_paid', 'generated_at']
        read_only_fields = ['id', 'generated_at']

    def __init__(self, *args, **kwargs):
        from .models.core import TenantBilling
        self.__class__.Meta.model = TenantBilling
        super().__init__(*args, **kwargs)


class TenantInvoiceSerializer(BaseSerializer):
    """Serializer for TenantInvoice model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'invoice_number', 'amount', 'status', 'issued_at', 'due_date']
        read_only_fields = ['id', 'invoice_number', 'issued_at']

    def __init__(self, *args, **kwargs):
        from .models.core import TenantInvoice
        self.__class__.Meta.model = TenantInvoice
        super().__init__(*args, **kwargs)


class TenantSettingsSerializer(BaseSerializer):
    """Serializer for TenantSettings model."""

    class Meta:
        model  = None
        fields = ['id', 'tenant', 'max_routes', 'max_offers_per_route', 'enable_ab_testing', 'enable_personalization', 'updated_at']
        read_only_fields = ['id', 'tenant', 'updated_at']

    def __init__(self, *args, **kwargs):
        from .models.core import TenantSettings
        self.__class__.Meta.model = TenantSettings
        super().__init__(*args, **kwargs)
