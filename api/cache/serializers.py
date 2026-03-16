# api/cache/serializers.py
"""
Beautiful Cache Serializers - DRF serializers with nice structure
"""
from rest_framework import serializers


class CacheStatsSerializer(serializers.Serializer):
    """Cache statistics - for API responses"""
    backend = serializers.CharField(help_text="Cache backend name")
    status = serializers.CharField(help_text="Service status")
    keys_count = serializers.IntegerField(required=False, allow_null=True)
    memory_used = serializers.CharField(required=False, allow_null=True)
    hits = serializers.IntegerField(required=False, allow_null=True)
    misses = serializers.IntegerField(required=False, allow_null=True)
    uptime_seconds = serializers.IntegerField(required=False, allow_null=True)
    redis_version = serializers.CharField(required=False, allow_null=True)


class CacheInvalidateSerializer(serializers.Serializer):
    """Serializer for cache invalidation requests"""
    pattern = serializers.CharField(max_length=200, help_text="Key pattern to invalidate (e.g. user:123:*)")
    operation = serializers.CharField(
        max_length=50,
        required=False,
        help_text="Operation type (user_update, task_delete, etc.)"
    )


class CacheHealthSerializer(serializers.Serializer):
    """Cache health check response"""
    healthy = serializers.BooleanField()
    backend = serializers.CharField()
    message = serializers.CharField(required=False)


class CacheBackendSerializer(serializers.Serializer):
    """Single backend info with badge-ready fields"""
    name = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
