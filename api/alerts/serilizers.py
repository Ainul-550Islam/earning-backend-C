# alerts/serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    AlertRule, AlertLog, Notification, AlertSchedule,
    AlertEscalation, AlertTemplate, AlertAnalytics,
    AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)


class AlertRuleSerializer(serializers.ModelSerializer):
    """তোমার AlertRule model এর serializer"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    can_trigger_now = serializers.BooleanField(read_only=True)
    trigger_count_today = serializers.IntegerField(read_only=True)
    avg_processing_time = serializers.FloatField(read_only=True)
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'alert_type', 'severity', 'description',
            'threshold_value', 'time_window_minutes',
            'send_email', 'send_telegram', 'send_sms', 'send_webhook',
            'email_recipients', 'telegram_chat_id', 'sms_recipients', 'webhook_url',
            'is_active', 'last_triggered', 'cooldown_minutes',
            'trigger_count', 'avg_processing_time',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
            'can_trigger_now', 'trigger_count_today'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'last_triggered']
    
    def validate(self, data):
        """তোমার AlertRule model এর clean method এর মতো validation"""
        # Cooldown validation
        if 'cooldown_minutes' in data and 'time_window_minutes' in data:
            if data['cooldown_minutes'] >= data['time_window_minutes']:
                raise serializers.ValidationError(
                    "Cooldown minutes must be less than time window minutes"
                )
        
        # Server error rate validation
        if data.get('alert_type') == 'server_error' and 'threshold_value' in data:
            if data['threshold_value'] > 100:
                raise serializers.ValidationError("Error rate cannot exceed 100%")
        
        return data
    
    def validate_email_recipients(self, value):
        """তোমার model validation মতো email validation"""
        if value:
            from django.core.validators import validate_email
            emails = [e.strip() for e in value.split(',') if e.strip()]
            for email in emails:
                validate_email(email)
        return value
    
    def create(self, validated_data):
        """তোমার AlertRule model এর save method এর মতো"""
        validated_data['created_by'] = self.context['request'].user
        instance = super().create(validated_data)
        
        # তোমার AlertRuleHistory model এ log
        AlertRuleHistory.log_change(
            rule=instance,
            action='create',
            changed_by=self.context['request'].user,
            old_data=None,
            new_data=validated_data,
            changed_fields=list(validated_data.keys())
        )
        
        return instance
    
    def update(self, instance, validated_data):
        """তোমার AlertRule model এর update"""
        import json as _json
        from .models import _safe_serialize
        old_data = {
            field.name: _safe_serialize(getattr(instance, field.name))
            for field in instance._meta.fields
            if field.name not in ['id', 'created_at', 'updated_at']
        }
        # ✅ FIXED: Ensure JSON-serializable
        old_data = _json.loads(_json.dumps(old_data, default=str))
        
        # তোমার AlertRule active manager এর cache clear
        from django.core.cache import cache
        cache_key = f'active_alert_rules_AlertRule'
        cache.delete(cache_key)
        
        instance = super().update(instance, validated_data)
        
        # Changed fields identify
        changed_fields = []
        for field in validated_data:
            if field not in ['created_at', 'updated_at']:
                changed_fields.append(field)
        
        # তোমার AlertRuleHistory model এ log
        AlertRuleHistory.log_change(
            rule=instance,
            action='update',
            changed_by=self.context['request'].user,
            old_data=old_data,
            new_data=validated_data,
            changed_fields=changed_fields
        )
        
        return instance


class AlertLogSerializer(serializers.ModelSerializer):
    """তোমার AlertLog model এর serializer"""
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_severity = serializers.CharField(source='rule.severity', read_only=True)
    rule_alert_type = serializers.CharField(source='rule.alert_type', read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    time_to_resolve = serializers.FloatField(read_only=True)
    age_in_minutes = serializers.FloatField(read_only=True)
    
    class Meta:
        model = AlertLog
        fields = [
            'id', 'rule', 'rule_name', 'rule_severity', 'rule_alert_type',
            'triggered_at', 'trigger_value', 'threshold_value',
            'message', 'details',
            'processing_time_ms', 'processing_started',
            'email_sent', 'telegram_sent', 'sms_sent', 'webhook_sent',
            'email_sent_at', 'telegram_sent_at', 'sms_sent_at', 'webhook_sent_at',
            'is_resolved', 'resolved_at', 'resolved_by', 'resolved_by_username',
            'resolution_note', 'escalated_at', 'escalation_level',
            'time_to_resolve', 'age_in_minutes'
        ]
        read_only_fields = [
            'triggered_at', 'processing_started', 
            'email_sent_at', 'telegram_sent_at', 'sms_sent_at', 'webhook_sent_at',
            'resolved_at', 'escalated_at'
        ]
    
    def create(self, validated_data):
        """তোমার AlertLog model এর save method এর মতো"""
        instance = super().create(validated_data)
        
        # AlertRule এর last_triggered update
        if instance.rule:
            AlertRule.objects.filter(id=instance.rule_id).update(
                last_triggered=instance.triggered_at
            )
        
        return instance
    
    def update(self, instance, validated_data):
        """তোমার AlertLog model এর update"""
        # যদি resolved করা হয়
        if 'is_resolved' in validated_data and validated_data['is_resolved']:
            if not instance.is_resolved:
                validated_data['resolved_at'] = timezone.now()
                validated_data['resolved_by'] = self.context['request'].user
        
        return super().update(instance, validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    """তোমার Notification model এর serializer"""
    alert_log_id = serializers.IntegerField(source='alert_log.id', read_only=True)
    rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    can_retry = serializers.BooleanField(read_only=True)
    retry_delay = serializers.IntegerField(read_only=True)
    delivery_time_seconds = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'alert_log', 'alert_log_id', 'rule_name',
            'notification_type', 'recipient', 'subject', 'message', 'status',
            'created_at', 'sent_at', 'delivered_at', 'read_at',
            'message_id', 'error_message', 'retry_count', 'last_retry_at',
            'max_retries', 'estimated_cost', 'currency', 'response_time_ms',
            'can_retry', 'retry_delay', 'delivery_time_seconds'
        ]
        read_only_fields = [
            'created_at', 'sent_at', 'delivered_at', 'read_at',
            'last_retry_at', 'response_time_ms'
        ]
    
    def validate(self, data):
        """তোমার Notification model validation"""
        if 'status' in data and data['status'] == 'failed':
            if 'error_message' not in data or not data['error_message']:
                raise serializers.ValidationError(
                    "Error message is required for failed notifications"
                )
        
        return data


class AlertGroupSerializer(serializers.ModelSerializer):
    """তোমার AlertGroup model এর serializer"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    active_alerts_count = serializers.IntegerField(read_only=True)
    should_send_group_alert = serializers.BooleanField(read_only=True)
    last_group_alert_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = AlertGroup
        fields = [
            'id', 'name', 'description', 'rules',
            'group_notification_enabled', 'group_threshold', 'cooldown_minutes',
            'group_email_recipients', 'group_telegram_chat_id', 'group_sms_recipients',
            'group_message_template',
            'is_active', 'last_group_alert_at',
            'cached_alert_count', 'cache_updated_at',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
            'active_alerts_count', 'should_send_group_alert'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def validate_group_threshold(self, value):
        """তোমার model validation"""
        if value < 1:
            raise serializers.ValidationError("Group threshold must be at least 1")
        return value


class SystemHealthCheckSerializer(serializers.ModelSerializer):
    """তোমার SystemHealthCheck model এর serializer"""
    needs_checking = serializers.BooleanField(read_only=True)
    uptime_percentage = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    status_color = serializers.CharField(read_only=True)
    
    class Meta:
        model = SystemHealthCheck
        fields = [
            'id', 'check_name', 'check_type', 'description',
            'endpoint_url', 'check_interval_minutes', 'timeout_seconds',
            'status', 'status_message', 'response_time_ms', 'error_message',
            'last_checked', 'last_success', 'next_check',
            'alert_on_failure', 'alert_rule',
            'warning_threshold_ms', 'critical_threshold_ms',
            'is_active', 'priority', 'response_history',
            'needs_checking', 'uptime_percentage', 'avg_response_time', 'status_color'
        ]
        read_only_fields = ['last_checked', 'last_success', 'next_check']


class AlertAnalyticsSerializer(serializers.ModelSerializer):
    """তোমার AlertAnalytics model এর serializer"""
    class Meta:
        model = AlertAnalytics
        fields = [
            'id', 'date',
            'total_alerts', 'resolved_alerts', 'unresolved_alerts',
            'escalated_alerts', 'false_positives', 'acknowledged_alerts',
            'avg_response_time_min', 'avg_resolution_time_min',
            'max_response_time_min', 'min_response_time_min', 'p95_response_time_min',
            'notifications_sent', 'emails_sent', 'telegrams_sent',
            'sms_sent', 'webhooks_sent', 'notifications_failed',
            'notification_success_rate', 'avg_notification_delay_ms',
            'estimated_sms_cost', 'estimated_email_cost', 'total_notification_cost',
            'system_uptime_percent', 'alert_accuracy_percent', 'avg_processing_time_ms',
            'critical_alerts', 'high_alerts', 'medium_alerts', 'low_alerts',
            'alerts_by_type',
            'resolution_rate', 'false_positive_rate', 'escalation_rate',
            'avg_alerts_per_hour',
            'generated_at', 'generation_duration_ms', 'is_complete'
        ]
        read_only_fields = ['generated_at']


class AlertDashboardConfigSerializer(serializers.ModelSerializer):
    """তোমার AlertDashboardConfig model এর serializer"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = AlertDashboardConfig
        fields = [
            'id', 'user', 'user_username',
            'theme', 'default_time_range',
            'show_alert_stats', 'show_system_health', 'show_recent_alerts',
            'show_notification_stats', 'show_alert_trends', 'show_severity_distribution',
            'show_performance_metrics', 'show_quick_actions', 'show_alert_groups',
            'show_escalation_status',
            'severity_filter', 'alert_type_filter',
            'show_resolved_alerts', 'show_acknowledged_alerts', 'show_false_positives',
            'auto_refresh_interval', 'show_desktop_notifications', 'play_alert_sound',
            'dashboard_layout',
            'chart_type', 'chart_color_scheme',
            'data_points_limit',
            'default_export_format',
            'alert_sound', 'custom_sound_url',
            'updated_at', 'created_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']


# ============================================
# API VIEWSETS
# ============================================

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

class AlertRuleViewSet(viewsets.ModelViewSet):
    """তোমার AlertRule model এর API"""
    queryset = AlertRule.objects.all()
    serializer_class = AlertRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """তোমার AlertRule active manager ব্যবহার"""
        queryset = super().get_queryset()
        
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('created_by')
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """তোমার AlertRule toggle active"""
        alert_rule = self.get_object()
        alert_rule.is_active = not alert_rule.is_active
        alert_rule.save()
        
        action_name = 'activate' if alert_rule.is_active else 'deactivate'
        AlertRuleHistory.log_change(
            rule=alert_rule,
            action=action_name,
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'is_active': alert_rule.is_active,
            'message': f'Alert rule {action_name}d successfully'
        })
    
    @action(detail=True, methods=['post'])
    def test_trigger(self, request, pk=None):
        """তোমার AlertRule test trigger"""
        alert_rule = self.get_object()
        
        if not alert_rule.can_trigger_now():
            return Response({
                'error': 'Alert rule is in cooldown period'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # তোমার AlertLog model create
        alert_log = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=alert_rule.threshold_value * 1.5,
            threshold_value=alert_rule.threshold_value,
            message=f"Test alert for rule: {alert_rule.name}",
            details={
                'test': True,
                'triggered_by': request.user.username
            }
        )
        
        alert_log.mark_as_processing()
        alert_log.mark_as_complete()
        
        AlertRuleHistory.log_change(
            rule=alert_rule,
            action='test',
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'alert_log_id': alert_log.id,
            'message': 'Test alert triggered successfully'
        })
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """তোমার AlertRule clone"""
        original_rule = self.get_object()
        
        cloned_rule = AlertRule.objects.create(
            name=f"{original_rule.name} (Copy)",
            alert_type=original_rule.alert_type,
            severity=original_rule.severity,
            description=original_rule.description,
            threshold_value=original_rule.threshold_value,
            time_window_minutes=original_rule.time_window_minutes,
            send_email=original_rule.send_email,
            send_telegram=original_rule.send_telegram,
            send_sms=original_rule.send_sms,
            send_webhook=original_rule.send_webhook,
            webhook_url=original_rule.webhook_url,
            email_recipients=original_rule.email_recipients,
            telegram_chat_id=original_rule.telegram_chat_id,
            sms_recipients=original_rule.sms_recipients,
            is_active=False,
            cooldown_minutes=original_rule.cooldown_minutes,
            created_by=request.user,
        )
        
        AlertRuleHistory.log_change(
            rule=cloned_rule,
            action='clone',
            changed_by=request.user
        )
        
        serializer = self.get_serializer(cloned_rule)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AlertLogViewSet(viewsets.ModelViewSet):
    """তোমার AlertLog model এর API"""
    queryset = AlertLog.objects.all()
    serializer_class = AlertLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """তোমার AlertLog managers ব্যবহার"""
        queryset = super().get_queryset()
        
        if self.request.query_params.get('unresolved_only') == 'true':
            queryset = queryset.filter(is_resolved=False)
        elif self.request.query_params.get('resolved_only') == 'true':
            queryset = queryset.filter(is_resolved=True)
        
        return queryset.select_related('rule', 'resolved_by')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """তোমার AlertLog resolve"""
        alert_log = self.get_object()
        
        if alert_log.is_resolved:
            return Response({
                'error': 'Alert already resolved'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        alert_log.is_resolved = True
        alert_log.resolved_at = timezone.now()
        alert_log.resolved_by = request.user
        
        if request.data.get('resolution_note'):
            alert_log.resolution_note = request.data['resolution_note']
        
        alert_log.save()
        
        return Response({
            'status': 'success',
            'message': 'Alert resolved successfully'
        })
    
    @action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        """তোমার AlertLog bulk resolve"""
        alert_ids = request.data.get('alert_ids', [])
        
        if not alert_ids:
            return Response({
                'error': 'No alert IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        alerts = AlertLog.objects.filter(
            id__in=alert_ids,
            is_resolved=False
        )
        
        count = alerts.count()
        alerts.update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        
        return Response({
            'status': 'success',
            'message': f'{count} alerts resolved successfully'
        })


class NotificationViewSet(viewsets.ModelViewSet):
    """তোমার Notification model এর API"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if self.request.query_params.get('status'):
            queryset = queryset.filter(status=self.request.query_params['status'])
        
        return queryset.select_related('alert_log', 'alert_log__rule')
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """তোমার Notification retry"""
        notification = self.get_object()
        
        if not notification.can_retry():
            return Response({
                'error': 'Cannot retry this notification'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        notification.status = 'pending'
        notification.save()
        
        return Response({
            'status': 'success',
            'message': 'Notification queued for retry'
        })