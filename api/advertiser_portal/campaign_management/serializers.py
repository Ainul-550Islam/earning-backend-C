"""
Campaign Management Serializers

This module contains Django REST Framework serializers for campaign
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..database_models.campaign_model import Campaign, CampaignSpend, CampaignGroup
from ..database_models.targeting_model import Targeting
from ..database_models.creative_model import Creative
from ..database_models.analytics_model import AnalyticsReport
from ..enums import *
from ..validators import *


class TargetingSerializer(serializers.ModelSerializer):
    """Serializer for Targeting model."""
    
    class Meta:
        model = Targeting
        fields = [
            'id', 'campaign', 'name', 'description', 'geo_targeting_type',
            'countries', 'regions', 'cities', 'postal_codes', 'device_targeting',
            'os_families', 'browsers', 'carriers', 'device_models', 'age_min',
            'age_max', 'genders', 'languages', 'interests', 'keywords',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'created_at', 'updated_at']


class CampaignSpendSerializer(serializers.ModelSerializer):
    """Serializer for CampaignSpend model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = CampaignSpend
        fields = [
            'id', 'campaign', 'campaign_name', 'date', 'hour', 'impressions',
            'clicks', 'conversions', 'cost', 'revenue', 'ctr', 'cpc', 'cpa',
            'conversion_rate', 'created_at'
        ]
        read_only_fields = ['id', 'campaign', 'campaign_name', 'created_at']


