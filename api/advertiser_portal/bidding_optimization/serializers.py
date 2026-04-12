"""
Bidding Optimization Serializers

This module provides serializers for bidding optimization including
bids, strategies, budget optimization, and automated bidding.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.bidding_model import Bid, BidStrategy, BidOptimization, BudgetAllocation
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class BidSerializer(serializers.ModelSerializer):
    """Serializer for Bid model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    advertiser_name = serializers.CharField(source='campaign.advertiser.company_name', read_only=True)
    
    class Meta:
        model = Bid
        fields = [
            'id', 'campaign', 'campaign_name', 'advertiser_name',
            'bid_type', 'bid_amount', 'bid_currency', 'targeting_criteria',
            'creative_ids', 'bid_strategy', 'max_bid', 'min_bid',
            'bid_adjustments', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_bid_amount(self, value):
        """Validate bid amount."""
        if value <= 0:
            raise serializers.ValidationError("Bid amount must be positive")
        return value
    
    def validate_max_bid(self, value):
        """Validate maximum bid."""
        if value <= 0:
            raise serializers.ValidationError("Maximum bid must be positive")
        return value
    
    def validate_min_bid(self, value):
        """Validate minimum bid."""
        if value < 0:
            raise serializers.ValidationError("Minimum bid cannot be negative")
        return value
    
    def validate(self, attrs):
        """Validate bid data."""
        max_bid = attrs.get('max_bid')
        min_bid = attrs.get('min_bid')
        bid_amount = attrs.get('bid_amount')
        
        if max_bid and min_bid and min_bid > max_bid:
            raise serializers.ValidationError("Minimum bid cannot be greater than maximum bid")
        
        if bid_amount and max_bid and bid_amount > max_bid:
            raise serializers.ValidationError("Bid amount cannot be greater than maximum bid")
        
        if bid_amount and min_bid and bid_amount < min_bid:
            raise serializers.ValidationError("Bid amount cannot be less than minimum bid")
        
        return attrs


class BidCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bids."""
    
    class Meta:
        model = Bid
        fields = [
            'campaign', 'bid_type', 'bid_amount', 'bid_currency',
            'targeting_criteria', 'creative_ids', 'bid_strategy',
            'max_bid', 'min_bid', 'bid_adjustments'
        ]
    
    def validate_campaign(self, value):
        """Validate campaign exists and belongs to user."""
        try:
            campaign = Campaign.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                if campaign.advertiser != advertiser:
                    raise serializers.ValidationError("Campaign does not belong to advertiser")
            
            return campaign
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class BidOptimizationSerializer(serializers.ModelSerializer):
    """Serializer for BidOptimization model."""
    
    optimized_by_name = serializers.CharField(source='optimized_by.username', read_only=True)
    
    class Meta:
        model = BidOptimization
        fields = [
            'id', 'bid', 'optimization_type', 'old_amount', 'new_amount',
            'optimization_metadata', 'optimized_by', 'optimized_by_name',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BidStrategySerializer(serializers.ModelSerializer):
    """Serializer for BidStrategy model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = BidStrategy
        fields = [
            'id', 'advertiser', 'advertiser_name', 'strategy_type', 'name',
            'description', 'configuration', 'target_metric', 'target_value',
            'bid_limits', 'optimization_rules', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_target_value(self, value):
        """Validate target value."""
        if value <= 0:
            raise serializers.ValidationError("Target value must be positive")
        return value
    
    def validate_configuration(self, value):
        """Validate configuration."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a dictionary")
        return value
    
    def validate_bid_limits(self, value):
        """Validate bid limits."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Bid limits must be a dictionary")
        return value
    
    def validate_optimization_rules(self, value):
        """Validate optimization rules."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Optimization rules must be a list")
        return value


class BidStrategyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bid strategies."""
    
    class Meta:
        model = BidStrategy
        fields = [
            'advertiser', 'strategy_type', 'name', 'description',
            'configuration', 'target_metric', 'target_value',
            'bid_limits', 'optimization_rules', 'is_active'
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


class BudgetAllocationSerializer(serializers.ModelSerializer):
    """Serializer for BudgetAllocation model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    advertiser_name = serializers.CharField(source='campaign.advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = BudgetAllocation
        fields = [
            'id', 'campaign', 'campaign_name', 'advertiser_name',
            'old_budget', 'new_budget', 'optimization_type',
            'target_metric', 'target_value', 'created_by',
            'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BudgetOptimizationRequestSerializer(serializers.Serializer):
    """Serializer for budget optimization requests."""
    
    campaign_id = serializers.UUIDField(required=True)
    optimization_type = serializers.ChoiceField(
        choices=['performance', 'opportunity', 'conservation'],
        default='performance'
    )
    target_metric = serializers.ChoiceField(
        choices=['ctr', 'cpc', 'cpa', 'roas', 'conversions'],
        default='roas'
    )
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    
    def validate_campaign_id(self, value):
        """Validate campaign exists and belongs to user."""
        try:
            campaign = Campaign.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                if campaign.advertiser != advertiser:
                    raise serializers.ValidationError("Campaign does not belong to advertiser")
            
            return campaign
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class BudgetOptimizationResponseSerializer(serializers.Serializer):
    """Serializer for budget optimization responses."""
    
    campaign_id = serializers.UUIDField()
    old_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    new_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    optimization_type = serializers.CharField()
    target_metric = serializers.CharField()
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    allocation_id = serializers.UUIDField()


class PerformanceBiddingConfigSerializer(serializers.Serializer):
    """Serializer for performance bidding configuration."""
    
    target_metric = serializers.ChoiceField(
        choices=['ctr', 'cpc', 'cpa', 'roas', 'conversions'],
        required=True
    )
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    bid_adjustment_factor = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0.1, max_value=5.0, default=1.0)
    optimization_frequency = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly'],
        default='daily'
    )
    max_bid_adjustment = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=1.0, default=0.5)
    min_bid_adjustment = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=1.0, default=0.1)


class PerformanceBiddingRequestSerializer(serializers.Serializer):
    """Serializer for performance bidding requests."""
    
    campaign_id = serializers.UUIDField(required=True)
    config = PerformanceBiddingConfigSerializer(required=True)
    
    def validate_campaign_id(self, value):
        """Validate campaign exists and belongs to user."""
        try:
            campaign = Campaign.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                if campaign.advertiser != advertiser:
                    raise serializers.ValidationError("Campaign does not belong to advertiser")
            
            return campaign
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")


class AutomatedBiddingRuleSerializer(serializers.Serializer):
    """Serializer for automated bidding rules."""
    
    advertiser_id = serializers.UUIDField(required=True)
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    condition = serializers.JSONField(required=True)
    action = serializers.JSONField(required=True)
    is_active = serializers.BooleanField(default=True)
    
    def validate_advertiser_id(self, value):
        """Validate advertiser exists and belongs to user."""
        try:
            advertiser = Advertiser.objects.get(id=value, is_deleted=False)
            user = self.context['request'].user
            
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("Advertiser does not belong to user")
            
            return advertiser
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")
    
    def validate_condition(self, value):
        """Validate condition structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Condition must be a dictionary")
        
        required_fields = ['metric', 'operator', 'value']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Condition must contain '{field}' field")
        
        return value
    
    def validate_action(self, value):
        """Validate action structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Action must be a dictionary")
        
        required_fields = ['type', 'parameters']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Action must contain '{field}' field")
        
        return value


class AutomatedBiddingResponseSerializer(serializers.Serializer):
    """Serializer for automated bidding responses."""
    
    rule_id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    status = serializers.CharField()


class BiddingStatisticsSerializer(serializers.Serializer):
    """Serializer for bidding statistics."""
    
    total_bids = serializers.IntegerField()
    active_bids = serializers.IntegerField()
    bids_by_type = serializers.DictField()
    average_bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class BudgetRecommendationSerializer(serializers.Serializer):
    """Serializer for budget recommendations."""
    
    campaign_id = serializers.UUIDField()
    campaign_name = serializers.CharField()
    current_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    recommended_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField()
    confidence = serializers.DecimalField(max_digits=3, decimal_places=2)


class BudgetRecommendationsResponseSerializer(serializers.Serializer):
    """Serializer for budget recommendations response."""
    
    recommendations = BudgetRecommendationSerializer(many=True)


class AutomatedBiddingRuleListSerializer(serializers.Serializer):
    """Serializer for automated bidding rule list."""
    
    id = serializers.CharField()
    name = serializers.CharField()
    condition = serializers.CharField()
    action = serializers.CharField()
    is_active = serializers.BooleanField()


class AutomatedBiddingRulesResponseSerializer(serializers.Serializer):
    """Serializer for automated bidding rules response."""
    
    rules = AutomatedBiddingRuleListSerializer(many=True)


# Response serializers for various endpoints
class BidCreateResponseSerializer(serializers.Serializer):
    """Serializer for bid creation response."""
    
    id = serializers.UUIDField()
    campaign_id = serializers.UUIDField()
    bid_type = serializers.CharField()
    bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    bid_currency = serializers.CharField()
    bid_strategy = serializers.CharField()
    max_bid = serializers.DecimalField(max_digits=10, decimal_places=2)
    min_bid = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class BidOptimizationResponseSerializer(serializers.Serializer):
    """Serializer for bid optimization response."""
    
    id = serializers.UUIDField()
    bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    optimized_at = serializers.DateTimeField()
    optimization_metadata = serializers.JSONField()


class BidPerformanceResponseSerializer(serializers.Serializer):
    """Serializer for bid performance response."""
    
    bid_id = serializers.UUIDField()
    campaign = serializers.DictField()
    bid_details = serializers.DictField()
    performance_metrics = serializers.DictField()
    optimization_history = serializers.ListField()
    generated_at = serializers.DateTimeField()


class BidStrategyCreateResponseSerializer(serializers.Serializer):
    """Serializer for bid strategy creation response."""
    
    id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    strategy_type = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    target_metric = serializers.CharField()
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class BidStrategyApplicationResponseSerializer(serializers.Serializer):
    """Serializer for bid strategy application response."""
    
    message = serializers.CharField()


class PerformanceBiddingEnableResponseSerializer(serializers.Serializer):
    """Serializer for performance bidding enable response."""
    
    message = serializers.CharField()
