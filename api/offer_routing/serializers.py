"""
Django REST Framework Serializers for Offer Routing System

This module provides serializers for all models in the offer routing system,
including validation, nested relationships, and custom field handling.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum, Avg
import json

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
    OfferExposureStat
)

User = get_user_model()


# Base Serializers
class BaseSerializer(serializers.ModelSerializer):
    """Base serializer with common functionality."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add tenant filtering for non-superusers
        if 'request' in self.context:
            request = self.context['request']
            if not request.user.is_superuser:
                self.Meta.fields = tuple(f for f in self.Meta.fields if f != 'tenant')
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# Core Serializers
class RouteConditionSerializer(BaseSerializer):
    """Serializer for RouteCondition model."""
    
    class Meta:
        model = RouteCondition
        fields = '__all__'


class RouteActionSerializer(BaseSerializer):
    """Serializer for RouteAction model."""
    
    class Meta:
        model = RouteAction
        fields = '__all__'


class OfferRouteSerializer(BaseSerializer):
    """Serializer for OfferRoute model."""
    
    conditions = RouteConditionSerializer(many=True, read_only=True)
    actions = RouteActionSerializer(many=True, read_only=True)
    geo_rules = serializers.SerializerMethodField()
    device_rules = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferRoute
        fields = '__all__'
    
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
    """Serializer for creating OfferRoute instances."""
    
    conditions = RouteConditionSerializer(many=True, required=False)
    actions = RouteActionSerializer(many=True, required=False)
    
    class Meta:
        model = OfferRoute
        exclude = ['tenant']
    
    def create(self, validated_data):
        """Create OfferRoute with nested conditions and actions."""
        conditions_data = validated_data.pop('conditions', [])
        actions_data = validated_data.pop('actions', [])
        
        # Set tenant from request
        validated_data['tenant'] = self.context['request'].user
        
        offer_route = OfferRoute.objects.create(**validated_data)
        
        # Create conditions
        for condition_data in conditions_data:
            RouteCondition.objects.create(route=offer_route, **condition_data)
        
        # Create actions
        for action_data in actions_data:
            RouteAction.objects.create(route=offer_route, **action_data)
        
        return offer_route


# Targeting Serializers
class GeoRouteRuleSerializer(BaseSerializer):
    """Serializer for GeoRouteRule model."""
    
    class Meta:
        model = GeoRouteRule
        fields = '__all__'
    
    def validate_country(self, value):
        """Validate country code."""
        if value and len(value) != 2:
            raise serializers.ValidationError("Country code must be 2 characters.")
        return value.upper() if value else value


class DeviceRouteRuleSerializer(BaseSerializer):
    """Serializer for DeviceRouteRule model."""
    
    class Meta:
        model = DeviceRouteRule
        fields = '__all__'


class UserSegmentRuleSerializer(BaseSerializer):
    """Serializer for UserSegmentRule model."""
    
    class Meta:
        model = UserSegmentRule
        fields = '__all__'


class TimeRouteRuleSerializer(BaseSerializer):
    """Serializer for TimeRouteRule model."""
    
    class Meta:
        model = TimeRouteRule
        fields = '__all__'
    
    def validate_days_of_week(self, value):
        """Validate days of week."""
        if value:
            try:
                days = [int(d.strip()) for d in value.split(',')]
                if not all(0 <= d <= 6 for d in days):
                    raise serializers.ValidationError("Days must be 0-6 (Sunday-Saturday).")
                return value
            except (ValueError, AttributeError):
                raise serializers.ValidationError("Invalid days format. Use comma-separated numbers 0-6.")
        return value


class BehaviorRouteRuleSerializer(BaseSerializer):
    """Serializer for BehaviorRouteRule model."""
    
    class Meta:
        model = BehaviorRouteRule
        fields = '__all__'
    
    def validate_time_period_hours(self, value):
        """Validate time period hours."""
        if not 1 <= value <= 8760:  # Max 1 year
            raise serializers.ValidationError("Time period must be between 1 and 8760 hours.")
        return value


# Scoring Serializers
class OfferScoreSerializer(BaseSerializer):
    """Serializer for OfferScore model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = OfferScore
        fields = '__all__'
    
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
            raise serializers.ValidationError("Conversion rate must be between 0 and 100.")
        return value


class OfferScoreConfigSerializer(BaseSerializer):
    """Serializer for OfferScoreConfig model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    
    class Meta:
        model = OfferScoreConfig
        fields = '__all__'
    
    def validate(self, data):
        """Validate weight distribution."""
        weights = ['epc_weight', 'cr_weight', 'relevance_weight', 'freshness_weight']
        total_weight = sum(data.get(w, 0) for w in weights)
        
        if abs(total_weight - 1.0) > 0.01:  # Allow small rounding errors
            raise serializers.ValidationError(f"Weights must sum to 1.0 (current: {total_weight})")
        
        return data


