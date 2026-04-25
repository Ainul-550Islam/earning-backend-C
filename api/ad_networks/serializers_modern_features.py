"""
api/ad_networks/serializers_modern_features.py
Serializers for modern features based on internet research
SaaS-ready with tenant support
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import json

from .models_modern_features import (
    RealTimeBid, PredictiveAnalytics, PrivacyCompliance, ProgrammaticCampaign,
    MLFraudDetection, CrossPlatformAttribution, DynamicCreative, VoiceAd,
    Web3Transaction, MetaverseAd
)

User = get_user_model()


# ==================== MODERN FEATURES SERIALIZERS ====================

class RealTimeBidSerializer(serializers.ModelSerializer):
    """Serializer for Real-time Bidding"""
    
    class Meta:
        model = RealTimeBid
        fields = [
            'id', 'bid_id', 'ad_network', 'offer', 'user', 'bid_amount',
            'floor_price', 'bid_type', 'bid_time', 'response_time_ms',
            'win_notification_sent', 'tenant_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['bid_time', 'created_at', 'updated_at']
    
    def validate_bid_amount(self, value):
        """Validate bid amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Bid amount must be positive")
        return value
    
    def validate_response_time_ms(self, value):
        """Validate response time is reasonable"""
        if value and value > 1000:  # 1 second max
            raise serializers.ValidationError("Response time must be less than 1000ms")
        return value


class PredictiveAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for Predictive Analytics"""
    
    class Meta:
        model = PredictiveAnalytics
        fields = [
            'id', 'prediction_id', 'offer', 'model_type', 'model_version',
            'confidence_score', 'prediction_value', 'actual_value',
            'training_data_points', 'last_trained_at', 'tenant_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['training_data_points', 'created_at', 'updated_at']
    
    def validate_confidence_score(self, value):
        """Validate confidence score is between 0 and 1"""
        if value and not (0 <= value <= 1):
            raise serializers.ValidationError("Confidence score must be between 0 and 1")
        return value
    
    def to_representation(self, instance):
        """Add calculated fields"""
        data = super().to_representation(instance)
        
        # Add accuracy if actual value exists
        if instance.actual_value and instance.prediction_value:
            accuracy = abs(1 - (instance.actual_value - instance.prediction_value) / instance.prediction_value)
            data['accuracy'] = round(accuracy, 4)
        
        return data


class PrivacyComplianceSerializer(serializers.ModelSerializer):
    """Serializer for Privacy Compliance"""
    
    class Meta:
        model = PrivacyCompliance
        fields = [
            'id', 'consent_id', 'user', 'compliance_framework', 'consent_given',
            'consent_timestamp', 'consent_purpose', 'data_retention_days',
            'do_not_sell', 'data_deletion_requested', 'data_deletion_completed',
            'ip_address', 'user_agent', 'geolocation', 'tenant_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['consent_timestamp', 'ip_address', 'user_agent', 'created_at', 'updated_at']
    
    def validate_data_retention_days(self, value):
        """Validate data retention days"""
        if value and (value < 30 or value > 2555):  # GDPR limits
            raise serializers.ValidationError("Data retention days must be between 30 and 2555")
        return value
    
    def validate_consent_purpose(self, value):
        """Validate consent purpose is not empty"""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Consent purpose must be at least 10 characters")
        return value


class ProgrammaticCampaignSerializer(serializers.ModelSerializer):
    """Serializer for Programmatic Campaigns"""
    
    class Meta:
        model = ProgrammaticCampaign
        fields = [
            'id', 'campaign_id', 'name', 'ad_network', 'demand_side_platform',
            'supply_side_platform', 'ad_exchange', 'bidding_strategy',
            'target_audience', 'target_geography', 'target_devices', 'target_time',
            'impressions', 'clicks', 'conversions', 'spend', 'tenant_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['impressions', 'clicks', 'conversions', 'created_at', 'updated_at']
    
    def validate_spend(self, value):
        """Validate spend is non-negative"""
        if value and value < 0:
            raise serializers.ValidationError("Spend cannot be negative")
        return value
    
    def validate_targeting(self, value):
        """Validate targeting JSON fields"""
        if value and isinstance(value, dict):
            for field_name, field_value in value.items():
                if not isinstance(field_value, (dict, list)):
                    raise serializers.ValidationError(f"Targeting field '{field_name}' must be a valid JSON object or array")
        return value


class MLFraudDetectionSerializer(serializers.ModelSerializer):
    """Serializer for ML Fraud Detection"""
    
    class Meta:
        model = MLFraudDetection
        fields = [
            'id', 'detection_id', 'user', 'offer', 'model_name', 'model_version',
            'confidence_score', 'fraud_type', 'risk_score', 'risk_level',
            'evidence_data', 'ip_address', 'device_fingerprint', 'user_agent',
            'action_taken', 'reviewed_by', 'reviewed_at', 'review_notes',
            'tenant_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['confidence_score', 'evidence_data', 'created_at', 'updated_at']
    
    def validate_risk_score(self, value):
        """Validate risk score is between 0 and 100"""
        if value and not (0 <= value <= 100):
            raise serializers.ValidationError("Risk score must be between 0 and 100")
        return value
    
    def to_representation(self, instance):
        """Add calculated fields"""
        data = super().to_representation(instance)
        
        # Add risk level description
        risk_descriptions = {
            'low': 'Low Risk - Minimal suspicious activity',
            'medium': 'Medium Risk - Some suspicious patterns detected',
            'high': 'High Risk - Strong suspicious patterns detected',
            'critical': 'Critical Risk - Immediate action required'
        }
        data['risk_description'] = risk_descriptions.get(instance.risk_level, 'Unknown Risk Level')
        
        return data


class CrossPlatformAttributionSerializer(serializers.ModelSerializer):
    """Serializer for Cross-Platform Attribution"""
    
    class Meta:
        model = CrossPlatformAttribution
        fields = [
            'id', 'attribution_id', 'user', 'touchpoints', 'attribution_model',
            'conversion_value', 'conversion_currency', 'source_platform', 'source_campaign',
            'source_ad_group', 'source_ad', 'source_keyword', 'attributed_platform',
            'attributed_network', 'attributed_offer', 'first_touch_time',
            'last_touch_time', 'conversion_time', 'attribution_window_hours',
            'tenant_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_conversion_value(self, value):
        """Validate conversion value is positive"""
        if value and value <= 0:
            raise serializers.ValidationError("Conversion value must be positive")
        return value
    
    def validate_attribution_window_hours(self, value):
        """Validate attribution window"""
        if value and (value < 1 or value > 90):  # 1 hour to 90 days
            raise serializers.ValidationError("Attribution window must be between 1 and 90 hours")
        return value


class DynamicCreativeSerializer(serializers.ModelSerializer):
    """Serializer for Dynamic Creative"""
    
    class Meta:
        model = DynamicCreative
        fields = [
            'id', 'creative_id', 'ad_network', 'offer', 'creative_type',
            'base_creative_url', 'dynamic_elements', 'personalization_rules',
            'optimization_model', 'optimization_goal', 'impressions', 'clicks',
            'conversions', 'ctr', 'conversion_rate', 'test_group', 'is_winner',
            'confidence_level', 'tenant_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['impressions', 'clicks', 'conversions', 'ctr', 'conversion_rate', 'created_at', 'updated_at']
    
    def validate_ctr(self, value):
        """Validate CTR is between 0 and 1"""
        if value and not (0 <= value <= 1):
            raise serializers.ValidationError("CTR must be between 0 and 1")
        return value
    
    def validate_conversion_rate(self, value):
        """Validate conversion rate is between 0 and 1"""
        if value and not (0 <= value <= 1):
            raise serializers.ValidationError("Conversion rate must be between 0 and 1")
        return value
    
    def to_representation(self, instance):
        """Add calculated fields"""
        data = super().to_representation(instance)
        
        # Add performance metrics
        if instance.impressions > 0:
            data['ctr_percentage'] = f"{instance.ctr * 100:.2f}%"
        
        if instance.clicks > 0:
            data['conversion_rate_percentage'] = f"{instance.conversion_rate * 100:.2f}%"
        
        return data


class VoiceAdSerializer(serializers.ModelSerializer):
    """Serializer for Voice Ads"""
    
    class Meta:
        model = VoiceAd
        fields = [
            'id', 'ad_id', 'ad_network', 'offer', 'voice_platform', 'ad_format',
            'audio_url', 'audio_duration', 'audio_file_size', 'audio_format',
            'target_demographics', 'target_genres', 'target_time_of_day',
            'plays', 'completions', 'clicks', 'conversions', 'tenant_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['plays', 'completions', 'clicks', 'conversions', 'created_at', 'updated_at']
    
    def validate_audio_duration(self, value):
        """Validate audio duration"""
        if value and (value < 1 or value > 3600):  # 1 second to 1 hour
            raise serializers.ValidationError("Audio duration must be between 1 and 3600 seconds")
        return value
    
    def validate_audio_file_size(self, value):
        """Validate audio file size"""
        if value and (value < 1024 or value > 100 * 1024 * 1024):  # 1KB to 100MB
            raise serializers.ValidationError("Audio file size must be between 1KB and 100MB")
        return value


class Web3TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Web3 Transactions"""
    
    class Meta:
        model = Web3Transaction
        fields = [
            'id', 'transaction_hash', 'blockchain_network', 'ad_network', 'offer', 'user',
            'amount', 'token_symbol', 'gas_fee', 'status', 'contract_address',
            'function_called', 'block_number', 'tenant_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['block_number', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        """Validate transaction amount"""
        if value and value <= 0:
            raise serializers.ValidationError("Transaction amount must be positive")
        return value
    
    def validate_gas_fee(self, value):
        """Validate gas fee"""
        if value and value < 0:
            raise serializers.ValidationError("Gas fee cannot be negative")
        return value
    
    def to_representation(self, instance):
        """Add formatted fields"""
        data = super().to_representation(instance)
        
        # Add blockchain explorer URL
        explorer_urls = {
            'ethereum': f"https://etherscan.io/tx/{instance.transaction_hash}",
            'polygon': f"https://polygonscan.com/tx/{instance.transaction_hash}",
            'bsc': f"https://bscscan.com/tx/{instance.transaction_hash}",
            'avalanche': f"https://snowtrace.io/tx/{instance.transaction_hash}",
        }
        data['explorer_url'] = explorer_urls.get(instance.blockchain_network)
        
        return data


class MetaverseAdSerializer(serializers.ModelSerializer):
    """Serializer for Metaverse Ads"""
    
    class Meta:
        model = MetaverseAd
        fields = [
            'id', 'ad_id', 'metaverse_platform', 'ad_network', 'offer', 'asset_url',
            'asset_type', 'virtual_coordinates', 'virtual_world', 'placement_type',
            'views', 'interactions', 'conversions', 'tenant_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['views', 'interactions', 'conversions', 'created_at', 'updated_at']
    
    def validate_virtual_coordinates(self, value):
        """Validate virtual coordinates JSON"""
        if value and isinstance(value, dict):
            required_fields = ['x', 'y', 'z']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"Virtual coordinates must include {field}")
        return value
    
    def to_representation(self, instance):
        """Add formatted fields"""
        data = super().to_representation(instance)
        
        # Add platform-specific URLs
        platform_urls = {
            'decentraland': f"https://decentraland.org/places/{instance.virtual_world}",
            'sandbox': f"https://www.sandbox.game/en/{instance.virtual_world}",
            'roblox': f"https://www.roblox.com/games/{instance.virtual_world}",
            'fortnite': f"https://fortnitecreative.com/{instance.virtual_world}",
            'minecraft': f"https://minecraft.net/server/{instance.virtual_world}",
        }
        data['platform_url'] = platform_urls.get(instance.metaverse_platform)
        
        return data


# ==================== NESTED SERIALIZERS ====================

class PredictiveAnalyticsNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for predictive analytics"""
    
    class Meta:
        model = PredictiveAnalytics
        fields = ['prediction_id', 'model_type', 'confidence_score', 'prediction_value', 'last_trained_at']


class MLFraudDetectionNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for fraud detection"""
    
    class Meta:
        model = MLFraudDetection
        fields = ['detection_id', 'fraud_type', 'risk_score', 'risk_level', 'action_taken']


class CrossPlatformAttributionNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for attribution"""
    
    class Meta:
        model = CrossPlatformAttribution
        fields = ['attribution_id', 'attribution_model', 'conversion_value', 'source_platform']


# ==================== AGGREGATE SERIALIZERS ====================

class RealTimeBidAggregateSerializer(serializers.Serializer):
    """Aggregate serializer for RTB statistics"""
    
    total_bids = serializers.IntegerField()
    successful_bids = serializers.IntegerField()
    failed_bids = serializers.IntegerField()
    average_bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_response_time = serializers.FloatField()
    win_rate = serializers.FloatField()
    
    def validate_win_rate(self, value):
        """Validate win rate is between 0 and 1"""
        if value and not (0 <= value <= 1):
            raise serializers.ValidationError("Win rate must be between 0 and 1")
        return value


class PredictiveAnalyticsAggregateSerializer(serializers.Serializer):
    """Aggregate serializer for predictive analytics"""
    
    total_predictions = serializers.IntegerField()
    accurate_predictions = serializers.IntegerField()
    accuracy_rate = serializers.FloatField()
    average_confidence = serializers.FloatField()
    models_trained = serializers.IntegerField()
    
    def validate_accuracy_rate(self, value):
        """Validate accuracy rate is between 0 and 1"""
        if value and not (0 <= value <= 1):
            raise serializers.ValidationError("Accuracy rate must be between 0 and 1")
        return value


# ==================== FILTER SERIALIZERS ====================

class RealTimeBidFilterSerializer(serializers.Serializer):
    """Filter serializer for RTB queries"""
    
    bid_type = serializers.ChoiceField(choices=RealTimeBid.BID_TYPES, required=False)
    min_bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    ad_network = serializers.IntegerField(required=False)
    offer = serializers.IntegerField(required=False)
    user = serializers.IntegerField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    
    def validate_date_range(self, attrs):
        """Validate date range"""
        if attrs.get('date_from') and attrs.get('date_to'):
            if attrs['date_from'] > attrs['date_to']:
                raise serializers.ValidationError("date_from must be before date_to")
        return attrs


class PredictiveAnalyticsFilterSerializer(serializers.Serializer):
    """Filter serializer for predictive analytics"""
    
    model_type = serializers.ChoiceField(choices=PredictiveAnalytics.MODEL_TYPES, required=False)
    min_confidence_score = serializers.DecimalField(max_digits=5, decimal_places=4, required=False)
    max_confidence_score = serializers.DecimalField(max_digits=5, decimal_places=4, required=False)
    offer = serializers.IntegerField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    
    def validate_confidence_range(self, attrs):
        """Validate confidence score range"""
        if attrs.get('min_confidence_score') and attrs.get('max_confidence_score'):
            if attrs['min_confidence_score'] > attrs['max_confidence_score']:
                raise serializers.ValidationError("min_confidence_score must be less than max_confidence_score")
        return attrs


# ==================== EXPORTS ====================

__all__ = [
    # Main Serializers
    'RealTimeBidSerializer',
    'PredictiveAnalyticsSerializer',
    'PrivacyComplianceSerializer',
    'ProgrammaticCampaignSerializer',
    'MLFraudDetectionSerializer',
    'CrossPlatformAttributionSerializer',
    'DynamicCreativeSerializer',
    'VoiceAdSerializer',
    'Web3TransactionSerializer',
    'MetaverseAdSerializer',
    
    # Nested Serializers
    'PredictiveAnalyticsNestedSerializer',
    'MLFraudDetectionNestedSerializer',
    'CrossPlatformAttributionNestedSerializer',
    
    # Aggregate Serializers
    'RealTimeBidAggregateSerializer',
    'PredictiveAnalyticsAggregateSerializer',
    
    # Filter Serializers
    'RealTimeBidFilterSerializer',
    'PredictiveAnalyticsFilterSerializer',
]
