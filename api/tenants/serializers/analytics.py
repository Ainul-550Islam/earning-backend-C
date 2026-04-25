"""
Analytics Serializers

This module contains serializers for analytics-related models including
TenantMetric, TenantHealthScore, TenantFeatureFlag, and TenantNotification.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.analytics import TenantMetric, TenantHealthScore, TenantFeatureFlag, TenantNotification


class TenantMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantMetric model.
    """
    metric_type_display = serializers.SerializerMethodField()
    change_display = serializers.SerializerMethodField()
    is_positive_change = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantMetric
        fields = [
            'id', 'tenant', 'date', 'metric_type', 'metric_type_display',
            'value', 'unit', 'metadata', 'previous_value', 'change_percentage',
            'change_display', 'is_positive_change', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at'
        ]
    
    def get_metric_type_display(self, obj):
        """Get metric type display name."""
        return obj.get_metric_type_display()
    
    def get_change_display(self, obj):
        """Get formatted change display."""
        return obj.change_display
    
    def get_is_positive_change(self, obj):
        """Check if change is positive."""
        return obj.is_positive_change
    
    def validate(self, attrs):
        """Validate metric data."""
        # Validate metric type
        metric_type = attrs.get('metric_type')
        valid_types = ['mau', 'dau', 'revenue', 'api_calls', 'storage_used',
                       'bandwidth_used', 'tickets_open', 'campaigns_active',
                       'publishers_active', 'conversion_rate', 'custom']
        if metric_type and metric_type not in valid_types:
            raise serializers.ValidationError("Invalid metric type.")
        
        # Validate value
        value = attrs.get('value')
        if value is not None and value < 0:
            raise serializers.ValidationError("Metric value cannot be negative.")
        
        return attrs


class TenantHealthScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantHealthScore model.
    """
    health_grade_display = serializers.SerializerMethodField()
    risk_level_display = serializers.SerializerMethodField()
    days_since_last_activity = serializers.SerializerMethodField()
    recommendations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantHealthScore
        fields = [
            'id', 'tenant', 'engagement_score', 'usage_score', 'payment_score',
            'support_score', 'overall_score', 'health_grade', 'health_grade_display',
            'risk_level', 'risk_level_display', 'churn_probability',
            'last_activity_at', 'days_since_last_activity', 'days_inactive',
            'positive_factors', 'negative_factors', 'risk_signals',
            'recommendations', 'recommendations_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at'
        ]
    
    def get_health_grade_display(self, obj):
        """Get health grade display name."""
        return obj.get_health_grade_display()
    
    def get_risk_level_display(self, obj):
        """Get risk level display name."""
        return obj.get_risk_level_display()
    
    def get_days_since_last_activity(self, obj):
        """Get days since last activity."""
        if obj.last_activity_at:
            delta = timezone.now() - obj.last_activity_at
            return delta.days
        return None
    
    def get_recommendations_count(self, obj):
        """Get count of recommendations."""
        return len(obj.recommendations) if obj.recommendations else 0
    
    def validate(self, attrs):
        """Validate health score data."""
        # Validate score ranges (0-100)
        score_fields = [
            'engagement_score', 'usage_score', 'payment_score',
            'support_score', 'overall_score', 'churn_probability'
        ]
        
        for field in score_fields:
            if field in attrs:
                score = attrs[field]
                if score < 0 or score > 100:
                    raise serializers.ValidationError(f"{field} must be between 0 and 100.")
        
        # Validate days inactive
        days_inactive = attrs.get('days_inactive')
        if days_inactive is not None and days_inactive < 0:
            raise serializers.ValidationError("Days inactive cannot be negative.")
        
        return attrs


class TenantFeatureFlagSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantFeatureFlag model.
    """
    flag_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    target_users_count = serializers.SerializerMethodField()
    target_segments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantFeatureFlag
        fields = [
            'id', 'tenant', 'flag_key', 'name', 'description', 'flag_type',
            'flag_type_display', 'is_enabled', 'status_display', 'rollout_pct',
            'variant', 'starts_at', 'expires_at', 'is_active', 'target_users',
            'target_users_count', 'target_segments', 'target_segments_count',
            'conditions', 'metadata', 'tags', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at'
        ]
    
    def get_flag_type_display(self, obj):
        """Get flag type display name."""
        return obj.get_flag_type_display()
    
    def get_status_display(self, obj):
        """Get status display name."""
        return "Active" if obj.is_active() else "Inactive"
    
    def get_is_active(self, obj):
        """Check if flag is currently active."""
        return obj.is_active()
    
    def get_target_users_count(self, obj):
        """Get count of target users."""
        return len(obj.target_users) if obj.target_users else 0
    
    def get_target_segments_count(self, obj):
        """Get count of target segments."""
        return len(obj.target_segments) if obj.target_segments else 0
    
    def validate(self, attrs):
        """Validate feature flag data."""
        # Validate flag type
        flag_type = attrs.get('flag_type')
        valid_types = ['boolean', 'percentage', 'whitelist', 'blacklist', 'conditional']
        if flag_type and flag_type not in valid_types:
            raise serializers.ValidationError("Invalid flag type.")
        
        # Validate rollout percentage
        rollout_pct = attrs.get('rollout_pct')
        if rollout_pct is not None:
            if rollout_pct < 0 or rollout_pct > 100:
                raise serializers.ValidationError("Rollout percentage must be between 0 and 100.")
        
        # Validate timing
        starts_at = attrs.get('starts_at')
        expires_at = attrs.get('expires_at')
        
        if starts_at and expires_at and starts_at >= expires_at:
            raise serializers.ValidationError("Start time must be before expiry time.")
        
        return attrs


class TenantFeatureFlagCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new feature flags.
    """
    class Meta:
        model = TenantFeatureFlag
        fields = [
            'flag_key', 'name', 'description', 'flag_type', 'is_enabled',
            'rollout_pct', 'variant', 'starts_at', 'expires_at', 'target_users',
            'target_segments', 'conditions', 'metadata', 'tags'
        ]
    
    def validate_flag_key(self, value):
        """Validate flag key uniqueness for tenant."""
        if self.instance and self.instance.flag_key == value:
            return value
        
        if self.context['request'].tenant.feature_flags.filter(flag_key=value).exists():
            raise serializers.ValidationError("Feature flag with this key already exists.")
        return value
    
    def validate(self, attrs):
        """Validate feature flag creation data."""
        flag_type = attrs.get('flag_type')
        rollout_pct = attrs.get('rollout_pct', 0)
        
        # Validate flag type specific requirements
        if flag_type == 'percentage' and rollout_pct == 0:
            raise serializers.ValidationError("Percentage rollout must be greater than 0.")
        
        if flag_type == 'whitelist' and not attrs.get('target_users'):
            raise serializers.ValidationError("Target users are required for whitelist type.")
        
        return attrs


class TenantNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantNotification model.
    """
    notification_type_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    delivery_channels = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantNotification
        fields = [
            'id', 'tenant', 'title', 'message', 'notification_type',
            'notification_type_display', 'priority', 'priority_display',
            'status', 'status_display', 'is_read', 'read_at', 'target_users',
            'target_roles', 'send_email', 'send_push', 'send_sms',
            'send_in_app', 'delivery_channels', 'scheduled_at', 'expires_at',
            'action_url', 'action_text', 'metadata', 'is_urgent', 'is_pending',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'read_at', 'created_at', 'updated_at'
        ]
    
    def get_notification_type_display(self, obj):
        """Get notification type display name."""
        return obj.get_notification_type_display()
    
    def get_priority_display(self, obj):
        """Get priority display name."""
        return obj.get_priority_display()
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_delivery_channels(self, obj):
        """Get list of enabled delivery channels."""
        return obj.get_delivery_channels()
    
    def get_is_urgent(self, obj):
        """Check if notification is urgent."""
        return obj.is_urgent
    
    def validate(self, attrs):
        """Validate notification data."""
        # Validate scheduled time
        scheduled_at = attrs.get('scheduled_at')
        if scheduled_at and scheduled_at <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        
        # Validate expiry time
        expires_at = attrs.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise serializers.ValidationError("Expiry time must be in the future.")
        
        # Validate timing consistency
        if scheduled_at and expires_at and scheduled_at >= expires_at:
            raise serializers.ValidationError("Scheduled time must be before expiry time.")
        
        return attrs
