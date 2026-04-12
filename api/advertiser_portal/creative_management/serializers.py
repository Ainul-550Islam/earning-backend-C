"""
Creative Management Serializers

This module contains Django REST Framework serializers for creative
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..database_models.creative_model import Creative, CreativeAsset, CreativeApprovalLog
from ..database_models.campaign_model import Campaign
from ..database_models.analytics_model import AnalyticsReport
from ..enums import *
from ..validators import *


class CreativeAssetSerializer(serializers.ModelSerializer):
    """Serializer for CreativeAsset model."""
    
    class Meta:
        model = CreativeAsset
        fields = [
            'id', 'creative', 'asset_type', 'asset_path', 'asset_name',
            'asset_size', 'asset_mime_type', 'asset_url', 'created_at'
        ]
        read_only_fields = ['id', 'creative', 'created_at']


class CreativeApprovalLogSerializer(serializers.ModelSerializer):
    """Serializer for CreativeApprovalLog model."""
    
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = CreativeApprovalLog
        fields = [
            'id', 'creative', 'action', 'reviewed_by', 'reviewed_by_username',
            'notes', 'created_at'
        ]
        read_only_fields = ['id', 'creative', 'reviewed_by_username', 'created_at']


class CreativeSerializer(serializers.ModelSerializer):
    """Serializer for Creative model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    assets = CreativeAssetSerializer(many=True, read_only=True)
    
    class Meta:
        model = Creative
        fields = [
            'id', 'advertiser', 'advertiser_name', 'campaign', 'campaign_name',
            'name', 'description', 'creative_type', 'file_path', 'file_name',
            'file_size', 'file_mime_type', 'file_hash', 'width', 'height',
            'duration', 'aspect_ratio', 'file_format', 'color_scheme',
            'brand_colors', 'text_content', 'call_to_action', 'landing_page_url',
            'display_url', 'third_party_tracking_urls', 'click_tracking_url',
            'impression_tracking_url', 'dynamic_creative', 'template_id',
            'template_data', 'personalization_rules', 'ad_variations',
            'fallback_creative', 'status', 'approval_status', 'quality_score',
            'performance_score', 'labels', 'external_creative_id',
            'integration_settings', 'auto_optimize', 'optimization_goals',
            'require_approval', 'assets', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'campaign', 'campaign_name',
            'file_path', 'file_hash', 'quality_score', 'performance_score',
            'assets', 'created_at', 'updated_at'
        ]


class CreativeDetailSerializer(CreativeSerializer):
    """Detailed serializer for Creative model with additional fields."""
    
    approval_history = CreativeApprovalLogSerializer(
        source='approval_logs',
        many=True,
        read_only=True
    )
    recent_performance = serializers.SerializerMethodField()
    optimization_recommendations = serializers.SerializerMethodField()
    
    class Meta(CreativeSerializer.Meta):
        fields = CreativeSerializer.Meta.fields + [
            'approval_history', 'recent_performance', 'optimization_recommendations'
        ]
    
    def get_recent_performance(self, obj):
        """Get recent performance for creative."""
        try:
            return obj.get_performance_metrics()
        except Exception:
            return {}
    
    def get_optimization_recommendations(self, obj):
        """Get optimization recommendations for creative."""
        try:
            return obj.get_optimization_recommendations()
        except Exception:
            return []


class CreativeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Creative."""
    
    assets = CreativeAssetSerializer(many=True, required=False)
    
    class Meta:
        model = Creative
        fields = [
            'advertiser', 'campaign', 'name', 'description', 'creative_type',
            'file', 'width', 'height', 'duration', 'aspect_ratio', 'file_format',
            'color_scheme', 'brand_colors', 'text_content', 'call_to_action',
            'landing_page_url', 'display_url', 'third_party_tracking_urls',
            'click_tracking_url', 'impression_tracking_url', 'dynamic_creative',
            'template_id', 'template_data', 'personalization_rules',
            'ad_variations', 'fallback_creative', 'labels', 'external_creative_id',
            'integration_settings', 'auto_optimize', 'optimization_goals',
            'require_approval', 'assets'
        ]
    
    def validate(self, attrs):
        """Validate creative data."""
        # Validate file for creative type
        creative_file = attrs.get('file')
        creative_type = attrs.get('creative_type')
        
        if creative_file and creative_type:
            if not CreativeService.validate_file(creative_file, creative_type):
                raise serializers.ValidationError("Invalid file for this creative type")
        
        # Validate dimensions
        width = attrs.get('width')
        height = attrs.get('height')
        
        if width and height:
            if width <= 0 or height <= 0:
                raise serializers.ValidationError("Width and height must be positive")
        
        # Validate duration for video creatives
        duration = attrs.get('duration')
        if duration and duration <= 0:
            raise serializers.ValidationError("Duration must be positive")
        
        # Validate aspect ratio
        aspect_ratio = attrs.get('aspect_ratio')
        if aspect_ratio:
            try:
                ratio = float(aspect_ratio)
                if ratio <= 0:
                    raise serializers.ValidationError("Aspect ratio must be positive")
            except ValueError:
                raise serializers.ValidationError("Invalid aspect ratio format")
        
        # Validate URLs
        landing_page_url = attrs.get('landing_page_url')
        if landing_page_url:
            from django.core.validators import URLValidator
            validator = URLValidator()
            validator(landing_page_url)
        
        return attrs
    
    def validate_file(self, value):
        """Validate uploaded file."""
        if value:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if value.size > max_size:
                raise serializers.ValidationError("File size cannot exceed 10MB")
        return value
    
    def validate_width(self, value):
        """Validate width."""
        if value and value <= 0:
            raise serializers.ValidationError("Width must be positive")
        return value
    
    def validate_height(self, value):
        """Validate height."""
        if value and value <= 0:
            raise serializers.ValidationError("Height must be positive")
        return value
    
    def validate_duration(self, value):
        """Validate duration."""
        if value and value <= 0:
            raise serializers.ValidationError("Duration must be positive")
        return value
    
    def validate_landing_page_url(self, value):
        """Validate landing page URL."""
        if value:
            from django.core.validators import URLValidator
            validator = URLValidator()
            try:
                validator(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid URL format")
        return value
    
    def validate_third_party_tracking_urls(self, value):
        """Validate third-party tracking URLs."""
        if value:
            from django.core.validators import URLValidator
            validator = URLValidator()
            for url in value:
                try:
                    validator(url)
                except ValidationError:
                    raise serializers.ValidationError(f"Invalid URL: {url}")
        return value


class CreativeUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Creative."""
    
    assets = CreativeAssetSerializer(many=True, required=False)
    
    class Meta:
        model = Creative
        fields = [
            'name', 'description', 'landing_page_url', 'display_url',
            'call_to_action', 'text_content', 'color_scheme', 'brand_colors',
            'third_party_tracking_urls', 'click_tracking_url',
            'impression_tracking_url', 'dynamic_creative', 'template_id',
            'template_data', 'personalization_rules', 'ad_variations',
            'fallback_creative', 'labels', 'external_creative_id',
            'integration_settings', 'auto_optimize', 'optimization_goals',
            'require_approval', 'assets'
        ]
    
    def validate_landing_page_url(self, value):
        """Validate landing page URL."""
        if value:
            from django.core.validators import URLValidator
            validator = URLValidator()
            try:
                validator(value)
            except ValidationError:
                raise serializers.ValidationError("Invalid URL format")
        return value
    
    def validate_third_party_tracking_urls(self, value):
        """Validate third-party tracking URLs."""
        if value:
            from django.core.validators import URLValidator
            validator = URLValidator()
            for url in value:
                try:
                    validator(url)
                except ValidationError:
                    raise serializers.ValidationError(f"Invalid URL: {url}")
        return value


class CreativeOptimizationSerializer(serializers.Serializer):
    """Serializer for creative optimization requests."""
    
    creative_id = serializers.UUIDField()
    optimization_type = serializers.ChoiceField(
        choices=['auto', 'manual', 'text', 'visual', 'performance']
    )
    parameters = serializers.JSONField(required=False, default={})
    
    def validate_creative_id(self, value):
        """Validate creative exists."""
        try:
            Creative.objects.get(id=value, is_deleted=False)
        except Creative.DoesNotExist:
            raise serializers.ValidationError("Creative not found")
        return value