class GlobalOfferRankSerializer(BaseSerializer):
    """Serializer for GlobalOfferRank model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    
    class Meta:
        model = GlobalOfferRank
        fields = '__all__'


class UserOfferHistorySerializer(BaseSerializer):
    """Serializer for UserOfferHistory model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserOfferHistory
        fields = '__all__'
    
    def validate_conversion_value(self, value):
        """Validate conversion value."""
        if value < 0:
            raise serializers.ValidationError("Conversion value cannot be negative.")
        return value


class OfferAffinityScoreSerializer(BaseSerializer):
    """Serializer for OfferAffinityScore model."""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = OfferAffinityScore
        fields = '__all__'
    
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


# Personalization Serializers
class UserPreferenceVectorSerializer(BaseSerializer):
    """Serializer for UserPreferenceVector model."""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    vector_size = serializers.SerializerMethodField()
    
    class Meta:
        model = UserPreferenceVector
        fields = '__all__'
    
    def get_vector_size(self, obj):
        """Get size of preference vector."""
        try:
            return len(obj.vector) if obj.vector else 0
        except (TypeError, ValueError):
            return 0
    
    def validate_category_weights(self, value):
        """Validate category weights."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Category weights must be a dictionary.")
        
        for key, val in value.items():
            if not isinstance(val, (int, float)) or not 0 <= val <= 1:
                raise serializers.ValidationError(f"Weight for '{key}' must be between 0 and 1.")
        
        return value


class ContextualSignalSerializer(BaseSerializer):
    """Serializer for ContextualSignal model."""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = ContextualSignal
        fields = '__all__'
    
    def validate_weight(self, value):
        """Validate weight field."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Weight must be between 0 and 1.")
        return value
    
    def validate_expires_at(self, value):
        """Validate expires_at field."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration time must be in the future.")
        return value


class PersonalizationConfigSerializer(BaseSerializer):
    """Serializer for PersonalizationConfig model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PersonalizationConfig
        fields = '__all__'
    
    def validate(self, data):
        """Validate weight distribution."""
        weights = ['collaborative_weight', 'content_based_weight', 'hybrid_weight']
        total_weight = sum(data.get(w, 0) for w in weights)
        
        if abs(total_weight - 1.0) > 0.01:
            raise serializers.ValidationError(f"Weights must sum to 1.0 (current: {total_weight})")
        
        return data


# Cap Serializers
class OfferRoutingCapSerializer(BaseSerializer):
    """Serializer for OfferRoutingCap model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    remaining_capacity = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferRoutingCap
        fields = '__all__'
    
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


class UserOfferCapSerializer(BaseSerializer):
    """Serializer for UserOfferCap model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    remaining_today = serializers.SerializerMethodField()
    
    class Meta:
        model = UserOfferCap
        fields = '__all__'
    
    def get_remaining_today(self, obj):
        """Calculate remaining shows for today."""
        return max(0, obj.max_shows_per_day - obj.shown_today)
    
    def validate_max_shows_per_day(self, value):
        """Validate max shows per day."""
        if not 1 <= value <= 1000:
            raise serializers.ValidationError("Max shows per day must be between 1 and 1000.")
        return value


class CapOverrideSerializer(BaseSerializer):
    """Serializer for CapOverride model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    
    class Meta:
        model = CapOverride
        fields = '__all__'
    
    def validate(self, data):
        """Validate time range."""
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError("Valid from must be before valid to.")
        
        return data


# Fallback Serializers
class FallbackRuleSerializer(BaseSerializer):
    """Serializer for FallbackRule model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    
    class Meta:
        model = FallbackRule
        fields = '__all__'
    
    def validate_priority(self, value):
        """Validate priority field."""
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10.")
        return value


class DefaultOfferPoolSerializer(BaseSerializer):
    """Serializer for DefaultOfferPool model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    offer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DefaultOfferPool
        fields = '__all__'
    
    def get_offer_count(self, obj):
        """Get count of offers in pool."""
        return obj.offers.count()
    
    def validate_max_offers(self, value):
        """Validate max offers field."""
        if not 1 <= value <= 100:
            raise serializers.ValidationError("Max offers must be between 1 and 100.")
        return value


class EmptyResultHandlerSerializer(BaseSerializer):
    """Serializer for EmptyResultHandler model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    
    class Meta:
        model = EmptyResultHandler
        fields = '__all__'
    
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


