from rest_framework import serializers
from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
from django.contrib.auth import get_user_model


User = get_user_model()


class RateLimitConfigSerializer(serializers.ModelSerializer):
    tenant = serializers.PrimaryKeyRelatedField(
        queryset=__import__('api.tenants.models', fromlist=['Tenant']).Tenant.objects.all(),
        required=False, allow_null=True
    )

    class Meta:
        model = RateLimitConfig
        fields = [
            'id', 'name', 'rate_limit_type', 'requests_per_unit',
            'time_unit', 'time_value', 'user', 'tenant',
            'endpoint', 'ip_address', 'task_type', 'offer_wall',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RateLimitConfigCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimitConfig
        fields = [
            'name', 'rate_limit_type', 'requests_per_unit',
            'time_unit', 'time_value', 'user', 'endpoint',
            'ip_address', 'task_type', 'offer_wall', 'is_active'
        ]

    def validate(self, data):
        # Validate rate limit values
        if data.get('requests_per_unit', 1) <= 0:
            raise serializers.ValidationError("অনুরোধ সংখ্যা ০ এর চেয়ে বড় হতে হবে")

        if data.get('time_value', 1) <= 0:
            raise serializers.ValidationError("সময় মান ০ এর চেয়ে বড় হতে হবে")

        return data


class RateLimitLogSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = RateLimitLog
        fields = [
            'id', 'user', 'ip_address', 'endpoint',
            'request_method', 'status',
            'requests_count',
            'timestamp', 'created_at'
        ]
        read_only_fields = ['created_at']


class UserRateLimitProfileSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = UserRateLimitProfile
        fields = [
            'id', 'user', 'is_premium',
            'premium_until', 'custom_daily_limit', 'custom_hourly_limit',
            'total_requests', 'blocked_requests', 'last_request_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['total_requests', 'blocked_requests', 
                          'last_request_at', 'created_at', 'updated_at']


class RateLimitBulkUpdateSerializer(serializers.Serializer):
    # Accept either list of int IDs or list of dicts with 'id' key
    configs = serializers.ListField(required=True)
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'update'],
        required=True
    )

    def validate_configs(self, value):
        """Normalise to list of dicts each containing 'id'."""
        normalised = []
        for item in value:
            if isinstance(item, dict):
                if 'id' not in item:
                    raise serializers.ValidationError("প্রতিটি কনফিগারেশনে id ফিল্ড প্রয়োজন")
                normalised.append(item)
            elif isinstance(item, int):
                normalised.append({'id': item})
            else:
                try:
                    normalised.append({'id': int(item)})
                except (TypeError, ValueError):
                    raise serializers.ValidationError(f"Invalid config entry: {item!r}")
        return normalised


class RateLimitStatsSerializer(serializers.Serializer):
    timeframe = serializers.CharField()
    total_requests = serializers.IntegerField()
    blocked_requests = serializers.IntegerField()
    allowed_requests = serializers.IntegerField()
    block_rate = serializers.FloatField()
    
    class Meta:
        fields = ['timeframe', 'total_requests', 'blocked_requests', 
                 'allowed_requests', 'block_rate']


# Abuse Report Serializers
class AbuseReportSerializer(serializers.ModelSerializer):
    reporter_display = serializers.CharField(source='reporter.username', read_only=True, default='')

    class Meta:
        model = AbuseReport
        fields = [
            'id', 'reporter', 'reporter_display',
            'reported_ip', 'reason', 'description', 'evidence',
            'ip_address', 'endpoint', 'abuse_type', 'severity',
            'pattern', 'metadata', 'is_blocked', 'is_investigated',
            'first_seen', 'last_seen', 'count_24h', 'count_7d', 'count_total',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'first_seen', 'last_seen', 'count_24h', 'count_7d',
            'count_total', 'created_at', 'updated_at',
        ]


class AbuseReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbuseReport
        fields = [
            'ip_address', 'endpoint', 'abuse_type', 'severity',
            'pattern', 'metadata'
        ]
    
    def validate_severity(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Severity must be between 1 and 5")
        return value


# IP Block List Serializers
class IPBlockListSerializer(serializers.ModelSerializer):
    block_type_display = serializers.CharField(source='get_block_type_display', read_only=True, default='')

    class Meta:
        model = IPBlockList
        fields = [
            'id', 'ip_address', 'ip_range_start', 'ip_range_end',
            'block_type', 'block_type_display',
            'reason', 'description', 'is_active', 'created_by',
            'permanent', 'expires_at',
            'block_count', 'last_blocked_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'block_count', 'last_blocked_at', 'created_at', 'updated_at',
        ]


class IPBlockListCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPBlockList
        fields = [
            'ip_address', 'ip_range_start', 'ip_range_end',
            'block_type', 'reason', 'description',
            'permanent', 'expires_at', 'is_active',
        ]



class IPBlockBulkCreateSerializer(serializers.Serializer):
    ip_addresses = serializers.ListField(
        child=serializers.IPAddressField(),
        required=True
    )
    reason = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    duration_days = serializers.IntegerField(min_value=1, max_value=365, default=7)


# Rate Limit Insight Serializers
class RateLimitInsightSerializer(serializers.ModelSerializer):
    health_score_display = serializers.SerializerMethodField()
    
    class Meta:
        model = RateLimitInsight
        fields = [
            'id', 'date', 'hour', 'total_requests', 'blocked_requests',
            'unique_users', 'unique_ips', 'top_abusers', 'top_endpoints',
            'abuse_reports_count', 'active_blocks_count', 'health_score',
            'health_score_display', 'recommendations', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_health_score_display(self, obj):
        if hasattr(obj, 'get_health_score'):
            return obj.get_health_score()
        return "N/A"


class RateLimitInsightCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimitInsight
        fields = [
            'date', 'hour', 'total_requests', 'blocked_requests',
            'unique_users', 'unique_ips', 'top_abusers', 'top_endpoints',
            'abuse_reports_count', 'active_blocks_count', 'recommendations',
            'metadata'
        ]


# Rate Limit Exception Serializers
class RateLimitExceptionSerializer(serializers.ModelSerializer):
    target_display = serializers.SerializerMethodField()
    exception_type_display = serializers.CharField(source='get_exception_type_display', read_only=True)
    granted_by_display = serializers.CharField(source='granted_by.username', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = RateLimitException
        fields = [
            'id', 'user', 'ip_address', 'endpoint_pattern',
            'exception_type', 'exception_type_display', 'reason',
            'multiplier', 'max_requests', 'is_active', 'permanent',
            'expires_at', 'granted_by', 'granted_by_display',
            'usage_count', 'last_used_at', 'is_expired',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'granted_by', 'usage_count', 'last_used_at',
            'created_at', 'updated_at'
        ]
    
    def get_target_display(self, obj):
        if obj.user:
            return f"User: {obj.user.username}"
        elif obj.ip_address:
            return f"IP: {obj.ip_address}"
        elif obj.endpoint_pattern:
            return f"Endpoint: {obj.endpoint_pattern}"
        return "Unknown"


class RateLimitExceptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimitException
        fields = [
            'user', 'ip_address', 'endpoint_pattern',
            'exception_type', 'reason', 'multiplier',
            'max_requests', 'permanent', 'expires_at'
        ]
    
    def validate(self, data):
        # Validate that exactly one target is specified
        targets = ['user', 'ip_address', 'endpoint_pattern']
        used_targets = [target for target in targets if data.get(target)]
        
        if len(used_targets) != 1:
            raise serializers.ValidationError(
                "ঠিক একটি টার্গেট নির্দিষ্ট করতে হবে (user, ip_address, or endpoint_pattern)"
            )
        
        # Validate expiry for non-permanent exceptions
        if not data.get('permanent', False) and not data.get('expires_at'):
            raise serializers.ValidationError("expires_at required for non-permanent exceptions")
        
        # Validate multiplier
        if data.get('multiplier', 1) < 1:
            raise serializers.ValidationError("Multiplier must be at least 1")
        
        return data


# Additional Serializers for API Endpoints
class RateLimitInfoSerializer(serializers.Serializer):
    is_allowed = serializers.BooleanField()
    configs = serializers.ListField(child=serializers.DictField())
    failed_configs = serializers.ListField(child=serializers.DictField(), required=False)
    remaining_requests = serializers.IntegerField(required=False)
    reset_time = serializers.IntegerField(required=False)


class TaskLimitSerializer(serializers.Serializer):
    is_allowed = serializers.BooleanField()
    limit = serializers.IntegerField()
    remaining = serializers.IntegerField()
    reset_time = serializers.IntegerField()
    is_premium = serializers.BooleanField()


class OfferLimitSerializer(serializers.Serializer):
    is_allowed = serializers.BooleanField()
    limit = serializers.IntegerField()
    remaining = serializers.IntegerField()
    reset_time = serializers.IntegerField()


class ReferralLimitSerializer(serializers.Serializer):
    is_allowed = serializers.BooleanField()
    limit = serializers.IntegerField()
    remaining = serializers.IntegerField()
    reset_time = serializers.IntegerField()


class AbusePatternSerializer(serializers.Serializer):
    risk_score = serializers.IntegerField()
    abuse_types = serializers.ListField(child=serializers.CharField())
    patterns = serializers.DictField()
    recommendations = serializers.ListField(child=serializers.CharField())


class IPBlockCheckSerializer(serializers.Serializer):
    ip_address = serializers.IPAddressField()
    is_blocked = serializers.BooleanField()
    block_info = serializers.DictField(required=False)


class SystemHealthSerializer(serializers.Serializer):
    redis_status = serializers.CharField()
    total_configs = serializers.IntegerField()
    active_configs = serializers.IntegerField()
    total_logs_last_24h = serializers.IntegerField()
    active_blocks = serializers.IntegerField()
    system_load = serializers.FloatField()


class BulkActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.ChoiceField(choices=['activate', 'deactivate', 'delete'])


class ExportConfigSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=['csv', 'json', 'excel'])
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    include_metadata = serializers.BooleanField(default=False)

class RateLimitWebhookSerializer(serializers.Serializer):
    """Serializer for rate limit webhook payloads."""
    event_type = serializers.CharField(max_length=100)
    timestamp = serializers.DateTimeField(required=False, allow_null=True)
    data = serializers.JSONField(required=False, default=dict)
    signature = serializers.CharField(required=False, allow_blank=True, default='')
    source = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_event_type(self, value):
        allowed = ['rate_limit_exceeded','abuse_detected','ip_blocked',
                   'config_changed','user_blocked','custom']
        if value not in allowed:
            # Allow any event type but flag unknown ones
            pass
        return value


class RateLimitWebhookDeliverySerializer(serializers.Serializer):
    """Serializer for webhook delivery status."""
    webhook_id = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=['pending','delivered','failed','retry'])
    attempts = serializers.IntegerField(min_value=0, default=0)
    last_attempt_at = serializers.DateTimeField(required=False, allow_null=True)
    response_code = serializers.IntegerField(required=False, allow_null=True)