class CreativeAnalyticsSerializer(serializers.Serializer):
    """Serializer for creative analytics requests."""
    
    creative_id = serializers.UUIDField()
    date_range = serializers.DictField(
        child=serializers.CharField(),
        required=False
    )
    metrics = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    dimensions = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_creative_id(self, value):
        """Validate creative exists."""
        try:
            Creative.objects.get(id=value, is_deleted=False)
        except Creative.DoesNotExist:
            raise serializers.ValidationError("Creative not found")
        return value
    
    def validate_date_range(self, value):
        """Validate date range format."""
        if 'start_date' in value:
            try:
                date.fromisoformat(value['start_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid start_date format")
        
        if 'end_date' in value:
            try:
                date.fromisoformat(value['end_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid end_date format")
        
        return value


class CreativeAssetCreateSerializer(serializers.Serializer):
    """Serializer for creating creative assets."""
    
    creative_id = serializers.UUIDField()
    asset_type = serializers.ChoiceField(
        choices=['image', 'video', 'audio', 'document', 'icon', 'logo', 'banner']
    )
    asset_path = serializers.CharField(required=False)
    asset_name = serializers.CharField()
    asset_size = serializers.IntegerField(required=False, default=0)
    mime_type = serializers.CharField(required=False)
    asset_url = serializers.URLField(required=False)
    
    def validate_creative_id(self, value):
        """Validate creative exists."""
        try:
            Creative.objects.get(id=value, is_deleted=False)
        except Creative.DoesNotExist:
            raise serializers.ValidationError("Creative not found")
        return value
    
    def validate_asset_size(self, value):
        """Validate asset size."""
        if value and value < 0:
            raise serializers.ValidationError("Asset size cannot be negative")
        return value


class CreativeApprovalSerializer(serializers.Serializer):
    """Serializer for creative approval actions."""
    
    creative_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_creative_id(self, value):
        """Validate creative exists."""
        try:
            Creative.objects.get(id=value, is_deleted=False)
        except Creative.DoesNotExist:
            raise serializers.ValidationError("Creative not found")
        return value


class CreativePerformanceSerializer(serializers.Serializer):
    """Serializer for creative performance data."""
    
    basic_metrics = serializers.DictField(read_only=True)
    efficiency_metrics = serializers.DictField(read_only=True)
    quality_metrics = serializers.DictField(read_only=True)
    engagement_metrics = serializers.DictField(read_only=True)


class CreativeListResponseSerializer(serializers.Serializer):
    """Serializer for creative list response."""
    
    creatives = CreativeSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)


class CreativeDetailResponseSerializer(serializers.Serializer):
    """Serializer for creative detail response."""
    
    creative = CreativeDetailSerializer(read_only=True)
    performance = CreativePerformanceSerializer(read_only=True)
    assets = CreativeAssetSerializer(many=True, read_only=True)
    approval_history = CreativeApprovalLogSerializer(many=True, read_only=True)


class OptimizationReportSerializer(serializers.Serializer):
    """Serializer for optimization report."""
    
    creative = serializers.DictField(read_only=True)
    performance = CreativePerformanceSerializer(read_only=True)
    recommendations = serializers.ListField(read_only=True)
    optimization_history = serializers.ListField(read_only=True)


class AnalyticsDataSerializer(serializers.Serializer):
    """Serializer for analytics data."""
    
    creative = serializers.DictField(read_only=True)
    metrics = serializers.DictField(read_only=True)
    daily_breakdown = serializers.ListField(read_only=True)
    hourly_breakdown = serializers.ListField(read_only=True)


class ApprovalHistorySerializer(serializers.Serializer):
    """Serializer for approval history."""
    
    history = serializers.ListField(read_only=True)
    total_entries = serializers.IntegerField(read_only=True)


class AssetListSerializer(serializers.Serializer):
    """Serializer for asset list."""
    
    assets = CreativeAssetSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)


# Response serializers for API responses

class CreativeActionResponseSerializer(serializers.Serializer):
    """Serializer for creative action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class CreativeDuplicateResponseSerializer(serializers.Serializer):
    """Serializer for creative duplication response."""
    
    creative = CreativeDetailSerializer(read_only=True)
    message = serializers.CharField(read_only=True)


class ReportGenerationResponseSerializer(serializers.Serializer):
    """Serializer for report generation response."""
    
    message = serializers.CharField(read_only=True)
    file_path = serializers.CharField(read_only=True)
    report_id = serializers.UUIDField(read_only=True)


class AssetActionResponseSerializer(serializers.Serializer):
    """Serializer for asset action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    asset = CreativeAssetSerializer(read_only=True, required=False)