class CampaignGroupSerializer(serializers.ModelSerializer):
    """Serializer for CampaignGroup model."""
    
    campaign_count = serializers.SerializerMethodField()
    total_budget = serializers.SerializerMethodField()
    total_spend = serializers.SerializerMethodField()
    
    class Meta:
        model = CampaignGroup
        fields = [
            'id', 'advertiser', 'name', 'description', 'color', 'icon',
            'campaign_count', 'total_budget', 'total_spend', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign_count', 'total_budget', 'total_spend', 'created_at', 'updated_at']
    
    def get_campaign_count(self, obj):
        """Get number of campaigns in group."""
        return obj.campaigns.filter(is_deleted=False).count()
    
    def get_total_budget(self, obj):
        """Get total budget of all campaigns in group."""
        total = obj.campaigns.filter(is_deleted=False).aggregate(
            total=models.Sum('total_budget')
        )['total'] or 0
        return float(total)
    
    def get_total_spend(self, obj):
        """Get total spend of all campaigns in group."""
        total = obj.campaigns.filter(is_deleted=False).aggregate(
            total=models.Sum('current_spend')
        )['total'] or 0
        return float(total)


class CampaignSerializer(serializers.ModelSerializer):
    """Serializer for Campaign model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    targeting = TargetingSerializer(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'objective', 'bidding_strategy', 'target_cpa', 'target_roas',
            'daily_budget', 'total_budget', 'start_date', 'end_date',
            'delivery_method', 'start_time', 'end_time', 'days_of_week',
            'timezone', 'frequency_cap', 'frequency_cap_period',
            'device_targeting', 'platform_targeting', 'geo_targeting',
            'audience_targeting', 'language_targeting', 'content_targeting',
            'auto_optimize', 'optimization_goals', 'learning_phase',
            'bid_adjustments', 'bid_floor', 'bid_ceiling', 'conversion_window',
            'attribution_model', 'status', 'is_active', 'quality_score',
            'performance_score', 'campaign_groups', 'labels', 'targeting',
            'current_spend', 'remaining_budget', 'budget_utilization',
            'total_impressions', 'total_clicks', 'total_conversions',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'targeting', 'quality_score',
            'performance_score', 'current_spend', 'remaining_budget',
            'budget_utilization', 'total_impressions', 'total_clicks',
            'total_conversions', 'created_at', 'updated_at'
        ]


class CampaignDetailSerializer(CampaignSerializer):
    """Detailed serializer for Campaign model with additional fields."""
    
    spend_history = CampaignSpendSerializer(
        source='campaign_spends',
        many=True,
        read_only=True
    )
    campaign_groups_details = CampaignGroupSerializer(
        source='campaign_groups_objects',
        many=True,
        read_only=True
    )
    recent_creatives = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    
    class Meta(CampaignSerializer.Meta):
        fields = CampaignSerializer.Meta.fields + [
            'spend_history', 'campaign_groups_details', 'recent_creatives',
            'performance_summary'
        ]
    
    def get_recent_creatives(self, obj):
        """Get recent creatives for campaign."""
        creatives = obj.creatives.filter(is_deleted=False).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(creative.id),
                'name': creative.name,
                'creative_type': creative.creative_type,
                'status': creative.status,
                'created_at': creative.created_at
            }
            for creative in creatives
        ]
    
    def get_performance_summary(self, obj):
        """Get performance summary for campaign."""
        try:
            return obj.get_performance_metrics()
        except Exception:
            return {}


class CampaignCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Campaign."""
    
    targeting = TargetingSerializer(required=False)
    
    class Meta:
        model = Campaign
        fields = [
            'advertiser', 'name', 'description', 'objective', 'bidding_strategy',
            'target_cpa', 'target_roas', 'daily_budget', 'total_budget',
            'start_date', 'end_date', 'delivery_method', 'start_time',
            'end_time', 'days_of_week', 'timezone', 'frequency_cap',
            'frequency_cap_period', 'device_targeting', 'platform_targeting',
            'geo_targeting', 'audience_targeting', 'language_targeting',
            'content_targeting', 'auto_optimize', 'optimization_goals',
            'learning_phase', 'bid_adjustments', 'bid_floor', 'bid_ceiling',
            'conversion_window', 'attribution_model', 'campaign_groups',
            'labels', 'external_campaign_id', 'integration_settings',
            'auto_pause_on_budget_exhaust', 'auto_restart_on_budget_refill',
            'require_approval', 'targeting'
        ]
    
    def validate(self, attrs):
        """Validate campaign data."""
        # Validate date range
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date")
        
        # Validate budget
        daily_budget = attrs.get('daily_budget')
        total_budget = attrs.get('total_budget')
        
        if daily_budget and total_budget:
            if daily_budget > total_budget:
                raise serializers.ValidationError("Daily budget cannot exceed total budget")
        
        # Validate bidding strategy and targets
        bidding_strategy = attrs.get('bidding_strategy')
        target_cpa = attrs.get('target_cpa')
        target_roas = attrs.get('target_roas')
        
        if bidding_strategy == BiddingStrategyEnum.TARGET_CPA.value and not target_cpa:
            raise serializers.ValidationError("Target CPA is required for Target CPA bidding")
        
        if bidding_strategy == BiddingStrategyEnum.TARGET_ROAS.value and not target_roas:
            raise serializers.ValidationError("Target ROAS is required for Target ROAS bidding")
        
        return attrs
    
    def validate_start_date(self, value):
        """Validate start date."""
        if value < date.today():
            raise serializers.ValidationError("Start date cannot be in the past")
        return value
    
    def validate_daily_budget(self, value):
        """Validate daily budget."""
        if value <= 0:
            raise serializers.ValidationError("Daily budget must be positive")
        return value
    
    def validate_total_budget(self, value):
        """Validate total budget."""
        if value <= 0:
            raise serializers.ValidationError("Total budget must be positive")
        return value


class CampaignUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Campaign."""
    
    targeting = TargetingSerializer(required=False)
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'description', 'objective', 'bidding_strategy',
            'target_cpa', 'target_roas', 'daily_budget', 'total_budget',
            'end_date', 'delivery_method', 'start_time', 'end_time',
            'days_of_week', 'timezone', 'frequency_cap', 'frequency_cap_period',
            'device_targeting', 'platform_targeting', 'geo_targeting',
            'audience_targeting', 'language_targeting', 'content_targeting',
            'auto_optimize', 'optimization_goals', 'learning_phase',
            'bid_adjustments', 'bid_floor', 'bid_ceiling', 'conversion_window',
            'attribution_model', 'campaign_groups', 'labels',
            'auto_pause_on_budget_exhaust', 'auto_restart_on_budget_refill',
            'require_approval', 'targeting'
        ]
    
    def validate(self, attrs):
        """Validate campaign update data."""
        # Validate end date if provided
        if 'end_date' in attrs:
            instance = self.instance
            if instance and attrs['end_date'] <= instance.start_date:
                raise serializers.ValidationError("End date must be after start date")
        
        # Validate budget changes
        daily_budget = attrs.get('daily_budget')
        total_budget = attrs.get('total_budget')
        
        if daily_budget and total_budget:
            if daily_budget > total_budget:
                raise serializers.ValidationError("Daily budget cannot exceed total budget")
        
        return attrs


class CampaignOptimizationSerializer(serializers.Serializer):
    """Serializer for campaign optimization requests."""
    
    campaign_id = serializers.UUIDField()
    optimization_type = serializers.ChoiceField(
        choices=['auto', 'manual', 'creative', 'targeting', 'budget']
    )
    parameters = serializers.JSONField(required=False, default={})
    
    def validate_campaign_id(self, value):
        """Validate campaign exists."""
        try:
            Campaign.objects.get(id=value, is_deleted=False)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        return value


class CampaignTargetingSerializer(serializers.Serializer):
    """Serializer for campaign targeting requests."""
    
    campaign_id = serializers.UUIDField()
    targeting_data = TargetingSerializer()
    
    def validate_campaign_id(self, value):
        """Validate campaign exists."""
        try:
            Campaign.objects.get(id=value, is_deleted=False)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        return value


class CampaignAnalyticsSerializer(serializers.Serializer):
    """Serializer for campaign analytics requests."""
    
    campaign_id = serializers.UUIDField()
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
    
    def validate_campaign_id(self, value):
        """Validate campaign exists."""
        try:
            Campaign.objects.get(id=value, is_deleted=False)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
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


class CampaignBudgetSerializer(serializers.Serializer):
    """Serializer for campaign budget requests."""
    
    campaign_id = serializers.UUIDField()
    budget = serializers.DictField()
    
    def validate_campaign_id(self, value):
        """Validate campaign exists."""
        try:
            Campaign.objects.get(id=value, is_deleted=False)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        return value
    
    def validate_budget(self, value):
        """Validate budget data."""
        if 'daily_budget' in value:
            if value['daily_budget'] <= 0:
                raise serializers.ValidationError("Daily budget must be positive")
        
        if 'total_budget' in value:
            if value['total_budget'] <= 0:
                raise serializers.ValidationError("Total budget must be positive")
        
        return value


class CampaignPerformanceSerializer(serializers.Serializer):
    """Serializer for campaign performance data."""
    
    basic_metrics = serializers.DictField(read_only=True)
    efficiency_metrics = serializers.DictField(read_only=True)
    quality_metrics = serializers.DictField(read_only=True)
    budget_metrics = serializers.DictField(read_only=True)
    targeting_metrics = serializers.DictField(read_only=True)


class CampaignListResponseSerializer(serializers.Serializer):
    """Serializer for campaign list response."""
    
    campaigns = CampaignSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)


class CampaignDetailResponseSerializer(serializers.Serializer):
    """Serializer for campaign detail response."""
    
    campaign = CampaignDetailSerializer(read_only=True)
    performance = CampaignPerformanceSerializer(read_only=True)
    targeting = TargetingSerializer(read_only=True, required=False)
    spend_history = CampaignSpendSerializer(many=True, read_only=True)


class OptimizationReportSerializer(serializers.Serializer):
    """Serializer for optimization report."""
    
    campaign = serializers.DictField(read_only=True)
    performance = CampaignPerformanceSerializer(read_only=True)
    recommendations = serializers.ListField(read_only=True)
    optimization_history = serializers.ListField(read_only=True)


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


class AnalyticsDataSerializer(serializers.Serializer):
    """Serializer for analytics data."""
    
    campaign = serializers.DictField(read_only=True)
    metrics = serializers.DictField(read_only=True)
    daily_breakdown = serializers.ListField(read_only=True)
    hourly_breakdown = serializers.ListField(read_only=True)


class BudgetSummarySerializer(serializers.Serializer):
    """Serializer for budget summary."""
    
    budget_settings = serializers.DictField(read_only=True)
    spend_tracking = serializers.DictField(read_only=True)
    alerts = serializers.ListField(read_only=True)


class BudgetAlertSerializer(serializers.Serializer):
    """Serializer for budget alerts."""
    
    type = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    value = serializers.FloatField(read_only=True)


# Response serializers for API responses

class CampaignActionResponseSerializer(serializers.Serializer):
    """Serializer for campaign action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class CampaignDuplicateResponseSerializer(serializers.Serializer):
    """Serializer for campaign duplication response."""
    
    campaign = CampaignDetailSerializer(read_only=True)
    message = serializers.CharField(read_only=True)


class ReportGenerationResponseSerializer(serializers.Serializer):
    """Serializer for report generation response."""
    
    message = serializers.CharField(read_only=True)
    file_path = serializers.CharField(read_only=True)
    report_id = serializers.UUIDField(read_only=True)
