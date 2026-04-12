"""
Core Alert Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.core import (
    AlertRule, AlertLog, Notification, AlertSchedule, AlertEscalation, 
    AlertTemplate, AlertAnalytics, AlertGroup, AlertSuppression, 
    SystemHealthCheck, AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)

User = get_user_model()


class AlertRuleSerializer(serializers.ModelSerializer):
    """AlertRule serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    last_triggered_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'alert_type', 'severity', 'description',
            'threshold_value', 'time_window_minutes', 'is_active',
            'send_email', 'send_telegram', 'send_sms', 'send_webhook',
            'webhook_url', 'email_recipients', 'cooldown_minutes',
            'trigger_count', 'last_triggered', 'created_at', 'updated_at',
            'created_by', 'created_by_name', 'last_triggered_ago'
        ]
        read_only_fields = ['trigger_count', 'last_triggered', 'created_at', 'updated_at', 'created_by']
    
    def get_last_triggered_ago(self, obj):
        if obj.last_triggered:
            from django.utils import timezone
            delta = timezone.now() - obj.last_triggered
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return "Just now"
        return "Never"


class AlertLogSerializer(serializers.ModelSerializer):
    """AlertLog serializer"""
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_severity = serializers.CharField(source='rule.severity', read_only=True)
    rule_alert_type = serializers.CharField(source='rule.alert_type', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    age_in_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertLog
        fields = [
            'id', 'rule', 'rule_name', 'rule_severity', 'rule_alert_type',
            'message', 'trigger_value', 'threshold_value', 'details',
            'is_resolved', 'resolved_at', 'resolution_note', 'resolved_by',
            'resolved_by_name', 'triggered_at', 'processing_time_ms',
            'escalation_level', 'age_in_minutes'
        ]
        read_only_fields = ['triggered_at', 'processing_time_ms', 'escalation_level']
    
    def get_age_in_minutes(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.triggered_at
        return delta.total_seconds() / 60


class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer"""
    alert_rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'alert_log', 'notification_type', 'recipient', 'subject',
            'message', 'status', 'sent_at', 'message_id', 'response_time_ms',
            'retry_count', 'last_retry_at', 'created_at', 'alert_rule_name'
        ]
        read_only_fields = ['created_at', 'sent_at', 'message_id', 'response_time_ms', 'retry_count', 'last_retry_at']


class AlertScheduleSerializer(serializers.ModelSerializer):
    """AlertSchedule serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertSchedule
        fields = [
            'id', 'name', 'schedule_type', 'is_active', 'cron_expression',
            'start_date', 'end_date', 'timezone', 'alert_rules',
            'notification_channels', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class AlertEscalationSerializer(serializers.ModelSerializer):
    """AlertEscalation serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertEscalation
        fields = [
            'id', 'rule', 'level', 'escalation_delay_minutes', 'auto_escalate',
            'escalation_message', 'notification_channels', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class AlertTemplateSerializer(serializers.ModelSerializer):
    """AlertTemplate serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertTemplate
        fields = [
            'id', 'name', 'template_type', 'subject_template', 'message_template',
            'html_template', 'variables', 'is_default', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class AlertAnalyticsSerializer(serializers.ModelSerializer):
    """AlertAnalytics serializer"""
    
    class Meta:
        model = AlertAnalytics
        fields = [
            'id', 'date', 'total_alerts', 'resolved_alerts', 'unresolved_alerts',
            'critical_alerts', 'high_alerts', 'medium_alerts', 'low_alerts',
            'avg_resolution_time', 'escalated_alerts', 'created_at', 'updated_at'
        ]
        read_only_fields = ['date', 'created_at', 'updated_at']


class AlertGroupSerializer(serializers.ModelSerializer):
    """AlertGroup serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    rules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertGroup
        fields = [
            'id', 'name', 'description', 'is_active', 'rules', 'group_notification_enabled',
            'notification_threshold', 'notification_cooldown_minutes', 'last_group_alert_at',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'rules_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'last_group_alert_at']
    
    def get_rules_count(self, obj):
        return obj.rules.count()


class AlertSuppressionSerializer(serializers.ModelSerializer):
    """AlertSuppression serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertSuppression
        fields = [
            'id', 'name', 'suppression_type', 'rule', 'alert_type', 'severity',
            'start_time', 'end_time', 'reason', 'is_active', 'created_by',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class SystemHealthCheckSerializer(serializers.ModelSerializer):
    """SystemHealthCheck serializer"""
    
    class Meta:
        model = SystemHealthCheck
        fields = [
            'id', 'check_name', 'check_type', 'status', 'response_time_ms',
            'status_message', 'details', 'checked_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['checked_at', 'created_at', 'updated_at']


class AlertRuleHistorySerializer(serializers.ModelSerializer):
    """AlertRuleHistory serializer"""
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertRuleHistory
        fields = [
            'id', 'rule', 'change_type', 'old_values', 'new_values',
            'change_reason', 'changed_by', 'changed_by_name', 'changed_at'
        ]
        read_only_fields = ['changed_at', 'changed_by']


class AlertDashboardConfigSerializer(serializers.ModelSerializer):
    """AlertDashboardConfig serializer"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = AlertDashboardConfig
        fields = [
            'id', 'user', 'user_name', 'dashboard_layout', 'widgets',
            'preferences', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SystemMetricsSerializer(serializers.ModelSerializer):
    """SystemMetrics serializer"""
    
    class Meta:
        model = SystemMetrics
        fields = [
            'id', 'timestamp', 'cpu_usage_percent', 'memory_usage_percent',
            'disk_usage_percent', 'network_io', 'total_users', 'active_users_1h',
            'active_users_24h', 'data_source', 'details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['timestamp', 'created_at', 'updated_at']


# Simplified serializers for API responses
class AlertRuleListSerializer(serializers.ModelSerializer):
    """Simplified AlertRule serializer for list views"""
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'alert_type', 'severity', 'is_active',
            'trigger_count', 'last_triggered', 'created_at'
        ]


class AlertLogListSerializer(serializers.ModelSerializer):
    """Simplified AlertLog serializer for list views"""
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_severity = serializers.CharField(source='rule.severity', read_only=True)
    
    class Meta:
        model = AlertLog
        fields = [
            'id', 'rule', 'rule_name', 'rule_severity', 'message',
            'trigger_value', 'is_resolved', 'triggered_at'
        ]


class NotificationListSerializer(serializers.ModelSerializer):
    """Simplified Notification serializer for list views"""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'recipient', 'status',
            'created_at', 'retry_count'
        ]


class SystemHealthCheckListSerializer(serializers.ModelSerializer):
    """Simplified SystemHealthCheck serializer for list views"""
    
    class Meta:
        model = SystemHealthCheck
        fields = [
            'id', 'check_name', 'check_type', 'status',
            'response_time_ms', 'checked_at'
        ]


# Create/Update serializers
class AlertRuleCreateSerializer(serializers.ModelSerializer):
    """AlertRule serializer for create operations"""
    
    class Meta:
        model = AlertRule
        fields = [
            'name', 'alert_type', 'severity', 'description',
            'threshold_value', 'time_window_minutes', 'is_active',
            'send_email', 'send_telegram', 'send_sms', 'send_webhook',
            'webhook_url', 'email_recipients', 'cooldown_minutes'
        ]
    
    def validate_threshold_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Threshold value must be positive")
        return value
    
    def validate_time_window_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError("Time window must be positive")
        return value
    
    def validate_cooldown_minutes(self, value):
        if value < 0:
            raise serializers.ValidationError("Cooldown cannot be negative")
        return value


class AlertLogResolveSerializer(serializers.Serializer):
    """Serializer for resolving alert logs"""
    resolution_note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        # Accept either 'note' or 'resolution_note'
        note = attrs.get('note') or attrs.get('resolution_note', 'Manually resolved')
        attrs['resolution_note'] = note
        return attrs


class AlertLogBulkResolveSerializer(serializers.Serializer):
    """Serializer for bulk resolving alert logs"""
    ids = serializers.ListField(child=serializers.IntegerField())
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    resolution_note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one alert ID is required")
        return value
    
    def validate(self, attrs):
        # Accept either 'note' or 'resolution_note'
        note = attrs.get('note') or attrs.get('resolution_note', 'Bulk resolved by admin')
        attrs['resolution_note'] = note
        return attrs


class AlertRuleBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating alert rules"""
    ids = serializers.ListField(child=serializers.IntegerField())
    is_active = serializers.BooleanField()
    
    def validate_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one rule ID is required")
        return value
