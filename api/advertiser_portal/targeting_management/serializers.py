"""
Targeting Management Serializers

This module contains Django REST Framework serializers for targeting
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..database_models.targeting_model import Targeting, AudienceSegment, TargetingRule
from ..database_models.campaign_model import Campaign
from ..enums import *
from ..validators import *


class TargetingRuleSerializer(serializers.ModelSerializer):
    """Serializer for TargetingRule model."""
    
    class Meta:
        model = TargetingRule
        fields = [
            'id', 'targeting', 'rule_name', 'rule_type', 'conditions',
            'actions', 'priority', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'targeting', 'created_at']


class AudienceSegmentSerializer(serializers.ModelSerializer):
    """Serializer for AudienceSegment model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AudienceSegment
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'segment_type', 'criteria', 'audience_size', 'estimated_reach',
            'refresh_frequency', 'last_refresh', 'is_active', 'is_public',
            'tags', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'audience_size',
            'estimated_reach', 'last_refresh', 'created_at', 'updated_at'
        ]


class AudienceSegmentDetailSerializer(AudienceSegmentSerializer):
    """Detailed serializer for AudienceSegment model with additional fields."""
    
    insights = serializers.SerializerMethodField()
    performance_metrics = serializers.SerializerMethodField()
    
    class Meta(AudienceSegmentSerializer.Meta):
        fields = AudienceSegmentSerializer.Meta.fields + [
            'insights', 'performance_metrics'
        ]
    
    def get_insights(self, obj):
        """Get insights for segment."""
        try:
            return AudienceSegmentService.get_segment_insights(obj.id)
        except Exception:
            return {}
    
    def get_performance_metrics(self, obj):
        """Get performance metrics for segment."""
        # This would implement actual performance metrics calculation
        return {
            'ctr': 0,
            'conversion_rate': 0,
            'roas': 0
        }


