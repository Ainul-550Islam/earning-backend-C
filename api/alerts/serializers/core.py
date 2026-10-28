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
from ..validators import (
    validate_alert_rule_condition,
    validate_alert_severity,
    validate_threshold_value,
    validate_time_window,
    validate_cron_expression,
    validate_json_schema,
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

    def validate_severity(self, value):
        """Wire validate_alert_severity() from validators.py."""
        result = validate_alert_severity(value)
        if not result['valid']:
            raise serializers.ValidationError(result['errors'])
        return result.get('normalized_severity', value)

    def validate(self, attrs):
        """
        Cross-field validation:
        - validate_alert_rule_condition() on conditions / filter_conditions
        - webhook_url required when send_webhook=True
        - validate_time_window() on time_window_minutes
        """
        # Condition dict validation
        conditions = attrs.get('conditions') or attrs.get('filter_conditions')
        if conditions and isinstance(conditions, dict):
            result = validate_alert_rule_condition(conditions)
            if not result['valid']:
                raise serializers.ValidationError({'conditions': result['errors']})

        # Webhook URL required if send_webhook is True
        send_webhook = attrs.get('send_webhook', getattr(self.instance, 'send_webhook', False))
        webhook_url = attrs.get('webhook_url') or getattr(self.instance, 'webhook_url', None)
        if send_webhook and not webhook_url:
            raise serializers.ValidationError(
                {'webhook_url': 'webhook_url is required when send_webhook is True.'}
            )

        # Time window sanity check
        time_window = attrs.get('time_window_minutes')
        if time_window is not None:
            tw_result = validate_time_window(time_window, unit='minutes')
            if not tw_result['valid']:
                raise serializers.ValidationError(
                    {'time_window_minutes': tw_result['errors']}
                )

        # server_error alert type cannot have a threshold above 100% (mirrors AlertRule.clean())
        alert_type = attrs.get('alert_type', getattr(self.instance, 'alert_type', None))
        threshold_value = attrs.get('threshold_value', getattr(self.instance, 'threshold_value', None))
        if alert_type == 'server_error' and threshold_value is not None and threshold_value > 100:
            raise serializers.ValidationError('Error rate cannot exceed 100%.')

        return attrs


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
    alert_log = serializers.PrimaryKeyRelatedField(queryset=AlertLog.objects.all(), required=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'alert_log', 'notification_type', 'recipient', 'subject',
            'message', 'status', 'sent_at', 'message_id', 'response_time_ms',
            'retry_count', 'last_retry_at', 'created_at', 'alert_rule_name'
        ]
        read_only_fields = ['created_at', 'sent_at', 'message_id', 'response_time_ms', 'retry_count', 'last_retry_at']


class AlertScheduleSerializer(serializers.ModelSerializer):
    """AlertSchedule serializer — fields match actual AlertSchedule model."""

    class Meta:
        model = AlertSchedule
        fields = [
            'id', 'rule', 'name', 'description',
            'start_time', 'end_time', 'days_of_week',
            'timezone', 'is_active', 'priority',
        ]

    def validate_priority(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Priority must be at least 1.')
        return value

    def validate(self, attrs):
        """end_time must be after start_time when both provided."""
        start = attrs.get('start_time') or getattr(self.instance, 'start_time', None)
        end = attrs.get('end_time') or getattr(self.instance, 'end_time', None)
        if start and end and start >= end:
            raise serializers.ValidationError(
                {'end_time': 'end_time must be after start_time.'}
            )
        return attrs


class AlertEscalationSerializer(serializers.ModelSerializer):
    """AlertEscalation serializer"""
    
    class Meta:
        model = AlertEscalation
        fields = [
            'id', 'rule', 'level', 'delay_minutes', 'auto_escalate',
            'message_template', 'escalate_to_user', 'escalate_to_email',
            'escalate_to_sms', 'escalate_to_telegram', 'require_acknowledgment',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AlertTemplateSerializer(serializers.ModelSerializer):
    """AlertTemplate serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertTemplate
        fields = [
            'id', 'name', 'alert_type', 'language',
            'email_subject', 'email_body', 'sms_message', 'telegram_message',
            'push_title', 'push_body', 'webhook_payload',
            'available_variables', 'is_default',
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
            'avg_resolution_time_min', 'escalated_alerts', 'generated_at'
        ]
        read_only_fields = ['date', 'generated_at']


class AlertGroupSerializer(serializers.ModelSerializer):
    """AlertGroup serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    rules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertGroup
        fields = [
            'id', 'name', 'description', 'is_active', 'rules', 'group_notification_enabled',
            'group_threshold', 'cooldown_minutes', 'last_group_alert_at',
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
            'start_time', 'end_time', 'description', 'is_active', 'created_by',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class SystemHealthCheckSerializer(serializers.ModelSerializer):
    """SystemHealthCheck serializer"""
    
    class Meta:
        model = SystemHealthCheck
        fields = [
            'id', 'check_name', 'check_type', 'status', 'response_time_ms',
            'status_message', 'error_message', 'last_checked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['last_checked', 'created_at', 'updated_at']


class AlertRuleHistorySerializer(serializers.ModelSerializer):
    """AlertRuleHistory serializer"""
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertRuleHistory
        fields = [
            'id', 'rule', 'action', 'old_data', 'new_data', 'changed_fields',
            'changed_by', 'changed_by_name', 'changed_at'
        ]
        read_only_fields = ['changed_at', 'changed_by']


class AlertDashboardConfigSerializer(serializers.ModelSerializer):
    """AlertDashboardConfig serializer"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = AlertDashboardConfig
        fields = [
            'id', 'user', 'user_name', 'dashboard_layout',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SystemMetricsSerializer(serializers.ModelSerializer):
    """SystemMetrics serializer"""
    
    class Meta:
        model = SystemMetrics
        fields = [
            'id', 'timestamp', 'cpu_usage_percent', 'memory_usage_percent',
            'disk_usage_percent', 'total_users', 'active_users_1h',
            'active_users_24h', 'avg_response_time_ms', 'error_count_1h',
            'total_earnings_1h', 'total_earnings_24h', 'new_signups_1h',
            'new_signups_24h', 'data_source', 'notes',
        ]
        read_only_fields = ['timestamp']


# Simplified serializers for API responses
class SystemHealthCheckListSerializer(serializers.ModelSerializer):
    """Simplified SystemHealthCheck serializer for list views"""
    
    class Meta:
        model = SystemHealthCheck
        fields = [
            'id', 'check_name', 'check_type', 'status',
            'response_time_ms', 'last_checked'
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
        """Wire validate_threshold_value() from validators.py."""
        result = validate_threshold_value(value, threshold_type='numeric')
        if not result['valid']:
            raise serializers.ValidationError(result['errors'])
        return value

    def validate_time_window_minutes(self, value):
        """Wire validate_time_window() from validators.py."""
        result = validate_time_window(value, unit='minutes')
        if not result['valid']:
            raise serializers.ValidationError(result['errors'])
        return value

    def validate_cooldown_minutes(self, value):
        if value < 0:
            raise serializers.ValidationError("Cooldown cannot be negative")
        return value

    def validate(self, attrs):
        """
        Cross-field: validate_alert_rule_condition() on conditions,
        validate_alert_severity() on severity.
        """
        conditions = attrs.get('conditions') or attrs.get('filter_conditions')
        if conditions and isinstance(conditions, dict):
            result = validate_alert_rule_condition(conditions)
            if not result['valid']:
                raise serializers.ValidationError({'conditions': result['errors']})

        severity = attrs.get('severity')
        if severity:
            sev_result = validate_alert_severity(severity)
            if not sev_result['valid']:
                raise serializers.ValidationError({'severity': sev_result['errors']})
            attrs['severity'] = sev_result.get('normalized_severity', severity)

        return attrs


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


# ── List serializers (lightweight versions for list endpoints) ─────────────
class AlertRuleListSerializer(AlertRuleSerializer):
    class Meta(AlertRuleSerializer.Meta):
        fields = ['id', 'name', 'alert_type', 'severity', 'is_active', 'created_at']

class AlertLogListSerializer(AlertLogSerializer):
    class Meta(AlertLogSerializer.Meta):
        fields = ['id', 'rule', 'triggered_at', 'severity', 'status', 'message']

class NotificationListSerializer(NotificationSerializer):
    class Meta(NotificationSerializer.Meta):
        fields = ['id', 'notification_type', 'recipient', 'status', 'created_at']

class SystemMetricsListSerializer(SystemMetricsSerializer):
    class Meta(SystemMetricsSerializer.Meta):
        fields = ['id', 'timestamp', 'cpu_usage_percent', 'memory_usage_percent',
                  'disk_usage_percent', 'total_users', 'active_users_1h', 'avg_response_time_ms']


class AlertLogDetailSerializer(AlertLogSerializer):
    """Serializer that includes computed display fields"""
    class Meta(AlertLogSerializer.Meta):
        pass

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data is None:
            data = {}
        if instance:
            data['severity_display'] = getattr(instance, 'severity', 'medium').title() if hasattr(instance, 'severity') else 'Medium'
            data['status_display'] = getattr(instance, 'status', 'pending').title() if hasattr(instance, 'status') else 'Pending'
            data['rule_name'] = getattr(getattr(instance, 'rule', None), 'name', '') or ''
            data['age_minutes'] = instance.get_age() if hasattr(instance, 'get_age') else 0
        return data

