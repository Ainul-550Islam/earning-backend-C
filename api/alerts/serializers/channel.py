"""
Channel Serializers
"""
import re

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog,
    ChannelRateLimit, AlertRecipient
)
from ..validators import (
    validate_channel_config,
    validate_webhook_url,
    validate_time_window,
    validate_json_schema,
)

User = get_user_model()

# Channel ``config`` holds credentials (webhook URLs, tokens, SMTP passwords, API keys).
# They are masked in API output and restored from the stored value when a client sends
# the placeholder back, so a read-modify-write cycle never loses or exposes a secret.
SECRET_CONFIG_KEY = re.compile(
    r'secret|token|passw|pwd|api[_-]?key|auth|credential|private|signing|webhook_url|dsn|bearer',
    re.IGNORECASE,
)
SECRET_MASK = '********'


def redact_config(value, key=None):
    """Return a copy of ``value`` with every secret-looking entry masked."""
    if isinstance(value, dict):
        return {k: redact_config(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_config(v, key) for v in value]
    if key is not None and SECRET_CONFIG_KEY.search(str(key)) and value not in (None, '', False):
        return SECRET_MASK
    return value


def _restore_masked(new, old, unresolved, path=''):
    if isinstance(new, dict):
        old = old if isinstance(old, dict) else {}
        return {k: _restore_masked(v, old.get(k), unresolved, f'{path}{k}.') for k, v in new.items()}
    if isinstance(new, str) and new == SECRET_MASK:
        if old in (None, ''):
            unresolved.append(path.rstrip('.'))
            return new
        return old
    return new


class AlertChannelSerializer(serializers.ModelSerializer):
    """AlertChannel serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    health_status = serializers.SerializerMethodField()
    success_rate_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertChannel
        fields = [
            'id', 'name', 'channel_type', 'description', 'is_enabled', 'priority',
            'rate_limit_per_minute', 'rate_limit_per_hour', 'rate_limit_per_day',
            'max_retries', 'retry_delay_minutes', 'config', 'status',
            'last_success', 'last_failure', 'consecutive_failures',
            'total_sent', 'total_failed', 'success_rate', 'success_rate_display',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'health_status'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'last_success', 'last_failure', 
                          'consecutive_failures', 'total_sent', 'total_failed', 'success_rate']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(data.get('config'), dict):
            data['config'] = redact_config(data['config'])
        return data

    def validate_config(self, value):
        """Restore masked placeholders from the stored config (never persist the mask)."""
        if not isinstance(value, dict):
            return value
        stored = self.instance.config if isinstance(self.instance, AlertChannel) else None
        unresolved = []
        restored = _restore_masked(value, stored, unresolved)
        if unresolved:
            raise serializers.ValidationError(
                "No stored value to keep for masked field(s): " + ', '.join(sorted(unresolved)))
        return restored

    def get_health_status(self, obj):
        return obj.get_health_status()
    
    def get_success_rate_display(self, obj):
        return f"{obj.success_rate:.1f}%"
    
    def validate_priority(self, value):
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10")
        return value
    
    def validate_rate_limit_per_minute(self, value):
        if not 1 <= value <= 1000:
            raise serializers.ValidationError("Rate limit per minute must be between 1 and 1000")
        return value
    
    def validate_rate_limit_per_hour(self, value):
        if not 1 <= value <= 10000:
            raise serializers.ValidationError("Rate limit per hour must be between 1 and 10000")
        return value
    
    def validate_rate_limit_per_day(self, value):
        if not 1 <= value <= 100000:
            raise serializers.ValidationError("Rate limit per day must be between 1 and 100000")
        return value
    
    def validate_max_retries(self, value):
        if not 0 <= value <= 10:
            raise serializers.ValidationError("Max retries must be between 0 and 10")
        return value
    
    def validate_retry_delay_minutes(self, value):
        if not 1 <= value <= 60:
            raise serializers.ValidationError("Retry delay must be between 1 and 60 minutes")
        return value

    def validate(self, attrs):
        """
        Cross-field validation:
        - validate_webhook_url() for webhook/slack channels that supply a webhook_url
        - Full validate_channel_config() is intentionally deferred to the service layer
          so partial configs (e.g. only smtp_host supplied) remain serializer-valid.
        """
        channel_type = attrs.get('channel_type') or getattr(self.instance, 'channel_type', None)
        config = attrs.get('config') or getattr(self.instance, 'config', {}) or {}

        if channel_type in ('webhook', 'slack') and isinstance(config, dict):
            webhook_url = config.get('webhook_url')
            if webhook_url:
                url_result = validate_webhook_url(webhook_url)
                if not url_result['valid']:
                    raise serializers.ValidationError(
                        {'config': {'webhook_url': url_result['errors']}}
                    )

        return attrs


class ChannelRouteSerializer(serializers.ModelSerializer):
    """ChannelRoute serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    source_rules_count = serializers.SerializerMethodField()
    source_channels_count = serializers.SerializerMethodField()
    destination_channels_count = serializers.SerializerMethodField()


    source_rules = serializers.PrimaryKeyRelatedField(
        many=True, required=False,
        queryset=__import__('api.alerts.models.core', fromlist=['AlertRule']).AlertRule.objects.all()
    )
    source_channels = serializers.PrimaryKeyRelatedField(
        many=True, required=False,
        queryset=AlertChannel.objects.all()
    )
    destination_channels = serializers.PrimaryKeyRelatedField(
        many=True, required=False,
        queryset=AlertChannel.objects.all()
    )
    
    class Meta:
        model = ChannelRoute
        fields = [
            'id', 'name', 'description', 'route_type', 'is_active', 'priority',
            'source_rules', 'source_channels', 'destination_channels', 'conditions',
            'start_time', 'end_time', 'days_of_week', 'escalation_delay_minutes',
            'escalate_after_failures', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'source_rules_count',
            'source_channels_count', 'destination_channels_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_source_rules_count(self, obj):
        return obj.source_rules.count()
    
    def get_source_channels_count(self, obj):
        return obj.source_channels.count()
    
    def get_destination_channels_count(self, obj):
        return obj.destination_channels.count()
    
    def validate_priority(self, value):
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Priority must be between 1 and 10")
        return value
    
    def validate_escalation_delay_minutes(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Escalation delay must be at least 1 minute")
        return value
    
    def validate_escalate_after_failures(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Escalate after failures must be at least 1")
        return value

    def validate(self, attrs):
        """
        Cross-field validation:
        - time_based routes: start_time must be before end_time
        - validate_time_window() on escalation_delay_minutes
        - conditions dict run through validate_json_schema()
        """
        route_type = attrs.get('route_type') or getattr(self.instance, 'route_type', None)
        if route_type == 'time_based':
            start = attrs.get('start_time') or getattr(self.instance, 'start_time', None)
            end = attrs.get('end_time') or getattr(self.instance, 'end_time', None)
            if start and end and start >= end:
                raise serializers.ValidationError(
                    {'start_time': 'start_time must be before end_time for time_based routes.'}
                )

        escalation_delay = attrs.get('escalation_delay_minutes')
        if escalation_delay is not None:
            tw_result = validate_time_window(escalation_delay, unit='minutes')
            if not tw_result['valid']:
                raise serializers.ValidationError(
                    {'escalation_delay_minutes': tw_result['errors']}
                )

        conditions = attrs.get('conditions')
        if conditions and isinstance(conditions, dict):
            schema_result = validate_json_schema(conditions)
            if not schema_result['valid']:
                raise serializers.ValidationError({'conditions': schema_result['errors']})

        return attrs


class ChannelHealthLogSerializer(serializers.ModelSerializer):
    """ChannelHealthLog serializer"""
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    channel_type = serializers.CharField(source='channel.channel_type', read_only=True)
    
    class Meta:
        model = ChannelHealthLog
        fields = [
            'id', 'channel', 'channel_name', 'channel_type',
            'check_name', 'status', 'status_message',
            'response_time_ms', 'error_message', 'check_type', 'details',
            'checked_at'
        ]
        read_only_fields = ['checked_at']


class ChannelRateLimitSerializer(serializers.ModelSerializer):
    """ChannelRateLimit serializer"""
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    channel_type = serializers.CharField(source='channel.channel_type', read_only=True)
    
    class Meta:
        model = ChannelRateLimit
        fields = [
            'id', 'channel', 'channel_name', 'channel_type', 'limit_type',
            'window_seconds', 'max_requests', 'burst_size', 'refill_rate',
            'bucket_size', 'current_tokens', 'last_refill', 'total_requests',
            'rejected_requests', 'rejection_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'current_tokens', 'last_refill', 
                          'total_requests', 'rejected_requests', 'rejection_rate']
    
    def validate_window_seconds(self, value):
        if not 1 <= value <= 86400:
            raise serializers.ValidationError("Window seconds must be between 1 and 86400")
        return value
    
    def validate_max_requests(self, value):
        if not 1 <= value <= 100000:
            raise serializers.ValidationError("Max requests must be between 1 and 100000")
        return value
    
    def validate_burst_size(self, value):
        if value is not None and not 1 <= value <= 1000:
            raise serializers.ValidationError("Burst size must be between 1 and 1000")
        return value
    
    def validate_refill_rate(self, value):
        if value is not None and not 0.1 <= value <= 1000:
            raise serializers.ValidationError("Refill rate must be between 0.1 and 1000")
        return value
    
    def validate_bucket_size(self, value):
        if value is not None and not 1 <= value <= 10000:
            raise serializers.ValidationError("Bucket size must be between 1 and 10000")
        return value


class AlertRecipientSerializer(serializers.ModelSerializer):
    """AlertRecipient serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_available_now = serializers.SerializerMethodField()
    contact_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRecipient
        fields = [
            'id', 'name', 'recipient_type', 'user', 'user_name', 'email_address',
            'phone_number', 'webhook_url', 'preferred_channels', 'channel_config',
            'priority', 'is_active', 'available_hours_start', 'available_hours_end',
            'available_days', 'timezone', 'max_notifications_per_hour',
            'max_notifications_per_day', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'is_available_now', 'contact_info'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_is_available_now(self, obj):
        return obj.is_available_now()
    
    def get_contact_info(self, obj):
        return obj.get_contact_info()
    
    def validate_max_notifications_per_hour(self, value):
        if not 1 <= value <= 1000:
            raise serializers.ValidationError("Max notifications per hour must be between 1 and 1000")
        return value
    
    def validate_max_notifications_per_day(self, value):
        if not 1 <= value <= 10000:
            raise serializers.ValidationError("Max notifications per day must be between 1 and 10000")
        return value


# Simplified serializers for list views
class AlertChannelListSerializer(serializers.ModelSerializer):
    """Simplified AlertChannel serializer for list views"""
    health_status = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertChannel
        fields = [
            'id', 'name', 'channel_type', 'is_enabled', 'priority', 'status',
            'total_sent', 'total_failed', 'success_rate', 'health_status'
        ]
    
    def get_health_status(self, obj):
        return obj.get_health_status()


class ChannelRouteListSerializer(serializers.ModelSerializer):
    """Simplified ChannelRoute serializer for list views"""
    
    class Meta:
        model = ChannelRoute
        fields = [
            'id', 'name', 'route_type', 'is_active', 'priority',
            'created_at', 'updated_at'
        ]


class ChannelHealthLogListSerializer(serializers.ModelSerializer):
    """Simplified ChannelHealthLog serializer for list views"""
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    
    class Meta:
        model = ChannelHealthLog
        fields = [
            'id', 'channel', 'channel_name', 'status', 'response_time_ms',
            'check_type', 'checked_at'
        ]


class AlertRecipientListSerializer(serializers.ModelSerializer):
    """Simplified AlertRecipient serializer for list views"""
    is_available_now = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRecipient
        fields = [
            'id', 'name', 'recipient_type', 'priority', 'is_active',
            'is_available_now', 'timezone'
        ]
    
    def get_is_available_now(self, obj):
        return obj.is_available_now()


# Action serializers
class AlertChannelTestSerializer(serializers.Serializer):
    """Serializer for testing channels (no additional fields needed)"""
    pass


class ChannelRouteTestSerializer(serializers.Serializer):
    """Serializer for testing channel routing"""
    rule_id = serializers.IntegerField(required=True)
    trigger_value = serializers.FloatField(required=True)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_rule_id(self, value):
        from ..models.core import AlertRule
        try:
            AlertRule.objects.get(id=value)
        except AlertRule.DoesNotExist:
            raise serializers.ValidationError("Alert rule not found")
        return value


class ChannelRateLimitTestSerializer(serializers.Serializer):
    """Serializer for testing rate limits (no additional fields needed)"""
    pass


class AlertRecipientAvailabilityUpdateSerializer(serializers.Serializer):
    """Serializer for updating recipient availability"""
    available_hours_start = serializers.TimeField(required=False, allow_null=True)
    available_hours_end = serializers.TimeField(required=False, allow_null=True)
    timezone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    available_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_empty=True
    )
    is_active = serializers.BooleanField(required=False)


class AlertRecipientUsageStatsSerializer(serializers.Serializer):
    """Serializer for getting recipient usage statistics"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
