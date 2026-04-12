"""
Retargeting Engines Serializers

This module provides serializers for retargeting operations including
pixels, audience segments, retargeting campaigns, and conversion tracking.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.retargeting_model import RetargetingPixel, AudienceSegment, RetargetingCampaign, ConversionEvent
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class RetargetingCampaignSerializer(serializers.ModelSerializer):
    """Serializer for RetargetingCampaign model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    pixel_name = serializers.CharField(source='pixel.name', read_only=True)
    audience_segment_name = serializers.CharField(source='audience_segment.name', read_only=True)
    activated_by_name = serializers.CharField(source='activated_by.username', read_only=True)
    
    class Meta:
        model = RetargetingCampaign
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'retargeting_type', 'pixel', 'pixel_name', 'audience_segment',
            'audience_segment_name', 'targeting_rules', 'budget_limits',
            'frequency_capping', 'duration_days', 'status', 'activated_at',
            'activated_by', 'activated_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'activated_at', 'activated_by', 'created_at', 'updated_at']
    
    def validate_duration_days(self, value):
        """Validate duration days."""
        if value <= 0:
            raise serializers.ValidationError("Duration days must be positive")
        if value > 365:
            raise serializers.ValidationError("Duration days cannot exceed 365")
        return value
    
    def validate_targeting_rules(self, value):
        """Validate targeting rules."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Targeting rules must be a dictionary")
        return value
    
    def validate_budget_limits(self, value):
        """Validate budget limits."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Budget limits must be a dictionary")
        return value
    
    def validate_frequency_capping(self, value):
        """Validate frequency capping."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Frequency capping must be a dictionary")
        return value


class RetargetingCampaignCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating retargeting campaigns."""
    
    class Meta:
        model = RetargetingCampaign
        fields = [
            'advertiser', 'name', 'description', 'retargeting_type',
            'pixel', 'audience_segment', 'targeting_rules', 'budget_limits',
            'frequency_capping', 'duration_days'
        ]
    
    def validate_advertiser(self, value):
        """Validate advertiser exists and belongs to user."""
        try:
            advertiser = Advertiser.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("Advertiser does not belong to user")
            
            return advertiser
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class RetargetingPixelSerializer(serializers.ModelSerializer):
    """Serializer for RetargetingPixel model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = RetargetingPixel
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'pixel_type', 'pixel_code', 'tracking_url', 'conversion_value',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'pixel_code', 'created_at', 'updated_at']
    
    def validate_conversion_value(self, value):
        """Validate conversion value."""
        if value < 0:
            raise serializers.ValidationError("Conversion value cannot be negative")
        return value


class RetargetingPixelCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating retargeting pixels."""
    
    class Meta:
        model = RetargetingPixel
        fields = [
            'advertiser', 'name', 'description', 'pixel_type',
            'tracking_url', 'conversion_value'
        ]
    
    def validate_advertiser(self, value):
        """Validate advertiser exists and belongs to user."""
        try:
            advertiser = Advertiser.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("Advertiser does not belong to user")
            
            return advertiser
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class AudienceSegmentSerializer(serializers.ModelSerializer):
    """Serializer for AudienceSegment model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AudienceSegment
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'segment_type', 'criteria', 'pixel_ids', 'rules', 'audience_size',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'audience_size', 'created_at', 'updated_at']
    
    def validate_criteria(self, value):
        """Validate criteria."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Criteria must be a dictionary")
        return value
    
    def validate_rules(self, value):
        """Validate rules."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Rules must be a list")
        return value


class AudienceSegmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating audience segments."""
    
    class Meta:
        model = AudienceSegment
        fields = [
            'advertiser', 'name', 'description', 'segment_type',
            'criteria', 'pixel_ids', 'rules'
        ]
    
    def validate_advertiser(self, value):
        """Validate advertiser exists and belongs to user."""
        try:
            advertiser = Advertiser.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("Advertiser does not belong to user")
            
            return advertiser
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class ConversionEventSerializer(serializers.ModelSerializer):
    """Serializer for ConversionEvent model."""
    
    pixel_name = serializers.CharField(source='pixel.name', read_only=True)
    retargeting_campaign_name = serializers.CharField(source='retargeting_campaign.name', read_only=True)
    
    class Meta:
        model = ConversionEvent
        fields = [
            'id', 'pixel', 'pixel_name', 'retargeting_campaign',
            'retargeting_campaign_name', 'event_type', 'conversion_value',
            'user_agent', 'ip_address', 'custom_data', 'event_date'
        ]
        read_only_fields = ['id', 'event_date']
    
    def validate_conversion_value(self, value):
        """Validate conversion value."""
        if value < 0:
            raise serializers.ValidationError("Conversion value cannot be negative")
        return value
    
    def validate_custom_data(self, value):
        """Validate custom data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom data must be a dictionary")
        return value


class PixelCodeResponseSerializer(serializers.Serializer):
    """Serializer for pixel code response."""
    
    pixel_id = serializers.UUIDField()
    pixel_name = serializers.CharField()
    pixel_type = serializers.CharField()
    pixel_code = serializers.CharField()
    tracking_code = serializers.CharField()
    tracking_url = serializers.CharField()
    instructions = serializers.ListField(child=serializers.CharField())


class PixelEventTrackingRequestSerializer(serializers.Serializer):
    """Serializer for pixel event tracking requests."""
    
    event_type = serializers.CharField(default='conversion')
    conversion_value = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    user_agent = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.JSONField(required=False, default=dict)


class RetargetingPerformanceResponseSerializer(serializers.Serializer):
    """Serializer for retargeting performance response."""
    
    campaign_id = serializers.UUIDField()
    campaign_name = serializers.CharField()
    retargeting_type = serializers.CharField()
    date_range = serializers.DictField()
    performance_metrics = serializers.DictField()
    generated_at = serializers.DateTimeField()


class AudienceSegmentUpdateSizeResponseSerializer(serializers.Serializer):
    """Serializer for audience segment size update response."""
    
    message = serializers.CharField()
    audience_size = serializers.IntegerField()


class AudienceInsightsResponseSerializer(serializers.Serializer):
    """Serializer for audience insights response."""
    
    segment_id = serializers.UUIDField()
    segment_name = serializers.CharField()
    audience_size = serializers.IntegerField()
    demographics = serializers.DictField()
    behavior = serializers.DictField()
    engagement = serializers.DictField()


class ConversionTrackingRequestSerializer(serializers.Serializer):
    """Serializer for conversion tracking requests."""
    
    pixel_id = serializers.UUIDField(required=True)
    retargeting_campaign = serializers.UUIDField(required=False)
    event_type = serializers.CharField(default='conversion')
    conversion_value = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    user_agent = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.JSONField(required=False, default=dict)


class ConversionTrackingResponseSerializer(serializers.Serializer):
    """Serializer for conversion tracking response."""
    
    message = serializers.CharField()


class ConversionStatisticsResponseSerializer(serializers.Serializer):
    """Serializer for conversion statistics response."""
    
    pixel_id = serializers.UUIDField()
    pixel_name = serializers.CharField()
    date_range = serializers.DictField()
    statistics = serializers.DictField()
    daily_conversions = serializers.ListField()


class PixelsListResponseSerializer(serializers.Serializer):
    """Serializer for pixels list response."""
    
    pixels = serializers.ListField(child=serializers.DictField())


# Response serializers for various endpoints
class RetargetingCampaignCreateResponseSerializer(serializers.Serializer):
    """Serializer for retargeting campaign creation response."""
    
    id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    retargeting_type = serializers.CharField()
    pixel_id = serializers.UUIDField(allow_null=True)
    audience_segment_id = serializers.UUIDField(allow_null=True)
    targeting_rules = serializers.DictField()
    budget_limits = serializers.DictField()
    frequency_capping = serializers.DictField()
    duration_days = serializers.IntegerField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RetargetingCampaignActivateResponseSerializer(serializers.Serializer):
    """Serializer for retargeting campaign activation response."""
    
    message = serializers.CharField()


class RetargetingCampaignPauseResponseSerializer(serializers.Serializer):
    """Serializer for retargeting campaign pause response."""
    
    message = serializers.CharField()


class RetargetingPixelCreateResponseSerializer(serializers.Serializer):
    """Serializer for retargeting pixel creation response."""
    
    id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    pixel_type = serializers.CharField()
    pixel_code = serializers.CharField()
    tracking_url = serializers.CharField()
    conversion_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class PixelEventTrackingResponseSerializer(serializers.Serializer):
    """Serializer for pixel event tracking response."""
    
    message = serializers.CharField()


class PixelActivateResponseSerializer(serializers.Serializer):
    """Serializer for pixel activation response."""
    
    message = serializers.CharField()


class PixelDeactivateResponseSerializer(serializers.Serializer):
    """Serializer for pixel deactivation response."""
    
    message = serializers.CharField()


class AudienceSegmentCreateResponseSerializer(serializers.Serializer):
    """Serializer for audience segment creation response."""
    
    id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    segment_type = serializers.CharField()
    criteria = serializers.DictField()
    pixel_ids = serializers.ListField()
    rules = serializers.ListField()
    audience_size = serializers.IntegerField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RetargetingStatisticsResponseSerializer(serializers.Serializer):
    """Serializer for retargeting statistics response."""
    
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    campaigns_by_type = serializers.DictField()
