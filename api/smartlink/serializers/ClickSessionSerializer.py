from rest_framework import serializers
from api.smartlink.models.click import ClickSession


class ClickSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for ClickSession records.
    Sessions are created automatically by the redirect engine.
    Read-only for external callers.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ClickSession
        fields = [
            'id',
            'session_id',
            'smartlink',
            'smartlink_slug',
            'ip',
            'user_agent',
            'country',
            'device_type',
            'click_count',
            'first_seen',
            'last_seen',
            'duration_seconds',
        ]
        read_only_fields = fields

    def get_duration_seconds(self, obj):
        """Total session duration from first to last click in seconds."""
        if obj.first_seen and obj.last_seen:
            delta = obj.last_seen - obj.first_seen
            return round(delta.total_seconds())
        return 0


class ClickSessionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing sessions — omits user_agent and raw fields.
    Used in admin session browsing and publisher analytics.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)

    class Meta:
        model = ClickSession
        fields = [
            'id',
            'session_id',
            'smartlink_slug',
            'country',
            'device_type',
            'click_count',
            'first_seen',
            'last_seen',
        ]
        read_only_fields = fields