# A/B Test Serializers
class RoutingABTestSerializer(BaseSerializer):
    """Serializer for RoutingABTest model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    control_route_name = serializers.CharField(source='control_route.name', read_only=True)
    variant_route_name = serializers.CharField(source='variant_route.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = RoutingABTest
        fields = '__all__'
    
    def validate_split_percentage(self, value):
        """Validate split percentage."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Split percentage must be between 0 and 100.")
        return value
    
    def validate_min_sample_size(self, value):
        """Validate minimum sample size."""
        if value < 100:
            raise serializers.ValidationError("Minimum sample size must be at least 100.")
        return value
    
    def validate_duration_hours(self, value):
        """Validate duration hours."""
        if value and (value < 1 or value > 8760):  # Max 1 year
            raise serializers.ValidationError("Duration must be between 1 and 8760 hours.")
        return value
    
    def validate(self, data):
        """Validate test configuration."""
        started_at = data.get('started_at')
        ended_at = data.get('ended_at')
        
        if started_at and ended_at and started_at >= ended_at:
            raise serializers.ValidationError("Start time must be before end time.")
        
        # Validate different routes
        control_route = data.get('control_route')
        variant_route = data.get('variant_route')
        
        if control_route and variant_route and control_route == variant_route:
            raise serializers.ValidationError("Control and variant routes must be different.")
        
        return data


class ABTestAssignmentSerializer(BaseSerializer):
    """Serializer for ABTestAssignment model."""
    
    test_name = serializers.CharField(source='test.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    conversion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ABTestAssignment
        fields = '__all__'
    
    def get_conversion_rate(self, obj):
        """Calculate conversion rate."""
        if obj.impressions == 0:
            return 0.0
        return round((obj.conversions / obj.impressions) * 100, 2)
    
    def validate_variant(self, value):
        """Validate variant field."""
        valid_variants = ['control', 'variant']
        if value not in valid_variants:
            raise serializers.ValidationError(f"Variant must be one of: {valid_variants}")
        return value


class ABTestResultSerializer(BaseSerializer):
    """Serializer for ABTestResult model."""
    
    test_name = serializers.CharField(source='test.name', read_only=True)
    control_conversion_rate = serializers.SerializerMethodField()
    variant_conversion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ABTestResult
        fields = '__all__'
    
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


# Analytics Serializers
class RoutingDecisionLogSerializer(BaseSerializer):
    """Serializer for RoutingDecisionLog model."""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = RoutingDecisionLog
        fields = '__all__'
    
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
    
    class Meta:
        model = RoutingInsight
        fields = '__all__'
    
    def validate_severity(self, value):
        """Validate severity field."""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if value not in valid_severities:
            raise serializers.ValidationError(f"Severity must be one of: {valid_severities}")
        return value


class RoutePerformanceStatSerializer(BaseSerializer):
    """Serializer for RoutePerformanceStat model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    conversion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = RoutePerformanceStat
        fields = '__all__'
    
    def get_conversion_rate(self, obj):
        """Calculate conversion rate."""
        if obj.impressions == 0:
            return 0.0
        return round((obj.conversions / obj.impressions) * 100, 2)


class OfferExposureStatSerializer(BaseSerializer):
    """Serializer for OfferExposureStat model."""
    
    tenant_name = serializers.CharField(source='tenant.username', read_only=True)
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    
    class Meta:
        model = OfferExposureStat
        fields = '__all__'
    
    def validate_aggregation_type(self, value):
        """Validate aggregation type."""
        valid_types = ['hourly', 'daily', 'weekly', 'monthly']
        if value not in valid_types:
            raise serializers.ValidationError(f"Aggregation type must be one of: {valid_types}")
        return value


# Specialized Serializers for API Endpoints
class RoutingRequestSerializer(serializers.Serializer):
    """Serializer for routing requests."""
    
    user_id = serializers.IntegerField(required=True)
    context = serializers.JSONField(required=True)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=50)
    cache_enabled = serializers.BooleanField(default=True)
    
    def validate_context(self, value):
        """Validate context data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Context must be a dictionary.")
        
        # Validate required context fields
        required_fields = ['ip_address']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Context must include '{field}'.")
        
        return value


class RoutingResponseSerializer(serializers.Serializer):
    """Serializer for routing responses."""
    
    success = serializers.BooleanField()
    offers = serializers.ListField(child=serializers.DictField())
    metadata = serializers.DictField()
    error_message = serializers.CharField(allow_null=True)


class OfferRecommendationSerializer(serializers.Serializer):
    """Serializer for offer recommendations."""
    
    offer_id = serializers.IntegerField()
    score = serializers.FloatField()
    rank = serializers.IntegerField()
    confidence = serializers.FloatField(allow_null=True)
    reasons = serializers.ListField(child=serializers.CharField(), required=False)


class BulkAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk A/B test assignments."""
    
    user_ids = serializers.ListField(child=serializers.IntegerField())
    test_id = serializers.IntegerField()
    
    def validate_user_ids(self, value):
        """Validate user IDs."""
        if len(value) > 1000:
            raise serializers.ValidationError("Cannot assign more than 1000 users at once.")
        
        # Check if users exist
        existing_users = User.objects.filter(id__in=value).count()
        if existing_users != len(value):
            raise serializers.ValidationError("Some users do not exist.")
        
        return value


class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance metrics."""
    
    date = serializers.DateField()
    total_decisions = serializers.IntegerField()
    avg_response_time_ms = serializers.FloatField()
    cache_hit_rate = serializers.FloatField()
    conversion_rate = serializers.FloatField()
    revenue_per_user = serializers.DecimalField(max_digits=10, decimal_places=2)


# Summary Serializers
class RouteSummarySerializer(serializers.Serializer):
    """Serializer for route summary information."""
    
    route_id = serializers.IntegerField()
    name = serializers.CharField()
    priority = serializers.IntegerField()
    total_offers = serializers.IntegerField()
    active_offers = serializers.IntegerField()
    avg_score = serializers.FloatField()
    conversion_rate = serializers.FloatField()


class UserSummarySerializer(serializers.Serializer):
    """Serializer for user summary information."""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    total_decisions = serializers.IntegerField()
    avg_score = serializers.FloatField()
    conversion_rate = serializers.FloatField()
    preferred_categories = serializers.ListField(child=serializers.CharField())


class TestSummarySerializer(serializers.Serializer):
    """Serializer for A/B test summary."""
    
    test_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    control_conversions = serializers.IntegerField()
    variant_conversions = serializers.IntegerField()
    winner = serializers.CharField(allow_null=True)
    confidence = serializers.FloatField(allow_null=True)


# Export Serializers
class DecisionLogExportSerializer(serializers.Serializer):
    """Serializer for decision log export."""
    
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    user_id = serializers.IntegerField(required=False)
    offer_id = serializers.IntegerField(required=False)
    format = serializers.ChoiceField(choices=['csv', 'json'], default='csv')


class PerformanceExportSerializer(serializers.Serializer):
    """Serializer for performance data export."""
    
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    aggregation = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )
    format = serializers.ChoiceField(choices=['csv', 'json'], default='csv')


