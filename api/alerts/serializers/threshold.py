"""
Threshold Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold, 
    ThresholdHistory, ThresholdProfile
)

User = get_user_model()


class ThresholdConfigSerializer(serializers.ModelSerializer):
    """ThresholdConfig serializer"""
    alert_rule_name = serializers.CharField(source='alert_rule.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ThresholdConfig
        fields = [
            'id', 'alert_rule', 'alert_rule_name', 'threshold_type', 'primary_threshold',
            'secondary_threshold', 'operator', 'time_window_minutes', 'is_active',
            'config', 'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def validate_primary_threshold(self, value):
        if value <= 0:
            raise serializers.ValidationError("Primary threshold must be positive")
        return value
    
    def validate_secondary_threshold(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Secondary threshold must be positive")
        return value
    
    def validate_time_window_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError("Time window must be positive")
        return value


class ThresholdBreachSerializer(serializers.ModelSerializer):
    """ThresholdBreach serializer"""
    threshold_config_name = serializers.CharField(source='threshold_config.name', read_only=True)
    alert_rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = ThresholdBreach
        fields = [
            'id', 'threshold_config', 'threshold_config_name', 'alert_log', 'alert_rule_name',
            'severity', 'breach_value', 'threshold_value', 'breach_percentage',
            'detected_at', 'acknowledged_at', 'acknowledged_by', 'acknowledged_by_name',
            'resolved_at', 'resolved_by', 'resolved_by_name', 'is_resolved',
            'notes', 'duration_minutes'
        ]
        read_only_fields = ['detected_at', 'acknowledged_at', 'acknowledged_by', 'resolved_at', 'resolved_by']
    
    def get_duration_minutes(self, obj):
        if obj.resolved_at:
            return (obj.resolved_at - obj.detected_at).total_seconds() / 60
        elif obj.acknowledged_at:
            return (obj.acknowledged_at - obj.detected_at).total_seconds() / 60
        else:
            from django.utils import timezone
            return (timezone.now() - obj.detected_at).total_seconds() / 60


class AdaptiveThresholdSerializer(serializers.ModelSerializer):
    """AdaptiveThreshold serializer"""
    threshold_config_name = serializers.CharField(source='threshold_config.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AdaptiveThreshold
        fields = [
            'id', 'threshold_config', 'threshold_config_name', 'adaptation_method',
            'learning_period_days', 'min_samples', 'confidence_threshold',
            'adaptation_frequency', 'current_threshold', 'adaptation_count',
            'last_adaptation', 'is_active', 'config', 'created_by',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'current_threshold', 'adaptation_count', 'last_adaptation']
    
    def validate_learning_period_days(self, value):
        if value <= 0:
            raise serializers.ValidationError("Learning period must be positive")
        return value
    
    def validate_min_samples(self, value):
        if value <= 0:
            raise serializers.ValidationError("Minimum samples must be positive")
        return value
    
    def validate_confidence_threshold(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Confidence threshold must be between 0 and 1")
        return value


class ThresholdHistorySerializer(serializers.ModelSerializer):
    """ThresholdHistory serializer"""
    adaptive_threshold_name = serializers.CharField(source='adaptive_threshold.name', read_only=True)
    
    class Meta:
        model = ThresholdHistory
        fields = [
            'id', 'adaptive_threshold', 'adaptive_threshold_name', 'change_type',
            'old_threshold', 'new_threshold', 'change_percentage', 'reason',
            'created_at'
        ]
        read_only_fields = ['created_at']


class ThresholdProfileSerializer(serializers.ModelSerializer):
    """ThresholdProfile serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ThresholdProfile
        fields = [
            'id', 'name', 'profile_type', 'description', 'is_default', 'is_active',
            'threshold_settings', 'alert_type_mappings', 'created_by',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def validate_threshold_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Threshold settings must be a dictionary")
        return value
    
    def validate_alert_type_mappings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Alert type mappings must be a dictionary")
        return value


# Simplified serializers for list views
class ThresholdConfigListSerializer(serializers.ModelSerializer):
    """Simplified ThresholdConfig serializer for list views"""
    alert_rule_name = serializers.CharField(source='alert_rule.name', read_only=True)
    
    class Meta:
        model = ThresholdConfig
        fields = [
            'id', 'alert_rule', 'alert_rule_name', 'threshold_type',
            'primary_threshold', 'is_active', 'created_at'
        ]


class ThresholdBreachListSerializer(serializers.ModelSerializer):
    """Simplified ThresholdBreach serializer for list views"""
    threshold_config_name = serializers.CharField(source='threshold_config.name', read_only=True)
    alert_rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    
    class Meta:
        model = ThresholdBreach
        fields = [
            'id', 'threshold_config', 'threshold_config_name', 'alert_rule_name',
            'severity', 'breach_value', 'detected_at', 'is_resolved'
        ]


class AdaptiveThresholdListSerializer(serializers.ModelSerializer):
    """Simplified AdaptiveThreshold serializer for list views"""
    threshold_config_name = serializers.CharField(source='threshold_config.name', read_only=True)
    
    class Meta:
        model = AdaptiveThreshold
        fields = [
            'id', 'threshold_config', 'threshold_config_name', 'adaptation_method',
            'current_threshold', 'adaptation_count', 'is_active', 'last_adaptation'
        ]


# Action serializers
class ThresholdBreachAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging threshold breaches"""
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ThresholdBreachResolveSerializer(serializers.Serializer):
    """Serializer for resolving threshold breaches"""
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ThresholdConfigEvaluateSerializer(serializers.Serializer):
    """Serializer for evaluating threshold conditions"""
    current_value = serializers.FloatField(required=True)
    
    def validate_current_value(self, value):
        if value is None:
            raise serializers.ValidationError("Current value is required")
        return value


class AdaptiveThresholdAdaptSerializer(serializers.Serializer):
    """Serializer for manual threshold adaptation"""
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ThresholdProfileApplySerializer(serializers.Serializer):
    """Serializer for applying threshold profiles"""
    threshold_config_id = serializers.IntegerField(required=True)
    
    def validate_threshold_config_id(self, value):
        from ..models.threshold import ThresholdConfig
        try:
            ThresholdConfig.objects.get(id=value)
        except ThresholdConfig.DoesNotExist:
            raise serializers.ValidationError("Threshold configuration not found")
        return value


class ThresholdProfileEffectiveSettingsSerializer(serializers.Serializer):
    """Serializer for getting effective settings"""
    alert_type = serializers.CharField(max_length=50, required=True)
    
    def validate_alert_type(self, value):
        if not value:
            raise serializers.ValidationError("Alert type is required")
        return value
