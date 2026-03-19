from rest_framework import serializers
from .models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from django.contrib.auth import get_user_model


User = get_user_model()


class RateLimitConfigSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = RateLimitConfig
        fields = [
            'id', 'name', 'rate_limit_type', 'requests_per_unit',
            'time_unit', 'time_value', 'user', 'user_username',
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
        # Validate that at least one target field is set
        target_fields = ['user', 'endpoint', 'ip_address', 'task_type', 'offer_wall']
        if not any(data.get(field) for field in target_fields):
            raise serializers.ValidationError(
                "কমপক্ষে একটি টার্গেট ফিল্ড (user, endpoint, ip_address, task_type, offer_wall) সেট করতে হবে"
            )
        
        # Validate rate limit values
        if data['requests_per_unit'] <= 0:
            raise serializers.ValidationError("অনুরোধ সংখ্যা ০ এর চেয়ে বড় হতে হবে")
        
        if data['time_value'] <= 0:
            raise serializers.ValidationError("সময় মান ০ এর চেয়ে বড় হতে হবে")
        
        return data


class RateLimitLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    config_name = serializers.CharField(source='config.name', read_only=True)
    
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
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserRateLimitProfile
        fields = [
            'id', 'user', 'email', 'is_premium',
            'premium_until', 'custom_daily_limit', 'custom_hourly_limit',
            'total_requests', 'blocked_requests', 'last_request_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['total_requests', 'blocked_requests', 
                          'last_request_at', 'created_at', 'updated_at']


class RateLimitBulkUpdateSerializer(serializers.Serializer):
    configs = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'update'],
        required=True
    )
    
    def validate_configs(self, value):
        for config in value:
            if 'id' not in config:
                raise serializers.ValidationError("প্রতিটি কনফিগারেশনে id ফিল্ড প্রয়োজন")
        return value


class RateLimitStatsSerializer(serializers.Serializer):
    timeframe = serializers.CharField()
    total_requests = serializers.IntegerField()
    blocked_requests = serializers.IntegerField()
    allowed_requests = serializers.IntegerField()
    block_rate = serializers.FloatField()
    
    class Meta:
        fields = ['timeframe', 'total_requests', 'blocked_requests', 
                 'allowed_requests', 'block_rate']