# Validation Serializers
class RouteValidationSerializer(serializers.Serializer):
    """Serializer for route validation."""
    
    route_id = serializers.IntegerField()
    test_context = serializers.JSONField()
    
    def validate_test_context(self, value):
        """Validate test context."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test context must be a dictionary.")
        return value


class CapValidationSerializer(serializers.Serializer):
    """Serializer for cap validation."""
    
    offer_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    cap_type = serializers.CharField()


# Configuration Serializers
class SystemConfigSerializer(serializers.Serializer):
    """Serializer for system configuration."""
    
    cache_enabled = serializers.BooleanField()
    personalization_enabled = serializers.BooleanField()
    ab_testing_enabled = serializers.BooleanField()
    monitoring_enabled = serializers.BooleanField()
    max_concurrent_requests = serializers.IntegerField(min_value=1, max_value=1000)
    default_timeout_ms = serializers.IntegerField(min_value=100, max_value=10000)


# Health Check Serializers
class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer for health check responses."""
    
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    services = serializers.DictField()
    metrics = serializers.DictField()


# Error Response Serializers
class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses."""
    
    error_code = serializers.CharField()
    error_message = serializers.CharField()
    details = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField()


# Pagination Serializers
class PaginatedResponseSerializer(serializers.Serializer):
    """Serializer for paginated responses."""
    
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField(child=serializers.DictField())


# Field Validators
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


# Serializer Mixins
class TenantFilterMixin:
    """Mixin for tenant filtering."""
    
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


# Combined Serializers with Mixins
class TenantFilteredOfferRouteSerializer(TenantFilterMixin, OfferRouteSerializer):
    """OfferRoute serializer with tenant filtering."""
    pass


class AuditedRoutingABTestSerializer(AuditMixin, RoutingABTestSerializer):
    """A/B test serializer with audit tracking."""
    pass