class TargetingSerializer(serializers.ModelSerializer):
    """Serializer for Targeting model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    advertiser_name = serializers.CharField(source='campaign.advertiser.company_name', read_only=True)
    rules = TargetingRuleSerializer(many=True, read_only=True)
    
    class Meta:
        model = Targeting
        fields = [
            'id', 'campaign', 'campaign_name', 'advertiser_name', 'name',
            'description', 'geo_targeting_type', 'countries', 'regions',
            'cities', 'postal_codes', 'coordinates', 'radius', 'geo_fencing',
            'device_targeting', 'os_families', 'browsers', 'carriers',
            'device_models', 'connection_types', 'age_min', 'age_max',
            'genders', 'languages', 'interests', 'keywords',
            'custom_audiences', 'lookalike_audiences', 'exclude_audiences',
            'behavioral_segments', 'contextual_targeting', 'site_targeting',
            'app_targeting', 'content_categories', 'placement_targeting',
            'time_targeting', 'frequency_capping', 'bid_adjustments',
            'rules', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'campaign', 'campaign_name', 'advertiser_name', 'rules',
            'created_at', 'updated_at'
        ]


class TargetingDetailSerializer(TargetingSerializer):
    """Detailed serializer for Targeting model with additional fields."""
    
    validation_result = serializers.SerializerMethodField()
    targeting_summary = serializers.SerializerMethodField()
    reach_estimation = serializers.SerializerMethodField()
    targeting_score = serializers.SerializerMethodField()
    performance_metrics = serializers.SerializerMethodField()
    optimization_recommendations = serializers.SerializerMethodField()
    
    class Meta(TargetingSerializer.Meta):
        fields = TargetingSerializer.Meta.fields + [
            'validation_result', 'targeting_summary', 'reach_estimation',
            'targeting_score', 'performance_metrics', 'optimization_recommendations'
        ]
    
    def get_validation_result(self, obj):
        """Get validation result for targeting."""
        try:
            return obj.validate_targeting()
        except Exception:
            return {'valid': True, 'warnings': []}
    
    def get_targeting_summary(self, obj):
        """Get targeting summary."""
        try:
            return obj.get_targeting_summary()
        except Exception:
            return {}
    
    def get_reach_estimation(self, obj):
        """Get reach estimation."""
        try:
            return obj.estimate_reach()
        except Exception:
            return {'estimated_reach': 0}
    
    def get_targeting_score(self, obj):
        """Get targeting score."""
        try:
            return obj.calculate_targeting_score()
        except Exception:
            return 0.0
    
    def get_performance_metrics(self, obj):
        """Get performance metrics."""
        try:
            return TargetingService._get_targeting_performance(obj)
        except Exception:
            return {}
    
    def get_optimization_recommendations(self, obj):
        """Get optimization recommendations."""
        try:
            performance = TargetingService._get_targeting_performance(obj)
            return TargetingService._get_optimization_recommendations(obj, performance)
        except Exception:
            return []


class TargetingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Targeting."""
    
    rules = TargetingRuleSerializer(many=True, required=False)
    
    class Meta:
        model = Targeting
        fields = [
            'campaign', 'name', 'description', 'geo_targeting_type',
            'countries', 'regions', 'cities', 'postal_codes', 'coordinates',
            'radius', 'geo_fencing', 'device_targeting', 'os_families',
            'browsers', 'carriers', 'device_models', 'connection_types',
            'age_min', 'age_max', 'genders', 'languages', 'interests',
            'keywords', 'custom_audiences', 'lookalike_audiences',
            'exclude_audiences', 'behavioral_segments', 'contextual_targeting',
            'site_targeting', 'app_targeting', 'content_categories',
            'placement_targeting', 'time_targeting', 'frequency_capping',
            'bid_adjustments', 'rules'
        ]
    
    def validate(self, attrs):
        """Validate targeting data."""
        # Validate age range
        age_min = attrs.get('age_min')
        age_max = attrs.get('age_max')
        
        if age_min and age_max:
            if age_min > age_max:
                raise serializers.ValidationError("age_min cannot be greater than age_max")
        
        # Validate radius if coordinates are provided
        coordinates = attrs.get('coordinates')
        radius = attrs.get('radius')
        
        if coordinates and not radius:
            raise serializers.ValidationError("radius is required when coordinates are provided")
        
        if radius and radius < 0:
            raise serializers.ValidationError("radius cannot be negative")
        
        # Validate bid adjustments
        bid_adjustments = attrs.get('bid_adjustments', {})
        if bid_adjustments:
            for key, value in bid_adjustments.items():
                if not isinstance(value, (int, float)) or value < -100 or value > 100:
                    raise serializers.ValidationError(f"Invalid bid adjustment for {key}: must be between -100 and 100")
        
        return attrs
    
    def validate_age_min(self, value):
        """Validate minimum age."""
        if value and (value < 13 or value > 65):
            raise serializers.ValidationError("age_min must be between 13 and 65")
        return value
    
    def validate_age_max(self, value):
        """Validate maximum age."""
        if value and (value < 13 or value > 65):
            raise serializers.ValidationError("age_max must be between 13 and 65")
        return value
    
    def validate_radius(self, value):
        """Validate radius."""
        if value and value < 0:
            raise serializers.ValidationError("radius cannot be negative")
        return value


class TargetingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Targeting."""
    
    rules = TargetingRuleSerializer(many=True, required=False)
    
    class Meta:
        model = Targeting
        fields = [
            'name', 'description', 'geo_targeting_type', 'countries',
            'regions', 'cities', 'postal_codes', 'coordinates', 'radius',
            'geo_fencing', 'device_targeting', 'os_families', 'browsers',
            'carriers', 'device_models', 'connection_types', 'age_min',
            'age_max', 'genders', 'languages', 'interests', 'keywords',
            'custom_audiences', 'lookalike_audiences', 'exclude_audiences',
            'behavioral_segments', 'contextual_targeting', 'site_targeting',
            'app_targeting', 'content_categories', 'placement_targeting',
            'time_targeting', 'frequency_capping', 'bid_adjustments',
            'rules'
        ]
    
    def validate(self, attrs):
        """Validate targeting update data."""
        # Validate age range
        age_min = attrs.get('age_min')
        age_max = attrs.get('age_max')
        
        if age_min and age_max:
            if age_min > age_max:
                raise serializers.ValidationError("age_min cannot be greater than age_max")
        
        # Validate bid adjustments
        bid_adjustments = attrs.get('bid_adjustments', {})
        if bid_adjustments:
            for key, value in bid_adjustments.items():
                if not isinstance(value, (int, float)) or value < -100 or value > 100:
                    raise serializers.ValidationError(f"Invalid bid adjustment for {key}: must be between -100 and 100")
        
        return attrs
    
    def validate_radius(self, value):
        """Validate radius."""
        if value and value < 0:
            raise serializers.ValidationError("radius cannot be negative")
        return value


class AudienceSegmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating AudienceSegment."""
    
    class Meta:
        model = AudienceSegment
        fields = [
            'advertiser', 'name', 'description', 'segment_type',
            'criteria', 'refresh_frequency', 'is_active', 'is_public', 'tags'
        ]
    
    def validate_criteria(self, value):
        """Validate segment criteria."""
        if not value:
            raise serializers.ValidationError("Criteria cannot be empty")
        return value


class AudienceSegmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating AudienceSegment."""
    
    class Meta:
        model = AudienceSegment
        fields = [
            'name', 'description', 'segment_type', 'criteria',
            'refresh_frequency', 'is_active', 'is_public', 'tags'
        ]
    
    def validate_criteria(self, value):
        """Validate segment criteria."""
        if value and not value:
            raise serializers.ValidationError("Criteria cannot be empty")
        return value


class GeographicTargetingSerializer(serializers.Serializer):
    """Serializer for geographic targeting requests."""
    
    coordinates = serializers.DictField()
    radius = serializers.FloatField(min_value=0)
    
    def validate_coordinates(self, value):
        """Validate coordinates."""
        if 'latitude' not in value or 'longitude' not in value:
            raise serializers.ValidationError("Coordinates must include latitude and longitude")
        
        lat = value['latitude']
        lng = value['longitude']
        
        if not (-90 <= lat <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        
        if not (-180 <= lng <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        
        return value


class DeviceTargetingSerializer(serializers.Serializer):
    """Serializer for device targeting requests."""
    
    device_types = serializers.ListField(child=serializers.CharField())
    os_families = serializers.ListField(child=serializers.CharField())
    browsers = serializers.ListField(child=serializers.CharField())
    connection_types = serializers.ListField(child=serializers.CharField())
    
    def validate_device_types(self, value):
        """Validate device types."""
        valid_devices = ['desktop', 'mobile', 'tablet']
        for device in value:
            if device not in valid_devices:
                raise serializers.ValidationError(f"Invalid device type: {device}")
        return value
    
    def validate_os_families(self, value):
        """Validate OS families."""
        valid_os = ['windows', 'macos', 'linux', 'android', 'ios']
        for os in value:
            if os not in valid_os:
                raise serializers.ValidationError(f"Invalid OS family: {os}")
        return value


class BehavioralTargetingSerializer(serializers.Serializer):
    """Serializer for behavioral targeting requests."""
    
    segment_type = serializers.ChoiceField(choices=['custom', 'lookalike', 'retargeting'])
    criteria = serializers.JSONField()
    description = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate_criteria(self, value):
        """Validate behavioral criteria."""
        if not value:
            raise serializers.ValidationError("Criteria cannot be empty")
        return value


class TargetingOptimizationSerializer(serializers.Serializer):
    """Serializer for targeting optimization requests."""
    
    targeting_id = serializers.UUIDField()
    optimization_goals = serializers.ListField(child=serializers.CharField())
    optimization_type = serializers.ChoiceField(
        choices=['auto', 'manual', 'performance', 'reach', 'efficiency']
    )
    
    def validate_targeting_id(self, value):
        """Validate targeting exists."""
        try:
            Targeting.objects.get(id=value)
        except Targeting.DoesNotExist:
            raise serializers.ValidationError("Targeting not found")
        return value


class TargetingValidationSerializer(serializers.Serializer):
    """Serializer for targeting validation results."""
    
    valid = serializers.BooleanField(read_only=True)
    errors = serializers.ListField(read_only=True)
    warnings = serializers.ListField(read_only=True)
    suggestions = serializers.ListField(read_only=True)


class TargetingSummarySerializer(serializers.Serializer):
    """Serializer for targeting summary."""
    
    geo_targeting = serializers.DictField(read_only=True)
    device_targeting = serializers.DictField(read_only=True)
    demographic_targeting = serializers.DictField(read_only=True)
    behavioral_targeting = serializers.DictField(read_only=True)
    estimated_reach = serializers.IntegerField(read_only=True)
    targeting_score = serializers.FloatField(read_only=True)


class ReachEstimationSerializer(serializers.Serializer):
    """Serializer for reach estimation."""
    
    estimated_reach = serializers.IntegerField(read_only=True)
    confidence_level = serializers.FloatField(read_only=True)
    breakdown = serializers.DictField(read_only=True)
    assumptions = serializers.ListField(read_only=True)


class OverlapCheckSerializer(serializers.Serializer):
    """Serializer for overlap check results."""
    
    overlap_percentage = serializers.FloatField(read_only=True)
    overlapping_criteria = serializers.ListField(read_only=True)
    unique_criteria = serializers.ListField(read_only=True)
    recommendations = serializers.ListField(read_only=True)


class TargetingExpansionSerializer(serializers.Serializer):
    """Serializer for targeting expansion suggestions."""
    
    expansion_type = serializers.CharField(read_only=True)
    suggestions = serializers.ListField(read_only=True)
    estimated_reach_increase = serializers.IntegerField(read_only=True)
    confidence_score = serializers.FloatField(read_only=True)


class OptimizationReportSerializer(serializers.Serializer):
    """Serializer for optimization report."""
    
    targeting = serializers.DictField(read_only=True)
    current_performance = serializers.DictField(read_only=True)
    optimization_history = serializers.ListField(read_only=True)
    recommendations = serializers.ListField(read_only=True)
    estimated_improvement = serializers.DictField(read_only=True)


# Response serializers for API responses

class TargetingListResponseSerializer(serializers.Serializer):
    """Serializer for targeting list response."""
    
    targetings = TargetingSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)


class TargetingDetailResponseSerializer(serializers.Serializer):
    """Serializer for targeting detail response."""
    
    targeting = TargetingDetailSerializer(read_only=True)
    validation_result = TargetingValidationSerializer(read_only=True)
    reach_estimation = ReachEstimationSerializer(read_only=True)
    optimization_recommendations = serializers.ListField(read_only=True)


class AudienceSegmentListResponseSerializer(serializers.Serializer):
    """Serializer for audience segment list response."""
    
    segments = AudienceSegmentSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)


class AudienceSegmentDetailResponseSerializer(serializers.Serializer):
    """Serializer for audience segment detail response."""
    
    segment = AudienceSegmentDetailSerializer(read_only=True)
    insights = serializers.DictField(read_only=True)
    performance_metrics = serializers.DictField(read_only=True)


class TargetingActionResponseSerializer(serializers.Serializer):
    """Serializer for targeting action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class OptimizationResponseSerializer(serializers.Serializer):
    """Serializer for optimization response."""
    
    optimization_applied = serializers.BooleanField(read_only=True)
    applied_recommendations = serializers.ListField(read_only=True)
    new_targeting_score = serializers.FloatField(read_only=True)
    performance_improvement = serializers.DictField(read_only=True)


class GeographicDataSerializer(serializers.Serializer):
    """Serializer for geographic data."""
    
    countries = serializers.ListField(read_only=True)
    cities = serializers.ListField(read_only=True)
    regions = serializers.ListField(read_only=True)


class DeviceStatisticsSerializer(serializers.Serializer):
    """Serializer for device statistics."""
    
    device_performance = serializers.DictField(read_only=True)
    os_performance = serializers.DictField(read_only=True)
    browser_performance = serializers.DictField(read_only=True)
    recommendations = serializers.ListField(read_only=True)


class BehavioralDataSerializer(serializers.Serializer):
    """Serializer for behavioral data."""
    
    browsing_history = serializers.ListField(read_only=True)
    search_patterns = serializers.ListField(read_only=True)
    purchase_history = serializers.ListField(read_only=True)
    engagement_patterns = serializers.ListField(read_only=True)
